"""Freeze the supplied test pack and create a reproducible, unrun schedule."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

from evaluation_history import reject_unapproved_reruns

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'suites/v2'


def read_verified_suite(directory):
    suite = json.loads((directory / 'prompts.json').read_text(encoding='utf-8-sig'))
    markdown = (directory / 'prompts.md').read_text(encoding='utf-8-sig')
    blocks = re.findall(r'```text\n(.*?)\n```', markdown, flags=re.S)
    prompts = suite['prompts']
    assert prompts and len(prompts) == len(blocks)
    assert len({p['id'] for p in prompts}) == len(prompts)
    for prompt, block in zip(prompts, blocks):
        assert prompt['prompt'] == block, f"Markdown/JSON mismatch: {prompt['id']}"
    return suite, prompts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE,
                        help='Prompt pack directory; defaults to the new-only follow-up pack.')
    parser.add_argument('--validate-only', action='store_true',
                        help='Check inputs and rerun protection without creating a run or calling models.')
    parser.add_argument('--allow-reruns', action='store_true',
                        help='Use only after the user explicitly requests rerunning old prompts.')
    args = parser.parse_args()
    source = args.source.resolve()
    suite, prompts = read_verified_suite(source)
    reject_unapproved_reruns(ROOT, prompts, allow_reruns=args.allow_reruns)
    if args.validate_only:
        print(json.dumps({'suite_version': suite['suite_version'],
                          'input_pairs_verified': len(prompts),
                          'planned_runs_at_three_repeats': len(prompts) * 6,
                          'models_called': 0}))
        return
    now = datetime.now(timezone.utc)
    output = ROOT / 'runs' / now.strftime('%Y%m%dT%H%M%SZ')
    frozen = output / 'inputs'
    frozen.mkdir(parents=True)
    names = ['README.md', 'prompts.json', 'prompts.md', 'results-template.json']
    for optional in ('review-guide.json', 'baseline-references.json'):
        if (source / optional).exists():
            names.append(optional)
    for name in names:
        shutil.copyfile(source / name, frozen / name)
    suite, prompts = read_verified_suite(frozen)
    reject_unapproved_reruns(ROOT, prompts, allow_reruns=args.allow_reruns)
    models = ['gpt-5.6-sol', 'gpt-6-astra']
    schedule = []
    pair_index = 0
    for repeat in range(1, 4):
        cases = prompts[::-1] if repeat == 2 else prompts
        for case in cases:
            order = models if pair_index % 2 == 0 else models[::-1]
            for model in order:
                schedule.append({
                    'sequence': len(schedule) + 1,
                    'run_id': f"{case['id']}-{model}-r{repeat}",
                    'case_id': case['id'],
                    'case_kind': case['kind'],
                    'repeat': repeat,
                    'model_identifier': model,
                    'reasoning_setting': 'xhigh',
                    'prompt_sha256': sha256(case['prompt'].encode('utf-8')).hexdigest(),
                    'exact_prompt': case['prompt'],
                    'run_status': 'not_run',
                })
            pair_index += 1
    assert len(schedule) == len(prompts) * len(models) * 3
    manifest = {
        'suite_version': suite['suite_version'],
        'frozen_at_utc': now.isoformat(),
        'source_directory': str(source),
        'input_files_sha256': {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in sorted(frozen.iterdir())
        },
        'prompt_representations_match': True,
        'planned_runs': len(schedule),
        'status': 'prepared_not_run',
        'allow_reruns': args.allow_reruns,
        'product_surface': None,
        'notes': [
            'Original files preserved without modifications.',
            'Model order alternates for each case/repeat pair.',
            'Repeat 2 reverses case order; repeats 1 and 3 use source order.',
            'Human coding must remain null until a human actually reviews it.',
            'Scope cases are assessments only; no implementation is authorized by their text.',
        ],
    }
    for filename, data in [('manifest.json', manifest), ('schedule.json', schedule)]:
        (output / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (ROOT / 'active-run.txt').write_text(str(output), encoding='utf-8')
    print(json.dumps({'output_directory': str(output), 'input_pairs_verified': len(prompts), 'scheduled_runs': len(schedule)}))


if __name__ == '__main__':
    main()
