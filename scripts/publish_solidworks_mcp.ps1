param(
    [string]$Project = "vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj",
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64",
    [string]$Output = "artifacts\solidworks-mcp"
)

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

$projectPath = Resolve-Path $Project
$outputPath = Join-Path (Get-Location) $Output
$targetExe = Join-Path $outputPath "SolidWorksMcpApp.exe"

if (Test-FileLocked $targetExe) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $outputPath = Join-Path (Get-Location) ("artifacts\solidworks-mcp-" + $stamp)
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
