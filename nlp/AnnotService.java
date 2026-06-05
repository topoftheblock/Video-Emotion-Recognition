package MultimodalRedenPortal.nlp;

import MultimodalRedenPortal.data.*;
import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport;
import com.google.gson.Gson;
import de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence;
import org.apache.uima.fit.factory.JCasFactory;
import org.apache.uima.fit.util.JCasUtil;
import org.apache.uima.jcas.JCas;
import org.apache.uima.util.CasCopier;
import org.bson.types.ObjectId;

import java.io.InputStream;
import java.util.Base64;

/**
 * Service for managing the Annotations.
 * The Pipelines can be run seperately, however for simplicity it is right now still necessary, that for a given speech
 * the ProtocolPipeline has been executed before the VideoPipeline
 * (so not really independent, but could be extended if necessary).
 *
 * Uses the CASMetadata interface (package data) to keep track of what was already done for one speech.
 * The CASSerializer is used, to store and load the serialiazed CAS from the db.
 * The CASToReportMapper is used to create/update and store a Report for the frontend out of a CAS.
 *
 * @author Max Froese
 */
public class AnnotService {

    private final ProtocolPipeline protocolPipeline;
    private final VideoPipeline videoPipeline;
    private final Factory factory;
    private final VideoService videoService;

    /**
     * Creates an AnnotService with both pipelines initialized.
     * Uses default of 1 worker for each pipeline.
     *
     * @param factory Factory for creating the necessary java objects.
     * @throws Exception if pipeline initialization fails
     */
    public AnnotService(Factory factory) throws Exception {
        this(factory, 1, 1);
    }

    /**
     * Creates an AnnotService with both pipelines initialized.
     *
     * @param factory Factory
     * @param protocolWorkers Number of workers for protocol pipeline
     * @param videoWorkers Number of workers for video pipeline
     * @throws Exception if pipeline initialization fails
     */
    public AnnotService(Factory factory, int protocolWorkers, int videoWorkers) throws Exception {
        this.factory = factory;
        this.videoService = factory.getVideoService();
        this.protocolPipeline = new ProtocolPipeline(protocolWorkers);
        this.videoPipeline = new VideoPipeline(videoWorkers);
    }

    // ========== Protocol Annotation =========

    /**
     * Annotates a speech protocol (text only, no video).
     * Steps:
     * 1. Check if already annotated
     * 2. Create JCas with speech text
     * 3. Run protocol pipeline (spaCy, GerVader, ParlBert: all remote)
     * 4. Serialize and store CAS + metadata in the corresponding speech document
     *
     * @param speech The speech to annotate
     * @throws Exception if processing fails
     */
    public void annotateProtocol(Speech speech) throws Exception {
        // 1. Check if already annotated
        CASMetadata metadata = speech.getCasMetadata();
        if (metadata != null && metadata.hasProtocolAnnotations()) {
            System.out.println("Protocol already annotated for speech: " + speech.getID());
            return;
        }

        System.out.println("Annotating protocol for speech: " + speech.getID());

        // 2. Create JCas with speech text
        JCas jCas = speech.toCas();

        // 3. Run protocol pipeline
        protocolPipeline.process(jCas);

        // 4a. Create CASMetadata object using factory and set info/metadata about the added annotdata
        CASMetadata newMetadata = factory.createCASMetadata();
        newMetadata.addView("_InitialView");
        newMetadata.markProtocolProcessed();

        // 4b.Serialize and store
        String serializedCas = CASSerializer.serializeToBase64(jCas);
        speech.setSerializedCas(serializedCas);
        speech.setCasMetadata(newMetadata);

        System.out.println("✓ Protocol annotation complete for speech: " + speech.getID());
    }

    // ========= Video Annotation ==========

