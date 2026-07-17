using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;

namespace SolidWorksBridge.SolidWorks;

/// <summary>
/// Result of a selection operation.
/// </summary>
public record SelectionResult(
    bool Success,
    string Message,
    SelectableEntityType? EntityType = null,
    int? EntityIndex = null,
    string? ComponentName = null,
    double[]? Box = null);

/// <summary>
/// World-space center of the currently selected planar or non-planar face.
/// The center is computed from the selected face bounding box in assembly coordinates.
/// </summary>
public record SelectedFaceCenterResult(
    bool Success,
    string Message,
    double[]? Center = null,
    double? Area = null);

/// <summary>
/// Reference plane metadata discovered from the active document feature tree.
/// </summary>
public record ReferencePlaneInfo(
    int Index,
    string Name,
    string SelectionName,
    string SelectionType);

/// <summary>
/// Small snapshot of the current SolidWorks language and active-document planes.
/// </summary>
public record SolidWorksContextInfo(
    string CurrentLanguage,
    IReadOnlyList<ReferencePlaneInfo> ReferencePlanes);

/// <summary>
/// Lightweight description of a top-level FeatureManager node.
/// </summary>
public record FeatureTreeItemInfo(
    int Index,
    string Name,
    string TypeName,
    bool IsSketch,
    bool HasChildren);

public record FeatureManagerTreeNodeInfo(
    int NodeIndex,
    int Depth,
    string Text,
    int ObjectType,
    string? ObjectKind,
    bool IsRoot,
    bool IsExpanded,
    string? GraphPath,
    string? ParentGraphPath,
    string? FeatureName,
    string? FeatureTypeName,
    bool IsSketch,
    string? ComponentName,
    string? ComponentPath,
    string? DocumentTitle,
    string? DocumentPath);

public record ActiveFeatureManagerTreeResult(
    string DocumentTitle,
    int DocumentType,
    string? DocumentPath,
    int NodeCount,
    IReadOnlyList<FeatureManagerTreeNodeInfo> Nodes);

/// <summary>
/// Structured snapshot of one SolidWorks sensor attached to the active document.
/// </summary>
public record ModelHealthSensorInfo(
    int Index,
    string Name,
    string TypeName,
    string? DocumentPath,
    string DocumentReference,
    string SensorType,
    int SensorTypeCode,
    bool AlertEnabled,
    string? AlertType,
    int? AlertTypeCode,
    double? AlertValue1,
    double? AlertValue2,
    string? ThresholdDescription,
    bool AlertTriggered,
    double? CurrentValue,
    string? Units,
    string? FeatureDataType,
    string Status,
    string? FailureReason);

/// <summary>
/// Diagnostic state for one FeatureManager node based on SolidWorks feature error codes.
/// </summary>
public record FeatureDiagnosticInfo(
    int Index,
    string Name,
    string TypeName,
    bool IsSketch,
    bool HasChildren,
    bool HasIssue,
    int ErrorCode,
    bool IsWarning,
    string ErrorName,
    string ErrorDescription,
    bool AppearsInWhatsWrong,
    DiagnosticTargetContextInfo? TargetContext = null);

/// <summary>
/// Resolved ownership context for one diagnostic item when the active document is an assembly.
/// </summary>
public record DiagnosticTargetContextInfo(
    string ScopeType,
    bool IsExact,
    bool IsAmbiguous,
    string? DocumentPath,
    string? HierarchyPath,
    string? ComponentName,
    string? SourceFilePath,
    string? OwningAssemblyHierarchyPath,
    string? OwningAssemblyFilePath,
    int SourceFileReuseCount,
    string? Reason,
    IReadOnlyList<ComponentInstanceInfo> MatchingInstances);

/// <summary>
/// One issue-bearing diagnostic item enriched with assembly target context.
/// </summary>
public record CorrelatedDiagnosticIssueInfo(
    string Source,
    int? Index,
    string Name,
    string TypeName,
    int ErrorCode,
    bool IsWarning,
    string ErrorName,
    string ErrorDescription,
    bool AppearsInWhatsWrong,
    DiagnosticTargetContextInfo TargetContext);

/// <summary>
/// One item from SolidWorks' What's Wrong system for the active document.
/// </summary>
public record WhatsWrongItemInfo(
    string Name,
    string TypeName,
    int ErrorCode,
    bool IsWarning,
    string ErrorName,
    string ErrorDescription,
    DiagnosticTargetContextInfo? TargetContext = null);

/// <summary>
/// Combined feature-tree and What's Wrong diagnostics for the active document.
/// </summary>
public record FeatureDiagnosticsResult(
    IReadOnlyList<FeatureDiagnosticInfo> FeatureDiagnostics,
    IReadOnlyList<WhatsWrongItemInfo> WhatsWrongItems,
    int ErrorCount,
    int WarningCount,
    IReadOnlyList<CorrelatedDiagnosticIssueInfo>? CorrelatedIssues = null);

/// <summary>
/// Lightweight description of whether the active document is currently in an edit mode
/// that blocks safe feature-tree reads or delete operations.
/// </summary>
public record EditStateInfo(
    bool IsEditing,
    string EditMode,
    bool CanReadFeatureTree,
    bool CanDeleteFeatures);

/// <summary>
/// Result of deleting one or more features from the active document.
/// </summary>
public record DeleteFeaturesResult(
    int DeletedCount,
    IReadOnlyList<string> DeletedFeatureNames,
    IReadOnlyList<string> FailedFeatureNames);

/// <summary>
/// Supported selectable topology entity kinds.
/// </summary>
public enum SelectableEntityType
{
    Face,
    Edge,
    Vertex,
}

/// <summary>
/// Lightweight description of a selectable topology entity.
/// </summary>
public record SelectableEntityInfo(
    int Index,
    SelectableEntityType EntityType,
    string? ComponentName,
    double[]? Box);

/// <summary>
/// Result of a face-mapping record or select operation.
/// </summary>
public record FaceMappingResult(
    bool Success,
    string Message,
    string? FaceName,
    string? ComponentName,
    FaceMappingSelectionDiagnostics? Diagnostics = null);

public record FaceMappingSelectionDiagnostics(
    string? LeafComponentName,
    string? LeafComponentFullName,
    double[]? SavedLocalCenter,
    double? SavedArea,
    double[]? SavedLocalNormal,
    double CenterTolerance,
    double AreaRelativeTolerance,
    double NormalDotTolerance,
    string? FailureReason,
    IReadOnlyList<FaceMappingCandidateDiagnostic> Candidates);

public record FaceMappingCandidateDiagnostic(
    int Rank,
    double Score,
    bool Accepted,
    string? RejectReason,
    double CenterDistance,
    double? Area,
    double? AreaRelativeError,
    double? NormalDot,
    double[]? LocalCenter,
    double[]? LocalNormal,
    double[]? Box);

public record FaceMappingProbeResult(
    bool Success,
    string Message,
    string? FaceName,
    string? ComponentName,
    string? LeafComponentName,
    string? LeafComponentFullName,
    double[]? WorldCenter,
    double[]? LocalCenter,
    double[]? WorldNormal,
    double[]? LocalNormal,
    double? Area,
    double[]? Box,
    string MappingPath);

/// <summary>
/// Stable reference to a measured topology entity.
/// </summary>
public record MeasuredEntityInfo(
    SelectableEntityType EntityType,
    int Index,
    string? ComponentName,
    double[]? Box);

/// <summary>
/// Result of measuring two topology entities using SolidWorks' official IMeasure API.
/// Distances are reported in meters when available; unavailable values are null.
/// </summary>
public record EntityMeasurementResult(
    MeasuredEntityInfo FirstEntity,
    MeasuredEntityInfo SecondEntity,
    int ArcOption,
    double? Distance,
    double? NormalDistance,
    double? CenterDistance,
    double? Angle,
    double? DeltaX,
    double? DeltaY,
    double? DeltaZ,
    double? Projection,
    double? X,
    double? Y,
    double? Z,
    bool IsParallel,
    bool IsPerpendicular,
    bool IsIntersect);

/// <summary>
/// Interface for selecting entities in the active document.
/// All sketch / feature / assembly operations depend on prior selection.
/// </summary>
public interface ISelectionService
{
    /// <summary>
    /// Select an entity by its name and type string (e.g. "Front Plane", "swSelDATUMPLANES").
    /// Coordinates default to 0,0,0 which is sufficient for named entities.
    /// </summary>
    SelectionResult SelectByName(string name, string selType, bool append = false, int mark = 0);

    /// <summary>
    /// List selectable topology entities on the active part or assembly.
    /// </summary>
    IReadOnlyList<SelectableEntityInfo> ListEntities(
        SelectableEntityType? entityType = null,
        string? componentName = null);

    /// <summary>
    /// List reference planes from the active document by traversing the feature tree.
    /// The returned names are localized to the current SolidWorks language.
    /// </summary>
    IReadOnlyList<ReferencePlaneInfo> ListReferencePlanes();

    /// <summary>
    /// Get the current SolidWorks UI language and the active document's reference planes.
    /// If no document is open, the plane list is empty.
    /// </summary>
    SolidWorksContextInfo GetSolidWorksContext();

    /// <summary>
    /// Enumerate the active document's top-level FeatureManager nodes.
    /// </summary>
    IReadOnlyList<FeatureTreeItemInfo> ListFeatureTree();

    /// <summary>
    /// Traverse the active document's FeatureManager tree exactly as shown in the SolidWorks UI.
    /// </summary>
    ActiveFeatureManagerTreeResult TraverseActiveFeatureManagerTree();

    /// <summary>
    /// Enumerate the active document's sensor features and current alert state.
    /// </summary>
    IReadOnlyList<ModelHealthSensorInfo> ListModelHealthSensors();

    /// <summary>
    /// Read SolidWorks feature error codes and What's Wrong items for the active document.
    /// </summary>
    FeatureDiagnosticsResult GetFeatureDiagnostics();

    /// <summary>
    /// Report whether the active document is currently editing a sketch or is otherwise in a safe state
    /// for feature-tree reads and delete operations.
    /// </summary>
    EditStateInfo GetEditState();

    /// <summary>
    /// Select a topology entity by the index returned from <see cref="ListEntities"/>.
    /// </summary>
    SelectionResult SelectEntity(
        SelectableEntityType entityType,
        int index,
        bool append = false,
        int mark = 0,
        string? componentName = null);

    /// <summary>
    /// Measure two topology entities by their ListEntities indexes using SolidWorks' official IMeasure API.
    /// </summary>
    EntityMeasurementResult MeasureEntities(
        SelectableEntityType firstEntityType,
        int firstIndex,
        SelectableEntityType secondEntityType,
        int secondIndex,
        string? firstComponentName = null,
        string? secondComponentName = null,
        int arcOption = 1);

    /// <summary>
    /// Delete a top-level feature or sketch by its feature-tree name.
    /// </summary>
    SelectionResult DeleteFeatureByName(string featureName);

    /// <summary>
    /// Delete loose sketches that are present in the FeatureManager but are not consumed by downstream features.
    /// </summary>
    DeleteFeaturesResult DeleteUnusedSketches();

    /// <summary>Clear the current selection set.</summary>
    void ClearSelection();

    /// <summary>
    /// Record the currently-selected face into the persistent face mapping file.
    /// The face is stored in component-local coordinates so the entry survives
    /// move/rotate/mate operations on the owning component.
    /// </summary>
    FaceMappingResult RecordFaceMapping(string faceName, string componentName);

    /// <summary>
    /// Record the first solid-body face found under a component. This is a demo fallback for
    /// components where any stable face is acceptable.
    /// </summary>
    FaceMappingResult RecordFirstFaceMapping(string faceName, string componentName);

    /// <summary>
    /// Select a face previously recorded with <see cref="RecordFaceMapping"/> by its name.
    /// Matching is done in component-local coordinates, so the selection is stable
    /// across move/rotate/mate operations.
    /// </summary>
    FaceMappingResult SelectFaceByName(string faceName, string componentName, bool append = false, int mark = 0);

    /// <summary>
    /// Return the mapping-style geometry fingerprint for the currently selected face without writing face_mappings.json.
    /// </summary>
    FaceMappingProbeResult GetSelectedFaceMappingProbe(string? faceName = null, string? componentName = null);

    /// <summary>Return the world-space bounding-box center for the currently selected face.</summary>
    SelectedFaceCenterResult GetSelectedFaceCenter();
}

/// <summary>
/// Implements <see cref="ISelectionService"/> via <see cref="ISwConnectionManager"/>.
/// </summary>
public class SelectionService : ISelectionService
{
    private enum StandardPlaneKind
    {
        Unknown = 0,
        Front,
        Top,
        Right,
    }

