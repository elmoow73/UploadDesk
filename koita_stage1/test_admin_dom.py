r"""Offline real-browser regression for duplicate hrefs in supplied menu HTML.

Run separately: .venv\Scripts\python test_admin_dom.py
No credentials or network requests are used.
"""
from playwright.sync_api import sync_playwright
from backend import BOARD_MENU, PRESS_MENU, PRESS_PUBLICITY

HTML = '''<ul class="lft_sub_menu_ul">
<li class="lv1_1"><a href="/admmgr/manage/bannerListKMT.do"><strong>시스템 관리</strong></a></li>
<li class="lv1_2">
<a href="/admmgr/board/commBoardGovRnDList.do"><strong>게시판 관리</strong><b><img></b></a>
<ul class="sec_ul"><li><a href="/admmgr/board/commBoardGovRnDList.do">기타 관리</a>
<ul class="tir_ul"><li><a href="/admmgr/board/commBoardGovRnDList.do">정부 R&amp;D사업</a></li></ul></li>
<li><a href="/admmgr/board/commBoardPressList.do">산기협</a>
<ul class="tir_ul"><li><a href="/admmgr/board/commBoardPressList.do">언론홍보</a></li>
<li><a href="/admmgr/board/commBoardNoticeList.do">공지사항</a></li></ul></li></ul></li></ul>'''


def main():
    with sync_playwright() as pw:
        browser = None
        for channel in ('chrome', 'msedge'):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                pass
        if browser is None:
            raise RuntimeError('Chrome or Edge required')
        try:
            page = browser.new_page()
            page.route('**/*', lambda route: route.abort())
            page.set_content(HTML)
            assert page.locator('a[href="/admmgr/board/commBoardGovRnDList.do"]').count() == 3
            assert page.locator('a[href="/admmgr/board/commBoardPressList.do"]').count() == 2
            for selector, text in ((BOARD_MENU, '게시판 관리'), (PRESS_MENU, '산기협'), (PRESS_PUBLICITY, '언론홍보')):
                locator = page.locator(selector)
                assert locator.count() == 1
                assert locator.inner_text() == text
                locator.click(trial=True)
            print('PASS: all three menu selectors uniquely match the correct clickable element')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
