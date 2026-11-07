# Fichier de fabrication PyInstaller : dossier portable SceniX16 (mode « dossier »).
# Utilisation : tools\build.ps1

from pathlib import Path

root = Path(SPECPATH).parent
src = root / "src"

a = Analysis(
    [str(src / "scenix16" / "__main__.py")],
    pathex=[str(src)],
    datas=[(str(src / "scenix16" / "resources"), "scenix16/resources")],
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="SceniX16",
)
