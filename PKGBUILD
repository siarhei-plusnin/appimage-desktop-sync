pkgname=appimage-desktop-sync
pkgver=0.1.0
pkgrel=2
pkgdesc='Event-driven AppImage desktop launcher synchronizer'
arch=('any')
license=('MIT')
depends=('desktop-file-utils' 'inotify-tools')
install="${pkgname}.install"

source=(
    'appimage-desktop-sync'
    'appimage-desktop-sync.service'
    'README.md'
    'LICENSE'
)
sha256sums=('1e77ad4d5d532a8ba2d9f4dcd6ce1d23afc485f73008cf73e8effbdb1e7c9b03'
            '1008258bea01bcdf6177d7ccd7d46d0c55df77103aef876c9e8dbb04c679106c'
            '5ae57c539f2040eb76f65a2df61e93955840ad8ef236fb8ceab4a414042d642a'
            'cf525a9626afe055da94df76b1a0ba0ea053d1fb939b0cdbb2b1312552772c9f')

package() {
    install -Dm755 "${srcdir}/appimage-desktop-sync" "${pkgdir}/usr/bin/appimage-desktop-sync"
    install -Dm644 "${srcdir}/appimage-desktop-sync.service" "${pkgdir}/usr/lib/systemd/user/appimage-desktop-sync.service"
    install -Dm644 "${srcdir}/README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
