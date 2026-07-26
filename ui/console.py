import os
import re
from pathlib import Path
from core.analyzer import PDFAnalyzer
from reports.excel import ExcelReport

__version__ = "0.1.0"


class ConsoleInterface:

    def __init__(self):
        self.analyzer = PDFAnalyzer()

    def run(self):
        print("=" * 60)
        print(f" СПИСОК ДЕТАЛЕЙ ТУ ЭКСЕЛЬ (Версия {__version__})")
        print("=" * 60)
        print(
            "Подсказка: Вы можете просто перетащить нужную папку в это окно мышкой.\n"
        )

        input_dir = input("1. Укажите путь к папке с чертежами: ").strip().strip('"')
        if not os.path.isdir(input_dir):
            print("\nОшибка: Указанная папка не существует.")
            input("Нажмите Enter для выхода...")
            return

        output_dir = (
            input("2. Укажите путь для сохранения отчета (Excel): ")
            .strip()
            .strip('"')
        )
        if not os.path.isdir(output_dir):
            print("\nОшибка: Папка для сохранения не найдена.")
            input("Нажмите Enter для выхода...")
            return

        file_name = input("3. Имя Excel файла: ").strip()
        if not file_name:
            file_name = "Список_деталей"

        output_path = os.path.join(output_dir, f"{file_name}.xlsx")

        blueprints = []

        print(f"\nСканирование директории: {input_dir} ...")
        print("-" * 60)

        for pdf_path in Path(input_dir).rglob("*.pdf"):
            if re.search(r"анн?улировано", str(pdf_path), re.IGNORECASE):
                continue

            doc = self.analyzer.process_file(pdf_path)
            blueprints.append(doc)
            print(f"Обработка ({doc.doc_type}): {doc.filename}")

        print("-" * 60)

        if not blueprints:
            print("\nИтог: Документов не найдено.")
            input("Нажмите Enter для выхода...")
            return

        report = ExcelReport(blueprints, output_path)
        report.create()

        print(f"\nУСПЕХ! Отчет сформирован.")
        print(f"Путь: {output_path}")
        print(f"Найдено документов: {len(blueprints)}")

        input("\nНажмите Enter для закрытия программы...")