# json_store.py
"""
Small shared helper for the many ``data/*.json`` stores.

Several managers each reimplemented the same idiom — load a JSON file with a
``try/except`` returning a default, and save it with ``mkdir`` + write +
best-effort Drive ``data_sync.push``. :class:`JsonStore` centralises that so the
behaviour (and its logging) lives in one place.
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("json_store")


class JsonStore:
    """
    A single JSON file on disk with load/save helpers.

    Parameters
    ----------
    path : str | Path
        Location of the JSON file (e.g. ``"data/budgets.json"``).
    default : Any
        Value returned by :meth:`load` when the file is missing or unreadable.
        A deep copy is returned each time so callers can never mutate the shared
        default.
    sync : bool
        When True, :meth:`save` also pushes the file to the shared Drive folder
        via ``data_sync`` (best-effort — never raises).
    """

    def __init__(self, path: str | Path, *, default: Any = None, sync: bool = False):
        self.path = Path(path)
        self._default = default
        self.sync = sync

    def load(self) -> Any:
        """Return the parsed JSON, or a deep copy of the default on miss/error."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not read %s: %s", self.path, exc)
        return copy.deepcopy(self._default)

    def save(self, data: Any) -> bool:
        """Write *data* as JSON (creating parent dirs). Returns True on success."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Save failed for %s: %s", self.path, exc)
            return False

        if self.sync:
            try:
                import data_sync
                data_sync.push(str(self.path))
            except Exception as exc:  # noqa: BLE001 – sync is best-effort
                log.debug("Drive sync skipped for %s: %s", self.path, exc)
        return True
