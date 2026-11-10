param(
    [switch]$SkipInstaller,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$pythonPath = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv
    } else {
        & python -m venv .venv
    }
}

& $pythonPath -m pip install -r requirements-build.txt
if (-not $SkipTests) {
    & $pythonPath -m pip install -r requirements-dev.txt
    & $pythonPath -m pytest
    & $pythonPath -m ruff check .
}

& $pythonPath scripts\generate_icon.py
& $pythonPath scripts\generate_version_info.py
& $pythonPath -m PyInstaller --noconfirm --clean ApplicationPhotoAssistant.spec

$portableExe = Join-Path $projectRoot "dist\ApplicationPhotoAssistant.exe"
& $portableExe --self-test
if ($LASTEXITCODE -ne 0) { throw "Packaged self-test failed with exit code $LASTEXITCODE" }
& $portableExe --smoke-test
if ($LASTEXITCODE -ne 0) { throw "Packaged smoke-test failed with exit code $LASTEXITCODE" }

$version = & $pythonPath -c "from photo_assistant.version import __version__; print(__version__)"
if (-not $SkipInstaller) {
    $compilerCandidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "E:\Inno Setup 7\ISCC.exe"
    )
    $registryInstallLocations = Get-ItemProperty `
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^Inno Setup [67]' } |
        ForEach-Object { Join-Path $_.InstallLocation 'ISCC.exe' }
    $compilerCandidates += $registryInstallLocations
    $compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $compiler) {
        throw "Inno Setup 6 or 7 not found. Install it, or use -SkipInstaller for a portable-only build."
    }
    & $compiler "/DMyAppVersion=$version" "installer\ApplicationPhotoAssistant.iss"
}

$releaseFiles = Get-ChildItem -LiteralPath ".\dist" -File -Recurse |
    Where-Object { $_.Extension -in ".exe", ".zip" }
$checksumLines = foreach ($file in $releaseFiles) {
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = [IO.Path]::GetRelativePath((Join-Path $projectRoot "dist"), $file.FullName).Replace("\", "/")
    "$hash  $relative"
}
Set-Content -LiteralPath ".\dist\SHA256SUMS.txt" -Value $checksumLines -Encoding utf8

Write-Host ""
Write-Host "Build complete: dist\ApplicationPhotoAssistant.exe" -ForegroundColor Green
if (-not $SkipInstaller) {
    Write-Host "Installer complete: dist\installer\ApplicationPhotoAssistant-Setup-$version-windows-x64.exe" -ForegroundColor Green
}
Write-Host "Checksums: dist\SHA256SUMS.txt" -ForegroundColor Green
