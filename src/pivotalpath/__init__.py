"""PivotalPath API — Python wrapper for the v2 endpoint contract.

Quick start::

    import pivotalpath as pp

    # Free, no key needed (served from the public dataset):
    indices = pp.index_catalog()
    rets    = pp.index_return(id='iHFC', date_min='202401', pivot=True)

    # Paid endpoints — set your key first:
    pp.set_api_key("YOUR_API_KEY")
    rows = pp.get('your_endpoint', some_filter='value')   # generic call
    rows = pp.your_endpoint(some_filter='value')          # same, via shortcut

    # Discover what your key can call (served live by the API):
    pp.help()                # how to get started
    pp.reference()           # endpoints, groups, parameters

    # Explicit clients for parallel keys / staging vs prod:
    prod = pp.Client(api_key="...", base_url="https://...")

Endpoint names come from your API reference (https://apis.pivotalpath.com) —
not from this package. Any ``pp.<name>(...)`` is shorthand for
``pp.get('<name>', ...)``.

When ``pandas`` is installed, every call returns a ``DataFrame``; otherwise it
returns a plain ``list[dict]`` — the package detects pandas at import time.
"""
from __future__ import annotations

import sys      as _sys
import types    as _types
from functools import partial
from typing    import Any

from ._version    import __version__
from .client      import Client, PivotalPathError, HAS_PANDAS, DEFAULT_BASE_URL
from ._excepthook import install_excepthook, uninstall_excepthook


# Singleton client backing the module-level shortcuts. Eagerly created so
# the bound-method shortcuts below (``pp.get`` / ``pp.returns`` / …) and the
# dynamic ``pp.<endpoint>`` resolver point straight at ``Client.get``. That
# matters for tracebacks: a stack at the moment of an error then has only the
# user's call frame and the ``Client`` raise — no wrapper closure in between.
_default: Client = Client()


def _rebind_shortcuts() -> None:
    """Point the module-level shortcuts at the current ``_default`` Client.
    ``pp.get`` / ``pp.returns`` / ``pp.mtd`` / ``pp.info`` are direct bound
    methods. Per-endpoint shortcuts (``pp.<endpoint>``) are NOT bound here —
    they resolve dynamically through ``_ProtectedModule.__getattr__`` against
    the current ``_default``, so the package never enumerates endpoint names.
    Called whenever ``_default`` is replaced (e.g. by ``set_api_key``).
    """
    g = globals()
    g['get']     = _default.get
    g['returns'] = _default.returns
    g['mtd']     = _default.mtd
    g['info']    = _default.info
    g['reference'] = _default.reference
    g['help']      = _default.help


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
    'set_api_key', 'set_base_url', 'get', 'returns', 'mtd', 'info',
    'reference', 'help',
    'install_excepthook', 'uninstall_excepthook',
]


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
    def __getattr__(self, name):
        # Dynamic per-endpoint shortcut: ``pp.<endpoint>(...)`` resolves to a
        # ``functools.partial`` over the singleton's ``get``. Only fires for
        # names not already in the module (so the real public API is untouched).
        # The package never enumerates endpoint names — the caller supplies
        # them. Underscore / non-lowercase names raise AttributeError so
        # dunders, IPython probes, and would-be constants aren't dispatched.
        if name.startswith('_') or not name.islower():
            raise AttributeError(
                f'module {__name__!r} has no attribute {name!r}')
        return partial(_default.get, name)

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
