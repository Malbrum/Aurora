"""Én tråd inn, ett forslag ut. Løkken eies av SDK-ens tool runner; vi eier verktøyene og grensene."""
import json
from pathlib import Path

from agentic.tools import Toolbox, is_sensitive

SYSTEM = (Path(__file__).parent / 'prompt.md').read_text(encoding='utf-8')
BETAS = ['server-side-fallback-2026-07-01']


def thread_as_text(messages, channel):
    """Tråden som ren tekst. Egne svar fra senteret merkes, så modellen ser hva som allerede er sagt."""
    domain = channel.rsplit('@', 1)[-1]
    lines = []
    for m in messages:
        role = 'SENTERET' if m['from'].endswith('@' + domain) else 'MEDLEM'
        lines.append(f"--- {role} <{m['from']}> {m['date']} | {m['subject']}\n{m['body'].strip()}\n")
    return '\n'.join(lines)


def manual(reason, summary):
    return {'kind': 'other', 'summary': summary, 'backoffice_action': 'ingen', 'reply_draft': '',
            'needs_human': True, 'confidence': 0.0, 'reason': reason}


def run_case(client, config, messages, brp, *, runner_factory=None):
    """Returnerer (forslag, verktøykall, forbruk). Sensitivt innhold går aldri til modellen."""
    if any(is_sensitive(m['body']) for m in messages if not m['from'].endswith('@' + config.gmail_channel.rsplit('@', 1)[-1])):
        return manual('sensitive_content', 'Tråden inneholder helse-, bank- eller fødselsnummeropplysninger.'), [], {}
    box = Toolbox(brp)
    text = thread_as_text(messages, config.gmail_channel)
    make = runner_factory or (lambda tools, prompt: client.beta.messages.tool_runner(
        model=config.model, max_tokens=16000, system=SYSTEM, tools=tools, max_iterations=config.max_turns,
        betas=BETAS, fallbacks='default', inference_geo=config.inference_geo,
        messages=[{'role': 'user', 'content': prompt}]))
    runner = make(box.tools(), 'Behandle denne tråden og avslutt med propose.\n\n' + text)
    usage = {'input_tokens': 0, 'output_tokens': 0, 'cache_read_input_tokens': 0, 'turns': 0}
    last = None
    for message in runner:
        last = message
        usage['turns'] += 1
        for key in ('input_tokens', 'output_tokens', 'cache_read_input_tokens'):
            usage[key] += getattr(message.usage, key, 0) or 0
    if last is not None and last.stop_reason == 'refusal':
        return manual('refusal', 'Modellen avviste forespørselen.'), box.calls, usage
    if box.proposal is None:
        return manual('no_proposal', 'Agenten avsluttet uten forslag.'), box.calls, usage
    return box.proposal, box.calls, usage


def as_markdown(proposal, calls, usage):
    flag = 'MENNESKE MÅ INN' if proposal['needs_human'] else 'klar til kontroll'
    return (f"**{proposal['kind']}** · {flag} · sikkerhet {proposal['confidence']:.2f}\n\n"
            f"{proposal['summary']}\n\n**Back Office:** {proposal['backoffice_action']}\n\n"
            f"**Svarutkast:**\n{proposal['reply_draft']}\n\n"
            f"Verktøy: {', '.join(c['tool'] for c in calls) or 'ingen'} · tokens inn/ut: "
            f"{usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)}")
