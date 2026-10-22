import hashlib
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from news_catalog import Article, load_articles, NEWS_ROOT


class NewsTests(unittest.TestCase):
    def test_actual_database_read_does_not_modify_file(self):
        path = NEWS_ROOT / 'koita_news.sqlite'
        before = hashlib.sha256(path.read_bytes()).digest()
        articles, _ = load_articles()
        self.assertGreaterEqual(len(articles), 3)
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).digest())
        self.assertEqual(len({article.key for article in articles}), len(articles))

    def test_bad_values_excluded_and_same_url_types_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            with closing(sqlite3.connect(Path(temporary) / 'koita_news.sqlite')) as db:
                db.execute('CREATE TABLE news(seq, date, press, type, title, url)')
                db.executemany('INSERT INTO news VALUES (?, ?, ?, ?, ?, ?)', [
                    (1, '2026-10-20', 'KBS', '방송', '기사', 'https://example.com/a'),
                    (2, '2026-10-20', 'KBS', '온라인', '기사', 'https://example.com/a'),
                    (3, '2026-10-20', '출처', '온라인', '기사', 'javascript:alert(1)'),
                ])
                db.commit()
            articles, skipped = load_articles(temporary)
            self.assertEqual(len(articles), 2)
            self.assertEqual(skipped, 1)
            self.assertEqual({article.kind for article in articles}, {'방송', '온라인'})

    def test_dialog_checkbox_search_cancel_and_restore(self):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from news_dialog import NewsDialog
        app = QApplication.instance() or QApplication([])
        articles, _ = load_articles()
        with patch('news_dialog.load_articles', return_value=(articles, 0)):
            dialog = NewsDialog()
            for index in range(3):
                dialog.table.item(index, 0).setCheckState(Qt.CheckState.Checked)
            selected = dialog.checked_articles()
            self.assertEqual(len(selected), 3)
            dialog.search.setText('no matching article at all')
            self.assertEqual(dialog.checked_articles(), selected)
            dialog.reload()
            self.assertEqual(dialog.checked_articles(), selected)
            restored = NewsDialog(selected)
            self.assertEqual(restored.checked_articles(), selected)
            dialog.reject()
            self.assertEqual(dialog.result(), 0)
            dialog.close()
            restored.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
