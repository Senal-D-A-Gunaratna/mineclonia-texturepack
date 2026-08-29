"""
Shared helpers for the Mineclonia texture pack pipeline.

Every script in this directory is meant to be run as its own step in the
GitHub Actions workflow, so state is passed between them via:
  - release-cache.json (persisted, git-tracked)
  - $GITHUB_OUTPUT (ephemeral, step-to-step within a single run)
"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = REPO_ROOT / "release-cache.json"
CLONE_DIR = REPO_ROOT / "clone"
TEXTUREPACK_DIR = REPO_ROOT / "texturepack"
ASSETS_DIR = REPO_ROOT / "assets"

UPSTREAM_OWNER = "mineclonia"
UPSTREAM_REPO = "mineclonia"
UPSTREAM_API_BASE = (
    f"https://codeberg.org/api/v1/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}"
)
UPSTREAM_CLONE_URL = f"https://codeberg.org/{UPSTREAM_OWNER}/{UPSTREAM_REPO}.git"

DEFAULT_CACHE = {
    "pack_version": "1.01",
    "last_checked_tag": None,
    "last_texture_hash": None,
}


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return dict(DEFAULT_CACHE)
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Backfill any missing keys so an older cache file never crashes a script.
    for key, value in DEFAULT_CACHE.items():
        data.setdefault(key, value)
    return data


def save_cache(data: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def bump_version(version: str) -> str:
    """1.01 -> 1.02 ... 1.99 -> 2.00 (last two digits roll, then major bumps)."""
    major_str, minor_str = version.split(".")
    major, minor = int(major_str), int(minor_str)
    minor += 1
    if minor > 99:
        minor = 0
        major += 1
    return f"{major}.{minor:02d}"


def run(cmd, cwd=None, check=True):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


def write_output(name: str, value: str) -> None:
    """Write a step output for later steps in the same GitHub Actions job."""
    gh_output = os.environ.get("GITHUB_OUTPUT")
    print(f"output: {name}={value}")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def hash_png_tree(root: Path) -> str:
    """
    Deterministic hash of a directory's .png files (relative path + content).
    Used to detect whether a new upstream release actually changed any
    textures, independent of unrelated code/lua changes in the release.
    """
    hasher = hashlib.sha256()
    png_files = sorted(p for p in root.rglob("*.png") if p.is_file())
    for path in png_files:
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
