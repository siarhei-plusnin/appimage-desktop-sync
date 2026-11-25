import base64
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "appimage-desktop-sync"
MARKER = "X-AppImage-Sync=true\n"
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
HAS_APPIMAGE_FIXTURE_TOOLS = all(shutil.which(tool) for tool in ("cc", "mksquashfs", "7z"))


class SyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="appimage-sync-test-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "Applications"
        self.app_directory = self.root / "Portable App"
        self.app_directory.mkdir(parents=True)
        self.appimage = self.app_directory / "Foo.AppImage"
        self.appimage.touch()
        self.override = self.app_directory / "Foo.desktop"
        self.applications = self.home / "data" / "applications"
        self.environment = {
            **os.environ,
            "HOME": str(self.home),
            "APPIMAGE_ROOT": str(self.root),
            "XDG_DATA_HOME": str(self.home / "data"),
            "XDG_CACHE_HOME": str(self.home / "cache"),
            "XDG_RUNTIME_DIR": str(self.home),
        }

    def sync(self):
        return subprocess.run(
            ["sh", str(SCRIPT), "sync"],
            env=self.environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def launcher(self):
        launchers = list(self.applications.glob("appimage-sync-foo-*.desktop"))
        self.assertEqual(len(launchers), 1)
        return launchers[0]

    def desktop(self, name="Custom Foo"):
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f'Exec=env "XDG_DATA_HOME={self.appimage}.home/.local/share" '
            f'"{self.appimage}" --portable %U\n'
            "Icon=custom-icon\n"
            "Terminal=false\n"
            "Actions=Settings;\n"
            "\n[Desktop Action Settings]\n"
            "Name=Settings\n"
            f'Exec="{self.appimage}" --settings\n'
        )

    def embedded_desktop(self, name="Embedded Foo", icon="foo", exec_line="AppRun %U"):
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Exec={exec_line}\n"
            f"Icon={icon}\n"
        )

    def make_embedded_appimage(self, desktop=None, files=None, diricon_target=None):
        self.make_appimage(
            desktop=desktop or self.embedded_desktop(),
            files=files or {"foo.svg": "<svg>embedded</svg>\n"},
            diricon_target=diricon_target,
        )

    def make_appimage(self, desktop=None, files=None, diricon_target=None):
        if not HAS_APPIMAGE_FIXTURE_TOOLS:
            self.skipTest("cc, mksquashfs, and 7z are required")

        build_directory = self.home / "appimage-build"
        if build_directory.exists():
            shutil.rmtree(build_directory)
        appdir = build_directory / "appdir"
        appdir.mkdir(parents=True)

        if desktop is not None:
            (appdir / "Foo.desktop").write_text(desktop)
        for name, content in (files or {}).items():
            path = appdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        if diricon_target is not None:
            (appdir / ".DirIcon").symlink_to(diricon_target)

        runtime = self.home / "runtime"
        if not runtime.exists():
            source = self.home / "runtime.c"
            source.write_text("int main(void) { return 0; }\n")
            subprocess.run(["cc", str(source), "-o", str(runtime)], check=True, capture_output=True)
        runtime_data = bytearray(runtime.read_bytes())
        runtime_data[8:11] = b"AI\x02"
        runtime.write_bytes(runtime_data)

        payload = build_directory / "payload.squashfs"
        subprocess.run(
            ["mksquashfs", str(appdir), str(payload), "-noappend", "-quiet"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        self.appimage.write_bytes(runtime.read_bytes() + payload.read_bytes())

    def managed_icon(self):
        for line in self.launcher().read_text().splitlines():
            if line.startswith("Icon="):
                value = line.removeprefix("Icon=")
                path = Path(value)
                if path.parent == self.home / "data" / "icons" / "appimage-sync":
                    return path
                return None
        return None

    def assert_valid_launcher(self):
        if shutil.which("desktop-file-validate"):
            subprocess.run(["desktop-file-validate", str(self.launcher())], check=True)

    def test_override_lifecycle_preserves_fields_and_source(self):
        self.sync()
        launcher = self.launcher()
        generated = launcher.read_text()
        source = self.desktop().replace(
            "Type=Application\n", "Type=Application\nX-AppImage-Sync=false\n"
        )
        self.override.write_text(source)
        self.sync()

        expected = self.desktop().replace("[Desktop Entry]\n", "[Desktop Entry]\n" + MARKER)
        self.assertEqual(launcher.read_text(), expected)
        self.assertEqual(self.override.read_text(), source)
        self.assertEqual(launcher.stat().st_mode & 0o777, 0o644)
        self.assertEqual(launcher.read_text().count(MARKER), 1)
        self.assert_valid_launcher()

        before = launcher.stat()
        self.assertEqual(self.sync().stdout, "")
        after = launcher.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))

        self.override.write_text(source.replace("Custom Foo", "Edited Foo"))
        self.sync()
        self.assertIn("Name=Edited Foo\n", launcher.read_text())
        self.override.unlink()
        self.sync()
        self.assertEqual(launcher.read_text(), generated)
        self.appimage.unlink()
        self.sync()
        self.assertFalse(launcher.exists())

    def test_selection_prefers_basename_and_rejects_ambiguity(self):
        fallback = self.app_directory / "vendor.desktop"
        fallback.write_text(self.desktop("Fallback"))
        self.sync()
        self.assertIn("Name=Fallback\n", self.launcher().read_text())

        extra = self.app_directory / "other.desktop"
        extra.write_text(self.desktop("Other"))
        self.sync()
        self.assertIn("Name=Foo\n", self.launcher().read_text())

        self.override.write_text(self.desktop("Exact"))
        self.sync()
        self.assertIn("Name=Exact\n", self.launcher().read_text())

        self.override.unlink()
        extra.unlink()
        (self.app_directory / ".Second.aPpImAgE").touch()
        self.sync()
        self.assertIn("Name=Foo\n", self.launcher().read_text())
        self.override.write_text(self.desktop("Exact with two apps"))
        self.sync()
        self.assertIn("Name=Exact with two apps\n", self.launcher().read_text())

    def test_nested_desktop_does_not_override_parent_app(self):
        nested = self.app_directory / "Foo.AppImage.home"
        nested.mkdir()
        (nested / "Foo.desktop").write_text(self.desktop("Nested"))
        self.sync()
        self.assertIn("Name=Foo\n", self.launcher().read_text())

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_unmanaged_launcher_survives_sync_and_cleanup(self):
        self.make_embedded_appimage()
        self.sync()
        launcher = self.launcher()
        icon = self.managed_icon()
        unmanaged = launcher.read_text().replace(MARKER, "")
        launcher.write_text(unmanaged)
        self.override.write_text(self.desktop())
        self.assertIn("Refusing to overwrite unmanaged launcher", self.sync().stderr)
        self.assertEqual(launcher.read_text(), unmanaged)
        self.appimage.unlink()
        self.sync()
        self.assertEqual(launcher.read_text(), unmanaged)
        self.assertTrue(icon.exists())

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_incomplete_override_keeps_previous_launcher_and_icon(self):
        self.make_embedded_appimage()
        self.sync()
        launcher = self.launcher()
        previous = launcher.read_text()
        icon = self.managed_icon()
        self.override.write_text("# Being written\n")
        self.assertIn("Skipping invalid or unreadable desktop override", self.sync().stderr)
        self.assertEqual(launcher.read_text(), previous)
        self.assertTrue(icon.exists())
        self.assertEqual(list(self.applications.glob(".appimage-sync*")), [])
        self.override.write_text(self.desktop())
        self.sync()
        self.assertIn("Name=Custom Foo\n", launcher.read_text())

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_embedded_desktop_is_normalized_cached_and_refreshed(self):
        embedded = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Embedded Foo\n"
            "Name[fr]=Foo intégré\n"
            "Comment=Embedded comment\n"
            "Exec=env INTERNAL=1 ./AppRun --portable %F\n"
            "TryExec=./AppRun\n"
            "Path=/inside/image\n"
            "Icon=foo\n"
            "Terminal=true\n"
            "Categories=Development;\n"
            "MimeType=text/plain;\n"
            "StartupWMClass=Foo\n"
            "StartupNotify=true\n"
            "NoDisplay=true\n"
            "Hidden=true\n"
            "DBusActivatable=true\n"
            "X-Custom=Keep\n"
            "Actions=Settings;\n"
            "\n[Desktop Action Settings]\n"
            "Name=Settings\n"
            "Name[fr]=Paramètres\n"
            "Exec=./internal --settings %U\n"
            "Icon=foo\n"
        )
        self.make_appimage(
            desktop=embedded,
            files={"foo.svg": "<svg>embedded</svg>\n"},
            diricon_target="foo.svg",
        )
        self.sync()

        launcher = self.launcher()
        text = launcher.read_text()
        icon = self.managed_icon()
        self.assertIsNotNone(icon)
        self.assertEqual(icon.read_text(), "<svg>embedded</svg>\n")
        self.assertIn("Name=Embedded Foo\n", text)
        self.assertIn("Name[fr]=Foo intégré\n", text)
        self.assertIn("Comment=Embedded comment\n", text)
        self.assertIn("Categories=Development;\n", text)
        self.assertIn("MimeType=text/plain;\n", text)
        self.assertIn("StartupWMClass=Foo\n", text)
        self.assertIn("Terminal=true\n", text)
        self.assertIn("X-Custom=Keep\n", text)
        self.assertIn(f'Exec="{self.appimage}" %F\n', text)
        self.assertIn(f"TryExec={self.appimage}\n", text)
        self.assertIn(f"Path={self.app_directory}\n", text)
        self.assertIn(f"Icon={icon}\n", text)
        self.assertIn("DBusActivatable=false\n", text)
        self.assertNotIn("NoDisplay=", text)
        self.assertNotIn("Hidden=", text)
        self.assertNotIn("--portable", text)
        self.assertEqual(text.count(MARKER), 1)

        self.assertNotIn("Actions=", text)
        self.assertNotIn("[Desktop Action", text)
        self.assertNotIn("X-Desktop-File-Install-Version", text)
        self.assert_valid_launcher()

        launcher_before = launcher.stat()
        icon_before = icon.stat()
        self.assertEqual(self.sync().stdout, "")
        launcher_after = launcher.stat()
        icon_after = icon.stat()
        self.assertEqual(
            (launcher_before.st_ino, launcher_before.st_mtime_ns),
            (launcher_after.st_ino, launcher_after.st_mtime_ns),
        )
        self.assertEqual(
            (icon_before.st_ino, icon_before.st_mtime_ns),
            (icon_after.st_ino, icon_after.st_mtime_ns),
        )

        self.make_appimage(
            desktop=embedded.replace("Embedded Foo", "Embedded Updated"),
            files={"foo.svg": "<svg>updated</svg>\n"},
            diricon_target="foo.svg",
        )
        self.sync()
        self.assertIn("Name=Embedded Updated\n", self.launcher().read_text())
        self.assertEqual(self.managed_icon().read_text(), "<svg>updated</svg>\n")

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_sibling_icons_take_precedence_and_fall_back_to_embedded(self):
        self.make_embedded_appimage(diricon_target="foo.svg")
        sibling_png = self.app_directory / "Foo.png"
        sibling_png.write_bytes(TINY_PNG)
        self.sync()
        self.assertEqual(self.managed_icon().read_bytes(), TINY_PNG)
        self.assertEqual(self.managed_icon().suffix, ".png")

        sibling_png.unlink()
        self.sync()
        self.assertEqual(self.managed_icon().read_text(), "<svg>embedded</svg>\n")
        self.assertEqual(self.managed_icon().suffix, ".svg")

        sibling_diricon = self.app_directory / ".DirIcon"
        sibling_diricon.write_text("/* XPM */\nstatic char *icon[] = {\"1 1 1 1\", \"  c None\", \" \"};\n")
        self.sync()
        self.assertEqual(self.managed_icon().suffix, ".xpm")
        self.assertIn("XPM", self.managed_icon().read_text())

        sibling_diricon.unlink()
        self.sync()
        self.assertEqual(self.managed_icon().read_text(), "<svg>embedded</svg>\n")
        self.assertEqual(len(list((self.home / "data" / "icons" / "appimage-sync").iterdir())), 1)

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_embedded_hicolor_icon_and_uppercase_sibling_icon(self):
        self.make_appimage(
            desktop=self.embedded_desktop(exec_line="AppRun --flag"),
            files={"usr/share/icons/hicolor/256x256/apps/foo.png": TINY_PNG},
        )
        self.sync()
        self.assertEqual(self.managed_icon().read_bytes(), TINY_PNG)
        self.assertEqual(self.managed_icon().suffix, ".png")
        self.assertIn(f'Exec="{self.appimage}"\n', self.launcher().read_text())

        sibling = self.app_directory / "Foo.SVG"
        sibling.write_text("<svg>uppercase</svg>\n")
        self.sync()
        self.assertEqual(self.managed_icon().read_text(), "<svg>uppercase</svg>\n")
        self.assertEqual(self.managed_icon().suffix, ".svg")

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_invalid_embedded_desktop_falls_back_to_generated(self):
        self.make_appimage(desktop="# Missing desktop group\n")
        result = self.sync()
        self.assertIn("Ignoring invalid embedded desktop file", result.stderr)
        text = self.launcher().read_text()
        self.assertIn("Name=Foo\n", text)
        self.assertIn(f'Exec="{self.appimage}" %U\n', text)
        self.assertIn("Icon=application-x-executable\n", text)

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_unsafe_embedded_icon_paths_are_not_used(self):
        self.make_appimage(desktop=self.embedded_desktop(name="Foo", icon="/etc/hostname"))
        self.sync()
        self.assertIsNone(self.managed_icon())
        self.assertIn("Icon=application-x-executable\n", self.launcher().read_text())

        self.make_appimage(
            desktop=self.embedded_desktop(name="Foo"),
            diricon_target="/etc/hostname",
        )
        self.sync()
        self.assertIsNone(self.managed_icon())
        self.assertIn("Icon=application-x-executable\n", self.launcher().read_text())

    @unittest.skipUnless(HAS_APPIMAGE_FIXTURE_TOOLS, "AppImage fixture tools are required")
    def test_override_removal_falls_back_to_embedded_desktop(self):
        self.make_embedded_appimage()
        self.override.write_text(self.desktop("Override Foo"))
        self.sync()
        self.assertIn("Name=Override Foo\n", self.launcher().read_text())
        self.assertIsNone(self.managed_icon())

        self.override.unlink()
        self.sync()
        self.assertIn("Name=Embedded Foo\n", self.launcher().read_text())
        self.assertIsNotNone(self.managed_icon())

    @unittest.skipUnless(shutil.which("inotifywait"), "inotifywait is required")
    def test_watcher_tracks_override_creation_edit_rename_and_removal(self):
        log = tempfile.TemporaryFile(mode="w+")
        self.addCleanup(log.close)
        watcher = subprocess.Popen(
            ["sh", str(SCRIPT), "watch"],
            env=self.environment,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )

        def stop():
            if watcher.poll() is None:
                os.killpg(watcher.pid, signal.SIGTERM)
            try:
                watcher.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(watcher.pid, signal.SIGKILL)
                watcher.wait(timeout=5)

        self.addCleanup(stop)

        def wait_for(predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if watcher.poll() is not None:
                    break
                if predicate():
                    return
                time.sleep(0.02)
            log.seek(0)
            self.fail("Watcher did not reach expected state:\n" + log.read())

        def watching():
            # Wait for actual watches, rather than guessing a startup delay.
            children = Path(f"/proc/{watcher.pid}/task/{watcher.pid}/children").read_text()
            for child in children.split():
                for info in Path(f"/proc/{child}/fdinfo").glob("*"):
                    try:
                        if "inotify wd:" in info.read_text():
                            return True
                    except FileNotFoundError:
                        pass
            return False

        wait_for(watching)
        launcher = self.launcher()
        generated = launcher.read_text()

        sibling_icon = self.app_directory / "Foo.svg"
        sibling_icon.write_text("<svg>first</svg>\n")
        wait_for(lambda: self.managed_icon() is not None)
        icon = self.managed_icon()
        self.assertEqual(icon.read_text(), "<svg>first</svg>\n")
        sibling_icon.write_text("<svg>edited</svg>\n")
        wait_for(lambda: icon.read_text() == "<svg>edited</svg>\n")
        sibling_icon.unlink()
        wait_for(lambda: launcher.read_text() == generated)

        self.override.touch()
        wait_for(lambda: "Skipping invalid" in self._log_contents(log))
        self.override.write_text(self.desktop("Watched"))
        wait_for(lambda: "Name=Watched\n" in launcher.read_text())
        self.override.write_text(self.desktop("Edited"))
        wait_for(lambda: "Name=Edited\n" in launcher.read_text())
        self.override.rename(self.app_directory / "disabled.txt")
        wait_for(lambda: launcher.read_text() == generated)
        replacement = self.app_directory / "replacement.tmp"
        replacement.write_text(self.desktop("Replaced"))
        replacement.rename(self.override)
        wait_for(lambda: "Name=Replaced\n" in launcher.read_text())
        self.override.unlink()
        wait_for(lambda: launcher.read_text() == generated)
        self.appimage.unlink()
        wait_for(lambda: not launcher.exists())

    @staticmethod
    def _log_contents(log):
        log.seek(0)
        return log.read()


if __name__ == "__main__":
    unittest.main()
