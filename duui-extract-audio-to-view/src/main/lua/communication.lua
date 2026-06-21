-- ============================================================================
-- DUUI Communication Layer: Audio Extraction To View Component
--
-- This Lua script is the bridge between DUUI's Java-side CAS objects and the
-- Python annotator's REST API. DUUI runs it in an embedded Lua interpreter.
-- Two functions are required:
--   serialize   - reads data out of the (source) CAS, writes JSON to the
--                 request that is POSTed to the Python /v1/process endpoint
--   deserialize - reads the JSON response from Python, writes the result
--                 back into the (target) CAS
--
-- View routing (which view is read from / written to) is controlled entirely
-- from the Java pipeline via .withSourceView(...) and .withTargetView(...).
--
-- @author Nickolas Eickmann
-- ============================================================================


-- Bind the Java StandardCharsets class so we can reference UTF-8 below.
-- luajava.bindClass loads a Java class into Lua; this is a *static* binding.
StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

-- ----------------------------------------------------------------------------
-- serialize: CAS -> outgoing request body
--
--   inputCas     : the source view's CAS (set via .withSourceView in Java).
--                  Its Sofa holds the input video as a (base64) string.
--   outputStream : the stream whose contents become the POST body to Python.
--   params       : key/value parameters defined in Java via .withParameter(...)
--                  (here: output_format).
-- ----------------------------------------------------------------------------
function serialize(inputCas, outputStream, params)
    -- Read the Sofa data string of the source view.
    local videoBase64 = inputCas:getSofaDataString()

    -- Encode the payload as JSON and write it to the request stream.
    -- The `json` library is provided automatically by DUUI in every Lua script.
    -- These keys must match the fields the Python DUUIRequest model expects.
    -- The input format is intentionally not sent: ffmpeg auto-detects it on the
    -- Python side from the video bytes.
    outputStream:write(json.encode({
        video_base64 = videoBase64,
        output_format = params["output_format"]
    }))
end

-- ----------------------------------------------------------------------------
-- deserialize: incoming response body -> CAS
--
--   inputCas    : the target view's CAS (set via .withTargetView in Java).
--                 We write the extracted audio into this view's Sofa.
--   inputStream : the raw response stream returned by the Python annotator.
-- ----------------------------------------------------------------------------
function deserialize(inputCas, inputStream)
    -- Read the entire response stream into bytes and wrap them in a Java String,
    -- explicitly decoding as UTF-8 so the JSON text is interpreted correctly.
    local inputString = luajava.newInstance("java.lang.String", inputStream:readAllBytes(), StandardCharsets.UTF_8)

    -- Parse the JSON response into a Lua table.
    local results = json.decode(inputString)

    -- Only write back if the annotator actually returned audio. Note: DUUI's Lua
    -- environment uses `null` (not `nil`) to represent JSON null values, so the
    -- comparison must be against `null`.
    if results["audio_base64"] ~= null then
        -- Write the base64 audio into the target view's Sofa, tagging it with the
        -- MIME type returned by Python (e.g. "audio/wav"). Writing directly to
        -- inputCas targets whatever view was configured via .withTargetView.
        inputCas:setSofaDataString(results["audio_base64"], results["mime_type"])
    end
end