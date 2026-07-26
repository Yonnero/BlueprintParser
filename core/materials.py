import os
import re
import json
import sys


class MaterialLibrary:
    _RULES = None

    @classmethod
    def _get_resource_path(cls, filename: str) -> str:
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(base_dir, "resources", filename)

    @classmethod
    def _load_rules(cls) -> dict:
        if cls._RULES is not None:
            return cls._RULES

        json_path = cls._get_resource_path("materials.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cls._RULES = json.load(f)
        except Exception as e:
            print(f"Предупреждение: Не удалось прочитать {json_path} ({e}). База материалов пуста.")
            cls._RULES = {}

        return cls._RULES

    @classmethod
    def match(cls, raw_text: str) -> str:
        if not raw_text:
            return "-"

        text = raw_text.replace('\n', ' ').strip()
        rules = cls._load_rules()

        for standard_name, signatures in rules.items():
            for sig in signatures:
                if re.search(sig, text, re.IGNORECASE):
                    return standard_name

        return text