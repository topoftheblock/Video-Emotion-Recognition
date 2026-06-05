package MultimodalRedenPortal.nlp;

import org.apache.uima.cas.impl.XmiCasSerializer;
import org.apache.uima.cas.impl.XmiCasDeserializer;
import org.apache.uima.jcas.JCas;
import org.apache.uima.fit.factory.JCasFactory;
import org.xml.sax.SAXException;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Base64;

/**
 * Class for serializing and deserializing CAS objects.
 * Converts JCas to Base64-encoded XMI string for MongoDB storage.
 *
 * @author Max Froese
 */
public class CASSerializer {

    /**
     * Serializes a JCas object to a Base64-encoded XMI string.
     * (This format can be stored in MongoDB as a string field)
     *
     * @param jCas The JCas object to serialize
     * @return Base64-encoded XMI string representation of the CAS
     * @throws IOException if serialization fails
     * @throws SAXException if XML generation fails
     */
    public static String serializeToBase64(JCas jCas) throws IOException, SAXException {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();

        // Serialize CAS to XMI format
        XmiCasSerializer.serialize(jCas.getCas(), outputStream);

        // Convert to Base64 for storage in MongoDB
        byte[] xmiBytes = outputStream.toByteArray();
        return Base64.getEncoder().encodeToString(xmiBytes);
    }

    /**
     * Deserializes a Base64-encoded XMI string back to a JCas object.
     *
     * @param base64Xmi Base64-encoded XMI string from MongoDB
     * @return Reconstructed JCas object with all annotations
     * @throws Exception if deserialization fails
     */
    public static JCas deserializeFromBase64(String base64Xmi) throws Exception {
        // Decode Base64 string
        byte[] xmiBytes = Base64.getDecoder().decode(base64Xmi);

        // Create new JCas
        JCas jCas = JCasFactory.createJCas();

        // Deserialize XMI into the CAS
        ByteArrayInputStream inputStream = new ByteArrayInputStream(xmiBytes);
        XmiCasDeserializer.deserialize(inputStream, jCas.getCas(), true);

        return jCas;
    }

    /**
     * Checks if a serialized CAS exists (i.e., string is not null or empty).
     *
     * @param serializedCas The serialized CAS string to check
     * @return true if CAS data exists, false otherwise
     */
    public static boolean hasSerializedCas(String serializedCas) {
        return serializedCas != null && !serializedCas.isEmpty();
    }
}