import logging
import os
import re
from pathlib import Path
from typing import Optional

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.page import Page

from core.models import Blueprint, MaterialResult, MaterialStatus
from core.materials import MaterialLibrary
from core.blueprint_helpers import (
    Box,
    PT_PER_MM,
    FORM1_WIDTH_MM,
    FORM1_HEIGHT_MM,
    FORM1_NAME_MM,
    FORM1_MATERIAL_MM,
    map_form1_cell,
    extract_cell_candidates,
    fix_cp1251_mojibake,
)
from core.debug_visualizer import DebugVisualizer


class FilenameParser:

    @staticmethod
    def parse(filename: str) -> tuple[str, str, str, list[str]]:
        stem = os.path.splitext(filename)[0].strip()
        doc_type = "Деталь"
        warnings: list[str] = []

        if re.search(r"(?:[_ \-]|^|\d)[СC][БB](?:[_ \-.]|$)", stem, flags=re.IGNORECASE):
            doc_type = "Сборка"
            stem = re.sub(r"[_ \-]?[СC][БB](?=[_ \-.]|$)", "", stem, flags=re.IGNORECASE)
        elif re.search(r"(?:[_ \-]|^|\d)[СC]П(?:[_ \-.]|$)", stem, flags=re.IGNORECASE):
            doc_type = "Спецификация"
            stem = re.sub(r"[_ \-]?[СC]П(?=[_ \-.]|$)", "", stem, flags=re.IGNORECASE)

        parts = re.split(r"[_ ]+", stem.strip(), maxsplit=1)
        if len(parts) == 2:
            number = parts[0].strip()
            name = parts[1].replace("_", " ").strip()
        else:
            match = re.match(r"^([А-Яа-яA-Za-z0-9.\-]+?\d[А-ЯA-Z]?)([А-ЯЁ][а-яё].*)$", stem)
            if match:
                number, name = match.group(1), match.group(2)
                warnings.append("Разделено без явного пробела")
            else:
                number, name = stem, ""

        return number, name, doc_type, warnings


class TitleBlockLocator:

    @classmethod
    def locate_form1(cls, page: Page) -> tuple[Box, float]:
        width, height = float(page.width), float(page.height)
        mm = PT_PER_MM

        tb_zone = (max(0.0, width - 195 * mm), max(0.0, height - 65 * mm), width, height)
        words = page.crop(tb_zone).extract_words()

        bottom_edge = height - 5.0 * mm
        right_edge = width - 5.0 * mm
        score = 0.5

        for w in words:
            raw_w = fix_cp1251_mojibake(w["text"])
            clean_word = raw_w.lower().replace(".", "").replace("c", "с").strip()
            if "масс" in clean_word:
                bottom_edge = float(w["top"]) + (40.0 * mm)
                right_edge = float(w["x1"]) + (20.0 * mm)
                score = 1.0
                break
            elif "масшт" in clean_word:
                bottom_edge = float(w["top"]) + (40.0 * mm)
                right_edge = float(w["x1"]) + (5.0 * mm)
                score = 1.0
                break

        nom_w = FORM1_WIDTH_MM * mm
        nom_h = FORM1_HEIGHT_MM * mm

        title_box = Box(
            x0=right_edge - nom_w,
            top=bottom_edge - nom_h,
            x1=right_edge,
            bottom=bottom_edge,
        )
        return title_box, score


class PDFAnalyzer:
    def __init__(self, debug_output_dir: Optional[Path] = None, debug_all: bool = False):
        self.debug_output_dir = debug_output_dir
        self.debug_all = debug_all

    @staticmethod
    def parse_filename(filename: str) -> tuple[str, str, str]:
        number, name, doc_type, _ = FilenameParser.parse(filename)
        return number, name, doc_type

    def process_file(self, pdf_path: Path) -> Blueprint:
        doc = Blueprint(pdf_path)
        doc.number, doc.name, doc.doc_type, fn_warnings = FilenameParser.parse(doc.filename)
        doc.warnings.extend(fn_warnings)

        if doc.doc_type in ("Сборка", "Спецификация"):
            doc.material_result = MaterialResult(status=MaterialStatus.NOT_APPLICABLE)
            return doc

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if not pdf.pages:
                    doc.material_result = MaterialResult(status=MaterialStatus.READ_ERROR)
                    return doc

                page = pdf.pages[0]
                title_box, loc_score = TitleBlockLocator.locate_form1(page)

                name_cell = map_form1_cell(title_box, FORM1_NAME_MM)
                name_raw, _ = extract_cell_candidates(page, name_cell)
                if name_raw and re.search(r"(?i)сборочн", fix_cp1251_mojibake(name_raw)):
                    doc.doc_type = "Сборка"
                    doc.material_result = MaterialResult(
                        status=MaterialStatus.NOT_APPLICABLE,
                        raw_text=name_raw,
                        page_index=0,
                        bbox=name_cell.as_tuple(),
                        location_score=loc_score,
                    )
                    return doc

                mat_cell = map_form1_cell(title_box, FORM1_MATERIAL_MM)
                mat_raw, method = extract_cell_candidates(page, mat_cell)

                doc.material_result = MaterialLibrary.evaluate(
                    raw_text=mat_raw,
                    page_index=0,
                    bbox=mat_cell.as_tuple(),
                    extraction_method=method,
                    location_score=loc_score,
                )

                if self.debug_output_dir is not None:
                    is_suspicious = (
                        doc.material_result.status != MaterialStatus.MATCHED
                        or loc_score < 0.6
                    )
                    if self.debug_all or is_suspicious:
                        DebugVisualizer.save_diagnostic_bundle(
                            page=page,
                            doc=doc,
                            title_box=title_box,
                            output_dir=self.debug_output_dir,
                        )

                if hasattr(page, "close"):
                    page.close()

        except (PDFSyntaxError, PermissionError, OSError) as e:
            logging.warning(f"Ошибка чтения PDF {pdf_path.name}: {e}")
            doc.material_result = MaterialResult(status=MaterialStatus.READ_ERROR, warnings=(str(e),))
        except Exception as e:
            logging.exception(f"Сбой при анализе {pdf_path.name}: {e}")
            doc.material_result = MaterialResult(status=MaterialStatus.READ_ERROR, warnings=(str(e),))

        return doc