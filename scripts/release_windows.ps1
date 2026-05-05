param(
    [string]$Version = "",
    [string]$PreviousTag = "",
    [string]$Repo = "flathack/FL-Atlas-Launcher",
    [string[]]$Architectures = @("x64", "arm64"),
    [switch]$SkipBuild,
    [switch]$SkipUpload,
    [switch]$AllowDirty,
    [switch]$Draft,
    [switch]$Prerelease
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Resolve-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Assert-CleanWorktree {
    if ($AllowDirty) {
        Write-Host "Dirty worktree allowed by -AllowDirty." -ForegroundColor Yellow
        return
    }
    $status = git status --short
    if ($status) {
        throw "Worktree is dirty. Commit or stash changes before creating a release:`n$status"
    }
}

function Get-AppVersion {
    $content = Get-Content -LiteralPath "app\main.py" -Raw
    $match = [regex]::Match($content, 'APP_VERSION\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "Could not read APP_VERSION from app\main.py"
    }
    return $match.Groups[1].Value
}

function Normalize-Version {
    param([string]$Value)
    $value = $Value.Trim()
    if (-not $value) {
        throw "Version is empty."
    }
    if ($value.StartsWith("v")) {
        return $value
    }
    return "v$value"
}

function Get-PreviousTag {
    param([string]$Tag)
    if ($PreviousTag.Trim()) {
        return $PreviousTag.Trim()
    }
    $tags = git tag --sort=-creatordate
    foreach ($candidate in $tags) {
        $candidate = "$candidate".Trim()
        if ($candidate -and $candidate -ne $Tag) {
            return $candidate
        }
    }
    return ""
}

function Assert-PathInsideRepo {
    param([string]$Path)
    $repoRoot = (Resolve-Path ".").Path
    $full = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
    if (-not $full.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside repository: $full"
    }
    return $full
}

function Remove-GeneratedPath {
    param([string]$Path)
    $full = Assert-PathInsideRepo $Path
    if (Test-Path -LiteralPath $full) {
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Normalize-Architectures {
    $normalized = New-Object System.Collections.Generic.List[string]
    foreach ($arch in $Architectures) {
        $value = "$arch".Trim().ToLowerInvariant()
        if ($value -notin @("x64", "arm64")) {
            throw "Unsupported architecture: $arch. Use x64 or arm64."
        }
        if (-not $normalized.Contains($value)) {
            $normalized.Add($value)
        }
    }
    if ($normalized.Count -eq 0) {
        throw "No architectures selected."
    }
    return @($normalized)
}

function Resolve-PythonLauncher {
    param([string]$Arch)
    if ($Arch -eq "x64") {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            return @("py", "-3.13")
        }
        if (Test-Path -LiteralPath ".venv-x64\Scripts\python.exe") {
            return @((Resolve-Path ".venv-x64\Scripts\python.exe").Path)
        }
        if (Get-Command python -ErrorAction SilentlyContinue) {
            return @("python")
        }
    }
    if ($Arch -eq "arm64") {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            return @("py", "-3.13-arm64")
        }
    }
    throw "No Python launcher found for $Arch."
}

function Invoke-PythonCommand {
    param(
        [string]$Arch,
        [string[]]$Args
    )
    $launcher = Resolve-PythonLauncher $Arch
    & $launcher[0] @($launcher | Select-Object -Skip 1) @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed for ${Arch}: $($Args -join ' ')"
    }
}

function Resolve-BuildPython {
    param([string]$Arch)
    if ($Arch -eq "x64" -and (Test-Path -LiteralPath ".venv-x64\Scripts\python.exe")) {
        return (Resolve-Path ".venv-x64\Scripts\python.exe").Path
    }
    $launcher = Resolve-PythonLauncher $Arch
    $path = (& $launcher[0] @($launcher | Select-Object -Skip 1) -c "import sys; print(sys.executable)").Trim()
    if (-not $path -or -not (Test-Path -LiteralPath $path)) {
        throw "Could not resolve Python executable for $Arch."
    }
    return (Resolve-Path $path).Path
}

function Ensure-BuildRequirements {
    param(
        [string]$Arch,
        [string]$Python
    )
    Write-Step "Checking Python requirements for $Arch"
    & $Python -c "import PyInstaller, PySide6, pefile"
    if ($LASTEXITCODE -eq 0) {
        return
    }
    Write-Host "Installing missing build requirements for $Arch..." -ForegroundColor Yellow
    & $Python -m pip install --upgrade -r requirements.txt pyinstaller | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "release requirements install failed for $Arch"
    }
}

