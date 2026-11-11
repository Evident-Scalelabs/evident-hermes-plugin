# Website reports in Hermes

Start a Hermes chat with **“Is this evident?”**

> **You** · Is this evident?
>
> **Hermes** · Sure. What’s your website? I can give it a general look, see how it comes across to your buyers, or focus on a particular product or journey. What would help you most?
>
> **You** · Our buyers are small teams. Can they tell which plan includes support?
>
> **Hermes** · Which website should I look at?

You can also say **“Evident, review this: https://example.com/”** with your decision in the same message.

Send the URL and Hermes follows the journey with that buyer and decision in mind. A returning site uses its saved goal. A new URL starts a general perception scan when you leave the focus open. You can request a new goal or a fresh general review. “Is my website evident?” opens the same conversation. The wording of Hermes’s replies can vary with its configured model.

You get **one offline HTML report** with highlighted screenshots, actionable findings and the limits of what Hermes could verify. By default the report also includes independent AI answers and a dedicated Competitors page with suggested alternatives, quoted contrasts, and concrete changes to test. You can ask for a website-only review.

Enable `browser_enabled` and `allow_model_interpretation` once in this plugin's settings. A report request then authorizes its public-page capture and host-model processing, which may incur cost. The plugin uses the supported `ctx.llm.acomplete_structured` image/text API; it never reads model credentials or overrides provider/model settings. A vision-capable configured model is required. Capture-only `observe`/`evident_browse` still works without model calls. `demo` reviews a fictional buying journey, then verifies declared fixture changes in one visual report.

The automatic report discovers real links, headings and supported display controls, selects relevant visitor tasks with the configured host model, follows actual anchors, and inspects useful sections across pages in one isolated browser context. It returns one report with journey summaries, observed issues separated from hypotheses and strengths, cross-page citations, priorities with reasons, concrete changes and acceptance tests. It does not claim an exhaustive crawl or canonical perception score. Links to other origins are listed as handoffs unless that origin is already operator-authorized; forms, sign-ins, purchases and scan submissions are never performed.

In chat, the website review and the requested AI comparison share a run ID across two bounded tool calls. Hermes follows the returned continuation in the same conversation. Each dispatch reserves time under the host deadline for saving and returning its result. Direct CLI and slash scans perform both stages in sequence.

Default safety budgets are eight pages and 600 seconds for capture plus planning, configurable as `review_max_pages` (2–12) and `review_seconds` (60–900), or per command with `--max-pages`/`--seconds`. These are ceilings, not quotas. Planning uses at most ten disclosed host calls (up to 5,000 output tokens / 60 seconds each); one final multimodal report call is capped at 9,000 output tokens / 120 seconds. Navigation stays within 24 recorded steps, a 15-second bound per link click, 400 requests, 64 MiB response-body budget and 12 MiB total image bytes. There is no hidden model retry. Same-host/www entry redirects are inspected up to three hops with pinned public HTTPS; interior document redirects are followed only within the exact authorized origin, up to three hops. Requested URLs, redirect receipts and final URLs remain distinct; original literal assertions are not rewritten. Navigation URLs with query strings or credentials remain omitted; browser fragment navigation is preserved. Exact query parameters on public display assets are retained, never rewritten. The actual expanded plan is saved immutably before verification; replay never replans or rewrites earlier assertions.

Missing screenshots, invalid exact source quotes or model failure preserve captured evidence and produce an explicitly incomplete result. A missing or incorrect screenshot index is resolved only when its quote uniquely matches a measured text container; otherwise the highlight is omitted. Adjustments are recorded; model interpretation is not rewritten. Planning choices, rejected selections, the navigation trace, original model output and usage remain in the profile-owned run. The report identifies inspected routes, unresolved tasks and uncaptured handoffs.

## Evidence and verification

A native Hermes plugin for rendered evidence, screenshots, bounded link navigation and repeatable task assertions. It also retains the lightweight HTTP-source workflow. The plugin observes and verifies; authorized host tools apply separately approved local changes. These are new plugin contracts, not canonical measurement or scoring services.

Licensing has not yet been specified. There is no connected service, account requirement for deterministic capture, telemetry, editing tool or scheduled job. A conversational host-authored review uses the normal Hermes session. Optional separate model explanation uses the configured Hermes model only after opt-in and explicit consent.

## Compatibility and installation

Site history uses Hermes's native profile-scoped `plugins.plugin_storage.plugin_db()` and a local SQLite database beside the immutable evidence store. The host must provide that interface. The plugin records business context only through its explicit memory and investigation tools.

## Site memory and repeatable corrections

The `evident_memory` tool recalls the site's goal, audience, confirmed facts, competitor corrections, finding feedback, prior reviews and saved tests. Corrections use the same key and retain a revision. Facts supplied by the user carry that provenance. Observations and model interpretations retain their dated run references. An unavailable source is marked explicitly.

