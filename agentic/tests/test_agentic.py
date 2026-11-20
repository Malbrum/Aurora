"""Testene kjører uten nettverk og uten nøkkel: en innspilt kjører kaller verktøyene slik modellen ville."""
import json
from pathlib import Path
from types import SimpleNamespace

from agentic.agent import run_case, thread_as_text
from agentic.brp import FixtureBRP
from agentic.config import Config
from agentic.store import Store
from agentic.tools import KINDS, Toolbox, is_sensitive

FIXTURE = json.loads((Path(__file__).parent.parent / 'fixtures/faktura-etter-oppsigelse.json').read_text(encoding='utf-8'))
CONFIG = Config('', 'test-model', None, 6, '', '', '', 'ms@roabadet.no', 'post@roabadet.no', '', '', '', 14, Path(':memory:'))


class ScriptedRunner:
    """Spiller av en liste verktøykall mot ekte verktøyobjekter og gir ett falskt svar per runde."""

    def __init__(self, script):
        self.script = script

    def __call__(self, tools, prompt):
        self.prompt, by_name = prompt, {t.name: t for t in tools}
        self.results = [by_name[name].call(args) for name, args in self.script]
        return [SimpleNamespace(stop_reason='end_turn', usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                                                                             cache_read_input_tokens=0))]


def test_tools_read_fixture_and_propose():
    runner = ScriptedRunner([
        ('lookup_member', {'email': 'kunde.syntetisk@example.invalid'}),
        ('get_subscriptions', {'customer_id': 9001}),
        ('get_invoices', {'customer_id': 9001}),
        ('propose', {'kind': 'invoice_question', 'summary': 'Dobbelt faktura for november.',
                     'backoffice_action': 'Krediter F-5002', 'reply_draft': 'Hei, vi krediterer F-5002.',
                     'needs_human': True, 'confidence': 0.8}),
    ])
    proposal, calls, usage = run_case(None, CONFIG, FIXTURE['thread'], FixtureBRP(FIXTURE['brp']), runner_factory=runner)
    assert proposal['kind'] == 'invoice_question' and proposal['needs_human'] and proposal['confidence'] == 0.8
    assert [c['tool'] for c in calls] == ['lookup_member', 'get_subscriptions', 'get_invoices', 'propose']
    assert 'F-5002' in runner.results[2] and '"debitedUntil": "2026-11-30"' in runner.results[1]
    assert usage == {'input_tokens': 100, 'output_tokens': 20, 'cache_read_input_tokens': 0, 'turns': 1}
    assert 'MEDLEM <kunde.syntetisk@example.invalid>' in runner.prompt


def test_invalid_kind_is_rejected_and_no_proposal_means_manual():
    runner = ScriptedRunner([('propose', {'kind': 'delete_customer', 'summary': '', 'backoffice_action': '',
                                          'reply_draft': '', 'needs_human': False, 'confidence': 1})])
    proposal, calls, _ = run_case(None, CONFIG, FIXTURE['thread'], FixtureBRP(FIXTURE['brp']), runner_factory=runner)
    assert 'Ugyldig kind' in runner.results[0] and proposal['needs_human'] and proposal['reason'] == 'no_proposal'
    assert calls == []  # avvist kall logges ikke som forslag


def test_sensitive_text_never_reaches_the_model():
    thread = [{**FIXTURE['thread'][0], 'body': 'Legen min har sykmeldt meg, kan jeg fryse?'}]
    called = []
    proposal, calls, usage = run_case(None, CONFIG, thread, FixtureBRP(FIXTURE['brp']),
                                      runner_factory=lambda *a: called.append(a) or [])
    assert called == [] and proposal['reason'] == 'sensitive_content' and proposal['needs_human']
    assert is_sensitive('konto 1234.56.78901') and is_sensitive('fnr 010190 12345') and not is_sensitive('Trekk 499 kr')


def test_staff_messages_are_labelled_and_tools_are_read_only():
    text = thread_as_text([{'from': 'ansatt@roabadet.no', 'date': 'd', 'subject': 's', 'body': 'Svar'}], 'post@roabadet.no')
    assert text.startswith('--- SENTERET')
    names = [t.name for t in Toolbox(FixtureBRP(FIXTURE['brp'])).tools()]
    assert names == ['lookup_member', 'get_subscriptions', 'get_invoices', 'propose'] and 'other' in KINDS


def test_store_tracks_threads_and_outcomes(tmp_path):
    store = Store(tmp_path / 'a.db')
    assert not store.seen('t1', 'm1')
    store.mark('t1', 'm1', 'proposed')
    assert store.seen('t1', 'm1') and not store.seen('t1', 'm2')
    store.add_proposal('t1', {'kind': 'info_request', 'summary': 's', 'backoffice_action': 'ingen', 'reply_draft': 'r',
                             'needs_human': False, 'confidence': 0.9}, model='m', tool_calls=[], usage={'input_tokens': 1})
    rows = store.proposals()
    assert rows[0]['kind'] == 'info_request' and json.loads(rows[0]['usage']) == {'input_tokens': 1}
    store.set_outcome(rows[0]['id'], 'resolved')
    assert store.proposals()[0]['outcome'] == 'resolved'
    store.close()
