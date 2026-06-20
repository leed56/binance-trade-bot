"""Strategy plugin loader.

Mirrors binance_trade_bot/strategies/__init__.py: any file named ``*_strategy.py``
in this package exposing a ``Strategy`` class is loadable by its short name
(filename minus ``_strategy.py``).
"""
import importlib
import os


def get_strategy(name):
    """Load the Strategy class from ``<name>_strategy.py`` in this package.

    Imported as a proper submodule (not by raw file path) so the strategies'
    relative imports (``from .base import ...``) resolve correctly.
    """
    filename = f"{name}_strategy.py"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), filename)):
        return None
    module = importlib.import_module(f"{__package__}.{name}_strategy")
    return getattr(module, "Strategy", None)


def load_enabled(names, config, logger):
    strategies = []
    for name in names:
        cls = get_strategy(name)
        if cls is None:
            logger.warning(f"Unknown strategy '{name}', skipping")
            continue
        strategies.append(cls(config, logger))
    return strategies
