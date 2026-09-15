"""Keep the current contributor entry points navigable without a network call."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class CurrentDocumentationTests(unittest.TestCase):
    def test_current_markdown_links_resolve_inside_repository(self):
        for name in ('README.md', 'CONTRIBUTING.md', 'docs/README.md', 'docs/CONSOLIDATION.md', 'docs/TRANSITION_LAB.md'):
            path = ROOT / name
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                with self.subTest(document=name, link=link):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f'Missing contributor link: {target}')

    def test_main_and_release_are_not_conflated(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('Development source: `main`', readme)
        self.assertIn('v0.5.0', readme)
        self.assertNotIn('Development branch:', readme)
