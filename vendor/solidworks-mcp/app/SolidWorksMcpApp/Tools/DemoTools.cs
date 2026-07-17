using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace SolidWorksMcpApp.Tools;

public record DemoComponentLayout(
    string? ComponentName,
    string? FilePath,
    double X,
    double Y,
    double Z,
    string BottomFaceName = "\u5e95\u9762",
    double? CurrentX = null,
    double? CurrentY = null,
    double? CurrentZ = null);

public record DemoComponentArrangementResult(
    string RequestedComponentName,
    string ComponentName,
    string? FilePath,
    string BottomFaceName,
    bool Inserted,
    bool FaceMappingFound,
    FaceMappingResult? FaceSelection,
    MateOperationResult? BottomMateResult,
    SelectedFaceCenterResult? BottomFaceCenter,
    ComponentTransformResult? MoveResult);

public record DemoArrangementResult(
    bool Success,
    string Message,
    bool AlignBottom,
    double BaseZ,
    SwDocumentInfo? CreatedDocument,
    SwOpenResult? OpenedDocument,
    RebuildExecutionResult? Rebuild,
    SwImageExportResult? Screenshot,
    IReadOnlyList<DemoComponentArrangementResult> Components,
    IReadOnlyList<string> MissingFaceMappings);

public record DemoInitializationResult(
    bool Success,
    string Message,
    string AssemblyPath,
    string BasePlaneName,
    string BasePlaneSelectionType,
    SwDocumentInfo? CreatedDocument,
    SwSaveResult? SaveResult,
    RebuildExecutionResult? Rebuild,
    SwImageExportResult? Screenshot,
    IReadOnlyList<DemoComponentArrangementResult> Components,
    IReadOnlyList<string> MissingFaceMappings);

public record DemoCommonBaseResult(
    bool Success,
    string Message,
    string AssemblyPath,
    SwOpenResult? OpenedDocument,
    SwSaveResult? SaveResult,
    RebuildExecutionResult? Rebuild,
    SwImageExportResult? Screenshot,
    IReadOnlyList<DemoComponentArrangementResult> Components,
    IReadOnlyList<string> MissingFaceMappings,
    IReadOnlyList<DemoBottomOrientationCorrection> OrientationCorrections,
    IReadOnlyList<DemoBottomOrientationCheck> OrientationChecks);

public record DemoBottomOrientationCorrection(
    string Stage,
    string ComponentName,
    string BottomFaceName,
    bool Success,
    bool Applied,
    double[]? RotationAxis,
    double AngleDegrees,
    FaceMappingProbeResult? BeforeProbe,
    FaceMappingProbeResult? AfterRotationProbe,
    FaceMappingProbeResult? AfterRestoreProbe,
    ComponentTransformResult? RotationResult,
    ComponentTransformResult? RestoreCenterMoveResult,
    string Message);

public record DemoBottomOrientationCheck(
    string ComponentName,
    string BottomFaceName,
    bool Success,
    bool MatchesBase,
    double? DotWithBase,
    double NormalDotThreshold,
    double[]? WorldNormal,
    FaceMappingResult? FaceSelection,
    FaceMappingProbeResult? FaceProbe,
    string Message);

public record DemoLayoutCaptureComponent(
    string? ComponentName,
    string BottomFaceName = "\u5e95\u9762");

public record DemoDiscoveredLayoutComponent(
    string ComponentName,
    string DisplayName,
    string FilePath,
    string HierarchyPath,
    int Depth,
    bool IsAssembly,
    bool IsPart,
    bool IsSuppressed,
    bool IsHidden,
    double[]? Transform,
    double[]? Translation,
    double[]? XAxis,
    double[]? YAxis,
    double[]? ZAxis,
    string DefaultBottomFaceName);

public record DemoLayoutComponentDiscoveryResult(
    bool Success,
    string Message,
    string? SourceAssemblyPath,
    string Scope,
    bool IncludeParts,
    bool IncludeSuppressed,
    int ComponentCount,
    IReadOnlyList<DemoDiscoveredLayoutComponent> Components);

public record DemoCapturedLayoutComponent(
    string ComponentName,
    string FilePath,
    string HierarchyPath,
    string BottomFaceName,
    double[]? SourceTransform,
    double[]? ComponentTranslation,
    double[]? ComponentXAxis,
    double[]? ComponentYAxis,
    double[]? ComponentZAxis,
    double[]? BottomCenterWorld,
    double[]? BottomNormalWorld,
    CommonBaseLayout2d? Layout2d,
    bool FaceMappingFound,
    FaceMappingResult? FaceSelection,
    FaceMappingProbeResult? FaceProbe);

public record DemoCapturedLayoutDocument(
    bool Success,
    string Message,
    string? SourceAssemblyPath,
    string BaseComponentName,
    CommonBaseFrame? BaseFrame,
    IReadOnlyList<DemoCapturedLayoutComponent> Components,
    IReadOnlyList<string> MissingFaceMappings,
    string? OutputPath);

public record DemoApplyCapturedLayoutComponentResult(
    string ComponentName,
    string BottomFaceName,
    CommonBaseLayout2d? Layout2d,
    double[]? TargetBottomCenterWorld,
    FaceMappingResult? FaceSelection,
    SelectedFaceCenterResult? BottomFaceCenter,
    ComponentTransformResult? RotationResult,
    double? CurrentThetaDegrees,
    double? TargetThetaDegrees,
    double? DeltaThetaDegrees,
    ComponentTransformResult? MoveResult,
    string Message);

public record DemoApplyCapturedLayoutResult(
    bool Success,
    string Message,
    string LayoutJsonPath,
    string? AssemblyPath,
    SwOpenResult? OpenedDocument,
    RebuildExecutionResult? Rebuild,
    SwImageExportResult? Screenshot,
    IReadOnlyList<DemoApplyCapturedLayoutComponentResult> Components);

