import os
import platform
import shutil
import PyInstaller.__main__

print("=" * 60)
print(f" ЗАПУСК СБОРКИ ПРОГРАММЫ (ОС: {platform.system()}) ...")
print("=" * 60)

is_windows = platform.system() == "Windows"
add_data_sep = ";" if is_windows else ":"
icon_arg = ["--icon=resources/app_icon.ico"] if is_windows else []

args = [
    "main.py",
    "--onefile",
    f"--add-data=resources{add_data_sep}resources",
    "--name=BlueprintParser",
    "--noconfirm",
    "--clean",
] + icon_arg

PyInstaller.__main__.run(args)

for folder in ["build"]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
if os.path.exists("BlueprintParser.spec"):
    os.remove("BlueprintParser.spec")

output_file = "BlueprintParser.exe" if is_windows else "BlueprintParser"

print("\n" + "=" * 60)
print(f" Файл {output_file} лежит в папке dist/")
print("=" * 60)