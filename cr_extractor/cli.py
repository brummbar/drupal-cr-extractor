"""Command-line interface: fetch (mirror), render (markdown), run (both)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import api
from .classify import classify_record, parse_target
from .render import default_output_path, render, select_records
from .store import Store

IDLE_PAGES_TO_STOP = 2


def cmd_fetch(store: Store, full: bool, max_pages: int | None = None) -> int:
    listed = new = updated = skipped = 0
    idle_pages = 0
    mode = "full" if full else "incremental"
    print(f"Fetching Drupal core change records ({mode})...")
    for page, records, has_next in api.iter_pages():
        page_changed = 0
        for node in records:
            listed += 1
            if store.is_current(node):
                skipped += 1
                continue
            if store.exists(str(node["nid"])):
                updated += 1
            else:
                new += 1
            store.save(node)
            page_changed += 1
        print(f"  page {page}: {len(records)} listed, {page_changed} saved")
        if not full:
            idle_pages = idle_pages + 1 if page_changed == 0 and len(records) == api.PAGE_SIZE else 0
            if idle_pages >= IDLE_PAGES_TO_STOP:
                print(f"  no changes on {IDLE_PAGES_TO_STOP} consecutive pages; stopping (use --full to walk every page)")
                break
        if max_pages is not None and page + 1 >= max_pages:
            print(f"  reached --max-pages {max_pages}; stopping")
            break
        if not has_next:
            break
    store.write_meta(mode=mode, listed=listed, new=new, updated=updated, skipped=skipped)
    print(f"Done: {listed} listed, {new} new, {updated} updated, {skipped} already cached. Cache holds {store.count()} records.")
    return 0


def cmd_render(store: Store, target: str, from_version: str | None, output: str | None,
               split: bool, list_unclassified: bool) -> int:
    target_v = parse_target(target)
    from_v = parse_target(from_version) if from_version else None
    if from_v is not None and from_v >= target_v:
        raise ValueError(f"--from {from_version} must be lower than the target version {target}")
    if store.count() == 0:
        print("The cache is empty. Run `fetch --full` first.", file=sys.stderr)
        return 2
    out_path = Path(output) if output else default_output_path(target_v, from_v)
    written = render(store, target_v, out_path, from_version=from_v, split=split)
    by_version, drafts, unclassified = select_records(store, target_v, from_v)
    total = sum(len(v) for v in by_version.values())
    span = f"after {from_version} up to {target}" if from_v else f"{target_v[0]}.0–{target}"
    print(f"Rendered {total} published change records for Drupal {span} "
          f"({drafts} drafts skipped, {len(unclassified)} unclassified).")
    for path in written:
        print(f"  wrote {path}")
    if list_unclassified:
        print("Unclassified records (no usable version or branch):")
        for node in unclassified:
            print(f"  {node.get('url')}  branch={node.get('field_change_to_branch')!r} "
                  f"version={node.get('field_change_to')!r}  {node.get('title')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cr_extractor", description="Mirror drupal.org core change records and render them to Markdown.")
    parser.add_argument("--data-dir", default="data", help="cache directory (default: data)")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download new/updated change records into the cache")
    fetch.add_argument("--full", action="store_true", help="walk every page instead of stopping when nothing changes")
    fetch.add_argument("--max-pages", type=int, metavar="N", help="stop after N pages of 50 (useful for a quick subset)")

    def add_render_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("version", help="target version MAJOR.MINOR, e.g. 11.4 (includes 11.0 .. 11.4 unless --from is given)")
        p.add_argument("--from", dest="from_version", metavar="MAJOR.MINOR",
                       help="version you are on now (exclusive): --from 11.4 with target 11.5 renders only 11.5")
        p.add_argument("--output", help="markdown path (default: output/drupal-<span>-change-records.md)")
        p.add_argument("--split", action="store_true", help="write one file per minor plus an index file")
        p.add_argument("--list-unclassified", action="store_true", help="print records that could not be assigned to a version")

    add_render_args(sub.add_parser("render", help="render cached records to Markdown"))
    run = sub.add_parser("run", help="incremental fetch, then render")
    add_render_args(run)
    run.add_argument("--full", action="store_true", help="walk every page during the fetch")
    run.add_argument("--max-pages", type=int, metavar="N", help="stop the fetch after N pages of 50")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(Path(args.data_dir))
    try:
        if args.command == "fetch":
            return cmd_fetch(store, args.full, args.max_pages)
        if args.command == "render":
            return cmd_render(store, args.version, args.from_version, args.output, args.split, args.list_unclassified)
        if args.command == "run":
            code = cmd_fetch(store, args.full, args.max_pages)
            if code:
                return code
            return cmd_render(store, args.version, args.from_version, args.output, args.split, args.list_unclassified)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except api.ApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
