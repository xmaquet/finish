# Produit dist\Finish\Finish.exe à partir du dépôt.
# Python et l'environnement virtuel servent uniquement à construire.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Environnement absent. Créer .venv puis installer requirements.txt."
}

& $python -m pip install "pyinstaller>=6,<7"
& $python (Join-Path $root "scripts\make_icon.py")
& $python -m PyInstaller --noconfirm --clean (Join-Path $root "finish.spec")

$exe = Join-Path $root "dist\Finish\Finish.exe"
if (-not (Test-Path $exe)) {
    throw "Finish.exe introuvable."
}
Write-Host "Build terminé : $exe"
