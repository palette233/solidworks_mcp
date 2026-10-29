param(
    [Parameter(Mandatory = $true)][string]$AssemblyPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$ReferenceSearchFoldersJson
)

# Read the dependency table saved in a SolidWorks document without opening or
# saving that document.  The report is diagnostic evidence only; it never
# changes reference paths or SolidWorks search settings.
$ErrorActionPreference = 'Stop'
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
if (Test-Path -LiteralPath $ReportPath) { throw 'Refusing to overwrite an existing dependency inventory.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$interop = Join-Path $repoRoot 'vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorks.Interop.sldworks.dll'
Add-Type -Path $interop
Add-Type -ReferencedAssemblies $interop -TypeDefinition @'
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
public static class SolidWorksDependencyInventoryReadOnly {
    public sealed class SearchSettingsSnapshot {
        public string PreviousFolders { get; set; }
        public bool PreviousEnabled { get; set; }
        public string AppliedFolders { get; set; }
    }
    public static SearchSettingsSnapshot Apply(object application, string[] folders) {
        var sw = (ISldWorks)application;
        var previousFolders = sw.GetSearchFolders(0) ?? "";
        var previousEnabled = sw.GetUserPreferenceToggle(0);
        var ordered = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var folder in previousFolders.Split(new[] {';'}, StringSplitOptions.RemoveEmptyEntries)) {
            var value = folder.Trim();
            if (value.Length > 0 && seen.Add(value)) ordered.Add(value);
        }
        foreach (var folder in folders ?? new string[0]) {
            var value = (folder ?? "").Trim();
            if (value.Length > 0 && seen.Add(value)) ordered.Add(value);
        }
        var applied = String.Join(";", ordered);
        if (!sw.SetSearchFolders(0, applied)) throw new Exception("Failed to apply transient search folders.");
        sw.SetUserPreferenceToggle(0, true);
        return new SearchSettingsSnapshot { PreviousFolders = previousFolders,
            PreviousEnabled = previousEnabled, AppliedFolders = applied };
    }
    public static void Restore(object application, SearchSettingsSnapshot snapshot) {
        if (snapshot == null) return;
        var sw = (ISldWorks)application;
        if (!sw.SetSearchFolders(0, snapshot.PreviousFolders ?? "")) throw new Exception("Failed to restore search folders.");
        sw.SetUserPreferenceToggle(0, snapshot.PreviousEnabled);
        if (!String.Equals(sw.GetSearchFolders(0) ?? "", snapshot.PreviousFolders ?? "", StringComparison.Ordinal)
            || sw.GetUserPreferenceToggle(0) != snapshot.PreviousEnabled)
            throw new Exception("Search settings did not restore exactly.");
    }
    public static string[] Read(object application, string path) {
        var sw = (ISldWorks)application;
        return (string[])sw.GetDocumentDependencies2(path, true, true, false);
    }
}
'@

$clock = [System.Diagnostics.Stopwatch]::StartNew()
$assembly = (Resolve-Path -LiteralPath $AssemblyPath).Path
$application = [System.Runtime.InteropServices.Marshal]::GetActiveObject('SldWorks.Application')
$referenceSearchFolders = [string[]]@()
if ($ReferenceSearchFoldersJson) {
    $referenceSearchFolders = [string[]](ConvertFrom-Json -InputObject $ReferenceSearchFoldersJson)
    $referenceSearchFolders = [string[]]@($referenceSearchFolders | ForEach-Object {
        if (-not (Test-Path -LiteralPath $_ -PathType Container)) { throw "Reference search folder does not exist: $_" }
        (Resolve-Path -LiteralPath $_).Path
    } | Select-Object -Unique)
}
$snapshot = $null
try {
    if ($referenceSearchFolders.Count -gt 0) {
        $snapshot = [SolidWorksDependencyInventoryReadOnly]::Apply($application, $referenceSearchFolders)
    }
    $raw = [SolidWorksDependencyInventoryReadOnly]::Read($application, $assembly)
} finally {
    if ($null -ne $snapshot) {
        [SolidWorksDependencyInventoryReadOnly]::Restore($application, $snapshot)
    }
}
if (($raw.Count % 2) -ne 0) { throw 'SolidWorks returned an odd dependency array.' }
$dependencies = @()
for ($index = 0; $index -lt $raw.Count; $index += 2) {
    $savedPath = [string]$raw[$index + 1]
    $dependencies += [ordered]@{
        documentName = [string]$raw[$index]
        savedPath = $savedPath
        pathExists = Test-Path -LiteralPath $savedPath -PathType Leaf
    }
}
$report = [ordered]@{
    schemaVersion = 'solidworks-document-dependency-inventory/v1'
    generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    durationSeconds = $clock.Elapsed.TotalSeconds
    assemblyPath = $assembly
    assemblySha256 = (Get-FileHash -LiteralPath $assembly -Algorithm SHA256).Hash.ToLowerInvariant()
    dependencyCount = $dependencies.Count
    missingDependencyCount = @($dependencies | Where-Object { -not $_.pathExists }).Count
    dependencies = $dependencies
    readOnly = $true
    documentOpened = $false
    referenceSearchFolders = $referenceSearchFolders
    searchSettingsChangedTransiently = $referenceSearchFolders.Count -gt 0
    searchSettingsRestored = $true
}
$json = $report | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($ReportPath), $json, (New-Object System.Text.UTF8Encoding($false)))
$json
