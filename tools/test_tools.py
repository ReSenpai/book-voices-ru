"""Тесты проверки и упаковки: python -m unittest discover tools"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import curseforge  # noqa: E402
import package  # noqa: E402

MODULE, SOUNDS = check.MODULE, check.SOUNDS


def make_repo(root: Path, version="0.1.0"):
    """Маленький аддон с тем же устройством, что и настоящий."""
    module = root / MODULE
    (module / SOUNDS).mkdir(parents=True)
    (module / "generated").mkdir(exist_ok=True)
    audio = b"OggS-test"
    (module / SOUNDS / "300000001-progress.ogg").write_bytes(audio)
    (module / "generated" / "sound_length_table.lua").write_text(
        f'if not {MODULE} then return end\n{MODULE}.SoundLengthLookupByFileName = {{\n    ["300000001-progress"] = 2.5,\n}}\n',
        encoding="utf-8")
    # страница книги 00000010 → номер 300000000 + 0x0000001 → файл 300000001-progress (как Bridge.lua)
    (module / "generated" / "books.lua").write_text(
        f'if not {MODULE} then return end\n{MODULE}.Books = {{\n    ["00000010"] = "Глава первая.",\n}}\n',
        encoding="utf-8")
    (module / f"{MODULE}.toc").write_text(
        f"## Interface: 11509\n## Version: {version}\n## X-VoiceOver-DataModule-Priority: 200\n"
        "## X-VoiceOver-Locale: ruRU\n\nModule.lua\n", encoding="utf-8")
    manifest = {"version": version, "interface": 11509, "priority": 200, "locale": "ruRU",
                "files": {f"{SOUNDS}/300000001-progress.ogg": {"sha256": hashlib.sha256(audio).hexdigest(), "duration_s": 2.5}}}
    (module / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (module / "LICENSE-ASSETS.txt").write_text("Озвучка: CC BY-NC-SA 4.0\n", encoding="utf-8")  # как от конвертера
    for name in package.EXTRA:
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Изменения\n\n## {version} — 2026-10-23\n\n- Первый релиз.\n\n"
                                       "## 0.0.1\n\n- Старое.\n", encoding="utf-8")
    return root


class Base(unittest.TestCase):
    def setUp(self):
        self.root = make_repo(Path(tempfile.mkdtemp()))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class CheckTest(Base):
    def test_clean_repo(self):
        self.assertEqual(check.check_module(self.root) + check.check_no_player(self.root) + check.check_text(self.root), [])

    def test_changed_audio(self):
        (self.root / MODULE / SOUNDS / "300000001-progress.ogg").write_bytes(b"other")
        self.assertTrue(any("SHA-256" in p for p in check.check_module(self.root)))

    def test_extra_audio(self):
        (self.root / MODULE / SOUNDS / "300000002-progress.ogg").write_bytes(b"x")
        self.assertTrue(any("нет в манифесте" in p for p in check.check_module(self.root)))

    def test_page_without_sound(self):
        books = self.root / MODULE / "generated" / "books.lua"
        books.write_text(books.read_text(encoding="utf-8").replace(
            '    ["00000010"]', '    ["0000002a"] = false,\n    ["00000010"]'), encoding="utf-8")
        self.assertTrue(any("0000002a" in p and "нет звука" in p for p in check.check_module(self.root)))

    def test_sound_without_page(self):
        books = self.root / MODULE / "generated" / "books.lua"
        books.write_text(books.read_text(encoding="utf-8").replace('["00000010"]', '["00000020"]'), encoding="utf-8")
        found = check.check_module(self.root)
        self.assertTrue(any("300000001-progress" in p and "нет страницы" in p for p in found))

    def test_version_mismatch(self):
        toc = self.root / MODULE / f"{MODULE}.toc"
        toc.write_text(toc.read_text(encoding="utf-8").replace("0.1.0", "0.2.0"), encoding="utf-8")
        self.assertTrue(any("Version" in p for p in check.check_module(self.root)))

    def test_bundled_player_is_caught(self):
        """Плеер VoiceOver — зависимость, в аддон не входит: его копия в репозитории — ошибка."""
        (self.root / "AI_VoiceOver").mkdir()
        (self.root / "AI_VoiceOver" / "AI_VoiceOver.toc").write_text("## Title: VoiceOver\n", encoding="utf-8")
        self.assertEqual(len(check.check_no_player(self.root)), 1)

    def test_personal_data_is_caught(self):
        # образцы склеены из частей — иначе check_text нашёл бы их в самом этом файле
        for leak in ("C:" + "\\Users\\someone\\x", "mail me: someone" + "@example.com",
                     "-----BEGIN RSA " + "PRIVATE KEY-----", "ghp_" + "a" * 30):
            (self.root / "README.md").write_text(leak, encoding="utf-8")
            self.assertTrue(check.check_text(self.root), leak)

    def test_noreply_address_is_fine(self):
        (self.root / "README.md").write_text("123+name@users.noreply.github.com", encoding="utf-8")
        self.assertEqual(check.check_text(self.root), [])

    def test_strict_requires_luac(self):
        if shutil.which("luac5.1") or shutil.which("luac"):
            self.skipTest("luac есть")
        self.assertEqual(len(check.check_lua(self.root, strict=True)), 1)
        self.assertEqual(check.check_lua(self.root, strict=False), [])


class NewVersionTest(Base):
    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def setUp(self):
        super().setUp()
        self.git("init", "-q", "-b", "main")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "--allow-empty",
                 "-m", "base")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "-m", "v0.1.0")
        self.git("tag", "v0.1.0")
        self.git("checkout", "-q", "-b", "change")

    def commit_change(self):
        (self.root / MODULE / "Module.lua").write_text("-- новое\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "-m", "change")

    def test_changed_addon_with_released_version_fails(self):
        self.commit_change()
        self.assertEqual(len(check.check_new_version(self.root, "main")), 1)

    def test_new_version_passes(self):
        self.commit_change()
        toc = self.root / MODULE / f"{MODULE}.toc"
        toc.write_text(toc.read_text(encoding="utf-8").replace("0.1.0", "0.2.0"), encoding="utf-8")
        self.assertEqual(check.check_new_version(self.root, "main"), [])

    def test_only_changed_audio_is_decoded(self):
        """На PR декодируем только новые и изменённые OGG — остальные проверены при прошлом выпуске."""
        sounds = self.root / MODULE / SOUNDS
        (sounds / "300000002-progress.ogg").write_bytes(b"OggS-new")
        (sounds / "300000001-progress.ogg").write_bytes(b"OggS-changed")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "-m", "audio")

        changed = check.changed_audio(self.root, "main")

        self.assertEqual([p.name for p in changed], ["300000001-progress.ogg", "300000002-progress.ogg"])

    def test_deleted_audio_is_not_decoded(self):
        (self.root / MODULE / SOUNDS / "300000001-progress.ogg").unlink()
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "-m", "rm")

        self.assertEqual(check.changed_audio(self.root, "main"), [])

    def test_text_scan_covers_only_tracked_files(self):
        """В CI в рабочую копию ставятся инструменты (.lua/bin/luac) — это не содержимое репозитория."""
        (self.root / ".lua" / "bin").mkdir(parents=True)
        (self.root / ".lua" / "bin" / "luac").write_bytes(b"\x7fELF\x00free" + b"@GLIBC_2.2.5")
        (self.root / "NOTES").write_text("someone" + "@example.com", encoding="utf-8")  # не в git

        self.assertEqual(check.check_text(self.root), [])

    def test_binary_tracked_file_is_skipped(self):
        (self.root / "tool").write_bytes(b"\x00\x01free" + b"@GLIBC_2.2.5")
        self.git("add", "-A")

        self.assertEqual(check.check_text(self.root), [])

    def test_docs_only_change_needs_no_new_version(self):
        (self.root / "README.md").write_text("# новое\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@users.noreply.github.com", "commit", "-q", "-m", "docs")
        self.assertEqual(check.check_new_version(self.root, "main"), [])


class PackageTest(Base):
    def test_zip_has_only_module_folder_with_licenses(self):
        target = package.build(self.root, self.root / "dist")

        self.assertEqual(target.name, "book-voices-ru-v0.1.0.zip")
        names = zipfile.ZipFile(target).namelist()
        self.assertEqual({n.split("/")[0] for n in names}, {MODULE})
        self.assertEqual(len(names), len(set(names)))  # без повторов имён
        for name in ("README.md", "NOTICE", "LICENSE", "THIRD-PARTY.md", "CHANGELOG.md", "CC-BY-NC-SA-4.0.txt",
                     "LICENSE-ASSETS.txt"):
            self.assertIn(f"{MODULE}/{name}", names)

    def test_zip_is_reproducible(self):
        a = package.build(self.root, self.root / "a").read_bytes()
        b = package.build(self.root, self.root / "b").read_bytes()
        self.assertEqual(a, b)

    def test_release_notes_from_changelog(self):
        self.assertEqual(package.changelog_section("0.1.0", self.root), "- Первый релиз.\n")


class CurseForgeTest(Base):
    VERSIONS = [  # как отвечает GET /api/game/versions (фрагмент)
        {"id": 13001, "gameVersionTypeID": 67408, "name": "1.15.9", "slug": "1-15-9"},
        {"id": 12900, "gameVersionTypeID": 67408, "name": "1.15.8", "slug": "1-15-8"},
        {"id": 14000, "gameVersionTypeID": 99001, "name": "1.60.1", "slug": "1-60-1"},
    ]

    def test_game_version_from_module_interface(self):
        self.assertEqual(curseforge.game_version(self.root), "1.15.9")

    def test_resolve_game_version_ids(self):
        self.assertEqual(curseforge.resolve_game_versions(self.VERSIONS, ["1.15.9"]), [13001])

    def test_unknown_or_ambiguous_game_version_fails(self):
        with self.assertRaises(SystemExit):
            curseforge.resolve_game_versions(self.VERSIONS, ["1.15.10"])
        twice = self.VERSIONS + [{"id": 1, "gameVersionTypeID": 5, "name": "1.15.9", "slug": "x"}]
        with self.assertRaises(SystemExit):
            curseforge.resolve_game_versions(twice, ["1.15.9"])

    def test_metadata(self):
        meta = curseforge.build_metadata("0.2.0", "- Новое.\n", [13001])

        self.assertEqual(meta["displayName"], "Book Voices RU 0.2.0")
        self.assertEqual((meta["changelog"], meta["changelogType"]), ("- Новое.\n", "markdown"))
        self.assertEqual((meta["gameVersions"], meta["releaseType"]), ([13001], "release"))
        self.assertEqual(meta["relations"]["projects"], [
            {"slug": "voiceover", "type": "requiredDependency"},
        ])

    def test_multipart_body(self):
        body, content_type = curseforge.multipart({"metadata": '{"a": 1}'}, "file", "x.zip", b"PK\x03\x04")

        boundary = content_type.split("boundary=")[1]
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="metadata"\r\n\r\n{"a": 1}\r\n', body)
        self.assertIn(b'name="file"; filename="x.zip"\r\nContent-Type: application/zip\r\n\r\nPK\x03\x04\r\n', body)
        self.assertTrue(body.endswith(f"--{boundary}--\r\n".encode()))

    def test_skipped_without_project_or_token(self):
        for env in ({}, {"CF_PROJECT_ID": "123"}, {"CF_API_KEY": "t"}):
            self.assertIsNone(curseforge.credentials(env))
        self.assertEqual(curseforge.credentials({"CF_PROJECT_ID": "123", "CF_API_KEY": "t"}), ("123", "t"))


if __name__ == "__main__":
    unittest.main()
