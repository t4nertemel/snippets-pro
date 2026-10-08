# Changelog

All notable changes to **Snippets Pro** are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project is not versioned with SemVer, so entries are grouped by date and
reference the commit that introduced them.

- Repository: <https://github.com/t4nertemel/snippets-pro> (public, default branch `main`)
- Source of truth: `snippets.json` (committed) -> generated `README.md`
- Tooling: `snippet_cli.py` - Python standard library only, Python 3.8+

---

## 2026-10-08 - Categories, tag navigation and the `tags` command (`55b7d68`)

### Added
- **`category` field** - a top-level topic bucket that sits above language and alongside tags. Snippets
  without a category fall into an `Uncategorised` bucket, which is always listed last. Database schema
  bumped 1 -> 2.
- **`tags` command** - shows the tag vocabulary with usage counts, busiest first:
  `python snippet_cli.py tags` (plus `tags --json` and `tags --category Web`).
- **`--category` filter** on `list` and `search`, and `--category` on `add`/`edit`. Matching is
  case-insensitive and whitespace tolerant (`--category "web ui"`).
- **Category prompt** in `add` (Title -> Category -> Language -> Description -> Tags). `edit` pre-fills the
  current values, so `python snippet_cli.py edit 3 --category DevOps` moves a snippet between categories.
- **"Browse by tag" README index** - every tag listed with links to the snippets that carry it, making tags
  clickable navigation instead of plain text.
- **Tag typo guard** - when a new tag is close to one already in use, `add` warns with suggestions
  (for example `new tag 'utilss' - did you mean: utils?`) to stop the vocabulary fragmenting.

### Changed
- **README hierarchy is now three levels deep**: `## Category` -> `### Language` -> `#### Title`
  (previously `## Language` -> `### Title`). The table of contents mirrors it and links every level.
- **Summary line** reports categories as well as languages: "3 snippets across 3 categories and 3 languages".
- **`list` output** gained a `CATEGORY` column and now sorts by category -> language -> title.
- **Inline tags** under each snippet are links to the tag index, e.g. ``[`#filesystem`](#filesystem-1)``.
- **Sample snippets categorised**: `Networking` (retry decorator), `Web UI` (debounce),
  `Filesystem` (largest files).
- **Usage block** in the generated README documents the category and tag workflows.

### Fixed
- **Heading anchor collisions** are now resolved the way GitHub does it: structural headings are emitted
  before the tag index, so a tag whose name matches a category/language/snippet gets a deterministic `-N`
  suffix (`#filesystem` = the category, `#filesystem-1` = the tag). All 18 internal links were verified
  against GitHub's own rendered HTML.
- **`snippet_cli.py` normalised to LF line endings**, UTF-8 without BOM (it had been saved with CRLF).

---

## 2026-10-08 - Renamed to "Snippets Pro" (`2923e47`)

### Changed
- README heading and the stored repository title changed from `Snippets` to `Snippets Pro` via
  `python snippet_cli.py build --title "Snippets Pro"`. The title is persisted in `snippets.json`, so
  every later rebuild keeps it.

---

## 2026-10-08 - Initial release (`c3a31e8`)

### Added
- **`snippet_cli.py`** - dependency-free CLI (Python 3.8+) with `add`, `list`, `search`, `show`, `copy`,
  `edit`, `delete`, `build` and `sync`. Snippets are referenced by id, slug or any unique part of the title.
- **`add`** opens your editor (honours `SNIPPETS_EDITOR` / `VISUAL` / `EDITOR`, otherwise VS Code/Cursor
  with `--wait`, then nano/vim, then Notepad) and can also take code from `--file`, `--stdin` or the
  clipboard, so it stays scriptable.
- **`search`** covers titles, slugs, descriptions, tags **and the code itself**; `show --code-only` and
  `copy` make reuse a one-liner.
- **`snippets.json`** database (schema 1) holding `id`, `slug`, `title`, `language`, `description`, `tags`,
  `code`, `created`, `updated`; writes are atomic and hand edits are repaired on load.
- **Generated `README.md`** - grouped by language with a table of contents, syntax-highlighted fences that
  grow when the code itself contains backticks, and GitHub-compatible anchors (including `-1`/`-2` suffixes
  for duplicate headings).
- **`build --check`** plus `.github/workflows/check-readme.yml`: CI fails when `README.md` drifts from
  `snippets.json`.
- **`.gitignore`** and **`.gitattributes`** (`* text=auto eol=lf`) so regenerated files stay byte-stable.
- **Sample library**: `Retry decorator with backoff`, `Debounce (browser)`, `Find the largest files`.
- **Published** to <https://github.com/t4nertemel/snippets-pro> (public, branch `main`); first CI run green.
- **Local prerequisites**: Python 3.12.10 installed for the user (`py` launcher and `python` on PATH);
  pushes authenticate over HTTPS without repeated prompts.

---

## Ideas not implemented yet

- Bulk metadata edits: `recategorise OLD NEW` and `retag OLD NEW` (merge tag typos across many snippets).
- Smarter discovery: `search --any` (OR instead of AND), `--limit`, relevance ranking and
  `list --sort updated|title`.
- Static documentation site export (MkDocs or Docusaurus) into `/docs`, hosted on GitHub Pages.
- Optional VS Code extension that inserts a stored snippet into the active editor.

