import argparse
import sys
from malachi.config import Settings
from malachi.telemetry.logging import configure_logging


def main():
    parser = argparse.ArgumentParser(description="MALACHI autonomous skull")
    parser.add_argument(
        "--demo", action="store_true", help="Offline synthetic camera and mock audio"
    )
    parser.add_argument("--vision-only", action="store_true", help="Disable conversations")
    parser.add_argument(
        "--smoke-seconds",
        type=float,
        default=0,
        help="Quit after this many seconds (for automated dashboard smoke checks)",
    )
    args = parser.parse_args()
    settings = Settings()
    if args.demo:
        settings.conversation_backend = "mock"
        settings.vision_context_enabled = False
        settings.motion_backend = "simulation"
    if args.vision_only:
        settings.conversation_backend = "disabled"
        settings.vision_context_enabled = False
    configure_logging(settings.debug_mode)
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from malachi.ui.dashboard import Dashboard

    app = QApplication(sys.argv[:1])
    window = Dashboard(settings, args.demo)
    window.show()
    if args.smoke_seconds:
        QTimer.singleShot(int(args.smoke_seconds * 1000), window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
