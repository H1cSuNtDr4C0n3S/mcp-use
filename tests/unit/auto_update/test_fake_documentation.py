import asyncio
import json
import re
from pathlib import Path

from mcp_use.auto_update.analyzer import DocumentationAnalyzer
from mcp_use.auto_update.generator import AdapterGenerator
from mcp_use.auto_update.intelligence import IntelligenceReport, IntelligenceSignal
from mcp_use.auto_update.scraper import DocumentationScraper
from mcp_use.auto_update.tester import AutoUpdateTestSuite


class HeuristicIntelligence:
    def analyze(self, snapshot):
        text_lower = snapshot.raw_text.lower()
        signals: list[IntelligenceSignal] = []
        keyword_mapping = {
            "tool_choice": ("tool_choice keyword detected", "warning"),
            "parallel_tool_calls": ("parallel tool execution supported", "breaking"),
        }
        for keyword, (description, severity) in keyword_mapping.items():
            if keyword in text_lower:
                signals.append(IntelligenceSignal(keyword=keyword, description=description, severity=severity))

        json_schemas: list[dict] = []
        for block in re.findall(r"```json\s*(\{.*?\})\s*```", snapshot.raw_text, flags=re.DOTALL):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:  # pragma: no cover - defensive fallback
                continue
            if isinstance(parsed, dict):
                json_schemas.append(parsed)

        recommendations: list[str] = []
        if any(signal.severity == "breaking" for signal in signals):
            recommendations.append("Schedule integration tests for parallel tool execution")
        if any(signal.keyword == "tool_choice" for signal in signals):
            recommendations.append("Update LangChainAdapter to map tool_choice payloads")
        if json_schemas:
            recommendations.append("Generate schema artifacts from documentation examples")

        summary = "No significant changes detected."
        if signals:
            summary = "Detected signals: " + ", ".join(signal.keyword for signal in signals)

        return IntelligenceReport(
            summary=summary,
            signals=signals,
            json_schemas=json_schemas,
            recommendations=recommendations,
        )


def test_pipeline_handles_fake_documentation():
    doc_path = Path(__file__).parent / "data" / "fake_model_doc.md"
    fake_doc = doc_path.read_text()

    async def fetcher(_url: str) -> str:
        return fake_doc

    scraper = DocumentationScraper(fetcher=fetcher)
    snapshot = asyncio.run(scraper.scrape("gpt-fictitious", "file://fake"))

    assert snapshot.model == "gpt-fictitious"
    assert "invoke_directives" in snapshot.raw_text
    assert "cooperative_branches" in snapshot.raw_text

    analyzer = DocumentationAnalyzer(intelligence=HeuristicIntelligence())
    analysis = analyzer.analyze(snapshot)

    assert not analysis.signals, "The heuristic should not match unknown keywords"
    assert analysis.json_schemas, "Expected JSON schemas to be extracted"

    generator = AdapterGenerator()
    plan = generator.build_plan(analysis)

    assert plan.tasks, "The generation plan should include actionable tasks"
    assert plan.artifacts, "The fake documentation should yield generated artifacts"
    assert any("schema" in task.lower() for task in plan.tasks)

    suite = AutoUpdateTestSuite(plan)
    results = suite.run()

    assert all(result.passed for result in results)
