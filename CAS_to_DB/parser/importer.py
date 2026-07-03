class Importer:
    def __init__(self, parser, db):

        self.parser = parser
        self.db = db

        # xmi:id -> DB id
        self.person_map = {}
        self.segment_map = {}
        self.presence_map = {}
        self.emotion_map = {}

    def run(self):

        self.import_video()

        self.import_models()

        self.import_persons()

        self.import_presence()

        self.import_segments()

        self.import_tokens()

        self.import_embeddings()

        self.import_emotions()

        self.import_emotion_scores()
    
    def import_persons(self):

    persons = self.parser.by_type["FaceIdentity"]

    for face in persons:

        person = Person(
            clip_label=face.attrib.get("label"),
            match_score=None
        )

        self.db.add(person)
        self.db.flush()

        xmi_id = face.attrib["{http://www.omg.org/XMI}id"]

        self.person_map[xmi_id] = person.person_id

    self.db.commit()

    def import_segments(self):

    sentences = self.parser.by_type["Sentence"]

    for index, sent in enumerate(sentences):

        segment = Segment(

            kind="sentence",

            seg_index=index,

            begin=int(sent.attrib["begin"]),
            end=int(sent.attrib["end"]),

            start_time=float(sent.attrib["timeStart"]),
            end_time=float(sent.attrib["timeEnd"])
        )

        self.db.add(segment)
        self.db.flush()

        self.segment_map[
            sent.attrib["{http://www.omg.org/XMI}id"]
        ] = segment.segment_id

    self.db.commit()

    def import_tokens(self):

    tokens = self.parser.by_type["Token"]

    for token in tokens:

        db_token = LinguisticToken(

            word=token.attrib.get("value"),

            begin=int(token.attrib["begin"]),
            end=int(token.attrib["end"]),

            start_time=float(token.attrib["timeStart"]),
            end_time=float(token.attrib["timeEnd"])
        )

        self.db.add(db_token)

    self.db.commit()
    def import_emotions(self):

    emotions = self.parser.by_type["Emotion"]

    for emotion in emotions:

        db_emotion = BaseEmotion(

            modality=emotion.attrib["modality"],

            granularity=emotion.attrib["granularity"],

            start_time=float(emotion.attrib["timeStart"]),
            end_time=float(emotion.attrib["timeEnd"]),

            valence=float(emotion.attrib["valence"]),
            arousal=float(emotion.attrib["arousal"]),
            dominance=float(emotion.attrib.get("dominance", 0.0))
        )

        self.db.add(db_emotion)
        self.db.flush()

        self.emotion_map[
            emotion.attrib["{http://www.omg.org/XMI}id"]
        ] = db_emotion.emotion_id

    self.db.commit()
    def import_emotion_scores(self):

    scores = self.parser.by_type["EmotionScore"]

    for score in scores:

        emotion_xmi = score.attrib["reference"]

        emotion_id = self.emotion_map[emotion_xmi]

        db_score = EmotionScore(

            emotion_id=emotion_id,

            label=score.attrib["label"],

            score=float(score.attrib["score"])
        )

        self.db.add(db_score)

    self.db.commit()