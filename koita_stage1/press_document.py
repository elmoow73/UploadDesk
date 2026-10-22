import base64
from datetime import date
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
import unicodedata
import tempfile
from press_image import resize_press_image

NOTE = '* 자세한 내용은 첨부파일을 확인해 주시기 바랍니다.'


class DocumentError(ValueError):
    """Safe, fixed diagnostic text without document content or credentials."""


def online_date(text):
    # Full-width punctuation and zero-width formatting can occur in HWPX.
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Cf')
    marker = r'\(\s*온\s*라\s*인\s*\)'
    if not re.search(marker, text):
        raise DocumentError('문서에서 (온라인) 보도일 표시를 찾지 못했습니다.')
    # A trailing dot after the day is optional: 20.(화) and 21(수).
    matches = re.findall(marker + r'\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})(?!\d)\s*\.?', text)
    try:
        values = {date(*map(int, item)).isoformat() for item in matches}
    except ValueError:
        raise DocumentError('온라인 보도일에 유효하지 않은 날짜가 있습니다.') from None
    if not values:
        raise DocumentError('(온라인) 표시는 있으나 바로 뒤에서 연·월·일을 읽지 못했습니다.')
    if len(values) > 1:
        raise DocumentError('서로 다른 온라인 보도일이 여러 개 있어 확정할 수 없습니다.')
    return values.pop()


def prepare_document(path, output=None, image_path=None):
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer, QIODevice
    source = Path(path)
    if source.suffix.lower() != '.hwpx' or not source.is_file():
        raise DocumentError('존재하는 HWPX 파일을 선택해 주세요.')
    try:
        with zipfile.ZipFile(source) as archive:
            texts = []
            for name in archive.namelist():
                if re.fullmatch(r'Contents/section\d+\.xml', name):
                    node = ET.fromstring(archive.read(name))
                    texts.append(' '.join(n.text or '' for n in node.iter() if n.tag.endswith('}t')))
            publication_date = online_date(' '.join(texts))
            if image_path:
                image = QImage.fromData(Path(image_path).read_bytes())
            elif 'Preview/PrvImage.png' in archive.namelist():
                image = QImage.fromData(archive.read('Preview/PrvImage.png'))
            else:
                image = None
    except zipfile.BadZipFile:
        raise DocumentError('선택한 파일이 정상적인 HWPX 압축 형식이 아닙니다.') from None
    except KeyError:
        raise DocumentError('HWPX에 첫 페이지 미리보기 이미지가 없습니다.') from None
    except ET.ParseError:
        raise DocumentError('HWPX 본문 XML을 읽지 못했습니다.') from None
    except OSError:
        raise DocumentError('HWPX 파일을 읽을 수 없습니다. 접근 권한이나 파일 잠금 상태를 확인해 주세요.') from None
    if image is None:
        from hancom_render import render_first_page, RenderError
        try:
            with tempfile.TemporaryDirectory(prefix='koita_render_') as temporary:
                generated = Path(temporary) / 'first_page.jpg'
                render_first_page(source, generated)
                image = QImage.fromData(generated.read_bytes())
        except RenderError as error:
            raise DocumentError(str(error)) from None
    if image.isNull():
        raise DocumentError('HWPX 첫 페이지 미리보기를 읽지 못했습니다.')
    image = resize_press_image(image).convertToFormat(QImage.Format.Format_RGB32)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'JPG', 95):
        raise DocumentError('첫 페이지 JPG 변환에 실패했습니다.')
    jpeg = bytes(buffer.data())
    if output is not None:
        Path(output).write_bytes(jpeg)
    encoded = base64.b64encode(jpeg).decode('ascii')
    body = f'<p><img src="data:image/jpeg;base64,{encoded}" alt="보도자료 첫 페이지" width="{image.width()}" height="{image.height()}" style="width:700px;max-width:100%;height:auto;"></p><p>{NOTE}</p>'
    return publication_date, body, (image.width(), image.height())
