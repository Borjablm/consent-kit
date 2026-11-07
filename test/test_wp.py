"""WordPress test for the plugin, in a throwaway local WordPress (Docker). Never touches a live site.

    python test/test_wp.py           # build, start, test, then remove the containers and volume
    python test/test_wp.py --keep    # leave WordPress running at http://localhost:8089

Covers: install of the generic zip (silent until configured), settings pushed through the config
API with configure.py (the same script used on live sites), validation and permissions of that API,
the PHP output and output buffer, the REST consent log (validation, origin check, rate limit), purge,
the admin page, CSV export, noindex, the guard against old per-site plugins, and a self-update from
a release manifest that keeps the site's settings.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WP = Path(__file__).parent / "wp"
BASE = "http://localhost:8089"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{str(detail)[:400]}]"))


def sh(*args, check_rc=True):
    r = subprocess.run(["docker", "compose", *args], cwd=WP, capture_output=True, text=True, encoding="utf-8")
    if check_rc and r.returncode:
        raise SystemExit(f"docker compose {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def wp(*args, check_rc=True):
    return sh("run", "--rm", "-T", "cli", "wp", *args, check_rc=check_rc)


def get(path):
    with urllib.request.urlopen(BASE + path + ("&" if "?" in path else "?") + f"nc={time.time()}") as r:
        return r.read().decode("utf-8")


def request(path, body=None, method="POST", origin=None, auth=None, ctype="text/plain;charset=UTF-8"):
    h = {"Content-Type": ctype}
    if origin:
        h["Origin"] = origin
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(auth.encode()).decode()
    req = urllib.request.Request(BASE + path, data=body.encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def configure(env, *args):
    r = subprocess.run([sys.executable, str(ROOT / "configure.py"), *args], capture_output=True, text=True, env=env, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def make_release(version, folder):
    """A copy of the plugin with its version raised, zipped, plus update.json, as release.py would publish."""
    php = (ROOT / "wordpress" / "consent-kit.php").read_text(encoding="utf-8").replace("1.0.0", version)
    js = (ROOT / "consent-kit.js").read_text(encoding="utf-8").replace("Consent Kit 1.0.0.", f"Consent Kit {version}.")
    with zipfile.ZipFile(folder / f"consent-kit-{version}.zip", "w") as z:
        z.writestr("consent-kit/consent-kit.php", php)
        z.writestr("consent-kit/consent-kit.js", js)
    (folder / "update.json").write_text(json.dumps({"version": version, "package": f"http://releases/consent-kit-{version}.zip"}))


def setup():
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True)
    shutil.rmtree(WP / "releases", ignore_errors=True)
    (WP / "releases").mkdir()
    sh("up", "-d", "db", "wordpress", "releases")
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/wp-admin/install.php", timeout=3)
            break
        except Exception:
            time.sleep(2)
    if subprocess.run(["docker", "compose", "run", "--rm", "-T", "cli", "wp", "core", "is-installed"], cwd=WP, capture_output=True).returncode:
        # Local throwaway admin with a random password that is never used.
        wp("core", "install", f"--url={BASE}", "--title=Consent Kit test", "--admin_user=ckadmin", f"--admin_password=ck-{time.time_ns()}", "--admin_email=admin@example.test", "--skip-email")
        wp("rewrite", "structure", "/%postname%/", "--hard")
        for slug, title in [("aviso-legal", "Aviso legal"), ("politica-de-privacidad", "Política de privacidad"), ("politica-de-cookies", "Política de cookies")]:
            wp("post", "create", "--post_type=page", "--post_status=publish", f"--post_title={title}", f"--post_name={slug}")
        wp("user", "create", "ckeditor", "editor@example.test", "--role=editor", f"--user_pass=ck-{time.time_ns()}")
    wp("plugin", "deactivate", "azvai-consent", check_rc=False)
    wp("plugin", "install", "/dist/consent-kit-1.0.0.zip", "--force", "--activate")


def tests():
    out = sh("exec", "-T", "wordpress", "php", "-l", "/var/www/html/wp-content/plugins/consent-kit/consent-kit.php")
    check("php -l: no syntax errors", "No syntax errors" in out, out)

    # Fresh install: no settings yet, so no banner and an admin notice.
    wp("option", "delete", "consent_kit_config", check_rc=False)
    check("unconfigured: kit prints nothing", 'id="consent-kit-js"' not in get("/"))
    check("unconfigured: admin notice says to push settings", "no settings for this site yet" in wp("eval", "do_action('admin_notices');"))

    # Config API: permissions and validation.
    admin_pw = wp("user", "application-password", "create", "ckadmin", f"test-{time.time_ns()}", "--porcelain")
    editor_pw = wp("user", "application-password", "create", "ckeditor", f"test-{time.time_ns()}", "--porcelain")
    check("config API: anonymous GET refused", request("/wp-json/consent-kit/v1/config", method="GET")[0] == 401)
    check("config API: editor (not admin) refused", request("/wp-json/consent-kit/v1/config", method="GET", auth=f"ckeditor:{editor_pw}")[0] == 403)
    qc = json.loads((ROOT / "sites" / "quecafe.json").read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(qc)); bad["theme"]["bg"] = "red;}body{display:none"; bad["colour"] = "x"
    code, body = request("/wp-json/consent-kit/v1/config", json.dumps(bad), method="PUT", auth=f"ckadmin:{admin_pw}", ctype="application/json")
    check("config API: CSS injection and unknown keys refused with reasons", code == 400 and "theme.bg must be a plain CSS colour" in body and 'unknown key \\"colour\\"' in body, body)

    # configure.py against the local site, with a scratch copy of the quecafe settings.
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "sites" / "quecafe.json", tmp / "quecafe.json")
    env = {**os.environ, "CONSENT_KIT_SITES": str(tmp), "WP_QUECAFE_URL": BASE, "WP_QUECAFE_USER": "ckadmin", "WP_QUECAFE_APP_PASSWORD": admin_pw}
    rc, out = configure(env, "quecafe", "--push")
    check("configure.py --push: saved", rc == 0 and "saved on the live site" in out, out)
    rc, out = configure(env, "quecafe", "--diff")
    check("configure.py --diff: live equals the file", rc == 0 and "no differences" in out, out)
    rc, out = configure(env, "quecafe", "--set", "theme.button=#7a3b10", "--set", "texts.es.accept=Acepto")
    html = get("/")
    check("configure.py --set: change is live without re-uploading", rc == 0 and '"button":"#7a3b10"' in html and '"accept":"Acepto"' in html, out)
    configure(env, "quecafe", "--set", "texts.es.accept=Aceptar")
    hist = json.loads(wp("option", "get", "consent_kit_banner_history", "--format=json"))
    check("banner history: one entry per distinct wording, with version and text",
          len(hist) == 3 and [h["texts"]["es"]["accept"] for h in hist] == ["Aceptar", "Acepto", "Aceptar"] and all(h["version"] == 1 and h["saved_at"] for h in hist), hist)
    configure(env, "quecafe", "--push")
    check("banner history: an unchanged push adds nothing", len(json.loads(wp("option", "get", "consent_kit_banner_history", "--format=json"))) == 3)
    shutil.rmtree(tmp, ignore_errors=True)

    html = get("/")
    head = html.split("</head>")[0]
    i_ck, i_gtag = head.find('id="consent-kit-js"'), head.find("googletagmanager.com/gtag/js")
    check("head: consent default printed before the Google tag", 0 <= i_ck < i_gtag, (i_ck, i_gtag))
    cfg = json.loads(re.search(r"window\.ConsentKitConfig = (\{.*?\});\n", html).group(1))
    check("head: browser config has no wp block", "wp" not in cfg, list(cfg))
    check("head: policy link resolves to the cookie page", list(cfg["links"].values()) == [f"{BASE}/politica-de-cookies/"], cfg["links"])
    check("head: log endpoint is this site's REST route", cfg.get("logEndpoint") == f"{BASE}/wp-json/consent-kit/v1/log", cfg.get("logEndpoint"))
    check("buffer: WeCanTrack inline loader held back", re.search(r'<script type="text/plain" data-consent="granted">\s*\(function\(w, c, t, u\)', html))
    check("buffer: WeCanTrack preload and dns-prefetch removed", "wct-3.com/wct.js?type=session\" as=\"script\"" not in html and "//wct-3.com\">" not in html)
    check("buffer: unrelated preload kept", "block-library/style.min.css" in html)
    check("buffer: module script held back and keeps its type", '<script type="text/plain" data-consent="granted" data-type="module" src="https://wct-3.com/module.js">' in html, re.findall(r"<script[^>]*module[^>]*>", html))
    check("buffer: JSON-LD left alone", '<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","url":"https://wct-3.com/not-a-script"}</script>' in html)
    check("buffer: Google tag and other scripts untouched", '<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST" id="google_gtagjs-js"></script>' in html and "<script>window.__untouched = 1;</script>" in html)

    legal = get("/politica-de-cookies/")
    check("legal page: noindex, follow", re.search(r"<meta name='robots' content='[^']*noindex[^']*follow", legal), re.findall(r"<meta name='robots'[^>]*>", legal))
    check("normal page: indexable", "noindex" not in html)

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        ctx.route("https://wct-3.com/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body="window.__wctLoaded = (window.__wctLoaded||0)+1;"))
        ctx.route("https://www.googletagmanager.com/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/?nc=b1"); pg.wait_for_timeout(1200)
        check("browser: banner shown in Spanish (default language)", pg.is_visible("#consent-kit") and pg.inner_text("#ck-accept") == "Aceptar")
        check("browser: WeCanTrack not loaded before a choice", not pg.evaluate("window.__wctLoaded || window._wct"))
        check("browser: ads bar hidden while the banner is open", not pg.is_visible("#qc-ads-bar"))
        with pg.expect_response("**/wp-json/consent-kit/v1/log") as resp:
            pg.click("#ck-accept")
        check("browser: log endpoint answered 201", resp.value.status == 201, resp.value.status)
        pg.wait_for_timeout(1200)
        check("browser: WeCanTrack loader and module ran after Accept", pg.evaluate("window._wct && window._wct.uid") == "TEST" and pg.evaluate("window.__wctLoaded") == 2, pg.evaluate("[window._wct, window.__wctLoaded]"))
        cid = re.fullmatch(r"granted\.([a-f0-9]{20})\.1", next(c["value"] for c in ctx.cookies() if c["name"] == "qc_consent")).group(1)
        check("browser: no JS errors", not errors, errors)
        b.close()

    rows = wp("db", "query", f"SELECT choice, policy_version, site, path FROM wp_consent_kit_log WHERE consent_id='{cid}'", "--skip-column-names")
    check("log: row stored with choice, version, site and path", rows.split() == ["granted", "1", "localhost", "/"], rows)
    good = json.dumps({"id": "a" * 20, "choice": "denied", "version": 1, "path": "/x/", "lang": "es"})
    log = "/wp-json/consent-kit/v1/log"
    check("log API: bad id rejected (400)", request(log, json.dumps({"id": "nothex", "choice": "granted", "version": 1}))[0] == 400)
    check("log API: bad choice rejected (400)", request(log, json.dumps({"id": "b" * 20, "choice": "maybe", "version": 1}))[0] == 400)
    check("log API: other site's origin rejected (403)", request(log, good, origin="https://evil.example")[0] == 403)
    check("log API: same-origin record accepted (201)", request(log, good, origin=BASE)[0] == 201)
    codes = [request(log, good, origin=BASE)[0] for _ in range(30)]
    check("log API: rate limit kicks in at 30 per hour per visitor", 429 in codes, codes)
    wp("transient", "delete", "--all")

    wp("db", "query", "INSERT INTO wp_consent_kit_log (created_at, consent_id, choice, policy_version, site) VALUES ('2020-01-01 00:00:00', 'cccccccccccccccccccc', 'granted', 1, 'old')")
    wp("cron", "event", "run", "consent_kit_purge")
    left = wp("db", "query", "SELECT COUNT(*) FROM wp_consent_kit_log WHERE consent_id='cccccccccccccccccccc'", "--skip-column-names")
    check("purge: rows past retention deleted", left == "0", left)
    check("purge: daily event scheduled", "consent_kit_purge" in wp("cron", "event", "list", "--fields=hook", "--format=csv"))
    page = wp("eval", f"wp_set_current_user(1); $_GET['consent_id']='{cid}'; consent_kit_admin_page();")
    check("admin page: lookup finds the visitor's record", cid in page and "granted" in page and "Acceptance rate" in page, page[:300])
    check("admin page: shows what the banner said per version", "What the banner said, by policy version" in page and "Acepto" in page)
    csv = wp("eval", "wp_set_current_user(1); $_REQUEST['_wpnonce']=wp_create_nonce('consent_kit_export'); do_action('admin_post_consent_kit_export');")
    check("admin: CSV export has header and the record", csv.startswith("created_at_utc,consent_id,choice") and cid in csv, csv[:200])

    wp("plugin", "activate", "azvai-consent")
    html2 = get("/")
    check("guard: old plugin active, kit stays silent", 'id="consent-kit-js"' not in html2 and html2.count("'consent', 'default'") == 1 and "azv-consent-default" in html2)
    check("guard: admin notice tells you to deactivate the old plugin", "deactivate Azvai Cookie Consent first" in wp("eval", "do_action('admin_notices');"))
    wp("plugin", "deactivate", "azvai-consent")
    check("guard: kit back once the old plugin is off", 'id="consent-kit-js"' in get("/"))

    # Self-update: publish 1.0.1 on the stand-in release server, WordPress sees it, installs it, settings survive.
    make_release("1.0.1", WP / "releases")
    wp("transient", "delete", "--all", "--network", check_rc=False)
    listed = wp("plugin", "list", "--name=consent-kit", "--fields=name,version,update,update_version", "--format=json")
    info = json.loads(listed)[0]
    check("update: WordPress sees 1.0.1 from the manifest", info["update"] == "available" and info["update_version"] == "1.0.1", info)
    check("update: auto-update on for this plugin", wp("eval", "var_export(apply_filters('auto_update_plugin', false, (object) array('plugin' => 'consent-kit/consent-kit.php')));") == "true")
    up = wp("plugin", "update", "consent-kit", check_rc=False)
    ver = wp("plugin", "get", "consent-kit", "--field=version")
    check("update: installed 1.0.1", ver == "1.0.1", up[-300:])
    html3 = get("/")
    check("update: site settings kept and banner still served", '"cookie":"qc_consent"' in html3 and "Consent Kit 1.0.1." in html3)
    check("update: plugin still active", subprocess.run(["docker", "compose", "run", "--rm", "-T", "cli", "wp", "plugin", "is-active", "consent-kit"], cwd=WP, capture_output=True).returncode == 0)
    shutil.rmtree(WP / "releases", ignore_errors=True)


if __name__ == "__main__":
    keep = "--keep" in sys.argv
    try:
        setup()
        tests()
    finally:
        if not keep:
            sh("down", "-v", check_rc=False)
    print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
    sys.exit(0 if results and all(ok for _, ok in results) else 1)
