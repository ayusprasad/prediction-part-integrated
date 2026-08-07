from pathlib import Path

from paddleocr import PaddleOCR


class OCRService:

    def __init__(self):

        self.ocr = PaddleOCR(
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
            lang="en"
        )

    def extract_text(self, image_path: Path):

        result = self.ocr.predict(str(image_path))

        return result