package MultimodalRedenPortal.nlp;

import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport;
import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport.NLPStatistics;
import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport.EntityStat;
import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport.TopicDTO;
import MultimodalRedenPortal.data.annotcontainer.SpeechAnalysisReport.SentenceDetail;

import org.apache.uima.jcas.JCas;
import org.apache.uima.fit.util.JCasUtil;

import de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence;
import de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.pos.POS;
import de.tudarmstadt.ukp.dkpro.core.api.ner.type.NamedEntity;
import org.hucompute.textimager.uima.type.Sentiment;
import org.hucompute.textimager.uima.type.category.CategoryCoveredTagged;
import org.texttechnologylab.annotation.type.AudioToken;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Maps annotated CAS (Common Analysis Structure) to frontend-ready DTO (Data Transfer Object).

 * @author Max Froese
 */
public class CASToReportMapper {

    /**
     * Main mapping method: converts CAS to SpeechAnalysisReport without timestamps.
     *
     * @param jCas UIMA JCas containing NLP annotations
     * @return Complete SpeechAnalysisReport with global and local statistics
     */
    public static SpeechAnalysisReport map(JCas jCas) {
        SpeechAnalysisReport report = new SpeechAnalysisReport();

        // Extract sentences first (fills local stats)
        extractSentences(jCas, report);

        // Build global stats
        extractGlobalSentiment(jCas, report);
        extractGlobalTopics(jCas, report);
        aggregateGlobalPOS(report);
        extractGlobalEntities(jCas, report);

        return report;
    }

    /**
     * Extracts global sentiment (first one in CAS).
     * GerVader sentiment scores.
     *
     * @param jCas UIMA JCas containing sentiment annotations
     * @param report Report for Frontend
     */
    private static void extractGlobalSentiment(JCas jCas, SpeechAnalysisReport report) {
        report.globalStats.sentiment = JCasUtil.select(jCas, Sentiment.class).stream()
                .findFirst()
                .map(Sentiment::getSentiment)
                .orElse(0.0);
    }

    /**
     * Extracts global topics (first 5 in CAS):
     * Paralbert topics.
     *
     * @param jCas UIMA JCas containing topic annotations
     * @param report Report for Frontend
     */
    private static void extractGlobalTopics(JCas jCas, SpeechAnalysisReport report) {
        report.globalStats.topTopics = JCasUtil.select(jCas, CategoryCoveredTagged.class).stream()
                .limit(5)
                .map(c -> new TopicDTO(c.getValue(), c.getScore()))
                .collect(Collectors.toList());
    }

    /**
     * Aggregates global POS distribution from all sentence-level statistics.
     * Sums up POS tag counts across all sentences to get document-level distribution.
     *
     * @param report Report for Frontend
     */
    private static void aggregateGlobalPOS(SpeechAnalysisReport report) {
        for (SentenceDetail sentence : report.sentences) {
            sentence.localStats.posDistribution.forEach((tag, count) ->
                    report.globalStats.posDistribution.merge(tag, count, Integer::sum)
            );
        }
    }

    /**
     * Extracts global entity distribution from all named entities in the document.
     * Groups by type, counts apperance.
     * Results are sorted by frequency.
     * (Easier to extract directly for global stats, than to collect from all sentences)
     *
     * @param jCas UIMA JCas containing named entity annotations
     * @param report Report for Frontend
     */
    private static void extractGlobalEntities(JCas jCas, SpeechAnalysisReport report) {
        report.globalStats.entityDistribution = JCasUtil.select(jCas, NamedEntity.class).stream()
                .collect(Collectors.toMap(
                        NamedEntity::getValue,
                        ne -> {
                            EntityStat stat = new EntityStat(ne.getValue(), 1);
                            stat.nameCounts.put(ne.getCoveredText(), 1);
                            return stat;
                        },
                        (existing, replacement) -> {
                            existing.count++;
                            replacement.nameCounts.forEach((name, count) ->
                                    existing.nameCounts.merge(name, count, Integer::sum)
                            );
                            return existing;
                        }
                ))
                .values().stream()
                .sorted(Comparator.comparingInt((EntityStat e) -> e.count).reversed())
                .collect(Collectors.toList());
    }

    /**
     * Extracts all sentences with their local statistics.
     * For each sentence, extracts sentiment, POS distribution, entities, and topics.
     * Populates the report's sentence list with detailed per-sentence information.
     *
     * @param jCas UIMA JCas containing sentence annotations
     * @param report Report for Frontend
     */
    private static void extractSentences(JCas jCas, SpeechAnalysisReport report) {
        for (Sentence sentence : JCasUtil.select(jCas, Sentence.class)) {
            SentenceDetail detail = new SentenceDetail();

            detail.text = sentence.getCoveredText();
            detail.begin = sentence.getBegin();
            detail.end = sentence.getEnd();

            // Fill local stats for this sentence
            extractSentenceSentiment(jCas, sentence, detail);
            extractSentencePOS(jCas, sentence, detail);
            extractSentenceEntities(jCas, sentence, detail);
            extractSentenceTopics(jCas, sentence, detail);

            report.sentences.add(detail);
        }
    }

