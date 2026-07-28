#!/usr/bin/env python3
"""
Message extraction and catalog maintenance for MlamehTicket.

Pure-Python stand-in for `manage.py makemessages` / `compilemessages`. The GNU
gettext binaries (xgettext, msgfmt) are not required, so the i18n workflow works
on a plain Windows checkout and in CI.

Templates are run through Django's own `templatize()` -- the same helper
makemessages uses -- which correctly handles `{% trans %}`, `{% blocktrans %}`,
plurals and context. Its output is deliberately not valid Python (it pads
non-translatable text to preserve line numbers), so the `gettext(...)` calls are
recovered with a string-literal scanner rather than the `tokenize` module.
Python sources are read with `ast`.

Usage:
    python scripts/i18n.py extract          # report what is extractable
    python scripts/i18n.py update           # merge into the .po, keeping msgstr
    python scripts/i18n.py compile          # write the .mo
    python scripts/i18n.py check            # exit 1 on missing/untranslated
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCALE = "ar"

TEMPLATE_ROOT = PROJECT_ROOT / "templates"
PYTHON_EXCLUDE_DIRS = {".venv", "staticfiles", "media", "node_modules", "__pycache__", "migrations"}

# Strings that are deliberately identical in every language; `check` ignores them.
UNTRANSLATED_ALLOWLIST = {
    "TLS",
    "SSL",
    "user@example.com",
    "sender@example.com",
    "noreply@example.com",
}

# gettext call signatures, as they appear in templatize() output and in source.
# gettext_noop marks strings that are translated later via the `|gettext` filter,
# so they must be collected even though the call site itself does not translate.
SINGULAR_FUNCS = {"_", "gettext", "gettext_lazy", "gettext_noop", "ugettext", "ugettext_lazy"}
PLURAL_FUNCS = {"ngettext", "ngettext_lazy", "ungettext", "ungettext_lazy"}
CONTEXT_FUNCS = {"pgettext", "pgettext_lazy"}
CONTEXT_PLURAL_FUNCS = {"npgettext", "npgettext_lazy"}
ALL_FUNCS = SINGULAR_FUNCS | PLURAL_FUNCS | CONTEXT_FUNCS | CONTEXT_PLURAL_FUNCS

PYTHON_FORMAT_RE = re.compile(r"%(?:\([^)]*\))?[sdifger%]")


@dataclass
class Message:
    """One translatable string, plus every place it appears."""

    msgid: str
    plural: str | None = None
    context: str | None = None
    locations: set[tuple[str, int]] = field(default_factory=set)

    @property
    def key(self) -> tuple[str | None, str]:
        return (self.context, self.msgid)

    @property
    def is_python_format(self) -> bool:
        return bool(PYTHON_FORMAT_RE.search(self.msgid)) or bool(
            self.plural and PYTHON_FORMAT_RE.search(self.plural)
        )


class MessageSet:
    """Accumulates messages, merging locations for repeated strings."""

    def __init__(self) -> None:
        self._messages: dict[tuple[str | None, str], Message] = {}
        self.call_count = 0

    def add(
        self,
        msgid: str,
        *,
        path: str,
        line: int,
        plural: str | None = None,
        context: str | None = None,
    ) -> None:
        if not msgid:
            return
        self.call_count += 1
        key = (context, msgid)
        existing = self._messages.get(key)
        if existing is None:
            existing = Message(msgid=msgid, plural=plural, context=context)
            self._messages[key] = existing
        elif plural and not existing.plural:
            existing.plural = plural
        existing.locations.add((path, line))

    def __len__(self) -> int:
        return len(self._messages)

    def __contains__(self, key: object) -> bool:
        return key in self._messages

    def get(self, key: tuple[str | None, str]) -> Message | None:
        return self._messages.get(key)

    def values(self):
        return self._messages.values()

    def sorted_values(self) -> list[Message]:
        """Deterministic order: first source location, then msgid."""

        def sort_key(msg: Message):
            first = min(msg.locations) if msg.locations else ("", 0)
            return (first[0], first[1], msg.msgid)

        return sorted(self._messages.values(), key=sort_key)

    def keys(self):
        return self._messages.keys()


# --------------------------------------------------------------------------- #
# Literal scanner for templatize() output
# --------------------------------------------------------------------------- #


def _decode_literal(raw: str) -> str:
    """Turn the source text of a string literal into its value."""
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        # templatize normally escapes newlines; tolerate it if it ever does not.
        inner = raw
        for quote in ("'''", '"""', "'", '"'):
            if inner.startswith(quote) and inner.endswith(quote) and len(inner) >= 2 * len(quote):
                inner = inner[len(quote) : -len(quote)]
                break
        return (
            inner.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace("\\\\", "\\")
        )
    return value if isinstance(value, str) else str(value)


