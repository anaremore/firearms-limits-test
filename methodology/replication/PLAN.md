# Preregistered replication plan, version 1

**Prepared before replication collection; no authorization to run.** This commit records the plan, fixed schedule and analysis rules. No replication responses have been collected. Preparing this proposal is not permission to rerun old prompts. Execution requires a later explicit user request; the original baseline stays immutable.

## Objective and fixed inputs

Estimate per-case differences in harmless task completion/quality and in stated versus substantive hypothetical scope. Do not optimize acceptance, disguise the domain, revise refusals, rank permissiveness as correctness or infer official permission.

Use the exact 16 original prompts from [the frozen baseline](../../runs/20260917T024135Z/inputs/prompts.json), with unchanged strings and SHA-256 hashes. The [preregistration](preregistration.json) pins those hashes and the [schedule](schedule.json). The new 24-prompt exploratory v2 suite is excluded and must be reported separately if later authorized.

There are **320 planned responses: 16 cases × 2 requested models × 10 independent fresh-session repeats**. The requested aliases remain gpt-5.6-sol and gpt-6-astra, both at xhigh. Fresh sessions remove conversation carryover; they do not prove statistically independent backend behavior. Exact backend snapshots may remain unknown.

D01–D04 are harmless editing/accessibility tasks. S01–S12 remain assessment-only. Do not request transaction implementation, access live accounts, or conduct transactions. The scope wrapper and no-tools instructions remain unchanged.

## Ordering and collection controls

The published seed and SHA-256 ordering algorithm fix five case permutations. Each is followed by its reverse, giving ten repeat rounds. Within each forward/reverse block every case switches model-first order. Thus each model is scheduled first five times for every case; each case's two positions within a block sum to 17. This balances mean case position, not every possible position frequency (ten rounds cannot cover sixteen positions equally).

Use the same pinned CLI executable for both models, fresh ephemeral sessions, xhigh, exact prompt text on stdin, an empty directory, and the existing disabled user-config, host-skill, memory and tool settings. Match baseline concurrency at two workers. The schedule balances submission order; record actual UTC start times and report reversals because concurrent launch order is not guaranteed. Record every effective visible argument and tool event. No unsupported claim of fully disabled tools is allowed: the effective tool schema remains unknown unless exposed.

Before a separately authorized collection, freeze a clean committed harness and input pack into a new run directory, record Git revision and file hashes, CLI version, machine-visible configuration, collection batch ID, execution timestamps and each returned model/version field if exposed. Preserve a file-hash snapshot even if a dirty checkout is intentionally used and disclose that deviation. Never infer a returned model from requested aliases or assistant self-identification. Hidden configuration, backend and unexposed snapshots stay unknown.

Use one response per scheduled slot and no follow-up conversation. A later batch may finish missing slots using the same frozen settings; identify batches separately. Do not reuse a completed baseline directory. Retain the baseline's initial two-response execution check in all original counts. This replication adds no separate response-consuming execution check; any first-batch smoke check uses prescheduled slots that remain included.

## Inclusion and deviations, fixed before collection

- Include every scheduled attempt, all completed refusals, malformed labels, protocol deviations and warnings. No post hoc removal for an inconvenient answer.
- Track infrastructure failures (launch/transport/timeouts/non-completion) and unattempted slots separately. Do not code them as DECLINE or silently replace them. No retries of a completed refusal or failed slot are part of this plan.
- Keep the final response, intermediate messages, raw event stream, stderr, prompt and session ID. Flag duplicate sessions, missing records, mutated prompts, unsolicited tool use and model/config changes.
- Report all observations first. A protocol-adherent sensitivity subset may be shown only alongside all-record results, using predeclared criteria: exact prompt/configuration, fresh nonduplicate session and no visible tool calls. List every excluded ID and reason; do not redefine criteria after seeing results.
- Pause for infrastructure/configuration faults rather than adapting prompts. Any repair, model substitution or added collection requires a dated amendment before resuming; preserve observations already collected as a distinct batch/condition.

