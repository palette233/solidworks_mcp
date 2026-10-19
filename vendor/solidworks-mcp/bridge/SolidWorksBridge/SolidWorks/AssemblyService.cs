using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Runtime.InteropServices;

namespace SolidWorksBridge.SolidWorks;

/// <summary>
/// Info about a component in an assembly.
/// </summary>
public record ComponentInfo(string Name, string Path);

/// <summary>
/// Result of creating a non-destructive top-level module-only view by suppressing
/// every component that is not present in the requested keep list.
/// </summary>
public record TopLevelComponentIsolationResult(
    bool Success,
    IReadOnlyList<string> RequestedKeepComponentNames,
    IReadOnlyList<string> KeptComponentNames,
    IReadOnlyList<string> SuppressedComponentNames,
    IReadOnlyList<string> AlreadySuppressedComponentNames,
    IReadOnlyList<string> MissingKeepComponentNames,
    IReadOnlyList<string> FailedComponentNames,
    IReadOnlyList<string> RemainingResolvedComponentNames);

public record TopLevelComponentVisibilityIsolationResult(
    bool Success,
    IReadOnlyList<string> RequestedKeepComponentNames,
    IReadOnlyList<string> VisibleComponentNames,
    IReadOnlyList<string> HiddenComponentNames,
    IReadOnlyList<string> MissingKeepComponentNames,
    IReadOnlyList<string> SuppressedKeepComponentNames,
    IReadOnlyList<string> FailedComponentNames);

/// <summary>
/// Info about a component instance discovered by recursively traversing an assembly tree.
/// </summary>
public record ComponentInstanceInfo(string Name, string Path, string HierarchyPath, int Depth);

public record ComponentPoseInfo(
    string Name,
    string Path,
    string HierarchyPath,
    int Depth,
    double[]? Transform,
    double[]? Translation,
    double[]? XAxis,
    double[]? YAxis,
    double[]? ZAxis,
    double[]? BoundingBoxWorld = null,
    string? ReferencedConfiguration = null,
    int? SolvingState = null,
    string? SolvingStateName = null,
    double[]? TotalTransform = null,
    double[]? TotalTranslation = null,
    double[]? TotalXAxis = null,
    double[]? TotalYAxis = null,
    double[]? TotalZAxis = null);

public record ComponentSolvingStateResult(
    bool Success,
    string ComponentName,
    string HierarchyPath,
    string? ReferencedConfiguration,
    int PreviousSolvingState,
    string PreviousSolvingStateName,
    int RequestedSolvingState,
    string RequestedSolvingStateName,
    int ActualSolvingState,
    string ActualSolvingStateName,
    bool RebuildRequested,
    bool RebuildSucceeded);

public record ResolveLightweightComponentsResult(
    bool Success,
    int RawResolveCode,
    bool WarnIfNotResolved,
    bool RebuildRequested,
    bool RebuildSucceeded);

/// <summary>
/// Summary of a static interference check in an assembly.
/// </summary>
public record AssemblyInterferenceCheckResult(
    bool HasInterference,
    bool TreatCoincidenceAsInterference,
    int CheckedComponentCount,
    int InterferingFaceCount,
    IReadOnlyList<ComponentInstanceInfo> InterferingComponents);

/// <summary>
/// Detailed result of a two-module interference check performed on transformed leaf solid bodies.
/// Component AABBs are used only as a broad-phase filter; every surviving body pair is checked by
/// the SolidWorks modeler B-Rep kernel.
/// </summary>
public record LeafBodyInterferenceCheckResult(
    bool HasInterference,
    bool TreatCoincidenceAsInterference,
    bool ExactCheckComplete,
    int CheckedTopLevelComponentCount,
    int FirstLeafComponentCount,
    int SecondLeafComponentCount,
    int FirstBodyCount,
    int SecondBodyCount,
    long TotalBodyPairCount,
    int AabbCandidateBodyPairCount,
    int BodyWithoutBoundingBoxCount,
    long BroadPhaseBypassedBodyPairCount,
    int ExactCompletedBodyPairCount,
    int PrimaryCheckReturnedFalseCount,
    int FallbackExactCompletedBodyPairCount,
    int BooleanFallbackCompletedBodyPairCount,
    int BooleanFallbackNoIntersectionBodyPairCount,
    int FailedBodyPairCount,
    int InterferingBodyPairCount,
    IReadOnlyList<ComponentInstanceInfo> InterferingComponents,
    IReadOnlyList<LeafBodyInterferencePairInfo> InterferingBodyPairs,
    IReadOnlyList<string> Failures);

/// <summary>
/// A leaf solid-body pair that the SolidWorks B-Rep kernel reported as intersecting.
/// Bounding boxes are expressed in the active top-level assembly coordinate system.
/// </summary>
public record LeafBodyInterferencePairInfo(
    ComponentInstanceInfo FirstComponent,
    ComponentInstanceInfo SecondComponent,
    double[] FirstBoundingBoxWorld,
    double[] SecondBoundingBoxWorld,
    double[] AabbOverlapWorld,
    string DetectionMethod);

/// <summary>
/// Conservative world-space AABB for one solid body owned by a leaf component.
/// BodyIndex is stable only within the current capture and leaf component.
/// </summary>
public record LeafBodyEnvelopeInfo(
    ComponentInstanceInfo Component,
    int BodyIndex,
    double[] BoundingBoxWorld,
    string BoundingBoxSource);

public record LeafBodyEnvelopeCaptureResult(
    ComponentInstanceInfo TopLevelComponent,
    int LeafComponentCount,
    int BodyCount,
    IReadOnlyList<LeafBodyEnvelopeInfo> Bodies,
    int FailedBodyCount,
    bool CoverageComplete,
    IReadOnlyList<string> Failures);

public record AssemblyTargetResolutionResult(
    string? RequestedName,
    string? RequestedHierarchyPath,
    string? RequestedComponentPath,
    bool IsResolved,
    bool IsAmbiguous,
    ComponentInstanceInfo? ResolvedInstance,
    string? OwningAssemblyHierarchyPath,
    string? OwningAssemblyFilePath,
    int SourceFileReuseCount,
    IReadOnlyList<ComponentInstanceInfo> MatchingInstances);

public record SharedPartEditImpactResult(
    AssemblyTargetResolutionResult TargetResolution,
    string? SourceFilePath,
    int AffectedInstanceCount,
    IReadOnlyList<ComponentInstanceInfo> AffectedInstances,
    bool SafeDirectEdit,
    string RecommendedAction);

public record AssemblyComponentReplacementResult(
    string ReplacedHierarchyPath,
    string ReplacementFilePath,
    string ConfigName,
    bool ReplaceAllInstances,
    int UseConfigChoice,
    bool ReattachMates,
    bool Success);

public record AssemblyFeatureTreeNodeInfo(
    int NodeIndex,
    int Depth,
    string Text,
    int ObjectType,
    string? ObjectKind,
    bool IsRoot,
    bool IsExpanded,
    string GraphPath,
    string? ParentGraphPath,
    string? FeatureName,
    string? FeatureTypeName,
    bool IsSketch,
    string? ComponentName,
    string? ComponentPath,
    string? HierarchyPath,
    string? DocumentTitle,
    string? DocumentPath);

public record AssemblyFeatureTreeTraversalResult(
    string AssemblyTitle,
    string? AssemblyPath,
    int NodeCount,
    IReadOnlyList<AssemblyFeatureTreeNodeInfo> Nodes);

public record AssemblyFeatureSearchMatchInfo(
    int Rank,
    int Score,
    string Query,
    string MatchedText,
    string? FeatureName,
    string? FeatureTypeName,
    string GraphPath,
    string? ComponentName,
    string? ComponentPath,
    string? HierarchyPath,
    string? DocumentTitle,
    string? DocumentPath,
    bool RequiresOpenForEdit);

public record AssemblyFeatureSearchResult(
    string Query,
    bool ExactNameOnly,
    int MatchCount,
    IReadOnlyList<AssemblyFeatureSearchMatchInfo> Matches);

public record OpenComponentForEditingResult(
    bool Opened,
    string ComponentName,
    string ComponentPath,
    string? HierarchyPath,
    string Message,
    SwDocumentInfo? OpenedDocument);


public record ComponentTransformResult(
    bool Success,
    string Message,
    string? ComponentName,
    string? HierarchyPath);

public record ComponentReferencedConfigurationResult(
    bool Success,
    string ComponentName,
    string HierarchyPath,
    string PreviousConfiguration,
    string RequestedConfiguration,
    string ActualConfiguration,
    bool RebuildRequested,
    bool RebuildSucceeded);

public record MateOperationResult(string MateType, int ErrorStatus, string ErrorName, string ErrorDescription);

/// <summary>
/// Mate type for assembly constraints.
/// Values match swMateType_e.
/// </summary>
public enum MateType
{
    Coincident = 0,
    Concentric = 1,
    Perpendicular = 2,
    Parallel = 3,
    Distance = 5,
    Angle = 6,
}

/// <summary>
/// Mate alignment for assembly constraints.
/// Values match swMateAlign_e.
/// </summary>
public enum MateAlign
{
    None = 0,
    AntiAligned = 1,
    Closest = 2,
}

/// <summary>
/// Operations on SolidWorks assembly documents.
/// SolidWorks 瑁呴厤浣撴枃妗ｇ浉鍏虫搷浣滅殑鏈嶅姟鎺ュ彛锛屼緵 MCP 宸ュ叿灞傚寘瑁呭悗鏆撮湶缁欏ぇ妯″瀷璋冪敤銆?/// </summary>
public interface IAssemblyService
{
    /// <summary>
    /// Move a component by the specified delta in meters.
    /// 鎸変笘鐣屽潗鏍囩郴涓殑澧為噺绉诲姩鎸囧畾缁勪欢瀹炰緥锛屽崟浣嶄负绫筹紱閫傚悎鈥滄部 X/Y/Z 鏂瑰悜绉诲姩鎸囧畾璺濈鈥濈殑鍦烘櫙銆?    /// </summary>
    ComponentTransformResult MoveComponent(
        string componentName,
        double deltaX,
        double deltaY,
        double deltaZ,
        bool rebuild = true);

    /// <summary>
    /// Rotate a component around the specified world-space axis by the given angle in degrees.
    /// 鍥寸粫涓栫晫鍧愭爣绯讳腑鐨勬寚瀹氳酱鏃嬭浆缁勪欢瀹炰緥锛岃搴﹀崟浣嶄负搴︺€?    /// </summary>
    ComponentTransformResult RotateComponent(
        string componentName,
        double axisX,
        double axisY,
        double axisZ,
        double angleDegrees,
        bool rebuild = true);

    /// <summary>
    /// Replace only a component's world-space orientation while preserving its translation.
    /// The three axes must form a right-handed orthonormal frame.
    /// </summary>
    ComponentTransformResult SetComponentOrientation(
        string componentName,
        IReadOnlyList<double> xAxis,
        IReadOnlyList<double> yAxis,
        IReadOnlyList<double> zAxis,
        bool rebuild = true);

    /// <summary>Replace one component's complete Transform2 matrix.</summary>
    ComponentTransformResult SetComponentTransform(
        string componentName,
        IReadOnlyList<double> transform,
        bool rebuild = true);

    /// <summary>Switch one component instance to an existing referenced configuration.</summary>
    ComponentReferencedConfigurationResult SetComponentReferencedConfiguration(
        string componentName,
        string configurationName,
        bool rebuild = true);

    /// <summary>
    /// Temporarily suppress resolved mate features directly under the active assembly's MateGroup.
    /// Intended for high-level batch Transform2 workflows; callers must restore the returned names.
    /// </summary>
    IReadOnlyList<string> SuppressTopLevelMateFeatures();

    /// <summary>
    /// Restore top-level mate features previously returned by SuppressTopLevelMateFeatures.
    /// </summary>
    IReadOnlyList<string> RestoreTopLevelMateFeatures(IReadOnlyList<string> featureNames);

    /// <summary>
    /// Insert a component at the given position (meters). Returns component info.
    /// 鍚戝綋鍓嶆椿鍔ㄨ閰嶄綋瀵煎叆涓€涓浂浠舵垨瀛愯閰嶄綋锛屽苟鎸囧畾鍒濆鎻掑叆浣嶇疆锛屽潗鏍囧崟浣嶄负绫炽€?    /// </summary>
    ComponentInfo InsertComponent(string filePath, double x = 0, double y = 0, double z = 0);

    /// <summary>
    /// Rename one component instance in the active assembly.
    /// 重命名当前装配体中的一个组件实例；用于在导入后保持目标装配体实例名与源 layout/componentName 一致。
    /// </summary>
    ComponentInfo RenameComponent(string currentName, string newName);

    /// <summary>
    /// Add a Coincident mate between the two currently-selected entities.
    /// 瀵瑰綋鍓嶅凡缁忛€変腑鐨勪袱涓疄浣撴坊鍔犻噸鍚堥厤鍚堬紱甯哥敤浜庝袱涓钩闈?闈㈠叡闈紝鎴栬搴曢潰璐村悎鍩哄噯闈€?    /// </summary>
    MateOperationResult AddMateCoincident(MateAlign align = MateAlign.Closest);

    /// <summary>
    /// Add a Concentric mate between the two currently-selected entities.
    /// 瀵瑰綋鍓嶅凡缁忛€変腑鐨勪袱涓渾鏌遍潰鎴栧渾杈规坊鍔犲悓蹇冮厤鍚堛€?    /// </summary>
    MateOperationResult AddMateConcentric(MateAlign align = MateAlign.Closest);

    /// <summary>
    /// Add a Parallel mate between the two currently-selected entities.
    /// 瀵瑰綋鍓嶅凡缁忛€変腑鐨勪袱涓钩闈€侀潰鎴栬竟娣诲姞骞宠閰嶅悎銆?    /// </summary>
    MateOperationResult AddMateParallel(MateAlign align = MateAlign.Closest);

    /// <summary>
    /// Add a Distance mate between the two currently-selected entities.
    /// 瀵瑰綋鍓嶅凡缁忛€変腑鐨勪袱涓疄浣撴坊鍔犺窛绂婚厤鍚堬紝璺濈鍗曚綅涓虹背銆?    /// </summary>
    MateOperationResult AddMateDistance(double distance, MateAlign align = MateAlign.Closest);

    /// <summary>
    /// Add an Angle mate between the two currently-selected entities.
    /// 瀵瑰綋鍓嶅凡缁忛€変腑鐨勪袱涓钩闈㈠疄浣撴坊鍔犺搴﹂厤鍚堬紝浼犲叆瑙掑害鍗曚綅涓哄害銆?    /// </summary>
    MateOperationResult AddMateAngle(double angleDegrees, MateAlign align = MateAlign.Closest);

