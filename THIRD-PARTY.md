# Сторонние компоненты

В аддоне две чужие части: озвучка (распространяется без изменений и по условиям автора) и адаптированный код
поиска страниц из CatQuest.

| Компонент | Где лежит | Автор | Лицензия |
| --- | --- | --- | --- |
| Озвучка книг CatQuest Books 0.6.4 | `AI_VoiceOverData_BookVoices_RU/generated/sounds/books/` | Cathey (daniilcathey) | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), текст — `LICENSE-ASSETS.txt` |
| Код CatQuest 0.7.1 (CleanText, TextHash, LowerRu, Normalize, Words, Jaccard) | `AI_VoiceOverData_BookVoices_RU/TextMatch.lua` | daniilcathey | MIT, текст ниже |

Это не значит, что автор CatQuest и CatQuest Books одобряет этот проект.

## Зависимости, которые ставятся отдельно

В аддон не входят и распространяются своими авторами:

| Что | Авторы | Лицензия | Где взять |
| --- | --- | --- | --- |
| VoiceOver 1.4.5+ (плеер, обязателен) | mrthinger, xvwyh и [соавторы](https://github.com/mrthinger/wow-voiceover/graphs/contributors) | [Unlicense](https://unlicense.org/) | [CurseForge](https://www.curseforge.com/wow/addons/voiceover), [GitHub](https://github.com/mrthinger/wow-voiceover/releases/tag/v1.4.5) |

Book Voices RU проверена с VoiceOver 1.4.5 (`AI_VoiceOver-WoW_BlizzClassic-v1.4.5.zip`, SHA-256
`47870e96bef68a2cf71d9bf9539d28d7695f8fd696032f7bccd5aa3551e0c2c4`); тесты мостика (`tests/`) запускаются на
исходниках из этого архива.

## Уведомление MIT (CatQuest)

```
MIT License

Copyright (c) 2026 daniilcathey

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
