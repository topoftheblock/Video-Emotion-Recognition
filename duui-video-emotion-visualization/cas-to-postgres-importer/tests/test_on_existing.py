"""
Tests for `--on-existing` argument handling and the pre-parse filename
read it depends on.

The point of `skip` is that it costs nothing: the decision is made from
the raw XML, before the CAS is loaded. So the read has to work on a
tree, follow the same precedence as parsers/video.py, and the flag has
to be parsed without argparse swallowing the positional paths.
"""

import base64

import pytest
from lxml import etree

from importer import media
from importer.__main__ import _split_args
from importer.config import ON_EXISTING_CHOICES


def _document(*, multimedia=None, document_title=None):
    parts = []
    if multimedia is not None:
        parts.append(
            f'<type2:MultimediaElement xmi:id="4" filename="{multimedia}"/>'
        )
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
        f'{"".join(parts)}'
        '<cas:Sofa xmi:id="1" sofaID="_InitialView" mimeType="video/mp4" '
        f'sofaString="{base64.b64encode(b"video bytes").decode("ascii")}"/>'
        "</xmi:XMI>".encode("utf-8")
    ).getroottree()


def test_filename_comes_from_multimedia_element_first():
    tree = _document(multimedia="teil_000.mp4", document_title="something else.mp4")

    assert media.read_video_filename(tree) == "teil_000.mp4"


def test_filename_falls_back_to_document_metadata():
    # The shape every file in the Bundestag corpus actually has: no
    # MultimediaElement at all.
    tree = _document(document_title="teil_000.mp4")

    assert media.read_video_filename(tree) == "teil_000.mp4"


def test_no_identifying_annotation_reads_as_unknown():
    # None, not a guess: run() then leaves the decision to the video
    # parser reading the loaded CAS.
    assert media.read_video_filename(_document()) is None


def test_reading_the_filename_does_not_disturb_the_media_sofa():
    tree = _document(document_title="teil_000.mp4")

    media.read_video_filename(tree)

    payload = media.select_video_sofa(media.find_media_sofas(tree))
    assert payload.data() == b"video bytes"


@pytest.mark.parametrize("argv,expected", [
    (["cas/"], (["cas/"], None)),
    (["cas/", "--on-existing", "replace"], (["cas/"], "replace")),
    (["--on-existing=skip", "a.xmi", "b.xmi"], (["a.xmi", "b.xmi"], "skip")),
    ([], ([], None)),
])
def test_split_args(argv, expected):
    assert _split_args(argv) == expected


def test_an_unknown_mode_is_refused_before_any_work():
    with pytest.raises(SystemExit) as excinfo:
        _split_args(["--on-existing", "merge"])
    assert "skip" in str(excinfo.value)


def test_a_missing_mode_is_refused():
    with pytest.raises(SystemExit):
        _split_args(["--on-existing"])


def test_the_documented_modes_are_the_supported_ones():
    assert ON_EXISTING_CHOICES == ("skip", "replace")
