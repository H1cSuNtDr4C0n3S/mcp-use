"""LLM-backed intelligence layer for documentation analysis."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable

from .scraper import DocumentationSnapshot


@dataclass(slots=True)
class IntelligenceSignal:
    """A structured signal returned by the intelligence module."""

    keyword: str
    description: str
    severity: str = "info"


@dataclass(slots=True)
class IntelligenceReport:
    """Aggregated understanding of a documentation snapshot."""

    summary: str
    signals: list[IntelligenceSignal] = field(default_factory=list)
    json_schemas: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class DocumentationIntelligence:
    """Thin wrapper around an LLM that produces structured reports."""

    PROMPT_TEMPLATE = textwrap.dedent(
        """
        You are an assistant that reviews MCP function-calling documentation. Given the text
        below, analyse the entire content and respond ONLY with JSON using the following schema:
        {
          "summary": "string - high level synopsis of the changes",
          "signals": [
            {"keyword": "short token", "description": "string", "severity": "info|warning|breaking"}
          ],
          "json_schemas": [ {"type": "object", ... } ],
          "recommendations": ["string", ...]
        }
        Ensure the payload is valid JSON and capture relevant schema examples verbatim.
        Documentation text:
        \"\"\"{documentation}\"\"\"
        """
    ).strip()

    def __init__(self, llm: Callable[[str], str | dict[str, Any]] | None = None) -> None:
        self._llm = llm

    def analyze(self, snapshot: DocumentationSnapshot) -> IntelligenceReport:
        if self._llm is None:
            return self._heuristic_report(snapshot)
        prompt = self.PROMPT_TEMPLATE.format(documentation=snapshot.raw_text)
        raw_response = self._llm(prompt)
        payload = self._coerce_payload(raw_response)
        return self._report_from_payload(payload)

    def _coerce_payload(self, raw_response: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(raw_response, dict):
            return raw_response
        if not isinstance(raw_response, str):  # pragma: no cover - defensive programming
            msg = "LLM response must be a string or dictionary"
            raise TypeError(msg)
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if not match:
                msg = "Unable to parse LLM output as JSON"
                raise ValueError(msg) from None
            return json.loads(match.group(0))

    def _report_from_payload(self, payload: dict[str, Any]) -> IntelligenceReport:
        summary = str(payload.get("summary", ""))
        signals_payload = payload.get("signals", []) or []
        signals = [
            IntelligenceSignal(
                keyword=str(item.get("keyword", "")),
                description=str(item.get("description", "")),
                severity=str(item.get("severity", "info")),
            )
            for item in signals_payload
            if isinstance(item, dict)
        ]
        schemas_payload = payload.get("json_schemas", []) or []
        json_schemas: list[dict[str, Any]] = []
        for schema in schemas_payload:
            if isinstance(schema, dict):
                json_schemas.append(schema)
        recommendations_payload = payload.get("recommendations", []) or []
        recommendations = [
            str(item) for item in recommendations_payload if isinstance(item, str)
        ]
        return IntelligenceReport(
            summary=summary,
            signals=signals,
            json_schemas=json_schemas,
            recommendations=recommendations,
        )

    def _heuristic_report(self, snapshot: DocumentationSnapshot) -> IntelligenceReport:
        text_lower = snapshot.raw_text.lower()
        signals: list[IntelligenceSignal] = []
        keyword_mapping = {
            "tool_choice": ("tool_choice keyword detected", "warning"),
            "parallel_tool_calls": ("Parallel tool execution described", "breaking"),
            "tool_use": ("Anthropic tool_use section detected", "warning"),
            "function_call": ("Legacy function_call reference found", "info"),
        }
        for keyword, (description, severity) in keyword_mapping.items():
            if keyword in text_lower:
                signals.append(
                    IntelligenceSignal(keyword=keyword, description=description, severity=severity)
                )

        json_schemas: list[dict[str, Any]] = []
        for block in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", snapshot.raw_text, flags=re.DOTALL):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:  # pragma: no cover - defensive fallback
                continue
            if isinstance(parsed, dict):
                json_schemas.append(parsed)

        recommendations: list[str] = []
        if any(signal.severity == "breaking" for signal in signals):
            recommendations.append("Generate a high priority adapter patch and schedule integration tests.")
        if any(signal.keyword == "tool_choice" for signal in signals):
            recommendations.append("Update LangChainAdapter to map tool_choice fields to MCP call payloads.")
        if json_schemas:
            recommendations.append("Produce Pydantic models from discovered JSON schema examples for regression tests.")

        summary = "No signals detected in documentation."
        if signals:
            summary = f"Signals detected for {snapshot.model}: " + ", ".join(signal.keyword for signal in signals)

        return IntelligenceReport(
            summary=summary,
            signals=signals,
            json_schemas=json_schemas,
            recommendations=recommendations,
        )
