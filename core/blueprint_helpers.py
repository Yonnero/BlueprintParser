import re
import unicodedata
from dataclasses import dataclass
from statistics import median
from pdfplumber.page import Page

PT_PER_MM: float = 72.0 / 25.4
FORM1_WIDTH_MM: float = 185.0
FORM1_HEIGHT_MM: float = 55.0

FORM1_DESIGNATION_MM = (65.0, 0.0, 185.0, 15.0)
FORM1_NAME_MM = (65.0, 16.0, 134.5, 39.0)
FORM1_MATERIAL_MM = (65.5, 40.5, 134.5, 53.8)


@dataclass(frozen=True, slots=True)
class Box:
    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    def is_within(self, container: "Box", tolerance_pt: float = 5.0) -> bool:
        return (
            self.x0 >= container.x0 - tolerance_pt
            and self.top >= container.top - tolerance_pt
            and self.x1 <= container.x1 + tolerance_pt
            and self.bottom <= container.bottom + tolerance_pt
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.top, self.x1, self.bottom)


def map_form1_cell(
    title_box: Box,
    cell_mm: tuple[float, float, float, float],
    inset_mm: float = 0.2,
) -> Box:
    sx = title_box.width / FORM1_WIDTH_MM
    sy = title_box.height / FORM1_HEIGHT_MM

    c_x0, c_top, c_x1, c_bottom = cell_mm
    return Box(
        x0=title_box.x0 + (c_x0 + inset_mm) * sx,
        top=title_box.top + (c_top + inset_mm) * sy,
        x1=title_box.x0 + (c_x1 - inset_mm) * sx,
        bottom=title_box.top + (c_bottom - inset_mm) * sy,
    )


def fix_cp1251_mojibake(text: str) -> str:
    if not text:
        return ""
    latin1_Read_chars = sum(1 for ch in text if "\u00c0" <= ch <= "\u00ff")
    if latin1_Read_chars >= 2:
        try:
            repaired = text.encode("latin1", errors="ignore").decode("cp1251", errors="ignore")
            if sum(1 for ch in repaired if "А" <= ch <= "я" or ch in "Ёё") >= 2:
                return repaired
        except Exception:
            pass
    return text


def has_corrupted_encoding(text: str) -> bool:
    if not text:
        return False
    if re.search(r"\(cid:\d+\)", text):
        return True
    control_chars = sum(1 for ch in text if unicodedata.category(ch).startswith("C") and ch not in "\r\n\t")
    return control_chars > len(text) * 0.2


def normalize_cell_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = fix_cp1251_mojibake(raw_text)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(?i)\b(копировал|формат\s*[аa]\d?)\b", "", text)
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    return " ".join(lines).strip()


def _extract_chars_by_center(page: Page, cell_box: Box) -> list[dict]:
    selected = []
    for ch in page.chars:
        cx = (float(ch["x0"]) + float(ch["x1"])) / 2.0
        cy = (float(ch["top"]) + float(ch["bottom"])) / 2.0
        if cell_box.x0 <= cx <= cell_box.x1 and cell_box.top <= cy <= cell_box.bottom:
            selected.append(ch)
    return selected


def _reconstruct_text_from_chars(chars: list[dict]) -> str:
    if not chars:
        return ""

    deduped = []
    for ch in sorted(chars, key=lambda c: (round(c["top"], 1), round(c["x0"], 1))):
        if deduped:
            prev = deduped[-1]
            if (
                prev.get("text") == ch.get("text")
                and abs(float(prev["x0"]) - float(ch["x0"])) < 0.8
                and abs(float(prev["top"]) - float(ch["top"])) < 0.8
            ):
                continue
        deduped.append(ch)

    heights = [max(1.0, float(c["bottom"]) - float(c["top"])) for c in deduped]
    med_h = median(heights) if heights else 6.0
    y_tol = med_h * 0.45

    lines: list[list[dict]] = []
    for ch in sorted(deduped, key=lambda c: (float(c["top"]) + float(c["bottom"])) / 2.0):
        cy = (float(ch["top"]) + float(ch["bottom"])) / 2.0  # <--- Исправлено на ch
        if not lines:
            lines.append([ch])
        else:
            prev_cy = median([(float(c["top"]) + float(c["bottom"])) / 2.0 for c in lines[-1]])
            if abs(cy - prev_cy) <= y_tol:
                lines[-1].append(ch)
            else:
                lines.append([ch])

    result_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda c: float(c["x0"]))
        buf = []
        prev_x1 = None
        for ch in line_sorted:
            w = max(1.0, float(ch["x1"]) - float(ch["x0"]))
            if prev_x1 is not None and (float(ch["x0"]) - prev_x1) > w * 0.35:
                if not buf or buf[-1] != " ":
                    buf.append(" ")
            buf.append(ch.get("text", ""))
            prev_x1 = float(ch["x1"])
        result_lines.append("".join(buf).strip())

    return "\n".join(filter(None, result_lines))


def _extract_shx_annotations(page: Page, cell_box: Box) -> str:
    annots = getattr(page, "annots", None) or []
    found_texts = []
    for annot in annots:
        contents = annot.get("contents") or annot.get("data", {}).get("Contents")
        if not contents:
            continue
        if isinstance(contents, bytes):
            contents = contents.decode("utf-8", errors="ignore")

        x0, top, x1, bottom = (
            float(annot.get("x0", 0)),
            float(annot.get("top", 0)),
            float(annot.get("x1", 0)),
            float(annot.get("bottom", 0)),
        )
        cx, cy = (x0 + x1) / 2.0, (top + bottom) / 2.0
        if cell_box.x0 <= cx <= cell_box.x1 and cell_box.top <= cy <= cell_box.bottom:
            found_texts.append(str(contents).strip())

    return " ".join(found_texts)


def extract_cell_candidates(page: Page, cell_box: Box) -> tuple[str, str]:
    try:
        p_w, p_h = float(page.width), float(page.height)
        safe_box = (
            max(0.0, min(p_w, cell_box.x0)),
            max(0.0, min(p_h, cell_box.top)),
            max(0.0, min(p_w, cell_box.x1)),
            max(0.0, min(p_h, cell_box.bottom)),
        )
        if safe_box[2] > safe_box[0] and safe_box[3] > safe_box[1]:
            std_text = page.crop(safe_box).extract_text() or ""
            std_text = std_text.strip()
            if std_text and not has_corrupted_encoding(std_text):
                return std_text, "crop_extract_text"
    except Exception:
        std_text = ""

    chars = _extract_chars_by_center(page, cell_box)
    char_text = _reconstruct_text_from_chars(chars)
    if char_text and not has_corrupted_encoding(char_text):
        return char_text, "char_centers"

    annot_text = _extract_shx_annotations(page, cell_box)
    if annot_text:
        return annot_text, "shx_annotations"

    fallback = std_text or char_text
    method = "corrupted_encoding" if has_corrupted_encoding(fallback) else "empty"
    return fallback, method