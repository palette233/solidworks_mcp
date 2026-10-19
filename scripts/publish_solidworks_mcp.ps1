param(
    [string]$Project = "vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj",
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64",
    [string]$Output = "artifacts\solidworks-mcp"
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

function Test-FileLocked {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $false
    }

    try {
        $stream = [System.IO.File]::Open($Path, 'Open', 'ReadWrite', 'None')
        $stream.Close()
        return $false
    }
    catch {
        return $true
    }
}

$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet) {
    throw "dotnet was not found in PATH. Install .NET 8 SDK first."
}

$projectCandidate = if ([System.IO.Path]::IsPathRooted($Project)) {
    $Project
}
else {
    Join-Path $repoRoot $Project
}

$outputPath = if ([System.IO.Path]::IsPathRooted($Output)) {
    $Output
}
else {
    Join-Path $repoRoot $Output
}

$projectPath = Resolve-Path $projectCandidate
$targetExe = Join-Path $outputPath "SolidWorksMcpApp.exe"

if (Test-FileLocked $targetExe) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $outputPath = Join-Path $repoRoot ("artifacts\solidworks-mcp-" + $stamp)
    Write-Host "Target exe is in use. Publishing to alternate directory: $outputPath"
}

& $dotnet.Source publish $projectPath `
    -c $Configuration `
    -r $Runtime `
    --self-contained true `
    -o $outputPath

if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE"
}

Write-Host "Published to $outputPath"
