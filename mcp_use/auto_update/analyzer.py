"""Analyze scraped documentation with LLM-backed intelligence."""

from dataclasses import dataclass, field
from typing import Any

from .intelligence import DocumentationIntelligence, IntelligenceReport, IntelligenceSignal
from .scraper import DocumentationSnapshot


@dataclass(slots=True)
class ChangeSignal:
    """A structured signal extracted from the intelligence report."""

    keyword: str
    description: str
    severity: str = "info"


@dataclass(slots=True)
class ChangeAnalysis:
    """Structured result describing the impact of a documentation snapshot."""

    model: str
    signals: list[ChangeSignal] = field(default_factory=list)
    json_schemas: list[dict[str, Any]] = field(default_factory=list)
    recommended_updates: list[str] = field(default_factory=list)
    insights_summary: str | None = None

    def add_signal(self, keyword: str, description: str, severity: str = "info") -> None:
        self.signals.append(ChangeSignal(keyword=keyword, description=description, severity=severity))

    def add_recommendation(self, recommendation: str) -> None:
        self.recommended_updates.append(recommendation)


class DocumentationAnalyzer:
    """Derive actionable information from documentation snapshots via an LLM."""

    def __init__(self, intelligence: DocumentationIntelligence) -> None:
        self._intelligence = intelligence

    def analyze(self, snapshot: DocumentationSnapshot) -> ChangeAnalysis:
        report = self._intelligence.analyze(snapshot)
        analysis = ChangeAnalysis(model=snapshot.model, insights_summary=report.summary)
        self._apply_report(report, analysis)
        return analysis

    def _apply_report(self, report: IntelligenceReport, analysis: ChangeAnalysis) -> None:
        for signal in report.signals:
            self._add_signal(signal, analysis)
        analysis.json_schemas.extend(report.json_schemas)
        for recommendation in report.recommendations:
            analysis.add_recommendation(recommendation)

    def _add_signal(self, signal: IntelligenceSignal, analysis: ChangeAnalysis) -> None:
        keyword = signal.keyword or "llm_signal"
        description = signal.description or signal.keyword or "LLM reported change"
        severity = signal.severity or "info"
        analysis.add_signal(keyword=keyword, description=description, severity=severity)
