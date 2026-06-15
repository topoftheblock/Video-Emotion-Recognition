--[[
  duui_emotion.lua
  ----------------
  DUUI communication layer for the Phase-1 HSEmotion component.

  serialize   : extracts the phase1-graph payload from the CAS and sends it
                as JSON to the Python REST endpoint.
  deserialize : reads the returned emotions JSON and writes Emotion annotations
                back into the CAS.

  The CAS is expected to carry:
    - DocumentMetaData with a "phase1Json" feature containing the serialised
      phase1 graph, OR the four arrays (video / face_identities / tracks /
      face_detections) stored directly as document-level features.

  For simplicity this script passes the raw phase1 JSON string through and
  expects the Python side to parse it.  Adapt to your actual CAS schema.
--]]

StandardCharsets = luajava.bindClass("java.nio.charset.StandardCharsets")
JCasUtil         = luajava.bindClass("org.apache.uima.fit.util.JCasUtil")
DUUIUtils        = luajava.bindClass("org.texttechnologylab.DockerUnifiedUIMAInterface.lua.DUUILuaUtils")

EmotionType      = luajava.bindClass("org.texttechnologylab.annotation.emotion.Emotion")
EmotionScoreType = luajava.bindClass("org.texttechnologylab.annotation.emotion.EmotionScore")


-- ============================================================
--  serialize  :  CAS  ->  JSON  ->  Python tool
-- ============================================================
function serialize(inputCas, outputStream, parameters)
    -- Retrieve the phase1 payload stored in the document text.
    -- Convention: the DUUI pipeline stores the raw phase1.json content as the
    -- document text when processing video-graph documents.
    local phase1_text = inputCas:getDocumentText()

    -- Forward the entire phase1 payload unchanged; the Python REST endpoint
    -- expects exactly this structure.
    outputStream:write(phase1_text)
end


-- ============================================================
--  deserialize  :  JSON  ->  CAS annotations
-- ============================================================
function deserialize(inputCas, inputStream)
    local inputString = luajava.newInstance(
        "java.lang.String",
        inputStream:readAllBytes(),
        StandardCharsets.UTF_8
    )
    local results = json.decode(inputString)

    if results == nil or results["emotions"] == nil then
        return
    end

    local doc_len = DUUIUtils:getDocumentTextLength(inputCas)

    for _, emo in ipairs(results["emotions"]) do
        local anno = luajava.newInstance("org.texttechnologylab.annotation.emotion.Emotion", inputCas)

        -- span defaults to full document
        anno:setBegin(0)
        anno:setEnd(doc_len)

        -- core fields
        anno:setEmotionId(emo["id"]               or "")
        anno:setGranularity(emo["granularity"]    or "")
        anno:setReferenceType(emo["reference_type"] or "")
        anno:setReference(emo["reference"]        or "")
        anno:setModality(emo["modality"]          or "video")
        anno:setModel(emo["model"]                or "")

        -- temporal
        if emo["time_start"] ~= nil then anno:setTimeStart(emo["time_start"]) end
        if emo["time_end"]   ~= nil then anno:setTimeEnd(emo["time_end"])     end
        if emo["frame_index"] ~= nil then
            anno:setFrameIndex(emo["frame_index"])
        else
            anno:setFrameIndex(-1)
        end

        -- dominant
        anno:setDominant(emo["dominant"]           or "")
        if emo["dominant_score"] ~= nil then anno:setDominantScore(emo["dominant_score"]) end

        -- VA
        if emo["valence"] ~= nil then anno:setValence(emo["valence"]) end
        if emo["arousal"] ~= nil then anno:setArousal(emo["arousal"]) end

        -- aggregation chain (segment only)
        if emo["aggregated_from"] ~= nil and #emo["aggregated_from"] > 0 then
            local joined = table.concat(emo["aggregated_from"], ",")
            anno:setAggregatedFrom(joined)
        end

        -- EmotionScore array
        if emo["scores"] ~= nil then
            local fsArray = luajava.newInstance(
                "org.apache.uima.jcas.cas.FSArray",
                inputCas,
                #emo["scores"]
            )
            for i, sc in ipairs(emo["scores"]) do
                local scoreAnno = luajava.newInstance(
                    "org.texttechnologylab.annotation.emotion.EmotionScore",
                    inputCas
                )
                scoreAnno:setLabel(sc["label"] or "")
                scoreAnno:setScore(sc["score"] or 0.0)
                scoreAnno:addToIndexes()
                fsArray:set(i - 1, scoreAnno)
            end
            fsArray:addToIndexes()
            anno:setScores(fsArray)
        end

        anno:addToIndexes()
    end
end