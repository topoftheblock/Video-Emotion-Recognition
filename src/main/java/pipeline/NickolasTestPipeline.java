package pipeline;

import org.apache.uima.fit.factory.JCasFactory;
import org.apache.uima.jcas.JCas;
import org.apache.uima.util.CasCopier;
import org.dkpro.core.io.xmi.XmiWriter;
import org.texttechnologylab.DockerUnifiedUIMAInterface.DUUIComposer;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIDockerDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIRemoteDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIUIMADriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.io.reader.DUUIMultimodalCollectionReader;
import org.texttechnologylab.DockerUnifiedUIMAInterface.lua.DUUILuaContext;

import java.io.File;

import static org.apache.uima.fit.factory.AnalysisEngineFactory.createEngineDescription;

public class NickolasTestPipeline {

        private static final String EXTRACT_AUDIO_TO_VIEW = "duui_extract_audio";
        private static final String WHISPERX = "http://whisperx.service.component.duui.texttechnologylab.org/";
        private static final String SPACY = "docker.texttechnologylab.org/textimager-duui-spacy-single-de_core_news_sm:0.1.4";
        private static final String EMOTION = "docker.texttechnologylab.org/duui-transformers-emotion-german-emotions:latest";
        private static final String AUDIO_EMOTION = "whisper-emotion-app:latest";

        private static final String VIDEO_VIEW = "_InitialView";
        private static final String AUDIO_VIEW = "audioView";
        private static final String TRANSCRIPT_VIEW = "transcriptView";

        public static void main(String[] args) throws Exception {
                String videoDir = args.length > 0 ? args[0] : "src/main/resources/videos";
                String outDir = args.length > 1 ? args[1] : "output/xmi";
                new File(outDir).mkdirs();

                DUUILuaContext ctx = new DUUILuaContext().withJsonLibrary();
                DUUIComposer composer = new DUUIComposer()
                                .withSkipVerification(true)
                                .withLuaContext(ctx)
                                .withWorkers(1);

                composer.addDriver(new DUUIDockerDriver(), new DUUIRemoteDriver(),
                                new DUUIUIMADriver().withDebug(true));

                composer.add(new DUUIDockerDriver.Component(EXTRACT_AUDIO_TO_VIEW)
                        .withView(VIDEO_VIEW)
                        .withTargetView(AUDIO_VIEW)
                        .withParameter("input_format", "mp4")
                        .withParameter("output_format", "wav"));

                // 1) WhisperX: Video (_InitialView) -> Transkript + AudioToken (transcript)
//                composer.add(new DUUIRemoteDriver.Component(WHISPERX)
//                                .withParameter("language", "de")
//                                .withSourceView(VIDEO_VIEW)
//                                .withTargetView(TRANSCRIPT_VIEW));

                // 2) spaCy: Sentence/Token auf transcript
//                composer.add(new DUUIDockerDriver.Component(SPACY)
//                                .withParameter("language", "de")
//                                .withView(TRANSCRIPT_VIEW));

                // 3) AudioSentence: Zeitfenster pro Satz aus AudioToken
//                composer.add(new DUUIUIMADriver.Component(
//                                createEngineDescription(AudioSentenceAnnotator.class,
//                                                AudioSentenceAnnotator.PARAM_VIEW, TRANSCRIPT_VIEW)));

                // 4) German-Emotions: Emotion pro Satz auf transcript
//                composer.add(new DUUIDockerDriver.Component(EMOTION)
//                                .withParameter("selection",
//                                                "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence")
//                                .withView(TRANSCRIPT_VIEW));

                // 5) pipeline.EmotionSentenceMapper: DUUI-Emotion -> eigenes Schema, mit
                // AudioSentence verknüpfen
//                composer.add(new DUUIUIMADriver.Component(
//                                createEngineDescription(EmotionSentenceMapper.class,
//                                                EmotionSentenceMapper.PARAM_VIEW, TRANSCRIPT_VIEW)));

                // 6) Audio-Emotions (Whisper SER): Emotion aus Audio
//                composer.add(new DUUIDockerDriver.Component(AUDIO_EMOTION)
//                                .withParameter("selection", "org.texttechnologylab.annotation.type.MultimediaElement")
//                                .withView(VIDEO_VIEW));

                // 7) Video-Segmente mit eingebranntem Untertitel schreiben (braucht
                // _InitialView + AudioSentence)
//                composer.add(new DUUIUIMADriver.Component(
//                                createEngineDescription(VideoSubtitleSegmentWriter.class,
//                                                VideoSubtitleSegmentWriter.PARAM_OUTPUT_DIR, "output/clips",
//                                                VideoSubtitleSegmentWriter.PARAM_VIEW, TRANSCRIPT_VIEW,
//                                                VideoSubtitleSegmentWriter.PARAM_VIDEO_VIEW, VIDEO_VIEW)));

                // 7) XMI-Writer: ganzes CAS inkl. aller Views
                composer.add(new DUUIUIMADriver.Component(
                        createEngineDescription(XmiWriter.class,
                                XmiWriter.PARAM_TARGET_LOCATION, outDir,
                                XmiWriter.PARAM_PRETTY_PRINT, true,
                                XmiWriter.PARAM_OVERWRITE, true)));

                // Reader: erstes Video laden, ein CAS bauen, einmal durch die Pipeline
                DUUIMultimodalCollectionReader reader = new DUUIMultimodalCollectionReader(videoDir, "mp4", VIDEO_VIEW);

//                DUUIAsynchronousProcessor ap = new DUUIAsynchronousProcessor(reader);
//
//                composer.run(ap, "dd");

                if (reader.hasNext()) {
                        JCas jcas = JCasFactory.createJCas();
                        reader.getNextCas(jcas);
                        composer.run(jcas, "video-pipeline");
                } else {
                        System.out.println("Kein Video gefunden in: " + videoDir);
                }
                composer.shutdown();
        }
}