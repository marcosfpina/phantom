#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║  ███████╗██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗                       ║
║  ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝                       ║
║  ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗                         ║
║  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝                         ║
║  ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗                       ║
║  ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝                       ║
║  ════════════════════════════════════════════════════════════════════════════════║
║  Sentiment & Pattern Extraction for Contextual Text Research Engine v1.0        ║
║  ────────────────────────────────────────────────────────────────────────────────║
║  Multi-dimensional sentiment analysis with domain-specific taxonomy mapping      ║
║  Knowledge graph extraction • Trend detection • Insight generation               ║
╚══════════════════════════════════════════════════════════════════════════════════╝

Architecture:
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SPECTRE PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │  INGEST  │──▶│  PARSE   │──▶│ ANALYZE  │──▶│  ENRICH  │──▶│  OUTPUT  │      │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘      │
│       │              │              │              │              │              │
│       ▼              ▼              ▼              ▼              ▼              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │ File     │   │ Markdown │   │ Multi-   │   │ Knowledge│   │ Reports  │      │
│  │ Discovery│   │ AST      │   │ Sentiment│   │ Graph    │   │ Insights │      │
│  │ Metadata │   │ Sections │   │ Topics   │   │ Entities │   │ Trends   │      │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"
CODENAME = "SPECTRE"


# ANSI Colors
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    WHITE = "\033[0;37m"

    # Semantic
    SUCCESS = GREEN
    WARNING = YELLOW
    ERROR = RED
    INFO = CYAN
    DEBUG = MAGENTA
    HIGHLIGHT = BOLD + CYAN


# ══════════════════════════════════════════════════════════════════════════════════
# LEXICONS - Domain-Specific Sentiment Dictionaries
# ══════════════════════════════════════════════════════════════════════════════════


class SentimentLexicons:
    """
    Multi-dimensional sentiment lexicons for blockchain/Web3 domain.
    Each word has scores across different sentiment dimensions.
    """

    # Technical Confidence Lexicon
    # Measures technical certainty/uncertainty in statements
    TECHNICAL_CONFIDENCE = {
        # High confidence (positive)
        "proven": 0.8,
        "verified": 0.9,
        "audited": 0.85,
        "secure": 0.7,
        "tested": 0.6,
        "validated": 0.75,
        "confirmed": 0.7,
        "stable": 0.6,
        "reliable": 0.65,
        "robust": 0.7,
        "efficient": 0.5,
        "optimized": 0.6,
        "scalable": 0.55,
        "production-ready": 0.8,
        "battle-tested": 0.85,
        "trustless": 0.7,
        "immutable": 0.75,
        "decentralized": 0.6,
        "transparent": 0.65,
        "permissionless": 0.6,
        "censorship-resistant": 0.7,
        "formally verified": 0.95,
        "mathematically proven": 0.9,
        # Low confidence (negative)
        "experimental": -0.4,
        "untested": -0.7,
        "vulnerable": -0.8,
        "risky": -0.6,
        "unstable": -0.7,
        "buggy": -0.75,
        "flawed": -0.7,
        "deprecated": -0.5,
        "legacy": -0.3,
        "centralized": -0.4,
        "unaudited": -0.8,
        "alpha": -0.5,
        "beta": -0.3,
        "poc": -0.4,
        "proof-of-concept": -0.4,
        "hack": -0.85,
        "exploit": -0.9,
        "rug": -0.95,
        "scam": -0.95,
        "ponzi": -0.95,
        "honeypot": -0.9,
    }

    # Market Sentiment Lexicon
    # Measures bullish/bearish sentiment
    MARKET_SENTIMENT = {
        # Bullish (positive)
        "bullish": 0.9,
        "moon": 0.8,
        "pump": 0.6,
        "rally": 0.7,
        "breakout": 0.65,
        "surge": 0.7,
        "soar": 0.75,
        "gain": 0.5,
        "profit": 0.6,
        "ath": 0.8,
        "all-time-high": 0.8,
        "adoption": 0.6,
        "growth": 0.5,
        "accumulate": 0.55,
        "hodl": 0.6,
        "diamond hands": 0.7,
        "buy": 0.4,
        "long": 0.5,
        "undervalued": 0.6,
        "opportunity": 0.5,
        "institutional": 0.55,
        "mainstream": 0.5,
        "mass adoption": 0.7,
        "tvl": 0.4,
        "volume": 0.3,
        "liquidity": 0.35,
        # Bearish (negative)
        "bearish": -0.9,
        "dump": -0.7,
        "crash": -0.85,
        "plunge": -0.8,
        "drop": -0.5,
        "fall": -0.5,
        "decline": -0.55,
        "loss": -0.6,
        "sell": -0.4,
        "short": -0.5,
        "overvalued": -0.6,
        "bubble": -0.7,
        "correction": -0.4,
        "capitulation": -0.8,
        "fear": -0.65,
        "panic": -0.75,
        "fud": -0.6,
        "rug pull": -0.95,
        "exit scam": -0.95,
        "dead": -0.8,
        "worthless": -0.85,
        "bleeding": -0.7,
    }

    # Community/Social Sentiment
    # Measures community health and engagement
    COMMUNITY_SENTIMENT = {
        # Positive community signals
        "community": 0.4,
        "ecosystem": 0.45,
        "collaborative": 0.6,
        "open-source": 0.55,
        "transparent": 0.5,
        "inclusive": 0.5,
        "active": 0.45,
        "growing": 0.5,
        "vibrant": 0.6,
        "engaged": 0.55,
        "supportive": 0.6,
        "helpful": 0.55,
        "welcoming": 0.5,
        "innovative": 0.6,
        "pioneering": 0.65,
        "groundbreaking": 0.7,
        "revolutionary": 0.65,
        "disruptive": 0.5,
        "cutting-edge": 0.55,
        "governance": 0.4,
        "voting": 0.35,
        "proposal": 0.3,
        "contribution": 0.5,
        "developer": 0.4,
        "builder": 0.5,
        # Negative community signals
        "toxic": -0.8,
        "drama": -0.6,
        "conflict": -0.55,
        "controversy": -0.5,
        "abandoned": -0.75,
        "dead project": -0.85,
        "ghost chain": -0.8,
        "inactive": -0.6,
        "declining": -0.55,
        "exodus": -0.7,
        "centralized control": -0.65,
        "insider": -0.5,
        "whale manipulation": -0.7,
        "bot": -0.4,
        "fake": -0.7,
        "shill": -0.6,
        "spam": -0.5,
    }

    # Innovation/Progress Sentiment
    INNOVATION_SENTIMENT = {
        # Positive innovation
        "breakthrough": 0.8,
        "novel": 0.6,
        "innovative": 0.65,
        "revolutionary": 0.7,
        "cutting-edge": 0.6,
        "state-of-the-art": 0.65,
        "next-generation": 0.55,
        "advanced": 0.5,
        "sophisticated": 0.5,
        "elegant": 0.55,
        "efficient": 0.5,
        "optimized": 0.5,
        "upgrade": 0.45,
        "improvement": 0.4,
        "enhancement": 0.4,
        "milestone": 0.5,
        "achievement": 0.55,
        "success": 0.6,
        "launch": 0.4,
        "release": 0.35,
        "deployment": 0.35,
        "mainnet": 0.5,
        "testnet": 0.3,
        # Negative/stagnation
        "outdated": -0.5,
        "obsolete": -0.6,
        "stagnant": -0.55,
        "delayed": -0.4,
        "postponed": -0.35,
        "cancelled": -0.7,
        "failed": -0.75,
        "broken": -0.7,
        "bug": -0.5,
        "issue": -0.3,
        "problem": -0.35,
        "challenge": -0.2,
        "limitation": -0.3,
        "bottleneck": -0.4,
        "blocker": -0.45,
        "regression": -0.55,
    }

    # Risk Assessment Lexicon
    RISK_SENTIMENT = {
        # Low risk indicators
        "safe": 0.7,
        "secure": 0.65,
        "protected": 0.6,
        "insured": 0.55,
        "diversified": 0.5,
        "hedged": 0.45,
        "conservative": 0.4,
        "established": 0.5,
        "reputable": 0.55,
        "trusted": 0.6,
        "compliant": 0.5,
        "regulated": 0.45,
        "licensed": 0.5,
        "backed": 0.4,
        "collateralized": 0.45,
        "over-collateralized": 0.55,
        # High risk indicators
        "risky": -0.6,
        "dangerous": -0.7,
        "unsafe": -0.65,
        "unregulated": -0.4,
        "unlicensed": -0.45,
        "anonymous": -0.3,
        "leverage": -0.4,
        "margin": -0.35,
        "liquidation": -0.6,
        "impermanent loss": -0.5,
        "slippage": -0.35,
        "frontrunning": -0.6,
        "mev": -0.4,
        "flashloan attack": -0.8,
        "oracle manipulation": -0.75,
        "smart contract risk": -0.5,
        "protocol risk": -0.45,
        "counterparty risk": -0.5,
        "systemic risk": -0.6,
    }

    @classmethod
    def get_all_lexicons(cls) -> dict[str, dict[str, float]]:
        """Return all lexicons as a dictionary"""
        return {
            "technical": cls.TECHNICAL_CONFIDENCE,
            "market": cls.MARKET_SENTIMENT,
            "community": cls.COMMUNITY_SENTIMENT,
            "innovation": cls.INNOVATION_SENTIMENT,
            "risk": cls.RISK_SENTIMENT,
        }


