"""
Script 1: check-release

Purpose: find out whether upstream (Codeberg) has a newer release tag than
the last one we've seen, WITHOUT cloning anything — this is the cheap check
that stands between "cron fired" and "do expensive work".

Talks to Codeberg's Forgejo API (Gitea-compatible), which is a single small
HTTPS request rather than a git clone.

Outputs (via $GITHUB_OUTPUT):
  new_release   "true" | "false"
  tag           the latest upstream tag name (always set, even if unchanged)

Exit code is always 0 — "no new release" is a normal outcome, not an error.
Script 2 only runs when new_release == "true" (or a manual force-rebuild
was requested via workflow_dispatch).
"""
import os
import sys

import requests

from common import UPSTREAM_API_BASE, load_cache, write_output

FORCE_REBUILD = os.environ.get("FORCE_REBUILD", "false").lower() == "true"


def get_latest_tag() -> str:
    # /releases is sorted newest-first by Forgejo/Gitea; the first entry
    # is the latest published (non-draft) release.
    resp = requests.get(f"{UPSTREAM_API_BASE}/releases", params={"limit": 1}, timeout=30)
    resp.raise_for_status()
    releases = resp.json()
    if not releases:
        raise RuntimeError("Upstream repo has no releases at all")
    return releases[0]["tag_name"]


def main() -> int:
    cache = load_cache()
    latest_tag = get_latest_tag()
    last_checked_tag = cache.get("last_checked_tag")

    is_new = FORCE_REBUILD or (latest_tag != last_checked_tag)

    print(f"Last checked tag: {last_checked_tag!r}")
    print(f"Latest upstream tag: {latest_tag!r}")
    print(f"Force rebuild: {FORCE_REBUILD}")
    print(f"=> new_release: {is_new}")

    write_output("new_release", "true" if is_new else "false")
    write_output("tag", latest_tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
