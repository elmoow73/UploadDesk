"""Offline registration test. All network requests are intercepted."""
import threading
from playwright.sync_api import sync_playwright
from ir52_article import ExtractedArticle
from ir52_app import ArticleLoginWorker


def main():
    html = '''<meta charset="utf-8"><select id="code"><option value="press">보도자료</option><option value="article">기사</option><option value="award">장영실상</option></select>
    <input name="title"><input name="userNm"><input id="vwRegDt" name="vwRegDt">
    <input type="radio" name="topYn" value="N"><input type="radio" name="vwYn" value="Y">
    <textarea id="conts"></textarea><div id="editor"></div>
    <table><tbody id="relSiteTbody"><tr><td><input name="relSiteTitle"><input name="relSiteUrl"><input name="relSiteMedia"></td></tr></tbody></table>
    <button id="save" onclick="window.saved=true">등록</button>'''
    article = ExtractedArticle('https://www.mk.co.kr/news/it/12166326', '기사 제목 & 테스트', '2026-10-01', (
        ('text', '본문 <텍스트> & 원문'), ('image', 'https://wimg.mk.co.kr/example.jpg'), ('text', '사진설명: 원문 사진')))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        try:
            page = browser.new_page()
            page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html') if route.request.is_navigation_request() else route.abort())
            page.goto('https://www.koita.or.kr/admmgr/board/commBoardPressRegist.do')
            page.evaluate('''() => { window.saved = false; window.CrossEditor = {
                SetBodyValue: value => document.getElementById('editor').innerHTML = value,
                GetBodyValue: () => document.getElementById('editor').innerHTML
            }; }''')
            worker = ArticleLoginWorker('', '', article)
            worker.populate_registration(page)
            assert page.locator('#code').input_value() == 'article'
            assert page.locator('input[name="title"]').input_value() == article.title
            assert page.locator('#vwRegDt').input_value() == article.publication_date
            assert page.locator('input[name="relSiteTitle"]').input_value() == article.title
            assert page.locator('input[name="relSiteUrl"]').input_value() == article.url
            assert page.locator('input[name="relSiteMedia"]').input_value() == '매일경제'
            assert page.locator('#editor img').get_attribute('src') == article.parts[1][1]
            assert '본문 <텍스트> & 원문' in page.locator('#editor').text_content()
            assert page.evaluate('window.saved') is False
            print('PASS: article category, title, date, escaped body, IMG src, related site, no save')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
