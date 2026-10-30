# План: озвучка книг для VoiceOver

Цель — русская озвучка книг, записок и табличек в WoW Classic Era (ruRU, 1.15.9) через тот же плеер VoiceOver,
что играет квесты Quest Voices RU: одно окно, одна очередь, одни настройки. Звук — из CatQuest Books
(Cathey, CC BY-NC-SA 4.0), переносится байт в байт, как квесты.

## Решение: свой плеер или VoiceOver

Разбор VoiceOver 1.4.5 (`AI_VoiceOver`, 28.10.2026):

- Аддон живёт в глобальном окружении `VoiceOver` (`Environment.lua`): снаружи доступны `VoiceOver.SoundQueue`,
  `VoiceOver.Enums`, `VoiceOver.DataModules`.
- `SoundQueue:AddSoundToQueue(soundData)` принимает любую реплику; файл ищет `DataModules:PrepareSound`.
- Свой тип события добавить нельзя (`getFileNameForEvent` — local), но подходит `Enums.SoundEvent.Gossip`:
  при `unitIsObjectOrItem = true` поиск идёт по `module.GossipLookupByObjectName[имя][текст] = файл`
  с нечётким сравнением текста (`FuzzySearchBestKeys`) — другая редакция перевода страницы всё равно найдётся.
- Пол персонажа — префиксы `m-`/`f-` в `SoundLengthLookupByFileName`, как у квестов.
- Окно VoiceOver покажет имя (название книги) и текст, очередь и пауза работают.

Ограничения VoiceOver, которые придётся учесть:

- реплика без `questID` не встаёт в очередь, пока там есть квест (книга во время озвучки квеста промолчит);
- дубли отсекаются по имени файла;
- внутренний API может поменяться в новой версии VoiceOver — мостик проверяет версию и молчит, если она незнакома.

**Вывод:** свой плеер не нужен. Нужен модуль данных VoiceOver (звук + таблицы) и маленький мостик
(~100 строк Lua): открыл страницу → реплика в очередь VoiceOver, перелистнул → прошлая страница убирается,
следующая ставится, закрыл книгу → звук стоп. Если упрёмся в ограничения очереди — тогда свой плеер,
с идеями из CatQuest (MIT).

## Что берём у CatQuest (идеи, код MIT)

- Поиск страницы: хэш очищенного текста → название + номер страницы (`Titles.lua`) → первая строка
  (памятники с почти одинаковым текстом) → самая похожая страница.
- Очистка текста перед сравнением: цвета `|c…|r`, иконки, ссылки, `<…>`, пробелы.
- Остановка звука на `ITEM_TEXT_CLOSED` и при `/reload`/выходе (`PLAYER_LOGOUT`).

Если копируем код дословно — сохраняем уведомление MIT (копирайт daniilcathey) в `THIRD-PARTY.md`.

## Вход

- CatQuest Books 0.6.4 (CurseForge file 9233730, sha256 `efe9389e…3e4b`): 2317 записей, ~18.6 ч, 82 с вариантами
  по полу; рассказчик (1643) и голоса авторов писем. Индекс `Index.lua` (`books[хэш] = {d, v, g, c}`),
  `Titles.lua` (`bookTitles[название] = {хэш стр.1, …}`, `^первая строка`), `index_books.json` (модель `m`).
- vmangos `page_text` + `locales_page_text` (ruRU — `Text_loc8`): 1257 страниц, 426 книг, русских 1206.
  Хэш совпал с CatQuest у 979 (81%). Остальные записи CatQuest — лор мест, книги Forever, другие редакции.
- Названия для `GossipLookupByObjectName`: игра отдаёт `ItemTextGetItem()` — имя предмета или объекта.
  В vmangos: `item_template.page_text` + `locales_item.name_loc8`, `gameobject_template` (type 9, data0 — первая
  страница) + `locales_gameobject.name_loc8`.

## Шаги

- [x] B0. Папка и репозиторий `book-voices` (локально; GitHub — когда будет что показать).
- [x] B1. Reader CatQuest Books + lock + inspect — в конвертере (`classic-wow-voiceover`, `voru/catquest/books.py`,
      lock `config/catquest_books.lock.yaml`). `python -m voru.catquest books --source <zip> --out <json>`:
      2317 записей, 2399 файлов, 82 с вариантами по полу, 52 без субтитров, 699 названий, ~18.6 ч, 31 голос.
