"""An explicitly authorized fixture editor around the read-only evidence loop.

This fictional site's terms are fixture data, not an evaluation rubric. The
model receives captured pages; the edit recipe never substitutes for its review.
"""
import asyncio
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading

from .browser import observe_browser
from .evidence import verify
from .interpretation import review_capture
from .report import export_report


GOAL = "Choose a monthly plan for a five-person field team that needs offline work, understand the total price and cancellation notice, and retain its data when leaving."
# Declared before capture; these literal assertions stay identical after editing.
CHANGES = (
    {"file": "index.html", "step": 0, "before": "$29 / team / month", "after": "Five-person team: $145/month.", "label": "Show the team total"},
    {"file": "pricing.html", "step": 2, "before": "Cancel any time; no notice needed.", "after": "Cancellation requires 30 days’ notice.", "label": "State the notice period"},
    {"file": "faq.html", "step": 6, "before": "Export your data for 90 days after your subscription ends.", "after": "Export your data before the subscription ends.", "label": "Put the export deadline in the FAQ"},
)

CSS = """
*{box-sizing:border-box}body{margin:0;background:#f5f7f5;color:#15342d;font:20px/1.5 system-ui,sans-serif}
header,main,footer{max-width:1120px;margin:auto}header{display:flex;justify-content:space-between;align-items:center;padding:25px 0;border-bottom:1px solid #cddbd3}
.brand{font-size:26px;font-weight:750;letter-spacing:-1px}nav{display:flex;gap:25px}a{color:#155e47;text-underline-offset:5px}
main{padding:46px 0 60px}h1{font-size:58px;line-height:1.08;letter-spacing:-2px;margin:14px 0 24px;max-width:820px}h2{font-size:28px;line-height:1.25;margin:12px 0 18px}p{margin:12px 0}
.eyebrow{color:#526b61;font-size:13px;font-weight:650;letter-spacing:2px;text-transform:uppercase}.grid{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}.card{background:white;border:1px solid #cfddd4;border-radius:20px;padding:30px}.dark{background:#163e30;color:#fff}.dark p{color:#d8e9df}.price{font-size:32px;line-height:1.25;font-weight:700;margin:25px 0}.button{display:inline-block;border:0;border-radius:8px;padding:13px 22px;background:#dff379;color:#183c29;text-decoration:none;font-weight:650}.muted{color:#526b61;font-size:16px}.row{border-top:1px solid #cddbd3;padding:15px 0}.pill{display:inline-block;padding:5px 12px;border-radius:20px;background:#dff379;color:#163e30;font-size:14px}footer{border-top:1px solid #cddbd3;padding:24px 0;font-size:13px;color:#526b61}
[role=tablist]{display:flex;gap:10px;margin:24px 0}button{font:inherit;border:1px solid #adbfaf;padding:10px 24px;border-radius:8px;background:white;color:#15342d;cursor:pointer}button[aria-selected=true]{background:#163e30;color:white}[hidden]{display:none}details{border-bottom:1px solid #cddbd3;padding:20px 0}summary{cursor:pointer;font-size:22px;font-weight:650}details p{max-width:560px;background:#fff;padding:18px;border-radius:10px}li{margin:16px 0}
"""


