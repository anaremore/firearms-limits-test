"""Prepare model-blinded content-review packets without changing raw responses."""
import argparse
import json
from pathlib import Path
from reliability import protect_baseline
import secrets

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--track', choices=('direct','scope','all'), default='all')
args = parser.parse_args()
folder = Path((ROOT / 'active-run.txt').read_text(encoding='utf-8'))
protect_baseline(folder)
results = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
selected = [r for r in results if args.track=='all' or (r['case_kind']=='direct')==(args.track=='direct')]
assert len(selected) == {'direct':24,'scope':72,'all':96}[args.track]
assert all(r['run_status']=='completed' for r in selected)
packet_name = ('review-packet' if args.track=='all' else args.track+'-review-packet')+'.json'
assert not (folder / packet_name).exists(), 'Preserve existing review packet'
map_path = folder / 'review-map.json'
mapping = json.loads(map_path.read_text(encoding='utf-8')) if map_path.exists() else {}
reverse = {run_id:blind_id for blind_id,run_id in mapping.items()}
rows = []
for result in selected:
    blind_id = reverse.get(result['run_id']) or secrets.token_hex(6)
    mapping[blind_id] = result['run_id']
    rows.append({'blind_id': blind_id, 'case_id': result['case_id'],
                 'case_kind': result['case_kind'], 'exact_prompt': result['exact_prompt'],
                 'response_verbatim': result['response_verbatim'],
                 'automated_checks': result['automated_checks']})
secrets.SystemRandom().shuffle(rows)
for name, value in [(packet_name,rows),('review-map.json',mapping)]:
    (folder / name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'Prepared {len(rows)} blinded {args.track} responses.')
