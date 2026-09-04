import unittest

from cr_extractor.render import html_to_markdown, render_record


class RenderTests(unittest.TestCase):
    def test_code_block_language_and_heading_demotion(self):
        html = '<h2>Before</h2><p>Text</p><pre class="codeblock"><code class="language-php">$a = 1;\n</code></pre>'
        md = html_to_markdown(html)
        self.assertIn("##### Before", md)
        self.assertIn("```php\n$a = 1;\n```", md)
        self.assertNotIn("<p>", md)

    def test_comments_in_code_are_not_demoted(self):
        html = '<pre><code># comment line\nRewriteCond %{REQUEST_URI}\n</code></pre>'
        md = html_to_markdown(html)
        self.assertEqual(md, "```\n# comment line\nRewriteCond %{REQUEST_URI}\n```")

    def test_render_record(self):
        node = {
            "nid": "1", "title": "Thing removed", "url": "https://www.drupal.org/node/1",
            "field_change_to": "11.2.6", "field_change_to_branch": "11.2.x",
            "field_impacts": ["2", "9"], "field_issue_links": [{"url": "https://www.drupal.org/node/2"}],
            "author": {"name": "someone"}, "created": 1758091226, "changed": 1761789366,
            "field_description": {"value": "<p>Gone &amp; done.</p>"},
        }
        md = render_record(node)
        self.assertIn("### Thing removed", md)
        self.assertIn("- Introduced in: 11.2.6 (branch 11.2.x)", md)
        self.assertIn("- Impacts: Module developers, impact:9", md)
        self.assertIn("- Issues: https://www.drupal.org/node/2", md)
        self.assertIn("created 2025-09-17", md)
        self.assertIn("Gone & done.", md)


if __name__ == "__main__":
    unittest.main()


class SelectionTests(unittest.TestCase):
    def _store(self, versions):
        from cr_extractor.classify import classify
        class FakeStore:
            def iter_records(self_inner):
                for i, (branch, version) in enumerate(versions):
                    yield {"nid": str(i), "field_change_to_branch": branch, "field_change_to": version,
                           "field_change_record_status": True, "created": i, "title": f"cr{i}"}
        return FakeStore()

    def test_from_is_exclusive_and_spans_majors(self):
        from cr_extractor.render import covered_versions, select_records
        store = self._store([("10.4.x", "10.4.0"), ("10.5.x", "10.5.0"), ("10.6.x", "10.6.1"),
                             ("11.0.x", "11.0.0"), ("11.1.x", "11.1.0"), ("11.2.x", "11.2.0"), ("11.3.x", "11.3.0")])
        by_version, _, _ = select_records(store, (11, 2), (10, 4))
        self.assertEqual(sorted(by_version), [(10, 5), (10, 6), (11, 0), (11, 1), (11, 2)])
        self.assertEqual(covered_versions((11, 2), (10, 4), by_version), [(10, 5), (10, 6), (11, 0), (11, 1), (11, 2)])
        by_version, _, _ = select_records(store, (11, 2), (11, 1))
        self.assertEqual(sorted(by_version), [(11, 2)])
        by_version, _, _ = select_records(store, (11, 2), None)
        self.assertEqual(sorted(by_version), [(11, 0), (11, 1), (11, 2)])
        self.assertEqual(covered_versions((11, 3), (11, 0), {}), [(11, 1), (11, 2), (11, 3)])
