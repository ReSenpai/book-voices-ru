"""Загрузка релизного ZIP на CurseForge: python tools/curseforge.py <zip> --notes release-notes.md

Только стандартная библиотека. Нужны переменные окружения CF_PROJECT_ID (номер проекта на CurseForge) и CF_API_KEY
(токен с authors.curseforge.com → API Tokens). Нет хотя бы одной — загрузка пропускается без ошибки: так релиз на
GitHub работает и до появления проекта на CurseForge.

Версия игры берётся из `## Interface` модуля (11509 → 1.15.9) и переводится в ID через /api/game/versions.
Зависимость: VoiceOver — обязательная (плеер).
API: https://support.curseforge.com/en/support/solutions/articles/9000197321-curseforge-api
"""
import argparse
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import MODULE, ROOT, module_version, toc_metadata  # noqa: E402

API = "https://wow.curseforge.com"
RELATIONS = [
    {"slug": "voiceover", "type": "requiredDependency"},  # VoiceOver (MrThinger) — плеер
]


def game_version(root: Path = ROOT) -> str:
    """Interface 11509 → «1.15.9»: так CurseForge называет версии Classic Era."""
    interface = toc_metadata(root / MODULE / f"{MODULE}.toc")["Interface"].split(",")[0].strip()
    major, rest = int(interface[:-4]), interface[-4:]
    return f"{major}.{int(rest[:2])}.{int(rest[2:])}"


def resolve_game_versions(versions: list, names: list) -> list:
    ids = []
    for name in names:
        found = [v["id"] for v in versions if v["name"] == name]
        if len(found) != 1:
            raise SystemExit(f"CurseForge: версия игры {name!r} найдена {len(found)} раз — нужна ровно одна")
        ids.append(found[0])
    return ids


def build_metadata(version: str, notes: str, game_version_ids: list) -> dict:
    return {
        "displayName": f"Book Voices RU {version}",
        "changelog": notes,
        "changelogType": "markdown",
        "gameVersions": game_version_ids,
        "releaseType": "release",
        "relations": {"projects": RELATIONS},
    }


def multipart(fields: dict, file_field: str, filename: str, data: bytes) -> tuple:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 "Content-Type: application/zip\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def credentials(env=os.environ):
    project, token = env.get("CF_PROJECT_ID", "").strip(), env.get("CF_API_KEY", "").strip()
    return (project, token) if project and token else None


def _request(url: str, token: str, body: bytes = None, content_type: str = None):
    headers = {"X-Api-Token": token, "User-Agent": "book-voices-ru-release"}
    if content_type:
        headers["Content-Type"] = content_type
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=1800) as response:
        return json.loads(response.read().decode("utf-8"))


def upload(zip_path: Path, notes: str, project: str, token: str) -> int:
    versions = _request(f"{API}/api/game/versions", token)
    metadata = build_metadata(module_version(), notes, resolve_game_versions(versions, [game_version()]))
    body, content_type = multipart({"metadata": json.dumps(metadata, ensure_ascii=False)}, "file", zip_path.name,
                                   zip_path.read_bytes())
    return _request(f"{API}/api/projects/{project}/upload-file", token, body, content_type)["id"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("zip", type=Path)
    parser.add_argument("--notes", type=Path, required=True, help="текст изменений (markdown), как для GitHub Release")
    args = parser.parse_args(argv)

    found = credentials()
    if not found:
        print("CurseForge: нет CF_PROJECT_ID или CF_API_KEY — загрузка пропущена")
        return
    file_id = upload(args.zip, args.notes.read_text(encoding="utf-8"), *found)
    print(f"CurseForge: файл {file_id} загружен в проект {found[0]}")


if __name__ == "__main__":
    main()
