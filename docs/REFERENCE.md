# Evident technical reference

[Marketplace overview](../README.md) · [Plugin settings](../plugin.yaml) · [Dependencies](../DEPENDENCIES.md)

## First-time setup

1. In the intended Hermes profile, install and enable the catalog plugin.

   ```sh
   hermes plugins install evident-evidence --enable
   ```

2. Install managed Chromium from the Python environment that runs Hermes.

   ```sh
   python -m playwright install chromium
   ```

3. Merge these values into the profile's existing plugin settings. Preserve other entries. Model interpretation sends captured public text and screenshots to the configured Hermes model and can incur usage costs.

   ```yaml
   plugins:
     entries:
       evident-evidence:
         settings:
           browser_enabled: true
           allow_model_interpretation: true
   ```

4. Reload the profile, start a fresh chat and ask **“Is this evident?”** Supply your URL and, for a focused report, the buying decision to investigate. Interpreted reports require a vision-capable configured model.

URL reviews grant the requested public origin for that run. Capture-only tools use the profile's explicit authorization. Browser capture and model interpretation start disabled.

## Review a real website

Use chat or `hermes evident scan https://example.com/ --objective "Help first-time buyers choose a plan"`. Omit the goal to use the site's saved focus or the general review for a new site. Use `--general` to reset the focus. The URL tool uses the same implementation. In chat, `evident_scan` and its `evident_finish` continuation share one run ID and one report.

The review follows selected relevant links and display controls within its budget. The offline report contains observed strengths and problems, hypotheses, concrete changes and completion checks. Each of the [nine public questions](../PUBLIC_CHECKS.md) has an evidence-linked outcome. Measured text and image regions support highlights. Selected metadata and JSON-LD can support source claims without a screen location. The review covers the recorded states and tasks. Protected steps, failed reads and unvisited states remain gaps.

[The manifest](../plugin.yaml) owns budget settings and defaults. `--max-pages` and `--seconds` override the page and capture/planning ceilings for one run. The [review implementation](../interpretation.py) owns planning, vision and final report limits. The [browser collector](../browser.py) owns navigation, request, body and image caps. Reports retain actual work, metered calls, exact source text, requested/final URLs, capture geometry and unresolved tasks. Interrupted work can return a labelled partial report.

To recover a saved report, ask Hermes for it by exact URL or use `evident_inspect` with a run ID and `summary_only: true`. Retrieval performs no network or model calls. For already requested comparison work that stopped after the website stage, resume the same run with `evident_finish`.

## Independent AI answers and suggested alternatives

URL reports include four independent questions by default. Use `--no-context` or tool input `context: false` for a website-only review. The configured model receives each question without the scanned site or other answers. These are sampled model answers. The report retains the actual model route, questions, answers and source checks.

[The context collector](../contextual.py) bounds the additional model calls, public source reads and time. It classifies exact answer spans and checks factual claims against exact passages from that answer's own sources. One round of selected observed source links can resolve an unknown, with a separate reassessment. Conflicting, missing and insufficient evidence stays unknown. Advice and author uncertainty stay distinct from factual counts. Source support indicates agreement with retained passages. A format retry preserves both raw answers, and failed comparison work leaves the website report available.

Suggested competitors depend on the saved goal, offering, audience and geography. Each candidate's public text supports a scoped comparison. Use site memory to correct the candidate list. For a deeper comparison on a saved review, call `evident_finish` with its run ID and `competitors: true`. It adds one bounded configured-model analysis of retained sources and reuses a saved result on repeat.

## Site memory and repeatable corrections

`evident_memory` uses the active profile's native plugin database. It stores user-attributed goals, audience and confirmed facts, competitor corrections, finding feedback, run references and tests. Reuse a key to revise it. To forget a selected item or site, ask explicitly. Retrieval withholds prior summaries that could restore forgotten statements. Historical reports and test records remain on disk and each profile has independent storage.

Before a change, confirm the full expected statement in each cited region. `evident_save_test` freezes the finding, source identities, control state, expected text and baseline. After the site owner or an authorized host tool edits the site, replay the saved test.

```sh
hermes evident verify TEST_ID --saved --change "The site owner corrected the confirmed pricing statement"
```

Verification compares the same rendered statement and state, normalizing whitespace. A match in another region cannot satisfy it. Contradictory wording fails the check. Missing/ambiguous identity, changed conditions or truncated text makes it inconclusive. A corrected heading can satisfy its own cited region. Goal, audience and competitor changes preserve saved tests. Changing or forgetting a confirmed fact leaves its test inconclusive until the fact is restored or a new test is confirmed. Older captures without stable identity need a new baseline. A run-level replay uses its immutable expanded plan and assertions without replanning. The before/after view shows the recorded states and outcomes, with no claim about customer behavior.

Comparable repeat reviews reuse the saved buyer questions. Changed goals, confirmed facts, model route or sampling conditions can make the comparison inapplicable. Compare the actual answers, support and selected alternatives.

## Run capture directly without a model account

Authorize an exact public HTTPS origin for low-level capture, then observe and view. Verify by run ID after an authorized change.

```sh
hermes evident authorize https://example.com
hermes evident observe https://example.com/ --contains "Example Domain"
hermes evident view RUN_ID
hermes evident verify RUN_ID --change "Describe the authorized change"
```

Use `--json` for a machine-readable receipt. For a custom rendered trace, use `evident_browse` with `open`, an exact `follow_link` selector or `scroll` steps. An empty assertion list records observations without a verdict. Use `evident_screenshot` with the run ID and zero-based step. For a custom report, `evident_report` accepts exact quotes and measured element indexes or null. See the [registered tool schemas](../__init__.py).

