#!/usr/bin/env python3
"""
SENTINEL Integration - Compliance Guardrails para Phantom

Valida que todas as recomendações do Phantom atendam requisitos de compliance:
- LGPD Art. 20: Direito à revisão de decisões automatizadas
- LGPD Art. 18: Direito à explicação
- SOC2: Auditabilidade e rastreabilidade
"""

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("phantom.neotron.sentinel")

# Importar Neotron SENTINEL (com fallback se não disponível)
NEOTRON_AVAILABLE = False
try:
    # Adicionar path do Neotron
    neotron_path = Path("/home/kernelcore/master/neotron")
    if neotron_path.exists():
        sys.path.insert(0, str(neotron_path))

    from neutron.compliance.sentinel import (
        AgentOutput,
        ComplianceGuardrail,
        ComplianceViolation,
        EnforcedOutput,
        ValidationResult,
    )
    NEOTRON_AVAILABLE = True
    logger.info("Neotron SENTINEL loaded successfully")
except ImportError as e:
    logger.warning(f"Neotron not available: {e}. Running in bypass mode.")

    # Fallback classes para quando Neotron não está disponível
    @dataclass
    class AgentOutput:
        content: str
        metadata: dict | None = None
        has_explanation: bool = False
        explanation: str | None = None
        explanation_quality: float = 0.0
        model_name: str | None = None
        timestamp: datetime = None

        def __post_init__(self):
            if self.timestamp is None:
                self.timestamp = datetime.utcnow()

    @dataclass
    class ValidationResult:
        passed: bool
        details: str
        confidence: float = 1.0
        metadata: dict | None = None

    @dataclass
    class EnforcedOutput:
        original: AgentOutput
        validation_result: ValidationResult
        guardrail_name: str
        regulation: str
        enforced: bool
        audit_id: int | None = None

    class ComplianceViolation(Exception):
        pass

    class ComplianceGuardrail:
        def __init__(self, name, regulation, check, severity, description=""):
            self.name = name
            self.regulation = regulation
            self.check = check
            self.severity = severity
            self.description = description
            self.enabled = True

        def enforce(self, output: AgentOutput) -> EnforcedOutput:
            result = self.check(output)
            if not result.passed and self.severity == "block":
                raise ComplianceViolation(f"Compliance violation: {self.name} ({self.regulation})")
            return EnforcedOutput(
                original=output,
                validation_result=result,
                guardrail_name=self.name,
                regulation=self.regulation,
                enforced=True
            )


# =============================================================================
# Phantom-Specific Guardrails
# =============================================================================

def check_has_explanation(output: AgentOutput) -> ValidationResult:
    """
    LGPD Art. 18 - Direito à explicação

    Toda recomendação do Phantom deve ter uma explicação clara
    sobre porque aquele ADR foi recomendado.
    """
    if not output.has_explanation or not output.explanation:
        return ValidationResult(
            passed=False,
            details="Recomendação sem explicação (LGPD Art. 18 violation)",
            confidence=1.0,
            metadata={"missing": "explanation"}
        )

    # Verificar qualidade da explicação (mínimo 10 caracteres)
    if len(output.explanation) < 10:
        return ValidationResult(
            passed=False,
            details="Explicação muito curta (low quality)",
            confidence=0.8,
            metadata={"explanation_length": len(output.explanation)}
        )

    return ValidationResult(
        passed=True,
        details="Explicação fornecida conforme LGPD Art. 18",
        confidence=1.0,
        metadata={"explanation_length": len(output.explanation)}
    )