    /**
     * Annotates a speech with video transcription. (video --> transcript annotated by spacy in the transcript view).
     * Still requires that protocol has been annotated first!
     * Steps:
     * 1. Load existing CAS (with protocol annotations) (some requirement checks before)
     * 2. Add video view from speech.getVideo()
     * 3. Run video pipeline (WhisperX + spaCy on transcript)
     * 4. copy transcript and initalview to a new CAS (so videodata is not in the serialized cas)
     * 5. Serialize and update CAS + metadata
     *
     * @param speech The speech to annotate (must have video)
     * @throws Exception if processing fails
     */
    public void annotateVideo(Speech speech) throws Exception {
        // 1a. Check if video already annotated
        CASMetadata metadata = speech.getCasMetadata();
        if (metadata != null && metadata.hasVideoAnnotations()) {
            System.out.println("Video already annotated for speech: " + speech.getID());
            return;
        }

        // 1b. Video annotation requires existing protocol annotations
        if (metadata == null || !metadata.hasProtocolAnnotations()) {
            throw new IllegalStateException(
                    "Cannot annotate video without protocol annotations. " +
                            "Call annotateProtocol() first for speech: " + speech.getID()
            );
        }

        // 1c. Check if speech has video
        if (!speech.hasVideo()) {
            throw new IllegalStateException(
                    "Speech has no video data: " + speech.getID()
            );
        }

        System.out.println("Annotating video for speech: " + speech.getID());

        // 1d. Load existing CAS (with protocol annotations)
        JCas jCas = speech.toCas();

        // 2. Add video view from speech (no transcript)
        addVideoView(jCas, speech);

        // 3. Run video pipeline (creates also transcript view)
        videoPipeline.process(jCas);

        // 4. copy transcript and initial view to new CAS
        JCas newjCas =createCleanCasWithoutVideo(jCas);

        // 5a. Update metadata (if null irrelevant right now, as protocol needs to be annotated first anyhow)
        if (metadata == null) {
            metadata = factory.createCASMetadata();
        }
        metadata.markVideoProcessed();

        // 5b. Serialize and update
        String serializedCas = CASSerializer.serializeToBase64(newjCas);
        speech.setSerializedCas(serializedCas);
        speech.setCasMetadata(metadata);

        System.out.println("✓ Video annotation complete for speech: " + speech.getID());
    }

    /**
     * Adds a video view to the CAS using the speech's video data.
     *
     * @param jCas The JCas to add the video to
     * @param speech The speech containing the video
     * @throws Exception if video loading fails
     */
    private void addVideoView(JCas jCas, Speech speech) throws Exception {
        if (!speech.hasVideo()) {
            throw new IllegalStateException("No video");
        }

        // Video von GridFS laden
        ObjectId videoId = speech.getVideoId();
        InputStream videoStream = videoService.downloadVideo(videoId);

        // Convert to Base64 (only for Pipeline)
        byte[] videoBytes = videoStream.readAllBytes();
        String base64 = Base64.getEncoder().encodeToString(videoBytes);

        JCas videoView;
        try {
            videoView = jCas.getView("video");
        } catch (org.apache.uima.cas.CASRuntimeException e) {
            videoView = jCas.createView("video");
        }

        videoView.setSofaDataString(base64, "video/mp4");
        videoView.setDocumentLanguage("de");

       //No transcript view creation, the pipeline handles that
    }

    // ========== Combined Annotation ==========

    /**
     * Annotates protocol and optionally video if available.
     *
     * @param speech The speech to annotate
     * @throws Exception if processing fails
     */
    public void annotate(Speech speech) throws Exception {
        // Always annotate protocol first
        annotateProtocol(speech);

        // If speech has video, annotate it
        if (speech.hasVideo()) {
            annotateVideo(speech);
        }
    }
    // ========== Report Methods ==========

    /**
     * Creates and stores analysis report (protocol only, no timestamps).
     * Is actually create or update and store.
     *
     * @param speech The speech for which the report gets made/updated
     */
    public void createAndStoreReport(Speech speech) throws Exception {
        CASMetadata metadata = speech.getCasMetadata();
        if (metadata == null || !metadata.hasProtocolAnnotations()) {
            throw new IllegalStateException("Protocol not annotated: " + speech.getID());
        }

        System.out.println("Creating report for: " + speech.getID());

        JCas jCas = speech.toCas();
        SpeechAnalysisReport report = CASToReportMapper.map(jCas);

        speech.setReport(report);

        System.out.println("✓ Report stored");
    }

