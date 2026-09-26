import json
import re
import sys
from pathlib import Path
from typing import Optional
from core.models import MaterialResult, MaterialStatus
from core.blueprint_helpers import normalize_cell_text, has_corrupted_encoding

STANDARD_REGEX = re.compile(
    r"\b((?:ГОСТ|ОСТ|ТУ|DIN|ISO|EN|ASTM)\s*[0-9А-Яа-яA-Za-z.\-]+)",
    flags=re.IGNORECASE,
)


class MaterialLibrary:
    _rules: dict[str, list[str]] = {}
    _loaded: bool = False

    @classmethod
    def _load(cls) -> None:
        if cls._loaded:
            return
        if getattr(sys, "frozen", False):
            base_dir = Path(sys._MEIPASS)
        else:
            base_dir = Path(__file__).parent.parent

        json_path = base_dir / "resources" / "materials.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                cls._rules = json.load(f)
        cls._loaded = True

    @staticmethod
    def _is_bare_standard_trigger(trigger: str) -> bool:
        t = trigger.strip()
        return bool(re.match(r"^(?:ГОСТ|ОСТ|ТУ)\s*[0-9.\-]+$", t, flags=re.IGNORECASE))

    @staticmethod
    def _make_text_variants(text: str) -> list[str]:
        upper = text.upper()
        compact = re.sub(r"\s+", "", upper)
        translit_map = str.maketrans("ABCEHKMOPTX", "АВСЕНКМОРТХ")
        cyr_upper = upper.translate(translit_map)
        cyr_compact = compact.translate(translit_map)
        return list({upper, compact, cyr_upper, cyr_compact})

    @classmethod
    def evaluate(
        cls,
        raw_text: str,
        page_index: int = 0,
        bbox: Optional[tuple[float, float, float, float]] = None,
        extraction_method: str = "unknown",
        location_score: float = 0.0,
    ) -> MaterialResult:
        cls._load()

        if not raw_text or not raw_text.strip():
            return MaterialResult(
                status=MaterialStatus.NO_TEXT_IN_CELL,
                page_index=page_index,
                bbox=bbox,
                extraction_method=extraction_method,
                location_score=location_score,
            )

        if has_corrupted_encoding(raw_text):
            return MaterialResult(
                status=MaterialStatus.ENCODING_ERROR,
                raw_text=raw_text,
                page_index=page_index,
                bbox=bbox,
                extraction_method=extraction_method,
                location_score=location_score,
                warnings=("Повреждена таблица шрифтов (cid)",),
            )

        norm_text = normalize_cell_text(raw_text)
        std_match = STANDARD_REGEX.search(norm_text)
        standard = std_match.group(1).strip() if std_match else None
        grade_part = norm_text.replace(standard, "").strip() if standard else norm_text

        variants = cls._make_text_variants(norm_text) + cls._make_text_variants(grade_part)

        matched_triggers: dict[str, str] = {}

        for canonical_name, triggers in cls._rules.items():
            for trigger in triggers:
                if cls._is_bare_standard_trigger(trigger):
                    continue

                trig_u = trigger.upper().strip()
                trig_c = re.sub(r"\s+", "", trig_u)

                # Защита от вхождения короткого триггера внутрь другой марки (40Х внутри 40Х13, Д16 внутри Д16Т)
                pattern = re.compile(rf"(?<![0-9А-ЯA-Z]){re.escape(trig_u)}(?![0-9А-ЯA-Z])")
                pattern_c = re.compile(rf"(?<![0-9А-ЯA-Z]){re.escape(trig_c)}(?![0-9А-ЯA-Z])")

                if any(pattern.search(v) or pattern_c.search(v) or trig_u in v for v in variants):
                    # Дополнительно проверяем, что если триггер короткий, после него не идет буква/цифра марки
                    if any(pattern.search(v) or pattern_c.search(v) for v in variants):
                        if canonical_name not in matched_triggers or len(trig_c) > len(matched_triggers[canonical_name]):
                            matched_triggers[canonical_name] = trig_c

        final_categories = list(matched_triggers.keys())
        if len(final_categories) > 1:
            filtered = []
            for cat in final_categories:
                t_cat = matched_triggers[cat]
                if any(t_cat != matched_triggers[other] and t_cat in matched_triggers[other] for other in final_categories):
                    continue
                filtered.append(cat)
            final_categories = filtered

        if len(final_categories) == 1:
            return MaterialResult(
                status=MaterialStatus.MATCHED,
                raw_text=raw_text,
                normalized_text=norm_text,
                canonical_material=final_categories[0],
                grade=grade_part or norm_text,
                standard=standard,
                page_index=page_index,
                bbox=bbox,
                extraction_method=extraction_method,
                location_score=location_score,
            )

        if len(final_categories) > 1:
            return MaterialResult(
                status=MaterialStatus.AMBIGUOUS,
                raw_text=raw_text,
                normalized_text=norm_text,
                canonical_material=final_categories[0],
                grade=grade_part,
                standard=standard,
                page_index=page_index,
                bbox=bbox,
                extraction_method=extraction_method,
                location_score=location_score,
                warnings=(f"Конфликт: {', '.join(final_categories)}",),
            )

        return MaterialResult(
            status=MaterialStatus.UNRECOGNIZED,
            raw_text=raw_text,
            normalized_text=norm_text,
            grade=grade_part,
            standard=standard,
            page_index=page_index,
            bbox=bbox,
            extraction_method=extraction_method,
            location_score=location_score,
        )

    @classmethod
    def match(cls, raw_text: str) -> str:
        res = cls.evaluate(raw_text)
        return res.canonical_material if res.canonical_material else (res.normalized_text or "Не удалось прочитать")