---
name: evidence-diagrams
description: Turn website evidence into decision-ready visuals. Use when explaining recorded journeys, information conflicts or proposed website changes.
version: 1.1.0
metadata:
  hermes:
    tags: [reports, evidence, diagrams]
---

# Evidence diagrams

Choose one question for each exhibit: where did the journey stop, which claims disagree, or what should change?

Use a route for an actual sequence, a paired card for observed versus proposed content, and a status grid for check coverage. Give each node or claim a retained source reference. Routes follow the recorded trace: preserve returns, control changes and failed steps. A list of supporting sources is not proof that a visitor followed that sequence. Show suggested routes separately and label them proposed.

Write action titles as concrete changes. Keep observed content to one short sentence, the proposed change to one or two sentences, and the completion test to one sentence. Preserve qualifications that affect the decision. Put detailed rationale and secondary quotations in expandable evidence. Keep annotated screenshots beside the actions they support.

Use measured values only when the evidence contains them. Category colors communicate status, never an implied score, probability, priority calculation or customer emotion. Missing evidence stays visibly unknown. Do not invent trust curves, conversion funnels or competitor rankings.

For example: a captured product page leads to pricing, then an opened billing FAQ. The route labels those three recorded states. A separate change card proposes moving the billing qualification beside the price, cites the FAQ screenshot, and defines completion as seeing the same qualification in both places. It does not claim the proposed placement improved conversion.

The report renderer owns escaped markup, responsive layout and accessible text equivalents. Supply plain text and existing evidence references; do not generate executable HTML or arbitrary SVG. Review the exhibit at desktop and mobile widths and confirm every reference resolves.

## Structured exhibits

For each final-review note, supply `exhibit`: `kind` (`contrast` or `sequence`), `title`, and two to four `nodes`. Each node has a short `label`, `text`, `basis` (`observed` or `proposed`) and `evidence` indexes. Index 0 means the note's primary citation; 1 onward means its related citations in order. Cite the observation motivating a proposed state and label that state proposed.

A contrast exposes the decision in the evidence: two incompatible limits, stated terms versus another page, or an answer versus its qualification. Put the meaningful value or short qualitative state in `text` (about eight words), with its scope in `label`. A sequence shows observed handoffs or a proposed arrangement; proposed nodes never become claims of completed changes. Choose the relation from the actual evidence, not from note kind or a preset business keyword list. The note’s existing `uncertainty` supplies the diagram caption: one short material caveat.

The diagram carries the explanation. The adjacent action says what to change in one sentence; the completion test says what to verify. Use the expanded evidence for detail instead of repeating every diagram label as prose.
