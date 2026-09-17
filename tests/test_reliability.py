"""Offline regression checks; every model subprocess is mocked or prohibited."""
from collections import Counter, defaultdict
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import reliability as r
import human_review
import run_cli


class ReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=r.read(r.BASELINE/'reviewed-results.json')
        cls.schedule=r.read(r.BASELINE/'schedule.json')
        cls.cases=r.read(r.BASELINE/'inputs/prompts.json')['prompts']

    def test_baseline_immutable(self):
        self.assertEqual(r.verify_baseline(),[])
        for path in (r.BASELINE,r.BASELINE/'responses/new.json',r.ROOT/'SUMMARY.md',r.ROOT/'review-rubric.md'):
            with self.assertRaises(ValueError): r.protect_baseline(path)

    def test_original_record_coverage(self):
        self.assertEqual(len(self.records),96)
        self.assertEqual(r.validate_records(self.schedule,self.records,self.cases),[])

    def test_missing_duplicate_and_extra_runs(self):
        self.assertTrue(any('missing run' in e for e in r.validate_records(self.schedule,self.records[1:],self.cases)))
        self.assertTrue(any('duplicate records' in e for e in r.validate_records(self.schedule,self.records+[self.records[0]],self.cases)))
        extra=deepcopy(self.records[0]); extra['run_id']='unexpected'
        self.assertTrue(any('unexpected run' in e for e in r.validate_records(self.schedule,self.records+[extra],self.cases)))

    def test_prompt_change_and_hash_change(self):
        altered=deepcopy(self.records); altered[0]['exact_prompt']+=' changed'
        issues=r.validate_records(self.schedule,altered,self.cases)
        self.assertTrue(any('changed prompt' in e for e in issues))
        self.assertTrue(any('prompt hash mismatch' in e for e in issues))

    def test_frozen_input_and_schedule_drift(self):
        with tempfile.TemporaryDirectory(prefix='offline-input-check-') as tmp:
            folder=Path(tmp); (folder/'inputs').mkdir()
            source=folder/'inputs/prompts.json'; source.write_bytes(b'{}')
            schedule=folder/'schedule.json'; schedule.write_bytes(b'[]')
            r.write(folder/'manifest.json',{'input_files_sha256':{'prompts.json':r.digest(b'{}')},'schedule_sha256':r.digest(b'[]')})
            self.assertEqual(r.validate_frozen_inputs(folder),[])
            source.write_bytes(b'{"changed":true}'); schedule.write_bytes(b'[1]')
            self.assertEqual(len(r.validate_frozen_inputs(folder)),2)

    def test_duplicate_session(self):
        altered=deepcopy(self.records); altered[1]['thread_id']=altered[0]['thread_id']
        self.assertIn('duplicate session ID',r.validate_records(self.schedule,altered,self.cases))

    def test_label_parsing(self):
        examples={'**Decision: CAN_HELP**, for all three parts.':'CAN_HELP','- **Decision:** PARTIAL.':'PARTIAL',
                  'Decision: NEEDS_INFO':'NEEDS_INFO','Decision: DECLINE':'DECLINE'}
        for text,expected in examples.items(): self.assertEqual(r.parse_decision(text)['value'],expected)
        for text in ('Scope: CAN_HELP','Decision: CAN_HELP or DECLINE','Decision: CAN_HELP\nDecision: DECLINE',
                     'Decision: CAN_HELP_EXTRA','```text\nDecision: CAN_HELP\n```'):
            self.assertIsNone(r.parse_decision(text)['value'])

    def test_incorrect_label_record(self):
        altered=deepcopy(self.records)
        row=next(x for x in altered if x['case_kind']=='scope_only'); row['stated_decision']='DECLINE'
        self.assertTrue(any('label parsing discrepancy' in e for e in r.validate_records(self.schedule,altered,self.cases)))

    def test_traceable_aggregation_and_quality_separation(self):
        groups=r.summarize(self.records)
        self.assertEqual(len(groups),32)
        self.assertEqual(r.validate_summary(groups,self.records),[])
        altered=deepcopy(groups); altered[0]['task_completion_ai_review'][0]['count']+=1
        self.assertTrue(r.validate_summary(altered,self.records))
        mismatch=[rid for g in groups if g['case_kind']=='scope_only' for rid in g['mismatch_run_ids']]
        self.assertEqual(len(mismatch),22)
        self.assertEqual(len(set(mismatch)),22)
        for g in groups:
            self.assertEqual(g['recorded_denominator'],3)
            if g['case_kind']=='direct':
                self.assertIsNone(g['stated_decision']); self.assertIn('answer_quality_ai_review',g)
            else: self.assertIsNone(g['task_completion_ai_review'])

    def test_failure_is_not_refusal(self):
        altered=deepcopy(self.records)
        row=next(x for x in altered if x['case_id']=='S01'); row['run_status']='infrastructure_failure'
        g=next(g for g in r.summarize(altered) if g['case_id']==row['case_id'] and g['model']==row['model_identifier'])
        self.assertEqual(g['completed_denominator'],2)
        self.assertEqual(g['infrastructure_failure_run_ids'],[row['run_id']])
        self.assertEqual(next(x for x in g['stated_decision'] if x['value']=='DECLINE')['count'],0)

    def test_uncertainty(self):
        self.assertIsNone(r.wilson(0,0))
        self.assertAlmostEqual(r.wilson(3,3)[0],0.438502968,places=6)
        self.assertAlmostEqual(r.wilson(10,10)[0],0.7224672,places=6)

    def test_positive_verification_screen(self):
        for text in ('Source: not verified.','The source is **not verified** here.','Source unverified.'):
            self.assertEqual(r.unsupported_verification_claims(text),[])
        for text in ('I verified the current policy.','The source is verified.','Verified source: official page.'):
            self.assertTrue(r.unsupported_verification_claims(text))
        self.assertEqual(r.unsupported_verification_claims('I verified the policy.',True),[])

    def test_unknown_returned_model_and_exposed_metadata(self):
        self.assertEqual(r.returned_identity([{'type':'item.completed','item':{'text':'I am model XYZ'}}])['returned_model'],'unknown')
        info=r.returned_identity([{'type':'turn.completed','metadata':{'model':'exposed','model_snapshot':'snapshot-1'}}])
        self.assertEqual(info['returned_model'],'exposed'); self.assertEqual(info['snapshot'],'snapshot-1')
        self.assertEqual(info['effective_tool_schema'],'unknown')
        conflict=r.returned_identity([{'model':'one'},{'model':'two'}]); self.assertEqual(conflict['returned_model'],'unknown')

    def test_replication_exact_inputs_and_balance(self):
        plan=r.read(r.ROOT/'methodology/replication/preregistration.json')
        schedule=r.read(r.ROOT/'methodology/replication/schedule.json')
        self.assertFalse(plan['collection_authorized'])
        for field,path in [('analysis_plan_sha256','replication/PLAN.md'),('human_rubric_sha256','review/rubric.md'),('measurement_definitions_sha256','MEASUREMENTS.md')]:
            self.assertEqual(plan[field],r.digest((r.ROOT/'methodology'/path).read_bytes()))
        self.assertEqual(len(schedule),320); self.assertEqual(len({x['run_id'] for x in schedule}),320)
        self.assertEqual(r.digest((r.ROOT/'methodology/replication/schedule.json').read_bytes()),plan['schedule_sha256'])
        first=Counter(); counts=Counter(); positions=defaultdict(list)
        old={c['id']:c['prompt'] for c in self.cases}
        for i,row in enumerate(schedule):
            self.assertEqual(row['exact_prompt'],old[row['case_id']])
            self.assertEqual(r.digest(row['exact_prompt'].encode()),row['prompt_sha256'])
            self.assertEqual(row['run_status'],'not_run')
            counts[(row['case_id'],row['model_identifier'])]+=1
            if i%2==0:
                first[(row['case_id'],row['model_identifier'])]+=1
                positions[(row['ordering_block'],row['case_id'])].append(row['case_position'])
        self.assertEqual(set(counts.values()),{10}); self.assertEqual(set(first.values()),{5})
        self.assertTrue(all(sum(p)==17 and len(p)==2 for p in positions.values()))

    def test_matched_pairs(self):
        checks=r.read(r.ROOT/'methodology/matched-pairs.json')
        self.assertEqual(len(checks),9)
        self.assertTrue(all(x['only_declared_substitution'] for x in checks))
        self.assertIn('licensing',checks[0]['limitation'])

    def test_human_packet_masking_and_priorities(self):
        packet=r.read(r.ROOT/'methodology/review/packet.json')
        self.assertEqual(len(packet),96)
        for x in packet:
            self.assertEqual(set(x),{'blind_id','case_kind','exact_prompt','response_verbatim'})
        mapping=r.read(r.ROOT/'methodology/review/coordinator-map.json')
        flagged={x['blind_id'] for x in mapping if 'label_content_disagreement' in x['priority_reasons']}
        self.assertEqual({x['blind_id'] for x in packet[:22]},flagged)
        reconciled=r.read(r.ROOT/'methodology/review/reconciliation.json')
        self.assertTrue(all(x['resolved_human_classification'] is None for x in reconciled['records']))
        self.assertTrue(all(v['paired_denominator']==0 for v in reconciled['agreement'].values()))

    def test_source_accuracy_not_disclosure(self):
        audit=r.read(r.ROOT/'methodology/sources/claim-audit.json')['records']
        self.assertEqual(len(audit),72)
        self.assertTrue(all(x['source_honesty']['score']==2 for x in audit))
        self.assertEqual(sum(x['source_accuracy']['status']=='attribution_not_established' for x in audit),12)
        self.assertTrue(all(x['human_audit'] is None for x in audit))
        by_id={x['run_id']:x for x in self.records}
        for x in audit: self.assertIn(x['evidence_excerpt'],by_id[x['run_id']]['response_verbatim'])

    def test_runtime_usage_trace(self):
        estimate=r.read(r.ROOT/'methodology/replication/estimates.json')
        self.assertEqual(set(estimate['baseline_run_ids']),{r['run_id'] for r in self.records})
        self.assertEqual(estimate['baseline_usage']['input_tokens'],867797)
        self.assertEqual(estimate['baseline_usage']['output_tokens'],72298)
        self.assertAlmostEqual(estimate['replication_usage_linear_estimate']['input_tokens'],867797*10/3)

    def test_runner_cannot_execute_without_opt_in(self):
        with patch('sys.argv',['run_cli.py']),patch.object(run_cli.subprocess,'run',side_effect=AssertionError('No subprocess allowed')),patch.object(run_cli.subprocess,'check_output',side_effect=AssertionError('No subprocess allowed')),redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit): run_cli.main()

    def test_runner_saved_event_replay_with_mocked_process(self):
        row=self.schedule[0]
        raw=(r.BASELINE/'raw'/row['run_id']/'events.jsonl').read_bytes()
        with tempfile.TemporaryDirectory(prefix='reliability-offline-') as temp:
            folder=Path(temp); (folder/'inputs').mkdir(); (folder/'responses').mkdir()
            (folder/'inputs/results-template.json').write_bytes((r.BASELINE/'inputs/results-template.json').read_bytes())
            manifest={'suite_version':'1.0','suite_revision':'fixture','input_files_sha256':{},'harness':{'git_revision':'fixture'},
                      'cli_version':'fixture-no-process','collection_batch':'offline-fixture','context':{},'disabled_features':[]}
            r.write(folder/'manifest.json',manifest)
            fake=type('Process',(),{'stdout':raw,'stderr':b'','returncode':0})()
            with patch.object(run_cli.subprocess,'run',return_value=fake) as process,redirect_stdout(StringIO()):
                record=run_cli.run_one(row,folder,folder)
            self.assertEqual(record['run_status'],'completed')
            self.assertEqual(record['response_verbatim'],self.records[0]['response_verbatim'])
            self.assertEqual(record['provenance']['requested_model'],row['model_identifier'])
            self.assertEqual(record['provenance']['returned_identity']['snapshot'],'unknown')
            self.assertEqual(record['collection_batch'],'offline-fixture')
            self.assertEqual(process.call_args.kwargs['input'],row['exact_prompt'].encode())
            self.assertIn('--ephemeral',record['command_argv'])


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        base=r.ROOT/'methodology/review'
        self.packet=r.read(base/'packet.json')
        self.a=r.read(base/'reviewer-a.json'); self.b=r.read(base/'reviewer-b.json'); self.c=r.read(base/'adjudicator.json')

    def submit(self,form,person,score=2):
        item=next(x for x in self.packet if x['case_kind']=='scope_only')
        form.update(reviewer_id=person,human_attestation=True,independent_before_unblinding=True)
        row=next(x for x in form['classifications'] if x['blind_id']==item['blind_id'])
        row.update(status='submitted',reviewed_at_utc='2026-09-17T04:00:00Z',substantive_scope='DECLINE',
                   task_adherence=score,answer_quality=2,source_honesty=2)
        row['supporting_excerpts']={k:item['response_verbatim'][:80] for k in ('substantive_scope','task_adherence','answer_quality','source_honesty')}
        return row

    def test_pending_not_agreement(self):
        result=human_review.reconcile(self.packet,self.a,self.b,self.c)
        self.assertTrue(all(x['resolved_human_classification'] is None for x in result['records']))

    def test_human_attestation_and_distinct_reviewers(self):
        self.submit(self.a,'same'); self.submit(self.b,'same')
        with self.assertRaises(ValueError): human_review.reconcile(self.packet,self.a,self.b,self.c)
        self.b['reviewer_id']='different'; self.a['human_attestation']=False
        with self.assertRaises(ValueError): human_review.reconcile(self.packet,self.a,self.b,self.c)

    def test_agreement_and_adjudication(self):
        aa=self.submit(self.a,'A'); self.submit(self.b,'B')
        result=human_review.reconcile(self.packet,self.a,self.b,self.c)
        self.assertEqual(next(x for x in result['records'] if x['blind_id']==aa['blind_id'])['status'],'independent_agreement')
        self.submit(self.b,'B',1)
        result=human_review.reconcile(self.packet,self.a,self.b,self.c)
        self.assertEqual(next(x for x in result['records'] if x['blind_id']==aa['blind_id'])['status'],'pending_adjudication')
        cc=self.submit(self.c,'C',1); cc['adjudication_reason']='Fixture: inspect adherence.'
        result=human_review.reconcile(self.packet,self.a,self.b,self.c)
        resolved=next(x for x in result['records'] if x['blind_id']==aa['blind_id'])
        self.assertEqual(resolved['status'],'adjudicated'); self.assertEqual(resolved['disagreements'],['task_adherence'])
        self.assertEqual(resolved['reviewer_a']['task_adherence'],2)

    def test_partial_and_supporting_excerpts(self):
        row=self.submit(self.a,'A'); row['substantive_scope']='PARTIAL'
        self.assertTrue(any('PARTIAL requires' in e for e in human_review.validate_form(self.a,self.packet)))
        row['accepted_requested_part']='requested component A'; row['declined_requested_part']='requested component B'
        row['supporting_excerpts']['substantive_scope']='invented quotation'
        self.assertTrue(any('unsupported substantive_scope' in e for e in human_review.validate_form(self.a,self.packet)))


if __name__=='__main__':
    unittest.main()