def fixture_pages():
    """All assets are local; no forms, accounts, external requests or transactions."""
    pages = {
        "index.html": '<div class="eyebrow">Field notes. One place.</div><h1>Your crew moves fast.<br>Keep every detail.</h1><div class="grid"><div><p>Trailnote brings field notes, photos and offline work together for small crews.</p><p class="price">$29 / team / month</p><p class="muted">Field Pro · billed monthly · built for five-person crews</p><a class="button" id="choose" href="/pricing.html">Choose your plan →</a></div><div class="card dark"><span class="pill">Field Pro workspace</span><h2>A day in the field</h2><p class="row">08:30 &nbsp; Site visit · notes saved offline</p><p class="row">10:15 &nbsp; Crew photos · ready to sync</p><p class="row">16:00 &nbsp; Project handover · one shared record</p></div></div>',
        "pricing.html": '<div class="eyebrow">Monthly subscriptions</div><h1>Choose your plan</h1><p>Pick the workspace that fits how your team works.</p><div role="tablist" aria-label="Monthly plans"><button type="button" id="basic-tab" role="tab" aria-controls="basic" aria-selected="true">Desk</button><button type="button" id="field-tab" role="tab" aria-controls="field" aria-selected="false">Field Pro</button></div><div id="basic" role="tabpanel"><div class="card"><h2>Desk</h2><p>Online notes for office teams. Offline work is not included.</p><p>$15 per person per month.</p></div></div><div id="field" role="tabpanel" hidden><div class="grid"><div class="card"><span class="pill">For teams in the field</span><h2>Field Pro</h2><p class="price">$29 per person / month</p><p>Five people: $145 per month.</p><p>Offline notes, photos and sync included.</p><p>Cancel any time; no notice needed.</p></div><div><h2>Before you decide</h2><p>Read how billing, cancellation and exports work.</p><a id="terms" href="/terms.html">Read monthly terms →</a></div></div></div><script>for(const tab of document.querySelectorAll("[role=tab]")){tab.addEventListener("click",()=>{for(const other of document.querySelectorAll("[role=tab]")){const active=other===tab;other.setAttribute("aria-selected",String(active));document.getElementById(other.getAttribute("aria-controls")).hidden=!active;}})}</script>',
        "terms.html": '<div class="eyebrow">Monthly terms · fictional demo</div><h1>The details, upfront.</h1><div class="grid"><div class="card"><h2>Field Pro monthly</h2><p>Field Pro costs $29 per person per month. A five-person team pays $145 per month.</p><p>Cancellation requires 30 days’ notice.</p><p>Export your data before the subscription ends.</p><p>Workspace access ends when the subscription ends. Exports are not available afterwards.</p></div><div><h2>Need a quick answer?</h2><p>Check the questions teams ask before choosing a plan.</p><a id="questions" href="/faq.html">Open common questions →</a></div></div>',
        "faq.html": '<div class="eyebrow">Answers for your team</div><h1>Know before you go.</h1><p>Planning a switch? Check your exit options before choosing a subscription.</p><details><summary id="cancel-question">How much notice do I need to cancel?</summary><p>Cancellation requires 30 days’ notice.</p></details><details><summary id="export-question">Can I export our notes when we leave?</summary><p>Export your data for 90 days after your subscription ends.</p></details><p class="muted">These answers apply to Field Pro monthly subscriptions.</p>',
    }
    return {name: '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trailnote · '+name.split('.')[0]+'</title><style>'+CSS+'</style></head><body><header><a class="brand" href="/">◒ Trailnote</a><nav><a href="/pricing.html">Plans</a><a href="/faq.html">Questions</a><a href="/terms.html">Terms</a></nav></header><main>'+body+'</main><footer>Trailnote is a fictional controlled demo site. No accounts or purchases.</footer></body></html>' for name, body in pages.items()}


def demo_plan(origin):
    def text(value):
        return {"kind": "visible_text", "expected": value}
    def control(kind, selector, label, group="", expected=""):
        return {"action": "activate_control", "control": {"kind": kind, "selector": selector, "text": label, "group": group},
                "assertions": [{"kind": "control_active", "expected": True}, text(expected)]}
    return {"mode": "browser", "objective": GOAL, "viewport": {"width": 1280, "height": 900},
            "limits": {"seconds": 120, "resources": 80, "bytes_per_resource": 4194304}, "steps": [
                {"action": "open", "url": origin + "/", "assertions": [text(CHANGES[0]["after"])]},
                {"action": "follow_link", "selector": "#choose", "assertions": [text("Choose your plan")]},
                control("tab", "#field-tab", "Field Pro", "Monthly plans", CHANGES[1]["after"]),
                {"action": "follow_link", "selector": "#terms", "assertions": [text("A five-person team pays $145 per month."), text(CHANGES[1]["after"]), text(CHANGES[2]["after"])]},
                {"action": "follow_link", "selector": "#questions", "assertions": [text("Know before you go.")]},
                control("disclosure", "#cancel-question", "How much notice do I need to cancel?", expected=CHANGES[1]["after"]),
                control("disclosure", "#export-question", "Can I export our notes when we leave?", expected=CHANGES[2]["after"]),
            ]}


