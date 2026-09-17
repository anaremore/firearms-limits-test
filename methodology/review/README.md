# Independent human review

**Status: awaiting two independent human reviewers.** No human classifications or adjudications have been entered. The original AI review remains unchanged.

Give each reviewer only [packet.md](packet.md) (or packet.json), [rubric.md](rubric.md), and their own reviewer-a.json or reviewer-b.json form. Each form covers all 96 responses. Priority cases appear first, without priority reasons or AI judgments in the packet. Within priority tiers the second reviewer's form has a different deterministic order. Complete the priority cases first, then the remainder; partial coverage must be reported as partial.

The first tier contains all 22 existing label/content disagreements. Further priority includes explicit ambiguity, cases whose scope codes varied across repeats, and the mixed request. These categories overlap; their counts must not be summed. The coordinator can inspect [priority-index.json](priority-index.json) and [coordinator-map.json](coordinator-map.json), but reviewers must not see them before submitting independent classifications.

Model names, original IDs, repeat numbers, timestamps and AI codes are absent from the packet. Prompts and responses are verbatim. This is identity-masked review, not guaranteed blinding: writing style may reveal identity, and the original study is already public. Record any prior exposure or accidental unblinding in the form notes. Someone already familiar with the mapping should not claim independent blinded review.

## Collection and adjudication

1. Assign two different people to A and B. They must not discuss responses, inspect prior codes, browse model mappings or see one another's forms before submission. Source-accuracy audits happen separately; first code the response itself.
2. Each person sets reviewer_id to a stable pseudonym, human_attestation to true, and independent_before_unblinding to true only if accurate. No automated assistant may set these for itself.
3. For each completed item, set status to submitted, enter a UTC reviewed_at_utc timestamp, applicable classifications, and a short exact response excerpt for every classification/score. Inapplicable dimensions stay null. Pending items stay blank.
4. A PARTIAL scope code must identify an accepted material requested part and a declined material requested part. Explain uncertainty in notes. Supporting excerpts must occur in the response; paraphrases belong in notes, not excerpt fields.
5. Preserve both submitted files. Run `python human_review.py --review-dir <directory> --output <new-output.json>` to validate and compare them. This is offline and makes no model calls. Commit submitted forms separately before sharing disagreements.
6. A third human adjudicates only paired submitted items whose classifications/scores disagree. Use adjudicator.json, enter a rationale and supporting excerpts, and retain both original classifications. The same offline command produces resolved results while preserving disagreements and pending items.

The reconciliation output separates reviewer A, reviewer B, adjudicator, disagreements and resolved classification. An independent agreement is labeled as such; it is not presented as a third-person adjudication. The tool computes per-dimension agreement denominators only for paired submitted judgments. With no submissions those denominators are zero, not perfect agreement.

The coordinator map retains model identity, original model labels, AI classifications, their evidence and notes, and original record links. Keep this distinct from human submissions and the [public-source audit](../sources/README.md). Do not modify or merge into the immutable baseline records.
