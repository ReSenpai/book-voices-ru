# Как обновляется аддон

Озвучку, таблицы и манифест модуля здесь руками не правят: их собирает конвертер (`python -m voru.catquest`),
сделанный на основе [русского VoiceOver](https://github.com/the-homeless-god/wow-voiceover). Код мостика
(`Module.lua`, `TextMatch.lua`, `Bridge.lua` в папке модуля) — правится здесь, конвертер копирует его в сборку.

1. Код мостика — по тестам: `python -m pytest tests` (нужны `pytest` и `lupa`; исходники VoiceOver 1.4.5 — в
   переменной `VOICEOVER_DIR`, папка `AI_VoiceOver` из
   [его релиза](https://github.com/mrthinger/wow-voiceover/releases/tag/v1.4.5)).
2. В репозитории конвертера: `books-build --code <папка модуля здесь> --version <новая>` → `verify` →
   `export --repo <рабочая копия этого репозитория>`.
3. Здесь: раздел новой версии в `CHANGELOG.md`, ветка, pull request.
4. Проверки PR (`.github/workflows/checks.yml`) должны быть зелёными: тесты мостика, хэши, таблицы, страницы ↔ звук,
   Lua, декодирование новых и изменённых OGG, нет копии плеера VoiceOver, нет личных данных, версия новая.
5. После принятия PR в `main` релиз собирается сам (`.github/workflows/release.yml`).

Локально: `python tools/check.py` (быстро), `python tools/check.py --decode` (с ffmpeg), `python tools/package.py`.