Ask Hermes to remember or correct a fact, to show what it remembers, or to forget a selected item or the whole site. Forgetting removes the selected facts from retrieval. A retrieval boundary prevents older summaries from restoring forgotten statements. Historical reports and test records remain on disk. The `evident_delete` tool removes a specifically selected evidence run. Each Hermes profile has independent storage. Host conversation logs and host-created backups follow the host's retention settings.

For a saved correction, Hermes proposes the complete expected statement in each cited region. After the user confirms it, `evident_save_test` stores the finding, source selectors, page and section identities, displayed control states, expected text and baseline result. After an authorized edit, `evident_verify` accepts `test_id` and `change_context`. It replays the original journey and tests the same criteria. The report pairs highlighted before/after evidence. Site history retains the test's passed, failed or inconclusive outcome alongside its evidence run.

The first version compares exact rendered statements with whitespace normalized. Text in another region cannot satisfy a check. Additional contradictory wording fails the exact check. A missing page, ambiguous element, changed identity, truncated text, different control state or changed collection conditions yields an inconclusive result. Captures made before stable identity collection require a fresh baseline. Changed goals, audiences or confirmed business facts require new confirmation. Existing run-based verification remains available.

```sh
hermes evident verify TEST_ID --saved --change "The site owner corrected the confirmed pricing statement"
```

Comparable repeat reviews reuse their four saved buyer questions. The report compares individual answers, source-support counts, citations and suggested competitors. It records the actual model route and requested sampling settings. Changed conditions are labelled incomparable. Competitor include/exclude corrections guide future suggestions. Individual samples can vary even with identical settings. For more detail on a saved review, ask Hermes to expand its competitor page. It can call `evident_finish` with `competitors: true` for one saved analysis of the already captured public sources. This adds a model call and preserves the original review. Competitor choices remain editable through site memory.

Reports include a previous/next screenshot replay using retained images, measured highlights and the actual sequence of pages and controls. A fixed, hash-authorized offline script drives the viewer. Three leading actions stay prominent and further findings are expandable. Canonical and robots declarations are recorded on visited pages with their measurement limits.

General conversation memory, embeddings, multi-model campaigns, scheduling, Search Console, ranking/backlink data and mobile/keyboard investigations are planned extensions. This candidate uses site-specific history and the host's configured model.

## Host compatibility

