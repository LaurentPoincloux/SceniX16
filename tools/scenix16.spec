# Fichier de fabrication PyInstaller : dossier portable SceniX16 (mode « dossier »).
# Utilisation : tools\build.ps1
#
# Depuis 2.6c (Design Book v0.43, Q18, D59) :
# - propriétés Windows de l'exécutable : version 0.1.0.0, version du produit = scenix16.__version__ ;
# - build_info.json (date de fabrication, identifiant court du commit, présence de modifications
#   locales non commitées dans src/ et tools/) écrit dans le dossier de travail de la fabrication,
#   jamais dans les sources, puis joint aux ressources de l'exécutable ;
# - dossier LICENCES (textes officiels complets) copié à côté de SceniX16.exe.
# Seules des commandes Git en lecture sont utilisées (rev-parse, status).

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from PyInstaller import config
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

root = Path(SPECPATH).parent
src = root / "src"
sys.path.insert(0, str(src))
from scenix16 import __version__  # noqa: E402
from scenix16.version import BUILD_INFO_NAME, FILE_VERSION, build_info_payload  # noqa: E402


def git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


commit = git("rev-parse", "--short", "HEAD") or "inconnu"
changes = git("status", "--porcelain", "--untracked-files=all", "--", "src", "tools")
local_changes = changes is None or bool(changes)        # Git absent : prudence, signalé
work = Path(config.CONF["workpath"])
work.mkdir(parents=True, exist_ok=True)
build_info = work / BUILD_INFO_NAME
build_info.write_text(json.dumps(build_info_payload(date.today(), commit, local_changes), indent=1),
                      encoding="utf-8")
print(f"SceniX16 {__version__} · commit {commit}"
      f"{' (modifications locales non commitées)' if local_changes else ''}")

file_version = ".".join(str(n) for n in FILE_VERSION)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=FILE_VERSION, prodvers=FILE_VERSION),
    kids=[
        StringFileInfo([StringTable("040C04B0", [
            StringStruct("FileDescription", "SceniX16"),
            StringStruct("FileVersion", file_version),
            StringStruct("InternalName", "SceniX16"),
            StringStruct("OriginalFilename", "SceniX16.exe"),
            StringStruct("ProductName", "SceniX16"),
            StringStruct("ProductVersion", __version__),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
    ],
)

a = Analysis(
    [str(src / "scenix16" / "__main__.py")],
    pathex=[str(src)],
    datas=[(str(src / "scenix16" / "resources"), "scenix16/resources"),
           (str(build_info), "scenix16/resources")],
    excludes=["tkinter", "pytest", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SceniX16",
    console=False,
    upx=False,
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="SceniX16",
)

# dossier LICENCES à côté de l'exécutable (D59, section 12)
licences_target = Path(DISTPATH) / "SceniX16" / "LICENCES"
if licences_target.exists():
    shutil.rmtree(licences_target)
shutil.copytree(src / "scenix16" / "resources" / "LICENCES", licences_target)
