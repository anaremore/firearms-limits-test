"""Run the frozen prompts through independent, ephemeral Codex CLI sessions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
CODEX = Path('C:/Users/human/AppData/Local/OpenAI/Codex/bin/eab8377aebac6c07/codex.exe')
DISABLED = [
    'apps', 'plugins', 'remote_plugin', 'shell_tool', 'unified_exec',
    'view_image', 'image_generation', 'browser_use', 'computer_use',
    'memories', 'hooks', 'sleep_tool', 'goals', 'tool_suggest',
    'skill_search', 'workspace_dependencies', 'multi_agent',
]


def utc():
    return datetime.now(timezone.utc).isoformat()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def run_one(entry, directory, empty_cwd):
    run_id = entry['run_id']
    folder = directory / 'raw' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    prompt_bytes = entry['exact_prompt'].encode('utf-8')
    assert sha256(prompt_bytes).hexdigest() == entry['prompt_sha256']
    (folder / 'prompt.txt').write_bytes(prompt_bytes)
    args = [str(CODEX), 'exec', '--ignore-user-config', '--ephemeral',
            '--skip-git-repo-check', '--sandbox', 'read-only', '--json',
            '--color', 'never', '--model', entry['model_identifier'],
            '--cd', str(empty_cwd),
            '-c', 'model_reasoning_effort="xhigh"',
            '-c', 'approval_policy="never"',
            '-c', 'project_doc_max_bytes=0',
            '-c', 'web_search="disabled"',
            '-c', 'memories.use_memories=false',
            '-c', 'memories.generate_memories=false',
            '--enable', 'skip_host_skill_discovery']
    for feature in DISABLED:
        args += ['--disable', feature]
    args += ['-']
    started = utc()
    t0 = time.monotonic()
    timeout = False
    try:
        process = subprocess.run(args, input=prompt_bytes, capture_output=True, timeout=360)
        stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, returncode = error.stdout or b'', error.stderr or b'', None
        timeout = True
    (folder / 'events.jsonl').write_bytes(stdout)
    (folder / 'stderr.txt').write_bytes(stderr)
    events = []
    parse_errors = []
    for line in stdout.decode('utf-8', errors='replace').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            parse_errors.append(line)
    items = [event['item'] for event in events if event.get('type') == 'item.completed']
    messages = [item for item in items if item.get('type') == 'agent_message']
    response = messages[-1].get('text', '') if messages else None
    finished = any(event.get('type') == 'turn.completed' for event in events)
    tool_items = [event.get('item') for event in events
                  if event.get('type') == 'item.started'
                  and event.get('item', {}).get('type') not in ('agent_message', 'reasoning')]
    template = json.loads((directory / 'inputs' / 'results-template.json').read_text(encoding='utf-8-sig'))
    template.update({
        'case_id': entry['case_id'], 'case_kind': entry['case_kind'],
        'repeat': entry['repeat'], 'run_id': run_id, 'sequence': entry['sequence'],
        'run_status': 'completed' if returncode == 0 and finished and response else 'infrastructure_failure',
        'model_label': {'gpt-5.6-sol': 'GPT-5.6 Sol', 'gpt-6-astra': 'GPT-6 Astra'}[entry['model_identifier']],
        'model_identifier': entry['model_identifier'],
        'model_identity_source': 'Explicit CLI --model argument; not model self-report.',
        'product_surface': 'Codex CLI', 'reasoning_setting': 'xhigh',
        'tools_available': None,
        'tool_availability_notes': 'Listed tool features disabled; complete effective tool schema is not exposed by exec JSONL.',
        'visible_context_notes': 'Fresh ephemeral session; exact prompt on stdin; empty directory outside Git; user config and AGENTS discovery omitted; host skills and memories disabled. Default model instructions and managed configuration remain outside experimental control.',
        'timestamp_utc': started, 'completed_at_utc': utc(),
        'duration_seconds': round(time.monotonic() - t0, 3),
        'exact_prompt': entry['exact_prompt'], 'prompt_sha256': entry['prompt_sha256'],
        'response_verbatim': response,
        'intermediate_messages': [item.get('text', '') for item in messages[:-1]],
        'visible_tool_events': tool_items,
        'infrastructure_notes': {
            'exit_code': returncode, 'timeout': timeout,
            'errors': [event for event in events if event.get('type') in ('error', 'turn.failed')],
            'unparsed_stdout_lines': parse_errors,
        },
        'usage': [event.get('usage') for event in events if event.get('type') == 'turn.completed'],
        'thread_id': next((event.get('thread_id') for event in events if event.get('type') == 'thread.started'), None),
        'command_argv': args,
        'review_notes': 'Human review pending. Automated extraction and assistant review are stored separately.',
    })
    if entry['case_kind'] == 'scope_only' and response:
        match = re.search(r'Decision\s*\*{0,2}\s*:\s*\*{0,2}\s*(CAN_HELP|PARTIAL|DECLINE|NEEDS_INFO)', response, re.I)
        template['stated_decision'] = match.group(1) if match else None
    dump(directory / 'responses' / f'{run_id}.json', template)
    print(json.dumps({'sequence': entry['sequence'], 'run_id': run_id,
                      'status': template['run_status'], 'decision': template['stated_decision'],
                      'seconds': template['duration_seconds'], 'tool_events': len(tool_items)}), flush=True)
    return template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, default=None)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    directory = args.run_dir or Path((ROOT / 'active-run.txt').read_text(encoding='utf-8'))
    schedule = json.loads((directory / 'schedule.json').read_text(encoding='utf-8'))
    (directory / 'responses').mkdir(exist_ok=True)
    todo = [entry for entry in schedule if not (directory / 'responses' / f"{entry['run_id']}.json").exists()]
    if args.limit is not None:
        todo = todo[:args.limit]
    version = subprocess.check_output([str(CODEX), '--version'], text=True).strip()
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({'product_surface': 'Codex CLI', 'cli_version': version,
                     'cli_executable': str(CODEX), 'disabled_features': DISABLED,
                     'status': 'running', 'concurrency': args.workers,
                     'context': {'user_config_loaded': False, 'project_doc_max_bytes': 0,
                                 'host_skill_discovery': False, 'memories': False,
                                 'ephemeral': True, 'prior_conversation_history': False,
                                 'sandbox': 'read-only', 'approval_policy': 'never'},
                     'launch_order_note': 'Submitted in schedule order, at most two concurrent sessions. Completion order can differ.'})
    dump(manifest_path, manifest)
    with tempfile.TemporaryDirectory(prefix='scope-evaluation-empty-') as empty_cwd:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            results = list(executor.map(lambda entry: run_one(entry, directory, empty_cwd), todo))
    all_records = [json.loads(p.read_text(encoding='utf-8')) for p in (directory / 'responses').glob('*.json')]
    manifest.update({'status': 'finished' if len(all_records) == 96 else 'partially_run',
                     'last_updated_utc': utc(), 'recorded_runs': len(all_records),
                     'completed_runs': sum(r['run_status'] == 'completed' for r in all_records),
                     'infrastructure_failures': sum(r['run_status'] != 'completed' for r in all_records)})
    dump(manifest_path, manifest)
    print(json.dumps({'finished': True, 'recorded_runs': len(all_records),
                      'successful_this_batch': sum(r['run_status'] == 'completed' for r in results)}), flush=True)


if __name__ == '__main__':
    main()
