from etf_fundamental_score.factors.aum import AumFactor
from etf_fundamental_score.factors.concentration import ConcentrationFactor
from etf_fundamental_score.factors.fee import FeeFactor
from etf_fundamental_score.factors.flow import FlowFactor
from etf_fundamental_score.factors.tracking_error import TrackingErrorFactor
from etf_fundamental_score.factors.valuation import ValuationFactor

FACTOR_REGISTRY = {
    "aum": AumFactor,
    "fee": FeeFactor,
    "tracking_error": TrackingErrorFactor,
    "concentration": ConcentrationFactor,
    "valuation": ValuationFactor,
    "flow": FlowFactor,
}

__all__ = [
    "FACTOR_REGISTRY",
    "AumFactor",
    "FeeFactor",
    "TrackingErrorFactor",
    "ConcentrationFactor",
    "ValuationFactor",
    "FlowFactor",
]
