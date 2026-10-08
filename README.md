# Snippets Pro

**3 snippets** across **3 languages** - last updated **2026-10-08**.

## Table of contents

- **JavaScript** (1)
  - [Debounce (browser)](#debounce-browser)
- **PowerShell** (1)
  - [Find the largest files](#find-the-largest-files)
- **Python** (1)
  - [Retry decorator with backoff](#retry-decorator-with-backoff)

## JavaScript

### Debounce (browser)

Delay a function call until the user stops firing events.

`#utils` `#browser` `#performance` · updated 2026-10-08 · 14 lines

```javascript
/** Run `fn` only after `wait` ms of silence - handy for resize/scroll/input handlers. */
export function debounce(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

const onResize = debounce(() => {
  console.log(window.innerWidth);
}, 150);

window.addEventListener("resize", onResize);
```

## PowerShell

### Find the largest files

List the biggest files below a folder on Windows.

`#filesystem` `#windows` · updated 2026-10-08 · 10 lines

```powershell
# List the biggest files below a folder (Windows / PowerShell)
param(
    [string]$Path = "C:\Users",
    [int]$Top = 20
)

Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object -Property Length -Descending |
    Select-Object -First $Top FullName,
        @{ Name = "MB"; Expression = { [math]::Round($_.Length / 1MB, 2) } }
```

## Python

### Retry decorator with backoff

Updated description from the CLI.

`#http` `#retry` `#resilience` `#backoff` · updated 2026-10-08 · 26 lines

```python
"""Retry a flaky callable with exponential backoff."""
import functools
import time


def retry(attempts=3, delay=0.5, backoff=2.0, exceptions=(Exception,)):
    """Retry `function` until it stops raising, then give up."""
    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return function(*args, **kwargs)
                except exceptions:
                    if attempt == attempts:
                        raise
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


@retry(attempts=5, delay=0.2)
def fetch(url):
    return url
```

## Usage

```bash
python snippet_cli.py add                      # add a snippet (opens your editor)
python snippet_cli.py search "http retry"      # full-text search
python snippet_cli.py list                     # compact overview
python snippet_cli.py show 3 --code-only       # print just the code
python snippet_cli.py copy 3                   # copy the code to the clipboard
python snippet_cli.py edit 3                   # change metadata and/or code
python snippet_cli.py delete 3                 # remove it again
python snippet_cli.py build                    # regenerate this README
python snippet_cli.py sync                     # git add / commit / push
```

---

<sub>Auto-generated from [`snippets.json`](snippets.json) by [`snippet_cli.py`](snippet_cli.py) - edit the database, not this file. Run `python snippet_cli.py build` to refresh it.</sub>
