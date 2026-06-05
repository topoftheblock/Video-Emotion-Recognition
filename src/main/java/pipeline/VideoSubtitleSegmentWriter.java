package pipeline;

import org.apache.uima.analysis_engine.AnalysisEngineProcessException;
import org.apache.uima.cas.CASException;
import org.apache.uima.fit.component.JCasAnnotator_ImplBase;
import org.apache.uima.fit.descriptor.ConfigurationParameter;
import org.apache.uima.fit.util.JCasUtil;
import org.apache.uima.jcas.JCas;

import de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData;
import org.texttechnologylab.annotation.type.AudioSentence;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Base64;

import org.apache.uima.UimaContext;
import org.apache.uima.resource.ResourceInitializationException;

import org.texttechnologylab.annotation.emotion.Emotion;
import java.util.List;


// Lokale UIMA Analysis Engine (eingebunden über den DUUIUIMADriver), Consumer/Writer.
//
// Zweck: pro AudioSentence einen Video-Schnipsel ausgeben, in den der zugehörige
// Untertitel (= der ganze Satztext) eingebrannt wird.
//   - Zeitfenster: AudioSentence.timeStart / timeEnd (Sekunden)
//   - Untertiteltext: AudioSentence.getCoveredText() (Satztext aus dem Transkript)
//   - Videoquelle: das base64-Video-Sofa aus der Video-View (_InitialView)
//
// Voraussetzung: FFmpeg muss lokal installiert / im PATH sein (läuft im JVM-Prozess).
// Pro Dokument wird das Video EINMAL dekodiert und dann je Satz geschnitten.

/**
 * DUUI Writer-Komponente: schreibt pro AudioSentence einen .mp4-Clip mit
 * eingebranntem Untertitel (ganzer Satz) in PARAM_OUTPUT_DIR.
 */
public class VideoSubtitleSegmentWriter extends JCasAnnotator_ImplBase {

    public static final String PARAM_OUTPUT_DIR = "outputDir";
    public static final String PARAM_VIEW = "viewName";          // AudioSentence + Text
    public static final String PARAM_VIDEO_VIEW = "videoViewName"; // base64-Video-Sofa
    public static final String PARAM_FFMPEG = "ffmpegPath";

    @ConfigurationParameter(name = PARAM_OUTPUT_DIR, mandatory = true)
    private String outputDir;

    @ConfigurationParameter(name = PARAM_VIEW, mandatory = false, defaultValue = "transcript")
    private String viewName;

    @ConfigurationParameter(name = PARAM_VIDEO_VIEW, mandatory = false, defaultValue = "_InitialView")
    private String videoViewName;

    @ConfigurationParameter(name = PARAM_FFMPEG, mandatory = false, defaultValue = "ffmpeg")
    private String ffmpegPath;

    private int docCounter = 0;

    @Override
    public void initialize(UimaContext ctx) throws ResourceInitializationException {
        super.initialize(ctx);
        String env = System.getenv("FFMPEG_BIN");       //mac, ubuntu : solte null sein   REMINDER
        if (env != null && !env.isBlank()) {
            ffmpegPath = env;   // überschreibt den Default "ffmpeg"
        }
    }

    @Override
    public void process(JCas jcas) throws AnalysisEngineProcessException {
        docCounter++;

        // Views holen: Text/AudioSentence einerseits, Video-Sofa andererseits
        JCas textView;
        JCas videoView;
        try {
            textView = jcas.getView(viewName);
            videoView = jcas.getView(videoViewName);
        } catch (CASException e) {
            System.out.println("  VideoSubtitle: View fehlt (" + viewName + "/" + videoViewName + "), übersprungen.");
            return;
        }

        File outDir = new File(outputDir);
        if (!outDir.exists()) outDir.mkdirs();
        String base = baseName(jcas);

        // Video-Sofa (base64) EINMAL pro Dokument in eine temporäre Datei dekodieren
        File videoFile;
        try {
            String b64 = videoView.getSofaDataString();
            if (b64 == null || b64.isEmpty()) {
                System.out.println("  VideoSubtitle: kein Video-Sofa in '" + videoViewName + "', übersprungen.");
                return;
            }
            videoFile = File.createTempFile("duui_video_", ".mp4");
            Files.write(videoFile.toPath(), Base64.getDecoder().decode(b64));
        } catch (IOException e) {
            throw new AnalysisEngineProcessException(e);
        }

        int idx = 0;
        int written = 0;
        try {
            for (AudioSentence as : JCasUtil.select(textView, AudioSentence.class)) {
                idx++;
                float start = as.getTimeStart();
                float end = as.getTimeEnd();
                String text = as.getCoveredText();

                if (end <= start || text == null || text.isBlank()) {
                    continue; // kein nutzbares Zeitfenster / kein Text
                }

                // Emotion-Label anhängen
                String label = dominantLabel(textView, as);
                String subtitleText = (label != null)
                        ? text + "  [" + label + "]"
                        : text;

                File out = new File(outDir, base + "_" + String.format("%03d", idx) + ".mp4");
                File srt = null;
                try {
                    srt = writeSrt(subtitleText, end - start);
                    runFfmpeg(videoFile, start, end - start, srt, out);
                    written++;
                } catch (Exception e) {
                    System.out.println("  VideoSubtitle: Segment " + idx + " fehlgeschlagen: " + e.getMessage());
                } finally {
                    if (srt != null) srt.delete();
                }
            }
        } finally {
            videoFile.delete();
        }

        System.out.println("  [" + docCounter + "] Video-Segmente geschrieben: " + written + " (" + base + ")");
    }

