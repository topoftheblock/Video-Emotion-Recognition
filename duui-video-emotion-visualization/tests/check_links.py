"""Check that every relative Markdown link points at something real.

Relative links only. External URLs are deliberately not fetched: link
rot is real, but a checker that needs the network fails for reasons that
have nothing to do with the change being checked, and a check that fails
at random stops being read.
"""

import pathlib
import re
import sys

LINK = re.compile(r"\[[^\]]*\]\(([^)\s#]*)(?:#[^)\s]*)?\)")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def main() -> int:
    """Check every relative link, and report the broken ones.

    Returns:
        A process exit status: non-zero if any link is broken.
    """
    root = pathlib.Path(".")
    broken: list[str] = []
    checked = 0

    for md in sorted(root.rglob("*.md")):
        if SKIP_DIRS & set(md.parts):
            continue
        for match in LINK.finditer(md.read_text(encoding="utf-8")):
            target = match.group(1)
            # Same-page anchors have no file part to check.
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            checked += 1
            if not (md.parent / target).resolve().exists():
                broken.append(f"{md}: {target}")

    if broken:
        print(f"{len(broken)} broken link(s) of {checked} checked:")
        for entry in broken:
            print(f"  {entry}")
        return 1

    print(f"{checked} relative links, all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
