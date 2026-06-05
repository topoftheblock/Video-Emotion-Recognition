package MultimodalRedenPortal.nlp;

import de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence;
import org.apache.uima.UIMAException;
import org.apache.uima.fit.util.JCasUtil;
import org.apache.uima.jcas.JCas;
import org.texttechnologylab.DockerUnifiedUIMAInterface.DUUIComposer;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIDockerDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIRemoteDriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.driver.DUUIUIMADriver;
import org.texttechnologylab.DockerUnifiedUIMAInterface.lua.DUUILuaContext;
import org.xml.sax.SAXException;

import java.io.IOException;
import java.net.URISyntaxException;
import java.util.List;

/**
 * Pipeline for processing video files -> transcript -> spacy-processed transcript
 *
 * Components:
 * - WhisperX: Video transcription with word-level timestamps
 * - spaCy: Tokenization, POS, NER, dependcies, ...
 *
 * Views:
 * - Input: video (contains video data , format ?)
 * - Output: transcript (text, spacy annots)
 *
 * @author Max Froese
 */
public class VideoPipeline implements DUUIPipeline {

    private final DUUIComposer composer;
    private final int workers;

    /**
     * Creates a new video processing pipeline.
     *
     * @param workers Number of worker threads for parallel processing
     * @throws Exception if initialization fails
     */
    public VideoPipeline(int workers) throws Exception {
        this.workers = workers;
        this.composer = initComposer();
        buildPipeline();    //maybe build in process() and reset right after one pipeline run
    }

    /**
     * Initializes the DUUI composer with all necessary drivers. (probably whipser lokal, spacy remote)
     */
    private DUUIComposer initComposer() throws UIMAException, IOException, SAXException, URISyntaxException {
        DUUILuaContext ctx = new DUUILuaContext().withJsonLibrary();
        DUUIComposer composer = new DUUIComposer()
                .withSkipVerification(true)
                .withLuaContext(ctx)
                .withWorkers(workers);

        composer.addDriver(new DUUIUIMADriver(), new DUUIRemoteDriver(), new DUUIDockerDriver());//evtl only remote
        return composer;
    }

    /**
     * Builds the video processing pipeline with WhisperX and spaCy.
     */
    private void buildPipeline() throws Exception {
        // WhisperX: Transcribes video and creates transcript view
        composer.add(new DUUIRemoteDriver.Component("http://whisperx.service.component.duui.texttechnologylab.org")
                .withScale(workers)
                .withSourceView("video")
                .withTargetView("transcript")
                .withParameter("language", "de")
                .build());


        // spaCy: Analyzes the transcript text
        composer.add(new DUUIRemoteDriver.Component("http://spacy.service.component.duui.texttechnologylab.org")
                .withScale(workers)
                .withSourceView("transcript")
                .withTargetView("transcript")
                .withParameter("language", "de")
                .build());
    }



    /**
     * Processes the CAS through the already built pipeline
     * (No return of the CAS.)
     *
     * @throws Exception if an error occurs during the pipeline run
     */
    @Override
    public void process(JCas jCas) throws Exception {
        //buildPipeline();
        composer.run(jCas);
        //composer.resetPipeline();
    }

    /**
     * The name of the view that this pipeline produces (format text).
     * (no specs for the format though)
     *
     * @return list containing the only required view name : "video"
     */
    @Override
    public List<String> getRequiredViews() {
        return List.of("video");  //
    }

    /**
     * The name of the view that this pipeline produces (format text).
     *
     * @return a list containing the single produced view name: "transcript"
     */
    @Override
    public List<String> getProducedViews() {
        return List.of("transcript");  //
    }

    /**
     * Shuts down the composer with all drivers.
     *
     * @throws Exception if an error occurs during the shutdown process
     */
    @Override
    public void shutdown() throws Exception {
        composer.shutdown();
    }
}