def check_adr_traceability(output: AgentOutput) -> ValidationResult:
    """
    SOC2 - Auditabilidade e rastreabilidade

    Toda recomendação deve rastrear de volta ao ADR que a originou.
    """
    metadata = output.metadata or {}

    if "adr_id" not in metadata:
        return ValidationResult(
            passed=False,
            details="Recomendação sem rastreabilidade para ADR (SOC2 violation)",
            confidence=1.0,
            metadata={"missing": "adr_id"}
        )

    adr_id = metadata.get("adr_id")
    if not adr_id or not isinstance(adr_id, str):
        return ValidationResult(
            passed=False,
            details="ADR ID inválido",
            confidence=1.0,
            metadata={"adr_id": adr_id}
        )

    # Verificar formato ADR-XXXX
    if not adr_id.startswith("ADR-"):
        return ValidationResult(
            passed=False,
            details=f"ADR ID em formato inválido: {adr_id}",
            confidence=0.9,
            metadata={"adr_id": adr_id}
        )

    return ValidationResult(
        passed=True,
        details=f"Rastreabilidade OK: {adr_id}",
        confidence=1.0,
        metadata={"adr_id": adr_id}
    )


def check_recommendation_safety(output: AgentOutput) -> ValidationResult:
    """
    Segurança - Recomendações não podem ser destrutivas

    Verifica se a recomendação não contém comandos perigosos.
    """
    dangerous_patterns = [
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs.",
        "format c:",
        "> /dev/sda",
        "kill -9 1",  # kill init
        "reboot -f",  # força reboot sem sync
    ]

    content = output.content.lower()

    for pattern in dangerous_patterns:
        if pattern.lower() in content:
            return ValidationResult(
                passed=False,
                details=f"Comando perigoso detectado: {pattern}",
                confidence=1.0,
                metadata={"dangerous_pattern": pattern}
            )

    return ValidationResult(
        passed=True,
        details="Recomendação segura",
        confidence=1.0
    )


# =============================================================================
# Phantom Guardrails Registry
# =============================================================================

class PhantomGuardrails:
    """Registry de guardrails específicos do Phantom"""

    EXPLANATION_REQUIRED = ComplianceGuardrail(
        name="phantom_explanation_required",
        regulation="LGPD",
        check=check_has_explanation,
        severity="block",
        description="LGPD Art. 18 - Toda recomendação deve ter explicação"
    )

    ADR_TRACEABILITY = ComplianceGuardrail(
        name="phantom_adr_traceability",
        regulation="SOC2",
        check=check_adr_traceability,
        severity="block",
        description="SOC2 - Rastreabilidade para ADR fonte"
    )

    SAFETY_CHECK = ComplianceGuardrail(
        name="phantom_safety_check",
        regulation="SOC2",
        check=check_recommendation_safety,
        severity="block",
        description="Verificação de segurança - sem comandos destrutivos"
    )

    @classmethod
    def all_guardrails(cls) -> list[ComplianceGuardrail]:
        """Retorna todos os guardrails"""
        return [
            cls.EXPLANATION_REQUIRED,
            cls.ADR_TRACEABILITY,
            cls.SAFETY_CHECK,
        ]


# =============================================================================
# Phantom SENTINEL Engine
# =============================================================================

