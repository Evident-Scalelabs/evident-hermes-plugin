"""Direct user commands with concise native media delivery."""
import argparse
import asyncio
import json
import shlex

from .browser import observe_browser
from .interpretation import DEFAULT_OBJECTIVE
from .report import export_report


def browser_plan(url, expected, link=None):
    steps = [{"action": "open", "url": url, "assertions": [{"kind": "visible_text", "expected": expected if not link else "Synthetic Studio"}]}]
    if link:
        steps.append({"action": "follow_link", "selector": link, "assertions": [{"kind": "visible_text", "expected": expected}]})
    return {"mode": "browser", "objective": "Check the declared rendered text and navigation",
            "viewport": {"width": 1280, "height": 800}, "limits": {"seconds": 45, "resources": 40, "bytes_per_resource": 4194304}, "steps": steps}


def chat_summary(value):
    """Human output is deliberately separate from the CLI's opt-in JSON receipt."""
    if "authorized_origin" in value:
        return "Authorized anonymous read-only capture of " + value["authorized_origin"]
    result = value.get("after", value.get("result", value))
    if result.get("state") == "unavailable":
        return "Capture unavailable: " + result.get("detail", result.get("error", "Inspect plugin settings."))
    lines = ["Controlled goal-focused demo — " + result.get("state", "partial") + "." if "demo" in value else "Website evidence report"]
    if value.get("summary"):
        lines.append(value["summary"])
    if "state" in result:
        lines.append("Collection: " + result["state"] + ". Captured steps: " + str(result.get("observed_steps", 0)) + ".")
    if "pages_observed" in value:
        lines.append(str(value["pages_observed"]) + " pages examined; " + str(value["screenshots"]) + " screenshots in one report.")
    if result.get("run_id"):
        lines.append("Run: " + result["run_id"])
    if "review_complete" not in value and "demo" not in value and "observed_steps" in result:
        lines.append("Screenshots and coverage are in the report. Ask Hermes to review this run and return the annotated assessment; capture alone does not identify perception gaps.")
    paths = value.get("views", [value["view"]] if value.get("view") else [])
    for path in paths:
        # Hermes's native media path is consumed by supported chat adapters.
        lines.append("MEDIA:" + path)
    if value.get("interpretation"):
        lines.append(value["interpretation"]["summary"])
    return "\n".join(lines)


