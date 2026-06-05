StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")

function serialize(inputCas, outputStream, params)
    local audioBase64 = inputCas:getSofaDataString()
    local selectionType = nil
    if params ~= nil then
        selectionType = params:get("selection")
    end

    local segments = nil

    if selectionType ~= nil then
        local uimaType = inputCas:getTypeSystem():getType(selectionType)
        if uimaType ~= nil then
            segments = {}
            local iter = inputCas:getAnnotationIndex(uimaType):iterator()
            local id = 0
            while iter:isValid() do
                local anno = iter:get()
                table.insert(segments, {
                    id = id,
                    start_time = anno:getFloatValue(uimaType:getFeatureByBaseName("timeStart")),
                    end_time = anno:getFloatValue(uimaType:getFeatureByBaseName("timeEnd"))
                })
                id = id + 1
                iter:moveToNext()
            end
        end
    end

    outputStream:write(json.encode({
        audio = audioBase64,
        segments = segments
    }))
end

function deserialize(inputCas, inputStream, params)
    local inputString = luajava.newInstance("java.lang.String", inputStream:readAllBytes(), StandardCharsets.UTF_8)
    local results = json.decode(inputString)

    if results["modification_meta"] ~= nil and results["meta"] ~= nil and results["results"] ~= nil then
        local modification_meta = results["modification_meta"]
        local modification_anno = luajava.newInstance("org.texttechnologylab.annotation.DocumentModification", inputCas)
        modification_anno:setUser(modification_meta["user"])
        modification_anno:setTimestamp(modification_meta["timestamp"])
        modification_anno:setComment(modification_meta["comment"])
        modification_anno:addToIndexes()

        local selectionType = nil
        if params ~= nil then
            selectionType = params:get("selection")
        end

        local referenceAnnos = {}
        if selectionType ~= nil then
            local uimaType = inputCas:getTypeSystem():getType(selectionType)
            if uimaType ~= nil then
                local iter = inputCas:getAnnotationIndex(uimaType):iterator()
                while iter:isValid() do
                    table.insert(referenceAnnos, iter:get())
                    iter:moveToNext()
                end
            end
        end

        local documentText = inputCas:getDocumentText()
        if documentText == nil then
            documentText = ""
        end
        local docLength = string.len(documentText)

        for _, seg_result in ipairs(results["results"]) do
            local id = seg_result["id"]
            local emotions = seg_result["emotions"]

            local emotionAnno = luajava.newInstance("org.texttechnologylab.annotation.emotion.Emotion", inputCas)
            emotionAnno:setBegin(0)
            emotionAnno:setEnd(docLength)
            emotionAnno:setModality("audio")

            local refAnno = referenceAnnos[id + 1] -- Lua is 1-indexed
            if refAnno ~= nil then
                emotionAnno:setBegin(refAnno:getBegin())
                emotionAnno:setEnd(refAnno:getEnd())
                emotionAnno:setReference(refAnno)
                
                local uimaType = inputCas:getTypeSystem():getType(selectionType)
                emotionAnno:setTimeStart(refAnno:getFloatValue(uimaType:getFeatureByBaseName("timeStart")))
                emotionAnno:setTimeEnd(refAnno:getFloatValue(uimaType:getFeatureByBaseName("timeEnd")))
            end

            local numEmotions = #emotions
            local scoresArray = luajava.newInstance("org.apache.uima.jcas.cas.FSArray", inputCas:getJCas(), numEmotions)

            local dominantLabel = ""
            local dominantScore = -1.0

            for i, emo in ipairs(emotions) do
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
end
