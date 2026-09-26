import json
import logging
from pathlib import Path
from pdfplumber.page import Page

from core.models import Blueprint
from core.blueprint_helpers import (
    Box,
    FORM1_NAME_MM,
    FORM1_MATERIAL_MM,
    map_form1_cell,
    extract_cell_candidates,
)


class DebugVisualizer:

    @staticmethod
    def save_diagnostic_bundle(
        page: Page,
        doc: Blueprint,
        title_box: Box,
        output_dir: Path,
        dpi: int = 200,
    ) -> None:
        debug_folder = output_dir / "_debug_stamps"
        debug_folder.mkdir(parents=True, exist_ok=True)

        stem = doc.path.stem
        name_cell = map_form1_cell(title_box, FORM1_NAME_MM)
        mat_cell = map_form1_cell(title_box, FORM1_MATERIAL_MM)

        try:
            img_obj = page.to_image(resolution=dpi)

            img_obj.draw_rect(title_box.as_tuple(), stroke="blue", stroke_width=3)

            img_obj.draw_rect(name_cell.as_tuple(), stroke="orange", stroke_width=2)

            img_obj.draw_rect(mat_cell.as_tuple(), stroke="red", stroke_width=3)

            char_centers = []
            for ch in page.chars:
                cx = (float(ch["x0"]) + float(ch["x1"])) / 2.0
                cy = (float(ch["top"]) + float(ch["bottom"])) / 2.0
                if title_box.x0 <= cx <= title_box.x1 and title_box.top <= cy <= title_box.bottom:
                    char_centers.append((cx, cy))

            if char_centers:
                img_obj.draw_circles(char_centers, radius=1.5, fill="green", stroke="green")

            scale = dpi / 72.0
            pil_img = img_obj.annotated
            p_w, p_h = pil_img.size

            crop_left = max(0, int((title_box.x0 - 15) * scale))
            crop_top = max(0, int((title_box.top - 15) * scale))
            crop_right = min(p_w, int((title_box.x1 + 15) * scale))
            crop_bottom = min(p_h, int((title_box.bottom + 15) * scale))

            if crop_right > crop_left and crop_bottom > crop_top:
                cropped_pil = pil_img.crop((crop_left, crop_top, crop_right, crop_bottom))
            else:
                cropped_pil = pil_img

            png_path = debug_folder / f"{stem}_stamp.png"
            cropped_pil.save(png_path)

        except Exception as e:
            logging.warning(f"Не удалось отрендерить PNG штампа для {doc.filename}: {e}")

        try:
            chars_in_mat = [
                {
                    "text": ch.get("text"),
                    "x0": round(float(ch["x0"]), 2),
                    "top": round(float(ch["top"]), 2),
                    "x1": round(float(ch["x1"]), 2),
                    "bottom": round(float(ch["bottom"]), 2),
                    "fontname": ch.get("fontname"),
                }
                for ch in page.chars
                if mat_cell.x0 - 5 <= float(ch["x0"]) <= mat_cell.x1 + 5
                and mat_cell.top - 5 <= float(ch["top"]) <= mat_cell.bottom + 5
            ]

            name_raw, name_method = extract_cell_candidates(page, name_cell)
            mat_raw, mat_method = extract_cell_candidates(page, mat_cell)

            diag_data = {
                "filename": doc.filename,
                "parsed_number": doc.number,
                "parsed_name": doc.name,
                "doc_type": doc.doc_type,
                "page_metrics": {
                    "bbox": tuple(float(x) for x in page.bbox),
                    "mediabox": tuple(float(x) for x in getattr(page, "mediabox", ())),
                    "cropbox": tuple(float(x) for x in getattr(page, "cropbox", ())),
                    "rotation": getattr(page, "rotation", 0),
                },
                "located_boxes_pt": {
                    "title_block": [round(v, 2) for v in title_box.as_tuple()],
                    "name_cell": [round(v, 2) for v in name_cell.as_tuple()],
                    "material_cell": [round(v, 2) for v in mat_cell.as_tuple()],
                },
                "extraction_candidates": {
                    "name_cell": {"raw_text": name_raw, "method": name_method},
                    "material_cell": {"raw_text": mat_raw, "method": mat_method},
                },
                "material_result": {
                    "status": doc.material_result.status.value if doc.material_result else None,
                    "normalized_text": doc.material_result.normalized_text if doc.material_result else "",
                    "canonical_material": doc.material_result.canonical_material if doc.material_result else None,
                    "grade": doc.material_result.grade if doc.material_result else None,
                    "standard": doc.material_result.standard if doc.material_result else None,
                    "location_score": doc.material_result.location_score if doc.material_result else 0.0,
                    "warnings": list(doc.material_result.warnings) if doc.material_result else [],
                },
                "material_cell_chars": chars_in_mat,
            }

            json_path = debug_folder / f"{stem}_diag.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(diag_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.warning(f"Ошибка сохранения JSON-диагностики для {doc.filename}: {e}")