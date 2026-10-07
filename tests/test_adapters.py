import os
import tempfile
import unittest

from applicant_inbox.adapters import ADAPTERS, DEFAULT_PATHS, agency, board_a, board_b, chat, mail, webform

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sample")


def sample(adapter):
    return os.path.join(SAMPLE, DEFAULT_PATHS[adapter])


def by_id(result):
    return {a.source_id: a for a in result.applications}


class SampleAdapterTests(unittest.TestCase):
    def test_every_adapter_reads_its_sample_without_errors(self):
        counts = {}
        for name, parse in ADAPTERS.items():
            result = parse(sample(name))
            self.assertEqual(result.errors, [], msg=name)
            counts[name] = len(result.applications)
        self.assertEqual(counts, {"webform": 10, "board_a": 5, "board_b": 5, "agency": 3, "chat": 4, "mail": 3})

    def test_webform_normalises_contacts_and_keeps_raw_values(self):
        apps = by_id(webform.parse(sample("webform")))
        hasan = apps["web-007"]
        self.assertEqual(hasan.email, "hasan.beispielmann@example.com")
        self.assertEqual(hasan.raw_email, "Hasan.Beispielmann@Example.com")
        self.assertEqual(hasan.phone, "+498999998011")
        self.assertEqual(hasan.raw_phone, "0049 89 99998 011")
        self.assertEqual(hasan.received_at, "2026-10-06T07:30:27Z")      # 09:30 +02:00
        self.assertEqual(apps["web-009"].phone, "")                      # 'n/a'
        self.assertEqual(apps["web-009"].raw_phone, "n/a")

    def test_board_a_name_with_title_and_comma_is_kept_as_received(self):
        apps = by_id(board_a.parse(sample("board_a")))
        self.assertEqual(apps["A-1002"].name, "Fiktivova, Dr. Iris")
        self.assertEqual(apps["A-1002"].phone, "+493023125012")

    def test_board_b_joins_first_and_last_name_and_reads_german_dates(self):
        apps = by_id(board_b.parse(sample("board_b")))
        self.assertEqual(apps["B-2001"].name, "Clara Müller")
        self.assertEqual(apps["B-2001"].received_at, "2026-10-07T12:03:00Z")

    def test_agency_reads_nested_json(self):
        apps = by_id(agency.parse(sample("agency")))
        self.assertEqual(apps["AG-77"].name, "David Demo")
        self.assertEqual(apps["AG-77"].email, "d.demo@example.com")
        self.assertEqual(apps["AG-77"].phone, "+494066969004")
        self.assertEqual(apps["AG-77"].received_at, "2026-10-08T08:00:00Z")

    def test_chat_skips_system_notices_and_joins_multi_line_messages(self):
        result = chat.parse(sample("chat"))
        self.assertEqual(len(result.applications), 4)
        phone_only = [a for a in result.applications if a.phone == "+498999998020"][0]
        self.assertEqual(phone_only.name, "")
        self.assertIn("Können Sie mich bitte zurückrufen?", phone_only.message)
        self.assertIn("\n", phone_only.message)
        name_only = [a for a in result.applications if a.name == "Kira Probe"][0]
        self.assertEqual(name_only.phone, "")
        self.assertFalse(name_only.has_contact)
        self.assertEqual(phone_only.raw_phone, "+49 89 99998 020")

    def test_chat_ids_are_stable_across_runs(self):
        first = [a.source_id for a in chat.parse(sample("chat")).applications]
        second = [a.source_id for a in chat.parse(sample("chat")).applications]
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 4)

    def test_mail_takes_phone_from_signature_and_name_from_header(self):
        apps = {a.name: a for a in mail.parse(sample("mail")).applications}
        self.assertEqual(apps["David Demo"].phone, "+494066969004")
        self.assertEqual(apps["David Demo"].email, "david.demo@example.net")
        self.assertEqual(apps["Kira Probe"].phone, "+494066969006")
        self.assertEqual(apps["BEISPIELMANN, Hasan"].phone, "")
        self.assertEqual(apps["David Demo"].received_at, "2026-10-07T17:02:11Z")


class ChatEdgeCaseTests(unittest.TestCase):
    def test_system_notice_between_messages_is_not_glued_to_the_previous_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "chat.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("05.10.26, 14:32 - +49 30 23125001: Erste Nachricht\n"
                             "05.10.26, 14:33 - Ann hat die Gruppe verlassen\n"
                             "05.10.26, 14:40 - +49 30 23125001: Zweite Nachricht\n")
            result = chat.parse(path)
        self.assertEqual([a.message for a in result.applications], ["Erste Nachricht", "Zweite Nachricht"])


class ErrorHandlingTests(unittest.TestCase):
    """One broken record must be reported, not abort the import and not hide the good ones."""

    def _write(self, directory, name, text):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_webform_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "w.jsonl",
                               '{"id": "1", "submitted": "2026-10-05T09:00:00+02:00", "fullName": "A B"}\n'
                               'this is not json\n'
                               '{"id": "3"}\n'
                               '\n')
            result = webform.parse(path)
        self.assertEqual(len(result.applications), 1)
        self.assertEqual(len(result.errors), 2)
        self.assertTrue(result.errors[0].startswith("line 2"))

    def test_csv_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "a.csv",
                               "Application ID,Date,Candidate,Email,Phone,Cover note\n"
                               "A-1,2026-10-05,Ann Example,ann@example.com,,\n"
                               "A-2,05/10/2026,Ben Example,ben@example.com,,\n")
            result = board_a.parse(path)
        self.assertEqual([a.source_id for a in result.applications], ["A-1"])
        self.assertTrue(result.errors[0].startswith("row 3"))

    def test_mail_without_from_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "broken.eml", "Subject: no sender\n\nbody\n")
            self._write(tmp, "notes.txt", "ignored")
            result = mail.parse(tmp)
        self.assertEqual(result.applications, [])
        self.assertEqual(len(result.errors), 1)


if __name__ == "__main__":
    unittest.main()
