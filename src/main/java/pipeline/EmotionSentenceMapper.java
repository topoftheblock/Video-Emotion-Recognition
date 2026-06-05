package pipeline;

import org.apache.uima.analysis_engine.AnalysisEngineProcessException;
import org.apache.uima.cas.CASException;
import org.apache.uima.fit.component.JCasAnnotator_ImplBase;
import org.apache.uima.fit.descriptor.ConfigurationParameter;
import org.apache.uima.fit.util.JCasUtil;
import org.apache.uima.jcas.JCas;
import org.apache.uima.jcas.cas.FSArray;

import org.texttechnologylab.annotation.AnnotationComment;
import org.texttechnologylab.annotation.type.AudioSentence;
import org.texttechnologylab.annotation.emotion.Emotion;
import org.texttechnologylab.annotation.emotion.EmotionScore;

import java.util.List;

// Lokale UIMA-Komponente (DUUIUIMADriver).
//
// Aufgabe (Satz-Granularitaet, Modalitaet "text"):
// Die DUUI-German-Emotions-Komponente schreibt org.texttechnologylab.annotation.Emotion
// ueber Satz-Spannen (begin/end), mit der Verteilung als FSArray<AnnotationComment>
// (key = Label, value = Score als String) und einem setModel(MetaData).
//
// Diese Komponente ueberfuehrt das in das eigene, saubere Schema
// (org.texttechnologylab.annotation.emotion.Emotion):
//   - findet das deckungsgleiche AudioSentence (selectCovered ueber begin/end)
//   - kopiert die Scores in EmotionScore-FS, bestimmt dominant/dominantScore
//   - setzt begin/end (vom Satz) UND reference (aufs AudioSentence)
//   - uebernimmt die vorhandene MetaData via getModel() (kein Neuanlegen)
//   - setzt modality = "text"
//
// Annahme: DUUI-Emotion und AudioSentence liegen in derselben (Transkript-)View.

/**
 * Mappt die DUUI-Emotion-Ausgabe auf das eigene Emotion-Schema und verknüpft sie
 * mit dem zugehörigen AudioSentence.
 */
public class EmotionSentenceMapper extends JCasAnnotator_ImplBase {

    public static final String PARAM_VIEW = "viewName";
    @ConfigurationParameter(name = PARAM_VIEW, mandatory = false, defaultValue = "transcript")
    private String viewName;

    // voll qualifizierter Name des DUUI-Komponenten-Emotionstyps (Quelle)
    private static final String DUUI_EMOTION = "org.texttechnologylab.annotation.Emotion";

    @Override
    public void process(JCas jcas) throws AnalysisEngineProcessException {
        JCas view;
        try {
            view = jcas.getView(viewName);
        } catch (CASException e) {
            System.out.println("  pipeline.EmotionSentenceMapper: View '" + viewName + "' fehlt, übersprungen.");
            return;
        }

        // Quelltyp (DUUI-Emotion) generisch holen, um keine harte Klassenabhängigkeit
        // auf den DUUI-Typ zu brauchen.
        org.apache.uima.cas.Type duuiType = view.getTypeSystem().getType(DUUI_EMOTION);
        if (duuiType == null) {
            System.out.println("  pipeline.EmotionSentenceMapper: Typ " + DUUI_EMOTION + " nicht im Typesystem.");
            return;
        }

        // Feature-Handles am DUUI-Typ
        org.apache.uima.cas.Feature fEmotions = duuiType.getFeatureByBaseName("Emotions"); // FSArray<AnnotationComment>
        org.apache.uima.cas.Feature fModel    = duuiType.getFeatureByBaseName("model");    // MetaData

        int created = 0;
        for (org.apache.uima.cas.text.AnnotationFS src :
                org.apache.uima.fit.util.CasUtil.select(view.getCas(), duuiType)) {

            int begin = src.getBegin();
            int end = src.getEnd();

            // Ziel-Emotion im eigenen Schema
            Emotion emo = new Emotion(view, begin, end);
            emo.setModality("text");

            // MetaData uebernehmen (geteilte Instanz der DUUI-Komponente)
            if (fModel != null) {
                org.apache.uima.cas.FeatureStructure md = src.getFeatureValue(fModel);
                if (md instanceof org.texttechnologylab.annotation.model.MetaData) {
                    emo.setModel((org.texttechnologylab.annotation.model.MetaData) md);
                }
            }

            // Scores aus FSArray<AnnotationComment> uebernehmen
            String bestLabel = null;
            double bestScore = Double.NEGATIVE_INFINITY;

            org.apache.uima.cas.FeatureStructure arrFs =
                    (fEmotions != null) ? src.getFeatureValue(fEmotions) : null;

            if (arrFs instanceof FSArray) {
                FSArray arr = (FSArray) arrFs;
                FSArray out = new FSArray(view, arr.size());
                for (int i = 0; i < arr.size(); i++) {
                    org.apache.uima.cas.FeatureStructure fs = arr.get(i);
                    if (!(fs instanceof AnnotationComment)) continue;
                    AnnotationComment ac = (AnnotationComment) fs;
                    String label = ac.getKey();
                    double score = parseDouble(ac.getValue());

                    EmotionScore es = new EmotionScore(view);
                    es.setLabel(label);
                    es.setScore(score);
                    out.set(i, es);

                    if (score > bestScore) { bestScore = score; bestLabel = label; }
                }
                emo.setScores(out);
            }

            if (bestLabel != null) {
                emo.setDominant(bestLabel);
                emo.setDominantScore(bestScore);
            }

            // Verknuepfung mit dem deckungsgleichen AudioSentence (Standard: Covering)
            List<AudioSentence> covering = JCasUtil.selectCovering(view, AudioSentence.class, begin, end);
            AudioSentence as = covering.isEmpty() ? null : covering.get(0);
            if (as == null) {
                // exakte Deckung als Fallback (gleiche Spanne)
                for (AudioSentence cand : JCasUtil.selectAt(view, AudioSentence.class, begin, end)) {
                    as = cand; break;
                }
            }
            if (as != null) {
                emo.setReference(as);
                // Zeit gleich mit uebernehmen (Komfort fuer rein zeitbasierte Auswertung)
                emo.setTimeStart(as.getTimeStart());
                emo.setTimeEnd(as.getTimeEnd());
            }

            emo.addToIndexes();
            created++;
        }

        System.out.println("  pipeline.EmotionSentenceMapper: " + created + " Emotion(en) gemappt.");
    }

    private static double parseDouble(String s) {
        if (s == null) return 0d;
        try {
            return Double.parseDouble(s.trim());
        } catch (NumberFormatException e) {
            return 0d;
        }
    }
}
