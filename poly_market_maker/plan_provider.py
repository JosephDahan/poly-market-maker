from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.common.plans import PlanSnapshotEntry, fetch_plan_for_market  # noqa: E402


class PlanProvider:
    """Accessor for allocator plans stored in Neon."""

    def __init__(self, market_id: str) -> None:
        self.market_id = market_id
        self.logger = logging.getLogger(self.__class__.__name__)

    def current(self) -> Optional[PlanSnapshotEntry]:
        try:
            plan = fetch_plan_for_market(self.market_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("Failed to fetch plan for %s: %s", self.market_id, exc)
            return None
        return plan
