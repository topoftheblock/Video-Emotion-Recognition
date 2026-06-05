StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local audioBase64 = inputCas:getSofaDataString()

    outputStream:write(json.encode({
        audio = audioBase64,
    }))
end

function deserialize(inputCas, inputStream)
    local inputString = luajava.newInstance("java.lang.String", inputStream:readAllBytes(), StandardCharsets.UTF_8)
    local results = json.decode(inputString)

    if results["modification_meta"] ~= nil and results["meta"] ~= nil and results["emotions"] ~= nil then
        local modification_meta = results["modification_meta"]
        local modification_anno = luajava.newInstance("org.texttechnologylab.annotation.DocumentModification", inputCas)
        modification_anno:setUser(modification_meta["user"])
        modification_anno:setTimestamp(modification_meta["timestamp"])
        modification_anno:setComment(modification_meta["comment"])
        modification_anno:addToIndexes()

        local documentText = inputCas:getDocumentText()
        if documentText == nil then
            documentText = ""
        end
        local docLength = string.len(documentText)

        for i, emo in ipairs(results["emotions"]) do
            local emotionAnno = luajava.newInstance("org.texttechnologylab.annotation.type.EmotionAnnotation", inputCas)
            emotionAnno:setBegin(0)
            emotionAnno:setEnd(docLength)
            emotionAnno:setEmotion(emo["emotion"])
            emotionAnno:setConfidence(emo["confidence"])
            emotionAnno:addToIndexes()

            local meta = results["meta"]
            local meta_anno = luajava.newInstance("org.texttechnologylab.annotation.AnnotatorMetaData", inputCas)
            meta_anno:setReference(emotionAnno)
            meta_anno:setName(meta["name"])
            meta_anno:setVersion(meta["version"])
            meta_anno:setModelName(meta["modelName"])
            meta_anno:setModelVersion(meta["modelVersion"])
            meta_anno:addToIndexes()
        end
    end
end