def scan_gettext_calls(source: str) -> list[tuple[str, list[str], int]]:
    """
    Find gettext-family calls in templatize() output.

    Returns (function name, decoded string literal arguments, 1-based line).
    """
    results: list[tuple[str, list[str], int]] = []
    i, line, length = 0, 1, len(source)

    while i < length:
        char = source[i]

        if char == "\n":
            line += 1
            i += 1
            continue

        if not (char.isalpha() or char == "_"):
            i += 1
            continue

        start = i
        while i < length and (source[i].isalnum() or source[i] == "_"):
            i += 1
        word = source[start:i]

        if word not in ALL_FUNCS or i >= length or source[i] != "(":
            continue

        call_line = line
        i += 1  # step past "("
        depth = 1
        literals: list[str] = []

        while i < length and depth:
            char = source[i]

            if char == "\n":
                line += 1
                i += 1
                continue

            if char in "\"'":
                quote = source[i : i + 3] if source[i : i + 3] in ("'''", '"""') else char
                lit_start = i
                i += len(quote)
                while i < length:
                    if source[i] == "\\":
                        i += 2
                        continue
                    if source[i : i + len(quote)] == quote:
                        i += len(quote)
                        break
                    if source[i] == "\n":
                        line += 1
                    i += 1
                literals.append(_decode_literal(source[lit_start:i]))
                continue

            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            i += 1

        results.append((word, literals, call_line))

    return results


def extract_templates(message_set: MessageSet) -> int:
    """Extract from every Django template. Returns the file count."""
    from django.utils.translation.template import templatize

    files = sorted(TEMPLATE_ROOT.rglob("*.html"))
    for template_path in files:
        rel = template_path.relative_to(PROJECT_ROOT).as_posix()
        # utf-8-sig: several sources in this repo carry a UTF-8 BOM.
        raw = template_path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            templatized = templatize(raw, origin=rel)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  warning: could not templatize {rel}: {exc}", file=sys.stderr)
            continue

        for func, literals, line in scan_gettext_calls(templatized):
            if func in CONTEXT_PLURAL_FUNCS and len(literals) >= 3:
                message_set.add(
                    literals[1], plural=literals[2], context=literals[0], path=rel, line=line
                )
            elif func in CONTEXT_FUNCS and len(literals) >= 2:
                message_set.add(literals[1], context=literals[0], path=rel, line=line)
            elif func in PLURAL_FUNCS and len(literals) >= 2:
                message_set.add(literals[0], plural=literals[1], path=rel, line=line)
            elif literals:
                message_set.add(literals[0], path=rel, line=line)

    return len(files)


# --------------------------------------------------------------------------- #
# ast-based extraction for Python sources
# --------------------------------------------------------------------------- #


def _iter_python_files():
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in PYTHON_EXCLUDE_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_python(message_set: MessageSet) -> int:
    """Extract from every Python source file. Returns the file count."""
    count = 0
    for py_path in _iter_python_files():
        rel = py_path.relative_to(PROJECT_ROOT).as_posix()
        try:
            tree = ast.parse(
                py_path.read_text(encoding="utf-8-sig", errors="replace"), filename=rel
            )
        except SyntaxError as exc:
            print(f"  warning: could not parse {rel}: {exc}", file=sys.stderr)
            continue
        count += 1

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                continue
            if name not in ALL_FUNCS:
                continue

            args = [_string_arg(a) for a in node.args]
            line = node.lineno

            if name in CONTEXT_PLURAL_FUNCS and len(args) >= 3 and args[0] and args[1]:
                message_set.add(
                    args[1], plural=args[2], context=args[0], path=rel, line=line
                )
            elif name in CONTEXT_FUNCS and len(args) >= 2 and args[0] and args[1]:
                message_set.add(args[1], context=args[0], path=rel, line=line)
            elif name in PLURAL_FUNCS and len(args) >= 2 and args[0] and args[1]:
                message_set.add(args[0], plural=args[1], path=rel, line=line)
            elif args and args[0]:
                message_set.add(args[0], path=rel, line=line)

    return count


def collect_messages(verbose: bool = True) -> MessageSet:
    """Run both extractors against a configured Django."""
    _setup_django()
    message_set = MessageSet()
    template_count = extract_templates(message_set)
    python_count = extract_python(message_set)
    if verbose:
        print(f"  templates scanned : {template_count}")
        print(f"  python files      : {python_count}")
        print(f"  gettext calls     : {message_set.call_count}")
        print(f"  distinct messages : {len(message_set)}")
    return message_set


def _setup_django() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