    /// <summary>
    /// List all top-level components in the active assembly.
    /// 鍒楀嚭褰撳墠娲诲姩瑁呴厤浣撶殑椤跺眰缁勪欢瀹炰緥锛屼笉閫掑綊杩涘叆瀛愯閰嶄綋銆?    /// </summary>
    IReadOnlyList<ComponentInfo> ListComponents();

    /// <summary>
    /// Suppress every direct child of the active assembly except the exact component
    /// instance names in <paramref name="keepComponentNames"/>. This preserves the
    /// source-context component instances and their internal configuration state.
    /// </summary>
    TopLevelComponentIsolationResult SuppressTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true);

    /// <summary>
    /// Hide every non-target direct child while keeping dependencies and component
    /// suppression states unchanged. This is the safe fallback for context assemblies
    /// where suppressing a driver component also suppresses requested modules.
    /// </summary>
    TopLevelComponentVisibilityIsolationResult HideTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true);

    /// <summary>
    /// List all component instances in the active assembly by recursively traversing subassemblies.
    /// 閫掑綊鍒楀嚭褰撳墠娲诲姩瑁呴厤浣撲腑鐨勬墍鏈夌粍浠跺疄渚嬶紝骞惰繑鍥炲眰绾ц矾寰勶紝閫傚悎澶勭悊宓屽瀛愯閰嶄綋銆?    /// </summary>
    IReadOnlyList<ComponentInstanceInfo> ListComponentsRecursive();

    IReadOnlyList<ComponentPoseInfo> ListComponentPoses(bool topLevelOnly = true);

    /// <summary>
    /// List the pose of one exact top-level component and only its descendants.
    /// This avoids traversing unrelated modules in large production assemblies.
    /// </summary>
    IReadOnlyList<ComponentPoseInfo> ListTopLevelComponentSubtreePoses(string hierarchyPath);

    ComponentSolvingStateResult SetTopLevelComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true);

    ComponentSolvingStateResult SetComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true);

    ResolveLightweightComponentsResult ResolveAllLightweightComponents(
        bool warnIfNotResolved = false,
        bool rebuild = true);

    /// <summary>
    /// Resolve one exact component instance in the active assembly using name, hierarchy path, path, or any combination.
    /// 鏍规嵁缁勪欢鍚嶃€佸眰绾ц矾寰勬垨婧愭枃浠惰矾寰勮В鏋愬敮涓€缁勪欢瀹炰緥锛涚敤浜庡湪鎿嶄綔鍓嶆秷闄ゅ悓鍚?澶嶇敤缁勪欢姝т箟銆?    /// </summary>
    AssemblyTargetResolutionResult ResolveComponentTarget(
        string? componentName = null,
        string? hierarchyPath = null,
        string? componentPath = null);

    /// <summary>
    /// Analyze how many placements would change if the resolved component's source file were edited directly.
    /// 鍒嗘瀽鐩存帴缂栬緫鐩爣缁勪欢婧愭枃浠朵細褰卞搷澶氬皯涓疄渚嬶紱鐢ㄤ簬鍒ゆ柇鍏变韩闆朵欢/瀛愯閰嶄綋鏄惁闇€瑕佸厛鏇挎崲鍗曞疄渚嬪啀缂栬緫銆?    /// </summary>
    SharedPartEditImpactResult AnalyzeSharedPartEditImpact(
        string? componentName = null,
        string? hierarchyPath = null,
        string? componentPath = null);

    /// <summary>
    /// Inspect top-level assembly mates and export only the face-based basic mates whose endpoints
    /// belong to the two requested module instances. The active source assembly is never modified.
    /// </summary>
    AssemblyMatePairExportResult ExportMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string? outputPath = null,
        bool saveJson = true);

    /// <summary>
    /// Rank module pairs that have directly rebuildable face-based basic mates in the source assembly.
    /// This is the safe fallback when the preferred pair has no direct mate.
    /// </summary>
    AssemblyMatePairCandidateResult FindMatePairCandidates(
        string sourceAssemblyPath,
        IReadOnlyList<string>? allowedModuleTokens = null,
        int maxResults = 10);

    /// <summary>
    /// Create an independent two-module assembly, rebuild the exported pair mates, save/reopen it,
    /// and verify the mate types and endpoint ownership. The source assembly remains read-only.
    /// </summary>
    AssemblyMatePairRoundTripResult RoundTripMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string outputAssemblyPath,
        string? exportJsonPath = null,
        bool allowAutomaticFallback = true,
        IReadOnlyList<string>? allowedModuleTokens = null);

    /// <summary>
    /// Export all binary inter-module top-level mate features for the requested module subtrees,
    /// preserving endpoint geometry identity and grouping the relations into module-pair bundles.
    /// The source assembly is opened read-only from the tool's point of view and is never modified.
    /// </summary>
    AssemblyModuleMateGraphResult ExportModuleMateGraph(
        string sourceAssemblyPath,
        IReadOnlyList<string>? moduleTokens = null,
        string? outputPath = null,
        bool saveJson = true);

    /// <summary>
    /// Read top-level mate types, participating components, and advanced options without resolving
    /// endpoint faces or persistent references.
    /// </summary>
    AssemblyTopLevelMateAuditResult AuditTopLevelMateFeatures(
        string sourceAssemblyPath,
        string? outputPath = null,
        bool saveJson = true);

    /// <summary>Update one named top-level Slot mate in an explicitly supplied assembly copy.</summary>
    AssemblySlotMateUpdateResult UpdateTopLevelSlotMate(
        string assemblyPath,
        string mateName,
        int constraint,
        double distance = 0,
        double percent = 0,
        bool flipDirection = false,
        bool save = true);

    /// <summary>
    /// Enumerate reusable face endpoints independently of existing mate features.
    /// </summary>
    AssemblyFaceEndpointCatalogResult BuildFaceEndpointCatalog(
        string sourceAssemblyPath,
        IReadOnlyList<string> moduleTokens,
        string? outputPath = null,
        bool sourceMateFacesOnly = true,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        bool saveJson = true);

    /// <summary>
    /// Enumerate reusable face endpoints from one uniquely selected leaf component only.
    /// </summary>
    AssemblyFaceEndpointCatalogResult BuildLeafFaceEndpointCatalog(
        string sourceAssemblyPath,
        string moduleToken,
        string leafSelector,
        string? outputPath = null,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        int maximumFaceCount = 500,
        bool saveJson = true);

    /// <summary>Select and optionally zoom to one endpoint from a saved catalog.</summary>
    AssemblyFaceEndpointSelectionResult SelectFaceEndpointFromCatalog(
        string catalogPath,
        string endpointId,
        bool zoomToSelection = true);

    /// <summary>
    /// Capture the first face selected in the active assembly as a reusable endpoint entry.
    /// </summary>
    AssemblyFaceEndpointCatalogEntry CaptureSelectedFaceEndpoint(string moduleToken);

    /// <summary>
    /// Rebuild the complete exported module-level mate graph in a new assembly using one of three
    /// controlled initial-placement modes, then save/reopen and compare every module pose.
    /// </summary>
    AssemblyModuleMateReconstructionExperimentResult RunModuleMateReconstructionExperiment(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        string mode,
        string baseModuleToken = "A600",
        IReadOnlyList<string>? moduleTokens = null,
        IReadOnlyList<string>? residualAnchorModuleSelectors = null,
        double poseToleranceMeters = 1e-5,
        double rotationTolerance = 1e-6);

    /// <summary>
    /// Create a new assembly from a compiled editable mate-graph JSON without re-reading the
    /// prototype mate tree, then save/reopen and verify mate types and scalar parameters.
    /// </summary>
    AssemblyEditableMateGraphReconstructionResult RebuildAssemblyFromMateGraph(
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string? baseModuleToken = null,
        string? initialPlacementMode = null);

    AssemblyContextMateGraphReconstructionResult RemateComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false,
        bool forceInitialDisplacement = false);

    /// <summary>
    /// Measure validation-only relations in an existing saved checkpoint without
    /// rebuilding mates or saving a CAD document.
    /// </summary>
    AssemblyContextRelationVerificationResult VerifyRelationsInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false);

    /// <summary>
    /// Copy an existing assembly context, remove the original target instance, insert a fresh
    /// instance from its independent module file, and locate it from the effective mate graph.
    /// </summary>
    AssemblyContextIncrementalInsertResult InsertComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken);

    /// <summary>
    /// Copy a solved parent assembly, retain only the requested top-level component source files,
    /// and save/reopen the result as an explicitly static context snapshot.  This preserves the
    /// parent-context checkpoint for geometry review without claiming kinematic reconstruction.
    /// </summary>
    AssemblyStaticContextSubsetResult CreateAssemblyStaticContextSubset(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        IReadOnlyList<string> keepComponentPaths);

    /// <summary>
    /// Run a static interference check for the active assembly or a subset of component instances.
    /// This follows the official ToolsCheckInterference2 workflow and temporarily changes the SolidWorks selection set.
    /// 瀵规暣涓椿鍔ㄨ閰嶄綋鎴栨寚瀹氱粍浠堕泦鍚堟墽琛岄潤鎬佸共娑夋鏌ワ紱璋冪敤鏈熼棿浼氫复鏃舵敼鍙?SolidWorks 褰撳墠閫夋嫨闆嗐€?    /// </summary>
    AssemblyInterferenceCheckResult CheckInterference(
        IReadOnlyList<string>? hierarchyPaths = null,
        bool treatCoincidenceAsInterference = false);

    /// <summary>
    /// Check exactly two module instances by expanding them to leaf solid bodies, transforming body
    /// copies into the active assembly coordinate system, applying an AABB broad phase, and running
    /// the SolidWorks modeler B-Rep check for every surviving body pair.
    /// </summary>
    LeafBodyInterferenceCheckResult CheckInterferenceByLeafBodies(
        IReadOnlyList<string> hierarchyPaths,
        bool treatCoincidenceAsInterference = false);

    /// <summary>
    /// Capture every transformed leaf solid-body AABB below one resolved module instance.
    /// This is a read-only geometry extraction used to build conservative multi-box occupancy models.
    /// </summary>
    LeafBodyEnvelopeCaptureResult CaptureLeafBodyEnvelopes(string hierarchyPath);

    /// <summary>
    /// Replace a top-level component instance in the active assembly with another model file.
    /// 灏嗘椿鍔ㄨ閰嶄綋涓殑椤跺眰缁勪欢瀹炰緥鏇挎崲涓哄彟涓€涓浂浠舵垨瑁呴厤浣撴枃浠讹紱宓屽缁勪欢闇€鍏堟墦寮€鍏舵墍灞炲瓙瑁呴厤浣撳啀鏇挎崲銆?    /// </summary>
    AssemblyComponentReplacementResult ReplaceComponent(
        string hierarchyPath,
        string replacementFilePath,
        string configName = "",
        bool replaceAllInstances = false,
        int useConfigChoice = (int)swReplaceComponentsConfiguration_e.swReplaceComponentsConfiguration_MatchName,
        bool reattachMates = true);

    /// <summary>
    /// Traverse the active assembly's FeatureManager tree exactly as shown in the UI, including nested component
    /// and subassembly nodes, without opening each child document.
    /// </summary>
    AssemblyFeatureTreeTraversalResult TraverseAssemblyFeatureTrees();

    /// <summary>
    /// Search the active assembly's visible FeatureManager tree and return candidate feature/component matches
    /// with enough context for the user to confirm the correct child document before editing.
    /// </summary>
    AssemblyFeatureSearchResult SearchAssemblyFeatureTrees(string query, bool exactNameOnly = false, int maxResults = 200);

    /// <summary>
    /// Open one confirmed component source document for editing by exact source path.
    /// </summary>
    OpenComponentForEditingResult OpenComponentForEditing(string componentPath, string? hierarchyPath = null);

}

/// <summary>
/// Implements <see cref="IAssemblyService"/> via SolidWorks IAssemblyDoc COM API.
/// </summary>
public partial class AssemblyService : IAssemblyService
{
    // SolidWorks reports assembly geometry in metres.  Keep the broad-phase
    // shortcut conservative so numerical noise or a nominally touching pair
    // still reaches the exact interference API.
    internal const double InterferenceAabbSeparationTolerance = 1e-6;

    private const int RpcServerFault = unchecked((int)0x80010105);

    private sealed record WorldSpaceSolidBody(
        IBody2 Body,
        ComponentInstanceInfo Component,
        int BodyIndex,
        double[] BoundingBox,
        string BoundingBoxSource);

    private readonly ISwConnectionManager _cm;

    public AssemblyService(ISwConnectionManager cm)
    {
        _cm = cm ?? throw new ArgumentNullException(nameof(cm));
    }

    public ComponentInfo InsertComponent(string filePath, double x = 0, double y = 0, double z = 0)
    {
        if (string.IsNullOrWhiteSpace(filePath))
            throw new ArgumentException("filePath must not be empty", nameof(filePath));
        if (!File.Exists(filePath))
            throw new FileNotFoundException($"Component file was not found: {filePath}", filePath);

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var assyDoc = (IModelDoc2)assy;
        var assyPath = assyDoc.GetPathName();
        var assyTitle = assyDoc.GetTitle();

        // For a saved standalone part, let SolidWorks resolve the model's active/default
        // configuration instead of forcing an existing selected config in the target assembly.
        var comp = assy.AddComponent5(filePath, 0, "", false, "", x, y, z) as IComponent2;
        if (comp == null)
        {
            var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks not connected");
            swApp.OpenDoc(filePath);
            if (!string.IsNullOrWhiteSpace(assyPath))
            {
                swApp.ActivateDoc(assyPath);
            }
            else if (!string.IsNullOrWhiteSpace(assyTitle))
            {
                swApp.ActivateDocByTitle(assyTitle);
            }
            comp = assy.AddComponent5(filePath, 0, "", false, "", x, y, z) as IComponent2;
        }

        if (comp == null)
        {
            throw new InvalidOperationException($"Failed to insert component: {filePath}");
        }

        return new ComponentInfo(comp.Name2, comp.GetPathName());
    }

