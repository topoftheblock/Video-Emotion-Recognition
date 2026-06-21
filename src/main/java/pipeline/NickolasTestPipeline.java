package pipeline;

import org.dkpro.core.io.xmi.XmiWriter;
import org.texttechnologylab.DockerUnifiedUIMAInterface.DUUIComposer;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIDockerDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIRemoteDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIUIMADriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.io.DUUIAsynchronousProcessor;
import org.texttechnologylab.DockerUnifiedUIMAInterface.io.reader.DUUIMultimodalCollectionReader;
import org.texttechnologylab.DockerUnifiedUIMAInterface.lua.DUUILuaContext;

import java.io.File;

import static org.apache.uima.fit.factory.AnalysisEngineFactory.createEngineDescription;

/**
 * DUUI pipeline that extracts the audio track from video files and writes the
 * result to XMI.
 *
 * <p>The pipeline reads {@code .mp4} videos from a directory, runs each through
 * the {@code duui_extract_audio_to_view} component (which extracts the audio
 * into a separate CAS view), and serializes the resulting CAS - including both
 * the original video view and the new audio view - to XMI files.</p>
 *
 * <p>Pipeline stages:</p>
 * <ol>
 *   <li>{@link DUUIMultimodalCollectionReader} loads each video into the
 *       {@code _InitialView} Sofa of a CAS.</li>
 *   <li>The {@code duui_extract_audio_to_view} Docker component reads that view,
 *       extracts the audio, and writes it into the {@code audioView}.</li>
 *   <li>{@link XmiWriter} serializes the full CAS to an XMI file.</li>
 * </ol>
 *
 * <p>Usage: {@code NickolasTestPipeline [videoDir] [outDir]}. Both arguments are
 * optional and fall back to defaults.</p>
 *
 * @author Maximilian Froesse, Nickolas Eickmann
 */
public class NickolasTestPipeline {

        /** Docker image name of the audio-extraction component. */
        private static final String EXTRACT_AUDIO_TO_VIEW = "duui_extract_audio_to_view:latest";
        private static final String WHISPERX = "docker.texttechnologylab.org/duui-whisperx:latest";


        /** Source view: the reader places each video's bytes in the initial view. */
        private static final String VIDEO_VIEW = "_InitialView";
        private static final String TRANSCRIPT_VIEW = "transcriptView";

        /** Target view: the extracted audio Sofa is written here. */
        private static final String AUDIO_VIEW = "audioView";

        public static void main(String[] args) throws Exception {
                // Input directory of videos and output directory for XMI files; both
                // optional CLI args with sensible defaults. The output dir is created
                // if it does not yet exist.
                String videoDir = args.length > 0 ? args[0] : "src/main/resources/videos";
                String outDir = args.length > 1 ? args[1] : "output/xmi";
                new File(outDir).mkdirs();

                // Lua context with the JSON library enabled - required because the
                // component's communication layer uses json.encode / json.decode.
                DUUILuaContext ctx = new DUUILuaContext().withJsonLibrary();

                // The composer orchestrates the pipeline.
                //   withSkipVerification(true) - skip the component self-check on startup
                //   withWorkers(1)             - process one CAS at a time
                DUUIComposer composer = new DUUIComposer()
                        .withSkipVerification(true)
                        .withLuaContext(ctx)
                        .withWorkers(1);

                // Register the drivers the pipeline uses. Each component below runs on
                // one of these:
                //   DUUIDockerDriver - runs components as local Docker containers
                //   DUUIRemoteDriver - talks to components exposed over HTTP (unused here)
                //   DUUIUIMADriver   - runs native UIMA analysis engines in-process
                composer.addDriver(new DUUIDockerDriver(), new DUUIRemoteDriver(),
                        new DUUIUIMADriver().withDebug(true));

                // Stage 1: audio extraction.
                // Reads the video from VIDEO_VIEW, writes the extracted audio into
                // AUDIO_VIEW, and requests MP3 output. The input format is auto-detected
                // by the component, so it is not specified here.
                composer.add(new DUUIDockerDriver.Component(EXTRACT_AUDIO_TO_VIEW)
                        .withSourceView(VIDEO_VIEW)
                        .withTargetView(AUDIO_VIEW)
                        .withParameter("output_format", "mp3"));

                composer.add(new DUUIDockerDriver.Component(WHISPERX)
                        .withParameter("language", "de")
                        .withSourceView(AUDIO_VIEW)
                        .withTargetView(TRANSCRIPT_VIEW));

                // Stage 2: write the full CAS (all views, including the new audio view)
                // to XMI. PRETTY_PRINT formats the XML; OVERWRITE allows re-runs to
                // replace existing files in the output directory.
                composer.add(new DUUIUIMADriver.Component(
                        createEngineDescription(XmiWriter.class,
                                XmiWriter.PARAM_TARGET_LOCATION, outDir,
                                XmiWriter.PARAM_PRETTY_PRINT, true,
                                XmiWriter.PARAM_OVERWRITE, true)));

                // Reader over all *.mp4 files in videoDir, loading each into VIDEO_VIEW.
                // Wrapped in an asynchronous processor so the composer pulls CASes from
                // it and drives them through the pipeline.
                DUUIMultimodalCollectionReader reader = new DUUIMultimodalCollectionReader(videoDir, "mp4", VIDEO_VIEW);
                DUUIAsynchronousProcessor ap = new DUUIAsynchronousProcessor(reader);

                // Execute the pipeline, then release resources (stops containers, etc.).
                composer.run(ap, "run");
                composer.shutdown();
        }
}