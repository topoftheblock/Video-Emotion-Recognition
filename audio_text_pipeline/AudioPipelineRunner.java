package audio_text_pipeline;

import org.apache.uima.jcas.JCas;
import org.apache.uima.fit.factory.JCasFactory;

public class AudioPipelineRunner {

    public static void main(String[] args) {
        System.out.println("Starte Audio/Text Pipeline Initialisierung...");

        // 1. Instantiate the Connection
        DUUIAudioPipelineConnection pipeline = new DUUIAudioPipelineConnection();

        if (pipeline.isAvailable()) {
            try {
                // 2. Mock a JCas for testing (In production, use your DUUIReader or JCas provider)
                JCas jcas = JCasFactory.createJCas();

                // Create the AudioView and load some dummy Base64 audio into it
                JCas audioView = jcas.createView("AudioView");
                audioView.setSofaDataString("UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=", "audio/wav"); // Tiny empty wav base64

                System.out.println("JCas vorbereitet. Starte Verarbeitung...");

                // 3. Process the JCas through the DUUI containers
                pipeline.process(jcas);

                System.out.println("Verarbeitung abgeschlossen. Emotionen sind nun in der 'EmotionView' verfügbar.");

            } catch (Exception e) {
                System.err.println("Fehler während der Pipeline-Ausführung:");
                e.printStackTrace();
            }
        } else {
            System.out.println("Pipeline-Abbruch: Container/Composer nicht verfügbar.");
        }
    }
}