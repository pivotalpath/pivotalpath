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

    def returns(self, id: Any = ..., *,
                api_class: Any = ...,
                start:     Any = ...,
                end:       Any = ...,
                pivot:     bool = ...,
                columns:   str = ...,
                **filters: Any) -> Any: ...
    mtd = returns

    def info(self, id: Any, *,
             select: Any = ...,
             **filters: Any) -> Any: ...

    def reference(self, *, raw: bool = ...) -> Any: ...
    def help(self) -> None: ...

    # Per-endpoint shortcuts resolve dynamically: client.<endpoint>(...) is
    # shorthand for client.get('<endpoint>', ...). Endpoint names are not
    # enumerated here — they come from your API reference.
    def __getattr__(self, name: str) -> Any: ...