`hermes evident demo` runs the fictional Trailnote plan-selection exercise. The harness edits its own isolated fixture, then compares the same assertions. Demo interpretation uses the configured model and may incur costs. It does not request competitor or independent-answer context.

## HTTP-source evidence loop

Use `evident_observe` with explicit URLs, time/body limits, and literal `text_contains` or `http_status` assertions. Source text may include hidden content. An explicit list of URLs records independent GETs. For click paths, displayed controls and visibility, use the browser collector. [Evidence contracts](../evidence.py) own the retained HTTP and browser envelopes, assertion outcomes, hashes and replay. Missing, blocked and truncated evidence can leave assertions unknown. Earlier good steps remain inspectable after failure.

## Browser interoperability and visual evidence

URL reviews try a dedicated native Hermes session when its supervisor offers the capture seam. Local native reuse requires `browser.cloud_provider: local` and `browser.headless: true`. It refuses existing profiles, custom executables and CDP overrides. When native reuse is unavailable, use configured managed Chromium or the isolated worker. The collector records what it used and why. `allow_hosted_browser` opts into the configured hosted provider and its charges. It does not grant extra network scope.

The [browser](../browser.py) and [transport](../transport.py) owners preserve requested/final URLs and enforce anonymous, DNS-validated, pinned-address reads. Rendered reviews can admit bounded same-origin GET fetch/XHR and public display assets. Direct capture uses the stricter mode, allowing only cached display assets during control activation. Forms, credentialed requests, writes, workers, frames and unapproved origins are excluded. GET requests still reach the site and can be logged. Top-level navigation omits query URLs. Browser fragments and exact public asset queries are retained under their separate contracts.

## Local FAQ and plan interactions

The collector revalidates exact observable control identities before opening disclosures, semantic tabs, grouped radios or labelled native selects outside forms. The planner investigates, skips or leaves each pending control unknown within scope. Captures retain before/after state, exact step and screenshot. Opened answers can resolve an earlier uncertainty. Unsupported or network-dependent states can remain unobserved.

## Optional isolated browser worker for Docker hosts

If local Chromium cannot start sandboxed, use the operator-managed [browser worker](../browser_server/). Both sides need the Playwright version declared in the manifest. Use a literal loopback URL such as `ws://127.0.0.1:9777/evident-evidence` in `browser_server_url`. Share the caller's network namespace. Keep the unauthenticated server within that trusted runtime, with no secrets, data mounts or public port. Run non-root with the [pinned seccomp profile](https://github.com/microsoft/playwright/blob/v1.64.0/utils/docker/seccomp_profile.json) and sandbox enabled. Connection failure stays visible. A changed collector mode limits comparison with older baselines.

## Limits, privacy and retention

The plugin uses the normal Hermes session and optionally the configured model API. Session logs and model-provider retention follow their own policies. A standalone text explanation via `evident_explain` or `hermes evident explain RUN_ID --consent` requires opt-in and consent. It saves one bounded interpretation of retained text, without changing evidence or assertions.

The browser masks populated or editable form inputs in captured text and images. Visible public text, screenshots and empty placeholders can still contain sensitive material. Use the review for public pages or an isolated synthetic fixture only.

[The store](../storage.py) keeps at most 50 runs per profile, with 4 MB per JSON artifact and 20 MB per report. Retained local files include the immutable plan, captures, usage, receipts and HTML. Exported reports work offline, with a local screenshot replay and optional evident.so invitation. The plugin uploads nothing to Evident and performs no automatic eviction.

Use `evident_delete` with an exact run ID and `confirm_delete: true` only after the user asks to delete it. This removes the selected run and its exports. Other runs can contain comparison evidence from the deleted run. Forgetting, uninstalling, or deleting a run leaves host logs, backup and external records governed by their own owners.

## Host compatibility

Use Python 3.11+ and a supported POSIX Hermes host with tool/skill registration and native plugin storage. See [manifest and dependency inventory](../DEPENDENCIES.md) for versions. Inspect the retained compatibility record before claiming support for a new runtime or packaged distribution.

For a source installation in a disposable profile, follow the host's [catalog validation instructions](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).

```sh
hermes plugins doctor /absolute/path/to/evident-evidence --ci
hermes plugins validate /absolute/path/to/evident-evidence --install-deps
hermes plugins enable evident-evidence
```

## Reproduce the checks

Use the smallest check that exercises the affected seam. Run deterministic unit coverage with `python -m unittest discover -s tests -p 'test_*.py' -v`. Run integrations in a disposable profile with receipts outside the repository.

| Seam | Fixture |
| --- | --- |
| HTTP limits, cancellation and replay | [integration_http.py](../tests/integration_http.py) |
| Native registration, handlers and isolation | [integration_hermes.py](../tests/integration_hermes.py) with the authorized local Hermes source path |
| Native browser dispatch and capture | [integration_browser.py](../tests/integration_browser.py) with the local Hermes source path and matching Chromium |
| Saved criteria and before/after evidence | [integration_saved_retests.py](../tests/integration_saved_retests.py) |
| Adaptive navigation and control paths | [journey](../tests/integration_journey.py), [controls](../tests/integration_controls.py), [automatic controls](../tests/integration_auto_controls.py) and [same-origin read data](../tests/integration_read_data.py) |
| Fictional site demo and same-assertion replay | [integration_demo.py](../tests/integration_demo.py) |

Browser fixtures use real rendering and local synthetic sites. Their model mocks establish contracts, while model quality and hosted behavior require separately authorized evidence. The [v0.19.4 reference](https://github.com/Evident-Scalelabs/evident-hermes-plugin/blob/d04f9b5d729913f36dba828200e9ed80f557a856/docs/REFERENCE.md#retained-runtime-reference) retains the prior compatibility observations, commands and detailed release rationale.
