if not VoiceOver or not VoiceOver.DataModules then return end
-- Русская озвучка: на клиенте с другой локалью модуль не регистрируется (мостик тогда тоже молчит)
if GetLocale() ~= "ruRU" then return end

AI_VoiceOverData_BookVoices_RU = {}

function AI_VoiceOverData_BookVoices_RU:GetSoundPath(fileName, event)
    return format([[generated\sounds\books\%s.ogg]], fileName)
end

VoiceOver.DataModules:Register("AI_VoiceOverData_BookVoices_RU", AI_VoiceOverData_BookVoices_RU)
