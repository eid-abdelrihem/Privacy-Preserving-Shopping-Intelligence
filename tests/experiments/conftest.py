"""Ensure the project root is on sys.path for experiment tests.

This is needed because pyproject.toml uses ``package = false``,
so the project root is not automatically added to sys.path by pytest.
"""

import sys
from pathlib import Path

# Add the project root to sys.path so that ``import scripts.experiments``
# works during pytest collection.
_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
