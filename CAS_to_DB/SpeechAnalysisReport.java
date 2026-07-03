package MultimodalRedenPortal.data.annotcontainer;

import java.util.*;

/**
 * DTO for frontend visualization of analyzed speech.
 * (Although not super perfect for that, but at least so we have type security concerning java).
 *
 * @author Max Froese
 */
public class SpeechAnalysisReport {

    // Global stats
    public NLPStatistics globalStats = new NLPStatistics();

    // All sentences with local stats
    public List<SentenceDetail> sentences = new ArrayList<>();


    /**
     * NLP stats structure used for both global and local statistics.
     */
    public static class NLPStatistics {
        public double sentiment;                                    // -1.0 to 1.0
        public Map<String, Integer> posDistribution = new HashMap<>();  // for bar chart
        public List<EntityStat> entityDistribution = new ArrayList<>(); // for bubble chart
        public List<TopicDTO> topTopics = new ArrayList<>();           // top 5 topics
    }

    /**
     * Named entity statistics grouped by type.
     */
    public static class EntityStat {
        public String label;                                // PER, LOC, ORG
        public int count;                                   // total count
        public Map<String, Integer> nameCounts = new HashMap<>();  // actual names

        public EntityStat(String label, int count) {
            this.label = label;
            this.count = count;
        }
    }

    /**
     * Topic with score.
     */
    public static class TopicDTO {
        public String topicName;
        public double score;

        public TopicDTO(String name, double s) {
            this.topicName = name;
            this.score = s;
        }
    }

    /**
     * Single sentence with text, positions, and local stats.
     */
    public static class SentenceDetail {
        public String text;
        public int begin;
        public int end;

        // Local stats
        public NLPStatistics localStats = new NLPStatistics();

        // Video timestamps in seconds
        public double startTime = -1.0;
        public double endTime = -1.0;

        // Entity texts for  highlighting
        public List<String> entityTexts = new ArrayList<>();
    }
}