# --------------------------------------------------------------------------- #
# Catalog helpers
# --------------------------------------------------------------------------- #


def _require_polib():
    try:
        import polib
    except ImportError:
        sys.exit(
            "Error: polib is not installed.\n"
            "Install it with: pip install -r requirements-dev.txt"
        )
    return polib


def po_path(locale: str) -> Path:
    return PROJECT_ROOT / "locale" / locale / "LC_MESSAGES" / "django.po"


def mo_path(locale: str) -> Path:
    return po_path(locale).with_suffix(".mo")


def load_catalog(locale: str):
    polib = _require_polib()
    path = po_path(locale)
    if not path.exists():
        sys.exit(f"Error: catalog not found at {path}")
    return polib.pofile(str(path), wrapwidth=78)


def nplurals_of(catalog) -> int:
    header = catalog.metadata.get("Plural-Forms", "")
    match = re.search(r"nplurals\s*=\s*(\d+)", header)
    return int(match.group(1)) if match else 2


def entry_key(entry) -> tuple[str | None, str]:
    return (entry.msgctxt or None, entry.msgid)


def is_translated(entry, nplurals: int) -> bool:
    if entry.msgid_plural:
        if not entry.msgstr_plural:
            return False
        return all(str(entry.msgstr_plural.get(i, "")).strip() for i in range(nplurals))
    return bool(entry.msgstr.strip())


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_extract(args) -> int:
    print("Extracting translatable strings...")
    messages = collect_messages()

    if args.list:
        print("\nAll extracted messages:")
        for msg in messages.sorted_values():
            first = min(msg.locations)
            label = f"{first[0]}:{first[1]}"
            print(f"  {label:<58} {msg.msgid[:70]!r}")
    return 0


def cmd_update(args) -> int:
    locale = args.locale
    print(f"Updating catalog for locale '{locale}'...")
    messages = collect_messages()

    catalog = load_catalog(locale)
    polib = _require_polib()
    nplurals = nplurals_of(catalog)
    print(f"  nplurals          : {nplurals}")

    # Index the catalog, collapsing duplicate msgids and preferring the copy that
    # carries a translation. gettext resolves duplicates to whichever copy compiled
    # last, so leaving them in place makes the effective translation ambiguous.
    # Obsolete entries are indexed separately so a string that reappears in the
    # source is revived with its old translation instead of being re-added empty.
    existing: dict[tuple[str | None, str], object] = {}
    retired: dict[tuple[str | None, str], object] = {}
    duplicates = []

    for entry in catalog:
        index = retired if entry.obsolete else existing
        key = entry_key(entry)
        kept = index.get(key)
        if kept is None:
            index[key] = entry
        elif is_translated(entry, nplurals) and not is_translated(kept, nplurals):
            index[key] = entry
            duplicates.append(kept)
        else:
            duplicates.append(entry)
    for entry in duplicates:
        catalog.remove(entry)

    updated = obsoleted = added = promoted = revived = 0

    def refresh(entry, msg) -> None:
        """Point an existing entry at its current source locations."""
        nonlocal promoted
        entry.obsolete = 0
        entry.occurrences = sorted(msg.locations)

        if msg.is_python_format and "python-format" not in entry.flags:
            entry.flags.append("python-format")

        # A string that gained a plural form keeps its existing singular text.
        if msg.plural and not entry.msgid_plural:
            entry.msgid_plural = msg.plural
            carried = entry.msgstr
            entry.msgstr = ""
            entry.msgstr_plural = {i: (carried if i == 0 else "") for i in range(nplurals)}
            promoted += 1
        elif msg.plural:
            entry.msgid_plural = msg.plural
            for i in range(nplurals):
                entry.msgstr_plural.setdefault(i, "")

    seen: set[tuple[str | None, str]] = set()

    for msg in messages.sorted_values():
        entry = existing.get(msg.key)
        if entry is not None:
            refresh(entry, msg)
            seen.add(msg.key)
            updated += 1
            continue

        entry = retired.pop(msg.key, None)
        if entry is not None:
            refresh(entry, msg)
            existing[msg.key] = entry
            seen.add(msg.key)
            revived += 1
            continue

        entry = polib.POEntry(
            msgid=msg.msgid,
            msgstr="",
            msgctxt=msg.context,
            occurrences=sorted(msg.locations),
        )
        if msg.plural:
            entry.msgid_plural = msg.plural
            entry.msgstr_plural = {i: "" for i in range(nplurals)}
        if msg.is_python_format:
            entry.flags.append("python-format")
        catalog.append(entry)
        existing[msg.key] = entry
        seen.add(msg.key)
        added += 1

    # Anything still active but no longer referenced becomes obsolete. The msgstr
    # is kept so the translation survives if the string comes back.
    for key, entry in existing.items():
        if key not in seen:
            entry.obsolete = 1
            obsoleted += 1

    catalog.save(str(po_path(locale)))

    total = len([e for e in catalog if not e.obsolete])
    untranslated = [e for e in catalog if not e.obsolete and not is_translated(e, nplurals)]
    print(f"  entries refreshed  : {updated}")
    print(f"  duplicates removed : {len(duplicates)}")
    print(f"  revived from stale : {revived}")
    print(f"  entries added      : {added}")
    print(f"  promoted to plural : {promoted}")
    print(f"  marked obsolete    : {obsoleted}")
    print(f"  active entries     : {total}")
    print(f"  untranslated       : {len(untranslated)}")
    print(f"\nWrote {po_path(locale)}")
    if untranslated:
        print("Run 'python scripts/i18n.py check --verbose' to list what still needs Arabic.")
    return 0


