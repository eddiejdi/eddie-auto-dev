"""Specialized agents package.

Fallback loader:
- no homelab, alguns modulos existem apenas como ``.pyc`` em ``__pycache__``
- este finder permite importar ``specialized_agents.*`` diretamente desses
  bytecodes quando o arquivo ``.py`` correspondente nao estiver presente
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path


class _SpecializedAgentsPycFinder(importlib.abc.MetaPathFinder):
    """Resolve submodulos do pacote a partir de ``__pycache__`` quando preciso."""

    def __init__(self, package_dir: Path) -> None:
        self._package_dir = package_dir
        self._pycache_dir = package_dir / "__pycache__"
        self._package_name = __name__

    def find_spec(self, fullname: str, path=None, target=None):  # type: ignore[override]
        if not fullname.startswith(self._package_name + "."):
            return None

        module_name = fullname.rsplit(".", 1)[-1]
        source_path = self._package_dir / f"{module_name}.py"
        if source_path.exists():
            return None

        pyc_candidates = sorted(
            self._pycache_dir.glob(f"{module_name}.cpython-*.pyc")
        )
        if not pyc_candidates:
            return None

        pyc_path = pyc_candidates[-1]
        loader = importlib.machinery.SourcelessFileLoader(fullname, str(pyc_path))
        return importlib.util.spec_from_loader(fullname, loader, origin=str(pyc_path))


_package_dir = Path(__file__).resolve().parent
_finder = _SpecializedAgentsPycFinder(_package_dir)

if not any(isinstance(finder, _SpecializedAgentsPycFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _finder)
