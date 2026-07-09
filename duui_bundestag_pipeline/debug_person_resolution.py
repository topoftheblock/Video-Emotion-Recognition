#!/usr/bin/env python3
"""
Debugging tool: reports how identity:Person / FaceIdentity / VoiceIdentity
would resolve for a given CAS, WITHOUT writing anything to the database.

Use this when person_id ends up NULL across the board after a real
import and you need to know why -- e.g. whether the CAS has any
identity:Person annotations at all, whether FaceIdentity/VoiceIdentity
labels actually match up, and which face/voice tracks would end up
orphaned (no person_id) if you ran the real pipeline right now.

Usage:
    python debug_person_resolution.py [path/to/file.xmi]
"""

import sys
from collections import Counter

from cassis import load_cas_from_xmi

from duui_parser.cas_views import select_across_views
from duui_parser.config import TYPES, XMI_FILE
from duui_parser.identity_resolution import (
    parse_person_label,
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from duui_parser.typesystem import get_xmi_id, load_merged_typesystem


def load_cas(xmi_file):
    print(f"Loading typesystem + CAS from {xmi_file} ...")
    merged_typesystem = load_merged_typesystem()
    with open(xmi_file, "rb") as f:
        return load_cas_from_xmi(f, typesystem=merged_typesystem, lenient=True, trusted=True)


def build_person_maps(cas):
    """Mirrors parsers/person.py exactly, but only builds the lookup
    maps -- no DB writes -- so this reflects what the real import
    would produce."""
    face_id_to_person_id = {}
    voice_id_to_person_id = {}
    persons = []

    for person in select_across_views(cas, TYPES["person"]):
        person_id = get_xmi_id(person)
        label = getattr(person, "label", None)
        label_parts = parse_person_label(label)
        clip_label = getattr(person, "clip_label", getattr(person, "personId", label))

        persons.append(
            {
                "person_id": person_id,
                "label": label,
                "clip_label": clip_label,
                "label_parts": label_parts,
            }
        )

        if "face" in label_parts:
            face_id_to_person_id[label_parts["face"]] = person_id
        if "voice" in label_parts:
            voice_id_to_person_id[label_parts["voice"]] = person_id

    return persons, face_id_to_person_id, voice_id_to_person_id


def report_persons(persons):
    print(f"\n=== identity:Person ({len(persons)} found) ===")
    if not persons:
        print("  NONE. No identity:Person annotations exist in this CAS at all --")
        print("  every face_id_to_person_id / voice_id_to_person_id lookup below")
        print("  will therefore be empty, and every person_id downstream will be NULL,")
        print("  regardless of how many FaceIdentity/VoiceIdentity records exist.")
        return
    for p in persons[:20]:
        print(f"  person_id={p['person_id']} clip_label={p['clip_label']!r} label={p['label']!r} parsed={p['label_parts']}")
    if len(persons) > 20:
        print(f"  ... and {len(persons) - 20} more")


def report_face_identities(cas, context):
    resolved, unresolved = 0, 0
    unresolved_face_ids = Counter()
    total = 0
    for face_identity in select_across_views(cas, TYPES["face_identity"]):
        total += 1
        face_id = getattr(face_identity, "faceId", None)
        person_id = resolve_person_id_via_face_fs(face_identity, context)
        if person_id is not None:
            resolved += 1
        else:
            unresolved += 1
            unresolved_face_ids[face_id] += 1

    print(f"\n=== identity:FaceIdentity ({total} found) ===")
    print(f"  resolved to a person_id: {resolved}")
    print(f"  UNRESOLVED (would be inserted with person_id=NULL): {unresolved}")
    if unresolved_face_ids:
        print("  unresolved faceId values (count):")
        for face_id, count in unresolved_face_ids.most_common(20):
            print(f"    {face_id!r}: {count}")


def report_voice_identities(cas, context):
    resolved, unresolved = 0, 0
    unresolved_voice_ids = Counter()
    total = 0
    for voice_identity in select_across_views(cas, TYPES["voice_identity"]):
        total += 1
        voice_id = getattr(voice_identity, "voiceId", None)
        person_id = resolve_person_id_via_voice_fs(voice_identity, context)
        if person_id is not None:
            resolved += 1
        else:
            unresolved += 1
            unresolved_voice_ids[voice_id] += 1

    print(f"\n=== identity:VoiceIdentity ({total} found) ===")
    print(f"  resolved to a person_id: {resolved}")
    print(f"  UNRESOLVED (would be inserted with person_id=NULL): {unresolved}")
    if unresolved_voice_ids:
        print("  unresolved voiceId values (count):")
        for voice_id, count in unresolved_voice_ids.most_common(20):
            print(f"    {voice_id!r}: {count}")


def report_embeddings_without_link(cas):
    """Embeddings feature structures don't carry faceId/voiceId
    themselves -- only the parent FaceIdentity/VoiceIdentity does --
    so if identity resolution fails, that string is gone the moment
    parsing finishes (face_embeddings/voice_embeddings have no column
    for it). Surface that here so it's not a silent trap."""
    embedding_total = sum(1 for _ in select_across_views(cas, TYPES["embedding"]))
    print(f"\n=== org.texttechnologylab.uima.type.Embedding ({embedding_total} found) ===")
    print("  Note: embedding_id/vector is preserved regardless of identity resolution,")
    print("  but the faceId/voiceId string itself is NOT stored on the embedding row --")
    print("  it only survives if linked to a person_id via the resolution above.")


def main(xmi_file=None):
    xmi_file = xmi_file or XMI_FILE
    cas = load_cas(xmi_file)

    persons, face_id_to_person_id, voice_id_to_person_id = build_person_maps(cas)
    context = {
        "face_id_to_person_id": face_id_to_person_id,
        "voice_id_to_person_id": voice_id_to_person_id,
    }

    report_persons(persons)
    report_face_identities(cas, context)
    report_voice_identities(cas, context)
    report_embeddings_without_link(cas)

    print("\nDone.")


if __name__ == "__main__":
    xmi_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(xmi_path)
