"""Собранный модуль целиком (B4): файлы из TOC в порядке клиента, настоящие таблицы, очередь VoiceOver 1.4.5."""
import pytest

from tests.test_bridge import key
from tests.wow import ADDON, ADDON_DIR, Wow

pytestmark = pytest.mark.skipif(not (ADDON_DIR / "generated" / "books.lua").exists(),
                                reason="модуль не собран (python -m voru.catquest books-build)")


@pytest.fixture(scope="module")
def wow():
    w = Wow()
    w.install_module()
    return w


@pytest.fixture(autouse=True)
def empty_queue(wow):
    yield
    wow.fire("PLAYER_LOGOUT")


def books(wow):
    return dict(wow.g[ADDON].Books.items())


def lengths(wow):
    return dict(wow.g[ADDON].SoundLengthLookupByFileName.items())


def test_module_is_registered_with_tables(wow):
    module = wow.vo.DataModules.GetModule(wow.vo.DataModules, ADDON)

    assert len(list(module.Books.keys())) > 1000 and len(list(module.BookTitles.keys())) > 300


def test_every_page_has_its_sound(wow):
    have = lengths(wow)

    assert all(key(h) in have or key(h, "m") in have for h in books(wow))


def test_real_page_with_newlines_plays(wow):
    """Субтитры записи склеены пробелами, а игра показывает страницу со строками — находит нечёткий поиск."""
    have = lengths(wow)
    text = next(t for h, t in sorted(books(wow).items()) if t and key(h) in have and len(t) > 200)

    wow.open_page("Какая-то книга", 1, text.replace(". ", ".\n"))

    [sound] = wow.queue()
    found = next(h for h in books(wow) if key(h) == sound.fileName)
    # та же страница или её другая редакция (в паке бывают обе)
    assert wow.ns.Jaccard(wow.ns.Words(books(wow)[found]), wow.ns.Words(text)) >= 0.7
    assert sound.filePath == rf"Interface\AddOns\{ADDON}\generated\sounds\books\{sound.fileName}.ogg"
    assert (ADDON_DIR / "generated" / "sounds" / "books" / f"{sound.fileName}.ogg").exists()


def test_gendered_page_follows_player_sex(wow):
    have = lengths(wow)
    book_hash, text = next((h, t) for h, t in sorted(books(wow).items()) if t and key(h, "f") in have)
    wow.set_player_sex(3)

    wow.open_page(None, 1, text)

    assert wow.queue()[0].fileName == key(book_hash, "f")
    wow.set_player_sex(2)
