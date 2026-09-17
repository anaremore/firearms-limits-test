"""Prevent repeating completed prompt text in another run without explicit opt-in."""
from hashlib import sha256
import json


def completed_prompt_hashes(root, exclude_run=None):
    excluded = exclude_run.resolve() if exclude_run is not None else None
    hashes = set()
    for record_path in (root / 'runs').glob('*/responses/*.json'):
        if excluded is not None and record_path.parent.parent.resolve() == excluded:
            continue
        record = json.loads(record_path.read_text(encoding='utf-8-sig'))
        if record.get('run_status') == 'completed':
            hashes.add(sha256(record['exact_prompt'].encode('utf-8')).hexdigest())
    return hashes


def reject_unapproved_reruns(root, entries, exclude_run=None, allow_reruns=False):
    if allow_reruns:
        return
    completed = completed_prompt_hashes(root, exclude_run)
    blocked = set()
    for entry in entries:
        prompt = entry['prompt'] if 'prompt' in entry else entry['exact_prompt']
        if sha256(prompt.encode('utf-8')).hexdigest() in completed:
            blocked.add(entry.get('case_id', entry.get('id', 'unknown')))
    if blocked:
        raise SystemExit('Old prompts are blocked from another run: ' + ', '.join(sorted(blocked))
                         + '. Reuse their saved results. Pass --allow-reruns only after an explicit user request.')
