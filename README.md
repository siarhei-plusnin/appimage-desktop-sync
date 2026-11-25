# AppImage Desktop Sync

`appimage-desktop-sync` watches an AppImage directory and maintains matching desktop launchers under `~/.local/share/applications`.

The watcher is event-driven. It uses `inotifywait` recursively and filters events to AppImages, desktop files, PNG/SVG/XPM icons, and `.DirIcon` files. It does not poll.

## Behavior

- Watches `~/Applications` by default.
- Maintains one desktop launcher for every AppImage below the watched directory.
- Uses a sibling `.desktop` override when available; otherwise uses the AppImage's embedded root `.desktop` file as a metadata template.
- Generates a minimal launcher when neither an override nor usable embedded metadata is available.
- Extracts one embedded icon when possible and stores it under `~/.local/share/icons/appimage-sync/`.
- Normalizes embedded launch commands to invoke the AppImage directly.
- Updates launchers and icons only when their content changes.
- Removes stale launchers only when they contain the `X-AppImage-Sync=true` ownership marker.
- Refreshes the desktop application database after synchronization.

## Build And Install

```sh
makepkg -si
```

The package depends on `7zip` for selective embedded metadata and icon extraction.

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

For `Foo.AppImage`, `Foo.desktop` takes priority. If there is no matching filename, the directory's sole `.desktop` file is used only when it also contains exactly one AppImage. Otherwise, the AppImage's embedded desktop file is used when available, falling back to a generated launcher. Matching uses the AppImage's exact basename without its extension and the lowercase `.desktop` extension; AppImage extensions are case-insensitive. Only files directly in the AppImage's directory are considered.

The override is copied into the managed launcher under `~/.local/share/applications` (or `$XDG_DATA_HOME/applications`). Its fields, including `Exec=`, `Path=`, icons, and desktop actions, are preserved; `X-AppImage-Sync=true` is added or replaced in `[Desktop Entry]`. The source file is left untouched.

Edits, additions, renames, and removal of overrides trigger synchronization. Removing an override re-runs selection and restores the embedded or generated launcher. An unreadable override or one missing `[Desktop Entry]` is skipped with a diagnostic, retaining any existing launcher and managed icon until the override is fixed.

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

## Embedded Desktop Files

For type-2 SquashFS AppImages without a sibling override, the synchronizer reads the canonical `.desktop` file from the AppImage root and uses it as a template. The AppImage is never executed to inspect it, and only the desktop file and selected icon are extracted.

Descriptive and behavioral fields are preserved, including:

- `Name`, localized names, `Comment`, `Categories`, `MimeType`, and `Keywords`
- `Terminal`, `StartupNotify`, and `StartupWMClass`
- Application-specific `X-` metadata

Launch-related fields are normalized:

- `Exec=` invokes the AppImage directly. Embedded arguments and environment wrappers are discarded.
- The original `%F`, `%U`, `%f`, or `%u` file/URL field code is preserved. If `Exec=` was missing, `%U` is used; if it accepted no files, no field code is added.
- `TryExec=` contains the absolute AppImage path.
- `Path=` contains the AppImage's parent directory.
- Embedded `Actions=` and `[Desktop Action ...]` groups are stripped rather than rewriting internal commands. Sibling overrides keep their actions unchanged.
- `DBusActivatable=false` ensures the desktop environment uses `Exec=`.
- `Hidden` and `NoDisplay` are removed so managed entries remain visible.
- `X-AppImage-Sync=true` appears exactly once in `[Desktop Entry]`.

Malformed embedded desktop files are ignored with a diagnostic, and a minimal launcher is generated instead. Unsupported AppImage formats, unreadable archives, and missing extraction tools also fall back safely.

Extracted metadata is cached under `${XDG_CACHE_HOME:-$HOME/.cache}/appimage-desktop-sync/`. A fingerprint based on inode, size, modification time, and change time avoids re-reading unchanged AppImages.

## Icons

A `.desktop` file references an icon; it does not contain the image itself. For generated and embedded-template launchers, icons are selected in this order:

1. `<AppImage-stem>.svg`, `.png`, or `.xpm` beside the AppImage
2. `.DirIcon` beside the AppImage
3. Embedded `.DirIcon`
4. The icon named by the embedded desktop entry, checking the AppImage root and common hicolor locations
5. `application-x-executable`

PNG, SVG, and XPM are supported. The selected icon is copied to:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/icons/appimage-sync/
```

The managed launcher uses the copied icon's absolute path in `Icon=`, so no icon-theme installation or icon-cache refresh is required. Sibling `.desktop` overrides remain untouched and may use either an absolute icon path or an installed icon-theme name.

Icon additions, edits, renames, and removal trigger synchronization. Stale managed icons are removed when no longer selected, unless another desktop file still references them.

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

Generated launchers, icons, and extraction caches are user data and are not removed automatically with the package. Remove them with:

```sh
rm -f ~/.local/share/applications/appimage-sync-*.desktop
rm -rf ~/.local/share/icons/appimage-sync
rm -rf ~/.cache/appimage-desktop-sync
update-desktop-database ~/.local/share/applications
```

If you use custom XDG directories, apply the same cleanup under `$XDG_DATA_HOME` and `$XDG_CACHE_HOME`.
