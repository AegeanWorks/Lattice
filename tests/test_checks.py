"""The integrity gate catches broken provenance, endpoints, duplicates and cycles."""

import unittest

from lattice.checks import run_checks
from lattice.database import open_database
from lattice.repository import Repository


class CheckTests(unittest.TestCase):
    """Each test injects one defect into an otherwise clean graph."""

    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.repository = Repository(self.connection)
        self.paper, _ = self.repository.add_paper({
            "title": "Clean paper",
            "doi": "10.1/clean",
            "abstract": ("A quote Loose quote Second quote Second about sleep improves "
                         "recall across participants."),
        })
        self.claim = self.repository.add_claim(
            self.paper.id, "A claim", "A quote", locator="page 4")
        self.question = self.repository.add_question("A question?")
        self.repository.add_edge(self.claim.id, self.question.id, "supports")

    def test_clean_graph_passes(self):
        report = run_checks(self.repository)
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual(report.errors, [])

    def test_warning_for_unlinked_claim(self):
        extra = self.repository.add_claim(self.paper.id, "Loose claim", "Loose quote", locator="page 5")
        report = run_checks(self.repository)
        self.assertTrue(report.passed)
        self.assertIn("claim.unlinked", [issue.code for issue in report.warnings])
        self.assertIn(extra.id, " ".join(issue.message for issue in report.warnings))

    def test_cycle_is_an_error(self):
        second = self.repository.add_claim(self.paper.id, "Second", "Second quote", locator="page 6")
        self.repository.add_edge(self.claim.id, second.id, "supports")
        self.repository.add_edge(second.id, self.claim.id, "supports")
        report = run_checks(self.repository)
        self.assertFalse(report.passed)
        self.assertIn("edge.support_cycle", [issue.code for issue in report.errors])

    def test_missing_endpoint_is_an_error(self):
        self.connection.execute(
            "INSERT INTO edges(src, dst, kind, note, created_at) VALUES(?, ?, ?, '', 'now')",
            ("claim:c_999999", f"question:{self.question.id}", "supports"))
        report = run_checks(self.repository)
        self.assertIn("edge.endpoint", [issue.code for issue in report.errors])

    def test_empty_quote_is_an_error(self):
        self.connection.execute("UPDATE claims SET quote = '' WHERE id = ?", (self.claim.id,))
        report = run_checks(self.repository)
        self.assertIn("claim.provenance", [issue.code for issue in report.errors])

    def test_doi_duplicate_is_an_error(self):
        self.connection.execute("DROP INDEX papers_doi")
        self.connection.execute(
            "INSERT INTO papers(id, kind, title, authors, year, venue, doi, arxiv, url, abstract,"
            " created_at) VALUES('p_other', 'paper', 'Other', '', '', '', '10.1/clean', '', '', '', 'now')")
        report = run_checks(self.repository)
        self.assertIn("paper.duplicate_doi", [issue.code for issue in report.errors])

    def test_question_without_evidence_is_a_warning(self):
        empty = self.repository.add_question("Unanswered?")
        report = run_checks(self.repository)
        self.assertTrue(report.passed)
        self.assertIn(empty.id, " ".join(issue.message for issue in report.warnings))

    def test_missing_locator_is_an_error(self):
        self.connection.execute("UPDATE claims SET locator = '' WHERE id = ?", (self.claim.id,))
        report = run_checks(self.repository)
        self.assertFalse(report.passed)
        self.assertIn("claim.locator_missing", [issue.code for issue in report.errors])

    def test_drifted_quote_is_an_error(self):
        self.connection.execute("UPDATE claims SET quote = 'fabricated drifted sentence' WHERE id = ?",
                                (self.claim.id,))
        report = run_checks(self.repository)
        self.assertFalse(report.passed)
        self.assertIn("claim.quote_drift", [issue.code for issue in report.errors])

    def test_rotted_abstract_locator_is_an_error(self):
        self.connection.execute("UPDATE claims SET locator = 'abstract:s9999' WHERE id = ?",
                                (self.claim.id,))
        report = run_checks(self.repository)
        self.assertFalse(report.passed)
        self.assertIn("claim.locator_unresolvable", [issue.code for issue in report.errors])

    def test_abstract_locator_after_neutral_sentences_resolves(self):
        paper, _ = self.repository.add_paper({
            "title": "Locator slots",
            "abstract": ("Background. This paper studies sleep. Slow-wave sleep increased "
                         "recall accuracy by 28% compared with wakeful rest."),
        })
        claim = self.repository.add_claim(
            paper.id, "Sleep improved recall",
            "Slow-wave sleep increased recall accuracy by 28% compared with wakeful rest.",
            locator="abstract:s3")
        self.repository.add_edge(claim.id, self.question.id, "supports")
        report = run_checks(self.repository)
        codes = [issue.code for issue in report.errors]
        self.assertNotIn("claim.locator_unresolvable", codes, report.to_dict())

    def test_malformed_edge_is_reported_instead_of_raising(self):
        self.connection.execute(
            "INSERT INTO edges(src, dst, kind, note, created_at) VALUES(?, ?, ?, '', 'now')",
            ("garbage", f"question:{self.question.id}", "supports"))
        report = run_checks(self.repository)
        self.assertFalse(report.passed)
        self.assertIn("edge.endpoint", [issue.code for issue in report.errors])

    def test_reject_claim_without_locator_at_write_time(self):
        from lattice.errors import LatticeError
        with self.assertRaises(LatticeError):
            self.repository.add_claim(self.paper.id, "No locator", "A quote", locator="")


if __name__ == "__main__":
    unittest.main()
