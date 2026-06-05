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

        local emotionAnno = luajava.newInstance("org.texttechnologylab.annotation.emotion.Emotion", inputCas)
        emotionAnno:setBegin(0)
        emotionAnno:setEnd(docLength)
        emotionAnno:setModality("audio")

        local numEmotions = #results["emotions"]
        local scoresArray = luajava.newInstance("org.apache.uima.jcas.cas.FSArray", inputCas:getJCas(), numEmotions)

        local dominantLabel = ""
        local dominantScore = -1.0

        for i, emo in ipairs(results["emotions"]) do
            local scoreAnno = luajava.newInstance("org.texttechnologylab.annotation.emotion.EmotionScore", inputCas)
            scoreAnno:setLabel(emo["emotion"])
            scoreAnno:setScore(emo["confidence"])
            scoreAnno:addToIndexes()
            
            scoresArray:set(i-1, scoreAnno)
            
            if emo["confidence"] > dominantScore then
                dominantScore = emo["confidence"]
                dominantLabel = emo["emotion"]
            end
        end

        emotionAnno:setScores(scoresArray)
        emotionAnno:setDominant(dominantLabel)
        emotionAnno:setDominantScore(dominantScore)
        emotionAnno:addToIndexes()

        local meta = results["meta"]
        local meta_anno = luajava.newInstance("org.texttechnologylab.annotation.model.MetaData", inputCas)
        meta_anno:setReference(emotionAnno)
        meta_anno:setName(meta["name"])
        meta_anno:setVersion(meta["version"])
        meta_anno:setModelName(meta["modelName"])
        meta_anno:setModelVersion(meta["modelVersion"])
        meta_anno:addToIndexes()
    end
end
