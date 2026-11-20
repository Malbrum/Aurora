"""CLI: poll (Gmail → agent → lager), show (siste forslag), replay (syntetisk tråd fra JSON), outcome."""
import json
import sys
from pathlib import Path

from agentic import config as cfg
from agentic.agent import as_markdown, run_case
from agentic.brp import BRP, FixtureBRP
from agentic.store import Store


def client_for(config):
    """Nøkkel fra .env.agentic hvis satt; ellers SDK-ens egen oppslag (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN
    eller en lagret `ant auth login`-profil). Bjørn legger inn nøkkelen selv. Feilen kommer før første kall."""
    import os
    import anthropic
    profile = Path.home() / '.config/anthropic'
    if not (config.anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
            or profile.exists()):
        sys.exit('Ingen Anthropic-innlogging funnet. Sett ANTHROPIC_API_KEY i .env.agentic eller kjør `ant auth login`.')
    return anthropic.Anthropic(api_key=config.anthropic_api_key or None)


def poll(config):
    from agentic.gmail import Gmail
    gmail = Gmail(config.gmail_account, config.gmail_channel, config.gmail_client_id, config.gmail_client_secret,
                  config.gmail_refresh_token)
    brp = BRP(config.brp_base_url, config.brp_username, config.brp_password)
    store, client = Store(config.db_path), client_for(config)
    try:
        for thread_id in gmail.thread_ids(config.gmail_days):
            messages = gmail.thread(thread_id)
            if not messages or store.seen(thread_id, messages[-1]['id']):
                continue
            if messages[-1]['from'].endswith('@' + config.gmail_channel.rsplit('@', 1)[-1]):
                store.mark(thread_id, messages[-1]['id'], 'answered_by_staff')
                continue
            proposal, calls, usage = run_case(client, config, messages, brp)
            store.add_proposal(thread_id, proposal, model=config.model, tool_calls=calls, usage=usage)
            store.mark(thread_id, messages[-1]['id'], 'needs_human' if proposal['needs_human'] else 'proposed')
            print(f'{thread_id}: {proposal["kind"]} ({"menneske" if proposal["needs_human"] else "klar"})')
    finally:
        gmail.close(), brp.close(), store.close()


def replay(config, path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    proposal, calls, usage = run_case(client_for(config), config, data['thread'], FixtureBRP(data['brp']))
    print(as_markdown(proposal, calls, usage))
    if 'expected_kind' in data:
        print('\nForventet:', data['expected_kind'], '→', 'TREFF' if proposal['kind'] == data['expected_kind'] else 'BOM')


def show(config):
    store = Store(config.db_path)
    for p in store.proposals(20):
        print(f"#{p['id']} {p['created_at']} {p['thread_id']} {p['kind']} "
              f"{'menneske' if p['needs_human'] else 'klar'} {p['confidence']:.2f} utfall={p['outcome'] or '-'}")
        print('  ', (p['summary'] or '').replace('\n', ' ')[:200])
    store.close()


def main(argv):
    config = cfg.load()
    command = argv[1] if len(argv) > 1 else 'show'
    if command == 'poll':
        poll(config)
    elif command == 'replay':
        replay(config, argv[2])
    elif command == 'outcome':
        store = Store(config.db_path)
        store.set_outcome(int(argv[2]), argv[3])
        store.close()
    else:
        show(config)


if __name__ == '__main__':
    main(sys.argv)
