"""Read or change a site's Consent Kit settings through its REST API. No plugin re-upload.

sites/<name>.json is the source of truth (in git); this script keeps the live site equal to it.

    python configure.py quecafe --diff                      # live settings vs sites/quecafe.json
    python configure.py quecafe --push                      # make live equal to the file
    python configure.py quecafe --set theme.button=#4928fd --set texts.es.accept=Aceptar   # edit file, then push
    python configure.py quecafe --auto-theme                # read colours from the live site, write, push
    python configure.py quecafe --pull                      # copy live settings into the file

Credentials come from environment variables WP_<SLUG>_URL, WP_<SLUG>_USER and
WP_<SLUG>_APP_PASSWORD (a WordPress application password), or from a dotenv file named in
CONSENT_KIT_ENV_FILE. <SLUG> is the site file name in capitals unless SLUGS maps it.
The user must be an administrator (the config route needs manage_options).
"""
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SITES = Path(os.environ.get("CONSENT_KIT_SITES", HERE / "sites"))  # override used by the tests
sys.path.insert(0, str(HERE))
from build import check  # noqa: E402

# certifi's roots, as requests uses. Some Python installs reject newer Let's Encrypt chains
# (YE1, seen Nov 2026) that browsers and curl accept.
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

# Site file name -> wordpress-publish slug, where they differ.
SLUGS = {"lumination": "LAI"}


def creds(name):
    slug = SLUGS.get(name, name).upper()
    env = Path(os.environ["CONSENT_KIT_ENV_FILE"]) if os.environ.get("CONSENT_KIT_ENV_FILE") else None
    vals = {}
    for key in ("URL", "USER", "APP_PASSWORD"):
        k = f"WP_{slug}_{key}"
        v = os.environ.get(k)
        if not v and env and env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith(k + "="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not v:
            raise SystemExit(f"{k} is not set (environment, or the file in CONSENT_KIT_ENV_FILE).")
        vals[key] = v
    return vals["URL"].rstrip("/"), vals["USER"], vals["APP_PASSWORD"]


def call(name, method, body=None):
    url, user, pw = creds(name)
    req = urllib.request.Request(
        f"{url}/wp-json/consent-kit/v1/config", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode(),
                 "Content-Type": "application/json", "User-Agent": "consent-kit-configure"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        if e.code == 404:
            raise SystemExit(f"{name}: Consent Kit is not installed or active on {url} (404).")
        if e.code in (401, 403):
            raise SystemExit(f"{name}: not allowed ({e.code}). The app-password user must be an administrator, and the password must still be valid.")
        raise SystemExit(f"{name}: {e.code} {detail}")


def flat(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        else:
            out[key] = v
    return out


def set_path(cfg, path, raw):
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    try:
        value = json.loads(raw)  # numbers, true/false, lists
    except json.JSONDecodeError:
        value = raw
    node[keys[-1]] = value


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    name, args = sys.argv[1], sys.argv[2:]
    path = SITES / f"{name}.json"
    local = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if "--pull" in args:
        live = call(name, "GET")["config"]
        path.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote live settings into {path}")
        return

    if "--diff" in args:
        res = call(name, "GET")
        live = res["config"] or {}
        a, b = flat(live), flat(local)
        empty = (None, [], {})
        changes = [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k) and not (a.get(k) in empty and b.get(k) in empty)]
        print(f"{name}: plugin {res['plugin_version']}" + (f", paused because {res['paused_by']} is active" if res["paused_by"] else ""))
        for k, was, now in changes:
            print(f"  {k}: live {json.dumps(was, ensure_ascii=False)}  ->  file {json.dumps(now, ensure_ascii=False)}")
        print("  no differences" if not changes else f"  {len(changes)} difference(s)")
        return

    changed = False
    if "--auto-theme" in args:
        from theme import read, theme_for
        url, _, _ = creds(name)
        theme, notes = theme_for(read(url + "/"))
        local["theme"] = theme
        print("theme from live colours: " + "; ".join(notes))
        changed = True
    for i, a in enumerate(args):
        if a == "--set":
            k, _, v = args[i + 1].partition("=")
            set_path(local, k, v)
            changed = True
    if changed:
        path.write_text(json.dumps(local, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {path}")

    if changed or "--push" in args:
        check(local, name)
        res = call(name, "PUT", local)
        cleared = ", ".join(res.get("caches_cleared") or []) or "none found, clear the page cache by hand"
        print(f"{name}: saved on the live site. Page caches cleared: {cleared}")


if __name__ == "__main__":
    main()
