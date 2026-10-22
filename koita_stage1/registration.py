from pathlib import Path
from urllib.parse import urlsplit
from press_document import NOTE
from news_catalog import valid_article


def set_text_field(field, value):
    """Assign to the exact input element, independent of the active cursor."""
    field.evaluate('''(element, value) => {
        if (!(element instanceof HTMLInputElement) || element.disabled || element.readOnly)
            throw new Error('Unexpected input element');
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(element, value);
        element.dispatchEvent(new Event('input', {bubbles:true}));
        element.dispatchEvent(new Event('change', {bubbles:true}));
    }''', value)
    if field.input_value() != value:
        raise ValueError('Input value mismatch')


def form_snapshot(page):
    return page.evaluate('''() => {
        const values = {};
        for (const name of ['title', 'userNm', 'vwRegDt']) {
            const field = document.querySelector('input[name="' + name + '"]');
            if (field) values[name] = field.value;
        }
        if (typeof CrossEditor !== 'undefined' && typeof CrossEditor.GetBodyValue === 'function') {
            const doc = new DOMParser().parseFromString(CrossEditor.GetBodyValue(), 'text/html');
            values.bodyText = doc.body.textContent;
            values.images = [...doc.images].map(img => img.getAttribute('src'));
        }
        return values;
    }''')


def fill_related_sites(page, articles, stop, report):
    if not articles:
        return True
    address = urlsplit(page.url)
    if (address.scheme != 'https' or address.hostname != 'www.koita.or.kr'
            or address.path != '/admmgr/board/commBoardPressRegist.do'):
        report('관련사이트 입력 중단: 등록 페이지 도착을 확인하지 못했습니다.')
        return False
    try:
        before = form_snapshot(page)
        if not all(valid_article(article) for article in articles):
            report('관련사이트 입력 중단: 선택 기사의 제목·출처·URL을 확인해 주세요.')
            return False
        rows = page.locator('#relSiteTbody > tr')
        count = rows.count()
        if count < 1 or count > len(articles):
            report('관련사이트 입력 중단: 기존 행 수가 예상과 다릅니다.')
            return False
        # Avoid overwriting any manually entered data.
        for index in range(count):
            for name in ('relSiteTitle', 'relSiteUrl', 'relSiteMedia'):
                if rows.nth(index).locator(f'input[name="{name}"]').input_value().strip():
                    report('관련사이트 입력 중단: 이미 입력된 값이 있어 덮어쓰지 않았습니다.')
                    return False
        add = page.locator('input[type="button"][onclick*="addTR"][onclick*="relSiteTbody"]')
        if count < len(articles) and add.count() != 1:
            report('관련사이트 입력 중단: 추가 버튼이 없거나 여러 개입니다.')
            return False
        for expected in range(count + 1, len(articles) + 1):
            if stop.is_set():
                return False
            add.click()
            page.wait_for_function("count => document.querySelectorAll('#relSiteTbody > tr').length === count", arg=expected, timeout=5000)
        for index, article in enumerate(articles):
            if stop.is_set():
                return False
            report(f'관련사이트 {index + 1}/{len(articles)} 입력 중…')
            row = rows.nth(index)
            for name, value in (('relSiteTitle', article.title), ('relSiteUrl', article.url), ('relSiteMedia', article.press)):
                field = row.locator(f'input[name="{name}"]')
                set_text_field(field, value)
        if form_snapshot(page) != before:
            report('관련사이트 입력 후 검증 중단: 제목·작성자·게시일자 또는 본문이 변경되었습니다. 최종 등록은 누르지 않았습니다.')
            return False
        report(f'관련사이트 {len(articles)}개 입력 완료 · 최종 등록은 누르지 않았습니다.')
        return True
    except Exception as error:
        report('관련사이트 입력 중단 (' + type(error).__name__ + '): 행과 입력칸을 확인해 주세요. 최종 등록은 누르지 않았습니다.')
        return False


