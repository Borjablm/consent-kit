"""Publish a new version to every site. Run from the repository checkout, on main, with a clean tree.

    1. Raise the version in wordpress/consent-kit.php (header and CONSENT_KIT_VERSION) and the
       first line of consent-kit.js, and commit.
    2. python release.py

It runs both test suites and stops on any failure, builds the zip, creates the GitHub release
v<version> with the zip attached, and only then commits update.json. Sites check that file and
show the update in wp-admin within about 12 hours; an admin installs it on each site (from 1.1.2
on, nothing installs automatically).
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
    # Push the code first and tag that exact commit. (1.1.0 was tagged on the old main because the
    # release was created before the push, so `npm install ...#v1.1.0` and jsDelivr got 1.0.0 code.)
    run("git", "push")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
    run("gh", "release", "create", f"v{v}", str(zip_path), "--repo", REPO, "--target", sha, "--title", f"Consent Kit {v}", "--notes", f"Consent Kit {v}. Install it from Plugins in wp-admin on each site.")
    subprocess.run(["git", "fetch", "-q", "--tags"], cwd=HERE, check=True)
    tagged = subprocess.run(["git", "rev-list", "-n1", f"v{v}"], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
    if tagged != sha:
        raise SystemExit(f"v{v} points at {tagged}, expected {sha}. update.json was NOT changed; fix the tag first.")
    shutil.copy(HERE / "dist" / "update.json", HERE / "update.json")
    json.loads((HERE / "update.json").read_text(encoding="utf-8"))
    run("git", "add", "update.json")
    run("git", "commit", "-m", f"Release {v}")
    run("git", "push")
    print(f"Released {v}. Sites pick it up within about 12 hours; check one with `python configure.py <site> --diff`.")


if __name__ == "__main__":
    main()
