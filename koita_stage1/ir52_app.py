import sys
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QApplication, QWidget, QFormLayout, QLineEdit,
                              QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QPlainTextEdit)
from ir52_article import fetch_article, validate_article_url
from news_dialog import NewsDialog
from app import LoginWorker
from registration import set_text_field, fill_related_sites
from news_catalog import Article
from urllib.parse import urlsplit


class FetchWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.ready.emit(fetch_article(self.url, self.status.emit))
        except ValueError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(f'기사 불러오기 실패 ({type(error).__name__}). URL과 접속 상태를 확인해 주세요.')


class ArticleLoginWorker(LoginWorker):
    def __init__(self, username, password, article):
        super().__init__(username, password, '', article.title)
        self.article = article

    def populate_registration(self, page):
        if self.stop.is_set():
            return
        validate_article_url(self.article.url)
        address = urlsplit(page.url)
        if (address.scheme != 'https' or address.hostname != 'www.koita.or.kr'
                or address.path != '/admmgr/board/commBoardPressRegist.do'):
            self.status.emit('입력 중단: 지정된 게시판 등록 페이지가 아닙니다.')
            return
        options = page.locator('#code option').evaluate_all(
            '(options) => options.map(o => ({label:o.textContent, value:o.value}))')
        matches = [o for o in options if o['label'].strip() == '기사']
        if len(matches) != 1:
            self.status.emit('입력 중단: 구분에서 ‘기사’ 항목을 유일하게 확인하지 못했습니다.')
            return
        page.wait_for_function("() => typeof CrossEditor !== 'undefined' && typeof CrossEditor.SetBodyValue === 'function' && typeof CrossEditor.GetBodyValue === 'function'", timeout=20000)
        if self.stop.is_set():
            return
        page.locator('#code').select_option(matches[0]['value'])
        set_text_field(page.locator('input[name="title"]'), self.article.title)
        set_text_field(page.locator('#vwRegDt'), self.article.publication_date)
        set_text_field(page.locator('input[name="userNm"]'), '이승현')
        page.locator('input[name="topYn"][value="N"]').check()
        page.locator('input[name="vwYn"][value="Y"]').check()
        page.evaluate('html => { CrossEditor.SetBodyValue(html); document.getElementById("conts").value = CrossEditor.GetBodyValue(); }', self.article.body_html())
        text = page.evaluate('() => new DOMParser().parseFromString(CrossEditor.GetBodyValue(), "text/html").body.textContent')
        if not all(v in text for k, v in self.article.parts if k == 'text'):
            raise ValueError('Article body verification failed')
        expected_images = [v for k, v in self.article.parts if k == 'image']
        actual_images = page.evaluate('() => [...new DOMParser().parseFromString(CrossEditor.GetBodyValue(), "text/html").images].map(img => img.getAttribute("src"))')
        if actual_images != expected_images:
            raise ValueError('Article image verification failed')
        if self.stop.is_set():
            return
        related = Article('', self.article.publication_date, '매일경제', '기사', self.article.title, self.article.url)
        if not fill_related_sites(page, [related], self.stop, self.status.emit):
            return
        for selector, value in (('#code', matches[0]['value']), ('input[name="title"]', self.article.title), ('#vwRegDt', self.article.publication_date)):
            if page.locator(selector).input_value() != value:
                raise ValueError('Article field verification failed')
        self.status.emit('등록 준비 완료: 구분 ‘기사’·제목·게시일·사진 포함 본문·관련사이트(매일경제)를 입력했습니다. 최종 등록은 누르지 않았습니다.')


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.article = self.fetcher = self.worker = None
        self.setWindowTitle('UploadDeskIR52 · 개발 중')
        self.resize(850, 720)
        self.user, self.password, self.url = QLineEdit(), QLineEdit(), QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.url.setPlaceholderText('기사 URL을 붙여넣어 주세요')
        self.choose = QPushButton('DB에서 선택')
        self.choose.clicked.connect(self.choose_article)
        self.fetch = QPushButton('기사 불러오기')
        self.fetch.clicked.connect(self.load_article)
        row = QHBoxLayout()
        for widget in (self.url, self.choose, self.fetch):
            row.addWidget(widget)
        form = QFormLayout()
        form.addRow('그룹웨어 ID', self.user)
        form.addRow('비밀번호', self.password)
        form.addRow('관련사이트', row)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText('추출된 제목·게시일자·사진·본문이 표시됩니다.')
        self.run = QPushButton('로그인 후 게시판에 자동 입력')
        self.run.setEnabled(False)
        self.run.clicked.connect(self.start_upload)
        self.stop = QPushButton('브라우저 닫기')
        self.stop.clicked.connect(self.stop_upload)
        self.status = QLabel('매일경제 기사 1개를 선택하거나 URL을 입력해 주세요. 최종 저장은 직접 확인 후 진행합니다.')
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)
        layout.addWidget(self.run)
        layout.addWidget(self.stop)
        layout.addWidget(self.status)
        self.url.textChanged.connect(self.invalidate)

    def invalidate(self):
        self.article = None
        self.preview.clear()
        self.run.setEnabled(False)

    def choose_article(self):
        dialog = NewsDialog(parent=self)
        if dialog.exec() == NewsDialog.DialogCode.Accepted:
            selected = dialog.checked_articles()
            if len(selected) != 1:
                self.status.setText('게시물 1개에 사용할 기사 1개를 선택해 주세요.')
                return
            self.url.setText(selected[0].url)
            self.load_article()

    def load_article(self):
        if self.fetcher and self.fetcher.isRunning():
            return
        self.invalidate()
        self.fetcher = FetchWorker(self.url.text().strip())
        self.fetcher.ready.connect(self.loaded)
        self.fetcher.status.connect(self.status.setText)
        self.fetcher.failed.connect(self.status.setText)
        self.fetcher.finished.connect(lambda: self.set_source_enabled(True))
        self.set_source_enabled(False)
        self.status.setText('기사 제목과 본문을 불러오는 중…')
        self.fetcher.start()

    def set_source_enabled(self, enabled):
        for widget in (self.url, self.choose, self.fetch):
            widget.setEnabled(enabled)

    def loaded(self, article):
        self.article = article
        self.preview.setPlainText(article.preview())
        self.run.setEnabled(True)
        self.status.setText('추출 완료 · 원문과 비교한 후 게시판 자동 입력을 실행해 주세요.')

    def start_upload(self):
        if not self.article or (self.worker and self.worker.isRunning()):
            return
        if not self.user.text().strip() or not self.password.text():
            self.status.setText('ID와 비밀번호를 입력해 주세요.')
            return
        self.worker = ArticleLoginWorker(self.user.text().strip(), self.password.text(), self.article)
        self.password.clear()
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self.upload_finished)
        self.set_source_enabled(False)
        self.run.setEnabled(False)
        self.worker.start()

    def stop_upload(self):
        if self.worker:
            self.worker.stop.set()

    def upload_finished(self):
        self.set_source_enabled(True)
        self.run.setEnabled(self.article is not None)

    def closeEvent(self, event):
        running = [w for w in (self.fetcher, self.worker) if w and w.isRunning()]
        if running:
            self.stop_upload()
            for worker in running:
                worker.finished.connect(self.close)
            self.status.setText('진행 중인 요청 종료 후 닫힙니다.')
            event.ignore()
        else:
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
