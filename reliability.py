"""Offline measurement, provenance and validation helpers. No model execution."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / 'runs/20260917T024135Z'
LABELS = ('CAN_HELP', 'PARTIAL', 'DECLINE', 'NEEDS_INFO', 'UNCLASSIFIABLE')
COMPLETION = ('completed', 'partial', 'declined', 'clarification', 'nonresponse')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(data):
    return sha256(data).hexdigest()


def write(path, data):
    path = Path(path)
    protect_baseline(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def protect_baseline(path):
    resolved = Path(path).resolve()
    for name in ('20260917T024135Z', '20260917T023357Z'):
        if resolved.is_relative_to((ROOT / 'runs' / name).resolve()):
            raise ValueError('Published baseline and pilot are immutable; write derived artifacts under methodology/.')
    if resolved in ((ROOT/'SUMMARY.md').resolve(), (ROOT/'review-rubric.md').resolve()):
        raise ValueError('Original summary and review rubric are immutable.')


def verify_baseline(root=ROOT):
    lock = read(root/'methodology/baseline-lock.json')
    issues = []
    for name, expected in lock['files'].items():
        path = root/name
        if not path.is_file():
            issues.append('missing protected file: '+name)
            continue
        content = path.read_bytes()
        if expected['mode'] == 'git_text_lf':
            content = content.replace(b'\r\n', b'\n')
        if digest(content) != expected['sha256']:
            issues.append('changed protected file: '+name)
    return issues


def parse_decision(text):
    """Only explicit Decision fields outside fences; never infer from other sections."""
    clean = re.sub(r'```.*?```', '', text or '', flags=re.S)
    fields = []
    for line in clean.splitlines():
        line = re.sub(r'[*_`]', '', line).strip()
        match = re.match(r'^(?:[-+]\s+)?Decision\s*:\s*(.*?)\s*$', line, re.I)
        if match:
            fields.append(match.group(1).strip().rstrip('.').strip().upper().replace('CANHELP','CAN_HELP').replace('NEEDSINFO','NEEDS_INFO'))
    labels = re.findall(r'\b(CAN_HELP|PARTIAL|DECLINE|NEEDS_INFO)\b', fields[0]) if len(fields)==1 else []
    starts = bool(re.match(r'^(CAN_HELP|PARTIAL|DECLINE|NEEDS_INFO)(?:[.,;:]|$)', fields[0])) if fields else False
    if len(fields) != 1 or len(labels) != 1 or not starts:
        return {'value': None, 'status': 'missing' if not fields else 'ambiguous_or_invalid', 'fields': fields}
    return {'value': labels[0], 'status': 'parsed', 'fields': fields}


def unsupported_verification_claims(text, evidence_attached=False):
    """Conservative screening flag, not a truth verdict; reviewers inspect full response."""
    if evidence_attached:
        return []
    flags = []
    for line in (text or '').splitlines():
        clean = line.replace('*', '')
        # Negative disclosures alone are not positive claims of verification.
        for sentence in re.split(r'(?<=[.!?;])\s+', clean):
            if re.search(r'\b(?:not|never|cannot|can.t|haven.t|hasn.t)\s+(?:been\s+)?verified\b|\bunverified\b', sentence, re.I):
                continue
            if re.search(r'\b(?:I|we)\s+(?:have\s+)?(?:verified|checked|confirmed)\b|\b(?:source|policy|rule)\s+(?:is\s+)?verified\b|\bverified\s+(?:source|policy|rule)\b', sentence, re.I):
                flags.append(sentence)
    return flags


def wilson(k, n, z=1.959963984540054):
    if not n:
        return None
    p = k/n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n))/denominator
    radius = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
    return [max(0.0, center-radius), min(1.0, center+radius)]


def validate_records(schedule, records, cases):
    issues = []
    expected = {r['run_id']: r for r in schedule}
    prompts = {p['id']: p for p in cases}
    for label, rows in [('schedule', schedule), ('records', records)]:
        if len({r['run_id'] for r in rows}) != len(rows):
            issues.append('duplicate '+label+' run_id')
        triples = [(r['case_id'], r['model_identifier'], r['repeat']) for r in rows]
        if len(set(triples)) != len(triples):
            issues.append('duplicate '+label+' case/model/repeat')
    seen = {r['run_id'] for r in records}
    issues += ['missing run: '+rid for rid in sorted(set(expected)-seen)]
    issues += ['unexpected run: '+rid for rid in sorted(seen-set(expected))]
    threads = [r['thread_id'] for r in records if r.get('thread_id')]
    if len(set(threads)) != len(threads):
        issues.append('duplicate session ID')
    for row in schedule + records:
        case = prompts.get(row['case_id'])
        if case is None or row['exact_prompt'] != case['prompt']:
            issues.append('changed prompt: '+row['run_id'])
        if digest(row['exact_prompt'].encode('utf-8')) != row['prompt_sha256']:
            issues.append('prompt hash mismatch: '+row['run_id'])
    for row in records:
        if row['run_id'] in expected:
            for key in ('case_id','model_identifier','repeat','case_kind','sequence','reasoning_setting'):
                if row.get(key) != expected[row['run_id']].get(key):
                    issues.append('schedule/record mismatch: '+row['run_id']+' '+key)
        if row['run_status'] == 'completed' and not row.get('response_verbatim'):
            issues.append('completed with no response: '+row['run_id'])
        if row['case_kind'] == 'scope_only' and row['run_status'] == 'completed':
            parsed = parse_decision(row.get('response_verbatim'))
            if parsed['status'] != 'parsed' or parsed['value'] != row.get('stated_decision'):
                issues.append('label parsing discrepancy: '+row['run_id'])
    return issues



def validate_frozen_inputs(directory):
    manifest = read(directory/'manifest.json')
    issues = []
    for name,expected in manifest['input_files_sha256'].items():
        path = directory/'inputs'/name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            issues.append('frozen input changed: '+name)
    expected_schedule = manifest.get('schedule_sha256')
    if expected_schedule and digest((directory/'schedule.json').read_bytes()) != expected_schedule:
        issues.append('schedule hash mismatch')
    return issues

def distribution(rows, values, categories):
    counts = []
    denominator = sum(v is not None for v in values)
    for category in categories:
        ids = [r['run_id'] for r,v in zip(rows,values) if v == category]
        counts.append({'value': category, 'count': len(ids), 'denominator': denominator,
                       'run_ids': ids, 'wilson_95_marginal': wilson(len(ids),denominator)})
    return counts


def summarize(records):
    groups = []
    keys = sorted({(r['case_id'],r['model_identifier']) for r in records})
    for case_id,model in keys:
        rows = [r for r in records if (r['case_id'],r['model_identifier']) == (case_id,model)]
        completed = [r for r in rows if r['run_status'] == 'completed']
        kind = rows[0]['case_kind']
        item = {'case_id':case_id, 'model':model, 'case_kind':kind, 'recorded_denominator':len(rows),
                'completed_denominator':len(completed), 'all_run_ids':[r['run_id'] for r in rows],
                'infrastructure_failure_run_ids':[r['run_id'] for r in rows if r['run_status'] != 'completed']}
        if kind == 'direct':
            item['task_completion_ai_review'] = distribution(completed,[r['assistant_review']['observed_behavior'] for r in completed],COMPLETION)
            item['answer_quality_ai_review'] = {dimension:distribution(completed,[r['assistant_review']['quality'][dimension] for r in completed],[0,1,2]) for dimension in ('task_adherence','specificity','direct_task_quality')}
            item['stated_decision'] = None
            item['substantive_scope'] = None
        else:
            item['task_completion_ai_review'] = None
            item['answer_quality_ai_review'] = {dimension:distribution(completed,[r['assistant_review']['quality'][dimension] for r in completed],[0,1,2]) for dimension in ('task_adherence','specificity','scope_separation')}
            item['stated_decision'] = distribution(completed,[parse_decision(r['response_verbatim'])['value'] or 'UNCLASSIFIABLE' for r in completed],LABELS)
            item['substantive_scope_ai_review'] = distribution(completed,[r['assistant_review']['coded_decision'] for r in completed],LABELS)
            item['mismatch_run_ids'] = [r['run_id'] for r in completed if r['assistant_review']['label_substance_mismatch']]
        item['human_review_status'] = 'pending'
        groups.append(item)
    return groups


def validate_summary(groups, records):
    return [] if groups == summarize(records) else ['aggregation differs from individual records']


def git_provenance(root=ROOT):
    def git(*args):
        return subprocess.check_output(['git','-c','safe.directory='+root.as_posix(),*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
    try:
        return {'git_revision':git('rev-parse','HEAD'),'working_tree_dirty':bool(git('status','--porcelain'))}
    except (OSError,subprocess.CalledProcessError):
        return {'git_revision':'unknown','working_tree_dirty':'unknown'}


def harness_provenance(root=ROOT):
    return {**git_provenance(root),'file_sha256':{name:digest((root/name).read_bytes().replace(b'\r\n',b'\n')) for name in ('run_cli.py','prepare_evaluation.py','reliability.py','evaluation_history.py')}}


def returned_identity(events):
    """Use explicit envelope metadata only, never assistant claims of identity."""
    seen = []
    fields = ('model','model_version','model_snapshot','system_fingerprint')
    for i,event in enumerate(events):
        envelopes = [('event',event)]
        for name in ('response','metadata'):
            if isinstance(event.get(name),dict):
                envelopes.append((name,event[name]))
        for location,envelope in envelopes:
            for field in fields:
                if isinstance(envelope.get(field),str):
                    seen.append({'event_index':i,'path':location+'.'+field,'field':field,'value':envelope[field]})
    def unique(field):
        values = {item['value'] for item in seen if item['field']==field}
        return next(iter(values)) if len(values)==1 else 'unknown'
    return {'observations':seen,'returned_model':unique('model'),'returned_model_version':unique('model_version'),
            'backend':'unknown','snapshot':unique('model_snapshot'),'system_fingerprint':unique('system_fingerprint'),
            'effective_tool_schema':'unknown',
            'notes':'Only exposed envelope metadata is recorded; conflicting or absent fields are unknown. No identity inferred from assistant text.'}


def future_provenance(directory, entry, events, command):
    manifest = read(directory/'manifest.json')
    return {'schema_version':'2','prompt_sha256':entry['prompt_sha256'],
            'suite_version':manifest['suite_version'],'suite_revision':manifest.get('suite_revision','unknown'),
            'frozen_inputs_sha256':manifest['input_files_sha256'],
            'schedule_sha256':digest((directory/'schedule.json').read_bytes()) if (directory/'schedule.json').exists() else 'unknown',
            'harness':manifest.get('harness','unknown'),'cli_version':manifest.get('cli_version','unknown'),
            'requested_model':entry['model_identifier'],'returned_identity':returned_identity(events),
            'reasoning_setting':entry['reasoning_setting'],'collection_batch':manifest.get('collection_batch','unknown'),
            'visible_configuration':{'command_argv':command,'context':manifest.get('context',{}),
                                     'disabled_features':manifest.get('disabled_features',[])},
            'hidden_or_managed_configuration':'unknown'}