Requires Python 3.11+ on a POSIX host with `O_NOFOLLOW` and `fcntl`, plus native `register_tool`, `register_skill`, `get_config`, `plugins.plugin_storage.plugin_data_dir` and `plugin_db`. Conversational routing uses the native pre_llm_call hook and, when offered by the host, register_system_prompt_section. Native loader and fixture tests ran on macOS with Python 3.14 against official Hermes v0.23.1 source, and on Linux with Python 3.13.5 and Hermes v0.21.5. The Linux host used the isolated loopback browser worker because its supervisor capture interface was unavailable. The manifest declares its concrete dependencies. Windows and vendor Desktop bundles require separate compatibility work. [Tested official Hermes source](https://github.com/NousResearch/hermes-agent/tree/3b421578588243f920886e6fe79a6faa87ea026e)

For an existing supported Hermes installation, extract the private ZIP and copy only its `evident-evidence/` directory into the intended profile's `plugins/` directory. A disposable test profile is recommended for first use. Do not replace an existing plugin directory without reviewing its local changes. Run the [official checks](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission):

```sh
hermes plugins doctor /absolute/path/to/evident-evidence --ci
hermes plugins validate /absolute/path/to/evident-evidence --install-deps
hermes plugins enable evident-evidence
```

The plugin declares `playwright==1.64.0`. The official plugin installer/validator prepares it. Install its matching managed Chromium using `python -m playwright install chromium` in the same Hermes runtime. Installation uses a native plugin directory. Configured-model URL reviews and memory conversations were exercised through the native Hermes CLI. Separate deterministic fixtures exercise real headless Chromium, native dispatch and verification without model interpretation. Use the retained receipts for the tested source revision and destination runtime.

In that profile's settings, explicitly authorize anonymous read-only origins. Default settings deny all capture. Public mode permits HTTPS on port 443 only. `fixture_origin` is an optional single **isolated synthetic** server, using literal `127.0.0.1` or `::1` and an explicit non-default port; it is not permission to inspect unrelated local services. Example configuration:

```yaml
plugins:
  enabled: [evident-evidence]
  entries:
    evident-evidence:
      settings:
        browser_enabled: true
        browser_server_url: ""
        allow_model_interpretation: false
        authorized_origins: ["https://example.com"]
        fixture_origin: ""
```

Low-level capture tools cannot grant origins or change these settings. The requested URL report has its own run-scoped public host/www-alias grant. Host development tools remain governed by host/user approvals. Configure only targets you are authorized to read without transactions or side effects; anonymous GET requests still reach a website and its logs.

## Review a real website

Ask Hermes: **Give https://example.com/ a general perception-gap review and return the report.** The bundled skill uses `evident_scan` to complete capture, model interpretation and HTML delivery in one operation. The direct slash command uses the same implementation. `evident_report` remains available for custom evidence journeys; it is not a required second user step. Exact-quote/geometry validation checks citations, not the semantic truth of model conclusions.

## Run capture directly without a model account

After installing/enabling the plugin, these are native Hermes commands (also available as `/evident ...` in chat):

```sh
hermes evident authorize https://example.com
hermes evident observe https://example.com/ --contains "Example Domain"
hermes evident verify RUN_ID --change "Describe the local change"
hermes evident view RUN_ID
```

`--json` opts into machine-readable CLI output; chat commands always return concise prose. `/evident demo` follows a five-person buying goal on a fictional Trailnote site. It opens the plan selector and two FAQs, sends the actual retained text/images to the configured Hermes model, and leads with three evidenced actions when supported. The separately authorized demo harness edits three copies on its own temporary loopback site; the observer replays the identical plan and assertions. One HTML attachment contains highlighted before/after captures and expandable full evidence, exact changes and provenance. The checks prove rendered text/state changes, not customer outcomes or every part of a model recommendation. Partial capture or model failure stays visible. This demo requires the existing browser/model opt-ins, may incur host model cost, and never edits a real scanned website. Independent AI answers/competitors are reserved for real URL reports; they would be misleading for the fictional fixture.

For a rendered tool call, use `evident_browse` with:

```json
{"plan":{"mode":"browser","objective":"Read opening hours through the declared link","viewport":{"width":1280,"height":800},"limits":{"seconds":30,"resources":40,"bytes_per_resource":524288},"steps":[{"action":"open","url":"https://example.com/","assertions":[{"kind":"visible_text","expected":"Example Domain"}]}]}}
```

An empty assertion list captures observations without a pass/fail outcome. Add `{action: "scroll", offset: 1200, assertions: []}` for lower viewports (offset 0–12000), or add `follow_link` steps with an exact CSS `selector` for one anchor and fixed `visible_text` assertions. Forms, arbitrary buttons and script inputs are unsupported. Recorded disclosures, tabs and outside-form grouped radios support `activate_control` as described below. Use `evident_screenshot` with `run_id` and zero-based `step` to display the actual retained viewport. Browser before/after verification reuses the exact plan, viewport, collector and recorded Chromium version/connection mode. Rendered text is bounded; a missing match in truncated text remains unknown.

The browser is deliberately constrained: only validated, anonymous document/display-resource GETs are fulfilled through the pinned-IP transport. XHR/fetch, forms, workers, frames, popups, sockets, downloads and cross-origin or over-budget redirects are blocked. Cookies and request credentials are not forwarded. Blocked resources may change layout or prevent an app from loading; the receipt exposes the captured/blocked resource ledger. A screenshot establishes only the recorded rendered viewport, not a complete unrestricted user experience.

## Optional isolated browser worker for Docker hosts

If a host cannot provide Chromium's sandbox, the plugin fails explicitly. The independently authored optional worker in `browser_server/` uses public Playwright `launchServer`/`connect`, with matching Playwright 1.64.0 on both sides. It is not a private Evident service or a CDP/personal-browser adapter. Set the new plugin setting `browser_server_url` to the operator-created loopback endpoint, for example `ws://127.0.0.1:9777/evident-evidence`. Only literal loopback WebSocket endpoints are accepted; tool inputs cannot set it.

The included Dockerfile pins an official Linux amd64 image. Run the worker as a separate non-root container with no credentials/data mounts, no public port, and the [official version-pinned seccomp profile](https://github.com/microsoft/playwright/blob/v1.64.0/utils/docker/seccomp_profile.json) so Chromium's sandbox remains enabled. Bound its memory/CPU and temporary storage. The worker must share the caller's network namespace for loopback access. That endpoint has no separate authentication and must stay within the trusted local runtime. Deployment is operator-owned; plugin registration never creates a service or changes Docker security settings.

The default mode launches a fresh sandboxed process with a scrubbed browser environment and temporary home. Worker mode uses a dedicated managed browser process and creates a fresh isolated context per run; contexts and pages are closed after capture, including errors. It never selects an existing default context. Mode changes make previous baselines incomparable. Worker startup/connect failures do not fall back to an unsandboxed browser. No host network forwarding is requested through Playwright.

## Optional model explanation

Enable `allow_model_interpretation` in this plugin's settings after configuring a model through Hermes's normal setup. Then call `evident_explain` with `run_id` and `consent: true`, or `hermes evident explain RUN_ID --consent`. It sends at most 4000 retained text characters per step, no screenshots, for one bounded structured explanation (900 output tokens, 30-second host timeout). It uses `ctx.llm`, never reads credentials and does not override the configured provider/model. Cost may apply.

The explanation cites known step indexes, keeps assumptions/limitations explicit, and is persisted separately before being returned. It never changes assertions or evidence. Repeating the call returns the saved explanation. Model-provider behavior is unit-tested with a labeled mock; a live configured model is a separate test, not inferred from that mock. Screenshots, navigation and literal verification do not require model calls; the goal-focused demo does.

The controlled demo has a separate real browser integration check:

```sh
python tests/integration_demo.py --receipt-dir /path/to/private/demo-receipts
```

It tests real rendering, plan selection, FAQ expansion and identical-assertion replay without model calls. A live `/evident demo` run through the installed Hermes model is separate evidence for interpretation and report delivery.

## HTTP-source evidence loop

Use `skill_view("evident-evidence:evidence-loop")`, or call `evident_observe` with:

```json
{
  "plan": {
    "objective": "Check the declared source text",
    "steps": [{
      "url": "https://example.com/",
      "assertions": [{"kind": "text_contains", "expected": "Example Domain"}, {"kind": "http_status", "expected": 200}]
    }],
    "limits": {"seconds": 10, "bytes_per_page": 65536}
  }
}
```

`evident_inspect({"run_id":"…"})` retrieves the plan, step evidence, final receipt and saved report path. If a call times out, ask “Get my saved Evident report for [exact URL].” Hermes can use `evident_inspect({"url":"…"})` to find the latest matching request in this profile, or supply a run ID and `summary_only: true`. The response identifies the URL, goal, stage and retained evidence. A running review can be inspected again. An interrupted review with evidence yields a labelled partial report. A saved website stage with pending, previously requested comparison work can be continued with `evident_finish`. Asking only to retrieve a report makes no network or model calls. The HTML is exported automatically inside the owning run; it contains no executable page content or external resources. JSON artifacts are already on disk. No viewer server is started.

After the host applies a separately approved local change, call `evident_verify({"run_id":"…","change_context":"Describe the actual change"})`. Verification accepts no replacement URLs or assertions. It replays the saved plan under the **current** authorization settings. The plugin never writes to the target site or source workspace.

An explicit sequence of URLs is a task trace of separate requests. It does not demonstrate link navigation, clicks, form completion, screenshots or a browser journey. Assertions are literal, case-sensitive substring checks over parsed source text, or exact HTTP-status equality. They do not infer business meaning. HTML text nodes are joined with newlines; scripts, styles, templates, textarea content and element attributes are omitted. Hidden text can remain. A source-text match does not establish rendered visibility.

## New plugin result contract

`evident-evidence.v1` (HTTP) and `evident-evidence.v2` (browser) are plugin-owned envelopes. Each run has an immutable plan, UUID, per-step records and final receipt. HTTP step records retain requested/fetched URL, timestamps, status, MIME, response-byte count, peer IP, source text, locator and assertion outcomes. Browser steps retain rendered text, screenshot bytes/hash, navigation URL, title, scroll position, visible heading/link geometry and assertions; the request ledger retains status, MIME, byte count, peer and body hash for captured resources. `sha256` hashes the received body (not retained as raw HTML); `source_text_sha256` hashes the retained UTF-8 text. Hashes indicate local content identity, not independent source validation. No canonical page key is generated.

Collection states are `complete`, `policy_stop`, `timeout`, `error`, `cancelled`, or `incomplete` when no final receipt exists. `unavailable` describes a tool/config/storage refusal. An assertion is `true`/`false` only for an observed source response or rendered step; otherwise its outcome is null. An unmet assertion is not automatically a website defect. Successful earlier steps remain inspectable after a later failure. Unsupported MIME, encoding, truncated content and byte-limit failures yield no negative assertion.

Verification compares the original plan and collector/Python environment, plus the recorded browser version and viewport in browser mode. Each shared assertion is `unchanged`, `met_after`, `regression`, `unknown`, or `incomparable`. `verified` means the same assertion was observed both times in comparable collector conditions. It does not prove causality, conversion, trust, ranking, human behavior or revenue. Timestamps and content hashes are retained; dynamic website state may differ even with identical settings. HTTP capture itself performs no model interpretation; the explicit explanation tool is separate.

## Limits, privacy and retention

- Explicit 1–24 steps and 0–5 assertions per browser navigation step (1–5 for HTTP source checks). Time budget: 1–30 seconds total network work; body budget: 256–65,536 bytes per page; response headers: 16 KiB. Parsing/persistence adds bounded local overhead. No retries or cross-run caches. Browser mode separately allows up to 900 seconds, 400 network requests of up to 4 MiB each, with a shared 64 MiB body budget, four concurrent transfers, a 320–1600px viewport and full-page images bounded to 20,000px height, 2 MB per image and 12 MiB total image bytes. Actual response-body reads count even on failure; unused reservations are returned. Successful display assets are cached only within this run, under the same byte bound; cache hits and policy refusals do not consume network-request slots. Diagnostic events are separately bounded to 640. One capture/cleanup/report export/model explanation at a time per profile. Different profiles have independent stores.
- DNS answers must all be public, then the socket connects directly to one validated numeric address with original TLS hostname verification. No second hostname lookup for connection, proxy, cookies, credentials or arbitrary request headers. IPv4/IPv6 special/transition addresses are rejected. Redirects are not followed. In HTTP mode, only explicitly supplied pages are fetched and subresources never load. Browser mode fetches validated display resources within the declared budget. A blocked redirect requires a new authorized target/baseline.
- Navigation URLs with query strings, fragments, embedded credentials or ambiguous authorities are rejected before persistence. Display assets (stylesheets, scripts, images and fonts) may retain exact query URLs and use public HTTPS CDN origins, checked by the same pinned-IP transport. This does not grant navigation to those origins, private-network access or credentialed requests. Exact accepted URLs are retained without canonicalization. Only anonymous public pages and synthetic fixtures are intended. Source text can contain personal/sensitive content; this is not comprehensive redaction. HTTP-source parsing omits input attributes, but text elsewhere may remain. Screenshots can contain any values visible in the captured viewport.
- DNS resolvers and requested websites receive normal network traffic. Raw bodies are held in bounded memory for parsing, then discarded. Extracted text and tool results may reach the host conversation/model provider without invoking the optional explanation tool; that tool makes one disclosed host-model call when explicitly enabled and consented. Host session billing is unknown. Response-body bytes are measured for successful captures; failed-request transfer totals are unknown.
- Local records live under the active profile's `plugin-data/evident-evidence/<run-id>/` with restrictive file permissions, exclusive writes and symlink refusal. No arbitrary file-path tool input or artifact import exists. A 50-run cap prevents unbounded growth; each JSON artifact is capped at 4 MB and each exported report at 20 MB, including before/after images. No automatic eviction or upload. Hard termination can leave an incomplete record; inspect preserves completed steps.
- Async cancellation retains completed steps and a cancellation receipt when delivered to the handler. End-user Ctrl-C propagation in a packaged Hermes application is not established; the network deadline still bounds each run.
- `evident_delete({"run_id":"…","confirm_delete":true})` removes only that selected run after the user requests it. Unexpected files cause refusal. This cannot erase host chat, backups, external provider records or website/DNS logs. Exported views stay inside their owning run and selected-run deletion removes them too. Evidence embedded in another run’s comparison report remains with that later run. Removing the plugin does not imply deletion of retained data.

## Reproduce the checks

In this directory with Python 3.11+:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/integration_http.py
```

The first command contains transport-boundary mocks for mixed DNS and address pinning; it is not live DNS-rebinding evidence. The second uses actual disposable loopback sockets and newly authored synthetic responses. It exercises repair, unchanged output, regression, second layout, page injection, chunked transfer, redirect refusal, size limits, local-origin isolation, revoked scope, timeout and cancellation.

With a clean public Hermes source runtime and its validation dependencies available, run the real loader/registry test in an empty environment and disposable profile. It loads the candidate as an enabled native plugin, invokes the registered handlers, retains before/after artifacts, and checks profile isolation:

```sh
HERMES_HOME=/absolute/disposable/profile python tests/integration_hermes.py /absolute/hermes-source --receipt-dir /absolute/private-receipts
```

Add `--public` only to authorize one anonymous HTTPS capture of `https://example.com/`. The synthetic edit is a test-harness operation, not a recording of interactive host approval. No paid production operation or model is involved. Real host/source integration and protocol mocks are distinct evidence; neither establishes a connected backend contract.

For the rendered integration, install the pinned Playwright dependency and its managed Chromium, then run (only where isolated native browser execution is authorized):

```sh
python tests/integration_browser.py /absolute/hermes-source --receipt-dir /absolute/private-rendered-receipts
```

This fixture exercises real Hermes dispatch, JavaScript rendering, hidden-text exclusion, anchor navigation, screenshots, identical-assertion repair and regression, redirect boundaries, and request restrictions. It uses synthetic local content without model interpretation. Executed-test receipts identify the source revision and serving host for each run.

Saved business-claim tests have a separate native fixture. It checks wrong-region text, a remaining contradiction, a correction, a missing page and ambiguous identity using the same criteria, then checks remembered outcomes and profile isolation.

```sh
python tests/integration_saved_retests.py /absolute/hermes-source --receipt-dir /absolute/private-retest-receipts
```

## Journey integration check

`python tests/integration_journey.py --receipt-dir /absolute/private/test-output` exercises real browser navigation across a synthetic three-page path, source-linked cross-page annotations, immutable expanded-plan replay, invalid-reference/boundary refusal and no form submission. Its planning/model content is explicitly mocked. A live configured host-model run is separate evidence. Optional `--browser-server` uses the explicitly configured loopback worker.

Adaptive runs retain `planning-0.json` through `planning-9.json` and an immutable `execution-plan.json`. `evident_verify` reads that expanded plan and repeats it without a planner; every original assertion remains unchanged. Navigation checks use the selected observed link's literal destination, declared before clicking. `return_to` can only revisit a previously observed URL; `follow_href` clicks a real same-window non-download anchor; `focus_heading` targets one recorded heading. These steps accept no model code. Successful navigation checks do not prove task completion or commercial improvement. The scope is checked again on replay.

Automatic control investigations execute one action per observed state. Remaining choices are resolved against the latest retained inventory using the complete control identity. Changed or missing identities are recorded as rejected; newly observed controls require a fresh host decision. The browser checks the identity again immediately before clicking. It does not relax an identity match or substitute another selector to recover a stale choice. `tests/integration_auto_controls.py` exercises changing plan details, a stable FAQ, and unchanged-assertion replay with a real browser and explicitly mocked relevance decisions.

Approved interior redirects cancel the original browser request without loading a failed-request page, then issue each checked hop through the same pinned transport. Cleanup refuses new resources and separately bounds route removal, pending-resource settlement, context closure and connection closure to ten seconds each. Cleanup failures remain in the receipt and prevent a complete result; a supervisor-owned browser is never closed by this cleanup.

Visible form labels and empty-field placeholders can support a citation and highlight. Populated field values are never returned as element text; forms are not submitted. Screenshot content remains a picture of the public anonymous page, so this is not a promise of universal visual redaction.

Form privacy: populated inputs, controls without a displayed placeholder, selects and editable regions are hidden from captured text and masked in PNGs. Empty placeholders remain visible evidence. Each step records this masking. This is targeted control masking, not a claim of complete personal-information detection or redaction.

## Report presentation

The report uses Evident’s palette and an action-first document layout with overview, recommendations, findings with captured evidence, visitor journeys, supporting screenshots, method and a link to explore a deeper report at https://evident.so/. Each image is embedded once; focused source crops carry measured highlights, with an expandable full-page capture. Finding numbers link back to the relevant recommendation. The footer links to evident.so as publisher; the overview explicitly labels the reviewed site. The configured Hermes model writes an evidence-backed cover headline, standfirst and action-first summary in the same final report call. All analytical content comes from that retained Hermes review, with observations, hypotheses and strengths distinguished. System serif/sans/mono fonts keep the HTML self-contained without remote fonts or tracking. The CTA does not upload the report, submit the target or start a scan. This presentation is independently implemented for the plugin; it does not include private evaluation methods or full-service scores.

Image encoding is recorded per run: PNG is retained when it fits; oversized photographic pages use a fresh native browser JPEG at quality85/65/45 with the same measured dimensions and masks. PNG and JPEG artifacts remain inspectable through the same screenshot tool. Model inputs contain source text and element indexes/text; full geometry stays in the retained owner artifact and determines report highlights.


## Focused perception-gap review

The current report uses [nine public review questions](PUBLIC_CHECKS.md), not private Evident factors. Each has an explicit evidence-linked outcome and each recommendation identifies its checks. This is an unscored model assessment, not a search-performance, external-AI-answer or visitor-research measurement.

For a direct command, `/evident URL` or `/evident scan URL --general` starts a general review immediately. Supply `--objective "Help a first-time visitor choose the right product"` for a focused review. The tool and noninteractive CLI also default to general when called directly. Conversational intake uses the website and focus from the current chat.

One concise report puts changes, evidence and completion checks first. Supporting rationale, the complete check readout and technical trace expand in place. All retained screenshots, measured highlights and original full-page captures remain in the same HTML. The final CTA links to evident.so without uploading anything. Captured rendered head declarations and selected JSON-LD fields supplement visible text; declaration-only quotes do not get invented screenshot locations.

## Independent AI answers and suggested alternatives

URL reports include AI answers and suggested competitors automatically, for both general and goal-focused analysis. Use `--no-context` or `context: false` only for a website-only report; `--context` remains accepted. The same report retains all website screenshots and adds visual answer/site comparisons and alternative-position cards. The context section adds seven configured-host-model calls, plus one follow-up check when linked evidence is captured, and at most one format-recovery call for each of the four independent answers and anonymous public HTTPS reads of up to eleven distinct model-suggested sources and six additional observed source links (at most three same-origin redirects each, 4 MiB per response). Context has a separate 360-second ceiling. It uses no search API, private Evident service, new provider credentials or model override.

Four role-consistent questions are frozen before answering: branded overview, branded conditions, category options and category decision. Their wording follows the visitor goal and asks concrete customer decisions, not a website-audit checklist. Every answer receives only its own question, without the captured pages, findings or earlier answers. The actual served route and usage are retained; route changes are flagged. These direct host-model calls have no retrieval tools. References are model-supplied; known URLs can be supplied without inventing quotations. After retrieval, a separate configured-host-model pass classifies exact answer spans as factual claims, advice, author uncertainty or other text. Only factual claims enter the supported/contradicted/unknown counts; advice and other text remain separately inspectable. Factual premises inside advice remain factual. Unclassified gaps are retained as visibly unknown. Classification and original text are then frozen.

The same pass selects up to six observed source links to investigate unresolved factual claims. Each source keeps up to 120 eligible links within 24 KiB from a bounded 640-anchor inventory, prioritizing links outside navigation landmarks and disclosing truncation. Relative links respect the fetched document URL and any HTML base URL. Follow-up selection excludes known PDFs, archives and non-text display/data assets using standard MIME mappings, and the model is told to choose readable guide sections rather than PDFs or downloads. Unknown suffixes remain eligible; the actual response MIME still determines whether a source can be read. The plugin validates the selected parent, link and answer indexes; it cannot fetch a model-invented follow-up URL. A uniquely matching claim reference may omit outer formatting whitespace; the original claim span and requested reference are both retained, and internal text changes remain invalid. Public HTTPS destinations may differ from the parent origin, but each uses the existing DNS-pinned, anonymous transport and exact-origin redirect policy. Query strings, fragments, credentials, private addresses, cookies, forms and browser access are not added. One round only, within the existing 360-second context budget; no repeated attempt around a block.

A final check reassesses factual verdicts for answers with additional captured evidence, using only that answer's cited pages and selected linked evidence. Earlier support can change when the followed evidence conflicts; classification and wording cannot change. Supported requires exact passages establishing the whole claim and qualifications; contradicted requires explicit incompatible evidence; absent, conflicting or insufficient evidence stays unknown. Code binds exact answer/source spans and scope, not semantic truth. Invalid pieces cannot confer support or discard valid siblings. The report shows factual counts, separate advice, expandable passages and a source-following trail identifying evidence discovered after answering. Original and followed sources remain distinct. Older reports stay unclassified or unassessed rather than receiving invented classifications. This is an independent sample, not a live survey of search/answer engines.

The model compares exact answer quotations with exact retained website quotations, distinguishing consistency, tension, omission and unknown. Differences suggest a check or clarification; they do not automatically make the website wrong. Three suggested competitors/alternatives are conditional on offering, audience, geography and goal. One public source page per candidate supports the compact comparison; this is HTTP text, not a rendered competitor journey. Fewer candidates are retained when evidence is insufficient. A rejected candidate could reflect a wrong model inference, brief, audience or region; it is not itself proof of positioning failure. Supply the intended alternatives or scope in a new goal-focused request to refine the comparison.

Questions, raw model outputs (including context-claims.json and context-claims-followup.json), observed links and context-followups.json, source receipts, bound claim checks and comparisons are immutable context artifacts alongside the original evidence. Enrichment failure keeps the completed website report and labels only the context incomplete. No private factors or new scores are introduced.

Link discovery excludes fully clipped carousel slides and transparent links, while retaining below-fold links reachable by ordinary scrolling. Image alt text or an explicit accessible label supplies the name for image-only anchors. The same visibility check selects a reachable duplicate when following a recorded link. No arbitrary carousel controls or generic buttons are activated.

Before closing the isolated context, capture cancels outstanding resource transfers and records them as interrupted. This prevents late resource callbacks from writing errors after a bounded run ends.

Resource diagnostics retain at most 640 events; omissions are disclosed. Per-document HTTP status and aggregate network/cache counts are maintained independently, so truncating repeated asset events cannot hide a later HTTP error or undercount cache reuse.

If an independent answer fails the JSON contract, the plugin asks the same question once more with a format reminder, without supplying the failed answer or website evidence. Both raw responses are retained; the report discloses a recovered format retry in the answer's evidence details. A second invalid response remains unavailable. There is no semantic rewriting, citation repair or retry loop; the existing overall context time limit still applies.

## Local FAQ and plan interactions

The planner can open native `details/summary`, buttons with `aria-expanded` and a unique `aria-controls` target or a uniquely identified region whose `aria-labelledby` names that button, ARIA tabs in a tablist with an associated tabpanel, and labeled radio choices in an outside-form group. It selects a retained control index; the browser resolves and revalidates its exact DOM identity immediately before acting. Already-active controls are not toggled closed. No business/domain keyword rule defines which control matters: the configured host model selects from observed labels and the review objective.

Each action records the before/after state, confirmed activation, newly rendered text, geometry and screenshot. `control_active=true` is a repeatable assertion, not a claim that the content is correct. The frozen execution plan replays the same identities and assertions. Opening an answer is counter-evidence to an earlier missing-information hypothesis; different plan states are not treated as conflicting prices.

During local control capture, **all new network requests are refused**, including navigation, scripts, images and GET side-effect attempts; cached display resources alone may be reused. The existing form/XHR/socket/worker/popup restrictions remain. This is observation in a disposable anonymous context, not account, cart, checkout, consent or submission automation. Controls that need fresh network data or lack supported DOM relationships remain unverified. Separately selected link navigation resumes the existing authorized navigation policy. The inventory is capped at 80 controls and each click at ten seconds, within the existing 24-step, page, time and image budgets.

Run `python tests/integration_controls.py --receipt-dir /absolute/private/path` with the declared browser runtime to exercise real local controls, blocked side effects, forged identities, masking, and same-assertion repair/replay. Its planner is mocked; live Hermes acceptance is separate.

## Browser interoperability and visual evidence

Website reports try Hermes's documented supervisor capture interface using a uniquely named native session and a fresh context. The host must explicitly select `browser.cloud_provider: local` and `browser.headless: true`; existing profiles, custom executables and CDP overrides are refused. On older hosts or missing native tooling, the configured isolated worker (or managed Chromium) remains available. The run records why native reuse was unavailable. Native lifecycle contract tests use mocks; a separate real managed-Chromium supervisor capture test passed on the inspected Hermes source. Neither establishes support on every Hermes version.

`allow_hosted_browser` is off by default. Enabling it permits the explicitly selected Hermes cloud provider and its charges; it does not configure credentials, enable credential auto-detection, solve challenges or bypass access controls. The evidence network policy still applies: this is not an unrestricted hosted browser or a promise to overcome 403 responses. Hosted provider integration requires a separate real-provider test.

Website scans allow anonymous same-origin GET fetch/XHR data (including JSON) and public display resources during supported interactions. The existing pinned-address transport protects private networks. Forms, POST, workers, sockets, frames and unapproved origins remain blocked; cookie-dependent and cross-origin APIs may fail. GET is not a proof of server-side non-mutation. Direct capture defaults to the stricter existing mode; verification reuses the baseline network mode. Controls include disclosures, semantic tabs, grouped radios and labelled native selects outside forms, with bounded state confirmation. Closed shadow roots and custom controls without sufficient semantics remain unsupported.

The bundled `evidence-diagrams` skill is loaded into the report request. Visuals use actual capture order, public check outcomes and cited observed/proposed actions. They do not infer scores or visitor behavior. Original highlighted screenshots and full evidence remain in the same offline HTML. Set `show_evident_cta: false` to omit the separate deep-report invitation; attribution remains. There is no tracking or automatic upload.

Run `python tests/integration_read_data.py --receipt-dir /absolute/private/path` for delayed API disclosures, native selection, blocked POST/form controls and identical-assertion replay using real Chromium. No live model is used in that fixture. Broad website coverage remains unmeasured; retain blocked and partial tasks in any benchmark denominator.

Long pages retain labelled image regions around the investigated state, with a bounded viewport fallback when a full image is too expensive. Captured element coordinates are translated into that retained image; unseen areas do not receive highlights. Native fragment navigation preserves the actual URL and counts a document once across its fragment states. Query-bearing document navigation remains unsupported. Privacy masking uses CSSOM without disabling the website's content-security policy. Font responses served as generic binary are accepted only for browser font requests with a supported font signature.

Default URL reviews account for every pending supported control on the current page: the configured model chooses investigate, skip or unknown with a reason. Selected control investigations run before leaving, one action per refreshed observation; navigation yields for the next page’s review. Panel/media metadata supports opaque labels without reading hidden answers as visible evidence. No domain or keyword rule decides relevance. The report’s Control investigation disclosure separates actual changes, already-active checks, skips and unresolved controls. Budgets and unsupported controls still limit coverage; no whole-site completion guarantee.

Control interactions, section-focus and scroll states retain a labelled region up to two viewports high around the selected state, instead of repeating the entire page. Repeated control states use native JPEG at quality 85; first page captures keep the existing PNG/long-page JPEG policy. These choices conserve the unchanged 12 MiB run image budget. Region origins and measured highlight coordinates stay attached to each state; unavailable captures still remain explicit.

The final host review supplies source-bound qualitative exhibits: contrasts or sequences of observed/proposed states. The renderer draws these labels without inventing conclusions or quantitative scores. Invalid diagrams are omitted individually while their findings remain. Full quotations, rationale and collector detail use disclosures; all retained screenshots remain available through the visual evidence gallery.
