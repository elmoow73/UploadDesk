"""Read-only access to the existing news database; never writes to MyBrain."""
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

NEWS_ROOT = Path('C:/Users/21017/Desktop/MyBrain/News')


@dataclass(frozen=True)
class Article:
    key: str
    date: str
    press: str
    kind: str
    title: str
    url: str


def valid_article(article):
    address = urlsplit(article.url)
    return bool(article.title.strip() and article.press.strip()
                and address.scheme in ('http', 'https') and address.hostname
                and not address.username and not address.password)


def load_articles(root=NEWS_ROOT):
    path = Path(root) / 'koita_news.sqlite'
    if not path.is_file():
        raise ValueError('News 폴더에 koita_news.sqlite DB가 없습니다.')
    # mode=ro prevents accidental database creation and writes.
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute('SELECT seq, date, press, type, title, url FROM news ORDER BY date DESC, seq DESC').fetchall()
    articles, skipped = [], 0
    for row in rows:
        article = Article(*(str(value) if value is not None else '' for value in row))
        try:
            valid = valid_article(article)
        except ValueError:
            valid = False
        if valid:
            articles.append(article)
        else:
            skipped += 1
    return articles, skipped
