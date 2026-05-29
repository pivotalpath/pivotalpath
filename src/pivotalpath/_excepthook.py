"""Pretty-print PivotalPathError as ``Error: <message>`` instead of a
full Python traceback in interactive contexts (plain REPL + IPython /
Jupyter). Auto-installs at package import in interactive mode;
opt-out with ``pivotalpath.uninstall_excepthook()``.

For scripts and tests, the full traceback is preserved — that's what
you want when debugging from the call site. Toggle behaviour at any
time with ``install_excepthook()`` / ``uninstall_excepthook()``.
"""
from __future__ import annotations

import sys
from typing import Any

from .client import PivotalPathError


# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------
def _format(exc: PivotalPathError) -> str:
    """One-line error rendering. Drops the python type prefix; keeps
    the ``message`` body so the user sees only what's actionable."""
    return f'Error: {exc.message}'


# ----------------------------------------------------------------------
# Plain-Python REPL: replace ``sys.excepthook``
# ----------------------------------------------------------------------
_prev_excepthook: Any = None


def _hook(exc_type, exc_value, exc_tb):
    if isinstance(exc_value, PivotalPathError):
        print(_format(exc_value), file=sys.stderr)
        return
    if _prev_excepthook is not None:
        _prev_excepthook(exc_type, exc_value, exc_tb)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)


_hook._pp_installed = True  # type: ignore[attr-defined]


def _is_interactive() -> bool:
    """REPL or ``python -i``? IPython sets neither so we detect it
    separately below."""
    return hasattr(sys, 'ps1') or bool(getattr(sys.flags, 'interactive', 0))


# ----------------------------------------------------------------------
# IPython / Jupyter: register a custom exception handler
# ----------------------------------------------------------------------
_ipython_installed = False


def _try_install_ipython() -> bool:
    """Register an IPython traceback handler for PivotalPathError.
    Returns True if IPython is available and the handler was set."""
    global _ipython_installed
    try:
        from IPython import get_ipython  # type: ignore
    except ImportError:
        return False
    ip = get_ipython()
    if ip is None:
        return False

    def _ipy_handler(self, etype, value, tb, tb_offset=None):
        # The signature is fixed by IPython; ``self`` is the shell.
        print(_format(value), file=sys.stderr)

    ip.set_custom_exc((PivotalPathError,), _ipy_handler)
    _ipython_installed = True
    return True


def _try_uninstall_ipython() -> bool:
    """Clear the custom handler we installed, if any."""
    global _ipython_installed
    try:
        from IPython import get_ipython  # type: ignore
    except ImportError:
        return False
    ip = get_ipython()
    if ip is None:
        return False
    # Passing an empty tuple clears any custom handler — IPython's
    # documented way to remove a registered exception class.
    ip.set_custom_exc((), None)
    _ipython_installed = False
    return True


# ----------------------------------------------------------------------
# Public toggles
# ----------------------------------------------------------------------
def install_excepthook(force: bool = False) -> bool:
    """Install the clean-error hook for the current Python session.

    By default only installs when running in an interactive context
    (REPL, ``python -i``, IPython, Jupyter). Pass ``force=True`` to
    install unconditionally — useful for scripts where you'd rather
    surface a one-liner than a stack trace.

    Returns True if a hook was installed (or was already in place).
    Idempotent — calling twice is harmless.
    """
    global _prev_excepthook

    if not force and not _is_interactive() and not _try_install_ipython():
        return False

    # IPython case: handler was set above, don't touch sys.excepthook.
    if _ipython_installed:
        return True

    # Plain REPL / forced install: replace sys.excepthook.
    if getattr(sys.excepthook, '_pp_installed', False):
        return True   # already installed
    _prev_excepthook = sys.excepthook
    sys.excepthook = _hook
    return True


def uninstall_excepthook() -> bool:
    """Restore Python's default traceback rendering for
    PivotalPathError. Returns True if anything was removed."""
    global _prev_excepthook
    removed = False
    if _ipython_installed:
        if _try_uninstall_ipython():
            removed = True
    if getattr(sys.excepthook, '_pp_installed', False):
        sys.excepthook = (_prev_excepthook
                          if _prev_excepthook is not None
                          else sys.__excepthook__)
        _prev_excepthook = None
        removed = True
    return removed
