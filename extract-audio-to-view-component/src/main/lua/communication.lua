StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local videoBase64 = inputCas:getSofaDataString()

    outputStream:write(json.encode({
        video_base64 = videoBase64,
        input_format = params["input_format"],
        output_format = params["output_format"]
    }))
end

function deserialize(inputCas, inputStream)
    local inputString = luajava.newInstance("java.lang.String", inputStream:readAllBytes(), StandardCharsets.UTF_8)
    local results = json.decode(inputString)

    if results["audio_base64"] ~= null then
        inputCas:setSofaDataString(results["audio_base64"], results["mime_type"])
    end
end