    /**
     * Adds timestamps to existing report.
     *
     * @param speech The speech to which Report the timestamps get added
     */
    public void addTimestampsToReport(Speech speech) throws Exception {
        CASMetadata metadata = speech.getCasMetadata();
        if (metadata == null || !metadata.hasVideoAnnotations()) {
            throw new IllegalStateException("Video not annotated: " + speech.getID());
        }

        SpeechAnalysisReport report = speech.getReport();
        if (report == null) {
            throw new IllegalStateException("No report found: " + speech.getID());
        }

        System.out.println("Adding timestamps to: " + speech.getID());

        JCas jCas = speech.toCas();
        CASToReportMapper.addTimestamps(jCas, report);

        speech.setReport(report);

        System.out.println("✓ Timestamps added");
    }


    // ========== Utility Methods ==========

    /**
     * Checks if a speech needs protocol annotation.
     *
     * @param speech The speech to check
     * @return true if protocol annotation needed
     */
    public boolean needsProtocolAnnotation(Speech speech) {
        CASMetadata metadata = speech.getCasMetadata();
        return metadata == null || !metadata.hasProtocolAnnotations();
    }

    /**
     * Checks if a speech needs video annotation.
     *
     * @param speech The speech to check
     * @return true if video annotation needed
     */
    public boolean needsVideoAnnotation(Speech speech) {
        CASMetadata metadata = speech.getCasMetadata();
        return metadata == null || !metadata.hasVideoAnnotations();
    }

    /**
     * Returns metadata about what has been processed.
     *
     * @param speech The speech to check
     * @return CASMetadata or null
     */
    public CASMetadata getMetadata(Speech speech) {
        return speech.getCasMetadata();
    }

    /**
     * Checks if a speech has a specific view.
     *
     * @param speech The speech to check
     * @param viewName Name of the view (e.g., "transcript")
     * @return true if view exists
     */
    public boolean hasView(Speech speech, String viewName) {
        CASMetadata metadata = speech.getCasMetadata();
        return metadata != null && metadata.hasView(viewName);
    }

    /**
     * Only resets the Casmetadata, does not delete/reset the report or the serilized cas.
     * But so it is possible to run the AnnotPipelines again and the CAS gets overwritten.
     * Report is createorupdate anyhow.
     *
    * @param speech the speech to reset
    * @throws Exception if database update fails
    */
    public void resetAnnotations(Speech speech) throws Exception {
        System.out.println("Resetting the metadata annotations for speech: " + speech.getID());

        speech.setCasMetadata(factory.createCASMetadata());  // Leeres Metadata-Objekt

        System.out.println("✓ Annotations reset");
    }

    /**
     * Creates a new CAS containing only the _InitialView and transcript views from the old CAS.
     * The video view is excluded.
     *
     * @param  oldCas oldCAS with all views including video
     * @return a new CAS with only _InitialView and transcript
     * @throws Exception if CAS creation or copying fails
     */
    private JCas createCleanCasWithoutVideo(JCas oldCas) throws Exception {
        System.out.println("Creating new CAS without video data...");

        JCas newCas = JCasFactory.createJCas();
        CasCopier copier = new CasCopier(oldCas.getCas(), newCas.getCas());

        copier.copyCasView(oldCas.getView("_InitialView").getCas(), true);
        copier.copyCasView(oldCas.getView("transcript").getCas(), true);

        System.out.println("✓ Clean CAS created (video view excluded)");
        return newCas;
    }

    // ========== Shutdown ==========

    /**
     * Shuts down both pipelines.
     * (Both get initialized automatically with a AnnotService Instance)
     *
     * @throws Exception if shutdown fails
     */
    public void shutdown() throws Exception {
        System.out.println("Shutting down pipelines ...");

        protocolPipeline.shutdown();
        videoPipeline.shutdown();

        System.out.println("✓ Annotation service shut down successfully");
    }
}