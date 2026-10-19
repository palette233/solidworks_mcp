using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;
using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

internal sealed class SolidWorksMcpHubTestClient : IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private static readonly string[] RequiredTools =
    [
        "Ping",
        "SolidWorksConnect",
        "SolidWorksDisconnect",
        "GetSolidWorksCompatibility",
        "GetSolidWorksSupportMatrix",
        "NewDocument",
        "OpenDocument",
        "CloseDocument",
        "SaveDocument",
        "GetActiveDocumentRebuildState",
        "ForceRebuildActiveDocument",
        "SaveDocumentAs",
        "Undo",
        "ShowStandardView",
        "RotateView",
        "ExportCurrentViewPng",
        "ListDocuments",
        "GetActiveDocument",
        "SelectByName",
        "ListEntities",
        "ListReferencePlanes",
        "GetSolidWorksContext",
        "GetEditState",
        "TraverseActiveFeatureManagerTree",
        "ListModelHealthSensors",
        "GetFeatureDiagnostics",
        "SelectEntity",
        "MeasureEntities",
        "DeleteFeatureByName",
        "DeleteUnusedSketches",
        "ClearSelection",
        "InsertSketch",
        "FinishSketch",
        "SketchUseEdge3",
        "AddPoint",
        "AddLine",
        "AddCircle",
        "AddRectangle",
        "AddArc",
        "AddEllipse",
        "AddPolygon",
        "AddText",
        "Extrude",
        "ExtrudeCut",
        "Revolve",
        "Fillet",
        "Chamfer",
        "Shell",
        "TraverseAssemblyChildFeatureTrees",
        "SearchAssemblyChildFeatures",
        "OpenAssemblyChildComponentForEditing",
        "BuildActiveAssemblyEntityAnnotationTargetIndex",
        "CaptureActiveAssemblyEntityAnnotationTargetsFromIndex",
        "CaptureActiveAssemblyEntityAnnotationSet",
        "AnnotateAssemblyEntityCaptureSetWithQwen",
        "ImportAssemblyEntityDimensionAnnotations",
        "QueryAssemblyEntityDimensionAnnotations",
        "QueryAssemblyStructuralComponentTargets",
        "HighlightAssemblyEntityAnnotationTarget",
        "DiagnoseActiveDocumentHealth",
        "ReviewModelStructureHygiene",
        "ReplaceNestedComponentAndVerifyPersistence",
        "ReviewTargetedStaticInterference",
    ];

    private readonly StdioClientTransport _transport;
    private readonly McpClient _client;

    private SolidWorksMcpHubTestClient(StdioClientTransport transport, McpClient client)
    {
        _transport = transport;
        _client = client;
    }

    public static SolidWorksMcpHubTestClient Create(string clientName = "SolidWorksBridge.Tests")
    {
        string exePath = ResolveAppExecutablePath();
        var transport = new StdioClientTransport(
            new StdioClientTransportOptions
            {
                Name = "solidworks-mcp-test-proxy",
                Command = exePath,
                Arguments = ["--proxy", "--client", clientName],
                WorkingDirectory = Path.GetDirectoryName(exePath),
            },
            NullLoggerFactory.Instance);

        var client = McpClient.CreateAsync(transport, loggerFactory: NullLoggerFactory.Instance)
            .GetAwaiter()
            .GetResult();

        var session = new SolidWorksMcpHubTestClient(transport, client);
        session.ValidateRequiredTools();
        return session;
    }

    public void Dispose()
    {
        _client.DisposeAsync().AsTask().GetAwaiter().GetResult();
    }

    public string CallToolText(string toolName, IReadOnlyDictionary<string, object?>? arguments = null)
    {
        string resolvedToolName = ToMcpToolName(toolName);
        var result = _client.CallToolAsync(resolvedToolName, arguments).GetAwaiter().GetResult();
        return ExtractText(resolvedToolName, result);
    }

    public T CallTool<T>(string toolName, IReadOnlyDictionary<string, object?>? arguments = null)
    {
        string text = CallToolText(toolName, arguments);
        if (string.Equals(text, "null", StringComparison.OrdinalIgnoreCase))
        {
            return default!;
        }

        var value = JsonSerializer.Deserialize<T>(text, JsonOptions);
        if (value is null)
        {
            throw new InvalidOperationException($"Tool '{toolName}' returned an empty payload when '{typeof(T).Name}' was expected.");
        }

        return value;
    }

    public T? CallToolNullable<T>(string toolName, IReadOnlyDictionary<string, object?>? arguments = null)
    {
        string text = CallToolText(toolName, arguments);
        if (string.IsNullOrWhiteSpace(text) || string.Equals(text, "null", StringComparison.OrdinalIgnoreCase))
        {
            return default;
        }

        return JsonSerializer.Deserialize<T>(text, JsonOptions);
    }

    public string CallToolErrorText(string toolName, IReadOnlyDictionary<string, object?>? arguments = null)
    {
        string resolvedToolName = ToMcpToolName(toolName);
        var result = _client.CallToolAsync(resolvedToolName, arguments).GetAwaiter().GetResult();
        string text = GetResultText(result);
        if (result.IsError.GetValueOrDefault())
        {
            return text;
        }

        throw new InvalidOperationException(
            $"Tool '{resolvedToolName}' completed successfully when an MCP error result was expected. Payload: {text}");
    }

    public static IReadOnlyDictionary<string, object?> Args(params (string Key, object? Value)[] values)
    {
        var dictionary = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var (key, value) in values)
        {
            if (value is not null)
            {
                dictionary[key] = value;
            }
        }

        return dictionary;
    }

    private void ValidateRequiredTools()
    {
        var tools = _client.ListToolsAsync().GetAwaiter().GetResult();
        var toolNames = new HashSet<string>(tools.Select(tool => tool.Name), StringComparer.Ordinal);
        string[] missing = RequiredTools
            .Select(ToMcpToolName)
            .Where(name => !toolNames.Contains(name))
            .ToArray();
        if (missing.Length == 0)
        {
            return;
        }

        string available = toolNames.Count == 0
            ? "<none>"
            : string.Join(", ", toolNames.OrderBy(name => name, StringComparer.Ordinal));

        throw new InvalidOperationException(
            "The running SolidWorks MCP hub does not expose the tools required by the integration harness. " +
            $"Missing tools: {string.Join(", ", missing)}. " +
            $"Available tools: {available}. " +
            "If you already had the hub running before rebuilding, restart SolidWorksMcpApp so the latest tool surface is loaded.");
    }

    private static string ToMcpToolName(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException("Tool name must not be empty.", nameof(name));
        }

        if (name.Contains('_', StringComparison.Ordinal))
        {
            return name.ToLowerInvariant();
        }

        var builder = new System.Text.StringBuilder(name.Length + 8);
        for (int index = 0; index < name.Length; index++)
        {
            char current = name[index];
            if (char.IsUpper(current))
            {
                bool hasPrevious = index > 0;
                bool previousIsLowerOrDigit = hasPrevious && (char.IsLower(name[index - 1]) || char.IsDigit(name[index - 1]));
                bool nextIsLower = index + 1 < name.Length && char.IsLower(name[index + 1]);
                if (hasPrevious && (previousIsLowerOrDigit || nextIsLower))
                {
                    builder.Append('_');
                }

                builder.Append(char.ToLowerInvariant(current));
            }
            else
            {
                builder.Append(current);
            }
        }

        return builder.ToString();
    }

    private static string ExtractText(string toolName, CallToolResult result)
    {
        string text = GetResultText(result);
        if (!result.IsError.GetValueOrDefault())
        {
            return text;
        }

        throw new InvalidOperationException(
            $"Tool '{toolName}' returned an MCP error result: {text}");
    }

    private static string GetResultText(CallToolResult result)
    {
        string[] textBlocks = result.Content
            .OfType<TextContentBlock>()
            .Select(block => block.Text)
            .Where(text => !string.IsNullOrWhiteSpace(text))
            .ToArray();

        string text = textBlocks.Length == 0
            ? string.Empty
            : string.Join(Environment.NewLine, textBlocks);
        return text;
    }

    private static string ResolveAppExecutablePath()
    {
        string? configuredPath = Environment.GetEnvironmentVariable("SOLIDWORKS_MCP_APP_EXE");
        if (!string.IsNullOrWhiteSpace(configuredPath) && File.Exists(configuredPath))
        {
            return Path.GetFullPath(configuredPath);
        }

        foreach (var process in Process.GetProcessesByName("SolidWorksMcpApp"))
        {
            try
            {
                string? processPath = process.MainModule?.FileName;
                if (!string.IsNullOrWhiteSpace(processPath) && File.Exists(processPath))
                {
                    return Path.GetFullPath(processPath);
                }
            }
            catch
            {
                // Best effort only; keep searching other candidates.
            }
            finally
            {
                process.Dispose();
            }
        }

        string repositoryRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".."));
        string[] candidates =
        [
            Path.Combine(repositoryRoot, "artifacts", "self-hosted", "win-x64", "SolidWorksMcpApp.exe"),
            Path.Combine(repositoryRoot, "app", "SolidWorksMcpApp", "bin", "Release", "net8.0-windows", "win-x64", "SolidWorksMcpApp.exe"),
            Path.Combine(repositoryRoot, "app", "SolidWorksMcpApp", "bin", "Debug", "net8.0-windows", "win-x64", "SolidWorksMcpApp.exe"),
        ];

        var existingCandidate = candidates
            .Where(File.Exists)
            .Select(path => new FileInfo(path))
            .OrderByDescending(info => info.LastWriteTimeUtc)
            .FirstOrDefault();

        if (existingCandidate is not null)
        {
            return existingCandidate.FullName;
        }

        throw new FileNotFoundException(
            "Could not locate SolidWorksMcpApp.exe for the hub/proxy integration tests. " +
            "Set SOLIDWORKS_MCP_APP_EXE or build the tray app first.");
    }
}

