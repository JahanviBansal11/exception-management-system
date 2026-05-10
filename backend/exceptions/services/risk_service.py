"""
RiskService — pure risk score calculation and persistence.

No imports from other services. Input: exception fields → Output: (score, rating).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Tuple

from django.db import transaction

if TYPE_CHECKING:
    from exceptions.models import ExceptionRequest

logger = logging.getLogger(__name__)

# Risk rating thresholds (score → label)
_THRESHOLDS = [
    (36, "Low"),
    (432, "Medium"),
    (1200, "High"),
]


class RiskService:

    @staticmethod
    def calculate_score(exception_request: "ExceptionRequest") -> int:
        """Calculate composite risk score from weighted factor product."""
        component_total = sum(c.weight for c in exception_request.data_components.all())
        if component_total == 0:
            return 0
        return (
            exception_request.asset_type.weight
            * exception_request.asset_purpose.weight
            * exception_request.data_classification.weight
            * exception_request.internet_exposure.weight
            * component_total
        )

    @staticmethod
    def determine_rating(score: int) -> str:
        """Map a numeric score to a risk rating label."""
        for threshold, label in _THRESHOLDS:
            if score < threshold:
                return label
        return "Critical"

    @staticmethod
    def recalculate_and_persist(exception_request: "ExceptionRequest") -> Tuple[int, str]:
        """
        Atomically recalculate risk and persist to DB.
        Uses select_for_update to prevent concurrent M2M race conditions.
        Returns (score, rating).
        """
        from exceptions.models import ExceptionRequest as ER

        with transaction.atomic():
            locked = ER.objects.select_for_update().get(pk=exception_request.pk)
            score = RiskService.calculate_score(locked)
            rating = RiskService.determine_rating(score)
            ER.objects.filter(pk=locked.pk).update(risk_score=score, risk_rating=rating)

        logger.debug("Exception #%s risk: score=%s rating=%s", exception_request.pk, score, rating)
        return score, rating