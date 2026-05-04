"""HTTP client for the PivotalPath v2 API.

This module is the workhorse — package-level shortcuts in ``__init__``
delegate to a singleton instance of ``Client``. Most users should
import the package and call functions directly::

    import pivotalpath as pp
    pp.set_api_key("...")
    df = pp.fund_catalog(location='London')

Use ``Client`` directly when you need parallel keys, custom base URLs,
or explicit configuration::

    client = pp.Client(api_key="...", base_url="https://...")
    df = client.fund_catalog(...)
"""
from __future__ import annotations

import os
from functools import partial
from typing import Any

import requests

from .endpoints import (
    ENDPOINTS, FREE_ENDPOINTS, ENDPOINT_PARTS,
    API_CLASSES, API_FEATURES, resolve_endpoint,
)


# Asset-class auto-detection from id prefix. Single-letter prefixes
# only — ``f`` (fund), ``i`` (index), ``b`` (basket). Ids that don't
# start with one of these (e.g. arbitrary user-coined slugs) must use
# the explicit endpoint forms — ``pp.returns`` / ``pp.info`` will
# raise an ``InvalidParameter`` instead of guessing.
_CLASS_PREFIXES: tuple[tuple[str, str], ...] = (
    ('f', 'fund'),
    ('i', 'index'),
    ('b', 'basket'),
)


def _detect_asset_class(id_str: str) -> str | None:
    """Return ``'fund'`` / ``'index'`` / ``'basket'`` based on the id's
    leading characters. ``None`` if no prefix matches — caller decides
    how to surface that."""
    if not isinstance(id_str, str) or not id_str:
        return None
    s = id_str.lower()
    for prefix, cls in _CLASS_PREFIXES:
        if s.startswith(prefix):
            return cls
    return None


# Reserved query-parameter keys understood by the v2 server (separate
# from real column-name filters). Mirrors API_PARAM_ALIASES on the
# server. Keep in sync — adding a new reserved keyword needs both
# sides updated.
_RESERVED_KEYS: frozenset[str] = frozenset((
    'select',  'fields',     'show_fields',
    'pivot',   'tsformat',   'tsFormat',
    'pivot_columns', 'label', 'column_label',
    'tsLabel', 'tsName',     'tslabel',
    '_limit_', '_limit',     'limit_',     'limit',
    'date_min', 'start',     'start_date',
    'date_max', 'end',       'end_date',
    'id',      'apikey',     'Authorization',
))


# ----------------------------------------------------------------------
# Optional pandas dependency. Detected once at import. Calls return a
# ``pandas.DataFrame`` when pandas is installed, else ``list[dict]`` —
# same parsing path either way; the DataFrame wrap happens at the
# return boundary in ``Client.get``.
# ----------------------------------------------------------------------
try:
    import pandas as _pd
    HAS_PANDAS = True
except ImportError:
    _pd = None        # type: ignore
    HAS_PANDAS = False


DEFAULT_BASE_URL = os.environ.get(
    'PIVOTALPATH_BASE_URL',
    'https://apis.pivotalpath.com/resources/api/v2/',
)


def _merge_returns(parts, *, pivot: bool):
    """Combine per-class results from a multi-class ``returns(...)``
    fan-out. Pivoted: outer-join on ``date`` so each class contributes
    its own id columns. Non-pivoted: row-concat. Works with or without
    pandas — falls back to a manual dict merge for the no-pandas path.
    """
    if HAS_PANDAS:
        if pivot:
            out = parts[0]
            for p in parts[1:]:
                out = out.merge(p, on='date', how='outer')
            return out.sort_values('date').reset_index(drop=True)
        return _pd.concat(parts, ignore_index=True)

    if pivot:
        by_date: dict = {}
        for p in parts:
            for row in p:
                d = row.get('date')
                if d is None:
                    continue
                merged = by_date.setdefault(d, {'date': d})
                for k, v in row.items():
                    if k != 'date':
                        merged[k] = v
        return sorted(by_date.values(), key=lambda r: r['date'])

    out_list: list = []
    for p in parts:
        out_list.extend(p)
    return out_list


class PivotalPathError(Exception):
    """Raised when the v2 envelope reports a non-null ``error`` block,
    or when the HTTP response is not a parseable JSON envelope.

    Lives at the package root for tracebacks: ``__module__`` is set
    to ``'pivotalpath'`` so the displayed type reads
    ``pivotalpath.PivotalPathError`` instead of the long internal
    ``src.pivotalpath.client.PivotalPathError`` path.
    """

    def __init__(self, error_type: str, message: str,
                 status_code: int | None = None):
        self.type = error_type
        self.message = message
        self.status_code = status_code
        super().__init__(f'{error_type}: {message}')


