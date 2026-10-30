"""Мостик: открыта страница книги → реплика в очереди настоящего VoiceOver 1.4.5 (SoundQueue, DataModules)."""
import pytest

from tests.wow import ADDON, Wow

PAGE1 = "Глава первая.\nПришла тьма, и город пал под натиском нежити."
PAGE2 = "Глава вторая.\nВыжившие ушли на север, к горам Альтерака."
SILENT = "Счёт за постой: три серебряных, ужин и овёс для лошади."
SOUNDS = rf"Interface\AddOns\{ADDON}\generated\sounds\books"
BOOK_ID_BASE = 300_000_000  # как в конвертере (voru/catquest/books_build.py)


def book_id(book_hash):
    return BOOK_ID_BASE + int(book_hash[:7], 16)


def key(book_hash, gender=None):
    return f"{gender + '-' if gender else ''}{book_id(book_hash)}-progress"


def install(wow, locale="ruRU"):
    wow.set_locale(locale)
    wow.g._present(ADDON, 200)
    wow.run_addon_file("Module.lua")
    module = wow.g[ADDON]
    if module is not None:
        h1, h2 = wow.g.CatHash(PAGE1), wow.g.CatHash(PAGE2)
        module.Books = wow.table({h1: PAGE1.replace("\n", " "), h2: PAGE2.replace("\n", " "), "0e0e0e0e": False})
        module.BookTitles = wow.table({"Хроники падения": [h1, h2], 'Дневник "Ворона"': ["0e0e0e0e"]})
        module.SoundLengthLookupByFileName = wow.table({key(h1, "m"): 10.0, key(h1, "f"): 11.0, key(h2): 8.0,
                                                        key("0e0e0e0e"): 5.0})
    wow.run_addon_file("TextMatch.lua")
    wow.run_addon_file("Bridge.lua")
    return module


@pytest.fixture
def wow():
    w = Wow()
    w.lua.execute("""function CatHash(text)
        local h = 0
        for i = 1, #text do h = (h * 31 + text:byte(i)) % 4294967296 end
        return string.format("%08x", h)
    end""")
    return w


@pytest.fixture
def book(wow):
    install(wow)
    return wow


def hashes(wow):
    return wow.g.CatHash(PAGE1), wow.g.CatHash(PAGE2)


def files(wow):
    return [s.fileName for s in wow.queue()]


def add_quest(wow):
    wow.vo.SoundQueue.sounds[len(wow.vo.SoundQueue.sounds) + 1] = wow.table(
        {"questID": 947, "fileName": "947-accept", "id": 99, "event": 1, "length": 5.0,
         "filePath": r"Interface\AddOns\Quests\947-accept.ogg"})


def test_module_registers_with_voiceover(book):
    module = book.vo.DataModules.GetModule(book.vo.DataModules, ADDON)
    assert module is not None
    assert module.GetSoundPath(module, "m-300000001-progress", book.vo.Enums.SoundEvent.QuestProgress) == \
        r"generated\sounds\books\m-300000001-progress.ogg"


def test_voiced_page_plays_through_voiceover_queue(book):
    h1, _ = hashes(book)
    book.open_page("Хроники падения", 1, PAGE1, has_next=True)

    [sound] = book.queue()
    assert sound.fileName == key(h1, "m")
    assert sound.name == "Хроники падения"
    assert sound.title == "Хроники падения, стр. 1"
    assert sound.length == 10.0
    assert book.played() == [rf"{SOUNDS}\{key(h1, 'm')}.ogg"]


def test_page_is_a_separate_clickable_line_in_the_queue(book):
    """Очередь VoiceOver показывает строкой (и удаляет кликом) только квестовые события с названием;
    реплики Gossip в ней свёрнуты. Номер записи — далеко за номерами квестов."""
    h1, _ = hashes(book)
    book.open_page("Хроники падения", 1, PAGE1)

    sound = book.queue()[0]
    assert book.vo.Enums.SoundEvent.IsQuestEvent(book.vo.Enums.SoundEvent, sound.event)
    assert sound.questID == book_id(h1) >= BOOK_ID_BASE
    book.vo.SoundQueue.RemoveSoundFromQueue(book.vo.SoundQueue, sound)  # так делает клик по строке
    assert book.queue() == []


def test_single_page_title_has_no_page_number(book):
    book.open_page('Дневник "Ворона"', 1, "Сегодня снова шёл дождь.")

    assert book.queue()[0].title == 'Дневник "Ворона"'


def test_female_character_hears_female_variant(book):
    h1, _ = hashes(book)
    book.set_player_sex(3)

    book.open_page("Хроники падения", 1, PAGE1)

    assert files(book) == [key(h1, "f")]


def test_page_without_gender_variants(book):
    _, h2 = hashes(book)

    book.open_page("Хроники падения", 2, PAGE2)

    assert files(book) == [key(h2)]


def test_unvoiced_page_is_silent(book):
    book.open_page("Счёт", 1, SILENT)

    assert book.queue() == []


