"""
Splash screen for DennTech Crypto Suite
Displays logo for 3-5 seconds before app launch
"""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QSplashScreen, QApplication


def show_splash(duration_ms: int = 4000):
    """
    Display a splash screen with the logo.

    Args:
        duration_ms: Duration to show splash in milliseconds (default 4000 = 4 seconds)

    Returns:
        QSplashScreen instance or None
    """
    base_dir = Path(__file__).parent
    logo_path = base_dir / "suite_logo.png"

    if not logo_path.exists():
        logo_path = base_dir / "logo.png"

    if logo_path.exists():
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            splash = QSplashScreen(pixmap)
            splash.setWindowFlags(splash.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            splash.show()
            QApplication.processEvents()
            return splash

    return None
