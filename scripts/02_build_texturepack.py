"""
Script 2: build-texturepack

Only runs when script 1 found a new upstream tag (or a manual force-rebuild
was requested). Responsibilities:

  1. Clone the remote repo into clone/ if it isn't there yet; otherwise
     reset the existing clone to the target tag, discarding local changes.
  2. Walk clone/mods/, and in every subdirectory delete everything except
     .png files, then delete any directory left empty.
  3. Hash the resulting set of .png files. If that hash matches
     last_texture_hash from release-cache.json, the new release didn't
     actually touch any textures -> stop here, nothing to publish.
  4. If the hash differs: wipe texturepack/, copy the cleaned mods/ tree
     into it, copy Mineclonia's LICENSE.txt into assets/ (so it's shipped
     inside the pack and kept current), then copy assets/ into
     texturepack/ too.

Outputs (via $GITHUB_OUTPUT):
  changed       "true" | "false"
  texture_hash  the new hash (only meaningful when changed == "true")

release-cache.json itself is NOT written here — script 3 updates and
persists it only after a release has actually been published, so a failed
publish step can be retried against the same state next run.
"""

import os
import shutil
import sys
from pathlib import Path

from common import (
    ASSETS_DIR,
    CLONE_DIR,
    TEXTUREPACK_DIR,
    UPSTREAM_CLONE_URL,
    clear_dir,
    hash_png_tree,
    load_cache,
    run,
    write_output,
)

TAG = os.environ.get("RELEASE_TAG")
if not TAG:
    print("RELEASE_TAG env var is required", file=sys.stderr)
    sys.exit(1)


def sync_clone(tag: str) -> None:
    if not (CLONE_DIR / ".git").exists():
        print(f"No existing clone — cloning {UPSTREAM_CLONE_URL} @ {tag}")
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                tag,
                UPSTREAM_CLONE_URL,
                str(CLONE_DIR),
            ]
        )
        return

    print("Existing clone found — resetting to latest remote state")
    run(["git", "fetch", "--depth", "1", "--tags", "origin", "tag", tag], cwd=CLONE_DIR)
    run(["git", "checkout", "--force", tag], cwd=CLONE_DIR)
    run(["git", "reset", "--hard", tag], cwd=CLONE_DIR)
    run(["git", "clean", "-fdx"], cwd=CLONE_DIR)


def strip_mods_to_pngs(mods_dir: Path) -> None:
    if not mods_dir.exists():
        raise RuntimeError(f"Expected mods/ dir at {mods_dir}, not found")

    # Delete every non-.png file anywhere under mods/.
    for path in mods_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() != ".png":
            path.unlink()

    # Bottom-up so nested-now-empty dirs get removed too.
    for path in sorted(mods_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def copy_upstream_license() -> None:
    license_src = CLONE_DIR / "LICENSE.txt"
    if license_src.exists():
        shutil.copy2(license_src, ASSETS_DIR / "LICENSE.txt")
        print("Copied upstream LICENSE.txt into assets/")
    else:
        print(
            "WARNING: upstream LICENSE.txt not found, keeping existing assets copy",
            file=sys.stderr,
        )


def stage_texturepack(mods_dir: Path) -> None:
    clear_dir(TEXTUREPACK_DIR)
    shutil.copytree(mods_dir, TEXTUREPACK_DIR, dirs_exist_ok=True)
    shutil.copytree(ASSETS_DIR, TEXTUREPACK_DIR, dirs_exist_ok=True)


def main() -> int:
    cache = load_cache()

    sync_clone(TAG)
    strip_mods_to_pngs(CLONE_DIR / "mods")

    new_hash = hash_png_tree(CLONE_DIR / "mods")
    old_hash = cache.get("last_texture_hash")
    changed = new_hash != old_hash

    print(f"Previous texture hash: {old_hash}")
    print(f"New texture hash:      {new_hash}")
    print(f"=> changed: {changed}")

    if changed:
        copy_upstream_license()
        stage_texturepack(CLONE_DIR / "mods")

    write_output("changed", "true" if changed else "false")
    write_output("texture_hash", new_hash)
    return 0


if __name__ == "__main__":
    sys.exit(main())
