"""Browser test for consent-kit.js with each real site config, without touching any site.

Serves a test page at https://<site>/__ck_test through Playwright routing (so cookies behave as on
the real origin), with the config the WordPress plugin would print, a held-back inline script and a
held-back external script, and captures what the banner sends to the log endpoint.

    python test/test_js.py            # all sites
    python test/test_js.py quecafe    # one site
"""
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "consent-kit.js").read_text(encoding="utf-8")
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{detail}]"))


def page_html(cfg, lang, version=None):
    c = {k: v for k, v in cfg.items() if k != "wp"}
    c["lang"] = lang
    c["links"] = {lang: f"https://{cfg['site']}/policy-{lang}/"}
    c["logEndpoint"] = f"https://{cfg['site']}/wp-json/consent-kit/v1/log"
    if version:
        c["version"] = version
    held_inline = '<script type="text/plain" data-consent="granted">window.__heldInline = (window.__heldInline || 0) + 1; document.cookie = "_tracker_test=1; path=/";</script>'
    held_src = f'<script type="text/plain" data-consent="granted" src="https://{cfg["site"]}/__held.js" async></script>'
    ads = '<aside id="qc-ads-bar">ads</aside>'
    return (f"<!doctype html><html lang={lang}><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<script id=consent-kit-js>window.ConsentKitConfig={json.dumps(c)};\n{JS}</script>{held_inline}</head>"
            f"<body><h1>Test</h1><a href='#cookie-settings' id=reopen>Cookie settings</a>{ads}{held_src}</body></html>")


