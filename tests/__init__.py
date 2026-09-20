"""Test package.

Adds ``src/`` to ``sys.path`` so the suite runs from a bare checkout
(``python -m unittest discover``) as well as from an installed package
(``pip install -e .[dev] && pytest``).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
