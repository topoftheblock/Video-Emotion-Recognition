"""Tests for `--on-existing` and the filename read it depends on.

The point of `skip` is that it costs nothing: the decision is made from
the raw XML, before the CAS is loaded. So the read has to work on a
tree, follow the same precedence as `parsers/video.py`, and the flag
has to parse without argparse swallowing the positional paths.
"""

import base64

import pytest
from lxml import etree
from lxml.etree import _ElementTree

from importer.__main__ import _split_args
from importer.cas import sofas
from importer.config import ON_EXISTING_CHOICES


def _document(
    *, multimedia: str | None = None, document_title: str | None = None
) -> _ElementTree:
    """Build a minimal CAS tree carrying a video sofa.

    Args:
        multimedia: A filename for a MultimediaElement, if one is
            wanted.
        document_title: A title for a DocumentMetaData, if one is
            wanted.

    Returns:
        The parsed tree, ready for the functions under test.
    """
    parts = []
    if multimedia is not None:
        parts.append(f'<type2:MultimediaElement xmi:id="4" filename="{multimedia}"/>')
    if document_title is not None:
        parts.append(
            f'<type3:DocumentMetaData xmi:id="3" documentTitle="{document_title}"/>'
        )
    return etree.fromstring(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/XMI" '
        'xmlns:cas="http:///uima/cas.ecore" '
        'xmlns:type2="http:///org/texttechnologylab/annotation/type.ecore" '
        'xmlns:type3="http:///de/tudarmstadt/ukp/dkpro/core/api/metadata/type.ecore" '
        'xmi:version="2.0">'
        f"{''.join(parts)}"
        '<cas:Sofa xmi:id="1" sofaID="_InitialView" mimeType="video/mp4" '
        f'sofaString="{base64.b64encode(b"video bytes").decode("ascii")}"/>'
        "</xmi:XMI>".encode("utf-8")
    ).getroottree()


def test_filename_comes_from_multimedia_element_first() -> None:
    """MultimediaElement wins when both annotations carry a name."""
    tree = _document(multimedia="teil_000.mp4", document_title="something else.mp4")

    assert sofas.read_video_filename(tree) == "teil_000.mp4"


def test_filename_falls_back_to_document_metadata() -> None:
    """A CAS without MultimediaElement still yields a filename.

    This is the shape real exports have been observed to take.
    """
    tree = _document(document_title="teil_000.mp4")

    assert sofas.read_video_filename(tree) == "teil_000.mp4"


def test_no_identifying_annotation_reads_as_unknown() -> None:
    """With neither annotation, the read returns None, not a guess.

    `run` then leaves the decision to the video parser, which reads the
    loaded CAS.
    """
    assert sofas.read_video_filename(_document()) is None


def test_reading_the_filename_does_not_disturb_the_media_sofa() -> None:
    """The early read leaves the payload intact for the extraction."""
    tree = _document(document_title="teil_000.mp4")

    sofas.read_video_filename(tree)

    payload = sofas.select_video_sofa(sofas.find_media_sofas(tree))
    assert payload is not None
    assert payload.data() == b"video bytes"


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["cas/"], (["cas/"], None)),
        (["cas/", "--on-existing", "replace"], (["cas/"], "replace")),
        (["--on-existing=skip", "a.xmi", "b.xmi"], (["a.xmi", "b.xmi"], "skip")),
        ([], ([], None)),
    ],
)
def test_split_args(argv: list[str], expected: tuple) -> None:
    """Both forms of the flag parse, and paths are left alone."""
    assert _split_args(argv) == expected


def test_an_unknown_mode_is_refused_before_any_work() -> None:
    """An unknown mode exits, and the message says what is valid."""
    with pytest.raises(SystemExit) as excinfo:
        _split_args(["--on-existing", "merge"])
    assert "skip" in str(excinfo.value)


def test_a_missing_mode_is_refused() -> None:
    """The flag without a value exits, rather than defaulting."""
    with pytest.raises(SystemExit):
        _split_args(["--on-existing"])


def test_the_documented_modes_are_the_supported_ones() -> None:
    """The modes the docstrings name are the ones the code accepts."""
    assert ON_EXISTING_CHOICES == ("skip", "replace")