    /**
     * Extracts sentiment score for a single sentence.
     * Uses GerVader sentiment annotations covered by the sentence span.
     *
     * @param jCas UIMA JCas containing sentiment annotations
     * @param sentence Sentence annotation to analyze
     * @param detail Sentence detail
     */
    private static void extractSentenceSentiment(JCas jCas, Sentence sentence, SentenceDetail detail) {
        detail.localStats.sentiment = JCasUtil.selectCovered(jCas, Sentiment.class, sentence).stream()
                .mapToDouble(Sentiment::getSentiment)
                .findFirst()
                .orElse(0.0);
    }

    /**
     * Extracts POS (Part-of-Speech) tag distribution for a single sentence.
     * Counts occurrences of each POS tag, excluding punctuation tags (starting with $).
     * Uses spaCy POS annotations.
     *
     * @param jCas UIMA JCas containing POS annotations
     * @param sentence Sentence annotation to analyze
     * @param detail Sentence detail
     */
    private static void extractSentencePOS(JCas jCas, Sentence sentence, SentenceDetail detail) {
        for (POS pos : JCasUtil.selectCovered(jCas, POS.class, sentence)) {
            String tag = pos.getPosValue();
            // Ignore all punctuation tags (start with $)
            if (!tag.startsWith("$")) {
                detail.localStats.posDistribution.merge(tag, 1, Integer::sum);
            }
        }
    }

    /**
     * Extracts named entities for a single sentence.
     * Populates both entity texts (for highlighting) and entity distribution (grouped by type).
     * Groups entities by type and counts different surface forms.
     *
     * @param jCas UIMA JCas containing named entity annotations
     * @param sentence Sentence annotation to analyze
     * @param detail Sentence detail
     */
    private static void extractSentenceEntities(JCas jCas, Sentence sentence, SentenceDetail detail) {
        // Entity texts
        JCasUtil.selectCovered(jCas, NamedEntity.class, sentence).stream()
                .map(NamedEntity::getCoveredText)
                .forEach(detail.entityTexts::add);

        // Entity distribution (grouped by type)
        detail.localStats.entityDistribution = JCasUtil.selectCovered(jCas, NamedEntity.class, sentence).stream()
                .collect(Collectors.toMap(
                        NamedEntity::getValue,
                        ne -> {
                            EntityStat stat = new EntityStat(ne.getValue(), 1);
                            stat.nameCounts.put(ne.getCoveredText(), 1);
                            return stat;
                        },
                        (existing, replacement) -> {
                            existing.count++;
                            replacement.nameCounts.forEach((name, count) ->
                                    existing.nameCounts.merge(name, count, Integer::sum)
                            );
                            return existing;
                        }
                ))
                .values().stream()
                .sorted(Comparator.comparingInt((EntityStat e) -> e.count).reversed())
                .collect(Collectors.toList());
    }

    /**
     * Extracts topics for a single sentence.
     * Selects top 5 topics based on confidence scores from ParlBert.
     * Topics are sorted by score in descending order.
     *
     * @param jCas UIMA JCas containing topic annotations
     * @param sentence Sentence annotation to analyze
     * @param detail Sentence detail
     */
    private static void extractSentenceTopics(JCas jCas, Sentence sentence, SentenceDetail detail) {
        detail.localStats.topTopics = JCasUtil.selectCovered(jCas, CategoryCoveredTagged.class, sentence).stream()
                .sorted(Comparator.comparingDouble(CategoryCoveredTagged::getScore).reversed())
                .limit(5)
                .map(c -> new TopicDTO(c.getValue(), c.getScore()))
                .collect(Collectors.toList());
    }

    /**
     * Adds video timestamps from transcript view to sentence details.
     * Matches protocol sentences with transcript sentences (1:1 mapping).
     * Extracts timing information from AudioToken annotations created by WhisperX.
     * Uses timeStart from the first token and timeEnd from the last token in each sentence.
     * If no AudioTokens are found for a sentence, timestamps are set to -1.
     * (Results are okay, but sentence partitions output from spacy are pretty different in transcript and protocol)
     *
     * @param jCas UIMA JCas containing transcript view with AudioToken annotations
     * @param report Report whose sentences should be enriched with timestamp information
     */
    public static void addTimestamps(JCas jCas, SpeechAnalysisReport report) {
        try {
            JCas transcriptView = jCas.getView("transcript");
            List<Sentence> transcriptSentences = JCasUtil.select(transcriptView, Sentence.class).stream()
                    .collect(Collectors.toList());

            // 1:1 mapping between protocol and transcript sentences
            for (int i = 0; i < report.sentences.size() && i < transcriptSentences.size(); i++) {
                Sentence transcriptSentence = transcriptSentences.get(i);
                SentenceDetail detail = report.sentences.get(i);

                // Get all AudioTokens covered by this sentence
                List<AudioToken> audioTokens = JCasUtil.selectCovered(AudioToken.class, transcriptSentence)
                        .stream()
                        .sorted(Comparator.comparingInt(AudioToken::getBegin))
                        .collect(Collectors.toList());

                if (!audioTokens.isEmpty()) {
                    // Get timeStart from first token, timeEnd from last token
                    AudioToken firstToken = audioTokens.get(0);
                    AudioToken lastToken = audioTokens.get(audioTokens.size() - 1);

                    detail.startTime = firstToken.getTimeStart();
                    detail.endTime = lastToken.getTimeEnd();
                } else {
                    detail.startTime = -1;
                    detail.endTime = -1;
                }
            }
        } catch (Exception e) {
            System.err.println("Warning: Could not extract timestamps: " + e.getMessage());
            e.printStackTrace();
        }
    }
}