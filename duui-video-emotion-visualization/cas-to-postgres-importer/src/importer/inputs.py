"""Deciding which CAS files a run should import.

Turns whatever was passed on the command line — files, directories, or
nothing at all — into a concrete list of paths, and explains clearly
when that list comes out empty. Kept apart from `pipeline.py` because
deciding *what* to import is a separate question from importing it.
"""

import os
from pathlib import Path

from .config import INPUT_XMI_DIR, XMI_FILE


def default_input_paths() -> list[str]:
    """Return what to import when the command line names no path.

    The single file named by `DUUI_XMI_FILE` if that is set — the older
    one-CAS-at-a-time workflow — and otherwise the whole
    `DUUI_INPUT_XMI_DIR` directory.
    """
    return [XMI_FILE] if XMI_FILE else [INPUT_XMI_DIR]


def resolve_xmi_paths(paths: list[str] | list[Path]) -> list[Path]:
    """Expand files and directories into a sorted list of CAS files.

    A directory contributes every `*.xmi` directly inside it, and is
    deliberately not searched recursively: a CAS and its companion video
    live side by side in one flat drop directory, so recursing would
    only risk picking up unrelated exports.

    An explicitly named file is taken as-is even when it does not end in
    `.xmi`, since naming it is already an unambiguous instruction.

    Args:
        paths: File or directory paths, as strings or `Path` objects.

    Returns:
        The matching paths, de-duplicated by their resolved location.
    """
    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            resolved.extend(sorted(path.glob("*.xmi")))
        else:
            resolved.append(path)

    seen = set()
    unique = []
    for path in resolved:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def describe_missing_inputs(paths: list[str] | list[Path]) -> list[str]:
    """Explain, one line per path, why `resolve_xmi_paths` found none.

    `Path.glob` swallows OSError, so it reports an unreadable directory
    exactly the way it reports an empty one: by yielding nothing. That
    collapses three very different failures — a host path that does not
    exist, which Docker then mounts an empty directory over; a mount the
    container is not allowed to read; and a drop directory that
    genuinely holds no CAS — into one indistinguishable "no .xmi files"
    symptom.

    This re-walks the same paths with the errors left in, so the caller
    can name the actual cause instead of the symptom.

    Args:
        paths: The same paths that were handed to `resolve_xmi_paths`.

    Returns:
        One human-readable reason per path, in the order given.
    """
    reasons = []
    for raw in paths:
        path = Path(raw)

        if not path.exists():
            reasons.append(f"{path}: does not exist")
            continue

        if not path.is_dir():
            reasons.append(f"{path}: exists but is not a directory")
            continue

        try:
            entries = sorted(os.listdir(path))
        except OSError as exc:
            # Statable but not listable: a mount permission problem
            # rather than a missing-file one.
            reasons.append(
                f"{path}: directory exists but cannot be read "
                f"({exc.strerror}) — check the mount's permissions"
            )
            continue

        if not entries:
            reasons.append(
                f"{path}: directory is empty "
                "— check that the host path mounted here is the one you meant"
            )
            continue

        preview = ", ".join(entries[:5])
        if len(entries) > 5:
            preview += f", ... (+{len(entries) - 5} more)"
        reasons.append(
            f"{path}: holds {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}, "
            f"none named *.xmi ({preview})"
        )

    return reasons
