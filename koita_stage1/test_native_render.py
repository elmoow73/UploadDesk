"""Explicit integration check: starts Hancom; not run by unittest discovery."""
from pathlib import Path
import hashlib
import uuid
from hancom_render import render_first_page
from press_document import prepare_document


def main():
    source = next(Path('C:/Users/21017/Desktop/★★★ 업무/★★★ 언론보도/★★★ 보도자료/261021_데모데이/최종').glob('*.hwpx'))
    before = hashlib.sha256(source.read_bytes()).digest()
    output = Path(__file__).parent / 'generated' / ('demoday_' + uuid.uuid4().hex + '.jpg')
    dimensions = render_first_page(source, output)
    publication_date, body, _ = prepare_document(source, image_path=output)
    assert before == hashlib.sha256(source.read_bytes()).digest()
    assert publication_date == '2026-10-21'
    assert 'data:image/jpeg;base64,' in body
    print('PASS: native first-page render', dimensions, 'date', publication_date, 'source unchanged')
    print(output.as_posix().encode('unicode_escape').decode())


if __name__ == '__main__':
    main()
