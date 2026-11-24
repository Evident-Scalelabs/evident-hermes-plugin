# Evident technical reference

[Marketplace overview](../README.md) · [Plugin settings](../plugin.yaml) · [Dependencies](../DEPENDENCIES.md)

## First-time setup

In the intended Hermes profile, install the plugin and the browser used by its Python environment.

```sh
hermes plugins install evident-evidence --enable
python -m playwright install chromium
```

Merge the following into the existing profile settings. Both options default off. Interpreted reports send captured public text and screenshots to your configured vision-capable model and may incur charges.

```yaml
plugins:
  entries:
    evident-evidence:
      settings:
        browser_enabled: true
        allow_model_interpretation: true
```

Reload the profile and ask **“Is this evident?”** in a fresh chat. Supply a public URL and, optionally, a buying decision. That review authorizes the requested origin for the run.

## Review a real website

Give Hermes the URL and your goal in chat. The equivalent CLI command is

```sh
hermes evident scan https://example.com/ --objective "Help first-time buyers choose a plan"
```

Omitting the goal reuses the site's saved focus or starts a general review. Use `--general` to request the general review. `--max-pages` and `--seconds` bound exploration and planning. The [manifest](../plugin.yaml) owns defaults, the [review implementation](../interpretation.py) owns model limits and the [browser collector](../browser.py) owns capture limits.

The offline report answers the [public review questions](../PUBLIC_CHECKS.md) using observed pages and controls. Highlights cite measured text or image regions. Metadata and JSON-LD can support a claim without a screen location. Reports retain source text, requested and final URLs, capture geometry, metered calls and gaps, including protected or unvisited steps.

To retrieve a saved report without another network or model call, ask for the exact URL or use `evident_inspect` with the run ID and `summary_only: true`. Interrupted work may return a partial report. Resume an already requested comparison with `evident_finish` and the original run ID.

## Independent AI answers and suggested alternatives

The default review asks the configured model four questions independently of the site and one another. It retains the model route, questions, answers and cited passages. Use `--no-context` or `context: false` for a website-only report.

The [context collector](../contextual.py) compares factual answer spans with the answer's sources. It may follow one round of observed links to reassess an unknown. Conflicting or insufficient sources stay unknown. Advice and uncertainty are labeled separately. A failed comparison preserves the website report.

Competitor suggestions use the saved goal, offering, audience, geography and candidates' public text. Correct the list in site memory. For deeper analysis of retained sources, call `evident_finish` with the run ID and `competitors: true`. Repeated requests reuse the saved result.

## Site memory and repeatable corrections

`evident_memory` uses the active profile's native plugin database. It stores user-attributed goals, audience and confirmed facts, competitor corrections, finding feedback, run references and tests. Reuse a key to revise it. To forget a selected item or site, ask explicitly. Retrieval withholds prior summaries that could restore forgotten statements. Historical reports and test records remain on disk and each profile has independent storage.

Before a change, confirm the full expected statement in each cited region. `evident_save_test` freezes the finding, source identities, control state, expected text and baseline. After the site owner or an authorized host tool edits the site, replay the saved test.

```sh
hermes evident verify TEST_ID --saved --change "The site owner corrected the confirmed pricing statement"
```

A [saved test](../retests.py) compares the confirmed statement in its original region and control state after normalizing whitespace. Conflicting wording fails. Ambiguous identity, changed conditions or truncated text gives an inconclusive result. Older captures without stable identity require a new baseline.

Changing or forgetting a confirmed fact makes its test inconclusive until the fact is restored or a new test confirmed. Edits to the goal, audience or competitor list preserve tests. To compare the entire run, replay the saved run ID and its original plan and assertions.

Comparable repeat reviews reuse the saved buyer questions. Changed goals, confirmed facts, model route or sampling conditions can make the comparison inapplicable. Compare the actual answers, support and selected alternatives.

## Run capture directly without a model account

For rendered capture, enable `browser_enabled` and install Chromium. Authorize the exact HTTPS origin (no path or trailing slash), capture the page, then replay after the owner makes a change.

```sh
hermes evident authorize https://example.com
hermes evident observe https://example.com/ --contains "Example Domain"
hermes evident view RUN_ID
hermes evident verify RUN_ID --change "Describe the authorized change"
```

Add `--json` for the machine receipt. For custom rendering, `evident_browse` takes `open`, exact `follow_link` selectors or `scroll` steps. Empty assertions record observations only. Use `evident_screenshot` with the run ID and zero-based step. For `evident_report`, supply exact quotes and measured element indexes (or null). See the [tool schemas](../__init__.py).

## HTTP-source evidence loop

For independent HTTP GETs, use `evident_observe` with explicit URLs, time/body limits and `text_contains` or `http_status` assertions. Source may contain hidden text. Use rendered capture for visibility and click paths. Missing, blocked or truncated responses can leave assertions unknown while earlier steps remain available. [Evidence and replay contracts](../evidence.py).

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

Use Python 3.11+ and a supported POSIX Hermes host with tool/skill registration and native plugin storage. The [manifest](../plugin.yaml) pins Playwright. The [dependency inventory](../DEPENDENCIES.md) identifies upstream licenses and the isolated worker image.

For a source installation in a disposable profile, follow the host's [catalog validation instructions](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).

```sh
hermes plugins doctor /absolute/path/to/evident-evidence --ci
hermes plugins validate /absolute/path/to/evident-evidence --install-deps
hermes plugins enable evident-evidence
```

## Reproduce the checks

`hermes evident demo` uses the configured model and may incur costs. It edits only the fictional Trailnote fixture and replays the original assertions. Independent answers and competitor comparisons are excluded.

Use the smallest check that exercises the affected seam. Run deterministic unit coverage with `python -m unittest discover -s tests -p 'test_*.py' -v`. Run integrations in a disposable profile with receipts outside the repository.

| Seam | Fixture |
| --- | --- |
| HTTP limits, cancellation and replay | [integration_http.py](../tests/integration_http.py) |
| Native registration, handlers and isolation | [integration_hermes.py](../tests/integration_hermes.py) with the authorized local Hermes source path |
| Native browser dispatch and capture | [integration_browser.py](../tests/integration_browser.py) with the local Hermes source path and matching Chromium |
| Strict content security policy, long pages, masked controls and fragment navigation | [integration_resilience.py](../tests/integration_resilience.py) |
| Saved criteria and before/after evidence | [integration_saved_retests.py](../tests/integration_saved_retests.py) |
| Adaptive navigation and control paths | [journey](../tests/integration_journey.py), [controls](../tests/integration_controls.py), [automatic controls](../tests/integration_auto_controls.py) and [same-origin read data](../tests/integration_read_data.py) |
| Fictional site demo and same-assertion replay | [integration_demo.py](../tests/integration_demo.py) |

Browser fixtures use real rendering and local synthetic sites. Their model mocks establish contracts, while model quality and hosted behavior require separately authorized evidence. The [v0.19.4 reference](https://github.com/Evident-Scalelabs/evident-hermes-plugin/blob/d04f9b5d729913f36dba828200e9ed80f557a856/docs/REFERENCE.md#retained-runtime-reference) retains the prior compatibility observations, commands and detailed release rationale.
