"""
PHANTOM-NEOTRON Integration Module

Integra Phantom Intelligence com Neotron Compliance Framework.
Garante que todas as recomendações de ADRs passem por validação de compliance.
"""

from phantom.neotron.oracle_explainer import OracleExplainer
from phantom.neotron.sentinel_integration import (
    PhantomGuardrails,
    PhantomSentinel,
    validate_recommendation,
)

__all__ = [
    "PhantomSentinel",
    "PhantomGuardrails",
    "validate_recommendation",
    "OracleExplainer",
]
