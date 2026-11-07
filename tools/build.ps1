# Fabrique le dossier portable dist\SceniX16\ (SceniX16.exe + _internal\).
# À lancer depuis la racine du projet : .\tools\build.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "$root\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --log-level WARN `
    --distpath "$root\dist" --workpath "$root\build" "$root\tools\scenix16.spec"
if ($LASTEXITCODE -ne 0) { Write-Host "Echec de la fabrication (code $LASTEXITCODE)"; exit $LASTEXITCODE }
Write-Host "Dossier portable cree : $root\dist\SceniX16"
