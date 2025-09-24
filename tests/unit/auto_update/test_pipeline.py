from mcp_use.auto_update.analyzer import DocumentationAnalyzer
from mcp_use.auto_update.generator import AdapterGenerator
from mcp_use.auto_update.intelligence import IntelligenceReport, IntelligenceSignal
from mcp_use.auto_update.scraper import DocumentationSnapshot
from mcp_use.auto_update.tester import AutoUpdateTestSuite, TestResult


class FakeIntelligence:
    def __init__(self, report: IntelligenceReport):
        self.report = report
        self.last_snapshot: DocumentationSnapshot | None = None

    def analyze(self, snapshot: DocumentationSnapshot) -> IntelligenceReport:
        self.last_snapshot = snapshot
        return self.report


def build_analyzer(report: IntelligenceReport) -> DocumentationAnalyzer:
    return DocumentationAnalyzer(intelligence=FakeIntelligence(report))


def build_snapshot(text: str) -> DocumentationSnapshot:
    return DocumentationSnapshot(model="gpt-x", url="https://example.com", raw_text=text, sections={})


def test_analyzer_detects_signals_and_json():
    text = """
    The new interface introduces tool_choice and parallel_tool_calls.

    ```json
    {"type": "object", "properties": {"tool_calls": {"type": "array"}}}
    ```
    """
    report = IntelligenceReport(
        summary="Parallel tools and schema updates detected.",
        signals=[
            IntelligenceSignal(keyword="tool_choice", description="tool_choice keyword introduced", severity="warning"),
            IntelligenceSignal(keyword="parallel_tool_calls", description="Parallel execution supported", severity="breaking"),
        ],
        json_schemas=[{"type": "object", "properties": {"tool_calls": {"type": "array"}}}],
        recommendations=[
            "Update LangChainAdapter to support tool_choice",
            "Add regression schema",
        ],
    )

    analyzer = build_analyzer(report)
    analysis = analyzer.analyze(build_snapshot(text))

    assert {signal.keyword for signal in analysis.signals} >= {"tool_choice", "parallel_tool_calls"}
    assert analysis.json_schemas, "Expected JSON schemas to be captured"
    assert any("LangChainAdapter" in rec for rec in analysis.recommended_updates)


def test_generator_and_testsuite_validate_plan():
    text = """
    tool_choice is now required.

    ```json
    {"required": ["tool_choice"]}
    ```
    """
    report = IntelligenceReport(
        summary="tool_choice now required.",
        signals=[
            IntelligenceSignal(keyword="tool_choice", description="tool_choice is required", severity="warning"),
        ],
        json_schemas=[{"required": ["tool_choice"]}],
        recommendations=["Update LangChainAdapter mapping", "Generate schema artifact"],
    )

    analyzer = build_analyzer(report)
    analysis = analyzer.analyze(build_snapshot(text))

    generator = AdapterGenerator()
    plan = generator.build_plan(analysis)

    assert plan.tasks, "Generator should include at least one task"
    assert plan.artifacts, "JSON schema should produce artifacts"

    suite = AutoUpdateTestSuite(plan)
    results = suite.run()

    assert all(result.passed for result in results)
    assert isinstance(results[0], TestResult)
