param(
    [string]$EnvPath = ".env",
    [string]$InstallDir = ".tools/tesseract"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir ".." )).Path
}

function Set-EnvValue {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )

    if (-not (Test-Path $FilePath)) {
        throw "No se encontro el archivo .env en: $FilePath"
    }

    $escapedKey = [regex]::Escape($Key)
    $lines = Get-Content -Path $FilePath
    $updated = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^$escapedKey=") {
            $lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $lines += "$Key=$Value"
    }

    Set-Content -Path $FilePath -Value $lines -Encoding UTF8
}

function Find-TesseractExe {
    param([string]$BaseInstallDir)

    $candidates = @(
        (Join-Path $BaseInstallDir "tesseract.exe"),
        (Join-Path $BaseInstallDir "Tesseract-OCR/tesseract.exe"),
        "$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
        "$env:LocalAppData\Programs\Tesseract-OCR\tesseract.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    $cmd = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    return $null
}

$repoRoot = Resolve-RepoRoot
$resolvedEnvPath = $EnvPath
if (-not [System.IO.Path]::IsPathRooted($resolvedEnvPath)) {
    $resolvedEnvPath = Join-Path $repoRoot $resolvedEnvPath
}

$resolvedInstallDir = $InstallDir
if (-not [System.IO.Path]::IsPathRooted($resolvedInstallDir)) {
    $resolvedInstallDir = Join-Path $repoRoot $resolvedInstallDir
}

New-Item -ItemType Directory -Path $resolvedInstallDir -Force | Out-Null

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget no esta disponible. Instala App Installer de Microsoft Store y vuelve a ejecutar."
}

Write-Host "Instalando Tesseract con winget..."
winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements --silent --location "$resolvedInstallDir"

$exePath = Find-TesseractExe -BaseInstallDir $resolvedInstallDir
if (-not $exePath) {
    throw "Tesseract se instalo pero no fue posible ubicar tesseract.exe"
}

$normalized = $exePath -replace "\\", "/"
Set-EnvValue -FilePath $resolvedEnvPath -Key "OCR_TESSERACT_CMD" -Value $normalized
Set-EnvValue -FilePath $resolvedEnvPath -Key "OCR_ENABLED" -Value "true"

Write-Host "Listo. OCR_TESSERACT_CMD actualizado en $resolvedEnvPath"
Write-Host "Ruta detectada: $normalized"
