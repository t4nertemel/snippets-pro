#!/usr/bin/env python3
"""snippet_cli.py - a tiny, dependency-free personal snippet repository.

Snippets live in ``snippets.json`` (a plain JSON database) and are rendered to
``README.md`` so the repository stays readable (and searchable) on GitHub,
your phone, or any Markdown viewer.

Commands
--------
    python snippet_cli.py add                 # prompt + open your editor
    python snippet_cli.py add --file utils.py # scriptable / non-interactive
    python snippet_cli.py list                # overview of everything
    python snippet_cli.py search QUERY        # full-text search
    python snippet_cli.py show REF            # print one snippet + its code
    python snippet_cli.py edit REF            # edit metadata/code
    python snippet_cli.py delete REF          # remove a snippet
    python snippet_cli.py build               # regenerate README.md
    python snippet_cli.py sync                # git add/commit/push

``REF`` is a snippet id, its slug, or any unique part of its title.

Only the Python standard library is used, so the project has no install step
beyond having Python 3.8+ available.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "snippets.json"
README_PATH = BASE_DIR / "README.md"

DB_SCHEMA = 1
README_TITLE = "Snippets"

# Canonical language slugs (left side) mapped from common aliases (right side).
LANGUAGE_ALIASES = {
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "node": "javascript",
    "ts": "typescript",
    "py": "python",
    "py3": "python",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "console": "shell",
    "ps1": "powershell",
    "pwsh": "powershell",
    "ps": "powershell",
    "c++": "cpp",
    "cxx": "cpp",
    "cs": "csharp",
    "c#": "csharp",
    "dotnet": "csharp",
    "golang": "go",
    "rs": "rust",
    "rb": "ruby",
    "yml": "yaml",
    "md": "markdown",
    "htm": "html",
    "kt": "kotlin",
    "makefile": "make",
    "docker": "dockerfile",
    "golangci": "go",
}

# Pretty names used in README headings.
LANGUAGE_NAMES = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "shell": "Shell",
    "powershell": "PowerShell",
    "cpp": "C++",
    "csharp": "C#",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "java": "Java",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "dart": "Dart",
    "lua": "Lua",
    "perl": "Perl",
    "r": "R",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "json": "JSON",
    "yaml": "YAML",
    "toml": "TOML",
    "xml": "XML",
    "markdown": "Markdown",
    "dockerfile": "Dockerfile",
    "make": "Makefile",
    "vue": "Vue",
    "jsx": "JSX",
    "tsx": "TSX",
    "text": "Text",
    "other": "Other",
}

# Syntax-hint token used inside ``` fences (must be a real GitHub identifier).
FENCE_TOKENS = {"shell": "bash", "csharp": "csharp", "cpp": "cpp", "text": "text", "make": "makefile"}

# File extension used for the temporary editor buffer.
LANGUAGE_EXTENSIONS = {
    "javascript": ".js",
    "typescript": ".ts",
    "python": ".py",
    "shell": ".sh",
    "powershell": ".ps1",
    "cpp": ".cpp",
    "csharp": ".cs",
    "go": ".go",
    "rust": ".rs",
    "ruby": ".rb",
    "php": ".php",
    "java": ".java",
    "kotlin": ".kt",
    "swift": ".swift",
    "dart": ".dart",
    "lua": ".lua",
    "perl": ".pl",
    "r": ".r",
    "sql": ".sql",
    "html": ".html",
    "css": ".css",
    "scss": ".scss",
    "json": ".json",
    "yaml": ".yaml",
    "toml": ".toml",
    "xml": ".xml",
    "markdown": ".md",
    "dockerfile": "Dockerfile",
    "make": "Makefile",
    "vue": ".vue",
    "jsx": ".jsx",
    "tsx": ".tsx",
    "text": ".txt",
}

# Characters that NFKD does not decompose but that we still want transliterated
# (handy for Turkish titles: "İşlem Görüntüleme" -> "islem-goruntuleme").
TRANSLITERATION = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
        "æ": "ae",
        "ø": "o",
        "ß": "ss",
    }
)

# --------------------------------------------------------------------------
# Small console helpers
# --------------------------------------------------------------------------

USE_COLOR = False


def enable_ansi() -> bool:
    """Turn colour on when attached to a real terminal and not opted out."""
    if os.environ.get("NO_COLOR") or os.environ.get("SNIPPETS_NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.name == "nt":  # enable VT escape sequences on legacy consoles
        try:
            os.system("")
        except Exception:
            return False
    return True


def paint(text: str, *codes: str) -> str:
    if not USE_COLOR or not codes:
        return text
    return "".join(codes) + text + "\033[0m"


def bold(text: str) -> str:
    return paint(text, "\033[1m")


def dim(text: str) -> str:
    return paint(text, "\033[2m")


def green(text: str) -> str:
    return paint(text, "\033[32m")


def yellow(text: str) -> str:
    return paint(text, "\033[33m")


def cyan(text: str) -> str:
    return paint(text, "\033[36m")


def red(text: str) -> str:
    return paint(text, "\033[31m")


def info(message: str) -> None:
    print(f"{green('✓')} {message}")


def warn(message: str) -> None:
    print(f"{yellow('!')} {message}", file=sys.stderr)


def fail(message: str) -> None:
    """Print an error and abort."""
    print(f"{red('✗')} {message}", file=sys.stderr)
    raise SystemExit(1)

# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------


def now_iso() -> str:
    """Current local time as `YYYY-MM-DDTHH:MM:SS+HH:MM`."""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now().astimezone().date().isoformat()


def slugify(text: str) -> str:
    """Lowercase, ASCII-ish, hyphen separated identifier."""
    text = (text or "").translate(TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "snippet"


def normalize_language(raw: str) -> str:
    """Map any user spelling ("Py", ".JS", "C++") to a canonical slug."""
    value = (raw or "").strip().lower().lstrip(".")
    if not value:
        return "text"
    value = LANGUAGE_ALIASES.get(value, value)
    return re.sub(r"[^a-z0-9+#]+", "", value) or "text"


def language_name(slug: str) -> str:
    return LANGUAGE_NAMES.get(slug, slug.capitalize())


def fence_token(slug: str) -> str:
    return FENCE_TOKENS.get(slug, slug)


def language_extension(slug: str) -> str:
    return LANGUAGE_EXTENSIONS.get(slug, ".txt")


def parse_tags(raw) -> list:
    """Accept "a, b" / "a b" / ["a", "b"] and return a clean lowercase list."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = [str(item) for item in raw]
    else:
        items = re.split(r"[,\s]+", str(raw))
    seen, tags = set(), []
    for item in items:
        tag = item.strip().lstrip("#").lower()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def normalize_code(code: str) -> str:
    """Trim blank lines and guarantee a single trailing newline."""
    return (code or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def ensure_snippet_shape(raw: dict, fallback_id: int) -> dict:
    """Repair/complete a snippet record coming from a hand-edited database."""
    title = str(raw.get("title") or f"Snippet {fallback_id}").strip()
    stamp = now_iso()
    snippet = {
        "id": int(raw.get("id") or fallback_id),
        "title": title,
        "language": normalize_language(str(raw.get("language") or "text")),
        "description": str(raw.get("description") or "").strip(),
        "tags": parse_tags(raw.get("tags")),
        "code": normalize_code(str(raw.get("code") or "")),
        "created": str(raw.get("created") or stamp),
        "updated": str(raw.get("updated") or stamp),
    }
    snippet["slug"] = str(raw.get("slug") or slugify(title))
    return snippet


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------


def empty_db() -> dict:
    return {"schema": DB_SCHEMA, "title": README_TITLE, "updated": None, "snippets": []}


def load_db() -> dict:
    """Read snippets.json, repairing anything that looks off."""
    if not DB_PATH.exists():
        return empty_db()
    try:
        with DB_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"Could not read {DB_PATH.name}: {exc}")
        return empty_db()

    if isinstance(raw, list):  # tolerate a bare list of snippets
        raw = {"schema": DB_SCHEMA, "updated": None, "snippets": raw}
    if not isinstance(raw, dict):
        fail(f"{DB_PATH.name} must contain a JSON object.")

    db = empty_db()
    db["schema"] = int(raw.get("schema") or DB_SCHEMA)
    db["title"] = str(raw.get("title") or README_TITLE)
    db["updated"] = raw.get("updated")

    snippets, used_ids, used_slugs = [], set(), set()
    next_free = 1
    for item in raw.get("snippets") or []:
        if not isinstance(item, dict):
            continue
        while next_free in used_ids:
            next_free += 1
        snippet = ensure_snippet_shape(item, next_free)
        if snippet["id"] in used_ids:
            snippet["id"] = next_free
        used_ids.add(snippet["id"])
        next_free = max(next_free, snippet["id"]) + 1

        slug, suffix = snippet["slug"], 2
        while slug in used_slugs:
            slug = f"{snippet['slug']}-{suffix}"
            suffix += 1
        snippet["slug"] = slug
        used_slugs.add(slug)
        snippets.append(snippet)

    db["snippets"] = snippets
    return db


