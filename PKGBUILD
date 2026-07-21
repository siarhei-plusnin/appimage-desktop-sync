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
sha256sums=(
    'be9b5b3dccaa9dde416d7ff6c3f73f15c69c79e50bfbd17beca98832c9658c92'
    '1008258bea01bcdf6177d7ccd7d46d0c55df77103aef876c9e8dbb04c679106c'
    'e7e0b7156a120d069a98979bc56510071bb98255a1b143d14c5a8b1d13ae7617'
    '436225bf456d63efb7a64b8b48c78c7a43d60e611524922d270b7b6940d8fed2'
)

package() {
    install -Dm755 "${srcdir}/appimage-desktop-sync" "${pkgdir}/usr/bin/appimage-desktop-sync"
    install -Dm644 "${srcdir}/appimage-desktop-sync.service" "${pkgdir}/usr/lib/systemd/user/appimage-desktop-sync.service"
    install -Dm644 "${srcdir}/README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