def run(site, browser):
    cfg = json.loads((ROOT / "sites" / f"{site}.json").read_text(encoding="utf-8"))
    host, name = cfg["site"], cfg["cookie"]
    clear = cfg.get("clearCookies", [])
    hides = bool(cfg.get("hideWhileOpen"))
    langs = list(cfg["texts"])
    url = f"https://{host}/__ck_test"

    for width in (1366, 375):
        tag = f"[{site} {width}]"
        lang = langs[0]
        t = cfg["texts"][lang]
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        beacons = []
        state = {"html": page_html(cfg, lang)}
        ctx.route(url, lambda r: r.fulfill(status=200, content_type="text/html", body=state["html"]))
        ctx.route(f"https://{host}/__held.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body="window.__heldSrc = (window.__heldSrc || 0) + 1;"))
        ctx.route(f"https://{host}/wp-json/consent-kit/v1/log", lambda r: (beacons.append(json.loads(r.request.post_data)), r.fulfill(status=201, body="{}")))
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        cookies = lambda: {c["name"]: c["value"] for c in ctx.cookies()}
        default = lambda: pg.evaluate("Array.from(dataLayer.find(a => a[0]==='consent' && a[1]==='default'))[2]")

        pg.goto(url); pg.wait_for_timeout(600)
        check(f"{tag} first visit: banner shown", pg.is_visible("#consent-kit"))
        check(f"{tag} first visit: wording matches config", pg.inner_text("#consent-kit p").startswith(t["message"]) and pg.inner_text("#ck-accept") == t["accept"] and pg.inner_text("#ck-reject") == t["reject"])
        check(f"{tag} first visit: policy link", pg.get_attribute("#consent-kit a", "href") == f"https://{host}/policy-{lang}/" and pg.inner_text("#consent-kit a") == t["link"])
        d = default()
        check(f"{tag} first visit: every Consent Mode signal denied", all(d[s] == "denied" for s in ("ad_storage", "ad_user_data", "ad_personalization", "analytics_storage")), d)
        check(f"{tag} first visit: held scripts did not run, no tracker cookie", not pg.evaluate("window.__heldInline || window.__heldSrc") and "_tracker_test" not in cookies())
        if hides:
            check(f"{tag} first visit: ads bar hidden while banner open", not pg.is_visible("#qc-ads-bar"))
        box = pg.eval_on_selector("#consent-kit", "e => { const r = e.getBoundingClientRect(); return [r.left, r.right, document.documentElement.scrollWidth, innerWidth]; }")
        check(f"{tag} banner fits the screen", box[0] >= 0 and box[1] <= box[3] and box[2] <= box[3], box)
        pg.screenshot(path=str(SHOTS / f"{site}-{width}.png"))

        events = pg.evaluate("window.__ev = []; document.addEventListener('consentkit:change', e => __ev.push(e.detail.choice)); ConsentKit.on(c => __ev.push('cb:' + c)); 1")
        pg.click("#ck-accept"); pg.wait_for_timeout(600)
        val = cookies().get(name, "")
        m = re.fullmatch(r"granted\.([a-f0-9]{20})\.(\d+)", val)
        check(f"{tag} accept: banner closed", not pg.is_visible("#consent-kit"))
        check(f"{tag} accept: choice stored as granted.<id>.<version>", m and int(m.group(2)) == cfg["version"], val)
        upd = pg.evaluate("dataLayer.filter(a => a[0]==='consent' && a[1]==='update').map(a => a[2])")
        check(f"{tag} accept: Consent Mode update grants only the configured signals", upd and upd[-1] == {s: "granted" for s in cfg["grant"]}, upd)
        check(f"{tag} accept: held inline and external scripts ran once", pg.evaluate("window.__heldInline") == 1 and pg.evaluate("window.__heldSrc") == 1)
        check(f"{tag} accept: logged with the same id", beacons and beacons[-1]["id"] == (m.group(1) if m else None) and beacons[-1]["choice"] == "granted" and beacons[-1]["version"] == cfg["version"] and beacons[-1]["site"] == host, beacons)
        check(f"{tag} accept: event and callback fired", pg.evaluate("__ev") == ["cb:granted", "granted"], pg.evaluate("__ev"))
        if hides:
            check(f"{tag} accept: ads bar back", pg.is_visible("#qc-ads-bar"))

        pg.reload(); pg.wait_for_timeout(600)
        check(f"{tag} return visit: no banner, analytics granted by default, held scripts run", not pg.is_visible("#consent-kit") and default()["analytics_storage"] == "granted" and default()["ad_storage"] == "denied" and pg.evaluate("window.__heldInline") == 1 and pg.evaluate("ConsentKit.get()") == "granted")

        pg.click("#reopen"); pg.wait_for_timeout(200)
        check(f"{tag} #cookie-settings reopens banner", pg.is_visible("#consent-kit"))
        planted = [{"name": n, "value": "x", "domain": "." + host, "path": "/"} for n in [c + "_x" if c == "_ga" else c for c in clear]]
        planted += [{"name": "_ga", "value": "x", "domain": "." + host, "path": "/"}]
        ctx.add_cookies(planted)
        n_before = len(beacons)
        pg.click("#ck-reject"); pg.wait_for_timeout(600)
        left = [c for c in cookies() if any(c.startswith(p) for p in clear)]
        check(f"{tag} reject: tracking cookies cleared", not left, left)
        val2 = cookies().get(name, "")
        check(f"{tag} reject: stored as denied with the same id", m and val2 == f"denied.{m.group(1)}.{cfg['version']}", val2)
        check(f"{tag} reject: logged", len(beacons) == n_before + 1 and beacons[-1]["choice"] == "denied" and beacons[-1]["id"] == (m.group(1) if m else None))
        pg.reload(); pg.wait_for_timeout(600)
        check(f"{tag} after reject: no banner, held scripts inert, analytics denied", not pg.is_visible("#consent-kit") and not pg.evaluate("window.__heldInline || window.__heldSrc") and default()["analytics_storage"] == "denied")

        # Visitors who chose under the old per-site plugin (plain "granted") keep their choice.
        ctx.clear_cookies(); ctx.add_cookies([{"name": name, "value": "granted", "domain": host, "path": "/"}])
        pg.reload(); pg.wait_for_timeout(600)
        check(f"{tag} old-plugin cookie still counts", not pg.is_visible("#consent-kit") and default()["analytics_storage"] == "granted")

        # Bumping the policy version asks everyone again.
        state["html"] = page_html(cfg, lang, version=cfg["version"] + 1)
        pg.reload(); pg.wait_for_timeout(600)
        check(f"{tag} version bump: banner back, analytics denied until asked", pg.is_visible("#consent-kit") and default()["analytics_storage"] == "denied")

        if len(langs) > 1:
            other = langs[1]
            state["html"] = page_html(cfg, other)
            ctx.clear_cookies(); pg.reload(); pg.wait_for_timeout(600)
            check(f"{tag} {other} page shows {other} wording", pg.inner_text("#ck-accept") == cfg["texts"][other]["accept"] and pg.inner_text("#consent-kit p").startswith(cfg["texts"][other]["message"]))
            if width == 375:
                pg.screenshot(path=str(SHOTS / f"{site}-{other}-{width}.png"))

        check(f"{tag} no JS errors", not errors, errors)
        ctx.close()

        # Global Privacy Control: with no choice yet it counts as Reject (no banner, nothing stored or logged).
        g = browser.new_context(viewport={"width": width, "height": 800})
        g.add_init_script("Object.defineProperty(navigator, 'globalPrivacyControl', {get: () => true});")
        state["html"] = page_html(cfg, lang)
        g.route(url, lambda r: r.fulfill(status=200, content_type="text/html", body=state["html"]))
        g.route(f"https://{host}/__held.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body="window.__heldSrc = 1;"))
        logged = []
        g.route(f"https://{host}/wp-json/consent-kit/v1/log", lambda r: (logged.append(1), r.fulfill(status=201, body="{}")))
        gp = g.new_page(); gp.goto(url); gp.wait_for_timeout(600)
        gd = gp.evaluate("Array.from(dataLayer.find(a => a[0]==='consent' && a[1]==='default'))[2]")
        check(f"{tag} GPC: no banner, analytics denied, held scripts inert, nothing stored or logged",
              not gp.is_visible("#consent-kit") and gd["analytics_storage"] == "denied" and not gp.evaluate("window.__heldInline || window.__heldSrc")
              and name not in {c["name"] for c in g.cookies()} and not logged)
        gp.click("#reopen"); gp.wait_for_timeout(200); gp.click("#ck-accept"); gp.wait_for_timeout(400)
        check(f"{tag} GPC: visitor can still open settings and accept", gp.evaluate("ConsentKit.get()") == "granted" and gp.evaluate("window.__heldInline") == 1)
        g.close()


if __name__ == "__main__":
    sites = sys.argv[1:] or sorted(p.stem for p in (ROOT / "sites").glob("*.json"))
    with sync_playwright() as p:
        b = p.chromium.launch()
        for s in sites:
            run(s, b)
        b.close()
    print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
    sys.exit(0 if all(ok for _, ok in results) else 1)
