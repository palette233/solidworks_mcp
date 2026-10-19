using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class DocumentTools(StaDispatcher sta, IDocumentService docs)
{
    [McpServerTool, Description("Create a new SolidWorks document. type: 'Part', 'Assembly', or 'Drawing'.")]
    public async Task<string> NewDocument(
        [Description("Document type: Part, Assembly, or Drawing")] string type = "Part",
        [Description("Optional path to a template file (.prtdot, .asmdot, .drwdot)")] string? templatePath = null)
    {
        var info = await sta.InvokeLoggedAsync(
            nameof(NewDocument),
            new { type, templatePath },
            () =>
            {
                var docType = ToolArgumentParsing.ParseDocType(type);
                return docs.NewDocument(docType, templatePath);
            });
        return JsonSerializer.Serialize(info);
    }

    [McpServerTool, Description("Open an existing SolidWorks document by file path.")]
    public async Task<string> OpenDocument(
        [Description("Full file path to the SolidWorks document")] string path)
    {
        var result = await sta.InvokeLoggedAsync(nameof(OpenDocument), new { path }, () => docs.OpenDocument(path));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Activate an already-open SolidWorks document by its window title without reopening or rebuilding it.")]
    public async Task<string> ActivateDocumentByTitle(
        [Description("Exact SolidWorks document title, for example FL9A24D062A000.001")] string title)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ActivateDocumentByTitle),
            new { title },
            () => docs.ActivateDocumentByTitle(title));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Close an open SolidWorks document by file path.")]
    public async Task<string> CloseDocument(
        [Description("Full file path of the document to close")] string path)
    {
        await sta.InvokeLoggedAsync(nameof(CloseDocument), new { path }, () => docs.CloseDocument(path));
        return $"Closed: {path}";
    }

    [McpServerTool, Description("Save an open SolidWorks document by file path.")]
    public async Task<string> SaveDocument(
        [Description("Full file path of the document to save")] string path)
    {
        var result = await sta.InvokeLoggedAsync(nameof(SaveDocument), new { path }, () => docs.SaveDocument(path));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Read the active SolidWorks document's native rebuild state.")]
    public async Task<string> GetActiveDocumentRebuildState()
    {
        var result = await sta.InvokeLoggedAsync(nameof(GetActiveDocumentRebuildState), null, docs.GetActiveDocumentRebuildState);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Force a rebuild of the active SolidWorks document and return the before/after rebuild state.")]
    public async Task<string> ForceRebuildActiveDocument(
        [Description("For assemblies, true rebuilds only the top-level assembly; false includes subassemblies.")] bool topOnly = false)
    {
        var result = await sta.InvokeLoggedAsync(nameof(ForceRebuildActiveDocument), new { topOnly }, () => docs.ForceRebuildActiveDocument(topOnly));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Save or export a SolidWorks document to a new file path. The output format is inferred from the extension, so this supports native SolidWorks formats and common exports like STEP or STL. When sourcePath is omitted, the active document is used.")]
    public async Task<string> SaveDocumentAs(
        [Description("Output file path. Extension determines the saved/exported format.")] string outputPath,
        [Description("Optional source document path. Defaults to the active document when omitted.")] string? sourcePath = null,
        [Description("When true, performs a copy/export and keeps the source document path unchanged.")] bool saveAsCopy = true)
    {
        var result = await sta.InvokeLoggedAsync(nameof(SaveDocumentAs), new { outputPath, sourcePath, saveAsCopy }, () => docs.SaveDocumentAs(outputPath, sourcePath, saveAsCopy));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Save an already-open SolidWorks document by its exact window title. Use this for untitled recovery documents or when the active-document COM pointer is unreliable in a long-running session.")]
    public async Task<string> SaveDocumentAsByTitle(
        [Description("Exact SolidWorks document title, for example model or 装配体8.")] string sourceTitle,
        [Description("Output file path. Extension determines the saved format.")] string outputPath,
        [Description("When true, writes a copy and leaves the original open document identity unchanged.")] bool saveAsCopy = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SaveDocumentAsByTitle),
            new { sourceTitle, outputPath, saveAsCopy },
            () => docs.SaveDocumentAsByTitle(outputPath, sourceTitle, saveAsCopy));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Undo the last N operations on the active SolidWorks document.")]
    public async Task<string> Undo(
        [Description("Number of undo steps to apply.")] int steps = 1)
    {
        await sta.InvokeLoggedAsync(nameof(Undo), new { steps }, () => docs.Undo(steps));
        return $"Undid {steps} step(s).";
    }

    [McpServerTool, Description("Switch the active SolidWorks document to a standard view. Supported values: front, back, left, right, top, bottom, isometric, trimetric, dimetric.")]
    public async Task<string> ShowStandardView(
        [Description("Standard view name.")] string view = "isometric")
    {
        var standardView = await sta.InvokeLoggedAsync(
            nameof(ShowStandardView),
            new { view },
            () =>
            {
                var parsedView = ToolArgumentParsing.ParseStandardView(view);
                docs.ShowStandardView(parsedView);
                return parsedView;
            });
        return $"Switched to {standardView} view.";
    }

    [McpServerTool, Description("Rotate the active SolidWorks view around the global x, y, and z axes. Angles are in degrees.")]
    public async Task<string> RotateView(
        [Description("Rotation around the global X axis in degrees.")] double xDegrees = 0,
        [Description("Rotation around the global Y axis in degrees.")] double yDegrees = 0,
        [Description("Rotation around the global Z axis in degrees.")] double zDegrees = 0)
    {
        await sta.InvokeLoggedAsync(nameof(RotateView), new { xDegrees, yDegrees, zDegrees }, () => docs.RotateView(xDegrees, yDegrees, zDegrees));
        return JsonSerializer.Serialize(new { xDegrees, yDegrees, zDegrees });
    }

    [McpServerTool, Description("Export the current SolidWorks viewport to a PNG file.")]
    public async Task<string> ExportCurrentViewPng(
        [Description("Output PNG file path.")] string outputPath,
        [Description("Image width in pixels.")] int width = 1600,
        [Description("Image height in pixels.")] int height = 900,
        [Description("When true, includes the PNG as base64 data in the tool result.")] bool includeBase64Data = false,
        [Description("When true, zoom to fit the whole model before export. Set false to preserve a prior zoom-to-selection operation.")] bool fitToView = true)
    {
        var result = await sta.InvokeLoggedAsync(nameof(ExportCurrentViewPng), new { outputPath, width, height, includeBase64Data, fitToView }, () => docs.ExportCurrentViewPng(outputPath, width, height, includeBase64Data, fitToView));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Automatically export front, back, left, right, top, and bottom SolidWorks standard views to PNG files. Use this when the model needs six orthographic screenshots to inspect current 3D geometry.")]
    public async Task<string> ExportStandardViewPngSet(
        [Description("Output directory where the six PNG files will be written.")] string outputDirectory,
        [Description("File name prefix. Files are named prefix-front.png, prefix-back.png, prefix-left.png, prefix-right.png, prefix-top.png, and prefix-bottom.png.")] string fileNamePrefix = "view",
        [Description("Image width in pixels.")] int width = 1600,
        [Description("Image height in pixels.")] int height = 900,
        [Description("When true, includes each PNG as base64 data in the tool result. Usually false is better to keep MCP responses small.")] bool includeBase64Data = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ExportStandardViewPngSet),
            new { outputDirectory, fileNamePrefix, width, height, includeBase64Data },
            () => docs.ExportStandardViewPngSet(outputDirectory, fileNamePrefix, width, height, includeBase64Data));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("List all currently open SolidWorks documents.")]
    public async Task<string> ListDocuments()
    {
        var list = await sta.InvokeLoggedAsync(nameof(ListDocuments), null, docs.ListDocuments);
        return JsonSerializer.Serialize(list);
    }

    [McpServerTool, Description("Get the currently active SolidWorks document.")]
    public async Task<string> GetActiveDocument()
    {
        var info = await sta.InvokeLoggedAsync(nameof(GetActiveDocument), null, docs.GetActiveDocument);
        return info is null ? "null" : JsonSerializer.Serialize(info);
    }

    [McpServerTool, Description("Read the active SolidWorks document's configuration names and active configuration without changing the document. Use this to discover engineering states such as 0-degree and 25-degree configurations before any state-specific validation.")]
    public async Task<string> InspectActiveDocumentConfigurations()
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(InspectActiveDocumentConfigurations),
            null,
            docs.InspectActiveDocumentConfigurations);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Activate one configuration in the active SolidWorks document and optionally rebuild it. Returns the previous and effective configuration names so measurement workflows can restore the source state before closing without saving.")]
    public async Task<string> SetActiveDocumentConfiguration(
        [Description("Exact configuration name stored in the active SolidWorks document.")] string configurationName,
        [Description("When true, force a full rebuild after activating the configuration.")] bool rebuild = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SetActiveDocumentConfiguration),
            new { configurationName, rebuild },
            () => docs.SetActiveDocumentConfiguration(configurationName, rebuild));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Silently open a SolidWorks document when needed and read its configuration names without activating or rebuilding it. This avoids UI activation side effects during read-only engineering-state discovery.")]
    public async Task<string> InspectDocumentConfigurations(
        [Description("Full file path to the SolidWorks document.")] string path)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(InspectDocumentConfigurations),
            new { path },
            () => docs.InspectDocumentConfigurations(path));
        return JsonSerializer.Serialize(result);
    }
}
