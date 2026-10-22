import importlib.util
import os
import threading
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
from pathlib import Path
from backend import trusted_url, load_config, attempt, open_registration, find_admin_menu


class BackendTests(unittest.TestCase):
    def test_hidden_admin_menu_opens_myoffice_before_return(self):
        page, frame = MagicMock(), MagicMock()
        frame.url = 'https://gw.koita.or.kr/menu'
        page.frames = [frame]
        candidates, offices, office, candidate = (MagicMock() for _ in range(4))
        candidates.count.return_value = 1
        candidates.nth.return_value = candidate
        candidate.is_visible.side_effect = [False, True]
        offices.count.return_value = 1
        offices.nth.return_value = office
        office.is_visible.return_value = True
        office.locator.return_value.filter.return_value.count.return_value = 0
        def locate(selector):
            if selector.startswith('li[name="submenu_li"]'):
                result = MagicMock()
                result.filter.return_value = candidates
                return result
            return offices
        frame.locator.side_effect = locate
        self.assertIs(find_admin_menu(page, threading.Event(), lambda _: None), candidate)
        office.hover.assert_called_once()
        office.locator.return_value.click.assert_called_once()
        candidate.click.assert_not_called()

    def test_admin_menu_in_frame_with_hidden_duplicate(self):
        page, frame = MagicMock(), MagicMock()
        frame.url = 'https://gw.koita.or.kr/menu'
        page.frames = [frame]
        candidates = frame.locator.return_value.filter.return_value
        candidates.count.return_value = 2
        hidden, visible = MagicMock(), MagicMock()
        hidden.is_visible.return_value = False
        visible.is_visible.return_value = True
        candidates.nth.side_effect = [hidden, visible]
        messages = []
        self.assertIs(find_admin_menu(page, threading.Event(), messages.append), visible)
        self.assertIn('숨김 1개', messages[-1])

    def test_ambiguous_visible_admin_menus_not_clicked(self):
        page = MagicMock()
        page.url = 'https://gw.koita.or.kr/'
        page.frames = [page]
        candidates = page.locator.return_value.filter.return_value
        candidates.count.return_value = 2
        candidates.nth.return_value.is_visible.return_value = True
        self.assertIsNone(find_admin_menu(page, threading.Event(), lambda _: None))
        candidates.nth.return_value.click.assert_not_called()

    def test_registration_navigation_stops_after_opening_form(self):
        page, admin = MagicMock(), MagicMock()
        page.url = 'https://gw.koita.or.kr/main'
        page.frames = [page]
        admin.url = 'https://www.koita.or.kr/admmgr/'
        page.expect_popup.return_value.__enter__.return_value.value = admin
        page.locator.return_value.filter.return_value.count.return_value = 1
        admin.locator.return_value.count.return_value = 1
        messages = []
        result = open_registration(page, threading.Event(), messages.append)
        self.assertIs(result, admin)
        self.assertEqual(admin.locator.call_count, 4)
        selectors = [call.args[0] for call in admin.locator.call_args_list]
        self.assertIn('commBoardGovRnDList.do', selectors[0])
        self.assertIn('commBoardPressList.do', selectors[1])
        self.assertIn('언론홍보', selectors[2])
        self.assertIn('commBoardPressRegist.do', selectors[3])
        self.assertEqual(admin.locator.return_value.click.call_count, 4)
        admin.fill.assert_not_called()
        admin.locator.return_value.fill.assert_not_called()
        self.assertTrue(messages[-1].startswith('테스트 완료'))

    def test_registration_rejects_unexpected_popup_origin(self):
        page, admin = MagicMock(), MagicMock()
        page.url = 'https://gw.koita.or.kr/main'
        page.frames = [page]
        admin.url = 'https://other.example/'
        page.expect_popup.return_value.__enter__.return_value.value = admin
        page.locator.return_value.filter.return_value.count.return_value = 1
        messages = []
        open_registration(page, threading.Event(), messages.append)
        admin.locator.assert_not_called()
        self.assertIn('중단', messages[-1])

    def test_navigation_failure_is_not_returned_as_registration_page(self):
        page = MagicMock()
        messages = []
        with patch('backend.find_admin_menu', return_value=None):
            self.assertIsNone(open_registration(page, threading.Event(), messages.append))
        page.expect_popup.assert_not_called()

    def test_actual_config_uses_visible_label_and_enters_both_fields(self):
        config = load_config(Path(__file__).with_name('login_selectors.json'))
        self.assertEqual(config['username'], '#uid')
        self.assertEqual(config['password'], '#upw')
        self.assertEqual(config['submit'], 'label[for="LoginButton"]')
        page = MagicMock()
        page.url = 'https://gw.koita.or.kr/'
        controls = {config[key]: MagicMock() for key in ('username', 'password', 'submit')}
        for control in controls.values():
            control.count.return_value = 1
            control.is_visible.return_value = True
        page.locator.side_effect = controls.__getitem__
        attempt(page, config, 'dummy-id', 'dummy-password', threading.Event(), lambda _: None)
        controls['#uid'].fill.assert_called_once_with('dummy-id')
        controls['#upw'].fill.assert_called_once_with('dummy-password')
        controls['label[for="LoginButton"]'].click.assert_called_once()

    def test_destination(self):
        self.assertTrue(trusted_url('https://gw.koita.or.kr/'))
        for url in ('http://gw.koita.or.kr', 'https://gw.koita.or.kr.evil.test',
                    'https://user:secret@gw.koita.or.kr', 'https://gw.koita.or.kr:444/'):
            self.assertFalse(trusted_url(url))

    def test_unverified_config_never_touches_page(self):
        with patch('backend.Path.read_text', return_value='{"login_url":"https://gw.koita.or.kr/", "verified": false}'):
            config = load_config('unverified.json')
        self.assertIsNone(config)
        messages = []
        attempt(object(), config, 'example', 'not-a-real-password', threading.Event(), messages.append)
        self.assertIn('자동 입력하지 않았습니다', messages[0])

    def test_verified_attempt_and_positive_marker(self):
        page = MagicMock()
        page.url = 'https://gw.koita.or.kr/'
        controls = {key: MagicMock() for key in ('user', 'pass', 'submit', 'success')}
        for control in controls.values():
            control.count.return_value = 1
            control.is_visible.return_value = True
        page.locator.side_effect = controls.__getitem__
        config = dict(username='user', password='pass', submit='submit', success='success')
        messages = []
        attempt(page, config, 'example', 'dummy', threading.Event(), messages.append)
        controls['pass'].fill.assert_called_once_with('dummy')
        controls['submit'].click.assert_called_once()
        self.assertTrue(messages[-1].startswith('로그인 성공'))

    def test_redirect_never_receives_credentials(self):
        page = MagicMock()
        page.url = 'https://other.example/'
        attempt(page, {}, 'example', 'dummy', threading.Event(), lambda _: None)
        page.locator.assert_not_called()


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'PySide6 not installed')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_required_fields_and_masking(self):
        from app import Window
        from PySide6.QtWidgets import QLineEdit
        window = Window()
        self.assertFalse(window.fill_form.isChecked())
        self.assertEqual(window.password.echoMode(), QLineEdit.EchoMode.Password)
        window.start_test()
        self.assertIsNone(window.worker)
        window.user.setText('example')
        window.start_test()
        self.assertIsNone(window.worker)
        self.assertFalse(window.file.text())
        self.assertFalse(window.title.text())
        window.password.setText('dummy')
        window.start_test()
        self.assertIsNone(window.worker)
        window.title.setText('필수 제목')
        window.start_test()
        self.assertIsNone(window.worker)
        window.close()


if __name__ == '__main__':
    print('Dependencies:', {name: bool(importlib.util.find_spec(name)) for name in ('PySide6', 'playwright')})
    unittest.main(verbosity=2)