class PhantomSentinel:
    """
    SENTINEL engine para Phantom

    Aplica todos os guardrails de compliance em recomendações do Phantom.
    """

    def __init__(self, guardrails: list[ComplianceGuardrail] | None = None):
        self.guardrails = guardrails or PhantomGuardrails.all_guardrails()
        self.neotron_available = NEOTRON_AVAILABLE
        logger.info(
            f"PhantomSentinel initialized with {len(self.guardrails)} guardrails "
            f"(Neotron: {'available' if NEOTRON_AVAILABLE else 'bypass mode'})"
        )

    def validate(
        self,
        recommendation: str,
        adr_id: str | None = None,
        explanation: str | None = None,
        model_name: str = "phantom-cerebro",
    ) -> EnforcedOutput:
        """
        Valida uma recomendação contra todos os guardrails

        Args:
            recommendation: Texto da recomendação
            adr_id: ID do ADR que originou a recomendação
            explanation: Explicação de porque essa recomendação foi feita
            model_name: Nome do modelo/engine que gerou

        Returns:
            EnforcedOutput com resultados de validação

        Raises:
            ComplianceViolation: Se algum guardrail severity="block" falhar
        """

        # Criar AgentOutput
        output = AgentOutput(
            content=recommendation,
            metadata={"adr_id": adr_id} if adr_id else {},
            has_explanation=bool(explanation),
            explanation=explanation,
            explanation_quality=len(explanation or "") / 100.0,  # Heurística simples
            model_name=model_name,
        )

        # Aplicar todos os guardrails
        results: list[EnforcedOutput] = []

        for guardrail in self.guardrails:
            try:
                enforced = guardrail.enforce(output)
                results.append(enforced)

                if not enforced.validation_result.passed:
                    logger.warning(
                        f"Guardrail '{guardrail.name}' failed: "
                        f"{enforced.validation_result.details}"
                    )

            except ComplianceViolation as e:
                logger.error(f"Compliance violation: {e}")
                raise

        # Se todos passaram, retornar o último resultado
        # (ou criar um resultado consolidado)
        passed_all = all(r.validation_result.passed for r in results)

        return EnforcedOutput(
            original=output,
            validation_result=ValidationResult(
                passed=passed_all,
                details=f"Validado por {len(results)} guardrails",
                confidence=1.0,
                metadata={
                    "total_guardrails": len(results),
                    "passed": sum(1 for r in results if r.validation_result.passed),
                    "failed": sum(1 for r in results if not r.validation_result.passed),
                }
            ),
            guardrail_name="phantom_sentinel_suite",
            regulation="LGPD+SOC2",
            enforced=True
        )


# =============================================================================
# Utility Functions
# =============================================================================

def validate_recommendation(
    recommendation: str,
    adr_id: str | None = None,
    explanation: str | None = None,
) -> tuple[bool, str]:
    """
    Helper function para validação rápida

    Returns:
        (passed, details) - True se passou, False se falhou + detalhes
    """
    sentinel = PhantomSentinel()

    try:
        result = sentinel.validate(recommendation, adr_id, explanation)
        return (result.validation_result.passed, result.validation_result.details)

    except ComplianceViolation as e:
        return (False, str(e))


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("PHANTOM SENTINEL - Compliance Validation")
    print("=" * 60)

    sentinel = PhantomSentinel()

    # Test 1: Válida com tudo OK
    print("\n[TEST 1] Recomendação válida:")
    try:
        result = sentinel.validate(
            recommendation="Verificar ventilação do sistema",
            adr_id="ADR-0023",
            explanation="Baseado no ADR-0023 sobre thermal management, a temperatura de 82°C está acima do threshold seguro de 75°C"
        )
        print(f"  ✅ PASSED: {result.validation_result.details}")
    except ComplianceViolation as e:
        print(f"  ❌ BLOCKED: {e}")

    # Test 2: Sem explicação (deve falhar)
    print("\n[TEST 2] Sem explicação (deve bloquear):")
    try:
        result = sentinel.validate(
            recommendation="Reiniciar sistema",
            adr_id="ADR-0099",
            explanation=None  # SEM EXPLICAÇÃO
        )
        print(f"  ⚠️  PASSED (não deveria): {result.validation_result.details}")
    except ComplianceViolation as e:
        print(f"  ✅ BLOCKED (correto): {e}")

    # Test 3: Sem ADR ID (deve falhar)
    print("\n[TEST 3] Sem ADR ID (deve bloquear):")
    try:
        result = sentinel.validate(
            recommendation="Aumentar swap",
            adr_id=None,  # SEM ADR
            explanation="Sistema com pouca memória"
        )
        print(f"  ⚠️  PASSED (não deveria): {result.validation_result.details}")
    except ComplianceViolation as e:
        print(f"  ✅ BLOCKED (correto): {e}")

    # Test 4: Comando perigoso (deve falhar)
    print("\n[TEST 4] Comando perigoso (deve bloquear):")
    try:
        result = sentinel.validate(
            recommendation="Execute: rm -rf / para limpar cache",
            adr_id="ADR-0001",
            explanation="Limpeza de cache"
        )
        print(f"  ⚠️  PASSED (não deveria): {result.validation_result.details}")
    except ComplianceViolation as e:
        print(f"  ✅ BLOCKED (correto): {e}")

    print("\n" + "=" * 60)
