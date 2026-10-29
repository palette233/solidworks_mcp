param(
    [Parameter(Mandatory = $true)][string]$AssemblyPath,
    [string]$ProcessReportPath,
    [string]$CadResultPath,
    [Parameter(Mandatory = $true)][string]$ReportPath
)

# Close only unmodified dependency documents left open by a completed read-only
# inspection.  Documents that are not dependencies of the inspected assembly,
# including arbitrary user documents, are never closed by this recovery tool.
$ErrorActionPreference = 'Stop'
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
if (Test-Path -LiteralPath $ReportPath) { throw 'Refusing to overwrite an existing cleanup report.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$interop = Join-Path $repoRoot 'vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorks.Interop.sldworks.dll'
Add-Type -Path $interop
Add-Type -ReferencedAssemblies $interop -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using SolidWorks.Interop.sldworks;
public static class ReadOnlyInspectionResidualCleanup {
    private static string Normalize(string path) {
        return Path.GetFullPath(path).TrimEnd('\\').ToLowerInvariant();
    }
    public static object Run(object application, string assemblyPath) {
        var sw = (ISldWorks)application;
        var rawDependencies = (string[])sw.GetDocumentDependencies2(assemblyPath, true, true, false);
        var dependencies = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (rawDependencies != null) {
            for (var index = 1; index < rawDependencies.Length; index += 2) {
                var path = rawDependencies[index];
                if (!String.IsNullOrWhiteSpace(path)) dependencies.Add(Normalize(path));
            }
        }
        var before = new List<string>();
        var eligible = new List<IModelDoc2>();
        var leftOpen = new List<string>();
        var rawDocuments = sw.GetDocuments();
        if (rawDocuments != null) {
            foreach (object value in (object[])rawDocuments) {
                var document = value as IModelDoc2;
                if (document == null) continue;
                var path = document.GetPathName();
                var identity = String.IsNullOrWhiteSpace(path) ? document.GetTitle() : Path.GetFullPath(path);
                before.Add(identity);
                if (!String.IsNullOrWhiteSpace(path)
                    && !String.Equals(Normalize(path), Normalize(assemblyPath), StringComparison.OrdinalIgnoreCase)
                    && dependencies.Contains(Normalize(path))) {
                    eligible.Add(document);
                } else {
                    leftOpen.Add(identity);
                }
            }
        }
        var closed = new List<string>();
        var modifiedSkipped = new List<string>();
        foreach (var document in eligible) {
            var path = document.GetPathName();
            var identity = String.IsNullOrWhiteSpace(path) ? document.GetTitle() : Path.GetFullPath(path);
            if (document.GetSaveFlag()) {
                modifiedSkipped.Add(identity);
                continue;
            }
            sw.CloseDoc(document.GetTitle());
            closed.Add(identity);
        }
        var after = new List<string>();
        rawDocuments = sw.GetDocuments();
        if (rawDocuments != null) {
            foreach (object value in (object[])rawDocuments) {
                var document = value as IModelDoc2;
                if (document == null) continue;
                var path = document.GetPathName();
                after.Add(String.IsNullOrWhiteSpace(path) ? document.GetTitle() : Path.GetFullPath(path));
            }
        }
        return new {
            beforeOpenDocuments = before,
            dependencyDocumentCount = dependencies.Count,
            eligibleDependencyDocuments = eligible.Count,
            closedDocuments = closed,
            modifiedDocumentsSkipped = modifiedSkipped,
            unrelatedDocumentsLeftOpen = leftOpen,
            afterOpenDocuments = after,
            success = modifiedSkipped.Count == 0
        };
    }
}
'@

$assembly = (Resolve-Path -LiteralPath $AssemblyPath).Path
if ([bool]$ProcessReportPath -eq [bool]$CadResultPath) {
    throw 'Specify exactly one of ProcessReportPath or CadResultPath.'
}
$evidenceKind = ''
$evidencePath = ''
if ($ProcessReportPath) {
    $evidenceKind = 'read_only_inspection_process'
    $evidencePath = (Resolve-Path -LiteralPath $ProcessReportPath).Path
    $process = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($process.returnCode -ne 0 -or $process.cadReexecuted -ne $false -or $process.readOnly -ne $true) {
        throw 'The bound process report is not a successful read-only inspection.'
    }
} else {
    $evidenceKind = 'cad_execution_result'
    $evidencePath = (Resolve-Path -LiteralPath $CadResultPath).Path
    $cad = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cad.success -ne $true -or $cad.outputClosedAfterVerification -ne $true -or $cad.documentBaselineCleanup.sessionRestored -ne $true) {
        throw 'The bound CAD result does not prove a successful baseline-restored execution.'
    }
    if ([System.IO.Path]::GetFullPath([string]$cad.outputAssemblyPath) -ne $assembly) {
        throw 'The CAD result output assembly differs from AssemblyPath.'
    }
}
$application = [System.Runtime.InteropServices.Marshal]::GetActiveObject('SldWorks.Application')
$result = [ReadOnlyInspectionResidualCleanup]::Run($application, $assembly)
$payload = [ordered]@{
    schemaVersion = 'readonly-inspection-residual-cleanup/v1'
    generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    assemblyPath = $assembly
    assemblySha256 = (Get-FileHash -LiteralPath $assembly -Algorithm SHA256).Hash.ToLowerInvariant()
    sourceEvidenceKind = $evidenceKind
    sourceEvidencePath = $evidencePath
    sourceEvidenceSha256 = (Get-FileHash -LiteralPath $evidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
    beforeOpenDocuments = $result.beforeOpenDocuments
    dependencyDocumentCount = $result.dependencyDocumentCount
    eligibleDependencyDocuments = $result.eligibleDependencyDocuments
    closedDocuments = $result.closedDocuments
    modifiedDocumentsSkipped = $result.modifiedDocumentsSkipped
    unrelatedDocumentsLeftOpen = $result.unrelatedDocumentsLeftOpen
    afterOpenDocuments = $result.afterOpenDocuments
    success = $result.success
    userDocumentsClosed = $false
}
$json = $payload | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($ReportPath), $json, (New-Object System.Text.UTF8Encoding($false)))
$json
