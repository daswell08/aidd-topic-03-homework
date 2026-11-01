from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.utils import timezone


def quotation_to_decimal(quotation) -> Decimal:
    """Convert a Tinkoff Quotation/MoneyValue to Decimal, including nano."""
    if quotation is None:
        return Decimal("0")
    units = Decimal(getattr(quotation, "units", 0) or 0)
    nano = Decimal(getattr(quotation, "nano", 0) or 0)
    return units + nano / Decimal("1000000000")


def quotation_to_float(quotation) -> float:
    return float(quotation_to_decimal(quotation))


def as_aware_datetime(value: Optional[datetime]) -> datetime:
    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value
