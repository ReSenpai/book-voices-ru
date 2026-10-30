local addonName, ns = ...

-- Мостик: открыта страница книги, записки или таблички → реплика в очереди VoiceOver (одно окно и очередь с квестами).
-- Своего события у VoiceOver нет. Страница идёт как квестовое событие QuestProgress (сам VoiceOver его не использует)
-- с номером записи вместо номера квеста — далеко за номерами настоящих квестов:
--   * в очереди страница — отдельная строка с названием, клик по ней убирает её (реплики Gossip там свёрнуты);
--   * встаёт в очередь и за квестами (реплику без questID VoiceOver не ставит, пока в очереди квест);
--   * файл VoiceOver ищет сам: [m-|f-]<номер>-progress, дубли по имени файла отсекает тоже он.
-- Страницу находим сами (TextMatch.lua).

local DEFAULT_NAME = "Книга"  -- ItemTextGetItem() может вернуть nil
local BOOK_ID_BASE = 300000000  -- как в конвертере (voru/catquest/books_build.py)

local VoiceOver = VoiceOver
local module = VoiceOver and VoiceOver.DataModules and VoiceOver.DataModules:GetModule(addonName)
local SoundQueue = VoiceOver and VoiceOver.SoundQueue
local Event = VoiceOver and VoiceOver.Enums and VoiceOver.Enums.SoundEvent
-- Другой локали (модуль не зарегистрирован) или незнакомого API VoiceOver — молчим
if not (module and Event and Event.QuestProgress and SoundQueue and SoundQueue.AddSoundToQueue
        and SoundQueue.RemoveSoundFromQueue and SoundQueue.IsEmpty and SoundQueue.ResumeQueue and SoundQueue.sounds) then
    return
end

local index = ns.BookIndex(module.Books or {}, module.BookTitles or {})

-- Номер записи для VoiceOver: первые 7 знаков хэша (уникальны среди записей — проверяет сборка).
local function BookID(bookHash)
    return BOOK_ID_BASE + tonumber(bookHash:sub(1, 7), 16)
end

local function IsBookSound(soundData)
    return soundData.event == Event.QuestProgress and soundData.questID and soundData.questID >= BOOK_ID_BASE
end

local function OnPage()
    local title, page, text = ItemTextGetItem(), ItemTextGetPage(), ItemTextGetText()
    local bookHash = index:Find(title, page, text)
    if not bookHash then return end

    local name = title and title ~= "" and title or DEFAULT_NAME
    local paged = page and (page > 1 or ItemTextHasNextPage and ItemTextHasNextPage())
    SoundQueue:AddSoundToQueue({
        event = Event.QuestProgress,
        questID = BookID(bookHash),
        name = name,
        title = paged and format("%s, стр. %d", name, page) or name,
        text = ns.CleanText(text),
    })
end

-- Страницы книг из очереди (с конца: удаление сдвигает следующие).
local function StopBooks()
    for i = #SoundQueue.sounds, 1, -1 do
        local soundData = SoundQueue.sounds[i]
        if soundData and IsBookSound(soundData) then SoundQueue:RemoveSoundFromQueue(soundData) end
    end
end

local handlers = {
    ITEM_TEXT_READY = OnPage,
    ITEM_TEXT_CLOSED = function()
        if VoiceOver.Addon.db.profile.Audio.StopAudioOnDisengage then StopBooks() end
    end,
    -- /reload и выход: звук PlaySoundFile переживает перезагрузку интерфейса, а очередь — нет. Пауза VoiceOver
    -- сохраняется у персонажа: после /reload пустая очередь стояла бы на паузе и новая страница молчала.
    PLAYER_LOGOUT = function()
        StopBooks()
        VoiceOver.Addon.db.char.IsPaused = false
    end,
}

-- Пауза VoiceOver относится к тому, что в очереди: очередь опустела (страницы и квесты убраны) — пауза снимается,
-- иначе следующая открытая книга или квест молча ждали бы. Касается и квестов: очередь у VoiceOver одна.
hooksecurefunc(SoundQueue, "RemoveSoundFromQueue", function()
    if SoundQueue:IsEmpty() and VoiceOver.Addon.db.char.IsPaused then SoundQueue:ResumeQueue() end
end)

local frame = CreateFrame("Frame")
for event in pairs(handlers) do
    frame:RegisterEvent(event)
end
frame:SetScript("OnEvent", function(_, event) handlers[event]() end)
