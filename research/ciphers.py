"""Import the handwritten cipher module (``encyption.py``)."""

from __future__ import annotations

import sys
from types import ModuleType

from research.paths import ROOT

_MODULE: ModuleType | None = None


def load_encyption() -> ModuleType:
    """Load ``encyption.py`` from the repo root.

    The filename is missing an "r". This loader keeps that file as the source
    of truth for every cipher.
    """
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import encyption
    except ModuleNotFoundError as exc:
        if exc.name == "Crypto":
            raise SystemExit(
                "pycryptodome is required to import encyption.py.\n"
                "Install it with: python3 -m pip install pycryptodome"
            ) from exc
        raise
    _MODULE = encyption
    return encyption
