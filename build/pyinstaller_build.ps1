# build/pyinstaller_build.ps1
# Build a single-file openia.exe for Windows using PyInstaller.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."

pip install --quiet pyinstaller
pip install --quiet -e "$RepoRoot"

pyinstaller `
    --onefile `
    --console `
    --name openia `
    "$RepoRoot\openia\cli.py"

Write-Host "Build complete: dist\openia.exe"
