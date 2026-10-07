import contextlib
import csv
import io
import os
import random
import tempfile
import unittest

from applicant_inbox.adapters import ADAPTERS, DEFAULT_PATHS
from applicant_inbox.cli import main
from applicant_inbox.dedupe import cluster, possible_duplicates
from applicant_inbox.models import Application
from applicant_inbox.store import Store

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sample")


def load_sample():
    applications = []
    for name, parse in ADAPTERS.items():
        applications += parse(os.path.join(SAMPLE, DEFAULT_PATHS[name])).applications
    return applications


def app(source_id, name="", email="", phone="", received="2026-10-05T10:00:00Z", source="test"):
    return Application.build(source, source_id, received, name, email, phone)


def groups(candidates):
    return sorted(sorted(c.application_keys) for c in candidates)


class SampleClusteringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.applications = load_sample()
        cls.candidates = cluster(cls.applications)

    def summary(self):
        return {(c.name, tuple(c.sources), c.applications, c.needs_review) for c in self.candidates}

    def test_totals(self):
        self.assertEqual(len(self.applications), 30)
        self.assertEqual(len(self.candidates), 18)

    def test_expected_merges(self):
        merged = {(c.name, tuple(c.sources), c.applications) for c in self.candidates if c.applications > 1}
        self.assertEqual(merged, {
            ("Anna Beispiel", ("board_a", "chat", "webform"), 3),     # e-mail link + phone link
            ("Ben Muster", ("board_a", "webform"), 2),                # different e-mails, same phone
            ("Clara Mueller", ("board_b", "webform"), 2),             # Müller vs Mueller
            ("Elif Testfrau", ("webform",), 2),                       # double submit
            ("Hasan Beispielmann", ("mail", "webform"), 2),           # case + 'LAST, First'
            ("Iris Fiktivova", ("board_a", "webform"), 2),            # title + 'Last, First'
            ("David Demo", ("agency", "mail"), 2),                    # phone from the mail signature
            ("Gina Probe", ("board_a", "board_b"), 2),
            ("Kira Probe", ("chat", "mail"), 2),                      # phone-only chat message
            ("Ida Muster", ("agency", "chat", "webform"), 3),         # bridged by a nameless chat message
        })

    def test_shared_phone_of_two_people_is_not_merged(self):
        felix = [c for c in self.candidates if c.name == "Felix Fiktiv"]
        franka = [c for c in self.candidates if c.name == "Franka Fiktiv"]
        self.assertEqual((len(felix), len(franka)), (1, 1))
        self.assertNotEqual(felix[0].candidate_id, franka[0].candidate_id)
        self.assertEqual(felix[0].phones, franka[0].phones)

    def test_shared_generic_mailbox_is_not_merged(self):
        mia = [c for c in self.candidates if c.name == "Mia Beispiel"][0]
        nico = [c for c in self.candidates if c.name == "Nico Probe"][0]
        self.assertEqual(mia.emails, nico.emails)
        self.assertNotEqual(mia.candidate_id, nico.candidate_id)

    def test_nameless_message_bridging_two_people_is_flagged(self):
        flagged = [c for c in self.candidates if c.needs_review]
        self.assertEqual(len(flagged), 1)
        keys = " ".join(flagged[0].application_keys)
        self.assertIn("webform:web-010", keys)    # Ida Muster
        self.assertIn("agency:AG-79", keys)       # Jan Muster
        self.assertEqual(sum(1 for c in self.candidates if c.needs_review), 1)

    def test_same_name_without_shared_contact_is_reported_not_merged(self):
        names = sorted(group[0].name for group in possible_duplicates(self.candidates))
        self.assertEqual(names, ["Kira Probe", "Leon Testmann"])
        self.assertEqual(sum(1 for c in self.candidates if c.name == "Leon Testmann"), 2)

    def test_one_candidate_name_picks_the_complete_spelling(self):
        names = {c.name for c in self.candidates}
        self.assertIn("Iris Fiktivova", names)          # not 'Fiktivova, Dr. Iris'
        self.assertIn("Hasan Beispielmann", names)      # not 'BEISPIELMANN, Hasan'


