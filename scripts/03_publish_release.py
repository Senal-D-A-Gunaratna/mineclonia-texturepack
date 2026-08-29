"""
Script 3: publish-release

Only runs when script 2 reported changed == "true". Responsibilities:

  1. Zip up texturepack/.
  2. Bump our own pack_version in release-cache.json (1.01 -> 1.02, ...,
     1.99 -> 2.00), and name the zip after the new version.
  3. Publish it as a GitHub release using the `gh` CLI (preinstalled on
     GitHub-hosted runners; auth comes from GH_TOKEN in the environment).
  4. Persist the updated release-cache.json (pack_version, the upstream
     tag we just built from, and the texture hash script 2 computed) —
     the workflow commits this file back to the repo in the step after
     this script runs.

Outputs (via $GITHUB_OUTPUT):
  new_version   the newly published pack version, e.g. "1.02"
"""

import os
import shutil
import sys

from common import (
    REPO_ROOT,
    TEXTUREPACK_DIR,
    bump_version,
    load_cache,
    run,
    save_cache,
    write_output,
)

UPSTREAM_TAG = os.environ.get("RELEASE_TAG")
TEXTURE_HASH = os.environ.get("TEXTURE_HASH")

if not UPSTREAM_TAG or not TEXTURE_HASH:
    print("RELEASE_TAG and TEXTURE_HASH env vars are required", file=sys.stderr)
    sys.exit(1)


def zip_texturepack(version: str) -> str:
    archive_base = str(REPO_ROOT / f"mineclonia-texturepack-v{version}")
    archive_path = shutil.make_archive(archive_base, "zip", root_dir=TEXTUREPACK_DIR)
    print(f"Created {archive_path}")
    return archive_path


def publish_github_release(version: str, zip_path: str) -> None:
    tag = f"v{version}"
    title = f"Mineclonia Texture Pack v{version}"
    notes = (
        f"Auto-generated from Mineclonia release `{UPSTREAM_TAG}` "
        f"(https://codeberg.org/mineclonia/mineclonia/releases/tag/{UPSTREAM_TAG}).\n\n"
        "All textures are the original work of the Mineclonia project and its "
        "contributors; this repo only repackages the `.png` assets from `mods/` "
        "into a standalone Luanti/Minetest texture pack. See LICENSE.txt (GPLv3, "
        "inherited from upstream) and CREDITS.md included in the archive."
    )
    run(
        [
            "gh",
            "release",
            "create",
            tag,
            zip_path,
            "--title",
            title,
            "--notes",
            notes,
        ]
    )


def main() -> int:
    cache = load_cache()
    new_version = bump_version(cache["pack_version"])

    zip_path = zip_texturepack(new_version)
    publish_github_release(new_version, zip_path)

    cache["pack_version"] = new_version
    cache["last_checked_tag"] = UPSTREAM_TAG
    cache["last_texture_hash"] = TEXTURE_HASH
    save_cache(cache)

    write_output("new_version", new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
