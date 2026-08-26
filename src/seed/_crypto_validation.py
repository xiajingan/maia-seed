"""Strict boundary validation for crypto contracts."""

from __future__ import annotations

import re
from typing import cast

KEY_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
MAX_DATA = 4096
MAX_FRAME = 12288


def valid_key_id(value: object) -> bool:
    return type(value) is str and KEY_ID.fullmatch(value) is not None


def validate_ring_ids(active_key_id: object, previous_key_ids: object) -> tuple[str, tuple[str, ...]] | None:
    if not valid_key_id(active_key_id) or type(previous_key_ids) is not tuple or len(previous_key_ids) > 8:
        return None
    if any(not valid_key_id(key) for key in previous_key_ids):
        return None
    active = cast(str, active_key_id)
    previous = cast(tuple[str, ...], previous_key_ids)
    if active in previous or len(set(previous)) != len(previous):
        return None
    return active, previous


def valid_data(value: object) -> bool:
    return type(value) is bytes and len(value) <= MAX_DATA


def valid_frame(value: object) -> bool:
    return type(value) is bytes and len(value) <= MAX_FRAME
