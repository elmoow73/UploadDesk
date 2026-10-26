import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from ir52_article import extract_article, validate_url, validate_article_url


class ExtractionTests(unittest.TestCase):
    def test_supplied_example_matches(self):
        parent = Path(__file__).resolve().parents[2]
        sources = list(parent.glob('*예시 html.txt'))
        expected = list(parent.glob('*업로드 형식.txt'))
        if not sources or not expected:
            self.skipTest('External examples not present')
        article = extract_article(sources[0].read_text(encoding='utf-8-sig'), 'https://www.mk.co.kr/news/it/12166326')
        normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
        self.assertEqual(normalize(article.preview()), normalize(expected[0].read_text(encoding='utf-8-sig')))
        self.assertEqual(sum(k == 'image' for k, v in article.parts), 1)
        self.assertNotIn('Advertisement', article.body_html())
        self.assertNotIn('<script', article.body_html())

    def test_missing_body(self):
        with self.assertRaises(ValueError):
            extract_article('<html>not an article</html>', 'https://www.mk.co.kr/')

    def test_invalid_urls(self):
        for value in ('file:///a', 'javascript:alert(1)', 'https://user:pass@example.com'):
            with self.assertRaises(ValueError):
                validate_url(value)

    def test_mk_domains_only(self):
        for value in ('https://www.mk.co.kr/news/1', 'https://m.mk.co.kr/news/1', 'https://mk.co.kr/news/1'):
            self.assertEqual(validate_article_url(value), value)
        from ir52_article import fetch_article
        for value in ('https://example.com/', 'https://mk.co.kr.evil.com/', 'https://fake-mk.co.kr/'):
            with patch('ir52_article.open_article_url') as fetch:
                with self.assertRaisesRegex(ValueError, '매일경제 사이트가 아닙니다'):
                    fetch_article(value)
                fetch.assert_not_called()

    def test_http_403_uses_browser(self):
        from ir52_article import fetch_article
        with patch('ir52_article.open_article_url', side_effect=HTTPError('https://www.mk.co.kr/', 403, 'Forbidden', {}, None)), patch('ir52_article.fetch_with_browser', return_value='article') as browser:
            self.assertEqual(fetch_article('https://www.mk.co.kr/'), 'article')
            browser.assert_called_once()

    def test_http_404_reports_code_without_retry(self):
        from ir52_article import fetch_article
        with patch('ir52_article.open_article_url', side_effect=HTTPError('https://www.mk.co.kr/', 404, 'Not Found', {}, None)), patch('ir52_article.fetch_with_browser') as browser:
            with self.assertRaisesRegex(ValueError, 'HTTP 404'):
                fetch_article('https://www.mk.co.kr/')
            browser.assert_not_called()

    def test_ui(self):
        from PySide6.QtWidgets import QApplication
        from ir52_app import Window
        app = QApplication.instance() or QApplication([])
        window = Window()
        self.assertFalse(hasattr(window, 'file'))
        self.assertFalse(hasattr(window, 'image_path'))
        self.assertFalse(window.run.isEnabled())
        window.close()


if __name__ == '__main__':
    unittest.main()
