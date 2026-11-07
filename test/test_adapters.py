"""Browser test for the JavaScript and React adapters, with real React 18 (npm install first).

    python test/test_adapters.py

1. <ConsentKitScript> is server-rendered with react-dom/server (as Next.js does) and its output put first in <head>.
2. A React app using useConsent() and <ConsentGate> is mounted in Chrome, with the adapters imported as ES modules.
3. Checks: the banner works from the server-rendered script, the gated content appears only after Accept
   (also after a reload), goes on Reject, and a value that tries to close the script tag cannot.
"""
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
NM = ROOT / "node_modules"
ORIGIN = "https://adapter-test.example"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{str(detail)[:300]}]"))


if not (NM / "react" / "umd").exists():
    raise SystemExit("Run `npm install` in the repository first (React is a dev dependency for this test).")

config = {
    "site": "adapter-test.example", "cookie": "ck_test", "version": 1, "grant": ["analytics_storage"],
    "clearCookies": ["_ga"], "defaultLang": "en", "links": {"en": "/privacy"},
    "texts": {"en": {"message": "Test </script><script>window.__pwned=1</script> banner.", "accept": "Accept", "reject": "Reject", "link": "Privacy", "label": "Cookie consent"}},
}
ssr = subprocess.run(["node", str(ROOT / "test" / "ssr.mjs"), json.dumps(config)], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
check("server render: ConsentKitScript renders", ssr.returncode == 0 and ssr.stdout.startswith('<script id="consent-kit-js">'), ssr.stderr or ssr.stdout[:120])
check("server render: config cannot close the script tag", ssr.stdout.count("</script>") == 1, ssr.stdout.count("</script>"))

APP = """
import { createElement as h } from "react";
import { useConsent, ConsentGate, openConsentSettings } from "/adapters/react.mjs";
function App() {
  const choice = useConsent();
  return h("div", null,
    h("p", { id: "status" }, String(choice)),
    h("button", { id: "settings", onClick: openConsentSettings }, "Cookie settings"),
    h(ConsentGate, { fallback: h("p", { id: "fallback" }, "no tracking") }, h("p", { id: "gated" }, "tracking on")));
}
ReactDOM.createRoot(document.getElementById("root")).render(h(App));
"""
PAGE = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">{ssr.stdout}
<script src="/nm/react/umd/react.development.js"></script>
<script src="/nm/react-dom/umd/react-dom.development.js"></script>
<script type="importmap">{{"imports": {{"react": "/shim/react.mjs"}}}}</script>
</head><body><div id="root"></div><script type="module">{APP}</script></body></html>"""
SHIM = "const R = window.React; export default R; export const { createElement, Fragment, useSyncExternalStore } = R;"


def route(r):
    path = r.request.url[len(ORIGIN):].split("?")[0]
    if path == "/":
        return r.fulfill(status=200, content_type="text/html", body=PAGE)
    if path == "/shim/react.mjs":
        return r.fulfill(status=200, content_type="text/javascript", body=SHIM)
    if path.startswith("/adapters/"):
        return r.fulfill(status=200, content_type="text/javascript", body=(ROOT / path.lstrip("/")).read_text(encoding="utf-8"))
    if path.startswith("/nm/"):
        return r.fulfill(status=200, content_type="text/javascript", body=(NM / path[4:]).read_text(encoding="utf-8"))
    return r.fulfill(status=404, body="")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()
    ctx.route(f"{ORIGIN}/**", route)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(ORIGIN + "/"); pg.wait_for_selector("#status")
    check("first visit: banner shown from the server-rendered script", pg.is_visible("#consent-kit"))
    check("first visit: useConsent() is null, gate shows the fallback", pg.inner_text("#status") == "null" and pg.is_visible("#fallback") and not pg.query_selector("#gated"))
    check("injected text stayed text", not pg.evaluate("window.__pwned") and "</script>" in pg.inner_text("#consent-kit p"))
    pg.click("#ck-accept"); pg.wait_for_timeout(200)
    check("accept: useConsent() updates and the gate opens without a reload", pg.inner_text("#status") == "granted" and pg.is_visible("#gated"))
    pg.reload(); pg.wait_for_selector("#status"); pg.wait_for_timeout(200)
    check("reload: still granted, gate open, no banner", pg.inner_text("#status") == "granted" and pg.is_visible("#gated") and not pg.is_visible("#consent-kit"))
    pg.click("#settings"); pg.wait_for_timeout(100)
    check("openConsentSettings() reopens the banner", pg.is_visible("#consent-kit"))
    pg.click("#ck-reject"); pg.wait_for_timeout(200)
    check("reject: useConsent() updates and the gate closes", pg.inner_text("#status") == "denied" and not pg.query_selector("#gated"))
    check("no JS errors", not errors, errors)
    b.close()

print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
