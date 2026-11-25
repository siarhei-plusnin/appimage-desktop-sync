pkgname=appimage-desktop-sync
pkgver=0.1.0
pkgrel=5
pkgdesc='Event-driven AppImage desktop launcher synchronizer'
arch=('any')
license=('MIT')
depends=('7zip' 'desktop-file-utils' 'inotify-tools')
install="${pkgname}.install"

source=(
    'appimage-desktop-sync'
    'appimage-desktop-sync.service'
    'README.md'
    'LICENSE'
)
sha256sums=('329f8270e507fd745540c70b90b33d2016ac15a7da10472aa924dfd59d8ca1ca'
            '1008258bea01bcdf6177d7ccd7d46d0c55df77103aef876c9e8dbb04c679106c'
            'f24a5085f8e6009cf947f49d14584604be3c172f9ddaeafc8e32eda41838ce16'
            'cf525a9626afe055da94df76b1a0ba0ea053d1fb939b0cdbb2b1312552772c9f')

package() {
    install -Dm755 "${srcdir}/appimage-desktop-sync" "${pkgdir}/usr/bin/appimage-desktop-sync"
    install -Dm644 "${srcdir}/appimage-desktop-sync.service" "${pkgdir}/usr/lib/systemd/user/appimage-desktop-sync.service"
    install -Dm644 "${srcdir}/README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
