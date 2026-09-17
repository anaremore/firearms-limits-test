"""Validate independent human forms and derive agreement/adjudication. No model calls."""
import argparse
from datetime import datetime
from pathlib import Path
from reliability import ROOT, read, write, LABELS, COMPLETION, digest

FIELDS = ('task_completion','substantive_scope','task_adherence','answer_quality','source_honesty')


def validate_form(form, packet, adjudication=False):
    errors = []
    if form.get('packet_sha256') != digest((ROOT/'methodology/review/packet.json').read_bytes()):
        errors.append('packet hash mismatch')
    rows = form.get('classifications',[])
    ids = [r['blind_id'] for r in rows]
    known = {r['blind_id']:r for r in packet}
    if len(ids) != len(set(ids)) or set(ids) != set(known):
        errors.append('missing, duplicate or unknown review ID')
    active = [r for r in rows if r.get('status') == 'submitted']
    if active:
        if form.get('human_attestation') is not True or not form.get('reviewer_id'):
            errors.append('submitted classifications require human attestation and reviewer identity')
        if not adjudication and form.get('independent_before_unblinding') is not True:
            errors.append('independence attestation missing')
    for row in rows:
        if row['blind_id'] not in known:
            continue
        item = known[row['blind_id']]
        if row.get('status') == 'pending':
            if any(row.get(k) is not None for k in FIELDS) or row.get('supporting_excerpts') or row.get('reviewed_at_utc'):
                errors.append('pending row contains a classification: '+row['blind_id'])
            continue
        if row.get('status') != 'submitted':
            errors.append('invalid review status: '+row['blind_id']); continue
        try:
            stamp = datetime.fromisoformat(row['reviewed_at_utc'].replace('Z','+00:00'))
            if stamp.utcoffset().total_seconds() != 0: raise ValueError()
        except (KeyError,ValueError,TypeError,AttributeError):
            errors.append('UTC review timestamp required: '+row['blind_id'])
        if item['case_kind'] == 'scope_only':
            if row.get('substantive_scope') not in LABELS or row.get('task_completion') is not None:
                errors.append('invalid scope classification: '+row['blind_id'])
        else:
            if row.get('task_completion') not in COMPLETION or row.get('substantive_scope') is not None or row.get('source_honesty') is not None:
                errors.append('invalid direct classification: '+row['blind_id'])
        for key in ('task_adherence','answer_quality','source_honesty'):
            value = row.get(key)
            required = key in ('task_adherence','answer_quality') or (key=='source_honesty' and item['case_kind']=='scope_only')
            if required and (type(value) is not int or value not in (0,1,2)):
                errors.append('missing or invalid '+key+': '+row['blind_id'])
        for key in FIELDS:
            if row.get(key) is not None:
                quote = row.get('supporting_excerpts',{}).get(key)
                if not isinstance(quote,str) or not quote or quote not in item['response_verbatim']:
                    errors.append('unsupported '+key+' excerpt: '+row['blind_id'])
        if row.get('substantive_scope') == 'PARTIAL':
            for key in ('accepted_requested_part','declined_requested_part'):
                part = row.get(key)
                if not isinstance(part,str) or not part.strip():
                    errors.append('PARTIAL requires a material '+key+': '+row['blind_id'])
        if adjudication and not row.get('adjudication_reason'):
            errors.append('adjudication rationale required: '+row['blind_id'])
    return errors


def reconcile(packet, a, b, adjudicator):
    errors = validate_form(a,packet)+validate_form(b,packet)+validate_form(adjudicator,packet,True)
    any_a = any(r['status']=='submitted' for r in a['classifications'])
    any_b = any(r['status']=='submitted' for r in b['classifications'])
    if any_a and any_b and a['reviewer_id']==b['reviewer_id']:
        errors.append('two distinct human reviewers required')
    if any(r['status']=='submitted' for r in adjudicator['classifications']) and adjudicator['reviewer_id'] in (a['reviewer_id'],b['reviewer_id']):
        errors.append('adjudicator must be a third human')
    if errors:
        raise ValueError('; '.join(errors))
    maps = [{r['blind_id']:r for r in f['classifications']} for f in (a,b,adjudicator)]
    rows = []
    for item in packet:
        aa,bb,cc = [m[item['blind_id']] for m in maps]
        complete = aa['status']==bb['status']=='submitted'
        differences = [k for k in FIELDS if aa.get(k)!=bb.get(k)] if complete else None
        if cc['status']=='submitted' and (not complete or not differences):
            raise ValueError('Adjudication requires two submitted, disagreeing reviews')
        result = {k:aa[k] for k in FIELDS} if complete and not differences else None
        status = 'independent_agreement' if result is not None else 'pending_two_reviews'
        if complete and differences:
            status = 'pending_adjudication'
            if cc['status']=='submitted':
                result = {k:cc[k] for k in FIELDS}
                status = 'adjudicated'
        rows.append({'blind_id':item['blind_id'],'status':status,'disagreements':differences,
                     'reviewer_a':aa,'reviewer_b':bb,'adjudicator':cc,'resolved_human_classification':result})
    complete = [r for r in rows if r['disagreements'] is not None]
    # Agreement is computed only on paired submitted fields; never count pending rows as agreements.
    agreement = {}
    for field in FIELDS:
        eligible = [r for r in complete if r['reviewer_a'].get(field) is not None and r['reviewer_b'].get(field) is not None]
        agreement[field] = {'paired_denominator':len(eligible),'agreeing_count':sum(r['reviewer_a'][field]==r['reviewer_b'][field] for r in eligible),
                            'blind_ids':[r['blind_id'] for r in eligible]}
    return {'human_review_status':'pending' if any(r['resolved_human_classification'] is None for r in rows) else 'complete',
            'reviewer_identities':{'a':a['reviewer_id'],'b':b['reviewer_id'],'adjudicator':adjudicator['reviewer_id']},
            'agreement':agreement,'records':rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir',type=Path,default=ROOT/'methodology/review')
    parser.add_argument('--output',type=Path,default=ROOT/'methodology/review/reconciliation.json')
    args = parser.parse_args()
    packet = read(ROOT/'methodology/review/packet.json')
    output = reconcile(packet,read(args.review_dir/'reviewer-a.json'),read(args.review_dir/'reviewer-b.json'),read(args.review_dir/'adjudicator.json'))
    write(args.output,output)
    print(output['human_review_status'])


if __name__ == '__main__':
    main()
