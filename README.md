# mineclonia-texturepack

A GitHub Actions pipeline that watches [Mineclonia](https://codeberg.org/mineclonia/mineclonia)
on Codeberg for new releases and repackages its textures as a standalone
Luanti/Minetest texture pack, published here as GitHub releases

Runs every 6 hours (`.github/workflows/build-texturepack.yml`), or on demand
via the "Run workflow" button in the Actions tab (with an optional `force`
input to rebuild even if nothing changed upstream)

## Pipeline

| Step | Script | Does |
| --- | --- | --- |
| 1 | `scripts/01_check_release.py` | Hits Codeberg's API for the latest release tag. If it's new, fetches just the old and new tag objects (no working tree) into a scratch dir and runs `git diff --name-status old new -- '*.png'` to see whether the release touched any textures at all |
| 2 | `scripts/02_build_texturepack.py` | Clones/resets `clone/` to that tag, strips `mods/` down to just `.png` files, hashes them, and compares to the last build. Only stages `texturepack/` if the actual texture bytes changed |
| 3 | `scripts/03_publish_release.py` | Zips `texturepack/`, bumps our own pack version, publishes a GitHub release, and updates `release-cache.json` |

Two layers of "did anything actually change" checking, both before any
publish happens:

- **Step 1** is path-level and cheap — no full clone, just a tag-vs-tag
  diff. It rules out releases that only touched code/docs, so step 2 never
  even clones for those.
- **Step 2** is content-level — it hashes the stripped `.png` tree, so even
  a release that touched a texture path but left the bytes identical (e.g.
  reverted) still won't trigger a publish.

Most scheduled runs should exit after step 1 with nothing to do

## Repo layout

- `scripts/` — the pipeline, run in order by the workflow
- `assets/` — `texture_pack.conf`, `CREDITS.md`, and `LICENSE.txt` (the last
  one is synced from upstream on every successful build) — copied into every
  release alongside the textures
- `release-cache.json` — tracks our pack version, the last upstream tag we
  built from, and a hash of the last texture set (to detect no-op releases)
- `clone/` and `texturepack/` are working directories, gitignored — never
  committed

## Versioning

Our own pack version (independent of Mineclonia's upstream version number),
starting at `1.00`. The last two digits count up to `99`, then roll over and
the first digit increments (`1.99` → `2.00`)

## Credits

All artwork belongs to the [Mineclonia](https://codeberg.org/mineclonia/mineclonia)
project and its contributors. This repo only automates repackaging their
`.png` assets — see `assets/CREDITS.md` and `assets/LICENSE.txt` (GPLv3,
inherited from upstream)
