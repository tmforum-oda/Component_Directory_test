# ODA Component Catalog (trial)

A generated MkDocs Material site that turns the component data in
[tmforum-rand/TMForum-ODA-Ready-for-publication](https://github.com/tmforum-rand/TMForum-ODA-Ready-for-publication)
(branch `v1.0.0`) into a browsable catalog, laid out after the
[TM Forum ODA Component Directory](https://www.tmforum.org/oda/directory).

This repo holds only the site generator - `generate.py`, `mkdocs.yml`, and
the `static/` assets it copies into the build. It does not contain any
component data itself; `generate.py` reads that from a checkout of the data
repo above, located via the `ODA_DATA_REPO` environment variable (see
`resolve_data_repo()` in `generate.py`). Nothing under `docs/` is
hand-written - re-run the generator any time the data repo's component
assets change, there is nothing to hand-edit.

## Build locally

Clone the data repo alongside this one (or point `ODA_DATA_REPO` at any
existing checkout):

```bash
git clone --branch v1.0.0 https://github.com/tmforum-rand/TMForum-ODA-Ready-for-publication.git ../TMForum-ODA-Ready-for-publication
pip install -r requirements.txt
python generate.py
mkdocs serve
```

`mkdocs serve` starts a local preview at http://127.0.0.1:8000. If the data
repo checkout isn't a sibling directory, set `ODA_DATA_REPO=/path/to/it`
before running `generate.py`.

## Deploy

`.github/workflows/docs.yml` checks out this repo and the data repo, runs
the same two steps, and publishes the built site to GitHub Pages on every
push to `master`. GitHub Pages must be enabled once in this repository's
Settings > Pages, with **Source** set to **GitHub Actions**.
