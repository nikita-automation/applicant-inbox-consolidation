import unittest
from datetime import datetime

from applicant_inbox import normalize as n


class PhoneTests(unittest.TestCase):
    def test_formats_that_must_collapse_to_one_number(self):
        variants = ["030 23125 001", "+49 30 23125001", "+49 (0) 30 23125 001", "0049 30 23125001",
                    "030/23125-001", "49 30 23125001", "+49 030 23125001"]
        self.assertEqual({n.normalize_phone(v) for v in variants}, {"+493023125001"})

    def test_other_numbers(self):
        self.assertEqual(n.normalize_phone("0221 4710 002"), "+492214710002")
        self.assertEqual(n.normalize_phone("0049 89 99998 011"), "+498999998011")
        self.assertEqual(n.normalize_phone("+49 0151 2345678"), "+491512345678")   # typo '+49 0'
        self.assertEqual(n.normalize_phone("+380 44 123 4567"), "+380441234567")   # foreign numbers stay

    def test_unusable_values_become_empty_not_guesses(self):
        for bad in (None, "", "n/a", "123", "0123", "abc", "12345678", "+1"):
            self.assertEqual(n.normalize_phone(bad), "", msg=repr(bad))

    def test_phone_in_free_text_needs_a_label_or_plus(self):
        self.assertEqual(n.find_phone_in_text("Viele Grüße\nTel.: +49 (0)40 66969 004"), "+494066969004")
        self.assertEqual(n.find_phone_in_text("Mobil 040 66969 006"), "+494066969006")
        self.assertEqual(n.find_phone_in_text("Erreichbar unter +49 40 66969 007 ab 18 Uhr"), "+494066969007")
        self.assertEqual(n.find_phone_in_text("Bewerbung vom 05.10.2026, bitte bis 12.10.2026 antworten"), "")
        self.assertEqual(n.find_phone_in_text(""), "")


    def test_length_limits_are_inclusive(self):
        self.assertEqual(n.normalize_phone("+12345678"), "+12345678")                       # 8 digits
        self.assertEqual(n.normalize_phone("+1234567"), "")                                 # 7
        self.assertEqual(n.normalize_phone("+123456789012345"), "+123456789012345")         # 15
        self.assertEqual(n.normalize_phone("+1234567890123456"), "")                        # 16


class EmailTests(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(n.normalize_email(" Hasan.Beispielmann@Example.com "), "hasan.beispielmann@example.com")
        self.assertEqual(n.normalize_email("mailto:A@B.de"), "a@b.de")
        self.assertEqual(n.normalize_email("<a@b.de>"), "a@b.de")

    def test_dots_and_plus_tags_are_preserved(self):
        self.assertNotEqual(n.normalize_email("a.b@x.de"), n.normalize_email("ab@x.de"))
        self.assertEqual(n.normalize_email("ab+job@x.de"), "ab+job@x.de")

    def test_invalid_values(self):
        for bad in (None, "", "not-an-email", "a@b", "a b@c.de"):
            self.assertEqual(n.normalize_email(bad), "", msg=repr(bad))


class NameTests(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(n.name_tokens("Müller, Dr. Clara"), ["clara", "mueller"])
        self.assertEqual(n.name_tokens("Clara Mueller"), ["clara", "mueller"])
        self.assertEqual(n.name_tokens("José  Núñez"), ["jose", "nunez"])
        self.assertEqual(n.name_tokens(""), [])
        self.assertEqual(n.name_tokens(None), [])

    def test_compatible_pairs(self):
        pairs = [("Anna Beispiel", "Anna Beispiel"), ("Clara Müller", "Clara Mueller"),
                 ("Anna Beispiel", "A. Beispiel"), ("Anna Beispiel", "Beispiel, Anna-Lena"),
                 ("Hasan Beispielmann", "BEISPIELMANN, Hasan"), ("Muster Ben", "Ben Muster"),
                 ("Anna Beispiel", ""), ("", ""), ("Kira Probe", "Kira Probe-Muster")]
        for a, b in pairs:
            self.assertTrue(n.names_compatible(a, b), msg="%r ~ %r" % (a, b))
            self.assertTrue(n.names_compatible(b, a), msg="%r ~ %r (reversed)" % (b, a))

    def test_incompatible_pairs(self):
        pairs = [("Ida Muster", "Jan Muster"), ("Felix Fiktiv", "Franka Fiktiv"),
                 ("Gina Probe", "Nico Probe"), ("Anna Beispiel", "Mia Beispiel"),
                 ("Anna Beispiel", "Anna Muster"), ("B. Muster", "Anna Muster")]
        for a, b in pairs:
            self.assertFalse(n.names_compatible(a, b), msg="%r !~ %r" % (a, b))
            self.assertFalse(n.names_compatible(b, a), msg="%r !~ %r (reversed)" % (b, a))

    def test_name_key_ignores_order_and_spelling(self):
        self.assertEqual(n.name_key("Clara Müller"), n.name_key("Mueller, Clara"))


class TimeTests(unittest.TestCase):
    @unittest.skipIf(n._LOCAL is None, "no time zone database")
    def test_naive_timestamps_are_berlin_local(self):
        self.assertEqual(n.to_utc_iso(datetime(2026, 10, 5, 14, 3)), "2026-10-05T12:03:00Z")   # CEST
        self.assertEqual(n.to_utc_iso(datetime(2026, 11, 5, 14, 3)), "2026-11-05T13:03:00Z")   # CET


if __name__ == "__main__":
    unittest.main()
