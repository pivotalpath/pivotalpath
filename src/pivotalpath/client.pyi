"""Type stubs for ``Client`` — see ``__init__.pyi`` for the rationale."""
from typing import Any

HAS_PANDAS: bool
DEFAULT_BASE_URL: str


class PivotalPathError(Exception):
    type: str
    message: str
    status_code: int | None
    def __init__(self, error_type: str, message: str,
                 status_code: int | None = ...) -> None: ...


class Client:
    api_key:  str | None
    base_url: str
    timeout:  float
    validate: bool

    def __init__(self,
                 api_key: str | None = ...,
                 base_url: str | None = ...,
                 timeout: float = ...,
                 validate: bool = ...) -> None: ...

    def get(self,
            endpoint: str | None = ...,
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

    def returns(self, id: Any, *,
                start:   Any = ...,
                end:     Any = ...,
                pivot:   bool = ...,
                columns: str = ...,
                **filters: Any) -> Any: ...
    mtd = returns

    def info(self, id: Any, *,
             select: Any = ...,
             **filters: Any) -> Any: ...

    # ---- per-endpoint shortcuts (mirror endpoints.ENDPOINT_TIERS) -----
    def fund_catalog       (self, **params: Any) -> Any: ...
    def fund_person        (self, **params: Any) -> Any: ...
    def fund_return        (self, **params: Any) -> Any: ...
    def fund_vote          (self, **params: Any) -> Any: ...
    def fund_aum           (self, **params: Any) -> Any: ...
    def index_catalog      (self, **params: Any) -> Any: ...
    def index_peergroup    (self, **params: Any) -> Any: ...
    def index_return       (self, **params: Any) -> Any: ...
    def basket_catalog     (self, **params: Any) -> Any: ...
    def basket_return      (self, **params: Any) -> Any: ...
    def notes_catalog      (self, **params: Any) -> Any: ...
    def pitchbooks_catalog (self, **params: Any) -> Any: ...
