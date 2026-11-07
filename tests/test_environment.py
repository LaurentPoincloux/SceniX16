"""Vérifie que l'environnement fournit tout ce que demande le Design Book."""

import sys

from PySide6 import QtCore, __version__ as pyside_version
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter
from PySide6.QtSvg import QSvgRenderer


def test_python_version_supported():
    assert (3, 13) <= sys.version_info[:2] < (3, 16)


def test_pyside_version():
    assert pyside_version == "6.12.0"
    assert QtCore.qVersion() == "6.12.0"


def test_image_formats_for_visuals(qapp):
    """Formats retenus pour les visuels (Q7) : PNG, JPG/JPEG, WebP, SVG."""
    formats = {bytes(f).decode() for f in QImageReader.supportedImageFormats()}
    for fmt in ("png", "jpg", "jpeg", "webp", "svg"):
        assert fmt in formats, fmt


def test_svg_rendering(qapp):
    svg = QByteArray(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        b'<rect width="40" height="20" fill="#FF5A1F"/></svg>'
    )
    renderer = QSvgRenderer(svg)
    assert renderer.isValid()
    image = QImage(80, 40, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    assert QColor(image.pixel(10, 10)).name() == "#ff5a1f"


def test_print_support_available():
    from PySide6.QtPrintSupport import QPrinter

    assert QPrinter() is not None