- [x] B2. Поиск страницы + покрытие на vmangos — конвертер: `voru/corpus/sql_dump.py` (строки таблиц из дампа без
      MySQL), `voru/corpus/book_pages.py` (страницы, номер в цепочке, русские названия предметов/объектов),
      `voru/catquest/books_match.py` (алгоритм — образец для Lua-мостика).
      `python -m voru.catquest books-match --source <Books.zip> --catquest <CatQuest.zip> --dump <mangos.sql> --report work/catquest/books-match`
      Итог 29.10.2026: книжных записей 1387 (лор исключён — 930, по текстам `LoreZones.lua` CatQuest), ~9.9 ч,
      1469 файлов, 182 МБ. Из 1206 русских страниц vmangos находят озвучку 1191 (98.8%): hash 979, title 143,
      fuzzy 63, first_line 6; нет — 15 (дневник син'дорай, записки Нефариана, 2 HTML-страницы). 51 страница без перевода.
      Исправлены ловушки CatQuest: «^(HTML)»/«^$N!» не ключи (нет слов); title/first_line принимаются, только если
      текст похож (≥ 0.2) или у записи нет субтитров; теги HTML не считаются словами; две редакции одной страницы
      (похожесть ≥ 0.7) не мешают нечёткому поиску. Страница прослушивания не нужна: спорная связка одна
      (2858 «С вечной любовью», 0.23, по виду верная); проверка — в игре.
      **Решение по дизайну:** поиск идёт во время игры по тексту клиента (Blizzard меняла перевод — vmangos только
      оценка). Модуль везёт все 1387 записей (и новые редакции), их тексты для сравнения и Titles; мостик сам находит
      страницу и подставляет в `GossipLookupByObjectName[название][текст]` найденную запись — тогда VoiceOver
      гарантированно возьмёт её файл.
- [x] B3. Мостик (Lua) внутри модуля — один аддон `AI_VoiceOverData_BookVoices_RU`: `Module.lua` (регистрация,
      locale guard, путь `generated\soundsooks\<файл>.ogg`), `TextMatch.lua` (поиск страницы — копия алгоритма
      `books_match.py`), `Bridge.lua`. Тесты: `../classic-wow-voiceover/.venv/Scripts/python -m pytest tests` (lupa,
      настоящие SoundQueue/DataModules VoiceOver 1.4.5 из `VOICEOVER_DIR`, по умолчанию копия в конвертере).
      Сверка с Python на паке 0.6.4 и страницах vmangos: 1206 из 1206 решений одинаковы.
      **Переделка 30.10.2026 по проверке в игре:** страница идёт не как Gossip, а как `QuestProgress` с номером записи
      `300 000 000 + первые 7 знаков хэша` вместо questID (файл `[m-|f-]<номер>-progress`). Gossip в очереди VoiceOver
      свёрнут (`HIDE_GOSSIP_OPTIONS`) и не встаёт за квестами; квестовое событие — строка «Название, стр. N», клик
      убирает, встаёт за квестами. Перелистнул — новая страница в очередь следом, дубли отсекает VoiceOver (по файлу).
      `ITEM_TEXT_CLOSED` убирает страницы книг по настройке VoiceOver «StopAudioOnDisengage»; `PLAYER_LOGOUT` глушит их
      и снимает паузу VoiceOver (она сохранялась у персонажа — после /reload пустая очередь стояла на паузе).
      Очередь опустела (всё убрано кликами) — пауза VoiceOver снимается (хук на `RemoveSoundFromQueue`; касается и квестов).
      Побочное: пока в очереди страница книги, Gossip NPC в неё не встаёт (как при квесте).
- [x] B4. Build + verify модуля `AI_VoiceOverData_BookVoices_RU` — конвертер: `voru/catquest/books_build.py`
      (`python -m voru.catquest books-build --source <Books.zip> --catquest <CatQuest.zip> --code ../book-voices/AI_VoiceOverData_BookVoices_RU --out work/catquest/books-module --version 0.1.0`),
      затем `verify --pack …` и `export --pack … --repo ../book-voices`. verify теперь общий: папка звука из манифеста,
      Lua из TOC с аргументами аддона, сверка `Books` ↔ звук. Итог 30.10.2026: 1387 страниц, 1469 файлов (82 с полом,
      52 без субтитров), 10.63 ч, 188 МБ, лор исключён (930); 1469/1469 декодируются, проблем нет. В `book-voices`
      сквозной тест собранного модуля (`tests/test_module.py`). Проверено в игре 30.10.2026 (после переделки мостика:
      очередь, перелистывание, клик по строке, книга во время квеста, пауза).
- [x] B5. Репозиторий по образцу quest-voices-ru: README (примеры — `docs/samples/*.mp4`, 8 голосов), CHANGELOG,
      NOTICE, THIRD-PARTY (MIT CatQuest), CONTRIBUTING, LICENSE (GPL v3), LICENSE-ASSETS (CC BY-NC-SA 4.0);
      `tools/check.py` (+ сверка Books ↔ звук), `package.py` (→ `dist/book-voices-ru-v<версия>.zip`, 192 МБ),
      `curseforge.py`; workflows checks (+ Lua-тесты мостика на VoiceOver 1.4.5 из релиза, SHA-256 закреплён) / release /
      curseforge. GitHub: ReSenpai/book-voices-ru (публичный, About и темы); 30.10.2026 первый push → релиз v0.1.0
      (ZIP 192 МБ), checks на main зелёные (26 + 39 тестов, gitleaks), защита main как у квестов (PR + check, и для
      админа). Ролики примеров в README — ссылки user-attachments (сверены с docs/samples по SHA-256).

## Не входит

- Лор мест (930 рассказов CatQuest при входе в зону) — не книги и не реплика NPC; отдельно (решение 29.10.2026).

## Открытые вопросы

- Имя аддона: «Book Voices RU», репозиторий `book-voices-ru`.
- Один аддон (мостик + звук) или два — пока один (B3); разделить можно позже без смены кода мостика.
