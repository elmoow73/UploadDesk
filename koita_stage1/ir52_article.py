"""Article extraction from the supplied MK HTML structure. No page scripts run."""
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from datetime import date
import re
from urllib.parse import urlsplit, urljoin


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def validate_url(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('http 또는 https 기사 URL을 입력해 주세요.')
    return url


def validate_article_url(url):
    validate_url(url)
    host = urlsplit(url).hostname.lower()
    if host != 'mk.co.kr' and not host.endswith('.mk.co.kr'):
        raise ValueError('매일경제 사이트가 아닙니다.')
    return url


@dataclass(frozen=True)
class ExtractedArticle:
    url: str
    title: str
    publication_date: str
    parts: tuple

    def preview(self):
        lines = [f'제목: {self.title}', f'게시일자: {self.publication_date}']
        for kind, value in self.parts:
            lines.append(f'사진({value})' if kind == 'image' else value)
        return '\n\n'.join(lines[:2]) + '\n\n내용: ' + '\n\n'.join(lines[2:])

    def body_html(self):
        # The board resets paragraph margins. Use an explicit empty line so
        # paragraph separation survives the editor's stylesheet.
        blocks = [f'<p style="margin:0"><img src="{escape(v, quote=True)}" style="max-width:100%;height:auto" alt=""></p>'
                  if k == 'image' else f'<p style="margin:0">{escape(v)}</p>' for k, v in self.parts]
        return '<p style="margin:0"><br></p>'.join(blocks)


def extract_article(source, url):
    validate_article_url(url)
    parser = Parser()
    parser.feed(source)
    nodes = list(parser.root.walk())
    meta = {n.attrs.get('property', n.attrs.get('name', '')): n.attrs.get('content', '')
            for n in nodes if n.tag == 'meta'}
    title = meta.get('taboola:title') or meta.get('og:title', '').removesuffix(' - 매일경제')
    published = meta.get('article:published_time', '')[:10]
    containers = [n for n in nodes if n.has_class('news_cnt_detail_wrap')]
    if len(containers) != 1 or not title or not published:
        raise ValueError('지원하는 매일경제 기사 구조가 아닙니다. 제목·게시일·본문을 확인해 주세요.')
    date.fromisoformat(published)
    parts, pending = [], []

    def flush():
        value = clean(''.join(pending))
        pending.clear()
        if value:
            parts.append(('text', value))

    def visit(node):
        if isinstance(node, str):
            pending.append(node)
            return
        if node.tag in {'script', 'style', 'iframe', 'button'} or node.has_class('ad-slot'):
            return
        if node.has_class('thumb_area'):
            flush()
            images = [n for n in node.walk() if n.tag == 'img']
            for image in images:
                # The supplied example excludes the 676×70 footer logo.
                height = image.attrs.get('orgheight', '')
                if height.isdigit() and int(height) <= 100:
                    continue
                src = urljoin(url, image.attrs.get('src', ''))
                validate_url(src)
                parts.append(('image', src))
                captions = [n for n in node.walk() if n.tag == 'figcaption']
                caption = clean(captions[0].text()) if captions else clean(image.attrs.get('alt', ''))
                if caption and caption != '사진설명':
                    parts.append(('text', '사진설명: ' + caption))
            return
        if node.tag == 'br':
            flush()
            return
        block = node.tag in {'div', 'p', 'h2', 'h3'}
        if block:
            flush()
        for child in node.children:
            visit(child)
        if block:
            flush()

    visit(containers[0])
    flush()
    if not parts or not any(k == 'text' and len(v) > 100 for k, v in parts):
        raise ValueError('기사 본문이 없거나 일부만 제공됩니다.')
    return ExtractedArticle(url, clean(title), published, tuple(parts))


def fetch_with_browser(url, report=lambda message: None):
    """Use a fresh installed browser context; never bypass TLS or login checks."""
    from playwright.sync_api import sync_playwright, Error, TimeoutError
    validate_article_url(url)
    report('사이트가 직접 요청을 거부하여 Chrome·Edge로 기사를 불러오는 중…')
    with sync_playwright() as pw:
        browser = None
        for channel in ('chrome', 'msedge'):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True)
                break
            except Error:
                continue
        if browser is None:
            raise ValueError('기사 접속용 Chrome 또는 Edge를 실행하지 못했습니다. 브라우저 설치 상태를 확인해 주세요.')
        try:
            context = browser.new_context(accept_downloads=False, locale='ko-KR')
            page = context.new_page()
            def guard_navigation(route):
                if route.request.is_navigation_request() and route.request.frame == page.main_frame:
                    try:
                        validate_article_url(route.request.url)
                    except ValueError:
                        route.abort()
                        return
                route.continue_()
            page.route('**/*', guard_navigation)
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            validate_article_url(page.url)
            if response is not None and response.status >= 400:
                raise ValueError(f'기사 사이트가 브라우저 접속도 거부했습니다 (HTTP {response.status}). URL을 브라우저에서 직접 확인해 주세요.')
            try:
                page.locator('.news_cnt_detail_wrap').wait_for(state='attached', timeout=15000)
            except TimeoutError:
                raise ValueError('브라우저에서 기사 본문을 찾지 못했습니다. 지원하는 매일경제 기사 URL인지 확인해 주세요.') from None
            return extract_article(page.content(), page.url)
        except TimeoutError:
            raise ValueError('기사 브라우저 접속 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.') from None
        finally:
            browser.close()


def open_article_url(request, timeout):
    from urllib.request import HTTPRedirectHandler, build_opener

    class MKRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            validate_article_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return build_opener(MKRedirectHandler()).open(request, timeout=timeout)


def fetch_article(url, report=lambda message: None):
    from urllib.request import Request
    from urllib.error import HTTPError, URLError
    validate_article_url(url)
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with open_article_url(request, timeout=25) as response:
            validate_article_url(response.url)
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError('기사 HTML이 너무 큽니다.')
            charset = response.headers.get_content_charset() or 'utf-8'
            return extract_article(raw.decode(charset), response.url)
    except HTTPError as error:
        code = error.code
        error.close()
        if code in (403, 406, 429):
            return fetch_with_browser(url, report)
        raise ValueError(f'기사 접속 실패 (HTTP {code}). 기사 URL과 사이트 상태를 확인해 주세요.') from None
    except URLError:
        raise ValueError('기사 서버에 연결하지 못했습니다. 인터넷 연결·인증서·방화벽 설정을 확인해 주세요.') from None