def fill_registration(page, title, path, publication_date, body, stop, report):
    address = urlsplit(page.url)
    if (address.scheme != 'https' or address.hostname != 'www.koita.or.kr'
            or address.path != '/admmgr/board/commBoardPressRegist.do'):
        report('입력 중단: 산기협 등록 페이지가 아닙니다.')
        return False
    stage = '등록 폼 필수 요소 확인'
    try:
        controls = {
            'category': '#code', 'title': 'input[name="title"]',
            'notice': 'input[name="topYn"][value="N"]',
            'author': 'input[name="userNm"]', 'date': '#vwRegDt',
            'public': 'input[name="vwYn"][value="Y"]',
            'attachment': '#coa_html_upload[type="file"]',
        }
        for selector in controls.values():
            if page.locator(selector).count() != 1:
                report('입력 중단: 등록 폼의 필수 요소가 없거나 여러 개입니다.')
                return False
        if stop.is_set():
            return False
        report('편집기 초기화 완료를 확인한 뒤 기본 항목을 입력합니다…')
        stage = '나모 편집기 초기화 확인'
        page.wait_for_function('''() => {
            try {
                if (typeof CrossEditor === 'undefined' ||
                    typeof CrossEditor.SetBodyValue !== 'function' ||
                    typeof CrossEditor.GetBodyValue !== 'function') return false;
                const frame = document.getElementById('NamoSE_Ifr__conts');
                if (frame && (!frame.contentDocument || frame.contentDocument.readyState !== 'complete')) return false;
                return typeof CrossEditor.GetBodyValue() === 'string';
            } catch (_) { return false; }
        }''', timeout=20000)
        report('구분·제목·공지여부·작성자·게시일자·공개여부 입력 중…')
        stage = '기본 항목 입력'
        page.locator(controls['category']).select_option('004002000')
        set_text_field(page.locator(controls['title']), title)
        page.locator(controls['notice']).check()
        set_text_field(page.locator(controls['author']), '이승현')
        set_text_field(page.locator(controls['date']), publication_date)
        page.locator(controls['public']).check()
        if stop.is_set():
            return False
        report('첫 페이지 JPG와 안내 문구를 내용에 삽입 중…')
        stage = '나모 편집기 초기화 확인'
        page.wait_for_function('''() => typeof CrossEditor !== 'undefined' &&
            typeof CrossEditor.SetBodyValue === 'function' &&
            typeof CrossEditor.GetBodyValue === 'function' ''', timeout=15000)
        stage = '나모 편집기 본문 적용'
        page.evaluate('''html => {
            CrossEditor.SetBodyValue(html);
            document.getElementById('conts').value = CrossEditor.GetBodyValue();
        }''', body)
        stage = '편집기 본문 반환값 확인'
        page.wait_for_function('''note => {
            const value = CrossEditor.GetBodyValue();
            const doc = new DOMParser().parseFromString(value, 'text/html');
            return (doc.body.textContent || '').includes(note) &&
                !!doc.querySelector('img[src^="data:image/jpeg;base64,"]');
        }''', arg=NOTE, timeout=10000)
        stage = '편집기 JPG 표시 확인'
        rendered = False
        for _ in range(40):
            if stop.is_set():
                return False
            for frame in page.frames:
                if frame.evaluate('''() => [...document.images].some(img =>
                    img.src.startsWith('data:image/jpeg;base64,') && img.complete && img.naturalWidth > 0)'''):
                    rendered = True
                    break
            if rendered:
                break
            page.wait_for_timeout(250)
        if not rendered:
            report('내용 입력 중단: 편집기에서 JPG 표시를 확인하지 못했습니다. 이미지 업로드 방식 확인이 필요합니다.')
            return False
        report('HWPX 첨부 선택 중… 사이트가 확장자를 허용하는지 확인합니다.')
        stage = 'HWPX 첨부 선택 및 목록 확인'
        page.locator(controls['attachment']).set_input_files(str(Path(path).resolve()))
        page.locator('#coa_view_box').get_by_text(Path(path).name, exact=False).wait_for(state='visible', timeout=10000)
        stage = '본문·첨부 완료 후 기본 항목 재검증'
        for key, value in (('category', '004002000'), ('title', title), ('author', '이승현'), ('date', publication_date)):
            if page.locator(controls[key]).input_value() != value:
                raise ValueError('Basic field changed during editor update')
        if not page.locator(controls['notice']).is_checked() or not page.locator(controls['public']).is_checked():
            raise ValueError('Radio option changed during editor update')
        report('입력 완료: JPG·안내 문구와 HWPX 첨부 목록을 확인했습니다. 첨부는 대기 목록 기준이며 서버 전송 완료는 미검증입니다. 최종 등록은 누르지 않았습니다.')
        return True
    except Exception as error:
        report(stage + ' 중단 (' + type(error).__name__ + '): 해당 입력 단계의 화면을 확인해 주세요. 최종 등록은 누르지 않았습니다.')
        return False
