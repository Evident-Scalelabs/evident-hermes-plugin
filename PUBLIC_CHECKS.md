# Public perception-gap review questions

The plugin applies the same unscored questions to an anonymous general or goal-focused review. The goal determines which paths to inspect. [Question definitions and outcome codes](checks.py) own the exact wording.

| Lens | Check | Evidence used |
| --- | --- | --- |
| Search Lens | Page labels | Captured title/description, headings and visible page text |
| Search Lens | Link meaning | Actual link text/context and followed destination |
| AI Lens | Declared information | Selected JSON-LD fields compared with visible statements |
| AI Lens | Answers in context | Information and qualifications relevant to the requested task |
| AI Lens | Information agreement | Attributed statements from the inspected pages, including different conditions |
| Human Lens | Offer clarity | Visible offer, audience and user goal |
| Human Lens | Terms at the decision | Published costs/eligibility/conditions along the inspected path |
| Human Lens | Supporting evidence | Captured support for important claims; unvisited sources stay unknown |
| Human Lens | Next step | Link promises, observed navigation and unresolved handoffs |

Each result cites inspected evidence and records an observed issue, no issue within scope, inconclusive, unavailable or inapplicable with a reason. Highlights identify the cited region. Recommendations name the check and suggest a retest.

Search evidence includes the rendered title, canonical and robots declarations. AI evidence includes selected JSON-LD strings and visible statements. Report a structured-data issue only when the captured evidence supports it. Optional markup may be absent. The lenses describe captured content. Ranking, indexing, answer-engine recommendations, conversion and visitor behavior require independent evidence. Coverage excludes response-header directives, robots.txt enforcement, a sitemap census, initial-source parity and form submissions.

For user-confirmed corrections, follow [saved tests and replay](docs/REFERENCE.md#site-memory-and-repeatable-corrections).

Background for these independently authored questions includes [W3C link purpose](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html), [W3C headings and labels](https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html), [Nielsen’s usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) and [Google’s structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies). Those sources provide background, without endorsing or validating the lenses.
