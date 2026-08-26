"""Internal runtime clock for retry references."""

from __future__ import annotations

import time


def now() -> int:
    return int(time.time())
