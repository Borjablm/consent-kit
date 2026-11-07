"""Build the one WordPress zip every site runs, plus the update manifest.

    python build.py        -> dist/consent-kit-<version>.zip and dist/update.json

The zip has no site settings: each site's settings live in its database and are pushed with
configure.py. Built with zipfile, never Compress-Archive (WordPress rejects its backslash paths).
Release with release.py, which runs the tests first.
"""
import json
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
REPO = "Borjablm/consent-kit"
SIGNALS = {"ad_storage", "ad_user_data", "ad_personalization", "analytics_storage"}
TEXT_KEYS = {"message", "accept", "reject", "link", "label"}


def version():
    php = (HERE / "wordpress" / "consent-kit.php").read_text(encoding="utf-8")
    v = re.search(r"^ \* Version: (\S+)", php, re.M).group(1)
    const = re.search(r"CONSENT_KIT_VERSION\s*=\s*'([^']+)'", php).group(1)
    js = (HERE / "consent-kit.js").read_text(encoding="utf-8")
    if const != v or not js.startswith(f"/*!\n * Consent Kit {v}."):
        raise SystemExit(f"version mismatch: header {v}, constant {const}, consent-kit.js header must say {v}")
    return v


def check(cfg, name):
    """Local checks before a push; the plugin validates again on the server."""
    errors = []
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,30}", cfg.get("cookie", "")):
        errors.append("cookie must be a short lowercase name")
    if not isinstance(cfg.get("version"), int) or cfg["version"] < 1:
        errors.append("version must be a positive integer (raise it to ask everyone again)")
    if not set(cfg.get("grant", [])) <= SIGNALS:
        errors.append(f"grant may only contain {sorted(SIGNALS)}")
    texts = cfg.get("texts") or {}
    if not texts:
        errors.append("texts needs at least one language")
    for lang, t in texts.items():
        missing = TEXT_KEYS - set(t)
        if missing:
            errors.append(f"texts.{lang} is missing {sorted(missing)}")
        for k, v in t.items():
            if "—" in v:
                errors.append(f"texts.{lang}.{k} has an em-dash")
    if cfg.get("defaultLang") and cfg["defaultLang"] not in texts:
        errors.append("defaultLang has no texts")
    if "policyPage" not in cfg.get("wp", {}):
        errors.append("wp.policyPage is required (page ID, slug or URL)")
    if errors:
        raise SystemExit(f"{name}: " + "; ".join(errors))


def build():
    v = version()
    DIST.mkdir(exist_ok=True)
    out = DIST / f"consent-kit-{v}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "wordpress" / "consent-kit.php", "consent-kit/consent-kit.php")
        z.write(HERE / "consent-kit.js", "consent-kit/consent-kit.js")
    manifest = {
        "version": v,
        "package": f"https://github.com/{REPO}/releases/download/v{v}/consent-kit-{v}.zip",
        "url": f"https://github.com/{REPO}",
        "requires": "6.5",
        "requires_php": "7.4",
        "tested": "6.8",
    }
    (DIST / "update.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"built {out.relative_to(HERE)} and dist/update.json")
    return out


if __name__ == "__main__":
    for p in sorted((HERE / "sites").glob("*.json")):
        check(json.loads(p.read_text(encoding="utf-8")), p.stem)
    build()
