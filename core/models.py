from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class MaterialStatus(str, Enum):
    MATCHED = "matched"
    NOT_APPLICABLE = "not_applicable"
    NO_TEXT_IN_CELL = "no_text_in_cell"
    UNRECOGNIZED = "unrecognized"
    AMBIGUOUS = "ambiguous"
    ENCODING_ERROR = "encoding_error"
    READ_ERROR = "read_error"


@dataclass(frozen=True, slots=True)
class MaterialResult:
    status: MaterialStatus
    raw_text: str = ""
    normalized_text: str = ""
    canonical_material: Optional[str] = None
    grade: Optional[str] = None
    standard: Optional[str] = None
    page_index: Optional[int] = None
    bbox: Optional[tuple[float, float, float, float]] = None
    extraction_method: Optional[str] = None
    location_score: Optional[float] = None
    warnings: tuple[str, ...] = ()


@dataclass
class Blueprint:
    path: Path
    number: str = ""
    name: str = ""
    doc_type: str = "Деталь"
    material_result: Optional[MaterialResult] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def directory(self) -> str:
        return str(self.path.parent.resolve())

    @property
    def folder_name(self) -> str:
        return self.path.parent.name

    @property
    def material(self) -> str:
        if not self.material_result:
            return "-"

        status = self.material_result.status
        if status == MaterialStatus.MATCHED and self.material_result.canonical_material:
            return self.material_result.canonical_material
        if status == MaterialStatus.NOT_APPLICABLE:
            return "-"
        if status in (MaterialStatus.UNRECOGNIZED, MaterialStatus.AMBIGUOUS):
            return self.material_result.normalized_text or "Не удалось прочитать"
        return "Не удалось прочитать"

    def to_dict(self) -> dict:
        return {
            "Номер": self.number,
            "Наименование": self.name,
            "Тип": self.doc_type,
            "Материал": self.material,
            "Ссылка": str(self.path.resolve()),
            "Директория": self.directory,
            "Папка": self.folder_name,
        }