    // ---- Helfer --------------------------------------------------------------

    /** Dateiname-Basis aus DocumentId (falls vorhanden), sonst Zähler. */
    private String baseName(JCas jcas) {
        try {
            DocumentMetaData md = DocumentMetaData.get(jcas);
            if (md != null && md.getDocumentId() != null && !md.getDocumentId().isEmpty()) {
                String id = new File(md.getDocumentId()).getName(); // evtl. Pfad -> nur Dateiname
                int dot = id.lastIndexOf('.');
                if (dot > 0) id = id.substring(0, dot);            // Endung weg
                return id.replaceAll("[^a-zA-Z0-9_-]", "_");        // dateinamen-sicher
            }
        } catch (Exception ignore) {
            // keine Metadaten -> Fallback
        }
        return "video_" + docCounter;
    }

    /** Schreibt eine SRT-Datei mit genau einem Cue (0 -> Dauer) und dem Satztext. */
    private File writeSrt(String text, float durationSec) throws IOException {
        File srt = File.createTempFile("duui_sub_", ".srt");
        String body = "1\n"
                + "00:00:00,000 --> " + srtTime(durationSec) + "\n"
                + text.replace("\r", " ").replace("\n", " ").trim() + "\n";
        Files.write(srt.toPath(), body.getBytes(StandardCharsets.UTF_8));
        return srt;
    }

    /** Sekunden -> SRT-Zeitformat HH:MM:SS,mmm */
    private String srtTime(float sec) {
        int ms = Math.round(sec * 1000f);
        int h = ms / 3_600_000; ms %= 3_600_000;
        int m = ms / 60_000;    ms %= 60_000;
        int s = ms / 1_000;     ms %= 1_000;
        return String.format("%02d:%02d:%02d,%03d", h, m, s, ms);
    }

    private void runFfmpeg(File video, float start, float duration, File srt, File out)
            throws IOException, InterruptedException {

        ProcessBuilder pb = new ProcessBuilder(
                ffmpegPath, "-y",
                "-ss", String.valueOf(start),
                "-i", video.getAbsolutePath(),
                "-t", String.valueOf(duration),
                "-vf", "subtitles=" + srt.getName(),   // nur Dateiname, kein Pfad
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                out.getAbsolutePath());
        pb.directory(srt.getParentFile());             // Arbeitsverzeichnis = SRT-Ordner
        pb.redirectErrorStream(true);


        Process p = pb.start();
        StringBuilder log = new StringBuilder();
        try (BufferedReader r = new BufferedReader(
                new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                log.append(line).append('\n');
            }
        }
        int code = p.waitFor();
        if (code != 0) {
            // letzte ~15 Zeilen reichen meist
            String[] lines = log.toString().split("\n");
            int from = Math.max(0, lines.length - 15);
            StringBuilder tail = new StringBuilder();
            for (int i = from; i < lines.length; i++) tail.append(lines[i]).append('\n');
            throw new IOException("FFmpeg exit " + code + "\n" + tail);
        }
    }

    /** Dominantes Label der Emotion, die deckungsgleich zum Satz liegt (oder null). */
    private String dominantLabel(JCas view, AudioSentence as) {
        for (Emotion emo : JCasUtil.selectCovered(view, Emotion.class, as)) {
            if (emo.getBegin() == as.getBegin() && emo.getEnd() == as.getEnd()) {
                return emo.getDominant();
            }
        }
        // Fallback: irgendeine Emotion mit gleicher Spanne via selectAt
        for (Emotion emo : JCasUtil.selectAt(view, Emotion.class, as.getBegin(), as.getEnd())) {
            return emo.getDominant();
        }
        return null;
    }
}
