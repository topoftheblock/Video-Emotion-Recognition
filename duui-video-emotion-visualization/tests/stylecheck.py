"""Check a sub-project against the style guide and the glossary.

    python3 tests/stylecheck.py <dir> [--exempt <path suffix>...]

Reports what no other checker does: prose wrapped past 72 columns, `--`
where an em dash belongs, malformed section banners, retired glossary
terms in prose *and* in identifiers, `noqa` directives for rules that
are not enabled, missing docstrings, and references to the current
corpus.

Every one of these is a rule in docs/documentation-style.md or
docs/glossary.md that `ruff` and `mypy` say nothing about. Phase 5 found
212 prose lines wrapped at the wrong width in a sub-project whose
rewrite was otherwise finished, which is why this exists rather than
being left to review.

Run it under the project's own interpreter, not the host's: the code
uses syntax the older versions cannot parse, and a checker that cannot
parse a file silently checks nothing.
"""

import argparse
import ast
import pathlib
import re
import sys

PROSE_WIDTH = 72
CODE_WIDTH = 88
BANNER_WIDTH = 74

# A well-formed section banner, per the style guide: `# --- Name
# ------`. The name may hold anything that is not a run of dashes, so a
# hyphen, an apostrophe or a plus sign is all fine.
BANNER_OK = re.compile(r"^([ \t]*)# --- [^\s-].*? -{3,}$")
# Anything meant to be one. Dashes at *both* ends, which is what tells a
# banner from a comment opening with a CSS custom property or a CLI flag
# (`# --factory because ...`).
BANNER_ANY = re.compile(r"^[ \t]*#\s*-{3,}.*-{3,}\s*$")

# The rule prefixes `pyproject.toml` actually selects. A `noqa` naming
# anything else suppresses a rule that was never enabled, and only
# implies the project runs a check it does not.
SELECTED_RULES = ("E", "F", "I")

# (pattern, flags, message). Case matters for some of these: an acronym
# is wrong in lower case but right in upper, so those patterns are
# deliberately case-sensitive.
GLOSSARY = [
    (r"\bviewer\b", re.I, "'viewer' is retired — say 'the webapp'"),
    (r"global identit(y|ies)", re.I, "'identity' as a noun — say 'global person'"),
    (r"cross-video person", re.I, "say 'global person'"),
    # The noun only. "clip off the top" is the verb, and `clip_label` is
    # a column name.
    (
        r"\b(a|the|each|every|this|that|per|two|these|those)\s+clips?\b|\bclips\b(?!_)",
        re.I,
        "say 'video', not 'clip'",
    ),
    # Only the noun: "recording its id" is the verb, and is fine.
    (
        r"\b(a|the|each|every|this|that|per)\s+recording\b|\brecordings\b",
        re.I,
        "say 'video', not 'recording'",
    ),
    (r"media directory|video folder", re.I, "say 'video store'"),
    (r"\btype system\b", re.I, "one word: 'typesystem'"),
    (r"\bthe XMI\b", 0, "say 'the CAS'; .xmi is the serialization"),
    (r"\ba cas\b", 0, "'CAS' is uppercase"),
    (r"\bimport job\b", re.I, "say 'an importer run'"),
    (r"the visual modality", re.I, "say the literal value: 'video'"),
]

# Rule 4 of the style guide: documentation never describes the corpus
# that happens to be loaded.
CORPUS = [
    (r"current corpus|in this corpus|our corpus", re.I, "do not describe the corpus"),
    (r"(?<!\d)\d{1,3},\d{3}(?!\d)", 0, "no corpus figures"),
]

# Rule 8 of the style guide: US English, everywhere, including code
# comments and log output. Nothing else in the roster spell-checks, so
# without this the rule holds only by review — and it did not: Phase 8
# found 231 British spellings across 38 files, in prose and in
# identifiers alike.
#
# Matched as substrings, not whole words, because the guide binds
# identifiers too and `load_person_colours` has no word boundary before
# `colours`. Two sequences contain one of these and are not misspelled:
# an ARIA attribute, and a license's actual name.
SPELLING = [
    ("colour", "color"),
    ("behaviour", "behavior"),
    ("artefact", "artifact"),
    ("centre", "center"),
    ("judgement", "judgment"),
    ("defence", "defense"),
    ("labelled", "labeled"),
    ("grey", "gray"),
    ("recognis", "recogniz"),
    ("normalis", "normaliz"),
    ("synthesise", "synthesize"),
    ("analyse", "analyze"),
    ("licence", "license"),
    ("flavour", "flavor"),
    ("honour", "honor"),
    ("favour", "favor"),
    ("organis", "organiz"),
    ("initialis", "initializ"),
    ("serialis", "serializ"),
]
SPELLING_EXEMPT = ("aria-labelledby", "Ubuntu Font Licence")

