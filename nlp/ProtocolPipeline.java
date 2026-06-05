package MultimodalRedenPortal.nlp;

import de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence;
import org.apache.uima.UIMAException;
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
 * Pipeline for processing speech protocol texts (without video)
 *
 * Components:
 * - spaCy: Tokenization (including sentencization?), POS, NER, dependency, and more?
 * - GerVader: Sentiment analysis (sentence and full text level)
 * - ParlBert: Topic classification (sentence and full text level)
 *
 * Views:
 * - Input: _InitialView (speech full text)
 * - Output: Annotations in _InitialView
 *
 * @author Max Froese
 */
public class ProtocolPipeline implements DUUIPipeline {

    private final DUUIComposer composer;
    private final int workers;

    /**
     * Creates a new protocol pipeline.
     *
     * @param workers Number of worker threads for parallel processing
     * @throws Exception if initialization fails
     */
    public ProtocolPipeline(int workers) throws Exception {
        this.workers = workers;
        this.composer = initComposer();
        buildPipeline();    //maybe build in process() and reset right after one pipeline run
    }

    /**
     * Initializes the DUUI composer with all necessary drivers. (propably only remote right now)
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
     * Builds the NLP pipeline with spaCy, GerVader, and ParlBert.
     */
    private void buildPipeline() throws Exception {
        // spaCy for linguistic annotations (on default view)
        composer.add(new DUUIRemoteDriver.Component("http://spacy.service.component.duui.texttechnologylab.org")
                .withScale(workers)
                .build());

        // GerVader for sentiment analysis
        composer.add(new DUUIRemoteDriver.Component("http://gervader.service.component.duui.texttechnologylab.org")
                .withScale(workers)
                .withParameter("selection", Sentence.class.getName())
                .build());

        // ParlBert for topic modeling
        composer.add(new DUUIRemoteDriver.Component("http://parlbert.service.component.duui.texttechnologylab.org")
                .withScale(workers)
                .withParameter("selection", Sentence.class.getName())
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
     * @return list containing the only required view name : "_InitialView"
     */
    @Override
    public List<String> getRequiredViews() {
        return List.of("_InitialView");  //
    }

    /**
     * The name of the view that this pipeline produces (format text).
     *
     * @return a list containing the single produced view name: "_InitialView"
     */
    @Override
    public List<String> getProducedViews() {
        return List.of("_InitialView");  //
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