internal sealed class McpSwConnectionManager : ISwConnectionManager
{
    private sealed record ConnectToolResult(
        bool Connected,
        SolidWorksConnectionAttemptInfo? ConnectionAttempt,
        SolidWorksCompatibilityInfo? Compatibility);

    private readonly SolidWorksMcpHubTestClient _client;

    public McpSwConnectionManager(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public bool IsConnected { get; private set; }

    public ISldWorksApp? SwApp => null;

    public SolidWorksConnectionAttemptInfo? LastConnectionAttempt { get; private set; }

    public void Connect()
    {
        var result = _client.CallTool<ConnectToolResult>("SolidWorksConnect");
        IsConnected = result.Connected;
        LastConnectionAttempt = result.ConnectionAttempt;
    }

    public void Disconnect()
    {
        _client.CallToolText("SolidWorksDisconnect");
        IsConnected = false;
        LastConnectionAttempt = null;
    }

    public void EnsureConnected() => Connect();

    public SolidWorksCompatibilityInfo GetCompatibilityInfo()
    {
        EnsureConnected();
        return _client.CallTool<SolidWorksCompatibilityInfo>("GetSolidWorksCompatibility");
    }
}

internal sealed class McpDocumentService : IDocumentService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpDocumentService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public SwDocumentInfo NewDocument(SwDocType docType, string? templatePath = null)
        => _client.CallTool<SwDocumentInfo>("NewDocument", SolidWorksMcpHubTestClient.Args(
            ("type", docType.ToString()),
            ("templatePath", templatePath)));

    public SwOpenResult OpenDocument(string path)
        => _client.CallTool<SwOpenResult>("OpenDocument", SolidWorksMcpHubTestClient.Args(("path", path)));

    public SwDocumentInfo ActivateDocumentByTitle(string title)
        => _client.CallTool<SwDocumentInfo>("ActivateDocumentByTitle", SolidWorksMcpHubTestClient.Args(("title", title)));

    public void CloseDocument(string path)
        => _client.CallToolText("CloseDocument", SolidWorksMcpHubTestClient.Args(("path", path)));

    public SwSaveResult SaveDocument(string path)
        => _client.CallTool<SwSaveResult>("SaveDocument", SolidWorksMcpHubTestClient.Args(("path", path)));

    public RebuildStateInfo GetActiveDocumentRebuildState()
        => _client.CallTool<RebuildStateInfo>("GetActiveDocumentRebuildState");

