from pathlib import Path
import unittest
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import patch
from press_document import online_date, DocumentError, prepare_document


class DocumentDateTests(unittest.TestCase):
    def test_day_with_or_without_trailing_dot(self):
        for text in ('(온라인) 2026. 10. 21.(수) 16:00 이후',
                     '(온라인) 2026. 10. 21(수) 16:00 이후'):
            with self.subTest(text=text):
                self.assertEqual(online_date(text), '2026-10-21')

    def test_online_date_not_print_date(self):
        self.assertEqual(online_date('(온라인) 2026. 10. 21(수) 16:00 이후 (지 면) 2026. 10. 22(목) 조간'), '2026-10-21')

    def test_unicode_and_split_marker(self):
        self.assertEqual(online_date('（온 라\u200b인）\n２０２６．１０．２１（수）'), '2026-10-21')

    def test_ambiguous_invalid_or_missing_dates_stop(self):
        for text in ('(온라인) 2026. 10. 21 (온라인) 2026. 10. 22',
                     '(온라인) 2026. 2. 30', '(지면) 2026. 10. 22',
                     '(온라인) 추후 발표 (지면) 2026. 10. 22',
                     '(온라인) 2026. 10. 211(수)'):
            with self.subTest(text=text), self.assertRaises(DocumentError):
                online_date(text)

    def test_actual_demoday_hwpx(self):
        folder = Path('C:/Users/21017/Desktop/★★★ 업무/★★★ 언론보도/★★★ 보도자료/261021_데모데이/최종')
        files = list(folder.glob('*.hwpx'))
        if not files:
            self.skipTest('Actual demoday sample is not available')
        for file in files:
            with zipfile.ZipFile(file) as archive:
                texts = []
                for name in archive.namelist():
                    if name.startswith('Contents/section') and name.endswith('.xml'):
                        node = ET.fromstring(archive.read(name))
                        texts.append(' '.join(n.text or '' for n in node.iter() if n.tag.endswith('}t')))
                self.assertEqual(online_date(' '.join(texts)), '2026-10-21')
                if 'Preview/PrvImage.png' not in archive.namelist():
                    from hancom_render import RenderError
                    with patch('hancom_render.render_first_page', side_effect=RenderError('변환기 테스트 중단')) as renderer:
                        with self.assertRaisesRegex(DocumentError, '변환기 테스트 중단'):
                            prepare_document(file)
                        renderer.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
