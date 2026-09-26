"""Bootstrap for standalone diagnostic/maintenance scripts.

Scripts under ``scripts/`` are run directly (``python scripts/foo.py``), so the
repository root is not on ``sys.path``. Importing this module first inserts the
repository root so ``src`` and ``eval`` packages become importable while
keeping all imports at the top of each script (ruff/sorting clean).

Example::

    import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

    from src.llm.service import build_default_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
