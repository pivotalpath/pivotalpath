# pivotalpath

Python wrapper around the PivotalPath v2 HTTP API. Returns
`pandas.DataFrame` when pandas is installed, otherwise plain
`list[dict]`. Single hard dependency: `requests`.

## Install

```bash
# Core install - pulls `requests`
pip install pivotalpath

# With pandas extra - calls return DataFrames
pip install "pivotalpath[pandas]"
```

Without the `[pandas]` extra, calls return plain `list[dict]`.

## Configure

Set the API key via env var or call:

```python
import os
os.environ['PIVOTALPATH_API_KEY'] = 'pp-...'
# OR
import pivotalpath as pp
pp.set_api_key('pp-...')
```

The base URL defaults to the production API
(`https://apis.pivotalpath.com/resources/api/v2/`). Point at a local
dev server (or staging) via the `PIVOTALPATH_BASE_URL` env var or
`pp.set_base_url(...)`.

### Without a key

No key set? The two free endpoints — `index_catalog` and `index_return`
— are served straight from the public dataset
(`github.com/pivotalpath/publicdata`), so they work out of the box with
no signup:

```python
import pivotalpath as pp        # no key needed
idx = pp.index_catalog()
ret = pp.index_return(id='iHFC', date_min='202001', pivot=True, columns='name')
```

All the usual query options (`select`, `id`, date window, filters,
`pivot`) apply — they're evaluated locally against the dataset. The data
is fetched once per process and cached. Any paid endpoint raises
`PivotalPathError('ApiKeyRequired', …)` until you set a key. (Override
the dataset location with `PIVOTALPATH_PUBLICDATA_URL` if you've forked
it.)

## Use

```python
import pivotalpath as pp

# Free, no key needed (served from the public dataset):
indices = pp.index_catalog()
rets    = pp.index_return(date_min='202401', date_max='202412',
                          pivot=True, columns='name')

# Paid endpoints — set your key, then call any endpoint by name.
pp.set_api_key('pp-...')
rows = pp.get('your_endpoint', some_filter='value', select=['id', 'name'])
rows = pp.your_endpoint(some_filter='value')   # identical, via shortcut
```

> **Endpoint discovery.** This package is intentionally *schema-agnostic* — it
> ships no list of endpoints or columns. Which endpoints you can call (and
> their columns) comes from your **API reference** at
> <https://apis.pivotalpath.com> (the Reference tab), not from this package.
> Any `pp.<name>(...)` is shorthand for `pp.get('<name>', ...)`. The two free
> endpoints, `index_catalog` and `index_return`, are the exception: their data
> is public.

### Discover endpoints from Python

The reference is served live by the API, so these calls need a network
connection and always match the current service:

```python
pp.help()         # how to get started, and where the full reference lives
pp.reference()    # one row per endpoint you can use: name, group, tier, parameters
pp.reference(raw=True)   # the complete OpenAPI document (dict)
```

Without an API key you see the public edition (the free endpoints). With a
valid key (`pp.set_api_key('pp-...')`) you see the complete edition, the same
document as the Reference tab and the PDF.

### Errors

A non-null envelope `error` block raises `PivotalPathError` carrying the
type, message, and HTTP status code. Calling a paid endpoint without a key
raises `PivotalPathError('ApiKeyRequired', …)` with a pointer to where to
get one.

```python
from pivotalpath import PivotalPathError

try:
    rows = pp.index_return(id='iHFC')
except PivotalPathError as e:
    print(e.type, e.message, e.status_code)
```

### Errors in notebooks and the REPL

In an interactive session (Python REPL, IPython, Jupyter) a
`PivotalPathError` prints as a one-line message instead of a traceback:

```text
>>> pp.index_catalog(select=['bogus'])
Error: 'bogus' is not a column on 'index_catalog'. Try: abstract, id, name
```

Scripts and tests are unaffected and keep the full traceback. To get the
traceback in a session too, call `pp.uninstall_excepthook()`; to get the
one-liner in a script, call `pp.install_excepthook(force=True)`.

### Multiple keys / multiple environments

The module-level shortcuts share a singleton `Client`. For two keys
in one process (or to point at a different base URL), instantiate
clients explicitly:

```python
from pivotalpath import Client

prod = Client(api_key='pp-prod...', base_url='https://apis.pivotalpath.com/resources/api/v2/')
dev  = Client(api_key='pp-dev...',  base_url='http://127.0.0.1:8044/resources/api/v2/')

a = prod.index_catalog()
b = dev.index_catalog()
```

## Auto-routing by id prefix

`pp.returns()` (alias `pp.mtd()`) and `pp.info()` detect the asset
class from the leading character of each id and route to the matching
`<class>_return` or `<class>_catalog` endpoint:

| Prefix | Class | Examples       |
|--------|-------|----------------|
| `i`    | index | `iHFC`, `iQNT` |

```python
df = pp.returns(id=['iHFC', 'iQNT'], start='202401', columns='name')
df = pp.mtd(id='iHFC')                    # alias of pp.returns
df = pp.info(id='iHFC')                   # catalog metadata for an id
```

Only index ids (`i…`) auto-route. For any other endpoint, name it
explicitly — `pp.returns(api_class='…', …)` or, most directly,
`pp.get('<endpoint>', id=['my_slug'])`.

## Catalog filters resolve to ids

The package recognises kwargs that belong on the matching `<class>_catalog`
table and resolves them to ids in one step — it fetches matching ids from
the catalog, then runs your query filtered by those ids, returned to you as
a single call:

```python
# Filter by index name, then pull the matching return series:
df = pp.index_return(name='PivotalPath Composite%', start='202401', pivot=True)
```

Works for any non-catalog feature; pass `id=…` explicitly to bypass the
resolver.

## Endpoints

This package does **not** enumerate endpoints. See the **Reference** tab at
<https://apis.pivotalpath.com> for the endpoints and columns available to
your subscription. Every endpoint is callable two equivalent ways:

```python
pp.get('your_endpoint', **params)   # generic
pp.your_endpoint(**params)          # dynamic shortcut (same request)
```

`index_catalog` and `index_return` are free and work with no key (served
from the public dataset — see [Without a key](#without-a-key)).

## Common parameters

Same shape as the HTTP API:

- `select=['id', 'name']` — restrict columns
- `id=['iHFC', 'iQNT']` — restrict to a list of ids
- `date_min='202401'`, `date_max='202412'` — time-series window
- `pivot=True`, `columns='name'` — wide-form output

## License

Proprietary. Copyright (c) 2026 PivotalPath. All rights reserved. See
[LICENSE](LICENSE). Use is for accessing PivotalPath's APIs; the public
endpoints work without a key. Access to the source code does not grant any
license except as stated there. Data is governed separately, by your
agreement with PivotalPath or, for the public dataset, by the terms
published with it.
