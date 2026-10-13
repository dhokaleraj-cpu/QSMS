"""R22 · Turn raw Supabase / PostgREST errors into plain messages."""
from __future__ import annotations

import ast
import re


def db_message(exc: object) -> str:
    """Return only the human message of a PostgREST error ({'message': ..., 'code': ...})."""
    text = str(exc or "").strip()
    data = getattr(exc, "message", None)
    if isinstance(data, str) and data.strip() and not data.strip().startswith("{"):
        return data.strip()
    if text.startswith("{") and "message" in text:
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict) and parsed.get("message"):
                return str(parsed["message"]).strip()
        except Exception:
            pass
        match = re.search(r"""['"]message['"]\s*:\s*(['"])(.*?)\1\s*,\s*['"]code['"]""", text, flags=re.S)
        if match:
            return match.group(2).strip()
    return text
