"""Generic endpoint-name resolution for the v2 API.

The package is deliberately **schema-agnostic** — it does NOT enumerate the
server's endpoints. The caller names the endpoint (``pp.get('foo_bar')`` or
the dynamic shortcut ``pp.foo_bar(...)``); this module only normalises the
structured ``api_class`` + ``api_feature`` form, plus a few generic
plural/shorthand aliases, into the ``<class>_<feature>`` the server expects.

Nothing proprietary lives here — only generic vocabulary (asset classes and
feature words) needed to build a name from caller-supplied parts.
"""
from __future__ import annotations


# Forgiving aliases — generic plural/shorthand forms a caller might type in
# the structured ``api_class`` / ``api_feature`` form. Intentionally generic:
# no specific endpoint names.
FEATURE_ALIASES: dict[str, str] = {
    'returns':         'return',
    'returns_series':  'return',
    'timeseries':      'return',
}
CLASS_ALIASES: dict[str, str] = {
    'indices':  'index',
    'indexes':  'index',
}


def resolve_endpoint(api_class: str | None,
                     api_feature: str | None) -> str | None:
    """``('index', 'return')`` -> ``'index_return'``.

    Applies the alias maps (so ``returns`` -> ``return``, etc.) and returns
    ``None`` if either side is empty. The composed name is sent to the server
    as-is; an unknown name surfaces as the server's own error.
    """
    if not api_class or not api_feature:
        return None
    cls  = CLASS_ALIASES.get(api_class,   api_class)
    feat = FEATURE_ALIASES.get(api_feature, api_feature)
    return f'{cls}_{feat}'