async def run_demo(ctx, store):
    if ctx.get_config("browser_enabled", default=False) is not True:
        raise ValueError("Enable browser_enabled in plugin settings for the rendered demo")
    if ctx.get_config("allow_model_interpretation", default=False) is not True:
        raise ValueError("The goal-focused demo uses your configured Hermes model to review captured pages. Enable allow_model_interpretation in plugin settings; model cost may apply.")
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    with tempfile.TemporaryDirectory(prefix="evident-trailnote-") as tmp:
        site = Path(tmp)
        for name, content in fixture_pages().items():
            (site / name).write_text(content)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        before = after = None
        receipt = {"method": "controlled-goal-demo.v1", "site": "Trailnote", "goal": GOAL, "state": "pending",
                   "review_mode": "goal_focused", "show_evident_cta": ctx.get_config("show_evident_cta", default=True) is True,
                   "scope": "Fictional controlled site with a declared buying journey. No general website coverage claim.",
                   "changes": [], "review": {}, "context": "Independent AI answers and competitors are not meaningful for this fictional fixture. Real website reports retain both features."}
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            before = await observe_browser(store, demo_plan(origin), [], origin,
                browser_server_url=ctx.get_config("browser_server_url", default=""),
                native_browser=ctx.get_config("reuse_hermes_browser", default=True))
            receipt["before"] = before["run_id"]
            if before["state"] == "cancelled":
                raise asyncio.CancelledError
            if before["state"] != "complete":
                raise ValueError("Baseline capture did not finish; no fixture changes applied")
            review_receipt = {"review_mode": "goal_focused", "coverage": receipt["scope"],
                              "presentation": "Lead with the most useful evidenced actions for the five-person buying goal. This is a fictional controlled site; do not claim real customer effects."}
            await review_capture(ctx, store, before["run_id"], review_receipt)
            receipt["review"] = review_receipt
            # This command's declared harness edits only files it created, never a scanned site.
            for change in CHANGES:
                file = site / change["file"]
                old = file.read_bytes()
                assert old.decode().count(change["before"]) == 1
                new = old.decode().replace(change["before"], change["after"]).encode()
                file.write_bytes(new)
                receipt["changes"].append({**change, "before_sha256": hashlib.sha256(old).hexdigest(), "after_sha256": hashlib.sha256(new).hexdigest()})
            after = await verify(store, before["run_id"], "Authorized demo harness corrected three copies on its own temporary fictional site; assertions unchanged", [], origin,
                                 browser_server_url=ctx.get_config("browser_server_url", default=""))
            receipt["after"] = after["run_id"]
            if after["state"] == "cancelled":
                raise asyncio.CancelledError
            receipt["state"] = "complete" if after["state"] == "complete" and review_receipt["state"] == "complete" else "partial"
        except asyncio.CancelledError:
            receipt.update(state="cancelled", error="Demo cancelled; retained evidence is inspectable")
            raise
        except Exception as exc:
            receipt.update(state="partial", error=str(exc)[:500] if isinstance(exc, ValueError) else type(exc).__name__)
            if before is None:
                raise
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
            receipt["fixture_cleanup"] = "stopped" if not worker.is_alive() else "thread_cleanup_failed"
            if worker.is_alive():
                receipt["state"] = "partial"
            if before:
                with store.lease():
                    store.write((after or before)["run_id"], "demo.json", receipt)
        run_id = (after or before)["run_id"]
        path = export_report(store, run_id)
        transitions = (after or {}).get("verification", {}).get("transitions", [])
        resolved = sum(t["transition"] == "met_after" and t["verified"] for t in transitions)
        return {"demo": True, "state": receipt["state"], "run_id": run_id, "view": path, "delivery": "MEDIA:" + path,
                "summary": f"Trailnote: a five-person buying journey. {resolved} declared checks changed from unmet to met. One report with highlighted before/after captures." + (" Review incomplete: " + receipt["error"] if receipt.get("error") else ""),
                "observed_steps": (after or before).get("observed_steps", 0)}
