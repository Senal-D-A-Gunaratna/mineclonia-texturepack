# mineclonia-texturepack

A GitHub Actions pipeline that watches [Mineclonia](https://codeberg.org/mineclonia/mineclonia)
on Codeberg for new releases and repackages its textures as a standalone
Luanti/Minetest texture pack, published here as GitHub releases.

Runs every 6 hours (`.github/workflows/build-texturepack.yml`), or on demand
via the "Run workflow" button in the Actions tab (with an optional `force`
input to rebuild even if nothing changed upstream).

## Pipeline

| Step | Script | Does |
|---|---|---|
| 1 | `scripts/01_check_release.py` | Hits Codeberg's API for the latest release tag. No cloning — just decides whether it's worth continuing. |
| 2 | `scripts/02_build_texturepack.py` | Clones/resets `clone/` to that tag, strips `mods/` down to just `.png` files, hashes them, and compares to the last build. Only stages `texturepack/` if textures actually changed. |
| 3 | `scripts/03_publish_release.py` | Zips `texturepack/`, bumps our own pack version, publishes a GitHub release, and updates `release-cache.json`. |

Each step only runs if the previous one found something worth acting on —
most scheduled runs should exit after step 1 with nothing to do.

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
starting at `1.01`. The last two digits count up to `99`, then roll over and
the first digit increments (`1.99` → `2.00`).

## Credits

All artwork belongs to the [Mineclonia](https://codeberg.org/mineclonia/mineclonia)
project and its contributors. This repo only automates repackaging their
`.png` assets — see `assets/CREDITS.md` and `assets/LICENSE.txt` (GPLv3,
inherited from upstream).
