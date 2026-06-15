using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Runtime.InteropServices;

namespace SolidWorksBridge.SolidWorks;

/// <summary>
/// Info about a component in an assembly.
/// </summary>
public record ComponentInfo(string Name, string Path);

/// <summary>
/// Info about a component instance discovered by recursively traversing an assembly tree.
/// </summary>
public record ComponentInstanceInfo(string Name, string Path, string HierarchyPath, int Depth);

/// <summary>
/// Summary of a static interference check in an assembly.
/// </summary>
public record AssemblyInterferenceCheckResult(
    bool HasInterference,
    bool TreatCoincidenceAsInterference,
    int CheckedComponentCount,
    int InterferingFaceCount,
    IReadOnlyList<ComponentInstanceInfo> InterferingComponents);

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
        double deltaZ);

    /// <summary>
    /// Rotate a component around the specified world-space axis by the given angle in degrees.
    /// 鍥寸粫涓栫晫鍧愭爣绯讳腑鐨勬寚瀹氳酱鏃嬭浆缁勪欢瀹炰緥锛岃搴﹀崟浣嶄负搴︺€?    /// </summary>
    ComponentTransformResult RotateComponent(
        string componentName,
        double axisX,
        double axisY,
        double axisZ,
        double angleDegrees);

    /// <summary>
    /// Insert a component at the given position (meters). Returns component info.
    /// 鍚戝綋鍓嶆椿鍔ㄨ閰嶄綋瀵煎叆涓€涓浂浠舵垨瀛愯閰嶄綋锛屽苟鎸囧畾鍒濆鎻掑叆浣嶇疆锛屽潗鏍囧崟浣嶄负绫炽€?    /// </summary>
    ComponentInfo InsertComponent(string filePath, double x = 0, double y = 0, double z = 0);

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
    /// List all component instances in the active assembly by recursively traversing subassemblies.
    /// 閫掑綊鍒楀嚭褰撳墠娲诲姩瑁呴厤浣撲腑鐨勬墍鏈夌粍浠跺疄渚嬶紝骞惰繑鍥炲眰绾ц矾寰勶紝閫傚悎澶勭悊宓屽瀛愯閰嶄綋銆?    /// </summary>
    IReadOnlyList<ComponentInstanceInfo> ListComponentsRecursive();

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
    /// Run a static interference check for the active assembly or a subset of component instances.
    /// This follows the official ToolsCheckInterference2 workflow and temporarily changes the SolidWorks selection set.
    /// 瀵规暣涓椿鍔ㄨ閰嶄綋鎴栨寚瀹氱粍浠堕泦鍚堟墽琛岄潤鎬佸共娑夋鏌ワ紱璋冪敤鏈熼棿浼氫复鏃舵敼鍙?SolidWorks 褰撳墠閫夋嫨闆嗐€?    /// </summary>
    AssemblyInterferenceCheckResult CheckInterference(
        IReadOnlyList<string>? hierarchyPaths = null,
        bool treatCoincidenceAsInterference = false);

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
public class AssemblyService : IAssemblyService
{
    private const int RpcServerFault = unchecked((int)0x80010105);

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

        // For a saved standalone part, let SolidWorks resolve the model's active/default
        // configuration instead of forcing an existing selected config in the target assembly.
        var comp = assy.AddComponent5(filePath, 0, "", false, "", x, y, z) as IComponent2
            ?? throw new InvalidOperationException($"Failed to insert component: {filePath}");

        return new ComponentInfo(comp.Name2, comp.GetPathName());
    }


    public ComponentTransformResult MoveComponent(
        string componentName,
        double deltaX,
        double deltaY,
        double deltaZ)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        // Search all instances (including subassemblies) to match behaviour of other target-resolution methods.
        var instances = EnumerateComponentInstances(assy);
        var target = instances.FirstOrDefault(i =>
            string.Equals(i.Info.Name, componentName, StringComparison.OrdinalIgnoreCase));

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

        var doc = (IModelDoc2)assy;
        doc.EditRebuild3();

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
        double angleDegrees)
    {
        if (string.IsNullOrWhiteSpace(componentName))
            throw new ArgumentException("componentName must not be empty", nameof(componentName));

        _cm.EnsureConnected();
        var assy = GetAssemblyDoc();

        var instances = EnumerateComponentInstances(assy);
        var target = instances.FirstOrDefault(i =>
            string.Equals(i.Info.Name, componentName, StringComparison.OrdinalIgnoreCase));

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

        var doc = (IModelDoc2)assy;
        doc.EditRebuild3();

        return new ComponentTransformResult(
            true,
            $"Rotated component '{componentName}' around ({axisX},{axisY},{axisZ}) by {angleDegrees}掳",
            target.Info.Name,
            target.Info.HierarchyPath);
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
