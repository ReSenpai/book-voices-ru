"""Поиск озвученной страницы в Lua — те же случаи, что у образца books_match.py в конвертере (держать одинаковыми)."""
import pytest

from tests.wow import Wow

TEXTS = {
    "first": "Глава первая.\nПришла тьма, и город пал под натиском нежити.",
    "edition": "Глава первая.\nПришла тьма, и город пал под натиском Плети.",  # та же страница в новой редакции
    "second": "Глава вторая.\nВыжившие ушли на север, к горам Альтерака.",
    "plaque": "Курдран Громовой Молот\nЗнаменитый драконобоец.",
    "plaque2": "Курдран Громовой Молот\nЗнаменитый укротитель грифонов.",
}


@pytest.fixture
def wow():
    w = Wow()
    w.run_addon_file("TextMatch.lua")
    return w


@pytest.fixture
def index(wow):
    h = {k: wow.ns.TextHash(wow.ns.CleanText(t)) for k, t in TEXTS.items()}
    books = {h[k]: t.replace("\n", " ") for k, t in TEXTS.items()}  # субтитры пака — без переводов строк
    books["0d0d0d0d"] = False  # запись без субтитров
    titles = {"Хроники падения": [h["first"], h["second"]], "^Курдран Громовой Молот": [h["plaque"]],
              "Безмолвная книга": ["0d0d0d0d"]}
    idx = wow.ns.BookIndex(wow.table(books), wow.table(titles))
    return idx, h


def find(idx, title, page, text):
    result = idx.Find(idx, title, page, text)
    return result if isinstance(result, tuple) else (result, None, None)  # lupa: одиночный nil — не кортеж


def words(wow, text):
    return {w for w in wow.ns.Words(text) if w != 0}


def test_clean_text_follows_catquest(wow):
    assert wow.ns.CleanText("|cff00ff00Зелёный|r  текст\r\n  <ремарка>|nконец  ") == "Зелёный текст\n(ремарка)\nконец"
    assert wow.ns.CleanText("a\n\n\n\nb") == "a\n\nb"
    assert wow.ns.CleanText("|TInterface\\Icons\\x:16|tЗнак |Hitem:1|h[Меч]|h") == "Знак [Меч]"
    assert wow.ns.CleanText(None) == ""


def test_text_hash_matches_catquest(wow):
    assert wow.ns.TextHash("abc") == "00017862"
    assert wow.ns.TextHash("Ёж") == "00608b57"  # байты UTF-8, как text_hash в конвертере


def test_words_ignore_case_yo_and_punctuation(wow):
    assert words(wow, "Всё — хорошо, ЁЖ! а") == {"все", "хорошо", "еж"}
    assert wow.ns.Words("Всё — хорошо")[0] == 2


def test_words_ignore_html_markup_but_keep_remarks(wow):
    page = wow.ns.CleanText('<HTML>\n<BODY>\n<H1 align="center">ЗВАНИЯ ОРДЫ</H1><BR/>\n<P>Вождь</P></BODY></HTML>')
    assert words(wow, page) == {"звания", "орды", "вождь"}
    assert words(wow, wow.ns.CleanText("<шепчет> Тише")) == {"шепчет", "тише"}


def test_exact_text_wins(index):
    idx, h = index
    assert find(idx, "Другое название", 7, "  " + TEXTS["second"].replace("\n", " \n ")) == (h["second"], "hash", 1.0)


def test_title_and_page_when_text_differs(index):
    idx, h = index
    book_hash, method, _ = find(idx, "Хроники падения", 2, "Глава вторая. Уцелевшие ушли на север, к Альтеракским горам.")
    assert (book_hash, method) == (h["second"], "title")


def test_title_of_entry_without_subtitles_is_trusted(index):
    idx, _ = index
    assert find(idx, "Безмолвная книга", 1, "Любой текст")[:2] == ("0d0d0d0d", "title")


def test_title_or_first_line_with_unrelated_text_is_rejected(index):
    idx, _ = index
    assert find(idx, "Хроники падения", 2, "Совсем другое письмо про урожай пшеницы.")[0] is None
    assert find(idx, None, 1, "Курдран Громовой Молот\nРецепт тушёной баранины с луком, морковью, чесноком, "
                "перцем, солью и свежей зеленью для праздника.")[0] is None


def test_page_out_of_range_is_not_a_title_match(index):
    idx, _ = index
    assert find(idx, "Хроники падения", 3, "Совсем другое письмо про урожай пшеницы.")[0] is None


def test_first_line_for_near_identical_plaques(index):
    idx, h = index
    book_hash, method, _ = find(idx, "Памятник", 1, "Курдран Громовой Молот\nЗнаменитый драконобоец и герой.")
    assert (book_hash, method) == (h["plaque"], "first_line")


def test_first_line_without_words_is_not_a_key(wow, index):
    idx, h = index
    idx.titles["^(HTML)"] = wow.table([h["second"]])
    page = '<HTML>\n<BODY>\n<H1 align="center">Глава вторая</H1><P>Выжившие ушли на север, к горам.</P>'
    assert find(idx, None, 1, page)[1] == "fuzzy"


def test_fuzzy_picks_similar_page_even_with_two_editions(index):
    idx, h = index
    book_hash, method, _ = find(idx, None, 1, "Глава первая. Пришла тьма, и город пал под натиском нежити Плети.")
    assert method == "fuzzy" and book_hash in (h["first"], h["edition"])


def test_fuzzy_refuses_when_two_different_pages_fit(index):
    idx, _ = index
    assert find(idx, None, 1, "Глава. Пришла тьма. Выжившие ушли, город пал.")[0] is None


def test_nothing_for_empty_text(index):
    idx, _ = index
    assert find(idx, None, 1, "")[0] is None