def save_db(db: dict) -> None:
    """Write the database atomically so a crash cannot corrupt it."""
    db["schema"] = DB_SCHEMA
    db["updated"] = now_iso()
    payload = json.dumps(db, indent=2, ensure_ascii=False)
    temp_path = DB_PATH.with_name(DB_PATH.name + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
    os.replace(str(temp_path), str(DB_PATH))


def unique_slug(db: dict, title: str, keep_id=None) -> str:
    base = slugify(title)
    taken = {s["slug"] for s in db["snippets"] if s["id"] != keep_id}
    slug, suffix = base, 2
    while slug in taken:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def next_id(db: dict) -> int:
    return max((s["id"] for s in db["snippets"]), default=0) + 1


# --------------------------------------------------------------------------
# Snippet lookup
# --------------------------------------------------------------------------


def resolve_snippet(db: dict, ref: str) -> dict:
    """Find a snippet by id, slug, title or unique title fragment."""
    snippets = db["snippets"]
    if not snippets:
        fail("The snippet database is empty. Add one with: snippet_cli.py add")

    needle = (ref or "").strip()
    if not needle:
        fail("No snippet reference given.")

    if needle.isdigit():
        for snippet in snippets:
            if snippet["id"] == int(needle):
                return snippet

    lowered = needle.lower()
    for snippet in snippets:
        if snippet["slug"].lower() == lowered or snippet["title"].lower() == lowered:
            return snippet

    matches = [
        snippet
        for snippet in snippets
        if lowered in snippet["slug"].lower() or lowered in snippet["title"].lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        listing = ", ".join(f"{s['id']}={s['title']}" for s in matches)
        fail(f"'{ref}' matches several snippets: {listing}")
    fail(f"No snippet matches '{ref}'. Try: python snippet_cli.py list")
    return {}


# --------------------------------------------------------------------------
# Editor integration
# --------------------------------------------------------------------------


def split_command(command: str) -> list:
    """Split an editor command line, honouring quoted paths (Windows safe)."""
    parts = re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', command)
    return [first or second or third for first, second, third in parts]


def find_editor() -> list:
    """Prefer $SNIPPETS_EDITOR/$VISUAL/$EDITOR, then VS Code, then notepad/nano."""
    for variable in ("SNIPPETS_EDITOR", "VISUAL", "EDITOR"):
        candidate = os.environ.get(variable)
        if candidate and candidate.strip():
            return split_command(candidate)

    # VS Code (and friends) need --wait, otherwise we would read back an
    # empty buffer while the user is still typing.
    for binary in ("code", "code-insiders", "codium", "cursor"):
        path = shutil.which(binary)
        if path:
            if path.lower().endswith((".cmd", ".bat")):
                return ["cmd", "/c", path, "--wait"]
            return [path, "--wait"]

    for binary in ("nano", "vim", "vi", "pico"):
        path = shutil.which(binary)
        if path:
            return [path]

    notepad = shutil.which("notepad")
    return [notepad] if notepad else []


def open_in_editor(text: str, slug: str = "snippet", language: str = "text") -> str:
    """Open a temporary buffer, wait for the editor, and return the new text."""
    editor = find_editor()
    if not editor:
        fail("No editor found. Set the EDITOR or SNIPPETS_EDITOR environment variable.")

    suffix = language_extension(language)
    prefix = f"{slug or 'snippet'}-"
    if not suffix.startswith("."):  # Makefile / Dockerfile style names
        prefix, suffix = "", suffix

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        prefix=prefix,
        suffix=suffix,
        dir=tempfile.gettempdir(),
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(text + "\n" if text and not text.endswith("\n") else text)
        print(dim(f"  editor: {' '.join(editor)}  ->  {path.name}"))
        subprocess.call(editor + [str(path)])
        return normalize_code(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        fail(f"Could not launch the editor ({' '.join(editor)}): {exc}")
        return ""
    finally:
        try:
            path.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Interactive input
# --------------------------------------------------------------------------


def prompt(label: str, default: str = None, required: bool = False) -> str:
    """Ask a question on the terminal, with an optional default value."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            answer = input(f"{bold(label)}{suffix}: ").strip()
        except EOFError:
            answer = ""
        if answer:
            return answer
        if default is not None:
            return default
        if not required:
            return ""
        warn("This value is required.")


def pick_language(default: str = "text") -> str:
    known = ", ".join(sorted(LANGUAGE_NAMES))
    print(dim(f"  known languages: {known}"))
    return normalize_language(prompt("Language", default=default))


# --------------------------------------------------------------------------
# Display helpers
# --------------------------------------------------------------------------

EXTENSION_LANGUAGES = {
    ext: slug for slug, ext in LANGUAGE_EXTENSIONS.items() if ext.startswith(".")
}
SPECIAL_FILENAMES = {"dockerfile": "dockerfile", "makefile": "make", "cmakelists.txt": "cmake"}


def guess_language(path) -> str:
    """Best-effort language detection from a file name."""
    if path is None:
        return ""
    name = Path(path).name.lower()
    if name in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[name]
    return EXTENSION_LANGUAGES.get(Path(path).suffix.lower(), "")


def fence_for(code: str) -> str:
    """Return a backtick fence longer than any backtick run inside the code."""
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", code or "")), default=0)
    return "`" * max(3, longest + 1)


def format_tags(tags) -> str:
    return " ".join(f"#{tag}" for tag in tags)


def print_snippet(snippet: dict, show_code: bool = True) -> None:
    print()
    print(f"{bold(str(snippet['id']))} {bold(snippet['title'])}")
    details = [cyan(language_name(snippet["language"])), f"slug: {snippet['slug']}"]
    print("  " + dim(" · ".join(details)))
    if snippet["description"]:
        print(f"  {snippet['description']}")
    if snippet["tags"]:
        print("  " + dim(format_tags(snippet["tags"])))
    print("  " + dim(f"created {snippet['created'][:10]} · updated {snippet['updated'][:10]}"))
    if show_code and snippet["code"]:
        fence = fence_for(snippet["code"])
        print("  " + dim(fence + fence_token(snippet["language"])))
        print(snippet["code"])
        print("  " + dim(fence))
    print()


def build_summary_rows(snippets) -> list:
    """(id, title, language, tags, updated) rows, title-sorted per language."""
    return [
        (
            snippet["id"],
            snippet["title"],
            language_name(snippet["language"]),
            format_tags(snippet["tags"]),
            snippet["updated"][:10],
        )
        for snippet in sorted(snippets, key=lambda s: (s["language"], s["title"].lower()))
    ]


def print_table(rows) -> None:
    if not rows:
        print(dim("  (nothing to show)"))
        return
    headers = ("ID", "TITLE", "LANGUAGE", "TAGS", "UPDATED")
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    line = "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))
    print(dim(line.rstrip()))
    print(dim("  ".join("-" * width for width in widths)))
    for row in rows:
        print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())


# --------------------------------------------------------------------------
# Command: add
# --------------------------------------------------------------------------


def read_code_source(args) -> str:
    """Read snippet code from stdin or from the file given via --file."""
    if args.stdin or args.file == "-":
        return normalize_code(sys.stdin.read())
    path = Path(args.file).expanduser()
    if not path.is_file():
        fail(f"File not found: {path}")
    return normalize_code(path.read_text(encoding="utf-8", errors="replace"))


def cmd_add(args) -> int:
    db = load_db()

    source_path = None
    if args.file and args.file != "-":
        source_path = Path(args.file).expanduser()

    non_interactive = bool(source_path or args.file == "-" or args.stdin)

    if non_interactive:
        code = read_code_source(args)
        title = args.title or (source_path.stem if source_path else "Stdin snippet")
        language = normalize_language(args.language or guess_language(source_path) or "text")
        description = args.description or ""
        tags = parse_tags(args.tags)
    else:
        title = args.title or prompt("Title", required=True)
        language = normalize_language(args.language) if args.language else pick_language("text")
        description = args.description if args.description is not None else prompt("Description (optional)")
        tags = parse_tags(args.tags if args.tags is not None else prompt("Tags (comma separated, optional)"))
        print(dim("  Opening your editor - save, then close the tab to store the snippet."))
        code = open_in_editor("", unique_slug(db, title), language)

    if not code.strip():
        fail("The snippet is empty - nothing was saved.")

    stamp = now_iso()
    snippet = {
        "id": next_id(db),
        "slug": unique_slug(db, title),
        "title": title,
        "language": language,
        "description": description,
        "tags": tags,
        "code": code,
        "created": stamp,
        "updated": stamp,
    }
    db["snippets"].append(snippet)
    save_db(db)
    write_readme(db)

    info(f"Saved snippet #{snippet['id']} \"{title}\" ({language_name(language)}, {len(code.splitlines())} lines)")
    print(dim("  snippets.json and README.md updated"))
    return 0


# --------------------------------------------------------------------------
# Command: list / search / show
# --------------------------------------------------------------------------


def filter_snippets(snippets, language=None, tag=None) -> list:
    result = list(snippets)
    if language:
        wanted_languages = {normalize_language(language)}
        result = [s for s in result if s["language"] in wanted_languages]
    if tag:
        wanted_tags = set(parse_tags(tag))
        result = [s for s in result if wanted_tags.issubset(set(s["tags"]))]
    return result


def snippet_haystack(snippet: dict) -> str:
    return " ".join(
        [
            snippet["title"],
            snippet["slug"],
            snippet["language"],
            language_name(snippet["language"]),
            snippet["description"],
            " ".join(snippet["tags"]),
            snippet["code"],
        ]
    ).lower()


def cmd_list(args) -> int:
    db = load_db()
    snippets = filter_snippets(db["snippets"], language=args.language, tag=args.tag)
    if args.json:
        print(json.dumps(snippets, indent=2, ensure_ascii=False))
        return 0

    print()
    print(bold(f"{len(snippets)} snippet(s)"))
    print_table(build_summary_rows(snippets))
    print()
    print(dim("  read one with: python snippet_cli.py show <id|slug>"))
    return 0


def cmd_search(args) -> int:
    db = load_db()
    terms = [term for term in (args.terms or []) if term.strip()]
    if not terms:
        fail("Give at least one search term.")

    candidates = filter_snippets(db["snippets"], language=args.language, tag=args.tag)
    matches = [
        snippet
        for snippet in candidates
        if all(term.lower() in snippet_haystack(snippet) for term in terms)
    ]

    if args.json:
        print(json.dumps(matches, indent=2, ensure_ascii=False))
        return 0

    query = " ".join(terms)
    if not matches:
        warn(f"No snippet matches '{query}'.")
        return 1

    print()
    print(bold(f"{len(matches)} match(es) for '{query}'"))
    print_table(build_summary_rows(matches))
    if args.show:
        for snippet in matches:
            print_snippet(snippet)
    else:
        print(dim("  add --show to print the code of every match"))
    return 0


def cmd_show(args) -> int:
    db = load_db()
    snippet = resolve_snippet(db, args.ref)
    if args.json:
        print(json.dumps(snippet, indent=2, ensure_ascii=False))
        return 0
    if args.code_only:
        print(snippet["code"])
        return 0
    print_snippet(snippet)
    return 0


# --------------------------------------------------------------------------
# Command: edit / delete / copy
# --------------------------------------------------------------------------


def cmd_edit(args) -> int:
    db = load_db()
    snippet = resolve_snippet(db, args.ref)

    has_field_flag = any(
        value is not None for value in (args.title, args.language, args.description, args.tags)
    )
    has_code_flag = bool(args.file or args.stdin)
    non_interactive = has_field_flag or has_code_flag

    if non_interactive:
        new_title = args.title if args.title is not None else snippet["title"]
        new_language = normalize_language(args.language) if args.language else snippet["language"]
        new_description = args.description if args.description is not None else snippet["description"]
        new_tags = parse_tags(args.tags) if args.tags is not None else snippet["tags"]
        code = read_code_source(args) if has_code_flag else snippet["code"]
    else:
        new_title = prompt("Title", default=snippet["title"], required=True)
        print(dim(f"  current language: {language_name(snippet['language'])}"))
        new_language = pick_language(snippet["language"])
        new_description = prompt("Description", default=snippet["description"])
        new_tags = parse_tags(prompt("Tags", default=format_tags(snippet["tags"])))
        print(dim("  Opening your editor with the current code..."))
        code = open_in_editor(snippet["code"], snippet["slug"], new_language)

    if not code.strip():
        fail("Refusing to store an empty snippet.")

    changes = {}
    if new_title != snippet["title"]:
        changes["title"] = new_title
        changes["slug"] = unique_slug(db, new_title, keep_id=snippet["id"])
    if new_language != snippet["language"]:
        changes["language"] = new_language
    if new_description != snippet["description"]:
        changes["description"] = new_description
    if new_tags != snippet["tags"]:
        changes["tags"] = new_tags
    if code != snippet["code"]:
        changes["code"] = code

    if not changes:
        warn("Nothing changed.")
        return 0

    snippet.update(changes)
    snippet["updated"] = now_iso()
    save_db(db)
    write_readme(db)

    info(f"Updated #{snippet['id']} \"{snippet['title']}\" ({', '.join(sorted(changes))})")
    return 0


def cmd_delete(args) -> int:
    db = load_db()
    snippet = resolve_snippet(db, args.ref)

    if not args.yes:
        answer = prompt(f"Delete #{snippet['id']} \"{snippet['title']}\"? [y/N]", default="n")
        if answer.strip().lower() not in ("y", "yes"):
            warn("Cancelled - nothing was deleted.")
            return 1

    db["snippets"] = [item for item in db["snippets"] if item["id"] != snippet["id"]]
    save_db(db)
    write_readme(db)
    info(f"Deleted #{snippet['id']} \"{snippet['title']}\"")
    return 0


def copy_to_clipboard(text: str) -> bool:
    """Best-effort clipboard copy on Windows, macOS and Linux."""
    if os.name == "nt":
        commands = [["clip"]]
    elif sys.platform == "darwin":
        commands = [["pbcopy"]]
    else:
        commands = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]

    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
            if process.returncode == 0:
                return True
        except OSError:
            continue
    return False


def cmd_copy(args) -> int:
    db = load_db()
    snippet = resolve_snippet(db, args.ref)
    if copy_to_clipboard(snippet["code"]):
        info(f"Copied #{snippet['id']} \"{snippet['title']}\" to the clipboard.")
        return 0
    warn("No clipboard tool found - printing the code instead.")
    print(snippet["code"])
    return 1


# --------------------------------------------------------------------------
# README generation
# --------------------------------------------------------------------------


class AnchorRegistry:
    """Recreate GitHub's heading anchors, including the -1 / -2 duplicates."""

    def __init__(self):
        self.counts = {}

    def register(self, text: str) -> str:
        base = github_anchor(text)
        seen = self.counts.get(base, 0)
        self.counts[base] = seen + 1
        return base if seen == 0 else f"{base}-{seen}"


def github_anchor(text: str) -> str:
    """Lowercase, punctuation-free, hyphen separated heading anchor."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def group_by_language(snippets) -> list:
    """[(language_slug, display_name, [titles-sorted snippets]), ...]"""
    groups = {}
    for snippet in snippets:
        groups.setdefault(snippet["language"], []).append(snippet)
    return [
        (slug, language_name(slug), sorted(items, key=lambda s: s["title"].lower()))
        for slug, items in sorted(groups.items(), key=lambda pair: language_name(pair[0]).lower())
    ]


USAGE_BLOCK = [
    "```bash",
    "python snippet_cli.py add                      # add a snippet (opens your editor)",
    'python snippet_cli.py search "http retry"      # full-text search',
    "python snippet_cli.py list                     # compact overview",
    "python snippet_cli.py show 3 --code-only       # print just the code",
    "python snippet_cli.py copy 3                   # copy the code to the clipboard",
    "python snippet_cli.py edit 3                   # change metadata and/or code",
    "python snippet_cli.py delete 3                 # remove it again",
    "python snippet_cli.py build                    # regenerate this README",
    "python snippet_cli.py sync                     # git add / commit / push",
    "```",
]


def build_readme(db: dict, title: str = README_TITLE) -> str:
    """Render the whole README as a single Markdown string."""
    snippets = db["snippets"]
    groups = group_by_language(snippets)

    registry = AnchorRegistry()
    entries = []  # (language_slug, display_name, snippet, anchor)
    for slug, display_name, items in groups:
        for snippet in items:
            entries.append((slug, display_name, snippet, registry.register(snippet["title"])))

    lines = [f"# {title}", ""]
    if snippets:
        languages = len(groups)
        plural = "s" if languages != 1 else ""
        lines.append(
            f"**{len(snippets)} snippet{'s' if len(snippets) != 1 else ''}** "
            f"across **{languages} language{plural}** - "
            f"last updated **{(db.get('updated') or today())[:10]}**."
        )
    else:
        lines.append("_No snippets yet. Add your first one with `python snippet_cli.py add`._")
    lines.append("")

    if snippets:
        lines.append("## Table of contents")
        lines.append("")
        current_language = None
        for slug, display_name, snippet, anchor in entries:
            if slug != current_language:
                current_language = slug
                count = sum(1 for entry in entries if entry[0] == slug)
                lines.append(f"- **{display_name}** ({count})")
            lines.append(f"  - [{snippet['title']}](#{anchor})")
        lines.append("")

        for slug, display_name, items in groups:
            lines.append(f"## {display_name}")
            lines.append("")
            for snippet in items:
                lines.append(f"### {snippet['title']}")
                lines.append("")
                if snippet["description"]:
                    lines.append(snippet["description"])
                    lines.append("")
                meta = []
                if snippet["tags"]:
                    meta.append(" ".join(f"`#{tag}`" for tag in snippet["tags"]))
                meta.append(f"updated {snippet['updated'][:10]}")
                meta.append(f"{len(snippet['code'].splitlines())} lines")
                lines.append(" · ".join(meta))
                lines.append("")
                fence = fence_for(snippet["code"])
                lines.append(fence + fence_token(snippet["language"]))
                lines.append(snippet["code"])
                lines.append(fence)
                lines.append("")

    lines.append("## Usage")
    lines.append("")
    lines.extend(USAGE_BLOCK)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"<sub>Auto-generated from [`snippets.json`](snippets.json) by "
        f"[`snippet_cli.py`](snippet_cli.py) - edit the database, not this file. "
        f"Run `python snippet_cli.py build` to refresh it.</sub>"
    )
    lines.append("")
    return "\n".join(lines)


def write_readme(db: dict, title: str = None) -> Path:
    """Render and store README.md (always with LF endings)."""
    content = build_readme(db, title or db.get("title") or README_TITLE)
    with README_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return README_PATH


# --------------------------------------------------------------------------
# Command: build / sync
# --------------------------------------------------------------------------


def cmd_build(args) -> int:
    db = load_db()

    if args.title:
        db["title"] = args.title

    if args.check:
        expected = build_readme(db, db.get("title") or README_TITLE)
        current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
        if current == expected:
            info("README.md is up to date.")
            return 0
        warn("README.md is out of date - run: python snippet_cli.py build")
        return 1

    save_db(db)
    write_readme(db, db.get("title") or README_TITLE)
    info(f"README.md rebuilt from {len(db['snippets'])} snippet(s).")
    return 0


def run_git(arguments, check=True):
    """Run a git command inside the repository folder."""
    result = subprocess.run(
        ["git"] + arguments, cwd=str(BASE_DIR), capture_output=True, text=True
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        fail(f"git {' '.join(arguments)} failed: {detail}")
    return result


def cmd_sync(args) -> int:
    if shutil.which("git") is None:
        fail("git is not installed or not on PATH.")
    if not (BASE_DIR / ".git").exists():
        fail("This folder is not a git repository yet. Run: git init -b main")

    # Make sure the exported files match the database before committing.
    db = load_db()
    write_readme(db, db.get("title") or README_TITLE)

    run_git(["add", "-A"])
    staged = run_git(["diff", "--cached", "--name-only"]).stdout.strip()
    if staged:
        message = args.message or f"snippets: sync {today()}"
        run_git(["commit", "-m", message])
        info(f"Committed {len(staged.splitlines())} file change(s): {message}")
    else:
        info("Nothing to commit - the working tree is already clean.")

    if args.no_push:
        return 0

    remotes = run_git(["remote"], check=False).stdout.split()
    if "origin" not in remotes:
        warn("No 'origin' remote configured yet. One-time setup:")
        print("  git remote add origin https://github.com/<your-user>/<your-repo>.git")
        print("  git push -u origin main")
        return 1

    upstream = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False
    )
    if upstream.returncode == 0:
        run_git(["push"])
    else:
        run_git(["push", "-u", "origin", "HEAD"])
    info("Pushed to GitHub.")
    return 0


# --------------------------------------------------------------------------
# Command line interface
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snippet_cli.py",
        description="Manage a personal snippet repository (snippets.json -> README.md).",
        epilog=(
            "examples:\n"
            "  python snippet_cli.py add --file utils.py --tags http,retry\n"
            "  python snippet_cli.py search retry --show\n"
            "  python snippet_cli.py show debounce --code-only\n"
            "  python snippet_cli.py sync -m \"add debounce helper\"\n"
            "\n"
            "environment:\n"
            "  SNIPPETS_EDITOR / VISUAL / EDITOR   editor used by add and edit\n"
            "  NO_COLOR                            disable coloured terminal output\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--no-color", action="store_true", help="disable coloured output")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add_metadata_arguments(subparser) -> None:
        subparser.add_argument("--title", help="snippet title")
        subparser.add_argument("--language", help="language, e.g. python, js, bash, c++")
        subparser.add_argument("--description", help="short description shown in the README")
        subparser.add_argument("--tags", help="comma separated tags, e.g. http,retry")

    add_parser = subparsers.add_parser("add", help="add a snippet (opens your editor)")
    add_metadata_arguments(add_parser)
    add_parser.add_argument("--file", help="read the code from a file ('-' for stdin) instead of the editor")
    add_parser.add_argument("--stdin", action="store_true", help="read the code from stdin")
    add_parser.set_defaults(handler=cmd_add)

    list_parser = subparsers.add_parser("list", help="list stored snippets")
    list_parser.add_argument("--language", help="only show this language")
    list_parser.add_argument("--tag", help="only show snippets carrying every given tag")
    list_parser.add_argument("--json", action="store_true", help="machine readable output")
    list_parser.set_defaults(handler=cmd_list)

    search_parser = subparsers.add_parser("search", help="full-text search across all snippets")
    search_parser.add_argument("terms", nargs="+", help="words that must all appear (code included)")
    search_parser.add_argument("--language", help="restrict the search to one language")
    search_parser.add_argument("--tag", help="restrict the search to snippets with these tags")
    search_parser.add_argument("--show", action="store_true", help="print the code of every match")
    search_parser.add_argument("--json", action="store_true", help="machine readable output")
    search_parser.set_defaults(handler=cmd_search)

    show_parser = subparsers.add_parser("show", help="print one snippet")
    show_parser.add_argument("ref", help="id, slug or part of the title")
    show_parser.add_argument("--code-only", action="store_true", help="print only the code")
    show_parser.add_argument("--json", action="store_true", help="machine readable output")
    show_parser.set_defaults(handler=cmd_show)

    copy_parser = subparsers.add_parser("copy", help="copy a snippet's code to the clipboard")
    copy_parser.add_argument("ref", help="id, slug or part of the title")
    copy_parser.set_defaults(handler=cmd_copy)

    edit_parser = subparsers.add_parser("edit", help="edit metadata and/or code")
    edit_parser.add_argument("ref", help="id, slug or part of the title")
    add_metadata_arguments(edit_parser)
    edit_parser.add_argument("--file", help="replace the code with this file's content ('-' for stdin)")
    edit_parser.add_argument("--stdin", action="store_true", help="replace the code with stdin")
    edit_parser.set_defaults(handler=cmd_edit)

    delete_parser = subparsers.add_parser("delete", help="delete a snippet")
    delete_parser.add_argument("ref", help="id, slug or part of the title")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt")
    delete_parser.set_defaults(handler=cmd_delete)

    build_parser_ = subparsers.add_parser("build", help="regenerate README.md")
    build_parser_.add_argument("--title", help="heading used at the top of the README")
    build_parser_.add_argument("--check", action="store_true", help="exit 1 when README.md is stale (CI mode)")
    build_parser_.set_defaults(handler=cmd_build)

    sync_parser = subparsers.add_parser("sync", help="git add/commit/push the repository")
    sync_parser.add_argument("-m", "--message", help="commit message")
    sync_parser.add_argument("--no-push", action="store_true", help="commit locally without pushing")
    sync_parser.set_defaults(handler=cmd_sync)

    return parser


def main(argv=None) -> int:
    global USE_COLOR
    parser = build_parser()
    args = parser.parse_args(argv)
    USE_COLOR = enable_ansi() and not args.no_color
    return args.handler(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)

