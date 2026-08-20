#!/usr/bin/env python3
"""
JUDGE API - Endpoint para julgar bundles do AI-OS-Agent

Integrado com Neotron Compliance Framework:
- SENTINEL: Validação de compliance para recomendações
- ORACLE: Explainability para ADRs recomendados
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from phantom.providers import LocalImmutableBucketProvider, get_storage_provider

logger = logging.getLogger("judge_api")

# Importar Neotron integration
try:
    from phantom.neotron.oracle_explainer import OracleExplainer
    from phantom.neotron.sentinel_integration import PhantomSentinel
    NEOTRON_INTEGRATION_AVAILABLE = True
    logger.info("Neotron integration loaded successfully")
except ImportError as e:
    logger.warning(f"Neotron integration not available: {e}")
    NEOTRON_INTEGRATION_AVAILABLE = False
    PhantomSentinel = None  # type: ignore
    OracleExplainer = None  # type: ignore

# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════


class CPUMetrics(BaseModel):
    usage_percent: float
    cores: list[float] = Field(default_factory=list)


class MemoryMetrics(BaseModel):
    total_bytes: int
    used_bytes: int
    usage_percent: float


class ThermalMetrics(BaseModel):
    max_temp_celsius: float
    avg_temp_celsius: float


class SystemMetrics(BaseModel):
    cpu: CPUMetrics
    memory: MemoryMetrics
    thermal: ThermalMetrics


class Alert(BaseModel):
    timestamp: int
    severity: str  # "Info", "Warning", "Critical"
    category: str  # "Thermal", "Memory", "Disk", etc.
    message: str
    details: str | None = None


class LogEntry(BaseModel):
    timestamp: int
    priority: str
    unit: str | None = None
    message: str


class PhantomGateBundle(BaseModel):
    timestamp: int
    hostname: str | None = None
    metrics: SystemMetrics
    alerts: list[Alert]
    logs: list[LogEntry]


class PhantomGateResponse(BaseModel):
    severity: str  # "info", "warning", "critical"
    insights: list[str]
    relevant_adrs: list[str]
    recommendations: list[str]
    bundle_file: str
    bundle_dir: str = "/tmp/phantom-bundles"
    notes: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════════════════════════

DEFAULT_BUNDLE_STORAGE = Path.home() / ".phantom" / "buckets" / "phantom-bundles"
storage_provider = get_storage_provider(base_dir=DEFAULT_BUNDLE_STORAGE)


def save_bundle(bundle: PhantomGateBundle) -> tuple[str, str]:
    """Salvar bundle no storage provider imutável e retornar (file_identifier, directory_or_bucket)"""
    key = f"bundle-{bundle.timestamp}.json"
    content_str = json.dumps(bundle.dict(), indent=2)

    try:
        saved_key = storage_provider.put(content_str, key=key)
    except FileExistsError:
        saved_key = key

    if isinstance(storage_provider, LocalImmutableBucketProvider):
        filepath = storage_provider._safe_path(saved_key)
        return str(filepath), str(storage_provider.base_dir)
    elif hasattr(storage_provider, "bucket_name"):
        prefix = "gs" if "GCS" in storage_provider.__class__.__name__ else "s3"
        return saved_key, f"{prefix}://{storage_provider.bucket_name}"
    else:
        return saved_key, "immutable-storage"


# ═══════════════════════════════════════════════════════════════
# ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════


class JudgmentEngine:
    """Engine para julgar bundles baseado em métricas e knowledge base"""

    def __init__(self, knowledge_base_path: str | None = None):
        self.knowledge_base_path = knowledge_base_path
        self.cerebro_rag = None
        self.sentinel = None
        self.oracle = None

        # Tentar inicializar Cerebro RAG
        if knowledge_base_path:
            self._init_cerebro_rag()

        # Inicializar Neotron components
        self._init_neotron_components()

    def _init_cerebro_rag(self) -> None:
        """Inicializar Vector Store (lazy)"""
        try:
            from phantom.rag.cortex_embeddings import EmbeddingGenerator
            from phantom.rag.vectors import create_vector_store

            # Inicializar gerador de embeddings e vector store
            self.embedding_gen = EmbeddingGenerator()
            self.vector_store = create_vector_store(embedding_dim=384, backend="auto")

            # Carregar dados do Knowledge Base se disponível
            if self.knowledge_base_path and Path(self.knowledge_base_path).exists():
                with open(self.knowledge_base_path) as f:
                    kb_data = json.load(f)
                    decisions = kb_data.get("decisions", [])
                    if decisions:
                        texts = [
                            f"{d['title']} {d.get('summary', '')}" for d in decisions
                        ]
                        metadata = [
                            {"id": d["id"], "title": d["title"]} for d in decisions
                        ]

                        logger.info(f"Indexing {len(texts)} ADRs...")
                        embeddings = self.embedding_gen.encode(texts)
                        self.vector_store.add(embeddings, texts, metadata)

            logger.info("RAG Engine initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize RAG: {e}")
            self.vector_store = None

    def _init_neotron_components(self) -> None:
        """Inicializar SENTINEL e ORACLE"""
        if not NEOTRON_INTEGRATION_AVAILABLE:
            logger.warning("Neotron integration not available - compliance checks disabled")
            return

        try:
            # Inicializar SENTINEL para compliance validation
            self.sentinel = PhantomSentinel()  # type: ignore
            logger.info("SENTINEL compliance engine initialized")

            # Inicializar ORACLE para explainability
            self.oracle = OracleExplainer()  # type: ignore
            logger.info("ORACLE explainer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Neotron components: {e}")
            self.sentinel = None
            self.oracle = None

    def judge(self, bundle: PhantomGateBundle) -> PhantomGateResponse:
        """Julgar bundle e retornar análise"""

        insights: list[str] = []
        recommendations: list[str] = []
        relevant_adrs: list[str] = []
        severity = "info"
        notes: list[str] = []

        # 1. Análise de métricas
        if bundle.metrics.thermal.max_temp_celsius > 75:
            severity = "warning"
            insights.append(
                f"Temperatura elevada detectada: {bundle.metrics.thermal.max_temp_celsius:.1f}°C"
            )
            recommendations.append("Verificar ventilação do sistema")
            recommendations.append("Considerar reduzir carga de trabalho")

        if bundle.metrics.memory.usage_percent > 85:
            severity = "warning" if severity == "info" else severity
            insights.append(
                f"Uso de memória crítico: {bundle.metrics.memory.usage_percent:.1f}%"
            )
            recommendations.append("Identificar processos com alto consumo de memória")
            recommendations.append("Considerar aumentar swap ou RAM")

        if bundle.metrics.cpu.usage_percent > 90:
            severity = "warning" if severity == "info" else severity
            insights.append(
                f"CPU em uso intenso: {bundle.metrics.cpu.usage_percent:.1f}%"
            )
            recommendations.append("Revisar processos em execução")

        # 2. Análise de alertas
        critical_alerts = [a for a in bundle.alerts if a.severity == "Critical"]
        if critical_alerts:
            severity = "critical"
            insights.append(f"{len(critical_alerts)} alertas críticos detectados")

        # 3. Consultar knowledge base via RAG
        adr_results = []  # Para ORACLE processing
        if getattr(self, "vector_store", None) and bundle.alerts:
            # Montar query semântica baseada nos alertas
            alert_messages = [a.message for a in bundle.alerts]
            query_text = f"System alerts: {', '.join(alert_messages)}"

            try:
                # Gerar embedding da query
                query_emb = self.embedding_gen.encode_single(query_text)

                # Buscar no Vector Store
                results = self.vector_store.search(query_emb, top_k=3)

                for result in results:
                    if result.score > 0.3:  # Threshold
                        meta = result.metadata
                        adr_id = meta.get("id", "UNKNOWN")
                        adr_title = meta.get("title", "Untitled")

                        relevant_adrs.append(adr_id)
                        notes.append(
                            f"🧠 RAG Match ({result.score:.2f}): {adr_title}"
                        )

                        # Guardar para ORACLE
                        adr_results.append({
                            "id": adr_id,
                            "title": adr_title,
                            "score": float(result.score),
                            "text": result.text
                        })

            except Exception as e:
                logger.error(f"RAG query failed: {e}")

        # 3.5. Gerar explicações com ORACLE
        if self.oracle and adr_results:
            try:
                metrics_dict = {
                    "cpu": {
                        "usage_percent": bundle.metrics.cpu.usage_percent
                    },
                    "memory": {
                        "usage_percent": bundle.metrics.memory.usage_percent
                    },
                    "thermal": {
                        "max_temp_celsius": bundle.metrics.thermal.max_temp_celsius,
                        "avg_temp_celsius": bundle.metrics.thermal.avg_temp_celsius
                    }
                }

                alerts_dict = [
                    {
                        "severity": a.severity,
                        "category": a.category,
                        "message": a.message
                    }
                    for a in bundle.alerts
                ]

                explanations = self.oracle.explain_multiple(
                    adr_results, metrics_dict, alerts_dict
                )

                for exp in explanations:
                    notes.append(
                        f"⚡ ORACLE Explanation ({exp.confidence:.2f}): "
                        f"{exp.explanation[:150]}..."
                    )

                    # Adicionar recommendation com explicação
                    rec_text = f"Aplicar {exp.adr_id}: {exp.adr_title}"

                    # Validar com SENTINEL antes de adicionar
                    if self.sentinel:
                        try:
                            validated = self.sentinel.validate(
                                recommendation=rec_text,
                                adr_id=exp.adr_id,
                                explanation=exp.explanation,
                                model_name="phantom-cerebro-rag"
                            )

                            if validated.validation_result.passed:
                                recommendations.append(rec_text)
                                notes.append(
                                    f"✅ SENTINEL: Compliance validated for {exp.adr_id}"
                                )
                            else:
                                notes.append(
                                    f"⚠️ SENTINEL: Compliance check failed for {exp.adr_id}: "
                                    f"{validated.validation_result.details}"
                                )

                        except Exception as e:
                            logger.error(f"SENTINEL validation failed: {e}")
                            # Add anyway com warning
                            recommendations.append(rec_text)
                            notes.append(f"⚠️ SENTINEL: Validation error - {str(e)}")
                    else:
                        # Sem SENTINEL, adiciona direto
                        recommendations.append(rec_text)

            except Exception as e:
                logger.error(f"ORACLE/SENTINEL processing failed: {e}")

        # 4. Salvar bundle
        bundle_file, bundle_dir = save_bundle(bundle)

        return PhantomGateResponse(
            severity=severity,
            insights=insights,
            relevant_adrs=list(set(relevant_adrs))[:5],  # Top 5
            recommendations=recommendations,
            bundle_file=bundle_file,
            bundle_dir=bundle_dir,
            notes=notes,
        )


# ═══════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════

_judgment_engine: JudgmentEngine | None = None


def get_judgment_engine() -> JudgmentEngine:
    """Get singleton judgment engine"""
    global _judgment_engine

    if _judgment_engine is None:
        # Tentar localizar knowledge base do ADR-Ledger
        kb_path = "/home/kernelcore/arch/adr-ledger/knowledge/knowledge_base.json"
        _judgment_engine = JudgmentEngine(knowledge_base_path=kb_path)

    return _judgment_engine
