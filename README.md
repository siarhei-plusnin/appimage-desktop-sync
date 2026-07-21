# AppImage Desktop Sync

`appimage-desktop-sync` watches an AppImage directory and maintains matching desktop launchers under `~/.local/share/applications`.

The watcher is event-driven. It uses `inotifywait` recursively and filters events to filenames ending in `.AppImage`, case-insensitively. It does not poll.

## Behavior

- Watches `~/Applications` by default.
- Creates one desktop launcher for every AppImage below the watched directory.
- Uses direct, quoted AppImage paths in `Exec=`.
- Updates launchers only when their generated content changes.
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
