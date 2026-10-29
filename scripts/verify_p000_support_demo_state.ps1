param(
    [Parameter(Mandatory = $true)][string]$AssemblyPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$SourceCheckpoint,
    [string]$BaseToken = 'A600',
    [string]$TargetToken = 'P000',
    [string]$ExpectedMateNamesJson,
    [string]$TargetLeafRelativePath,
    [int]$ExpectedTopLevelComponentCount = 0,
    [int]$ExpectedTopLevelMateCount = 0,
    [string]$ReferenceSearchFoldersJson,
    [switch]$CaptureOnly,
    [switch]$CaptureSingleModule,
    [switch]$AllowMissingReferencesForMeasurement
)
# Bounded state inspection: a two-module demo or a single-target cumulative chain,
# including top-level mates. Never traverse the base's entire leaf tree or save
# a user document; close only documents opened by this inspection.
$ErrorActionPreference = 'Stop'
if ($CaptureSingleModule -and -not $CaptureOnly) {
    throw 'Single-module capture is only available for measurement, never CAD acceptance.'
}
if ($AllowMissingReferencesForMeasurement -and -not $CaptureOnly) {
    throw 'Missing-reference tolerance is only available for measurement, never CAD acceptance.'
}
# Windows PowerShell can auto-load the binary utility cmdlets without loading
# its script functions in an inherited PowerShell 7 environment (Get-FileHash).
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
if (Test-Path -LiteralPath $ReportPath) { throw 'Refusing to overwrite an existing verification report.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$interop = Join-Path $repoRoot 'vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorks.Interop.sldworks.dll'
Add-Type -Path $interop
Add-Type -ReferencedAssemblies $interop -TypeDefinition @'
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
public static class P000SupportDemoReadOnly {
    public sealed class SearchSettingsSnapshot {
        public string PreviousFolders { get; set; }
        public bool PreviousEnabled { get; set; }
        public string AppliedFolders { get; set; }
    }
    public static SearchSettingsSnapshot ApplyReferenceSearchFolders(object application, string[] folders) {
        var sw = (ISldWorks)application;
        var previousFolders = sw.GetSearchFolders(0) ?? "";
        var previousEnabled = sw.GetUserPreferenceToggle(0);
        var ordered = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var folder in previousFolders.Split(new[] {';'}, StringSplitOptions.RemoveEmptyEntries)) {
            var trimmed = folder.Trim();
            if (trimmed.Length > 0 && seen.Add(trimmed)) ordered.Add(trimmed);
        }
        foreach (var folder in folders ?? new string[0]) {
            var trimmed = (folder ?? "").Trim();
            if (trimmed.Length > 0 && seen.Add(trimmed)) ordered.Add(trimmed);
        }
        var applied = String.Join(";", ordered);
        if (!sw.SetSearchFolders(0, applied)) throw new Exception("Failed to apply transient referenced-document search folders.");
        sw.SetUserPreferenceToggle(0, true);
        return new SearchSettingsSnapshot {
            PreviousFolders = previousFolders,
            PreviousEnabled = previousEnabled,
            AppliedFolders = applied
        };
    }
    public static void RestoreReferenceSearchFolders(object application, SearchSettingsSnapshot snapshot) {
        if (snapshot == null) return;
        var sw = (ISldWorks)application;
        if (!sw.SetSearchFolders(0, snapshot.PreviousFolders ?? "")) throw new Exception("Failed to restore referenced-document search folders.");
        sw.SetUserPreferenceToggle(0, snapshot.PreviousEnabled);
        var restoredFolders = sw.GetSearchFolders(0) ?? "";
        var restoredEnabled = sw.GetUserPreferenceToggle(0);
        if (!String.Equals(restoredFolders, snapshot.PreviousFolders ?? "", StringComparison.Ordinal) || restoredEnabled != snapshot.PreviousEnabled)
            throw new Exception("Referenced-document search settings did not restore exactly.");
    }
    private static object MateState(IFeature feature) {
        bool warning;
        int code = feature.GetErrorCode2(out warning);
        var mate = (IMate2)feature.GetSpecificFeature2();
        double? dimension = null;
        var display = (IDisplayDimension)feature.GetFirstDisplayDimension();
        if (display != null) dimension = ((IDimension)display.GetDimension2(0)).SystemValue;
        return new { name = feature.Name, isSuppressed = feature.IsSuppressed(),
            errorCode = code, isWarning = warning, mateType = mate.Type,
            alignment = mate.Alignment, dimensionSystemValue = dimension };
    }
    private static string DocumentKey(IModelDoc2 document) {
        var path = document.GetPathName();
        if (!String.IsNullOrWhiteSpace(path)) {
            return "path:" + System.IO.Path.GetFullPath(path).TrimEnd('\\').ToLowerInvariant();
        }
        return "title:" + (document.GetTitle() ?? "").ToLowerInvariant();
    }
    private static HashSet<string> SnapshotOpenDocuments(ISldWorks sw) {
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var raw = sw.GetDocuments();
        if (raw == null) return result;
        foreach (object value in (object[])raw) {
            var document = value as IModelDoc2;
            if (document != null) result.Add(DocumentKey(document));
        }
        return result;
    }
    private static string[] CloseDocumentsOpenedSince(ISldWorks sw, HashSet<string> before) {
        var closed = new List<string>();
        var raw = sw.GetDocuments();
        if (raw == null) return closed.ToArray();
        var newlyOpened = new List<IModelDoc2>();
        foreach (object value in (object[])raw) {
            var document = value as IModelDoc2;
            if (document != null && !before.Contains(DocumentKey(document))) {
                newlyOpened.Add(document);
            }
        }
        foreach (var document in newlyOpened) {
            if (document.GetSaveFlag()) {
                throw new Exception(
                    "Read-only inspection unexpectedly modified a document opened by the inspection; " +
                    "leaving it open: " + (document.GetPathName() ?? document.GetTitle()));
            }
            var identity = document.GetPathName();
            if (String.IsNullOrWhiteSpace(identity)) identity = document.GetTitle();
            var title = document.GetTitle();
            sw.CloseDoc(title);
            closed.Add(identity ?? title);
        }
        return closed.ToArray();
    }
    public static object Read(object application, string path, string[] expectedMateNames, string targetToken, string targetLeafPath, bool allowMissingReferences) {
        var sw = (ISldWorks)application;
        var previous = sw.IActiveDoc2;
        string previousTitle = previous == null ? null : previous.GetTitle();
        var openBefore = SnapshotOpenDocuments(sw);
        IModelDoc2 model = (IModelDoc2)sw.GetOpenDocumentByName(path);
        bool openedHere = model == null;
        var result = new Dictionary<string, object>();
        try {
            int errors = 0, warnings = 0;
            // Silent (1) + ReadOnly (2); an already-open user document is only read.
            if (openedHere) model = (IModelDoc2)sw.OpenDoc6(path, 2, 3, "", ref errors, ref warnings);
            if (model == null || (errors != 0 && !(allowMissingReferences && errors == 2))) throw new Exception(
                "Read-only inspection open failed: " + errors +
                "; warnings=" + warnings + "; documentReturned=" + (model != null) +
                "; fileExists=" + System.IO.File.Exists(path) + "; path=" + path);
            result["openWarnings"] = warnings;
            result["openErrors"] = errors;
            result["partialReferenceMeasurement"] = errors == 2 && allowMissingReferences;
            var components = new List<object>();
            foreach (object raw in (object[])((IAssemblyDoc)model).GetComponents(true)) {
                var component = (IComponent2)raw;
                components.Add(new { name = component.Name2, sourcePath = component.GetPathName(),
                    configuration = component.ReferencedConfiguration, solvingState = component.Solving,
                    isFixed = component.IsFixed(), constrainedStatus = component.GetConstrainedStatus(),
                    suppressionState = component.GetSuppression(),
                    transform = component.Transform2 == null ? null : (double[])((IMathTransform)component.Transform2).ArrayData,
                    boundingBoxWorld = (double[])component.GetBox(false, false) });
            }
            result["components"] = components;
            if (!String.IsNullOrEmpty(targetLeafPath)) {
                IComponent2 target = null;
                foreach (object raw in (object[])((IAssemblyDoc)model).GetComponents(true)) {
                    var candidate = (IComponent2)raw;
                    if (candidate.Name2.Contains(targetToken + ".001-")) {
                        if (target != null) throw new Exception("Ambiguous target for leaf witness");
                        target = candidate;
                    }
                }
                if (target == null) throw new Exception("Target missing for leaf witness");
                var leaf = target;
                foreach (string segment in targetLeafPath.Split('/')) {
                    IComponent2 match = null;
                    foreach (object raw in (object[])leaf.GetChildren()) {
                        var candidate = (IComponent2)raw;
                        var name = candidate.Name2;
                        if (name.Substring(name.LastIndexOf('/') + 1) == segment) {
                            if (match != null) throw new Exception("Ambiguous bounded leaf path");
                            match = candidate;
                        }
                    }
                    if (match == null) throw new Exception("Witness leaf missing: " + segment);
                    leaf = match;
                }
                result["targetLeafWitness"] = new { name = leaf.Name2,
                    sourcePath = leaf.GetPathName(),
                    transform = (double[])((IMathTransform)leaf.GetTotalTransform(true)).ArrayData };
            }
            var mates = new List<object>();
            foreach (string name in expectedMateNames) {
                var feature = (IFeature)((IAssemblyDoc)model).FeatureByName(name);
                if (feature == null) throw new Exception("Expected mate not found: " + name);
                mates.Add(MateState(feature));
            }
            result["mates"] = mates;
            var allMates = new List<object>();
            for (var group = model.IFirstFeature(); group != null; group = group.IGetNextFeature()) {
                if (group.GetTypeName2() != "MateGroup") continue;
                for (var feature = group.IGetFirstSubFeature(); feature != null; feature = feature.IGetNextSubFeature()) {
                    if (feature.GetSpecificFeature2() is IMate2) allMates.Add(MateState(feature));
                }
            }
            result["allTopLevelMates"] = allMates;
            result["readOnly"] = true;
            return result;
        } finally {
            if (openedHere && model != null) sw.CloseDoc(model.GetTitle());
            var closed = CloseDocumentsOpenedSince(sw, openBefore);
            result["openDocumentCountBefore"] = openBefore.Count;
            result["documentsOpenedByInspectionClosed"] = closed;
            result["openDocumentCountAfterCleanup"] = sw.GetDocumentCount();
            if (!String.IsNullOrEmpty(previousTitle)) {
                int error = 0;
                sw.ActivateDoc3(previousTitle, false, 0, ref error);
            }
        }
    }
}
'@
$clock = [System.Diagnostics.Stopwatch]::StartNew()
$started = [DateTime]::UtcNow.ToString('o')
$absoluteAssemblyPath = (Resolve-Path -LiteralPath $AssemblyPath).Path
$beforeHash = (Get-FileHash -LiteralPath $absoluteAssemblyPath -Algorithm SHA256).Hash.ToLowerInvariant()
# Windows PowerShell 5.1 provides Marshal.GetActiveObject. Attach only: do not
# create a second SolidWorks process if the existing session is unavailable.
$application = [System.Runtime.InteropServices.Marshal]::GetActiveObject('SldWorks.Application')
$referenceSearchFolders = [string[]]@()
if ($ReferenceSearchFoldersJson) {
    $referenceSearchFolders = [string[]](ConvertFrom-Json -InputObject $ReferenceSearchFoldersJson)
    $referenceSearchFolders = [string[]]@($referenceSearchFolders | ForEach-Object {
        if (-not (Test-Path -LiteralPath $_ -PathType Container)) { throw "Reference search folder does not exist: $_" }
        (Resolve-Path -LiteralPath $_).Path
    } | Select-Object -Unique)
}
$searchSnapshot = $null
$sourceObserved = $null
$sourceBeforeHash = $null
$sourceAfterHash = $null
$expectedNames = [string[]]@("MCP_GRAPH_${TargetToken}_${BaseToken}_DATUM_DISTANCE_1", "MCP_GRAPH_${TargetToken}_${BaseToken}_DATUM_DISTANCE_2", "MCP_GRAPH_${TargetToken}_${BaseToken}_DATUM_SUPPORT")
if ($ExpectedMateNamesJson) { $expectedNames = [string[]](ConvertFrom-Json -InputObject $ExpectedMateNamesJson) }
if ($CaptureOnly) { $expectedNames = [string[]]@() }
try {
    if ($referenceSearchFolders.Count -gt 0) {
        $searchSnapshot = [P000SupportDemoReadOnly]::ApplyReferenceSearchFolders($application, $referenceSearchFolders)
    }
    if ($SourceCheckpoint) {
        $SourceCheckpoint = (Resolve-Path -LiteralPath $SourceCheckpoint).Path
        $sourceBeforeHash = (Get-FileHash -LiteralPath $SourceCheckpoint -Algorithm SHA256).Hash.ToLowerInvariant()
        $sourceObserved = [P000SupportDemoReadOnly]::Read($application, $SourceCheckpoint, [string[]]@(), $TargetToken, $null, $false)
        $sourceAfterHash = (Get-FileHash -LiteralPath $SourceCheckpoint -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $observed = [P000SupportDemoReadOnly]::Read($application, $absoluteAssemblyPath, $expectedNames, $TargetToken, $TargetLeafRelativePath, [bool]$AllowMissingReferencesForMeasurement)
} finally {
    if ($null -ne $searchSnapshot) {
        [P000SupportDemoReadOnly]::RestoreReferenceSearchFolders($application, $searchSnapshot)
    }
}
$afterHash = (Get-FileHash -LiteralPath $absoluteAssemblyPath -Algorithm SHA256).Hash.ToLowerInvariant()
$base = @($observed.components | Where-Object { $_.name -like "*${BaseToken}.001-*" })
$target = @($observed.components | Where-Object { $_.name -like "*${TargetToken}.001-*" })
if ($ExpectedTopLevelComponentCount -eq 0) { $ExpectedTopLevelComponentCount = $(if ($SourceCheckpoint) { $sourceObserved.components.Count + 1 } else { 2 }) }
$checks = [ordered]@{
    expectedTopLevelComponentCount = $observed.components.Count -eq $ExpectedTopLevelComponentCount
    onlyBaseFixed = $base.Count -eq 1 -and $base[0].isFixed -and $target.Count -eq 1 -and -not $target[0].isFixed -and @($observed.components | Where-Object { $_.isFixed }).Count -eq 1
    threeActiveMates = $observed.mates.Count -eq $expectedNames.Count -and @($observed.mates | Where-Object { $_.isSuppressed }).Count -eq 0
    matesHaveNoErrors = @($observed.mates | Where-Object { $_.errorCode -ne 0 }).Count -eq 0
    expectedTopLevelMateCount = $ExpectedTopLevelMateCount -eq 0 -or $observed.allTopLevelMates.Count -eq $ExpectedTopLevelMateCount
    allTopLevelMatesActive = @($observed.allTopLevelMates | Where-Object { $_.isSuppressed }).Count -eq 0
    allTopLevelMatesHaveNoErrors = @($observed.allTopLevelMates | Where-Object { $_.errorCode -ne 0 }).Count -eq 0
    outputFileUnchanged = $beforeHash -eq $afterHash
}
if ($CaptureOnly) {
    # A prototype measurement may have fixed or underconstrained components.
    # Record the observation without claiming that its assembly passed CAD acceptance.
    $checks = [ordered]@{
        outputFileUnchanged = $beforeHash -eq $afterHash
        readOnlyObservation = $observed.readOnly -eq $true
        requestedModuleUnique = $target.Count -eq 1
        requestedBaseUnique = $base.Count -eq 1
    }
    $scopedComponents = @($base) + @($target)
    if ($CaptureSingleModule) {
        # An isolated measurement wrapper has no target installation base.
        # Keep its fixed pose explicitly a capture frame, not installation evidence.
        $checks.Remove('requestedBaseUnique')
        $checks['singleModuleWrapper'] = $observed.components.Count -eq 1
        $scopedComponents = @($target)
    }
    # This snapshot measures component transforms, not bodies. Lightweight
    # components expose saved transforms; require separate face evidence for geometry.
    # Reject suppressed (0) and internal-ID mismatch (5), retaining the exact state.
    $expectedMeasuredCount = $(if ($CaptureSingleModule) { 1 } else { 2 })
    $checks['measuredComponentsAvailable'] = $scopedComponents.Count -eq $expectedMeasuredCount -and @($scopedComponents | Where-Object { $_.suppressionState -notin @(1, 2, 3, 4) }).Count -eq 0
    $checks['measuredSourceFilesPresent'] = @($scopedComponents | Where-Object { -not $_.sourcePath -or -not (Test-Path -LiteralPath $_.sourcePath -PathType Leaf) }).Count -eq 0
    $checks['measuredTransformsValid'] = @($scopedComponents | Where-Object { @($_.transform).Count -ne 16 -or @($_.transform | Where-Object { [double]::IsNaN($_) -or [double]::IsInfinity($_) }).Count -gt 0 }).Count -eq 0
}
$report = [ordered]@{
    schemaVersion = $(if ($CaptureOnly) { 'assembly-measurement-readonly-state/v1' } else { 'p000-support-position-readonly-state/v1' })
    cadAcceptanceEvaluated = -not $CaptureOnly
    captureSingleModule = [bool]$CaptureSingleModule
    startedAtUtc = $started
    finishedAtUtc = [DateTime]::UtcNow.ToString('o')
    durationSeconds = $clock.Elapsed.TotalSeconds
    assemblyPath = $absoluteAssemblyPath
    assemblySha256 = $afterHash
    referenceSearchFolders = $referenceSearchFolders
    referenceSearchSettingsRestored = $true
    checks = $checks
    success = @($checks.Values | Where-Object { $_ -ne $true }).Count -eq 0
    observed = $observed
    sourceCheckpointPath = $SourceCheckpoint
    sourceCheckpointSha256Before = $sourceBeforeHash
    sourceCheckpointSha256After = $sourceAfterHash
    sourceObserved = $sourceObserved
    actualFixationMethod = 'not_verified'
}
$json = $report | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($ReportPath), $json, (New-Object System.Text.UTF8Encoding($false)))
$json
if (-not $report.success) { exit 2 }