# ══════════════════════════════════════════════════════════════════════════════════
# VADER-STYLE SENTIMENT ANALYZER (Custom Implementation)
# ══════════════════════════════════════════════════════════════════════════════════


class VADERAnalyzer:
    """
    Valence Aware Dictionary and sEntiment Reasoner
    Custom implementation with blockchain domain adaptation
    """

    # Booster/dampener words
    BOOSTERS = {
        "very": 0.293,
        "really": 0.288,
        "extremely": 0.375,
        "absolutely": 0.350,
        "totally": 0.300,
        "completely": 0.320,
        "highly": 0.280,
        "incredibly": 0.350,
        "significantly": 0.270,
        "particularly": 0.240,
        "especially": 0.260,
        "exceptionally": 0.340,
        "remarkably": 0.300,
        "substantially": 0.270,
    }

    DAMPENERS = {
        "slightly": -0.200,
        "somewhat": -0.180,
        "barely": -0.250,
        "hardly": -0.280,
        "marginally": -0.220,
        "partially": -0.180,
        "kind of": -0.200,
        "sort of": -0.200,
        "a bit": -0.180,
        "a little": -0.180,
        "relatively": -0.150,
    }

    # Negation words
    NEGATIONS = {
        "not",
        "n't",
        "never",
        "no",
        "none",
        "nobody",
        "nothing",
        "neither",
        "nowhere",
        "hardly",
        "barely",
        "scarcely",
        "without",
        "lack",
        "lacking",
        "lacks",
        "failed",
        "fail",
    }

    # Punctuation amplifiers
    PUNCT_EMPHASIS = {
        "!": 0.292,
        "!!": 0.584,
        "!!!": 0.876,
        "?!": 0.400,
        "!?": 0.400,
    }

    # ALL CAPS amplifier
    CAPS_INCR = 0.733

    def __init__(self, lexicon: dict[str, float]):
        self.lexicon = lexicon
        self._word_cache: dict[str, float] = {}

    def _normalize(self, score: float, alpha: float = 15) -> float:
        """Normalize score to [-1, 1] range using VADER's normalization"""
        return score / math.sqrt((score * score) + alpha)

    def _is_negated(self, tokens: list[str], idx: int, window: int = 3) -> bool:
        """Check if word at idx is negated within window"""
        start = max(0, idx - window)
        return any(tokens[i].lower() in self.NEGATIONS for i in range(start, idx))

    def _get_booster_score(self, word: str) -> float:
        """Get booster/dampener score for word"""
        word_lower = word.lower()
        if word_lower in self.BOOSTERS:
            return self.BOOSTERS[word_lower]
        if word_lower in self.DAMPENERS:
            return self.DAMPENERS[word_lower]
        return 0.0

    def _is_all_caps(self, word: str) -> bool:
        """Check if word is ALL CAPS (and not just short)"""
        return word.isupper() and len(word) > 1

    def analyze(self, text: str) -> dict[str, float]:
        """
        Analyze text and return sentiment scores.
        Returns: {pos, neg, neu, compound}
        """
        # Tokenize
        tokens = self._tokenize(text)

        if not tokens:
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}

        sentiments = []

        for i, token in enumerate(tokens):
            token_lower = token.lower()

            # Skip if not in lexicon
            if token_lower not in self.lexicon:
                continue

            valence = self.lexicon[token_lower]

            # Check for negation
            if self._is_negated(tokens, i):
                valence *= -0.74  # VADER negation coefficient

            # Check for boosters/dampeners in preceding words
            if i > 0:
                booster = self._get_booster_score(tokens[i - 1])
                if valence > 0:
                    valence += booster
                elif valence < 0:
                    valence -= booster

            # ALL CAPS emphasis
            if self._is_all_caps(token):
                if valence > 0:
                    valence += self.CAPS_INCR
                elif valence < 0:
                    valence -= self.CAPS_INCR

            sentiments.append(valence)

        # Calculate scores
        if not sentiments:
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}

        # Sum and normalize compound
        sum_s = sum(sentiments)

        # Punctuation emphasis
        for punct, incr in self.PUNCT_EMPHASIS.items():
            if punct in text:
                if sum_s > 0:
                    sum_s += incr
                elif sum_s < 0:
                    sum_s -= incr

        compound = self._normalize(sum_s)

        # Calculate pos/neg/neu proportions
        pos_sum = sum(s for s in sentiments if s > 0)
        neg_sum = sum(abs(s) for s in sentiments if s < 0)
        neu_count = len(tokens) - len(sentiments)

        total = pos_sum + neg_sum + neu_count
        if total == 0:
            total = 1

        pos = pos_sum / total
        neg = neg_sum / total
        neu = neu_count / total

        # Normalize to sum to 1
        total_pnn = pos + neg + neu
        if total_pnn > 0:
            pos /= total_pnn
            neg /= total_pnn
            neu /= total_pnn

        return {
            "pos": round(pos, 4),
            "neg": round(neg, 4),
            "neu": round(neu, 4),
            "compound": round(compound, 4),
        }

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer"""
        # Handle contractions and special chars
        text = re.sub(r"([a-zA-Z])'([a-zA-Z])", r"\1'\2", text)
        # Split on whitespace and punctuation (keeping punctuation)
        tokens = re.findall(r"\b\w+\b|[!?]+", text)
        return tokens


# ══════════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════════


class SentimentDimension(Enum):
    """Multi-dimensional sentiment classification"""

    TECHNICAL = "technical"
    MARKET = "market"
    COMMUNITY = "community"
    INNOVATION = "innovation"
    RISK = "risk"
    OVERALL = "overall"


class SentimentLabel(Enum):
    """Categorical sentiment labels"""

    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"

    @classmethod
    def from_compound(cls, compound: float) -> SentimentLabel:
        """Convert compound score to label"""
        if compound >= 0.5:
            return cls.VERY_POSITIVE
        elif compound >= 0.1:
            return cls.POSITIVE
        elif compound <= -0.5:
            return cls.VERY_NEGATIVE
        elif compound <= -0.1:
            return cls.NEGATIVE
        else:
            return cls.NEUTRAL


@dataclass
class SentimentScore:
    """Sentiment analysis result for a single dimension"""

    dimension: str
    compound: float
    positive: float
    negative: float
    neutral: float
    label: str
    confidence: float
    word_count: int
    matched_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MultiDimensionalSentiment:
    """Complete multi-dimensional sentiment analysis"""

    technical: SentimentScore
    market: SentimentScore
    community: SentimentScore
    innovation: SentimentScore
    risk: SentimentScore
    overall: SentimentScore

    # Aggregate metrics
    dominant_dimension: str = ""
    sentiment_divergence: float = 0.0  # How much dimensions disagree
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "technical": self.technical.to_dict(),
            "market": self.market.to_dict(),
            "community": self.community.to_dict(),
            "innovation": self.innovation.to_dict(),
            "risk": self.risk.to_dict(),
            "overall": self.overall.to_dict(),
            "dominant_dimension": self.dominant_dimension,
            "sentiment_divergence": self.sentiment_divergence,
            "confidence": self.confidence,
        }


@dataclass
class TopicMatch:
    """Topic/taxonomy match result"""

    term: str
    category: str
    frequency: int
    contexts: list[str] = field(default_factory=list)  # Surrounding text snippets


@dataclass
class Entity:
    """Extracted entity"""

    text: str
    entity_type: str  # PROTOCOL, TOKEN, PERSON, ORG, CONCEPT
    frequency: int
    sentiment_association: float  # Average sentiment when mentioned
    co_occurrences: list[str] = field(default_factory=list)


@dataclass
class Section:
    """Markdown section"""

    level: int
    title: str
    content: str
    start_line: int
    end_line: int
    word_count: int
    sentiment: SentimentScore | None = None


@dataclass
class DocumentAnalysis:
    """Complete document analysis result"""

    # Metadata
    filepath: str
    filename: str
    file_hash: str
    file_size: int
    word_count: int
    line_count: int
    analyzed_at: str

    # Content structure
    title: str
    sections: list[Section] = field(default_factory=list)

    # Sentiment
    sentiment: MultiDimensionalSentiment | None = None
    section_sentiments: list[dict] = field(default_factory=list)

    # Topics & Entities
    topics: list[TopicMatch] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)

    # Keywords & Phrases
    keywords: list[tuple[str, float]] = field(default_factory=list)
    key_phrases: list[str] = field(default_factory=list)

    # Relationships
    topic_sentiment_correlation: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.sentiment:
            d["sentiment"] = self.sentiment.to_dict()
        return d


@dataclass
class CorpusInsights:
    """Insights extracted from entire corpus"""

    # Overview
    total_documents: int
    total_words: int
    analyzed_at: str

    # Sentiment distributions
    sentiment_distribution: dict[str, dict[str, int]] = field(default_factory=dict)
    avg_sentiment_by_dimension: dict[str, float] = field(default_factory=dict)
    sentiment_trend: list[dict] = field(default_factory=list)  # Over documents

    # Topic analysis
    topic_frequency: dict[str, int] = field(default_factory=dict)
    topic_sentiment: dict[str, float] = field(default_factory=dict)
    topic_co_occurrence: dict[str, list[str]] = field(default_factory=dict)

    # Entity analysis
    top_entities: list[Entity] = field(default_factory=list)
    entity_network: dict[str, list[str]] = field(default_factory=dict)

    # Key insights (generated)
    key_findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["top_entities"] = [asdict(e) for e in self.top_entities]
        return d


# ══════════════════════════════════════════════════════════════════════════════════
# TAXONOMY MANAGER
# ══════════════════════════════════════════════════════════════════════════════════


class TaxonomyManager:
    """
    Manages domain taxonomy for topic classification.
    Builds hierarchical category structure from flat term list.
    """

    # Category mappings (term patterns -> category)
    CATEGORY_PATTERNS = {
        "blockchain_core": [
            "blockchain",
            "distributed ledger",
            "dlt",
            "consensus",
            "proof-of-stake",
            "proof-of-authority",
            "byzantine fault",
            "sharding",
            "state channels",
            "rollups",
        ],
        "smart_contracts": [
            "smart contract",
            "teal",
            "pyteal",
            "solidity",
            "vyper",
            "formal verification",
            "audit",
            "security analysis",
        ],
        "defi": [
            "defi",
            "decentralized finance",
            "dex",
            "amm",
            "liquidity",
            "yield",
            "staking",
            "lending",
            "borrowing",
            "stablecoin",
            "tvl",
            "impermanent loss",
        ],
        "tokens_nfts": [
            "token",
            "nft",
            "tokenization",
            "erc",
            "arc",
            "fungible",
            "non-fungible",
            "collectible",
            "badge",
        ],
        "governance": [
            "dao",
            "governance",
            "voting",
            "proposal",
            "treasury",
            "decentralized governance",
            "token holder",
        ],
        "scalability": [
            "scalability",
            "layer-2",
            "l2",
            "rollup",
            "zk-snark",
            "zk-stark",
            "optimistic",
            "validium",
            "sidechain",
        ],
        "security": [
            "security",
            "audit",
            "vulnerability",
            "exploit",
            "hack",
            "bug bounty",
            "penetration",
            "threat",
        ],
        "development": [
            "sdk",
            "api",
            "developer",
            "ide",
            "debugging",
            "testing",
            "deployment",
            "framework",
            "tool",
        ],
        "infrastructure": [
            "node",
            "rpc",
            "infrastructure",
            "indexer",
            "explorer",
            "monitoring",
            "analytics",
        ],
        "ecosystem": [
            "ecosystem",
            "community",
            "partnership",
            "integration",
            "adoption",
            "enterprise",
            "institution",
        ],
        "privacy": [
            "privacy",
            "zero-knowledge",
            "zk",
            "confidential",
            "anonymous",
            "private transaction",
        ],
        "interoperability": [
            "interoperability",
            "cross-chain",
            "bridge",
            "atomic swap",
            "wrapped",
            "pegged",
        ],
        "storage": [
            "storage",
            "ipfs",
            "arweave",
            "filecoin",
            "decentralized storage",
        ],
        "identity": [
            "identity",
            "did",
            "ssi",
            "credential",
            "verification",
            "kyc",
            "aml",
        ],
        "financial": [
            "financial",
            "fintech",
            "regtech",
            "compliance",
            "regulation",
            "regulatory",
            "legal",
        ],
    }

    def __init__(self):
        self.terms: set[str] = set()
        self.term_to_category: dict[str, str] = {}
        self.category_terms: dict[str, set[str]] = defaultdict(set)
        self.term_patterns: dict[str, re.Pattern] = {}

    def load_taxonomy(self, terms: list[str]):
        """Load and categorize taxonomy terms"""
        for term in terms:
            term_clean = term.strip().lower()
            if not term_clean:
                continue

            self.terms.add(term_clean)

            # Categorize term
            category = self._categorize_term(term_clean)
            self.term_to_category[term_clean] = category
            self.category_terms[category].add(term_clean)

            # Build regex pattern for term
            # Handle multi-word terms and variations
            pattern = self._build_term_pattern(term_clean)
            self.term_patterns[term_clean] = pattern

    def _categorize_term(self, term: str) -> str:
        """Determine category for a term"""
        term_lower = term.lower()

        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in term_lower or term_lower in pattern:
                    return category

        # Default categorization by keyword heuristics
        if any(kw in term_lower for kw in ["contract", "code", "function"]):
            return "smart_contracts"
        if any(kw in term_lower for kw in ["token", "coin", "asset"]):
            return "tokens_nfts"
        if any(kw in term_lower for kw in ["protocol", "network", "chain"]):
            return "blockchain_core"

        return "general"

    def _build_term_pattern(self, term: str) -> re.Pattern:
        """Build regex pattern for term matching"""
        # Escape special chars and handle variations
        escaped = re.escape(term)

        # Allow for hyphen/space/underscore variations
        flexible = escaped.replace(r"\ ", r"[\s_-]?")
        flexible = flexible.replace(r"\-", r"[\s_-]?")
        flexible = flexible.replace(r"\_", r"[\s_-]?")

        # Word boundaries
        pattern = rf"\b{flexible}\b"

        return re.compile(pattern, re.IGNORECASE)

    def match_terms(self, text: str) -> list[TopicMatch]:
        """Find all taxonomy terms in text"""
        matches = []
        text.lower()

        for term, pattern in self.term_patterns.items():
            found = pattern.findall(text)
            if found:
                # Get context snippets
                contexts = []
                for match in pattern.finditer(text):
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    contexts.append(f"...{context}...")

                matches.append(
                    TopicMatch(
                        term=term,
                        category=self.term_to_category.get(term, "general"),
                        frequency=len(found),
                        contexts=contexts[:3],  # Keep top 3 contexts
                    )
                )

        # Sort by frequency
        matches.sort(key=lambda x: x.frequency, reverse=True)
        return matches

    def get_categories(self) -> dict[str, set[str]]:
        """Get all categories and their terms"""
        return dict(self.category_terms)


# ══════════════════════════════════════════════════════════════════════════════════
# MARKDOWN PARSER
# ══════════════════════════════════════════════════════════════════════════════════


class MarkdownParser:
    """
    Parse markdown files into structured sections.
    Extracts headers, content, code blocks, links, etc.
    """

    # Regex patterns
    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
    LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
    ITALIC_PATTERN = re.compile(r"\*([^*]+)\*")
    LIST_ITEM_PATTERN = re.compile(r"^[\s]*[-*+]\s+(.+)$", re.MULTILINE)

    def __init__(self):
        pass

    def parse(self, content: str, filepath: str = "") -> tuple[str, list[Section]]:
        """
        Parse markdown content into structured sections.
        Returns: (title, sections)
        """
        lines = content.split("\n")
        sections: list[Section] = []

        # Extract title (first H1 or filename)
        title = self._extract_title(content, filepath)

        # Find all headers and their positions
        headers = []
        for i, line in enumerate(lines):
            match = self.HEADER_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                header_text = match.group(2).strip()
                headers.append((i, level, header_text))

        # Build sections
        if not headers:
            # No headers - treat entire content as one section
            clean_content = self._clean_content(content)
            sections.append(
                Section(
                    level=0,
                    title="Content",
                    content=clean_content,
                    start_line=0,
                    end_line=len(lines) - 1,
                    word_count=len(clean_content.split()),
                )
            )
        else:
            for i, (line_num, level, header_text) in enumerate(headers):
                # Determine end of section
                end_line = headers[i + 1][0] - 1 if i + 1 < len(headers) else len(lines) - 1

                # Extract section content
                section_lines = lines[line_num + 1 : end_line + 1]
                section_content = "\n".join(section_lines)
                clean_content = self._clean_content(section_content)

                sections.append(
                    Section(
                        level=level,
                        title=header_text,
                        content=clean_content,
                        start_line=line_num,
                        end_line=end_line,
                        word_count=len(clean_content.split()),
                    )
                )

        return title, sections

    def _extract_title(self, content: str, filepath: str) -> str:
        """Extract document title"""
        # Try to find H1
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Fall back to filename
        if filepath:
            return Path(filepath).stem.replace("-", " ").replace("_", " ").title()

        return "Untitled"

    def _clean_content(self, content: str) -> str:
        """Remove markdown syntax, keeping plain text"""
        text = content

        # Remove code blocks
        text = self.CODE_BLOCK_PATTERN.sub(" ", text)

        # Remove inline code
        text = self.INLINE_CODE_PATTERN.sub(lambda m: m.group(0)[1:-1], text)

        # Remove images
        text = self.IMAGE_PATTERN.sub("", text)

        # Convert links to text
        text = self.LINK_PATTERN.sub(r"\1", text)

        # Remove bold/italic markers
        text = self.BOLD_PATTERN.sub(r"\1", text)
        text = self.ITALIC_PATTERN.sub(r"\1", text)

        # Remove header markers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Remove list markers
        text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    def extract_links(self, content: str) -> list[tuple[str, str]]:
        """Extract all links from content"""
        return self.LINK_PATTERN.findall(content)

    def extract_code_blocks(self, content: str) -> list[str]:
        """Extract all code blocks"""
        return self.CODE_BLOCK_PATTERN.findall(content)


# ══════════════════════════════════════════════════════════════════════════════════
# KEYWORD EXTRACTOR (TF-IDF Style)
# ══════════════════════════════════════════════════════════════════════════════════


class KeywordExtractor:
    """
    Extract keywords using TF-IDF-like scoring.
    Optimized for single-document analysis.
    """

    # Stop words (expanded)
    STOP_WORDS = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "now",
        "here",
        "there",
        "then",
        "once",
        "if",
        "because",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "while",
        "being",
        "having",
        "doing",
        "etc",
        "eg",
        "ie",
        "vs",
        "via",
        "per",
        "de",
        "la",
        "el",
    }

    def __init__(self):
        self.document_frequencies: dict[str, int] = defaultdict(int)
        self.total_documents = 0

    def extract(self, text: str, top_n: int = 20) -> list[tuple[str, float]]:
        """Extract top keywords with scores"""
        # Tokenize and clean
        words = self._tokenize(text)

        if not words:
            return []

        # Calculate term frequency
        tf = Counter(words)
        len(words)

        # Calculate TF-IDF-like scores
        scores = {}
        for word, count in tf.items():
            # TF component (log-normalized)
            tf_score = 1 + math.log(count) if count > 0 else 0

            # IDF component (simulated with word rarity heuristic)
            # Longer words and less common patterns get higher scores
            idf_score = 1 + (len(word) / 10)  # Length bonus

            # Penalize very common words
            if word in self.STOP_WORDS:
                idf_score *= 0.1

            scores[word] = tf_score * idf_score

        # Sort and return top N
        sorted_keywords = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_keywords[:top_n]

    def extract_phrases(self, text: str, top_n: int = 10) -> list[str]:
        """Extract key phrases (bigrams and trigrams)"""
        words = self._tokenize(text)

        if len(words) < 2:
            return []

        # Generate n-grams
        bigrams = [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
        trigrams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]

        # Count and filter
        phrase_counts = Counter(bigrams + trigrams)

        # Filter out phrases with stop words at boundaries
        filtered = {
            phrase: count
            for phrase, count in phrase_counts.items()
            if not any(
                phrase.startswith(sw + " ") or phrase.endswith(" " + sw)
                for sw in self.STOP_WORDS
            )
        }

        # Return top N
        return [phrase for phrase, _ in Counter(filtered).most_common(top_n)]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize and clean text"""
        # Lowercase and extract words
        words = re.findall(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)*\b", text.lower())

        # Filter
        filtered = [w for w in words if len(w) > 2 and w not in self.STOP_WORDS]

        return filtered


