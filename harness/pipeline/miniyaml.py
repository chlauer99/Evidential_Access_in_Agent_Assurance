"""Load the pipeline configs: PyYAML if installed, else a small parser for the YAML subset the configs use
(nested block mappings, block lists of scalars, flow lists/maps such as [a, b] and {k: v, k2: [x]}, scalars,
comments). JSON configs are accepted as well."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _scalar(s: str):
    s = s.strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "yes"):
        return True
    if s in ("false", "False", "no"):
        return False
    if (s[0] == s[-1]) and s[0] in "\"'" and len(s) >= 2:
        return s[1:-1].replace('\\"', '"') if s[0] == '"' else s[1:-1].replace("''", "'")
    if s[0] in "[{":
        v, rest = _flow(s, 0)
        return v
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", s):
        return float(s)
    return s


def _flow(s, i):
    """Parse a flow collection starting at s[i]; return (value, index after it)."""
    open_, close = s[i], "]" if s[i] == "[" else "}"
    i += 1; items = [] if open_ == "[" else {}
    buf, depth, q = "", 0, None
    parts = []
    while i < len(s):
        c = s[i]
        if q:
            buf += c
            if c == q:
                q = None
        elif c in "\"'":
            q = c; buf += c
        elif c in "[{":
            v, i = _flow(s, i); parts.append(("val", buf, v)); buf = ""; continue
        elif c == ",":
            parts.append(("str", buf, None)); buf = ""
        elif c == close:
            parts.append(("str", buf, None)); i += 1; break
        else:
            buf += c
        i += 1
    # assemble
    pending_key = None
    for kind, text, val in parts:
        if open_ == "[":
            if kind == "val":
                items.append(val)
            elif text.strip():
                items.append(_scalar(text))
        else:
            if kind == "val":
                k = text.strip().rstrip(":").strip()
                items[k] = val
            elif text.strip():
                k, _, v = text.partition(":")
                items[k.strip().strip("\"'")] = _scalar(v)
    return items, i


def _strip_comment(line: str) -> str:
    out, q = "", None
    for i, c in enumerate(line):
        if q:
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out += c
    return out.rstrip()


def _parse_block(lines, i, indent):
    """Parse lines[i:] at the given indentation; return (value, next index)."""
    if i < len(lines) and lines[i][1].startswith("- "):
        out = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            out.append(_scalar(lines[i][1][2:])); i += 1
        return out, i
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        text = lines[i][1]
        k, _, v = text.partition(":")
        k = k.strip().strip("\"'")
        if v.strip():
            out[k] = _scalar(v); i += 1
        else:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                out[k], i = _parse_block(lines, i, lines[i][0])
            else:
                out[k] = None
    return out, i


def load(path) -> dict:
    p = Path(path)
    txt = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(txt)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(txt)
    except ImportError:
        pass
    lines = []
    for raw in txt.splitlines():
        s = _strip_comment(raw)
        if s.strip():
            lines.append((len(s) - len(s.lstrip(" ")), s.strip()))
    v, _ = _parse_block(lines, 0, lines[0][0] if lines else 0)
    return v
