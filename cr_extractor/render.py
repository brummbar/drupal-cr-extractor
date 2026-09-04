"""Render cached change records into Markdown for a MAJOR.MINOR target (cumulative over minors)."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from markdownify import MarkdownConverter

from .classify import classify_record, version_sort_key
from .store import Store

IMPACTS = {
    "1": "Site builders, administrators, editors",
    "2": "Module developers",
    "3": "Themers",
    "4": "Site templates, recipes and distribution developers",
}

CODE_LANGUAGE_RE = re.compile(r"language-([\w+-]+)")


class _Converter(MarkdownConverter):
    """markdownify tuned for drupal.org bodies: fenced code with language, demoted headings."""

    def __init__(self, **options):
        options.setdefault("heading_style", "ATX")
        options.setdefault("bullets", "-")
        options.setdefault("code_language_callback", self._code_language)
        super().__init__(**options)

    def convert_pre(self, el, text, parent_tags):
        # Strip the trailing newline drupal.org keeps inside <pre>, which would add a blank line before the fence.
        return super().convert_pre(el, text.rstrip("\n") if text else text, parent_tags)

    @staticmethod
    def _code_language(element) -> str:
        for candidate in (element, *element.find_all("code", limit=1)):
            match = CODE_LANGUAGE_RE.search(" ".join(candidate.get("class", [])))
            if match:
                return match.group(1)
        return ""


def html_to_markdown(html: str) -> str:
    text = _Converter().convert(html or "")
    text = _demote_headings(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _demote_headings(text: str) -> str:
    """Push headings below the record's own ### level, leaving fenced code blocks untouched."""
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            match = re.match(r"^(#{1,6}) ", line)
            if match:
                line = "#" * min(len(match.group(1)) + 3, 6) + line[len(match.group(1)):]
        out.append(line)
    return "\n".join(out)


def _date(timestamp) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "unknown"


def _impacts(node: dict) -> str:
    keys = node.get("field_impacts") or []
    return ", ".join(IMPACTS.get(str(k), f"impact:{k}") for k in keys) or "not specified"


def _issues(node: dict) -> str:
    links = [link.get("url") for link in node.get("field_issue_links") or [] if link.get("url")]
    return ", ".join(links) or "none"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render_record(node: dict) -> str:
    version = (node.get("field_change_to") or "").strip() or "not specified"
    branch = (node.get("field_change_to_branch") or "").strip() or "not specified"
    author = (node.get("author") or {}).get("name") or "unknown"
    body = html_to_markdown((node.get("field_description") or {}).get("value") or "")
    lines = [
        f"### {node.get('title', '').strip()}",
        "",
        f"- Source: {node.get('url', '')}",
        f"- Introduced in: {version} (branch {branch})",
        f"- Impacts: {_impacts(node)}",
        f"- Issues: {_issues(node)}",
        f"- Author: {author} · created {_date(node.get('created'))} · updated {_date(node.get('changed'))}",
        "",
        body or "_No description._",
        "",
    ]
    return "\n".join(lines)


Version = tuple[int, int]


def select_records(store: Store, target: Version, from_version: Version | None = None):
    """Return (records grouped by (major, minor), drafts skipped, unclassified nodes).

    Selected versions are those v with from_version < v <= target, where a missing from_version
    means "everything of the target major from .0". Ordering is lexicographic on (major, minor),
    so ranges may span majors (e.g. from 10.4 to 11.2 gives 10.5, 10.6, 11.0, 11.1, 11.2).
    """
    lower = from_version if from_version is not None else (target[0], -1)
    by_version: dict[Version, list[dict]] = defaultdict(list)
    drafts = 0
    unclassified: list[dict] = []
    for node in store.iter_records():
        classification = classify_record(node)
        if classification is None:
            unclassified.append(node)
            continue
        if not (lower < classification <= target):
            continue
        if not node.get("field_change_record_status"):
            drafts += 1
            continue
        by_version[classification].append(node)
    return by_version, drafts, unclassified


