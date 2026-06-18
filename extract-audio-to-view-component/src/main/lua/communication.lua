--[[
StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")
Base64 = luajava.bindClass("java.util.Base64")

function serialize(inputCas, outputStream, parameters)
    local sofa = inputCas:getSofa()
    local mimeType = sofa:getMimeType()  -- e.g. "video/mp4"
    local videoBytes = inputCas:getSofaDataArray()  -- byte[] from the SofA
    local encoded = Base64.getEncoder():encodeToString(videoBytes)

    outputStream:write(json.encode({
        video_base64 = encoded,
        mime_type = mimeType,
        input_format = input_format,
        output_format = output_format,
    }))
end

function deserialize(inputCas, inputStream)
    local inputString = luajava.newInstance("java.lang.String", inputStream:readAllBytes(), StandardCharsets.UTF_8)
    local results = json.decode(inputString)

    if results["audio_base64"] ~= nil then
        local audioBytes = Base64.getDecoder():decode(results["audio_base64"])

        -- Create (or get) the target view and set its Sofa data
        local audioView = inputCas:createView("audio")
        audioView:setSofaDataArray(audioBytes, results["mime_type"])
    end
end ]]

StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local videoBase64 = inputCas:getView("_InitialView"):getSofaDataString()

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
        local view = inputCas:getView("audioView")   -- match your Java target view name
        view:setSofaDataString(results["audio_base64"], results["mime_type"])
    end
end