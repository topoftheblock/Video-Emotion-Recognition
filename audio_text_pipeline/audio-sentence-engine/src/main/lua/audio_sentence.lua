StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local textView = inputCas:getView()
    local sentences = {}
    local tokens = {}

    local sentenceIdx = textView:getAnnotationIndex("de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence")
    -- We now look for DiarizedAudioToken!
    local tokenIdx = textView:getAnnotationIndex("org.texttechnologylab.annotation.type.DiarizedAudioToken")

    for sent in iterator(sentenceIdx) do
        table.insert(sentences, { begin = sent:getBegin(), ["end"] = sent:getEnd() })
    end
    for tok in iterator(tokenIdx) do
        -- Extract the speakerId safely (it might be null if whisper failed to assign it)
        local speaker = ""
        if tok:getSpeakerId() ~= nil then
            speaker = tok:getSpeakerId()
        end

        table.insert(tokens, {
            begin = tok:getBegin(),
            ["end"] = tok:getEnd(),
            timeStart = tok:getTimeStart(),
            timeEnd = tok:getTimeEnd(),
            speakerId = speaker
        })
    end

    outputStream:write(json.encode({ sentences = sentences, tokens = tokens }))
end

function deserialize(outputCas, inputStream, params)
    local textView = outputCas:getView()
    local response = json.decode(inputStream:readAllBytes())

    for _, as in ipairs(response.audio_sentences) do
        local audioSentAnno = textView:createAnnotation("org.texttechnologylab.annotation.type.AudioSentence", as.begin, as.end)
        audioSentAnno:setDoubleValue(audioSentAnno:getType():getFeatureByBaseName("timeStart"), as.timeStart)
        audioSentAnno:setDoubleValue(audioSentAnno:getType():getFeatureByBaseName("timeEnd"), as.timeEnd)
        -- We can now safely set speakerId if your XML supports it, or just use the bounds.
        -- audioSentAnno:setStringValue(audioSentAnno:getType():getFeatureByBaseName("speakerId"), as.speakerId)

        textView:addFsToIndexes(audioSentAnno)
    end
end