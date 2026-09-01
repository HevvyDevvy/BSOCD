<#
.SYNOPSIS
  Builds BasicSOCDrills.exe (PyInstaller) then packages it as .msix, .appx,
  and their bundle equivalents, using the Windows SDK's makeappx/signtool.

.REQUIREMENTS
  - Windows 10/11 with the Windows SDK installed (makeappx.exe, signtool.exe
    on PATH — normally under
    C:\Program Files (x86)\Windows Kits\10\bin\<ver>\x64\)
  - Python 3.9+ and `pip install pyinstaller` already done
  - A code-signing certificate (.pfx) whose Subject matches the
    <Identity Publisher="..."> value in AppxManifest.xml exactly.
    For Store submission this can be a self-signed/test cert for local
    testing, but the Store itself will re-sign with its own certificate
    on publish — you still need *a* valid cert to produce a package
    Partner Center will accept for upload.

.USAGE
  ./packaging/build_msix.ps1 -PfxPath C:\path\new_cert.pfx -PfxPassword "..."
#>

param(
    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [string]$Version = "1.0.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Packaging = Join-Path $Root "packaging"
$Dist = Join-Path $Root "dist"
$StageDir = Join-Path $Packaging "stage"
$OutDir = Join-Path $Root "out"

function Resolve-SdkTool {
    param([Parameter(Mandatory)][string]$ToolName)

    # Already on PATH (covers local dev machines with a configured shell)
    $existing = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($existing) { return $existing.Source }

    # windows-latest GitHub runners have the Windows SDK installed but do
    # NOT put its bin folder on PATH. Search the standard install root for
    # the highest-versioned x64 tools folder that actually contains the
    # tool we need.
    $sdkRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin"
    )
    $candidates = foreach ($root in $sdkRoots) {
        if (Test-Path $root) {
            Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
                Where-Object { Test-Path (Join-Path $_.FullName "x64\$ToolName") } |
                Sort-Object Name -Descending
        }
    }
    $best = $candidates | Select-Object -First 1
    if (-not $best) {
        throw "Could not find $ToolName under any Windows Kits SDK install (searched: $($sdkRoots -join ', ')). Install the Windows SDK, or add its bin\<version>\x64 folder to PATH."
    }
    $toolPath = Join-Path $best.FullName "x64\$ToolName"
    Write-Host "Resolved $ToolName -> $toolPath"
    return $toolPath
}

$MakeAppx = Resolve-SdkTool -ToolName "makeappx.exe"
$SignTool = Resolve-SdkTool -ToolName "signtool.exe"

Write-Host "==> 1. Building Windows executable with PyInstaller"
pyinstaller "$Packaging\BasicSOCDrills.spec" --distpath "$Dist" --workpath "$Root\build" --noconfirm
if (-not (Test-Path "$Dist\BasicSOCDrills.exe")) {
    throw "PyInstaller did not produce dist\BasicSOCDrills.exe"
}

Write-Host "==> 2. Staging MSIX payload"
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $StageDir "Assets") | Out-Null

Copy-Item "$Dist\BasicSOCDrills.exe" $StageDir

$manifestContent = Get-Content "$Packaging\AppxManifest.xml" -Raw
# Scope the replace to only the <Identity ...> element's Version attribute.
# A plain 'Version="..."' pattern is case-INSENSITIVE by default in
# PowerShell, so it would also match the XML declaration's lowercase
# version="1.0" on line 1 and corrupt it (XML requires that to stay
# exactly "1.0" or "1.1") - hence wrapping it in an Identity-scoped
# capture group below.
$manifestContent = $manifestContent -creplace '(<Identity\b[^>]*?)Version="[\d\.]+"', "`$1Version=`"$Version`""
Set-Content -Path (Join-Path $StageDir "AppxManifest.xml") -Value $manifestContent -NoNewline -Encoding utf8

$IconsDir = Join-Path $Packaging "icons"
foreach ($asset in @("StoreLogo.png","Square150x150Logo.png","Square44x44Logo.png","Wide310x150Logo.png")) {
    $src = Join-Path $IconsDir $asset
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $StageDir "Assets\$asset")
    } else {
        Write-Warning "Missing icon asset: $asset — place branded PNGs in packaging\icons\ before Store submission."
    }
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "==> 3. Packaging .msix"
& $MakeAppx pack /d "$StageDir" /p "$OutDir\BasicSOCDrills.msix" /o

Write-Host "==> 4. Packaging .appx (legacy alias of the same payload)"
Copy-Item "$OutDir\BasicSOCDrills.msix" "$OutDir\BasicSOCDrills.appx" -Force

Write-Host "==> 5. Building .msixbundle / .appxbundle (multi-architecture container)"
$BundleStage = Join-Path $Packaging "bundle_stage"
if (Test-Path $BundleStage) { Remove-Item $BundleStage -Recurse -Force }
New-Item -ItemType Directory -Path $BundleStage | Out-Null
Copy-Item "$OutDir\BasicSOCDrills.msix" $BundleStage
& $MakeAppx bundle /d "$BundleStage" /p "$OutDir\BasicSOCDrills.msixbundle" /o
Copy-Item "$OutDir\BasicSOCDrills.msixbundle" "$OutDir\BasicSOCDrills.appxbundle" -Force

if ($PfxPath -and (Test-Path $PfxPath)) {
    Write-Host "==> 6. Signing packages with $PfxPath"
    foreach ($pkg in @("BasicSOCDrills.msix","BasicSOCDrills.appx","BasicSOCDrills.msixbundle","BasicSOCDrills.appxbundle")) {
        $pkgPath = Join-Path $OutDir $pkg
        & $SignTool sign /fd SHA256 /a /f $PfxPath /p $PfxPassword $pkgPath
    }
} else {
    Write-Warning "No -PfxPath given: packages were built UNSIGNED. Store submission via Partner Center handles final signing, but local sideload/testing requires you to sign (or install your test cert into Trusted People) first."
}

Write-Host "`nDone. Packages are in: $OutDir"
Get-ChildItem $OutDir | Format-Table Name, Length
