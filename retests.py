"""User-confirmed, immutable checks bound to retained rendered source regions."""
import copy
import hashlib
import json

from .evidence import now, verify
from .site_history import site_identity


def normalized(text):
    return " ".join(text.split())


def active_controls(step):
    return [{key: control.get(key, "") for key in ("kind", "selector", "text", "group")}
            for control in step.get("controls", []) if control.get("active")]


def evaluate(definition, record):
    results = []
    steps = {step["index"]: step for step in record["steps"]}
    for criterion in definition["criteria"]:
        step = steps.get(criterion["step"], {})
        matches = [(index, element) for index, element in enumerate(step.get("elements", []))
                   if element.get("identity", {}).get("selector") == criterion["identity"]["selector"]]
        result = {"step": criterion["step"], "expected": criterion["expected_text"],
                  "status": "inconclusive", "observed": None, "element": None}
        if step.get("state") != "observed" or step.get("fetched_url") != criterion["url"]:
            result["reason"] = "The original page and state were not observed"
        elif active_controls(step) != criterion["controls"]:
            result["reason"] = "The displayed control state differs from the baseline"
        elif len(matches) != 1:
            result["reason"] = "The source element is missing or ambiguous"
        else:
            index, element = matches[0]
            result.update(element=index, observed=element["text"])
            if element.get("identity") != criterion["identity"] or element.get("text_truncated", True):
                result["reason"] = "The source identity changed or its text is incomplete"
            else:
                result["status"] = "passed" if normalized(element["text"]) == normalized(criterion["expected_text"]) else "failed"
                result["reason"] = "Exact rendered statement matched" if result["status"] == "passed" else "The confirmed statement still differs"
        results.append(result)
    status = "inconclusive" if any(r["status"] == "inconclusive" for r in results) else "failed" if any(r["status"] == "failed" for r in results) else "passed"
    return {"status": status, "criteria": results}


def save_test(store, run_id, finding, criteria, confirm):
    if confirm is not True:
        raise ValueError("Confirm the intended statements with the user before saving a test")
    record = store.inspect(run_id)
    if record["result"].get("state") == "incomplete":
        raise ValueError("The baseline requires a final capture receipt")
    notes = record.get("review", {}).get("notes", [])
    if type(finding) is not int or not 0 <= finding < len(notes):
        raise ValueError("Select a retained finding by its zero-based index")
    if record["plan"].get("mode") != "browser":
        raise ValueError("Saved claim tests require rendered source evidence")
    note = notes[finding]
    cited = {(c["step"], c.get("element")) for c in [note, *note.get("related_evidence", [])]}
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 5:
        raise ValueError("Provide one to five exact expected statements for this finding's cited elements")
    frozen, seen = [], set()
    steps = {s["index"]: s for s in record["steps"]}
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != {"step", "element", "expected_text"}:
            raise ValueError("Each criterion requires step, element and expected_text")
        step_index, element_index = criterion["step"], criterion["element"]
        if type(step_index) is not int or type(element_index) is not int:
            raise ValueError("Select numeric retained step and element indexes")
        key = (step_index, element_index)
        if key not in cited or key in seen:
            raise ValueError("Each criterion must select a distinct element cited by the finding")
        seen.add(key)
        expected = criterion["expected_text"]
        if not isinstance(expected, str) or not 1 <= len(expected.strip()) <= 1200:
            raise ValueError("Expected statements require 1–1200 characters")
        step = steps.get(step_index, {})
        elements = step.get("elements", [])
        if step.get("state") != "observed" or not 0 <= element_index < len(elements):
            raise ValueError("The cited source element is unavailable")
        element = elements[element_index]
        identity = element.get("identity", {})
        if not identity.get("selector") or element.get("text_truncated", True):
            raise ValueError("This capture lacks complete element identity; capture a new review before saving a test")
        if element.get("text_origin") != "rendered_text":
            raise ValueError("Select a rendered statement, not an input value or placeholder")
        frozen.append({**criterion, "identity": copy.deepcopy(identity), "url": step["fetched_url"],
                       "controls": active_controls(step)})
    url = record.get("scan", {}).get("requested_url") or record["plan"]["steps"][0]["url"]
    definition = {"version": 1, "source_run": run_id, "finding": finding, "title": note["title"],
                  "site_url": url, "objective": record["plan"]["objective"], "created": now(),
                  "operator": "normalized_exact_text", "criteria": frozen,
                  "confirmation": "User-confirmed intended statements, supplied through the host tool"}
    definition["criteria_sha256"] = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    baseline = evaluate(definition, record)
    if baseline["status"] == "inconclusive":
        raise ValueError("The source identities are ambiguous or unavailable in this baseline")
    with store.history() as history:
        definition["site_revision"] = history.recall(url)["comparison_revision"]
        test_id = history.save_test(url, definition)
    return {"test_id": test_id, "definition": definition, "baseline": baseline}


async def verify_test(store, test_id, change_context, origins, fixture_origin, **options):
    with store.history() as history:
        definition = history.test(test_id)
        current_revision = history.recall(definition["site_url"])["comparison_revision"]
    try:
        baseline = store.inspect(definition["source_run"])
    except (OSError, ValueError):
        return {"state": "inconclusive", "test_id": test_id, "detail": "Baseline evidence is unavailable"}
    if current_revision != definition["site_revision"]:
        return {"state": "inconclusive", "test_id": test_id,
                "detail": "Site facts or goals changed; confirm a new test for the current conditions"}
    # This invocation authorizes replay of the saved public site. Private origins still
    # require the existing exact fixture setting and all transport checks remain active.
    public_origins = list(origins)
    origin = site_identity(baseline["plan"]["steps"][0]["url"])[1]
    if origin.startswith("https://") and origin not in public_origins:
        public_origins.append(origin)
    result = await verify(store, definition["source_run"], change_context, public_origins, fixture_origin, **options)
    after = store.inspect(result["run_id"])
    before_checks, after_checks = evaluate(definition, baseline), evaluate(definition, after)
    comparable = result.get("verification", {}).get("comparable", False) and before_checks["status"] != "inconclusive"
    with store.history() as history:
        if history.recall(definition["site_url"])["comparison_revision"] != current_revision:
            comparable = False
    if not comparable:
        after_checks["status"] = "inconclusive"
        for criterion in after_checks["criteria"]:
            criterion.update(status="inconclusive", reason="Collection conditions or confirmed site context changed")
    receipt = {"test_id": test_id, "definition": definition, "before": before_checks,
               "after": after_checks, "comparable": comparable,
               "meaning": "The same user-confirmed statements in the same retained source regions and replayed control states."}
    store.write(result["run_id"], "retest.json", receipt)
    with store.history() as history:
        history.record_run(definition["site_url"], {**after, "retest": receipt}, current_revision)
    from .report import export_report
    path = export_report(store, result["run_id"])
    return {"state": after_checks["status"], "run_id": result["run_id"], "test_id": test_id,
            "criteria_sha256": definition["criteria_sha256"], "before": before_checks, "after": after_checks,
            "comparable": comparable, "report_path": path, "delivery": "MEDIA:" + path}
