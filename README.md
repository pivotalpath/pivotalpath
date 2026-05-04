# pivotalpath

Python wrapper around the PivotalPath v2 HTTP API. Returns
`pandas.DataFrame` when pandas is installed, otherwise plain
`list[dict]`. Single hard dependency: `requests`.

## Install

Not on PyPI yet — install directly from GitHub
(`github.com/pivotalpath/pivotalpath`):

```bash
# Core install — pulls `requests`
pip install git+https://github.com/pivotalpath/pivotalpath.git

# With pandas extra — calls return DataFrames
pip install "pivotalpath[pandas] @ git+https://github.com/pivotalpath/pivotalpath.git"
```

Without the `[pandas]` extra, calls return plain `list[dict]`. Once
the package is published to PyPI, `pip install pivotalpath` /
`pip install pivotalpath[pandas]` will be the canonical commands.

## Configure

Set the API key via env var or call:

```python
import os
os.environ['PIVOTALPATH_API_KEY'] = 'sk-...'
# OR
import pivotalpath as pp
pp.set_api_key('sk-...')
```

The base URL defaults to the production API
(`https://apis.pivotalpath.com/resources/api/v2/`). Point at a local
dev server (or staging) via the `PIVOTALPATH_BASE_URL` env var or
`pp.set_base_url(...)`.

## Use

```python
import pivotalpath as pp
pp.set_api_key('sk-...')

# Free endpoints — no key needed:
indices = pp.index_catalog()
returns = pp.index_return(date_min='202401', date_max='202412',
                          pivot=True, pivot_columns='name')

# Paid endpoints:
funds  = pp.fund_catalog(location='London',
                          select=['name', 'manager', 'aum'])
people = pp.fund_person(id=['f123', 'f456'])

# Generic for endpoints not yet wrapped (or named dynamically):
rows = pp.get('basket_return', date_min='202401')
```

### Errors

A non-null envelope `error` block raises `PivotalPathError` carrying
the type, message, and HTTP status code:

```python
from pivotalpath import PivotalPathError

try:
    rows = pp.fund_catalog(location='London')
except PivotalPathError as e:
    print(e.type, e.message, e.status_code)
```

### Cleaner errors in notebooks (opt-in)

By default `PivotalPathError` prints a full Python traceback like any
other exception. In an interactive notebook you usually don't need
that — you just want to see what's wrong. Opt in once:

```python
import pivotalpath as pp
pp.install_excepthook()
```

After that:

```text
>>> pp.fund_catalog(select=['pg_code'])
Error: 'pg_code' is not a column on 'fund_catalog'. Try: aum, id, location, name
```

instead of:

```text
>>> pp.fund_catalog(select=['pg_code'])
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  ...
pivotalpath.PivotalPathError: InvalidParameter: 'pg_code' is not a column ...
```

The hook covers plain Python REPL, IPython, and Jupyter. Pass
`force=True` to install in scripts where you'd rather log a one-liner
than dump a stack. Reverse with `pp.uninstall_excepthook()`.

The package does **not** auto-install on import — silently changing
`sys.excepthook` as a side effect of `import` is considered bad form
(it surprises collaborators, collides with other tools like
`rich.traceback`, and hides debug info). It's an explicit one-line
opt-in.

### Multiple keys / staging vs prod

The module-level shortcuts share a singleton `Client`. For two keys
in one process (or to point at a different base URL), instantiate
clients explicitly:

```python
from pivotalpath import Client

prod = Client(api_key='sk-prod...', base_url='https://api.pivotalpath.com/resources/api/v2/')
dev  = Client(api_key='sk-dev...',  base_url='https://dev.pivotalpath.com/resources/api/v2/')

a = prod.fund_catalog(location='London')
b = dev.fund_catalog(location='London')
```

## Auto-routing by id prefix

`pp.returns()` (alias `pp.mtd()`) and `pp.info()` detect the asset
class from the leading character of each id and route to the right
`<class>_return` or `<class>_catalog` endpoint:

| Prefix | Class  | Examples           |
|--------|--------|--------------------|
| `f`    | fund   | `f123`, `f456`     |
| `i`    | index  | `iHFC`, `iQNT`     |
| `b`    | basket | `b101`             |

Mixed-class lists or ids without a known prefix raise
`PivotalPathError('InvalidParameter', …)` up front; for those, use
the explicit endpoint form (`pp.fund_return(id=['my_slug'])`).

```python
df = pp.returns(id=['f123', 'f456'], start='202401', columns='name')
df = pp.mtd(id='f123')                   # alias of pp.returns
df = pp.info(id=['f123', 'i456'])        # mixed → rejected
```

## Catalog filters resolve to ids

The package recognises kwargs that belong on the matching catalog
table and resolves them to ids in one step:

```python
# 1) fund_catalog?name=AQR%&select=id
# 2) fund_return?id=[...]&start=202401
# Returned to you as if it were a single call.
df = pp.fund_return(name='AQR%', start='202401', pivot=True)
```

Works for any non-catalog feature; pass `id=…` explicitly to bypass.

## Endpoints

| Endpoint              | Tier | Notes                                  |
|-----------------------|------|----------------------------------------|
| `index_catalog`       | FREE | Index/benchmark definitions            |
| `index_return`        | FREE | Monthly index/benchmark returns        |
| `index_peergroup`     | paid | Constituent funds per peergroup        |
| `fund_catalog`        | paid | Fund metadata                          |
| `fund_person`         | paid | PMs / analysts per fund                |
| `fund_return`         | paid | Monthly fund returns                   |
| `fund_aum`            | paid | Historical AUM                         |
| `fund_vote`           | paid | Manager-vote signals                   |
| `basket_catalog`      | paid | Custom basket definitions              |
| `basket_return`       | paid | Monthly basket returns                 |
| `notes_catalog`       | paid | Research notes metadata                |
| `pitchbooks_catalog`  | paid | Pitchbook archive metadata             |

Add a new endpoint by appending it to `ENDPOINT_TIERS` in
`endpoints.py` — the `Client.<name>` method and the package-level
`pp.<name>(...)` shortcut are auto-generated.

## Common parameters

Same shape as the HTTP API:

- `select=['name','aum']` — restrict columns
- `id=['f123','f456']` — restrict to a list of ids
- `date_min='202401'`, `date_max='202412'` — time-series window
- `pivot=True`, `pivot_columns='name'` — wide-form output
