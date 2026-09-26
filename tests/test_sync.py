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
        if shutil.which("desktop-file-validate"):
            subprocess.run(["desktop-file-validate", str(launcher)], check=True)

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

    def test_unmanaged_launcher_survives_sync_and_cleanup(self):
        self.sync()
        launcher = self.launcher()
        unmanaged = self.desktop("Unmanaged")
        launcher.write_text(unmanaged)
        self.override.write_text(self.desktop())
        self.assertIn("Refusing to overwrite unmanaged launcher", self.sync().stderr)
        self.assertEqual(launcher.read_text(), unmanaged)
        self.appimage.unlink()
        self.sync()
        self.assertEqual(launcher.read_text(), unmanaged)

    def test_incomplete_override_keeps_previous_launcher(self):
        self.sync()
        launcher = self.launcher()
        generated = launcher.read_text()
        self.override.write_text("# Being written\n")
        self.assertIn("Skipping invalid or unreadable desktop override", self.sync().stderr)
        self.assertEqual(launcher.read_text(), generated)
        self.assertEqual(list(self.applications.glob(".appimage-sync*")), [])
        self.override.write_text(self.desktop())
        self.sync()
        self.assertIn("Name=Custom Foo\n", launcher.read_text())

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
