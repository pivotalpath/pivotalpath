"""Key-less data path — serve the free endpoints from the public dataset.

When a :class:`~pivotalpath.client.Client` has no API key, ``index_catalog``
and ``index_return`` are read from the public GitHub repo
(``github.com/pivotalpath/publicdata``) instead of the HTTP API. Those two
are the only features available without a key.

This module holds the constants, CSV parsing, and a local query engine that
re-applies the same query semantics the v2 server would (``select``, ``id``,
date window, column filters, ``pivot``, ``_limit_``) so the documented
examples keep working offline. ``Client`` calls :func:`query` and wraps the
result in a ``DataFrame`` (or leaves it as ``list[dict]``) at the boundary,
exactly like the HTTP path.
"""
from __future__ import annotations

import csv as _csv
import io as _io
import os
import re as _re
from typing import Any


# The two endpoints available without an API key. Anything else needs a key.
PUBLIC_ENDPOINTS: frozenset[str] = frozenset({'index_catalog', 'index_return'})

# Static schema for the public endpoints — mirrors the CSV headers in the
# publicdata repo. Lets preflight + catalog-filter resolution work key-less
# without an HTTP ``/_schema`` round-trip.
PUBLIC_SCHEMA: dict[str, set[str]] = {
    'index_catalog': {'id', 'name', 'abstract'},
    'index_return':  {'date', 'id', 'mtd'},
}

_DEFAULT_BASE = 'https://raw.githubusercontent.com/pivotalpath/publicdata/main/'

# Keys that are reserved query controls, NOT column filters. Mirrors the
# server's param vocabulary; anything not here is treated as a column filter.
_NON_FILTER_KEYS: frozenset[str] = frozenset({
    'id', 'select', 'fields', 'show_fields',
    'pivot', 'pivot_columns', 'columns', 'label', 'column_label',
    'tsformat', 'tsFormat', 'tslabel', 'tsLabel', 'tsName',
    '_limit_', '_limit', 'limit_', 'limit',
    'date_min', 'date_max', 'start', 'end', 'start_date', 'end_date',
    'apikey', 'Authorization',
})


def base_url() -> str:
    """Raw-content base for the public dataset. Override with the
    ``PIVOTALPATH_PUBLICDATA_URL`` env var (e.g. to point at a fork or a
    local checkout served over HTTP)."""
    return os.environ.get('PIVOTALPATH_PUBLICDATA_URL', _DEFAULT_BASE).rstrip('/') + '/'