CHECKED_SUFFIXES = (
    ".py",
    ".toml",
    ".js",
    ".css",
    ".html",
    ".sh",
    ".yml",
    ".sql",
    ".cjs",
    ".jsonc",
)
# Files carrying real prose no suffix rule reaches: config dotfiles, and
# a shell script named for the git hook it installs as.
CHECKED_NAMES = (
    "Dockerfile",
    ".dockerignore",
    "requirements.txt",
    ".env.example",
    ".prettierignore",
    ".sqlfluff",
    ".yamllint",
    "pre-commit",
)
# `Dockerfile.tests` and the like: same comment syntax, same rules.
CHECKED_PREFIXES = ("Dockerfile.",)

# Not source: vendored font licenses, recorded measurements that are
# data rather than prose anyone wrote, and the caches and installed
# packages a development machine accumulates. The last never appears
# in the lint image, where the mount is the repository; it appears when
# the checker is run against a working tree.
SKIP_PARTS = (
    "__pycache__",
    "resources",
    "fonts",
    "a11y-baseline",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
)

# A SQL comment. The marker is the same two characters as the legacy em
# dash, which is why `.sql` needs its own handling rather than falling
# through to the `#` rule: without stripping the marker first, every
# comment in the schema reports itself as a dash.
SQL_COMMENT = re.compile(r"^[ \t]*--")

# The same, in the C-comment languages: `/* --- Name --- */`.
CSS_BANNER_OK = re.compile(r"^/\* --- [^\s-].*? -{3,} \*/$")
CSS_BANNER_ANY = re.compile(r"^\s*/\*\s*-{3,}.*-{3,}\s*(\*/)?\s*$")


# The four node types that can carry a docstring. Named once, so the
# check and the extraction below agree by construction.
Documentable = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def docstring_node(node: ast.AST) -> ast.Expr | None:
    """Return this node's docstring statement, if it has one.

    Returns the node rather than a bool so the caller does not have to
    reach back into `node.body` to find what this already located —
    which it cannot do without an ignore, `ast.AST` having no `body`.
    """
    if not isinstance(node, Documentable) or not node.body:
        return None
    first = node.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first
    return None


def _c_comment_lines(src: str) -> set[int]:
    """Return the line numbers inside `//` or `/* */` comments.

    A deliberately simple scan: it does not try to understand strings or
    regex literals, so a `//` inside one counts as a comment. That errs
    toward checking more prose, never less, which is the safe direction
    for a style check.
    """
    lines: set[int] = set()
    in_block = False
    for number, line in enumerate(src.split("\n"), start=1):
        stripped = line.strip()
        if in_block:
            lines.add(number)
            if "*/" in line:
                in_block = False
            continue
        if stripped.startswith("//"):
            lines.add(number)
        elif stripped.startswith("/*"):
            lines.add(number)
            if "*/" not in line[line.index("/*") :]:
                in_block = True
    return lines


def prose_lines(src: str, path: pathlib.Path) -> set[int]:
    """Return the line numbers holding comment or docstring prose.

    Args:
        src: The file's contents.
        path: Its path, which decides how comments are recognized.

    Returns:
        Every line number that carries prose rather than code.
    """
    lines: set[int] = set()
    if path.suffix == ".py":
        for node in ast.walk(ast.parse(src)):
            doc = docstring_node(node)
            if doc is not None and doc.end_lineno is not None:
                lines.update(range(doc.lineno, doc.end_lineno + 1))
    if path.suffix in (".js", ".css", ".cjs", ".jsonc"):
        return _c_comment_lines(src)
    if path.suffix == ".sql":
        return {
            number
            for number, line in enumerate(src.split("\n"), start=1)
            if SQL_COMMENT.match(line)
        }
    if path.suffix == ".html":
        return {
            number
            for number, line in enumerate(src.split("\n"), start=1)
            if "<!--" in line or "-->" in line
        }
    for number, line in enumerate(src.split("\n"), start=1):
        if re.match(r"^\s*#", line):
            lines.add(number)
    return lines


