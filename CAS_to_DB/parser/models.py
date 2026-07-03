from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    String,
    Text,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


# -------------------------------------------------------------------------
# Video
# -------------------------------------------------------------------------

class Video(Base):
    __tablename__ = "video"

    video_id = Column(BigInteger, primary_key=True)

    filename = Column(Text)
    duration = Column(Float)

    processed_at = Column(DateTime)

    fps = Column(Float)

    width = Column(Integer)
    height = Column(Integer)

    segments = relationship("Segment", back_populates="video")
    persons = relationship("Person", back_populates="video")


# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------

class Model(Base):
    __tablename__ = "model"

    model_id = Column(BigInteger, primary_key=True)

    name = Column(Text)
    version = Column(Text)
    source = Column(Text)


# -------------------------------------------------------------------------
# Persons
# -------------------------------------------------------------------------

class GlobalPerson(Base):
    __tablename__ = "global_person"

    global_person_id = Column(BigInteger, primary_key=True)

    real_name = Column(Text)


class Person(Base):
    __tablename__ = "person"

    person_id = Column(BigInteger, primary_key=True)

    video_id = Column(BigInteger, ForeignKey("video.video_id"))
    global_person_id = Column(
        BigInteger,
        ForeignKey("global_person.global_person_id"),
        nullable=True,
    )

    clip_label = Column(Text)
    match_score = Column(Float)

    video = relationship("Video", back_populates="persons")


# -------------------------------------------------------------------------
# Segments
# -------------------------------------------------------------------------

class Segment(Base):
    __tablename__ = "segment"

    segment_id = Column(BigInteger, primary_key=True)

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    kind = Column(Text)

    seg_index = Column(Integer)

    start_time = Column(Float)
    end_time = Column(Float)

    begin = Column(Integer)
    end = Column(Integer)

    person_id = Column(
        BigInteger,
        ForeignKey("person.person_id"),
        nullable=True,
    )

    video = relationship("Video", back_populates="segments")


# -------------------------------------------------------------------------
# Tokens
# -------------------------------------------------------------------------

class LinguisticToken(Base):
    __tablename__ = "linguistic_token"

    token_id = Column(BigInteger, primary_key=True)

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    segment_id = Column(BigInteger, ForeignKey("segment.segment_id"))

    start_time = Column(Float)
    end_time = Column(Float)

    begin = Column(Integer)
    end = Column(Integer)

    word = Column(Text)

    pos_tag = Column(Text)

    ner_label = Column(Text)


# -------------------------------------------------------------------------
# Embeddings
# -------------------------------------------------------------------------

class FaceEmbedding(Base):
    __tablename__ = "face_embedding"

    embedding_id = Column(BigInteger, primary_key=True)

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    model_id = Column(BigInteger, ForeignKey("model.model_id"))

    embedding = Column(Vector(512))


class VoiceEmbedding(Base):
    __tablename__ = "voice_embedding"

    embedding_id = Column(BigInteger, primary_key=True)

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    model_id = Column(BigInteger, ForeignKey("model.model_id"))

    embedding = Column(Vector(192))


# -------------------------------------------------------------------------
# Presence
# -------------------------------------------------------------------------

class Presence(Base):
    __tablename__ = "presence"

    presence_id = Column(BigInteger, primary_key=True)

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    modality = Column(Text)

    start_time = Column(Float)
    end_time = Column(Float)

    begin = Column(Integer)

    end = Column(Integer)


# -------------------------------------------------------------------------
# Face Detection
# -------------------------------------------------------------------------

class FaceDetection(Base):
    __tablename__ = "face_detection"

    detection_id = Column(BigInteger, primary_key=True)

    presence_id = Column(BigInteger, ForeignKey("presence.presence_id"))

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    frame_index = Column(Integer)

    t_time = Column(Float)

    x = Column(Float)
    y = Column(Float)
    w = Column(Float)
    h = Column(Float)

    detection_score = Column(Float)


# -------------------------------------------------------------------------
# Person Detection
# -------------------------------------------------------------------------

class PersonDetection(Base):
    __tablename__ = "person_detection"

    detection_id = Column(BigInteger, primary_key=True)

    presence_id = Column(BigInteger, ForeignKey("presence.presence_id"))

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    frame_index = Column(Integer)

    t_time = Column(Float)

    x = Column(Float)
    y = Column(Float)
    w = Column(Float)
    h = Column(Float)

    detection_score = Column(Float)


# -------------------------------------------------------------------------
# Emotions
# -------------------------------------------------------------------------

class BaseEmotion(Base):
    __tablename__ = "base_emotion"

    emotion_id = Column(BigInteger, primary_key=True)

    person_id = Column(BigInteger, ForeignKey("person.person_id"))

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    modality = Column(Text)

    granularity = Column(Text)

    start_time = Column(Float)
    end_time = Column(Float)

    begin = Column(Integer)
    end = Column(Integer)

    frame_index = Column(Integer)

    x = Column(Float)
    y = Column(Float)
    w = Column(Float)
    h = Column(Float)

    valence = Column(Float)
    arousal = Column(Float)
    dominance = Column(Float)

    dominant_label = Column(Text)


class EmotionScore(Base):
    __tablename__ = "emotion_score"

    emotion_id = Column(
        BigInteger,
        ForeignKey("base_emotion.emotion_id"),
        primary_key=True,
    )

    label = Column(Text, primary_key=True)

    score = Column(Float)


class FusedEmotion(Base):
    __tablename__ = "fused_emotion"

    fused_id = Column(BigInteger, primary_key=True)

    video_id = Column(BigInteger, ForeignKey("video.video_id"))

    person_id = Column(
        BigInteger,
        ForeignKey("person.person_id"),
        nullable=True,
    )

    fusion_method = Column(Text)

    target_modality = Column(Text)

    start_time = Column(Float)

    end_time = Column(Float)

    valence = Column(Float)

    arousal = Column(Float)

    dominant_label = Column(Text)


class EmotionFusionReference(Base):
    __tablename__ = "emotion_fusion_reference"

    fused_id = Column(
        BigInteger,
        ForeignKey("fused_emotion.fused_id"),
        primary_key=True,
    )

    source_emotion_id = Column(
        BigInteger,
        ForeignKey("base_emotion.emotion_id"),
        primary_key=True,
    )