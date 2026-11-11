"""Consume Hermes's documented supervisor capture with an exclusively owned session.

No personal profiles, pre-existing CDP endpoints or implicit cloud-provider selection.
Older hosts keep the isolated worker path and retain the capability reason.
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4


@asynccontextmanager
async def native_session(enabled=False, hosted=False):
    receipt = {"requested": bool(enabled), "state": "disabled", "hosted_allowed": bool(hosted)}
    endpoint = None
    registry = supervisor = None
    owned = False
    session = "evident-" + uuid4().hex
    try:
        if enabled:
            try:
                from tools.registry import registry
                from tools.browser_supervisor import SUPERVISOR_REGISTRY as supervisor
                from hermes_cli.config import load_config
                config = load_config().get("browser", {}) or {}
                if not callable(getattr(supervisor, "capture", None)):
                    raise ValueError("Host lacks the documented supervisor capture interface")
                if config.get("headed") or config.get("headless") is not True:
                    raise ValueError("Native reuse requires explicitly headless browser configuration")
                if not registry.get_schema("browser_exec"):
                    raise ValueError("Host browser_exec tool is unavailable")
                if any(config.get(k) for k in ("use_real_profile", "user_data_dir", "cdp_url", "executable_path")) or any(os.environ.get(k) for k in ("BU_CDP_WS", "BU_CDP_URL", "BROWSER_CDP_URL")):
                    raise ValueError("Native reuse refuses personal/persistent profiles and externally supplied browser endpoints")
                provider = config.get("cloud_provider")
                if provider != "local" and not (hosted and isinstance(provider, str) and provider.strip()):
                    raise ValueError("Host must explicitly select local, or an explicitly authorized hosted provider; auto-detection is not used")
                # Fixed trusted code; target content and model output never become executable code.
                owned = True
                result = await asyncio.to_thread(registry.dispatch, "browser_exec", {
                    "session": session, "code": "# Starting an isolated evidence session\nnew_tab('about:blank')", "timeout_s": 45}, task_id=session)
                parsed = json.loads(result) if isinstance(result, str) else result
                if not isinstance(parsed, dict) or parsed.get("error") or parsed.get("success") is False:
                    raise ValueError("Native browser session could not start")
                handle = await asyncio.to_thread(supervisor.capture, session)
                if not handle.is_valid():
                    raise ValueError("Native browser capture is no longer valid")
                endpoint = handle.cdp_url
                receipt.update(state="ready", connection="hermes_supervisor", hosted=provider != "local")
            except (ImportError, ValueError, RuntimeError, AttributeError, OSError) as exc:
                # Do not retain provider responses or CDP URLs, which may include credentials.
                receipt.update(state="unavailable", reason=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
        yield endpoint, receipt
    finally:
        if owned:
            try:
                # Only the unique session created above is addressed. Its default tab is never used for evidence.
                result = await asyncio.to_thread(registry.dispatch, "browser_exec", {
                    "session": session, "code": "# Closing the isolated evidence session\ncdp('Browser.close')", "timeout_s": 15}, task_id=session)
                parsed = json.loads(result) if isinstance(result, str) else result
                receipt["cleanup"] = "requested" if isinstance(parsed, dict) and not parsed.get("error") else "not_confirmed"
            except Exception:
                receipt["cleanup"] = "not_confirmed"
            finally:
                if supervisor:
                    try:
                        await asyncio.to_thread(supervisor.stop, session)
                    except Exception:
                        receipt["cleanup"] = "not_confirmed"
