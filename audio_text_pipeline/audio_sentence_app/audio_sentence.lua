function serialize(inputCas, outputStream, params)
    local textView = inputCas:getView("TextView")

    local sentences = {}
    local tokens = {}
    local speakers = {}

    -- Extract all prerequisites from the index
    local sentenceIdx = textView:getAnnotationIndex("de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence")
    local tokenIdx = textView:getAnnotationIndex("org.texttechnologylab.annotation.AudioToken")
    local speakerIdx = textView:getAnnotationIndex("org.texttechnologylab.annotation.SpeakerSegment")

    -- Convert indexes to serializable tables
    for sent in iterator(sentenceIdx) do
        table.insert(sentences, { begin = sent:getBegin(), ["end"] = sent:getEnd() })
    end
    for tok in iterator(tokenIdx) do
        table.insert(tokens, { begin = tok:getBegin(), ["end"] = tok:getEnd(), timeStart = tok:getFeatureValue("timeStart"), timeEnd = tok:getFeatureValue("timeEnd") })
    end
    for spk in iterator(speakerIdx) do
        table.insert(speakers, { speakerId = spk:getFeatureValue("speakerId"), timeStart = spk:getFeatureValue("timeStart"), timeEnd = spk:getFeatureValue("timeEnd") })
    end

    outputStream:write(json.encode({ sentences = sentences, tokens = tokens, speakers = speakers }))
end

function deserialize(outputCas, inputStream, params)
    local textView = outputCas:getView("TextView")
    local response = json.decode(inputStream:readAllBytes())

    for _, as in ipairs(response.audio_sentences) do
        local audioSentAnno = textView:createAnnotation("org.texttechnologylab.annotation.AudioSentence", as.begin, as.end)
        audioSentAnno:setFeatureValue("timeStart", as.timeStart)
        audioSentAnno:setFeatureValue("timeEnd", as.timeEnd)
        audioSentAnno:setFeatureValue("speakerId", as.speakerId)
        textView:addFsToIndexes(audioSentAnno)
    end
end