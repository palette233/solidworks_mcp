using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class AssemblyTools(StaDispatcher sta, IAssemblyService assembly)
{
    [McpServerTool, Description("Traverse the active assembly's visible FeatureManager tree, including feature nodes inside child parts and nested subassemblies, without opening every child document. Use this when the user asks to inspect, browse, or understand features inside assembly child components.")]
    public async Task<string> TraverseAssemblyChildFeatureTrees()
    {
        var result = await sta.InvokeLoggedAsync(nameof(TraverseAssemblyChildFeatureTrees), null, assembly.TraverseAssemblyFeatureTrees);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Search for a feature inside the active assembly and its child part/subassembly FeatureManager trees without opening child documents. This is the preferred first tool for requests like 'find a feature in an assembly child part' or 'locate the part that owns this feature'. Returns componentPath and hierarchyPath so the user can confirm the target before editing.")]
    public async Task<string> SearchAssemblyChildFeatures(
        [Description("Feature name, sketch name, component name, or FeatureManager tree text to search inside the active assembly's child feature trees.")] string query,
        [Description("When true, only exact text matches are returned.")] bool exactNameOnly = false,
        [Description("Maximum number of ranked matches to return. Defaults to 200 so large assemblies expose enough feature candidates in content.json.")] int maxResults = 200)
    {
        var payload = new { query, exactNameOnly, maxResults };
        var result = await sta.InvokeLoggedAsync(nameof(SearchAssemblyChildFeatures), payload, () => assembly.SearchAssemblyFeatureTrees(query, exactNameOnly, maxResults));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Open one user-confirmed child part or subassembly source document for editing after SearchAssemblyChildFeatures identifies the owning component. Use only after the user confirms the returned componentPath/hierarchyPath is the intended target.")]
    public async Task<string> OpenAssemblyChildComponentForEditing(
        [Description("Exact confirmed component source file path returned by SearchAssemblyChildFeatures.")] string componentPath,
        [Description("Optional confirmed hierarchy path returned by SearchAssemblyChildFeatures to disambiguate reused parts.")] string? hierarchyPath = null)
    {
        var payload = new { componentPath, hierarchyPath };
        var result = await sta.InvokeLoggedAsync(nameof(OpenAssemblyChildComponentForEditing), payload, () => assembly.OpenComponentForEditing(componentPath, hierarchyPath));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Insert a component into the active SolidWorks assembly at the given position.")]
    public async Task<string> InsertComponent(
        [Description("Full file path to the component (.sldprt or .sldasm)")] string filePath,
        [Description("X position in meters (default 0)")] double x = 0,
        [Description("Y position in meters (default 0)")] double y = 0,
        [Description("Z position in meters (default 0)")] double z = 0)
    {
        var info = await sta.InvokeLoggedAsync(nameof(InsertComponent), new { filePath, x, y, z }, () => assembly.InsertComponent(filePath, x, y, z));
        return JsonSerializer.Serialize(info);
    }

    [McpServerTool, Description("Rename one component instance in the active assembly. Use this immediately after insertion to create stable aliases for later transform, configuration, and collision operations.")]
    public async Task<string> RenameComponent(
        [Description("Current component instance name returned by InsertComponent.")] string currentName,
        [Description("Requested unique component instance name.")] string newName)
    {
        var info = await sta.InvokeLoggedAsync(
            nameof(RenameComponent),
            new { currentName, newName },
            () => assembly.RenameComponent(currentName, newName));
        return JsonSerializer.Serialize(info);
    }

    [McpServerTool, Description("Add a Coincident mate between the two currently-selected faces, edges, or planes.")]
    public async Task<string> AddMateCoincident(
        [Description("Mate alignment: None=0, AntiAligned=1, Closest=2")] int align = 2)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddMateCoincident),
            new { align },
            () =>
            {
                var parsedAlign = ToolArgumentParsing.ParseMateAlign(align);
                return assembly.AddMateCoincident(parsedAlign);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add a Concentric mate between the two currently-selected cylindrical faces or circular edges.")]
    public async Task<string> AddMateConcentric(
        [Description("Mate alignment: None=0, AntiAligned=1, Closest=2")] int align = 2)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddMateConcentric),
            new { align },
            () =>
            {
                var parsedAlign = ToolArgumentParsing.ParseMateAlign(align);
                return assembly.AddMateConcentric(parsedAlign);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add a Parallel mate between the two currently-selected planar faces or edges.")]
    public async Task<string> AddMateParallel(
        [Description("Mate alignment: None=0, AntiAligned=1, Closest=2")] int align = 2)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddMateParallel),
            new { align },
            () =>
            {
                var parsedAlign = ToolArgumentParsing.ParseMateAlign(align);
                return assembly.AddMateParallel(parsedAlign);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add a Distance mate between the two currently-selected entities.")]
    public async Task<string> AddMateDistance(
        [Description("Distance between the entities in meters")] double distance,
        [Description("Mate alignment: None=0, AntiAligned=1, Closest=2")] int align = 2)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddMateDistance),
            new { distance, align },
            () =>
            {
                var parsedAlign = ToolArgumentParsing.ParseMateAlign(align);
                return assembly.AddMateDistance(distance, parsedAlign);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add an Angle mate between the two currently-selected planar entities.")]
    public async Task<string> AddMateAngle(
        [Description("Angle between the entities in degrees")] double angleDegrees,
        [Description("Mate alignment: None=0, AntiAligned=1, Closest=2")] int align = 2)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddMateAngle),
            new { angleDegrees, align },
            () =>
            {
                var parsedAlign = ToolArgumentParsing.ParseMateAlign(align);
                return assembly.AddMateAngle(angleDegrees, parsedAlign);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("List all components in the active SolidWorks assembly.")]
    public async Task<string> ListComponents()
    {
        var list = await sta.InvokeLoggedAsync(nameof(ListComponents), null, assembly.ListComponents);
        return JsonSerializer.Serialize(list);
    }

    [McpServerTool, Description("Create a non-destructive top-level module-only view in the active assembly by suppressing every direct child except the exact component instance names supplied. The requested keep list is fully validated before any suppression occurs. Use this on a saved copy when preserving source-context configurations is more important than reinserting modules into a blank assembly.")]
    public async Task<string> SuppressTopLevelComponentsExcept(
        [Description("Exact top-level component instance names to keep resolved and visible.")] string[] keepComponentNames,
        [Description("Rebuild the assembly after suppression.")] bool rebuild = true)
    {
        var payload = new { keepComponentNames, rebuild };
        var result = await sta.InvokeLoggedAsync(
            nameof(SuppressTopLevelComponentsExcept),
            payload,
            () => assembly.SuppressTopLevelComponentsExcept(keepComponentNames, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Create a non-destructive eight-module visual isolation in the active assembly by hiding every direct child except the exact requested component instances. Unlike suppression, hiding preserves component dependencies and configuration state. The keep list is fully validated before the document is changed.")]
    public async Task<string> HideTopLevelComponentsExcept(
        [Description("Exact top-level component instance names to keep visible.")] string[] keepComponentNames,
        [Description("Rebuild the assembly after changing visibility.")] bool rebuild = true)
    {
        var payload = new { keepComponentNames, rebuild };
        var result = await sta.InvokeLoggedAsync(
            nameof(HideTopLevelComponentsExcept),
            payload,
            () => assembly.HideTopLevelComponentsExcept(keepComponentNames, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("List all component instances in the active SolidWorks assembly by recursively traversing subassemblies. Returns each instance with its hierarchy path and depth so shared parts can be counted before editing.")]
    public async Task<string> ListComponentsRecursive()
    {
        var list = await sta.InvokeLoggedAsync(nameof(ListComponentsRecursive), null, assembly.ListComponentsRecursive);
        return JsonSerializer.Serialize(list);
    }

    [McpServerTool, Description("List component Transform2 poses in the active SolidWorks assembly. Returns transform, translation, and component axes for layout-capture workflows.")]
    public async Task<string> ListComponentPoses(
        [Description("When true, only first-level components are returned. When false, nested instances are included.")] bool topLevelOnly = true)
    {
        var list = await sta.InvokeLoggedAsync(nameof(ListComponentPoses), new { topLevelOnly }, () => assembly.ListComponentPoses(topLevelOnly));
        return JsonSerializer.Serialize(list);
    }

    [McpServerTool, Description("List the pose of one exact top-level component and only its descendant subtree. Use this instead of a full recursive assembly scan when validating one module.")]
    public async Task<string> ListTopLevelComponentSubtreePoses(
        [Description("Exact top-level component instance name or hierarchy path.")] string hierarchyPath)
    {
        var list = await sta.InvokeLoggedAsync(
            nameof(ListTopLevelComponentSubtreePoses),
            new { hierarchyPath },
            () => assembly.ListTopLevelComponentSubtreePoses(hierarchyPath));
        return JsonSerializer.Serialize(list);
    }

    [McpServerTool, Description("Set one exact top-level subassembly to solve as rigid or flexible, preserving its referenced configuration and other component properties. Use 0 for rigid and 1 for flexible.")]
    public async Task<string> SetTopLevelComponentSolvingState(
        [Description("Exact top-level component instance name or hierarchy path.")] string hierarchyPath,
        [Description("Solve-as state: rigid=0, flexible=1.")] int solvingState,
        [Description("Rebuild the active assembly after changing the state.")] bool rebuild = true)
    {
        var payload = new { hierarchyPath, solvingState, rebuild };
        var result = await sta.InvokeLoggedAsync(
            nameof(SetTopLevelComponentSolvingState),
            payload,
            () => assembly.SetTopLevelComponentSolvingState(hierarchyPath, solvingState, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Set one exact component at any nested hierarchy path to solve as rigid or flexible in the active assembly context. Use 0 for rigid and 1 for flexible.")]
    public async Task<string> SetComponentSolvingState(
        [Description("Exact recursive hierarchy path returned by list_component_poses or list_top_level_component_subtree_poses.")] string hierarchyPath,
        [Description("Solve-as state: rigid=0, flexible=1.")] int solvingState,
        [Description("Rebuild the active assembly after changing the state.")] bool rebuild = true)
    {
        var payload = new { hierarchyPath, solvingState, rebuild };
        var result = await sta.InvokeLoggedAsync(
            nameof(SetComponentSolvingState),
            payload,
            () => assembly.SetComponentSolvingState(hierarchyPath, solvingState, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Resolve all lightweight components in the active assembly before recursive hierarchy, solving-state, or exact B-Rep operations.")]
    public async Task<string> ResolveAllLightweightComponents(
        [Description("Ask SolidWorks to warn if any component cannot be resolved.")] bool warnIfNotResolved = false,
        [Description("Rebuild the active assembly after resolving components.")] bool rebuild = true)
    {
        var payload = new { warnIfNotResolved, rebuild };
        var result = await sta.InvokeLoggedAsync(
            nameof(ResolveAllLightweightComponents),
            payload,
            () => assembly.ResolveAllLightweightComponents(warnIfNotResolved, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Move a component by the specified delta in world-space meters. Searches all instances including subassemblies. Use the component instance name, e.g. 'Part1-1'.")]
    public async Task<string> MoveComponent(
        [Description("Component instance name, e.g. 'Part1-1'")] string componentName,
        [Description("X displacement in meters (e.g., 0.02 for 20mm)")] double deltaX,
        [Description("Y displacement in meters")] double deltaY,
        [Description("Z displacement in meters")] double deltaZ)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(MoveComponent),
            new { componentName, deltaX, deltaY, deltaZ },
            () => assembly.MoveComponent(componentName, deltaX, deltaY, deltaZ));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Rotate a component around a world-space axis by the given angle. Use axisX/Y/Z to define the rotation axis (e.g. 0,0,1 for Z-axis), and angleDegrees for the rotation amount.")]
    public async Task<string> RotateComponent(
        [Description("Component instance name, e.g. 'Part1-1'")] string componentName,
        [Description("X component of rotation axis")] double axisX,
        [Description("Y component of rotation axis")] double axisY,
        [Description("Z component of rotation axis")] double axisZ,
        [Description("Rotation angle in degrees (positive = counter-clockwise when looking along the axis)")] double angleDegrees)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(RotateComponent),
            new { componentName, axisX, axisY, axisZ, angleDegrees },
            () => assembly.RotateComponent(componentName, axisX, axisY, axisZ, angleDegrees));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Set a component's complete world-space orientation while preserving its current translation. Use this when a single in-plane theta axis is insufficient to distinguish a 180-degree roll.")]
    public async Task<string> SetComponentOrientation(
        [Description("Component instance name, e.g. 'Part1-1'")] string componentName,
        [Description("Requested world-space component X axis as three values")] double[] xAxis,
        [Description("Requested world-space component Y axis as three values")] double[] yAxis,
        [Description("Requested world-space component Z axis as three values")] double[] zAxis,
        [Description("Rebuild the assembly immediately after setting the orientation")] bool rebuild = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SetComponentOrientation),
            new { componentName, xAxis, yAxis, zAxis, rebuild },
            () => assembly.SetComponentOrientation(componentName, xAxis, yAxis, zAxis, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Set one component's complete SolidWorks Transform2 matrix. The array must contain exactly 16 finite values in SolidWorks Transform2 order. Use this for reproducible evidence assemblies rather than chaining approximate moves and rotations.")]
    public async Task<string> SetComponentTransform(
        [Description("Exact or unambiguous component instance name.")] string componentName,
        [Description("Complete 16-value SolidWorks Transform2 array.")] double[] transform,
        [Description("Rebuild the assembly after the transform is assigned.")] bool rebuild = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SetComponentTransform),
            new { componentName, transform, rebuild },
            () => assembly.SetComponentTransform(componentName, transform, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Switch one component instance to an existing referenced configuration and report the actual configuration after rebuild. Use only on a copied or newly-created evidence assembly when source CAD must remain unchanged.")]
    public async Task<string> SetComponentReferencedConfiguration(
        [Description("Exact or unambiguous component instance name.")] string componentName,
        [Description("Existing configuration name in the referenced model.")] string configurationName,
        [Description("Rebuild the assembly after switching the configuration.")] bool rebuild = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SetComponentReferencedConfiguration),
            new { componentName, configurationName, rebuild },
            () => assembly.SetComponentReferencedConfiguration(componentName, configurationName, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Resolve one exact component instance in the active SolidWorks assembly by name, hierarchy path, path, or any combination. Returns a resolved target or explicit ambiguity details for downstream workflows.")]
    public async Task<string> ResolveComponentTarget(
        [Description("Optional component instance name to match exactly, for example Pulley-1.")] string? componentName = null,
        [Description("Optional full hierarchy path to match exactly. This is the most precise selector when available.")] string? hierarchyPath = null,
        [Description("Optional full source model path to match exactly.")] string? componentPath = null)
    {
        var payload = new { componentName, hierarchyPath, componentPath };
        var result = await sta.InvokeLoggedAsync(nameof(ResolveComponentTarget), payload, () => assembly.ResolveComponentTarget(componentName, hierarchyPath, componentPath));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Read one source assembly and export only the direct, two-face basic mates between two requested top-level subassemblies. The source assembly is not modified.")]
    public async Task<string> ExportMatePair(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Exact top-level component name/hierarchy path, or an unambiguous token such as A180.")] string firstModuleSelector,
        [Description("Exact top-level component name/hierarchy path, or an unambiguous token such as A800.")] string secondModuleSelector,
        [Description("Optional JSON output path.")] string? outputPath = null,
        [Description("Write the result to JSON when true.")] bool saveJson = true)
    {
        var payload = new { sourceAssemblyPath, firstModuleSelector, secondModuleSelector, outputPath, saveJson };
        var result = await sta.InvokeLoggedAsync(
            nameof(ExportMatePair),
            payload,
            () => assembly.ExportMatePair(sourceAssemblyPath, firstModuleSelector, secondModuleSelector, outputPath, saveJson));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Rank top-level module pairs that have directly rebuildable two-face basic mates. Use this when a preferred pair has no direct mate.")]
    public async Task<string> FindMatePairCandidates(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Optional module-name tokens to include. Defaults to the known Project 02 process modules.")] string[]? allowedModuleTokens = null,
        [Description("Maximum ranked candidates to return.")] int maxResults = 10)
    {
        var payload = new { sourceAssemblyPath, allowedModuleTokens, maxResults };
        var result = await sta.InvokeLoggedAsync(
            nameof(FindMatePairCandidates),
            payload,
            () => assembly.FindMatePairCandidates(sourceAssemblyPath, allowedModuleTokens, maxResults));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Run a safe mate round-trip demo: export a pair's exact face endpoints from a read-only source assembly, create an independent two-module assembly, rebuild the mates, save/reopen, and verify mate equivalence. Never overwrites an existing output file.")]
    public async Task<string> RoundTripMatePair(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Preferred first top-level module selector, e.g. A180.")] string firstModuleSelector,
        [Description("Preferred second top-level module selector, e.g. A800.")] string secondModuleSelector,
        [Description("New output .SLDASM path. Existing files are never overwritten.")] string outputAssemblyPath,
        [Description("Optional new mate-export JSON path.")] string? exportJsonPath = null,
        [Description("When true, rank and use another known module pair if the preferred pair has no rebuildable direct mate.")] bool allowAutomaticFallback = true,
        [Description("Optional module tokens used by automatic fallback.")] string[]? allowedModuleTokens = null)
    {
        var payload = new { sourceAssemblyPath, firstModuleSelector, secondModuleSelector, outputAssemblyPath, exportJsonPath, allowAutomaticFallback, allowedModuleTokens };
        var result = await sta.InvokeLoggedAsync(
            nameof(RoundTripMatePair),
            payload,
            () => assembly.RoundTripMatePair(sourceAssemblyPath, firstModuleSelector, secondModuleSelector, outputAssemblyPath, exportJsonPath, allowAutomaticFallback, allowedModuleTokens));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Export a read-only module-level mate graph from one source assembly. All binary top-level mate features whose leaf endpoints belong to two requested module subtrees are recorded and grouped into installation-relation bundles.")]
    public async Task<string> ExportModuleMateGraph(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Optional module-name tokens. Project 02 defaults include A600 plus the eight process modules.")] string[]? moduleTokens = null,
        [Description("Optional JSON output path.")] string? outputPath = null,
        [Description("Write the graph JSON when true.")] bool saveJson = true)
    {
        var payload = new { sourceAssemblyPath, moduleTokens, outputPath, saveJson };
        var result = await sta.InvokeLoggedAsync(
            nameof(ExportModuleMateGraph),
            payload,
            () => assembly.ExportModuleMateGraph(sourceAssemblyPath, moduleTokens, outputPath, saveJson));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Read a lightweight audit of one assembly's top-level mate features, including mate types, participating component names, and Width/Slot/Distance advanced parameters. Endpoint faces and persistent references are deliberately not traversed.")]
    public async Task<string> AuditTopLevelMateFeatures(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Optional JSON output path.")] string? outputPath = null,
        [Description("Write the audit JSON when true.")] bool saveJson = true)
    {
        var payload = new { sourceAssemblyPath, outputPath, saveJson };
        var result = await sta.InvokeLoggedAsync(
            nameof(AuditTopLevelMateFeatures),
            payload,
            () => assembly.AuditTopLevelMateFeatures(sourceAssemblyPath, outputPath, saveJson));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Update one named top-level Slot mate in an explicitly supplied assembly copy and return before/after advanced parameters. Constraint values: Free=0, Center=1, Distance=2, Percent=3.")]
    public async Task<string> UpdateTopLevelSlotMate(
        [Description("Full path of the assembly copy to modify and save.")] string assemblyPath,
        [Description("Exact top-level Slot mate feature name, for example 槽口2.")] string mateName,
        [Description("Slot constraint: Free=0, Center=1, Distance=2, Percent=3.")] int constraint,
        [Description("Distance-along-slot value in metres for constraint 2.")] double distance = 0,
        [Description("Percent-along-slot value in [0,100] for constraint 3.")] double percent = 0,
        [Description("Reverse the slot direction.")] bool flipDirection = false,
        [Description("Save the assembly copy after the update.")] bool save = true)
    {
        var payload = new { assemblyPath, mateName, constraint, distance, percent, flipDirection, save };
        var result = await sta.InvokeLoggedAsync(
            nameof(UpdateTopLevelSlotMate),
            payload,
            () => assembly.UpdateTopLevelSlotMate(assemblyPath, mateName, constraint, distance, percent, flipDirection, save));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Build a reusable face-endpoint catalog for selected top-level modules. The catalog is independent of existing mates and records module/leaf identity, referenced configurations, body/face indices, geometric fingerprints, and persistent references.")]
    public async Task<string> BuildFaceEndpointCatalog(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("One or more unique top-level module-name tokens.")] string[] moduleTokens,
        [Description("Optional new JSON output path. Existing files are never overwritten.")] string? outputPath = null,
        [Description("When true, build a fast seed catalog from faces already referenced by source mates. When false, exhaustively traverse module leaf faces.")] bool sourceMateFacesOnly = true,
        [Description("When true, include planar faces only.")] bool planarOnly = true,
        [Description("Ignore faces smaller than this area in square metres.")] double minimumFaceArea = 1e-8,
        [Description("Write the catalog JSON when true.")] bool saveJson = true)
    {
        var payload = new { sourceAssemblyPath, moduleTokens, outputPath, sourceMateFacesOnly, planarOnly, minimumFaceArea, saveJson };
        var result = await sta.InvokeLoggedAsync(
            nameof(BuildFaceEndpointCatalog),
            payload,
            () => assembly.BuildFaceEndpointCatalog(sourceAssemblyPath, moduleTokens, outputPath, sourceMateFacesOnly, planarOnly, minimumFaceArea, saveJson));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Build a bounded reusable face-endpoint catalog from one uniquely selected leaf component inside one top-level module. No sibling leaves or other modules are scanned.")]
    public async Task<string> BuildLeafFaceEndpointCatalog(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("Unique top-level module-name token that owns the leaf.")] string moduleToken,
        [Description("Unique leaf instance name, relative hierarchy path, or source-file stem inside the module.")] string leafSelector,
        [Description("Optional new JSON output path. Existing files are never overwritten.")] string? outputPath = null,
        [Description("When true, include planar faces only.")] bool planarOnly = true,
        [Description("Ignore faces smaller than this area in square metres.")] double minimumFaceArea = 1e-8,
        [Description("Explicit safety limit for total faces exposed by the selected leaf.")] int maximumFaceCount = 500,
        [Description("Write the catalog JSON when true.")] bool saveJson = true)
    {
        var payload = new { sourceAssemblyPath, moduleToken, leafSelector, outputPath, planarOnly, minimumFaceArea, maximumFaceCount, saveJson };
        var result = await sta.InvokeLoggedAsync(
            nameof(BuildLeafFaceEndpointCatalog),
            payload,
            () => assembly.BuildLeafFaceEndpointCatalog(sourceAssemblyPath, moduleToken, leafSelector, outputPath, planarOnly, minimumFaceArea, maximumFaceCount, saveJson));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Resolve one EndpointId from a saved face catalog, select that face in the catalog source assembly, and optionally zoom to it for visual confirmation.")]
    public async Task<string> SelectFaceEndpointFromCatalog(
        [Description("Full path of a solidworks-face-endpoint-catalog/v1 JSON file.")] string catalogPath,
        [Description("Exact stable EndpointId to select.")] string endpointId,
        [Description("Zoom the active view to the selected face when true.")] bool zoomToSelection = true)
    {
        var payload = new { catalogPath, endpointId, zoomToSelection };
        var result = await sta.InvokeLoggedAsync(
            nameof(SelectFaceEndpointFromCatalog),
            payload,
            () => assembly.SelectFaceEndpointFromCatalog(catalogPath, endpointId, zoomToSelection));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Capture the first face selected in the active SolidWorks assembly as a reusable face-endpoint catalog entry. The supplied module token must uniquely identify the selected face's top-level module.")]
    public async Task<string> CaptureSelectedFaceEndpoint(
        [Description("Unique top-level module-name token that owns the selected face.")] string moduleToken)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(CaptureSelectedFaceEndpoint),
            new { moduleToken },
            () => assembly.CaptureSelectedFaceEndpoint(moduleToken));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Run one controlled full module-mate reconstruction experiment. Modes: source_pose, mate_only, residual_anchors. Creates a new assembly, rebuilds all exported inter-module mates including Width and Slot, saves/reopens, and reports pose errors. Never overwrites an existing file.")]
    public async Task<string> RunModuleMateReconstructionExperiment(
        [Description("Full path of the read-only source .SLDASM.")] string sourceAssemblyPath,
        [Description("New output .SLDASM path. Existing files are never overwritten.")] string outputAssemblyPath,
        [Description("Experiment mode: source_pose, mate_only, or residual_anchors.")] string mode,
        [Description("Unique fixed base token. Defaults to A600.")] string baseModuleToken = "A600",
        [Description("Optional module-name tokens. Defaults to the Project 02 module graph set.")] string[]? moduleTokens = null,
        [Description("Only for residual_anchors: module tokens or source hierarchy paths whose full source transform is retained as a conservative residual anchor.")] string[]? residualAnchorModuleSelectors = null,
        [Description("Translation tolerance for source-pose equivalence, in meters.")] double poseToleranceMeters = 1e-5,
        [Description("Maximum absolute rotation-matrix element tolerance.")] double rotationTolerance = 1e-6)
    {
        var payload = new { sourceAssemblyPath, outputAssemblyPath, mode, baseModuleToken, moduleTokens, residualAnchorModuleSelectors, poseToleranceMeters, rotationTolerance };
        var result = await sta.InvokeLoggedAsync(
            nameof(RunModuleMateReconstructionExperiment),
            payload,
            () => assembly.RunModuleMateReconstructionExperiment(
                sourceAssemblyPath,
                outputAssemblyPath,
                mode,
                baseModuleToken,
                moduleTokens,
                residualAnchorModuleSelectors,
                poseToleranceMeters,
                rotationTolerance));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Create a new assembly from a compiled editable module-mate graph JSON. This reads the JSON as the executable source of truth, does not re-export prototype mates, never overwrites an existing assembly, and saves/reopens to verify mate types and distance/angle values.")]
    public async Task<string> RebuildAssemblyFromMateGraph(
        [Description("Full path of an editable-module-mate-graph/v1 JSON file.")] string effectiveMateGraphPath,
        [Description("Full path for the new .SLDASM. Existing files are never overwritten.")] string outputAssemblyPath,
        [Description("Optional unique base module token or hierarchy path. Defaults to EditPolicy.baseModuleToken.")] string? baseModuleToken = null,
        [Description("Initial placement: deterministic or source_pose. Defaults to EditPolicy.initialPlacementMode.")] string? initialPlacementMode = null)
    {
        var payload = new { effectiveMateGraphPath, outputAssemblyPath, baseModuleToken, initialPlacementMode };
        var result = await sta.InvokeLoggedAsync(
            nameof(RebuildAssemblyFromMateGraph),
            payload,
            () => assembly.RebuildAssemblyFromMateGraph(
                effectiveMateGraphPath,
                outputAssemblyPath,
                baseModuleToken,
                initialPlacementMode));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Copy an existing assembly context and apply an editable mate-graph patch directly to components already present in the copy. PatchAudit addMate creates only the new mate; updateMate replaces only the edited relation; removeMate suppresses only the deleted relation. Existing components are not reinserted or displaced. Legacy graphs without PatchAudit retain the older remate experiment behaviour.")]
    public async Task<string> RemateComponentInAssemblyContextFromMateGraph(
        [Description("Full path of the existing source assembly. It is never modified.")] string sourceAssemblyPath,
        [Description("Full path of the compiled effective mate graph JSON.")] string effectiveMateGraphPath,
        [Description("New .SLDASM output path. Existing files are rejected.")] string outputAssemblyPath,
        [Description("Module token to displace and remate, for example A500.")] string targetModuleToken,
        [Description("When true, require the source to be the active resolved assembly, verify all graph endpoints there, then Save As the working output without reopening a lightweight copy.")] bool preserveResolvedSourceSession = false,
        [Description("When true, suppress the replaced source mates and deliberately move the target to a deterministic non-source pose before rebuilding the requested mate bundle.")] bool forceInitialDisplacement = false)
    {
        var payload = new { sourceAssemblyPath, effectiveMateGraphPath, outputAssemblyPath, targetModuleToken, preserveResolvedSourceSession, forceInitialDisplacement };
        var result = await sta.InvokeLoggedAsync(
            nameof(RemateComponentInAssemblyContextFromMateGraph),
            payload,
            () => assembly.RemateComponentInAssemblyContextFromMateGraph(
                sourceAssemblyPath,
                effectiveMateGraphPath,
                outputAssemblyPath,
                targetModuleToken,
                preserveResolvedSourceSession,
                forceInitialDisplacement));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Measure validation-only relations in an existing saved assembly checkpoint without rebuilding mates, saving, or mutating the CAD document.")]
    public async Task<string> VerifyRelationsInAssemblyContextFromMateGraph(
        [Description("Full path of the existing saved .SLDASM checkpoint. It is never modified.")] string sourceAssemblyPath,
        [Description("Full path of the compiled effective mate graph JSON containing ValidationRelations and no driving mates.")] string effectiveMateGraphPath,
        [Description("Module token participating in the validation graph, for example A500.")] string targetModuleToken,
        [Description("When true, require the source to be the active resolved assembly instead of opening it.")] bool preserveResolvedSourceSession = false)
    {
        var payload = new { sourceAssemblyPath, effectiveMateGraphPath, targetModuleToken, preserveResolvedSourceSession };
        var result = await sta.InvokeLoggedAsync(
            nameof(VerifyRelationsInAssemblyContextFromMateGraph),
            payload,
            () => assembly.VerifyRelationsInAssemblyContextFromMateGraph(
                sourceAssemblyPath,
                effectiveMateGraphPath,
                targetModuleToken,
                preserveResolvedSourceSession));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Copy an existing assembly context, remove the original target instance, insert a fresh instance from the target module file at a deterministic non-source pose, and locate it only through an effective mate graph. Existing flexible context modules remain in their parent assembly.")]
    public async Task<string> InsertComponentInAssemblyContextFromMateGraph(
        [Description("Full path of the existing source assembly. It is never modified.")] string sourceAssemblyPath,
        [Description("Full path of the compiled effective mate graph JSON.")] string effectiveMateGraphPath,
        [Description("New .SLDASM output path. Existing files are rejected.")] string outputAssemblyPath,
        [Description("Module token to remove and freshly insert, for example A500.")] string targetModuleToken)
    {
        var payload = new { sourceAssemblyPath, effectiveMateGraphPath, outputAssemblyPath, targetModuleToken };
        var result = await sta.InvokeLoggedAsync(
            nameof(InsertComponentInAssemblyContextFromMateGraph),
            payload,
            () => assembly.InsertComponentInAssemblyContextFromMateGraph(
                sourceAssemblyPath,
                effectiveMateGraphPath,
                outputAssemblyPath,
                targetModuleToken));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Copy a solved parent assembly and retain only the requested top-level component source files as a static context snapshot. The source is never modified. The result is for geometry/collision review and does not claim motion reconstruction.")]
    public async Task<string> CreateAssemblyStaticContextSubset(
        [Description("Full path of the solved source .SLDASM. It is never modified.")] string sourceAssemblyPath,
        [Description("New output .SLDASM path. Existing files are rejected.")] string outputAssemblyPath,
        [Description("Full source-model paths of the top-level components to retain exactly once.")] string[] keepComponentPaths)
    {
        var payload = new { sourceAssemblyPath, outputAssemblyPath, keepComponentPaths };
        var result = await sta.InvokeLoggedAsync(
            nameof(CreateAssemblyStaticContextSubset),
            payload,
            () => assembly.CreateAssemblyStaticContextSubset(
                sourceAssemblyPath,
                outputAssemblyPath,
                keepComponentPaths));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Analyze how many placements would change if the resolved component's source file were edited directly. Use this before any geometry-changing part edit.")]
    public async Task<string> AnalyzeSharedPartEditImpact(
        [Description("Optional component instance name to match exactly, for example Pulley-1.")] string? componentName = null,
        [Description("Optional full hierarchy path to match exactly. This is the most precise selector when available.")] string? hierarchyPath = null,
        [Description("Optional full source model path to match exactly.")] string? componentPath = null)
    {
        var payload = new { componentName, hierarchyPath, componentPath };
        var result = await sta.InvokeLoggedAsync(nameof(AnalyzeSharedPartEditImpact), payload, () => assembly.AnalyzeSharedPartEditImpact(componentName, hierarchyPath, componentPath));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Run a static interference check in the active SolidWorks assembly using the official ToolsCheckInterference2 workflow. The assembly must be fully resolved, and this tool temporarily changes the selection set while it runs.")]
    public async Task<string> CheckInterference(
        [Description("Optional component instance hierarchy paths to check. Leave null to check the whole active assembly.")] string[]? hierarchyPaths = null,
        [Description("When true, coincident or touching faces are treated as interference.")] bool treatCoincidenceAsInterference = false)
    {
        var payload = new { hierarchyPaths, treatCoincidenceAsInterference };
        var result = await sta.InvokeLoggedAsync(nameof(CheckInterference), payload, () => assembly.CheckInterference(hierarchyPaths, treatCoincidenceAsInterference));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Run a time-efficient exact B-Rep interference check between two module instances. The tool expands each module to transformed leaf solid bodies, uses body AABBs only for broad-phase filtering, and checks every surviving body pair with the SolidWorks modeler kernel.")]
    public async Task<string> CheckInterferenceByLeafBodies(
        [Description("Exactly two component instance hierarchy paths to check.")] string[] hierarchyPaths,
        [Description("When true, coincident or touching faces are treated as interference.")] bool treatCoincidenceAsInterference = false)
    {
        var payload = new { hierarchyPaths, treatCoincidenceAsInterference };
        var result = await sta.InvokeLoggedAsync(
            nameof(CheckInterferenceByLeafBodies),
            payload,
            () => assembly.CheckInterferenceByLeafBodies(hierarchyPaths, treatCoincidenceAsInterference));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Capture conservative world-space bounding boxes for every transformed leaf solid body below one module instance. Pass @root to capture all top-level children of the active standalone assembly. This read-only tool is intended for generating multi-box occupancy models and portal/channel evidence.")]
    public async Task<string> CaptureLeafBodyEnvelopes(
        [Description("Exact hierarchy path of one top-level or nested module instance, or @root for the active standalone assembly.")] string hierarchyPath)
    {
        var payload = new { hierarchyPath };
        var result = await sta.InvokeLoggedAsync(
            nameof(CaptureLeafBodyEnvelopes),
            payload,
            () => assembly.CaptureLeafBodyEnvelopes(hierarchyPath));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Replace a top-level component instance in the active SolidWorks assembly with another model file. For subassembly content, open the owning subassembly first.")]
    public async Task<string> ReplaceComponent(
        [Description("Hierarchy path of the component instance to replace. The target must be top-level in the active assembly.")] string hierarchyPath,
        [Description("Full file path to the replacement part or assembly.")] string replacementFilePath,
        [Description("Optional configuration name in the replacement model. Empty string uses the default or matched configuration.")] string configName = "",
        [Description("When true, replace all instances of the selected component in the active assembly.")] bool replaceAllInstances = false,
        [Description("Configuration choice: MatchName=0, ManuallySelect=1.")] int useConfigChoice = 0,
        [Description("When true, SolidWorks attempts to reattach existing mates to the replacement component.")] bool reattachMates = true)
    {
        var payload = new { hierarchyPath, replacementFilePath, configName, replaceAllInstances, useConfigChoice, reattachMates };
        var result = await sta.InvokeLoggedAsync(nameof(ReplaceComponent), payload, () => assembly.ReplaceComponent(hierarchyPath, replacementFilePath, configName, replaceAllInstances, useConfigChoice, reattachMates));
        return JsonSerializer.Serialize(result);
    }
}
