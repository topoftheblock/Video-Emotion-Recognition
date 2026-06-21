function serialize(inputCas, outputStream, params)
    local audioView = inputCas:getView("AudioView")
    outputStream:write(json.encode({ audio_base64 = audioView:getSofaDataString() }))
end

function deserialize(outputCas, inputStream, params)
    local textView = outputCas:getView("TextView")
    local response = json.decode(inputStream:readAllBytes())

    for _, seg in ipairs(response.segments) do
        -- Created as 0-bound annotations since they are mapped purely temporally first
        local speakerAnno = textView:createAnnotation("org.texttechnologylab.annotation.SpeakerSegment", 0, 0)
        speakerAnno:setFeatureValue("speakerId", seg.speaker_id)
        speakerAnno:setFeatureValue("timeStart", seg.start)
        speakerAnno:setFeatureValue("timeEnd", seg.end)
        textView:addFsToIndexes(speakerAnno)
    end
end