    public RebuildExecutionResult ForceRebuildActiveDocument(bool topOnly = false)
        => _client.CallTool<RebuildExecutionResult>("ForceRebuildActiveDocument", SolidWorksMcpHubTestClient.Args(("topOnly", topOnly)));

    public SwSaveResult SaveDocumentAs(string outputPath, string? sourcePath = null, bool saveAsCopy = true)
        => _client.CallTool<SwSaveResult>("SaveDocumentAs", SolidWorksMcpHubTestClient.Args(
            ("outputPath", outputPath),
            ("sourcePath", sourcePath),
            ("saveAsCopy", saveAsCopy)));

    public SwSaveResult SaveDocumentAsByTitle(string outputPath, string sourceTitle, bool saveAsCopy = true)
        => _client.CallTool<SwSaveResult>("SaveDocumentAsByTitle", SolidWorksMcpHubTestClient.Args(
            ("outputPath", outputPath),
            ("sourceTitle", sourceTitle),
            ("saveAsCopy", saveAsCopy)));

    public void Undo(int steps = 1)
        => _client.CallToolText("Undo", SolidWorksMcpHubTestClient.Args(("steps", steps)));

    public void ShowStandardView(SwStandardView view)
        => _client.CallToolText("ShowStandardView", SolidWorksMcpHubTestClient.Args(("view", view.ToString())));

    public void RotateView(double xDegrees = 0, double yDegrees = 0, double zDegrees = 0)
        => _client.CallToolText("RotateView", SolidWorksMcpHubTestClient.Args(
            ("xDegrees", xDegrees),
            ("yDegrees", yDegrees),
            ("zDegrees", zDegrees)));

    public SwImageExportResult ExportCurrentViewPng(string outputPath, int width = 1600, int height = 900, bool includeBase64Data = false, bool fitToView = true)
        => _client.CallTool<SwImageExportResult>("ExportCurrentViewPng", SolidWorksMcpHubTestClient.Args(
            ("outputPath", outputPath),
            ("width", width),
            ("height", height),
            ("includeBase64Data", includeBase64Data),
            ("fitToView", fitToView)));

    public SwStandardViewImageExportResult ExportStandardViewPngSet(
        string outputDirectory,
        string fileNamePrefix = "view",
        int width = 1600,
        int height = 900,
        bool includeBase64Data = false)
        => _client.CallTool<SwStandardViewImageExportResult>("ExportStandardViewPngSet", SolidWorksMcpHubTestClient.Args(
            ("outputDirectory", outputDirectory),
            ("fileNamePrefix", fileNamePrefix),
            ("width", width),
            ("height", height),
            ("includeBase64Data", includeBase64Data)));

    public SwDocumentInfo[] ListDocuments()
        => _client.CallTool<SwDocumentInfo[]>("ListDocuments");

    public SwDocumentInfo? GetActiveDocument()
        => _client.CallToolNullable<SwDocumentInfo>("GetActiveDocument");

    public SwDocumentConfigurationInventory InspectActiveDocumentConfigurations()
        => _client.CallTool<SwDocumentConfigurationInventory>("InspectActiveDocumentConfigurations");

    public SwDocumentConfigurationSwitchResult SetActiveDocumentConfiguration(
        string configurationName,
        bool rebuild = true)
        => _client.CallTool<SwDocumentConfigurationSwitchResult>(
            "SetActiveDocumentConfiguration",
            SolidWorksMcpHubTestClient.Args(
                ("configurationName", configurationName),
                ("rebuild", rebuild)));

    public SwDocumentConfigurationInventory InspectDocumentConfigurations(string path)
        => _client.CallTool<SwDocumentConfigurationInventory>(
            "InspectDocumentConfigurations",
            SolidWorksMcpHubTestClient.Args(("path", path)));
}