function Get-PythonPlatform {
    param([string]$Python)
    return (& $Python -c "import sysconfig; print(sysconfig.get_platform())").Trim().ToLowerInvariant()
}

function Assert-PythonArchitecture {
    param(
        [string]$Arch,
        [string]$Python
    )
    $platform = Get-PythonPlatform $Python
    if ($Arch -eq "x64" -and $platform -notlike "*amd64*") {
        throw "Windows x64 release requires win-amd64 Python, got: $platform"
    }
    if ($Arch -eq "arm64" -and $platform -notlike "*arm64*") {
        throw "Windows arm64 release requires win-arm64 Python, got: $platform"
    }
}

function Invoke-ReleaseBuild {
    param(
        [string]$Arch,
        [string]$Python
    )
    Write-Step "Building Windows $Arch"
    Assert-PythonArchitecture $Arch $Python

    Remove-GeneratedPath "dist-$Arch"
    Remove-GeneratedPath "build-$Arch"

    & $Python -m PyInstaller --noconfirm --clean --distpath "dist-$Arch" --workpath "build-$Arch" "FL-Atlas-Launcher.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed for $Arch"
    }
}

function Get-ReleaseExePath {
    param([string]$Arch)
    $candidates = @(
        "dist-$Arch\FL-Atlas-Launcher.exe",
        "dist-$Arch\FL-Atlas-Launcher\FL-Atlas-Launcher.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    throw "Could not find FL-Atlas-Launcher.exe in dist-$Arch."
}

function Get-PeMachine {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Path).Path)
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
        throw "Not a PE file: $Path"
    }
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    if ($peOffset + 6 -gt $bytes.Length) {
        throw "Invalid PE header: $Path"
    }
    $sig = [System.Text.Encoding]::ASCII.GetString($bytes, $peOffset, 4)
    if ($sig -ne "PE$([char]0)$([char]0)") {
        throw "Invalid PE signature: $Path"
    }
    return [BitConverter]::ToUInt16($bytes, $peOffset + 4)
}

function Assert-BuildArchitecture {
    param([string]$Arch)
    $exe = Get-ReleaseExePath $Arch
    $actual = Get-PeMachine $exe
    $expected = if ($Arch -eq "x64") { 0x8664 } else { 0xAA64 }
    if ($actual -ne $expected) {
        throw "$exe has PE machine 0x$($actual.ToString('x')), expected 0x$($expected.ToString('x'))"
    }
}

function New-ReleaseZip {
    param(
        [string]$Arch,
        [string]$Tag
    )
    Write-Step "Creating release ZIP for Windows $Arch"
    $releaseDir = "release\$Tag"
    $stageDir = "release\$Tag\FL-Atlas-Launcher-$Arch"
    Remove-GeneratedPath $stageDir
    if (-not (Test-Path -LiteralPath $releaseDir)) {
        New-Item -ItemType Directory -Path $releaseDir | Out-Null
    }
    New-Item -ItemType Directory -Path $stageDir | Out-Null

    Copy-Item -LiteralPath (Get-ReleaseExePath $Arch) -Destination (Join-Path $stageDir "FL-Atlas-Launcher.exe") -Force
    if (Test-Path -LiteralPath "README.md") {
        Copy-Item -LiteralPath "README.md" -Destination (Join-Path $stageDir "README.md") -Force
    }

    $zipPath = Join-Path $releaseDir "FL-Atlas-Launcher-$Tag-windows-$Arch.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    tar -a -cf $zipPath -C $releaseDir "FL-Atlas-Launcher-$Arch"
    if ($LASTEXITCODE -ne 0) {
        throw "ZIP creation failed: $zipPath"
    }

    $hashPath = "$zipPath.sha256"
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $hashPath -Value "$hash  $(Split-Path -Leaf $zipPath)" -Encoding UTF8
    return @((Resolve-Path $zipPath).Path, (Resolve-Path $hashPath).Path)
}

function Get-CommitLines {
    param([string]$Range)
    if ($Range) {
        return @(git log --reverse --oneline $Range)
    }
    return @(git log --reverse --oneline)
}