# ══════════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════════


class EntityExtractor:
    """
    Extract named entities relevant to blockchain domain.
    Uses pattern-based extraction (no ML dependencies).
    """

    # Known entity patterns
    PROTOCOL_PATTERNS = [
        r"\b(Algorand|Ethereum|Bitcoin|Solana|Cardano|Polkadot|Cosmos|Avalanche)\b",
        r"\b(Uniswap|Aave|Compound|MakerDAO|Curve|Yearn|Synthetix|dYdX)\b",
        r"\b(Chainlink|Band Protocol|API3|Pyth|Flux)\b",
        r"\b(IPFS|Arweave|Filecoin|Storj|Sia)\b",
    ]

    TOKEN_PATTERNS = [
        r"\b(ETH|BTC|SOL|ALGO|ADA|DOT|ATOM|AVAX)\b",
        r"\b(USDT|USDC|DAI|BUSD|FRAX|LUSD)\b",
        r"\$([A-Z]{2,10})\b",  # $TOKEN format
    ]

    PERSON_PATTERNS = [
        r"\b(Vitalik|Satoshi|CZ|SBF)\b",
    ]

    CONCEPT_PATTERNS = [
        r"\b(zero-knowledge|zk-SNARK|zk-STARK|rollup|sharding)\b",
        r"\b(proof-of-stake|proof-of-work|DPoS|PoA)\b",
        r"\b(AMM|DEX|CEX|TVL|APY|APR)\b",
    ]

    def __init__(self):
        self.compiled_patterns = {
            "PROTOCOL": [re.compile(p, re.IGNORECASE) for p in self.PROTOCOL_PATTERNS],
            "TOKEN": [
                re.compile(p) for p in self.TOKEN_PATTERNS
            ],  # Case sensitive for tokens
            "PERSON": [re.compile(p, re.IGNORECASE) for p in self.PERSON_PATTERNS],
            "CONCEPT": [re.compile(p, re.IGNORECASE) for p in self.CONCEPT_PATTERNS],
        }

    def extract(self, text: str) -> list[Entity]:
        """Extract all entities from text"""
        entities: dict[str, Entity] = {}

        for entity_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    entity_text = match.group(0)

                    # Normalize
                    if entity_type == "TOKEN":
                        entity_text = entity_text.upper().lstrip("$")
                    else:
                        entity_text = entity_text.title()

                    key = f"{entity_type}:{entity_text}"

                    if key in entities:
                        entities[key].frequency += 1
                    else:
                        entities[key] = Entity(
                            text=entity_text,
                            entity_type=entity_type,
                            frequency=1,
                            sentiment_association=0.0,
                            co_occurrences=[],
                        )

        return list(entities.values())

    def find_co_occurrences(
        self, entities: list[Entity], text: str, window: int = 100
    ) -> None:
        """Find entity co-occurrences within text window"""
        text.lower()

        for entity in entities:
            # Find positions of this entity
            pattern = re.compile(re.escape(entity.text), re.IGNORECASE)
            positions = [m.start() for m in pattern.finditer(text)]

            # For each position, find nearby entities
            co_occurring = set()
            for pos in positions:
                window_start = max(0, pos - window)
                window_end = min(len(text), pos + window)
                window_text = text[window_start:window_end].lower()

                for other in entities:
                    if other.text != entity.text and other.text.lower() in window_text:
                        co_occurring.add(other.text)

            entity.co_occurrences = list(co_occurring)


