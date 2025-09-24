"""Plan and generate code patches for new tool formats."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from typing import Iterable

from .analyzer import ChangeAnalysis


@dataclass(slots=True)
class GenerationArtifact:
    """Represents a code artifact produced by the generator."""

    filename: str
    content: str


@dataclass(slots=True)
class CodeGenerationPlan:
    """High-level instructions for updating MCP-Use."""

    model: str
    summary: str
    tasks: list[str] = field(default_factory=list)
    artifacts: list[GenerationArtifact] = field(default_factory=list)

    def add_task(self, task: str) -> None:
        self.tasks.append(task)

    def add_artifact(self, filename: str, content: str) -> None:
        self.artifacts.append(GenerationArtifact(filename=filename, content=content))


class AdapterGenerator:
    """Translate analysis results into actionable code generation plans."""

    def build_plan(self, analysis: ChangeAnalysis) -> CodeGenerationPlan:
        summary = self._summarize(analysis)
        plan = CodeGenerationPlan(model=analysis.model, summary=summary)
        for recommendation in analysis.recommended_updates:
            plan.add_task(recommendation)
        for schema_index, schema in enumerate(analysis.json_schemas, start=1):
            filename = f"{analysis.model}_schema_{schema_index}.py"
            content = self._render_schema_module(schema, analysis.model, schema_index)
            plan.add_artifact(filename, content)
        if not plan.tasks:
            plan.add_task("Review documentation manually; no actionable items detected.")
        return plan

    def _summarize(self, analysis: ChangeAnalysis) -> str:
        if analysis.insights_summary:
            return analysis.insights_summary
        if not analysis.signals:
            return "No signals detected in documentation."
        signals = ", ".join(signal.keyword for signal in analysis.signals)
        return f"Signals detected for {analysis.model}: {signals}."

    def _render_schema_module(self, schema: dict, model: str, index: int) -> str:
        serialized_schema = json.dumps(schema, indent=4, sort_keys=True)
        template = textwrap.dedent(
            f'''"""Auto-generated schema snapshot for {model} (example {index})."""

from __future__ import annotations

from pydantic import BaseModel

EXAMPLE_SCHEMA = {serialized_schema}


class ToolCallSchema(BaseModel):
    """Pydantic model mirroring the scraped schema for regression tests."""

    __root__: dict = EXAMPLE_SCHEMA
'''
        )
        return template

    def iter_artifact_paths(self, plan: CodeGenerationPlan) -> Iterable[str]:
        for artifact in plan.artifacts:
            yield artifact.filename
