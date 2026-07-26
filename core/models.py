from pathlib import Path


class Blueprint:
    def __init__(self, pdf_path: Path):
        self.path = pdf_path
        self.filename = pdf_path.name
        self.directory = str(pdf_path.parent.resolve())
        self.folder_name = pdf_path.parent.name
        self.number = ""
        self.name = ""
        self.doc_type = "Деталь"
        self.material = "-"

    def to_dict(self) -> dict:
        return {
            "Номер": self.number,
            "Наименование": self.name,
            "Тип": self.doc_type,
            "Материал": self.material,
            "Ссылка": str(self.path.resolve()),
            "Директория": self.directory,
            "Папка": self.folder_name
        }