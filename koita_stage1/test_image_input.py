from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from press_document import prepare_document


class ImageInputTests(unittest.TestCase):
    def test_native_output_is_saved_as_700px_jpeg(self):
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QIODevice
        from hancom_render import render_first_page
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.hwpx'
            source.write_bytes(b'unchanged')
            output = root / 'resized.jpg'
            def native(command, **kwargs):
                image = QImage(1240, 1754, QImage.Format.Format_RGB32)
                image.fill(0xffffff)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                assert image.save(buffer, 'BMP')
                Path(command[-1]).write_bytes(bytes(buffer.data()))
                return CompletedProcess(command, 0, b'', b'')
            with patch('hancom_render.subprocess.run', side_effect=native):
                dimensions = render_first_page(source, output)
            data = output.read_bytes()
            self.assertTrue(data.startswith(b'\xff\xd8'))
            saved = QImage.fromData(data)
            self.assertEqual((saved.width(), saved.height()), (700, 990))
            self.assertEqual(dimensions, (700, 990))
            self.assertEqual(source.read_bytes(), b'unchanged')

    def test_selected_image_replaces_missing_preview_without_hancom(self):
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QIODevice
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'sample.hwpx'
            image_path = root / 'manual.png'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('Contents/section0.xml', '<p xmlns:h="test"><h:t>(온라인) 2026. 10. 21(수)</h:t></p>')
            image = QImage(40, 60, QImage.Format.Format_RGB32)
            image.fill(0xffffff)
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self.assertTrue(image.save(buffer, 'PNG'))
            image_path.write_bytes(bytes(buffer.data()))
            with patch('hancom_render.render_first_page') as renderer:
                publication_date, body, dimensions = prepare_document(source, image_path=image_path)
                renderer.assert_not_called()
            self.assertEqual(publication_date, '2026-10-21')
            self.assertEqual(dimensions, (700, 1050))
            self.assertIn('data:image/jpeg;base64,', body)

    def test_missing_preview_uses_generated_image(self):
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QIODevice
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'sample.hwpx'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('Contents/section0.xml', '<p xmlns:h="test"><h:t>(온라인) 2026. 10. 21(수)</h:t></p>')
            def render(path, output):
                image = QImage(120, 180, QImage.Format.Format_RGB32)
                image.fill(0xffffff)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                assert image.save(buffer, 'JPG')
                Path(output).write_bytes(bytes(buffer.data()))
                return 120, 180
            with patch('hancom_render.render_first_page', side_effect=render) as renderer:
                publication_date, body, dimensions = prepare_document(source)
            renderer.assert_called_once()
            self.assertEqual(publication_date, '2026-10-21')
            self.assertEqual(dimensions, (700, 1050))


if __name__ == '__main__':
    unittest.main(verbosity=2)