    private static readonly IReadOnlyDictionary<string, string[]> SelectionTypeAliases =
        new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            ["swSelDATUMPLANES"] = ["swSelDATUMPLANES", "PLANE"],
            ["PLANE"] = ["PLANE", "swSelDATUMPLANES"],
            ["swSelFACES"] = ["swSelFACES", "FACE"],
            ["FACE"] = ["FACE", "swSelFACES"],
            ["swSelEDGES"] = ["swSelEDGES", "EDGE"],
            ["EDGE"] = ["EDGE", "swSelEDGES"],
            ["swSelVERTICES"] = ["swSelVERTICES", "VERTEX"],
            ["VERTEX"] = ["VERTEX", "swSelVERTICES"],
        };

    private sealed record EntityCandidate(
        int Index,
        IEntity Entity,
        SelectableEntityType EntityType,
        string? ComponentName,
        double[]? Box);

    private sealed record FeatureErrorInfo(int ErrorCode, bool IsWarning, SwCodeInfo CodeInfo);

    private sealed record FeatureNode(
        Feature Feature,
        int Index,
        string Name,
        string TypeName,
        bool IsSketch,
        bool HasChildren);

    private sealed record WhatsWrongFeatureInfo(
        Feature Feature,
        string Name,
        string TypeName,
        int ErrorCode,
        bool IsWarning,
        SwCodeInfo CodeInfo);

    private sealed record AssemblyComponentContext(
        IComponent2 Component,
        ComponentInstanceInfo Info);

    private readonly ISwConnectionManager _cm;

    public SelectionService(ISwConnectionManager cm)
    {
        _cm = cm ?? throw new ArgumentNullException(nameof(cm));
    }

    public SelectionResult SelectByName(string name, string selType, bool append = false, int mark = 0)
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        if (!append)
        {
            doc.ClearSelection2(true);
        }

        foreach (var candidateType in ExpandSelectionTypes(selType))
        {
            // SelectByID(name, type, x, y, z) — x/y/z are 0,0,0 for named geometry
            bool ok = doc.Extension.SelectByID2(name, candidateType, 0, 0, 0, append, mark, null, 0);
            if (ok)
            {
                string message = string.Equals(candidateType, selType, StringComparison.OrdinalIgnoreCase)
                    ? $"Selected '{name}'"
                    : $"Selected '{name}' using selection type '{candidateType}' (requested '{selType}')";
                return new SelectionResult(true, message);
            }
        }

        // Localized SolidWorks installs may rename the default planes.
        // For plane selections, retry by matching semantic plane kind (front/top/right)
        // against discovered reference planes from the active feature tree.
        if (IsPlaneSelection(selType))
        {
            var fallback = TrySelectLocalizedStandardPlane(doc, name, selType, append, mark);
            if (fallback != null)
            {
                return fallback;
            }
        }

        return new SelectionResult(false, $"Could not select '{name}' (type: {selType})");
    }

    public IReadOnlyList<SelectableEntityInfo> ListEntities(
        SelectableEntityType? entityType = null,
        string? componentName = null)
    {
        _cm.EnsureConnected();

        return EnumerateEntities(entityType, componentName)
            .Select(candidate => new SelectableEntityInfo(
                candidate.Index,
                candidate.EntityType,
                candidate.ComponentName,
                candidate.Box))
            .ToList()
            .AsReadOnly();
    }

    public IReadOnlyList<ReferencePlaneInfo> ListReferencePlanes()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        return EnumerateReferencePlanes(doc).ToList().AsReadOnly();
    }

    public SolidWorksContextInfo GetSolidWorksContext()
    {
        _cm.EnsureConnected();

        var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks connection is not available.");
        string language = SafeGetCurrentLanguage(swApp) ?? "unknown";
        var doc = swApp.IActiveDoc2;
        IReadOnlyList<ReferencePlaneInfo> planes = doc == null
            ? Array.Empty<ReferencePlaneInfo>()
            : EnumerateReferencePlanes(doc).ToList().AsReadOnly();

        return new SolidWorksContextInfo(language, planes);
    }

    public IReadOnlyList<FeatureTreeItemInfo> ListFeatureTree()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, "reading the FeatureManager tree");

        return EnumerateFeatureTree(doc)
            .Select(node => new FeatureTreeItemInfo(
                node.Index,
                node.Name,
                node.TypeName,
                node.IsSketch,
                node.HasChildren))
            .ToList()
            .AsReadOnly();
    }

    public ActiveFeatureManagerTreeResult TraverseActiveFeatureManagerTree()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, "reading the active FeatureManager tree");

        var featureManager = _cm.SwApp?.FeatureManager
            ?? throw new InvalidOperationException("FeatureManager is not available for the active document.");
        var root = GetFeatureTreeRootItem(featureManager)
            ?? throw new InvalidOperationException("Could not access the active FeatureManager tree root.");

        var nodes = new List<FeatureManagerTreeNodeInfo>();
        TraverseTreeNode(root, depth: 0, parentGraphPath: null, nodes, doc);

        return new ActiveFeatureManagerTreeResult(
            DocumentTitle: SafeGetDocumentTitle(doc) ?? "<untitled>",
            DocumentType: SafeGetDocumentType(doc),
            DocumentPath: NormalizePathOrNull(SafeGetDocumentPath(doc)),
            NodeCount: nodes.Count,
            Nodes: nodes.AsReadOnly());
    }

    public FeatureDiagnosticsResult GetFeatureDiagnostics()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, "reading feature diagnostics");

        var treeNodes = EnumerateFeatureTree(doc).ToList();
        var assemblyComponents = TryEnumerateAssemblyComponentContexts(doc);
        string? activeDocumentPath = NormalizePathOrNull(doc.GetPathName());
        var whatsWrongEntries = EnumerateWhatsWrongItems(doc).ToList();
        var whatsWrongItems = whatsWrongEntries
            .Select(entry => new WhatsWrongItemInfo(
                entry.Name,
                entry.TypeName,
                entry.ErrorCode,
                entry.IsWarning,
                entry.CodeInfo.Name,
                entry.CodeInfo.Description,
                CorrelateDiagnosticTargetContext(
                    entry.Feature,
                    entry.Name,
                    entry.TypeName,
                    activeDocumentPath,
                    assemblyComponents)))
            .ToList();
        var whatsWrongKeys = new HashSet<string>(
            whatsWrongItems.Select(item => BuildFeatureKey(item.Name, item.TypeName)),
            StringComparer.OrdinalIgnoreCase);

        var featureDiagnostics = treeNodes
            .Select(node =>
            {
                var error = GetFeatureErrorInfo(node.Feature);
                bool appearsInWhatsWrong = whatsWrongKeys.Contains(BuildFeatureKey(node.Name, node.TypeName));
                DiagnosticTargetContextInfo? targetContext = error.ErrorCode != 0 || appearsInWhatsWrong
                    ? CorrelateDiagnosticTargetContext(
                        node.Feature,
                        node.Name,
                        node.TypeName,
                        activeDocumentPath,
                        assemblyComponents)
                    : null;

                return new FeatureDiagnosticInfo(
                    node.Index,
                    node.Name,
                    node.TypeName,
                    node.IsSketch,
                    node.HasChildren,
                    HasIssue: error.ErrorCode != 0,
                    ErrorCode: error.ErrorCode,
                    IsWarning: error.IsWarning,
                    ErrorName: error.CodeInfo.Name,
                    ErrorDescription: error.CodeInfo.Description,
                    AppearsInWhatsWrong: appearsInWhatsWrong,
                    TargetContext: targetContext);
            })
            .ToList()
            .AsReadOnly();

        int warningCount = whatsWrongItems.Count(item => item.IsWarning);
        int errorCount = whatsWrongItems.Count - warningCount;
        var correlatedKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var correlatedIssues = new List<CorrelatedDiagnosticIssueInfo>();

        foreach (var item in featureDiagnostics.Where(item => item.TargetContext != null))
        {
            correlatedIssues.Add(new CorrelatedDiagnosticIssueInfo(
                Source: "feature_tree",
                Index: item.Index,
                Name: item.Name,
                TypeName: item.TypeName,
                ErrorCode: item.ErrorCode,
                IsWarning: item.IsWarning,
                ErrorName: item.ErrorName,
                ErrorDescription: item.ErrorDescription,
                AppearsInWhatsWrong: item.AppearsInWhatsWrong,
                TargetContext: item.TargetContext!));
            correlatedKeys.Add(BuildFeatureKey(item.Name, item.TypeName));
        }

        foreach (var item in whatsWrongItems.Where(item => item.TargetContext != null))
        {
            if (!correlatedKeys.Add(BuildFeatureKey(item.Name, item.TypeName)))
            {
                continue;
            }

            correlatedIssues.Add(new CorrelatedDiagnosticIssueInfo(
                Source: "whats_wrong",
                Index: null,
                Name: item.Name,
                TypeName: item.TypeName,
                ErrorCode: item.ErrorCode,
                IsWarning: item.IsWarning,
                ErrorName: item.ErrorName,
                ErrorDescription: item.ErrorDescription,
                AppearsInWhatsWrong: true,
                TargetContext: item.TargetContext!));
        }

        return new FeatureDiagnosticsResult(
            featureDiagnostics,
            whatsWrongItems.AsReadOnly(),
            errorCount,
            warningCount,
            correlatedIssues.AsReadOnly());
    }

    public EditStateInfo GetEditState()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        return GetEditState(doc);
    }

    public SelectionResult SelectEntity(
        SelectableEntityType entityType,
        int index,
        bool append = false,
        int mark = 0,
        string? componentName = null)
    {
        _cm.EnsureConnected();

        var candidate = EnumerateEntities(entityType, componentName)
            .FirstOrDefault(item => item.Index == index);

        if (candidate == null)
        {
            string scope = string.IsNullOrWhiteSpace(componentName)
                ? string.Empty
                : $" for component '{componentName}'";
            return new SelectionResult(false, $"Could not find {entityType} at index {index}{scope}");
        }

        var selectionManager = GetActiveModelDoc().ISelectionManager
            ?? throw new InvalidOperationException("No selection manager available.");

        if (!append)
        {
            GetActiveModelDoc().ClearSelection2(true);
        }

        var selectData = CreateSelectData(selectionManager, mark);

        bool ok = candidate.Entity.Select4(append, selectData);
        return ok
            ? new SelectionResult(
                true,
                $"Selected {entityType} at index {index}",
                candidate.EntityType,
                candidate.Index,
                candidate.ComponentName,
                candidate.Box)
            : new SelectionResult(
                false,
                $"Failed to select {entityType} at index {index}",
                candidate.EntityType,
                candidate.Index,
                candidate.ComponentName,
                candidate.Box);
    }

    public EntityMeasurementResult MeasureEntities(
        SelectableEntityType firstEntityType,
        int firstIndex,
        SelectableEntityType secondEntityType,
        int secondIndex,
        string? firstComponentName = null,
        string? secondComponentName = null,
        int arcOption = 1)
    {
        if (arcOption is < 0 or > 2)
        {
            throw new ArgumentOutOfRangeException(nameof(arcOption), "arcOption must be 0 (center), 1 (minimum), or 2 (maximum).");
        }

        _cm.EnsureConnected();

        var doc = GetActiveModelDoc();
        var first = ResolveEntityCandidate(firstEntityType, firstIndex, firstComponentName);
        var second = ResolveEntityCandidate(secondEntityType, secondIndex, secondComponentName);
        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("No selection manager available.");
        var extension = doc.Extension
            ?? throw new InvalidOperationException("No model extension available on the active document.");

        doc.ClearSelection2(true);
        try
        {
            if (!first.Entity.Select4(false, CreateSelectData(selectionManager, 0)))
            {
                throw new InvalidOperationException($"Failed to select the first entity ({firstEntityType} index {firstIndex}).");
            }

            if (!second.Entity.Select4(true, CreateSelectData(selectionManager, 0)))
            {
                throw new InvalidOperationException($"Failed to select the second entity ({secondEntityType} index {secondIndex}).");
            }

            var measure = extension.CreateMeasure()
                ?? throw new InvalidOperationException("SolidWorks did not create a measure tool.");
            measure.ArcOption = arcOption;

            if (!measure.Calculate(null))
            {
                throw new InvalidOperationException("SolidWorks could not measure the selected entities.");
            }

            return new EntityMeasurementResult(
                ToMeasuredEntityInfo(first),
                ToMeasuredEntityInfo(second),
                arcOption,
                NormalizeMeasureValue(measure.Distance),
                NormalizeMeasureValue(measure.NormalDistance),
                NormalizeMeasureValue(measure.CenterDistance),
                NormalizeMeasureValue(measure.Angle),
                NormalizeMeasureValue(measure.DeltaX),
                NormalizeMeasureValue(measure.DeltaY),
                NormalizeMeasureValue(measure.DeltaZ),
                NormalizeMeasureValue(measure.Projection),
                NormalizeMeasureValue(measure.X),
                NormalizeMeasureValue(measure.Y),
                NormalizeMeasureValue(measure.Z),
                measure.IsParallel,
                measure.IsPerpendicular,
                measure.IsIntersect);
        }
        finally
        {
            doc.ClearSelection2(true);
        }
    }

    public SelectionResult DeleteFeatureByName(string featureName)
    {
        if (string.IsNullOrWhiteSpace(featureName))
        {
            throw new ArgumentException("featureName must not be empty", nameof(featureName));
        }

        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, $"deleting feature '{featureName}'");
        var feature = EnumerateFeatureTree(doc)
            .FirstOrDefault(node => string.Equals(node.Name, featureName, StringComparison.OrdinalIgnoreCase));

        if (feature == null)
        {
            return new SelectionResult(false, $"Could not find feature '{featureName}' in the FeatureManager tree.");
        }

        return TryDeleteFeature(doc, feature.Feature)
            ? new SelectionResult(true, $"Deleted feature '{feature.Name}'.")
            : new SelectionResult(false, $"Failed to delete feature '{feature.Name}'.");
    }

    public DeleteFeaturesResult DeleteUnusedSketches()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, "deleting unused sketches");

        var deleted = new List<string>();
        var failed = new List<string>();
        var looseSketches = EnumerateFeatureTree(doc)
            .Where(node => node.IsSketch && !node.HasChildren)
            .OrderByDescending(node => node.Index)
            .ToList();

        foreach (var sketch in looseSketches)
        {
            if (TryDeleteFeature(doc, sketch.Feature))
            {
                deleted.Add(sketch.Name);
            }
            else
            {
                failed.Add(sketch.Name);
            }
        }

        return new DeleteFeaturesResult(deleted.Count, deleted.AsReadOnly(), failed.AsReadOnly());
    }

    public void ClearSelection()
    {
        _cm.EnsureConnected();
        GetActiveModelDoc().ClearSelection2(true);
    }

    // ── Helpers ───────────────────────────────────────────────────

    private IModelDoc2 GetActiveModelDoc()
    {
        return _cm.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document. Open or create a document first.");
    }

    private IEnumerable<EntityCandidate> EnumerateEntities(
        SelectableEntityType? entityType,
        string? componentName)
    {
        var all = EnumerateBodyContexts()
            .SelectMany(context => EnumerateEntitiesForBody(context.Body, context.ComponentName))
            .Where(candidate => entityType == null || candidate.EntityType == entityType)
            .Where(candidate => string.IsNullOrWhiteSpace(componentName)
                || string.Equals(candidate.ComponentName, componentName, StringComparison.OrdinalIgnoreCase))
            .ToList();

        for (int index = 0; index < all.Count; index++)
        {
            var candidate = all[index];
            yield return candidate with { Index = index };
        }
    }

    private EntityCandidate ResolveEntityCandidate(
        SelectableEntityType entityType,
        int index,
        string? componentName)
    {
        var candidate = EnumerateEntities(entityType, componentName)
            .FirstOrDefault(item => item.Index == index);

        if (candidate == null)
        {
            string scope = string.IsNullOrWhiteSpace(componentName)
                ? string.Empty
                : $" for component '{componentName}'";
            throw new InvalidOperationException($"Could not find {entityType} at index {index}{scope}.");
        }

        return candidate;
    }

    private static MeasuredEntityInfo ToMeasuredEntityInfo(EntityCandidate candidate)
        => new(candidate.EntityType, candidate.Index, candidate.ComponentName, candidate.Box);

    private static IEnumerable<ReferencePlaneInfo> EnumerateReferencePlanes(IModelDoc2 doc)
    {
        int index = 0;
        for (var feature = doc.FirstFeature() as Feature; feature != null; feature = feature.GetNextFeature() as Feature)
        {
            string? typeName = SafeGetFeatureTypeName(feature);
            if (!string.Equals(typeName, "RefPlane", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var (selectionName, selectionType) = SafeGetSelectionIdentity(feature);
            string name = SafeGetFeatureName(feature)
                ?? selectionName
                ?? $"RefPlane{index + 1}";

            yield return new ReferencePlaneInfo(
                index,
                name,
                selectionName ?? name,
                selectionType ?? "PLANE");

            index++;
        }
    }

    private static IEnumerable<FeatureNode> EnumerateFeatureTree(IModelDoc2 doc)
    {
        int index = 0;
        for (var feature = doc.FirstFeature() as Feature; feature != null; feature = feature.GetNextFeature() as Feature)
        {
            string typeName = SafeGetFeatureTypeName(feature) ?? "Unknown";
            string name = SafeGetFeatureName(feature)
                ?? $"Feature{index + 1}";

            yield return new FeatureNode(
                feature,
                index,
                name,
                typeName,
                IsSketchLike(typeName),
                HasChildFeatures(feature));

            index++;
        }
    }

    private static ITreeControlItem? GetFeatureTreeRootItem(IFeatureManager featureManager)
    {
        try
        {
            return featureManager.GetFeatureTreeRootItem2((int)swFeatMgrPane_e.swFeatMgrPaneBottom) as ITreeControlItem
                ?? featureManager.GetFeatureTreeRootItem2((int)swFeatMgrPane_e.swFeatMgrPaneTop) as ITreeControlItem
                ?? featureManager.GetFeatureTreeRootItem() as ITreeControlItem;
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

    private static void TraverseTreeNode(
        ITreeControlItem node,
        int depth,
        string? parentGraphPath,
        ICollection<FeatureManagerTreeNodeInfo> nodes,
        IModelDoc2 activeDocument)
    {
        int siblingIndex = 0;
        for (var current = node; current != null; current = SafeGetNextTreeNode(current))
        {
            int nodeIndex = nodes.Count;
            string text = SafeGetTreeNodeText(current) ?? $"TreeNode{nodeIndex}";
            string graphPath = BuildTreeGraphPath(parentGraphPath, siblingIndex, text);
            object? treeObject = SafeGetTreeNodeObject(current);
            int objectType = SafeGetTreeNodeObjectType(current);
            string? objectKind = DescribeTreeNodeObject(treeObject);
            string? featureName = null;
            string? featureTypeName = null;
            bool isSketch = false;
            string? componentName = null;
            string? componentPath = null;
            string? documentTitle = SafeGetDocumentTitle(activeDocument);
            string? documentPath = NormalizePathOrNull(SafeGetDocumentPath(activeDocument));

            if (treeObject is Feature feature)
            {
                featureName = SafeGetFeatureName(feature);
                featureTypeName = SafeGetFeatureTypeName(feature);
                isSketch = IsSketchLike(featureTypeName);
            }
            else if (treeObject is IComponent2 component)
            {
                componentName = SafeGetComponentName(component);
                componentPath = NormalizePathOrNull(SafeGetComponentPath(component));
            }
            else if (treeObject is IModelDoc2 modelDoc)
            {
                documentTitle = SafeGetDocumentTitle(modelDoc);
                documentPath = NormalizePathOrNull(SafeGetDocumentPath(modelDoc));
            }

            nodes.Add(new FeatureManagerTreeNodeInfo(
                NodeIndex: nodeIndex,
                Depth: depth,
                Text: text,
                ObjectType: objectType,
                ObjectKind: objectKind,
                IsRoot: SafeIsTreeRoot(current),
                IsExpanded: SafeIsTreeExpanded(current),
                GraphPath: graphPath,
                ParentGraphPath: parentGraphPath,
                FeatureName: featureName,
                FeatureTypeName: featureTypeName,
                IsSketch: isSketch,
                ComponentName: componentName,
                ComponentPath: componentPath,
                DocumentTitle: documentTitle,
                DocumentPath: documentPath));

            var child = SafeGetFirstTreeChild(current);
            if (child != null)
            {
                TraverseTreeNode(child, depth + 1, graphPath, nodes, activeDocument);
            }

            siblingIndex++;
        }
    }

    private static string BuildTreeGraphPath(string? parentGraphPath, int siblingIndex, string text)
    {
        string segment = $"{siblingIndex}:{text}";
        return string.IsNullOrWhiteSpace(parentGraphPath)
            ? segment
            : $"{parentGraphPath}/{segment}";
    }

    private static ITreeControlItem? SafeGetFirstTreeChild(ITreeControlItem node)
    {
        try
        {
            return node.GetFirstChild() as ITreeControlItem;
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

    private static ITreeControlItem? SafeGetNextTreeNode(ITreeControlItem node)
    {
        try
        {
            return node.GetNext() as ITreeControlItem;
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

    private static string? SafeGetTreeNodeText(ITreeControlItem node)
    {
        try
        {
            return node.Text;
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

    private static int SafeGetTreeNodeObjectType(ITreeControlItem node)
    {
        try
        {
            return node.ObjectType;
        }
        catch (COMException)
        {
            return 0;
        }
        catch (TargetInvocationException)
        {
            return 0;
        }
    }

    private static object? SafeGetTreeNodeObject(ITreeControlItem node)
    {
        try
        {
            return node.Object;
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

    private static bool SafeIsTreeExpanded(ITreeControlItem node)
    {
        try
        {
            return node.Expanded;
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }
    }

    private static bool SafeIsTreeRoot(ITreeControlItem node)
    {
        try
        {
            return node.IsRoot;
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }
    }

    private static string? DescribeTreeNodeObject(object? treeObject)
    {
        return treeObject switch
        {
            Feature => "feature",
            IComponent2 => "component",
            IModelDoc2 => "document",
            _ when treeObject == null => null,
            _ => treeObject.GetType().Name
        };
    }

    private static IEnumerable<WhatsWrongFeatureInfo> EnumerateWhatsWrongItems(IModelDoc2 doc)
    {
        var extension = doc.Extension;
        if (extension == null)
        {
            yield break;
        }

        object featuresRaw;
        object errorCodesRaw;
        object warningsRaw;
        if (!extension.GetWhatsWrong(out featuresRaw, out errorCodesRaw, out warningsRaw))
        {
            yield break;
        }

        var features = (featuresRaw as object[] ?? Array.Empty<object>()).OfType<Feature>().ToArray();
        var errorCodes = ToIntArray(errorCodesRaw);
        var warnings = ToBoolArray(warningsRaw);
        int count = new[] { features.Length, errorCodes.Length, warnings.Length }.Min();
        for (int index = 0; index < count; index++)
        {
            var feature = features[index];
            int errorCode = errorCodes[index];
            var codeInfo = SolidWorksApiErrorFactory.CreateFeatureErrorCodeInfo(errorCode);
            yield return new WhatsWrongFeatureInfo(
                feature,
                Name: SafeGetFeatureName(feature) ?? $"Feature{index + 1}",
                TypeName: SafeGetFeatureTypeName(feature) ?? "Unknown",
                ErrorCode: errorCode,
                IsWarning: warnings[index],
                CodeInfo: codeInfo);
        }
    }

    private static IReadOnlyList<AssemblyComponentContext>? TryEnumerateAssemblyComponentContexts(IModelDoc2 doc)
    {
        if (doc is not IAssemblyDoc assembly)
        {
            return null;
        }

        var raw = assembly.GetComponents(true) as object[] ?? Array.Empty<object>();
        var results = new List<AssemblyComponentContext>();
        foreach (var component in raw.OfType<IComponent2>())
        {
            TraverseAssemblyComponent(component, component.Name2 ?? "Component", depth: 0, results);
        }

        return results.AsReadOnly();
    }

    private static void TraverseAssemblyComponent(
        IComponent2 component,
        string hierarchyPath,
        int depth,
        ICollection<AssemblyComponentContext> results)
    {
        string name = component.Name2 ?? $"Component{depth}";
        string path = component.GetPathName() ?? string.Empty;
        results.Add(new AssemblyComponentContext(component, new ComponentInstanceInfo(name, path, hierarchyPath, depth)));

        var children = component.GetChildren() as object[] ?? Array.Empty<object>();
        foreach (var child in children.OfType<IComponent2>())
        {
            string childName = child.Name2 ?? "Component";
            TraverseAssemblyComponent(child, $"{hierarchyPath}/{childName}", depth + 1, results);
        }
    }

    private static DiagnosticTargetContextInfo? CorrelateDiagnosticTargetContext(
        Feature feature,
        string name,
        string typeName,
        string? activeDocumentPath,
        IReadOnlyList<AssemblyComponentContext>? assemblyComponents)
    {
        if (assemblyComponents == null)
        {
            return null;
        }

        if (TryResolveExactComponentContextFromFeature(feature, assemblyComponents, out var exactFeatureMatch))
        {
            return CreateExactComponentContext(
                exactFeatureMatch.Info,
                assemblyComponents,
                activeDocumentPath,
                "Resolved via the feature's bound component.");
        }

        var exactMatches = FindExactDiagnosticComponentMatches(name, assemblyComponents);
        if (exactMatches.Count == 1)
        {
            return CreateExactComponentContext(
                exactMatches[0].Info,
                assemblyComponents,
                activeDocumentPath,
                "Resolved via an exact component-instance name match.");
        }

        if (exactMatches.Count > 1)
        {
            return TryCreateAmbiguousSharedSourceContext(
                exactMatches,
                activeDocumentPath,
                "Multiple component instances matched the diagnostic name.",
                unresolvedReason: "The diagnostic name matched multiple component instances that do not collapse to one exact target.");
        }

        var heuristicMatches = FindHeuristicDiagnosticComponentMatches(name, assemblyComponents);
        if (heuristicMatches.Count == 1)
        {
            return CreateExactComponentContext(
                heuristicMatches[0].Info,
                assemblyComponents,
                activeDocumentPath,
                "Resolved via source-name and component-name heuristics.");
        }

        if (heuristicMatches.Count > 1)
        {
            return TryCreateAmbiguousSharedSourceContext(
                heuristicMatches,
                activeDocumentPath,
                "Multiple reused component instances matched the diagnostic heuristics.",
                unresolvedReason: "The diagnostic heuristics matched multiple component instances without one exact target.");
        }

        if (IsClearlyAssemblyLevelDiagnostic(typeName))
        {
            return new DiagnosticTargetContextInfo(
                ScopeType: "assembly_level",
                IsExact: true,
                IsAmbiguous: false,
                DocumentPath: activeDocumentPath,
                HierarchyPath: null,
                ComponentName: null,
                SourceFilePath: null,
                OwningAssemblyHierarchyPath: null,
                OwningAssemblyFilePath: activeDocumentPath,
                SourceFileReuseCount: 0,
                Reason: $"The diagnostic type '{typeName}' is treated as assembly-level scope.",
                MatchingInstances: Array.Empty<ComponentInstanceInfo>());
        }

        return new DiagnosticTargetContextInfo(
            ScopeType: "unresolved_target_context",
            IsExact: false,
            IsAmbiguous: false,
            DocumentPath: activeDocumentPath,
            HierarchyPath: null,
            ComponentName: null,
            SourceFilePath: null,
            OwningAssemblyHierarchyPath: null,
            OwningAssemblyFilePath: activeDocumentPath,
            SourceFileReuseCount: 0,
            Reason: $"Could not correlate diagnostic '{name}' ({typeName}) to an exact component instance or a recognized assembly-level target.",
            MatchingInstances: Array.Empty<ComponentInstanceInfo>());
    }

    private static bool TryResolveExactComponentContextFromFeature(
        Feature feature,
        IReadOnlyList<AssemblyComponentContext> assemblyComponents,
        out AssemblyComponentContext match)
    {
        match = default!;

        object? specificFeature;
        try
        {
            specificFeature = feature.GetSpecificFeature2();
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }

        if (specificFeature is not IComponent2 component)
        {
            return false;
        }

        var matches = assemblyComponents
            .Where(candidate => IsSameComponentInstance(candidate.Component, component))
            .ToList();
        if (matches.Count != 1)
        {
            return false;
        }

        match = matches[0];
        return true;
    }

    private static IReadOnlyList<AssemblyComponentContext> FindExactDiagnosticComponentMatches(
        string diagnosticName,
        IReadOnlyList<AssemblyComponentContext> assemblyComponents)
    {
        return assemblyComponents
            .Where(candidate =>
                string.Equals(candidate.Info.HierarchyPath, diagnosticName, StringComparison.OrdinalIgnoreCase)
                || string.Equals(candidate.Info.Name, diagnosticName, StringComparison.OrdinalIgnoreCase))
            .ToList()
            .AsReadOnly();
    }

    public IReadOnlyList<ModelHealthSensorInfo> ListModelHealthSensors()
    {
        _cm.EnsureConnected();
        var doc = GetActiveModelDoc();
        EnsureNotEditing(doc, "reading model health sensors");

        string? documentPath = NormalizePathOrNull(doc.GetPathName());
        string documentReference = documentPath
            ?? SafeGetDocumentTitle(doc)
            ?? "ActiveDocument";

        return EnumerateFeatureTree(doc)
            .Select(node => TryCreateModelHealthSensorInfo(node, documentPath, documentReference))
            .Where(static sensor => sensor != null)
            .Cast<ModelHealthSensorInfo>()
            .ToList()
            .AsReadOnly();
    }

    private static IReadOnlyList<AssemblyComponentContext> FindHeuristicDiagnosticComponentMatches(
        string diagnosticName,
        IReadOnlyList<AssemblyComponentContext> assemblyComponents)
    {
        var tokens = BuildDiagnosticLookupTokens(diagnosticName);
        if (tokens.Count == 0)
        {
            return Array.Empty<AssemblyComponentContext>();
        }

        return assemblyComponents
            .Where(candidate =>
            {
                string normalizedName = NormalizeLookupToken(candidate.Info.Name);
                string normalizedNameWithoutInstance = NormalizeLookupToken(TrimInstanceSuffix(candidate.Info.Name));
                string normalizedSourceStem = NormalizeLookupToken(Path.GetFileNameWithoutExtension(candidate.Info.Path));
                return tokens.Contains(normalizedName)
                    || tokens.Contains(normalizedNameWithoutInstance)
                    || tokens.Contains(normalizedSourceStem);
            })
            .ToList()
            .AsReadOnly();
    }

    private static HashSet<string> BuildDiagnosticLookupTokens(string? diagnosticName)
    {
        var tokens = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(diagnosticName))
        {
            return tokens;
        }

        string trimmed = diagnosticName.Trim();
        AddLookupToken(tokens, trimmed);
        AddLookupToken(tokens, TrimInstanceSuffix(trimmed));
        AddLookupToken(tokens, Path.GetFileNameWithoutExtension(trimmed));
        return tokens;
    }

    private static void AddLookupToken(ISet<string> tokens, string? value)
    {
        string normalized = NormalizeLookupToken(value);
        if (!string.IsNullOrEmpty(normalized))
        {
            tokens.Add(normalized);
        }
    }

    private static string NormalizeLookupToken(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var builder = new System.Text.StringBuilder(value.Length);
        foreach (char current in value)
        {
            if (char.IsLetterOrDigit(current))
            {
                builder.Append(char.ToLowerInvariant(current));
            }
        }

        return builder.ToString();
    }

    private static string TrimInstanceSuffix(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        string trimmed = value.Trim();
        int dashIndex = trimmed.LastIndexOf('-');
        if (dashIndex <= 0 || dashIndex + 1 >= trimmed.Length)
        {
            return trimmed;
        }

        for (int index = dashIndex + 1; index < trimmed.Length; index++)
        {
            if (!char.IsDigit(trimmed[index]))
            {
                return trimmed;
            }
        }

        return trimmed[..dashIndex];
    }

    private static DiagnosticTargetContextInfo CreateExactComponentContext(
        ComponentInstanceInfo match,
        IReadOnlyList<AssemblyComponentContext> assemblyComponents,
        string? activeDocumentPath,
        string reason)
    {
        string? owningAssemblyHierarchyPath = GetParentHierarchyPath(match.HierarchyPath);
        string? owningAssemblyFilePath = ResolveOwningAssemblyFilePath(
            assemblyComponents,
            owningAssemblyHierarchyPath,
            activeDocumentPath);

        return new DiagnosticTargetContextInfo(
            ScopeType: "component_instance",
            IsExact: true,
            IsAmbiguous: false,
            DocumentPath: activeDocumentPath,
            HierarchyPath: match.HierarchyPath,
            ComponentName: match.Name,
            SourceFilePath: NormalizePathOrNull(match.Path),
            OwningAssemblyHierarchyPath: owningAssemblyHierarchyPath,
            OwningAssemblyFilePath: owningAssemblyFilePath,
            SourceFileReuseCount: CountSourceFileReuse(assemblyComponents, match.Path),
            Reason: reason,
            MatchingInstances: new[] { match });
    }

    private static DiagnosticTargetContextInfo TryCreateAmbiguousSharedSourceContext(
        IReadOnlyList<AssemblyComponentContext> matches,
        string? activeDocumentPath,
        string ambiguousReason,
        string unresolvedReason)
    {
        var matchingInstances = matches
            .Select(match => match.Info)
            .DistinctBy(match => match.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToList()
            .AsReadOnly();

        if (matchingInstances.Count == 0)
        {
            return new DiagnosticTargetContextInfo(
                ScopeType: "unresolved_target_context",
                IsExact: false,
                IsAmbiguous: false,
                DocumentPath: activeDocumentPath,
                HierarchyPath: null,
                ComponentName: null,
                SourceFilePath: null,
                OwningAssemblyHierarchyPath: null,
                OwningAssemblyFilePath: activeDocumentPath,
                SourceFileReuseCount: 0,
                Reason: unresolvedReason,
                MatchingInstances: Array.Empty<ComponentInstanceInfo>());
        }

        string? sharedSourcePath = NormalizePathOrNull(matchingInstances[0].Path);
        bool sameSourcePath = sharedSourcePath != null
            && matchingInstances.All(instance => PathsEqual(instance.Path, sharedSourcePath));

        if (sameSourcePath)
        {
            return new DiagnosticTargetContextInfo(
                ScopeType: "shared_source_scope",
                IsExact: false,
                IsAmbiguous: true,
                DocumentPath: activeDocumentPath,
                HierarchyPath: null,
                ComponentName: null,
                SourceFilePath: sharedSourcePath,
                OwningAssemblyHierarchyPath: null,
                OwningAssemblyFilePath: activeDocumentPath,
                SourceFileReuseCount: matchingInstances.Count,
                Reason: ambiguousReason,
                MatchingInstances: matchingInstances);
        }

        return new DiagnosticTargetContextInfo(
            ScopeType: "unresolved_target_context",
            IsExact: false,
            IsAmbiguous: false,
            DocumentPath: activeDocumentPath,
            HierarchyPath: null,
            ComponentName: null,
            SourceFilePath: null,
            OwningAssemblyHierarchyPath: null,
            OwningAssemblyFilePath: activeDocumentPath,
            SourceFileReuseCount: 0,
            Reason: unresolvedReason,
            MatchingInstances: matchingInstances);
    }

    private static bool IsClearlyAssemblyLevelDiagnostic(string? typeName)
    {
        if (string.IsNullOrWhiteSpace(typeName))
        {
            return false;
        }

        return typeName.Contains("Mate", StringComparison.OrdinalIgnoreCase)
            || typeName.EndsWith("Folder", StringComparison.OrdinalIgnoreCase)
            || string.Equals(typeName, "MateGroup", StringComparison.OrdinalIgnoreCase);
    }

    private static int CountSourceFileReuse(IReadOnlyList<AssemblyComponentContext> assemblyComponents, string? sourceFilePath)
    {
        string? normalizedPath = NormalizePathOrNull(sourceFilePath);
        if (normalizedPath == null)
        {
            return 0;
        }

        return assemblyComponents.Count(component => PathsEqual(component.Info.Path, normalizedPath));
    }

    private static string? ResolveOwningAssemblyFilePath(
        IReadOnlyList<AssemblyComponentContext> assemblyComponents,
        string? owningAssemblyHierarchyPath,
        string? activeAssemblyPath)
    {
        if (owningAssemblyHierarchyPath == null)
        {
            return activeAssemblyPath;
        }

        string? candidateHierarchyPath = owningAssemblyHierarchyPath;
        while (candidateHierarchyPath != null)
        {
            string? candidatePath = assemblyComponents
                .FirstOrDefault(component => string.Equals(component.Info.HierarchyPath, candidateHierarchyPath, StringComparison.OrdinalIgnoreCase))
                ?.Info.Path;
            if (!string.IsNullOrWhiteSpace(candidatePath))
            {
                return NormalizePathOrNull(candidatePath);
            }

            candidateHierarchyPath = GetParentHierarchyPath(candidateHierarchyPath);
        }

        return activeAssemblyPath;
    }

    private static string? GetParentHierarchyPath(string? hierarchyPath)
    {
        if (string.IsNullOrWhiteSpace(hierarchyPath))
        {
            return null;
        }

        int separatorIndex = hierarchyPath.LastIndexOf('/');
        return separatorIndex <= 0 ? null : hierarchyPath[..separatorIndex];
    }

    private static bool IsSameComponentInstance(IComponent2 left, IComponent2 right)
    {
        return string.Equals(left.Name2, right.Name2, StringComparison.OrdinalIgnoreCase)
            && PathsEqual(left.GetPathName(), right.GetPathName());
    }

    private static string? NormalizePathOrNull(string? path)
    {
        return string.IsNullOrWhiteSpace(path)
            ? null
            : Path.GetFullPath(path);
    }

    private static bool PathsEqual(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
        {
            return false;
        }

        return string.Equals(Path.GetFullPath(left), Path.GetFullPath(right), StringComparison.OrdinalIgnoreCase);
    }

    private static IEnumerable<string> ExpandSelectionTypes(string selType)
    {
        if (SelectionTypeAliases.TryGetValue(selType, out var aliases))
        {
            return aliases;
        }

        return [selType];
    }

    private static FeatureErrorInfo GetFeatureErrorInfo(Feature feature)
    {
        bool isWarning;
        int errorCode = feature.GetErrorCode2(out isWarning);
        return new FeatureErrorInfo(errorCode, isWarning, SolidWorksApiErrorFactory.CreateFeatureErrorCodeInfo(errorCode));
    }

    private static string BuildFeatureKey(string name, string typeName)
        => string.Concat(name, "||", typeName);

    private static int[] ToIntArray(object? raw)
    {
        return raw switch
        {
            null => Array.Empty<int>(),
            int[] ints => ints,
            object[] objects => objects.Select(ToInt).ToArray(),
            _ => Array.Empty<int>(),
        };
    }

    private static int ToInt(object? value)
    {
        return value switch
        {
            null => 0,
            int intValue => intValue,
            short shortValue => shortValue,
            long longValue => unchecked((int)longValue),
            _ => Convert.ToInt32(value),
        };
    }

    private static bool[] ToBoolArray(object? raw)
    {
        return raw switch
        {
            null => Array.Empty<bool>(),
            bool[] bools => bools,
            object[] objects => objects.Select(ToBool).ToArray(),
            _ => Array.Empty<bool>(),
        };
    }

    private static bool ToBool(object? value)
    {
        return value switch
        {
            null => false,
            bool boolValue => boolValue,
            short shortValue => shortValue != 0,
            int intValue => intValue != 0,
            _ => Convert.ToBoolean(value),
        };
    }

    private static bool IsPlaneSelection(string selType)
        => ExpandSelectionTypes(selType)
            .Any(type => string.Equals(type, "PLANE", StringComparison.OrdinalIgnoreCase)
                || string.Equals(type, "swSelDATUMPLANES", StringComparison.OrdinalIgnoreCase));

    private static SelectionResult? TrySelectLocalizedStandardPlane(
        IModelDoc2 doc,
        string requestedName,
        string requestedType,
        bool append,
        int mark)
    {
        var requestedKind = GetStandardPlaneKind(requestedName);
        if (requestedKind == StandardPlaneKind.Unknown)
        {
            return null;
        }

        var planes = EnumerateReferencePlanes(doc).ToList();
        var plane = planes.FirstOrDefault(candidate =>
        {
            var planeKind = GetStandardPlaneKind(candidate.Name);
            if (planeKind == StandardPlaneKind.Unknown)
            {
                planeKind = GetStandardPlaneKind(candidate.SelectionName);
            }

            return planeKind == requestedKind;
        });

        if (plane == null)
        {
            return null;
        }

        var candidateTypes = ExpandSelectionTypes(requestedType)
            .Concat(ExpandSelectionTypes(plane.SelectionType))
            .Distinct(StringComparer.OrdinalIgnoreCase);

        foreach (var candidateType in candidateTypes)
        {
            bool ok = doc.Extension.SelectByID2(plane.SelectionName, candidateType, 0, 0, 0, append, mark, null, 0);
            if (ok)
            {
                return new SelectionResult(
                    true,
                    $"Selected '{plane.SelectionName}' via localized fallback for '{requestedName}' (type '{candidateType}')");
            }
        }

        return null;
    }

    private static StandardPlaneKind GetStandardPlaneKind(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return StandardPlaneKind.Unknown;
        }

        var text = value.Trim().ToLowerInvariant();

        if (text.Contains("front") || text.Contains("前视") || text.Contains("前基准") || text.Contains("前平面"))
        {
            return StandardPlaneKind.Front;
        }

        if (text.Contains("top") || text.Contains("上视") || text.Contains("上基准") || text.Contains("上平面"))
        {
            return StandardPlaneKind.Top;
        }

        if (text.Contains("right") || text.Contains("右视") || text.Contains("右基准") || text.Contains("右平面"))
        {
            return StandardPlaneKind.Right;
        }

        return StandardPlaneKind.Unknown;
    }

    private IEnumerable<(IBody2 Body, string? ComponentName)> EnumerateBodyContexts()
    {
        var doc = GetActiveModelDoc();

        if (doc is IPartDoc part)
        {
            foreach (var body in GetBodies(part))
            {
                yield return (body, null);
            }

            yield break;
        }

        if (doc is IAssemblyDoc assembly)
        {
            var components = (object[]?)assembly.GetComponents(true) ?? Array.Empty<object>();
            foreach (var component in EnumerateAssemblyComponentsRecursive(components.OfType<IComponent2>()))
            {
                foreach (var body in GetBodies(component))
                {
                    yield return (body, component.Name2);
                }
            }

            yield break;
        }

        throw new InvalidOperationException("Topology listing is only supported for part and assembly documents.");
    }

    private static IEnumerable<EntityCandidate> EnumerateEntitiesForBody(IBody2 body, string? componentName)
    {
        foreach (var face in ((object[]?)body.GetFaces() ?? Array.Empty<object>()).OfType<IFace2>())
        {
            yield return new EntityCandidate(-1, (IEntity)face, SelectableEntityType.Face, componentName, GetBox(face));
        }

        foreach (var edge in ((object[]?)body.GetEdges() ?? Array.Empty<object>()).OfType<IEdge>())
        {
            yield return new EntityCandidate(-1, (IEntity)edge, SelectableEntityType.Edge, componentName, GetBox(edge));
        }

        foreach (var vertex in ((object[]?)body.GetVertices() ?? Array.Empty<object>()).OfType<IVertex>())
        {
            yield return new EntityCandidate(-1, (IEntity)vertex, SelectableEntityType.Vertex, componentName, GetBox(vertex));
        }
    }

    private static IEnumerable<IComponent2> EnumerateAssemblyComponentsRecursive(IEnumerable<IComponent2> components)
    {
        foreach (var component in components)
        {
            yield return component;

            var children = (object[]?)component.GetChildren() ?? Array.Empty<object>();
            foreach (var child in EnumerateAssemblyComponentsRecursive(children.OfType<IComponent2>()))
            {
                yield return child;
            }
        }
    }

    private static IEnumerable<IBody2> GetBodies(IPartDoc part)
    {
        return ((object[]?)part.GetBodies2((int)swBodyType_e.swSolidBody, true) ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    private static IEnumerable<IBody2> GetBodies(IComponent2 component)
    {
        return (component.GetBodies3((int)swBodyType_e.swSolidBody, out _) as object[] ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    /// <summary>Recursively collect bodies from a component and all its child components.</summary>
    private static IEnumerable<IBody2> GetBodiesDeep(IComponent2 component)
    {
        foreach (var body in GetBodies(component))
            yield return body;
        var children = (object[]?)component.GetChildren() ?? [];
        foreach (var child in children.OfType<IComponent2>())
            foreach (var body in GetBodiesDeep(child))
                yield return body;
    }

    private static IEnumerable<(IBody2 Body, IComponent2 Component)> GetBodyContextsDeep(IComponent2 component)
    {
        foreach (var body in GetBodies(component))
            yield return (body, component);

        var children = (object[]?)component.GetChildren() ?? [];
        foreach (var child in children.OfType<IComponent2>())
            foreach (var context in GetBodyContextsDeep(child))
                yield return context;
    }

    private static double[]? GetBox(IFace2 face)
        => ToDoubleArray(face.GetBox());

    private static double[]? GetBox(IEdge edge)
    {
        var start = ToDoubleArray((edge.GetStartVertex() as IVertex)?.GetPoint());
        var end = ToDoubleArray((edge.GetEndVertex() as IVertex)?.GetPoint());

        if (start == null && end == null)
        {
            return null;
        }

        var first = start ?? end!;
        var second = end ?? first;

        if (first.Length < 3 || second.Length < 3)
        {
            return first;
        }

        return
        [
            Math.Min(first[0], second[0]),
            Math.Min(first[1], second[1]),
            Math.Min(first[2], second[2]),
            Math.Max(first[0], second[0]),
            Math.Max(first[1], second[1]),
            Math.Max(first[2], second[2]),
        ];
    }

    private static double[]? GetBox(IVertex vertex)
    {
        var point = ToDoubleArray(vertex.GetPoint());
        if (point == null || point.Length < 3)
        {
            return point;
        }

        return [point[0], point[1], point[2], point[0], point[1], point[2]];
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

    private static byte[]? ToByteArray(object? raw)
    {
        return raw switch
        {
            null => null,
            byte[] bytes => bytes,
            object[] objects => objects
                .Select(value =>
                {
                    try { return (byte?)Convert.ToByte(value, CultureInfo.InvariantCulture); }
                    catch { return null; }
                })
                .Where(value => value.HasValue)
                .Select(value => value!.Value)
                .ToArray(),
            _ => null,
        };
    }

    private static double? NormalizeMeasureValue(double value)
        => value == -1 ? null : value;

    private static bool IsSketchLike(string? typeName)
    {
        if (string.IsNullOrWhiteSpace(typeName))
        {
            return false;
        }

        return string.Equals(typeName, "ProfileFeature", StringComparison.OrdinalIgnoreCase)
            || string.Equals(typeName, "3DProfileFeature", StringComparison.OrdinalIgnoreCase);
    }

    private static bool HasChildFeatures(Feature feature)
    {
        try
        {
            return (feature.GetChildren() as object[] ?? Array.Empty<object>()).Length > 0;
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }
    }

    private static bool HasSubFeatures(Feature feature)
    {
        try
        {
            return feature.GetFirstSubFeature() is Feature;
        }
        catch (COMException)
        {
            return false;
        }
        catch (TargetInvocationException)
        {
            return false;
        }
    }

    private static bool TryDeleteFeature(IModelDoc2 doc, Feature feature)
    {
        try
        {
            doc.ClearSelection2(true);
            if (!feature.Select2(false, -1))
            {
                return false;
            }

            bool deleted = doc.Extension.DeleteSelection2(0);
            doc.ClearSelection2(true);
            return deleted;
        }
        catch (COMException)
        {
            doc.ClearSelection2(true);
            return false;
        }
        catch (TargetInvocationException)
        {
            doc.ClearSelection2(true);
            return false;
        }
    }

    private static EditStateInfo GetEditState(IModelDoc2 doc)
    {
        if (doc.GetActiveSketch2() != null)
        {
            return new EditStateInfo(
                IsEditing: true,
                EditMode: "sketch",
                CanReadFeatureTree: false,
                CanDeleteFeatures: false);
        }

        return new EditStateInfo(
            IsEditing: false,
            EditMode: "none",
            CanReadFeatureTree: true,
            CanDeleteFeatures: true);
    }

    private static void EnsureNotEditing(IModelDoc2 doc, string operation)
    {
        var state = GetEditState(doc);
        if (!state.IsEditing)
        {
            return;
        }

        throw new InvalidOperationException($"Finish the active {state.EditMode} before {operation}.");
    }

    private static SelectData CreateSelectData(ISelectionMgr selectionManager, int mark)
    {
        var selectData = selectionManager.CreateSelectData()
            ?? throw new InvalidOperationException("Could not create selection data.");

        var markProperty = selectData.GetType().GetProperty("Mark", BindingFlags.Instance | BindingFlags.Public);
        if (markProperty?.CanWrite == true)
        {
            markProperty.SetValue(selectData, mark);
        }

        return selectData;
    }

    private static string? SafeGetCurrentLanguage(ISldWorksApp swApp)
    {
        try
        {
            return swApp.GetCurrentLanguage();
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
        catch (TargetInvocationException)
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
        catch (TargetInvocationException)
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
        catch (TargetInvocationException)
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
        catch (TargetInvocationException)
        {
            return null;
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
        catch (TargetInvocationException)
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
        catch (TargetInvocationException)
        {
            return null;
        }
    }

    private static int SafeGetDocumentType(IModelDoc2 doc)
    {
        try
        {
            return doc.GetType();
        }
        catch (COMException)
        {
            return 0;
        }
        catch (TargetInvocationException)
        {
            return 0;
        }
    }

    private static (string? SelectionName, string? SelectionType) SafeGetSelectionIdentity(Feature feature)
    {
        try
        {
            string selectionType;
            string selectionName = feature.GetNameForSelection(out selectionType);
            return (selectionName, selectionType);
        }
        catch (COMException)
        {
            return (null, null);
        }
        catch (TargetInvocationException)
        {
            return (null, null);
        }
    }

    private static ModelHealthSensorInfo? TryCreateModelHealthSensorInfo(
        FeatureNode node,
        string? documentPath,
        string documentReference)
    {
        var sensor = TryGetFeatureSensor(node.Feature);
        return sensor == null
            ? null
            : CreateModelHealthSensorInfo(node, sensor, documentPath, documentReference);
    }

    private static ISensor? TryGetFeatureSensor(Feature feature)
    {
        object? specificFeature = null;

        try
        {
            specificFeature = feature.GetSpecificFeature2();
        }
        catch (COMException)
        {
            // Fall through to the legacy accessor.
        }
        catch (TargetInvocationException)
        {
            // Fall through to the legacy accessor.
        }

        if (specificFeature is ISensor directSensor)
        {
            return directSensor;
        }

        try
        {
            specificFeature = feature.GetSpecificFeature();
        }
        catch (COMException)
        {
            return null;
        }
        catch (TargetInvocationException)
        {
            return null;
        }

        return specificFeature as ISensor;
    }

    private static ModelHealthSensorInfo CreateModelHealthSensorInfo(
        FeatureNode node,
        ISensor sensor,
        string? documentPath,
        string documentReference)
    {
        var failures = new List<string>();
        int sensorTypeCode = TryReadSensorProperty(sensor, static s => s.SensorType, nameof(ISensor.SensorType), failures, fallbackValue: -1);
        bool alertEnabled = TryReadSensorProperty(sensor, static s => s.SensorAlertEnabled, nameof(ISensor.SensorAlertEnabled), failures, fallbackValue: false);
        int? alertTypeCode = alertEnabled
            ? TryReadSensorPropertyNullable(sensor, static s => s.SensorAlertType, nameof(ISensor.SensorAlertType), failures)
            : null;
        double? alertValue1 = alertEnabled
            ? TryReadSensorPropertyNullable(sensor, static s => s.SensorAlertValue1, nameof(ISensor.SensorAlertValue1), failures)
            : null;
        double? alertValue2 = alertEnabled
            ? TryReadSensorPropertyNullable(sensor, static s => s.SensorAlertValue2, nameof(ISensor.SensorAlertValue2), failures)
            : null;
        bool alertTriggered = alertEnabled
            && TryReadSensorProperty(sensor, static s => s.SensorAlertState, nameof(ISensor.SensorAlertState), failures, fallbackValue: false);
        var (currentValue, units) = TryReadSensorValue(sensor, failures);
        string? featureDataType = TryReadSensorFeatureDataType(sensor, failures);
        string status = failures.Count == 0 ? "completed" : "partial";

        return new ModelHealthSensorInfo(
            Index: node.Index,
            Name: node.Name,
            TypeName: node.TypeName,
            DocumentPath: documentPath,
            DocumentReference: documentReference,
            SensorType: DescribeSensorType(sensorTypeCode),
            SensorTypeCode: sensorTypeCode,
            AlertEnabled: alertEnabled,
            AlertType: alertTypeCode.HasValue ? DescribeSensorAlertType(alertTypeCode.Value) : null,
            AlertTypeCode: alertTypeCode,
            AlertValue1: alertValue1,
            AlertValue2: alertValue2,
            ThresholdDescription: DescribeSensorThreshold(alertEnabled, alertTypeCode, alertValue1, alertValue2, units),
            AlertTriggered: alertTriggered,
            CurrentValue: currentValue,
            Units: units,
            FeatureDataType: featureDataType,
            Status: status,
            FailureReason: failures.Count == 0 ? null : string.Join("; ", failures));
    }

    private static T TryReadSensorProperty<T>(
        ISensor sensor,
        Func<ISensor, T> accessor,
        string propertyName,
        List<string> failures,
        T fallbackValue)
    {
        try
        {
            return accessor(sensor);
        }
        catch (COMException ex)
        {
            failures.Add($"Failed to read {propertyName}: {ex.Message}");
            return fallbackValue;
        }
        catch (TargetInvocationException ex)
        {
            failures.Add($"Failed to read {propertyName}: {ex.InnerException?.Message ?? ex.Message}");
            return fallbackValue;
        }
    }

    private static T? TryReadSensorPropertyNullable<T>(
        ISensor sensor,
        Func<ISensor, T> accessor,
        string propertyName,
        List<string> failures)
        where T : struct
    {
        try
        {
            return accessor(sensor);
        }
        catch (COMException ex)
        {
            failures.Add($"Failed to read {propertyName}: {ex.Message}");
            return null;
        }
        catch (TargetInvocationException ex)
        {
            failures.Add($"Failed to read {propertyName}: {ex.InnerException?.Message ?? ex.Message}");
            return null;
        }
    }

    private static (double? CurrentValue, string? Units) TryReadSensorValue(ISensor sensor, List<string> failures)
    {
        try
        {
            bool hasValue = sensor.GetSensorValue(out double currentValue, out string units);
            return hasValue
                ? (currentValue, string.IsNullOrWhiteSpace(units) ? null : units)
                : (null, null);
        }
        catch (COMException ex)
        {
            failures.Add($"Failed to read {nameof(ISensor.GetSensorValue)}: {ex.Message}");
            return (null, null);
        }
        catch (TargetInvocationException ex)
        {
            failures.Add($"Failed to read {nameof(ISensor.GetSensorValue)}: {ex.InnerException?.Message ?? ex.Message}");
            return (null, null);
        }
    }

    private static string? TryReadSensorFeatureDataType(ISensor sensor, List<string> failures)
    {
        try
        {
            return sensor.GetSensorFeatureData()?.GetType().Name;
        }
        catch (COMException ex)
        {
            failures.Add($"Failed to read {nameof(ISensor.GetSensorFeatureData)}: {ex.Message}");
            return null;
        }
        catch (TargetInvocationException ex)
        {
            failures.Add($"Failed to read {nameof(ISensor.GetSensorFeatureData)}: {ex.InnerException?.Message ?? ex.Message}");
            return null;
        }
    }

    private static string DescribeSensorType(int sensorTypeCode) =>
        Enum.IsDefined(typeof(swSensorType_e), sensorTypeCode)
            ? Enum.GetName(typeof(swSensorType_e), sensorTypeCode) ?? $"unknown({sensorTypeCode})"
            : $"unknown({sensorTypeCode})";

    private static string DescribeSensorAlertType(int alertTypeCode) =>
        Enum.IsDefined(typeof(swSensorAlertType_e), alertTypeCode)
            ? Enum.GetName(typeof(swSensorAlertType_e), alertTypeCode) ?? $"unknown({alertTypeCode})"
            : $"unknown({alertTypeCode})";

    private static string? DescribeSensorThreshold(
        bool alertEnabled,
        int? alertTypeCode,
        double? alertValue1,
        double? alertValue2,
        string? units)
    {
        if (!alertEnabled)
        {
            return "alert disabled";
        }

        if (!alertTypeCode.HasValue)
        {
            return null;
        }

        string value1 = FormatSensorValue(alertValue1, units);
        string value2 = FormatSensorValue(alertValue2, units);

        return alertTypeCode.Value switch
        {
            (int)swSensorAlertType_e.swSensorAlert_GreaterThan => $"> {value1}",
            (int)swSensorAlertType_e.swSensorAlert_LessThan => $"< {value1}",
            (int)swSensorAlertType_e.swSensorAlert_Exactly => $"= {value1}",
            (int)swSensorAlertType_e.swSensorAlert_NotGreaterThan => $"<= {value1}",
            (int)swSensorAlertType_e.swSensorAlert_NotLessThan => $">= {value1}",
            (int)swSensorAlertType_e.swSensorAlert_NotExactly => $"!= {value1}",
            (int)swSensorAlertType_e.swSensorAlert_Between => $"between {value1} and {value2}",
            (int)swSensorAlertType_e.swSensorAlert_NotBetween => $"outside {value1} to {value2}",
            (int)swSensorAlertType_e.swSensorAlert_True => "true",
            (int)swSensorAlertType_e.swSensorAlert_False => "false",
            _ => null,
        };
    }

    private static string FormatSensorValue(double? value, string? units)
    {
        if (!value.HasValue)
        {
            return string.IsNullOrWhiteSpace(units) ? "n/a" : $"n/a {units}";
        }

        string numeric = value.Value.ToString("0.###", CultureInfo.InvariantCulture);
        return string.IsNullOrWhiteSpace(units) ? numeric : $"{numeric} {units}";
    }

    // ── Face mapping ─────────────────────────────────────────────

    private static string FaceMappingFilePath =>
        ResolveFaceMappingFilePath();

    private static string ResolveFaceMappingFilePath()
    {
        var configured = System.Environment.GetEnvironmentVariable("DEMO_FACE_MAPPING_PATH");
        return string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(AppContext.BaseDirectory, "face_mappings.json")
            : Path.GetFullPath(configured);
    }

    private static System.Text.Json.Nodes.JsonObject LoadMappings()
    {
        if (!File.Exists(FaceMappingFilePath)) return [];
        try { return System.Text.Json.Nodes.JsonNode.Parse(File.ReadAllText(FaceMappingFilePath)) as System.Text.Json.Nodes.JsonObject ?? []; }
        catch { return []; }
    }

    private static void SaveMappings(System.Text.Json.Nodes.JsonObject root)
    {
        var directory = Path.GetDirectoryName(FaceMappingFilePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(FaceMappingFilePath,
            root.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
    }

    private IComponent2? FindComponent(string componentName)
    {
        var doc = GetActiveModelDoc();
        if (doc is not IAssemblyDoc assy) return null;
        var all = (object[]?)assy.GetComponents(false) ?? [];
        // Match by exact Name2, or by the short name (last segment after '/').
        return all.OfType<IComponent2>().FirstOrDefault(c =>
            string.Equals(c.Name2, componentName, StringComparison.OrdinalIgnoreCase) ||
            string.Equals(c.Name2.Split('/').Last(), componentName, StringComparison.OrdinalIgnoreCase));
    }

    private static double[] BoxCenter(double[] box) =>
        [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2];

    public SelectedFaceCenterResult GetSelectedFaceCenter()
    {
        _cm.EnsureConnected();
        var selMgr = GetActiveModelDoc().ISelectionManager;
        int count = selMgr.GetSelectedObjectCount2(-1);
        if (count == 0)
            return new SelectedFaceCenterResult(false, "No entity selected. Select a face first.");

        IFace2? face = null;
        for (int i = 1; i <= count; i++)
        {
            if (selMgr.GetSelectedObjectType3(i, -1) == (int)swSelectType_e.swSelFACES)
            {
                face = selMgr.GetSelectedObject6(i, -1) as IFace2;
                break;
            }
        }

        if (face == null)
            return new SelectedFaceCenterResult(false, "Selected entity is not a face.");

        var box = ToDoubleArray(face.GetBox());
        if (box == null || box.Length < 6)
            return new SelectedFaceCenterResult(false, "Could not read selected face bounding box.");

        var center = BoxCenter(box);
        return new SelectedFaceCenterResult(
            true,
            $"Selected face center is ({center[0]}, {center[1]}, {center[2]}) meters.",
            center,
            face.GetArea());
    }

    private static double Dist(double[] a, double[] b) =>
        Math.Sqrt((a[0]-b[0])*(a[0]-b[0]) + (a[1]-b[1])*(a[1]-b[1]) + (a[2]-b[2])*(a[2]-b[2]));

    /// <summary>
    /// Convert a world-space point to the local coordinate space of the given leaf component.
    /// Uses the forward transform (world = T2 * local), so local = T2^-1 * world.
    /// Transform2.ArrayData layout (column-major): columns are [R0|R1|R2|T], scale at index 12.
    /// </summary>
    private static double[] WorldToLocal(double[] world, IComponent2 component)
    {
        var xform = GetComponentWorldTransform(component);
        if (xform == null) return world;

        // ArrayData: 16 doubles, column-major rotation + translation + scale
        // [R00,R10,R20, R01,R11,R21, R02,R12,R22, Tx,Ty,Tz, Scale, 0,0,0]
        //  col0         col1         col2          translation
        var raw = xform.ArrayData as double[];
        if (raw == null || raw.Length < 13) return world;

        double s = raw[12] == 0 ? 1.0 : raw[12];
        // Subtract translation first, then apply R^T (= inverse rotation for orthonormal R)
        double dx = world[0] - raw[9] * s;
        double dy = world[1] - raw[10] * s;
        double dz = world[2] - raw[11] * s;
        // R^T: row i of R^T = column i of R
        // column 0 = raw[0],raw[1],raw[2]; column 1 = raw[3],raw[4],raw[5]; column 2 = raw[6],raw[7],raw[8]
        double lx = raw[0]*dx + raw[1]*dy + raw[2]*dz;
        double ly = raw[3]*dx + raw[4]*dy + raw[5]*dz;
        double lz = raw[6]*dx + raw[7]*dy + raw[8]*dz;
        return [lx / s, ly / s, lz / s];
    }

    private static double[] LocalToWorld(double[] local, IComponent2 component)
    {
        var xform = GetComponentWorldTransform(component);
        if (xform == null) return local;

        var raw = xform.ArrayData as double[];
        if (raw == null || raw.Length < 13) return local;

        double s = raw[12] == 0 ? 1.0 : raw[12];
        double lx = local[0] * s;
        double ly = local[1] * s;
        double lz = local[2] * s;
        return [
            raw[9] * s + raw[0] * lx + raw[3] * ly + raw[6] * lz,
            raw[10] * s + raw[1] * lx + raw[4] * ly + raw[7] * lz,
            raw[11] * s + raw[2] * lx + raw[5] * ly + raw[8] * lz,
        ];
    }

    private static IMathTransform? GetComponentWorldTransform(IComponent2 component)
    {
        try
        {
            return component.GetTotalTransform(true) ?? component.Transform2;
        }
        catch
        {
            return component.Transform2;
        }
    }

    private static double[]? LocalToWorldVector(double[] localVector, IComponent2 component)
    {
        var xform = GetComponentWorldTransform(component);
        if (xform == null) return NormalizeVectorOrNull(localVector);

        var raw = xform.ArrayData as double[];
        if (raw == null || raw.Length < 13) return NormalizeVectorOrNull(localVector);

        double wx = raw[0] * localVector[0] + raw[3] * localVector[1] + raw[6] * localVector[2];
        double wy = raw[1] * localVector[0] + raw[4] * localVector[1] + raw[7] * localVector[2];
        double wz = raw[2] * localVector[0] + raw[5] * localVector[1] + raw[8] * localVector[2];
        return NormalizeVectorOrNull([wx, wy, wz]);
    }

    private static double[]? NormalizeVectorOrNull(double[] vector)
    {
        if (vector.Length < 3) return null;
        double length = Math.Sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);
        return length < 1e-9
            ? null
            : [vector[0] / length, vector[1] / length, vector[2] / length];
    }

    private static double[]? TryGetPlanarFaceNormal(IFace2 face)
    {
        try
        {
            var surface = face.GetSurface() as ISurface;
            if (surface != null && surface.IsPlane())
            {
                var plane = ToDoubleArray(surface.PlaneParams);
                if (plane != null && plane.Length >= 6)
                {
                    var normal = NormalizeVectorOrNull([plane[3], plane[4], plane[5]]);
                    if (normal != null)
                    {
                        return ApplyFaceSense(face, normal);
                    }
                }
            }

            return TryGetTessellatedFaceNormal(face);
        }
        catch
        {
            return TryGetTessellatedFaceNormal(face);
        }
    }

    private static double[] ApplyFaceSense(IFace2 face, double[] normal)
    {
        try
        {
            if (!face.FaceInSurfaceSense())
            {
                return [-normal[0], -normal[1], -normal[2]];
            }
        }
        catch
        {
            // Some topology proxies do not expose FaceInSurfaceSense reliably.
        }

        return normal;
    }

    private static double[]? TryGetTessellatedFaceNormal(IFace2 face)
    {
        var normal = TryGetAverageTessellatedNormal(face);
        if (normal != null)
        {
            return normal;
        }

        var tessTriangles =
            TryInvokeDoubleArray(face, "GetTessTriangles", true)
            ?? TryInvokeDoubleArray(face, "GetTessTriangles", false)
            ?? TryInvokeDoubleArray(face, "GetTessTriangles");

        normal = TryFitTriangleNormalFromTessellation(tessTriangles);
        return normal == null ? null : ApplyFaceSense(face, normal);
    }

    private static double[]? TryGetAverageTessellatedNormal(IFace2 face)
    {
        var tessNormals =
            TryInvokeDoubleArray(face, "GetTessNorms")
            ?? TryInvokeDoubleArray(face, "GetTessNormals");
        if (tessNormals == null || tessNormals.Length < 3)
        {
            return null;
        }

        double x = 0, y = 0, z = 0;
        for (var i = 0; i + 2 < tessNormals.Length; i += 3)
        {
            x += tessNormals[i];
            y += tessNormals[i + 1];
            z += tessNormals[i + 2];
        }

        return NormalizeVectorOrNull([x, y, z]);
    }

    internal static double[]? TryFitTriangleNormalFromTessellation(double[]? tessTriangles)
    {
        if (tessTriangles == null || tessTriangles.Length < 9)
        {
            return null;
        }

        var candidates = new List<TessellationNormalCandidate>();
        AddTessellationNormalCandidate(tessTriangles, vertexStride: 3, candidates);
        AddTessellationNormalCandidate(tessTriangles, vertexStride: 9, candidates);

        return candidates
            .OrderBy(candidate => candidate.MaxPlaneResidual)
            .ThenByDescending(candidate => candidate.AreaWeight)
            .FirstOrDefault()
            ?.Normal;
    }

    private static void AddTessellationNormalCandidate(
        double[] data,
        int vertexStride,
        ICollection<TessellationNormalCandidate> candidates)
    {
        var triangleStride = vertexStride * 3;
        if (data.Length < triangleStride || data.Length % triangleStride != 0)
        {
            return;
        }

        var points = new List<double[]>();
        double nx = 0, ny = 0, nz = 0, areaWeight = 0;
        for (var offset = 0; offset + triangleStride - 1 < data.Length; offset += triangleStride)
        {
            var p0 = ReadPoint(data, offset);
            var p1 = ReadPoint(data, offset + vertexStride);
            var p2 = ReadPoint(data, offset + vertexStride * 2);
            var cross = Cross(Subtract(p1, p0), Subtract(p2, p0));
            var area2 = Length(cross);
            if (area2 < 1e-12)
            {
                continue;
            }

            nx += cross[0];
            ny += cross[1];
            nz += cross[2];
            areaWeight += area2;
            points.Add(p0);
            points.Add(p1);
            points.Add(p2);
        }

        var normal = NormalizeVectorOrNull([nx, ny, nz]);
        if (normal == null || points.Count < 3)
        {
            return;
        }

        var origin = points[0];
        var maxResidual = points
            .Select(point => Math.Abs(Dot(Subtract(point, origin), normal)))
            .DefaultIfEmpty(double.PositiveInfinity)
            .Max();
        candidates.Add(new TessellationNormalCandidate(normal, areaWeight, maxResidual));
    }

    private static double[] ReadPoint(double[] data, int offset) =>
        [data[offset], data[offset + 1], data[offset + 2]];

    private static double[] Subtract(double[] a, double[] b) =>
        [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

    private static double[] Cross(double[] a, double[] b) =>
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ];

    private static double Dot(double[] a, double[] b) =>
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

    private static double Length(double[] vector) =>
        Math.Sqrt(Dot(vector, vector));

    private static double[]? TryInvokeDoubleArray(object target, string methodName, params object[] args)
    {
        try
        {
            var result = target
                .GetType()
                .InvokeMember(
                    methodName,
                    BindingFlags.InvokeMethod | BindingFlags.Public | BindingFlags.Instance,
                    binder: null,
                    target,
                    args);
            return ToDoubleArray(result);
        }
        catch
        {
            return null;
        }
    }

    private sealed record TessellationNormalCandidate(double[] Normal, double AreaWeight, double MaxPlaneResidual);

    private string? TryGetPersistentReferenceBase64(IFace2 face)
    {
        try
        {
            var doc = GetActiveModelDoc();
            var bytes = ToByteArray(doc.Extension.GetPersistReference3(face));
            return bytes is { Length: > 0 } ? Convert.ToBase64String(bytes) : null;
        }
        catch
        {
            return null;
        }
    }

    private FaceMappingResult? TrySelectFaceByPersistentReference(
        string persistentReferenceBase64,
        string faceName,
        string componentName,
        bool append,
        int mark)
    {
        try
        {
            var bytes = Convert.FromBase64String(persistentReferenceBase64);
            var doc = GetActiveModelDoc();
            int error = 0;
            var resolved = doc.Extension.GetObjectByPersistReference3(bytes, out error);
            if (resolved is not IFace2 face)
            {
                return new FaceMappingResult(
                    false,
                    $"Persistent reference did not resolve to a face for '{faceName}' in '{componentName}'. Error={error}.",
                    faceName,
                    componentName);
            }

            if (!append)
            {
                doc.ClearSelection2(true);
            }

            var selectData = CreateSelectData(doc.ISelectionManager, mark);
            var ok = ((IEntity)face).Select4(append, selectData);
            return ok
                ? new FaceMappingResult(
                    true,
                    $"Selected face '{faceName}' for '{componentName}' via persistent reference.",
                    faceName,
                    componentName)
                : new FaceMappingResult(
                    false,
                    $"Persistent reference resolved but failed to select face '{faceName}' for '{componentName}'.",
                    faceName,
                    componentName);
        }
        catch (Exception ex)
        {
            return new FaceMappingResult(
                false,
                $"Persistent reference selection failed for '{faceName}' in '{componentName}': {ex.Message}",
                faceName,
                componentName);
        }
    }

    public FaceMappingProbeResult GetSelectedFaceMappingProbe(string? faceName = null, string? componentName = null)
    {
        // 读取 SolidWorks 当前选择集中的第一个面，并返回“当前状态下”的几何探针数据。
        // 该函数不会主动寻找面，只验证已经选中的面；因此常用于：
        // 1. 手动选面后确认记录内容；
        // 2. SelectFaceByName 自动选回面后，检查是否仍是同一个几何面；
        // 3. Common Base / Replay 前读取底面中心和法向，作为移动或朝向校验依据。
        _cm.EnsureConnected();
        var selMgr = GetActiveModelDoc().ISelectionManager;
        int count = selMgr.GetSelectedObjectCount2(-1);
        if (count == 0)
            return new FaceMappingProbeResult(false, "No entity selected. Select a face in SolidWorks first.", faceName, componentName, null, null, null, null, null, null, null, null, FaceMappingFilePath);

        IFace2? face = null;
        IComponent2? leafComponent = null;
        for (int i = 1; i <= count; i++)
        {
            if (selMgr.GetSelectedObjectType3(i, -1) == (int)swSelectType_e.swSelFACES)
            {
                face = selMgr.GetSelectedObject6(i, -1) as IFace2;
                leafComponent = selMgr.GetSelectedObjectsComponent3(i, -1) as IComponent2;
                break;
            }
        }

        if (face == null)
            return new FaceMappingProbeResult(false, "Selected entity is not a face.", faceName, componentName, null, null, null, null, null, null, null, null, FaceMappingFilePath);

        var box = ToDoubleArray(face.GetBox());
        if (box == null || box.Length < 6)
            return new FaceMappingProbeResult(false, "Could not read face bounding box.", faceName, componentName, null, null, null, null, null, null, null, null, FaceMappingFilePath);

        var localCenter = BoxCenter(box);
        var worldCenter = leafComponent != null ? LocalToWorld(localCenter, leafComponent) : localCenter;
        var localNormal = TryGetPlanarFaceNormal(face);
        var worldNormal = localNormal != null && leafComponent != null
            ? LocalToWorldVector(localNormal, leafComponent)
            : localNormal;
        var leafFullName = leafComponent?.Name2 ?? componentName;
        var leafName = leafFullName?.Split('/').Last() ?? componentName;
        var area = face.GetArea();

        var normalMessage = worldNormal == null
            ? " Selected face has no valid planar normal."
            : $" normal=[{worldNormal[0]:F6},{worldNormal[1]:F6},{worldNormal[2]:F6}].";

        return new FaceMappingProbeResult(
            true,
            $"Selected face probe: leaf='{leafName}', local=[{localCenter[0]:F6},{localCenter[1]:F6},{localCenter[2]:F6}], area={area:F9}.{normalMessage}",
            faceName,
            componentName,
            leafName,
            leafFullName,
            worldCenter,
            localCenter,
            worldNormal,
            localNormal,
            area,
            box,
            FaceMappingFilePath);
    }

    public FaceMappingResult RecordFaceMapping(string faceName, string componentName)
    {
        // 手动记录路径：用户先在 SolidWorks UI 里选中一个真实面，
        // MCP 再把该面的 leaf component、局部中心、面积、法向、Persistent Reference 等写入 face_mappings.json。
        // 注意：这里不判断“这个面是否真的是底面”，只忠实记录当前选择。
        // 因此真实装配体里底面不明显时，记录质量直接决定后续 SelectFaceByName、Common Base、Replay 的稳定性。
        _cm.EnsureConnected();
        var selMgr = GetActiveModelDoc().ISelectionManager;
        int count = selMgr.GetSelectedObjectCount2(-1);
        if (count == 0)
            return new FaceMappingResult(false, "No entity selected. Select a face in SolidWorks first.", faceName, componentName);

        IFace2? face = null;
        IComponent2? leafComponent = null;
        for (int i = 1; i <= count; i++)
        {
            if (selMgr.GetSelectedObjectType3(i, -1) == (int)swSelectType_e.swSelFACES)
            {
                face = selMgr.GetSelectedObject6(i, -1) as IFace2;
                // GetSelectedObjectsComponent3 returns the leaf component the face belongs to.
                leafComponent = selMgr.GetSelectedObjectsComponent3(i, -1) as IComponent2;
                break;
            }
        }
        if (face == null)
            return new FaceMappingResult(false, "Selected entity is not a face.", faceName, componentName);

        return SaveFaceMapping(face, leafComponent, faceName, componentName);
    }

    public FaceMappingResult RecordFirstFaceMapping(string faceName, string componentName)
    {
        // 自动兜底记录路径：遍历目标组件下的实体并记录遇到的第一个面。
        // 这只能用于快速诊断或非关键组件占位；它没有“识别真实底面”的语义。
        // 如果后续要做精确共底面，应优先使用 RecordFaceMapping 手动记录，或实现更可靠的底面自动识别策略。
        _cm.EnsureConnected();

        var component = FindComponent(componentName);
        if (component == null)
            return new FaceMappingResult(false, $"Component '{componentName}' was not found.", faceName, componentName);

        foreach (var (body, leafComponent) in GetBodyContextsDeep(component))
        {
            foreach (var face in ((object[]?)body.GetFaces() ?? Array.Empty<object>()).OfType<IFace2>())
            {
                return SaveFaceMapping(face, leafComponent, faceName, componentName);
            }
        }

        return new FaceMappingResult(false, $"No solid-body face found under component '{componentName}'.", faceName, componentName);
    }

    private FaceMappingResult SaveFaceMapping(IFace2 face, IComponent2? leafComponent, string faceName, string componentName)
    {
        // face_mappings.json 的核心结构由这里生成。
        // 保存 leafComponentFullName + localCenter 的原因是：组件整体移动/旋转后，
        // 面在 leaf component 坐标系下的位置通常不变，便于在新姿态下重新找回同一个面。
        // 但如果重新导入后组件实例名变化，或同类面很多且 localCenter/area/normal 不够区分，仍可能选错面。
        var box = ToDoubleArray(face.GetBox());
        if (box == null || box.Length < 6)
            return new FaceMappingResult(false, "Could not read face bounding box.", faceName, componentName);

        var localCenter = BoxCenter(box);
        var worldCenter = leafComponent != null ? LocalToWorld(localCenter, leafComponent) : localCenter;
        double area = face.GetArea();
        var localNormal = TryGetPlanarFaceNormal(face);

        // Convert to leaf-component local coordinates — stable across assembly-level move/rotate/mate.
        var worldNormal = localNormal != null && leafComponent != null
            ? LocalToWorldVector(localNormal, leafComponent)
            : localNormal;
        // Name2 may be prefixed with ancestor names (e.g. "ParentAsm/LeafPart"); use the short name only.
        string leafFullName = leafComponent?.Name2 ?? componentName;
        string leafName = leafFullName.Split('/').Last();
        string? persistentReferenceBase64 = TryGetPersistentReferenceBase64(face);

        var root = LoadMappings();
        if (root[componentName] is not System.Text.Json.Nodes.JsonObject compNode)
        {
            compNode = [];
            root[componentName] = compNode;
        }
        compNode[faceName] = System.Text.Json.Nodes.JsonNode.Parse(System.Text.Json.JsonSerializer.Serialize(new
        {
            leafComponentName = leafName,
            leafComponentFullName = leafFullName,
            localCenter,
            localNormal,
            worldNormal,
            persistentReferenceBase64,
            area,
        }));
        SaveMappings(root);

        return new FaceMappingResult(true,
            $"Recorded face '{faceName}' on leaf '{leafName}' at local [{localCenter[0]:F4},{localCenter[1]:F4},{localCenter[2]:F4}], area={area:F6}",
            faceName, componentName);
    }

    public FaceMappingResult SelectFaceByName(string faceName, string componentName, bool append = false, int mark = 0)
    {
        // 自动选回路径：
        // 1. 从 face_mappings.json 读取记录；
        // 2. 优先用 SolidWorks Persistent Reference 找回 IFace2；
        // 3. Persistent Reference 失败时，按 leaf component + localCenter + area + localNormal 扫描候选面；
        // 4. 选中分数最好的候选面。
        // 这一步是后续“操作底面”的入口：mate、probe、move/replay 都依赖它先选中正确底面。
        _cm.EnsureConnected();
        var root = LoadMappings();
        if (root[componentName] is not System.Text.Json.Nodes.JsonObject compNode || compNode[faceName] is not System.Text.Json.Nodes.JsonNode entryNode)
            return new FaceMappingResult(false, $"No mapping found for '{faceName}' in '{componentName}'. Call record_face_mapping first.", faceName, componentName);

        // Parse saved entry.
        string? leafName = null;
        string? leafFullName = null;
        double[]? savedLocal = null;
        double[]? savedLocalNormal = null;
        string? persistentReferenceBase64 = null;
        double savedArea = -1;

        if (entryNode is System.Text.Json.Nodes.JsonObject obj)
        {
            leafName = obj["leafComponentName"]?.GetValue<string>();
            leafFullName = obj["leafComponentFullName"]?.GetValue<string>();
            persistentReferenceBase64 = obj["persistentReferenceBase64"]?.GetValue<string>();
            savedLocal = obj["localCenter"] != null
                ? System.Text.Json.JsonSerializer.Deserialize<double[]>(obj["localCenter"]!.ToJsonString())
                : null;
            savedLocalNormal = obj["localNormal"] != null
                ? System.Text.Json.JsonSerializer.Deserialize<double[]>(obj["localNormal"]!.ToJsonString())
                : null;
            if (savedLocalNormal is { Length: >= 3 } && !CommonBaseLayoutMath.IsValidNormal(savedLocalNormal))
            {
                savedLocalNormal = null;
            }
            savedArea = obj["area"] != null ? obj["area"]!.GetValue<double>() : -1;
        }

        // Fall back to legacy plain-array world-coord format.
        if (savedLocal == null)
            savedLocal = System.Text.Json.JsonSerializer.Deserialize<double[]>(entryNode.ToJsonString());

        if (savedLocal == null || savedLocal.Length < 3)
            return new FaceMappingResult(false, $"Invalid mapping data for '{faceName}'.", faceName, componentName);

        if (!string.IsNullOrWhiteSpace(persistentReferenceBase64))
        {
            // Persistent Reference 是当前最稳定的选面方式，但它可能受文档另存、重新导入实例、
            // 组件替换等因素影响；失败后会自动降级到几何匹配。
            var persistentResult = TrySelectFaceByPersistentReference(
                persistentReferenceBase64,
                faceName,
                componentName,
                append,
                mark);
            if (persistentResult?.Success == true)
            {
                return persistentResult;
            }
        }

        // Locate the leaf component directly — O(N_components), not O(N_faces).
        // 先定位记录时的 leaf component，再只扫描该叶组件内的面，避免在整个装配体内 O(N_faces) 盲扫。
        // 对 10+ 子装配体场景，这一步能明显减少误选和耗时；但实例名变化时 leafFullName 可能失效。
        var leaf = !string.IsNullOrWhiteSpace(leafFullName)
            ? FindComponent(leafFullName)
            : leafName != null ? FindComponent(leafName) : FindComponent(componentName);
        if (leaf == null)
            return new FaceMappingResult(false, $"Leaf component '{leafName ?? componentName}' not found.", faceName, componentName);

        const double centerTolerance = 0.002; // meters, leaf-local bounding-box center tolerance
        const double areaRelativeTolerance = 0.05;
        const double normalDotTolerance = 0.95;
        var candidateRows = new List<(IFace2 Face, FaceMappingCandidateDiagnostic Diagnostic)>();

        foreach (var body in GetBodies(leaf))
        {
            foreach (var face in ((object[]?)body.GetFaces() ?? []).OfType<IFace2>())
            {
                var box = ToDoubleArray(face.GetBox());
                if (box == null || box.Length < 6) continue;
                var lc = WorldToLocal(BoxCenter(box), leaf);
                double centerDistance = Dist(lc, savedLocal);
                double score = centerDistance;

                double? area = null;
                double? areaRelativeError = null;
                if (savedArea > 0)
                {
                    area = face.GetArea();
                    areaRelativeError = Math.Abs(area.Value - savedArea) / savedArea;
                    score += areaRelativeError.Value * 0.1;
                }

                double? normalDot = null;
                double[]? candidateNormal = null;
                if (savedLocalNormal is { Length: >= 3 } savedNormal
                    && CommonBaseLayoutMath.IsValidNormal(savedNormal))
                {
                    candidateNormal = TryGetPlanarFaceNormal(face);
                    if (candidateNormal is { Length: >= 3 } candidateNormalValue
                        && CommonBaseLayoutMath.IsValidNormal(candidateNormalValue))
                    {
                        normalDot = Math.Abs(Dot(candidateNormalValue, savedNormal));
                        score += (1 - Math.Min(1, normalDot.Value)) * 0.05;
                    }
                    else
                    {
                        score += 1.0;
                    }
                }

                var rejectReasons = new List<string>();
                if (centerDistance > centerTolerance)
                {
                    rejectReasons.Add($"center distance {centerDistance:F6}m > {centerTolerance:F6}m");
                }
                if (areaRelativeError is not null && areaRelativeError > areaRelativeTolerance)
                {
                    rejectReasons.Add($"area relative error {areaRelativeError:F6} > {areaRelativeTolerance:F6}");
                }
                if (savedLocalNormal is { Length: >= 3 } && normalDot is null)
                {
                    rejectReasons.Add("candidate normal unavailable");
                }
                else if (normalDot is not null && normalDot < normalDotTolerance)
                {
                    rejectReasons.Add($"normal dot {normalDot:F6} < {normalDotTolerance:F6}");
                }

                candidateRows.Add((face, new FaceMappingCandidateDiagnostic(
                    Rank: 0,
                    Score: score,
                    Accepted: rejectReasons.Count == 0,
                    RejectReason: rejectReasons.Count == 0 ? null : string.Join("; ", rejectReasons),
                    CenterDistance: centerDistance,
                    Area: area,
                    AreaRelativeError: areaRelativeError,
                    NormalDot: normalDot,
                    LocalCenter: lc,
                    LocalNormal: candidateNormal,
                    Box: box)));
            }
        }

        var rankedRows = candidateRows
            .OrderBy(row => row.Diagnostic.Accepted ? 0 : 1)
            .ThenBy(row => row.Diagnostic.Score)
            .Select((row, index) => (row.Face, Diagnostic: row.Diagnostic with { Rank = index + 1 }))
            .ToList();
        var diagnostics = new FaceMappingSelectionDiagnostics(
            LeafComponentName: leafName,
            LeafComponentFullName: leafFullName,
            SavedLocalCenter: savedLocal,
            SavedArea: savedArea > 0 ? savedArea : null,
            SavedLocalNormal: savedLocalNormal,
            CenterTolerance: centerTolerance,
            AreaRelativeTolerance: areaRelativeTolerance,
            NormalDotTolerance: normalDotTolerance,
            FailureReason: null,
            Candidates: rankedRows.Take(5).Select(row => row.Diagnostic).ToList().AsReadOnly());

        if (rankedRows.Count == 0)
        {
            return new FaceMappingResult(
                false,
                $"No faces found on leaf '{leafName}'. Re-record the mapping.",
                faceName,
                componentName,
                diagnostics with { FailureReason = "No faces were available on the mapped leaf component." });
        }

        var best = rankedRows[0];
        if (!best.Diagnostic.Accepted)
        {
            return new FaceMappingResult(
                false,
                $"Mapped face '{faceName}' for '{componentName}' could not be selected reliably. Best candidate rejected: {best.Diagnostic.RejectReason}.",
                faceName,
                componentName,
                diagnostics with { FailureReason = best.Diagnostic.RejectReason });
        }

        var doc = GetActiveModelDoc();
        if (!append) doc.ClearSelection2(true);
        var selectData = CreateSelectData(doc.ISelectionManager, mark);
        bool ok = ((IEntity)best.Face).Select4(append, selectData);

        return ok
            ? new FaceMappingResult(true, $"Selected face '{faceName}' for '{componentName}'.", faceName, componentName, diagnostics)
            : new FaceMappingResult(false, $"Failed to select face '{faceName}' for '{componentName}'.", faceName, componentName, diagnostics);
    }
}
