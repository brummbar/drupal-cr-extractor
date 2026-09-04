# drupal-cr-extractor

Mirrors the Drupal core change records listed at <https://www.drupal.org/list-changes/drupal>
into a local cache and renders them to Markdown for a given `MAJOR.MINOR`, **cumulatively**:
`11.4` produces everything introduced in 11.0, 11.1, 11.2, 11.3 and 11.4.

The listing page sits behind a JavaScript bot challenge, so the tool uses drupal.org's public
REST API (`/api-d7/node.json?type=changenotice&field_project=3060`) instead. Only published
change records are rendered; drafts are cached but never emitted.

## Usage (Docker)

```sh
docker compose build
docker compose run --rm cr fetch --full     # first run: mirror all ~4 700 records (1–2 min)
docker compose run --rm cr run 11.4         # incremental fetch, then render 11.0 .. 11.4
docker compose run --rm cr render 11.4      # render only, from the cache
```

Output lands in `output/drupal-11.4-change-records.md`. Options for `render`/`run`:

- `--from MAJOR.MINOR` — the version you are on now (exclusive). `render 11.5 --from 11.4`
  emits only 11.5; `render 11.2 --from 10.4` emits 10.5, 10.6, 11.0, 11.1, 11.2.
  Output goes to `output/drupal-11.4-to-11.5-change-records.md`.
- `--output PATH` — write somewhere else.
- `--split` — one file per minor plus an index, for agents with small context windows.
- `--list-unclassified` — print records whose version and branch fields are unusable
  (e.g. branch `main` with version `12.x`); these are never rendered.

`fetch --max-pages N` (also on `run`) stops after N pages of 50, handy for trying the tool on a subset.

`fetch` walks the list sorted by last-modified and stops after two consecutive pages with nothing
new, so re-runs are quick. Pass `--full` to walk every page.

## Layout

- `cr_extractor/api.py` — API client with retries and pagination.
- `cr_extractor/store.py` — cache: `data/records/<nid>.json`, refreshed when `changed` differs.
- `cr_extractor/classify.py` — maps the free-text version/branch fields to `(major, minor)`.
- `cr_extractor/render.py` — Markdown rendering (HTML bodies converted with markdownify).
- `tests/` — run with `docker compose run --rm --entrypoint python cr -m unittest discover -s tests`.
