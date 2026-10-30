local _, ns = ...

-- Поиск озвученной страницы по тому, что показала игра: название (ItemTextGetItem), номер страницы (ItemTextGetPage)
-- и текст (ItemTextGetText). Образец — voru/catquest/books_match.py в конвертере (держать одинаковыми); идеи и
-- очистка текста — CatQuest 0.7.1 (Core.lua, TextMatch.lua — MIT, daniilcathey). Порядок:
--   1. hash — хэш очищенного текста совпал с записью пака;
--   2. title — по названию и номеру страницы (BookTitles);
--   3. first_line — по первой строке («^…» в BookTitles: памятники с почти одинаковым текстом);
--   4. fuzzy — самая похожая по словам (Жаккар) страница: не ниже FUZZY_MIN и с отрывом FUZZY_GAP от второй.
--      Почти одинаковые тексты (две редакции одной страницы, похожесть ≥ SAME_PAGE) вторым кандидатом не считаются.

local FUZZY_MIN, FUZZY_GAP = 0.5, 0.25
local SAME_PAGE = 0.7   -- две редакции одной страницы ≈ 0.8; разные страницы книги — < 0.3
local LINKED_MIN = 0.2  -- title/first_line: текст хоть немного похож — иначе это другая книга с тем же именем

-- CleanText CatQuest без опции stripBrackets: от этого текста считается хэш страницы.
function ns.CleanText(text)
    if not text or text == "" then return "" end
    local s = text:gsub("\r\n", "\n"):gsub("\r", "\n")
    s = s:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    s = s:gsub("|T.-|t", ""):gsub("|A.-|a", "")
    s = s:gsub("|H.-|h(.-)|h", "%1")
    s = s:gsub("|n", "\n"):gsub("<", "("):gsub(">", ")")
    s = s:gsub("[ \t]+", " "):gsub(" *\n *", "\n"):gsub("\n\n\n+", "\n\n")
    return (s:gsub("^[ \t\r\n]+", ""):gsub("[ \t\r\n]+$", ""))
end

-- h = (h·31 + байт) mod 2³² по байтам UTF-8.
function ns.TextHash(s)
    local h = 0
    for i = 1, #s do
        h = (h * 31 + s:byte(i)) % 4294967296
    end
    return string.format("%08x", h)
end

-- А–П (D0 90–9F) → а–п; Р–Я (D0 A0–AF) → р–я (D1 80–8F); Ё/ё → е; прочий не-ASCII — разделитель.
local function LowerRu(ch)
    local b1, b2 = ch:byte(1, 2)
    if b1 == 208 then
        if b2 == 129 then return "\208\181" end
        if b2 >= 144 and b2 <= 159 then return "\208" .. string.char(b2 + 32) end
        if b2 >= 160 and b2 <= 175 then return "\209" .. string.char(b2 - 32) end
        if b2 >= 176 and b2 <= 191 then return ch end
    elseif b1 == 209 then
        if b2 == 145 then return "\208\181" end
        if b2 >= 128 and b2 <= 143 then return ch end
    end
    return " "
end

-- Только явные диапазоны байтов: lower(), %w, %S зависят от локали C-библиотеки.
local function LowerAscii(ch) return string.char(ch:byte() + 32) end

-- Теги HTML-страниц (после CleanText — в скобках): «(HTML)», «(/P)», «(BR/)», «(H1 align="center")».
local function DropTag(open, slash, name, rest, close)
    if rest == "" or rest == "/" or rest:find("^%s") then return " " end
end

local function Normalize(text)
    local s = (text or ""):gsub("([<(])(/?)([A-Za-z][A-Za-z0-9]*)([^<>()]*)([>)])", DropTag)
    s = s:gsub("[A-Z]", LowerAscii):gsub("[\192-\255][\128-\191]*", LowerRu)
    return (s:gsub("[^0-9a-z\128-\255]", " "))
end

-- Множество слов (слова короче 2 букв не считаются); [0] — их число.
function ns.Words(text)
    local set, n = {}, 0
    for w in Normalize(text):gmatch("[^ ]+") do
        if #(w:gsub("[\128-\191]", "")) >= 2 and not set[w] then
            set[w] = true
            n = n + 1
        end
    end
    set[0] = n
    return set
end

function ns.Jaccard(a, b)
    local na, nb, both = a[0], b[0], 0
    if na == 0 and nb == 0 then return 1 end
    for w in pairs(a) do
        if w ~= 0 and b[w] then both = both + 1 end
    end
    return both / (na + nb - both)
end

local Index = {}
Index.__index = Index

-- books: [хэш] = субтитры записи или false (без субтитров); titles: [название | "^первая строка"] = {хэш стр. 1, …}.
function ns.BookIndex(books, titles)
    return setmetatable({ books = books, titles = titles }, Index)
end

-- Множества слов субтитров — при первом обращении к записи.
function Index:WordsOf(bookHash)
    self.words = self.words or {}
    local set = self.words[bookHash]
    if set == nil then
        local text = self.books[bookHash]
        set = text and ns.Words(text) or false
        self.words[bookHash] = set
    end
    return set or nil
end

-- Запись по названию/первой строке, и текст ей не противоречит.
function Index:Linked(bookHash, seen)
    if self.books[bookHash] == nil then return false end
    local set = self:WordsOf(bookHash)
    return not set or ns.Jaccard(seen, set) >= LINKED_MIN
end

---@return string|nil bookHash, string|nil method, number|nil score похожесть текста игры на озвученный
function Index:Find(title, page, text)
    local clean = ns.CleanText(text)
    if clean == "" then return nil end
    local seen = ns.Words(clean)

    local function found(bookHash, method)
        local set = self:WordsOf(bookHash)
        return bookHash, method, set and ns.Jaccard(seen, set) or 0
    end

    local bookHash = ns.TextHash(clean)
    if self.books[bookHash] ~= nil then return found(bookHash, "hash") end

    local pages = title and self.titles[title]
    if pages and page and page >= 1 and pages[page] and self:Linked(pages[page], seen) then
        return found(pages[page], "title")
    end

    local first = clean:match("^[^\n]*"):gsub("%s+$", "")
    local byLine = ns.Words(first)[0] > 0 and self.titles["^" .. first]  -- «(HTML)», «$N!» — не ключ
    if byLine and self:Linked(byLine[1], seen) then
        return found(byLine[1], "first_line")
    end

    return self:Fuzzy(seen)
end

function Index:Fuzzy(seen)
    local scores, best, bestHash = {}, -1, nil
    for bookHash in pairs(self.books) do
        local set = self:WordsOf(bookHash)
        if set then
            local j = ns.Jaccard(seen, set)
            scores[bookHash] = j
            if j > best or (j == best and bookHash > bestHash) then
                best, bestHash = j, bookHash
            end
        end
    end
    if not bestHash or best < FUZZY_MIN then return nil end
    local bestSet, second = self.words[bestHash], 0
    for bookHash, j in pairs(scores) do
        if j > second and bookHash ~= bestHash and ns.Jaccard(bestSet, self.words[bookHash]) < SAME_PAGE then
            second = j
        end
    end
    if best - second < FUZZY_GAP then return nil end
    return bestHash, "fuzzy", best
end
