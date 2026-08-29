"""
Script 1: check-release

Purpose: find out whether upstream (Codeberg) has a newer release tag than
the last one we've seen, and — if so — whether that release actually
touched any `.png` files, WITHOUT doing a full clone. This is the cheap
check that stands between "cron fired" and "do expensive work" (script 2's
full clone + strip + hash).

Step A talks to Codeberg's Forgejo API (Gitea-compatible), a single small
HTTPS request, to get the latest tag.

Step B, only when the tag changed: fetches just the old and new tag objects
(no working tree, no full history — same `git fetch --depth 1 origin tag
<tag>` pattern script 2 uses) into a scratch repo, then runs
`git diff --name-status old_tag new_tag -- '*.png'` to list every `.png`
that was added/modified/deleted between the two releases. This is the
"grep" step: instead of piping `git log`/`git diff` output through grep,
git's own pathspec (`-- '*.png'`) does the filtering and `--name-status`
already tags each path A/M/D, which is more reliable than text-matching
the porcelain output.

Outputs (via $GITHUB_OUTPUT):
  new_release   "true" | "false"
  tag           the latest upstream tag name (always set, even if unchanged)
  png_changed   "true" | "false" — did this release touch any .png paths?
                Always "true" when there's no previous tag to diff against
                (first run) or the diff itself fails, so we fail open into
                building rather than silently skipping a real change.
  png_added     comma-separated list of added .png paths
  png_modified  comma-separated list of modified .png paths
  png_deleted   comma-separated list of deleted .png paths

Exit code is always 0 — "no new release" is a normal outcome, not an error.
Script 2 only runs when new_release == "true" and png_changed == "true".
"""

import os
import shutil
import subprocess
import sys

import requests

from common import (
    REPO_ROOT,
    UPSTREAM_API_BASE,
    UPSTREAM_CLONE_URL,
    load_cache,
    run,
    write_output,
)

FORCE_REBUILD = os.environ.get("FORCE_REBUILD", "false").lower() == "true"

# Scratch dir for the tag-vs-tag diff only — separate from CLONE_DIR, which
# script 2 owns and resets to a single tag's working tree.
DIFF_CLONE_DIR = REPO_ROOT / ".release-check-clone"

# git diff --name-status status letters -> our vocabulary. Renames (Rxxx)
# and copies (Cxxx) are rare for a texture tree; treat them as "modified".
STATUS_MAP = {"A": "added", "M": "modified", "D": "deleted"}


def get_latest_tag() -> str:
    # /releases is sorted newest-first by Forgejo/Gitea; the first entry
    # is the latest published (non-draft) release.
    resp = requests.get(
        f"{UPSTREAM_API_BASE}/releases", params={"limit": 1}, timeout=30
    )
    resp.raise_for_status()
    releases = resp.json()
    if not releases:
        raise RuntimeError("Upstream repo has no releases at all")
    return releases[0]["tag_name"]


def diff_png_changes(old_tag: str, new_tag: str) -> dict:
    """Fetch just old_tag/new_tag into a scratch repo and diff .png paths."""
    changes = {"added": [], "modified": [], "deleted": []}

    if DIFF_CLONE_DIR.exists():
        shutil.rmtree(DIFF_CLONE_DIR)
    DIFF_CLONE_DIR.mkdir(parents=True)

    try:
        run(["git", "init", "-q"], cwd=DIFF_CLONE_DIR)
        run(["git", "remote", "add", "origin", UPSTREAM_CLONE_URL], cwd=DIFF_CLONE_DIR)
        for tag in (old_tag, new_tag):
            run(
                ["git", "fetch", "--depth", "1", "origin", "tag", tag],
                cwd=DIFF_CLONE_DIR,
            )

        result = subprocess.run(
            ["git", "diff", "--name-status", old_tag, new_tag, "--", "*.png"],
            cwd=DIFF_CLONE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            status, path = fields[0], fields[-1]
            changes[STATUS_MAP.get(status[0], "modified")].append(path)
    finally:
        shutil.rmtree(DIFF_CLONE_DIR, ignore_errors=True)

    return changes


def main() -> int:
    cache = load_cache()
    latest_tag = get_latest_tag()
    last_checked_tag = cache.get("last_checked_tag")

    is_new = FORCE_REBUILD or (latest_tag != last_checked_tag)

    print(f"Last checked tag: {last_checked_tag!r}")
    print(f"Latest upstream tag: {latest_tag!r}")
    print(f"Force rebuild: {FORCE_REBUILD}")
    print(f"=> new_release: {is_new}")

    changes = {"added": [], "modified": [], "deleted": []}
    png_changed = True  # fail open: build unless the diff proves otherwise

    if is_new and last_checked_tag and last_checked_tag != latest_tag:
        print(f"Diffing {last_checked_tag} -> {latest_tag} for .png changes")
        try:
            changes = diff_png_changes(last_checked_tag, latest_tag)
            png_changed = bool(
                changes["added"] or changes["modified"] or changes["deleted"]
            )
            for kind, paths in changes.items():
                for p in paths:
                    print(f"  {kind}: {p}")
            print(
                f"=> png_changed: {png_changed} "
                f"(+{len(changes['added'])} ~{len(changes['modified'])} -{len(changes['deleted'])})"
            )
        except subprocess.CalledProcessError as e:
            print(
                f"WARNING: png diff failed ({e}), assuming textures changed",
                file=sys.stderr,
            )
    elif is_new:
        print(
            "No previous tag to diff against (first run or forced) — assuming textures changed"
        )

    write_output("new_release", "true" if is_new else "false")
    write_output("tag", latest_tag)
    write_output("png_changed", "true" if png_changed else "false")
    write_output("png_added", ",".join(changes["added"]))
    write_output("png_modified", ",".join(changes["modified"]))
    write_output("png_deleted", ",".join(changes["deleted"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
