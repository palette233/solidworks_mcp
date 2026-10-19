using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class AssemblyEntityAnnotationTools(StaDispatcher sta, IAssemblyEntityAnnotationService annotations)
{
    [McpServerTool, Description("Build a reusable candidate target index for the active assembly without exporting screenshots. Traverses the active assembly plus loaded child components once and writes target-index.json so later capture calls can resolve targets by sourceIndex or targetId without re-enumerating every feature.")]
    public async Task<string> BuildActiveAssemblyEntityAnnotationTargetIndex(
        [Description("Output directory for target-index.json.")] string outputDirectory,
        [Description("Include component instance targets.")] bool includeComponents = true,
        [Description("Include active assembly and loaded child feature targets.")] bool includeFeatures = true,
        [Description("Include solid body targets when the body list is available from component documents.")] bool includeBodies = true,
        [Description("When true, only keeps targets that have a valid FeatureTypeName and filters ProfileFeature/OneBend. Defaults to true for feature annotation datasets.")] bool requireFeatureTypeName = true,
        [Description("When true, rebuilds target-index.json even if it already exists.")] bool overwrite = false)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(BuildActiveAssemblyEntityAnnotationTargetIndex),
            new { outputDirectory, includeComponents, includeFeatures, includeBodies, requireFeatureTypeName, overwrite },
            () => annotations.BuildActiveAssemblyEntityAnnotationTargetIndex(
                outputDirectory,
                includeComponents,
                includeFeatures,
                includeBodies,
                requireFeatureTypeName,
                overwrite));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Capture one or more assembly entity annotation targets from an existing target-index.json. Prefer sourceIndex or targetId for single-target capture; this avoids rebuilding the full candidate target list in every batch.")]
    public async Task<string> CaptureActiveAssemblyEntityAnnotationTargetsFromIndex(
        [Description("Output directory containing target-index.json and receiving manifest.json plus per-entity front/top/right PNG files.")] string outputDirectory,
        [Description("Image width in pixels.")] int width = 1280,
        [Description("Image height in pixels.")] int height = 720,
        [Description("Zero-based target offset in target-index.json. Ignored when targetId or sourceIndex is supplied.")] int startIndex = 0,
        [Description("Maximum targets to capture from the index. Use 1 for the most stable long-running capture.")] int maxTargets = 1,
        [Description("Optional stable targetId from target-index.json. When supplied, captures that single target.")] string? targetId = null,
        [Description("Optional zero-based SourceIndex from target-index.json. When supplied, captures that single source target.")] int? sourceIndex = null,
        [Description("When true, reads an existing manifest.json and skips targets already captured in it.")] bool skipExistingTargets = true,
        [Description("When true, updates manifest.json after every target so timed-out requests still preserve progress.")] bool writeManifestAfterEachTarget = true,
        [Description("Maximum wall-clock seconds this tool should spend capturing before returning a partial manifest normally. 0 disables the internal budget, but the MCP client may still enforce its own request timeout.")] int maxDurationSeconds = 45,
        [Description("When true, switches capture views to a clean hidden-lines-removed display and disables perspective/RealView where possible. Defaults to false so SolidWorks shading and target color override remain visible.")] bool useCleanDisplayMode = false,
        [Description("Extra zoom-out padding applied before selecting the target and exporting PNG. Defaults to 1.35 to prioritize fitting the whole model in view.")] double capturePaddingFactor = 1.35)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(CaptureActiveAssemblyEntityAnnotationTargetsFromIndex),
            new { outputDirectory, width, height, startIndex, maxTargets, targetId, sourceIndex, skipExistingTargets, writeManifestAfterEachTarget, maxDurationSeconds, useCleanDisplayMode, capturePaddingFactor },
            () => annotations.CaptureActiveAssemblyEntityAnnotationTargetsFromIndex(
                outputDirectory,
                width,
                height,
                startIndex,
                maxTargets,
                targetId,
                sourceIndex,
                skipExistingTargets,
                writeManifestAfterEachTarget,
                maxDurationSeconds,
                useCleanDisplayMode,
                capturePaddingFactor));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Capture an entity-level annotation dataset for the active assembly. Traverses active assembly features plus child component instances, child feature trees, and solid bodies when available; highlights each target; exports front/top/right PNG views; and writes a manifest.json with stable target IDs and ownership paths.")]
    public async Task<string> CaptureActiveAssemblyEntityAnnotationSet(
        [Description("Output directory for manifest.json and per-entity front/top/right PNG files.")] string outputDirectory,
        [Description("Image width in pixels.")] int width = 1280,
        [Description("Image height in pixels.")] int height = 720,
        [Description("Include component instance targets.")] bool includeComponents = true,
        [Description("Include active assembly and loaded child feature targets.")] bool includeFeatures = true,
        [Description("Include solid body targets when the body list is available from component documents.")] bool includeBodies = true,
        [Description("When true, only keeps targets that have a valid FeatureTypeName and filters ProfileFeature/OneBend. Defaults to true for feature annotation datasets.")] bool requireFeatureTypeName = true,
        [Description("Maximum targets to capture. 0 means no limit; use a small number for a dry run or batch.")] int maxTargets = 0,
        [Description("Zero-based target offset before maxTargets is applied. Use this to batch large assemblies: 0, 50, 100, ...")] int startIndex = 0,
        [Description("When true, reads an existing manifest.json and skips targets already captured in it.")] bool skipExistingTargets = true,
        [Description("When true, updates manifest.json after every target so timed-out requests still preserve progress.")] bool writeManifestAfterEachTarget = true,
        [Description("Maximum wall-clock seconds this tool should spend capturing before returning a partial manifest normally. 0 disables the internal budget, but the MCP client may still enforce its own request timeout.")] int maxDurationSeconds = 45,
        [Description("When true, switches capture views to a clean hidden-lines-removed display and disables perspective/RealView where possible. Defaults to false so SolidWorks shading and selection highlight remain visible.")] bool useCleanDisplayMode = false,
        [Description("Extra zoom-out padding applied before selecting the target and exporting PNG. Defaults to 1.35 to prioritize fitting the whole model in view.")] double capturePaddingFactor = 1.35)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(CaptureActiveAssemblyEntityAnnotationSet),
            new { outputDirectory, width, height, includeComponents, includeFeatures, includeBodies, requireFeatureTypeName, maxTargets, startIndex, skipExistingTargets, writeManifestAfterEachTarget, maxDurationSeconds, useCleanDisplayMode, capturePaddingFactor },
            () => annotations.CaptureActiveAssemblyEntityAnnotationSet(
                outputDirectory,
                width,
                height,
                includeComponents,
                includeFeatures,
                includeBodies,
                requireFeatureTypeName,
                maxTargets,
                startIndex,
                skipExistingTargets,
                writeManifestAfterEachTarget,
                maxDurationSeconds,
                useCleanDisplayMode,
                capturePaddingFactor));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Call an OpenAI-compatible Qwen vision endpoint to classify each captured assembly entity target as directly related to overall X/Y/Z assembly dimensions. Requires DASHSCOPE_API_KEY or QWEN_API_KEY in the SolidWorksMcpApp environment. Writes dimension-annotations.json next to the manifest by default.")]
    public async Task<string> AnnotateAssemblyEntityCaptureSetWithQwen(
        [Description("Path to the manifest.json produced by CaptureActiveAssemblyEntityAnnotationSet.")] string manifestPath,
        [Description("Optional output JSON path. Defaults to dimension-annotations.json next to the manifest.")] string? outputPath = null,
        [Description("Qwen vision model name. Defaults to SOLIDWORKS_ENTITY_ANNOTATION_QWEN_MODEL, QWEN_VISION_MODEL, or qwen3.6-flash.")] string? model = null,
        [Description("OpenAI-compatible API base URL or /chat/completions endpoint. Defaults to DASHSCOPE_BASE_URL, QWEN_BASE_URL, or DashScope compatible mode.")] string? baseUrl = null,
        [Description("Maximum targets to annotate in this call. 0 means all pending targets.")] int maxTargets = 0,
        [Description("When true, discards previous annotations at outputPath and recomputes requested targets.")] bool overwrite = false,
        [Description("HTTP timeout per request in seconds.")] int timeoutSeconds = 90)
    {
        var result = await annotations.AnnotateCaptureSetWithQwenAsync(
            manifestPath,
            outputPath,
            model,
            baseUrl,
            maxTargets,
            overwrite,
            timeoutSeconds);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Import external vision-model dimension annotations for a captured assembly entity manifest. Use this when Qwen is called outside the MCP process. Accepts either a JSON string or a file path containing an array/object of annotations and writes the normalized dimension-annotations.json index.")]
    public Task<string> ImportAssemblyEntityDimensionAnnotations(
        [Description("Path to the manifest.json produced by CaptureActiveAssemblyEntityAnnotationSet.")] string manifestPath,
        [Description("Annotation JSON string or path to a JSON file. Each entry should include targetId plus x/y/z related flags, descriptions, and identifiers.")] string annotationJsonOrFilePath,
        [Description("Optional output JSON path. Defaults to dimension-annotations.json next to the manifest.")] string? outputPath = null)
    {
        var result = annotations.ImportAssemblyDimensionAnnotations(manifestPath, annotationJsonOrFilePath, outputPath);
        return Task.FromResult(JsonSerializer.Serialize(result));
    }

    [McpServerTool, Description("Query an assembly entity dimension annotation index to find targets related to an overall X, Y, or Z size change. Use this before editing an assembly based on a user request like 'increase width', 'change height', or 'adjust overall length'.")]
    public Task<string> QueryAssemblyEntityDimensionAnnotations(
        [Description("Path to dimension-annotations.json produced by Qwen annotation or import.")] string annotationPath,
        [Description("Axis to query: x, y, z, all, or omitted.")] string? axis = null,
        [Description("Optional natural language or identifier query such as width, height, bracket, outer face, or component name.")] string? query = null,
        [Description("When true, only returns targets marked related on the requested axis.")] bool onlyRelated = true,
        [Description("Maximum number of matches to return.")] int maxResults = 50)
    {
        var result = annotations.QueryAssemblyDimensionAnnotations(annotationPath, axis, query, onlyRelated, maxResults);
        return Task.FromResult(JsonSerializer.Serialize(result));
    }

    [McpServerTool, Description("Query manifest.json for vision-added StructualInfo/StructuralInfo marks. Use this before CAD edits when the user asks to change the whole assembly/part height or length but does not name the exact component or feature.")]
    public Task<string> QueryAssemblyStructuralComponentTargets(
        [Description("Path to manifest.json containing target StructualInfo objects. Defaults to C:\\temp\\sw-entity-annotations-full\\manifest.json.")] string manifestPath = @"C:\temp\sw-entity-annotations-full\manifest.json",
        [Description("Structural type to find: height or length. If omitted, the tool tries to infer it from query.")] string? type = null,
        [Description("Optional user request or search text, such as '整体高度增高100mm' or 'increase overall length'.")] string? query = null,
        [Description("Maximum number of structural target matches to return.")] int maxResults = 20)
    {
        var result = annotations.QueryAssemblyStructuralComponentTargets(manifestPath, type, query, maxResults);
        return Task.FromResult(JsonSerializer.Serialize(result));
    }

    [McpServerTool, Description("Highlight a previously captured assembly entity target by targetId using either the capture manifest or dimension annotation file. Use this after querying annotations to locate the entity in the active SolidWorks assembly.")]
    public async Task<string> HighlightAssemblyEntityAnnotationTarget(
        [Description("Path to manifest.json or dimension-annotations.json.")] string manifestOrAnnotationPath,
        [Description("Stable targetId returned by capture/query tools.")] string targetId)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(HighlightAssemblyEntityAnnotationTarget),
            new { manifestOrAnnotationPath, targetId },
            () => annotations.HighlightAssemblyEntityAnnotationTarget(manifestOrAnnotationPath, targetId));
        return JsonSerializer.Serialize(result);
    }
}
