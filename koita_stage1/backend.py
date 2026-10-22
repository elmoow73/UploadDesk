"""Only selectors verified together with the user may enable automation."""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

URL = 'https://gw.koita.or.kr/'
BOARD_MENU = 'ul.lft_sub_menu_ul > li.lv1_2 > a[href="/admmgr/board/commBoardGovRnDList.do"]:has(> strong:text-is("게시판 관리"))'
PRESS_MENU = 'ul.lft_sub_menu_ul > li.lv1_2 > ul.sec_ul > li > a[href="/admmgr/board/commBoardPressList.do"]:text-is("산기협")'
PRESS_PUBLICITY = 'ul.lft_sub_menu_ul > li.lv1_2 > ul.sec_ul > li > ul.tir_ul > li > a[href="/admmgr/board/commBoardPressList.do"]:text-is("언론홍보")'


def trusted_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname == 'gw.koita.or.kr'
            and parsed.port in (None, 443) and not parsed.username and not parsed.password)


def load_config(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not trusted_url(data.get('login_url', '')):
        raise ValueError('Untrusted login destination')
    if data.get('verified') is not True:
        return None
    for key in ('username', 'password', 'submit', 'evidence'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError('Incomplete verified configuration')
    return data


def attempt(page, config, username, password, stop, report, timeout=20):
    if config is None:
        report('화면 구조 확인 필요: 실제 DOM 확인 후 선택자를 설정해야 합니다. 자동 입력하지 않았습니다.')
        return
    if not trusted_url(page.url):
        report('중단: 로그인 페이지가 지정된 HTTPS 주소와 다릅니다. 사용자 확인이 필요합니다.')
        return
    scope = page.frame_locator(config['frame_selector']) if config.get('frame_selector') else page
    # Require unique visible controls. Never fall back to guessed selectors.
    fields = [scope.locator(config[key]) for key in ('username', 'password', 'submit')]
    if any(field.count() != 1 or not field.is_visible() for field in fields):
        report('중단: 확인된 로그인 화면 구조와 다릅니다. 선택자를 다시 확인해 주세요.')
        return
    if stop.is_set():
        return
    report('ID와 비밀번호 입력 중…')
    fields[0].fill(username)
    fields[1].fill(password)
    if stop.is_set() or not trusted_url(page.url):
        return
    report('로그인 버튼 클릭 중…')
    fields[2].click(no_wait_after=True)
    if not config.get('success'):
        report('로그인 시도 완료 · 성공 여부 미검증: 인증 후 화면 표시를 아직 확인하지 못했습니다. 브라우저에서 결과를 직접 확인해 주세요.')
        return True
    report('로그인 요청 후 결과 확인 중… 추가 인증은 브라우저에서 직접 진행해 주세요.')
    deadline = time.monotonic() + timeout
    while not stop.is_set() and time.monotonic() < deadline:
        # Success must be an authenticated-only marker confirmed from the real DOM.
        if scope.locator(config['success']).is_visible():
            report('로그인 성공: 사전에 확인된 인증 후 화면 요소를 확인했습니다.')
            return True
        if config.get('failure') and scope.locator(config['failure']).is_visible():
            report('로그인 실패: 사이트의 실패 표시를 확인했습니다. 자동 재시도하지 않습니다.')
            return
        page.wait_for_timeout(250)
    if not stop.is_set():
        report('결과 확인 불가: 시간 초과 또는 추가 인증이 필요합니다. 브라우저를 확인해 주세요.')


def find_admin_menu(page, stop, report, timeout=30):
    """Inspect current DOM in each trusted frame, without collecting page text."""
    from playwright.sync_api import Error as PlaywrightError
    deadline = time.monotonic() + timeout
    last_summary = None
    office_open_attempted = False
    while not stop.is_set() and time.monotonic() < deadline:
        matches, total, hidden, frames = [], 0, 0, 0
        try:
            for frame in page.frames:
                if not trusted_url(frame.url):
                    continue
                frames += 1
                candidates = frame.locator('li[name="submenu_li"]').filter(
                    has_text=re.compile(r'^\s*Koita관리자\s*$'))
                count = candidates.count()
                total += count
                for index in range(count):
                    candidate = candidates.nth(index)
                    if candidate.is_visible():
                        matches.append(candidate)
                    else:
                        hidden += 1
            summary = (frames, total, len(matches), hidden)
            if summary != last_summary:
                report(f'관리자 메뉴 DOM 확인: 그룹웨어 프레임 {frames}개, 일치 {total}개, 표시 {len(matches)}개, 숨김 {hidden}개')
                last_summary = summary
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                report('관리자 메뉴 확인 중단: 화면에 표시된 동일 메뉴가 여러 개입니다. 임의로 클릭하지 않았습니다.')
                return None
            if hidden and not office_open_attempted:
                parents = []
                for frame in page.frames:
                    if not trusted_url(frame.url):
                        continue
                    offices = frame.locator('li[name="topmenu_li"][id="javamail/index_javamail.aspx"]')
                    for index in range(offices.count()):
                        office = offices.nth(index)
                        if office.is_visible():
                            parents.append(office)
                if len(parents) == 1:
                    office_open_attempted = True
                    report('숨겨진 관리자 메뉴 확인 · 마이오피스 메뉴를 펼치는 중…')
                    office = parents[0]
                    # Hover first for CSS dropdowns. Click the visible icon only
                    # if hover does not reveal the actual submenu.
                    office.hover(timeout=5000)
                    page.wait_for_timeout(400)
                    submenu = office.locator('li[name="submenu_li"]:visible').filter(
                        has_text=re.compile(r'^\s*Koita관리자\s*$'))
                    if submenu.count() == 0 and not stop.is_set():
                        office.locator('span.icon_menu.top_myOffice').click(timeout=5000)
                elif len(parents) > 1:
                    report('마이오피스 메뉴가 화면에 여러 개 표시됩니다. 화면 확인이 필요합니다.')
                    return None
            page.wait_for_timeout(250)
        except PlaywrightError:
            # Navigation can replace the DOM while login is completing.
            if page.is_closed():
                report('관리자 메뉴 확인 중단: 그룹웨어 창이 닫혔습니다.')
                return None
            page.wait_for_timeout(250)
    if not stop.is_set():
        if last_summary and last_summary[1] and not last_summary[2]:
            report('관리자 메뉴를 HTML에서 찾았지만 마이오피스 펼치기 후에도 숨겨져 있습니다. 현재 메뉴 화면 확인이 필요합니다.')
        else:
            report('관리자 메뉴를 현재 그룹웨어 창과 프레임에서 찾지 못했습니다. 로그인 완료 여부와 메뉴가 있는 창을 확인해 주세요.')
    return None


def open_registration(page, stop, report):
    """Use only user-supplied controls. Stop at the GET registration page."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    admin = page
    step = '로그인 후 Koita관리자 메뉴 확인'
    try:
        report('로그인 후 Koita관리자 메뉴를 기다리는 중…')
        menu = find_admin_menu(page, stop, report)
        if menu is None or stop.is_set():
            return None
        if not trusted_url(page.url):
            report('중단: 그룹웨어 주소 또는 Koita관리자 메뉴를 확인해 주세요.')
            return None
        step = 'Koita관리자 새 창 열기'
        report('로그인 후 관리자 메뉴 확인 · Koita관리자 새 창을 여는 중…')
        with page.expect_popup(timeout=15000) as popup:
            menu.click()
        admin = popup.value
        admin.wait_for_load_state('domcontentloaded', timeout=30000)

        def check_admin():
            address = urlsplit(admin.url)
            if (address.scheme != 'https' or address.hostname != 'www.koita.or.kr'
                    or address.port not in (None, 443) or address.username or address.password):
                raise ValueError('Unexpected admin origin')

        for label, selector, target in (
            ('게시판 관리', BOARD_MENU, '/admmgr/board/commBoardGovRnDList.do'),
            ('산기협', PRESS_MENU, '/admmgr/board/commBoardPressList.do'),
            ('언론홍보', PRESS_PUBLICITY, '/admmgr/board/commBoardPressList.do'),
            ('등록 페이지 열기', 'span.rit_btn_section input[type="button"][value="등록"][onclick*="commBoardPressRegist.do"]', '/admmgr/board/commBoardPressRegist.do'),
        ):
            if stop.is_set():
                return None
            step = label
            check_admin()
            report(label + ' 진행 중…')
            control = admin.locator(selector)
            count = control.count()
            if count > 1:
                report(label + f' 중단: 지정한 메뉴가 {count}개 일치합니다. 메뉴 계층 확인이 필요합니다.')
                return None
            control.wait_for(state='visible', timeout=15000)
            control.click()
            admin.wait_for_url(lambda url: urlsplit(url).path == target, timeout=20000)
            admin.wait_for_load_state('domcontentloaded', timeout=20000)
            check_admin()
        report('테스트 완료: 산기협 등록 페이지가 열렸습니다. 내용 입력·파일 업로드·게시물 저장은 실행하지 않았습니다.')
        return admin
    except PlaywrightTimeout:
        report(step + ' 시간 초과: 로그인·추가 인증 또는 메뉴 표시 상태를 브라우저에서 확인해 주세요. 자동 재시도하지 않습니다.')
    except Exception as error:
        # Class only: Playwright error messages can contain page data.
        report(step + ' 중단 (' + type(error).__name__ + '): 해당 단계 처리에 실패했습니다. 화면 구조 불일치로 단정할 수 없습니다.')
    return None
