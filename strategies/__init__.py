"""Auto-discover and register all candidate-generation strategy modules.

Each module in this package must expose:
  NAME: str          — short identifier used in --strategy CLI flag
  DESCRIPTION: str   — one-line human description
  get_candidates(starts: list[Stop], *, radius, results, **kwargs) -> list[Stop]
"""
import importlib
import pathlib
import pkgutil

REGISTRY: dict = {}

_here = pathlib.Path(__file__).parent
for _finder, _mod_name, _ in pkgutil.iter_modules([str(_here)]):
    _mod = importlib.import_module(f"strategies.{_mod_name}")
    if hasattr(_mod, "NAME"):
        REGISTRY[_mod.NAME] = _mod