internal sealed class McpSelectionService : ISelectionService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpSelectionService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public SelectionResult SelectByName(string name, string selType, bool append = false, int mark = 0)
        => _client.CallTool<SelectionResult>("SelectByName", SolidWorksMcpHubTestClient.Args(
            ("name", name),
            ("selType", selType),
            ("append", append),
            ("mark", mark)));

    public IReadOnlyList<SelectableEntityInfo> ListEntities(SelectableEntityType? entityType = null, string? componentName = null)
        => _client.CallTool<List<SelectableEntityInfo>>("ListEntities", SolidWorksMcpHubTestClient.Args(
            ("entityType", entityType?.ToString()),
            ("componentName", componentName)));

    public FaceGeometryListResult ListFaceGeometry(string componentName, bool planarOnly = true)
        => _client.CallTool<FaceGeometryListResult>("ListFaceGeometry", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("planarOnly", planarOnly)));

    public SelectionResult SelectFaceGeometry(string componentName, int faceIndex, bool append = false, int mark = 0)
        => _client.CallTool<SelectionResult>("SelectFaceGeometry", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("faceIndex", faceIndex),
            ("append", append),
            ("mark", mark)));

    public SelectionResult ActivateLeafComponentDocument(string componentName)
        => _client.CallTool<SelectionResult>("ActivateLeafComponentDocument", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName)));

    public SelectionResult SelectActivePartFaceGeometry(int faceIndex, bool append = false, int mark = 0)
        => _client.CallTool<SelectionResult>("SelectActivePartFaceGeometry", SolidWorksMcpHubTestClient.Args(
            ("faceIndex", faceIndex),
            ("append", append),
            ("mark", mark)));

    public SelectionResult ZoomToSelection()
        => _client.CallTool<SelectionResult>("ZoomToSelection");

    public IReadOnlyList<ReferencePlaneInfo> ListReferencePlanes()
        => _client.CallTool<List<ReferencePlaneInfo>>("ListReferencePlanes");

    public SolidWorksContextInfo GetSolidWorksContext()
        => _client.CallTool<SolidWorksContextInfo>("GetSolidWorksContext");

    public IReadOnlyList<FeatureTreeItemInfo> ListFeatureTree()
        => _client.CallTool<List<FeatureTreeItemInfo>>("ListFeatureTree");

    public ActiveFeatureManagerTreeResult TraverseActiveFeatureManagerTree()
        => _client.CallTool<ActiveFeatureManagerTreeResult>("TraverseActiveFeatureManagerTree");

    public IReadOnlyList<ModelHealthSensorInfo> ListModelHealthSensors()
        => _client.CallTool<List<ModelHealthSensorInfo>>("ListModelHealthSensors");

    public FeatureDiagnosticsResult GetFeatureDiagnostics()
        => _client.CallTool<FeatureDiagnosticsResult>("GetFeatureDiagnostics");

    public EditStateInfo GetEditState()
        => _client.CallTool<EditStateInfo>("GetEditState");

    public SelectionResult SelectEntity(SelectableEntityType entityType, int index, bool append = false, int mark = 0, string? componentName = null)
        => _client.CallTool<SelectionResult>("SelectEntity", SolidWorksMcpHubTestClient.Args(
            ("entityType", entityType.ToString()),
            ("index", index),
            ("append", append),
            ("mark", mark),
            ("componentName", componentName)));

    public EntityMeasurementResult MeasureEntities(
        SelectableEntityType firstEntityType,
        int firstIndex,
        SelectableEntityType secondEntityType,
        int secondIndex,
        string? firstComponentName = null,
        string? secondComponentName = null,
        int arcOption = 1)
        => _client.CallTool<EntityMeasurementResult>("MeasureEntities", SolidWorksMcpHubTestClient.Args(
            ("firstEntityType", firstEntityType.ToString()),
            ("firstIndex", firstIndex),
            ("secondEntityType", secondEntityType.ToString()),
            ("secondIndex", secondIndex),
            ("firstComponentName", firstComponentName),
            ("secondComponentName", secondComponentName),
            ("arcOption", arcOption)));

    public SelectionResult DeleteFeatureByName(string featureName)
        => _client.CallTool<SelectionResult>("DeleteFeatureByName", SolidWorksMcpHubTestClient.Args(("featureName", featureName)));

    public DeleteFeaturesResult DeleteUnusedSketches()
        => _client.CallTool<DeleteFeaturesResult>("DeleteUnusedSketches");

    public void ClearSelection()
        => _client.CallToolText("ClearSelection");

    public FaceMappingResult RecordFaceMapping(string faceName, string componentName)
        => _client.CallTool<FaceMappingResult>("RecordFaceMapping", SolidWorksMcpHubTestClient.Args(
            ("faceName", faceName), ("componentName", componentName)));

    public FaceMappingResult RecordFirstFaceMapping(string faceName, string componentName)
        => _client.CallTool<FaceMappingResult>("RecordFirstFaceMapping", SolidWorksMcpHubTestClient.Args(
            ("faceName", faceName), ("componentName", componentName)));

    public FaceMappingResult SelectFaceByName(string faceName, string componentName, bool append = false, int mark = 0)
        => _client.CallTool<FaceMappingResult>("SelectFaceByName", SolidWorksMcpHubTestClient.Args(
            ("faceName", faceName), ("componentName", componentName), ("append", append), ("mark", mark)));

    public FaceMappingProbeResult GetSelectedFaceMappingProbe(string? faceName = null, string? componentName = null)
        => _client.CallTool<FaceMappingProbeResult>("GetSelectedFaceMappingProbe", SolidWorksMcpHubTestClient.Args(
            ("faceName", faceName), ("componentName", componentName)));

    public SelectedFaceCenterResult GetSelectedFaceCenter()
        => _client.CallTool<SelectedFaceCenterResult>("GetSelectedFaceCenter");
}

internal sealed class McpSketchService : ISketchService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpSketchService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public void InsertSketch() => _client.CallToolText("InsertSketch");

    public void FinishSketch() => _client.CallToolText("FinishSketch");

    public void SketchUseEdge3(bool chain = false, bool innerLoops = true)
        => _client.CallToolText("SketchUseEdge3", SolidWorksMcpHubTestClient.Args(
            ("chain", chain),
            ("innerLoops", innerLoops)));

    public SketchEntityInfo AddPoint(double x, double y)
        => _client.CallTool<SketchEntityInfo>("AddPoint", SolidWorksMcpHubTestClient.Args(("x", x), ("y", y)));

    public SketchEntityInfo AddEllipse(double cx, double cy, double majorX, double majorY, double minorX, double minorY)
        => _client.CallTool<SketchEntityInfo>("AddEllipse", SolidWorksMcpHubTestClient.Args(
            ("cx", cx),
            ("cy", cy),
            ("majorX", majorX),
            ("majorY", majorY),
            ("minorX", minorX),
            ("minorY", minorY)));

    public SketchEntityInfo AddPolygon(double cx, double cy, double x, double y, int sides, bool inscribed)
        => _client.CallTool<SketchEntityInfo>("AddPolygon", SolidWorksMcpHubTestClient.Args(
            ("cx", cx),
            ("cy", cy),
            ("x", x),
            ("y", y),
            ("sides", sides),
            ("inscribed", inscribed)));

    public SketchEntityInfo AddText(double x, double y, string text, SketchTextOptions? options = null)
        => _client.CallTool<SketchEntityInfo>(
            "AddText",
            SolidWorksMcpHubTestClient.Args(
                ("x", x),
                ("y", y),
                ("text", text),
                ("justification", options?.Justification.ToString()),
                ("flipDirection", options?.FlipDirection),
                ("horizontalMirror", options?.HorizontalMirror),
                ("height", options?.Height),
                ("fontName", options?.FontName),
                ("bold", options?.Bold),
                ("italic", options?.Italic),
                ("underline", options?.Underline),
                ("widthFactor", options?.WidthFactor),
                ("charSpacingFactor", options?.CharSpacingFactor),
                ("rotationDegrees", options?.RotationDegrees)));

    public SketchEntityInfo AddLine(double x1, double y1, double x2, double y2)
        => _client.CallTool<SketchEntityInfo>("AddLine", SolidWorksMcpHubTestClient.Args(
            ("x1", x1),
            ("y1", y1),
            ("x2", x2),
            ("y2", y2)));

    public SketchEntityInfo AddCircle(double cx, double cy, double radius)
        => _client.CallTool<SketchEntityInfo>("AddCircle", SolidWorksMcpHubTestClient.Args(
            ("cx", cx),
            ("cy", cy),
            ("radius", radius)));

    public SketchEntityInfo AddRectangle(double x1, double y1, double x2, double y2)
        => _client.CallTool<SketchEntityInfo>("AddRectangle", SolidWorksMcpHubTestClient.Args(
            ("x1", x1),
            ("y1", y1),
            ("x2", x2),
            ("y2", y2)));

    public SketchEntityInfo AddArc(double cx, double cy, double x1, double y1, double x2, double y2, int direction)
        => _client.CallTool<SketchEntityInfo>("AddArc", SolidWorksMcpHubTestClient.Args(
            ("cx", cx),
            ("cy", cy),
            ("x1", x1),
            ("y1", y1),
            ("x2", x2),
            ("y2", y2),
            ("direction", direction)));
}

