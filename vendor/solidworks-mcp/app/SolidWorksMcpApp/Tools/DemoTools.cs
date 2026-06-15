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
            inserted = true;
            componentName = string.IsNullOrWhiteSpace(requestedName) ? info.Name : requestedName;
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
            selection.ClearSelection();

            var anchorSelection = selection.SelectFaceByName(
                anchor.Source.BottomFaceName,
                anchor.ComponentName,
                append: false,
                mark: 0);
            faceSelections[anchor.ComponentName] = anchorSelection;
            if (!anchorSelection.Success)
            {
                throw new InvalidOperationException(anchorSelection.Message);
            }

            var targetSelection = selection.SelectFaceByName(
                target.Source.BottomFaceName,
                target.ComponentName,
                append: true,
                mark: 0);
            faceSelections[target.ComponentName] = targetSelection;
            if (!targetSelection.Success)
            {
                throw new InvalidOperationException(targetSelection.Message);
            }

            bottomMates[target.ComponentName] = TryAddCoincidentMate();
        }

        selection.ClearSelection();
        return new BottomMateApplicationResult(faceSelections, bottomMates);
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
        var path = Path.Combine(AppContext.BaseDirectory, "face_mappings.json");
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

    private sealed record BottomCenterMovePlan(
        FaceMappingResult FaceSelection,
        SelectedFaceCenterResult Center,
        double DeltaX,
        double DeltaY,
        double DeltaZ);
}
