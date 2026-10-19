using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Globalization;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Net.Http.Headers;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SolidWorksBridge.SolidWorks;

public sealed record AssemblyEntitySelectionStatus
{
    public bool Attempted { get; init; }
    public bool Selected { get; init; }
    public string? Method { get; init; }
    public string? Message { get; init; }
}

public sealed record AssemblyEntityViewImageInfo
{
    public string ViewName { get; init; } = string.Empty;
    public string OutputPath { get; init; } = string.Empty;
    public int Width { get; init; }
    public int Height { get; init; }
}

public sealed record AssemblyEntityStructuralInfo
{
    public bool IsStructualComponent { get; init; }
    public bool? IsStructuralComponent { get; init; }
    public string? Type { get; init; }
    public string? Description { get; init; }
    public IReadOnlyList<string> Identifiers { get; init; } = Array.Empty<string>();

    [JsonIgnore]
    public bool IsMarkedStructural => IsStructualComponent || IsStructuralComponent == true;
}

public sealed record AssemblyEntityCaptureTargetInfo
{
    public string TargetId { get; init; } = string.Empty;
    public string EntityKind { get; init; } = string.Empty;
    public string DisplayName { get; init; } = string.Empty;
    public string? ComponentName { get; init; }
    public string? ComponentPath { get; init; }
    public string? HierarchyPath { get; init; }
    public int? ComponentDepth { get; init; }
    public string? DocumentTitle { get; init; }
    public string? DocumentPath { get; init; }
    public string? FeatureName { get; init; }
    public string? FeatureTypeName { get; init; }
    public string? FeaturePath { get; init; }
    public bool? HasSubFeatures { get; init; }
    public string? BodyName { get; init; }
    public int? BodyIndex { get; init; }
    public double[]? Box { get; init; }
    public string? GraphPath { get; init; }
    public AssemblyEntityStructuralInfo? StructualInfo { get; init; }
    public AssemblyEntityStructuralInfo? StructuralInfo { get; init; }
    public AssemblyEntitySelectionStatus Selection { get; init; } = new();
    public IReadOnlyList<AssemblyEntityViewImageInfo> Images { get; init; } = Array.Empty<AssemblyEntityViewImageInfo>();
}

public sealed record AssemblyEntityAnnotationCaptureResult
{
    public string SchemaVersion { get; init; } = AssemblyEntityAnnotationService.CaptureSchemaVersion;
    public DateTime CreatedUtc { get; init; } = DateTime.UtcNow;
    public string AssemblyTitle { get; init; } = string.Empty;
    public string? AssemblyPath { get; init; }
    public string OutputDirectory { get; init; } = string.Empty;
    public string ManifestPath { get; init; } = string.Empty;
    public int Width { get; init; }
    public int Height { get; init; }
    public int TargetCount { get; init; }
    public int TotalTargetCount { get; init; }
    public int StartIndex { get; init; }
    public int MaxTargets { get; init; }
    public int ProcessedThisRun { get; init; }
    public int SkippedExistingCount { get; init; }
    public int NextStartIndex { get; init; }
    public string? StoppedReason { get; init; }
    public IReadOnlyList<string> CapturedViews { get; init; } = Array.Empty<string>();
    public IReadOnlyList<AssemblyEntityCaptureTargetInfo> Targets { get; init; } = Array.Empty<AssemblyEntityCaptureTargetInfo>();
}

public sealed record AssemblyEntityAnnotationTargetIndexEntry
{
    public int SourceIndex { get; init; }
    public AssemblyEntityCaptureTargetInfo Target { get; init; } = new();
}

public sealed record AssemblyEntityAnnotationTargetIndex
{
    public string SchemaVersion { get; init; } = AssemblyEntityAnnotationService.TargetIndexSchemaVersion;
    public DateTime CreatedUtc { get; init; } = DateTime.UtcNow;
    public string AssemblyTitle { get; init; } = string.Empty;
    public string? AssemblyPath { get; init; }
    public string OutputDirectory { get; init; } = string.Empty;
    public string IndexPath { get; init; } = string.Empty;
    public int TargetCount { get; init; }
    public bool IncludeComponents { get; init; }
    public bool IncludeFeatures { get; init; }
    public bool IncludeBodies { get; init; }
    public bool RequireFeatureTypeName { get; init; }
    public IReadOnlyList<AssemblyEntityAnnotationTargetIndexEntry> Entries { get; init; } = Array.Empty<AssemblyEntityAnnotationTargetIndexEntry>();
}

public sealed record DimensionAxisAnnotationInfo
{
    public bool Related { get; init; }
    public string? Description { get; init; }
    public IReadOnlyList<string> Identifiers { get; init; } = Array.Empty<string>();
}

public sealed record AssemblyEntityDimensionAnnotationEntry
{
    public string TargetId { get; init; } = string.Empty;
    public AssemblyEntityCaptureTargetInfo? Target { get; init; }
    public DimensionAxisAnnotationInfo X { get; init; } = new();
    public DimensionAxisAnnotationInfo Y { get; init; } = new();
    public DimensionAxisAnnotationInfo Z { get; init; } = new();
    public string? OverallReason { get; init; }
    public double? Confidence { get; init; }
    public string AnnotationStatus { get; init; } = "imported";
    public string? Model { get; init; }
    public string? RawModelResponse { get; init; }
    public string? FailureReason { get; init; }
    public DateTime AnnotatedUtc { get; init; } = DateTime.UtcNow;
}

public sealed record AssemblyEntityDimensionAnnotationSet
{
    public string SchemaVersion { get; init; } = AssemblyEntityAnnotationService.AnnotationSchemaVersion;
    public DateTime CreatedUtc { get; init; } = DateTime.UtcNow;
    public string ManifestPath { get; init; } = string.Empty;
    public string? AssemblyPath { get; init; }
    public string? AssemblyTitle { get; init; }
    public string AnnotationPath { get; init; } = string.Empty;
    public int EntryCount { get; init; }
    public IReadOnlyList<AssemblyEntityDimensionAnnotationEntry> Entries { get; init; } = Array.Empty<AssemblyEntityDimensionAnnotationEntry>();
}

public sealed record AssemblyEntityVisionAnnotationResult
{
    public string ManifestPath { get; init; } = string.Empty;
    public string AnnotationPath { get; init; } = string.Empty;
    public string Model { get; init; } = string.Empty;
    public string Endpoint { get; init; } = string.Empty;
    public int RequestedTargetCount { get; init; }
    public int AnnotatedCount { get; init; }
    public int FailedCount { get; init; }
    public AssemblyEntityDimensionAnnotationSet AnnotationSet { get; init; } = new();
}

public sealed record AssemblyDimensionAnnotationMatchInfo
{
    public int Rank { get; init; }
    public int Score { get; init; }
    public IReadOnlyList<string> RelatedAxes { get; init; } = Array.Empty<string>();
    public AssemblyEntityDimensionAnnotationEntry Annotation { get; init; } = new();
}

public sealed record AssemblyDimensionAnnotationQueryResult
{
    public string AnnotationPath { get; init; } = string.Empty;
    public string? Axis { get; init; }
    public string? Query { get; init; }
    public bool OnlyRelated { get; init; }
    public int MatchCount { get; init; }
    public IReadOnlyList<AssemblyDimensionAnnotationMatchInfo> Matches { get; init; } = Array.Empty<AssemblyDimensionAnnotationMatchInfo>();
}

public sealed record AssemblyStructuralComponentMatchInfo
{
    public int Rank { get; init; }
    public int ManifestIndex { get; init; }
    public int Score { get; init; }
    public string StructuralType { get; init; } = string.Empty;
    public AssemblyEntityStructuralInfo StructualInfo { get; init; } = new();
    public AssemblyEntityCaptureTargetInfo Target { get; init; } = new();
}

public sealed record AssemblyStructuralComponentQueryResult
{
    public string ManifestPath { get; init; } = string.Empty;
    public string? RequestedType { get; init; }
    public string? Query { get; init; }
    public int MatchCount { get; init; }
    public IReadOnlyList<AssemblyStructuralComponentMatchInfo> Matches { get; init; } = Array.Empty<AssemblyStructuralComponentMatchInfo>();
}

public sealed record AssemblyEntityHighlightResult
{
    public string SourcePath { get; init; } = string.Empty;
    public string TargetId { get; init; } = string.Empty;
    public bool Found { get; init; }
    public AssemblyEntityCaptureTargetInfo? Target { get; init; }
    public AssemblyEntitySelectionStatus Selection { get; init; } = new();
}

public interface IAssemblyEntityAnnotationService
{
    AssemblyEntityAnnotationTargetIndex BuildActiveAssemblyEntityAnnotationTargetIndex(
        string outputDirectory,
        bool includeComponents = true,
        bool includeFeatures = true,
        bool includeBodies = true,
        bool requireFeatureTypeName = true,
        bool overwrite = false);

    AssemblyEntityAnnotationCaptureResult CaptureActiveAssemblyEntityAnnotationTargetsFromIndex(
        string outputDirectory,
        int width = 1280,
        int height = 720,
        int startIndex = 0,
        int maxTargets = 1,
        string? targetId = null,
        int? sourceIndex = null,
        bool skipExistingTargets = true,
        bool writeManifestAfterEachTarget = true,
        int maxDurationSeconds = 45,
        bool useCleanDisplayMode = false,
        double capturePaddingFactor = 1.35);

    AssemblyEntityAnnotationCaptureResult CaptureActiveAssemblyEntityAnnotationSet(
        string outputDirectory,
        int width = 1280,
        int height = 720,
        bool includeComponents = true,
        bool includeFeatures = true,
        bool includeBodies = true,
        bool requireFeatureTypeName = true,
        int maxTargets = 0,
        int startIndex = 0,
        bool skipExistingTargets = true,
        bool writeManifestAfterEachTarget = true,
        int maxDurationSeconds = 45,
        bool useCleanDisplayMode = false,
        double capturePaddingFactor = 1.35);

    Task<AssemblyEntityVisionAnnotationResult> AnnotateCaptureSetWithQwenAsync(
        string manifestPath,
        string? outputPath = null,
        string? model = null,
        string? baseUrl = null,
        int maxTargets = 0,
        bool overwrite = false,
        int timeoutSeconds = 90,
        CancellationToken cancellationToken = default);

    AssemblyEntityDimensionAnnotationSet ImportAssemblyDimensionAnnotations(
        string manifestPath,
        string annotationJsonOrFilePath,
        string? outputPath = null);

    AssemblyDimensionAnnotationQueryResult QueryAssemblyDimensionAnnotations(
        string annotationPath,
        string? axis = null,
        string? query = null,
        bool onlyRelated = true,
        int maxResults = 50);

    AssemblyStructuralComponentQueryResult QueryAssemblyStructuralComponentTargets(
        string manifestPath,
        string? type = null,
        string? query = null,
        int maxResults = 20);

    AssemblyEntityHighlightResult HighlightAssemblyEntityAnnotationTarget(
        string manifestOrAnnotationPath,
        string targetId);
}

public sealed class AssemblyEntityAnnotationService : IAssemblyEntityAnnotationService
{
    public const string CaptureSchemaVersion = "solidworks-mcp.assembly-entity-capture.v1";
    public const string TargetIndexSchemaVersion = "solidworks-mcp.assembly-entity-target-index.v1";
    public const string AnnotationSchemaVersion = "solidworks-mcp.assembly-dimension-annotations.v1";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private static readonly (SwStandardView View, string Name)[] ThreeViews =
    [
        (SwStandardView.Front, "front"),
        (SwStandardView.Top, "top"),
        (SwStandardView.Right, "right"),
    ];

    private static readonly string[] ManagementFeatureNameMarkers =
    [
        "Favorites",
        "Sensors",
        "DocsFolder",
        "History",
        "Annotations",
        "DesignBinder",
        "SolidBodies",
        "SurfaceBodies",
        "CutList",
        "LightsCamerasAndScene",
        "Mates",
        "Comments",
    ];

    private static readonly string[] ManagementFeatureTypeMarkers =
    [
        "DocsFolder",
        "Favorite",
        "Sensor",
        "History",
        "Annotation",
        "Material",
        "Mate",
        "RefPlane",
        "Reference",
        "CoordSys",
        "Origin",
        "Camera",
        "Light",
        "Comment",
        "Scene",
    ];

    private static readonly string[] PhysicalOrEditableFeatureTypeMarkers =
    [
        "ProfileFeature",
        "3DProfileFeature",
        "Sketch",
        "Boss",
        "Extrude",
        "Cut",
        "Revolve",
        "Sweep",
        "Loft",
        "Boundary",
        "Fillet",
        "Chamfer",
        "Shell",
        "Draft",
        "Rib",
        "Hole",
        "Pattern",
        "Mirror",
        "Linear",
        "Circular",
        "CurvePattern",
        "StructuralMember",
        "Weldment",
        "SheetMetal",
        "BaseFlange",
        "EdgeFlange",
        "MiterFlange",
        "Hem",
        "Jog",
        "Bend",
        "FormTool",
        "Tab",
        "MoveFace",
        "DeleteFace",
        "ReplaceFace",
        "Thicken",
        "Knit",
        "Surface",
        "Split",
        "Combine",
        "Scale",
    ];

    private static readonly string[] ExcludedFeatureTypeNames =
    [
        "ProfileFeature",
        "OneBend",
    ];

    private static readonly double[] CaptureHighlightMaterial =
    [
        1.0, 0.06, 0.0,
        0.9, 0.85, 0.25,
        0.35, 0.0, 0.0,
    ];

    private static readonly int MaterialConfigurationOption = (int)swInConfigurationOpts_e.swThisConfiguration;

    private readonly ISwConnectionManager _cm;

    private sealed record ComponentInstance(IComponent2 Component, ComponentInstanceInfo Info);