# ══════════════════════════════════════════════════════════════════════════════════
# SPECTRE ANALYZER (Main Engine)
# ══════════════════════════════════════════════════════════════════════════════════


class SpectreAnalyzer:
    """
    Main analysis engine combining all components.
    Processes documents through complete pipeline.
    """

    def __init__(self, taxonomy_terms: list[str] = None):
        # Initialize components
        self.taxonomy = TaxonomyManager()
        if taxonomy_terms:
            self.taxonomy.load_taxonomy(taxonomy_terms)

        self.md_parser = MarkdownParser()
        self.keyword_extractor = KeywordExtractor()
        self.entity_extractor = EntityExtractor()

        # Initialize sentiment analyzers for each dimension
        lexicons = SentimentLexicons.get_all_lexicons()
        self.sentiment_analyzers = {
            dim: VADERAnalyzer(lexicon) for dim, lexicon in lexicons.items()
        }

        # Combined lexicon for overall sentiment
        combined_lexicon = {}
        for lexicon in lexicons.values():
            combined_lexicon.update(lexicon)
        self.overall_analyzer = VADERAnalyzer(combined_lexicon)

        # Statistics
        self.documents_analyzed = 0
        self.total_words_processed = 0

    def analyze(self, text: str) -> MultiDimensionalSentiment:
        """Analyze raw text and return multi-dimensional sentiment."""
        word_count = len(text.split())
        sentiment = self._analyze_sentiment(text)
        self.documents_analyzed += 1
        self.total_words_processed += word_count
        return sentiment

    def analyze_document(self, filepath: Path) -> DocumentAnalysis:
        """Analyze a single markdown document"""
        # Read file
        content = filepath.read_text(encoding="utf-8", errors="replace")

        # Compute hash
        file_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Parse markdown
        title, sections = self.md_parser.parse(content, str(filepath))

        # Get full text for analysis
        full_text = " ".join(s.content for s in sections)
        word_count = len(full_text.split())
        line_count = len(content.split("\n"))

        # Multi-dimensional sentiment analysis
        sentiment = self._analyze_sentiment(full_text)

        # Analyze sentiment per section
        section_sentiments = []
        for section in sections:
            if section.word_count > 10:  # Skip very short sections
                section_sent = self._analyze_sentiment(section.content)
                section.sentiment = section_sent.overall
                section_sentiments.append(
                    {
                        "title": section.title,
                        "sentiment": section_sent.overall.to_dict(),
                    }
                )

        # Topic matching
        topics = self.taxonomy.match_terms(full_text)

        # Entity extraction
        entities = self.entity_extractor.extract(full_text)
        self.entity_extractor.find_co_occurrences(entities, full_text)

        # Keyword extraction
        keywords = self.keyword_extractor.extract(full_text)
        key_phrases = self.keyword_extractor.extract_phrases(full_text)

        # Topic-sentiment correlation
        topic_sentiment_corr = self._calculate_topic_sentiment_correlation(
            topics, full_text
        )

        # Build result
        analysis = DocumentAnalysis(
            filepath=str(filepath),
            filename=filepath.name,
            file_hash=file_hash,
            file_size=filepath.stat().st_size,
            word_count=word_count,
            line_count=line_count,
            analyzed_at=datetime.now(UTC).isoformat(),
            title=title,
            sections=sections,
            sentiment=sentiment,
            section_sentiments=section_sentiments,
            topics=topics,
            entities=entities,
            keywords=keywords,
            key_phrases=key_phrases,
            topic_sentiment_correlation=topic_sentiment_corr,
        )

        # Update stats
        self.documents_analyzed += 1
        self.total_words_processed += word_count

        return analysis

    def _analyze_sentiment(self, text: str) -> MultiDimensionalSentiment:
        """Perform multi-dimensional sentiment analysis"""
        results = {}

        # Analyze each dimension
        for dim, analyzer in self.sentiment_analyzers.items():
            scores = analyzer.analyze(text)

            # Find matched terms
            matched = [
                word for word in text.lower().split() if word in analyzer.lexicon
            ]

            results[dim] = SentimentScore(
                dimension=dim,
                compound=scores["compound"],
                positive=scores["pos"],
                negative=scores["neg"],
                neutral=scores["neu"],
                label=SentimentLabel.from_compound(scores["compound"]).value,
                confidence=abs(scores["compound"]),
                word_count=len(text.split()),
                matched_terms=list(set(matched))[:10],
            )

        # Overall sentiment
        overall_scores = self.overall_analyzer.analyze(text)
        results["overall"] = SentimentScore(
            dimension="overall",
            compound=overall_scores["compound"],
            positive=overall_scores["pos"],
            negative=overall_scores["neg"],
            neutral=overall_scores["neu"],
            label=SentimentLabel.from_compound(overall_scores["compound"]).value,
            confidence=abs(overall_scores["compound"]),
            word_count=len(text.split()),
            matched_terms=[],
        )

        # Find dominant dimension
        dimension_scores = {dim: abs(results[dim].compound) for dim in self.sentiment_analyzers}
        dominant = max(dimension_scores, key=dimension_scores.get)

        # Calculate sentiment divergence (how much dimensions disagree)
        compounds = [results[dim].compound for dim in self.sentiment_analyzers]
        divergence = statistics.stdev(compounds) if len(compounds) > 1 else 0.0

        # Average confidence
        avg_confidence = statistics.mean(
            results[dim].confidence for dim in self.sentiment_analyzers
        )

        return MultiDimensionalSentiment(
            technical=results["technical"],
            market=results["market"],
            community=results["community"],
            innovation=results["innovation"],
            risk=results["risk"],
            overall=results["overall"],
            dominant_dimension=dominant,
            sentiment_divergence=round(divergence, 4),
            confidence=round(avg_confidence, 4),
        )

    def _calculate_topic_sentiment_correlation(
        self, topics: list[TopicMatch], text: str
    ) -> dict[str, float]:
        """Calculate sentiment association for each topic"""
        correlations = {}

        for topic in topics[:20]:  # Top 20 topics
            # Get context around topic mentions
            pattern = re.compile(re.escape(topic.term), re.IGNORECASE)

            context_sentiments = []
            for match in pattern.finditer(text):
                # Extract surrounding context
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Analyze context sentiment
                scores = self.overall_analyzer.analyze(context)
                context_sentiments.append(scores["compound"])

            if context_sentiments:
                correlations[topic.term] = round(statistics.mean(context_sentiments), 4)

        return correlations

    def generate_corpus_insights(
        self, analyses: list[DocumentAnalysis]
    ) -> CorpusInsights:
        """Generate aggregate insights from multiple documents"""
        if not analyses:
            return CorpusInsights(
                total_documents=0,
                total_words=0,
                analyzed_at=datetime.now(UTC).isoformat(),
            )

        # Sentiment distributions
        sentiment_dist = defaultdict(lambda: defaultdict(int))
        sentiment_sums = defaultdict(list)

        for analysis in analyses:
            if analysis.sentiment:
                for dim in [
                    "technical",
                    "market",
                    "community",
                    "innovation",
                    "risk",
                    "overall",
                ]:
                    score = getattr(analysis.sentiment, dim)
                    sentiment_dist[dim][score.label] += 1
                    sentiment_sums[dim].append(score.compound)

        # Average sentiment by dimension
        avg_sentiment = {
            dim: round(statistics.mean(scores), 4) if scores else 0.0
            for dim, scores in sentiment_sums.items()
        }

        # Topic frequency across corpus
        topic_freq = defaultdict(int)
        topic_sentiments = defaultdict(list)

        for analysis in analyses:
            for topic in analysis.topics:
                topic_freq[topic.term] += topic.frequency
            for term, sent in analysis.topic_sentiment_correlation.items():
                topic_sentiments[term].append(sent)

        # Average topic sentiment
        topic_sent_avg = {
            term: round(statistics.mean(sents), 4)
            for term, sents in topic_sentiments.items()
            if sents
        }

        # Entity aggregation
        entity_counter: dict[str, Entity] = {}
        for analysis in analyses:
            for entity in analysis.entities:
                key = f"{entity.entity_type}:{entity.text}"
                if key in entity_counter:
                    entity_counter[key].frequency += entity.frequency
                else:
                    entity_counter[key] = Entity(
                        text=entity.text,
                        entity_type=entity.entity_type,
                        frequency=entity.frequency,
                        sentiment_association=0.0,
                        co_occurrences=entity.co_occurrences.copy(),
                    )

        top_entities = sorted(
            entity_counter.values(), key=lambda e: e.frequency, reverse=True
        )[:30]

        # Sentiment trend over documents
        trend = []
        for i, analysis in enumerate(analyses):
            if analysis.sentiment:
                trend.append(
                    {
                        "index": i,
                        "document": analysis.filename,
                        "overall": analysis.sentiment.overall.compound,
                        "technical": analysis.sentiment.technical.compound,
                        "market": analysis.sentiment.market.compound,
                    }
                )

        # Generate key findings
        findings = self._generate_findings(
            analyses, avg_sentiment, topic_freq, topic_sent_avg
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(avg_sentiment, topic_sent_avg)

        # Detect anomalies
        anomalies = self._detect_anomalies(analyses)

        return CorpusInsights(
            total_documents=len(analyses),
            total_words=sum(a.word_count for a in analyses),
            analyzed_at=datetime.now(UTC).isoformat(),
            sentiment_distribution=dict(sentiment_dist),
            avg_sentiment_by_dimension=avg_sentiment,
            sentiment_trend=trend,
            topic_frequency=dict(sorted(topic_freq.items(), key=lambda x: -x[1])[:50]),
            topic_sentiment=topic_sent_avg,
            top_entities=top_entities,
            key_findings=findings,
            recommendations=recommendations,
            anomalies=anomalies,
        )

    def _generate_findings(
        self,
        analyses: list[DocumentAnalysis],
        avg_sentiment: dict[str, float],
        topic_freq: dict[str, int],
        topic_sent: dict[str, float],
    ) -> list[str]:
        """Generate key findings from analysis"""
        findings = []

        # Overall sentiment finding
        overall = avg_sentiment.get("overall", 0)
        if overall > 0.3:
            findings.append(
                f"📈 Overall corpus sentiment is POSITIVE (avg: {overall:.2f})"
            )
        elif overall < -0.3:
            findings.append(
                f"📉 Overall corpus sentiment is NEGATIVE (avg: {overall:.2f})"
            )
        else:
            findings.append(
                f"📊 Overall corpus sentiment is NEUTRAL (avg: {overall:.2f})"
            )

        # Dimension-specific findings
        tech = avg_sentiment.get("technical", 0)
        market = avg_sentiment.get("market", 0)

        if tech > 0.2:
            findings.append(f"🔧 High TECHNICAL CONFIDENCE detected (avg: {tech:.2f})")
        elif tech < -0.2:
            findings.append(
                f"⚠️ Low TECHNICAL CONFIDENCE - potential security concerns (avg: {tech:.2f})"
            )

        if market > 0.3:
            findings.append(
                f"🐂 BULLISH market sentiment prevalent (avg: {market:.2f})"
            )
        elif market < -0.3:
            findings.append(f"🐻 BEARISH market sentiment detected (avg: {market:.2f})")

        # Top topics
        if topic_freq:
            top_topics = sorted(topic_freq.items(), key=lambda x: -x[1])[:5]
            topics_str = ", ".join(f"{t[0]} ({t[1]}x)" for t in top_topics)
            findings.append(f"🏷️ Most discussed topics: {topics_str}")

        # Topics with extreme sentiment
        if topic_sent:
            positive_topics = [(t, s) for t, s in topic_sent.items() if s > 0.3]
            negative_topics = [(t, s) for t, s in topic_sent.items() if s < -0.3]

            if positive_topics:
                pos_str = ", ".join(
                    f"{t[0]}" for t in sorted(positive_topics, key=lambda x: -x[1])[:3]
                )
                findings.append(f"✅ Positively associated topics: {pos_str}")

            if negative_topics:
                neg_str = ", ".join(
                    f"{t[0]}" for t in sorted(negative_topics, key=lambda x: x[1])[:3]
                )
                findings.append(f"❌ Negatively associated topics: {neg_str}")

        return findings

    def _generate_recommendations(
        self, avg_sentiment: dict[str, float], topic_sent: dict[str, float]
    ) -> list[str]:
        """Generate actionable recommendations"""
        recommendations = []

        tech = avg_sentiment.get("technical", 0)
        risk = avg_sentiment.get("risk", 0)
        community = avg_sentiment.get("community", 0)

        if tech < 0:
            recommendations.append(
                "💡 Consider emphasizing security audits and formal verification in documentation"
            )

        if risk < -0.2:
            recommendations.append(
                "💡 Risk-related content is negative - consider adding risk mitigation strategies"
            )

        if community < 0:
            recommendations.append(
                "💡 Community sentiment is low - focus on engagement and transparency"
            )

        # Topic-specific recommendations
        negative_topics = [t for t, s in topic_sent.items() if s < -0.2]
        if negative_topics:
            recommendations.append(
                f"💡 Address concerns around: {', '.join(negative_topics[:3])}"
            )

        return recommendations

    def _detect_anomalies(self, analyses: list[DocumentAnalysis]) -> list[str]:
        """Detect anomalous patterns in the corpus"""
        anomalies = []

        if len(analyses) < 3:
            return anomalies

        # Calculate sentiment statistics
        overall_scores = [a.sentiment.overall.compound for a in analyses if a.sentiment]

        if len(overall_scores) >= 3:
            mean = statistics.mean(overall_scores)
            stdev = statistics.stdev(overall_scores)

            # Find outliers (>2 std deviations)
            for analysis in analyses:
                if analysis.sentiment:
                    score = analysis.sentiment.overall.compound
                    if abs(score - mean) > 2 * stdev:
                        direction = "positive" if score > mean else "negative"
                        anomalies.append(
                            f"🔍 Outlier: '{analysis.filename}' has unusually {direction} "
                            f"sentiment ({score:.2f})"
                        )

        # Detect high divergence documents
        for analysis in analyses:
            if analysis.sentiment and analysis.sentiment.sentiment_divergence > 0.5:
                anomalies.append(
                    f"🔍 Mixed signals: '{analysis.filename}' shows high sentiment "
                    "divergence across dimensions"
                )

        return anomalies[:10]  # Limit to top 10


# ══════════════════════════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════════


class SpectrePipeline:
    """
    Main pipeline orchestrator.
    Handles file discovery, parallel processing, and output generation.
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        taxonomy_file: Path = None,
        workers: int = None,
        verbose: bool = True,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.workers = workers or os.cpu_count()
        self.verbose = verbose

        # Load taxonomy
        taxonomy_terms = []
        if taxonomy_file and taxonomy_file.exists():
            taxonomy_terms = taxonomy_file.read_text().strip().split("\n")
            self._log(f"Loaded {len(taxonomy_terms)} taxonomy terms", "INFO")

        # Initialize analyzer
        self.analyzer = SpectreAnalyzer(taxonomy_terms)

        # Results
        self.analyses: list[DocumentAnalysis] = []
        self.errors: list[dict] = []

        # Initialize output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "documents").mkdir(exist_ok=True)
        (self.output_dir / "reports").mkdir(exist_ok=True)

    def _log(self, message: str, level: str = "INFO"):
        """Log message with color"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": Colors.CYAN,
            "SUCCESS": Colors.GREEN,
            "WARNING": Colors.YELLOW,
            "ERROR": Colors.RED,
            "DEBUG": Colors.MAGENTA,
        }
        color = colors.get(level, Colors.WHITE)

        if self.verbose or level in ("ERROR", "WARNING", "SUCCESS"):
            print(f"{color}[{timestamp}] [{level:8}] {message}{Colors.RESET}")

    def discover_files(self) -> list[Path]:
        """Discover all markdown files"""
        files = list(self.input_dir.rglob("*.md"))
        files.extend(self.input_dir.rglob("*.markdown"))
        return sorted(files)

    def process_file(self, filepath: Path) -> DocumentAnalysis | None:
        """Process a single file"""
        try:
            analysis = self.analyzer.analyze_document(filepath)
            return analysis
        except Exception as e:
            self.errors.append(
                {
                    "file": str(filepath),
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            self._log(f"Error processing {filepath.name}: {e}", "ERROR")
            return None

    def run(self) -> CorpusInsights:
        """Execute the full pipeline"""
        self._print_banner()

        start_time = time.time()

        # Stage 1: Discovery
        self._log("═══ STAGE 1: FILE DISCOVERY ═══", "INFO")
        files = self.discover_files()
        self._log(f"Found {len(files)} markdown files", "INFO")

        if not files:
            self._log("No files to process", "WARNING")
            return CorpusInsights(
                total_documents=0,
                total_words=0,
                analyzed_at=datetime.now(UTC).isoformat(),
            )

        # Stage 2: Analysis
        self._log("═══ STAGE 2: DOCUMENT ANALYSIS ═══", "INFO")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.process_file, f): f for f in files}

            completed = 0
            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    result = future.result()
                    if result:
                        self.analyses.append(result)
                        completed += 1

                        # Progress indicator
                        if completed % 50 == 0:
                            self._log(
                                f"Processed {completed}/{len(files)} files", "INFO"
                            )
                except Exception as e:
                    self._log(f"Worker error for {filepath}: {e}", "ERROR")

        self._log(f"Analyzed {len(self.analyses)} documents successfully", "SUCCESS")

        # Stage 3: Aggregation
        self._log("═══ STAGE 3: CORPUS AGGREGATION ═══", "INFO")
        insights = self.analyzer.generate_corpus_insights(self.analyses)

        # Stage 4: Output Generation
        self._log("═══ STAGE 4: OUTPUT GENERATION ═══", "INFO")
        self._generate_outputs(insights)

        end_time = time.time()
        duration = end_time - start_time

        # Summary
        self._print_summary(insights, duration)

        return insights

    def _generate_outputs(self, insights: CorpusInsights):
        """Generate all output files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Individual document analyses
        for analysis in self.analyses:
            doc_path = (
                self.output_dir
                / "documents"
                / f"{Path(analysis.filename).stem}_analysis.json"
            )
            with open(doc_path, "w") as f:
                json.dump(analysis.to_dict(), f, indent=2, default=str)

        # Corpus insights
        insights_path = (
            self.output_dir / "reports" / f"corpus_insights_{timestamp}.json"
        )
        with open(insights_path, "w") as f:
            json.dump(insights.to_dict(), f, indent=2, default=str)

        # Summary report (human-readable)
        report_path = self.output_dir / "reports" / f"summary_report_{timestamp}.md"
        self._generate_markdown_report(insights, report_path)

        # Sentiment CSV
        csv_path = self.output_dir / "reports" / f"sentiment_data_{timestamp}.csv"
        self._generate_csv(csv_path)

        self._log(f"Reports saved to {self.output_dir / 'reports'}", "SUCCESS")

    def _generate_markdown_report(self, insights: CorpusInsights, output_path: Path):
        """Generate human-readable markdown report"""
        lines = [
            "# 🔮 SPECTRE Analysis Report",
            "",
            f"**Generated:** {insights.analyzed_at}",
            f"**Documents Analyzed:** {insights.total_documents}",
            f"**Total Words Processed:** {insights.total_words:,}",
            "",
            "---",
            "",
            "## 📊 Sentiment Overview",
            "",
            "| Dimension | Average Score | Interpretation |",
            "|-----------|--------------|----------------|",
        ]

        for dim, score in insights.avg_sentiment_by_dimension.items():
            interp = (
                "Positive" if score > 0.1 else "Negative" if score < -0.1 else "Neutral"
            )
            lines.append(f"| {dim.title()} | {score:.4f} | {interp} |")

        lines.extend(
            [
                "",
                "## 🏷️ Top Topics",
                "",
            ]
        )

        for topic, freq in list(insights.topic_frequency.items())[:15]:
            sent = insights.topic_sentiment.get(topic, 0)
            emoji = "📈" if sent > 0.1 else "📉" if sent < -0.1 else "📊"
            lines.append(
                f"- **{topic}**: {freq}x mentions {emoji} (sentiment: {sent:.2f})"
            )

        lines.extend(
            [
                "",
                "## 🎯 Key Findings",
                "",
            ]
        )

        for finding in insights.key_findings:
            lines.append(f"- {finding}")

        lines.extend(
            [
                "",
                "## 💡 Recommendations",
                "",
            ]
        )

        for rec in insights.recommendations:
            lines.append(f"- {rec}")

        if insights.anomalies:
            lines.extend(
                [
                    "",
                    "## 🔍 Anomalies Detected",
                    "",
                ]
            )
            for anomaly in insights.anomalies:
                lines.append(f"- {anomaly}")

        lines.extend(
            [
                "",
                "---",
                "",
                f"*Report generated by SPECTRE v{VERSION}*",
            ]
        )

        output_path.write_text("\n".join(lines))

    def _generate_csv(self, output_path: Path):
        """Generate sentiment data CSV"""
        lines = [
            "filename,word_count,overall,technical,market,community,innovation,risk,"
            "dominant_dimension"
        ]

        for analysis in self.analyses:
            if analysis.sentiment:
                s = analysis.sentiment
                lines.append(
                    f"{analysis.filename},{analysis.word_count},"
                    f"{s.overall.compound},{s.technical.compound},{s.market.compound},"
                    f"{s.community.compound},{s.innovation.compound},{s.risk.compound},"
                    f"{s.dominant_dimension}"
                )

        output_path.write_text("\n".join(lines))

    def _print_banner(self):
        """Print startup banner"""
        banner = f"""
{Colors.MAGENTA}╔══════════════════════════════════════════════════════════════════════════════════╗
║  ███████╗██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗                       ║
║  ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝                       ║
║  ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗                         ║
║  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝                         ║
║  ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗                       ║
║  ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝                       ║
║  ════════════════════════════════════════════════════════════════════════════════║
║  Sentiment & Pattern Extraction for Contextual Text Research Engine v{VERSION}        ║
╚══════════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
        print(banner)

    def _print_summary(self, insights: CorpusInsights, duration: float):
        """Print execution summary"""
        throughput = insights.total_documents / max(duration, 0.001)
        documents_row = (
            f"║  Documents Analyzed:    {insights.total_documents:>10}"
            "                                               ║"
        )
        words_row = (
            f"║  Total Words:           {insights.total_words:>10,}"
            "                                               ║"
        )
        print(f"""
{Colors.GREEN}╔══════════════════════════════════════════════════════════════════════════════════╗
║                              EXECUTION SUMMARY                                    ║
╠══════════════════════════════════════════════════════════════════════════════════╣
{documents_row}
{words_row}
║  Processing Time:       {duration:>10.2f}s                                              ║
║  Throughput:            {throughput:>10.2f} docs/sec                                        ║
╚══════════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
""")

        # Sentiment summary
        print(f"\n{Colors.CYAN}📊 Sentiment by Dimension:{Colors.RESET}")
        for dim, score in insights.avg_sentiment_by_dimension.items():
            bar_len = int(abs(score) * 20)
            if score >= 0:
                bar = Colors.GREEN + "█" * bar_len + "░" * (20 - bar_len) + Colors.RESET
            else:
                bar = Colors.RED + "█" * bar_len + "░" * (20 - bar_len) + Colors.RESET
            print(f"  {dim:12} {bar} {score:+.4f}")

        # Key findings
        print(f"\n{Colors.YELLOW}🎯 Key Findings:{Colors.RESET}")
        for finding in insights.key_findings[:5]:
            print(f"  {finding}")


# ══════════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ══════════════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SPECTRE - Sentiment & Pattern Extraction for Contextual Text Research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  spectre -i ./docs -o ./analysis
  spectre -i ./markdown -o ./results -t taxonomy.txt
  spectre -i ./content -o ./output -w 8 -v
""",
    )

    parser.add_argument(
        "-i", "--input", required=True, help="Input directory with .md files"
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output directory for results"
    )
    parser.add_argument("-t", "--taxonomy", help="Taxonomy file (one term per line)")
    parser.add_argument(
        "-w", "--workers", type=int, default=None, help="Worker threads"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--version", action="version", version=f"SPECTRE {VERSION}")

    args = parser.parse_args()

    # Run pipeline
    pipeline = SpectrePipeline(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        taxonomy_file=Path(args.taxonomy) if args.taxonomy else None,
        workers=args.workers,
        verbose=args.verbose,
    )

    insights = pipeline.run()

    # Exit code based on success
    sys.exit(0 if insights.total_documents > 0 else 1)


if __name__ == "__main__":
    main()
