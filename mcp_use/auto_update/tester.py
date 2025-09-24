"""Offline validation helpers for generated adapters."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable

from .generator import CodeGenerationPlan


@dataclass(slots=True)
class TestResult:
    __test__ = False
    """Represents the outcome of a validation step."""

    name: str
    passed: bool
    details: str | None = None


class AutoUpdateTestSuite:
    """Run static checks over generation plans."""

    def __init__(self, plan: CodeGenerationPlan) -> None:
        self.plan = plan

    def run(self) -> list[TestResult]:
        results = [self._validate_tasks_present(), *self._validate_artifacts()]
        return results

    def _validate_tasks_present(self) -> TestResult:
        if not self.plan.tasks:
            return TestResult(name="tasks", passed=False, details="No tasks present in plan.")
        return TestResult(name="tasks", passed=True)

    def _validate_artifacts(self) -> Iterable[TestResult]:
        for artifact in self.plan.artifacts:
            try:
                ast.parse(artifact.content)
            except SyntaxError as exc:  # pragma: no cover - covered in error branch tests
                yield TestResult(
                    name=f"artifact:{artifact.filename}",
                    passed=False,
                    details=f"Generated artifact is not valid Python: {exc}",
                )
            else:
                yield TestResult(name=f"artifact:{artifact.filename}", passed=True)

