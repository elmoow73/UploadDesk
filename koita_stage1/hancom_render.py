"""Native first-page rendering in an isolated Hancom Automation instance."""
from pathlib import Path
import subprocess
import sys
import tempfile
from press_image import resize_press_image


class RenderError(ValueError):
    pass


def render_first_page(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source.suffix.lower() != '.hwpx':
        raise RenderError('변환할 HWPX 파일을 선택해 주세요.')
    if output.exists():
        raise RenderError('출력 파일이 이미 있습니다. 새 출력 경로를 사용해 주세요.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='koita_native_') as temporary:
        native_image = Path(temporary) / 'first_page.bmp'
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), '--render', str(source), str(native_image)],
                capture_output=True, timeout=120,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise RenderError('한글 이미지 변환 시간이 초과되었습니다. 한글의 파일 접근 확인 창을 확인해 주세요. 열려 있는 변환용 한글 창은 직접 닫아 주세요.') from None
        native_bytes = native_image.read_bytes() if native_image.is_file() else None
    if result.returncode != 0 or native_bytes is None:
        # Child stderr may contain document paths; never forward raw exceptions.
        reasons = {2: '한글이 HWPX 열기를 완료하지 못했습니다. 파일 접근 확인 창을 허용해 주세요.',
                   3: '한글의 페이지 이미지 생성 API가 실패를 반환했습니다.',
                   4: '한글 자동화 API 호출 중 오류가 발생했습니다.'}
        detail = result.stdout.decode('ascii', errors='ignore').strip()
        if not detail.startswith('STAGE:') or len(detail) > 120:
            detail = ''
        raise RenderError(reasons.get(result.returncode, '한글 출력 이미지가 생성되지 않았습니다.') +
                          (' [' + detail + ']' if detail else '') + ' JPG·PNG 직접 선택도 사용할 수 있습니다.')
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer, QIODevice
    image = QImage.fromData(native_bytes)
    if image.isNull() or image.width() < 100 or image.height() < 100:
        raise RenderError('생성된 첫 페이지 이미지를 읽지 못했습니다.')
    image = resize_press_image(image)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'JPG', 95):
        raise RenderError('한글 페이지 이미지를 JPG로 인코딩하지 못했습니다.')
    output.write_bytes(bytes(buffer.data()))
    return image.width(), image.height()


def native_render(source, output):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    hwp = None
    stage = 'create'
    try:
        hwp = win32com.client.DispatchEx('HWPFrame.HwpObject')
        # Leave security prompts intact. No security module registration or
        # message-box suppression, and never save the original document.
        stage = 'show-window'
        hwp.XHwpWindows.Item(0).Visible = True
        stage = 'open'
        if not hwp.Open(str(Path(source).resolve()), '', ''):
            return 2
        # Signature verified from this PC's Hancom COM type information.
        # Page number is zero-based; 150 dpi, 24-bit BMP.
        # This Hancom version emits BMP even when passed 'jpg'; encode to JPEG
        # in the parent process rather than relying on the requested extension.
        stage = 'create-page-image'
        if not hwp.CreatePageImage(str(Path(output).resolve()), 0, 150, 24, 'bmp'):
            return 3
        return 0
    except Exception as error:
        print('STAGE:' + stage + ':' + type(error).__name__)
        return 4
    finally:
        if hwp is not None:
            try:
                hwp.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--render':
        sys.exit(native_render(sys.argv[2], sys.argv[3]))
    sys.exit(1)