    private sealed record RuntimeTarget(
        AssemblyEntityCaptureTargetInfo Info,
        object? SelectionObject,
        string SelectionKind,
        object? FallbackSelectionObject = null,
        string? FallbackSelectionKind = null);

    private sealed record RuntimeTargetBatchItem(RuntimeTarget Target, int SourceIndex);

    private sealed record MaterialSnapshot(object Target, string Kind, bool HadMaterial, object? OriginalValues);

    private sealed class TemporaryAppearanceOverride : IDisposable
    {
        private readonly IModelDoc2 _modelDoc;
        private readonly List<MaterialSnapshot> _snapshots;
        private bool _disposed;

        public TemporaryAppearanceOverride(IModelDoc2 modelDoc, List<MaterialSnapshot> snapshots)
        {
            _modelDoc = modelDoc;
            _snapshots = snapshots;
        }

        public int AppliedCount => _snapshots.Count;

        public string KindSummary => string.Join(
            ",",
            _snapshots
                .GroupBy(snapshot => snapshot.Kind)
                .Select(group => $"{group.Key}:{group.Count()}"));

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            foreach (var snapshot in _snapshots.AsEnumerable().Reverse())
            {
                RestoreMaterialSnapshot(snapshot);
            }

            SafeGraphicsRedraw(_modelDoc);
        }
    }

    public AssemblyEntityAnnotationService(ISwConnectionManager cm)
    {
        _cm = cm ?? throw new ArgumentNullException(nameof(cm));
    }

    public AssemblyEntityAnnotationTargetIndex BuildActiveAssemblyEntityAnnotationTargetIndex(
        string outputDirectory,
        bool includeComponents = true,
        bool includeFeatures = true,
        bool includeBodies = true,
        bool requireFeatureTypeName = true,
        bool overwrite = false)
    {
        if (string.IsNullOrWhiteSpace(outputDirectory))
        {
            throw new ArgumentException("outputDirectory must not be empty.", nameof(outputDirectory));
        }

        string normalizedDirectory = Path.GetFullPath(outputDirectory);
        Directory.CreateDirectory(normalizedDirectory);
        string indexPath = Path.Combine(normalizedDirectory, "target-index.json");
        if (!overwrite && File.Exists(indexPath))
        {
            return LoadTargetIndex(indexPath);
        }

        _cm.EnsureConnected();
        var assembly = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assembly;
        var runtimeTargets = BuildRuntimeTargetList(
            modelDoc,
            assembly,
            includeComponents,
            includeFeatures,
            includeBodies,
            requireFeatureTypeName);

        var index = CreateTargetIndex(
            indexPath,
            modelDoc,
            normalizedDirectory,
            includeComponents,
            includeFeatures,
            includeBodies,
            requireFeatureTypeName,
            runtimeTargets);
        WriteJson(indexPath, index);
        return index;
    }

    public AssemblyEntityAnnotationCaptureResult CaptureActiveAssemblyEntityAnnotationTargetsFromIndex(
        string outputDirectory,
        int width = 1280,
        int height = 720,
        int startIndex = 0,
        int maxTargets = 1,
        string? targetId = null,
        int? sourceIndex = null,
        bool skipExistingTargets = true,
        bool writeManifestAfterEachTarget = true,
        int maxDurationSeconds = 45,
        bool useCleanDisplayMode = false,
        double capturePaddingFactor = 1.35)
    {
        if (sourceIndex is < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(sourceIndex), sourceIndex, "sourceIndex must be 0 or greater when provided.");
        }

        ValidateCaptureArguments(outputDirectory, width, height, maxTargets, startIndex, maxDurationSeconds, capturePaddingFactor);
        string normalizedDirectory = Path.GetFullPath(outputDirectory);
        string indexPath = Path.Combine(normalizedDirectory, "target-index.json");
        var index = LoadTargetIndex(indexPath);

        _cm.EnsureConnected();
        var assembly = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assembly;

        AssemblyEntityAnnotationTargetIndexEntry? requestedTargetIdEntry = null;
        if (!string.IsNullOrWhiteSpace(targetId))
        {
            string normalizedTargetId = targetId.Trim();
            requestedTargetIdEntry = index.Entries.FirstOrDefault(entry =>
                string.Equals(entry.Target.TargetId, normalizedTargetId, StringComparison.OrdinalIgnoreCase));
            if (requestedTargetIdEntry == null)
            {
                throw new InvalidOperationException($"targetId was not found in target-index.json: {normalizedTargetId}");
            }
        }

        int effectiveStartIndex = sourceIndex ?? requestedTargetIdEntry?.SourceIndex ?? startIndex;
        var entries = SelectIndexEntriesForCapture(index, normalizedDirectory, effectiveStartIndex, maxTargets, targetId, sourceIndex, skipExistingTargets);
        int? advanceToSourceIndexWhenComplete = entries.Count > 0
            ? entries.Max(entry => entry.SourceIndex)
            : ResolveEmptyIndexedCaptureAdvanceSourceIndex(index, requestedTargetIdEntry, sourceIndex, effectiveStartIndex);
        var runtimeTargets = RehydrateRuntimeTargetsFromIndexEntries(entries).ToList();
        return CaptureRuntimeTargetBatch(
            modelDoc,
            normalizedDirectory,
            width,
            height,
            runtimeTargets,
            totalTargetCount: index.TargetCount,
            effectiveStartIndex,
            maxTargets,
            skipExistingTargets,
            writeManifestAfterEachTarget,
            maxDurationSeconds,
            useCleanDisplayMode,
            capturePaddingFactor,
            advanceToSourceIndexWhenComplete,
            unresolvedTargetCount: entries.Count - runtimeTargets.Count);
    }

    public AssemblyEntityAnnotationCaptureResult CaptureActiveAssemblyEntityAnnotationSet(
        string outputDirectory,
        int width = 1280,
        int height = 720,
        bool includeComponents = true,
        bool includeFeatures = true,
        bool includeBodies = true,
        bool requireFeatureTypeName = true,
        int maxTargets = 0,
        int startIndex = 0,
        bool skipExistingTargets = true,
        bool writeManifestAfterEachTarget = true,
        int maxDurationSeconds = 45,
        bool useCleanDisplayMode = false,
        double capturePaddingFactor = 1.35)
    {
        ValidateCaptureArguments(outputDirectory, width, height, maxTargets, startIndex, maxDurationSeconds, capturePaddingFactor);

        _cm.EnsureConnected();
        var assembly = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assembly;
        string normalizedDirectory = Path.GetFullPath(outputDirectory);
        var runtimeTargets = BuildRuntimeTargetList(
                modelDoc,
                assembly,
                includeComponents,
                includeFeatures,
                includeBodies,
                requireFeatureTypeName)
            .Select((target, index) => new RuntimeTargetBatchItem(target, index))
            .ToList();
        return CaptureRuntimeTargetBatch(
            modelDoc,
            normalizedDirectory,
            width,
            height,
            runtimeTargets,
            totalTargetCount: runtimeTargets.Count,
            startIndex,
            maxTargets,
            skipExistingTargets,
            writeManifestAfterEachTarget,
            maxDurationSeconds,
            useCleanDisplayMode,
            capturePaddingFactor);
    }

    private AssemblyEntityAnnotationCaptureResult CaptureRuntimeTargetBatch(
        IModelDoc2 modelDoc,
        string outputDirectory,
        int width,
        int height,
        IReadOnlyList<RuntimeTargetBatchItem> runtimeTargets,
        int totalTargetCount,
        int startIndex,
        int maxTargets,
        bool skipExistingTargets,
        bool writeManifestAfterEachTarget,
        int maxDurationSeconds,
        bool useCleanDisplayMode,
        double capturePaddingFactor,
        int? advanceToSourceIndexWhenComplete = null,
        int unresolvedTargetCount = 0)
    {
        outputDirectory = Path.GetFullPath(outputDirectory);
        Directory.CreateDirectory(outputDirectory);
        Directory.CreateDirectory(Path.Combine(outputDirectory, "entities"));
        string manifestPath = Path.Combine(outputDirectory, "manifest.json");
        var existingManifest = File.Exists(manifestPath) ? LoadCaptureManifest(manifestPath) : null;
        var capturedTargets = existingManifest?.Targets
            .Where(target => !string.IsNullOrWhiteSpace(target.TargetId))
            .DistinctBy(target => target.TargetId, StringComparer.OrdinalIgnoreCase)
            .ToList()
            ?? [];
        var capturedTargetIds = new HashSet<string>(capturedTargets.Select(target => target.TargetId), StringComparer.OrdinalIgnoreCase);

        var candidateTargets = runtimeTargets
            .Where(item => item.SourceIndex >= startIndex)
            .ToList();
        var batchTargets = candidateTargets;

        int skippedExistingCount = 0;
        if (skipExistingTargets)
        {
            int countBeforeSkip = batchTargets.Count;
            batchTargets = batchTargets
                .Where(item => !capturedTargetIds.Contains(item.Target.Info.TargetId))
                .ToList();
            skippedExistingCount = countBeforeSkip - batchTargets.Count;
        }

        if (candidateTargets.Count > 0 && batchTargets.Count == 0 && advanceToSourceIndexWhenComplete == null)
        {
            advanceToSourceIndexWhenComplete = candidateTargets.Max(item => item.SourceIndex);
        }

        if (maxTargets > 0)
        {
            batchTargets = batchTargets.Take(maxTargets).ToList();
        }

        WriteCaptureManifest(
            manifestPath,
            modelDoc,
            outputDirectory,
            width,
            height,
            capturedTargets,
            totalTargetCount,
            startIndex,
            maxTargets,
            processedThisRun: 0,
            skippedExistingCount,
            nextStartIndex: startIndex,
            stoppedReason: "started");

        int processedThisRun = 0;
        int lastProcessedSourceIndex = startIndex - 1;
        string? stoppedReason = null;
        var stopwatch = Stopwatch.StartNew();
        try
        {
            foreach (var batchTarget in batchTargets)
            {
                if (HasExceededTimeBudget(stopwatch, maxDurationSeconds))
                {
                    stoppedReason = "time-budget";
                    break;
                }

                var target = batchTarget.Target;
                var capturedTarget = CaptureTargetViews(
                        modelDoc,
                        target,
                        outputDirectory,
                        width,
                        height,
                        useCleanDisplayMode,
                        capturePaddingFactor);
                if (capturedTargetIds.Add(capturedTarget.TargetId))
                {
                    capturedTargets.Add(capturedTarget);
                }
                else
                {
                    int existingIndex = capturedTargets.FindIndex(item => string.Equals(item.TargetId, capturedTarget.TargetId, StringComparison.OrdinalIgnoreCase));
                    if (existingIndex >= 0)
                    {
                        capturedTargets[existingIndex] = capturedTarget;
                    }
                }

                processedThisRun++;
                lastProcessedSourceIndex = batchTarget.SourceIndex;
                if (writeManifestAfterEachTarget)
                {
                    WriteCaptureManifest(
                        manifestPath,
                        modelDoc,
                        outputDirectory,
                        width,
                        height,
                        capturedTargets,
                        totalTargetCount,
                        startIndex,
                        maxTargets,
                        processedThisRun,
                        skippedExistingCount,
                        CalculateNextStartIndex(startIndex, lastProcessedSourceIndex, processedThisRun, batchTargets.Count, totalTargetCount, advanceToSourceIndexWhenComplete),
                        stoppedReason);
                }
            }
        }
        finally
        {
            modelDoc.ClearSelection2(true);
            SafeGraphicsRedraw(modelDoc);
        }

        int nextStartIndex = CalculateNextStartIndex(startIndex, lastProcessedSourceIndex, processedThisRun, batchTargets.Count, totalTargetCount, advanceToSourceIndexWhenComplete);
        string resolvedStoppedReason = stoppedReason ?? ResolveCaptureStopReason(processedThisRun, batchTargets.Count, nextStartIndex, totalTargetCount);
        if (unresolvedTargetCount > 0 && !string.Equals(resolvedStoppedReason, "completed", StringComparison.OrdinalIgnoreCase))
        {
            resolvedStoppedReason = "unresolved-targets-skipped";
        }

        return WriteCaptureManifest(
            manifestPath,
            modelDoc,
            outputDirectory,
            width,
            height,
            capturedTargets,
            totalTargetCount,
            startIndex,
            maxTargets,
            processedThisRun,
            skippedExistingCount,
            nextStartIndex,
            resolvedStoppedReason);
    }

    public async Task<AssemblyEntityVisionAnnotationResult> AnnotateCaptureSetWithQwenAsync(
        string manifestPath,
        string? outputPath = null,
        string? model = null,
        string? baseUrl = null,
        int maxTargets = 0,
        bool overwrite = false,
        int timeoutSeconds = 90,
        CancellationToken cancellationToken = default)
    {
        if (maxTargets < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxTargets), maxTargets, "maxTargets must be 0 or greater.");
        }

        if (timeoutSeconds < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(timeoutSeconds), timeoutSeconds, "timeoutSeconds must be at least 1.");
        }

        var manifest = LoadCaptureManifest(manifestPath);
        string annotationPath = NormalizeOutputAnnotationPath(manifest, outputPath);
        string resolvedModel = ResolveConfiguredValue(model, "SOLIDWORKS_ENTITY_ANNOTATION_QWEN_MODEL", "QWEN_VISION_MODEL", "qwen3.6-flash");
        string resolvedBaseUrl = ResolveConfiguredValue(baseUrl, "DASHSCOPE_BASE_URL", "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1");
        string endpoint = ResolveChatCompletionsEndpoint(resolvedBaseUrl);
        string apiKey = System.Environment.GetEnvironmentVariable("DASHSCOPE_API_KEY")
            ?? System.Environment.GetEnvironmentVariable("QWEN_API_KEY")
            ?? throw new InvalidOperationException("Set DASHSCOPE_API_KEY or QWEN_API_KEY before calling Qwen annotation.");

        var existingEntries = File.Exists(annotationPath) && !overwrite
            ? LoadAnnotationSet(annotationPath).Entries
                .ToDictionary(entry => entry.TargetId, StringComparer.OrdinalIgnoreCase)
            : new Dictionary<string, AssemblyEntityDimensionAnnotationEntry>(StringComparer.OrdinalIgnoreCase);

        var targets = manifest.Targets
            .Where(target => overwrite || !existingEntries.ContainsKey(target.TargetId))
            .ToList();
        if (maxTargets > 0)
        {
            targets = targets.Take(maxTargets).ToList();
        }

        using var httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(timeoutSeconds),
        };
        httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);

        var newEntries = new List<AssemblyEntityDimensionAnnotationEntry>();
        foreach (var target in targets)
        {
            cancellationToken.ThrowIfCancellationRequested();
            newEntries.Add(await AnnotateTargetWithQwenAsync(
                httpClient,
                endpoint,
                resolvedModel,
                manifest,
                target,
                cancellationToken).ConfigureAwait(false));
        }

        var mergedEntries = overwrite
            ? newEntries
            : existingEntries.Values
                .Concat(newEntries)
                .OrderBy(entry => FindTargetOrder(manifest, entry.TargetId))
                .ThenBy(entry => entry.TargetId, StringComparer.OrdinalIgnoreCase)
                .ToList();

        var annotationSet = CreateAnnotationSet(manifest, annotationPath, mergedEntries);
        WriteJson(annotationPath, annotationSet);

        return new AssemblyEntityVisionAnnotationResult
        {
            ManifestPath = manifest.ManifestPath,
            AnnotationPath = annotationPath,
            Model = resolvedModel,
            Endpoint = endpoint,
            RequestedTargetCount = targets.Count,
            AnnotatedCount = newEntries.Count(entry => string.Equals(entry.AnnotationStatus, "completed", StringComparison.OrdinalIgnoreCase)),
            FailedCount = newEntries.Count(entry => !string.Equals(entry.AnnotationStatus, "completed", StringComparison.OrdinalIgnoreCase)),
            AnnotationSet = annotationSet,
        };
    }

    public AssemblyEntityDimensionAnnotationSet ImportAssemblyDimensionAnnotations(
        string manifestPath,
        string annotationJsonOrFilePath,
        string? outputPath = null)
    {
        if (string.IsNullOrWhiteSpace(annotationJsonOrFilePath))
        {
            throw new ArgumentException("annotationJsonOrFilePath must not be empty.", nameof(annotationJsonOrFilePath));
        }

        var manifest = LoadCaptureManifest(manifestPath);
        string annotationPath = NormalizeOutputAnnotationPath(manifest, outputPath);
        string json = File.Exists(annotationJsonOrFilePath)
            ? File.ReadAllText(Path.GetFullPath(annotationJsonOrFilePath), Encoding.UTF8)
            : annotationJsonOrFilePath;

        var entries = ParseImportedAnnotationEntries(json, manifest);
        var annotationSet = CreateAnnotationSet(manifest, annotationPath, entries);
        WriteJson(annotationPath, annotationSet);
        return annotationSet;
    }

    public AssemblyDimensionAnnotationQueryResult QueryAssemblyDimensionAnnotations(
        string annotationPath,
        string? axis = null,
        string? query = null,
        bool onlyRelated = true,
        int maxResults = 50)
    {
        if (maxResults < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maxResults), maxResults, "maxResults must be at least 1.");
        }

        string? normalizedAxis = NormalizeAxis(axis);
        string? normalizedQuery = NormalizeQuery(query);
        var annotationSet = LoadAnnotationSet(annotationPath);

        var matches = annotationSet.Entries
            .Select(entry => new
            {
                Entry = entry,
                RelatedAxes = GetRelatedAxes(entry, normalizedAxis),
                Score = ScoreAnnotation(entry, normalizedAxis, normalizedQuery),
            })
            .Where(item => !onlyRelated || item.RelatedAxes.Count > 0)
            .Where(item => normalizedQuery == null || item.Score > 0 || item.RelatedAxes.Count > 0)
            .OrderByDescending(item => item.RelatedAxes.Count)
            .ThenByDescending(item => item.Score)
            .ThenByDescending(item => item.Entry.Confidence ?? 0)
            .ThenBy(item => item.Entry.Target?.DisplayName ?? item.Entry.TargetId, StringComparer.OrdinalIgnoreCase)
            .Take(maxResults)
            .Select((item, index) => new AssemblyDimensionAnnotationMatchInfo
            {
                Rank = index,
                Score = item.Score,
                RelatedAxes = item.RelatedAxes,
                Annotation = item.Entry,
            })
            .ToList()
            .AsReadOnly();

        return new AssemblyDimensionAnnotationQueryResult
        {
            AnnotationPath = Path.GetFullPath(annotationPath),
            Axis = normalizedAxis,
            Query = normalizedQuery,
            OnlyRelated = onlyRelated,
            MatchCount = matches.Count,
            Matches = matches,
        };
    }

    public AssemblyStructuralComponentQueryResult QueryAssemblyStructuralComponentTargets(
        string manifestPath,
        string? type = null,
        string? query = null,
        int maxResults = 20)
    {
        if (maxResults < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maxResults), maxResults, "maxResults must be at least 1.");
        }

        var manifest = LoadCaptureManifest(manifestPath);
        string? requestedType = NormalizeStructuralType(type) ?? InferStructuralTypeFromQuery(query);
        string? normalizedQuery = NormalizeQuery(query);

        var matches = manifest.Targets
            .Select((target, index) => new
            {
                Target = target,
                ManifestIndex = index,
                StructualInfo = GetStructuralInfo(target),
            })
            .Where(item => item.StructualInfo?.IsMarkedStructural == true)
            .Select(item => new
            {
                item.Target,
                item.ManifestIndex,
                StructualInfo = item.StructualInfo!,
                StructuralType = NormalizeStructuralType(item.StructualInfo!.Type) ?? item.StructualInfo!.Type?.Trim() ?? string.Empty,
            })
            .Where(item => requestedType == null || string.Equals(item.StructuralType, requestedType, StringComparison.OrdinalIgnoreCase))
            .Select(item => new
            {
                item.Target,
                item.ManifestIndex,
                item.StructualInfo,
                item.StructuralType,
                Score = ScoreStructuralTarget(item.Target, item.StructualInfo, item.StructuralType, requestedType, normalizedQuery),
            })
            .Where(item => normalizedQuery == null || item.Score > 0 || requestedType != null)
            .OrderByDescending(item => string.Equals(item.StructuralType, requestedType, StringComparison.OrdinalIgnoreCase))
            .ThenByDescending(item => item.Score)
            .ThenBy(item => item.Target.DisplayName, StringComparer.OrdinalIgnoreCase)
            .Take(maxResults)
            .Select((item, rank) => new AssemblyStructuralComponentMatchInfo
            {
                Rank = rank,
                ManifestIndex = item.ManifestIndex,
                Score = item.Score,
                StructuralType = item.StructuralType,
                StructualInfo = item.StructualInfo,
                Target = item.Target,
            })
            .ToList()
            .AsReadOnly();

        return new AssemblyStructuralComponentQueryResult
        {
            ManifestPath = manifest.ManifestPath,
            RequestedType = requestedType,
            Query = normalizedQuery,
            MatchCount = matches.Count,
            Matches = matches,
        };
    }

    public AssemblyEntityHighlightResult HighlightAssemblyEntityAnnotationTarget(
        string manifestOrAnnotationPath,
        string targetId)
    {
        if (string.IsNullOrWhiteSpace(targetId))
        {
            throw new ArgumentException("targetId must not be empty.", nameof(targetId));
        }

        string sourcePath = Path.GetFullPath(manifestOrAnnotationPath);
        var requestedTarget = LoadTargetFromManifestOrAnnotation(sourcePath, targetId.Trim());
        if (requestedTarget == null)
        {
            return new AssemblyEntityHighlightResult
            {
                SourcePath = sourcePath,
                TargetId = targetId.Trim(),
                Found = false,
                Selection = new AssemblyEntitySelectionStatus
                {
                    Attempted = false,
                    Selected = false,
                    Message = "The targetId was not present in the manifest or annotation file.",
                },
            };
        }

        _cm.EnsureConnected();
        var assembly = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assembly;
        var runtimeTarget = EnumerateRuntimeTargets(
                modelDoc,
                assembly,
                includeComponents: true,
                includeFeatures: true,
                includeBodies: true)
            .FirstOrDefault(target => string.Equals(target.Info.TargetId, requestedTarget.TargetId, StringComparison.OrdinalIgnoreCase));

        if (runtimeTarget == null)
        {
            return new AssemblyEntityHighlightResult
            {
                SourcePath = sourcePath,
                TargetId = requestedTarget.TargetId,
                Found = false,
                Target = requestedTarget,
                Selection = new AssemblyEntitySelectionStatus
                {
                    Attempted = false,
                    Selected = false,
                    Message = "The target was in the file but could not be resolved in the active assembly.",
                },
            };
        }

        var selection = TrySelectRuntimeTarget(modelDoc, runtimeTarget);
        SafeGraphicsRedraw(modelDoc);

        return new AssemblyEntityHighlightResult
        {
            SourcePath = sourcePath,
            TargetId = requestedTarget.TargetId,
            Found = true,
            Target = runtimeTarget.Info,
            Selection = selection,
        };
    }

    private AssemblyEntityCaptureTargetInfo CaptureTargetViews(
        IModelDoc2 modelDoc,
        RuntimeTarget target,
        string outputDirectory,
        int width,
        int height,
        bool useCleanDisplayMode,
        double capturePaddingFactor)
    {
        var targetDirectory = Path.Combine(outputDirectory, "entities", ToSafePathSegment(target.Info.TargetId));
        Directory.CreateDirectory(targetDirectory);

        var images = new List<AssemblyEntityViewImageInfo>();
        var selection = TrySelectRuntimeTarget(modelDoc, target);
        using var appearance = ApplyTemporaryCaptureAppearance(modelDoc, target);
        selection = selection with
        {
            Message = $"{selection.Message} Temporary capture appearance applied to {appearance.AppliedCount} object(s): {appearance.KindSummary}.",
        };

        try
        {
            foreach (var (view, viewName) in ThreeViews)
            {
                PrepareViewForEntityCapture(modelDoc, view, useCleanDisplayMode);
                StabilizeCaptureView(modelDoc, capturePaddingFactor);
                PrepareTemporaryAppearanceForBitmapExport(modelDoc);
                string outputPath = Path.Combine(targetDirectory, $"{viewName}.png");
                var image = ExportPreparedViewPng(modelDoc, outputPath, width, height);
                images.Add(new AssemblyEntityViewImageInfo
                {
                    ViewName = viewName,
                    OutputPath = image.OutputPath,
                    Width = image.Width,
                    Height = image.Height,
                });
            }
        }
        finally
        {
            modelDoc.ClearSelection2(true);
        }

        return target.Info with
        {
            Selection = selection,
            Images = images.AsReadOnly(),
        };
    }

    private static void ValidateCaptureArguments(
        string outputDirectory,
        int width,
        int height,
        int maxTargets,
        int startIndex,
        int maxDurationSeconds,
        double capturePaddingFactor)
    {
        if (string.IsNullOrWhiteSpace(outputDirectory))
        {
            throw new ArgumentException("outputDirectory must not be empty.", nameof(outputDirectory));
        }

        if (width < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(width), width, "width must be at least 1.");
        }

        if (height < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(height), height, "height must be at least 1.");
        }

        if (maxTargets < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxTargets), maxTargets, "maxTargets must be 0 or greater.");
        }

        if (startIndex < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(startIndex), startIndex, "startIndex must be 0 or greater.");
        }

        if (maxDurationSeconds < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxDurationSeconds), maxDurationSeconds, "maxDurationSeconds must be 0 or greater.");
        }

        if (capturePaddingFactor < 1 || capturePaddingFactor > 3)
        {
            throw new ArgumentOutOfRangeException(nameof(capturePaddingFactor), capturePaddingFactor, "capturePaddingFactor must be between 1 and 3.");
        }
    }

    private IReadOnlyList<RuntimeTarget> BuildRuntimeTargetList(
        IModelDoc2 modelDoc,
        IAssemblyDoc assembly,
        bool includeComponents,
        bool includeFeatures,
        bool includeBodies,
        bool requireFeatureTypeName)
        => EnumerateRuntimeTargets(
                modelDoc,
                assembly,
                includeComponents,
                includeFeatures,
                includeBodies)
            .Where(target => ShouldKeepCaptureTarget(target.Info, requireFeatureTypeName))
            .ToList()
            .AsReadOnly();

    private static AssemblyEntityAnnotationTargetIndex CreateTargetIndex(
        string indexPath,
        IModelDoc2 modelDoc,
        string outputDirectory,
        bool includeComponents,
        bool includeFeatures,
        bool includeBodies,
        bool requireFeatureTypeName,
        IReadOnlyList<RuntimeTarget> targets)
    {
        var entries = targets
            .Select((target, index) => new AssemblyEntityAnnotationTargetIndexEntry
            {
                SourceIndex = index,
                Target = target.Info,
            })
            .ToList()
            .AsReadOnly();

        return new AssemblyEntityAnnotationTargetIndex
        {
            SchemaVersion = TargetIndexSchemaVersion,
            CreatedUtc = DateTime.UtcNow,
            AssemblyTitle = SafeGetDocumentTitle(modelDoc) ?? "<untitled>",
            AssemblyPath = NormalizePathOrNull(SafeGetDocumentPath(modelDoc)),
            OutputDirectory = outputDirectory,
            IndexPath = indexPath,
            TargetCount = entries.Count,
            IncludeComponents = includeComponents,
            IncludeFeatures = includeFeatures,
            IncludeBodies = includeBodies,
            RequireFeatureTypeName = requireFeatureTypeName,
            Entries = entries,
        };
    }

    private static IReadOnlyList<AssemblyEntityAnnotationTargetIndexEntry> SelectIndexEntriesForCapture(
        AssemblyEntityAnnotationTargetIndex index,
        string outputDirectory,
        int startIndex,
        int maxTargets,
        string? targetId,
        int? sourceIndex,
        bool skipExistingTargets)
    {
        IEnumerable<AssemblyEntityAnnotationTargetIndexEntry> entries = index.Entries;
        if (!string.IsNullOrWhiteSpace(targetId))
        {
            string normalizedTargetId = targetId.Trim();
            entries = entries.Where(entry => string.Equals(entry.Target.TargetId, normalizedTargetId, StringComparison.OrdinalIgnoreCase));
        }
        else if (sourceIndex.HasValue)
        {
            entries = entries.Where(entry => entry.SourceIndex == sourceIndex.Value);
        }
        else
        {
            entries = entries.Where(entry => entry.SourceIndex >= startIndex);
        }

        if (skipExistingTargets)
        {
            string manifestPath = Path.Combine(outputDirectory, "manifest.json");
            var capturedTargetIds = File.Exists(manifestPath)
                ? LoadCaptureManifest(manifestPath).Targets
                    .Select(target => target.TargetId)
                    .Where(id => !string.IsNullOrWhiteSpace(id))
                    .ToHashSet(StringComparer.OrdinalIgnoreCase)
                : new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            entries = entries.Where(entry => !capturedTargetIds.Contains(entry.Target.TargetId));
        }

        if (maxTargets > 0)
        {
            entries = entries.Take(maxTargets);
        }

        return entries.ToList().AsReadOnly();
    }

    private static int? ResolveEmptyIndexedCaptureAdvanceSourceIndex(
        AssemblyEntityAnnotationTargetIndex index,
        AssemblyEntityAnnotationTargetIndexEntry? requestedTargetIdEntry,
        int? sourceIndex,
        int startIndex)
    {
        if (requestedTargetIdEntry != null)
        {
            return requestedTargetIdEntry.SourceIndex;
        }

        if (!sourceIndex.HasValue)
        {
            return index.TargetCount > startIndex
                ? index.TargetCount - 1
                : null;
        }

        int value = sourceIndex.Value;
        if (index.Entries.Any(entry => entry.SourceIndex == value))
        {
            return value;
        }

        throw new InvalidOperationException($"sourceIndex was not found in target-index.json: {value}");
    }

    private IEnumerable<RuntimeTargetBatchItem> RehydrateRuntimeTargetsFromIndexEntries(
        IReadOnlyList<AssemblyEntityAnnotationTargetIndexEntry> entries)
    {
        foreach (var entry in entries)
        {
            var runtimeTarget = TryResolveRuntimeTargetFromIndexEntry(entry.Target);
            if (runtimeTarget != null)
            {
                yield return new RuntimeTargetBatchItem(runtimeTarget, entry.SourceIndex);
            }
        }
    }

    private RuntimeTarget? TryResolveRuntimeTargetFromIndexEntry(AssemblyEntityCaptureTargetInfo target)
    {
        if (string.Equals(target.EntityKind, "feature", StringComparison.OrdinalIgnoreCase))
        {
            return TryResolveFeatureRuntimeTargetFromIndexEntry(target);
        }

        // Component and body index capture can still use the legacy full resolver path.
        var assembly = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assembly;
        return EnumerateRuntimeTargets(
                modelDoc,
                assembly,
                includeComponents: true,
                includeFeatures: true,
                includeBodies: true)
            .FirstOrDefault(candidate => string.Equals(candidate.Info.TargetId, target.TargetId, StringComparison.OrdinalIgnoreCase));
    }

    private RuntimeTarget? TryResolveFeatureRuntimeTargetFromIndexEntry(AssemblyEntityCaptureTargetInfo target)
    {
        var assembly = GetAssemblyDoc();
        var assemblyModelDoc = (IModelDoc2)assembly;
        IComponent2? component = null;
        ComponentInstanceInfo? componentInfo = null;
        IModelDoc2 document = assemblyModelDoc;

        if (!string.IsNullOrWhiteSpace(target.HierarchyPath))
        {
            var instance = EnumerateComponentInstances(assembly)
                .FirstOrDefault(item => string.Equals(item.Info.HierarchyPath, target.HierarchyPath, StringComparison.OrdinalIgnoreCase));
            if (instance == null)
            {
                return null;
            }

            component = instance.Component;
            componentInfo = instance.Info;
            document = SafeGetComponentModelDoc(component) ?? document;
        }

        var feature = FindFeatureByPath(document, target.FeaturePath);
        if (feature == null)
        {
            return null;
        }

        return new RuntimeTarget(
            target,
            feature,
            "feature",
            FallbackSelectionObject: null,
            FallbackSelectionKind: null);
    }

    private static Feature? FindFeatureByPath(IModelDoc2 document, string? featurePath)
    {
        if (string.IsNullOrWhiteSpace(featurePath))
        {
            return null;
        }

        Feature? current = null;
        foreach (var segment in featurePath.Split('/', StringSplitOptions.RemoveEmptyEntries))
        {
            int colonIndex = segment.IndexOf(':');
            if (colonIndex <= 0 || !int.TryParse(segment[..colonIndex], NumberStyles.Integer, CultureInfo.InvariantCulture, out int siblingIndex))
            {
                return null;
            }

            current = current == null
                ? GetFeatureBySiblingIndex(SafeGetFirstFeature(document), siblingIndex, useSubFeatureChain: false)
                : GetFeatureBySiblingIndex(SafeGetFirstSubFeature(current), siblingIndex, useSubFeatureChain: true);
            if (current == null)
            {
                return null;
            }
        }

        return current;
    }

    private static Feature? GetFeatureBySiblingIndex(Feature? first, int siblingIndex, bool useSubFeatureChain)
    {
        int index = 0;
        var visited = new HashSet<Feature>();
        for (var current = first; current != null && visited.Add(current); current = useSubFeatureChain ? SafeGetNextSubFeature(current) : SafeGetNextFeature(current))
        {
            if (index == siblingIndex)
            {
                return current;
            }

            index++;
        }

        return null;
    }

    private static AssemblyEntityAnnotationCaptureResult WriteCaptureManifest(
        string manifestPath,
        IModelDoc2 modelDoc,
        string outputDirectory,
        int width,
        int height,
        IReadOnlyList<AssemblyEntityCaptureTargetInfo> capturedTargets,
        int totalTargetCount,
        int startIndex,
        int maxTargets,
        int processedThisRun,
        int skippedExistingCount,
        int nextStartIndex,
        string? stoppedReason)
    {
        var result = new AssemblyEntityAnnotationCaptureResult
        {
            SchemaVersion = CaptureSchemaVersion,
            CreatedUtc = DateTime.UtcNow,
            AssemblyTitle = SafeGetDocumentTitle(modelDoc) ?? "<untitled>",
            AssemblyPath = NormalizePathOrNull(SafeGetDocumentPath(modelDoc)),
            OutputDirectory = outputDirectory,
            ManifestPath = manifestPath,
            Width = width,
            Height = height,
            TargetCount = capturedTargets.Count,
            TotalTargetCount = totalTargetCount,
            StartIndex = startIndex,
            MaxTargets = maxTargets,
            ProcessedThisRun = processedThisRun,
            SkippedExistingCount = skippedExistingCount,
            NextStartIndex = nextStartIndex,
            StoppedReason = stoppedReason,
            CapturedViews = ThreeViews.Select(view => view.Name).ToArray(),
            Targets = capturedTargets.ToList().AsReadOnly(),
        };

        WriteJson(manifestPath, result);
        return result;
    }

    private static bool HasExceededTimeBudget(Stopwatch stopwatch, int maxDurationSeconds)
        => maxDurationSeconds > 0 && stopwatch.Elapsed >= TimeSpan.FromSeconds(maxDurationSeconds);

    private static int CalculateNextStartIndex(
        int startIndex,
        int lastProcessedSourceIndex,
        int processedThisRun,
        int requestedTargetCount,
        int totalTargetCount,
        int? advanceToSourceIndexWhenComplete = null)
    {
        if (processedThisRun > 0)
        {
            return Math.Min(totalTargetCount, lastProcessedSourceIndex + 1);
        }

        if (advanceToSourceIndexWhenComplete.HasValue)
        {
            return Math.Min(totalTargetCount, advanceToSourceIndexWhenComplete.Value + 1);
        }

        return requestedTargetCount == 0
            ? Math.Min(totalTargetCount, startIndex)
            : Math.Min(totalTargetCount, Math.Max(startIndex, lastProcessedSourceIndex + 1));
    }

    private static string ResolveCaptureStopReason(int processedThisRun, int requestedTargetCount, int nextStartIndex, int totalTargetCount)
    {
        if (processedThisRun < requestedTargetCount)
        {
            return "stopped";
        }

        return nextStartIndex >= totalTargetCount ? "completed" : "batch-completed";
    }

    private static void PrepareViewForEntityCapture(
        IModelDoc2 modelDoc,
        SwStandardView view,
        bool useCleanDisplayMode)
    {
        var (viewName, viewId) = GetStandardView(view);
        SafeShowNamedView(modelDoc, viewName, viewId);

        if (useCleanDisplayMode)
        {
            ApplyCleanCaptureDisplay(modelDoc);
        }
        else
        {
            ApplyShadedCaptureDisplay(modelDoc);
        }

        SafeZoomToFit(modelDoc);
        SafeGraphicsRedraw(modelDoc);
    }

    private static void StabilizeCaptureView(IModelDoc2 modelDoc, double capturePaddingFactor)
    {
        SafeZoomByFactor(modelDoc, 1 / Math.Max(capturePaddingFactor, 1));
        SafeGraphicsRedraw(modelDoc);
    }

    private static SwImageExportResult ExportPreparedViewPng(IModelDoc2 modelDoc, string outputPath, int width, int height)
    {
        string normalizedOutputPath = Path.GetFullPath(outputPath);
        var directory = Path.GetDirectoryName(normalizedOutputPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        string tempBmpPath = Path.Combine(Path.GetTempPath(), $"solidworks-mcp-entity-{Guid.NewGuid():N}.bmp");
        try
        {
            if (!modelDoc.SaveBMP(tempBmpPath, width, height) || !File.Exists(tempBmpPath))
            {
                throw new InvalidOperationException($"SolidWorks failed to export the current view to bitmap: {tempBmpPath}");
            }

            using (var bitmap = new Bitmap(tempBmpPath))
            {
                bitmap.Save(normalizedOutputPath, ImageFormat.Png);
            }

            return new SwImageExportResult(normalizedOutputPath, "image/png", width, height, Base64Data: null);
        }
        finally
        {
            try
            {
                if (File.Exists(tempBmpPath))
                {
                    File.Delete(tempBmpPath);
                }
            }
            catch
            {
                // Temporary capture cleanup is best-effort.
            }
        }
    }

    private static void PrepareTemporaryAppearanceForBitmapExport(IModelDoc2 modelDoc)
    {
        SafeGraphicsRedraw(modelDoc);
        SafeActivateAndRepaintView(modelDoc);
        Thread.Sleep(60);
    }

    private static TemporaryAppearanceOverride ApplyTemporaryCaptureAppearance(IModelDoc2 modelDoc, RuntimeTarget target)
    {
        var snapshots = new List<MaterialSnapshot>();
        var candidates = EnumerateCaptureAppearanceTargets(target)
            .DistinctBy(item => RuntimeHelpers.GetHashCode(item.Target))
            .Take(80)
            .ToList();

        foreach (var candidate in candidates)
        {
            if (TryApplyCaptureMaterial(candidate.Target, candidate.Kind, out var snapshot))
            {
                snapshots.Add(snapshot);
            }
        }

        SafeGraphicsRedraw(modelDoc);
        return new TemporaryAppearanceOverride(modelDoc, snapshots);
    }

    private static IEnumerable<(object Target, string Kind)> EnumerateCaptureAppearanceTargets(RuntimeTarget target)
    {
        if (target.SelectionObject is Feature feature)
        {
            foreach (var face in EnumerateFeatureFaces(feature))
            {
                yield return (face, "face");
            }

            if (TryGetFeatureBody(feature) is IBody2 body)
            {
                yield return (body, "feature-body");
            }
        }

        if (target.SelectionObject is IFace2 faceTarget)
        {
            yield return (faceTarget, "face");
        }

        if (target.SelectionObject is IBody2 bodyTarget)
        {
            yield return (bodyTarget, "body");
        }
    }

    private static IEnumerable<IFace2> EnumerateFeatureFaces(Feature feature)
    {
        foreach (var face in ToObjectArray(SafeInvokeCom<object>(feature, "GetAffectedFaces")).OfType<IFace2>())
        {
            yield return face;
        }

        foreach (var face in ToObjectArray(SafeInvokeCom<object>(feature, "GetFaces")).OfType<IFace2>())
        {
            yield return face;
        }
    }

    private static IBody2? TryGetFeatureBody(Feature feature)
        => SafeInvokeCom<object>(feature, "GetBody") as IBody2;

    private static bool TryApplyCaptureMaterial(object target, string kind, out MaterialSnapshot snapshot)
    {
        object? originalValues = TryGetMaterialValues(target, kind);
        bool hadMaterial = HasMaterialValues(target, kind, originalValues);
        snapshot = new MaterialSnapshot(target, kind, hadMaterial, CloneMaterialValues(originalValues));

        try
        {
            switch (target)
            {
                case IFace2 face:
                    face.SetMaterialPropertyValues2(CaptureHighlightMaterial.ToArray(), MaterialConfigurationOption, null);
                    return true;
                case IBody2 body:
                    body.MaterialPropertyValues2 = CaptureHighlightMaterial.ToArray();
                    return true;
                case Feature feature:
                    feature.SetMaterialPropertyValues2(CaptureHighlightMaterial.ToArray(), MaterialConfigurationOption, null);
                    return true;
                default:
                    return TrySetMaterialValuesByReflection(target, CaptureHighlightMaterial.ToArray());
            }
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

    private static object? TryGetMaterialValues(object target, string kind)
    {
        try
        {
            return target switch
            {
                IFace2 face => face.GetMaterialPropertyValues2(MaterialConfigurationOption, null),
                IBody2 body => body.MaterialPropertyValues2,
                Feature feature => feature.GetMaterialPropertyValues2(MaterialConfigurationOption, null),
                _ => TryGetMaterialValuesByReflection(target),
            };
        }
        catch (COMException)
        {
            return null;
        }
        catch (TargetInvocationException)
        {
            return null;
        }
        catch (ArgumentException)
        {
            return null;
        }
    }

    private static bool HasMaterialValues(object target, string kind, object? values)
    {
        try
        {
            return target switch
            {
                IFace2 face => face.HasMaterialPropertyValues(),
                IBody2 body => body.HasMaterialPropertyValues(),
                Feature feature => feature.HasMaterialPropertyValues(),
                _ => values != null,
            };
        }
        catch (COMException)
        {
            return values != null;
        }
        catch (TargetInvocationException)
        {
            return values != null;
        }
    }

    private static void RestoreMaterialSnapshot(MaterialSnapshot snapshot)
    {
        try
        {
            if (snapshot.HadMaterial && snapshot.OriginalValues != null)
            {
                SetMaterialValues(snapshot.Target, snapshot.Kind, snapshot.OriginalValues);
            }
            else
            {
                RemoveMaterialValues(snapshot.Target, snapshot.Kind);
            }
        }
        catch (COMException)
        {
            // Restoration is best-effort; leave SolidWorks responsive even if an object was invalidated.
        }
        catch (TargetInvocationException)
        {
            // Restoration is best-effort; leave SolidWorks responsive even if an object was invalidated.
        }
        catch (ArgumentException)
        {
            // Restoration is best-effort; leave SolidWorks responsive even if an object was invalidated.
        }
    }

    private static void SetMaterialValues(object target, string kind, object values)
    {
        object cloned = CloneMaterialValues(values) ?? values;
        switch (target)
        {
            case IFace2 face:
                face.SetMaterialPropertyValues2(cloned, MaterialConfigurationOption, null);
                break;
            case IBody2 body:
                body.MaterialPropertyValues2 = cloned;
                break;
            case Feature feature:
                feature.SetMaterialPropertyValues2(cloned, MaterialConfigurationOption, null);
                break;
            default:
                TrySetMaterialValuesByReflection(target, cloned);
                break;
        }
    }

    private static void RemoveMaterialValues(object target, string kind)
    {
        switch (target)
        {
            case IFace2 face:
                face.RemoveMaterialProperty2(MaterialConfigurationOption, null);
                break;
            case IBody2 body:
                body.RemoveMaterialProperty(MaterialConfigurationOption, null);
                break;
            case Feature feature:
                feature.RemoveMaterialProperty2(MaterialConfigurationOption, null);
                break;
            default:
                SafeInvokeCom<object>(target, "RemoveMaterialProperty");
                break;
        }
    }

    private static object? TryGetMaterialValuesByReflection(object target)
    {
        var type = target.GetType();
        var property = type.GetProperty("MaterialPropertyValues2")
            ?? type.GetProperty("MaterialPropertyValues");
        return property?.GetValue(target);
    }

    private static bool TrySetMaterialValuesByReflection(object target, object values)
    {
        var type = target.GetType();
        var property = type.GetProperty("MaterialPropertyValues2")
            ?? type.GetProperty("MaterialPropertyValues");
        if (property?.CanWrite == true)
        {
            property.SetValue(target, values);
            return true;
        }

        return false;
    }

    private static object? CloneMaterialValues(object? values)
    {
        if (values is null)
        {
            return null;
        }

        return values switch
        {
            double[] doubles => doubles.ToArray(),
            object[] objects => objects.ToArray(),
            Array array => array.Cast<object?>().ToArray(),
            _ => values,
        };
    }

    private static object[] ToObjectArray(object? value)
        => value switch
        {
            null => Array.Empty<object>(),
            object[] objects => objects,
            Array array => array.Cast<object>().ToArray(),
            _ => [value],
        };

    private static T? SafeInvokeCom<T>(object target, string methodName)
    {
        try
        {
            var value = target.GetType().InvokeMember(
                methodName,
                BindingFlags.InvokeMethod,
                binder: null,
                target,
                args: Array.Empty<object>());
            return value is T typed ? typed : default;
        }
        catch (MissingMethodException)
        {
            return default;
        }
        catch (COMException)
        {
            return default;
        }
        catch (TargetInvocationException)
        {
            return default;
        }
        catch (ArgumentException)
        {
            return default;
        }
    }

    private static void ApplyCleanCaptureDisplay(IModelDoc2 modelDoc)
    {
        try
        {
            modelDoc.Extension.ViewDisplayRealView = false;
        }
        catch (COMException)
        {
            // Best-effort display cleanup only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort display cleanup only.
        }

        try
        {
            modelDoc.IActiveView?.RemovePerspective();
        }
        catch (COMException)
        {
            // Best-effort display cleanup only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort display cleanup only.
        }

        try
        {
            var activeView = modelDoc.IActiveView;
            if (activeView != null)
            {
                activeView.DisplayMode = (int)swViewDisplayMode_e.swViewDisplayMode_HiddenLinesRemoved;
            }
        }
        catch (COMException)
        {
            // Some SolidWorks states reject IModelView.DisplayMode; fall back below.
        }
        catch (TargetInvocationException)
        {
            // Some SolidWorks states reject IModelView.DisplayMode; fall back below.
        }

        try
        {
            modelDoc.ViewDisplayHiddenremoved();
        }
        catch (COMException)
        {
            // Best-effort display cleanup only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort display cleanup only.
        }
    }

    private static void ApplyShadedCaptureDisplay(IModelDoc2 modelDoc)
    {
        try
        {
            var activeView = modelDoc.IActiveView;
            if (activeView != null)
            {
                activeView.DisplayMode = (int)swViewDisplayMode_e.swViewDisplayMode_ShadedWithEdges;
            }
        }
        catch (COMException)
        {
            // Some SolidWorks states reject IModelView.DisplayMode; fall back below.
        }
        catch (TargetInvocationException)
        {
            // Some SolidWorks states reject IModelView.DisplayMode; fall back below.
        }

        try
        {
            modelDoc.ViewDisplayShaded();
        }
        catch (COMException)
        {
            // Best-effort display setup only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort display setup only.
        }
    }

    private static void SafeShowNamedView(IModelDoc2 modelDoc, string viewName, int viewId)
    {
        try
        {
            modelDoc.ShowNamedView2(viewName, viewId);
        }
        catch (COMException)
        {
            // Best-effort view normalization only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort view normalization only.
        }
    }

    private static void SafeZoomToFit(IModelDoc2 modelDoc)
    {
        try
        {
            modelDoc.ViewZoomtofit2();
        }
        catch (COMException)
        {
            // Best-effort view normalization only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort view normalization only.
        }
    }

    private static void SafeZoomToBox(IModelDoc2 modelDoc, double[] box, double paddingFactor)
    {
        if (box.Length < 6)
        {
            return;
        }

        double centerX = (box[0] + box[3]) / 2;
        double centerY = (box[1] + box[4]) / 2;
        double centerZ = (box[2] + box[5]) / 2;
        double halfX = Math.Max((box[3] - box[0]) / 2, 0);
        double halfY = Math.Max((box[4] - box[1]) / 2, 0);
        double halfZ = Math.Max((box[5] - box[2]) / 2, 0);
        double maxHalf = Math.Max(Math.Max(halfX, halfY), halfZ);
        if (maxHalf <= 0)
        {
            return;
        }

        double padding = Math.Clamp(paddingFactor, 1, 3);
        halfX = Math.Max(halfX, maxHalf * 0.02) * padding;
        halfY = Math.Max(halfY, maxHalf * 0.02) * padding;
        halfZ = Math.Max(halfZ, maxHalf * 0.02) * padding;

        try
        {
            modelDoc.ViewZoomTo2(
                centerX - halfX,
                centerY - halfY,
                centerZ - halfZ,
                centerX + halfX,
                centerY + halfY,
                centerZ + halfZ);
        }
        catch (COMException)
        {
            // Best-effort view normalization only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort view normalization only.
        }
    }

    private static void SafeZoomByFactor(IModelDoc2 modelDoc, double factor)
    {
        if (!double.IsFinite(factor) || factor <= 0)
        {
            return;
        }

        try
        {
            modelDoc.IActiveView?.ZoomByFactor(factor);
        }
        catch (COMException)
        {
            // Best-effort view normalization only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort view normalization only.
        }
    }

    private static double CalculateAspectPadding(IModelDoc2 modelDoc, int outputWidth, int outputHeight)
    {
        if (outputWidth < 1 || outputHeight < 1)
        {
            return 1;
        }

        try
        {
            var view = modelDoc.IActiveView;
            if (view == null || view.FrameWidth <= 0 || view.FrameHeight <= 0)
            {
                return 1;
            }

            double viewportAspect = (double)view.FrameWidth / view.FrameHeight;
            double outputAspect = (double)outputWidth / outputHeight;
            if (viewportAspect <= 0 || outputAspect <= 0)
            {
                return 1;
            }

            return Math.Clamp(Math.Max(viewportAspect / outputAspect, outputAspect / viewportAspect), 1, 2);
        }
        catch (COMException)
        {
            return 1;
        }
        catch (TargetInvocationException)
        {
            return 1;
        }
    }

    private static double[]? SafeGetAssemblyBox(IAssemblyDoc assembly)
    {
        try
        {
            assembly.UpdateBox();
        }
        catch (COMException)
        {
            // Box reads can still work even when UpdateBox fails.
        }
        catch (TargetInvocationException)
        {
            // Box reads can still work even when UpdateBox fails.
        }

        try
        {
            return NormalizeBox(ToDoubleArray(assembly.GetBox(0)));
        }
        catch (COMException)
        {
            return null;
        }
        catch (TargetInvocationException)
        {
            return null;
        }
    }

    private static (string ViewName, int ViewId) GetStandardView(SwStandardView view) => view switch
    {
        SwStandardView.Front => ("*Front", (int)swStandardViews_e.swFrontView),
        SwStandardView.Back => ("*Back", (int)swStandardViews_e.swBackView),
        SwStandardView.Left => ("*Left", (int)swStandardViews_e.swLeftView),
        SwStandardView.Right => ("*Right", (int)swStandardViews_e.swRightView),
        SwStandardView.Top => ("*Top", (int)swStandardViews_e.swTopView),
        SwStandardView.Bottom => ("*Bottom", (int)swStandardViews_e.swBottomView),
        SwStandardView.Isometric => ("*Isometric", (int)swStandardViews_e.swIsometricView),
        SwStandardView.Trimetric => ("*Trimetric", (int)swStandardViews_e.swTrimetricView),
        SwStandardView.Dimetric => ("*Dimetric", (int)swStandardViews_e.swDimetricView),
        _ => throw new ArgumentOutOfRangeException(nameof(view)),
    };

    private IEnumerable<RuntimeTarget> EnumerateRuntimeTargets(
        IModelDoc2 assemblyModelDoc,
        IAssemblyDoc assembly,
        bool includeComponents,
        bool includeFeatures,
        bool includeBodies)
    {
        var instances = EnumerateComponentInstances(assembly);
        foreach (var instance in instances)
        {
            if (includeComponents)
            {
                yield return CreateComponentTarget(instance);
            }

            var componentDoc = SafeGetComponentModelDoc(instance.Component);
            if (componentDoc == null)
            {
                continue;
            }

            if (includeFeatures)
            {
                foreach (var target in EnumerateDocumentFeatureTargets(
                             componentDoc,
                             selectionDocument: assemblyModelDoc,
                             instance.Component,
                             instance.Info,
                             rootDisplayName: instance.Info.HierarchyPath))
                {
                    yield return target;
                }
            }

            if (includeBodies)
            {
                foreach (var target in EnumerateComponentBodyTargets(instance))
                {
                    yield return target;
                }
            }
        }

        if (includeFeatures)
        {
            foreach (var target in EnumerateDocumentFeatureTargets(
                         assemblyModelDoc,
                         selectionDocument: assemblyModelDoc,
                         component: null,
                         componentInfo: null,
                         rootDisplayName: "active assembly"))
            {
                yield return target;
            }
        }
    }

    private static RuntimeTarget CreateComponentTarget(ComponentInstance instance)
    {
        var info = new AssemblyEntityCaptureTargetInfo
        {
            TargetId = CreateTargetId(
                "component",
                instance.Info.HierarchyPath,
                instance.Info.Path,
                null,
                null,
                null,
                null),
            EntityKind = "component",
            DisplayName = instance.Info.HierarchyPath,
            ComponentName = instance.Info.Name,
            ComponentPath = NormalizePathOrNull(instance.Info.Path),
            HierarchyPath = instance.Info.HierarchyPath,
            ComponentDepth = instance.Info.Depth,
            DocumentTitle = instance.Info.Name,
            DocumentPath = NormalizePathOrNull(instance.Info.Path),
            GraphPath = instance.Info.HierarchyPath,
        };

        return new RuntimeTarget(info, instance.Component, "component");
    }

    private static IEnumerable<RuntimeTarget> EnumerateDocumentFeatureTargets(
        IModelDoc2 document,
        IModelDoc2 selectionDocument,
        IComponent2? component,
        ComponentInstanceInfo? componentInfo,
        string rootDisplayName)
    {
        int index = 0;
        var visited = new HashSet<Feature>();
        for (var feature = SafeGetFirstFeature(document); feature != null && visited.Add(feature); feature = SafeGetNextFeature(feature))
        {
            foreach (var target in EnumerateFeatureAndSubFeatureTargets(
                         feature,
                         selectionDocument,
                         component,
                         componentInfo,
                         rootDisplayName,
                         parentFeaturePath: null,
                         siblingIndex: index))
            {
                yield return target;
            }

            index++;
        }
    }

    private static IEnumerable<RuntimeTarget> EnumerateFeatureAndSubFeatureTargets(
        Feature feature,
        IModelDoc2 selectionDocument,
        IComponent2? component,
        ComponentInstanceInfo? componentInfo,
        string rootDisplayName,
        string? parentFeaturePath,
        int siblingIndex)
    {
        string featureName = SafeGetFeatureName(feature) ?? $"Feature{siblingIndex + 1}";
        string? featureTypeName = SafeGetFeatureTypeName(feature);
        string featurePath = string.IsNullOrWhiteSpace(parentFeaturePath)
            ? $"{siblingIndex}:{featureName}"
            : $"{parentFeaturePath}/{siblingIndex}:{featureName}";
        string? documentTitle = SafeGetDocumentTitle(selectionDocument);
        string? documentPath = NormalizePathOrNull(SafeGetDocumentPath(selectionDocument));

        if (component != null)
        {
            var componentDoc = SafeGetComponentModelDoc(component);
            documentTitle = componentDoc == null
                ? componentInfo?.Name
                : SafeGetDocumentTitle(componentDoc);
            documentPath = componentDoc == null
                ? NormalizePathOrNull(componentInfo?.Path)
                : NormalizePathOrNull(SafeGetDocumentPath(componentDoc));
        }

        var child = SafeGetFirstSubFeature(feature);
        if (ShouldCaptureFeatureTarget(featureName, featureTypeName) && child != null)
        {
            var info = new AssemblyEntityCaptureTargetInfo
            {
                TargetId = CreateTargetId(
                    "feature",
                    componentInfo?.HierarchyPath,
                    componentInfo?.Path,
                    documentPath,
                    featurePath,
                    null,
                    featureName),
                EntityKind = "feature",
                DisplayName = $"{rootDisplayName}/{featurePath}",
                ComponentName = componentInfo?.Name,
                ComponentPath = NormalizePathOrNull(componentInfo?.Path),
                HierarchyPath = componentInfo?.HierarchyPath,
                ComponentDepth = componentInfo?.Depth,
                DocumentTitle = documentTitle,
                DocumentPath = documentPath,
                FeatureName = featureName,
                FeatureTypeName = featureTypeName,
                FeaturePath = featurePath,
                HasSubFeatures = child != null,
                GraphPath = $"{rootDisplayName}/{featurePath}",
            };

            yield return new RuntimeTarget(
                info,
                feature,
                "feature",
                FallbackSelectionObject: null,
                FallbackSelectionKind: null);
        }

        int childIndex = 0;
        var visited = new HashSet<Feature>();
        for (var current = child; current != null && visited.Add(current); current = SafeGetNextSubFeature(current))
        {
            foreach (var target in EnumerateFeatureAndSubFeatureTargets(
                         current,
                         selectionDocument,
                         component,
                         componentInfo,
                         rootDisplayName,
                         featurePath,
                         childIndex))
            {
                yield return target;
            }

            childIndex++;
        }
    }

    internal static bool ShouldCaptureFeatureTarget(string? featureName, string? featureTypeName)
    {
        string name = featureName?.Trim() ?? string.Empty;
        string type = featureTypeName?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(type))
        {
            return false;
        }

        if (IsExcludedFeatureTypeName(type))
        {
            return false;
        }

        if (string.IsNullOrWhiteSpace(name))
        {
            return false;
        }

        if (IsManagementFeatureName(name) || IsManagementFeatureType(type))
        {
            return false;
        }

        return IsPhysicalOrEditableFeatureType(type);
    }

    internal static bool ShouldKeepCaptureTarget(AssemblyEntityCaptureTargetInfo target, bool requireFeatureTypeName)
    {
        if (!requireFeatureTypeName)
        {
            return true;
        }

        string? featureTypeName = target.FeatureTypeName;
        if (string.IsNullOrWhiteSpace(featureTypeName))
        {
            return false;
        }

        return ShouldCaptureFeatureTarget(target.FeatureName ?? target.DisplayName, featureTypeName);
    }

    private static bool IsExcludedFeatureTypeName(string type)
        => ExcludedFeatureTypeNames.Any(excluded =>
            string.Equals(type.Trim(), excluded, StringComparison.OrdinalIgnoreCase));

    private static bool IsManagementFeatureName(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return false;
        }

        string normalized = name.Replace(" ", string.Empty, StringComparison.OrdinalIgnoreCase);
        foreach (string marker in ManagementFeatureNameMarkers)
        {
            if (normalized.Contains(marker, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsManagementFeatureType(string type)
    {
        if (string.IsNullOrWhiteSpace(type))
        {
            return false;
        }

        if (type.EndsWith("Folder", StringComparison.OrdinalIgnoreCase)
            || type.Contains("Folder", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        foreach (string marker in ManagementFeatureTypeMarkers)
        {
            if (type.Contains(marker, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsPhysicalOrEditableFeatureType(string type)
    {
        if (string.IsNullOrWhiteSpace(type))
        {
            return false;
        }

        foreach (string marker in PhysicalOrEditableFeatureTypeMarkers)
        {
            if (type.Contains(marker, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<RuntimeTarget> EnumerateComponentBodyTargets(ComponentInstance instance)
    {
        var bodies = GetBodies(instance.Component).ToList();
        for (int index = 0; index < bodies.Count; index++)
        {
            var body = bodies[index];
            string? bodyName = SafeGetBodyName(body);
            string bodyDisplayName = string.IsNullOrWhiteSpace(bodyName)
                ? $"Body{index + 1}"
                : bodyName!;
            string graphPath = $"{instance.Info.HierarchyPath}/body/{index}:{bodyDisplayName}";
            var info = new AssemblyEntityCaptureTargetInfo
            {
                TargetId = CreateTargetId(
                    "body",
                    instance.Info.HierarchyPath,
                    instance.Info.Path,
                    instance.Info.Path,
                    null,
                    index.ToString(CultureInfo.InvariantCulture),
                    bodyName),
                EntityKind = "body",
                DisplayName = graphPath,
                ComponentName = instance.Info.Name,
                ComponentPath = NormalizePathOrNull(instance.Info.Path),
                HierarchyPath = instance.Info.HierarchyPath,
                ComponentDepth = instance.Info.Depth,
                DocumentTitle = instance.Info.Name,
                DocumentPath = NormalizePathOrNull(instance.Info.Path),
                BodyName = bodyName,
                BodyIndex = index,
                Box = NormalizeBox(ToDoubleArray(body.GetBodyBox())),
                GraphPath = graphPath,
            };

            yield return new RuntimeTarget(
                info,
                body,
                "body",
                FallbackSelectionObject: instance.Component,
                FallbackSelectionKind: "owning-component");
        }
    }

    private static AssemblyEntitySelectionStatus TrySelectRuntimeTarget(
        IModelDoc2 modelDoc,
        RuntimeTarget target)
    {
        modelDoc.ClearSelection2(true);
        if (target.SelectionObject == null)
        {
            return new AssemblyEntitySelectionStatus
            {
                Attempted = false,
                Selected = false,
                Message = "No selectable COM object was available for this target.",
            };
        }

        try
        {
            var primary = TrySelectObject(modelDoc, target.SelectionObject);
            if (!primary.Selected && target.FallbackSelectionObject != null)
            {
                var fallback = TrySelectObject(modelDoc, target.FallbackSelectionObject);
                if (fallback.Selected)
                {
                    return new AssemblyEntitySelectionStatus
                    {
                        Attempted = true,
                        Selected = true,
                        Method = target.FallbackSelectionKind,
                        Message = $"Selected fallback {target.FallbackSelectionKind} for {target.Info.EntityKind} target '{target.Info.DisplayName}' because direct {target.SelectionKind} selection did not highlight it.",
                    };
                }
            }

            return new AssemblyEntitySelectionStatus
            {
                Attempted = true,
                Selected = primary.Selected,
                Method = target.SelectionKind,
                Message = primary.Selected
                    ? $"Selected {target.Info.EntityKind} target '{target.Info.DisplayName}'."
                    : $"SolidWorks did not select {target.Info.EntityKind} target '{target.Info.DisplayName}'.",
            };
        }
        catch (COMException ex)
        {
            return new AssemblyEntitySelectionStatus
            {
                Attempted = true,
                Selected = false,
                Method = target.SelectionKind,
                Message = $"Selection failed: {ex.Message}",
            };
        }
        catch (TargetInvocationException ex)
        {
            return new AssemblyEntitySelectionStatus
            {
                Attempted = true,
                Selected = false,
                Method = target.SelectionKind,
                Message = $"Selection failed: {ex.InnerException?.Message ?? ex.Message}",
            };
        }
    }

    private static (bool Selected, string? Message) TrySelectObject(IModelDoc2 modelDoc, object selectionObject)
    {
        bool selected = selectionObject switch
        {
            IComponent2 component => component.Select2(false, 0),
            Feature feature => feature.Select2(false, 0),
            IEntity entity => SelectEntity(modelDoc, entity),
            _ => TryInvokeSelect2(selectionObject),
        };

        return (selected, null);
    }

    private static bool SelectEntity(IModelDoc2 modelDoc, IEntity entity)
    {
        var selectionManager = modelDoc.SelectionManager as ISelectionMgr
            ?? throw new InvalidOperationException("SelectionManager is unavailable.");
        var selectData = selectionManager.CreateSelectData()
            ?? throw new InvalidOperationException("Could not create selection data.");
        return entity.Select4(false, selectData);
    }

    private static bool TryInvokeSelect2(object selectionObject)
    {
        foreach (object?[] args in new[]
                 {
                     new object?[] { false, null },
                     new object?[] { false },
                 })
        {
            try
            {
                var value = selectionObject.GetType().InvokeMember(
                    "Select2",
                    BindingFlags.InvokeMethod,
                    binder: null,
                    target: selectionObject,
                    args: args);
                if (value is bool selected)
                {
                    return selected;
                }
            }
            catch (MissingMethodException)
            {
                continue;
            }
            catch (ArgumentException)
            {
                continue;
            }
        }

        return false;
    }

    private async Task<AssemblyEntityDimensionAnnotationEntry> AnnotateTargetWithQwenAsync(
        HttpClient httpClient,
        string endpoint,
        string model,
        AssemblyEntityAnnotationCaptureResult manifest,
        AssemblyEntityCaptureTargetInfo target,
        CancellationToken cancellationToken)
    {
        try
        {
            var payload = CreateQwenRequestPayload(model, manifest, target);
            using var requestContent = new StringContent(JsonSerializer.Serialize(payload, JsonOptions), Encoding.UTF8, "application/json");
            using var response = await httpClient.PostAsync(endpoint, requestContent, cancellationToken).ConfigureAwait(false);
            string responseText = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return CreateFailedAnnotation(target, model, responseText, $"Qwen request failed with HTTP {(int)response.StatusCode}.");
            }

            string modelContent = ExtractOpenAiCompatibleMessageContent(responseText);
            return ParseQwenAnnotation(target, model, modelContent);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            return CreateFailedAnnotation(target, model, null, ex.Message);
        }
    }

    private static object CreateQwenRequestPayload(
        string model,
        AssemblyEntityAnnotationCaptureResult manifest,
        AssemblyEntityCaptureTargetInfo target)
    {
        var content = new List<object>
        {
            new
            {
                type = "text",
                text = BuildVisionPrompt(manifest, target),
            },
        };

        foreach (var image in target.Images)
        {
            content.Add(new
            {
                type = "image_url",
                image_url = new
                {
                    url = ToPngDataUrl(image.OutputPath),
                },
            });
        }

        return new
        {
            model,
            messages = new[]
            {
                new
                {
                    role = "user",
                    content,
                },
            },
            temperature = 0,
        };
    }

    private static string BuildVisionPrompt(
        AssemblyEntityAnnotationCaptureResult manifest,
        AssemblyEntityCaptureTargetInfo target)
    {
        var builder = new StringBuilder();
        builder.AppendLine("You are a mechanical CAD assembly dimension analyst.");
        builder.AppendLine("The images are front, top, and right orthographic views exported from SolidWorks. The target entity should be highlighted when selection succeeded.");
        builder.AppendLine("Judge whether the target entity is directly related to the active assembly's overall bounding size along global X, Y, and Z.");
        builder.AppendLine("Directly related means changing this entity, its defining feature, or its placement would likely change an outside envelope dimension in that axis.");
        builder.AppendLine("Do not mark internal details, cosmetic features, hidden construction references, or non-envelope features as related unless they directly control an outside boundary.");
        builder.AppendLine("Return strict JSON only. No markdown.");
        builder.AppendLine("JSON schema:");
        builder.AppendLine("{\"x\":{\"related\":true|false,\"description\":\"...\",\"identifiers\":[\"...\"]},\"y\":{\"related\":true|false,\"description\":\"...\",\"identifiers\":[\"...\"]},\"z\":{\"related\":true|false,\"description\":\"...\",\"identifiers\":[\"...\"]},\"overallReason\":\"...\",\"confidence\":0.0}");
        builder.AppendLine("Target metadata:");
        builder.AppendLine(JsonSerializer.Serialize(new
        {
            manifest.AssemblyTitle,
            manifest.AssemblyPath,
            target.TargetId,
            target.EntityKind,
            target.DisplayName,
            target.ComponentName,
            target.HierarchyPath,
            target.ComponentPath,
            target.DocumentPath,
            target.FeatureName,
            target.FeatureTypeName,
            target.FeaturePath,
            target.BodyName,
            target.BodyIndex,
            target.Box,
            selectionSelected = target.Selection.Selected,
            selectionMessage = target.Selection.Message,
        }, JsonOptions));
        return builder.ToString();
    }

    private static AssemblyEntityDimensionAnnotationEntry ParseQwenAnnotation(
        AssemblyEntityCaptureTargetInfo target,
        string model,
        string modelContent)
    {
        string json = ExtractJsonObjectText(modelContent);
        try
        {
            using var document = JsonDocument.Parse(json);
            var root = document.RootElement;
            return new AssemblyEntityDimensionAnnotationEntry
            {
                TargetId = target.TargetId,
                Target = target,
                X = ReadAxis(root, "x"),
                Y = ReadAxis(root, "y"),
                Z = ReadAxis(root, "z"),
                OverallReason = ReadString(root, "overallReason") ?? ReadString(root, "overall_reason"),
                Confidence = ReadDouble(root, "confidence"),
                AnnotationStatus = "completed",
                Model = model,
                RawModelResponse = modelContent,
                AnnotatedUtc = DateTime.UtcNow,
            };
        }
        catch (JsonException ex)
        {
            return CreateFailedAnnotation(target, model, modelContent, $"Could not parse strict JSON from Qwen response: {ex.Message}");
        }
    }

    private static AssemblyEntityDimensionAnnotationEntry CreateFailedAnnotation(
        AssemblyEntityCaptureTargetInfo target,
        string model,
        string? rawResponse,
        string failureReason)
    {
        return new AssemblyEntityDimensionAnnotationEntry
        {
            TargetId = target.TargetId,
            Target = target,
            AnnotationStatus = "failed",
            Model = model,
            RawModelResponse = rawResponse,
            FailureReason = failureReason,
            AnnotatedUtc = DateTime.UtcNow,
        };
    }

    private static string ExtractOpenAiCompatibleMessageContent(string responseText)
    {
        using var document = JsonDocument.Parse(responseText);
        var root = document.RootElement;
        if (root.TryGetProperty("choices", out var choices)
            && choices.ValueKind == JsonValueKind.Array
            && choices.GetArrayLength() > 0)
        {
            var first = choices[0];
            if (first.TryGetProperty("message", out var message)
                && message.TryGetProperty("content", out var content))
            {
                return content.ValueKind == JsonValueKind.String
                    ? content.GetString() ?? string.Empty
                    : content.GetRawText();
            }
        }

        return responseText;
    }

    private static string ExtractJsonObjectText(string text)
    {
        string trimmed = text.Trim();
        if (trimmed.StartsWith("```", StringComparison.Ordinal))
        {
            int firstNewline = trimmed.IndexOf('\n');
            int lastFence = trimmed.LastIndexOf("```", StringComparison.Ordinal);
            if (firstNewline >= 0 && lastFence > firstNewline)
            {
                trimmed = trimmed[(firstNewline + 1)..lastFence].Trim();
            }
        }

        int start = trimmed.IndexOf('{');
        int end = trimmed.LastIndexOf('}');
        return start >= 0 && end >= start
            ? trimmed[start..(end + 1)]
            : trimmed;
    }

    private static IReadOnlyList<AssemblyEntityDimensionAnnotationEntry> ParseImportedAnnotationEntries(
        string json,
        AssemblyEntityAnnotationCaptureResult manifest)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        if (root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty("entries", out _))
        {
            var importedSet = JsonSerializer.Deserialize<AssemblyEntityDimensionAnnotationSet>(json, JsonOptions)
                ?? throw new InvalidOperationException("Could not deserialize annotation set.");
            return importedSet.Entries
                .Select(entry => AttachTargetFromManifest(entry, manifest))
                .ToList()
                .AsReadOnly();
        }

        JsonElement entriesElement = root;
        if (root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty("annotations", out var annotations))
        {
            entriesElement = annotations;
        }

        if (entriesElement.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidOperationException("Annotation JSON must be an array, an object with 'annotations', or a full annotation set with 'entries'.");
        }

        var entries = new List<AssemblyEntityDimensionAnnotationEntry>();
        foreach (var item in entriesElement.EnumerateArray())
        {
            string targetId = ReadString(item, "targetId")
                ?? ReadString(item, "target_id")
                ?? throw new InvalidOperationException("Each annotation entry must include targetId.");
            var target = manifest.Targets.FirstOrDefault(candidate => string.Equals(candidate.TargetId, targetId, StringComparison.OrdinalIgnoreCase));

            entries.Add(new AssemblyEntityDimensionAnnotationEntry
            {
                TargetId = targetId,
                Target = target,
                X = ReadAxis(item, "x"),
                Y = ReadAxis(item, "y"),
                Z = ReadAxis(item, "z"),
                OverallReason = ReadString(item, "overallReason") ?? ReadString(item, "overall_reason"),
                Confidence = ReadDouble(item, "confidence"),
                AnnotationStatus = ReadString(item, "annotationStatus") ?? ReadString(item, "annotation_status") ?? "imported",
                Model = ReadString(item, "model"),
                RawModelResponse = ReadString(item, "rawModelResponse") ?? ReadString(item, "raw_model_response"),
                FailureReason = ReadString(item, "failureReason") ?? ReadString(item, "failure_reason"),
                AnnotatedUtc = DateTime.UtcNow,
            });
        }

        return entries.AsReadOnly();
    }

    private static AssemblyEntityDimensionAnnotationEntry AttachTargetFromManifest(
        AssemblyEntityDimensionAnnotationEntry entry,
        AssemblyEntityAnnotationCaptureResult manifest)
    {
        var target = entry.Target
            ?? manifest.Targets.FirstOrDefault(candidate => string.Equals(candidate.TargetId, entry.TargetId, StringComparison.OrdinalIgnoreCase));
        return entry with { Target = target };
    }

    private static DimensionAxisAnnotationInfo ReadAxis(JsonElement root, string name)
    {
        if (!TryGetPropertyCaseInsensitive(root, name, out var axis))
        {
            return new DimensionAxisAnnotationInfo();
        }

        if (axis.ValueKind == JsonValueKind.True || axis.ValueKind == JsonValueKind.False)
        {
            return new DimensionAxisAnnotationInfo
            {
                Related = axis.GetBoolean(),
            };
        }

        if (axis.ValueKind != JsonValueKind.Object)
        {
            return new DimensionAxisAnnotationInfo();
        }

        return new DimensionAxisAnnotationInfo
        {
            Related = ReadBool(axis, "related"),
            Description = ReadString(axis, "description"),
            Identifiers = ReadStringArray(axis, "identifiers"),
        };
    }

    private static bool ReadBool(JsonElement root, string name)
    {
        if (!TryGetPropertyCaseInsensitive(root, name, out var value))
        {
            return false;
        }

        return value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => bool.TryParse(value.GetString(), out bool parsed) && parsed,
            _ => false,
        };
    }

    private static string? ReadString(JsonElement root, string name)
    {
        if (!TryGetPropertyCaseInsensitive(root, name, out var value)
            || value.ValueKind == JsonValueKind.Null
            || value.ValueKind == JsonValueKind.Undefined)
        {
            return null;
        }

        return value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : value.GetRawText();
    }

    private static double? ReadDouble(JsonElement root, string name)
    {
        if (!TryGetPropertyCaseInsensitive(root, name, out var value))
        {
            return null;
        }

        if (value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out double parsed))
        {
            return parsed;
        }

        if (value.ValueKind == JsonValueKind.String
            && double.TryParse(value.GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out parsed))
        {
            return parsed;
        }

        return null;
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement root, string name)
    {
        if (!TryGetPropertyCaseInsensitive(root, name, out var value)
            || value.ValueKind != JsonValueKind.Array)
        {
            return Array.Empty<string>();
        }

        return value.EnumerateArray()
            .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() : item.GetRawText())
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Select(item => item!)
            .ToList()
            .AsReadOnly();
    }

    private static bool TryGetPropertyCaseInsensitive(JsonElement root, string name, out JsonElement value)
    {
        if (root.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in root.EnumerateObject())
            {
                if (string.Equals(property.Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    value = property.Value;
                    return true;
                }
            }
        }

        value = default;
        return false;
    }

    private static AssemblyEntityDimensionAnnotationSet CreateAnnotationSet(
        AssemblyEntityAnnotationCaptureResult manifest,
        string annotationPath,
        IReadOnlyList<AssemblyEntityDimensionAnnotationEntry> entries)
    {
        return new AssemblyEntityDimensionAnnotationSet
        {
            SchemaVersion = AnnotationSchemaVersion,
            CreatedUtc = DateTime.UtcNow,
            ManifestPath = manifest.ManifestPath,
            AssemblyPath = manifest.AssemblyPath,
            AssemblyTitle = manifest.AssemblyTitle,
            AnnotationPath = annotationPath,
            EntryCount = entries.Count,
            Entries = entries,
        };
    }

    private static IReadOnlyList<string> GetRelatedAxes(AssemblyEntityDimensionAnnotationEntry entry, string? axis)
    {
        var related = new List<string>();
        if ((axis == null || axis == "x") && entry.X.Related)
        {
            related.Add("x");
        }

        if ((axis == null || axis == "y") && entry.Y.Related)
        {
            related.Add("y");
        }

        if ((axis == null || axis == "z") && entry.Z.Related)
        {
            related.Add("z");
        }

        return related.AsReadOnly();
    }

    private static AssemblyEntityStructuralInfo? GetStructuralInfo(AssemblyEntityCaptureTargetInfo target)
        => target.StructualInfo ?? target.StructuralInfo;

    private static string? NormalizeStructuralType(string? type)
    {
        if (string.IsNullOrWhiteSpace(type))
        {
            return null;
        }

        string normalized = type.Trim().ToLowerInvariant();
        return normalized switch
        {
            "height" or "h" or "z" or "高" or "高度" or "增高" or "升高" => "height",
            "length" or "len" or "l" or "x" or "长" or "长度" or "加长" or "延长" => "length",
            _ => normalized,
        };
    }

    private static string? InferStructuralTypeFromQuery(string? query)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return null;
        }

        string normalized = query.Trim();
        if (normalized.Contains("height", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("tall", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("高", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("高度", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("增高", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("升高", StringComparison.OrdinalIgnoreCase))
        {
            return "height";
        }

        if (normalized.Contains("length", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("long", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("长", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("长度", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("加长", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("延长", StringComparison.OrdinalIgnoreCase))
        {
            return "length";
        }

        return null;
    }

    private static int ScoreStructuralTarget(
        AssemblyEntityCaptureTargetInfo target,
        AssemblyEntityStructuralInfo info,
        string structuralType,
        string? requestedType,
        string? query)
    {
        int score = 1000;
        if (requestedType != null && string.Equals(structuralType, requestedType, StringComparison.OrdinalIgnoreCase))
        {
            score += 1000;
        }

        if (target.EntityKind.Equals("feature", StringComparison.OrdinalIgnoreCase))
        {
            score += 200;
        }

        if (target.HasSubFeatures == true)
        {
            score += 100;
        }

        if (query == null)
        {
            return score;
        }

        string haystack = BuildStructuralSearchText(target, info, structuralType);
        foreach (var token in SplitTokens(query))
        {
            if (haystack.Contains(token, StringComparison.OrdinalIgnoreCase))
            {
                score += 100;
            }
        }

        if (haystack.Contains(query, StringComparison.OrdinalIgnoreCase))
        {
            score += 500;
        }

        return score;
    }

    private static string BuildStructuralSearchText(
        AssemblyEntityCaptureTargetInfo target,
        AssemblyEntityStructuralInfo info,
        string structuralType)
    {
        return string.Join(" | ", new[]
        {
            target.TargetId,
            target.EntityKind,
            target.DisplayName,
            target.ComponentName,
            target.ComponentPath,
            target.HierarchyPath,
            target.DocumentTitle,
            target.DocumentPath,
            target.FeatureName,
            target.FeatureTypeName,
            target.FeaturePath,
            target.GraphPath,
            structuralType,
            info.Type,
            info.Description,
            string.Join(" ", info.Identifiers),
        }.Where(value => !string.IsNullOrWhiteSpace(value)));
    }

    private static int ScoreAnnotation(AssemblyEntityDimensionAnnotationEntry entry, string? axis, string? query)
    {
        int score = GetRelatedAxes(entry, axis).Count * 1000;
        if (query == null)
        {
            return score;
        }

        string haystack = BuildSearchText(entry);
        foreach (var token in SplitTokens(query))
        {
            if (haystack.Contains(token, StringComparison.OrdinalIgnoreCase))
            {
                score += 100;
            }
        }

        if (haystack.Contains(query, StringComparison.OrdinalIgnoreCase))
        {
            score += 500;
        }

        return score;
    }

    private static string BuildSearchText(AssemblyEntityDimensionAnnotationEntry entry)
    {
        var target = entry.Target;
        return string.Join(" | ", new[]
        {
            entry.TargetId,
            target?.EntityKind,
            target?.DisplayName,
            target?.ComponentName,
            target?.HierarchyPath,
            target?.ComponentPath,
            target?.DocumentPath,
            target?.FeatureName,
            target?.FeatureTypeName,
            target?.FeaturePath,
            target?.BodyName,
            entry.X.Description,
            entry.Y.Description,
            entry.Z.Description,
            string.Join(" ", entry.X.Identifiers),
            string.Join(" ", entry.Y.Identifiers),
            string.Join(" ", entry.Z.Identifiers),
            entry.OverallReason,
        }.Where(item => !string.IsNullOrWhiteSpace(item)));
    }

    private static IEnumerable<string> SplitTokens(string query)
        => query
            .Split([' ', ',', ';', '/', '\\', '|', ':', '-', '_', '，', '；', '、'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(token => token.Length > 0);

    private static string? NormalizeAxis(string? axis)
    {
        if (string.IsNullOrWhiteSpace(axis)
            || string.Equals(axis, "all", StringComparison.OrdinalIgnoreCase)
            || string.Equals(axis, "*", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        string normalized = axis.Trim().ToLowerInvariant();
        return normalized switch
        {
            "x" or "width" or "length" => "x",
            "y" or "depth" => "y",
            "z" or "height" => "z",
            _ => throw new ArgumentException("axis must be x, y, z, all, or omitted.", nameof(axis)),
        };
    }

    private static string? NormalizeQuery(string? query)
        => string.IsNullOrWhiteSpace(query) ? null : query.Trim();

    private static int FindTargetOrder(AssemblyEntityAnnotationCaptureResult manifest, string targetId)
    {
        for (int index = 0; index < manifest.Targets.Count; index++)
        {
            if (string.Equals(manifest.Targets[index].TargetId, targetId, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }

        return int.MaxValue;
    }

    private static AssemblyEntityCaptureTargetInfo? LoadTargetFromManifestOrAnnotation(string sourcePath, string targetId)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(sourcePath, Encoding.UTF8));
        if (document.RootElement.TryGetProperty("targets", out _))
        {
            var manifest = LoadCaptureManifest(sourcePath);
            return manifest.Targets.FirstOrDefault(target => string.Equals(target.TargetId, targetId, StringComparison.OrdinalIgnoreCase));
        }

        var annotations = LoadAnnotationSet(sourcePath);
        return annotations.Entries
            .FirstOrDefault(entry => string.Equals(entry.TargetId, targetId, StringComparison.OrdinalIgnoreCase))
            ?.Target;
    }

    private static AssemblyEntityAnnotationCaptureResult LoadCaptureManifest(string manifestPath)
    {
        string normalized = Path.GetFullPath(manifestPath);
        if (!File.Exists(normalized))
        {
            throw new FileNotFoundException($"Capture manifest was not found: {normalized}", normalized);
        }

        var manifest = JsonSerializer.Deserialize<AssemblyEntityAnnotationCaptureResult>(File.ReadAllText(normalized, Encoding.UTF8), JsonOptions)
            ?? throw new InvalidOperationException($"Could not deserialize capture manifest: {normalized}");
        return manifest with
        {
            ManifestPath = string.IsNullOrWhiteSpace(manifest.ManifestPath) ? normalized : Path.GetFullPath(manifest.ManifestPath),
            OutputDirectory = string.IsNullOrWhiteSpace(manifest.OutputDirectory)
                ? Path.GetDirectoryName(normalized) ?? Directory.GetCurrentDirectory()
                : Path.GetFullPath(manifest.OutputDirectory),
        };
    }

    private static AssemblyEntityAnnotationTargetIndex LoadTargetIndex(string indexPath)
    {
        string normalized = Path.GetFullPath(indexPath);
        if (!File.Exists(normalized))
        {
            throw new FileNotFoundException($"Target index was not found: {normalized}", normalized);
        }

        var index = JsonSerializer.Deserialize<AssemblyEntityAnnotationTargetIndex>(File.ReadAllText(normalized, Encoding.UTF8), JsonOptions)
            ?? throw new InvalidOperationException($"Could not deserialize target index: {normalized}");
        return index with
        {
            IndexPath = string.IsNullOrWhiteSpace(index.IndexPath) ? normalized : Path.GetFullPath(index.IndexPath),
            OutputDirectory = string.IsNullOrWhiteSpace(index.OutputDirectory)
                ? Path.GetDirectoryName(normalized) ?? Directory.GetCurrentDirectory()
                : Path.GetFullPath(index.OutputDirectory),
        };
    }

    private static AssemblyEntityDimensionAnnotationSet LoadAnnotationSet(string annotationPath)
    {
        string normalized = Path.GetFullPath(annotationPath);
        if (!File.Exists(normalized))
        {
            throw new FileNotFoundException($"Annotation file was not found: {normalized}", normalized);
        }

        var annotations = JsonSerializer.Deserialize<AssemblyEntityDimensionAnnotationSet>(File.ReadAllText(normalized, Encoding.UTF8), JsonOptions)
            ?? throw new InvalidOperationException($"Could not deserialize annotation file: {normalized}");
        return annotations with
        {
            AnnotationPath = string.IsNullOrWhiteSpace(annotations.AnnotationPath) ? normalized : Path.GetFullPath(annotations.AnnotationPath),
        };
    }

    private static string NormalizeOutputAnnotationPath(AssemblyEntityAnnotationCaptureResult manifest, string? outputPath)
    {
        string path = string.IsNullOrWhiteSpace(outputPath)
            ? Path.Combine(manifest.OutputDirectory, "dimension-annotations.json")
            : outputPath!;
        path = Path.GetFullPath(path);
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        return path;
    }

    private static void WriteJson<T>(string path, T value)
    {
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(path, JsonSerializer.Serialize(value, JsonOptions), Encoding.UTF8);
    }

    private static string ResolveConfiguredValue(string? explicitValue, string primaryEnv, string secondaryEnv, string fallback)
    {
        if (!string.IsNullOrWhiteSpace(explicitValue))
        {
            return explicitValue.Trim();
        }

        string? primary = System.Environment.GetEnvironmentVariable(primaryEnv);
        if (!string.IsNullOrWhiteSpace(primary))
        {
            return primary.Trim();
        }

        string? secondary = System.Environment.GetEnvironmentVariable(secondaryEnv);
        return string.IsNullOrWhiteSpace(secondary) ? fallback : secondary.Trim();
    }

    private static string ResolveChatCompletionsEndpoint(string baseUrl)
    {
        string trimmed = baseUrl.Trim().TrimEnd('/');
        return trimmed.EndsWith("/chat/completions", StringComparison.OrdinalIgnoreCase)
            ? trimmed
            : $"{trimmed}/chat/completions";
    }

    private static string ToPngDataUrl(string path)
    {
        string normalized = Path.GetFullPath(path);
        if (!File.Exists(normalized))
        {
            throw new FileNotFoundException($"Captured image was not found: {normalized}", normalized);
        }

        string base64 = Convert.ToBase64String(File.ReadAllBytes(normalized));
        return $"data:image/png;base64,{base64}";
    }

    private static string ToSafePathSegment(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char c in value)
        {
            builder.Append(char.IsLetterOrDigit(c) || c is '-' or '_' ? c : '_');
        }

        return builder.ToString();
    }

    private static string CreateTargetId(
        string entityKind,
        string? hierarchyPath,
        string? componentPath,
        string? documentPath,
        string? featurePath,
        string? entityIndex,
        string? entityName)
    {
        string canonical = string.Join("|", new[]
        {
            entityKind,
            hierarchyPath ?? string.Empty,
            componentPath ?? string.Empty,
            documentPath ?? string.Empty,
            featurePath ?? string.Empty,
            entityIndex ?? string.Empty,
            entityName ?? string.Empty,
        });
        byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return $"ae_{Convert.ToHexString(hash)[..16].ToLowerInvariant()}";
    }

    private static IReadOnlyList<ComponentInstance> EnumerateComponentInstances(IAssemblyDoc assy)
    {
        var raw = assy.GetComponents(true) as object[] ?? [];
        var results = new List<ComponentInstance>();
        foreach (var component in raw.OfType<IComponent2>())
        {
            TraverseComponent(component, component.Name2 ?? "Component", depth: 0, results);
        }

        return results.AsReadOnly();
    }

    private static void TraverseComponent(
        IComponent2 component,
        string hierarchyPath,
        int depth,
        ICollection<ComponentInstance> results)
    {
        string name = SafeGetComponentName(component) ?? $"Component{depth}";
        string path = NormalizePathOrNull(SafeGetComponentPath(component)) ?? string.Empty;
        results.Add(new ComponentInstance(component, new ComponentInstanceInfo(name, path, hierarchyPath, depth)));

        var children = SafeGetComponentChildren(component);
        foreach (var child in children.OfType<IComponent2>())
        {
            string childName = SafeGetComponentName(child) ?? "Component";
            TraverseComponent(child, $"{hierarchyPath}/{childName}", depth + 1, results);
        }
    }

    private IAssemblyDoc GetAssemblyDoc()
    {
        var doc = _cm.SwApp!.IActiveDoc2;
        if (doc == null)
        {
            int visibleDocumentCount = 0;
            IReadOnlyList<string> visibleDocuments = Array.Empty<string>();
            try
            {
                visibleDocumentCount = _cm.SwApp!.GetDocumentCount();
                visibleDocuments = _cm.SwApp!.ListDocs()
                    .Select(item => string.IsNullOrWhiteSpace(item.Path)
                        ? item.Title
                        : $"{item.Title} | {item.Path}")
                    .Where(item => !string.IsNullOrWhiteSpace(item))
                    .ToArray();
            }
            catch
            {
                // Diagnostic details are best-effort.
            }

            string detail = visibleDocuments.Count == 0
                ? $"MCP sees {visibleDocumentCount} open document(s), but none is active."
                : $"MCP sees {visibleDocumentCount} open document(s), but none is active: {string.Join("; ", visibleDocuments)}";
            throw new InvalidOperationException(
                "No active document. " + detail +
                " If SolidWorks visibly has a document open, the MCP Hub may be attached to a different or stale SolidWorks COM instance. " +
                "Use the Python runner --force-reconnect or --document <full .SLDASM path>, or restart the MCP tray/Hub.");
        }

        return doc as IAssemblyDoc
            ?? throw new InvalidOperationException("Active document is not an assembly");
    }

    private static void SafeGraphicsRedraw(IModelDoc2 doc)
    {
        try
        {
            doc.GraphicsRedraw2();
        }
        catch (COMException)
        {
            // Best-effort visual refresh only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort visual refresh only.
        }
    }

    private static void SafeDrawHighlightedItems(IModelDoc2 doc)
    {
        try
        {
            doc.IActiveView?.DrawHighlightedItems();
        }
        catch (COMException)
        {
            // Best-effort visual refresh only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort visual refresh only.
        }
    }

    private static void SafeActivateAndRepaintView(IModelDoc2 doc)
    {
        try
        {
            var activeView = doc.IActiveView;
            if (activeView == null)
            {
                return;
            }

            activeView.GetType().InvokeMember(
                "Repaint",
                BindingFlags.InvokeMethod,
                binder: null,
                target: activeView,
                args: Array.Empty<object>());
        }
        catch (MissingMethodException)
        {
            // Older interop wrappers may not expose IModelView.Repaint.
        }
        catch (COMException)
        {
            // Best-effort visual refresh only.
        }
        catch (TargetInvocationException)
        {
            // Best-effort visual refresh only.
        }
        catch (ArgumentException)
        {
            // Best-effort visual refresh only.
        }
    }

    private static string? SafeGetComponentName(IComponent2 component)
    {
        try
        {
            return component.Name2;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string? SafeGetComponentPath(IComponent2 component)
    {
        try
        {
            return component.GetPathName();
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static object[] SafeGetComponentChildren(IComponent2 component)
    {
        try
        {
            return component.GetChildren() as object[] ?? [];
        }
        catch (COMException)
        {
            return [];
        }
    }

    private static IModelDoc2? SafeGetComponentModelDoc(IComponent2 component)
    {
        try
        {
            return component.GetModelDoc2() as IModelDoc2;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static Feature? SafeGetFirstFeature(IModelDoc2 doc)
    {
        try
        {
            return doc.FirstFeature() as Feature;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static Feature? SafeGetNextFeature(Feature feature)
    {
        try
        {
            return feature.GetNextFeature() as Feature;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static Feature? SafeGetFirstSubFeature(Feature feature)
    {
        try
        {
            return feature.GetFirstSubFeature() as Feature;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static Feature? SafeGetNextSubFeature(Feature feature)
    {
        try
        {
            return feature.GetNextSubFeature() as Feature;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string? SafeGetFeatureName(Feature feature)
    {
        try
        {
            return feature.Name;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string? SafeGetFeatureTypeName(Feature feature)
    {
        try
        {
            return feature.GetTypeName2();
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string? SafeGetDocumentTitle(IModelDoc2 doc)
    {
        try
        {
            return doc.GetTitle();
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string? SafeGetDocumentPath(IModelDoc2 doc)
    {
        try
        {
            return doc.GetPathName();
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static IEnumerable<IBody2> GetBodies(IComponent2 component)
    {
        try
        {
            return (component.GetBodies3((int)swBodyType_e.swSolidBody, out _) as object[] ?? [])
                .OfType<IBody2>();
        }
        catch (COMException)
        {
            return [];
        }
    }

    private static string? SafeGetBodyName(IBody2 body)
    {
        try
        {
            return ((object)body).GetType().InvokeMember(
                "Name",
                BindingFlags.GetProperty,
                binder: null,
                target: body,
                args: null) as string;
        }
        catch
        {
            return null;
        }
    }

    private static double[]? NormalizeBox(double[]? box)
    {
        if (box == null || box.Length < 6)
        {
            return null;
        }

        return
        [
            Math.Round(box[0], 9, MidpointRounding.AwayFromZero),
            Math.Round(box[1], 9, MidpointRounding.AwayFromZero),
            Math.Round(box[2], 9, MidpointRounding.AwayFromZero),
            Math.Round(box[3], 9, MidpointRounding.AwayFromZero),
            Math.Round(box[4], 9, MidpointRounding.AwayFromZero),
            Math.Round(box[5], 9, MidpointRounding.AwayFromZero),
        ];
    }

    private static double[]? ToDoubleArray(object? raw)
    {
        return raw switch
        {
            null => null,
            double[] doubles => doubles,
            object[] objects => objects.OfType<double>().ToArray(),
            _ => null,
        };
    }

    private static string? NormalizePathOrNull(string? path)
        => string.IsNullOrWhiteSpace(path) ? null : path.Trim();
}