def test_turning_page_queues_next_page_after_current(book):
    h1, h2 = hashes(book)
    book.open_page("Хроники падения", 1, PAGE1, has_next=True)
    handle = book.queue()[0].handle

    book.open_page("Хроники падения", 2, PAGE2)

    assert files(book) == [key(h1, "m"), key(h2)]
    assert not book.stopped(handle)  # первая страница доигрывает
    assert len(book.played()) == 1
    book.finish_sound()
    assert files(book) == [key(h2)] and len(book.played()) == 2


def test_turning_pages_back_and_forth_adds_no_duplicates(book):
    h1, h2 = hashes(book)
    for page, text in ((1, PAGE1), (2, PAGE2), (1, PAGE1), (2, PAGE2), (1, PAGE1)):
        book.open_page("Хроники падения", page, text, has_next=page == 1)

    assert files(book) == [key(h1, "m"), key(h2)]
    assert len(book.played()) == 1


def test_turning_to_unvoiced_page_keeps_playing(book):
    book.open_page("Хроники падения", 1, PAGE1)

    book.open_page("Хроники падения", 3, SILENT)

    assert len(book.queue()) == 1


def test_page_after_finished_sound_plays_again(book):
    book.open_page("Хроники падения", 1, PAGE1)
    book.finish_sound()

    book.open_page("Хроники падения", 1, PAGE1)

    assert len(book.queue()) == 1 and len(book.played()) == 2


def test_book_joins_queue_after_quests(book):
    """Книга, открытая во время квеста, встаёт следом за ним (реплика с questID не отсекается)."""
    h1, _ = hashes(book)
    add_quest(book)

    book.open_page("Хроники падения", 1, PAGE1)

    assert files(book) == ["947-accept", key(h1, "m")]


def test_closing_book_keeps_playing_by_default(book):
    book.open_page("Хроники падения", 1, PAGE1)

    book.fire("ITEM_TEXT_CLOSED")

    assert len(book.queue()) == 1


def test_closing_book_stops_its_pages_when_voiceover_says_so(book):
    book.vo.Addon.db.profile.Audio.StopAudioOnDisengage = True
    book.open_page("Хроники падения", 1, PAGE1)
    book.open_page("Хроники падения", 2, PAGE2)
    add_quest(book)

    book.fire("ITEM_TEXT_CLOSED")

    assert files(book) == ["947-accept"]


def test_logout_and_reload_stop_the_page(book):
    book.open_page("Хроники падения", 1, PAGE1)
    handle = book.queue()[0].handle

    book.fire("PLAYER_LOGOUT")

    assert book.queue() == [] and book.stopped(handle)


def test_pause_does_not_survive_reload(book):
    """Пауза VoiceOver сохраняется у персонажа, а очередь после /reload пуста — открытая книга молчала бы."""
    book.open_page("Хроники падения", 1, PAGE1)
    book.vo.SoundQueue.PauseQueue(book.vo.SoundQueue)

    book.fire("PLAYER_LOGOUT")

    assert book.vo.Addon.db.char.IsPaused is False


def test_emptied_queue_is_not_left_paused(book):
    """Пауза, потом очередь очищена целиком (клики по строкам) — открытая затем книга или квест играют сразу."""
    book.open_page("Хроники падения", 1, PAGE1, has_next=True)
    book.open_page("Хроники падения", 2, PAGE2)
    book.vo.SoundQueue.PauseQueue(book.vo.SoundQueue)

    book.vo.SoundQueue.RemoveAllSoundsFromQueue(book.vo.SoundQueue)
    assert book.vo.Addon.db.char.IsPaused is False

    book.open_page("Хроники падения", 1, PAGE1)
    assert len(book.played()) == 2


def test_pause_stays_while_something_is_queued(book):
    book.open_page("Хроники падения", 1, PAGE1, has_next=True)
    book.open_page("Хроники падения", 2, PAGE2)
    book.vo.SoundQueue.PauseQueue(book.vo.SoundQueue)

    book.vo.SoundQueue.RemoveSoundFromQueue(book.vo.SoundQueue, book.queue()[1])

    assert book.vo.Addon.db.char.IsPaused is True


def test_book_without_title_still_plays(book):
    _, h2 = hashes(book)

    book.open_page(None, 2, PAGE2)

    [sound] = book.queue()
    assert sound.fileName == key(h2) and sound.name == "Книга" and sound.title == "Книга, стр. 2"


def test_other_locale_stays_silent(wow):
    install(wow, locale="enUS")

    wow.open_page("Хроники падения", 1, PAGE1)

    assert wow.vo.DataModules.GetModule(wow.vo.DataModules, ADDON) is None
    assert wow.queue() == []


def test_unknown_voiceover_api_stays_silent(wow):
    wow.vo.SoundQueue.RemoveSoundFromQueue = None
    install(wow)

    wow.open_page("Хроники падения", 1, PAGE1)

    assert wow.queue() == []
