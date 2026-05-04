"""PivotalPath API — Python wrapper for the v2 endpoint contract.

Quick start::

    import pivotalpath as pp
    pp.set_api_key("YOUR_API_KEY")

    indices = pp.index_catalog()                # free, no key needed
    funds   = pp.fund_catalog(location='London')
    rets    = pp.fund_return(id=['f123'], date_min='202401')

    # Generic call — works for any endpoint:
    rows    = pp.get('basket_return', date_min='202401')

    # Explicit clients for parallel keys / staging / prod:
    prod = pp.Client(api_key="...", base_url="https://prod...")
    dev  = pp.Client(api_key="...", base_url="https://dev...")

When ``pandas`` is installed, every call returns a ``DataFrame``;
otherwise it returns a plain ``list[dict]``. No code change needed —
the package detects pandas at import time.
"""
from __future__ import annotations

import sys      as _sys
import types    as _types
from functools import partial
from typing    import Any

from ._version    import __version__
from .client      import Client, PivotalPathError, HAS_PANDAS, DEFAULT_BASE_URL
from .endpoints   import (ENDPOINTS, ENDPOINT_TIERS, ENDPOINT_PARTS,
                            FREE_ENDPOINTS, PAID_ENDPOINTS,
                            API_CLASSES, API_FEATURES)
from ._excepthook import install_excepthook, uninstall_excepthook


# Singleton client backing module-level shortcuts. Eagerly created so
# the bound-method shortcuts below (``pp.get``, ``pp.fund_catalog``,
# …) point straight at ``Client.get`` / ``Client.<endpoint>``. That
# matters for tracebacks: a stack at the moment of an error then has
# only the user's call frame and the ``Client`` raise — no wrapper
# closure in between.
_default: Client = Client()


def _rebind_shortcuts() -> None:
    """Point every module-level shortcut at the current ``_default``
    Client. ``pp.get`` / ``pp.returns`` / ``pp.mtd`` / ``pp.info`` are
    direct bound methods; per-endpoint shortcuts are
    ``functools.partial`` wrappers over the master ``get`` with
    ``api_class`` and ``api_feature`` pre-bound (C-level, so they
    don't add a Python frame to tracebacks). Called whenever
    ``_default`` is replaced (e.g. by ``set_api_key``).
    """
    g = globals()
    g['get']     = _default.get
    g['returns'] = _default.returns
    g['mtd']     = _default.mtd
    g['info']    = _default.info
    for _ep, (_cls, _feat) in ENDPOINT_PARTS.items():
        g[_ep] = partial(_default.get,
                          api_class=_cls, api_feature=_feat)


def set_api_key(api_key: str) -> None:
    """Set the API key used by module-level shortcuts.

    Equivalent to setting the ``PIVOTALPATH_API_KEY`` env var before
    import. Re-creates the singleton so subsequent calls pick up the
    new key without restarting the process.
    """
    global _default
    _default = Client(api_key=api_key, base_url=_default.base_url)
    _rebind_shortcuts()


def set_base_url(base_url: str) -> None:
    """Override the v2 base URL on the singleton client (e.g., point
    at staging). Re-creates the singleton in place."""
    global _default
    _default = Client(api_key=_default.api_key, base_url=base_url)
    _rebind_shortcuts()


# Bind ``pp.get`` and every ``pp.<endpoint>`` directly to the
# corresponding bound method on the singleton. After this line, calls
# go straight to ``Client.<method>`` — no wrapper closure in between.
_rebind_shortcuts()


# Note: no auto-install of the clean-error display hook. Replacing
# ``sys.excepthook`` as a side effect of ``import`` is considered
# bad form (it surprises collaborators, collides with other tools,
# and hides debugging info). Users who want the one-line ``Error:
# <message>`` rendering can call ``pivotalpath.install_excepthook()``
# explicitly — typically once at the top of an analysis notebook.


__all__ = [
    '__version__',
    'Client', 'PivotalPathError', 'HAS_PANDAS', 'DEFAULT_BASE_URL',
    'ENDPOINTS', 'ENDPOINT_TIERS', 'FREE_ENDPOINTS', 'PAID_ENDPOINTS',
    'set_api_key', 'set_base_url', 'get', 'returns', 'mtd', 'info',
    'install_excepthook', 'uninstall_excepthook',
] + list(ENDPOINTS)


# ----------------------------------------------------------------------
# Public-API write protection. Catches typos like
# ``pp.set_api_key = 'pp-...'`` (with ``=`` instead of ``(...)`` ) which
# would otherwise silently shadow the function with a string and surface
# later as a confusing ``TypeError: 'str' object is not callable``.
#
# Internal rebinds inside this package use ``globals()[name] = value`` —
# that goes through the module's ``__dict__`` directly and bypasses
# ``__setattr__``, so ``set_api_key`` / ``set_base_url`` keep working.
# ----------------------------------------------------------------------
class _ProtectedModule(_types.ModuleType):
    def __setattr__(self, name, value):
        protected = self.__dict__.get('_PROTECTED_NAMES')
        if protected is not None and name in protected:
            raise AttributeError(
                f"cannot reassign 'pivotalpath.{name}' — it is part of "
                f"the public API. Did you mean to call it: "
                f"pp.{name}(...) ?"
            )
        super().__setattr__(name, value)


_PROTECTED_NAMES: frozenset[str] = frozenset(__all__)
_sys.modules[__name__].__class__ = _ProtectedModule