function New-ReleaseNotes {
    param(
        [string]$Tag,
        [string]$PrevTag
    )
    Write-Step "Generating release notes"
    $range = if ($PrevTag) { "$PrevTag..HEAD" } else { "" }
    $notesPath = "release\$Tag\release-notes.md"
    $notesDir = Split-Path -Parent $notesPath
    if (-not (Test-Path -LiteralPath $notesDir)) {
        New-Item -ItemType Directory -Path $notesDir | Out-Null
    }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("## FL Atlas Launcher $Tag")
    $lines.Add("")
    $lines.Add("Windows x64 and arm64 Build.")
    $lines.Add("")

    $commitLines = Get-CommitLines $range
    if ($commitLines.Count -gt 0) {
        $lines.Add("### Changes")
        foreach ($line in $commitLines) {
            $lines.Add("- ``$line``")
        }
        $lines.Add("")
    } else {
        $lines.Add("No commit changes were found for this release range.")
        $lines.Add("")
    }

    Set-Content -LiteralPath $notesPath -Value $lines -Encoding UTF8
    return (Resolve-Path $notesPath).Path
}

function Assert-ReleasePrerequisites {
    param([string]$Tag)
    Assert-Command "git"
    Assert-Command "tar"
    if (-not $SkipUpload) {
        Assert-Command "gh"
        gh auth status | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub CLI is not authenticated."
        }
    }

    $existingTag = git tag --list $Tag
    if ($existingTag) {
        throw "Tag already exists locally: $Tag"
    }
    $remoteTag = git ls-remote --tags origin $Tag
    if ($remoteTag) {
        throw "Tag already exists on origin: $Tag"
    }
    if (-not $SkipUpload) {
        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        gh release view $Tag --repo $Repo *> $null
        $releaseViewExitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorActionPreference
        if ($releaseViewExitCode -eq 0) {
            throw "GitHub release already exists: $Tag"
        }
    }
}

function Publish-Release {
    param(
        [string]$Tag,
        [string]$NotesPath,
        [string[]]$Assets
    )
    Write-Step "Publishing GitHub release"
    git tag $Tag
    git push origin $Tag
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push tag $Tag"
    }

    $args = @("release", "create", $Tag) + $Assets + @(
        "--repo", $Repo,
        "--title", "FL Atlas Launcher $Tag",
        "--notes-file", $NotesPath
    )
    if ($Draft) {
        $args += "--draft"
    }
    if ($Prerelease) {
        $args += "--prerelease"
    }
    & gh @args
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create GitHub release $Tag"
    }

    $release = gh release view $Tag --repo $Repo --json url,assets | ConvertFrom-Json
    Write-Host "Release URL: $($release.url)"
    foreach ($asset in $release.assets) {
        Write-Host "Asset uploaded: $($asset.name) ($($asset.size) bytes)"
    }
}

$repoRoot = Resolve-RepoRoot
Set-Location $repoRoot

$appVersion = Get-AppVersion
$releaseVersionInput = if ($Version.Trim()) { $Version } else { $appVersion }
$tag = Normalize-Version $releaseVersionInput
$prevTag = Get-PreviousTag $tag
$rangeLabel = if ($prevTag) { "$prevTag..HEAD" } else { "all commits" }

Write-Step "Preparing FL Atlas Launcher release $tag"
Write-Host "Repository: $repoRoot"
Write-Host "GitHub repo: $Repo"
Write-Host "Changelog range: $rangeLabel"

$architecturesToBuild = Normalize-Architectures
Write-Host "Architectures: $($architecturesToBuild -join ', ')"

Assert-CleanWorktree
Assert-ReleasePrerequisites $tag

if (-not $SkipBuild) {
    foreach ($arch in $architecturesToBuild) {
        $py = Resolve-BuildPython $arch
        Ensure-BuildRequirements $arch $py
        Invoke-ReleaseBuild $arch $py
    }
} else {
    Write-Step "Skipping build by request"
}

$assets = @()
foreach ($arch in $architecturesToBuild) {
    Assert-BuildArchitecture $arch
    $assets += New-ReleaseZip $arch $tag
}
$notes = New-ReleaseNotes $tag $prevTag

if ($SkipUpload) {
    Write-Step "Skipping upload by request"
    Write-Host "Release notes: $notes"
    foreach ($asset in $assets) {
        Write-Host "Asset ready: $asset"
    }
    exit 0
}

Publish-Release $tag $notes $assets
