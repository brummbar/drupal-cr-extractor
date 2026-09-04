import unittest

from cr_extractor.classify import classify, parse_target, version_sort_key


class ClassifyTests(unittest.TestCase):
    def test_combinations_seen_in_api(self):
        cases = {
            ("11.5.x", "11.5.0"): (11, 5),
            ("main", "11.5.0"): (11, 5),
            ("12.0.x", "12.0.0-beta1"): (12, 0),
            ("main", "12.0"): (12, 0),
            ("11.4.x", "11.x"): (11, 4),
            ("11.5.x", ""): (11, 5),
            ("10.6.x", "10.6.16"): (10, 6),
            ("main", "12.x"): None,
            ("main", ""): None,
            ("main", None): None,
            (None, None): None,
        }
        for (branch, version), expected in cases.items():
            with self.subTest(branch=branch, version=version):
                self.assertEqual(classify(branch, version), expected)

    def test_version_wins_over_branch(self):
        self.assertEqual(classify("12.0.x", "11.5.0"), (11, 5))

    def test_parse_target(self):
        self.assertEqual(parse_target("11.2"), (11, 2))
        self.assertEqual(parse_target(" 10.0 "), (10, 0))
        for bad in ("11", "11.2.x", "11.2.0", "abc", ""):
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, parse_target, bad)

    def test_version_sort_key(self):
        ordered = ["11.2.0-alpha1", "11.2.0-beta1", "11.2.0-beta2", "11.2.0-rc1", "11.2.0", "11.2.6", "11.10.0", "11.x", ""]
        shuffled = list(reversed(ordered))
        self.assertEqual(sorted(shuffled, key=version_sort_key), ordered)


if __name__ == "__main__":
    unittest.main()
