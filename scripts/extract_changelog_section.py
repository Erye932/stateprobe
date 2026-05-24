"""Extract a single version section from CHANGELOG.md.

Usage:
    python scripts/extract_changelog_section.py <version> [<changelog_path>]

Prints the section body (everything between ``## <version>`` and the next
``## `` heading) to stdout. Exits non-zero if the section is missing.

This is used by ``.github/workflows/release.yml`` to keep GitHub Release
notes in lock-step with CHANGELOG.md without hand-curating a second copy.

The version argument can carry an optional ``v`` prefix (``v0.4.0``) — it is
stripped before matching, so the same tag name works as both Git tag and
CHANGELOG heading.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


def extract(text: str, version: str) -> str | None:
    """Return the body of the section whose heading starts with ``version``.

    The heading must look like ``## <version>`` followed by either end-of-line
    or whitespace. The returned body is everything up to (but not including)
    the next ``## `` heading or end of file.
    """

    version = version.lstrip("v").strip()
    pattern = re.compile(
        r"^##\s+" + re.escape(version) + r"(?:\s|$)[^\n]*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version to extract, e.g. 0.4.0 or v0.4.0")
    parser.add_argument(
        "changelog",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG.md (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    path = pathlib.Path(args.changelog)
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    body = extract(path.read_text(encoding="utf-8"), args.version)
    if body is None:
        print(
            f"error: no '## {args.version.lstrip('v')}' section in {path}",
            file=sys.stderr,
        )
        return 1

    sys.stdout.write(body)
    if not body.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
