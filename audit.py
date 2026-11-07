"""Cookie and tracker audit for any live page, with or without Consent Kit. Read-only: it only visits.

    python audit.py https://quecafe.info/
    python audit.py https://quecafe.info/ https://azvai.com/en/ https://lumination.ai/

For each URL, in a clean browser: what cookies and third-party requests happen before any choice,
then after Reject (reload), then after Accept (fresh browser). Google Analytics hits show their
consent state (gcs=G100 means analytics denied, G101 granted). Exit code 1 if any cookie that is not
on the essential list is set before a choice, or anything but the consent cookie survives Reject.
Run it after adding any plugin, tag or embed, and monthly.
"""
import sys
import time
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

# Cookies that need no consent: security, load balancing, language. Extend with care.
ESSENTIAL = ("__cf_bm", "cf_clearance", "_cfuvid", "pll_language", "wordpress_test_cookie", "wp-wpml_current_language", "PHPSESSID")


def bust(url):
    return url + ("&" if "?" in url else "?") + f"ck_audit={int(time.time())}"


def visit(browser, url, action=None):
    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    reqs = []
    ctx.on("request", lambda r: reqs.append(r.url))
    pg = ctx.new_page()
    pg.goto(bust(url), wait_until="load", timeout=60000)
    pg.wait_for_timeout(4000)
    info = pg.evaluate("({kit: !!window.ConsentKit, cookie: (window.ConsentKitConfig||{}).cookie || null, banner: !!document.querySelector('#consent-kit:not([hidden]), #azv-consent:not([hidden]), #lai-consent:not([hidden]), #qc-consent:not([hidden])')})")
    snap = None
    if action and info["kit"]:
        reqs.clear()
        pg.click(f"#ck-{action}")
        pg.wait_for_timeout(1500)
        pg.goto(bust(url), wait_until="load", timeout=60000)
        pg.wait_for_timeout(4000)
    snap = {
        "cookies": [(c["name"], c["domain"], round((c["expires"] - time.time()) / 86400) if c["expires"] > 0 else "session") for c in ctx.cookies()],
        "hosts": sorted({urlparse(u).hostname for u in reqs if urlparse(u).hostname and not urlparse(u).hostname.endswith(urlparse(url).hostname.replace("www.", ""))}),
        "gcs": sorted({parse_qs(urlparse(u).query).get("gcs", ["?"])[0] for u in reqs if "/g/collect" in u}),
        **info,
    }
    ctx.close()
    return snap


def show(title, s, consent_cookie):
    print(f"  {title}")
    print(f"    third-party hosts: {', '.join(s['hosts']) or 'none'}")
    if s["gcs"]:
        print(f"    GA hits consent state (gcs): {', '.join(s['gcs'])}")
    for name, dom, days in sorted(s["cookies"]):
        tag = "consent choice" if name == consent_cookie else "essential" if name.startswith(ESSENTIAL) else "NEEDS CONSENT"
        print(f"    cookie {name:<28} {dom:<28} {str(days) + 'd' if days != 'session' else days:<8} {tag}")


def audit(browser, url):
    print(f"\n{url}")
    first = visit(browser, url)
    cc = first["cookie"]
    print(f"  Consent Kit: {'yes, cookie ' + cc if first['kit'] else 'not found'}; banner shown on first visit: {first['banner']}")
    show("before any choice", first, cc)
    bad = [n for n, _, _ in first["cookies"] if n != cc and not n.startswith(ESSENTIAL)]
    if first["kit"]:
        rej = visit(browser, url, "reject")
        show("after Reject (reloaded)", rej, cc)
        bad += [n for n, _, _ in rej["cookies"] if n != cc and not n.startswith(ESSENTIAL)]
        acc = visit(browser, url, "accept")
        show("after Accept (reloaded)", acc, cc)
    verdict = "OK" if not bad else "PROBLEM: set without consent: " + ", ".join(sorted(set(bad)))
    print(f"  => {verdict}")
    return not bad


if __name__ == "__main__":
    urls = sys.argv[1:]
    if not urls:
        raise SystemExit(__doc__)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ok = [audit(b, u) for u in urls]
        b.close()
    sys.exit(0 if all(ok) else 1)