# Pretty-print the class name in tracebacks.
PivotalPathError.__module__ = 'pivotalpath'


class Client:
    """One client per (api_key, base_url) pair.

    Parameters
    ----------
    api_key : str | None
        Authorization header for paid endpoints. Falls back to the
        ``PIVOTALPATH_API_KEY`` environment variable. Free endpoints
        (``index_catalog``, ``index_return``) work without a key.
    base_url : str | None
        v2 base URL (e.g. ``https://api.pivotalpath.com/resources/api/v2/``).
        Falls back to ``PIVOTALPATH_BASE_URL`` env var, then to the
        local-dev default.
    timeout : float
        Per-request timeout in seconds. Default 30.
    """

    def __init__(self, api_key: str | None = None,
                 base_url: str | None = None,
                 timeout: float = 30.0,
                 validate: bool = True):
        self.api_key  = api_key or os.environ.get('PIVOTALPATH_API_KEY')
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/') + '/'
        self.timeout  = timeout
        self.validate = validate
        self._session = requests.Session()
        # Schema cache: {endpoint: {column_name, ...}} or ``None``
        # if introspection failed (we then skip preflight gracefully).
        self._schema:  dict[str, set[str]] | None = None
        self._schema_attempted: bool = False

        # Per-endpoint shortcut bindings. Each is a ``functools.partial``
        # over the master ``Client.get`` with ``api_class`` and
        # ``api_feature`` pre-bound. ``partial`` is C-implemented in
        # CPython, so its ``__call__`` does NOT appear in Python
        # tracebacks — calling ``client.fund_catalog(...)`` jumps
        # straight from the user's frame into ``Client.get``, leaving
        # exactly one internal frame on error.
        for _ep, (_cls, _feat) in ENDPOINT_PARTS.items():
            self.__dict__[_ep] = partial(self.get,
                                          api_class=_cls,
                                          api_feature=_feat)

    # ------------------------------------------------------------------
    # Schema fetch + cache (lazy, one-shot per Client instance)
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        """Fetch ``GET /_schema`` once and cache as
        ``{endpoint: set(column_names)}``. Failure (route absent on an
        older server, network blip) leaves ``_schema`` as ``None`` —
        we then skip preflight rather than block legitimate calls."""
        if self._schema is not None or self._schema_attempted:
            return
        self._schema_attempted = True
        try:
            resp = self._session.get(self.base_url + '_schema',
                                       timeout=self.timeout)
            body = resp.json()
            if body.get('error') or not isinstance(body.get('data'), dict):
                return
            self._schema = {
                ep: {c['name'] for c in cols}
                for ep, cols in body['data'].items()
            }
        except Exception:
            # Graceful degradation — preflight is a nicety, not a gate.
            return

    def _preflight(self, endpoint: str,
                   params: dict) -> tuple[str, str] | None:
        """Validate ``endpoint`` + ``params`` against the cached
        schema. Returns ``(error_type, message)`` on failure or
        ``None`` on pass — the raise itself lives in ``Client.get`` so
        the visible traceback never contains this frame.
        """
        if endpoint not in ENDPOINTS:
            return ('UnknownEndpoint',
                    f"'{endpoint}' is not a known endpoint. "
                    f'Valid: {sorted(ENDPOINTS)}')

        if not self.validate:
            return None

        self._ensure_schema()
        if not self._schema or endpoint not in self._schema:
            return None  # schema unavailable → defer to server.

        cols = self._schema[endpoint]

        col_hint = ', '.join(sorted(cols))

        # Label-output keys (``pivot_columns``, ``label``, ``column_label``)
        # name a column to use as the *output* label after pivoting. That
        # column lives on the corresponding ``<class>_catalog`` (``name``,
        # ``firm``, ``peergroup`` …), not on the time-series endpoint
        # (which only has ``date``, ``id``, ``mtd``, …). Validate label
        # keys against the union of both schemas.
        label_cols = cols
        if '_' in endpoint and not endpoint.endswith('_catalog'):
            cat = endpoint.split('_', 1)[0] + '_catalog'
            cat_cols = self._schema.get(cat)
            if cat_cols:
                label_cols = cols | cat_cols
        label_hint = ', '.join(sorted(label_cols))

        def _check_col(value):
            if value is None:
                return None
            for v in (value if isinstance(value, (list, tuple)) else [value]):
                if v not in cols:
                    return ('InvalidParameter',
                            f"'{v}' is not a column on '{endpoint}'. "
                            f"Try: {col_hint}")
            return None

        def _check_label(value):
            if value is None:
                return None
            for v in (value if isinstance(value, (list, tuple)) else [value]):
                if v not in label_cols:
                    return ('InvalidParameter',
                            f"'{v}' is not a valid label column for "
                            f"'{endpoint}'. Try: {label_hint}")
            return None

        for key in ('select', 'fields', 'show_fields'):
            err = _check_col(params.get(key))
            if err:
                return err
        for key in ('pivot_columns', 'label', 'column_label'):
            err = _check_label(params.get(key))
            if err:
                return err

        # Filter kwargs (e.g. location='London') — the *key* must be
        # either a real column or a reserved query keyword. Allow
        # ``<col>_min`` / ``<col>_max`` / ``<col>_exclude`` suffixes
        # that the server's filter DSL strips.
        for k in params:
            if k in _RESERVED_KEYS or k in cols:
                continue
            stripped = next(
                (k[:-len(s)] for s in ('_min', '_max', '_exclude')
                 if k.endswith(s)),
                None,
            )
            if stripped is None or stripped not in cols:
                return ('InvalidParameter',
                        f"'{k}' is not a column on '{endpoint}'. "
                        f"Try: {col_hint}")

        return None

    # ------------------------------------------------------------------
    # Master call
    # ------------------------------------------------------------------
    def get(self,
            endpoint: str | None = None,
            *,
            api_class:   str | None = None,
            api_feature: str | None = None,
            select:  Any = None,
            limit:   Any = None,
            start:   Any = None,
            end:     Any = None,
            pivot:   Any = None,
            columns: Any = None,
            **filters: Any):
        """Call ``GET /<base_url>/<endpoint>?…`` and return its data.

        The endpoint can be given two ways — pick whichever reads
        better at the call site:

            client.get('fund_catalog', location='London')
            client.get(api_class='fund', api_feature='catalog',
                       location='London')

        ``api_class`` + ``api_feature`` is the structured form; the
        endpoint is built as ``f"{api_class}_{api_feature}"``. Common
        aliases (``returns`` → ``return``, ``funds`` → ``fund``, …)
        are resolved automatically.

        Reserved keywords (mapped to the server's canonical params):
            select   -> select
            limit    -> _limit_
            start    -> date_min     (also accepts date_min/start_date)
            end      -> date_max     (also accepts date_max/end_date)
            pivot    -> pivot
            columns  -> pivot_columns  ('id' or 'name' for time series)

        Everything else in ``**filters`` is passed through as a
        column-level filter. Returns ``pandas.DataFrame`` when pandas
        is installed, otherwise ``list[dict]``. Raises
        ``PivotalPathError`` on a non-null envelope error or a
        non-JSON response.
        """
        # Resolve the endpoint — either passed directly, or built
        # from api_class + api_feature.
        if endpoint is None:
            endpoint = resolve_endpoint(api_class, api_feature)
        if not endpoint:
            raise PivotalPathError(
                'InvalidParameter',
                'Pass either an endpoint string or both '
                "api_class and api_feature (e.g. api_class='fund', "
                "api_feature='catalog').",
            ) from None

        # Map reserved-keyword aliases onto the server's canonical
        # param names, then drop None values so they don't show up
        # as ``?key=None``. Pivot True/False stringifies to
        # "True"/"False"; the server already understands that shape.
        params: dict[str, Any] = dict(filters)
        if select  is not None: params['select']        = select
        if limit   is not None: params['_limit_']       = limit
        if start   is not None: params['date_min']      = start
        if end     is not None: params['date_max']      = end
        if pivot   is not None: params['pivot']         = pivot
        if columns is not None: params['pivot_columns'] = columns
        cleaned = {k: v for k, v in params.items() if v is not None}

        # Catalog-filter resolution: if the user passed kwargs that
        # belong to ``<class>_catalog`` (not to this endpoint's table),
        # do a 2-step lookup — fetch matching ids first, then run the
        # original query filtered by those ids. Lets users write
        # ``pp.fund_return(name='AQR%')`` without thinking about ids.
        cleaned, early_empty = self._resolve_catalog_filters(
            endpoint, cleaned)
        if early_empty:
            return _pd.DataFrame() if HAS_PANDAS else []

        # Preflight: catch obvious typos before the round-trip. Lifts
        # MySQL "Unknown column 'X'" errors into local
        # PivotalPathError('InvalidParameter', ...) with a helpful
        # message listing the legal columns. Raise in *this* frame so
        # the traceback shows only Client.get, not _preflight.
        pre_err = self._preflight(endpoint, cleaned)
        if pre_err is not None:
            raise PivotalPathError(*pre_err) from None

        return self._http_get(endpoint, cleaned)

    # ------------------------------------------------------------------
    # Raw HTTP — single round-trip, envelope unwrap, error → exception.
    # No preflight (caller decides). Used by ``get`` and by the catalog-
    # filter resolver.
    # ------------------------------------------------------------------
    def _http_get(self, endpoint: str, params: dict):
        url = self.base_url + endpoint.lstrip('/')
        headers: dict[str, str] = {}
        if self.api_key:
            headers['Authorization'] = self.api_key

        resp = self._session.get(url, headers=headers, params=params,
                                  timeout=self.timeout)
        try:
            body = resp.json()
        except ValueError:
            raise PivotalPathError(
                'BadResponse',
                f'Expected JSON envelope, got HTTP {resp.status_code}: '
                f'{resp.text[:200]}',
                status_code=resp.status_code,
            ) from None

        err = body.get('error')
        if err:
            raise PivotalPathError(
                err.get('type', 'Error'),
                err.get('message', ''),
                status_code=resp.status_code,
            ) from None

        data = body.get('data') or []
        if HAS_PANDAS:
            return _pd.DataFrame(data)
        return data

    # ------------------------------------------------------------------
    # Catalog-filter resolver: kwargs that belong to ``<class>_catalog``
    # but were passed to a non-catalog feature get turned into an
    # ``id=[...]`` filter via a one-shot catalog lookup.
    # ------------------------------------------------------------------
    def _resolve_catalog_filters(self, endpoint: str,
                                  params: dict) -> tuple[dict, bool]:
        """Return ``(new_params, early_empty)``.

        ``early_empty=True`` means "the catalog lookup matched zero
        rows — caller should short-circuit with an empty result rather
        than hit the data endpoint with ``id=[]``".

        No-op (returns ``(params, False)``) when:
          * schema isn't loaded (we can't tell catalog vs feature cols)
          * endpoint IS a catalog
          * caller already passed an explicit ``id`` (their choice wins)
          * none of the kwargs look like catalog filters
        """
        if '_' not in endpoint:
            return params, False
        cls, feature = endpoint.split('_', 1)
        if feature == 'catalog':
            return params, False
        if 'id' in params:
            return params, False  # explicit ids — don't override

        # We rely on the schema cache to tell catalog cols from
        # feature cols. Make sure it's loaded — preflight normally
        # does this, but it runs *after* us.
        self._ensure_schema()
        if not self._schema:
            return params, False

        feature_cols = self._schema.get(endpoint) or set()
        cat_endpoint = f'{cls}_catalog'
        cat_cols     = self._schema.get(cat_endpoint) or set()
        if not feature_cols or not cat_cols:
            return params, False

        catalog_filters: dict = {}
        passthrough:    dict = {}
        for k, v in params.items():
            if k in feature_cols or k in _RESERVED_KEYS:
                passthrough[k] = v
            elif k in cat_cols:
                catalog_filters[k] = v
            else:
                # Unknown elsewhere — let preflight surface the error.
                passthrough[k] = v

        if not catalog_filters:
            return params, False

        # Step 1: hit the catalog with select=id and the filters.
        cat_params = {**catalog_filters, 'select': 'id'}
        rows = self._http_get(cat_endpoint, cat_params)

        if HAS_PANDAS:
            ids = (rows['id'].dropna().astype(str).tolist()
                   if hasattr(rows, 'columns') and 'id' in rows.columns
                   else [])
        else:
            ids = [str(r['id']) for r in rows
                   if isinstance(r, dict) and r.get('id') is not None]

        if not ids:
            return passthrough, True

        passthrough['id'] = ids
        return passthrough, False

    # ------------------------------------------------------------------
    # Convenience helpers — auto-route by id prefix
    # ------------------------------------------------------------------
    def _route_by_id(self, id, *, where: str) -> tuple[list, str]:
        """Normalise ``id`` (str or list) and detect a single asset
        class from the prefixes. Returns ``(ids, api_class)``. Raises
        ``PivotalPathError`` with a user-friendly message on bad input.
        ``where`` is the surfacing helper name (``'returns'`` /
        ``'info'``) for clearer error messages.
        """
        if id is None:
            raise PivotalPathError(
                'InvalidParameter',
                f'{where}(id=...) requires at least one id.',
            ) from None
        ids = [id] if isinstance(id, str) else list(id)
        if not ids:
            raise PivotalPathError(
                'InvalidParameter',
                f'{where}(id=...) requires at least one id.',
            ) from None
        classes = {_detect_asset_class(x) for x in ids}
        classes.discard(None)
        if len(classes) > 1:
            raise PivotalPathError(
                'InvalidParameter',
                f'{where}(id=...): all ids must share the same asset '
                f'class; got mixed: {sorted(classes)}.',
            ) from None
        if not classes:
            raise PivotalPathError(
                'InvalidParameter',
                f"{where}(id=...): could not detect asset class from "
                f"prefix; first id was {ids[0]!r}. Expected ids to "
                f"start with 'f' (fund), 'i' (index), or 'b' (basket).",
            ) from None
        return ids, classes.pop()

    def returns(self, id: Any = None, *,
                api_class: Any = None,
                start: Any = None,
                end:   Any = None,
                pivot: bool = True,
                columns: str = 'id',
                **filters: Any):
        """Monthly returns — by id, or by catalog filters resolved
        across one or more asset classes.

        Two call shapes:

        1. ``returns(id=...)`` — pass an id (or list of ids) sharing a
           single asset class (``f<n>`` / ``mf<n>`` funds, ``i<n>`` /
           ``idx<n>`` indexes, ``b<n>`` baskets). Class is auto-detected
           from the prefix.

        2. ``returns(api_class=..., name='AQR%', ...)`` — no id; the
           call fans out per class, each running its own catalog lookup
           to translate the filters into ids. ``api_class`` accepts a
           single class string or a list; defaults to all three
           (``['fund', 'index', 'basket']``) when omitted. A class is
           silently skipped when its catalog/endpoint can't satisfy the
           filters (e.g. ``peergroup='CRD%'`` doesn't apply to baskets).

        ``columns`` controls the pivot label when ``pivot=True``:
        ``'id'`` (default) → column headers are asset ids, ``'name'``
        → human-readable names from the catalog.
        """
        if id is not None:
            ids, cls = self._route_by_id(id, where='returns')
            return self.get(
                api_class=cls, api_feature='return',
                id=ids, start=start, end=end,
                pivot=pivot, columns=columns,
                **filters,
            )

        if api_class is None:
            classes = ['fund', 'index', 'basket']
        elif isinstance(api_class, str):
            classes = [api_class]
        else:
            classes = list(api_class)

        if not classes:
            raise PivotalPathError(
                'InvalidParameter',
                'returns(...) needs api_class to be non-empty when id is omitted.',
            ) from None

        parts: list = []
        for cls in classes:
            try:
                part = self.get(
                    api_class=cls, api_feature='return',
                    start=start, end=end,
                    pivot=pivot, columns=columns,
                    **filters,
                )
            except PivotalPathError as e:
                # Skip a class whose catalog/endpoint can't accept these
                # filters (e.g. peergroup= on basket). Other errors raise.
                if e.type == 'InvalidParameter':
                    continue
                raise
            if HAS_PANDAS:
                if part is None or len(part) == 0:
                    continue
            elif not part:
                continue
            parts.append(part)

        if not parts:
            return _pd.DataFrame() if HAS_PANDAS else []
        if len(parts) == 1:
            return parts[0]
        return _merge_returns(parts, pivot=pivot)

    # ``mtd`` reads as the column name; some users prefer it as a
    # one-word alias of ``returns``. Same callable, different sticker.
    mtd = returns

    def info(self, id, *,
             select: Any = None,
             **filters: Any):
        """Catalog metadata for one or more ids — the row(s) that
        describe each asset (name, location, AUM, manager, …).

        ``id`` follows the same rules as ``returns``. Auto-routes to
        the corresponding ``<class>_catalog`` endpoint and filters by
        the supplied ids. Returns whatever the catalog table has;
        narrow with ``select=['name','aum',...]`` if you want fewer
        columns.
        """
        ids, api_class = self._route_by_id(id, where='info')
        return self.get(
            api_class=api_class, api_feature='catalog',
            id=ids, select=select, **filters,
        )

    # ------------------------------------------------------------------
    # Repr — useful when poking around in a notebook.
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        key = 'set' if self.api_key else 'unset'
        return (f'<pivotalpath.Client base_url={self.base_url!r} '
                f'api_key={key}>')


# Per-endpoint shortcuts are attached on each Client *instance* via
# ``functools.partial`` (see ``Client.__init__``). The .pyi stubs in
# this package declare them as methods of ``Client`` for type-checker
# benefit; at runtime they live in ``self.__dict__`` and are direct
# C-level wrappers around ``Client.get`` with the endpoint pre-bound.
