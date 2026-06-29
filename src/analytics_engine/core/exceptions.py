class AnalyticsError(Exception):
    """Base exception for analytics engine."""


class ConfigError(AnalyticsError):
    """Configuration loading or validation error."""


class AmountParseError(AnalyticsError):
    """Failed to parse an amount string."""


class PipelineError(AnalyticsError):
    """Pipeline execution error."""


class MetricComputeError(PipelineError):
    """Error computing a metric."""


class DetectorError(PipelineError):
    """Error running a detector."""
