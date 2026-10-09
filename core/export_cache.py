"""R12 performance: per-session memo for PDF / Excel export builders.

Pages build their PDF/Excel download bytes on every Streamlit rerun, so typing in
any field used to regenerate every report on the page. Builders are pure functions
of their input, so identical input returns the cached bytes instantly. The cache
lives in the user's session only, keeps the 24 most recent exports, and is bypassed
outside a running Streamlit session (tests, scripts).
"""
from __future__ import annotations

import functools
import hashlib
import pickle
from collections import OrderedDict
from typing import Any, Callable, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])
_MAX_ENTRIES = 24
_STATE_KEY = "_qcms_export_bytes_memo"


def _in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def session_memo_bytes(fn: _F) -> _F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _in_streamlit():
            return fn(*args, **kwargs)
        try:
            digest = hashlib.sha256(pickle.dumps((fn.__module__, fn.__qualname__, args, sorted(kwargs.items())), protocol=4)).hexdigest()
        except Exception:
            return fn(*args, **kwargs)
        import streamlit as st
        store = st.session_state.get(_STATE_KEY)
        if not isinstance(store, OrderedDict):
            store = OrderedDict()
            st.session_state[_STATE_KEY] = store
        if digest in store:
            store.move_to_end(digest)
            return store[digest]
        result = fn(*args, **kwargs)
        store[digest] = result
        while len(store) > _MAX_ENTRIES:
            store.popitem(last=False)
        return result
    wrapper.__wrapped_uncached__ = fn  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