def parse_csv(text: str) -> list[dict]:
    """Parse raw CSV text into ``list[dict]``. ``mtd`` is coerced to float;
    everything else stays a string (matching the JSON the API would return)."""
    rows: list[dict] = []
    for row in _csv.DictReader(_io.StringIO(text)):
        mtd = row.get('mtd')
        if mtd not in (None, ''):
            try:
                row['mtd'] = float(mtd)
            except (TypeError, ValueError):
                pass
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Small value helpers
# ----------------------------------------------------------------------
def _as_list(value: Any) -> list:
    """Normalise a param value to a list. Splits comma-strings so
    ``select='id,name'`` and ``select=['id','name']`` behave the same."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str) and ',' in value:
        return [v.strip() for v in value.split(',')]
    return [value]


def is_truthy(value: Any) -> bool:
    """Accept Python ``True`` or the string forms the server understands."""
    if value is None:
        return False
    return str(value).strip().lower() in ('true', '1', 'yes')


def _norm_month(value: Any) -> str | None:
    """Reduce a date to comparable digits — ``'2024-01'`` and ``'202401'``
    both become ``'202401'`` so the CSV's ``YYYY-MM`` and the API's
    ``YYYYMM`` window params compare directly."""
    if value is None:
        return None
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    return digits or None


def _cmp(a: Any, b: Any) -> int:
    """Three-way compare; numeric when both sides parse as float, else string."""
    try:
        fa, fb = float(a), float(b)
        return (fa > fb) - (fa < fb)
    except (TypeError, ValueError):
        sa, sb = str(a), str(b)
        return (sa > sb) - (sa < sb)


def _like(cell: Any, pattern: str) -> bool:
    """SQL-LIKE match: ``%`` is a wildcard, the rest is literal,
    case-insensitive (matching the server's filter DSL)."""
    if cell is None:
        return False
    rx = '^' + '.*'.join(_re.escape(p) for p in str(pattern).split('%')) + '$'
    return _re.match(rx, str(cell), _re.IGNORECASE) is not None


def _apply_col_filter(rows: list[dict], key: str, value: Any,
                      cols: set[str]) -> list[dict]:
    """Filter ``rows`` by one column kwarg. Supports ``<col>_min`` /
    ``<col>_max`` / ``<col>_exclude`` suffixes, list membership, ``%``
    LIKE wildcards, and exact match. Unrecognised keys are ignored (the
    server would too — preflight already flags genuine typos)."""
    for suf, op in (('_min', 'min'), ('_max', 'max'), ('_exclude', 'exclude')):
        if key.endswith(suf) and key[:-len(suf)] in cols:
            base = key[:-len(suf)]
            if op == 'min':
                return [r for r in rows if _cmp(r.get(base), value) >= 0]
            if op == 'max':
                return [r for r in rows if _cmp(r.get(base), value) <= 0]
            excl = {str(x) for x in _as_list(value)}
            return [r for r in rows if str(r.get(base)) not in excl]

    if key not in cols:
        return rows  # not a known column — leave rows untouched

    wanted = _as_list(value)

    def _match(cell: Any) -> bool:
        for v in wanted:
            if isinstance(v, str) and '%' in v:
                if _like(cell, v):
                    return True
            elif str(cell) == str(v):
                return True
        return False

    return [r for r in rows if _match(r.get(key))]


def query(endpoint: str, rows: list[dict], params: dict, *,
          name_map: dict | None = None) -> list[dict]:
    """Apply the v2 query params to locally-loaded ``rows`` and return the
    result as ``list[dict]`` (long form, or wide form when ``pivot`` is set).

    ``name_map`` (id -> name, from the catalog) is used only for
    ``pivot_columns='name'``.
    """
    cols = PUBLIC_SCHEMA.get(endpoint, set())
    rows = list(rows)

    # id filter
    if params.get('id') is not None:
        wanted = {str(x) for x in _as_list(params['id'])}
        rows = [r for r in rows if str(r.get('id')) in wanted]

    # date window (only meaningful where there's a date column)
    if 'date' in cols and (params.get('date_min') is not None
                           or params.get('date_max') is not None):
        nmin = _norm_month(params.get('date_min'))
        nmax = _norm_month(params.get('date_max'))

        def _in_range(r: dict) -> bool:
            d = _norm_month(r.get('date'))
            if d is None:
                return False
            if nmin is not None and d < nmin:
                return False
            if nmax is not None and d > nmax:
                return False
            return True

        rows = [r for r in rows if _in_range(r)]

    # column filters
    for k, v in params.items():
        if k not in _NON_FILTER_KEYS:
            rows = _apply_col_filter(rows, k, v, cols)

    # pivot (wide form) — only for the returns time-series
    if is_truthy(params.get('pivot')) and {'date', 'mtd'} <= cols:
        label_key = params.get('pivot_columns') or params.get('columns') or 'id'

        def _col(r: dict) -> str:
            rid = str(r.get('id'))
            if label_key == 'name' and name_map is not None:
                return str(name_map.get(rid, rid))
            if label_key in cols and label_key != 'mtd':
                return str(r.get(label_key))
            return rid

        dates = sorted({r.get('date') for r in rows if r.get('date') is not None})
        wide = {d: {'date': d} for d in dates}
        for r in rows:
            d = r.get('date')
            if d is not None:
                wide[d][_col(r)] = r.get('mtd')
        rows = [wide[d] for d in dates]
    else:
        # select (long form only) — restrict columns
        sel = (params.get('select') or params.get('fields')
               or params.get('show_fields'))
        if sel:
            keep = _as_list(sel)
            rows = [{k: r.get(k) for k in keep} for r in rows]

    # limit
    lim = params.get('_limit_')
    if lim is None:
        lim = params.get('limit')
    if lim is not None:
        try:
            rows = rows[:int(lim)]
        except (TypeError, ValueError):
            pass

    return rows
