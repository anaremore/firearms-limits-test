# Stopped Codex subagent pilot

This directory contains 16 completed responses from a planned 96-run subagent pilot. It stopped after sequence 16 when the study switched to the separate CLI run in `../20260917T024135Z`. The remaining 80 pilot runs were not attempted. Do not pool these responses with the CLI study.

Each measured child received the exact frozen prompt as its entire task message, requested `gpt-5.6-sol` or `gpt-6-astra` with `xhigh`, and used `fork_turns='none'`. Sequences 1–12 were launched directly by `/root`; sequences 13–16 were launched by `/root/remaining_test_runs`. This launch-path difference is recorded rather than treated as a controlled equivalence. The backend model snapshot was not exposed in the saved records.

The JSON files in `responses/` retain exact final output strings in `response_verbatim`, with hashes, frozen prompts, requested settings, recording times, and provenance. Recording times are not exact launch or completion times. Template human-review and quality fields remain null. `stated_decision` is only a literal extracted token, not a human assessment.

Subagents retained product and orchestration context. The full tool schema and complete tool traces were not captured or verified. Empty `tools_available` or `visible_tool_events` lists do not establish a tool-free condition. Two known deviations from the prompts' no-tools instruction occurred: `r1_d03_sol` and `r1_d04_sol` sent intermediate `collaboration.send_message` coordination messages. Their verbatim messages are preserved separately from the final responses in both the original `early-intermediate-messages.json` and the corresponding response records. These records do not request or contain private reasoning.

`manifest.json` records completed and unattempted counts. `schedule.json` remains the original frozen plan, so its original `not_run` fields are not execution results. `normalize-pilot.py` normalizes this pilot only; `validation.json` confirms all 16 task IDs, exact prompts and hashes, requested models and reasoning settings, null review fields, unchanged frozen inputs, and identical final/intermediate strings before and after normalization.

This incomplete pilot documents observed task outputs and stated scope assessments. It does not establish official policy, legality, implementation willingness for scope-only cases, or model-quality rankings.
