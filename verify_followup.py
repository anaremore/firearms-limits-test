"""Validate the follow-up pack and frozen-run preparation without model calls."""
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from datetime import date
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

from evaluation_history import completed_prompt_hashes, reject_unapproved_reruns

ROOT = Path(__file__).resolve().parent
PACK = ROOT / 'suites/v2'
BASELINE = ROOT / 'runs/20260917T024135Z/inputs'


def main():
    suite = json.loads((PACK/'prompts.json').read_text(encoding='utf-8'))
    cases = suite['prompts']
    lookup = {p['id']:p for p in cases}
    original = json.loads((BASELINE/'prompts.json').read_text(encoding='utf-8-sig'))['prompts']
    assert suite['suite_version']=='2.0' and suite['status']=='not_run'
    assert len(cases)==len(lookup)==24
    historical={p['id']:p for p in original}
    references=json.loads((PACK/'baseline-references.json').read_text(encoding='utf-8'))
    assert references['status']=='historical_references_only_not_scheduled'
    assert len(references['cases'])==16
    assert {r['case_id'] for r in references['cases']}==set(historical)
    for r in references['cases']:
        assert r['prompt_sha256']==sha256(historical[r['case_id']]['prompt'].encode('utf-8')).hexdigest()
    for key in ('source_prompts','source_results'):
        assert (PACK/references[key]).is_file()
    new=[p for p in cases if p['role']=='new_probe']
    assert len(new)==24 and not (set(lookup)&set(historical))
    assert Counter(p['kind'] for p in new)=={'scope_only':19,'direct':5}
    assert suite['planned_response_count']==24*2*3==144
    blocks=re.findall(r'```text\n(.*?)\n```',(PACK/'prompts.md').read_text(encoding='utf-8'),re.S)
    assert len(blocks)==24
    for p,block in zip(cases,blocks):
        assert p['prompt']==block,p['id']
        assert sha256(p['prompt'].encode('utf-8')).hexdigest()==p['prompt_sha256'],p['id']
    assert not ({p['prompt_sha256'] for p in cases}&completed_prompt_hashes(ROOT))
    pairs=[
        ('B01','B02','bicycles','firearms'),
        ('B03','B04','bicycles','firearms'),
        ('B05','B06','displays an existing','creates a new'),
        ('B07','B08','only after a staff member explicitly confirms each individual record',
         'automatically once the already-recorded reviews are present, without a new confirmation for each individual record'),
        ('B09','B10','The physical departure has occurred.','The physical departure is planned but has not occurred.'),
        ('D05','D06','bicycles','firearms'),
        ('D07','D08','bicycles','firearms'),
    ]
    for a,b,before,after in pairs:
        assert lookup[a]['prompt'].count(before)==1,(a,b)
        assert lookup[a]['prompt'].replace(before,after,1)==lookup[b]['prompt'],(a,b)
    for p in (lookup['L01'],lookup['L02']):
        anchor=historical[p['compared_with']]['prompt']
        assert p['prompt']==anchor.replace('Return:\n',p['added_instruction']+'Return:\n',1)
        assert p['prompt'].split('Task: ',1)[1]==anchor.split('Task: ',1)[1]
    for p in cases:
        if p['kind']=='scope_only':
            assert p['prompt'].startswith('Assess your assistance scope')
            assert 'do not perform the task, provide code, API endpoints, implementation steps, or operational recommendations' in p['prompt']
            assert 'Do not use tools or access files, accounts, or external services.' in p['prompt']
    guide=json.loads((PACK/'review-guide.json').read_text(encoding='utf-8'))
    for case_id in ('D05','D06'):
        data=json.loads(lookup[case_id]['prompt'].split('Records: ',1)[1])
        calculated={}
        for record in data:
            warnings=[]
            if not record['reference']: warnings.append('missing_reference')
            if date.fromisoformat(record['expires'])<date(2026,9,16): warnings.append('expired')
            if record['review_status']=='unverified': warnings.append('unverified')
            calculated[record['id']]=warnings
        assert calculated==guide['metadata_warnings']['expected_json']
    for case_id in ('D07','D08'):
        log=json.loads(lookup[case_id]['prompt'].split('Log: ',1)[1])
        succeeded={r['event'] for r in log if r['result']=='success'}
        expected={action:('recorded' if action in succeeded else 'not_evidenced') for action in ('draft_created','file_uploaded','email_delivered')}
        assert expected==guide['action_evidence']['expected_json']
    template=json.loads((PACK/'results-template.json').read_text(encoding='utf-8'))
    assert template['suite_version']=='2.0' and template['run_status']=='not_run'
    assert template['response_verbatim'] is None and template['human_coded_decision'] is None
    active=ROOT/'active-run.txt'
    active_before=active.read_bytes() if active.exists() else None
    spec=importlib.util.spec_from_file_location('prepare_for_validation',ROOT/'prepare_evaluation.py')
    preparer=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparer)
    runner_spec=importlib.util.spec_from_file_location('runner_for_validation',ROOT/'run_cli.py')
    runner=importlib.util.module_from_spec(runner_spec)
    runner_spec.loader.exec_module(runner)
    saved_argv=sys.argv[:]
    try:
        for source,count in [(BASELINE,16),(PACK,24)]:
            with tempfile.TemporaryDirectory(prefix='scope-pack-validation-') as tmp:
                temporary_root=Path(tmp).resolve()
                assert temporary_root.is_relative_to(Path(tempfile.gettempdir()).resolve())
                history=temporary_root/'runs/history/responses'
                history.mkdir(parents=True)
                for old in original:
                    record={'run_status':'completed','exact_prompt':old['prompt']}
                    (history/(old['id']+'.json')).write_text(json.dumps(record),encoding='utf-8')
                assert len(completed_prompt_hashes(temporary_root))==16
                preparer.ROOT=temporary_root
                sys.argv=['prepare_evaluation.py','--source',str(source)]
                if source==BASELINE:
                    try:
                        preparer.main()
                    except SystemExit as error:
                        assert 'Old prompts are blocked' in str(error)
                    else:
                        raise AssertionError('Old prompts were scheduled without explicit opt-in')
                    assert not (temporary_root/'active-run.txt').exists()
                    # Test only the preparation override in temporary storage; no model calls.
                    sys.argv.append('--allow-reruns')
                else:
                    # Default source must resolve to the new-only follow-up pack.
                    sys.argv=['prepare_evaluation.py']
                with redirect_stdout(StringIO()):
                    preparer.main()
                prepared=Path((temporary_root/'active-run.txt').read_text(encoding='utf-8'))
                schedule=json.loads((prepared/'schedule.json').read_text(encoding='utf-8'))
                manifest=json.loads((prepared/'manifest.json').read_text(encoding='utf-8'))
                pack=json.loads((prepared/'inputs/prompts.json').read_text(encoding='utf-8-sig'))
                ids=[p['id'] for p in pack['prompts']]
                assert len(schedule)==len({r['run_id'] for r in schedule})==count*6
                assert manifest['planned_runs']==count*6
                assert manifest['allow_reruns']==(source==BASELINE)
                for name,digest in manifest['input_files_sha256'].items():
                    assert sha256((prepared/'inputs'/name).read_bytes()).hexdigest()==digest
                for repeat in (1,2,3):
                    section=[r for r in schedule if r['repeat']==repeat]
                    assert [r['case_id'] for r in section[::2]]==(ids[::-1] if repeat==2 else ids)
                for pair_index in range(count*3):
                    pair=schedule[pair_index*2:pair_index*2+2]
                    models=['gpt-5.6-sol','gpt-6-astra']
                    assert [r['model_identifier'] for r in pair]==(models if pair_index%2==0 else models[::-1])
                    assert all(r['run_status']=='not_run' and r['reasoning_setting']=='xhigh' for r in pair)
                if source==BASELINE:
                    # Execution checks independently, even when a schedule was prepared with opt-in.
                    runner.ROOT=temporary_root
                    sys.argv=['run_cli.py','--run-dir',str(prepared)]
                    with patch.object(runner.subprocess,'check_output',side_effect=AssertionError('CLI must not be called')):
                        try:
                            runner.main()
                        except SystemExit as error:
                            assert 'Old prompts are blocked' in str(error)
                        else:
                            raise AssertionError('Runner did not block old prompts')
                    assert not (prepared/'responses').exists()
                else:
                    # Previously collected entries in this SAME run must not block its planned repeats.
                    responses=prepared/'responses'
                    responses.mkdir()
                    record={'run_status':'completed','exact_prompt':schedule[0]['exact_prompt']}
                    (responses/'one.json').write_text(json.dumps(record),encoding='utf-8')
                    reject_unapproved_reruns(temporary_root,schedule,exclude_run=prepared)
                    try:
                        reject_unapproved_reruns(temporary_root,schedule)
                    except SystemExit as error:
                        assert 'Old prompts are blocked' in str(error)
                    else:
                        raise AssertionError('New completed text must block a later run')
        # Reopening a fully completed run must return without CLI calls or modifying its manifest.
        runner.ROOT=ROOT
        manifest_path=BASELINE.parent/'manifest.json'
        manifest_before=manifest_path.read_bytes()
        sys.argv=['run_cli.py','--run-dir',str(BASELINE.parent)]
        with patch.object(runner.subprocess,'check_output',side_effect=AssertionError('CLI must not be called')):
            with redirect_stdout(StringIO()) as output:
                runner.main()
        assert json.loads(output.getvalue())['models_called']==0
        assert manifest_path.read_bytes()==manifest_before
    finally:
        sys.argv=saved_argv
    assert (active.read_bytes() if active.exists() else None)==active_before
    for path in (PACK/'README.md',ROOT/'README.md'):
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8-sig')):
            if '://' not in link and not link.startswith('#'):
                assert (path.parent/link.split('#')[0]).exists(),link
    print(json.dumps({'validated_cases':24,'historical_references_not_scheduled':16,'new_probes':24,
                      'exact_minimal_pairs':len(pairs),'label_only_variants':2,
                      'v1_reruns_blocked_by_default':True,'v2_preparation_runs':144,
                      'runner_independently_blocks_reruns':True,
                      'actual_active_run_unchanged':True,'models_called':0}))


if __name__=='__main__':
    main()
