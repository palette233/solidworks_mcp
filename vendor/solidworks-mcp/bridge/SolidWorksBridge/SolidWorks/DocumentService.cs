using SolidWorksBridge.SolidWorks;
using SolidWorks.Interop.sldworks;

namespace SolidWorksBridge.SolidWorks;

/// <summary>
/// Type of SolidWorks document. Values match swDocumentTypes_e from the SW API.
/// </summary>
public enum SwDocType
{
    Part = 1,
    Assembly = 2,
    Drawing = 3
}

/// <summary>
/// Lightweight descriptor for an open SolidWorks document.
/// </summary>
public record SwDocumentInfo(string Path, string Title, int Type);

/// <summary>
/// Read-only inventory of the configurations defined by one SolidWorks document.
/// Configuration names are returned exactly as stored by SolidWorks so callers can
/// distinguish engineering states such as "0度" and "25度" without changing the model.
/// </summary>
public record SwDocumentConfigurationInventory(
    string Path,
    string Title,
    string? ActiveConfiguration,
    IReadOnlyList<string> ConfigurationNames,
    int ConfigurationCount);

/// <summary>
/// Result of activating one configuration in the active SolidWorks document.
/// The previous and effective names are included so callers can restore the
/// source document after a read-only engineering-state measurement.
/// </summary>
public record SwDocumentConfigurationSwitchResult(
    bool Success,
    string? PreviousConfiguration,
    string RequestedConfiguration,
    string? ActiveConfiguration,
    bool RebuildRequested,
    bool RebuildSucceeded);

public record SwOpenResult(SwDocumentInfo Document, SwApiDiagnostics Diagnostics);

public record RebuildStateInfo(
    int RawStatus,
    bool NeedsRebuild,
    IReadOnlyList<SwCodeInfo> StatusCodes,
    string Summary);

public record RebuildExecutionResult(
    bool RebuildAttempted,
    bool RebuildSucceeded,
    bool TopOnly,
    RebuildStateInfo StatusBefore,
    RebuildStateInfo StatusAfter);

/// <summary>
/// Standard model orientations supported by SolidWorks.
/// </summary>
public enum SwStandardView
{
    Front,
    Back,
    Left,
    Right,
    Top,
    Bottom,
    Isometric,
    Trimetric,
    Dimetric
}

/// <summary>
/// Save/export result metadata.
/// </summary>
public record SwSaveResult(string SourcePath, string OutputPath, string Format, bool SaveAsCopy, int Errors, int Warnings, SwApiDiagnostics? Diagnostics = null);

/// <summary>
/// Exported view image metadata.
/// </summary>
public record SwImageExportResult(string OutputPath, string MimeType, int Width, int Height, string? Base64Data);

public record SwStandardViewImageExportResult(
    string OutputDirectory,
    string FileNamePrefix,
    int Width,
    int Height,
    IReadOnlyList<SwNamedImageExportResult> Images);

public record SwNamedImageExportResult(
    SwStandardView View,
    string ViewName,
    SwImageExportResult Image);

/// <summary>
/// High-level document operations exposed to the MCP layer.
/// </summary>
public interface IDocumentService
{
    /// <summary>
    /// Create a new document. Uses the SW default template for the given type
    /// when <paramref name="templatePath"/> is null.
    /// </summary>
    SwDocumentInfo NewDocument(SwDocType docType, string? templatePath = null);

    /// <summary>Open an existing document by file path.</summary>
    SwOpenResult OpenDocument(string path);

    /// <summary>Activate an already-open document by its SolidWorks title.</summary>
    SwDocumentInfo ActivateDocumentByTitle(string title);

    /// <summary>Close an open document by file path.</summary>
    void CloseDocument(string path);

    /// <summary>Save an open document by file path.</summary>
    SwSaveResult SaveDocument(string path);

    /// <summary>Get the active document's native rebuild state.</summary>
    RebuildStateInfo GetActiveDocumentRebuildState();

    /// <summary>Force a rebuild of the active document and return before/after rebuild state.</summary>
    RebuildExecutionResult ForceRebuildActiveDocument(bool topOnly = false);

