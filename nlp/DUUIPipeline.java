package MultimodalRedenPortal.nlp;

import org.apache.uima.jcas.JCas;
import java.util.List;

/**
 * Interface for DUUI  pipelines.
 *
 * @author Max Froese
 */
public interface DUUIPipeline {

    /**
     * Processes a JCas through this pipeline
     *
     * @param jCas The JCas to process
     * @throws Exception if processing fails
     */
    void process(JCas jCas) throws Exception;

    /**
     * Returns the list of views that must exist before! this pipeline can run.
     *
     * @return List of required view names (e.g., "_InitialView", "video")
     */
    List<String> getRequiredViews();

    /**
     * Returns the list of views that this pipeline will create and fill
     *
     * @return List of produced view names (e.g., "transcript")
     */
    List<String> getProducedViews();

    /**
     * Shuts down the pipeline
     *
     * @throws Exception if shutdown fails
     */
    void shutdown() throws Exception;
}