"""
Application entry point.

Usage:
    python main.py
"""

from pathlib import Path
import sys

# Ensure src/ is on the Python module search path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.app import App


def main():
    """Initialize and run the desktop application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
