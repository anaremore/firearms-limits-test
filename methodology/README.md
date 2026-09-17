# Reliability and reproducibility update

This is an **offline methodological update**, not another evaluation. The original [summary](../SUMMARY.md), 96 responses, classifications, findings and raw logs are unchanged. The separate pilot is also preserved. No new model calls or human classifications were collected.

- [Reanalysis with separate measurements](REPORT.md): per-case results with links, denominators and uncertainty.
- [Measurement definitions](MEASUREMENTS.md): completion, quality, stated labels, substantive scope and source dimensions.
- [Human review workflow](review/README.md): anonymized packet, two independent forms and adjudication.
- [Dated public-source audit](sources/README.md): source honesty is separate from claim accuracy.
- [Preregistered replication plan](replication/PLAN.md): 320 proposed responses using the unchanged original prompts; collection is not authorized.
- [Baseline provenance](baseline-provenance.json), [matched-pair checks](matched-pairs.json), [integrity inventory](baseline-lock.json) and [validation](validation.json).

The runner now requires explicit execution and batch identifiers, captures suite/harness provenance and exposed response metadata, and blocks changes to published runs. Unknown backend, snapshot, effective tool-schema and managed-configuration details remain unknown. Infrastructure failures are separate from refusals. The first two execution-check responses remain in the original denominator.

All 22 existing AI label/content disagreements are prioritized, along with two explicit ambiguity notes, cases showing repeat variability and the mixed request. Both human reviewers and the adjudicator remain pending. Human forms require identities, independence attestations, UTC timestamps and verbatim supporting excerpts. These are process checks, not proof that a person actually acted independently.

The new report preserves the original AI codes rather than silently recoding disputed answers. Source audits are a separate assistant assessment. No CAN_HELP response is described as demonstrated implementation capability or official permission. Greater permissiveness is never scored as correctness.

## Reproduce this update without model calls

From the repository root:

```powershell
python -m unittest discover -s tests -v
python .\build_methodology.py
python .\human_review.py
```

These commands read saved responses and write only derived methodology artifacts. The builder refuses to overwrite a changed review packet and preserves existing human forms. The reconciliation command validates submitted forms; it never supplies missing human classifications. Do not use run_cli.py for offline verification.

The hash inventory protects 432 published files at revision b815f10831f14d20e3e19d122c29e5d3c89b5e58. Raw streams and frozen inputs are checked byte for byte. Other published text is checked using Git's LF line-ending representation so a Windows checkout remains reproducible; no content or whitespace beyond CRLF/LF conversion is normalized. Future writer scripts reject both original run directories. Original SUMMARY.md and review-rubric.md are protected too; updated guidance lives here.

## What remains unverified

Independent human review and adjudication have not occurred. No replication or version 2 response has been collected. Source audits do not establish hidden instructions, exact historical backend configuration or project-level permission. Static accessibility checks are not a browser or assistive-technology audit. Confidence intervals condition on three repeats and existing AI codes, so they omit classification uncertainty and possible correlated/backend effects. Actual execution-time Git revisions were not captured in the baseline and are not retroactively invented.
