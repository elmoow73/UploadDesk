IMAGE_WIDTH = 700


def resize_press_image(image):
    from PySide6.QtCore import Qt
    if image.isNull():
        raise ValueError('이미지를 읽을 수 없습니다.')
    if image.width() == IMAGE_WIDTH:
        return image
    return image.scaledToWidth(IMAGE_WIDTH, Qt.TransformationMode.SmoothTransformation)
