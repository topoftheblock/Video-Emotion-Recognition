StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local audioView = inputCas:getView()
    outputStream:write(json.encode({ audio_base64 = audioView:getSofaDataString() }))
end

function deserialize(outputCas, inputStream, params)
    local textView = outputCas:getView()
    local response = json.decode(inputStream:readAllBytes())

    if response["segments"] ~= nil then
        for _, seg in ipairs(response.segments) do
            -- Strictly using the package from MultimodalIdentityTypeSystem.xml
            local speakerAnno = textView:createAnnotation("org.texttechnologylab.annotation.audio.SpeakerSegment", 0, 0)

            speakerAnno:setFeatureValueFromString("speakerId", seg.speaker_id)
            speakerAnno:setDoubleValue(speakerAnno:getType():getFeatureByBaseName("timeStart"), seg.start_time)
            speakerAnno:setDoubleValue(speakerAnno:getType():getFeatureByBaseName("timeEnd"), seg.end_time)

            textView:addFsToIndexes(speakerAnno)
        end
    end
end