[McpServerToolType]
public class DemoTools(
    StaDispatcher sta,
    IDocumentService docs,
    IAssemblyService assembly,
    ISelectionService selection)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = false,
    };

    [McpServerTool, Description("Initialize the demo assembly once: create a fixed assembly file, insert subassemblies at their requested positions, rebuild, save, and optionally export a screenshot. This does not create common-base mates and does not move components by bottom-face centers.")]
    public async Task<string> InitializeCommonBaseAssembly(
        [Description("Components to insert and initialize. Each component must provide filePath, componentName, x/y/z, and bottomFaceName.")]
        DemoComponentLayout[] components,
        [Description("Output assembly path to save and reuse for later movement calls.")]
        string outputAssemblyPath,
        [Description("Optional assembly template path used when creating the new assembly.")]
        string? templatePath = null,
        [Description("Reference movement plane used to interpret later 2D moves. For XY movement use Front Plane.")]
        string basePlaneName = "Front Plane",
        [Description("Reserved for future reference-plane mate support. Not used by the current entity-face mate workflow.")]
        string basePlaneSelectionType = "PLANE",
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(InitializeCommonBaseAssembly),
            new { components, outputAssemblyPath, templatePath, basePlaneName, basePlaneSelectionType, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => InitializeCore(
                components,
                outputAssemblyPath,
                templatePath,
                basePlaneName,
                basePlaneSelectionType,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Append one batch of components to an initialized common-base assembly target. Opens an existing assembly or creates it when missing, inserts only the supplied batch, saves progress, and optionally exports a screenshot. This is intended for large assemblies where one-shot initialize can time out.")]
    public async Task<string> AppendComponentsToCommonBaseAssembly(
        [Description("Component batch to insert. Each component must provide filePath, componentName, x/y/z, and bottomFaceName.")]
        DemoComponentLayout[] components,
        [Description("Output assembly path to create or append to.")]
        string outputAssemblyPath,
        [Description("Optional assembly template path used when creating the new assembly.")]
        string? templatePath = null,
        [Description("Reference movement plane used to interpret later 2D moves. For XY movement use Front Plane.")]
        string basePlaneName = "Front Plane",
        [Description("Reserved for future reference-plane mate support. Not used by the current entity-face mate workflow.")]
        string basePlaneSelectionType = "PLANE",
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AppendComponentsToCommonBaseAssembly),
            new { components, outputAssemblyPath, templatePath, basePlaneName, basePlaneSelectionType, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => AppendComponentsCore(
                components,
                outputAssemblyPath,
                templatePath,
                basePlaneName,
                basePlaneSelectionType,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Finalize an existing demo assembly once by mating later component bottom faces coincident to the first component bottom face, rebuilding, saving, and optionally exporting a screenshot. This does not move components to target coordinates.")]
    public async Task<string> FinalizeCommonBaseAssembly(
        [Description("Existing components whose bottom faces should be mated. Provide componentName and bottomFaceName.")]
        DemoComponentLayout[] components,
        [Description("Existing initialized assembly path to open or activate.")]
        string assemblyPath,
        [Description("Minimum dot product required for each component bottom-face world normal to match the base component normal. Defaults to 0.95.")]
        double normalDotThreshold = 0.95,
        [Description("When true, attempts to align component bottom-face normals using Transform2 before coincident mates are created. Defaults to true.")]
        bool enablePreMateOrientationCorrection = true,
        [Description("Experimental. When true, attempts to rotate components after coincident mates are created so bottom-face normals match. Defaults to false because rotating mated components can make SolidWorks solve for a long time.")]
        bool enablePostMateOrientationCorrection = false,
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(FinalizeCommonBaseAssembly),
            new { components, assemblyPath, normalDotThreshold, enablePreMateOrientationCorrection, enablePostMateOrientationCorrection, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => FinalizeCommonBaseCore(
                components,
                assemblyPath,
                normalDotThreshold,
                enablePreMateOrientationCorrection,
                enablePostMateOrientationCorrection,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Move existing components inside an already initialized common-base assembly. This does not insert components and does not recreate common-base mates.")]
    public async Task<string> MoveComponentsOnCommonBase(
        [Description("Existing components to move. Provide componentName plus target x/y/z and bottomFaceName. filePath is ignored.")]
        DemoComponentLayout[] components,
        [Description("Existing initialized assembly path to open or activate.")]
        string assemblyPath,
        [Description("Reference plane used during initialization. For XY movement use Front Plane.")]
        string basePlaneName = "Front Plane",
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(MoveComponentsOnCommonBase),
            new { components, assemblyPath, basePlaneName, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => MoveExistingCore(
                components,
                assemblyPath,
                basePlaneName,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("High-level demo workflow: create or open an assembly, insert subassemblies, verify recorded bottom-face mappings, mate all bottom faces coplanar to the first component bottom face, apply target positions, rebuild, and optionally export a PNG screenshot.")]
    public async Task<string> ArrangeComponentsOnCommonBase(
        [Description("Components to arrange. For first import, provide filePath plus x/y/z. For existing components, provide componentName plus currentX/currentY/currentZ and target x/y/z.")]
        DemoComponentLayout[] components,
        [Description("Optional existing assembly path to open. Leave empty to create a new assembly document.")]
        string? assemblyPath = null,
        [Description("Optional assembly template path used when creating a new assembly.")]
        string? templatePath = null,
        [Description("When true, each component must already have a recorded bottom-face mapping; the tool mates every later component bottom face coincident to the first component bottom face.")]
        bool alignBottom = true,
        [Description("Fallback common bottom height in meters when alignBottom=false. When alignBottom=true, bottom coplanarity is created with coincident mates.")]
        double baseZ = 0,
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ArrangeComponentsOnCommonBase),
            new { components, assemblyPath, templatePath, alignBottom, baseZ, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => ArrangeCore(
                components,
                assemblyPath,
                templatePath,
                alignBottom,
                baseZ,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Capture a source assembly's common-base 2D layout. The tool reads component Transform2 plus recorded bottom-face mappings, projects bottom centers into a base frame, and optionally writes layout JSON. It does not modify the assembly.")]
    public async Task<string> CaptureCommonBaseLayoutFromAssembly(
        [Description("Optional source assembly path. Leave empty to use the active assembly.")]
        string? sourceAssemblyPath = null,
        [Description("Optional component list. Leave empty to capture all top-level components. Each entry can provide componentName and bottomFaceName.")]
        DemoLayoutCaptureComponent[]? components = null,
        [Description("Base component used as the 2D layout origin. Defaults to the first captured component.")]
        string? baseComponentName = null,
        [Description("Optional output JSON path. Leave empty to return data only.")]
        string? outputPath = null)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(CaptureCommonBaseLayoutFromAssembly),
            new { sourceAssemblyPath, components, baseComponentName, outputPath },
            () => CaptureCommonBaseLayoutCore(
                sourceAssemblyPath,
                components,
                baseComponentName,
                outputPath));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Discover candidate layout components from a source assembly. This is read-only and returns resolved component names, file paths, hierarchy paths, and Transform2 data. It does not infer bottom faces.")]
    public async Task<string> DiscoverLayoutComponentsFromAssembly(
        [Description("Optional source assembly path. Leave empty to use the active assembly.")]
        string? sourceAssemblyPath = null,
        [Description("Discovery scope. Use topLevelOnly for direct child components, or recursive for all resolved descendants.")]
        string scope = "topLevelOnly",
        [Description("Whether to include part files. False keeps only subassemblies.")]
        bool includeParts = false,
        [Description("Reserved for a future suppressed-component implementation. Current version discovers resolved components only.")]
        bool includeSuppressed = false,
        [Description("Bottom face name assigned to each discovered component in the generated project config.")]
        string defaultBottomFaceName = "\u5e95\u9762")
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(DiscoverLayoutComponentsFromAssembly),
            new { sourceAssemblyPath, scope, includeParts, includeSuppressed, defaultBottomFaceName },
            () => DiscoverLayoutComponentsFromAssemblyCore(
                sourceAssemblyPath,
                scope,
                includeParts,
                includeSuppressed,
                defaultBottomFaceName));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    [McpServerTool, Description("Apply a previously captured common-base layout JSON to the active or specified assembly. Moves each component so its recorded bottom-face center reaches the captured layout2d position in the captured base frame. This does not create mates or fix orientation.")]
    public async Task<string> ApplyCapturedCommonBaseLayout(
        [Description("Path to a JSON file produced by CaptureCommonBaseLayoutFromAssembly.")]
        string layoutJsonPath,
        [Description("Optional target assembly path. Leave empty to use the active assembly.")]
        string? assemblyPath = null,
        [Description("Optional output PNG path. Leave empty to skip screenshot export.")]
        string? screenshotPath = null,
        [Description("Screenshot width in pixels.")]
        int screenshotWidth = 1600,
        [Description("Screenshot height in pixels.")]
        int screenshotHeight = 900,
        [Description("When true, includes base64 PNG data in the result.")]
        bool includeScreenshotBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ApplyCapturedCommonBaseLayout),
            new { layoutJsonPath, assemblyPath, screenshotPath, screenshotWidth, screenshotHeight, includeScreenshotBase64Data },
            () => ApplyCapturedCommonBaseLayoutCore(
                layoutJsonPath,
                assemblyPath,
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data));

        return JsonSerializer.Serialize(result, JsonOptions);
    }

    private DemoLayoutComponentDiscoveryResult DiscoverLayoutComponentsFromAssemblyCore(
        string? sourceAssemblyPath,
        string scope,
        bool includeParts,
        bool includeSuppressed,
        string defaultBottomFaceName)
    {
        SwOpenResult? openedDocument = null;
        if (!string.IsNullOrWhiteSpace(sourceAssemblyPath))
        {
            openedDocument = docs.OpenDocument(Path.GetFullPath(sourceAssemblyPath));
        }

        var normalizedScope = string.Equals(scope, "recursive", StringComparison.OrdinalIgnoreCase)
            ? "recursive"
            : "topLevelOnly";
        var recursive = string.Equals(normalizedScope, "recursive", StringComparison.OrdinalIgnoreCase);
        var bottomName = string.IsNullOrWhiteSpace(defaultBottomFaceName) ? "\u5e95\u9762" : defaultBottomFaceName;
        var discovered = assembly.ListComponentPoses(topLevelOnly: !recursive)
            .Select(pose =>
            {
                var extension = Path.GetExtension(pose.Path);
                var isAssembly = string.Equals(extension, ".SLDASM", StringComparison.OrdinalIgnoreCase);
                var isPart = string.Equals(extension, ".SLDPRT", StringComparison.OrdinalIgnoreCase);
                return new
                {
                    Pose = pose,
                    IsAssembly = isAssembly,
                    IsPart = isPart,
                };
            })
            .Where(item => includeParts || item.IsAssembly)
            .Select(item => new DemoDiscoveredLayoutComponent(
                item.Pose.Name,
                item.Pose.Name,
                item.Pose.Path,
                item.Pose.HierarchyPath,
                item.Pose.Depth,
                item.IsAssembly,
                item.IsPart,
                false,
                false,
                item.Pose.Transform,
                item.Pose.Translation,
                item.Pose.XAxis,
                item.Pose.YAxis,
                item.Pose.ZAxis,
                bottomName))
            .ToList()
            .AsReadOnly();

        var message = includeSuppressed
            ? "DiscoverLayoutComponentsFromAssembly completed for resolved components. Suppressed components are not included in this version."
            : "DiscoverLayoutComponentsFromAssembly completed.";

        return new DemoLayoutComponentDiscoveryResult(
            true,
            message,
            sourceAssemblyPath ?? openedDocument?.Document.Path,
            normalizedScope,
            includeParts,
            includeSuppressed,
            discovered.Count,
            discovered);
    }

    private DemoCapturedLayoutDocument CaptureCommonBaseLayoutCore(
        string? sourceAssemblyPath,
        DemoLayoutCaptureComponent[]? requestedComponents,
        string? baseComponentName,
        string? outputPath)
    {
        SwOpenResult? openedDocument = null;
        if (!string.IsNullOrWhiteSpace(sourceAssemblyPath))
        {
            openedDocument = docs.OpenDocument(Path.GetFullPath(sourceAssemblyPath));
        }

        var poses = assembly.ListComponentPoses(topLevelOnly: true)
            .ToDictionary(pose => pose.Name, StringComparer.OrdinalIgnoreCase);

        var requested = requestedComponents is { Length: > 0 }
            ? requestedComponents
                .Where(component => !string.IsNullOrWhiteSpace(component.ComponentName))
                .ToArray()
            : poses.Values
                .Select(pose => new DemoLayoutCaptureComponent(pose.Name))
                .ToArray();

        if (requested.Length == 0)
        {
            return new DemoCapturedLayoutDocument(
                false,
                "No top-level components found to capture.",
                sourceAssemblyPath,
                baseComponentName ?? "",
                null,
                Array.Empty<DemoCapturedLayoutComponent>(),
                Array.Empty<string>(),
                outputPath);
        }

        var captured = new List<DemoCapturedLayoutComponent>();
        var missing = new List<string>();
        foreach (var item in requested)
        {
            var componentName = item.ComponentName?.Trim() ?? "";
            var bottomFaceName = string.IsNullOrWhiteSpace(item.BottomFaceName) ? "\u5e95\u9762" : item.BottomFaceName;
            poses.TryGetValue(componentName, out var pose);

            if (pose == null)
            {
                missing.Add($"Component not found in source assembly: {componentName}");
                captured.Add(new DemoCapturedLayoutComponent(
                    componentName,
                    "",
                    "",
                    bottomFaceName,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    false,
                    null,
                    null));
                continue;
            }

            selection.ClearSelection();
            var faceSelection = selection.SelectFaceByName(bottomFaceName, componentName, append: false, mark: 0);
            FaceMappingProbeResult? probe = null;
            if (faceSelection.Success)
            {
                probe = selection.GetSelectedFaceMappingProbe(bottomFaceName, componentName);
            }
            else
            {
                missing.Add($"Bottom face mapping unavailable. componentName={componentName}, faceName={bottomFaceName}, message={faceSelection.Message}");
            }

            captured.Add(new DemoCapturedLayoutComponent(
                componentName,
                pose.Path,
                pose.HierarchyPath,
                bottomFaceName,
                pose.Transform,
                pose.Translation,
                pose.XAxis,
                pose.YAxis,
                pose.ZAxis,
                probe?.WorldCenter,
                probe?.WorldNormal,
                null,
                faceSelection.Success,
                faceSelection,
                probe));
        }

        var baseName = string.IsNullOrWhiteSpace(baseComponentName)
            ? captured.FirstOrDefault(component => component.BottomCenterWorld != null && component.BottomNormalWorld != null)?.ComponentName ?? ""
            : baseComponentName.Trim();
        var anchor = captured.FirstOrDefault(component =>
            string.Equals(component.ComponentName, baseName, StringComparison.OrdinalIgnoreCase));

        if (anchor?.BottomCenterWorld == null || anchor.BottomNormalWorld == null)
        {
            missing.Add($"Base component bottom face center/normal is unavailable: {baseName}");
            var failed = new DemoCapturedLayoutDocument(
                false,
                "CaptureCommonBaseLayoutFromAssembly failed. Record and verify bottom faces first.",
                sourceAssemblyPath ?? openedDocument?.Document.Path,
                baseName,
                null,
                captured.AsReadOnly(),
                missing.AsReadOnly(),
                outputPath);
            WriteCapturedLayoutIfRequested(failed, outputPath);
            return failed;
        }

        var frame = CommonBaseLayoutMath.CreateFrame(
            anchor.BottomCenterWorld,
            anchor.BottomNormalWorld,
            anchor.ComponentXAxis);

        var projected = captured
            .Select(component => component.BottomCenterWorld == null
                ? component
                : component with
                {
                    Layout2d = CommonBaseLayoutMath.ProjectPointWithRotation(
                        component.BottomCenterWorld,
                        frame,
                        component.ComponentXAxis,
                        component.ComponentYAxis,
                        component.ComponentZAxis),
                })
            .ToList()
            .AsReadOnly();

        var success = missing.Count == 0 && projected.All(component => component.Layout2d != null);
        var result = new DemoCapturedLayoutDocument(
            success,
            success
                ? "CaptureCommonBaseLayoutFromAssembly completed."
                : "CaptureCommonBaseLayoutFromAssembly completed with missing mappings or incomplete probes.",
            sourceAssemblyPath ?? openedDocument?.Document.Path,
            baseName,
            frame,
            projected,
            missing.AsReadOnly(),
            outputPath);

        WriteCapturedLayoutIfRequested(result, outputPath);
        return result;
    }

    private static void WriteCapturedLayoutIfRequested(DemoCapturedLayoutDocument document, string? outputPath)
    {
        if (string.IsNullOrWhiteSpace(outputPath))
        {
            return;
        }

        var normalized = Path.GetFullPath(outputPath);
        var directory = Path.GetDirectoryName(normalized);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(normalized, JsonSerializer.Serialize(document, JsonOptions));
    }

    private static double[]? GetPoseAxis(ComponentPoseInfo? pose, string? axisName)
    {
        if (pose == null || string.IsNullOrWhiteSpace(axisName))
        {
            return null;
        }

        return axisName.Trim().ToLowerInvariant() switch
        {
            "x" or "xaxis" or "componentxaxis" => pose.XAxis,
            "y" or "yaxis" or "componentyaxis" => pose.YAxis,
            "z" or "zaxis" or "componentzaxis" => pose.ZAxis,
            _ => null,
        };
    }

    private DemoApplyCapturedLayoutResult ApplyCapturedCommonBaseLayoutCore(
        string layoutJsonPath,
        string? assemblyPath,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        // Replay Layout 主流程：
        // 1. 读取 Capture 阶段生成的 layout2d；
        // 2. 将 layout2d 反算成共同底平面上的目标世界坐标；
        // 3. 如有 theta，则先绕共同底面法向做平面内旋转；
        // 4. 通过 SelectFaceByName 选回当前组件底面，并 probe 当前底面中心；
        // 5. 用 MoveComponent 按“目标底面中心 - 当前底面中心”的差值移动组件。
        // 因此 replay 精度依赖两件事：layout2d 本身正确，以及 SelectFaceByName 能选回真实底面。
        if (string.IsNullOrWhiteSpace(layoutJsonPath))
        {
            throw new ArgumentException("layoutJsonPath must not be empty.", nameof(layoutJsonPath));
        }

        var normalizedLayoutPath = Path.GetFullPath(layoutJsonPath);
        if (!File.Exists(normalizedLayoutPath))
        {
            throw new FileNotFoundException($"Captured layout JSON was not found: {normalizedLayoutPath}", normalizedLayoutPath);
        }

        var document = JsonSerializer.Deserialize<DemoCapturedLayoutDocument>(
            File.ReadAllText(normalizedLayoutPath),
            JsonOptions);

        if (document?.BaseFrame == null)
        {
            return new DemoApplyCapturedLayoutResult(
                false,
                "Captured layout JSON does not contain a valid baseFrame.",
                normalizedLayoutPath,
                assemblyPath,
                null,
                null,
                null,
                Array.Empty<DemoApplyCapturedLayoutComponentResult>());
        }

        SwOpenResult? openedDocument = null;
        var normalizedAssemblyPath = string.IsNullOrWhiteSpace(assemblyPath)
            ? null
            : Path.GetFullPath(assemblyPath);
        if (normalizedAssemblyPath != null)
        {
            openedDocument = docs.OpenDocument(normalizedAssemblyPath);
        }

        var results = new List<DemoApplyCapturedLayoutComponentResult>();
        foreach (var component in document.Components)
        {
            if (component.Layout2d == null)
            {
                results.Add(new DemoApplyCapturedLayoutComponentResult(
                    component.ComponentName,
                    component.BottomFaceName,
                    component.Layout2d,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    "Component has no captured layout2d."));
                continue;
            }

            var target = CommonBaseLayoutMath.PointFromLayout(component.Layout2d, document.BaseFrame);
            ComponentTransformResult? rotationResult = null;
            double? currentThetaDegrees = null;
            double? targetThetaDegrees = component.Layout2d.ThetaDegrees;
            double? deltaThetaDegrees = null;

            if (component.Layout2d.ThetaDegrees.HasValue && !string.IsNullOrWhiteSpace(component.Layout2d.ThetaAxis))
            {
                var pose = assembly.ListComponentPoses(topLevelOnly: true)
                    .FirstOrDefault(item => string.Equals(item.Name, component.ComponentName, StringComparison.OrdinalIgnoreCase));
                var currentAxis = GetPoseAxis(pose, component.Layout2d.ThetaAxis);
                currentThetaDegrees = CommonBaseLayoutMath.CalculateInPlaneRotationForAxis(currentAxis, document.BaseFrame);
                if (currentThetaDegrees.HasValue)
                {
                    deltaThetaDegrees = CommonBaseLayoutMath.DeltaAngleDegrees(
                        currentThetaDegrees.Value,
                        component.Layout2d.ThetaDegrees.Value);
                    if (Math.Abs(deltaThetaDegrees.Value) > 1e-6)
                    {
                        rotationResult = assembly.RotateComponent(
                            component.ComponentName,
                            document.BaseFrame.Normal[0],
                            document.BaseFrame.Normal[1],
                            document.BaseFrame.Normal[2],
                            -deltaThetaDegrees.Value);

                        if (!rotationResult.Success)
                        {
                            results.Add(new DemoApplyCapturedLayoutComponentResult(
                                component.ComponentName,
                                component.BottomFaceName,
                                component.Layout2d,
                                target,
                                null,
                                null,
                                rotationResult,
                                currentThetaDegrees,
                                targetThetaDegrees,
                                deltaThetaDegrees,
                                null,
                                rotationResult.Message));
                            continue;
                        }
                    }
                }
            }

            selection.ClearSelection();
            var faceSelection = selection.SelectFaceByName(
                component.BottomFaceName,
                component.ComponentName,
                append: false,
                mark: 0);

            if (!faceSelection.Success)
            {
                results.Add(new DemoApplyCapturedLayoutComponentResult(
                    component.ComponentName,
                    component.BottomFaceName,
                    component.Layout2d,
                    target,
                    faceSelection,
                    null,
                    rotationResult,
                    currentThetaDegrees,
                    targetThetaDegrees,
                    deltaThetaDegrees,
                    null,
                    faceSelection.Message));
                continue;
            }

            var probe = selection.GetSelectedFaceMappingProbe(component.BottomFaceName, component.ComponentName);
            var center = new SelectedFaceCenterResult(
                probe.Success && probe.WorldCenter is { Length: >= 3 },
                probe.Message,
                probe.WorldCenter,
                probe.Area);
            if (!center.Success || center.Center is not { Length: >= 3 })
            {
                results.Add(new DemoApplyCapturedLayoutComponentResult(
                    component.ComponentName,
                    component.BottomFaceName,
                    component.Layout2d,
                    target,
                    faceSelection,
                    center,
                    rotationResult,
                    currentThetaDegrees,
                    targetThetaDegrees,
                    deltaThetaDegrees,
                    null,
                    center.Message));
                continue;
            }

            var move = assembly.MoveComponent(
                component.ComponentName,
                target[0] - center.Center[0],
                target[1] - center.Center[1],
                target[2] - center.Center[2]);

            results.Add(new DemoApplyCapturedLayoutComponentResult(
                component.ComponentName,
                component.BottomFaceName,
                component.Layout2d,
                target,
                faceSelection,
                center,
                rotationResult,
                currentThetaDegrees,
                targetThetaDegrees,
                deltaThetaDegrees,
                move,
                move.Message));
        }

        selection.ClearSelection();
        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        var success = results.All(component =>
            component.MoveResult?.Success == true
            && (component.RotationResult == null || component.RotationResult.Success));
        return new DemoApplyCapturedLayoutResult(
            success,
            success
                ? "ApplyCapturedCommonBaseLayout completed."
                : "ApplyCapturedCommonBaseLayout completed with component move errors.",
            normalizedLayoutPath,
            normalizedAssemblyPath,
            openedDocument,
            rebuild,
            screenshot,
            results.AsReadOnly());
    }

    private DemoInitializationResult AppendComponentsCore(
        DemoComponentLayout[] components,
        string outputAssemblyPath,
        string? templatePath,
        string basePlaneName,
        string basePlaneSelectionType,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        if (components == null || components.Length == 0)
        {
            throw new ArgumentException("components must contain at least one component.", nameof(components));
        }

        if (string.IsNullOrWhiteSpace(outputAssemblyPath))
        {
            throw new ArgumentException("outputAssemblyPath must not be empty.", nameof(outputAssemblyPath));
        }

        var normalizedAssemblyPath = Path.GetFullPath(outputAssemblyPath);
        var outputDirectory = Path.GetDirectoryName(normalizedAssemblyPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        SwDocumentInfo? createdDocument = null;
        SwOpenResult? openedDocument = null;
        if (File.Exists(normalizedAssemblyPath))
        {
            openedDocument = docs.OpenDocument(normalizedAssemblyPath);
        }
        else
        {
            createdDocument = docs.NewDocument(SwDocType.Assembly, templatePath);
        }

        var prepared = components.Select(component => PrepareComponent(component, baseZ: 0, alignBottom: false)).ToList();
        var arranged = prepared
            .Select(component => new DemoComponentArrangementResult(
                RequestedComponentName: component.Source.ComponentName ?? "",
                ComponentName: component.ComponentName,
                FilePath: component.Source.FilePath,
                BottomFaceName: component.Source.BottomFaceName,
                Inserted: component.Inserted,
                FaceMappingFound: false,
                FaceSelection: null,
                BottomMateResult: null,
                BottomFaceCenter: null,
                MoveResult: null))
            .ToList();

        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        var saveResult = docs.SaveDocumentAs(normalizedAssemblyPath, sourcePath: null, saveAsCopy: false);
        var success = arranged.All(component => component.Inserted);
        var message = success
            ? "AppendComponentsToCommonBaseAssembly completed."
            : "AppendComponentsToCommonBaseAssembly completed with errors. Check component insert results.";
        if (openedDocument != null)
        {
            message += " Opened existing assembly before appending this batch.";
        }

        return new DemoInitializationResult(
            Success: success,
            Message: message,
            AssemblyPath: normalizedAssemblyPath,
            BasePlaneName: basePlaneName,
            BasePlaneSelectionType: basePlaneSelectionType,
            CreatedDocument: createdDocument,
            SaveResult: saveResult,
            Rebuild: rebuild,
            Screenshot: screenshot,
            Components: arranged.AsReadOnly(),
            MissingFaceMappings: Array.Empty<string>());
    }

    private DemoInitializationResult InitializeCore(
        DemoComponentLayout[] components,
        string outputAssemblyPath,
        string? templatePath,
        string basePlaneName,
        string basePlaneSelectionType,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        if (components == null || components.Length == 0)
        {
            throw new ArgumentException("components must contain at least one component.", nameof(components));
        }

        if (string.IsNullOrWhiteSpace(outputAssemblyPath))
        {
            throw new ArgumentException("outputAssemblyPath must not be empty.", nameof(outputAssemblyPath));
        }

        var normalizedAssemblyPath = Path.GetFullPath(outputAssemblyPath);
        var outputDirectory = Path.GetDirectoryName(normalizedAssemblyPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        if (File.Exists(normalizedAssemblyPath))
        {
            _ = docs.OpenDocument(normalizedAssemblyPath);
            var reusedComponents = components
                .Select(component => new DemoComponentArrangementResult(
                    RequestedComponentName: component.ComponentName ?? "",
                    ComponentName: component.ComponentName ?? "",
                    FilePath: component.FilePath,
                    BottomFaceName: component.BottomFaceName,
                    Inserted: false,
                    FaceMappingFound: false,
                    FaceSelection: null,
                    BottomMateResult: null,
                    BottomFaceCenter: null,
                    MoveResult: null))
                .ToList();

            var reusedRebuild = docs.ForceRebuildActiveDocument(topOnly: false);
            SwImageExportResult? reusedScreenshot = null;
            if (!string.IsNullOrWhiteSpace(screenshotPath))
            {
                reusedScreenshot = docs.ExportCurrentViewPng(
                    screenshotPath,
                    screenshotWidth,
                    screenshotHeight,
                    includeScreenshotBase64Data);
            }

            return new DemoInitializationResult(
                Success: true,
                Message: "InitializeCommonBaseAssembly reused existing assembly.",
                AssemblyPath: normalizedAssemblyPath,
                BasePlaneName: basePlaneName,
                BasePlaneSelectionType: basePlaneSelectionType,
                CreatedDocument: null,
                SaveResult: null,
                Rebuild: reusedRebuild,
                Screenshot: reusedScreenshot,
                Components: reusedComponents.AsReadOnly(),
                MissingFaceMappings: Array.Empty<string>());
        }

        var createdDocument = docs.NewDocument(SwDocType.Assembly, templatePath);
        var prepared = components.Select(component => PrepareComponent(component, baseZ: 0, alignBottom: false)).ToList();
        var arranged = prepared
            .Select(component => new DemoComponentArrangementResult(
                RequestedComponentName: component.Source.ComponentName ?? "",
                ComponentName: component.ComponentName,
                FilePath: component.Source.FilePath,
                BottomFaceName: component.Source.BottomFaceName,
                Inserted: component.Inserted,
                FaceMappingFound: false,
                FaceSelection: null,
                BottomMateResult: null,
                BottomFaceCenter: null,
                MoveResult: null))
            .ToList();

        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        var saveResult = docs.SaveDocumentAs(normalizedAssemblyPath, sourcePath: null, saveAsCopy: false);
        var success = arranged.All(component => component.Inserted);

        return new DemoInitializationResult(
            Success: success,
            Message: success
                ? "InitializeCommonBaseAssembly completed."
                : "InitializeCommonBaseAssembly completed with errors. Check component insert results.",
            AssemblyPath: normalizedAssemblyPath,
            BasePlaneName: basePlaneName,
            BasePlaneSelectionType: basePlaneSelectionType,
            CreatedDocument: createdDocument,
            SaveResult: saveResult,
            Rebuild: rebuild,
            Screenshot: screenshot,
            Components: arranged.AsReadOnly(),
            MissingFaceMappings: Array.Empty<string>());
    }

    private DemoCommonBaseResult FinalizeCommonBaseCore(
        DemoComponentLayout[] components,
        string assemblyPath,
        double normalDotThreshold,
        bool enablePreMateOrientationCorrection,
        bool enablePostMateOrientationCorrection,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        // Common Base 主流程：
        // 1. 打开目标装配体并确认每个组件都有底面映射；
        // 2. 可选：mate 前根据底面法向做一次姿态预修正；
        // 3. 以第一个组件为 anchor，对其它组件执行“anchor 底面 + target 底面”的 Coincident mate；
        // 4. 重建、保存，并再次 probe 每个底面的 worldNormal，检查朝向是否与 anchor 一致。
        // 这里的“操作底面”不是直接传 IFace2，而是每次通过 SelectFaceByName 从映射中重新选回面。
        if (components == null || components.Length == 0)
        {
            throw new ArgumentException("components must contain at least one component.", nameof(components));
        }

        if (string.IsNullOrWhiteSpace(assemblyPath))
        {
            throw new ArgumentException("assemblyPath must not be empty.", nameof(assemblyPath));
        }

        var normalizedAssemblyPath = Path.GetFullPath(assemblyPath);
        var openedDocument = docs.OpenDocument(normalizedAssemblyPath);
        var prepared = components.Select(PrepareExistingComponent).ToList();
        var missingMappings = MissingFaceMappings(prepared);
        if (missingMappings.Count > 0)
        {
            return new DemoCommonBaseResult(
                Success: false,
                Message: "Please record bottom face mappings before finalizing the common-base assembly.",
                AssemblyPath: normalizedAssemblyPath,
                OpenedDocument: openedDocument,
                SaveResult: null,
                Rebuild: null,
                Screenshot: null,
                Components: prepared.Select(ToBlockedResult).ToList().AsReadOnly(),
                MissingFaceMappings: missingMappings,
                OrientationCorrections: Array.Empty<DemoBottomOrientationCorrection>(),
                OrientationChecks: Array.Empty<DemoBottomOrientationCheck>());
        }

        var orientationCorrections = enablePreMateOrientationCorrection
            ? CorrectBottomFaceOrientations(
                prepared,
                normalDotThreshold,
                stage: "PreMateTransform2")
            : Array.Empty<DemoBottomOrientationCorrection>();

        var mateResult = MateBottomFacesToFirstComponent(prepared);
        var arranged = new List<DemoComponentArrangementResult>();
        foreach (var component in prepared)
        {
            mateResult.FaceSelections.TryGetValue(component.ComponentName, out var faceSelection);
            mateResult.BottomMates.TryGetValue(component.ComponentName, out var bottomMate);

            arranged.Add(new DemoComponentArrangementResult(
                RequestedComponentName: component.Source.ComponentName ?? "",
                ComponentName: component.ComponentName,
                FilePath: null,
                BottomFaceName: component.Source.BottomFaceName,
                Inserted: false,
                FaceMappingFound: true,
                FaceSelection: faceSelection,
                BottomMateResult: bottomMate,
                BottomFaceCenter: null,
                MoveResult: null));
        }

        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        if (enablePostMateOrientationCorrection)
        {
            var postMateCorrections = CorrectBottomFaceOrientations(
                prepared,
                normalDotThreshold,
                stage: "PostMate");
            orientationCorrections = orientationCorrections
                .Concat(postMateCorrections)
                .ToList()
                .AsReadOnly();
            rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        }
        var orientationChecks = ProbeBottomFaceOrientations(prepared, normalDotThreshold);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        var saveResult = docs.SaveDocumentAs(normalizedAssemblyPath, sourcePath: null, saveAsCopy: false);
        var success = arranged.All(component =>
            component.FaceSelection?.Success != false &&
            (component.BottomMateResult == null ||
                string.Equals(component.BottomMateResult.ErrorName, "swAddMateError_NoError", StringComparison.OrdinalIgnoreCase)))
            && orientationChecks.All(check => check.Success && check.MatchesBase);

        var hasOrientationMismatch = orientationChecks.Any(check => check.Success && !check.MatchesBase);
        var hasOrientationProbeError = orientationChecks.Any(check => !check.Success);

        return new DemoCommonBaseResult(
            Success: success,
            Message: success
                ? "FinalizeCommonBaseAssembly completed."
                : hasOrientationMismatch
                    ? "FinalizeCommonBaseAssembly completed with bottom face orientation mismatch."
                    : hasOrientationProbeError
                        ? "FinalizeCommonBaseAssembly completed with bottom face orientation probe errors. Check orientationChecks and re-record any non-planar or zero-normal bottom faces."
                        : "FinalizeCommonBaseAssembly completed with errors. Check component mate and orientation results.",
            AssemblyPath: normalizedAssemblyPath,
            OpenedDocument: openedDocument,
            SaveResult: saveResult,
            Rebuild: rebuild,
            Screenshot: screenshot,
            Components: arranged.AsReadOnly(),
            MissingFaceMappings: Array.Empty<string>(),
            OrientationCorrections: orientationCorrections,
            OrientationChecks: orientationChecks);
    }

    private DemoArrangementResult MoveExistingCore(
        DemoComponentLayout[] components,
        string assemblyPath,
        string basePlaneName,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        if (components == null || components.Length == 0)
        {
            throw new ArgumentException("components must contain at least one component.", nameof(components));
        }

        if (string.IsNullOrWhiteSpace(assemblyPath))
        {
            throw new ArgumentException("assemblyPath must not be empty.", nameof(assemblyPath));
        }

        var openedDocument = docs.OpenDocument(assemblyPath);
        var prepared = components.Select(PrepareExistingComponent).ToList();
        var missingMappings = MissingFaceMappings(prepared);
        if (missingMappings.Count > 0)
        {
            return new DemoArrangementResult(
                Success: false,
                Message: "Please record bottom face mappings before moving components on the common base.",
                AlignBottom: false,
                BaseZ: 0,
                CreatedDocument: null,
                OpenedDocument: openedDocument,
                Rebuild: null,
                Screenshot: null,
                Components: prepared.Select(ToBlockedResult).ToList().AsReadOnly(),
                MissingFaceMappings: missingMappings);
        }

        var arranged = new List<DemoComponentArrangementResult>();
        foreach (var component in prepared)
        {
            var movePlan = CalculateMoveToTargetBottomCenterOnPlane(component, basePlaneName);
            var move = movePlan.Center.Success && movePlan.Center.Center is { Length: >= 3 }
                ? assembly.MoveComponent(component.ComponentName, movePlan.DeltaX, movePlan.DeltaY, movePlan.DeltaZ)
                : new ComponentTransformResult(false, movePlan.Center.Message, component.ComponentName, null);

            arranged.Add(new DemoComponentArrangementResult(
                RequestedComponentName: component.Source.ComponentName ?? "",
                ComponentName: component.ComponentName,
                FilePath: null,
                BottomFaceName: component.Source.BottomFaceName,
                Inserted: false,
                FaceMappingFound: true,
                FaceSelection: movePlan.FaceSelection,
                BottomMateResult: null,
                BottomFaceCenter: movePlan.Center,
                MoveResult: move));
        }

        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        return new DemoArrangementResult(
            Success: arranged.All(component =>
                component.MoveResult?.Success != false &&
                component.BottomFaceCenter?.Success != false),
            Message: "MoveComponentsOnCommonBase completed.",
            AlignBottom: false,
            BaseZ: 0,
            CreatedDocument: null,
            OpenedDocument: openedDocument,
            Rebuild: rebuild,
            Screenshot: screenshot,
            Components: arranged.AsReadOnly(),
            MissingFaceMappings: Array.Empty<string>());
    }

    private DemoArrangementResult ArrangeCore(
        DemoComponentLayout[] components,
        string? assemblyPath,
        string? templatePath,
        bool alignBottom,
        double baseZ,
        string? screenshotPath,
        int screenshotWidth,
        int screenshotHeight,
        bool includeScreenshotBase64Data)
    {
        if (components == null || components.Length == 0)
        {
            throw new ArgumentException("components must contain at least one component.", nameof(components));
        }

        SwDocumentInfo? createdDocument = null;
        SwOpenResult? openedDocument = null;
        if (!string.IsNullOrWhiteSpace(assemblyPath))
        {
            openedDocument = docs.OpenDocument(assemblyPath);
        }
        else
        {
            createdDocument = docs.NewDocument(SwDocType.Assembly, templatePath);
        }

        var prepared = new List<PreparedComponent>();
        foreach (var component in components)
        {
            prepared.Add(PrepareComponent(component, baseZ, alignBottom));
        }

        if (alignBottom)
        {
            var missingMappings = prepared
                .Where(component => !HasFaceMapping(component.ComponentName, component.Source.BottomFaceName))
                .Select(component => $"Please record bottom face mapping first. componentName={component.ComponentName}, faceName={component.Source.BottomFaceName}")
                .ToList()
                .AsReadOnly();

            if (missingMappings.Count > 0)
            {
                return new DemoArrangementResult(
                    Success: false,
                    Message: "Please record bottom face mappings before arranging on a common base. SelectFaceByName is not called when mappings are missing.",
                    AlignBottom: alignBottom,
                    BaseZ: baseZ,
                    CreatedDocument: createdDocument,
                    OpenedDocument: openedDocument,
                    Rebuild: null,
                    Screenshot: null,
                    Components: prepared.Select(ToBlockedResult).ToList().AsReadOnly(),
                    MissingFaceMappings: missingMappings);
            }
        }

        var faceSelections = new Dictionary<string, FaceMappingResult>(StringComparer.OrdinalIgnoreCase);
        var bottomMates = new Dictionary<string, MateOperationResult>(StringComparer.OrdinalIgnoreCase);
        if (alignBottom)
        {
            var mateResult = MateBottomFacesToFirstComponent(prepared);
            foreach (var item in mateResult.FaceSelections)
            {
                faceSelections[item.Key] = item.Value;
            }

            foreach (var item in mateResult.BottomMates)
            {
                bottomMates[item.Key] = item.Value;
            }
        }

        var arranged = new List<DemoComponentArrangementResult>();
        for (var index = 0; index < prepared.Count; index++)
        {
            var component = prepared[index];
            faceSelections.TryGetValue(component.ComponentName, out var faceSelection);
            bottomMates.TryGetValue(component.ComponentName, out var bottomMate);
            var movePlan = CalculateMoveToTargetBottomCenter(component, baseZ, alignBottom);
            faceSelections[component.ComponentName] = movePlan.FaceSelection;
            var move = movePlan.Center.Success && movePlan.Center.Center is { Length: >= 3 }
                ? assembly.MoveComponent(component.ComponentName, movePlan.DeltaX, movePlan.DeltaY, movePlan.DeltaZ)
                : new ComponentTransformResult(
                    false,
                    movePlan.Center.Message,
                    component.ComponentName,
                    null);

            arranged.Add(new DemoComponentArrangementResult(
                RequestedComponentName: component.Source.ComponentName ?? "",
                ComponentName: component.ComponentName,
                FilePath: component.Source.FilePath,
                BottomFaceName: component.Source.BottomFaceName,
                Inserted: component.Inserted,
                FaceMappingFound: alignBottom,
                FaceSelection: movePlan.FaceSelection,
                BottomMateResult: bottomMate,
                BottomFaceCenter: movePlan.Center,
                MoveResult: move));
        }

        var rebuild = docs.ForceRebuildActiveDocument(topOnly: false);
        SwImageExportResult? screenshot = null;
        if (!string.IsNullOrWhiteSpace(screenshotPath))
        {
            screenshot = docs.ExportCurrentViewPng(
                screenshotPath,
                screenshotWidth,
                screenshotHeight,
                includeScreenshotBase64Data);
        }

        return new DemoArrangementResult(
            Success: arranged.All(component =>
                component.MoveResult?.Success != false &&
                component.BottomFaceCenter?.Success != false),
            Message: arranged.Any(component =>
                component.BottomMateResult != null &&
                !string.Equals(component.BottomMateResult.ErrorName, "swAddMateError_NoError", StringComparison.OrdinalIgnoreCase))
                ? "ArrangeComponentsOnCommonBase completed with mate warnings. Bottom centers were positioned with MoveComponent."
                : "ArrangeComponentsOnCommonBase completed.",
            AlignBottom: alignBottom,
            BaseZ: baseZ,
            CreatedDocument: createdDocument,
            OpenedDocument: openedDocument,
            Rebuild: rebuild,
            Screenshot: screenshot,
            Components: arranged.AsReadOnly(),
            MissingFaceMappings: Array.Empty<string>());
    }

    private PreparedComponent PrepareComponent(DemoComponentLayout source, double baseZ, bool alignBottom)
    {
        source = NormalizeComponentLayout(source);
        var requestedName = source.ComponentName?.Trim();
        var filePath = source.FilePath?.Trim();
        var inserted = false;
        var componentName = requestedName;
        double currentX;
        double currentY;
        double currentZ;

        if (!string.IsNullOrWhiteSpace(filePath))
        {
            var insertZ = alignBottom ? baseZ + source.Z : source.Z;
            var info = assembly.InsertComponent(filePath, source.X, source.Y, insertZ);
            if (!string.IsNullOrWhiteSpace(requestedName)
                && !string.Equals(info.Name, requestedName, StringComparison.OrdinalIgnoreCase))
            {
                info = assembly.RenameComponent(info.Name, requestedName);
            }
            inserted = true;
            componentName = info.Name;
            currentX = source.X;
            currentY = source.Y;
            currentZ = insertZ;
        }
        else
        {
            if (string.IsNullOrWhiteSpace(componentName))
            {
                throw new ArgumentException("Each component must provide componentName when filePath is not provided.");
            }

            currentX = source.CurrentX ?? 0;
            currentY = source.CurrentY ?? 0;
            currentZ = source.CurrentZ ?? 0;
        }

        return new PreparedComponent(
            Source: source,
            ComponentName: componentName!,
            Inserted: inserted,
            CurrentX: currentX,
            CurrentY: currentY,
            CurrentZ: currentZ);
    }

    private static DemoComponentArrangementResult ToBlockedResult(PreparedComponent component) =>
        new(
            RequestedComponentName: component.Source.ComponentName ?? "",
            ComponentName: component.ComponentName,
            FilePath: component.Source.FilePath,
            BottomFaceName: component.Source.BottomFaceName,
            Inserted: component.Inserted,
            FaceMappingFound: false,
            FaceSelection: null,
            BottomMateResult: null,
            BottomFaceCenter: null,
            MoveResult: null);

    private static DemoComponentArrangementResult ToFailedSelectionResult(
        PreparedComponent component,
        FaceMappingResult faceSelection) =>
        new(
            RequestedComponentName: component.Source.ComponentName ?? "",
            ComponentName: component.ComponentName,
            FilePath: component.Source.FilePath,
            BottomFaceName: component.Source.BottomFaceName,
            Inserted: component.Inserted,
            FaceMappingFound: true,
            FaceSelection: faceSelection,
            BottomMateResult: null,
            BottomFaceCenter: null,
            MoveResult: null);

    private BottomCenterMovePlan CalculateMoveToTargetBottomCenter(
        PreparedComponent component,
        double baseZ,
        bool alignBottom)
    {
        selection.ClearSelection();
        var faceSelection = selection.SelectFaceByName(
            component.Source.BottomFaceName,
            component.ComponentName,
            append: false,
            mark: 0);
        if (!faceSelection.Success)
        {
            return new BottomCenterMovePlan(
                faceSelection,
                new SelectedFaceCenterResult(false, faceSelection.Message),
                0,
                0,
                0);
        }

        var center = selection.GetSelectedFaceCenter();
        if (!center.Success || center.Center is not { Length: >= 3 })
        {
            return new BottomCenterMovePlan(faceSelection, center, 0, 0, 0);
        }

        var targetZ = alignBottom ? baseZ + component.Source.Z : component.Source.Z;
        return new BottomCenterMovePlan(
            faceSelection,
            center,
            component.Source.X - center.Center[0],
            component.Source.Y - center.Center[1],
            targetZ - center.Center[2]);
    }

    private PreparedComponent PrepareExistingComponent(DemoComponentLayout source)
    {
        source = NormalizeComponentLayout(source);
        var componentName = source.ComponentName?.Trim();
        if (string.IsNullOrWhiteSpace(componentName))
        {
            throw new ArgumentException("Each existing component must provide componentName.");
        }

        return new PreparedComponent(
            Source: source with { FilePath = null },
            ComponentName: componentName,
            Inserted: false,
            CurrentX: source.CurrentX ?? 0,
            CurrentY: source.CurrentY ?? 0,
            CurrentZ: source.CurrentZ ?? 0);
    }

    private static DemoComponentLayout NormalizeComponentLayout(DemoComponentLayout source)
    {
        var faceName = source.BottomFaceName?.Trim();
        if (string.IsNullOrWhiteSpace(faceName) || faceName == "??")
        {
            faceName = "\u5e95\u9762";
        }

        return source with { BottomFaceName = faceName };
    }

    private IReadOnlyList<string> MissingFaceMappings(IReadOnlyList<PreparedComponent> prepared) =>
        prepared
            .Where(component => !HasFaceMapping(component.ComponentName, component.Source.BottomFaceName))
            .Select(component => $"Please record bottom face mapping first. componentName={component.ComponentName}, faceName={component.Source.BottomFaceName}")
            .ToList()
            .AsReadOnly();

    private ReferencePlaneMatePlan MateBottomFaceToReferencePlane(
        PreparedComponent component,
        string basePlaneName,
        string basePlaneSelectionType)
    {
        selection.ClearSelection();
        var faceSelection = selection.SelectFaceByName(
            component.Source.BottomFaceName,
            component.ComponentName,
            append: false,
            mark: 0);
        if (!faceSelection.Success)
        {
            return new ReferencePlaneMatePlan(
                faceSelection,
                new SelectionResult(false, faceSelection.Message),
                new MateOperationResult("Coincident", -1, "SelectBottomFaceFailed", faceSelection.Message));
        }

        var planeSelection = selection.SelectByName(
            basePlaneName,
            basePlaneSelectionType,
            append: true,
            mark: 0);
        if (!planeSelection.Success)
        {
            return new ReferencePlaneMatePlan(
                faceSelection,
                planeSelection,
                new MateOperationResult("Coincident", -1, "SelectBasePlaneFailed", planeSelection.Message));
        }

        return new ReferencePlaneMatePlan(
            faceSelection,
            planeSelection,
            TryAddCoincidentMate());
    }

    private BottomCenterMovePlan CalculateMoveToTargetBottomCenterOnPlane(
        PreparedComponent component,
        string basePlaneName)
    {
        selection.ClearSelection();
        var faceSelection = selection.SelectFaceByName(
            component.Source.BottomFaceName,
            component.ComponentName,
            append: false,
            mark: 0);
        if (!faceSelection.Success)
        {
            return new BottomCenterMovePlan(
                faceSelection,
                new SelectedFaceCenterResult(false, faceSelection.Message),
                0,
                0,
                0);
        }

        var center = selection.GetSelectedFaceCenter();
        if (!center.Success || center.Center is not { Length: >= 3 })
        {
            return new BottomCenterMovePlan(faceSelection, center, 0, 0, 0);
        }

        var (deltaX, deltaY, deltaZ) = CalculatePlaneDelta(basePlaneName, component.Source, center.Center);
        return new BottomCenterMovePlan(faceSelection, center, deltaX, deltaY, deltaZ);
    }

    private static (double DeltaX, double DeltaY, double DeltaZ) CalculatePlaneDelta(
        string basePlaneName,
        DemoComponentLayout source,
        IReadOnlyList<double> center)
    {
        var normalized = (basePlaneName ?? "").Trim().ToLowerInvariant();
        if (normalized.Contains("top"))
        {
            return (source.X - center[0], 0, source.Z - center[2]);
        }

        if (normalized.Contains("right"))
        {
            return (0, source.Y - center[1], source.Z - center[2]);
        }

        return (source.X - center[0], source.Y - center[1], 0);
    }

    private BottomMateApplicationResult MateBottomFacesToFirstComponent(IReadOnlyList<PreparedComponent> prepared)
    {
        var faceSelections = new Dictionary<string, FaceMappingResult>(StringComparer.OrdinalIgnoreCase);
        var bottomMates = new Dictionary<string, MateOperationResult>(StringComparer.OrdinalIgnoreCase);
        if (prepared.Count < 2)
        {
            return new BottomMateApplicationResult(faceSelections, bottomMates);
        }

        var anchor = prepared[0];
        for (var index = 1; index < prepared.Count; index++)
        {
            var target = prepared[index];
            bottomMates[target.ComponentName] = TryMateBottomFace(anchor, target, faceSelections);
        }

        selection.ClearSelection();
        return new BottomMateApplicationResult(faceSelections, bottomMates);
    }

    private MateOperationResult TryMateBottomFace(
        PreparedComponent anchor,
        PreparedComponent target,
        IDictionary<string, FaceMappingResult> faceSelections)
    {
        // 单个 target 的共底面配合：
        // 先选 anchor 记录的底面，再 append 选 target 记录的底面，最后创建 Coincident mate。
        // 如果任意一侧 SelectFaceByName 选错或选不到，mate 就会失败或把错误的面配合到一起。
        selection.ClearSelection();

        var anchorSelection = selection.SelectFaceByName(
            anchor.Source.BottomFaceName,
            anchor.ComponentName,
            append: false,
            mark: 0);
        faceSelections[anchor.ComponentName] = anchorSelection;
        if (!anchorSelection.Success)
        {
            return new MateOperationResult(
                "Coincident",
                -1,
                "SelectAnchorFaceFailed",
                anchorSelection.Message);
        }

        var targetSelection = selection.SelectFaceByName(
            target.Source.BottomFaceName,
            target.ComponentName,
            append: true,
            mark: 0);
        faceSelections[target.ComponentName] = targetSelection;
        if (!targetSelection.Success)
        {
            return new MateOperationResult(
                "Coincident",
                -1,
                "SelectBottomFaceFailed",
                targetSelection.Message);
        }

        return TryAddCoincidentMate();
    }

    private IReadOnlyList<DemoBottomOrientationCorrection> CorrectBottomFaceOrientations(
        IReadOnlyList<PreparedComponent> prepared,
        double normalDotThreshold,
        string stage)
    {
        // 底面朝向修正入口。
        // 当前策略以第一个组件的底面 normal 为基准，逐个检查其它组件 normal 是否同向；
        // 如不同向，则尝试在 mate 前通过组件变换旋转姿态。该功能对面映射质量非常敏感，
        // 如果 SelectFaceByName probe 到的不是目标底面，修正方向也会随之错误。
        var corrections = new List<DemoBottomOrientationCorrection>();
        if (prepared.Count < 2)
        {
            return corrections.AsReadOnly();
        }

        var baseProbe = ProbeBottomFace(prepared[0]);
        var baseNormal = baseProbe.FaceProbe?.WorldNormal;
        if (!baseProbe.Success || !CommonBaseLayoutMath.IsValidNormal(baseNormal))
        {
            corrections.Add(new DemoBottomOrientationCorrection(
                stage,
                prepared[0].ComponentName,
                prepared[0].Source.BottomFaceName,
                Success: false,
                Applied: false,
                RotationAxis: null,
                AngleDegrees: 0,
                BeforeProbe: baseProbe.FaceProbe,
                AfterRotationProbe: null,
                AfterRestoreProbe: null,
                RotationResult: null,
                RestoreCenterMoveResult: null,
                Message: baseProbe.Message));
            return corrections.AsReadOnly();
        }

        for (var index = 1; index < prepared.Count; index++)
        {
            corrections.Add(CorrectBottomFaceOrientation(
                prepared[index],
                baseNormal!,
                normalDotThreshold,
                stage));
        }

        selection.ClearSelection();
        return corrections.AsReadOnly();
    }

    private DemoBottomOrientationCorrection CorrectBottomFaceOrientation(
        PreparedComponent component,
        IReadOnlyList<double> baseNormal,
        double normalDotThreshold,
        string stage)
    {
        var before = ProbeBottomFace(component);
        var beforeProbe = before.FaceProbe;
        var beforeNormal = beforeProbe?.WorldNormal;
        var beforeCenter = beforeProbe?.WorldCenter;

        if (!before.Success || !CommonBaseLayoutMath.IsValidNormal(beforeNormal) || beforeCenter is not { Length: >= 3 })
        {
            return new DemoBottomOrientationCorrection(
                stage,
                component.ComponentName,
                component.Source.BottomFaceName,
                Success: false,
                Applied: false,
                RotationAxis: null,
                AngleDegrees: 0,
                BeforeProbe: beforeProbe,
                AfterRotationProbe: null,
                AfterRestoreProbe: null,
                RotationResult: null,
                RestoreCenterMoveResult: null,
                Message: before.Message);
        }

        if (CommonBaseLayoutMath.NormalsMatchDirection(beforeNormal!, baseNormal, normalDotThreshold))
        {
            return new DemoBottomOrientationCorrection(
                stage,
                component.ComponentName,
                component.Source.BottomFaceName,
                Success: true,
                Applied: false,
                RotationAxis: null,
                AngleDegrees: 0,
                BeforeProbe: beforeProbe,
                AfterRotationProbe: null,
                AfterRestoreProbe: null,
                RotationResult: null,
                RestoreCenterMoveResult: null,
                Message: "Bottom-face normal already matches base component.");
        }

        var validBeforeProbe = beforeProbe!;
        var rotation = CommonBaseLayoutMath.CalculateNormalAlignmentRotation(beforeNormal!, baseNormal);
        if (rotation == null)
        {
            return new DemoBottomOrientationCorrection(
                stage,
                component.ComponentName,
                component.Source.BottomFaceName,
                Success: false,
                Applied: false,
                RotationAxis: null,
                AngleDegrees: 0,
                BeforeProbe: beforeProbe,
                AfterRotationProbe: null,
                AfterRestoreProbe: null,
                RotationResult: null,
                RestoreCenterMoveResult: null,
                Message: "Could not calculate a stable rotation axis for bottom-face orientation correction.");
        }

        var attempts = new[]
        {
            rotation.AngleDegrees,
            -rotation.AngleDegrees,
        };
        DemoBottomOrientationCorrection? lastAttempt = null;
        foreach (var angle in attempts)
        {
            var attempt = TryApplyBottomOrientationRotation(
                stage,
                component,
                validBeforeProbe,
                beforeCenter,
                baseNormal,
                rotation.Axis,
                angle,
                normalDotThreshold);
            if (attempt.Success)
            {
                return attempt;
            }

            lastAttempt = attempt;
            RollBackBottomOrientationRotation(component, beforeCenter, rotation.Axis, -angle);
        }

        return lastAttempt ?? new DemoBottomOrientationCorrection(
            stage,
            component.ComponentName,
            component.Source.BottomFaceName,
            Success: false,
            Applied: false,
            RotationAxis: rotation.Axis,
            AngleDegrees: rotation.AngleDegrees,
            BeforeProbe: beforeProbe,
            AfterRotationProbe: null,
            AfterRestoreProbe: null,
            RotationResult: null,
            RestoreCenterMoveResult: null,
            Message: "Bottom-face orientation correction failed before any rotation attempt.");
    }

    private DemoBottomOrientationCorrection TryApplyBottomOrientationRotation(
        string stage,
        PreparedComponent component,
        FaceMappingProbeResult beforeProbe,
        IReadOnlyList<double> beforeCenter,
        IReadOnlyList<double> baseNormal,
        IReadOnlyList<double> rotationAxis,
        double angleDegrees,
        double normalDotThreshold)
    {
        var rotationResult = assembly.RotateComponent(
            component.ComponentName,
            rotationAxis[0],
            rotationAxis[1],
            rotationAxis[2],
            angleDegrees);
        if (!rotationResult.Success)
        {
            return new DemoBottomOrientationCorrection(
                stage,
                component.ComponentName,
                component.Source.BottomFaceName,
                Success: false,
                Applied: true,
                RotationAxis: [rotationAxis[0], rotationAxis[1], rotationAxis[2]],
                AngleDegrees: angleDegrees,
                BeforeProbe: beforeProbe,
                AfterRotationProbe: null,
                AfterRestoreProbe: null,
                RotationResult: rotationResult,
                RestoreCenterMoveResult: null,
                Message: rotationResult.Message);
        }

        var afterRotation = ProbeBottomFace(component);
        var afterRotationCenter = afterRotation.FaceProbe?.WorldCenter;
        ComponentTransformResult? restoreCenterMove = null;
        if (afterRotation.Success && afterRotationCenter is { Length: >= 3 })
        {
            restoreCenterMove = assembly.MoveComponent(
                component.ComponentName,
                beforeCenter[0] - afterRotationCenter[0],
                beforeCenter[1] - afterRotationCenter[1],
                beforeCenter[2] - afterRotationCenter[2]);
        }

        var afterRestore = ProbeBottomFace(component);
        var afterNormal = afterRestore.FaceProbe?.WorldNormal;
        var matches = afterRestore.Success
            && CommonBaseLayoutMath.IsValidNormal(afterNormal)
            && CommonBaseLayoutMath.NormalsMatchDirection(afterNormal!, baseNormal, normalDotThreshold);

        return new DemoBottomOrientationCorrection(
            stage,
            component.ComponentName,
            component.Source.BottomFaceName,
            Success: matches,
            Applied: true,
            RotationAxis: [rotationAxis[0], rotationAxis[1], rotationAxis[2]],
            AngleDegrees: angleDegrees,
            BeforeProbe: beforeProbe,
            AfterRotationProbe: afterRotation.FaceProbe,
            AfterRestoreProbe: afterRestore.FaceProbe,
            RotationResult: rotationResult,
            RestoreCenterMoveResult: restoreCenterMove,
            Message: matches
                ? "Bottom-face orientation corrected to match base component."
                : "Bottom-face orientation correction attempt failed; component was rolled back before the next attempt or before returning.");
    }

    private void RollBackBottomOrientationRotation(
        PreparedComponent component,
        IReadOnlyList<double> beforeCenter,
        IReadOnlyList<double> rotationAxis,
        double rollbackAngleDegrees)
    {
        _ = assembly.RotateComponent(
            component.ComponentName,
            rotationAxis[0],
            rotationAxis[1],
            rotationAxis[2],
            rollbackAngleDegrees);

        var afterRollback = ProbeBottomFace(component);
        var rollbackCenter = afterRollback.FaceProbe?.WorldCenter;
        if (rollbackCenter is { Length: >= 3 })
        {
            _ = assembly.MoveComponent(
                component.ComponentName,
                beforeCenter[0] - rollbackCenter[0],
                beforeCenter[1] - rollbackCenter[1],
                beforeCenter[2] - rollbackCenter[2]);
        }
    }

    private BottomFaceProbe ProbeBottomFace(PreparedComponent component)
    {
        // 将“面映射”转成可操作的几何状态：
        // SelectFaceByName 负责选回面，GetSelectedFaceMappingProbe 负责读取当前 center/normal。
        // Common Base 用 normal 判断朝向，用 center 在旋转后恢复位置；Replay 用 center 计算 MoveComponent 偏移。
        selection.ClearSelection();
        var faceSelection = selection.SelectFaceByName(
            component.Source.BottomFaceName,
            component.ComponentName,
            append: false,
            mark: 0);
        if (!faceSelection.Success)
        {
            return new BottomFaceProbe(false, faceSelection.Message, faceSelection, null);
        }

        var probe = selection.GetSelectedFaceMappingProbe(
            component.Source.BottomFaceName,
            component.ComponentName);
        if (!probe.Success)
        {
            return new BottomFaceProbe(false, probe.Message, faceSelection, probe);
        }

        if (!CommonBaseLayoutMath.IsValidNormal(probe.WorldNormal))
        {
            return new BottomFaceProbe(
                false,
                $"{component.ComponentName} bottom face normal unavailable or near zero. Re-record a planar bottom face before finalizing common base.",
                faceSelection,
                probe);
        }

        if (probe.WorldCenter is not { Length: >= 3 })
        {
            return new BottomFaceProbe(false, $"{component.ComponentName} bottom face center unavailable.", faceSelection, probe);
        }

        return new BottomFaceProbe(true, probe.Message, faceSelection, probe);
    }

    private IReadOnlyList<DemoBottomOrientationCheck> ProbeBottomFaceOrientations(
        IReadOnlyList<PreparedComponent> prepared,
        double normalDotThreshold)
    {
        // mate 完成后的验收：重新选回每个组件底面，读取 worldNormal，并和 anchor 的 worldNormal 做 dot product。
        // 该检查只能证明“当前被选回的面”的朝向一致；如果面映射本身选错，检查结果也会失真。
        var checks = new List<DemoBottomOrientationCheck>();
        double[]? baseNormal = null;

        for (var index = 0; index < prepared.Count; index++)
        {
            var component = prepared[index];
            selection.ClearSelection();
            var faceSelection = selection.SelectFaceByName(
                component.Source.BottomFaceName,
                component.ComponentName,
                append: false,
                mark: 0);

            if (!faceSelection.Success)
            {
                checks.Add(new DemoBottomOrientationCheck(
                    component.ComponentName,
                    component.Source.BottomFaceName,
                    Success: false,
                    MatchesBase: false,
                    DotWithBase: null,
                    NormalDotThreshold: normalDotThreshold,
                    WorldNormal: null,
                    FaceSelection: faceSelection,
                    FaceProbe: null,
                    Message: faceSelection.Message));
                continue;
            }

            var probe = selection.GetSelectedFaceMappingProbe(
                component.Source.BottomFaceName,
                component.ComponentName);
            var normal = probe.WorldNormal;
            if (!probe.Success || !CommonBaseLayoutMath.IsValidNormal(normal))
            {
                var message = probe.Success
                    ? $"{component.ComponentName} bottom face normal unavailable or near zero. Re-record a planar bottom face before finalizing common base."
                    : probe.Message;
                checks.Add(new DemoBottomOrientationCheck(
                    component.ComponentName,
                    component.Source.BottomFaceName,
                    Success: false,
                    MatchesBase: false,
                    DotWithBase: null,
                    NormalDotThreshold: normalDotThreshold,
                    WorldNormal: normal,
                    FaceSelection: faceSelection,
                    FaceProbe: probe,
                    Message: message));
                continue;
            }

            var validNormal = normal!;
            if (baseNormal == null)
            {
                baseNormal = validNormal;
                checks.Add(new DemoBottomOrientationCheck(
                    component.ComponentName,
                    component.Source.BottomFaceName,
                    Success: true,
                    MatchesBase: true,
                    DotWithBase: 1,
                    NormalDotThreshold: normalDotThreshold,
                    WorldNormal: validNormal,
                    FaceSelection: faceSelection,
                    FaceProbe: probe,
                    Message: "Base bottom-face normal recorded for orientation comparison."));
                continue;
            }

            var dot = CommonBaseLayoutMath.Dot(
                CommonBaseLayoutMath.Normalize(validNormal),
                CommonBaseLayoutMath.Normalize(baseNormal));
            var matches = CommonBaseLayoutMath.NormalsMatchDirection(validNormal, baseNormal, normalDotThreshold);
            checks.Add(new DemoBottomOrientationCheck(
                component.ComponentName,
                component.Source.BottomFaceName,
                Success: true,
                MatchesBase: matches,
                DotWithBase: dot,
                NormalDotThreshold: normalDotThreshold,
                WorldNormal: validNormal,
                FaceSelection: faceSelection,
                FaceProbe: probe,
                Message: matches
                    ? "Bottom-face normal matches base component."
                    : "bottom face orientation mismatch"));
        }

        selection.ClearSelection();
        return checks.AsReadOnly();
    }

    private MateOperationResult TryAddCoincidentMate()
    {
        foreach (var align in new[] { MateAlign.Closest, MateAlign.AntiAligned, MateAlign.None })
        {
            try
            {
                var result = assembly.AddMateCoincident(align);
                if (string.Equals(result.ErrorName, "swAddMateError_NoError", StringComparison.OrdinalIgnoreCase))
                {
                    return result;
                }
            }
            catch (Exception ex) when (align != MateAlign.None)
            {
                // Try the next alignment option. Some SolidWorks face pairs reject Closest but accept AntiAligned/None.
                _ = ex;
            }
            catch (Exception ex)
            {
                return new MateOperationResult(
                    "Coincident",
                    -1,
                    "AddMateCoincidentFailed",
                    ex.Message);
            }
        }

        return new MateOperationResult(
            "Coincident",
            -1,
            "AddMateCoincidentFailed",
            "Failed to create Coincident mate with Closest, AntiAligned, or None alignment.");
    }

    private static bool HasFaceMapping(string componentName, string faceName)
    {
        var configured = Environment.GetEnvironmentVariable("DEMO_FACE_MAPPING_PATH");
        var path = string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(AppContext.BaseDirectory, "face_mappings.json")
            : Path.GetFullPath(configured);
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            var root = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
            return root?[componentName] is JsonObject componentNode && componentNode[faceName] != null;
        }
        catch
        {
            return false;
        }
    }

    private sealed record PreparedComponent(
        DemoComponentLayout Source,
        string ComponentName,
        bool Inserted,
        double CurrentX,
        double CurrentY,
        double CurrentZ);

    private sealed record BottomMateApplicationResult(
        IReadOnlyDictionary<string, FaceMappingResult> FaceSelections,
        IReadOnlyDictionary<string, MateOperationResult> BottomMates);

    private sealed record ReferencePlaneMatePlan(
        FaceMappingResult FaceSelection,
        SelectionResult PlaneSelection,
        MateOperationResult MateResult);

    private sealed record BottomCenterMovePlan(
        FaceMappingResult FaceSelection,
        SelectedFaceCenterResult Center,
        double DeltaX,
        double DeltaY,
        double DeltaZ);

    private sealed record BottomFaceProbe(
        bool Success,
        string Message,
        FaceMappingResult FaceSelection,
        FaceMappingProbeResult? FaceProbe);

}
