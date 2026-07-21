pkgname=appimage-desktop-sync
pkgver=0.1.0
pkgrel=1
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
sha256sums=('f7276d1499499865f4d4d75c58914c3a3d93ec5d3a83449d7be10d663aec47e8'
            '1008258bea01bcdf6177d7ccd7d46d0c55df77103aef876c9e8dbb04c679106c'
            'e7e0b7156a120d069a98979bc56510071bb98255a1b143d14c5a8b1d13ae7617'
            'cf525a9626afe055da94df76b1a0ba0ea053d1fb939b0cdbb2b1312552772c9f')

package() {
    install -Dm755 "${srcdir}/appimage-desktop-sync" "${pkgdir}/usr/bin/appimage-desktop-sync"
    install -Dm644 "${srcdir}/appimage-desktop-sync.service" "${pkgdir}/usr/lib/systemd/user/appimage-desktop-sync.service"
    install -Dm644 "${srcdir}/README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
