"""Сборка релизного ZIP: python tools/package.py [--notes notes.md] → dist/book-voices-ru-v<версия>.zip

В архиве одна папка для Interface/AddOns — модуль озвучки AI_VoiceOverData_BookVoices_RU (звук и мостик), в который кладутся
README, NOTICE и лицензии. Плеер VoiceOver игрок ставит отдельно (зависимость). Порядок файлов и даты
фиксированы — одинаковое содержимое даёт одинаковый архив.
--notes: раздел текущей версии из CHANGELOG.md — текст для страницы релиза.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import MODULE, ROOT, module_version  # noqa: E402

NAME = "book-voices-ru"
EXTRA = ["README.md", "NOTICE", "LICENSE", "LICENSE-ASSETS.txt", "THIRD-PARTY.md", "CHANGELOG.md"]
# В модуле уже есть свой короткий LICENSE-ASSETS.txt (атрибуция от конвертера) — полный текст лицензии
# из корня репозитория кладётся рядом под своим именем.
ARCHIVE_NAMES = {"LICENSE-ASSETS.txt": "CC-BY-NC-SA-4.0.txt"}
TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def changelog_section(version: str, root: Path = ROOT) -> str:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise SystemExit(f"в CHANGELOG.md нет раздела {version}")
    return match.group(1).strip() + "\n"


def entries(root: Path):
    for path in sorted((root / MODULE).rglob("*")):
        if path.is_file():
            yield path.relative_to(root).as_posix(), path
    for name in EXTRA:
        yield f"{MODULE}/{ARCHIVE_NAMES.get(name, name)}", root / name


def build(root: Path = ROOT, out_dir: Path = None) -> Path:
    version = module_version(root)
    out_dir = out_dir or root / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{NAME}-v{version}.zip"
    items = list(entries(root))
    names = [arcname for arcname, _ in items]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise SystemExit(f"в архив дважды попадает: {', '.join(duplicates)}")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for arcname, path in items:
            info = zipfile.ZipInfo(arcname, TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED if path.suffix == ".ogg" else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=Path, help="записать заметки релиза из CHANGELOG.md")
    args = parser.parse_args(argv)
    target = build()
    if args.notes:
        args.notes.write_text(changelog_section(module_version()), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
