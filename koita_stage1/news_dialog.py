from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                              QLabel, QTableWidget, QTableWidgetItem, QDialogButtonBox,
                              QHeaderView, QAbstractItemView)
from news_catalog import load_articles


class NewsDialog(QDialog):
    def __init__(self, selected=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle('관련사이트 기사 선택')
        self.resize(1100, 600)
        self.articles = []
        self.selected_keys = {article.key for article in selected}
        self.search = QLineEdit()
        self.search.setPlaceholderText('제목·출처·날짜·유형·URL 검색')
        refresh = QPushButton('DB 새로고침')
        refresh.clicked.connect(self.reload)
        top = QHBoxLayout()
        top.addWidget(self.search)
        top.addWidget(refresh)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['선택', '날짜', '출처', '유형', '제목', 'URL'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(5, 240)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('선택 적용')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('취소')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addWidget(self.info)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self.filter_rows)
        self.reload(first=True)

    def checked_articles(self):
        # Search only hides rows; checked hidden rows remain selected.
        return [article for row, article in enumerate(self.articles)
                if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]

    def reload(self, first=False):
        selected_keys = self.selected_keys if first else {article.key for article in self.checked_articles()}
        try:
            articles, skipped = load_articles()
        except Exception:
            self.info.setText('DB를 읽지 못했습니다. News 폴더의 DB 파일과 잠금 상태를 확인하고 새로고침해 주세요.')
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self.articles = articles
        self.table.setRowCount(len(articles))
        for row, article in enumerate(articles):
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if article.key in selected_keys else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, item)
            for column, value in enumerate((article.date, article.press, article.kind, article.title, article.url), 1):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.table.setItem(row, column, cell)
        self.info.setText(f'기사 {len(articles)}개 · 필수값/URL이 잘못된 항목 {skipped}개 제외 · DB는 수정하지 않습니다.')
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.filter_rows()

    def filter_rows(self):
        query = self.search.text().strip().casefold()
        for row, article in enumerate(self.articles):
            haystack = ' '.join((article.date, article.press, article.kind, article.title, article.url)).casefold()
            self.table.setRowHidden(row, bool(query and query not in haystack))
