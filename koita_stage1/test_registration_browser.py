"""Offline browser form test using supplied HTML; never contacts KOITA."""
from pathlib import Path
import re
import tempfile
import threading
from playwright.sync_api import sync_playwright
from registration import fill_registration, fill_related_sites
from news_catalog import load_articles
from press_document import NOTE, online_date


def main():
    assert online_date('(온라인) 2026. 10. 20.(화) 12:00 (지 면) 2026. 10. 21.(수)') == '2026-10-20'
    source = Path(__file__).resolve().parent.parent / '등록페이지 코드.txt'
    html = source.read_text(encoding='utf-8-sig')
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S | re.I)
    html = re.sub(r'<iframe\b[^>]*>.*?</iframe>', '', html, flags=re.S | re.I)
    html = '<html><body><table>' + html + '</table><div id="editor_test"></div></body></html>'
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as temporary:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        try:
            page = browser.new_page()
            page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html')
                       if route.request.is_navigation_request() else route.abort())
            page.goto('https://www.koita.or.kr/admmgr/board/commBoardPressRegist.do')
            page.evaluate('''() => {
                window.editorReady = false;
                const editor = document.getElementById('editor_test');
                editor.contentEditable = 'true';
                setTimeout(() => { window.editorReady = true; editor.focus(); }, 80);
                window.focusTimer = setInterval(() => editor.focus(), 5);
                window.CrossEditor = {
                    SetBodyValue: html => document.getElementById('editor_test').innerHTML = html,
                    GetBodyValue: () => {
                        if (!window.editorReady) throw new Error('Editor initializing');
                        return document.getElementById('editor_test').innerHTML;
                    }
                };
                document.getElementById('coa_html_upload').onchange = e => {
                    const item = document.createElement('li');
                    item.textContent = e.target.files[0].name;
                    document.getElementById('coa_view_box').append(item);
                };
                window.addCount = 0;
                window.addTR = id => {
                    const body = document.getElementById(id);
                    const row = body.firstElementChild.cloneNode(true);
                    row.querySelectorAll('input').forEach(input => input.value = '');
                    body.append(row);
                    window.addCount++;
                };
            }''')
            articles, _ = load_articles()
            assert len(articles) >= 3
            selected = articles[:3]
            from PySide6.QtGui import QImage
            image = QImage(10, 10, QImage.Format.Format_RGB32)
            image.fill(0xffffff)
            image_path = Path(temporary) / 'image.jpg'
            image.save(str(image_path), 'JPG')
            import base64
            body = '<p><img src="data:image/jpeg;base64,' + base64.b64encode(image_path.read_bytes()).decode() + '"></p><p>' + NOTE + '</p>'
            attachment = Path(temporary) / 'example.hwpx'
            attachment.write_bytes(b'offline fixture')
            messages = []
            assert fill_registration(page, '테스트 제목', attachment, '2026-10-20', body, threading.Event(), messages.append), messages
            assert page.locator('#code').input_value() == '004002000'
            assert page.locator('input[name=title]').input_value() == '테스트 제목'
            assert page.locator('input[name=userNm]').input_value() == '이승현'
            assert page.locator('#vwRegDt').input_value() == '2026-10-20'
            assert page.locator('input[name=topYn][value=N]').is_checked()
            assert page.locator('input[name=vwYn][value=Y]').is_checked()
            # Related sites are filled only AFTER the body and attachment.
            assert fill_related_sites(page, selected, threading.Event(), lambda _: None)
            assert page.evaluate('window.addCount') == 2
            assert page.locator('#relSiteTbody > tr').count() == 3
            for index, article in enumerate(selected):
                row = page.locator('#relSiteTbody > tr').nth(index)
                assert row.locator('input[name=relSiteTitle]').input_value() == article.title
                assert row.locator('input[name=relSiteUrl]').input_value() == article.url
                assert row.locator('input[name=relSiteMedia]').input_value() == article.press
            assert page.locator('input[name=title]').input_value() == '테스트 제목'
            assert page.evaluate('CrossEditor.GetBodyValue()').count(NOTE) == 1
            assert not fill_related_sites(page, selected, threading.Event(), lambda _: None)
            print('PASS: focus-stealing editor; basic fields -> body -> attachment -> related sites; values preserved; no submission')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
