"""Compatibility entry point; use ``streamlit run app.py`` for RetailPulse."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import main  # noqa: E402


if __name__ == "__main__":
    main()
