# Sol / Astra assistance-scope evaluation

**Start here: [Read the plain-language summary](SUMMARY.md).** It explains where the models agreed, where they differed, and how consistent their answers were.

**New: [Version 2 follow-up prompt pack](suites/v2/README.md), prepared but not run.** It schedules only 24 new targeted probes (144 responses at three repeats per model). The 16 original prompts and their results remain historical references; they will not be rerun unless explicitly requested. The additions examine business-domain effects, record changes, automation, audit integrity, safeguard bypass, weapon-assistance boundaries, evidence and uncertainty.

Completed all 96 CLI responses: 16 fixed prompts, GPT-5.6 Sol and GPT-6 Astra at `xhigh`, and three independent repeats. All 96 sessions were distinct; zero infrastructure failures and zero tool events were recorded.

- [Findings and model comparison](runs/20260917T024135Z/FINDINGS.md)
- [Blinded assistant content review](runs/20260917T024135Z/REVIEW.md)
- [CLI report and complete responses](runs/20260917T024135Z/REPORT.md)
- [Structured results](runs/20260917T024135Z/results.json)
- [Per-case decision counts](runs/20260917T024135Z/summary.json)
- [Validation results](runs/20260917T024135Z/validation.json)
- [Static accessibility checks](runs/20260917T024135Z/accessibility-checks.json)
- [Frozen study protocol](runs/20260917T024135Z/inputs/README.md)
- [Exact prompt strings](runs/20260917T024135Z/inputs/prompts.json)
- [Run settings and file hashes](runs/20260917T024135Z/manifest.json)
- [Separate subagent pilot](runs/20260917T023357Z/PILOT.md)

The blinded assistant review found all 24 direct tasks completed and flagged 22 scope-label/content mismatches. Scope decisions varied across repeated runs, so the findings report full distributions. Human review remains pending.

The direct tasks test generic copyediting and static accessibility markup for two business domains. Scope cases request decisions and short explanations only. No firearms transaction functionality was implemented or exercised.

The subagent pilot was stopped after 16 responses when the user asked about a cleaner CLI setup. It is retained as a separate observational condition and excluded from the CLI counts. Two pilot responses emitted coordination messages despite the no-tools instruction.

## Method and limits

Each CLI response came from a new ephemeral session using the exact frozen prompt on standard input. Both models used the same pinned CLI executable, `xhigh`, a read-only sandbox, and the same disabled tool features. User configuration, AGENTS discovery, host skills and memories were omitted for these invocations; no account credentials were copied or published. Authentication used the existing Codex CLI login.

The case order is forward/reverse/forward across repeats; model order alternates by case pair. At most two CLI processes run concurrently, submitted in the recorded schedule order. Completion order can differ. The first two requests were a successful execution check and are included unchanged in the main study. Subsequent requests used a second empty temporary directory with the same settings.

Exact backend snapshots, hidden model instructions and managed configuration are outside the experiment's control. The complete effective tool schema is not exposed by `codex exec` JSONL; tool availability is therefore recorded as unknown, together with the feature flags and observed tool events. CLI warnings are preserved in raw logs. The host-skill-discovery suppression flag is marked under development, and PowerShell shell snapshots are unsupported; these nonfatal warnings did not prevent responses.

Human coding and independent human quality review have not been performed. Template review fields remain null. Automated checks and blinded assistant content review are explicitly separate. [Reviewed structured results](runs/20260917T024135Z/reviewed-results.json) preserve the human fields as null. Stated assistance decisions do not prove implementation willingness or official permission, and greater permissiveness is not treated as better performance.

The CLI mode and output mechanisms follow the [official non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

## Reproduction

Python scripts use only the standard library. `prepare_evaluation.py` defaults to the new-only follow-up pack, freezes its inputs and checks that all Markdown prompts exactly match JSON. Preparation and execution both block text already completed in another saved run; `--allow-reruns` is reserved for an explicit user request. Existing results are reused for historical comparisons. `run_cli.py` reads the frozen schedule and saves each prompt, raw event stream, stderr and structured record. It resumes only entries without a result file; it never retries an existing refusal or infrastructure result. `build_report.py` verifies hashes, session uniqueness and correspondence between final responses and event logs before generating the report.

The default source pack and pinned executable paths are explicit constants in the runner scripts; adjust them for another machine, and use the same executable for both models. Running the model suite consumes the signed-in account's Codex allowance.

The following checks make no model calls and leave the active run unchanged. See the [follow-up protocol](suites/v2/README.md) for collection instructions and the remaining v2 reporting work.

```powershell
python .\prepare_evaluation.py --validate-only
python .\verify_followup.py
```

The originally supplied research files remain unchanged. This repository contains copies frozen for this run.

Review reproduction uses `prepare_review.py --track direct` and `--track scope` after the relevant responses are complete. The reviewer rubric is in [review-rubric.md](review-rubric.md); saved packets hide model labels. `finalize_review.py` checks full review coverage and every supporting excerpt, and `write_findings.py` builds the comparison. The frozen review map allows the published findings to be audited.
