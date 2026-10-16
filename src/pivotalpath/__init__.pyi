"""Type stubs for the pivotalpath package.

Why a .pyi: ``__init__.py`` binds ``get``/``returns``/``mtd``/``info`` at
import time and resolves ``pp.<endpoint>`` dynamically via the module's
``__getattr__``. Type-checkers can't see those, so this stub declares the
hand-written symbols plus a ``__getattr__`` fallback that lets
``pp.<anything>(...)`` type-check.

The package is schema-agnostic: no endpoint names are declared here.
"""
from typing import Any, List

from .client import (
    Client as Client,
    PivotalPathError as PivotalPathError,
    HAS_PANDAS as HAS_PANDAS,
    DEFAULT_BASE_URL as DEFAULT_BASE_URL,
)

__version__: str
__all__: List[str]


# ---- module-level configuration helpers ---------------------------------
def set_api_key(api_key: str) -> None: ...
def set_base_url(base_url: str) -> None: ...
def reference(*, raw: bool = ...) -> Any: ...
def help() -> None: ...
def install_excepthook(force: bool = ...) -> bool: ...
def uninstall_excepthook() -> bool: ...


# ---- generic call ------------------------------------------------------
def get(endpoint: str | None = ...,
        *,
        api_class:   str | None = ...,
        api_feature: str | None = ...,
        select:  Any = ...,
        limit:   Any = ...,
        start:   Any = ...,
        end:     Any = ...,
        pivot:   Any = ...,
        columns: Any = ...,
        **filters: Any) -> Any: ...


# ---- convenience helpers (auto-route by id prefix) ----------------------
def returns(id: Any, *,
            start:   Any = ...,
            end:     Any = ...,
            pivot:   bool = ...,
            columns: str = ...,
            **filters: Any) -> Any: ...
def mtd(id: Any, *,
        start:   Any = ...,
        end:     Any = ...,
        pivot:   bool = ...,
        columns: str = ...,
        **filters: Any) -> Any: ...
def info(id: Any, *,
         select: Any = ...,
         **filters: Any) -> Any: ...


# ---- dynamic per-endpoint shortcuts ------------------------------------
# pp.<endpoint>(...) is shorthand for pp.get('<endpoint>', ...). Endpoint
# names are not enumerated here — they come from your API reference.
def __getattr__(name: str) -> Any: ...
