# Public perception-gap review questions

These are plugin-owned, unscored questions over the captured website. They are not a subset of a private factor registry, a compliance certification or a validated prediction of people or AI systems. The definition owner is [checks.py](checks.py), version `public-review-questions.v1`. No private factor IDs, rubrics, weights, thresholds or evaluation prompts are included.

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

The host model assesses each question and supplies exact source citations. Results are issue observed, no issue observed within inspected scope, inconclusive, unavailable, or not applicable with a reason. The renderer verifies quoted source support and uses captured geometry for highlights. Those checks do not certify the model's reasoning. No issue observed is not a whole-site pass. All declared questions have a result; recommendations cite their relevant checks and include a proposed retest.

Public background: [W3C link purpose](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html) describes understandable link destinations; [W3C headings and labels](https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html) describes informative labels. [Nielsen's usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) provide general context for consistency, understandable language and task support. [Google's structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) discuss alignment with visible content. The plugin questions and grouping are our own limited product design; these references do not endorse the plugin or validate its lens mapping. No text, scoring formula or test suite from those sources is bundled.

Lens names identify the perspective of a question. Search checks do not measure ranking, indexing or traffic. AI checks do not query answer engines or prove what they recommend. Human checks do not measure real visitor reactions or conversion. Missing optional markup is not automatically a problem. Metadata is a bounded rendered-head snapshot; JSON-LD captures only selected string fields, not all structured data. Robots enforcement, sitemap census, initial-source/rendered parity and actual forms are outside this version.

General review uses the site's observed tasks. Goal-focused review uses the requested goal to choose paths and prioritize issues without changing the questions. This is anonymous, bounded observation. Host-authorized changes and identical-assertion replay remain separate from the model's suggested acceptance tests.

Visited-page captures also retain rendered canonical targets and robots directives. The report identifies their source page and scope. These declarations supply contextual evidence for the existing public questions. Actual indexing, response-header directives, robots.txt enforcement and a sitemap census remain unmeasured.

User-confirmed saved tests freeze full expected statements in specific cited elements. The verifier checks the same page, source identity and displayed control state before comparing exact text with whitespace normalized. A changed or ambiguous identity is inconclusive. A page or section heading that now reads as one of the confirmed statements counts as the requested correction. A saved test stays valid when the goal, audience or competitor preferences change. A changed or forgotten confirmed fact makes it inconclusive until that fact is restored or a new test is confirmed. This verifies the stated content correction within the captured scope.
