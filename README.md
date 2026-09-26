# AppImage Desktop Sync

`appimage-desktop-sync` watches an AppImage directory and maintains matching desktop launchers under `~/.local/share/applications`.

The watcher is event-driven. It uses `inotifywait` recursively and filters events to filenames ending in `.AppImage` or `.desktop`, case-insensitively. It does not poll.

## Behavior

- Watches `~/Applications` by default.
- Maintains one desktop launcher for every AppImage below the watched directory.
- Uses a sibling `.desktop` override when available; otherwise generates a launcher with a direct, quoted AppImage path in `Exec=`.
- Updates launchers only when their content changes.
- Removes stale launchers only when they contain the `X-AppImage-Sync=true` ownership marker.
- Refreshes the desktop application database after synchronization.

## Build And Install

```sh
makepkg -si
```

Enable the user service:

```sh
systemctl --user enable --now appimage-desktop-sync.service
```

Check its status and logs:

```sh
systemctl --user status appimage-desktop-sync.service
journalctl --user -u appimage-desktop-sync.service
```

## Commands

Run a one-time synchronization:

```sh
appimage-desktop-sync sync
```

Run the event watcher manually:

```sh
appimage-desktop-sync watch
```

## Desktop Overrides

Place a `.desktop` file alongside an AppImage to customize its launcher:

```text
~/Applications/Foo/
├── Foo.AppImage
├── Foo.desktop
└── Foo.AppImage.home/
```

For `Foo.AppImage`, `Foo.desktop` takes priority. If there is no matching filename, the directory's sole `.desktop` file is used only when it also contains exactly one AppImage. Otherwise, a launcher is generated. Matching uses the AppImage's exact basename without its extension and the lowercase `.desktop` extension; AppImage extensions are case-insensitive. Only files directly in the AppImage's directory are considered.

The override is copied into the managed launcher under `~/.local/share/applications` (or `$XDG_DATA_HOME/applications`). Its fields, including `Exec=`, `Path=`, icons, and desktop actions, are preserved; `X-AppImage-Sync=true` is added or replaced in `[Desktop Entry]`. The source file is left untouched.

Edits, additions, renames, and removal of overrides trigger synchronization. Removing an override re-runs selection and restores a generated launcher if no override applies. An unreadable override or one missing `[Desktop Entry]` is skipped with a diagnostic, retaining any existing launcher until the override is fixed.

### Portable App Data

For an app that writes outside its `.AppImage.home` directory but honors `XDG_DATA_HOME`, set it explicitly in the override:

```ini
[Desktop Entry]
Type=Application
Name=Foo
Exec=env "XDG_DATA_HOME=/home/you/Applications/Foo/Foo.AppImage.home/.local/share" "/home/you/Applications/Foo/Foo.AppImage" %U
Terminal=false
Categories=Utility;
```

Use your actual absolute paths: desktop `Exec=` values do not expand `~` or `$HOME`, and the synchronizer does not rewrite override paths. Create the target data directory before launching. Other XDG variables, such as `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME`, can be set in the same way. For path calculations or more complex setup, have `Exec=` invoke a sibling wrapper script.

## Custom Directory

Set `APPIMAGE_ROOT` in a systemd user override:

```sh
systemctl --user edit appimage-desktop-sync.service
```

Add:

```ini
[Service]
Environment=APPIMAGE_ROOT=/path/to/AppImages
```

Then restart the service:

```sh
systemctl --user restart appimage-desktop-sync.service
```

## Uninstall Cleanup

Generated launchers are user data and are not removed automatically with the package. Remove them with:

```sh
rm ~/.local/share/applications/appimage-sync-*.desktop
update-desktop-database ~/.local/share/applications
```