    public ComponentInfo RenameComponent(string currentName, string newName)
    {
        if (string.IsNullOrWhiteSpace(currentName))
            throw new ArgumentException("currentName must not be empty", nameof(currentName));
        if (string.IsNullOrWhiteSpace(newName))
            throw new ArgumentException("newName must not be empty", nameof(newName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var instances = EnumerateComponentInstances(assy);
        var target = instances.FirstOrDefault(i =>
            string.Equals(i.Info.Name, currentName, StringComparison.OrdinalIgnoreCase));
        if (target == null)
        {
            throw new InvalidOperationException($"Component '{currentName}' not found");
        }

        target.Component.Name2 = newName.Trim();
        return new ComponentInfo(target.Component.Name2, target.Component.GetPathName());
    }


    public ComponentTransformResult MoveComponent(
        string componentName,
        double deltaX,
        double deltaY,
        double deltaZ,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        // Transform-heavy replay calls this method once per top-level process module. Resolve the
        // named component directly first so we do not recursively call IComponent2.GetChildren()
        // for the complete assembly before every Transform2 write. Repeated full-tree traversal is
        // both expensive and, on large assemblies, can destabilize the SolidWorks COM server after
        // several successful component moves. Keep the recursive lookup as a compatibility fallback
        // for callers that target a nested component.
        var target = ResolveComponentForTransform(assy, componentName);

        if (target == null)
        {
            return new ComponentTransformResult(
                false,
                $"Component '{componentName}' not found",
                componentName,
                null);
        }

        var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks not connected");
        var mathUtil = swApp.GetMathUtility();

        // SolidWorks CreateTransform array layout (16 elements):
        // [R11,R12,R13, R21,R22,R23, R31,R32,R33, Tx,Ty,Tz, Scale, 0,0,0]
        double[] translationData =
        [
            1, 0, 0,
            0, 1, 0,
            0, 0, 1,
            deltaX, deltaY, deltaZ,
            1,
            0, 0, 0,
        ];

        var translationTransform = (IMathTransform)mathUtil.CreateTransform((object)translationData);

        // currentTransform 脳 translationTransform: offset in world space then restore orientation.
        var current = target.Component.Transform2;
        target.Component.Transform2 = (current != null
            ? current.Multiply(translationTransform)
            : translationTransform) as MathTransform;

        if (rebuild)
        {
            var doc = (IModelDoc2)assy;
            doc.EditRebuild3();
        }

        return new ComponentTransformResult(
            true,
            $"Moved component '{componentName}' by ({deltaX}, {deltaY}, {deltaZ}) meters",
            target.Info.Name,
            target.Info.HierarchyPath);
    }

    public ComponentTransformResult RotateComponent(
        string componentName,
        double axisX,
        double axisY,
        double axisZ,
        double angleDegrees,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        var target = ResolveComponentForTransform(assy, componentName);

        if (target == null)
        {
            return new ComponentTransformResult(
                false,
                $"Component '{componentName}' not found",
                componentName,
                null);
        }

        var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks not connected");
        var mathUtil = swApp.GetMathUtility();

        double angleRad = angleDegrees * Math.PI / 180.0;
        double c = Math.Cos(angleRad), s = Math.Sin(angleRad);

        // Normalize axis
        double len = Math.Sqrt(axisX * axisX + axisY * axisY + axisZ * axisZ);
        if (len < 1e-10)
            throw new ArgumentException("Rotation axis vector must not be zero.");
        double ux = axisX / len, uy = axisY / len, uz = axisZ / len;

        // Rodrigues rotation matrix
        double[] rotData =
        [
            c + ux*ux*(1-c),    ux*uy*(1-c) - uz*s, ux*uz*(1-c) + uy*s,
            uy*ux*(1-c) + uz*s, c + uy*uy*(1-c),    uy*uz*(1-c) - ux*s,
            uz*ux*(1-c) - uy*s, uz*uy*(1-c) + ux*s, c + uz*uz*(1-c),
            0, 0, 0,  // no translation
            1,        // scale
            0, 0, 0,
        ];

        var rotTransform = (IMathTransform)mathUtil.CreateTransform((object)rotData);
        var currentRot = target.Component.Transform2;
        target.Component.Transform2 = (currentRot != null
            ? currentRot.Multiply(rotTransform)
            : rotTransform) as MathTransform;

        if (rebuild)
        {
            var doc = (IModelDoc2)assy;
            doc.EditRebuild3();
        }

        return new ComponentTransformResult(
            true,
            $"Rotated component '{componentName}' around ({axisX},{axisY},{axisZ}) by {angleDegrees}掳",
            target.Info.Name,
            target.Info.HierarchyPath);
    }

    public ComponentTransformResult SetComponentOrientation(
        string componentName,
        IReadOnlyList<double> xAxis,
        IReadOnlyList<double> yAxis,
        IReadOnlyList<double> zAxis,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));

        var x = NormalizeOrientationAxis(xAxis, nameof(xAxis));
        var y = NormalizeOrientationAxis(yAxis, nameof(yAxis));
        var z = NormalizeOrientationAxis(zAxis, nameof(zAxis));
        if (Math.Abs(Dot(x, y)) > 1e-6 || Math.Abs(Dot(x, z)) > 1e-6 || Math.Abs(Dot(y, z)) > 1e-6)
            throw new ArgumentException("Orientation axes must be mutually perpendicular.");
        var handedness = Dot(Cross(x, y), z);
        if (handedness < 0.999999)
            throw new ArgumentException("Orientation axes must form a right-handed frame.");

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var target = ResolveComponentForTransform(assy, componentName);
        if (target == null)
        {
            return new ComponentTransformResult(
                false,
                $"Component '{componentName}' not found",
                componentName,
                null);
        }

        var current = target.Component.Transform2;
        var currentData = current?.ArrayData as double[];
        if (currentData == null || currentData.Length < 13)
        {
            return new ComponentTransformResult(
                false,
                $"Component '{componentName}' has no readable Transform2.",
                target.Info.Name,
                target.Info.HierarchyPath);
        }

        double[] targetData =
        [
            x[0], x[1], x[2],
            y[0], y[1], y[2],
            z[0], z[1], z[2],
            currentData[9], currentData[10], currentData[11],
            currentData[12],
            0, 0, 0,
        ];
        var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks not connected");
        var mathUtil = swApp.GetMathUtility();
        target.Component.Transform2 = (MathTransform)mathUtil.CreateTransform((object)targetData);

        if (rebuild)
            ((IModelDoc2)assy).EditRebuild3();

        return new ComponentTransformResult(
            true,
            $"Set component '{componentName}' to the requested full world-space orientation.",
            target.Info.Name,
            target.Info.HierarchyPath);
    }