internal sealed class McpFeatureService : IFeatureService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpFeatureService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public FeatureInfo Extrude(double depth, EndCondition endCondition = EndCondition.Blind, bool flipDirection = false)
        => _client.CallTool<FeatureInfo>("Extrude", SolidWorksMcpHubTestClient.Args(
            ("depth", depth),
            ("endCondition", (int)endCondition),
            ("flipDirection", flipDirection)));

    public FeatureInfo ExtrudeCut(double depth, EndCondition endCondition = EndCondition.Blind, bool flipDirection = false)
        => _client.CallTool<FeatureInfo>("ExtrudeCut", SolidWorksMcpHubTestClient.Args(
            ("depth", depth),
            ("endCondition", (int)endCondition),
            ("flipDirection", flipDirection)));

    public FeatureInfo Revolve(double angleDegrees, bool isCut = false)
        => _client.CallTool<FeatureInfo>("Revolve", SolidWorksMcpHubTestClient.Args(
            ("angleDegrees", angleDegrees),
            ("isCut", isCut)));

    public FeatureInfo Fillet(double radius)
        => _client.CallTool<FeatureInfo>("Fillet", SolidWorksMcpHubTestClient.Args(("radius", radius)));

    public FeatureInfo Chamfer(double distance)
        => _client.CallTool<FeatureInfo>("Chamfer", SolidWorksMcpHubTestClient.Args(("distance", distance)));

    public FeatureInfo Shell(double thickness)
        => _client.CallTool<FeatureInfo>("Shell", SolidWorksMcpHubTestClient.Args(("thickness", thickness)));
}

