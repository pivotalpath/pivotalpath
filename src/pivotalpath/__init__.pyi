"""Type stubs for the pivotalpath package.

Why a .pyi: ``__init__.py`` builds module-level shortcut functions and
``Client`` methods at import time via ``setattr`` (driven by
``endpoints.py``). Type-checkers can't see those — to them, only the
hand-written symbols exist. This stub declares every endpoint
explicitly so IDEs (Pyright/Pylance/mypy) stop flagging
``pp.fund_catalog(...)`` as unknown.

Update rule: when you add an endpoint to ``endpoints.py``, add a
matching ``def <name>(...)`` line here AND in ``client.pyi``. (No
runtime impact — these are read by static analysers only.)
"""
from typing import Any, List

from .client import (
    Client as Client,
    PivotalPathError as PivotalPathError,
    HAS_PANDAS as HAS_PANDAS,
    DEFAULT_BASE_URL as DEFAULT_BASE_URL,
)
from .endpoints import (
    ENDPOINTS as ENDPOINTS,
    ENDPOINT_TIERS as ENDPOINT_TIERS,
    FREE_ENDPOINTS as FREE_ENDPOINTS,
    PAID_ENDPOINTS as PAID_ENDPOINTS,
)

__version__: str
__all__: List[str]


# ---- module-level configuration helpers ---------------------------------
def set_api_key(api_key: str) -> None: ...
def set_base_url(base_url: str) -> None: ...
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


# ---- per-endpoint shortcuts (mirror endpoints.ENDPOINT_TIERS) ----------
def fund_catalog       (**params: Any) -> Any: ...
def fund_person        (**params: Any) -> Any: ...
def fund_return        (**params: Any) -> Any: ...
def fund_vote          (**params: Any) -> Any: ...
def fund_aum           (**params: Any) -> Any: ...
def index_catalog      (**params: Any) -> Any: ...
def index_peergroup    (**params: Any) -> Any: ...
def index_return       (**params: Any) -> Any: ...
def basket_catalog     (**params: Any) -> Any: ...
def basket_return      (**params: Any) -> Any: ...
def notes_catalog      (**params: Any) -> Any: ...
def pitchbooks_catalog (**params: Any) -> Any: ...