    public ComponentTransformResult SetComponentTransform(
        string componentName,
        IReadOnlyList<double> transform,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));
        if (transform is null || transform.Count != 16)
            throw new ArgumentException("transform must contain exactly 16 Transform2 values.", nameof(transform));
        if (transform.Any(value => double.IsNaN(value) || double.IsInfinity(value)))
            throw new ArgumentException("transform values must be finite.", nameof(transform));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var target = ResolveComponentForTransform(assy, componentName);
        if (target is null)
        {
            return new ComponentTransformResult(
                false,
                $"Component '{componentName}' not found",
                componentName,
                null);
        }

        var swApp = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks not connected");
        var mathUtil = swApp.GetMathUtility();
        target.Component.Transform2 = (MathTransform)mathUtil.CreateTransform((object)transform.ToArray());
        bool rebuildSucceeded = !rebuild || ((IModelDoc2)assy).EditRebuild3();

        return new ComponentTransformResult(
            rebuildSucceeded,
            rebuildSucceeded
                ? $"Set component '{componentName}' to the requested complete Transform2 matrix."
                : $"Set component '{componentName}' Transform2, but the assembly rebuild failed.",
            target.Info.Name,
            target.Info.HierarchyPath);
    }

    public ComponentReferencedConfigurationResult SetComponentReferencedConfiguration(
        string componentName,
        string configurationName,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));
        if (string.IsNullOrWhiteSpace(configurationName))
            throw new ArgumentException("configurationName must not be empty", nameof(configurationName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var target = ResolveComponentForTransform(assy, componentName)
            ?? throw new InvalidOperationException($"Component '{componentName}' not found.");

        string previous = target.Component.ReferencedConfiguration ?? string.Empty;
        target.Component.ReferencedConfiguration = configurationName;
        bool rebuildSucceeded = !rebuild || ((IModelDoc2)assy).EditRebuild3();
        string actual = target.Component.ReferencedConfiguration ?? string.Empty;
        bool success = rebuildSucceeded
            && string.Equals(actual, configurationName, StringComparison.OrdinalIgnoreCase);

        return new ComponentReferencedConfigurationResult(
            success,
            target.Info.Name,
            target.Info.HierarchyPath,
            previous,
            configurationName,
            actual,
            rebuild,
            rebuildSucceeded);
    }

    private static double[] NormalizeOrientationAxis(IReadOnlyList<double> axis, string parameterName)
    {
        if (axis == null || axis.Count < 3)
            throw new ArgumentException("Orientation axis must contain three values.", parameterName);
        var length = Math.Sqrt(axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2]);
        if (length < 1e-10)
            throw new ArgumentException("Orientation axis must not be zero.", parameterName);
        return [axis[0] / length, axis[1] / length, axis[2] / length];
    }

    private static double Dot(IReadOnlyList<double> first, IReadOnlyList<double> second)
        => first[0] * second[0] + first[1] * second[1] + first[2] * second[2];

    private static double[] Cross(IReadOnlyList<double> first, IReadOnlyList<double> second)
        =>
        [
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0],
        ];

    public IReadOnlyList<string> SuppressTopLevelMateFeatures()
    {
        _cm.EnsureConnected();
        var doc = (IModelDoc2)GetAssemblyDoc();
        var changed = new List<string>();
        foreach (var feature in EnumerateTopLevelMateFeatures(doc))
        {
            try
            {
                if (!feature.IsSuppressed()
                    && feature.SetSuppression((int)swFeatureSuppressionAction_e.swSuppressFeature))
                {
                    changed.Add(feature.Name);
                }
            }
            catch (COMException)
            {
                // Keep the operation best-effort; the caller receives only features that were actually changed.
            }
        }
        return changed.AsReadOnly();
    }

    public IReadOnlyList<string> RestoreTopLevelMateFeatures(IReadOnlyList<string> featureNames)
    {
        _cm.EnsureConnected();
        var doc = (IModelDoc2)GetAssemblyDoc();
        var requested = featureNames.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var restored = new List<string>();
        foreach (var feature in EnumerateTopLevelMateFeatures(doc))
        {
            if (!requested.Contains(feature.Name))
            {
                continue;
            }
            try
            {
                if (feature.IsSuppressed()
                    && feature.SetSuppression((int)swFeatureSuppressionAction_e.swUnSuppressFeature))
                {
                    restored.Add(feature.Name);
                }
            }
            catch (COMException)
            {
            }
        }
        return restored.AsReadOnly();
    }

    public MateOperationResult AddMateCoincident(MateAlign align = MateAlign.Closest)
        => AddMate(MateType.Coincident, align);

    public MateOperationResult AddMateConcentric(MateAlign align = MateAlign.Closest)
        => AddMate(MateType.Concentric, align);

    public MateOperationResult AddMateParallel(MateAlign align = MateAlign.Closest)
        => AddMate(MateType.Parallel, align);

    public MateOperationResult AddMateDistance(double distance, MateAlign align = MateAlign.Closest)
        => AddMate(MateType.Distance, align, distance: distance);

    public MateOperationResult AddMateAngle(double angleDegrees, MateAlign align = MateAlign.Closest)
        => AddMate(MateType.Angle, align, angle: angleDegrees * Math.PI / 180.0);

    public IReadOnlyList<ComponentInfo> ListComponents()
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        var raw = assy.GetComponents(true) as object[]
            ?? [];

        return raw
            .OfType<IComponent2>()
            .Select(c => new ComponentInfo(c.Name2, c.GetPathName()))
            .ToList()
            .AsReadOnly();
    }

    public IReadOnlyList<ComponentInstanceInfo> ListComponentsRecursive()
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        var instances = EnumerateComponentInstances(assy)
            .Select(instance => instance.Info)
            .ToList();

        return instances.AsReadOnly();
    }

    public IReadOnlyList<ComponentPoseInfo> ListComponentPoses(bool topLevelOnly = true)
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        if (topLevelOnly)
        {
            // Do not recursively enumerate every leaf and filter afterwards.  Large
            // production modules can contain thousands of descendants, while layout
            // broad-phase validation only needs the direct children of the active
            // assembly.  PairEnumerateTopLevelInstances performs that bounded query.
            return PairEnumerateTopLevelInstances(assy)
                .Select(instance => ToComponentPoseInfo(instance.Component, instance.Info))
                .ToList()
                .AsReadOnly();
        }

        return EnumerateComponentInstances(assy)
            .Select(instance => ToComponentPoseInfo(instance.Component, instance.Info))
            .ToList()
            .AsReadOnly();
    }

    public IReadOnlyList<ComponentPoseInfo> ListTopLevelComponentSubtreePoses(string hierarchyPath)
    {
        if (string.IsNullOrWhiteSpace(hierarchyPath))
            throw new ArgumentException("hierarchyPath must not be empty.", nameof(hierarchyPath));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var matches = PairEnumerateTopLevelInstances(assy)
            .Where(instance =>
                string.Equals(instance.Info.HierarchyPath, hierarchyPath, StringComparison.OrdinalIgnoreCase)
                || string.Equals(instance.Info.Name, hierarchyPath, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (matches.Count != 1)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IAssemblyDoc.GetComponents",
                "The requested top-level component must resolve to exactly one instance.",
                new Dictionary<string, object?>
                {
                    ["hierarchyPath"] = hierarchyPath,
                    ["resolvedInstanceCount"] = matches.Count,
                });
        }

        var instances = new List<ComponentInstance> { matches[0] };
        PairTraverseModuleSubtree(
            matches[0].Component,
            matches[0].Info.HierarchyPath,
            matches[0].Info.Depth,
            instances);
        return instances
            .Select(instance => ToComponentPoseInfo(instance.Component, instance.Info))
            .ToList()
            .AsReadOnly();
    }

    public TopLevelComponentIsolationResult SuppressTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true)
    {
        if (keepComponentNames == null || keepComponentNames.Count == 0)
            throw new ArgumentException("At least one top-level component name must be kept.", nameof(keepComponentNames));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var components = (assy.GetComponents(true) as object[] ?? [])
            .OfType<IComponent2>()
            .ToList();
        var requested = keepComponentNames
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var actualNames = components
            .Select(component => component.Name2)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var missing = requested
            .Where(name => !actualNames.Contains(name))
            .ToList();

        // Preflight all requested names before changing the document. A typo must
        // not accidentally suppress a module that the caller intended to preserve.
        if (missing.Count > 0)
        {
            return new TopLevelComponentIsolationResult(
                false,
                requested.AsReadOnly(),
                [],
                [],
                [],
                missing.AsReadOnly(),
                [],
                components.Where(component => !component.IsSuppressed())
                    .Select(component => component.Name2)
                    .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
                    .ToList()
                    .AsReadOnly());
        }

        var keep = requested.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var kept = new List<string>();
        var suppressed = new List<string>();
        var alreadySuppressed = new List<string>();
        var failed = new List<string>();
        foreach (var component in components)
        {
            if (keep.Contains(component.Name2))
            {
                kept.Add(component.Name2);
                continue;
            }
            if (component.IsSuppressed())
            {
                alreadySuppressed.Add(component.Name2);
                continue;
            }

            try
            {
                component.SetSuppression2((int)swComponentSuppressionState_e.swComponentSuppressed);
                if (component.IsSuppressed())
                    suppressed.Add(component.Name2);
                else
                    failed.Add(component.Name2);
            }
            catch (COMException)
            {
                failed.Add(component.Name2);
            }
        }

        if (rebuild)
            ((IModelDoc2)assy).EditRebuild3();

        var remainingResolved = components
            .Where(component => !component.IsSuppressed())
            .Select(component => component.Name2)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var success = failed.Count == 0
            && remainingResolved.Count == requested.Count
            && remainingResolved.All(keep.Contains);
        return new TopLevelComponentIsolationResult(
            success,
            requested.AsReadOnly(),
            kept.OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList().AsReadOnly(),
            suppressed.OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList().AsReadOnly(),
            alreadySuppressed.OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList().AsReadOnly(),
            missing.AsReadOnly(),
            failed.OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList().AsReadOnly(),
            remainingResolved.AsReadOnly());
    }

    public TopLevelComponentVisibilityIsolationResult HideTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true)
    {
        if (keepComponentNames == null || keepComponentNames.Count == 0)
            throw new ArgumentException("At least one top-level component name must be kept.", nameof(keepComponentNames));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var components = (assy.GetComponents(true) as object[] ?? [])
            .OfType<IComponent2>()
            .ToList();
        var requested = keepComponentNames
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var actualNames = components.Select(component => component.Name2)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var missing = requested.Where(name => !actualNames.Contains(name)).ToList();
        if (missing.Count > 0)
        {
            return new TopLevelComponentVisibilityIsolationResult(
                false, requested.AsReadOnly(), [], [], missing.AsReadOnly(), [], []);
        }

        var keep = requested.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var failed = new List<string>();
        foreach (var component in components)
        {
            try
            {
                component.Visible = keep.Contains(component.Name2)
                    ? (int)swComponentVisibilityState_e.swComponentVisible
                    : (int)swComponentVisibilityState_e.swComponentHidden;
            }
            catch (COMException)
            {
                failed.Add(component.Name2);
            }
        }
        if (rebuild)
            ((IModelDoc2)assy).EditRebuild3();

        var visible = components
            .Where(component => component.Visible == (int)swComponentVisibilityState_e.swComponentVisible)
            .Select(component => component.Name2)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var hidden = components
            .Where(component => component.Visible != (int)swComponentVisibilityState_e.swComponentVisible)
            .Select(component => component.Name2)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var suppressedKeep = components
            .Where(component => keep.Contains(component.Name2) && component.IsSuppressed())
            .Select(component => component.Name2)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();
        // Visibility isolation is intentionally independent of suppression state.
        // Some Project02 source-context instances report IsSuppressed=true while
        // remaining graphically visible and pose-addressable (for example patterned
        // or cached-context instances). Exact geometry availability is validated by
        // the downstream pose/B-Rep gates, not inferred here from that flag alone.
        var success = failed.Count == 0
            && visible.Count == requested.Count
            && visible.All(keep.Contains);
        return new TopLevelComponentVisibilityIsolationResult(
            success,
            requested.AsReadOnly(),
            visible.AsReadOnly(),
            hidden.AsReadOnly(),
            missing.AsReadOnly(),
            suppressedKeep.AsReadOnly(),
            failed.OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList().AsReadOnly());
    }

    public AssemblyTargetResolutionResult ResolveComponentTarget(
        string? componentName = null,
        string? hierarchyPath = null,
        string? componentPath = null)
    {
        ValidateTargetCriteria(componentName, hierarchyPath, componentPath);

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var activeAssemblyPath = NormalizeCriteria(((IModelDoc2)assy).GetPathName());
        var instances = EnumerateComponentInstances(assy);

        return ResolveComponentTargetCore(instances, activeAssemblyPath, componentName, hierarchyPath, componentPath);
    }

    public ComponentSolvingStateResult SetTopLevelComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true)
        => SetComponentSolvingStateCore(hierarchyPath, solvingState, rebuild, topLevelOnly: true);

    public ComponentSolvingStateResult SetComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true)
        => SetComponentSolvingStateCore(hierarchyPath, solvingState, rebuild, topLevelOnly: false);

    private ComponentSolvingStateResult SetComponentSolvingStateCore(
        string hierarchyPath,
        int solvingState,
        bool rebuild,
        bool topLevelOnly)
    {
        if (string.IsNullOrWhiteSpace(hierarchyPath))
            throw new ArgumentException("hierarchyPath must not be empty.", nameof(hierarchyPath));
        if (!Enum.IsDefined(typeof(swComponentSolvingOption_e), solvingState))
            throw new ArgumentOutOfRangeException(nameof(solvingState), solvingState, "Unknown component solving state.");

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var doc = (IModelDoc2)assy;
        var matches = EnumerateComponentInstances(assy)
            .Where(instance => !topLevelOnly || instance.Info.Depth == 0)
            .Where(instance =>
                string.Equals(instance.Info.HierarchyPath, hierarchyPath, StringComparison.OrdinalIgnoreCase)
                || string.Equals(instance.Info.Name, hierarchyPath, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (matches.Count != 1)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IAssemblyDoc.CompConfigProperties5",
                topLevelOnly
                    ? "The requested top-level component must resolve to exactly one instance."
                    : "The requested component hierarchy path must resolve to exactly one instance.",
                new Dictionary<string, object?>
                {
                    ["hierarchyPath"] = hierarchyPath,
                    ["resolvedInstanceCount"] = matches.Count,
                });
        }

        var target = matches[0];
        var component = target.Component;
        int previous = component.Solving;
        string referencedConfiguration = component.ReferencedConfiguration ?? string.Empty;
        int suppression = component.GetSuppression();
        if (suppression == (int)swComponentSuppressionState_e.swComponentLightweight)
            suppression = (int)swComponentSuppressionState_e.swComponentFullyResolved;
        bool visible = component.Visible == (int)swComponentVisibilityState_e.swComponentVisible;
        bool excludeFromBom;
        bool isEnvelope;
        try { excludeFromBom = component.ExcludeFromBOM; } catch { excludeFromBom = false; }
        try { isEnvelope = component.IsEnvelope(); } catch { isEnvelope = false; }

        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("Selection manager is not available for the active assembly.");
        doc.ClearSelection2(true);
        bool changed;
        try
        {
            var selectData = (SelectData)selectionManager.CreateSelectData();
            if (!component.Select4(false, selectData, false))
                throw new InvalidOperationException($"Failed to select component '{hierarchyPath}'.");
            changed = assy.CompConfigProperties5(
                suppression,
                solvingState,
                visible,
                true,
                referencedConfiguration,
                excludeFromBom,
                isEnvelope);
        }
        finally
        {
            doc.ClearSelection2(true);
        }

        bool rebuildSucceeded = !rebuild || doc.EditRebuild3();
        int actual = component.Solving;
        return new ComponentSolvingStateResult(
            changed && actual == solvingState && rebuildSucceeded,
            target.Info.Name,
            target.Info.HierarchyPath,
            referencedConfiguration,
            previous,
            ((swComponentSolvingOption_e)previous).ToString(),
            solvingState,
            ((swComponentSolvingOption_e)solvingState).ToString(),
            actual,
            ((swComponentSolvingOption_e)actual).ToString(),
            rebuild,
            rebuildSucceeded);
    }

    public ResolveLightweightComponentsResult ResolveAllLightweightComponents(
        bool warnIfNotResolved = false,
        bool rebuild = true)
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var doc = (IModelDoc2)assy;
        int rawResolveCode = assy.ResolveAllLightWeightComponents(warnIfNotResolved);
        bool rebuildSucceeded = !rebuild || doc.EditRebuild3();
        return new ResolveLightweightComponentsResult(
            rawResolveCode == 0 && rebuildSucceeded,
            rawResolveCode,
            warnIfNotResolved,
            rebuild,
            rebuildSucceeded);
    }

    public SharedPartEditImpactResult AnalyzeSharedPartEditImpact(
        string? componentName = null,
        string? hierarchyPath = null,
        string? componentPath = null)
    {
        ValidateTargetCriteria(componentName, hierarchyPath, componentPath);

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var activeAssemblyPath = NormalizeCriteria(((IModelDoc2)assy).GetPathName());
        var instances = EnumerateComponentInstances(assy);
        var resolution = ResolveComponentTargetCore(instances, activeAssemblyPath, componentName, hierarchyPath, componentPath);

        if (!resolution.IsResolved || resolution.ResolvedInstance == null)
        {
            return new SharedPartEditImpactResult(
                resolution,
                SourceFilePath: null,
                AffectedInstanceCount: 0,
                AffectedInstances: Array.Empty<ComponentInstanceInfo>(),
                SafeDirectEdit: false,
                RecommendedAction: resolution.IsAmbiguous ? "resolve_target_ambiguity" : "resolve_target_first");
        }

        var sourceFilePath = NormalizeCriteria(resolution.ResolvedInstance.Path);
        if (sourceFilePath == null)
        {
            return new SharedPartEditImpactResult(
                resolution,
                SourceFilePath: null,
                AffectedInstanceCount: 1,
                AffectedInstances: new[] { resolution.ResolvedInstance },
                SafeDirectEdit: false,
                RecommendedAction: "review_manually_missing_source_file");
        }

        var affectedInstances = instances
            .Where(instance => string.Equals(instance.Info.Path, sourceFilePath, StringComparison.OrdinalIgnoreCase))
            .Select(instance => instance.Info)
            .ToList()
            .AsReadOnly();

        bool safeDirectEdit = affectedInstances.Count == 1;

        return new SharedPartEditImpactResult(
            resolution,
            SourceFilePath: sourceFilePath,
            AffectedInstanceCount: affectedInstances.Count,
            AffectedInstances: affectedInstances,
            SafeDirectEdit: safeDirectEdit,
            RecommendedAction: safeDirectEdit ? "safe_direct_edit" : "replace_single_instance_before_edit");
    }

    public AssemblyInterferenceCheckResult CheckInterference(
        IReadOnlyList<string>? hierarchyPaths = null,
        bool treatCoincidenceAsInterference = false)
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var doc = (IModelDoc2)assy;

        var instances = EnumerateComponentInstances(assy);
        var selectedInstances = SelectInstances(instances, hierarchyPaths);
        if (selectedInstances.Count == 0)
        {
            return new AssemblyInterferenceCheckResult(
                HasInterference: false,
                TreatCoincidenceAsInterference: treatCoincidenceAsInterference,
                CheckedComponentCount: 0,
                InterferingFaceCount: 0,
                InterferingComponents: Array.Empty<ComponentInstanceInfo>());
        }

        if (selectedInstances.Count == 2
            && AreBoundingBoxesSeparated(
                GetComponentBoundingBox(selectedInstances[0].Component),
                GetComponentBoundingBox(selectedInstances[1].Component),
                InterferenceAabbSeparationTolerance))
        {
            return new AssemblyInterferenceCheckResult(
                HasInterference: false,
                TreatCoincidenceAsInterference: treatCoincidenceAsInterference,
                CheckedComponentCount: selectedInstances.Count,
                InterferingFaceCount: 0,
                InterferingComponents: Array.Empty<ComponentInstanceInfo>());
        }

        try
        {
            try
            {
                return CheckInterferenceViaToolsCheckInterference2(
                    assy,
                    doc,
                    selectedInstances,
                    treatCoincidenceAsInterference);
            }
            catch (System.Runtime.InteropServices.COMException ex) when (ex.HResult == RpcServerFault)
            {
                return CheckInterferenceViaDetectionManager(
                    assy,
                    instances,
                    hierarchyPaths,
                    treatCoincidenceAsInterference);
            }
        }
        catch (System.Runtime.InteropServices.COMException ex)
        {
            throw SolidWorksApiErrorFactory.FromComException(
                "IAssemblyDoc.ToolsCheckInterference2",
                ex,
                new Dictionary<string, object?>
                {
                    ["requestedHierarchyPaths"] = hierarchyPaths == null ? null : string.Join(" | ", hierarchyPaths),
                    ["treatCoincidenceAsInterference"] = treatCoincidenceAsInterference,
                });
        }
        finally
        {
            doc.ClearSelection2(true);
        }
    }

    private AssemblyInterferenceCheckResult CheckInterferenceViaToolsCheckInterference2(
        IAssemblyDoc assy,
        IModelDoc2 doc,
        IReadOnlyList<ComponentInstance> selectedInstances,
        bool treatCoincidenceAsInterference)
    {
        doc.ClearSelection2(true);
        for (int index = 0; index < selectedInstances.Count; index++)
        {
            bool append = index > 0;
            if (!selectedInstances[index].Component.Select2(append, 0))
            {
                throw SolidWorksApiErrorFactory.FromValidationFailure(
                    "IComponent2.Select2",
                    $"Failed to select component '{selectedInstances[index].Info.HierarchyPath}' for interference checking.",
                    new Dictionary<string, object?>
                    {
                        ["hierarchyPath"] = selectedInstances[index].Info.HierarchyPath,
                        ["componentPath"] = selectedInstances[index].Info.Path,
                    });
            }
        }

        object checkedComponents = selectedInstances
            .Select(instance => WrapDispatchObject(instance.Component))
            .Cast<object>()
            .ToArray();
        object interferingComponentsRaw;
        object interferingFacesRaw;

        assy.ToolsCheckInterference2(
            selectedInstances.Count,
            checkedComponents,
            treatCoincidenceAsInterference,
            out interferingComponentsRaw,
            out interferingFacesRaw);

        var interferingComponents = (interferingComponentsRaw as object[] ?? Array.Empty<object>())
            .OfType<IComponent2>()
            .ToList();
        var interferingFaces = (interferingFacesRaw as object[] ?? Array.Empty<object>())
            .OfType<IFace2>()
            .ToList();

        var matchedInfos = new List<ComponentInstanceInfo>();
        int pairCount = Math.Min(interferingComponents.Count, interferingFaces.Count);
        for (int index = 0; index < pairCount; index++)
        {
            var componentInfos = selectedInstances
                .Where(instance => IsSameComponentInstance(instance.Component, interferingComponents[index]))
                .Select(instance => instance.Info)
                .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
                .ToList();

            matchedInfos.AddRange(componentInfos);
        }

        if (pairCount < interferingComponents.Count)
        {
            matchedInfos.AddRange(selectedInstances
                .Where(instance => interferingComponents.Skip(pairCount)
                    .Any(component => IsSameComponentInstance(instance.Component, component)))
                .Select(instance => instance.Info)
                .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase));
        }

        var interferingInfos = matchedInfos
            .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToList()
            .AsReadOnly();

        return new AssemblyInterferenceCheckResult(
            HasInterference: interferingInfos.Count > 0,
            TreatCoincidenceAsInterference: treatCoincidenceAsInterference,
            CheckedComponentCount: selectedInstances.Count,
            InterferingFaceCount: pairCount,
            InterferingComponents: interferingInfos);
    }

    private AssemblyInterferenceCheckResult CheckInterferenceViaDetectionManager(
        IAssemblyDoc assy,
        IReadOnlyList<ComponentInstance> instances,
        IReadOnlyList<string>? hierarchyPaths,
        bool treatCoincidenceAsInterference)
    {
        var requestedPaths = hierarchyPaths == null || hierarchyPaths.Count == 0
            ? null
            : new HashSet<string>(hierarchyPaths, StringComparer.OrdinalIgnoreCase);

        InterferenceDetectionMgr? detectionManager = null;
        try
        {
            assy.ToolsCheckInterference();
            detectionManager = assy.InterferenceDetectionManager
                ?? throw new InvalidOperationException("SolidWorks did not provide an interference detection manager.");

            detectionManager.TreatCoincidenceAsInterference = treatCoincidenceAsInterference;
            detectionManager.TreatSubAssembliesAsComponents = false;
            detectionManager.IncludeMultibodyPartInterferences = true;
            detectionManager.MakeInterferingPartsTransparent = true;
            detectionManager.CreateFastenersFolder = false;
            detectionManager.IgnoreHiddenBodies = false;
            detectionManager.ShowIgnoredInterferences = false;
            detectionManager.UseTransform = false;
            detectionManager.NonInterferingComponentDisplay = (int)swNonInterferingComponentDisplay_e.swNonInterferingComponentDisplay_Wireframe;

            var interferences = (detectionManager.GetInterferences() as object[] ?? Array.Empty<object>())
                .OfType<IInterference>()
                .ToList();

            var matchedInfos = new List<ComponentInstanceInfo>();
            int interferingFaceCount = 0;
            foreach (var interference in interferences)
            {
                var components = (interference.Components as object[] ?? Array.Empty<object>())
                    .OfType<IComponent2>()
                    .ToList();
                var componentInfos = instances
                    .Where(instance => components.Any(component => IsSameComponentInstance(instance.Component, component)))
                    .Select(instance => instance.Info)
                    .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
                    .ToList();

                if (requestedPaths != null && !componentInfos.Any(info => requestedPaths.Contains(info.HierarchyPath)))
                {
                    continue;
                }

                matchedInfos.AddRange(componentInfos);
                if (!interference.IsPossibleInterference)
                {
                    interferingFaceCount += Math.Max(interference.GetComponentCount(), 0);
                }
            }

            var interferingInfos = matchedInfos
                .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
                .ToList()
                .AsReadOnly();

            int checkedComponentCount = requestedPaths == null
                ? instances.Count
                : instances.Count(instance => requestedPaths.Contains(instance.Info.HierarchyPath));

            return new AssemblyInterferenceCheckResult(
                HasInterference: interferingInfos.Count > 0,
                TreatCoincidenceAsInterference: treatCoincidenceAsInterference,
                CheckedComponentCount: checkedComponentCount,
                InterferingFaceCount: interferingFaceCount,
                InterferingComponents: interferingInfos);
        }
        catch (System.Runtime.InteropServices.COMException ex)
        {
            throw SolidWorksApiErrorFactory.FromComException(
                "IInterferenceDetectionMgr.GetInterferences",
                ex,
                new Dictionary<string, object?>
                {
                    ["requestedHierarchyPaths"] = hierarchyPaths == null ? null : string.Join(" | ", hierarchyPaths),
                    ["treatCoincidenceAsInterference"] = treatCoincidenceAsInterference,
                });
        }
        finally
        {
            detectionManager?.Done();
        }
    }

    public AssemblyComponentReplacementResult ReplaceComponent(
        string hierarchyPath,
        string replacementFilePath,
        string configName = "",
        bool replaceAllInstances = false,
        int useConfigChoice = (int)swReplaceComponentsConfiguration_e.swReplaceComponentsConfiguration_MatchName,
        bool reattachMates = true)
    {
        if (string.IsNullOrWhiteSpace(hierarchyPath))
            throw new ArgumentException("hierarchyPath must not be empty", nameof(hierarchyPath));
        if (string.IsNullOrWhiteSpace(replacementFilePath))
            throw new ArgumentException("replacementFilePath must not be empty", nameof(replacementFilePath));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var doc = (IModelDoc2)assy;

        var target = EnumerateComponentInstances(assy)
            .FirstOrDefault(instance => string.Equals(instance.Info.HierarchyPath, hierarchyPath, StringComparison.OrdinalIgnoreCase));
        if (target == null)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IAssemblyDoc.ReplaceComponents2",
                "The requested component instance was not found in the active assembly.",
                new Dictionary<string, object?>
                {
                    ["hierarchyPath"] = hierarchyPath,
                    ["replacementFilePath"] = replacementFilePath,
                });
        }

        if (target.Info.Depth != 0)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IAssemblyDoc.ReplaceComponents2",
                "Only top-level components in the active assembly can be replaced. Open the owning subassembly and retry.",
                new Dictionary<string, object?>
                {
                    ["hierarchyPath"] = hierarchyPath,
                    ["depth"] = target.Info.Depth,
                });
        }

        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("Selection manager is not available for the active assembly.");

        doc.ClearSelection2(true);
        try
        {
            var selectData = (SelectData)selectionManager.CreateSelectData();
            if (!target.Component.Select4(false, selectData, false))
            {
                throw SolidWorksApiErrorFactory.FromValidationFailure(
                    "IComponent2.Select4",
                    $"Failed to select component '{hierarchyPath}' for replacement.",
                    new Dictionary<string, object?>
                    {
                        ["hierarchyPath"] = hierarchyPath,
                        ["replacementFilePath"] = replacementFilePath,
                    });
            }

            bool success;
            try
            {
                success = assy.ReplaceComponents2(replacementFilePath, configName, replaceAllInstances, useConfigChoice, reattachMates);
            }
            catch (System.Runtime.InteropServices.COMException ex)
            {
                throw SolidWorksApiErrorFactory.FromComException(
                    "IAssemblyDoc.ReplaceComponents2",
                    ex,
                    new Dictionary<string, object?>
                    {
                        ["hierarchyPath"] = hierarchyPath,
                        ["replacementFilePath"] = replacementFilePath,
                        ["configName"] = configName,
                        ["replaceAllInstances"] = replaceAllInstances,
                        ["useConfigChoice"] = useConfigChoice,
                        ["reattachMates"] = reattachMates,
                    });
            }

            if (!success)
            {
                throw SolidWorksApiErrorFactory.FromValidationFailure(
                    "IAssemblyDoc.ReplaceComponents2",
                    "SolidWorks did not replace the selected component.",
                    new Dictionary<string, object?>
                    {
                        ["hierarchyPath"] = hierarchyPath,
                        ["replacementFilePath"] = replacementFilePath,
                        ["configName"] = configName,
                        ["replaceAllInstances"] = replaceAllInstances,
                        ["useConfigChoice"] = useConfigChoice,
                        ["reattachMates"] = reattachMates,
                    });
            }

            return new AssemblyComponentReplacementResult(
                hierarchyPath,
                replacementFilePath,
                configName,
                replaceAllInstances,
                useConfigChoice,
                reattachMates,
                success);
        }
        finally
        {
            doc.ClearSelection2(true);
        }
    }

    public AssemblyFeatureTreeTraversalResult TraverseAssemblyFeatureTrees()
    {
        _cm.EnsureConnected();
        var assemblyDoc = GetAssemblyDoc();
        var modelDoc = (IModelDoc2)assemblyDoc;
        var featureManager = _cm.SwApp?.FeatureManager
            ?? throw new InvalidOperationException("FeatureManager is not available for the active assembly.");
        var root = GetFeatureTreeRootItem(featureManager)
            ?? throw new InvalidOperationException("Could not access the active assembly FeatureManager tree root.");

        var nodes = new List<AssemblyFeatureTreeNodeInfo>();
        TraverseAssemblyTreeNode(
            node: root,
            depth: 0,
            parentGraphPath: null,
            activeAssembly: modelDoc,
            inheritedComponentName: null,
            inheritedComponentPath: null,
            inheritedHierarchyPath: null,
            nodes: nodes);

        return new AssemblyFeatureTreeTraversalResult(
            AssemblyTitle: SafeGetDocumentTitle(modelDoc) ?? "<untitled>",
            AssemblyPath: NormalizeCriteria(SafeGetDocumentPath(modelDoc)),
            NodeCount: nodes.Count,
            Nodes: nodes.AsReadOnly());
    }

    public AssemblyFeatureSearchResult SearchAssemblyFeatureTrees(string query, bool exactNameOnly = false, int maxResults = 200)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            throw new ArgumentException("query must not be empty.", nameof(query));
        }

        if (maxResults < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maxResults), maxResults, "maxResults must be at least 1.");
        }

        string normalizedQuery = query.Trim();
        string loweredQuery = normalizedQuery.ToLowerInvariant();
        var tree = TraverseAssemblyFeatureTrees();

        var matches = tree.Nodes
            .Select(node => new
            {
                Node = node,
                Score = ScoreAssemblyTreeNode(node, normalizedQuery, loweredQuery, exactNameOnly)
            })
            .Where(item => item.Score > 0)
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Node.Depth)
            .ThenBy(item => item.Node.NodeIndex)
            .Take(maxResults)
            .Select((item, index) => new AssemblyFeatureSearchMatchInfo(
                Rank: index,
                Score: item.Score,
                Query: normalizedQuery,
                MatchedText: item.Node.Text,
                FeatureName: item.Node.FeatureName,
                FeatureTypeName: item.Node.FeatureTypeName,
                GraphPath: item.Node.GraphPath,
                ComponentName: item.Node.ComponentName,
                ComponentPath: item.Node.ComponentPath,
                HierarchyPath: item.Node.HierarchyPath,
                DocumentTitle: item.Node.DocumentTitle,
                DocumentPath: item.Node.DocumentPath,
                RequiresOpenForEdit: !string.IsNullOrWhiteSpace(item.Node.ComponentPath)))
            .ToList()
            .AsReadOnly();

        return new AssemblyFeatureSearchResult(
            Query: normalizedQuery,
            ExactNameOnly: exactNameOnly,
            MatchCount: matches.Count,
            Matches: matches);
    }

    public OpenComponentForEditingResult OpenComponentForEditing(string componentPath, string? hierarchyPath = null)
    {
        string normalizedComponentPath = NormalizeCriteria(componentPath)
            ?? throw new ArgumentException("componentPath must not be empty.", nameof(componentPath));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var instances = EnumerateComponentInstances(assy);
        var matches = instances
            .Where(instance =>
                string.Equals(instance.Info.Path, normalizedComponentPath, StringComparison.OrdinalIgnoreCase)
                && (hierarchyPath == null || string.Equals(instance.Info.HierarchyPath, hierarchyPath, StringComparison.OrdinalIgnoreCase)))
            .Select(instance => instance.Info)
            .ToList();

        if (matches.Count == 0)
        {
            throw new InvalidOperationException(
                $"Component path '{normalizedComponentPath}' is not present in the active assembly" +
                (string.IsNullOrWhiteSpace(hierarchyPath) ? "." : $" at hierarchy path '{hierarchyPath}'."));
        }

        if (matches.Count > 1)
        {
            throw new InvalidOperationException(
                $"Component path '{normalizedComponentPath}' maps to multiple assembly instances. Provide the confirmed hierarchyPath to disambiguate.");
        }

        var target = matches[0];
        var opened = _cm.SwApp!.ActivateDoc(target.Path);
        return new OpenComponentForEditingResult(
            Opened: true,
            ComponentName: target.Name,
            ComponentPath: target.Path,
            HierarchyPath: target.HierarchyPath,
            Message: $"Opened component '{target.Name}' for editing after assembly-side confirmation.",
            OpenedDocument: opened);
    }

    // 鈹€鈹€ Helpers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    private sealed record ComponentInstance(IComponent2 Component, ComponentInstanceInfo Info);

    private static IEnumerable<IFeature> EnumerateTopLevelMateFeatures(IModelDoc2 doc)
    {
        for (var feature = doc.IFirstFeature(); feature != null; feature = feature.IGetNextFeature())
        {
            if (!string.Equals(feature.GetTypeName2(), "MateGroup", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            for (var mate = feature.IGetFirstSubFeature(); mate != null; mate = mate.IGetNextSubFeature())
            {
                var typeName = mate.GetTypeName2() ?? "";
                if (typeName.Contains("Mate", StringComparison.OrdinalIgnoreCase)
                    && !string.Equals(typeName, "MateGroup", StringComparison.OrdinalIgnoreCase))
                {
                    yield return mate;
                }
            }
        }
    }

    public LeafBodyInterferenceCheckResult CheckInterferenceByLeafBodies(
        IReadOnlyList<string> hierarchyPaths,
        bool treatCoincidenceAsInterference = false)
    {
        if (hierarchyPaths == null || hierarchyPaths.Count != 2)
        {
            throw new ArgumentException(
                "Exactly two component hierarchy paths are required for a leaf-body interference check.",
                nameof(hierarchyPaths));
        }

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        var selectedInstances = SelectInstances(EnumerateComponentInstances(assy), hierarchyPaths);
        if (selectedInstances.Count != 2)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IModeler.CheckInterferenceBetweenTwoBodies",
                "The two requested component hierarchy paths must each resolve to exactly one instance.",
                new Dictionary<string, object?>
                {
                    ["requestedHierarchyPaths"] = string.Join(" | ", hierarchyPaths),
                    ["resolvedInstanceCount"] = selectedInstances.Count,
                });
        }

        // A missing body AABB must not make an exact audit silently incomplete. Keep the
        // transformed body and route every pair involving it directly to the modeler kernel.
        // Bodies with valid AABBs still benefit from the normal broad-phase shortcut.
        var firstBodies = GetWorldSpaceSolidBodies(selectedInstances[0], includeBodiesWithoutBoundingBoxes: true);
        var secondBodies = GetWorldSpaceSolidBodies(selectedInstances[1], includeBodiesWithoutBoundingBoxes: true);
        if (firstBodies.Count == 0 || secondBodies.Count == 0)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IComponent2.GetBodies3",
                "Both requested modules must resolve to at least one solid body. Resolve lightweight components and retry.",
                new Dictionary<string, object?>
                {
                    ["firstHierarchyPath"] = selectedInstances[0].Info.HierarchyPath,
                    ["firstBodyCount"] = firstBodies.Count,
                    ["secondHierarchyPath"] = selectedInstances[1].Info.HierarchyPath,
                    ["secondBodyCount"] = secondBodies.Count,
                });
        }
        var modeler = _cm.SwApp!.GetModeler();

        int aabbCandidateCount = 0;
        long broadPhaseBypassedBodyPairCount = 0;
        int exactCompletedCount = 0;
        int primaryCheckReturnedFalseCount = 0;
        int fallbackExactCompletedCount = 0;
        int booleanFallbackCompletedCount = 0;
        int booleanFallbackNoIntersectionCount = 0;
        int interferingBodyPairCount = 0;
        var failures = new List<string>();
        var interferingInfos = new List<ComponentInstanceInfo>();
        var interferingBodyPairs = new List<LeafBodyInterferencePairInfo>();

        foreach (var first in firstBodies)
        {
            foreach (var second in secondBodies)
            {
                bool hasBothBoundingBoxes = first.BoundingBox.Length >= 6 && second.BoundingBox.Length >= 6;
                if (hasBothBoundingBoxes
                    && AreBoundingBoxesSeparated(first.BoundingBox, second.BoundingBox, InterferenceAabbSeparationTolerance))
                {
                    continue;
                }

                if (!hasBothBoundingBoxes)
                {
                    broadPhaseBypassedBodyPairCount++;
                }

                aabbCandidateCount++;
                try
                {
                    bool booleanFallbackInterference = false;
                    string detectionMethod = "CheckInterferenceBetweenTwoBodies";
                    object firstFacesRaw;
                    object secondFacesRaw;
                    object intersectionBodiesRaw;
                    bool succeeded = modeler.CheckInterferenceBetweenTwoBodies(
                        first.Body,
                        second.Body,
                        treatCoincidenceAsInterference,
                        out firstFacesRaw,
                        out secondFacesRaw,
                        out intersectionBodiesRaw);

                    if (!succeeded)
                    {
                        primaryCheckReturnedFalseCount++;
                        int options = (int)swCheckInterferenceOption_e.swBodyInterference_OptionDefault
                            | (int)swCheckInterferenceOption_e.swBodyInterference_ReturnInterferingObject;
                        if (treatCoincidenceAsInterference)
                        {
                            options |= (int)swCheckInterferenceOption_e.swBodyInterference_IncludeCoincidentFaces;
                        }

                        succeeded = modeler.CheckInterference3(
                            new object[] { first.Body },
                            new object[] { second.Body },
                            options,
                            ref firstFacesRaw,
                            ref secondFacesRaw,
                            ref intersectionBodiesRaw);
                        if (!succeeded)
                        {
                            detectionMethod = "IBody2.Operations2(SWBODYINTERSECT)";
                            int operationError;
                            var booleanResult = first.Body.ICopy().Operations2(
                                (int)swBodyOperationType_e.SWBODYINTERSECT,
                                second.Body.ICopy(),
                                out operationError);
                            if (operationError == (int)swBodyOperationError_e.swBodyOperationNoError
                                && CountComArray(booleanResult) > 0)
                            {
                                booleanFallbackInterference = true;
                                booleanFallbackCompletedCount++;
                            }
                            else if (operationError == (int)swBodyOperationError_e.swBodyOperationNoError
                                || operationError == (int)swBodyOperationError_e.swBodyOperationDisjointBodies
                                || operationError == (int)swBodyOperationError_e.swBodyOperationNoIntersect)
                            {
                                booleanFallbackCompletedCount++;
                                booleanFallbackNoIntersectionCount++;
                            }
                            else
                            {
                                failures.Add($"{first.Component.HierarchyPath} <-> {second.Component.HierarchyPath}: modeler checks returned false and Boolean intersection returned error {operationError}");
                                continue;
                            }
                        }
                        else
                        {
                            detectionMethod = "CheckInterference3";
                            fallbackExactCompletedCount++;
                        }
                    }

                    exactCompletedCount++;
                    int firstFaceCount = CountComArray(firstFacesRaw);
                    int secondFaceCount = CountComArray(secondFacesRaw);
                    int intersectionBodyCount = CountComArray(intersectionBodiesRaw);
                    if (booleanFallbackInterference
                        || firstFaceCount > 0
                        || secondFaceCount > 0
                        || intersectionBodyCount > 0)
                    {
                        interferingBodyPairCount++;
                        interferingInfos.Add(first.Component);
                        interferingInfos.Add(second.Component);
                        interferingBodyPairs.Add(new LeafBodyInterferencePairInfo(
                            FirstComponent: first.Component,
                            SecondComponent: second.Component,
                            FirstBoundingBoxWorld: first.BoundingBox,
                            SecondBoundingBoxWorld: second.BoundingBox,
                            AabbOverlapWorld: hasBothBoundingBoxes
                                ? GetBoundingBoxOverlap(first.BoundingBox, second.BoundingBox)
                                : Array.Empty<double>(),
                            DetectionMethod: detectionMethod));
                    }
                }
                catch (COMException ex)
                {
                    failures.Add($"{first.Component.HierarchyPath} <-> {second.Component.HierarchyPath}: 0x{ex.HResult:X8} {ex.Message}");
                }
            }
        }

        var firstLeaves = firstBodies
            .Select(item => item.Component.HierarchyPath)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Count();
        var secondLeaves = secondBodies
            .Select(item => item.Component.HierarchyPath)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Count();
        var distinctInterferingInfos = interferingInfos
            .DistinctBy(info => info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToList()
            .AsReadOnly();

        return new LeafBodyInterferenceCheckResult(
            HasInterference: interferingBodyPairCount > 0,
            TreatCoincidenceAsInterference: treatCoincidenceAsInterference,
            ExactCheckComplete: failures.Count == 0 && exactCompletedCount == aabbCandidateCount,
            CheckedTopLevelComponentCount: selectedInstances.Count,
            FirstLeafComponentCount: firstLeaves,
            SecondLeafComponentCount: secondLeaves,
            FirstBodyCount: firstBodies.Count,
            SecondBodyCount: secondBodies.Count,
            TotalBodyPairCount: (long)firstBodies.Count * secondBodies.Count,
            AabbCandidateBodyPairCount: aabbCandidateCount,
            BodyWithoutBoundingBoxCount: firstBodies.Count(item => item.BoundingBox.Length < 6)
                + secondBodies.Count(item => item.BoundingBox.Length < 6),
            BroadPhaseBypassedBodyPairCount: broadPhaseBypassedBodyPairCount,
            ExactCompletedBodyPairCount: exactCompletedCount,
            PrimaryCheckReturnedFalseCount: primaryCheckReturnedFalseCount,
            FallbackExactCompletedBodyPairCount: fallbackExactCompletedCount,
            BooleanFallbackCompletedBodyPairCount: booleanFallbackCompletedCount,
            BooleanFallbackNoIntersectionBodyPairCount: booleanFallbackNoIntersectionCount,
            FailedBodyPairCount: failures.Count,
            InterferingBodyPairCount: interferingBodyPairCount,
            InterferingComponents: distinctInterferingInfos,
            InterferingBodyPairs: interferingBodyPairs.AsReadOnly(),
            Failures: failures.AsReadOnly());
    }

    public LeafBodyEnvelopeCaptureResult CaptureLeafBodyEnvelopes(string hierarchyPath)
    {
        if (string.IsNullOrWhiteSpace(hierarchyPath))
        {
            throw new ArgumentException("A component hierarchy path is required.", nameof(hierarchyPath));
        }

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();
        if (string.Equals(hierarchyPath.Trim(), "@root", StringComparison.OrdinalIgnoreCase))
        {
            var activeModel = (IModelDoc2)assy;
            var activePath = activeModel.GetPathName() ?? string.Empty;
            var activeTitle = activeModel.GetTitle() ?? System.IO.Path.GetFileName(activePath);
            var capturedRootBodies = new List<WorldSpaceSolidBody>();
            var rootFailures = new List<string>();
            var topLevelComponents = (assy.GetComponents(true) as object[] ?? [])
                .OfType<IComponent2>()
                .ToList();
            foreach (var component in topLevelComponents)
            {
                string componentName = component.Name2 ?? "Component";
                TraverseWorldSpaceSolidBodies(
                    component,
                    componentName,
                    0,
                    capturedRootBodies,
                    rootFailures);
            }

            var rootEnvelopes = capturedRootBodies
                .Select(item => new LeafBodyEnvelopeInfo(
                    item.Component,
                    item.BodyIndex,
                    item.BoundingBox,
                    item.BoundingBoxSource))
                .ToList()
                .AsReadOnly();
            int rootLeafCount = rootEnvelopes
                .Select(item => item.Component.HierarchyPath)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count();
            var rootInfo = new ComponentInstanceInfo(
                activeTitle,
                activePath,
                "@root",
                -1);
            return new LeafBodyEnvelopeCaptureResult(
                rootInfo,
                rootLeafCount,
                rootEnvelopes.Count,
                rootEnvelopes,
                rootFailures.Count,
                rootFailures.Count == 0,
                rootFailures.AsReadOnly());
        }
        var selectedInstances = SelectInstances(
            EnumerateComponentInstances(assy),
            new[] { hierarchyPath });
        if (selectedInstances.Count != 1)
        {
            throw SolidWorksApiErrorFactory.FromValidationFailure(
                "IComponent2.GetBodies3",
                "The requested component hierarchy path must resolve to exactly one instance.",
                new Dictionary<string, object?>
                {
                    ["requestedHierarchyPath"] = hierarchyPath,
                    ["resolvedInstanceCount"] = selectedInstances.Count,
                });
        }

        var capturedBodies = new List<WorldSpaceSolidBody>();
        var failures = new List<string>();
        TraverseWorldSpaceSolidBodies(
            selectedInstances[0].Component,
            selectedInstances[0].Info.HierarchyPath,
            selectedInstances[0].Info.Depth,
            capturedBodies,
            failures);
        var bodies = capturedBodies.AsReadOnly();
        var envelopes = bodies
            .Select(item => new LeafBodyEnvelopeInfo(
                item.Component,
                item.BodyIndex,
                item.BoundingBox,
                item.BoundingBoxSource))
            .ToList()
            .AsReadOnly();
        int leafCount = envelopes
            .Select(item => item.Component.HierarchyPath)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Count();

        return new LeafBodyEnvelopeCaptureResult(
            selectedInstances[0].Info,
            leafCount,
            envelopes.Count,
            envelopes,
            failures.Count,
            failures.Count == 0,
            failures.AsReadOnly());
    }

    private static ITreeControlItem? GetFeatureTreeRootItem(IFeatureManager featureManager)
    {
        try
        {
            return featureManager.GetFeatureTreeRootItem2((int)swFeatMgrPane_e.swFeatMgrPaneBottom) as ITreeControlItem
                ?? featureManager.GetFeatureTreeRootItem2((int)swFeatMgrPane_e.swFeatMgrPaneTop) as ITreeControlItem
                ?? featureManager.GetFeatureTreeRootItem() as ITreeControlItem;
        }
        catch
        {
            return null;
        }
    }

    private static void TraverseAssemblyTreeNode(
        ITreeControlItem node,
        int depth,
        string? parentGraphPath,
        IModelDoc2 activeAssembly,
        string? inheritedComponentName,
        string? inheritedComponentPath,
        string? inheritedHierarchyPath,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        int siblingIndex = 0;
        for (var current = node; current != null; current = SafeGetNextTreeNode(current))
        {
            int nodeIndex = nodes.Count;
            string text = SafeGetTreeNodeText(current) ?? $"TreeNode{nodeIndex}";
            string graphPath = BuildTreeGraphPath(parentGraphPath, siblingIndex, text);
            object? treeObject = SafeGetTreeNodeObject(current);
            string? componentName = inheritedComponentName;
            string? componentPath = inheritedComponentPath;
            string? hierarchyPath = inheritedHierarchyPath;
            string? featureName = null;
            string? featureTypeName = null;
            bool isSketch = false;
            string? documentTitle = SafeGetDocumentTitle(activeAssembly);
            string? documentPath = NormalizeCriteria(SafeGetDocumentPath(activeAssembly));

            if (treeObject is IComponent2 component)
            {
                componentName = component.Name2;
                componentPath = NormalizeCriteria(component.GetPathName());
                hierarchyPath = BuildHierarchyPath(inheritedHierarchyPath, componentName);

                var componentDocument = SafeGetComponentModelDoc(component);
                documentTitle = componentDocument == null ? componentName : SafeGetDocumentTitle(componentDocument);
                documentPath = componentDocument == null ? componentPath : NormalizeCriteria(SafeGetDocumentPath(componentDocument));
            }
            else if (treeObject is Feature feature)
            {
                featureName = SafeGetFeatureName(feature);
                featureTypeName = SafeGetFeatureTypeName(feature);
                isSketch = IsSketchLike(featureTypeName);
            }
            else if (treeObject is IModelDoc2 modelDoc)
            {
                documentTitle = SafeGetDocumentTitle(modelDoc);
                documentPath = NormalizeCriteria(SafeGetDocumentPath(modelDoc));
            }

            nodes.Add(new AssemblyFeatureTreeNodeInfo(
                NodeIndex: nodeIndex,
                Depth: depth,
                Text: text,
                ObjectType: SafeGetTreeNodeObjectType(current),
                ObjectKind: DescribeTreeNodeObject(treeObject),
                IsRoot: SafeIsTreeRoot(current),
                IsExpanded: SafeIsTreeExpanded(current),
                GraphPath: graphPath,
                ParentGraphPath: parentGraphPath,
                FeatureName: featureName,
                FeatureTypeName: featureTypeName,
                IsSketch: isSketch,
                ComponentName: componentName,
                ComponentPath: componentPath,
                HierarchyPath: hierarchyPath,
                DocumentTitle: documentTitle,
                DocumentPath: documentPath));

            var child = SafeGetFirstTreeChild(current);
            bool loadedComponentContentsAdded = false;
            if (treeObject is IComponent2 componentForContent)
            {
                loadedComponentContentsAdded = AppendLoadedComponentContents(
                    componentForContent,
                    depth + 1,
                    graphPath,
                    hierarchyPath,
                    nodes);
            }

            if (!loadedComponentContentsAdded && child != null)
            {
                TraverseAssemblyTreeNode(
                    child,
                    depth + 1,
                    graphPath,
                    activeAssembly,
                    componentName,
                    componentPath,
                    hierarchyPath,
                    nodes);
            }

            siblingIndex++;
        }
    }

    private static bool AppendLoadedComponentContents(
        IComponent2 component,
        int depth,
        string parentGraphPath,
        string? hierarchyPath,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        bool addedAny = false;
        int siblingIndex = 0;
        var componentDoc = SafeGetComponentModelDoc(component);
        string? componentName = component.Name2;
        string? componentPath = NormalizeCriteria(component.GetPathName());
        string? documentTitle = componentDoc == null ? componentName : SafeGetDocumentTitle(componentDoc);
        string? documentPath = componentDoc == null ? componentPath : NormalizeCriteria(SafeGetDocumentPath(componentDoc));

        if (componentDoc != null)
        {
            var firstFeature = SafeGetFirstFeature(componentDoc);
            if (firstFeature != null)
            {
                addedAny = true;
                siblingIndex = TraverseTopLevelFeatureChain(
                    firstFeature,
                    depth,
                    parentGraphPath,
                    siblingIndex,
                    componentName,
                    componentPath,
                    hierarchyPath,
                    documentTitle,
                    documentPath,
                    nodes);
            }
        }

        foreach (var child in SafeGetComponentChildren(component).OfType<IComponent2>())
        {
            addedAny = true;
            AddLoadedComponentNode(
                child,
                depth,
                parentGraphPath,
                hierarchyPath,
                siblingIndex++,
                nodes);
        }

        return addedAny;
    }

    private static void AddLoadedComponentNode(
        IComponent2 component,
        int depth,
        string parentGraphPath,
        string? parentHierarchyPath,
        int siblingIndex,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        int nodeIndex = nodes.Count;
        string componentName = component.Name2 ?? $"Component{nodeIndex}";
        string? componentPath = NormalizeCriteria(component.GetPathName());
        string hierarchyPath = BuildHierarchyPath(parentHierarchyPath, componentName) ?? componentName;
        string graphPath = BuildTreeGraphPath(parentGraphPath, siblingIndex, componentName);
        var componentDoc = SafeGetComponentModelDoc(component);
        string? documentTitle = componentDoc == null ? componentName : SafeGetDocumentTitle(componentDoc);
        string? documentPath = componentDoc == null ? componentPath : NormalizeCriteria(SafeGetDocumentPath(componentDoc));

        nodes.Add(new AssemblyFeatureTreeNodeInfo(
            NodeIndex: nodeIndex,
            Depth: depth,
            Text: componentName,
            ObjectType: 0,
            ObjectKind: "component",
            IsRoot: false,
            IsExpanded: true,
            GraphPath: graphPath,
            ParentGraphPath: parentGraphPath,
            FeatureName: null,
            FeatureTypeName: null,
            IsSketch: false,
            ComponentName: componentName,
            ComponentPath: componentPath,
            HierarchyPath: hierarchyPath,
            DocumentTitle: documentTitle,
            DocumentPath: documentPath));

        AppendLoadedComponentContents(
            component,
            depth + 1,
            graphPath,
            hierarchyPath,
            nodes);
    }

    private static int TraverseTopLevelFeatureChain(
        Feature firstFeature,
        int depth,
        string parentGraphPath,
        int startSiblingIndex,
        string? componentName,
        string? componentPath,
        string? hierarchyPath,
        string? documentTitle,
        string? documentPath,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        int siblingIndex = startSiblingIndex;
        var visited = new HashSet<Feature>();
        for (var feature = firstFeature; feature != null && visited.Add(feature); feature = SafeGetNextFeature(feature))
        {
            AddLoadedFeatureNode(
                feature,
                depth,
                parentGraphPath,
                siblingIndex++,
                componentName,
                componentPath,
                hierarchyPath,
                documentTitle,
                documentPath,
                nodes);
        }

        return siblingIndex;
    }

    private static int TraverseSubFeatureChain(
        Feature firstFeature,
        int depth,
        string parentGraphPath,
        int startSiblingIndex,
        string? componentName,
        string? componentPath,
        string? hierarchyPath,
        string? documentTitle,
        string? documentPath,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        int siblingIndex = startSiblingIndex;
        var visited = new HashSet<Feature>();
        for (var feature = firstFeature; feature != null && visited.Add(feature); feature = SafeGetNextSubFeature(feature))
        {
            AddLoadedFeatureNode(
                feature,
                depth,
                parentGraphPath,
                siblingIndex++,
                componentName,
                componentPath,
                hierarchyPath,
                documentTitle,
                documentPath,
                nodes);
        }

        return siblingIndex;
    }

    private static void AddLoadedFeatureNode(
        Feature feature,
        int depth,
        string parentGraphPath,
        int siblingIndex,
        string? componentName,
        string? componentPath,
        string? hierarchyPath,
        string? documentTitle,
        string? documentPath,
        ICollection<AssemblyFeatureTreeNodeInfo> nodes)
    {
        int nodeIndex = nodes.Count;
        string featureName = SafeGetFeatureName(feature) ?? $"Feature{nodeIndex}";
        string? featureTypeName = SafeGetFeatureTypeName(feature);
        string graphPath = BuildTreeGraphPath(parentGraphPath, siblingIndex, featureName);

        nodes.Add(new AssemblyFeatureTreeNodeInfo(
            NodeIndex: nodeIndex,
            Depth: depth,
            Text: featureName,
            ObjectType: 0,
            ObjectKind: "feature",
            IsRoot: false,
            IsExpanded: true,
            GraphPath: graphPath,
            ParentGraphPath: parentGraphPath,
            FeatureName: featureName,
            FeatureTypeName: featureTypeName,
            IsSketch: IsSketchLike(featureTypeName),
            ComponentName: componentName,
            ComponentPath: componentPath,
            HierarchyPath: hierarchyPath,
            DocumentTitle: documentTitle,
            DocumentPath: documentPath));

        var firstSubFeature = SafeGetFirstSubFeature(feature);
        if (firstSubFeature != null)
        {
            TraverseSubFeatureChain(
                firstSubFeature,
                depth + 1,
                graphPath,
                0,
                componentName,
                componentPath,
                hierarchyPath,
                documentTitle,
                documentPath,
                nodes);
        }
    }

    private static int ScoreAssemblyTreeNode(AssemblyFeatureTreeNodeInfo node, string query, string loweredQuery, bool exactNameOnly)
    {
        int score = 0;
        foreach (var candidate in new[]
                 {
                     node.Text,
                     node.FeatureName,
                     node.FeatureTypeName,
                     node.ComponentName,
                     node.HierarchyPath,
                     node.ComponentPath
                 })
        {
            score = Math.Max(score, ScoreStringMatch(candidate, query, loweredQuery, exactNameOnly));
        }

        if (!string.IsNullOrWhiteSpace(node.ComponentPath))
        {
            score += 20;
        }

        if (!string.IsNullOrWhiteSpace(node.FeatureName))
        {
            score += 15;
        }

        return score;
    }

    private static int ScoreStringMatch(string? candidate, string query, string loweredQuery, bool exactNameOnly)
    {
        if (string.IsNullOrWhiteSpace(candidate))
        {
            return 0;
        }

        string value = candidate.Trim();
        string loweredValue = value.ToLowerInvariant();

        if (exactNameOnly)
        {
            return string.Equals(value, query, StringComparison.OrdinalIgnoreCase) ? 1200 : 0;
        }

        int score = 0;
        if (string.Equals(value, query, StringComparison.OrdinalIgnoreCase))
        {
            score += 1200;
        }
        else if (loweredValue.StartsWith(loweredQuery, StringComparison.Ordinal))
        {
            score += 850;
        }
        else if (loweredValue.Contains(loweredQuery, StringComparison.Ordinal))
        {
            score += 650;
        }

        foreach (var token in SplitSearchTokens(loweredQuery))
        {
            if (loweredValue.Contains(token, StringComparison.Ordinal))
            {
                score += 100;
            }
        }

        return score;
    }

    private static IEnumerable<string> SplitSearchTokens(string query)
    {
        return query
            .Split([' ', '/', '\\', '-', '_', ',', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Distinct(StringComparer.OrdinalIgnoreCase);
    }

    private static string BuildTreeGraphPath(string? parentGraphPath, int siblingIndex, string text)
    {
        string segment = $"{siblingIndex}:{text}";
        return string.IsNullOrWhiteSpace(parentGraphPath)
            ? segment
            : $"{parentGraphPath}/{segment}";
    }

    private static string? BuildHierarchyPath(string? parentHierarchyPath, string? componentName)
    {
        if (string.IsNullOrWhiteSpace(componentName))
        {
            return parentHierarchyPath;
        }

        return string.IsNullOrWhiteSpace(parentHierarchyPath)
            ? componentName.Trim()
            : $"{parentHierarchyPath}/{componentName.Trim()}";
    }

    private static ITreeControlItem? SafeGetFirstTreeChild(ITreeControlItem node)
    {
        try
        {
            return node.GetFirstChild() as ITreeControlItem;
        }
        catch
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
        catch
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
        catch
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
        catch
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
        catch
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
        catch
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
        catch
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

    private static string? SafeGetFeatureName(Feature feature)
    {
        try
        {
            return feature.Name;
        }
        catch
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
        catch
        {
            return null;
        }
    }

    private static IModelDoc2? SafeGetComponentModelDoc(IComponent2 component)
    {
        try
        {
            return component.GetModelDoc2() as IModelDoc2;
        }
        catch
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
        catch
        {
            return [];
        }
    }

    private static Feature? SafeGetFirstFeature(IModelDoc2 doc)
    {
        try
        {
            return doc.FirstFeature() as Feature;
        }
        catch
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
        catch
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
        catch
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
        catch
        {
            return null;
        }
    }

    private static bool IsSketchLike(string? typeName)
    {
        return string.Equals(typeName, "ProfileFeature", StringComparison.OrdinalIgnoreCase)
            || string.Equals(typeName, "3DProfileFeature", StringComparison.OrdinalIgnoreCase);
    }

    private static string? SafeGetDocumentTitle(IModelDoc2 doc)
    {
        try
        {
            return doc.GetTitle();
        }
        catch
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
        catch
        {
            return null;
        }
    }

    private static AssemblyTargetResolutionResult ResolveComponentTargetCore(
        IReadOnlyList<ComponentInstance> instances,
        string? activeAssemblyPath,
        string? componentName,
        string? hierarchyPath,
        string? componentPath)
    {
        var normalizedName = NormalizeCriteria(componentName);
        var normalizedHierarchyPath = NormalizeCriteria(hierarchyPath);
        var normalizedComponentPath = NormalizeCriteria(componentPath);

        var matches = instances
            .Where(instance => MatchesTarget(instance.Info, normalizedName, normalizedHierarchyPath, normalizedComponentPath))
            .Select(instance => instance.Info)
            .ToList()
            .AsReadOnly();

        if (matches.Count != 1)
        {
            return new AssemblyTargetResolutionResult(
                RequestedName: normalizedName,
                RequestedHierarchyPath: normalizedHierarchyPath,
                RequestedComponentPath: normalizedComponentPath,
                IsResolved: false,
                IsAmbiguous: matches.Count > 1,
                ResolvedInstance: null,
                OwningAssemblyHierarchyPath: null,
                OwningAssemblyFilePath: null,
                SourceFileReuseCount: 0,
                MatchingInstances: matches);
        }

        var resolvedInstance = matches[0];
        var owningAssemblyHierarchyPath = GetParentHierarchyPath(resolvedInstance.HierarchyPath);
        string? owningAssemblyFilePath = ResolveOwningAssemblyFilePath(instances, owningAssemblyHierarchyPath, activeAssemblyPath);

        return new AssemblyTargetResolutionResult(
            RequestedName: normalizedName,
            RequestedHierarchyPath: normalizedHierarchyPath,
            RequestedComponentPath: normalizedComponentPath,
            IsResolved: true,
            IsAmbiguous: false,
            ResolvedInstance: resolvedInstance,
            OwningAssemblyHierarchyPath: owningAssemblyHierarchyPath,
            OwningAssemblyFilePath: NormalizeCriteria(owningAssemblyFilePath),
            SourceFileReuseCount: CountSourceFileReuse(instances, resolvedInstance.Path),
            MatchingInstances: matches);
    }

    private static IReadOnlyList<ComponentInstance> EnumerateComponentInstances(IAssemblyDoc assy)
    {
        var raw = assy.GetComponents(true) as object[]
            ?? [];

        var results = new List<ComponentInstance>();
        foreach (var component in raw.OfType<IComponent2>())
        {
            TraverseComponent(component, component.Name2 ?? "Component", depth: 0, results);
        }

        return results.AsReadOnly();
    }

    private static IReadOnlyList<WorldSpaceSolidBody> GetWorldSpaceSolidBodies(
        ComponentInstance root,
        bool includeBodiesWithoutBoundingBoxes = false)
    {
        var results = new List<WorldSpaceSolidBody>();
        TraverseWorldSpaceSolidBodies(
            root.Component,
            root.Info.HierarchyPath,
            root.Info.Depth,
            results,
            includeBodiesWithoutBoundingBoxes: includeBodiesWithoutBoundingBoxes);
        return results.AsReadOnly();
    }

    private static void TraverseWorldSpaceSolidBodies(
        IComponent2 component,
        string hierarchyPath,
        int depth,
        ICollection<WorldSpaceSolidBody> results,
        ICollection<string>? captureFailures = null,
        bool includeBodiesWithoutBoundingBoxes = false)
    {
        string name = component.Name2 ?? $"Component{depth}";
        string path = component.GetPathName() ?? string.Empty;
        var info = new ComponentInstanceInfo(name, path, hierarchyPath, depth);

        object bodyInfo;
        var bodies = (component.GetBodies3((int)swBodyType_e.swSolidBody, out bodyInfo) as object[] ?? [])
            .OfType<IBody2>()
            .ToList();
        MathTransform? worldTransform;
        try
        {
            worldTransform = component.GetTotalTransform(true) as MathTransform
                ?? component.Transform2 as MathTransform;
        }
        catch (COMException)
        {
            worldTransform = component.Transform2 as MathTransform;
        }

        for (int bodyIndex = 0; bodyIndex < bodies.Count; bodyIndex++)
        {
            var sourceBody = bodies[bodyIndex];
            var body = sourceBody.ICopy();
            if (body == null)
            {
                RecordCaptureFailureOrThrow(
                    captureFailures,
                    $"Failed to copy body {bodyIndex} for '{hierarchyPath}'.");
                continue;
            }
            if (worldTransform != null && !body.ApplyTransform(worldTransform))
            {
                RecordCaptureFailureOrThrow(
                    captureFailures,
                    $"Failed to transform body {bodyIndex} for '{hierarchyPath}' into assembly coordinates.");
                continue;
            }

            var boundingBox = ToDoubleArray(body.GetBodyBox());
            string boundingBoxSource = "body-box";
            if (boundingBox == null || boundingBox.Length < 6)
            {
                boundingBox = GetBodyBoundingBoxFromFaces(body);
                boundingBoxSource = "face-box-union-fallback";
            }
            if (boundingBox == null || boundingBox.Length < 6)
            {
                if (includeBodiesWithoutBoundingBoxes)
                {
                    results.Add(new WorldSpaceSolidBody(
                        body,
                        info,
                        bodyIndex,
                        Array.Empty<double>(),
                        "unavailable"));
                    continue;
                }

                RecordCaptureFailureOrThrow(
                    captureFailures,
                    $"Failed to obtain a body bounding box for body {bodyIndex} of '{hierarchyPath}'.");
                continue;
            }

            results.Add(new WorldSpaceSolidBody(
                body,
                info,
                bodyIndex,
                NormalizeBoundingBox(boundingBox),
                boundingBoxSource));
        }

        var children = component.GetChildren() as object[] ?? [];
        foreach (var child in children.OfType<IComponent2>())
        {
            string childName = child.Name2 ?? "Component";
            TraverseWorldSpaceSolidBodies(
                child,
                $"{hierarchyPath}/{childName}",
                depth + 1,
                results,
                captureFailures,
                includeBodiesWithoutBoundingBoxes);
        }
    }

    private static void RecordCaptureFailureOrThrow(
        ICollection<string>? captureFailures,
        string message)
    {
        if (captureFailures == null)
        {
            throw new InvalidOperationException(message);
        }

        captureFailures.Add(message);
    }

    private static double[]? GetBodyBoundingBoxFromFaces(IBody2 body)
    {
        try
        {
            var faceBoxes = (body.GetFaces() as object[] ?? [])
                .OfType<IFace2>()
                .Select(face => ToDoubleArray(face.GetBox()))
                .Where(box => box is { Length: >= 6 })
                .Select(box => NormalizeBoundingBox(box!))
                .ToList();
            if (faceBoxes.Count == 0)
            {
                return null;
            }

            return
            [
                faceBoxes.Min(box => box[0]),
                faceBoxes.Min(box => box[1]),
                faceBoxes.Min(box => box[2]),
                faceBoxes.Max(box => box[3]),
                faceBoxes.Max(box => box[4]),
                faceBoxes.Max(box => box[5]),
            ];
        }
        catch (COMException)
        {
            return null;
        }
        catch (InvalidCastException)
        {
            return null;
        }
    }

    private static int CountComArray(object? value)
    {
        return value switch
        {
            null => 0,
            Array array => array.Length,
            _ => 1,
        };
    }

    private static double[]? ToDoubleArray(object? value)
    {
        if (value is double[] doubles)
        {
            return doubles;
        }

        if (value is Array array)
        {
            try
            {
                return array.Cast<object>().Select(Convert.ToDouble).ToArray();
            }
            catch (Exception) when (value is not double[])
            {
                return null;
            }
        }

        return null;
    }

    private static ComponentInstance? ResolveComponentForTransform(IAssemblyDoc assy, string componentName)
    {
        // IAssemblyDoc.GetComponentByName avoids recursively expanding every subassembly when the
        // requested component is already addressable by its instance name (the normal Replay case).
        // Some legacy/nested targets are not returned by this API, so retain the existing full-tree
        // search as a fallback instead of changing the public resolution semantics.
        try
        {
            if (assy.GetComponentByName(componentName) is IComponent2 direct)
            {
                var resolvedName = direct.Name2 ?? componentName;
                var path = direct.GetPathName() ?? string.Empty;
                return new ComponentInstance(
                    direct,
                    new ComponentInstanceInfo(resolvedName, path, resolvedName, 0));
            }
        }
        catch (COMException)
        {
            // Fall through to the established recursive resolver when the direct COM lookup is not
            // supported by the active document state.
        }

        return EnumerateComponentInstances(assy).FirstOrDefault(instance =>
            string.Equals(instance.Info.Name, componentName, StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<ComponentInstance> SelectInstances(
        IReadOnlyList<ComponentInstance> instances,
        IReadOnlyList<string>? hierarchyPaths)
    {
        if (hierarchyPaths == null || hierarchyPaths.Count == 0)
        {
            return instances;
        }

        var requested = new HashSet<string>(hierarchyPaths, StringComparer.OrdinalIgnoreCase);
        return instances
            .Where(instance => requested.Contains(instance.Info.HierarchyPath))
            .ToList()
            .AsReadOnly();
    }

    private static bool MatchesTarget(
        ComponentInstanceInfo info,
        string? componentName,
        string? hierarchyPath,
        string? componentPath)
    {
        return (componentName == null || string.Equals(info.Name, componentName, StringComparison.OrdinalIgnoreCase))
            && (hierarchyPath == null || string.Equals(info.HierarchyPath, hierarchyPath, StringComparison.OrdinalIgnoreCase))
            && (componentPath == null || string.Equals(info.Path, componentPath, StringComparison.OrdinalIgnoreCase));
    }

    private static int CountSourceFileReuse(IReadOnlyList<ComponentInstance> instances, string? componentPath)
    {
        var normalizedComponentPath = NormalizeCriteria(componentPath);
        if (normalizedComponentPath == null)
        {
            return 0;
        }

        return instances.Count(instance => string.Equals(instance.Info.Path, normalizedComponentPath, StringComparison.OrdinalIgnoreCase));
    }

    private static string? ResolveOwningAssemblyFilePath(
        IReadOnlyList<ComponentInstance> instances,
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
            var candidatePath = instances
                .FirstOrDefault(instance => string.Equals(instance.Info.HierarchyPath, candidateHierarchyPath, StringComparison.OrdinalIgnoreCase))
                ?.Info.Path;

            if (!string.IsNullOrWhiteSpace(candidatePath))
            {
                return NormalizeCriteria(candidatePath);
            }

            candidateHierarchyPath = GetParentHierarchyPath(candidateHierarchyPath);
        }

        return activeAssemblyPath;
    }

    private static object WrapDispatchObject(object value)
    {
        try
        {
            return new DispatchWrapper(value);
        }
        catch (InvalidOperationException)
        {
            return value;
        }
    }

    private static ComponentPoseInfo ToComponentPoseInfo(IComponent2 component, ComponentInstanceInfo info)
    {
        // GetBox 返回组件在当前装配体坐标系下的近似轴对齐包围盒。
        // 该数据只用于布局规划阶段估算占地范围，不替代最终的干涉检查。
        var boundingBoxWorld = GetComponentBoundingBox(component);
        var transform = component.Transform2?.ArrayData as double[];
        var totalTransform = SafeTotalTransformData(component);
        var totalTranslation = ExtractTransformTranslation(totalTransform);
        var totalXAxis = ExtractTransformAxis(totalTransform, 0);
        var totalYAxis = ExtractTransformAxis(totalTransform, 3);
        var totalZAxis = ExtractTransformAxis(totalTransform, 6);
        if (transform == null || transform.Length < 13)
        {
            return new ComponentPoseInfo(
                info.Name,
                info.Path,
                info.HierarchyPath,
                info.Depth,
                null,
                null,
                null,
                null,
                null,
                boundingBoxWorld,
                SafeReferencedConfiguration(component),
                SafeComponentSolvingState(component),
                SafeComponentSolvingStateName(component),
                totalTransform,
                totalTranslation,
                totalXAxis,
                totalYAxis,
                totalZAxis);
        }

        var data = (double[])transform.Clone();
        return new ComponentPoseInfo(
            info.Name,
            info.Path,
            info.HierarchyPath,
            info.Depth,
            data,
            [data[9], data[10], data[11]],
            NormalizeVector([data[0], data[1], data[2]]),
            NormalizeVector([data[3], data[4], data[5]]),
            NormalizeVector([data[6], data[7], data[8]]),
            boundingBoxWorld,
            SafeReferencedConfiguration(component),
            SafeComponentSolvingState(component),
            SafeComponentSolvingStateName(component),
            totalTransform,
            totalTranslation,
            totalXAxis,
            totalYAxis,
            totalZAxis);
    }

    private static double[]? SafeTotalTransformData(IComponent2 component)
    {
        try
        {
            var values = (component.GetTotalTransform(true) as MathTransform)?.ArrayData as double[];
            return values == null ? null : (double[])values.Clone();
        }
        catch
        {
            return null;
        }
    }

    private static double[]? ExtractTransformTranslation(double[]? transform)
        => transform is { Length: >= 12 }
            ? [transform[9], transform[10], transform[11]]
            : null;

    private static double[]? ExtractTransformAxis(double[]? transform, int offset)
        => transform is { Length: >= 9 }
            ? NormalizeVector([transform[offset], transform[offset + 1], transform[offset + 2]])
            : null;

    private static string? SafeReferencedConfiguration(IComponent2 component)
    {
        try { return component.ReferencedConfiguration; }
        catch { return null; }
    }

    private static int? SafeComponentSolvingState(IComponent2 component)
    {
        try { return component.Solving; }
        catch { return null; }
    }

    private static string? SafeComponentSolvingStateName(IComponent2 component)
    {
        int? state = SafeComponentSolvingState(component);
        return state.HasValue
            ? ((swComponentSolvingOption_e)state.Value).ToString()
            : null;
    }

    private static double[]? GetComponentBoundingBox(IComponent2 component)
    {
        try
        {
            var values = component.GetBox(false, false);
            if (values is double[] doubles && doubles.Length >= 6)
            {
                return NormalizeBoundingBox(doubles);
            }

            if (values is Array array && array.Length >= 6)
            {
                var converted = array.Cast<object>()
                    .Take(6)
                    .Select(Convert.ToDouble)
                    .ToArray();
                return NormalizeBoundingBox(converted);
            }
        }
        catch (COMException)
        {
            // Lightweight or unresolved components may not expose a box. Callers treat null as unavailable geometry.
        }
        catch (InvalidCastException)
        {
        }

        return null;
    }

    private static double[] NormalizeBoundingBox(double[] box)
        =>
        [
            Math.Min(box[0], box[3]),
            Math.Min(box[1], box[4]),
            Math.Min(box[2], box[5]),
            Math.Max(box[0], box[3]),
            Math.Max(box[1], box[4]),
            Math.Max(box[2], box[5]),
        ];

    internal static bool AreBoundingBoxesSeparated(
        double[]? first,
        double[]? second,
        double tolerance = InterferenceAabbSeparationTolerance)
    {
        if (first == null || second == null || first.Length < 6 || second.Length < 6)
        {
            return false;
        }

        var a = NormalizeBoundingBox(first);
        var b = NormalizeBoundingBox(second);
        double safeTolerance = Math.Max(tolerance, 0);
        return a[3] + safeTolerance < b[0]
            || b[3] + safeTolerance < a[0]
            || a[4] + safeTolerance < b[1]
            || b[4] + safeTolerance < a[1]
            || a[5] + safeTolerance < b[2]
            || b[5] + safeTolerance < a[2];
    }

    private static double[] GetBoundingBoxOverlap(double[] first, double[] second)
    {
        var a = NormalizeBoundingBox(first);
        var b = NormalizeBoundingBox(second);
        return
        [
            Math.Max(a[0], b[0]),
            Math.Max(a[1], b[1]),
            Math.Max(a[2], b[2]),
            Math.Min(a[3], b[3]),
            Math.Min(a[4], b[4]),
            Math.Min(a[5], b[5]),
        ];
    }

    private static double[] NormalizeVector(double[] vector)
    {
        var length = Math.Sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);
        return length < 1e-12
            ? [0, 0, 0]
            : [vector[0] / length, vector[1] / length, vector[2] / length];
    }

    private static string? GetParentHierarchyPath(string hierarchyPath)
    {
        int separatorIndex = hierarchyPath.LastIndexOf('/');
        return separatorIndex <= 0 ? null : hierarchyPath[..separatorIndex];
    }

    private static string? NormalizeCriteria(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private static void ValidateTargetCriteria(string? componentName, string? hierarchyPath, string? componentPath)
    {
        if (NormalizeCriteria(componentName) == null
            && NormalizeCriteria(hierarchyPath) == null
            && NormalizeCriteria(componentPath) == null)
        {
            throw new ArgumentException("At least one of componentName, hierarchyPath, or componentPath must be provided.");
        }
    }

    private static void TraverseComponent(
        IComponent2 component,
        string hierarchyPath,
        int depth,
        ICollection<ComponentInstance> results)
    {
        var name = component.Name2 ?? $"Component{depth}";
        string path = component.GetPathName() ?? string.Empty;

        results.Add(new ComponentInstance(component, new ComponentInstanceInfo(name, path, hierarchyPath, depth)));

        var children = component.GetChildren() as object[]
            ?? [];

        foreach (var child in children.OfType<IComponent2>())
        {
            var childName = child.Name2 ?? "Component";
            TraverseComponent(child, $"{hierarchyPath}/{childName}", depth + 1, results);
        }
    }

    private static bool IsSameComponentInstance(IComponent2 left, IComponent2 right)
    {
        return string.Equals(left.Name2, right.Name2, StringComparison.OrdinalIgnoreCase)
            && string.Equals(left.GetPathName(), right.GetPathName(), StringComparison.OrdinalIgnoreCase);
    }

    private IAssemblyDoc GetAssemblyDoc()
    {
        var doc = _cm.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document");

        return doc as IAssemblyDoc
            ?? throw new InvalidOperationException("Active document is not an assembly");
    }

    private MateOperationResult AddMate(MateType type, MateAlign align,
        double distance = 0, double angle = 0)
    {
        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        int errors = 0;
        // AddMate5(mateType, align, flip, distance, distMax, distMin,
        //          gearNumer, gearDenom, angle, angleMax, angleMin,
        //          forPosOnly, lockRot, widthOpt, ref errors)
        var mate = assy.AddMate5(
            (int)type, (int)align, false,
            distance, 0, 0,
            0, 0,
            angle, 0, 0,
            false, false, 0,
            out errors);

        var mateError = (swAddMateError_e)errors;
        if (mate == null || mateError != swAddMateError_e.swAddMateError_NoError)
        {
            throw SolidWorksApiErrorFactory.FromMateFailure(
                "IAssemblyDoc.AddMate5",
                $"Failed to create {type} mate.",
                errors,
                new Dictionary<string, object?>
                {
                    ["mateType"] = type,
                    ["align"] = align,
                    ["distance"] = distance,
                    ["angleRadians"] = angle,
                });
        }

        var codeInfo = SolidWorksApiErrorFactory.DecodeValue<swAddMateError_e>(errors);
        return new MateOperationResult(type.ToString(), errors, codeInfo.Name, codeInfo.Description);
    }
}