class PossibleDuplicatesTests(unittest.TestCase):
    def test_single_word_names_are_too_weak_to_report(self):
        candidates = cluster([app("1", "Madonna", "a@example.com"), app("2", "Madonna", "b@example.com")])
        self.assertEqual(len(candidates), 2)
        self.assertEqual(possible_duplicates(candidates), [])

    def test_full_names_are_reported(self):
        candidates = cluster([app("1", "Ann Example", "a@example.com"), app("2", "Ann Example", "b@example.com")])
        self.assertEqual(len(possible_duplicates(candidates)), 1)


class ClusteringPropertyTests(unittest.TestCase):
    def test_result_does_not_depend_on_input_order(self):
        applications = load_sample()
        expected = groups(cluster(applications))
        rng = random.Random(7)
        for _ in range(25):
            shuffled = applications[:]
            rng.shuffle(shuffled)
            self.assertEqual(groups(cluster(shuffled)), expected)

    def test_candidate_id_survives_a_later_duplicate(self):
        first = app("1", "Ann Example", "ann@example.com", received="2026-10-05T10:00:00Z")
        before = cluster([first])
        later = app("2", "Ann Example", "ann@example.com", received="2026-10-09T10:00:00Z", source="other")
        after = cluster([first, later])
        self.assertEqual(len(after), 1)
        self.assertEqual(before[0].candidate_id, after[0].candidate_id)

    def test_links_are_transitive(self):
        a = app("a", "Ann Example", "ann@example.com", "")
        b = app("b", "Ann Example", "ann@example.com", "030 23125 001")
        c = app("c", "A. Example", "", "030 23125 001")
        self.assertEqual(len(cluster([a, b, c])), 1)

    def test_no_contact_means_no_link(self):
        self.assertEqual(len(cluster([app("a", "Ann Example"), app("b", "Ann Example")])), 2)

    def test_empty_input(self):
        self.assertEqual(cluster([]), [])


class StoreTests(unittest.TestCase):
    def test_ingest_is_idempotent(self):
        store = Store()
        applications = load_sample()
        self.assertEqual(store.add_applications(applications), (30, 0))
        self.assertEqual(store.add_applications(load_sample()), (0, 30))
        self.assertEqual(len(store.applications()), 30)
        self.assertEqual(dict(store.counts_by_source())["webform"], 10)

    def test_candidates_round_trip_and_are_rebuilt_not_appended(self):
        store = Store()
        store.add_applications(load_sample())
        store.replace_candidates(cluster(store.applications()))
        store.replace_candidates(cluster(store.applications()))
        stored = store.candidates()
        self.assertEqual(len(stored), 18)
        anna = [c for c in stored if c.name == "Anna Beispiel"][0]
        self.assertEqual(anna.emails, ["anna.beispiel@example.com"])
        self.assertEqual(anna.phones, ["+493023125001"])
        self.assertFalse(anna.needs_review)


def run_cli(*args):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(list(args))
    return code, buffer.getvalue()


class CliTests(unittest.TestCase):
    def test_demo_then_reimport_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "inbox.db")
            code, out = run_cli("--db", db, "demo", SAMPLE)
            self.assertEqual(code, 0)
            self.assertIn("30 applications from 6 sources -> 18 candidates (12 duplicates merged, 1 group(s) need review)", out)
            self.assertIn("Possible duplicates", out)
            code, again = run_cli("--db", db, "demo", SAMPLE)
            self.assertIn("30 applications from 6 sources -> 18 candidates", again)
            self.assertEqual(again.count("0 new, 5 already known") + again.count("0 new, 10 already known")
                             + again.count("0 new, 3 already known") + again.count("0 new, 4 already known"), 6)

    def test_single_ingest_merge_report_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "inbox.db")
            run_cli("--db", db, "ingest", "webform", os.path.join(SAMPLE, "webform.jsonl"))
            _, out = run_cli("--db", db, "merge")
            self.assertIn("9 candidates", out)      # Elif's double submit collapses
            target = os.path.join(tmp, "candidates.csv")
            run_cli("--db", db, "export", "--out", target)
            with open(target, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 9)
            self.assertEqual(rows[0]["sources"], "webform")


if __name__ == "__main__":
    unittest.main()