    /// <summary>
    /// Save or export a document to a new path. The output format is inferred from
    /// the file extension, so this supports native SolidWorks files and formats like STEP or STL.
    /// When <paramref name="sourcePath"/> is null, the active document is used.
    /// </summary>
    SwSaveResult SaveDocumentAs(string outputPath, string? sourcePath = null, bool saveAsCopy = true);

    /// <summary>Save one already-open document resolved by its exact SolidWorks title.</summary>
    SwSaveResult SaveDocumentAsByTitle(string outputPath, string sourceTitle, bool saveAsCopy = true);

    /// <summary>Undo the last <paramref name="steps"/> operations on the active document.</summary>
    void Undo(int steps = 1);

    /// <summary>Switch the active document to a standard orientation.</summary>
    void ShowStandardView(SwStandardView view);

    /// <summary>Rotate the active document view around the global x, y, and z axes.</summary>
    void RotateView(double xDegrees = 0, double yDegrees = 0, double zDegrees = 0);

    /// <summary>Export the current active viewport to PNG.</summary>
    SwImageExportResult ExportCurrentViewPng(string outputPath, int width = 1600, int height = 900, bool includeBase64Data = false, bool fitToView = true);

    /// <summary>Export front/back/left/right/top/bottom standard views to PNG files.</summary>
    SwStandardViewImageExportResult ExportStandardViewPngSet(
        string outputDirectory,
        string fileNamePrefix = "view",
        int width = 1600,
        int height = 900,
        bool includeBase64Data = false);

    /// <summary>Return info for all currently open documents.</summary>
    SwDocumentInfo[] ListDocuments();

    /// <summary>Return info for the active document, or null if none is active.</summary>
    SwDocumentInfo? GetActiveDocument();

    /// <summary>Read configuration names and the active configuration from the active document.</summary>
    SwDocumentConfigurationInventory InspectActiveDocumentConfigurations();

    /// <summary>Activate one configuration in the active document and optionally rebuild it.</summary>
    SwDocumentConfigurationSwitchResult SetActiveDocumentConfiguration(
        string configurationName,
        bool rebuild = true);

    /// <summary>
    /// Open one document silently when needed and inspect its configurations without activating or rebuilding it.
    /// </summary>
    SwDocumentConfigurationInventory InspectDocumentConfigurations(string path);
}

/// <summary>
/// Implements <see cref="IDocumentService"/> via <see cref="ISwConnectionManager"/>.
/// </summary>
public class DocumentService : IDocumentService
{
    private readonly ISwConnectionManager _connectionManager;

    public DocumentService(ISwConnectionManager connectionManager)
    {
        _connectionManager = connectionManager
            ?? throw new ArgumentNullException(nameof(connectionManager));
    }

    public SwDocumentInfo NewDocument(SwDocType docType, string? templatePath = null)
    {
        _connectionManager.EnsureConnected();
        var sw = _connectionManager.SwApp!;

        var template = templatePath ?? sw.GetDefaultTemplatePath(docType);

        var doc = sw.NewDoc(template)
            ?? throw new InvalidOperationException(
                $"SolidWorks failed to create a new {docType} document using template: {template}");

        return doc;
    }

    public SwOpenResult OpenDocument(string path)
    {
        _connectionManager.EnsureConnected();
        var result = _connectionManager.SwApp!.OpenDoc(path);
        var activeDocument = _connectionManager.SwApp!.ActivateDoc(path);
        return result with { Document = activeDocument };
    }

