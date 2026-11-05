"""Wave 21 hardening: bool-safe integer triads and brief provenance."""

import unittest

from lattice.analysis import find_path, related_findings
from lattice.context import outline
from lattice.database import open_database
from lattice.discovery import DiscoveryService
from lattice.errors import LatticeError
from lattice.inquiry import ask, brief
from lattice.mcp import _int, dispatch_tool, get_prompt
from lattice.models import derive_tags, parse_confidence
from lattice.repository import Repository


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.repository = Repository(self.connection)
        paper, _ = self.repository.add_paper({
            "title": "Sleep and memory", "authors": "A. Researcher", "year": "2021",
            "abstract": "Sleep consolidates memory. We found no effect."})
        self.paper = paper
        support = self.repository.add_claim(
            paper.id, "Sleep consolidates memory", "Sleep consolidates memory.",
            locator="abstract:s1", stance="supports", confidence=0.9)
        self.claim = support
        self.question = self.repository.add_question("Does sleep consolidate memory?")
        self.repository.add_edge(support.id, self.question.id, "supports")

    def test_brief_question_mode_carries_locator(self):
        result = brief(self.repository, self.question.id, tokens=2000)
        self.assertIn("locator: abstract:s1", result["text"])
        self.assertIn("quote:", result["text"])

    def test_bool_integers_fail_with_lattice_error(self):
        service = DiscoveryService(self.repository)
        cases = [
            lambda: service.discover("sleep", source="offline", limit=True, ingest=False),
            lambda: ask(self.repository, "sleep", limit=True),
            lambda: brief(self.repository, self.question.id, tokens=True),
            lambda: self.repository.search("sleep", limit=True),
            lambda: self.repository.search_literature(limit=True),
            lambda: self.repository.subgraph(f"question:{self.question.id}", depth=True),
            lambda: outline(self.repository, tokens=True),
            lambda: parse_confidence(True),
            lambda: derive_tags("title", "abstract", limit=True),
            lambda: _int({"limit": True}, "limit", 10),
            lambda: dispatch_tool(self.repository, "search", {"query": "sleep", "limit": True}),
            lambda: get_prompt(self.repository, "literature-synthesis",
                               {"target": "x", "tokens": True}),
            lambda: find_path(self.repository, "paper:p_x", "paper:p_y", max_depth=True),
        ]
        for idx, fn in enumerate(cases):
            with self.subTest(case=idx), self.assertRaises(LatticeError):
                fn()

    def test_string_integers_fail_with_lattice_error(self):
        service = DiscoveryService(self.repository)
        cases = [
            lambda: service.discover("sleep", source="offline", limit="abc", ingest=False),
            lambda: ask(self.repository, "sleep", limit="abc"),
            lambda: brief(self.repository, self.question.id, tokens="abc"),
            lambda: self.repository.search("sleep", limit="abc"),
            lambda: self.repository.search_literature(limit="abc"),
            lambda: self.repository.subgraph(f"question:{self.question.id}", depth="abc"),
            lambda: outline(self.repository, tokens="abc"),
            lambda: parse_confidence("abc"),
            lambda: derive_tags("title", "abstract", limit="abc"),
            lambda: related_findings(self.repository, f"question:{self.question.id}",
                                     limit="abc"),
        ]
        for idx, fn in enumerate(cases):
            with self.subTest(case=idx), self.assertRaises(LatticeError):
                fn()


if __name__ == "__main__":
    unittest.main()
