# security_utils.py
"""
Shared security helpers.

Centralises the small, dependency-free routines used to harden user-facing
surfaces of the app:

* :func:`escape_html`     – neutralise HTML/JS before it is interpolated into
                            ``st.markdown(..., unsafe_allow_html=True)`` blocks
                            (stored-XSS defence).
* :func:`sanitize_csv_value` / :func:`sanitize_df_for_export`
                          – neutralise spreadsheet formula injection before any
                            ``DataFrame.to_csv`` / ``to_excel`` download.
* :func:`validate_upload` – enforce a size cap and extension allow-list on
                            user-uploaded files before they are parsed.
"""
from __future__ import annotations

import html
from typing import Iterable, Optional

import pandas as pd


# ============================================================
# HTML / XSS
# ============================================================
def escape_html(value) -> str:
    """
    Return *value* as a string safe to interpolate into HTML.

    Escapes ``& < > " '`` so user- or AI-supplied text (item/shop names,
    receipt OCR output, usernames, …) cannot inject markup or scripts when
    rendered through ``unsafe_allow_html=True``.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


# ============================================================
# CSV / spreadsheet formula injection
# ============================================================
# Leading characters that spreadsheet apps interpret as the start of a formula.
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_value(value):
    """
    Neutralise CSV/Excel formula injection for a single cell.

    If *value* is a string beginning with a formula trigger (``= + - @`` or a
    leading tab/CR) it is prefixed with a single quote so spreadsheet software
    treats it as literal text instead of executing it. Non-string values are
    returned unchanged.
    """
    if isinstance(value, str) and value.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + value
    return value


def sanitize_df_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of *df* with every text cell run through
    :func:`sanitize_csv_value`, ready for a safe CSV/Excel export.
    """
    if df is None or df.empty:
        return df
    safe = df.copy()
    for col in safe.columns:
        if safe[col].dtype == object:
            safe[col] = safe[col].map(sanitize_csv_value)
    return safe


# ============================================================
# Upload validation
# ============================================================
class UploadValidationError(ValueError):
    """Raised when an uploaded file fails size/type validation."""


def validate_upload(
    uploaded_file,
    max_mb: float = 25,
    allowed_ext: Optional[Iterable[str]] = None,
) -> None:
    """
    Validate a Streamlit ``UploadedFile`` before it is parsed.

    Enforces a maximum size (default 25 MB) and, when *allowed_ext* is given,
    an extension allow-list. Raises :class:`UploadValidationError` on failure so
    callers can surface a friendly message and abort before loading the file
    into memory (guards against memory-exhaustion / decompression-bomb inputs).
    """
    if uploaded_file is None:
        return

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_mb * 1024 * 1024:
        raise UploadValidationError(
            f"File is too large ({size / (1024 * 1024):.1f} MB). "
            f"Maximum allowed size is {max_mb:.0f} MB."
        )

    if allowed_ext:
        name = (getattr(uploaded_file, "name", "") or "").lower()
        allowed = tuple(e.lower() for e in allowed_ext)
        if not name.endswith(allowed):
            raise UploadValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed)}."
            )