def register_commands(ctx, make_store, scope):
    def setup(parser):
        actions = parser.add_subparsers(dest="action", required=True)
        actions.add_parser("demo", help="Run the goal-focused controlled demo with your Hermes model and one before/after report")
        observe = actions.add_parser("observe", help="Capture one authorized rendered page")
        observe.add_argument("url")
        observe.add_argument("--contains", required=True)
        scan = actions.add_parser("scan", help="Generate one annotated website report using captured screenshots and the configured Hermes model (may incur cost)")
        scan.add_argument("url")
        choice = scan.add_mutually_exclusive_group()
        choice.add_argument("--objective", default=None, help="Focus on this visitor goal or issue")
        scan.add_argument("--context", action=argparse.BooleanOptionalAction, default=True, help="Include four independent host-model answers, source checks and three suggested alternatives (default on); --no-context skips these extra calls and public source reads")
        choice.add_argument("--general", action="store_true", help="Run the general perception-gap review")
        scan.add_argument("--max-pages", type=int, default=None, help="Exploration page budget (2–12); not a quota")
        scan.add_argument("--seconds", type=int, default=None, help="Capture and planning budget (60–900 seconds)")
        for subparser in (observe, scan):
            subparser.add_argument("--json", action="store_true", help="Machine-readable output instead of the concise summary")
        repeat = actions.add_parser("verify", help="Repeat the saved assertions")
        repeat.add_argument("run_id")
        repeat.add_argument("--saved", action="store_true", help="Interpret the identifier as a saved business-claim test")
        repeat.add_argument("--change", required=True)
        view = actions.add_parser("view", help="Export retained screenshots and evidence as offline HTML")
        view.add_argument("run_id")
        explanation = actions.add_parser("explain", help="Send bounded retained text to the configured host model with explicit consent")
        explanation.add_argument("run_id")
        explanation.add_argument("--consent", action="store_true", help="Consent to host-model processing and possible model cost")
        authorize = actions.add_parser("authorize", help="Explicitly authorize a public HTTPS origin for capture")
        authorize.add_argument("origin")
        for name, subparser in actions.choices.items():
            if name not in ("observe", "scan"):
                subparser.add_argument("--json", action="store_true", help="Machine-readable output")

    def export(run_id):
        return export_report(make_store(), run_id)

    async def run(args):
        if args.action == "authorize":
            from .transport import target
            parsed, origin, port = target(args.origin)
            if args.origin != origin or parsed.scheme != "https" or port != 443:
                raise ValueError("Provide exactly a public HTTPS origin without a path or trailing slash")
            origins, _ = scope()
            ctx.set_config("authorized_origins", list(dict.fromkeys([*origins, origin])))
            return {"authorized_origin": origin, "network": "Anonymous read-only requests only"}
        if args.action == "view":
            return {"view": export(args.run_id), "summary": make_store().inspect(args.run_id).get("review", {}).get("summary", "Retained website screenshots and evidence.")}
        if args.action == "explain":
            return json.loads(await asyncio.to_thread(ctx.dispatch_tool, "evident_explain", {"run_id": args.run_id, "consent": args.consent}))
        if args.action == "verify":
            result = json.loads(await asyncio.to_thread(ctx.dispatch_tool, "evident_verify", {"test_id" if args.saved else "run_id": args.run_id, "change_context": args.change}))
            return {"result": result, "view": export(result["run_id"])} if "run_id" in result else result
        if args.action == "demo":
            from .demo import run_demo
            return await run_demo(ctx, make_store())
        if ctx.get_config("browser_enabled", default=False) is not True:
            raise ValueError("Enable browser_enabled in plugin settings for rendered capture")
        browser_server_url = ctx.get_config("browser_server_url", default="")
        if args.action == "scan":
            from .interpretation import scan_report
            return await scan_report(ctx, make_store(), args.url, DEFAULT_OBJECTIVE if args.general else args.objective, max_pages=args.max_pages, seconds=args.seconds, context=args.context)
        if args.action == "observe":
            origins, fixture = scope()
            result = await observe_browser(make_store(), browser_plan(args.url, args.contains), origins, fixture, browser_server_url=browser_server_url)
            return {"result": result, "view": export(result["run_id"])}
    def cli(args):
        try:
            result = asyncio.run(run(args))
            print(json.dumps(result, indent=2) if args.json else chat_summary(result))
            final_state = result.get("after", result.get("result", result)).get("state", "complete")
            if final_state not in ("complete", "passed"):
                raise SystemExit(1)
        except Exception as exc:
            print(json.dumps({"state": "unavailable", "error": str(exc)}) if args.json else "Could not complete the request: " + str(exc))
            raise SystemExit(1) from exc

    async def slash(raw):
        parser = argparse.ArgumentParser(prog="/evident", exit_on_error=False)
        setup(parser)
        try:
            tokens = shlex.split(raw)
            if tokens and tokens[0].startswith("https://"):
                tokens.insert(0, "scan")
            args=parser.parse_args(tokens)
            return chat_summary(await run(args))
        except (Exception, SystemExit) as exc:
            return "Could not complete the request: " + str(exc) + "\nUse /evident scan URL for a real website, or /evident view RUN to retrieve a report. /evident demo uses a synthetic site."

    ctx.register_cli_command("evident", "Inspect rendered evidence and verify changes", setup, cli)
    ctx.register_command("evident", slash, description="Rendered evidence, screenshots and verification", args_hint="scan URL | observe | verify | view | explain | authorize | demo")
