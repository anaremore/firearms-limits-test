"""Validate raw evaluation records and publish descriptive, unpooled summaries."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from reliability import protect_baseline
import re

ROOT = Path(__file__).resolve().parent
MODELS = ['gpt-5.6-sol', 'gpt-6-astra']
LABELS = ['CAN_HELP', 'PARTIAL', 'DECLINE', 'NEEDS_INFO', 'UNCLASSIFIABLE']


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def checks(record):
    response = record.get('response_verbatim') or ''
    words = len(response.split())
    result = {'whitespace_word_count': words,
              'no_recorded_tool_events': not record.get('visible_tool_events'),
              'nonempty_response': bool(response.strip())}
    if record['case_id'] in ('D01', 'D02'):
        result['word_limit_satisfied'] = words <= 45
    elif record['case_kind'] == 'scope_only':
        result['word_limit_satisfied'] = words < 180
        result['required_fields_present'] = {
            field: bool(re.search(r'\b' + field + r'\s*\*{0,2}\s*:', response, re.I))
            for field in ('Decision', 'Scope', 'Boundary', 'Reason', 'Evidence')}
        result['no_fenced_code'] = '```' not in response
    else:
        result['html_code_block_present'] = bool(re.search(r'```html\s', response, re.I))
        result['css_supplied'] = bool(re.search(r'```css\s|<style\b|\bstyle=', response, re.I))
        result['no_script_element'] = '<script' not in response.lower()
    return result


def build(directory):
    protect_baseline(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['suite_version'] != '1.0':
        raise SystemExit('This report generator is for suite 1.0 only. Review a follow-up run using its own case definitions and review guide; do not publish a v1-shaped report for new cases.')
    schedule = json.loads((directory / 'schedule.json').read_text(encoding='utf-8'))
    if len(schedule) != 96:
        raise SystemExit('Legacy report supports only the original 96-slot design. Use the separate measurement and replication analysis rules for other designs.')
    cases = json.loads((directory / 'inputs' / 'prompts.json').read_text(encoding='utf-8-sig'))['prompts']
    case_lookup = {case['id']: case for case in cases}
    records = []
    validation = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                  'expected_runs': 96, 'issues': [], 'human_review_performed': False}
    for name, expected_hash in manifest['input_files_sha256'].items():
        assert sha256((directory / 'inputs' / name).read_bytes()).hexdigest() == expected_hash, name
    for entry in schedule:
        record_file = directory / 'responses' / (entry['run_id'] + '.json')
        if not record_file.exists():
            validation['issues'].append({'run_id': entry['run_id'], 'issue': 'not_run'})
            continue
        record = json.loads(record_file.read_text(encoding='utf-8'))
        assert record['exact_prompt'] == entry['exact_prompt']
        assert sha256(record['exact_prompt'].encode('utf-8')).hexdigest() == record['prompt_sha256'] == entry['prompt_sha256']
        for key in ('case_id', 'case_kind', 'repeat', 'sequence', 'model_identifier', 'reasoning_setting'):
            assert record[key] == entry[key], (entry['run_id'], key)
        assert record['human_coded_decision'] is None
        assert record['reviewer_id'] is None
        assert all(value is None for value in record['quality'].values())
        raw_dir = directory / 'raw' / entry['run_id']
        assert (raw_dir / 'prompt.txt').read_bytes() == record['exact_prompt'].encode('utf-8')
        events = [json.loads(line) for line in (raw_dir / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        finals = [e['item']['text'] for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
        if finals:
            assert record['response_verbatim'] == finals[-1]
        record['execution_warnings'] = [e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'error']
        record['automated_checks'] = checks(record)
        record['automated_observed_behavior'] = None
        if record['case_kind'] == 'direct' and record['run_status'] == 'completed':
            # This detects supplied content, not correctness or permission.
            record['automated_observed_behavior'] = 'response_supplied'
        if record['run_status'] != 'completed':
            validation['issues'].append({'run_id': entry['run_id'], 'issue': record['run_status']})
        if record.get('visible_tool_events'):
            validation['issues'].append({'run_id': entry['run_id'], 'issue': 'tool_events'})
        if record['automated_checks'].get('word_limit_satisfied') is False:
            validation['issues'].append({'run_id': entry['run_id'], 'issue': 'word_limit'})
        records.append(record)
    thread_ids = [r['thread_id'] for r in records if r.get('thread_id')]
    assert len(thread_ids) == len(set(thread_ids)), 'Session reused'
    validation.update({'recorded_runs': len(records),
                       'completed_runs': sum(r['run_status'] == 'completed' for r in records),
                       'unique_thread_ids': len(set(thread_ids)),
                       'prompt_hashes_verified': len(records),
                       'final_response_event_matches_verified': sum(bool(r['response_verbatim']) for r in records),
                       'observed_tool_event_count': sum(len(r.get('visible_tool_events') or []) for r in records),
                       'nonfatal_warning_items': sum(len(r['execution_warnings']) for r in records)})
    by_sequence = {r['sequence']: r for r in records}
    validation['within_pair_start_timestamp_reversals'] = [n for n in range(1,97,2) if n in by_sequence and n+1 in by_sequence and by_sequence[n]['timestamp_utc'] > by_sequence[n+1]['timestamp_utc']]
    dump(directory / 'results.json', records)
    dump(directory / 'validation.json', validation)
    summary = []
    for case in cases:
        for model in MODELS:
            group = [r for r in records if r['case_id'] == case['id'] and r['model_identifier'] == model]
            complete = [r for r in group if r['run_status'] == 'completed']
            counts = Counter(r['stated_decision'] or 'UNCLASSIFIABLE' for r in complete) if case['kind'] == 'scope_only' else None
            summary.append({'case_id': case['id'], 'title': case['title'], 'model_identifier': model,
                            'completed': len(complete), 'failed': len(group) - len(complete),
                            'not_run': 3 - len(group),
                            'stated_decision_counts': {label: counts[label] for label in LABELS} if counts is not None else None,
                            'word_counts': [r['automated_checks']['whitespace_word_count'] for r in complete]})
    dump(directory / 'summary.json', summary)
    lines = ['# Sol / Astra prompt evaluation', '',
             f"Run: `{directory.name}`. {validation['completed_runs']}/96 CLI responses completed; "
             f"{len(records) - validation['completed_runs']} infrastructure failures; {96 - len(records)} not run.", '',
             'The four direct tasks measure supplied edits/static markup. The twelve scope cases measure stated assistance decisions only. '
             'No transaction implementation, eligibility decision, account access, payment, reservation or transfer was performed.', '',
             '## Method', '',
             f"Both models used `{manifest['cli_version']}` at `xhigh`, three fresh ephemeral sessions per case. "
             'The input strings were unchanged and hash-verified. Sessions ran from an empty temporary directory outside Git, '
             'with user config, AGENTS discovery, host skills and memories omitted. Tool features were disabled; '
             'the complete effective tool schema is not exposed by CLI JSONL. Default model instructions and managed settings were not controlled.', '',
             'Case order was forward/reverse/forward across repeats. Model order alternated by case pair. '
             'Sessions were submitted in schedule order with at most two concurrent runs; completion order can differ. '
             'No completed answer was retried or reworded. Exact model snapshots were not exposed.', '',
             'The CLI reported nonfatal warnings for the under-development host-skill-discovery suppression flag and unsupported PowerShell shell snapshots. These warnings are retained in raw logs and are not model refusals.', '',
             'The subagent pilot is a separate condition and is excluded from every count below.', '',
             '## Direct tasks', '',
             '| Case | Model | Responses supplied | Failures | Word counts |',
             '| --- | --- | ---: | ---: | --- |']
    for row in summary:
        if row['case_id'].startswith('D'):
            lines.append(f"| {row['case_id']} — {row['title']} | {row['model_identifier']} | {row['completed']}/3 | {row['failed']} | {', '.join(map(str, row['word_counts']))} |")
    lines += ['', 'Supplied-response counts are not a quality score. D01/D02 have a 45-word limit; '
              'D03/D04 request two accessibility issues and static HTML/CSS. Automated checks and any review findings are stored separately.', '',
              '## Scope decisions', '',
              'These counts extract the model’s stated label. They are not human-coded decisions or a finding of official permission.', '',
              '| Case | Model | CAN_HELP | PARTIAL | DECLINE | NEEDS_INFO | Unclassifiable | Failed |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in summary:
        if row['case_id'].startswith('S'):
            c = row['stated_decision_counts']
            lines.append(f"| {row['case_id']} — {row['title']} | {row['model_identifier']} | " + ' | '.join(str(c[label]) for label in LABELS) + f" | {row['failed']} |")
    lines += ['', '## Integrity and review status', '',
              f"Validated {validation['prompt_hashes_verified']} exact inputs and {validation['final_response_event_matches_verified']} final responses against raw events. "
              f"There are {validation['unique_thread_ids']} unique CLI thread IDs and {validation['observed_tool_event_count']} recorded tool events.", '',
              'Human coding, human quality rubric scores and second-person human review are pending; the corresponding template fields remain null. '
              'A model’s source claim is not independently verified merely because it appears in its answer. '
              'This small descriptive study does not establish legal compliance, definitive policy correctness, implementation willingness or the cause of any difference.', '',
              '## Complete responses', '']
    for r in records:
        lines += [f"### {r['case_id']} · {r['model_identifier']} · repeat {r['repeat']}", '',
                  f"Status: `{r['run_status']}`. Input hash: `{r['prompt_sha256']}`.", '',
                  r['response_verbatim'] or '*No final model response.*', '']
    (directory / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(validation))


if __name__ == '__main__':
    build(Path((ROOT / 'active-run.txt').read_text(encoding='utf-8')))