internal sealed class McpAssemblyService : IAssemblyService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpAssemblyService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public ComponentInfo InsertComponent(string filePath, double x = 0, double y = 0, double z = 0)
        => _client.CallTool<ComponentInfo>("InsertComponent", SolidWorksMcpHubTestClient.Args(
            ("filePath", filePath),
            ("x", x),
            ("y", y),
            ("z", z)));

    public MateOperationResult AddMateCoincident(MateAlign align = MateAlign.Closest)
        => _client.CallTool<MateOperationResult>("AddMateCoincident", SolidWorksMcpHubTestClient.Args(("align", (int)align)));

    public MateOperationResult AddMateConcentric(MateAlign align = MateAlign.Closest)
        => _client.CallTool<MateOperationResult>("AddMateConcentric", SolidWorksMcpHubTestClient.Args(("align", (int)align)));

    public MateOperationResult AddMateParallel(MateAlign align = MateAlign.Closest)
        => _client.CallTool<MateOperationResult>("AddMateParallel", SolidWorksMcpHubTestClient.Args(("align", (int)align)));

    public MateOperationResult AddMateDistance(double distance, MateAlign align = MateAlign.Closest)
        => _client.CallTool<MateOperationResult>("AddMateDistance", SolidWorksMcpHubTestClient.Args(
            ("distance", distance),
            ("align", (int)align)));

    public MateOperationResult AddMateAngle(double angleDegrees, MateAlign align = MateAlign.Closest)
        => _client.CallTool<MateOperationResult>("AddMateAngle", SolidWorksMcpHubTestClient.Args(
            ("angleDegrees", angleDegrees),
            ("align", (int)align)));

    public IReadOnlyList<ComponentInfo> ListComponents()
        => _client.CallTool<List<ComponentInfo>>(
            "ListComponents",
            SolidWorksMcpHubTestClient.Args());

    public TopLevelComponentIsolationResult SuppressTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true)
        => _client.CallTool<TopLevelComponentIsolationResult>(
            "SuppressTopLevelComponentsExcept",
            SolidWorksMcpHubTestClient.Args(
                ("keepComponentNames", keepComponentNames.ToArray()),
                ("rebuild", rebuild)));

    public TopLevelComponentVisibilityIsolationResult HideTopLevelComponentsExcept(
        IReadOnlyList<string> keepComponentNames,
        bool rebuild = true)
        => _client.CallTool<TopLevelComponentVisibilityIsolationResult>(
            "HideTopLevelComponentsExcept",
            SolidWorksMcpHubTestClient.Args(
                ("keepComponentNames", keepComponentNames.ToArray()),
                ("rebuild", rebuild)));

    public ComponentSolvingStateResult SetTopLevelComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true)
        => _client.CallTool<ComponentSolvingStateResult>(
            "SetTopLevelComponentSolvingState",
            SolidWorksMcpHubTestClient.Args(
                ("hierarchyPath", hierarchyPath),
                ("solvingState", solvingState),
                ("rebuild", rebuild)));

    public ComponentSolvingStateResult SetComponentSolvingState(
        string hierarchyPath,
        int solvingState,
        bool rebuild = true)
        => _client.CallTool<ComponentSolvingStateResult>(
            "SetComponentSolvingState",
            SolidWorksMcpHubTestClient.Args(
                ("hierarchyPath", hierarchyPath),
                ("solvingState", solvingState),
                ("rebuild", rebuild)));

    public ResolveLightweightComponentsResult ResolveAllLightweightComponents(
        bool warnIfNotResolved = false,
        bool rebuild = true)
        => _client.CallTool<ResolveLightweightComponentsResult>(
            "ResolveAllLightweightComponents",
            SolidWorksMcpHubTestClient.Args(
                ("warnIfNotResolved", warnIfNotResolved),
                ("rebuild", rebuild)));

    public IReadOnlyList<ComponentInstanceInfo> ListComponentsRecursive()
        => _client.CallTool<List<ComponentInstanceInfo>>(
            "ListComponentsRecursive",
            SolidWorksMcpHubTestClient.Args());

    public IReadOnlyList<ComponentPoseInfo> ListComponentPoses(bool topLevelOnly = true)
        => _client.CallTool<List<ComponentPoseInfo>>("ListComponentPoses", SolidWorksMcpHubTestClient.Args(("topLevelOnly", topLevelOnly)));

    public IReadOnlyList<ComponentPoseInfo> ListTopLevelComponentSubtreePoses(string hierarchyPath)
        => _client.CallTool<List<ComponentPoseInfo>>(
            "ListTopLevelComponentSubtreePoses",
            SolidWorksMcpHubTestClient.Args(("hierarchyPath", hierarchyPath)));

    public AssemblyTargetResolutionResult ResolveComponentTarget(string? componentName = null, string? hierarchyPath = null, string? componentPath = null)
        => _client.CallTool<AssemblyTargetResolutionResult>(
            "ResolveComponentTarget",
            SolidWorksMcpHubTestClient.Args(
                ("componentName", componentName),
                ("hierarchyPath", hierarchyPath),
                ("componentPath", componentPath)));

    public SharedPartEditImpactResult AnalyzeSharedPartEditImpact(string? componentName = null, string? hierarchyPath = null, string? componentPath = null)
        => _client.CallTool<SharedPartEditImpactResult>(
            "AnalyzeSharedPartEditImpact",
            SolidWorksMcpHubTestClient.Args(
                ("componentName", componentName),
                ("hierarchyPath", hierarchyPath),
                ("componentPath", componentPath)));

    public AssemblyMatePairExportResult ExportMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string? outputPath = null,
        bool saveJson = true)
        => _client.CallTool<AssemblyMatePairExportResult>("ExportMatePair", SolidWorksMcpHubTestClient.Args(
            ("sourceAssemblyPath", sourceAssemblyPath),
            ("firstModuleSelector", firstModuleSelector),
            ("secondModuleSelector", secondModuleSelector),
            ("outputPath", outputPath),
            ("saveJson", saveJson)));

    public AssemblyMatePairCandidateResult FindMatePairCandidates(
        string sourceAssemblyPath,
        IReadOnlyList<string>? allowedModuleTokens = null,
        int maxResults = 10)
        => _client.CallTool<AssemblyMatePairCandidateResult>("FindMatePairCandidates", SolidWorksMcpHubTestClient.Args(
            ("sourceAssemblyPath", sourceAssemblyPath),
            ("allowedModuleTokens", allowedModuleTokens?.ToArray()),
            ("maxResults", maxResults)));

    public AssemblyMatePairRoundTripResult RoundTripMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string outputAssemblyPath,
        string? exportJsonPath = null,
        bool allowAutomaticFallback = true,
        IReadOnlyList<string>? allowedModuleTokens = null)
        => _client.CallTool<AssemblyMatePairRoundTripResult>("RoundTripMatePair", SolidWorksMcpHubTestClient.Args(
            ("sourceAssemblyPath", sourceAssemblyPath),
            ("firstModuleSelector", firstModuleSelector),
            ("secondModuleSelector", secondModuleSelector),
            ("outputAssemblyPath", outputAssemblyPath),
            ("exportJsonPath", exportJsonPath),
            ("allowAutomaticFallback", allowAutomaticFallback),
            ("allowedModuleTokens", allowedModuleTokens?.ToArray())));

    public AssemblyModuleMateGraphResult ExportModuleMateGraph(
        string sourceAssemblyPath,
        IReadOnlyList<string>? moduleTokens = null,
        string? outputPath = null,
        bool saveJson = true)
        => _client.CallTool<AssemblyModuleMateGraphResult>("ExportModuleMateGraph", SolidWorksMcpHubTestClient.Args(
            ("sourceAssemblyPath", sourceAssemblyPath),
            ("moduleTokens", moduleTokens?.ToArray()),
            ("outputPath", outputPath),
            ("saveJson", saveJson)));

    public AssemblyTopLevelMateAuditResult AuditTopLevelMateFeatures(
        string sourceAssemblyPath,
        string? outputPath = null,
        bool saveJson = true)
        => _client.CallTool<AssemblyTopLevelMateAuditResult>("AuditTopLevelMateFeatures", SolidWorksMcpHubTestClient.Args(
            ("sourceAssemblyPath", sourceAssemblyPath),
            ("outputPath", outputPath),
            ("saveJson", saveJson)));

    public AssemblySlotMateUpdateResult UpdateTopLevelSlotMate(
        string assemblyPath,
        string mateName,
        int constraint,
        double distance = 0,
        double percent = 0,
        bool flipDirection = false,
        bool save = true)
        => _client.CallTool<AssemblySlotMateUpdateResult>("UpdateTopLevelSlotMate", SolidWorksMcpHubTestClient.Args(
            ("assemblyPath", assemblyPath),
            ("mateName", mateName),
            ("constraint", constraint),
            ("distance", distance),
            ("percent", percent),
            ("flipDirection", flipDirection),
            ("save", save)));

    public AssemblyModuleMateReconstructionExperimentResult RunModuleMateReconstructionExperiment(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        string mode,
        string baseModuleToken = "A600",
        IReadOnlyList<string>? moduleTokens = null,
        IReadOnlyList<string>? residualAnchorModuleSelectors = null,
        double poseToleranceMeters = 1e-5,
        double rotationTolerance = 1e-6)
        => _client.CallTool<AssemblyModuleMateReconstructionExperimentResult>(
            "RunModuleMateReconstructionExperiment",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("outputAssemblyPath", outputAssemblyPath),
                ("mode", mode),
                ("baseModuleToken", baseModuleToken),
                ("moduleTokens", moduleTokens?.ToArray()),
                ("residualAnchorModuleSelectors", residualAnchorModuleSelectors?.ToArray()),
                ("poseToleranceMeters", poseToleranceMeters),
                ("rotationTolerance", rotationTolerance)));

    public AssemblyEditableMateGraphReconstructionResult RebuildAssemblyFromMateGraph(
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string? baseModuleToken = null,
        string? initialPlacementMode = null)
        => _client.CallTool<AssemblyEditableMateGraphReconstructionResult>(
            "RebuildAssemblyFromMateGraph",
            SolidWorksMcpHubTestClient.Args(
                ("effectiveMateGraphPath", effectiveMateGraphPath),
                ("outputAssemblyPath", outputAssemblyPath),
                ("baseModuleToken", baseModuleToken),
                ("initialPlacementMode", initialPlacementMode)));

    public AssemblyContextMateGraphReconstructionResult RemateComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false,
        bool forceInitialDisplacement = false)
        => _client.CallTool<AssemblyContextMateGraphReconstructionResult>(
            "RemateComponentInAssemblyContextFromMateGraph",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("effectiveMateGraphPath", effectiveMateGraphPath),
                ("outputAssemblyPath", outputAssemblyPath),
                ("targetModuleToken", targetModuleToken),
                ("preserveResolvedSourceSession", preserveResolvedSourceSession),
                ("forceInitialDisplacement", forceInitialDisplacement)));

    public AssemblyContextRelationVerificationResult VerifyRelationsInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false)
        => _client.CallTool<AssemblyContextRelationVerificationResult>(
            "VerifyRelationsInAssemblyContextFromMateGraph",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("effectiveMateGraphPath", effectiveMateGraphPath),
                ("targetModuleToken", targetModuleToken),
                ("preserveResolvedSourceSession", preserveResolvedSourceSession)));

    public AssemblyContextIncrementalInsertResult InsertComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken)
        => _client.CallTool<AssemblyContextIncrementalInsertResult>(
            "InsertComponentInAssemblyContextFromMateGraph",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("effectiveMateGraphPath", effectiveMateGraphPath),
                ("outputAssemblyPath", outputAssemblyPath),
                ("targetModuleToken", targetModuleToken)));

    public AssemblyStaticContextSubsetResult CreateAssemblyStaticContextSubset(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        IReadOnlyList<string> keepComponentPaths)
        => _client.CallTool<AssemblyStaticContextSubsetResult>(
            "CreateAssemblyStaticContextSubset",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("outputAssemblyPath", outputAssemblyPath),
                ("keepComponentPaths", keepComponentPaths.ToArray())));

    public AssemblyFaceEndpointCatalogResult BuildFaceEndpointCatalog(
        string sourceAssemblyPath,
        IReadOnlyList<string> moduleTokens,
        string? outputPath = null,
        bool sourceMateFacesOnly = true,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        bool saveJson = true)
        => _client.CallTool<AssemblyFaceEndpointCatalogResult>(
            "BuildFaceEndpointCatalog",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("moduleTokens", moduleTokens.ToArray()),
                ("outputPath", outputPath),
                ("sourceMateFacesOnly", sourceMateFacesOnly),
                ("planarOnly", planarOnly),
                ("minimumFaceArea", minimumFaceArea),
                ("saveJson", saveJson)));

    public AssemblyFaceEndpointCatalogResult BuildLeafFaceEndpointCatalog(
        string sourceAssemblyPath,
        string moduleToken,
        string leafSelector,
        string? outputPath = null,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        int maximumFaceCount = 500,
        bool saveJson = true)
        => _client.CallTool<AssemblyFaceEndpointCatalogResult>(
            "BuildLeafFaceEndpointCatalog",
            SolidWorksMcpHubTestClient.Args(
                ("sourceAssemblyPath", sourceAssemblyPath),
                ("moduleToken", moduleToken),
                ("leafSelector", leafSelector),
                ("outputPath", outputPath),
                ("planarOnly", planarOnly),
                ("minimumFaceArea", minimumFaceArea),
                ("maximumFaceCount", maximumFaceCount),
                ("saveJson", saveJson)));

    public AssemblyFaceEndpointSelectionResult SelectFaceEndpointFromCatalog(
        string catalogPath,
        string endpointId,
        bool zoomToSelection = true)
        => _client.CallTool<AssemblyFaceEndpointSelectionResult>(
            "SelectFaceEndpointFromCatalog",
            SolidWorksMcpHubTestClient.Args(
                ("catalogPath", catalogPath),
                ("endpointId", endpointId),
                ("zoomToSelection", zoomToSelection)));

    public AssemblyFaceEndpointCatalogEntry CaptureSelectedFaceEndpoint(string moduleToken)
        => _client.CallTool<AssemblyFaceEndpointCatalogEntry>(
            "CaptureSelectedFaceEndpoint",
            SolidWorksMcpHubTestClient.Args(("moduleToken", moduleToken)));

    public AssemblyFeatureTreeTraversalResult TraverseAssemblyFeatureTrees()
        => _client.CallTool<AssemblyFeatureTreeTraversalResult>("TraverseAssemblyChildFeatureTrees");

    public AssemblyFeatureSearchResult SearchAssemblyFeatureTrees(string query, bool exactNameOnly = false, int maxResults = 200)
        => _client.CallTool<AssemblyFeatureSearchResult>("SearchAssemblyChildFeatures", SolidWorksMcpHubTestClient.Args(
            ("query", query),
            ("exactNameOnly", exactNameOnly),
            ("maxResults", maxResults)));

    public OpenComponentForEditingResult OpenComponentForEditing(string componentPath, string? hierarchyPath = null)
        => _client.CallTool<OpenComponentForEditingResult>("OpenAssemblyChildComponentForEditing", SolidWorksMcpHubTestClient.Args(
            ("componentPath", componentPath),
            ("hierarchyPath", hierarchyPath)));

    public AssemblyInterferenceCheckResult CheckInterference(IReadOnlyList<string>? hierarchyPaths = null, bool treatCoincidenceAsInterference = false)
        => _client.CallTool<AssemblyInterferenceCheckResult>("CheckInterference", SolidWorksMcpHubTestClient.Args(
            ("hierarchyPaths", hierarchyPaths?.ToArray()),
            ("treatCoincidenceAsInterference", treatCoincidenceAsInterference)));

    public LeafBodyInterferenceCheckResult CheckInterferenceByLeafBodies(IReadOnlyList<string> hierarchyPaths, bool treatCoincidenceAsInterference = false)
        => _client.CallTool<LeafBodyInterferenceCheckResult>("CheckInterferenceByLeafBodies", SolidWorksMcpHubTestClient.Args(
            ("hierarchyPaths", hierarchyPaths.ToArray()),
            ("treatCoincidenceAsInterference", treatCoincidenceAsInterference)));

    public LeafBodyEnvelopeCaptureResult CaptureLeafBodyEnvelopes(string hierarchyPath)
        => _client.CallTool<LeafBodyEnvelopeCaptureResult>("CaptureLeafBodyEnvelopes", SolidWorksMcpHubTestClient.Args(
            ("hierarchyPath", hierarchyPath)));

    public AssemblyComponentReplacementResult ReplaceComponent(
        string hierarchyPath,
        string replacementFilePath,
        string configName = "",
        bool replaceAllInstances = false,
        int useConfigChoice = 0,
        bool reattachMates = true)
        => _client.CallTool<AssemblyComponentReplacementResult>("ReplaceComponent", SolidWorksMcpHubTestClient.Args(
            ("hierarchyPath", hierarchyPath),
            ("replacementFilePath", replacementFilePath),
            ("configName", configName),
            ("replaceAllInstances", replaceAllInstances),
            ("useConfigChoice", useConfigChoice),
            ("reattachMates", reattachMates)));

    public ComponentTransformResult MoveComponent(string componentName, double deltaX, double deltaY, double deltaZ, bool rebuild = true)
        => _client.CallTool<ComponentTransformResult>("MoveComponent", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("deltaX", deltaX),
            ("deltaY", deltaY),
            ("deltaZ", deltaZ)));

    public ComponentTransformResult RotateComponent(string componentName, double axisX, double axisY, double axisZ, double angleDegrees, bool rebuild = true)
        => _client.CallTool<ComponentTransformResult>("RotateComponent", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("axisX", axisX),
            ("axisY", axisY),
            ("axisZ", axisZ),
            ("angleDegrees", angleDegrees)));

    public ComponentTransformResult SetComponentOrientation(
        string componentName,
        IReadOnlyList<double> xAxis,
        IReadOnlyList<double> yAxis,
        IReadOnlyList<double> zAxis,
        bool rebuild = true)
        => _client.CallTool<ComponentTransformResult>("SetComponentOrientation", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("xAxis", xAxis.ToArray()),
            ("yAxis", yAxis.ToArray()),
            ("zAxis", zAxis.ToArray()),
            ("rebuild", rebuild)));

    public ComponentTransformResult SetComponentTransform(
        string componentName,
        IReadOnlyList<double> transform,
        bool rebuild = true)
        => _client.CallTool<ComponentTransformResult>("SetComponentTransform", SolidWorksMcpHubTestClient.Args(
            ("componentName", componentName),
            ("transform", transform.ToArray()),
            ("rebuild", rebuild)));

    public ComponentReferencedConfigurationResult SetComponentReferencedConfiguration(
        string componentName,
        string configurationName,
        bool rebuild = true)
        => _client.CallTool<ComponentReferencedConfigurationResult>(
            "SetComponentReferencedConfiguration",
            SolidWorksMcpHubTestClient.Args(
                ("componentName", componentName),
                ("configurationName", configurationName),
                ("rebuild", rebuild)));

    public IReadOnlyList<string> SuppressTopLevelMateFeatures()
        => throw new NotSupportedException("Internal batch-layout helper is not exposed as an MCP tool.");

    public IReadOnlyList<string> RestoreTopLevelMateFeatures(IReadOnlyList<string> featureNames)
        => throw new NotSupportedException("Internal batch-layout helper is not exposed as an MCP tool.");

    public ComponentInfo RenameComponent(string currentName, string newName)
        => _client.CallTool<ComponentInfo>("RenameComponent", SolidWorksMcpHubTestClient.Args(
            ("currentName", currentName),
            ("newName", newName)));
}

