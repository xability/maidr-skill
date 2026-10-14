"""Static routing-contract guardrails, NOT model-behavior tests.

These checks catch contradictory docs, a late gate, and lost eval coverage.
The prompts in evals/evals.json still need real model runs and tool-trace review
(especially actual import/install attempts and exact artifact publication).
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "maidr"


class RoutingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        cls.docs = {
            "SKILL.md": cls.skill,
            "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
            **{name: (SKILL / "references" / name).read_text(encoding="utf-8")
               for name in ("python.md", "javascript.md")},
        }
        cls.evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]

    def test_gate_is_early_and_skill_stays_small(self):
        gate = self.skill.index("## Routing gate:")
        self.assertLess(gate, self.skill.index("## Workflow"))
        self.assertLess(gate, self.skill.index("### Where the chart goes"))
        self.assertLessEqual(len(self.skill[:gate].splitlines()), 25)
        self.assertLessEqual(len(self.skill.splitlines()), 300)

    def test_gate_preserves_language_then_requires_real_python_attempt(self):
        gate = self.skill.split("## Routing gate:", 1)[1].split("## Workflow", 1)[0]
        self.assertLess(gate.index("**maidr R package**"), gate.index("**py-maidr**"))
        self.assertLess(gate.index("**maidr.js**"), gate.index("**py-maidr**"))
        for requirement in (
            "existing code/project or explicit request",
            'python -c "import maidr"', "python -m pip install maidr",
            "then retry the import", "verdict is not an import/install attempt",
            "failing command/tool", "concrete error", "An import error alone is not enough",
            "exact generated HTML", "Do not redraw", "Read `references/python.md`",
            'maidr.save_html(fig, "chart.html", use_cdn=True)',
            "pass the original figure directly", "do not invent a plotting constructor",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, gate)
        self.assertLess(gate.index("**py-maidr**"), gate.index("Only after observed failure"))

    def test_reader_runtime_and_evidence_contract_agree_across_docs(self):
        for name, doc in self.docs.items():
            with self.subTest(doc=name):
                self.assertIn("reader needs no Python", doc)
                self.assertIn("concrete error", doc)
                self.assertIn("observed", doc)
                self.assertIn("explicit", doc)
        for name in ("SKILL.md", "README.md", "javascript.md"):
            self.assertIn("Rendering HTML is not JavaScript development", self.docs[name], name)
        for name in ("SKILL.md", "README.md", "python.md"):
            self.assertIn("exact", self.docs[name], name)
            self.assertIn("save_html", self.docs[name], name)

    def test_known_conflicting_shortcuts_do_not_return(self):
        obsolete = (
            "When Python exists on both sides",
            "if the user says they have no Python",
            "or a static HTML page that must open anywhere",
            "If the sandbox cannot reach PyPI, fall back",
            "Work's code sandbox reaches PyPI",
            "The chart lives in a JavaScript page or app",
        )
        for name, doc in self.docs.items():
            for phrase in obsolete:
                with self.subTest(doc=name, phrase=phrase):
                    self.assertNotIn(phrase, doc)

    def test_mcp_still_precedes_local_routing_and_has_its_own_evals(self):
        gate = self.skill.split("## Routing gate:", 1)[1]
        self.assertLess(gate.index("**First, look for maidr's own chart tool.**"),
                        gate.index("| Authoring task"))
        self.assertIn("only when all three rows on the left hold", self.skill)
        names = {case["name"] for case in self.evals}
        self.assertTrue({"maidr-mcp-connected-chart-in-chat", "maidr-mcp-connected-code-request",
                         "maidr-mcp-connected-panels-in-chat"}.issubset(names))

    def test_claude_native_html_delivery_is_distinct_from_work_and_unbound_widgets(self):
        obsolete = (
            "In a chat, the chart is an artifact, not a file.",
            "Never hand the chart to the product's own visualization widget instead.",
            "keyboard navigation/sonification cannot be tested,",
        )
        for name, doc in self.docs.items():
            with self.subTest(doc=name):
                self.assertIn("show_widget", doc)
                self.assertIn("--fragment", doc)
                self.assertIn("--visualize", doc)
                self.assertIn("artifact", doc.lower())
                self.assertIn("unverified", doc.lower())
                for phrase in obsolete:
                    self.assertNotIn(phrase, doc)
        self.assertIn("explicit artifact request", self.skill)
        self.assertIn("observed native runtime/accessibility failure", self.skill)
        self.assertIn("Lack of browser inspection is not a rendering failure", self.skill)
        self.assertIn("chosen binding's exact output", self.skill)

    def test_native_eval_coverage_requires_real_browser_evidence_and_fallbacks(self):
        cases = {case["name"]: case for case in self.evals}
        native = cases["claude-native-inline-no-maidr-mcp"]
        assertions = "\n".join(native["assertions"])
        for requirement in ("role=application", "audio frequencies", "--fragment",
                            "unverified", "Original SVG geometry", "show_chart"):
            self.assertIn(requirement, assertions)
        for name in ("claude-native-unavailable-artifact-fallback",
                     "claude-native-runtime-blocked-artifact-fallback"):
            self.assertTrue(cases[name]["setup"])
            self.assertIn("artifact", cases[name]["expected_output"])
        artifact = cases["claude-html-artifact-no-reader-python"]
        self.assertIn("native inline renderer is also available", artifact["setup"])
        neutral = cases["claude-neutral-chart-python-attempt"]
        self.assertIn("native inline HTML renderer", neutral["expected_output"])

    def test_eval_coverage_includes_execution_evidence_and_preserved_languages(self):
        self.assertEqual(len(self.evals), len({case["id"] for case in self.evals}))
        self.assertEqual(len(self.evals), len({case["name"] for case in self.evals}))
        cases = {case["name"]: case for case in self.evals}
        required = {
            "standalone-html-line-chart-no-reader-python": "self-contained",
            "claude-neutral-chart-python-attempt": "actual installation",
            "claude-html-artifact-no-reader-python": "exact",
            "claude-explicit-javascript-preserved": "Does not rewrite",
            "claude-explicit-r-preserved": "Does not force Python",
            "claude-observed-install-failure-fallback": "actual installation failure",
        }
        for name, assertion in required.items():
            with self.subTest(case=name):
                case = cases[name]
                self.assertTrue(case["setup"])
                self.assertTrue(case["prompt"])
                self.assertTrue(case["expected_output"])
                self.assertIn(assertion, "\n".join(case["assertions"]))
        # Failure must be induced by the harness, not alleged in the user's request.
        failure = cases["claude-observed-install-failure-fallback"]
        self.assertIn("actual tool output", failure["setup"])
        self.assertNotIn("install", failure["prompt"])


if __name__ == "__main__":
    unittest.main()
