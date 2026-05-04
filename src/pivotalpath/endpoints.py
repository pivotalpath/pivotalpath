"""Source of truth for the v2 endpoint catalog.

Kept manually in sync with the API server's ``API_ENDPOINT_TIERS``.
When the server adds an endpoint, add it here too — the client and the
package's module-level shortcuts pick it up automatically.
"""
from __future__ import annotations


# Endpoint name -> 'free' | 'paid' tier.
ENDPOINT_TIERS: dict[str, str] = {
    'fund_catalog':       'paid',
    'fund_person':        'paid',
    'fund_return':        'paid',
    'fund_vote':          'paid',
    'fund_aum':           'paid',
    'index_catalog':      'free',
    'index_peergroup':    'paid',
    'index_return':       'free',   # the index time-series
    'basket_catalog':     'paid',
    'basket_return':      'paid',
    'notes_catalog':      'paid',
    'pitchbooks_catalog': 'paid',
}

ENDPOINTS:      tuple[str, ...] = tuple(ENDPOINT_TIERS)
FREE_ENDPOINTS: frozenset[str]  = frozenset(
    ep for ep, t in ENDPOINT_TIERS.items() if t == 'free')
PAID_ENDPOINTS: frozenset[str]  = frozenset(
    ep for ep, t in ENDPOINT_TIERS.items() if t == 'paid')


# ``api_class`` / ``api_feature`` decomposition. The endpoint is
# always ``f"{api_class}_{api_feature}"``. Split on the *first*
# underscore so multi-word features (e.g. ``peergroup``) and
# multi-word classes (e.g. ``pitchbooks``) both resolve cleanly.
ENDPOINT_PARTS: dict[str, tuple[str, str]] = {
    ep: tuple(ep.split('_', 1))  # type: ignore[misc]
    for ep in ENDPOINT_TIERS
}

API_CLASSES:  tuple[str, ...] = tuple(sorted({c for c, _ in ENDPOINT_PARTS.values()}))
API_FEATURES: tuple[str, ...] = tuple(sorted({f for _, f in ENDPOINT_PARTS.values()}))


# Forgiving aliases. Plural / shorthand forms a user might guess at
# instead of the canonical feature name. Keep the alias set small —
# anything not here surfaces a clear "unknown endpoint" error with
# the legal options.
FEATURE_ALIASES: dict[str, str] = {
    'returns':         'return',
    'returns_series':  'return',
    'timeseries':      'return',
}
CLASS_ALIASES: dict[str, str] = {
    'funds':    'fund',
    'indices':  'index',
    'indexes':  'index',
    'baskets':  'basket',
    'notes':    'notes_catalog'.split('_')[0],   # 'notes'
}


def resolve_endpoint(api_class: str | None,
                     api_feature: str | None) -> str | None:
    """``('fund', 'catalog')`` → ``'fund_catalog'``.

    Applies the alias maps (so ``returns`` → ``return``, etc.) and
    returns ``None`` if either side is empty. The caller checks the
    result against ``ENDPOINTS``.
    """
    if not api_class or not api_feature:
        return None
    cls  = CLASS_ALIASES.get(api_class,   api_class)
    feat = FEATURE_ALIASES.get(api_feature, api_feature)
    return f'{cls}_{feat}'
