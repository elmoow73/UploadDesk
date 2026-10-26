import os
import sys
import threading
from pathlib import Path
import uuid
import json

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QApplication, QWidget, QFormLayout, QLineEdit,
                              QPushButton, QLabel, QFileDialog, QHBoxLayout, QVBoxLayout, QCheckBox)
from backend import URL, load_config, attempt, open_registration
from press_document import prepare_document, DocumentError
from registration import fill_registration, fill_related_sites
from news_dialog import NewsDialog
from hancom_render import render_first_page, RenderError


class ImageWorker(QThread):
    ready = Signal(str, int, int)
    failed = Signal(str)

    def __init__(self, source):
        super().__init__()
        self.source = source

    def run(self):
        try:
            output = Path(__file__).parent / 'generated' / ('first_page_' + uuid.uuid4().hex + '.jpg')
            width, height = render_first_page(self.source, output)
            self.ready.emit(str(output), width, height)
        except RenderError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit('JPG 생성 중단 (' + type(error).__name__ + '): 파일 접근 상태를 확인해 주세요.')


class LoginWorker(QThread):
    status = Signal(str)

    def __init__(self, username, password, file_path, title, fill_form=False, related_sites=(), image_path=None):
        super().__init__()
        self.username, self.password = username, password
        self.file_path, self.title = file_path, title
        self.fill_form = fill_form
        self.related_sites = tuple(related_sites)
        self.image_path = image_path
        self.stop = threading.Event()

    def populate_registration(self, page):
        if self.stop.is_set():
            return
        if not self.fill_form:
            if self.related_sites:
                fill_related_sites(page, self.related_sites, self.stop, self.status.emit)
            return
        self.status.emit('등록 페이지 도착 · HWPX 온라인 보도일과 첫 페이지 JPG 준비 중…')
        try:
            # Keep the JPEG in memory; no temporary directory/file is needed.
            if self.image_path:
                publication_date, body, dimensions = prepare_document(self.file_path, image_path=self.image_path)
            else:
                publication_date, body, dimensions = prepare_document(self.file_path)
        except DocumentError as error:
            self.status.emit('HWPX 준비 중단: ' + str(error) + ' 브라우저는 확인할 수 있도록 유지합니다.')
            return
        except Exception as error:
            self.status.emit('HWPX 준비 중단 (' + type(error).__name__ + '): 날짜 추출 또는 JPG 변환을 완료하지 못했습니다. 브라우저는 유지합니다.')
            return
        if self.stop.is_set():
            return
        self.status.emit(f'게시일자 {publication_date} · 첫 페이지 {dimensions[0]}×{dimensions[1]} 준비 완료 · 등록 폼 입력 시작')
        completed = fill_registration(page, self.title, self.file_path, publication_date, body, self.stop, self.status.emit)
        if not completed or self.stop.is_set():
            return
        if self.related_sites:
            self.status.emit('기본 항목·본문·첨부 확인 완료 · 마지막으로 관련사이트 입력 시작')
            fill_related_sites(page, self.related_sites, self.stop, self.status.emit)

    def run(self):
        # Prevent Playwright debug/API logs from including form values.
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        stage = '브라우저 자동화 모듈 로딩'
        try:
            from playwright.sync_api import sync_playwright, Error
            stage = '브라우저 실행'
            with sync_playwright() as pw:
                browser = None
                for channel in ('chrome', 'msedge'):
                    try:
                        browser = pw.chromium.launch(channel=channel, headless=False)
                        break
                    except Error:
                        continue
                if browser is None:
                    self.status.emit('Chrome 또는 Edge 실행 실패. 브라우저 설치와 회사 보안 정책을 확인해 주세요.')
                    return
                try:
                    context = browser.new_context(accept_downloads=False)
                    page = context.new_page()
                    page.set_default_timeout(8000)
                    self.status.emit('그룹웨어 로그인 페이지를 여는 중…')
                    stage = '그룹웨어 페이지 접속'
                    page.goto(URL, wait_until='domcontentloaded', timeout=30000)
                    stage = '로그인 설정 읽기'
                    config = load_config(Path(__file__).with_name('login_selectors.json'))
                    stage = 'ID·비밀번호 입력 및 로그인'
                    submitted = attempt(page, config, self.username, self.password, self.stop, self.status.emit)
                    self.username = self.password = ''
                    if submitted and not self.stop.is_set():
                        stage = '로그인 후 등록 페이지 이동'
                        registration_page = open_registration(page, self.stop, self.status.emit)
                        if registration_page is not None:
                            page = registration_page
                            stage = '등록 페이지 항목 입력'
                            self.populate_registration(page)
                    stage = '결과 확인용 브라우저 유지'
                    # Keep the temporary browser open for the user's inspection.
                    while not self.stop.is_set() and browser.is_connected() and not page.is_closed():
                        page.wait_for_timeout(200)
                finally:
                    browser.close()
        except ImportError:
            self.status.emit(stage + ' 중단: 필요한 모듈이 없습니다. requirements.txt 설치 상태를 확인해 주세요.')
        except Exception as error:
            # Never emit exception strings, page content, credentials, URLs or traces.
            self.status.emit(stage + ' 중단 (' + type(error).__name__ + '): 해당 단계의 동작을 완료하지 못했습니다. 인증서 경고는 우회하지 않습니다.')
        finally:
            self.username = self.password = ''


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.image_worker = None
        self.related_sites = []
        try:
            release_version = json.loads((Path(__file__).resolve().parent.parent / 'VERSION.json').read_text(encoding='utf-8')).get('version')
        except (OSError, ValueError):
            release_version = None
        version_label = f'v{release_version}' if release_version else '정식 버전 승인 대기'
        self.setWindowTitle(f'UploadDesk · {version_label}')
        self.resize(620, 330)
        self.user = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.file = QLineEdit()
        self.file.setReadOnly(True)
        self.title = QLineEdit()
        self.choose = QPushButton('HWPX 파일 선택')
        self.choose.clicked.connect(self.choose_file)
        row = QHBoxLayout()
        row.addWidget(self.file)
        row.addWidget(self.choose)
        form = QFormLayout()
        form.addRow('그룹웨어 ID *', self.user)
        form.addRow('비밀번호 *', self.password)
        form.addRow('HWPX 파일 *', row)
        form.addRow('보도자료 제목 *', self.title)
        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)
        self.image_path.setPlaceholderText('미지정 시 내장 미리보기 사용, 없으면 한글로 생성')
        self.render_button = QPushButton('첫 페이지 JPG 생성 (가로 700px)')
        self.render_button.clicked.connect(self.generate_image)
        self.image_button = QPushButton('JPG·PNG 직접 선택')
        self.image_button.clicked.connect(self.choose_image)
        self.clear_image = QPushButton('선택 해제')
        self.clear_image.clicked.connect(self.image_path.clear)
        image_row = QVBoxLayout()
        image_row.addWidget(self.image_path)
        image_actions = QHBoxLayout()
        for button in (self.render_button, self.image_button, self.clear_image):
            image_actions.addWidget(button)
        image_row.addLayout(image_actions)
        form.addRow('본문 첫 페이지 이미지', image_row)
        self.related_button = QPushButton('관련사이트 선택')
        self.related_button.clicked.connect(self.choose_related)
        self.related_summary = QLabel('선택한 기사 없음')
        related_row = QHBoxLayout()
        related_row.addWidget(self.related_button)
        related_row.addWidget(self.related_summary)
        form.addRow('관련사이트 (선택)', related_row)
        self.fill_form = QCheckBox('등록 페이지 도착 후 내용 자동 입력 (선택 해제 시 본문 입력하지 않음)')
        self.fill_form.setChecked(True)
        self.run_button = QPushButton('로그인 후 등록 페이지 열기')
        self.run_button.clicked.connect(self.start_test)
        self.stop_button = QPushButton('테스트 종료 / 브라우저 닫기')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_test)
        self.status = QLabel('대기 중 · ID, 비밀번호, HWPX 파일, 제목을 모두 입력해 주세요.')
        self.status.setWordWrap(True)
        note = QLabel('선택한 파일과 내용은 KOITA 등록 화면에 전달합니다. 최종 등록은 누르지 않습니다. 비밀번호는 저장하지 않습니다.')
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.fill_form)
        layout.addWidget(self.run_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.status)
        layout.addWidget(note)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'HWPX 파일 선택', '', 'HWPX (*.hwpx)')
        if path:
            self.file.setText(path)
            self.image_path.clear()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, '보도자료 첫 페이지 이미지 선택', '', '이미지 (*.jpg *.jpeg *.png)')
        if path:
            from PySide6.QtGui import QImage
            try:
                image = QImage.fromData(Path(path).read_bytes())
            except OSError:
                self.status.setText('선택한 이미지 파일에 접근할 수 없습니다.')
                return
            if image.isNull():
                self.status.setText('선택한 이미지를 읽을 수 없습니다.')
                return
            self.image_path.setText(path)
            self.status.setText('선택한 이미지를 본문 첫 페이지로 사용합니다.')

    def set_image_busy(self, busy):
        for button in (self.choose, self.render_button, self.image_button, self.clear_image, self.run_button):
            button.setEnabled(not busy)

    def generate_image(self):
        source = Path(self.file.text())
        if not source.is_file() or source.suffix.lower() != '.hwpx':
            self.status.setText('먼저 HWPX 파일을 선택해 주세요.')
            return
        self.set_image_busy(True)
        self.status.setText('한글로 첫 페이지 JPG 생성 중… 파일 접근 확인 창이 뜨면 직접 허용해 주세요.')
        self.image_worker = ImageWorker(str(source))
        self.image_worker.ready.connect(self.image_ready)
        self.image_worker.failed.connect(self.status.setText)
        self.image_worker.finished.connect(lambda: self.set_image_busy(False))
        self.image_worker.start()

    def image_ready(self, path, width, height):
        self.image_path.setText(path)
        self.status.setText(f'첫 페이지 JPG 생성 완료 · {width}×{height} · 본문에 이 이미지를 사용합니다.')

    def choose_related(self):
        dialog = NewsDialog(self.related_sites, self)
        if dialog.exec() == NewsDialog.DialogCode.Accepted:
            self.related_sites = dialog.checked_articles()
            self.related_summary.setText(f'{len(self.related_sites)}개 기사 선택' if self.related_sites else '선택한 기사 없음')

    def start_test(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.user.text().strip() or not self.password.text():
            self.status.setText('ID와 비밀번호를 입력해 주세요.')
            return
        if not self.title.text().strip():
            self.status.setText('보도자료 제목을 입력해 주세요.')
            return
        selected = Path(self.file.text())
        if not selected.is_file() or selected.suffix.lower() != '.hwpx':
            self.status.setText('존재하는 HWPX 파일을 선택해 주세요.')
            return
        if self.image_worker and self.image_worker.isRunning():
            return
        image_path = self.image_path.text() or None
        if image_path and not Path(image_path).is_file():
            self.status.setText('선택한 이미지가 없습니다. 이미지를 다시 선택하거나 생성해 주세요.')
            return
        self.worker = LoginWorker(self.user.text().strip(), self.password.text(), str(selected), self.title.text().strip(), self.fill_form.isChecked(), self.related_sites, image_path)
        self.password.clear()
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self.finished)
        self.run_button.setEnabled(False)
        self.related_button.setEnabled(False)
        for button in (self.choose, self.render_button, self.image_button, self.clear_image):
            button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker.start()

    def stop_test(self):
        if self.worker:
            self.worker.stop.set()
            self.stop_button.setEnabled(False)
            self.status.setText('테스트 종료 중… 진행 중인 접속 요청이 끝나면 닫힙니다.')

    def finished(self):
        self.run_button.setEnabled(True)
        self.related_button.setEnabled(True)
        for button in (self.choose, self.render_button, self.image_button, self.clear_image):
            button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        if self.image_worker and self.image_worker.isRunning():
            self.status.setText('이미지 생성 중입니다. 변환이 끝나면 창이 닫힙니다.')
            self.image_worker.finished.connect(self.close)
            event.ignore()
        elif self.worker and self.worker.isRunning():
            self.stop_test()
            self.worker.finished.connect(self.close)
            event.ignore()
        else:
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
