"""Проверка аддона перед релизом: python tools/check.py [--strict] [--decode] [--require-new-version].

Только стандартная библиотека Python. Внешние программы необязательны локально и обязательны в CI (--strict):
luac5.1 — синтаксис Lua, ffmpeg — декодирование OGG: всех (--decode) или изменённых в PR (--decode-changed BASE).

Что проверяется:
- каждый файл из manifest.json на месте и совпадает по SHA-256, лишних OGG нет;
- поля TOC модуля совпадают с манифестом, таблица длительностей — с файлами;
- у каждой страницы из Books есть звук, у каждого звука — страница;
- в репозитории нет копии плеера VoiceOver: он зависимость, а не часть аддона;
- в текстовых файлах нет локальных путей, адресов почты и ключей;
- --require-new-version: если папки аддона изменились, версия в TOC должна быть новой (тега ещё нет).
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = "AI_VoiceOverData_BookVoices_RU"
PLAYER = "AI_VoiceOver"  # плеер VoiceOver: зависимость, в аддон не входит
SOUNDS = "generated/sounds/books"
LENGTH_TOLERANCE = 0.001
BOOK_ID_BASE = 300_000_000  # как в Bridge.lua и конвертере
TEXT_SUFFIXES = {".lua", ".toc", ".md", ".txt", ".json", ".yml", ".yaml", ".py", ".xml", ".sha256", ""}
# Что не должно попасть в публичный репозиторий: локальные пути, почта, приватные ключи и токены.
FORBIDDEN = [
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.I), "локальный путь Windows"),
    (re.compile(r"/home/[a-z_][\w-]*/|/Users/[A-Za-z][\w-]*/"), "локальный путь"),
    (re.compile(r"[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.]+"), "адрес почты"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "приватный ключ"),
    (re.compile(r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}"), "токен GitHub"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "API-ключ"),
]
# Файлы, где адреса почты — часть чужого текста (лицензии), а не наши данные.
FORBIDDEN_SKIP = {"LICENSE", "LICENSE-ASSETS.txt"}


def toc_metadata(path: Path) -> dict:
    meta = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            key, _, value = line[3:].partition(":")
            meta[key.strip()] = value.strip()
    return meta


def module_version(root: Path = ROOT) -> str:
    return toc_metadata(root / MODULE / f"{MODULE}.toc")["Version"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_module(root: Path) -> list:
    problems = []
    module = root / MODULE
    manifest = json.loads((module / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    for relative, info in sorted(files.items()):
        path = module / relative
        if not path.exists():
            problems.append(f"{MODULE}/{relative}: нет файла")
        elif sha256(path) != info["sha256"]:
            problems.append(f"{MODULE}/{relative}: SHA-256 не совпадает с манифестом")
    on_disk = {p.relative_to(module).as_posix() for p in (module / SOUNDS).glob("*")}
    problems += [f"{MODULE}/{r}: нет в манифесте" for r in sorted(on_disk - set(files))]

    meta = toc_metadata(module / f"{MODULE}.toc")
    for key, expected in (("Version", manifest["version"]), ("Interface", str(manifest["interface"])),
                          ("X-VoiceOver-DataModule-Priority", str(manifest["priority"])),
                          ("X-VoiceOver-Locale", manifest["locale"])):
        if meta.get(key) != expected:
            problems.append(f"{MODULE}.toc: {key} = {meta.get(key)!r}, в манифесте {expected!r}")

    table = (module / "generated" / "sound_length_table.lua").read_text(encoding="utf-8")
    lengths = {k: float(v) for k, v in re.findall(r'\["([^"]+)"\] = ([0-9.]+),', table)}
    expected = {Path(r).stem: info["duration_s"] for r, info in files.items()}
    problems += [f"таблица длительностей: лишний ключ {k}" for k in sorted(set(lengths) - set(expected))]
    problems += [f"таблица длительностей: нет ключа {k}" for k in sorted(set(expected) - set(lengths))]
    problems += [f"таблица длительностей: {k} = {lengths[k]}, файл {expected[k]}"
                 for k in sorted(set(lengths) & set(expected))
                 if not (lengths[k] > 0 and abs(lengths[k] - expected[k]) <= LENGTH_TOLERANCE)]
    return problems + check_books(module, lengths)


def book_sound_key(book_hash: str) -> str:
    """Файл страницы, как его строит Bridge.lua: номер = BOOK_ID_BASE + первые 7 знаков хэша."""
    return f"{BOOK_ID_BASE + int(book_hash[:7], 16)}-progress"


def check_books(module: Path, lengths: dict) -> list:
    """Страница из Books без звука (мостик найдёт её, а VoiceOver промолчит) и звук без страницы."""
    books = re.findall(r'^    \["([0-9a-f]{8})"\] = ', (module / "generated" / "books.lua").read_text(encoding="utf-8"),
                       re.M)
    expected = {book_sound_key(h): h for h in books}
    voiced = {k[2:] if k.startswith(("m-", "f-")) else k for k in lengths}
    return ([f"Books: у страницы {h} нет звука ({key})" for key, h in sorted(expected.items()) if key not in voiced]
            + [f"звук {key}: нет страницы в Books" for key in sorted(voiced - set(expected))])


def check_no_player(root: Path) -> list:
    """Плеер VoiceOver — зависимость, которую игрок ставит сам: его копия в репозитории попала бы в релиз
    и разошлась с README и NOTICE."""
    if (root / PLAYER).exists():
        return [f"{PLAYER}/: плеер VoiceOver не входит в аддон — уберите папку (это зависимость, см. README)"]
    return []


def _repo_files(root: Path) -> list:
    """Файлы репозитория: в git — только отслеживаемые (в CI в рабочую копию ставятся инструменты вроде
    .lua/bin/luac, они не публикуются); вне git (временные копии) — всё дерево."""
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    inside = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
    if proc.returncode == 0 and inside.returncode == 0 and Path(inside.stdout.strip()).resolve() == root.resolve():
        return sorted(root / name for name in proc.stdout.decode("utf-8").split("\0") if name)
    return sorted(p for p in root.rglob("*") if p.is_file())


def check_text(root: Path) -> list:
    problems = []
    for path in _repo_files(root):
        relative = path.relative_to(root)
        if relative.parts[0] in {".git", "dist"} or path.name in FORBIDDEN_SKIP or not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:  # бинарный файл
            continue
        text = data.decode("utf-8", errors="replace")
        for pattern, what in FORBIDDEN:
            match = pattern.search(text)
            if match:
                problems.append(f"{relative.as_posix()}: {what}: {match.group(0)[:40]}")
    return problems


def check_lua(root: Path, strict: bool) -> list:
    luac = shutil.which("luac5.1") or shutil.which("luac")
    if not luac:
        return ["нет luac5.1 — синтаксис Lua не проверен"] if strict else []
    problems = []
    for path in sorted((root / MODULE).rglob("*.lua")):
        proc = subprocess.run([luac, "-p", str(path)], capture_output=True, text=True)
        if proc.returncode:
            problems.append(f"{path.relative_to(root).as_posix()}: {proc.stderr.strip()[:200]}")
    return problems


def _decode(path: Path):
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    return proc.stderr.strip().splitlines()[0][:200] if (proc.returncode or proc.stderr.strip()) else None


def check_decode(root: Path, files=None) -> list:
    if not shutil.which("ffmpeg"):
        return ["нет ffmpeg — декодирование не проверено"]
    files = sorted((root / MODULE / SOUNDS).glob("*.ogg")) if files is None else files
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [f"{p.relative_to(root).as_posix()}: не декодируется: {e}" for p, e in zip(files, pool.map(_decode, files)) if e]


def changed_audio(root: Path, base: str) -> list:
    """OGG, добавленные или изменённые относительно base: на PR декодируем только их — остальные байты
    не менялись (это доказывают хэши манифеста) и уже декодировались, когда попали в main."""
    names = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AMR", f"{base}...HEAD", "--",
                            f"{MODULE}/{SOUNDS}"], cwd=root, capture_output=True, text=True, check=True).stdout.split()
    return sorted(root / name for name in names if name.endswith(".ogg"))


def check_new_version(root: Path, base: str) -> list:
    version = module_version(root)
    tags = subprocess.run(["git", "tag", "--list", f"v{version}"], cwd=root, capture_output=True, text=True).stdout
    if not tags.strip():
        return []
    changed = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD", "--", MODULE],
                             cwd=root, capture_output=True, text=True).stdout.split()
    if changed:
        return [f"аддон изменён ({len(changed)} файлов), а версия {version} уже выпущена — поднимите Version в "
                f"{MODULE}.toc и manifest.json и добавьте раздел в CHANGELOG.md"]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="CI: внешние проверки обязательны")
    parser.add_argument("--decode", action="store_true", help="декодировать каждый OGG через ffmpeg")
    parser.add_argument("--decode-changed", metavar="BASE", help="PR: декодировать только OGG, изменённые от BASE")
    parser.add_argument("--require-new-version", metavar="BASE", help="ветка сравнения для PR, например origin/main")
    parser.add_argument("--print-version", action="store_true")
    args = parser.parse_args(argv)
    if args.print_version:
        print(module_version())
        return

    problems = check_module(ROOT) + check_no_player(ROOT) + check_text(ROOT) + check_lua(ROOT, args.strict)
    if args.decode:
        problems += check_decode(ROOT)
    elif args.decode_changed:
        changed = changed_audio(ROOT, args.decode_changed)
        print(f"декодирую изменённые OGG: {len(changed)}")
        problems += check_decode(ROOT, changed) if changed else []
    if args.require_new_version:
        problems += check_new_version(ROOT, args.require_new_version)
    if problems:
        print("\n".join(f"✗ {p}" for p in problems))
        print(f"проблем: {len(problems)}")
        sys.exit(1)
    print(f"Book Voices RU {module_version()}: проблем нет")


if __name__ == "__main__":
    main()
