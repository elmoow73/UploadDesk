import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import MagicMock, patch
from press_document import prepare_document, DocumentError


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_login_navigation_related_prepare_fill_order(self):
        from app import LoginWorker
        events = []
        worker = LoginWorker('dummy-id', 'dummy-pw', 'example.hwpx', '제목', True, ('selected',))
        pw_manager, browser, page, admin = (MagicMock() for _ in range(4))
        pw_manager.__enter__.return_value.chromium.launch.return_value = browser
        browser.new_context.return_value.new_page.return_value = page
        admin.is_closed.return_value = True
        with patch('playwright.sync_api.sync_playwright', return_value=pw_manager), \
             patch('app.attempt', side_effect=lambda *args: events.append('login') or True), \
             patch('app.open_registration', side_effect=lambda *args: events.append('navigate') or admin), \
             patch('app.fill_related_sites', side_effect=lambda *args: events.append('related') or True), \
             patch('app.prepare_document', side_effect=lambda *args: events.append('prepare') or ('2026-10-20', '<p>body</p>', (724, 1024))), \
             patch('app.fill_registration', side_effect=lambda *args: events.append('fill') or True):
            worker.run()
        self.assertEqual(events, ['login', 'navigate', 'prepare', 'fill', 'related'])
        self.assertEqual(worker.username, '')
        self.assertEqual(worker.password, '')

    def test_body_failure_does_not_fill_related_sites(self):
        from app import LoginWorker
        worker = LoginWorker('dummy-id', 'dummy-pw', 'example.hwpx', '제목', True, ('selected',))
        with patch('app.prepare_document', return_value=('2026-10-20', '<p>body</p>', (724, 1024))), \
             patch('app.fill_registration', return_value=False), \
             patch('app.fill_related_sites') as related:
            worker.populate_registration(MagicMock())
        related.assert_not_called()

    def test_preparation_failure_preserves_browser_and_specific_diagnostic(self):
        from app import LoginWorker
        worker = LoginWorker('dummy-id', 'dummy-pw', 'example.hwpx', '제목', True)
        page = MagicMock()
        messages = []
        worker.status.connect(messages.append)
        with patch('app.prepare_document', side_effect=DocumentError('온라인 보도일을 하나로 확정할 수 없습니다.')), \
             patch('app.fill_registration') as fill:
            worker.populate_registration(page)
        fill.assert_not_called()
        page.close.assert_not_called()
        self.assertIn('온라인 보도일', messages[-1])
        self.assertNotIn('dummy-pw', ' '.join(messages))

    def test_navigation_failure_never_prepares_document(self):
        from app import LoginWorker
        worker = LoginWorker('dummy-id', 'dummy-pw', 'example.hwpx', '제목', True)
        manager, page = MagicMock(), MagicMock()
        manager.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = page
        page.is_closed.return_value = True
        with patch('playwright.sync_api.sync_playwright', return_value=manager), \
             patch('app.attempt', return_value=True), \
             patch('app.open_registration', return_value=None), \
             patch('app.prepare_document') as prepare, patch('app.fill_registration') as fill:
            worker.run()
        prepare.assert_not_called()
        fill.assert_not_called()

    def test_real_sample_in_background_thread_without_file_writes(self):
        sample = Path('C:/Users/21017/Desktop/★★★ 업무/★★★ 언론보도/★★★ 보도자료/261020_외국인 연구인력 보도자료/최종/우리 기업의 외국인 연구인력 활용 실태 보고서 발간 보도자료.hwpx')
        if not sample.is_file():
            self.skipTest('Example HWPX not available')
        with patch('pathlib.Path.write_bytes', side_effect=AssertionError('No JPEG file writes expected')):
            with ThreadPoolExecutor(max_workers=1) as pool:
                publication_date, body, dimensions = pool.submit(prepare_document, sample).result(timeout=15)
        self.assertEqual(publication_date, '2026-10-20')
        self.assertEqual(dimensions, (700, 990))
        self.assertIn('data:image/jpeg;base64,', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
