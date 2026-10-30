"""Lua 5.1-окружение для мостика: настоящие исходники VoiceOver 1.4.5 + заглушки WoW API (книга, события, звук).

Исходники VoiceOver берутся из VOICEOVER_DIR (по умолчанию — копия в соседнем конвертере, она совпадает с 1.4.5
из игры побайтно).
"""
import os
from pathlib import Path

from lupa import lua51

REPO = Path(__file__).resolve().parents[1]
ADDON = "AI_VoiceOverData_BookVoices_RU"
ADDON_DIR = REPO / ADDON
VOICEOVER_DIR = Path(os.environ.get("VOICEOVER_DIR", REPO.parent / "classic-wow-voiceover" / "AI_VoiceOver"))
VOICEOVER_FILES = ("Environment.lua", "Enums.lua", "Utils.lua", "FuzzySearch.lua", "DataModules.lua",
                   "SoundQueue.lua")

WOW_API_STUBS = """
format = string.format
getn = table.getn
strsplit = function(sep, s, limit)
    local parts, from = {}, 1
    while true do
        if limit and #parts == limit - 1 then break end
        local a, b = string.find(s, sep, from, true)
        if not a then break end
        table.insert(parts, string.sub(s, from, a - 1))
        from = b + 1
    end
    table.insert(parts, string.sub(s, from))
    return unpack(parts)
end
strtrim = function(s) return (string.gsub(s, "^[ \\t\\r\\n]+", ""):gsub("[ \\t\\r\\n]+$", "")) end

_UNIT_SEX = 2
UnitSex = function() return _UNIT_SEX end
GetLocale = function() return _LOCALE or "ruRU" end
_TOC = {}
GetAddOnMetadata = function(name, key) return _TOC[name] and _TOC[name][key] end
GetCVar = function() return "1" end

_BOOK = {}
ItemTextGetItem = function() return _BOOK.title end
ItemTextGetText = function() return _BOOK.text end
ItemTextGetPage = function() return _BOOK.page end
ItemTextHasNextPage = function() return _BOOK.next end

_PLAYED, _STOPPED, _HANDLE = {}, {}, 0
PlaySoundFile = function(path, channel)
    _HANDLE = _HANDLE + 1
    if channel then table.insert(_PLAYED, path) end  -- TestSound играет без канала и сразу глушит
    return true, _HANDLE
end
StopSound = function(handle) if handle then _STOPPED[handle] = true end end

hooksecurefunc = function(t, name, hook)  -- пост-хук, как в клиенте (на таблице)
    local original = t[name]
    t[name] = function(...)
        local result = { original(...) }
        hook(...)
        return unpack(result)
    end
end

_FRAMES = {}
CreateFrame = function()
    local frame = { events = {} }
    function frame:RegisterEvent(event) self.events[event] = true end
    function frame:UnregisterEvent(event) self.events[event] = nil end
    function frame:SetScript(name, fn) self[name] = fn end
    table.insert(_FRAMES, frame)
    return frame
end
function _fire(event, ...)
    for _, frame in ipairs(_FRAMES) do
        if frame.events[event] and frame.OnEvent then frame.OnEvent(frame, event, ...) end
    end
end

function _setup_voiceover()
    VoiceOver.Addon = {
        db = { profile = { Audio = { SoundChannel = VoiceOver.Enums.SoundChannel.Master, AutoToggleDialog = false,
                                     StopAudioOnDisengage = false } },
               char = { IsPaused = false } },
        timers = {},
    }
    function VoiceOver.Addon:ScheduleTimer(fn, delay) table.insert(self.timers, fn); return #self.timers end
    function VoiceOver.Addon:CancelTimer(id) if id then self.timers[id] = false end end
    VoiceOver.Debug = { messages = {} }
    function VoiceOver.Debug:Print(msg) table.insert(self.messages, msg) end
    VoiceOver.SoundQueueUI = { UpdateSoundQueueDisplay = function() end, UpdatePauseDisplay = function() end }
end

function _present(name, priority)
    _TOC[name] = { ["X-VoiceOver-DataModule-Version"] = "1", ["X-VoiceOver-DataModule-Priority"] = tostring(priority) }
    VoiceOver.DataModules.presentModules[name] = { AddonName = name, ModulePriority = priority }
end

function _finish_sound(index)
    local sound = VoiceOver.SoundQueue.sounds[index or 1]
    VoiceOver.SoundQueue:RemoveSoundFromQueue(sound, true)
end
"""


class Wow:
    def __init__(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(WOW_API_STUBS)
        for name in VOICEOVER_FILES:
            self.lua.execute((VOICEOVER_DIR / name).read_text(encoding="utf-8"))
            if name == "Environment.lua":
                self.lua.execute("VoiceOver.Version = { IsRetailVanilla = true, "
                                 "IsRetailOrAboveLegacyVersion = function() return false end }")
        self.g.VoiceOver.SoundQueue.sounds = self.lua.table()
        self.g._setup_voiceover()
        self._run_file = self.lua.eval(
            "function(src, chunk, name, ns) return assert(loadstring(src, chunk))(name, ns) end")
        self.ns = self.lua.table()

    @property
    def g(self):
        return self.lua.globals()

    @property
    def vo(self):
        return self.g.VoiceOver

    def table(self, value):
        """Python dict/list → таблица Lua (вложенные — тоже)."""
        if isinstance(value, dict):
            t = self.lua.table()
            for k, v in value.items():
                t[k] = self.table(v)
            return t
        if isinstance(value, (list, tuple)):
            t = self.lua.table()
            for i, v in enumerate(value, 1):
                t[i] = self.table(v)
            return t
        return value

    def run_addon_file(self, relative, ns=None):
        """Файл аддона так, как его исполняет клиент: с аргументами (имя аддона, приватная таблица)."""
        src = (ADDON_DIR / relative).read_text(encoding="utf-8")
        return self._run_file(src, "@" + relative, ADDON, ns or self.ns)

    def install_module(self):
        """Модуль целиком, как клиент: файлы из .toc по порядку."""
        self.g._present(ADDON, 200)
        toc = (ADDON_DIR / f"{ADDON}.toc").read_text(encoding="utf-8").splitlines()
        for line in toc:
            if line.strip() and not line.startswith("#"):
                self.run_addon_file(line.strip().replace("\\", "/"))
        return self.g[ADDON]

    def set_locale(self, locale):
        self.g._LOCALE = locale

    def set_player_sex(self, sex):
        self.g._UNIT_SEX = sex

    def open_page(self, title, page, text, has_next=False):
        self.g._BOOK.title, self.g._BOOK.page, self.g._BOOK.text = title, page, text
        self.g._BOOK.next = has_next
        self.g._fire("ITEM_TEXT_READY")

    def fire(self, event, *args):
        self.g._fire(event, *args)

    def finish_sound(self, index=1):
        self.g._finish_sound(index)

    def queue(self):
        return [self.vo.SoundQueue.sounds[i] for i in range(1, len(self.vo.SoundQueue.sounds) + 1)]

    def played(self):
        return list(self.g._PLAYED.values())

    def stopped(self, handle):
        return bool(self.g._STOPPED[handle])
