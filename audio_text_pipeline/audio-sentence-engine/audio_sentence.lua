StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local textView = inputCas:getView("TextView")
    local sentences = {}
    local tokens = {}

    local sentenceIdx = textView:getAnnotationIndex("de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence")
    local tokenIdx = textView:getAnnotationIndex("org.texttechnologylab.annotation.type.AudioToken")

    for sent in iterator(sentenceIdx) do
        table.insert(sentences, { begin = sent:getBegin(), ["end"] = sent:getEnd() })
    end
    for tok in iterator(tokenIdx) do
        table.insert(tokens, {
            begin = tok:getBegin(),
            ["end"] = tok:getEnd(),
            timeStart = tok:getDoubleValue(tok:getType():getFeatureByBaseName("timeStart")),
            timeEnd = tok:getDoubleValue(tok:getType():getFeatureByBaseName("timeEnd"))
        })
    end

    outputStream:write(json.encode({ sentences = sentences, tokens = tokens }))
end

function deserialize(outputCas, inputStream, params)
    local textView = outputCas:getView("TextView")
    local response = json.decode(inputStream:readAllBytes())

    for _, as in ipairs(response.audio_sentences) do
        -- Strictly using the package inferred from AudioSentenceAnnotator.java
        local audioSentAnno = textView:createAnnotation("org.texttechnologylab.annotation.type.AudioSentence", as.begin, as.end)

        audioSentAnno:setDoubleValue(audioSentAnno:getType():getFeatureByBaseName("timeStart"), as.timeStart)
        audioSentAnno:setDoubleValue(audioSentAnno:getType():getFeatureByBaseName("timeEnd"), as.timeEnd)
        -- speakerId removed to comply with locked TypeSystem

        textView:addFsToIndexes(audioSentAnno)
    end
end