def _version_groups(nodes: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        groups[(node.get("field_change_to") or "").strip()].append(node)
    ordered = sorted(groups.items(), key=lambda item: version_sort_key(item[0]))
    return [(version, sorted(items, key=lambda n: int(n.get("created") or 0))) for version, items in ordered]


def _label(version: Version) -> str:
    return f"{version[0]}.{version[1]}"


def render_minor(version: Version, nodes: list[dict]) -> str:
    out = [f"# Drupal {_label(version)}", ""]
    for exact, items in _version_groups(nodes):
        if exact:
            out.append(f"## Introduced in {exact}")
        else:
            branches = sorted({(n.get('field_change_to_branch') or '').strip() for n in items} - {""})
            suffix = f" (branch {', '.join(branches)})" if branches else ""
            out.append(f"## Version not specified{suffix}")
        out.append("")
        out.append("\n---\n\n".join(render_record(node) for node in items))
        out.append("")
    return "\n".join(out)


def render_header(target: Version, from_version: Version | None, versions: list[Version],
                  by_version: dict, drafts: int, unclassified: int) -> str:
    total = sum(len(by_version.get(v, [])) for v in versions)
    if from_version is None:
        title = f"Drupal core change records up to {_label(target)}"
        scope = f"Covers Drupal {target[0]}.0 through {_label(target)}"
    else:
        title = f"Drupal core change records from {_label(from_version)} to {_label(target)}"
        scope = f"Covers what changed after Drupal {_label(from_version)} up to and including {_label(target)}"
    lines = [
        f"# {title}",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from "
        "https://www.drupal.org/list-changes/drupal (published records only).",
        "",
        f"{scope}: {total} change records in {len(versions)} minor release(s).",
        f"Skipped: {drafts} draft/review records for these minors. "
        f"{unclassified} cached records across all majors have no usable version or branch and are never rendered.",
        "",
        "| Minor | Change records |",
        "|-------|----------------|",
    ]
    lines += [f"| {_label(v)} | {len(by_version.get(v, []))} |" for v in versions]
    lines += ["", "## Contents", ""]
    for v in versions:
        lines.append(f"- Drupal {_label(v)}")
        for exact, items in _version_groups(by_version.get(v, [])):
            lines.append(f"  - {exact or 'version not specified'} ({len(items)})")
    lines.append("")
    return "\n".join(lines)


def covered_versions(target: Version, from_version: Version | None, by_version: dict) -> list[Version]:
    """Minor releases to emit: every minor of the target major from .0 (or after from_version),
    plus any earlier-major minors found in the cache when the range spans majors."""
    lower = from_version if from_version is not None else (target[0], -1)
    versions = {v for v in by_version if lower < v <= target}
    # Always list the target major's minors contiguously, even if some have no records.
    first_minor = lower[1] + 1 if lower[0] == target[0] else 0
    versions.update((target[0], m) for m in range(first_minor, target[1] + 1))
    return sorted(versions)


def default_output_path(target: Version, from_version: Version | None) -> Path:
    span = f"{_label(from_version)}-to-{_label(target)}" if from_version else _label(target)
    return Path("output") / f"drupal-{span}-change-records.md"


def render(store: Store, target: Version, output: Path, from_version: Version | None = None,
           split: bool = False) -> list[Path]:
    by_version, drafts, unclassified = select_records(store, target, from_version)
    versions = covered_versions(target, from_version, by_version)
    header = render_header(target, from_version, versions, by_version, drafts, len(unclassified))
    written: list[Path] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    if split:
        output.write_text(header + "\n", encoding="utf-8")
        written.append(output)
        for v in versions:
            path = output.with_name(f"{output.stem}-{_label(v)}{output.suffix}")
            path.write_text(render_minor(v, by_version.get(v, [])) + "\n", encoding="utf-8")
            written.append(path)
    else:
        parts = [header] + [render_minor(v, by_version.get(v, [])) for v in versions]
        output.write_text("\n".join(parts) + "\n", encoding="utf-8")
        written.append(output)
    return written
