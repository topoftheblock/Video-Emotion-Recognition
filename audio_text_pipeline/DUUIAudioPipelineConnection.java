package audio_text_pipeline;

import org.apache.uima.jcas.JCas;
import org.texttechnologylab.DockerUnifiedUIMAInterface.DUUIComposer;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIDockerDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIUIMADriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.lua.DUUILuaContext;

/**
 * Kapselt die Verbindung zur DUUI-Pipeline für das Audio/Text und Emotion System.
 * Nutzt den Component-Builder Ansatz, um Skalierung und Views sauber zu konfigurieren.
 */
public class DUUIAudioPipelineConnection {

    private DUUIComposer composer;
    private boolean available = false;

    /**
     * Initialisiert die DUUI Pipeline:
     * - Lua Context (JSON)
     * - Drivers (UIMA + Docker)
     * - Komponenten: WhisperX, SpaCy, VoiceIdentity, AudioSentence, TextEmotion
     */
    public DUUIAudioPipelineConnection() {
        try {
            // Setup
            DUUILuaContext ctx = new DUUILuaContext().withJsonLibrary();

            composer = new DUUIComposer()
                    .withLuaContext(ctx)
                    .withSkipVerification(true)
                    .withWorkers(4);

            DUUIUIMADriver uimaDriver = new DUUIUIMADriver();

            // Using DockerDriver here assuming you run your own local containers.
            // Replace with DUUIRemoteDriver if they are hosted on a server.
            DUUIDockerDriver dockerDriver = new DUIDockerDriver();

            composer.addDriver(uimaDriver, dockerDriver);

            // A) WhisperX: Transcribes Audio -> Text
            composer.add(new DUIDockerDriver.Component("registry/whisperx:latest")
                    .withSourceView("AudioView")
                    .withTargetView("TextView")
                    .withScale(1) // GPU bound, usually scale 1 is safer
                    .build());

            // B) SpaCy: NLP Processing on Transcript
            composer.add(new DUIDockerDriver.Component("registry/spacy:latest")
                    .withSourceView("TextView")
                    .withTargetView("TextView")
                    .withScale(2) // CPU bound, can run parallel
                    .build());

            // C) Voice Identity (Speaker Segments)
            composer.add(new DUIDockerDriver.Component("registry/voice-identity:latest")
                    .withSourceView("AudioView")
                    .withTargetView("TextView") // Anchors segments to the Text View
                    .withScale(1)
                    .build());

            // D) Audio Sentence Engine (Merges SpaCy Sentences & Whisper Tokens)
            composer.add(new DUIDockerDriver.Component("registry/audio-sentence:latest")
                    .withSourceView("TextView")
                    .withTargetView("TextView")
                    .withScale(2)
                    .build());

            // E) Text Emotion Engine
            composer.add(new DUIDockerDriver.Component("registry/text-emotion:latest")
                    // Pass the AudioSentence class name so the Lua script knows what to iterate over
                    .withParameter("selection", "org.texttechnologylab.annotation.AudioSentence")
                    .withSourceView("TextView")
                    .withTargetView("EmotionView")
                    .withScale(2)
                    .build());

            available = true;
            System.out.println("DUUI Audio/Text Pipeline erfolgreich initialisiert.");

        } catch (Throwable e) {
            System.err.println("WARNUNG: DUUI Audio Pipeline konnte nicht initialisiert werden.");
            e.printStackTrace();
            available = false;
        }
    }

    public void process(JCas jcas) throws Exception {
        if (available && composer != null) {
            // Trigger processing. Ensure the initial JCas has the audio loaded in the 'AudioView'
            composer.run(jcas);
        } else {
            throw new IllegalStateException("DUUI Audio Pipeline ist nicht verfügbar.");
        }
    }

    public boolean isAvailable() {
        return available;
    }
}