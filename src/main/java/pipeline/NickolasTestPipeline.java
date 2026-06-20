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

public class NickolasTestPipeline {

        private static final String EXTRACT_AUDIO_TO_VIEW = "duui_extract_audio_to_view";

        private static final String VIDEO_VIEW = "_InitialView";
        private static final String AUDIO_VIEW = "audioView";

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
                        .withParameter("output_format", "mp3"));

                composer.add(new DUUIUIMADriver.Component(
                        createEngineDescription(XmiWriter.class,
                                XmiWriter.PARAM_TARGET_LOCATION, outDir,
                                XmiWriter.PARAM_PRETTY_PRINT, true,
                                XmiWriter.PARAM_OVERWRITE, true)));

                DUUIMultimodalCollectionReader reader = new DUUIMultimodalCollectionReader(videoDir, "mp4", VIDEO_VIEW);

                DUUIAsynchronousProcessor ap = new DUUIAsynchronousProcessor(reader);

                composer.run(ap, "run");

                composer.shutdown();
        }
}