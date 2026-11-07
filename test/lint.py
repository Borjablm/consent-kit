"""Static checks, zero findings allowed (the bar in Lumination's backend CONTRIBUTING.md). Needs Docker.

    python test/lint.py

1. gitleaks: no secrets anywhere in the folder.
2. PHPCompatibilityWP: the plugin runs on PHP 7.4 and later.
3. WordPress-Extra coding standards (escaping, SQL preparation, nonces, style). Every
   phpcs:ignore must name its rule and give a reason after " -- ".
4. ESLint recommended rules on consent-kit.js.
Never weaken a rule to pass; fix the code.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = str(ROOT).replace("\\", "/")
ENV = {"MSYS_NO_PATHCONV": "1"}

PHPCS = (
    "cd /tmp && composer init -q -n --name=ck/lint 2>/dev/null; "
    "composer config allow-plugins.dealerdirect/phpcodesniffer-composer-installer true && "
    "composer require -q -n --dev wp-coding-standards/wpcs:^3 phpcompatibility/phpcompatibility-wp:^2.1 >/dev/null 2>&1 && "
    "vendor/bin/phpcs --standard=PHPCompatibilityWP --runtime-set testVersion 7.4- /src/consent-kit.php && "
    "vendor/bin/phpcs --standard=WordPress-Extra --exclude=WordPress.Files.FileName /src/consent-kit.php"
)
ESLINT = (
    "mkdir /l && cd /l && npm init -y >/dev/null && npm i -s eslint@9 @eslint/js@9 globals@15 >/dev/null 2>&1 && "
    "printf '%s\\n' \"import js from '@eslint/js'; import globals from 'globals';\" "
    "\"export default [js.configs.recommended, {languageOptions: {ecmaVersion: 2015, sourceType: 'script', globals: globals.browser}}];\" > eslint.config.mjs && "
    "cp /src/consent-kit.js . && npx eslint --max-warnings 0 consent-kit.js"
)

CHECKS = [
    ("Secrets (gitleaks)", ["docker", "run", "--rm", "-v", f"{SRC}:/src:ro", "zricethezav/gitleaks:latest", "dir", "/src", "--no-banner", "--redact"]),
    ("PHP 7.4+ and WordPress standards (phpcs)", ["docker", "run", "--rm", "-v", f"{SRC}/wordpress:/src:ro", "composer:2", "sh", "-c", PHPCS]),
    ("JavaScript (ESLint)", ["docker", "run", "--rm", "-v", f"{SRC}:/src:ro", "node:22-alpine", "sh", "-c", ESLINT]),
]


def suppressions_have_reasons():
    bad = [f"line {i}" for i, line in enumerate((ROOT / "wordpress" / "consent-kit.php").read_text(encoding="utf-8").splitlines(), 1)
           if "phpcs:ignore" in line and not re.search(r"phpcs:ignore [\w.]+(, [\w.]+)* -- \S", line)]
    return not bad, ", ".join(bad)


def main():
    import os
    failed = []
    for name, cmd in CHECKS:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **ENV})
        ok = r.returncode == 0
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            failed.append(name)
            print((r.stdout + r.stderr)[-3000:])
    ok, where = suppressions_have_reasons()
    print(("PASS " if ok else "FAIL ") + "Every phpcs:ignore names its rule and gives a reason" + ("" if ok else f" ({where})"))
    if not ok:
        failed.append("suppressions")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
