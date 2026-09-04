"""Derive (major, minor) from the free-text version/branch fields of a change record."""

from __future__ import annotations

import re

VERSION_RE = re.compile(r"^\s*(\d+)\.(\d+)(?:[.\-]|\s*$)")
BRANCH_RE = re.compile(r"^\s*(\d+)\.(\d+)\.x\s*$")
TARGET_RE = re.compile(r"^(\d+)\.(\d+)$")
PRERELEASE_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:-([a-z]+)(\d*))?$", re.IGNORECASE)

PRERELEASE_RANK = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3}


def parse_target(text: str) -> tuple[int, int]:
    """Parse a user-supplied `MAJOR.MINOR` string; raise ValueError otherwise."""
    match = TARGET_RE.match(text.strip())
    if not match:
        raise ValueError(f"expected a version like 11.2 (MAJOR.MINOR), got {text!r}")
    return int(match.group(1)), int(match.group(2))


def classify(branch: str | None, version: str | None) -> tuple[int, int] | None:
    """Return (major, minor) for a record, preferring the explicit version over the branch."""
    match = VERSION_RE.match(version or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    match = BRANCH_RE.match(branch or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def classify_record(node: dict) -> tuple[int, int] | None:
    return classify(node.get("field_change_to_branch"), node.get("field_change_to"))


def version_sort_key(version: str | None) -> tuple:
    """Numeric-aware sort key: 11.2.0-beta1 < 11.2.0-rc1 < 11.2.0 < 11.2.6; unparseable last."""
    text = (version or "").strip()
    match = PRERELEASE_RE.match(text)
    if not match:
        return (2, "") if not text else (1, text)
    major, minor, patch, tag, tag_number = match.groups()
    rank = PRERELEASE_RANK.get((tag or "").lower(), 4) if tag else 5
    return (0, int(major), int(minor), int(patch) if patch else -1, rank, int(tag_number) if tag_number else 0)
