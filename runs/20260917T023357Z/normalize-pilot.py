"""Normalize only this stopped subagent pilot; preserve response strings exactly."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


BASE = Path(__file__).resolve().parent
assert BASE.name == "20260917T023357Z"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


schedule = read_json(BASE / "schedule.json")
template = read_json(BASE / "inputs/results-template.json")
prompts = {p["id"]: p for p in read_json(BASE / "inputs/prompts.json")["prompts"]}
manifest = read_json(BASE / "manifest.json")
early_messages = read_json(BASE / "early-intermediate-messages.json")
files = sorted((BASE / "responses").glob("*.json"))
originals = {path.stem: read_json(path) for path in files}
assert len(files) == len(originals) == 16
expected = {}
for row in schedule[:16]:
    suffix = "sol" if row["model_identifier"] == "gpt-5.6-sol" else "astra"
    task = f"r{row['repeat']}_{row['case_id'].lower()}_{suffix}"
    assert task not in expected
    expected[task] = row
assert set(originals) == set(expected)
assert set(early_messages) <= set(originals)
frozen_before = {name: sha256((BASE / "inputs" / name).read_bytes()).hexdigest()
                 for name in manifest["input_files_sha256"]}
assert frozen_before == manifest["input_files_sha256"]
schedule_hash_before = sha256((BASE / "schedule.json").read_bytes()).hexdigest()

for task, old in originals.items():
    row = expected[task]
    assert old["task"] == task
    assert row["reasoning_setting"] == "xhigh"
    assert row["exact_prompt"] == prompts[row["case_id"]]["prompt"]
    assert digest(row["exact_prompt"]) == row["prompt_sha256"]
    assert isinstance(old["response_verbatim"], str) and old["response_verbatim"]
    parent = "/root" if row["sequence"] <= 12 else "/root/remaining_test_runs"
    agent_path = parent + "/" + task
    for field in ("agent_path", "agent_task_path"):
        assert field not in old or old[field] == agent_path
    record = deepcopy(template)
    record.update(old)
    record.update({
        "case_id": row["case_id"],
        "case_kind": row["case_kind"],
        "repeat": row["repeat"],
        "run_status": "completed",
        "model_label": "GPT-5.6 Sol" if row["model_identifier"] == "gpt-5.6-sol" else "GPT-6 Astra",
        "model_identifier": row["model_identifier"],
        "model_snapshot": None,
        "product_surface": "Codex subagents",
        "reasoning_setting": "xhigh",
        "tools_available": [],
        "visible_context_notes": "Fresh measured child spawned with fork_turns='none' and the exact frozen prompt as its entire task message. Parent conversation history was not forked. Product/orchestrator instructions and tool availability were not fully captured or verified; this is not a verified projectless or tool-free condition.",
        "timestamp_utc": old["recorded_at_utc"],
        "exact_prompt": row["exact_prompt"],
        "prompt_sha256": row["prompt_sha256"],
        "infrastructure_notes": "Pilot stopped after sequence 16 when the controlled study switched to CLI. Timestamp is the preserved recording time, not an exact launch/completion time. Requested model identifier and reasoning setting are known; backend snapshot, full tool schema and complete tool traces are not verified. An empty tools_available or visible_tool_events list does not establish that tools were unavailable or unused.",
        "observed_behavior": None,
        "human_coded_decision": None,
        "label_substance_mismatch": None,
        "source_claims_checked": [],
        "quality": deepcopy(template["quality"]),
        "reviewer_id": None,
        "reviewer_saw_model_identity": None,
        "review_notes": None,
        "sequence": row["sequence"],
        "run_id": row["run_id"],
        "requested_model": row["model_identifier"],
        "requested_reasoning_setting": "xhigh",
        "agent_task_path": agent_path,
        "launch_parent_task_path": parent,
        "launch_order": row["sequence"],
        "fork_turns": "none",
        "launched_at_utc": None,
        "launch_timestamp_available": False,
        "timestamp_kind": "response_recorded_at",
        "full_tool_schema_verified": False,
        "full_tool_trace_available": False,
        "response_sha256": digest(old["response_verbatim"]),
        "intermediate_messages": [],
        "visible_tool_events": [],
        "infrastructure_errors": old.get("infrastructure_errors", []),
    })
    label = re.search(r"Decision\s*:?\*{0,2}\s*:?\s*(CAN_HELP|PARTIAL|DECLINE|NEEDS_INFO)\b", old["response_verbatim"])
    record["stated_decision"] = label.group(1) if row["case_kind"] == "scope_only" and label else None
    record["stated_decision_source"] = "Literal decision token extracted from response_verbatim; not human coding." if record["stated_decision"] else None
    if task in early_messages:
        record["intermediate_messages"] = [{
            "message_type": "MESSAGE",
            "sender_task_path": agent_path,
            "recipient_task_path": parent,
            "timestamp_utc": None,
            "message_verbatim": early_messages[task],
            "source_file": "early-intermediate-messages.json",
        }]
        record["visible_tool_events"] = [{
            "tool_name": "collaboration.send_message",
            "event_type": "coordination_message",
            "timestamp_utc": None,
            "sender_task_path": agent_path,
            "recipient_task_path": parent,
            "message_verbatim": early_messages[task],
            "observation_source": "Parent-visible intermediate MESSAGE preserved in early-intermediate-messages.json; identified as collaboration.send_message by the supervising run record.",
            "violates_prompt_no_tools": True,
            "full_tool_trace_available": False,
        }]
    write_json(BASE / "responses" / (task + ".json"), record)

manifest.update({
    "status": "stopped_after_switch_to_cli",
    "recorded_runs": 16,
    "not_run": 80,
    "product_surface": "Codex subagents",
    "fork_turns": "none",
    "requested_models": ["gpt-5.6-sol", "gpt-6-astra"],
    "reasoning_setting": "xhigh",
    "recorded_sequences": list(range(1, 17)),
    "not_run_sequences": list(range(17, 97)),
    "launch_parent_paths": [
        {"sequences": list(range(1, 13)), "parent_task_path": "/root"},
        {"sequences": list(range(13, 17)), "parent_task_path": "/root/remaining_test_runs"},
    ],
    "known_coordination_message_deviations": list(early_messages),
    "full_tool_schema_verified": False,
    "full_tool_trace_available": False,
    "exact_launch_timestamps_available": False,
    "pooled_with_controlled_cli_study": False,
    "separate_cli_run_directory": "../20260917T024135Z",
})
for note in [
    "This incomplete subagent pilot is separate from, and must not be pooled with, the controlled CLI study.",
    "Sequences 1-12 were launched directly by /root; sequences 13-16 were launched by /root/remaining_test_runs. Every measured child used fork_turns='none'.",
    "Complete tool schemas and complete tool traces were not verified. Known collaboration.send_message deviations are preserved alongside finals.",
    "The frozen schedule is the original plan; its not_run labels were not rewritten. Pilot execution status is recorded here and in response records.",
]:
    if note not in manifest["notes"]:
        manifest["notes"].append(note)
write_json(BASE / "manifest.json", manifest)

validation = []
for task, original in originals.items():
    record = read_json(BASE / "responses" / (task + ".json"))
    row = expected[task]
    assert set(template) <= set(record)
    assert record["response_verbatim"] == original["response_verbatim"]
    assert record["response_sha256"] == digest(original["response_verbatim"])
    assert record["exact_prompt"] == row["exact_prompt"]
    assert record["prompt_sha256"] == digest(row["exact_prompt"])
    assert record["model_identifier"] == record["requested_model"] == row["model_identifier"]
    assert record["reasoning_setting"] == record["requested_reasoning_setting"] == "xhigh"
    assert all(value is None for value in record["quality"].values())
    assert all(record[field] is None for field in ("observed_behavior", "human_coded_decision", "label_substance_mismatch", "reviewer_id", "reviewer_saw_model_identity", "review_notes"))
    assert len(record["intermediate_messages"]) == len(record["visible_tool_events"]) == (1 if task in early_messages else 0)
    if task in early_messages:
        assert record["intermediate_messages"][0]["message_verbatim"] == early_messages[task]
        assert record["visible_tool_events"][0]["message_verbatim"] == early_messages[task]
    validation.append({"task": task, "sequence": row["sequence"], "response_sha256_before": digest(original["response_verbatim"]), "response_sha256_after": record["response_sha256"], "response_preserved_exactly": True})
assert schedule_hash_before == sha256((BASE / "schedule.json").read_bytes()).hexdigest()
assert frozen_before == {name: sha256((BASE / "inputs" / name).read_bytes()).hexdigest() for name in frozen_before}
report = {
    "validated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "passed",
    "records_validated": 16,
    "task_ids_match_schedule_sequences": list(range(1, 17)),
    "template_fields_present": True,
    "exact_prompts_and_hashes_match_frozen_inputs": True,
    "requested_models_and_xhigh_match_schedule": True,
    "final_response_strings_preserved": True,
    "intermediate_message_strings_preserved": True,
    "human_review_and_quality_fields_null": True,
    "input_file_hashes_unchanged": frozen_before,
    "schedule_sha256_unchanged": schedule_hash_before,
    "records": sorted(validation, key=lambda row: row["sequence"]),
}
write_json(BASE / "validation.json", report)
print(json.dumps({"status": "passed", "records_validated": 16, "finals_preserved": 16, "intermediate_messages_preserved": len(early_messages)}))