def _spelling_findings(lines: list[str]) -> list[tuple[int, str, str]]:
    """Report every British spelling, in prose and in identifiers alike.

    Args:
        lines: The file's lines.

    Returns:
        `(line, "spelling", message)` per finding.
    """
    found: list[tuple[int, str, str]] = []
    for number, line in enumerate(lines, start=1):
        probe = line
        for exempt in SPELLING_EXEMPT:
            probe = probe.replace(exempt, "")
        lowered = probe.lower()
        for british, american in SPELLING:
            if british in lowered:
                found.append(
                    (number, "spelling", f"British spelling; write '{american}'")
                )
    return found


def check_file(
    path: pathlib.Path, exempt: bool, exempt_terms: bool = False
) -> list[tuple[int, str, str]]:
    """Check one file against every rule.

    Args:
        path: The file to check.
        exempt: Whether the file is exempt from the width limits, which
            data files that happen to end in `.py` are.
        exempt_terms: Whether the file is exempt from the glossary,
            which a file whose *subject* is the glossary has to be:
            this module's own rule table holds every retired term by
            definition.

    Returns:
        `(line, kind, message)` per finding.
    """
    src = path.read_text()
    lines = src.split("\n")
    found: list[tuple[int, str, str]] = []

    spelling_lines = _spelling_findings(lines)
    try:
        prose = prose_lines(src, path)
    except SyntaxError as exc:
        return [(exc.lineno or 1, "syntax", str(exc))]

    for number, line in enumerate(lines, start=1):
        if path.suffix in (".js", ".css") and CSS_BANNER_ANY.match(line):
            if not CSS_BANNER_OK.match(line.strip()):
                found.append((number, "banner", f"malformed banner: {line.strip()}"))
            elif len(line) != BANNER_WIDTH:
                found.append(
                    (number, "banner", f"banner is {len(line)}, want {BANNER_WIDTH}")
                )
            continue
        if BANNER_ANY.match(line):
            if not BANNER_OK.match(line):
                found.append((number, "banner", f"malformed banner: {line.strip()}"))
            elif len(line) != BANNER_WIDTH:
                found.append(
                    (number, "banner", f"banner is {len(line)}, want {BANNER_WIDTH}")
                )
            continue

        if not exempt:
            if number in prose:
                # A comment that indents its content is quoting
                # something — a command, a path, a sample — and quoting
                # it is the point. Rewrapping would break it, so the
                # width rule has nothing to offer, exactly as with a
                # URL below.
                quoted = re.match(r"^[ \t]*(#|--|//|\*)\s{2,}\S", line) is not None
                if len(line) > PROSE_WIDTH and not quoted:
                    found.append(
                        (number, "width", f"prose {len(line)} > {PROSE_WIDTH}")
                    )
            # Code width belongs to the tool that already owns it:
            # prettier and stylelint for the C-comment languages,
            # yamllint for YAML — which exempts an unbreakable inline
            # value on purpose. Two checkers disagreeing helps nobody.
            elif path.suffix not in (".js", ".css", ".html", ".yml"):
                # A URL is one token and cannot be broken, so the width
                # rule has nothing to offer there.
                if len(line) > CODE_WIDTH and not re.search(r"https?://\S", line):
                    found.append((number, "width", f"code {len(line)} > {CODE_WIDTH}"))

        if number in prose:
            # Between words, or left dangling at a line break — both are
            # the legacy form. In SQL the opening marker is stripped
            # first, so a comment is judged on what it says rather than
            # on how it is introduced.
            probe = line
            if path.suffix == ".sql":
                probe = SQL_COMMENT.sub("", line, count=1)
            if re.search(r"(?<=\S) -- (?=\S)|(?<=\S) --\s*$|^\s*-- (?=\S)", probe):
                found.append((number, "emdash", "'--' as an em dash; write '—'"))
            # A color value lists numbers the way a grouped thousand is
            # written, so it is not a corpus figure.
            colorish = re.search(r"rgba?\(", line) is not None
            for pattern, flags, message in GLOSSARY + CORPUS:
                if colorish and "corpus figures" in message:
                    continue
                if exempt_terms and (pattern, flags, message) in GLOSSARY:
                    continue
                if re.search(pattern, line, flags):
                    found.append((number, "term", message))

        directive = (
            re.search(r"#\s*noqa:?\s*([A-Z]+)\d*", line)
            if path.suffix == ".py"
            else None
        )
        if directive and not directive.group(1).startswith(SELECTED_RULES):
            found.append(
                (
                    number,
                    "noqa",
                    f"noqa {directive.group(1)} suppresses an unselected rule",
                )
            )

    if path.suffix == ".py" and src.strip():
        tree = ast.parse(src)
        if not ast.get_docstring(tree):
            found.append((1, "docstring", "module has no docstring"))
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            # An @overload stub is a signature, not an implementation:
            # the real function below it carries the docstring.
            overload = any(
                (isinstance(d, ast.Name) and d.id == "overload")
                or (isinstance(d, ast.Attribute) and d.attr == "overload")
                for d in getattr(node, "decorator_list", [])
            )
            if not overload and not ast.get_docstring(node):
                found.append(
                    (node.lineno, "docstring", f"{node.name} has no docstring")
                )
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.returns is None
            ):
                found.append(
                    (node.lineno, "annot", f"{node.name} has no return annotation")
                )
            # The glossary binds identifiers too, not only prose.
            spaced = node.name.replace("_", " ")
            for pattern, flags, message in GLOSSARY:
                if re.search(pattern, spaced, flags):
                    found.append((node.lineno, "name", f"{node.name}: {message}"))

    # And it binds user-facing output, which is a string literal rather
    # than a comment: §9 of the style guide puts log lines, error
    # messages and anything the reader sees under the same rules. Three
    # of these reached the browser before this check existed.
    for number, line in enumerate(lines, start=1):
        if exempt_terms or number in prose or not re.search(r"[\"'`]", line):
            continue
        for text in re.findall(r"\"([^\"]{12,})\"|'([^']{12,})'|`([^`]{12,})`", line):
            literal = next(part for part in text if part)
            for pattern, flags, message in GLOSSARY:
                if re.search(pattern, literal, flags):
                    found.append((number, "term", f"in a string: {message}"))

    if not exempt_terms:
        found.extend(spelling_lines)
    return found