def cmd_compile(args) -> int:
    locale = args.locale
    catalog = load_catalog(locale)
    nplurals = nplurals_of(catalog)

    active = [e for e in catalog if not e.obsolete]
    translated = [e for e in active if is_translated(e, nplurals)]
    print(f"Catalog: {po_path(locale)}")
    print(f"  active entries : {len(active)}")
    print(f"  translated     : {len(translated)}")
    print(f"  untranslated   : {len(active) - len(translated)}")

    fuzzy = catalog.fuzzy_entries()
    if fuzzy:
        # Like msgfmt, polib omits fuzzy entries from the .mo, so a fuzzy string
        # still renders in English no matter what its msgstr says.
        print(f"  fuzzy          : {len(fuzzy)}  (EXCLUDED from the .mo - will render English)")
        for entry in fuzzy:
            print(f"      {entry.msgid[:88]!r}")

    catalog.save_as_mofile(str(mo_path(locale)))
    print(f"\nCompiled -> {mo_path(locale)}")
    return 0


def cmd_check(args) -> int:
    locale = args.locale
    messages = collect_messages(verbose=not args.quiet)
    catalog = load_catalog(locale)
    nplurals = nplurals_of(catalog)

    by_key = {entry_key(e): e for e in catalog if not e.obsolete}

    missing: list[Message] = []
    untranslated: list[Message] = []

    for msg in messages.sorted_values():
        if msg.msgid in UNTRANSLATED_ALLOWLIST:
            continue
        entry = by_key.get(msg.key)
        if entry is None:
            missing.append(msg)
        elif not is_translated(entry, nplurals):
            untranslated.append(msg)

    stale = [e for e in catalog if not e.obsolete and entry_key(e) not in messages.keys()]
    fuzzy = catalog.fuzzy_entries()

    def report(label: str, items: list[Message]) -> None:
        print(f"\n{label}: {len(items)}")
        if not items or not args.verbose:
            return
        for msg in items:
            first = min(msg.locations)
            print(f"  {first[0]}:{first[1]}")
            print(f"    {msg.msgid[:100]!r}")

    report("Missing from catalog", missing)
    report("Present but untranslated", untranslated)
    print(f"\nIn catalog but no longer in source: {len(stale)}")
    print(f"Fuzzy (awaiting native review): {len(fuzzy)}")

    if missing or untranslated:
        total = len(missing) + len(untranslated)
        print(
            f"\nFAIL: {total} of {len(messages)} strings would fall back to English."
        )
        if not args.verbose:
            print("Re-run with --verbose to list them.")
        print("Fix with: python scripts/i18n.py update  (then translate the new entries)")
        return 1

    print(f"\nOK: all {len(messages)} extracted strings resolve to a translation.")
    return 0


def main() -> int:
    # Some msgids contain non-ASCII (typographic ellipsis, Arabic); a cp1252
    # console would otherwise raise UnicodeEncodeError mid-report.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Extract, update, compile and verify translation catalogs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--locale", default=DEFAULT_LOCALE, help=f"locale to operate on (default: {DEFAULT_LOCALE})"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="report extractable strings")
    p_extract.add_argument("--list", action="store_true", help="print every message found")
    p_extract.set_defaults(func=cmd_extract)

    p_update = sub.add_parser("update", help="merge extracted strings into the .po")
    p_update.set_defaults(func=cmd_update)

    p_compile = sub.add_parser("compile", help="compile the .po into a .mo")
    p_compile.set_defaults(func=cmd_compile)

    p_check = sub.add_parser("check", help="fail if any string lacks a translation")
    p_check.add_argument("--verbose", action="store_true", help="list offending strings")
    p_check.add_argument("--quiet", action="store_true", help="suppress extraction stats")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