internal sealed class McpWorkflowService : IWorkflowService
{
    private readonly SolidWorksMcpHubTestClient _client;

    public McpWorkflowService(SolidWorksMcpHubTestClient client)
    {
        _client = client;
    }

    public ActiveDocumentHealthDiagnosticsResult DiagnoseActiveDocumentHealth(bool forceRebuild = true, bool topOnly = false, bool saveDocument = false)
        => _client.CallTool<ActiveDocumentHealthDiagnosticsResult>("DiagnoseActiveDocumentHealth", SolidWorksMcpHubTestClient.Args(
            ("forceRebuild", forceRebuild),
            ("topOnly", topOnly),
            ("saveDocument", saveDocument)));

    public ModelStructureHygieneAuditResult ReviewModelStructureHygiene()
        => _client.CallTool<ModelStructureHygieneAuditResult>("ReviewModelStructureHygiene");

    public TargetedStaticInterferenceReviewResult ReviewTargetedStaticInterference(
        string firstHierarchyPath,
        string secondHierarchyPath,
        bool treatCoincidenceAsInterference = false)
        => _client.CallTool<TargetedStaticInterferenceReviewResult>("ReviewTargetedStaticInterference", SolidWorksMcpHubTestClient.Args(
            ("firstHierarchyPath", firstHierarchyPath),
            ("secondHierarchyPath", secondHierarchyPath),
            ("treatCoincidenceAsInterference", treatCoincidenceAsInterference)));

    public NestedComponentReplacementWorkflowResult ReplaceNestedComponentAndVerifyPersistence(
        string replacementFilePath,
        string? componentName = null,
        string? hierarchyPath = null,
        string? componentPath = null,
        string configName = "",
        int useConfigChoice = 0,
        bool reattachMates = true)
        => _client.CallTool<NestedComponentReplacementWorkflowResult>("ReplaceNestedComponentAndVerifyPersistence", SolidWorksMcpHubTestClient.Args(
            ("replacementFilePath", replacementFilePath),
            ("componentName", componentName),
            ("hierarchyPath", hierarchyPath),
            ("componentPath", componentPath),
            ("configName", configName),
            ("useConfigChoice", useConfigChoice),
            ("reattachMates", reattachMates)));
}
