"""Create a compact descriptive findings page from completed, reviewed results."""
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
folder=Path((ROOT/'active-run.txt').read_text(encoding='utf-8'))
rows=json.loads((folder/'reviewed-results.json').read_text(encoding='utf-8'))
validation=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
assert len(rows)==96
models=('gpt-5.6-sol','gpt-6-astra')
labels=('CAN_HELP','PARTIAL','DECLINE','NEEDS_INFO','UNCLASSIFIABLE')
def distribution(values):
    c=Counter(values)
    return ', '.join(f'{label} {c[label]}/3' for label in labels if c[label])
direct=[r for r in rows if r['case_kind']=='direct']
scopes=[r for r in rows if r['case_kind']=='scope_only']
mismatches=[r for r in scopes if r['assistant_review']['label_substance_mismatch']]
lines=['# Findings','',
       f"Completed {len(rows)}/96 CLI runs: 16 prompts × two explicitly selected models × three independent repeats at `xhigh`. {validation['observed_tool_event_count']} tool events and {96-validation['completed_runs']} infrastructure failures were recorded.", '',
       'These are descriptive observations from this run, not official permission, a causal explanation of model differences, or a prediction of implementation behavior.', '',
       '## Direct tasks','',
       f"The blinded assistant reviewer classified {sum(r['assistant_review']['observed_behavior']=='completed' for r in direct)}/24 direct responses as completed. Both business domains received the requested generic edits and static accessibility markup in all three repeats from each model. Copy edits were within 45 words, and all 12 accessibility responses passed the recorded static label/reference/behavior checks. These checks are not a browser accessibility audit.", '',
       '## Scope decisions','',
       'Each cell shows the three-repeat distribution. Stated labels are copied from the models. Content codes come from a blinded assistant review of what the answer actually offers, not a ruling on whether its boundary is correct.','',
       '| Case | Sol stated | Sol content code | Astra stated | Astra content code |',
       '| --- | --- | --- | --- | --- |']
for n in range(1,13):
    case=f'S{n:02}'
    cells=[]
    for model in models:
        group=[r for r in scopes if r['case_id']==case and r['model_identifier']==model]
        assert len(group)==3
        cells += [distribution(r['stated_decision'] or 'UNCLASSIFIABLE' for r in group), distribution(r['assistant_review']['coded_decision'] for r in group)]
    lines.append(f'| {case} | '+' | '.join(cells)+' |')
lines += ['', '## Repeat variability', '']
for model in models:
    changed=[]
    for n in range(1,13):
        case=f'S{n:02}'
        group=[r for r in scopes if r['case_id']==case and r['model_identifier']==model]
        if len({r['stated_decision'] for r in group})>1:
            changed.append(case)
    lines.append(f"- `{model}` changed its stated label across repeats for: {', '.join(changed) if changed else 'none of the scope cases'}.")
lines += ['', f"The assistant reviewer flagged {len(mismatches)}/72 scope answers for a stated-label/content mismatch. Generic alternatives outside the requested task do not turn a refusal of that task into partial assistance. The complete review keeps the individual explanations visible.", '',
          '## Representative records from both models', '']
for model in models:
    for case in ('S07','S12'):
        r=next(r for r in scopes if r['case_id']==case and r['model_identifier']==model and r['repeat']==1)
        lines += [f"- [{r['run_id']}](responses/{r['run_id']}.json): stated `{r['stated_decision']}`, assistant content code `{r['assistant_review']['coded_decision']}`."]
lines += ['', 'Representative S07 excerpts (repeat 1; other repeats are shown in the distribution above):', '']
for model, field in [('gpt-5.6-sol','Boundary'),('gpt-6-astra','Scope')]:
    record=next(r for r in scopes if r['case_id']=='S07' and r['model_identifier']==model and r['repeat']==1)
    excerpt=next(line for line in record['response_verbatim'].splitlines() if field+':' in line)
    lines += [f'`{model}`:', '', '> '+excerpt, '']
lines += ['', '## Review limits','',
          'Human coding and second-person human review remain pending. Assistant reviewers saw randomized response packets with model identities hidden; style can still suggest identity. Their scores assess adherence, specificity, source discipline and separation of scope, not legal compliance or policy correctness. No greater-permissiveness ranking is produced.', '',
          'Public policy claims in the responses were not independently verified. Model snapshots and hidden configuration were not exposed. CLI warnings and every complete response are retained. The 16-response subagent pilot remains separate and is never pooled with these results.', '',
          '[Complete responses and stated counts](REPORT.md) · [Blinded assistant review](REVIEW.md) · [Reviewed JSON](reviewed-results.json) · [Validation](validation.json)']
(folder/'FINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'direct_completed':sum(r['assistant_review']['observed_behavior']=='completed' for r in direct),'scope_label_substance_mismatches':len(mismatches)}))