    public SwDocumentInfo ActivateDocumentByTitle(string title)
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.ActivateDocByTitle(title);
    }

    public void CloseDocument(string path)
    {
        _connectionManager.EnsureConnected();
        _connectionManager.SwApp!.CloseDoc(path);
    }

    public SwSaveResult SaveDocument(string path)
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.SaveDoc(path);
    }

    public RebuildStateInfo GetActiveDocumentRebuildState()
    {
        _connectionManager.EnsureConnected();

        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var extension = doc.Extension
            ?? throw new InvalidOperationException("No model extension available on the active document.");

        return CreateRebuildStateInfo(extension.NeedsRebuild2);
    }

    public RebuildExecutionResult ForceRebuildActiveDocument(bool topOnly = false)
    {
        _connectionManager.EnsureConnected();

        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var before = GetActiveDocumentRebuildState();
        bool rebuildSucceeded = doc.ForceRebuild3(topOnly);
        var after = GetActiveDocumentRebuildState();

        return new RebuildExecutionResult(
            RebuildAttempted: true,
            RebuildSucceeded: rebuildSucceeded,
            TopOnly: topOnly,
            StatusBefore: before,
            StatusAfter: after);
    }

    public SwSaveResult SaveDocumentAs(string outputPath, string? sourcePath = null, bool saveAsCopy = true)
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.SaveDocAs(outputPath, sourcePath, saveAsCopy);
    }

    public SwSaveResult SaveDocumentAsByTitle(string outputPath, string sourceTitle, bool saveAsCopy = true)
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.SaveDocAsByTitle(outputPath, sourceTitle, saveAsCopy);
    }

    public void Undo(int steps = 1)
    {
        _connectionManager.EnsureConnected();
        _connectionManager.SwApp!.Undo(steps);
    }

    public void ShowStandardView(SwStandardView view)
    {
        _connectionManager.EnsureConnected();
        _connectionManager.SwApp!.ShowStandardView(view);
    }

    public void RotateView(double xDegrees = 0, double yDegrees = 0, double zDegrees = 0)
    {
        _connectionManager.EnsureConnected();
        _connectionManager.SwApp!.RotateView(xDegrees, yDegrees, zDegrees);
    }

    public SwImageExportResult ExportCurrentViewPng(string outputPath, int width = 1600, int height = 900, bool includeBase64Data = false, bool fitToView = true)
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.ExportCurrentViewPng(outputPath, width, height, includeBase64Data, fitToView);
    }

    public SwStandardViewImageExportResult ExportStandardViewPngSet(
        string outputDirectory,
        string fileNamePrefix = "view",
        int width = 1600,
        int height = 900,
        bool includeBase64Data = false)
    {
        if (string.IsNullOrWhiteSpace(outputDirectory))
        {
            throw new ArgumentException("outputDirectory must not be empty.", nameof(outputDirectory));
        }

        if (string.IsNullOrWhiteSpace(fileNamePrefix))
        {
            throw new ArgumentException("fileNamePrefix must not be empty.", nameof(fileNamePrefix));
        }

        _connectionManager.EnsureConnected();
        string normalizedDirectory = Path.GetFullPath(outputDirectory);
        Directory.CreateDirectory(normalizedDirectory);

        var images = new List<SwNamedImageExportResult>();
        foreach (var view in SixOrthographicViews)
        {
            _connectionManager.SwApp!.ShowStandardView(view);
            string viewName = view.ToString().ToLowerInvariant();
            string outputPath = Path.Combine(normalizedDirectory, $"{fileNamePrefix}-{viewName}.png");
            var image = _connectionManager.SwApp!.ExportCurrentViewPng(outputPath, width, height, includeBase64Data);
            images.Add(new SwNamedImageExportResult(view, viewName, image));
        }

        return new SwStandardViewImageExportResult(
            normalizedDirectory,
            fileNamePrefix,
            width,
            height,
            images.AsReadOnly());
    }

    public SwDocumentInfo[] ListDocuments()
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.ListDocs();
    }

    public SwDocumentInfo? GetActiveDocument()
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.GetActiveDoc();
    }

    public SwDocumentConfigurationInventory InspectActiveDocumentConfigurations()
    {
        _connectionManager.EnsureConnected();

        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");

        return CreateConfigurationInventory(doc);
    }

    public SwDocumentConfigurationSwitchResult SetActiveDocumentConfiguration(
        string configurationName,
        bool rebuild = true)
    {
        if (string.IsNullOrWhiteSpace(configurationName))
        {
            throw new ArgumentException("configurationName must not be empty.", nameof(configurationName));
        }

        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        string? previous = null;
        try
        {
            previous = doc.ConfigurationManager?.ActiveConfiguration?.Name;
        }
        catch
        {
            // The switch itself remains useful even if an older document cannot
            // expose the current name before ShowConfiguration2 is called.
        }

        bool switched = doc.ShowConfiguration2(configurationName);
        bool rebuildSucceeded = !rebuild;
        if (switched && rebuild)
        {
            rebuildSucceeded = doc.ForceRebuild3(false);
        }

        string? active = null;
        try
        {
            active = doc.ConfigurationManager?.ActiveConfiguration?.Name;
        }
        catch
        {
            // The boolean SolidWorks API result still reports whether switching
            // succeeded when the effective configuration name is unavailable.
        }

        bool exactActiveMatch = string.Equals(
            active,
            configurationName,
            StringComparison.OrdinalIgnoreCase);
        return new SwDocumentConfigurationSwitchResult(
            // ShowConfiguration2 plus the effective active name define whether the
            // requested engineering state was selected. ForceRebuild3 can return
            // false when SolidWorks has no additional rebuild work; expose that
            // diagnostic separately instead of turning a valid state switch into
            // a false-negative configuration failure.
            Success: exactActiveMatch || (active is null && switched),
            PreviousConfiguration: previous,
            RequestedConfiguration: configurationName,
            ActiveConfiguration: active,
            RebuildRequested: rebuild,
            RebuildSucceeded: rebuildSucceeded);
    }

    public SwDocumentConfigurationInventory InspectDocumentConfigurations(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException("path must not be empty.", nameof(path));
        }

        _connectionManager.EnsureConnected();
        string normalizedPath = Path.GetFullPath(path);
        var sw = _connectionManager.SwApp!;
        var doc = sw.GetOpenModelDocument(normalizedPath);
        if (doc is null)
        {
            _ = sw.OpenDoc(normalizedPath);
            doc = sw.GetOpenModelDocument(normalizedPath)
                ?? throw new InvalidOperationException(
                    $"SolidWorks opened '{normalizedPath}' but did not expose its model document.");
        }

        return CreateConfigurationInventory(doc);
    }

    private static SwDocumentConfigurationInventory CreateConfigurationInventory(IModelDoc2 doc)
    {

        var configurationNames = new List<string>();
        object? rawNames = doc.GetConfigurationNames();
        if (rawNames is object[] values)
        {
            configurationNames.AddRange(values
                .Select(value => value?.ToString())
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Select(value => value!));
        }
        else if (rawNames is string[] stringValues)
        {
            configurationNames.AddRange(stringValues.Where(value => !string.IsNullOrWhiteSpace(value)));
        }

        string? activeConfiguration = null;
        try
        {
            activeConfiguration = doc.ConfigurationManager?.ActiveConfiguration?.Name;
        }
        catch
        {
            // Configuration enumeration is still useful even when an older or
            // partially loaded document cannot expose ActiveConfiguration.
        }

        return new SwDocumentConfigurationInventory(
            Path: doc.GetPathName() ?? string.Empty,
            Title: doc.GetTitle() ?? string.Empty,
            ActiveConfiguration: activeConfiguration,
            ConfigurationNames: configurationNames.AsReadOnly(),
            ConfigurationCount: configurationNames.Count);
    }

    private static RebuildStateInfo CreateRebuildStateInfo(int rawStatus)
    {
        var statusCodes = SolidWorksApiErrorFactory.CreateModelRebuildStatusCodes(rawStatus);
        string summary = string.Join("; ", statusCodes.Select(code => code.Description));
        return new RebuildStateInfo(
            RawStatus: rawStatus,
            NeedsRebuild: rawStatus != 0,
            StatusCodes: statusCodes,
            Summary: summary);
    }

    private static readonly SwStandardView[] SixOrthographicViews =
    [
        SwStandardView.Front,
        SwStandardView.Back,
        SwStandardView.Left,
        SwStandardView.Right,
        SwStandardView.Top,
        SwStandardView.Bottom,
    ];
}
