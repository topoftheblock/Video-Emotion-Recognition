package pipeline;

import org.apache.uima.analysis_engine.AnalysisEngineProcessException;
import org.apache.uima.cas.CASException;
import org.apache.uima.fit.component.JCasAnnotator_ImplBase;
import org.apache.uima.fit.descriptor.ConfigurationParameter;
import org.apache.uima.fit.util.JCasUtil;
import org.apache.uima.jcas.JCas;

import de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence;
import org.texttechnologylab.annotation.type.AudioSentence;
import org.texttechnologylab.annotation.type.AudioToken;

import java.util.List;
import java.util.stream.Collectors;



// Lokale UIMA Analysis Engine (eingebunden über den DUUIUIMADriver).
//
// AudioSentence (org.texttechnologylab.annotation.type) erbt über MultimediaElement
// von uima.tcas.Annotation, hat also begin/end UND timeStart/timeEnd.
//
// Der DUUIUIMADriver.Component-Builder exponiert keinen View-Setter,
// daher wird die Transkript-View hier explizit über jcas.getView(...) geholt.

/**
 * DUUI-Komponente: erzeugt pro spaCy-Satz ein AudioSentence mit Zeitfenster
 * aus den abgedeckten AudioToken. Verbindet Text und Zeit
 */
public class AudioSentenceAnnotator extends JCasAnnotator_ImplBase {

    public static final String PARAM_VIEW = "viewName";

    // View, in der Transkript-Text, AudioToken und Sentence liegen.
    @ConfigurationParameter(name = PARAM_VIEW, mandatory = false, defaultValue = "transcript")
    private String viewName;

    private int docCounter = 0;

    @Override
    public void process(JCas jcas) throws AnalysisEngineProcessException {
        docCounter++;


        JCas view;
        try {
            view = jcas.getView(viewName);
        } catch (CASException e) {
            System.out.println("  AudioSentence: View '" + viewName + "' fehlt, übersprungen.");
            return;
        }

        int created = 0;
        int skipped = 0;

        for (Sentence s : JCasUtil.select(view, Sentence.class)) {
            // alle Wort-Tokens, die in diesem Satz liegen
            List<AudioToken> covered = JCasUtil.selectCovered(AudioToken.class, s);

            // nicht-alignte Wörter (Zahlen, Währungen, ...) haben kein Timing: ??
            // timeEnd bleibt auf dem Float-Default 0.0, erstmal rausfiltern
            List<AudioToken> timed = covered.stream()
                    .filter(t -> t.getTimeEnd() > 0f)
                    .collect(Collectors.toList());

            if (timed.isEmpty()) {
                // Satz ohne nutzbares Timing -> kein AudioSentence
                skipped++;
                continue;
            }

            // Tokens kommen in begin-Reihenfolge -> erstes = frühester Start, letztes = spätestes Ende.
            // min/max zur Sicherheit, falls einzelne Tokens leicht aus der Reihe fallen.
            float start = (float) timed.stream().mapToDouble(AudioToken::getTimeStart).min().orElse(0d);
            float end   = (float) timed.stream().mapToDouble(AudioToken::getTimeEnd).max().orElse(0d);

            // AudioSentence im selben View anlegen: begin/end vom Satz, Zeit von den Tokens
            AudioSentence as = new AudioSentence(view, s.getBegin(), s.getEnd());
            as.setTimeStart(start);
            as.setTimeEnd(end);
            as.addToIndexes();
            created++;
        }

        System.out.println("  [" + docCounter + "] AudioSentence erzeugt: " + created
                + (skipped > 0 ? " (ohne Timing übersprungen: " + skipped + ")" : ""));
    }
}