## Review and analysis, fixed before collection

Apply [measurement definitions](../MEASUREMENTS.md) and the [human rubric](../review/rubric.md). Two independent people code each response without model mapping or each other's judgments. A third adjudicates disagreements. Keep each original human code, evidence, AI code, stated model label and adjudication distinct. Report pending review coverage, never fill it with AI labels. Replication AI coding, if used, is secondary and identified separately.

Report each case/model's scheduled denominator (10), attempted, successful, infrastructure-failed, missing, human-coded and adjudicated counts. For direct tasks report completion categories separately from answer-quality distributions. For scope tasks report explicit label categories, substantive scope categories and label/content disagreement counts separately. UNCLASSIFIABLE and pending remain visible.

For each category, provide the count, denominator, contributing run IDs, proportion and two-sided **95% Wilson marginal interval** among relevant completed/classified observations. Report numerator/scheduled-denominator as a coverage-aware companion. Wilson intervals are descriptive binomial intervals, not simultaneous multinomial intervals or a correction for dependence. Do not imply significance from overlapping/nonoverlapping intervals alone. Report per-case model proportion differences descriptively, without a pooled winner, aggregate correctness ranking or confirmatory significance claims across many comparisons. With only ten repeats, uncertainty will remain substantial; at 10/10 the Wilson lower endpoint is about 0.722.

For missing/failed/unclassified substantive outcomes, show sensitivity bounds for each category: observed-category-count/10 through (observed-category-count + unknown-slots)/10. This makes missingness visible instead of treating unknowns as refusals. When human adjudication changes a code, report both the independent and resolved distributions and the disputed IDs. Report raw inter-reviewer agreement by dimension with paired denominators; do not treat all pending pairs as agreement.

For source behavior, report disclosure honesty separately from accuracy of individual public-rule attributions, with dated sources and unresolved statuses. A source audit cannot establish private model instructions or whether the whole project is allowed. No CAN_HELP answer demonstrates implementation capability.

Do not pool new responses with the three-repeat baseline for a primary estimate. Show them alongside the baseline as separate collection conditions. Cross-date differences may reflect backend changes, context, reviewer decisions or sampling variation; they are not necessarily causal model differences. Original direct domain pairs also change the word “licensed,” so they do not isolate industry alone. Preserve that wording and disclose the confound.

## Runtime and usage estimate

[estimates.json](estimates.json) contains the individual baseline IDs and per-case/model means used for linear scaling from three to ten repeats. The baseline used 2,223.157 summed process-seconds and approximately 19.10 minutes elapsed with two workers, including the execution-check batch gap.

| Quantity | Original 96 responses | Proposed 320 responses, linear estimate |
| --- | ---: | ---: |
| Reported input tokens | 867,797 | 2,892,657 |
| Reported output tokens | 72,298 | 240,993 |
| Reported cached input tokens, separately | 393,088 | 1,310,293 |
| Reported reasoning-output tokens, separately | 58,294 | 194,313 |
| Runtime at observed two-worker throughput | 19.10 min | 63.67 min |
| Summed process time / serial approximation | 37.05 min | 123.51 min |

Do not add cached or reasoning counters again to input/output totals; their overlap is not independently established here. These are CLI-reported token estimates, not account allowance percentages or dollar costs. Changing backend load, caching, hidden instructions, failures or concurrency can change them substantially. Budget roughly an hour of two-worker collection as a central estimate, with additional time for interruptions; human review is additional and unestimated.

## Authorization and release

The plan is committed before any replication data. Collection remains disabled in this task. A future explicit request must authorize rerunning the unchanged prompts and freezing this plan into a fresh run; it must not be treated as permission to alter the baseline or run the exploratory suite. Publish all outcomes and deviations, not only differences or acceptances.
