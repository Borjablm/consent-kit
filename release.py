"""Publish a new version to every site. Run from the repository checkout, on main, with a clean tree.

    1. Raise the version in wordpress/consent-kit.php (header and CONSENT_KIT_VERSION) and the
       first line of consent-kit.js, and commit.
    2. python release.py

It runs both test suites and stops on any failure, builds the zip, creates the GitHub release
v<version> with the zip attached, and only then commits update.json. Sites check that file and
auto-update within about 12 hours. A bad release reaches every site, hence the test gate.
To roll back, release the previous code under a higher version number.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build import REPO, build, version  # noqa: E402


def run(*cmd, **kw):
    print("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=HERE, check=True, text=True, **kw)


def main():
    v = version()
    if subprocess.run(["git", "status", "--porcelain"], cwd=HERE, capture_output=True, text=True).stdout.strip():
        raise SystemExit("Commit or stash your changes first.")
    if subprocess.run(["gh", "release", "view", f"v{v}", "--repo", REPO], cwd=HERE, capture_output=True).returncode == 0:
        raise SystemExit(f"v{v} is already released. Raise the version first.")
    run(sys.executable, "test/lint.py")
    run(sys.executable, "test/test_js.py")
    run(sys.executable, "test/test_adapters.py")
    run(sys.executable, "test/test_wp.py")
    zip_path = build()
    run("gh", "release", "create", f"v{v}", str(zip_path), "--repo", REPO, "--title", f"Consent Kit {v}", "--notes", f"Consent Kit {v}. Sites update themselves from update.json.")
    shutil.copy(HERE / "dist" / "update.json", HERE / "update.json")
    json.loads((HERE / "update.json").read_text(encoding="utf-8"))
    run("git", "add", "update.json")
    run("git", "commit", "-m", f"Release {v}")
    run("git", "push")
    print(f"Released {v}. Sites pick it up within about 12 hours; check one with `python configure.py <site> --diff`.")


if __name__ == "__main__":
    main()
