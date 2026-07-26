import os
import platform
import shutil
import sys
import PyInstaller.__main__

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 60)
print(f" STARTING BUILD / ЗАПУСК СБОРКИ (OS: {platform.system()}) ...")
print("=" * 60)

is_windows = platform.system() == "Windows"
add_data_sep = ";" if is_windows else ":"

icon_arg = []
if is_windows:
    if os.path.exists("resources/app.ico"):
        icon_arg = ["--icon=resources/app.ico"]
    elif os.path.exists("resources/app_icon.ico"):
        icon_arg = ["--icon=resources/app_icon.ico"]
    elif os.path.exists("app_icon.ico"):
        icon_arg = ["--icon=app_icon.ico"]

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
print(f" SUCCESS! Binary file created: dist/{output_file}")
print("=" * 60)