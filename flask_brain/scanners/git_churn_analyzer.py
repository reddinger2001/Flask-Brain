"""Git churn analyzer — enriches nodes with file-level commit frequency."""

import subprocess
from pathlib import Path
from collections import defaultdict

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Graph, Node, Edge


class GitChurnAnalyzer(BaseScanner):
    """Reads git log to count how many times each file has changed."""

    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Return empty — this scanner only enriches existing nodes."""
        return [], []

    def enrich(self, graph: Graph) -> None:
        """Add churn_count and risk_score to every node whose file is tracked by git.

        churn_count  — number of commits that touched this file
        risk_score   — int(complexity * churn_count); 0 if complexity missing
        """
        churn = self._compute_churn()
        if not churn:
            return  # git not available or repo not initialised

        for node in graph.nodes.values():
            file_path = node.file_path
            count = churn.get(file_path, 0)
            node.metadata["churn_count"] = count
            complexity = node.metadata.get("complexity") or 0
            node.metadata["risk_score"] = int(complexity * count)

    def _compute_churn(self) -> dict[str, int]:
        """Run git log --name-only and count commits per file.

        Returns a dict mapping relative file path → commit count.
        Returns empty dict if git is not available or this is not a git repo.
        """
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    "--name-only",
                    "--pretty=format:",
                    "--no-merges",
                ],
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                timeout=30,
            )
            if result.returncode != 0:
                return {}

            churn: dict[str, int] = defaultdict(int)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    churn[line] += 1

            return dict(churn)

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {}
