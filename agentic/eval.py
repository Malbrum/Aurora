"""Evaluering: replay på alle fixtures, én linje per fixture og treffprosent. Krever modellnøkkel."""
import json
import os
import sys
from pathlib import Path

from agentic import config as cfg
from agentic.agent import run_case
from agentic.brp import FixtureBRP
from agentic.main import client_for

FIXTURES = Path(__file__).parent / 'fixtures'


def has_login(config):
    return bool(config.anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
                or (Path.home() / '.config/anthropic').exists())


def main(argv):
    config = cfg.load()
    if not has_login(config):
        sys.exit('Ingen ANTHROPIC_API_KEY i .env.agentic eller miljøet. Evalueringen kaller modellen og ble ikke kjørt.')
    client = client_for(config)
    paths = [Path(p) for p in argv[1:]] or sorted(FIXTURES.glob('*.json'))
    hits, total_in, total_out = 0, 0, 0
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        proposal, calls, usage = run_case(client, config, data['thread'], FixtureBRP(data['brp']))
        hit = proposal['kind'] == data['expected_kind']
        hits += hit
        total_in += usage.get('input_tokens', 0)
        total_out += usage.get('output_tokens', 0)
        print(f"{'TREFF' if hit else 'BOM  '} {path.stem:28} {proposal['kind']:17} forventet {data['expected_kind']:17} "
              f"{'menneske' if proposal['needs_human'] else 'klar    '} {proposal['confidence']:.2f} "
              f"verktøy={','.join(c['tool'] for c in calls) or 'ingen'} "
              f"tokens={usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)}")
        if not hit:
            print(f"      {proposal['summary']}")
    print(f'\nTreff: {hits}/{len(paths)} = {100 * hits / len(paths):.0f} %  tokens inn/ut: {total_in}/{total_out}')


if __name__ == '__main__':
    main(sys.argv)
