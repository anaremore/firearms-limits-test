"""Freeze the supplied test pack and create a reproducible, unrun schedule."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = Path('Z:/Projects/quietshot/docs/research/model-scope-evaluation')


def main():
    now = datetime.now(timezone.utc)
    output = ROOT / 'runs' / now.strftime('%Y%m%dT%H%M%SZ')
    frozen = output / 'inputs'
    frozen.mkdir(parents=True)
    for name in ('README.md', 'prompts.json', 'prompts.md', 'results-template.json'):
        shutil.copyfile(SOURCE / name, frozen / name)
    suite = json.loads((frozen / 'prompts.json').read_text(encoding='utf-8-sig'))
    markdown = (frozen / 'prompts.md').read_text(encoding='utf-8-sig')
    blocks = re.findall(r'```text\n(.*?)\n```', markdown, flags=re.S)
    prompts = suite['prompts']
    assert len(prompts) == len(blocks) == 16
    assert len({p['id'] for p in prompts}) == 16
    for prompt, block in zip(prompts, blocks):
        assert prompt['prompt'] == block, f"Markdown/JSON mismatch: {prompt['id']}"
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
    assert len(schedule) == 96
    manifest = {
        'suite_version': suite['suite_version'],
        'frozen_at_utc': now.isoformat(),
        'source_directory': str(SOURCE),
        'input_files_sha256': {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in sorted(frozen.iterdir())
        },
        'prompt_representations_match': True,
        'planned_runs': 96,
        'status': 'prepared_not_run',
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
    print(json.dumps({'output_directory': str(output), 'input_pairs_verified': 16, 'scheduled_runs': 96}))


if __name__ == '__main__':
    main()
