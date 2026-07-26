import os
import re
from pathlib import Path
import pdfplumber
from core.models import Blueprint
from core.materials import MaterialLibrary


class PDFAnalyzer:

    @staticmethod
    def parse_filename(filename: str) -> tuple[str, str, str]:
        name_without_ext = os.path.splitext(filename)[0]
        doc_type = "Деталь"

        if re.search(r'[_ \-]СБ([_ \.]|$)', name_without_ext, flags=re.IGNORECASE):
            doc_type = "Сборка"
            name_without_ext = re.sub(r'[_ \-]СБ([_ \.]|$)', '', name_without_ext, flags=re.IGNORECASE)
        elif re.search(r'[_ \-]СП([_ \.]|$)', name_without_ext, flags=re.IGNORECASE):
            doc_type = "Спецификация"
            name_without_ext = re.sub(r'[_ \-]СП([_ \.]|$)', '', name_without_ext, flags=re.IGNORECASE)

        name_without_ext = re.sub(r'(\d)([А-Яа-яA-Za-z])', r'\1 \2', name_without_ext)

        parts = re.split(r'[_ ]+', name_without_ext.strip(), maxsplit=1)
        number = parts[0].strip()
        name = parts[1].replace('_', ' ').strip() if len(parts) > 1 else ""

        return number, name, doc_type

    @staticmethod
    def extract_material(pdf_path: Path) -> str:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if not pdf.pages:
                    return "Не удалось прочитать"

                page = pdf.pages[0]
                mm = 2.83465
                width, height = float(page.width), float(page.height)

                tb_zone = (max(0, width - 195 * mm), max(0, height - 65 * mm), width, height)
                words = page.crop(tb_zone).extract_words()

                bottom_edge = height - 5 * mm
                right_edge = width - 5 * mm

                for w in words:
                    clean_word = w['text'].lower().replace('.', '').replace('c', 'с').strip()
                    if 'масс' in clean_word:
                        bottom_edge = w['top'] + (40 * mm)
                        right_edge = w['x1'] + (20 * mm)
                        break
                    elif 'масшт' in clean_word:
                        bottom_edge = w['top'] + (40 * mm)
                        right_edge = w['x1'] + (5 * mm)
                        break

                name_box = (max(0, right_edge - 119.5 * mm), max(0, bottom_edge - 39 * mm), right_edge - 50.5 * mm, bottom_edge - 16 * mm)
                if name_box[2] > name_box[0] and name_box[3] > name_box[1]:
                    name_text = page.crop(name_box).extract_text()
                    if name_text and re.search(r'(?i)Сборочн', name_text):
                        return "ПРОПУСК_СБ"

                mat_box = (max(0, right_edge - 119.5 * mm), max(0, bottom_edge - 14.5 * mm), right_edge - 50.5 * mm, bottom_edge - 0.5 * mm)
                if mat_box[2] > mat_box[0] and mat_box[3] > mat_box[1]:
                    raw_text = page.crop(mat_box).extract_text()
                    return MaterialLibrary.match(raw_text)

        except Exception:
            pass

        return "Не удалось прочитать"

    def process_file(self, pdf_path: Path) -> Blueprint:
        doc = Blueprint(pdf_path)
        doc.number, doc.name, doc.doc_type = self.parse_filename(doc.filename)

        if doc.doc_type == "Деталь":
            material = self.extract_material(pdf_path)
            if material == "ПРОПУСК_СБ":
                doc.doc_type = "Сборка"
                doc.material = "-"
            else:
                doc.material = material

        return doc