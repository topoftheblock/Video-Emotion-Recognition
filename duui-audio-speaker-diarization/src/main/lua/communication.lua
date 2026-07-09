-- DUUI communication layer for the Audio Speaker Diarization component.
--
-- serialize:   pull the base64 audio out of the CAS and send it to the tool.
-- deserialize: read the speaker turns back and write SpeakerSegment
--              annotations into the CAS.

-- Name of the view that carries the audio SOFA. Override per-pipeline via the
-- component parameter "audio_view"; defaults to "audio".
local DEFAULT_AUDIO_VIEW = "audio"

function serialize(inputCas, outputStream, params)
    params = params or {}
    local audioViewName = params["audio_view"] or DEFAULT_AUDIO_VIEW

    -- Fall back to the base CAS view if the named audio view is absent.
    local audioView
    local ok = pcall(function()
        audioView = inputCas:getView(audioViewName)
    end)
    if not ok or audioView == nil then
        audioView = inputCas
    end

    local payload = {
        audio_base64 = audioView:getSofaDataString()
    }

    -- Optional speaker-count hints passed through as component parameters.
    if params["num_speakers"] ~= nil then
        payload.num_speakers = tonumber(params["num_speakers"])
    end
    if params["min_speakers"] ~= nil then
        payload.min_speakers = tonumber(params["min_speakers"])
    end
    if params["max_speakers"] ~= nil then
        payload.max_speakers = tonumber(params["max_speakers"])
    end

    outputStream:write(json.encode(payload))
end

function deserialize(outputCas, inputStream, params)
    params = params or {}
    local targetViewName = params["target_view"]

    -- Write annotations into the target view if given, else the base CAS.
    local targetView = outputCas
    if targetViewName ~= nil then
        local ok = pcall(function()
            targetView = outputCas:getView(targetViewName)
        end)
        if not ok then
            targetView = outputCas
        end
    end

    local body = inputStream:readAllBytes()
    local response = json.decode(body)

    if response == nil or response["segments"] == nil then
        return
    end

    local SpeakerSegment = "org.texttechnologylab.annotation.audio.SpeakerSegment"

    for _, seg in ipairs(response.segments) do
        -- Temporal-only annotation: begin/end offsets are 0 because the
        -- segment is anchored on the audio timeline, not on character spans.
        local anno = targetView:createAnnotation(SpeakerSegment, 0, 0)

        anno:setStringValue(
            anno:getType():getFeatureByBaseName("speakerId"),
            seg.speaker_id
        )
        anno:setDoubleValue(
            anno:getType():getFeatureByBaseName("timeStart"),
            seg.start
        )
        anno:setDoubleValue(
            anno:getType():getFeatureByBaseName("timeEnd"),
            seg["end"]
        )

        targetView:addFsToIndexes(anno)
    end
end