def collect(root: pathlib.Path) -> list[pathlib.Path]:
    """Return every file under `root` this checker reads, sorted.

    Selection is by suffix, by exact name, or by prefix, because the
    files carrying prose in this repository are not all named the same
    way: some have a suffix, some are config dotfiles, and one is a git
    hook with no extension at all.
    """
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in SKIP_PARTS for part in path.parts)
        and (
            path.suffix in CHECKED_SUFFIXES
            or path.name in CHECKED_NAMES
            or path.name.startswith(CHECKED_PREFIXES)
        )
    )


def main() -> int:
    """Check every file under the given directory, and report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="the sub-project to check")
    parser.add_argument(
        "--exempt",
        nargs="*",
        default=[],
        help="path suffixes exempt from the width limits",
    )
    parser.add_argument(
        "--exempt-terms",
        nargs="*",
        default=[],
        help="path suffixes exempt from the glossary",
    )
    args = parser.parse_args()

    files = collect(pathlib.Path(args.root))

    by_kind: dict[str, list[str]] = {}
    total = 0
    for path in files:
        exempt = any(str(path).endswith(suffix) for suffix in args.exempt)
        exempt_terms = any(str(path).endswith(suffix) for suffix in args.exempt_terms)
        for number, kind, message in check_file(path, exempt, exempt_terms):
            by_kind.setdefault(kind, []).append(f"{path}:{number}: {message}")
            total += 1

    for kind in sorted(by_kind):
        print(f"\n  [{kind}] {len(by_kind[kind])}")
        for line in by_kind[kind]:
            print(f"    {line}")
    print(f"\n  TOTAL: {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
