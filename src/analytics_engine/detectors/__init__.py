"""Detector library — import all modules to trigger @registry.register decorators."""

from analytics_engine.detectors import (
    aging,  # noqa: F401
    ccc_stretch,  # noqa: F401
    concentration,  # noqa: F401
    liquidity,  # noqa: F401
    payable_cliff,  # noqa: F401
    sales_decline,  # noqa: F401
)
from analytics_engine.detectors.base import DetectorProtocol, detector_registry

__all__ = ["detector_registry", "DetectorProtocol"]
