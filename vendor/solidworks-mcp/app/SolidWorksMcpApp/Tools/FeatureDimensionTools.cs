using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class FeatureDimensionTools(StaDispatcher sta, IFeatureDimensionService featureDimensions)
{
    [McpServerTool, Description("Ensure the specified feature has a bindable driving dimension, creating a radial or diameter dimension from its owning sketch when needed, then create or update the global variable and bind the best-matching feature dimension by description. Use this for cases like cylinders created from circles that currently have no exposed radius or diameter dimension.")]
    public async Task<string> EnsureFeatureDimensionAndBindGlobalVariable(
        [Description("Exact SolidWorks feature name, for example Boss-Extrude1 or Sketch2.")] string featureName,
        [Description("Global variable name without surrounding quotes.")] string variableName,
        [Description("Right-hand-side expression, for example 100mm or 0.1.")] string expression,
        [Description("Natural-language description of the intended dimension, currently best for radius, diameter, length, width, or height.")] string dimensionDescription,
        [Description("When true, evaluates the equation immediately.")] bool solve = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(EnsureFeatureDimensionAndBindGlobalVariable),
            new { featureName, variableName, expression, dimensionDescription, solve },
            () => featureDimensions.EnsureFeatureDimensionAndBindGlobalVariable(
                featureName,
                variableName,
                expression,
                dimensionDescription,
                solve));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("List bindable dimensions that belong to a named SolidWorks feature. Use this after selecting or identifying a feature when you want the model to inspect candidate dimensions instead of requiring a manual dimension selection.")]
    public async Task<string> ListFeatureDimensions(
        [Description("Exact SolidWorks feature name, for example Boss-Extrude1 or Sketch2.")] string featureName)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ListFeatureDimensions),
            new { featureName },
            () => featureDimensions.ListFeatureDimensions(featureName));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Control square-tube length. If you already found the exact dimension name/token from ListFeatureDimensions, pass it as dimensionName and this tool will update that dimension directly. If dimensionName is omitted or cannot be resolved, the tool falls back to locating the square tube feature's parent-owned 2D/3D length-control sketch, choosing the line segment aligned with the requested global axis (X, Y, or Z), and updating or creating its driving dimension. Prefer dimensionName when available because square-tube length is often controlled by an external parent sketch dimension.")]
    public async Task<string> SetSquareTubeLength(
        [Description("Exact SolidWorks feature name for the square tube, for example Weldment1, Boss-Extrude3, or Structural Member2.")] string featureName,
        [Description("Target axis used only when dimensionName is unknown or cannot be resolved: X, Y, or Z.")] string axis,
        [Description("New tube length expression. Supports values like 1200mm, 1.2m, 120cm, or a bare meter value like 1.2.")] string lengthExpression,
        [Description("Optional exact dimension name/token returned by ListFeatureDimensions, such as D1@3D草图1, FullName, or DisplayDimensionSelectionName. When provided, this dimension is updated directly before trying axis-based fallback.")] string? dimensionName = null)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(SetSquareTubeLength),
            new { featureName, axis, lengthExpression, dimensionName },
            () => featureDimensions.SetSquareTubeLength(
                featureName,
                ToolArgumentParsing.ParseCartesianAxis(axis, nameof(axis)),
                lengthExpression,
                dimensionName));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add a driven reference radius or diameter dimension by selecting a cylindrical face from ListEntities and using SolidWorks' radial/diameter smart dimension behavior. Use this when the user asks to add a reference dimension on a cylinder face, not to drive model geometry.")]
    public async Task<string> AddReferenceCircularDimension(
        [Description("Dimension kind: Radius or Diameter.")] string dimensionKind,
        [Description("Entity type from ListEntities. Currently only Face is supported because the intended workflow selects a cylindrical face.")] string entityType,
        [Description("Zero-based entity index from ListEntities.")] int entityIndex,
        [Description("Optional component name for assembly context. Leave null for part context or top-level.")] string? componentName = null,
        [Description("Dimension placement X coordinate in meters.")] double x = 0.02,
        [Description("Dimension placement Y coordinate in meters.")] double y = 0.02,
        [Description("Dimension placement Z coordinate in meters.")] double z = 0)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddReferenceCircularDimension),
            new { dimensionKind, entityType, entityIndex, componentName, x, y, z },
            () =>
            {
                var kind = ToolArgumentParsing.ParseCircularReferenceDimensionKind(dimensionKind, nameof(dimensionKind));
                var type = ToolArgumentParsing.ParseSelectableEntityType(entityType, nameof(entityType));
                return featureDimensions.AddReferenceCircularDimension(kind, type, entityIndex, componentName, x, y, z);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Add a SolidWorks dimension to selected topology entities from ListEntities. Supports Smart, Distance, Horizontal, Vertical, Radius, Diameter, and Angle kinds. Currently creates reference/display dimensions on model topology; Driving is rejected with guidance because driving dimensions must be created in sketch or feature context.")]
    public async Task<string> AddDimension(
        [Description("Dimension kind: Smart, Distance, Horizontal, Vertical, Radius, Diameter, or Angle. Smart chooses Radius for one face target and Distance for two targets.")] string dimensionKind,
        [Description("Dimension role: Reference or Driving. Currently Reference is supported for model topology dimensions.")] string dimensionRole,
        [Description("First entity type from ListEntities: Face, Edge, or Vertex.")] string firstEntityType,
        [Description("Zero-based first entity index from ListEntities.")] int firstEntityIndex,
        [Description("Optional second entity type from ListEntities for distance/horizontal/vertical/angle dimensions.")] string? secondEntityType = null,
        [Description("Optional zero-based second entity index from ListEntities.")] int? secondEntityIndex = null,
        [Description("Optional component name for the first entity in assembly context. Leave null for part context or top-level.")] string? firstComponentName = null,
        [Description("Optional component name for the second entity in assembly context. Leave null for part context or top-level.")] string? secondComponentName = null,
        [Description("Dimension placement X coordinate in meters.")] double x = 0.02,
        [Description("Dimension placement Y coordinate in meters.")] double y = 0.02,
        [Description("Dimension placement Z coordinate in meters.")] double z = 0)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(AddDimension),
            new
            {
                dimensionKind,
                dimensionRole,
                firstEntityType,
                firstEntityIndex,
                secondEntityType,
                secondEntityIndex,
                firstComponentName,
                secondComponentName,
                x,
                y,
                z,
            },
            () =>
            {
                var kind = ToolArgumentParsing.ParseAddDimensionKind(dimensionKind, nameof(dimensionKind));
                var role = ToolArgumentParsing.ParseAddDimensionRole(dimensionRole, nameof(dimensionRole));
                var firstType = ToolArgumentParsing.ParseSelectableEntityType(firstEntityType, nameof(firstEntityType));
                SelectableEntityType? secondType = string.IsNullOrWhiteSpace(secondEntityType)
                    ? null
                    : ToolArgumentParsing.ParseSelectableEntityType(secondEntityType, nameof(secondEntityType));

                return featureDimensions.AddDimension(
                    kind,
                    role,
                    firstType,
                    firstEntityIndex,
                    secondType,
                    secondEntityIndex,
                    firstComponentName,
                    secondComponentName,
                    x,
                    y,
                    z);
            });
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Create or update a global variable and bind the best-matching dimension of the specified feature based on a natural-language dimension description such as radius, diameter, height, width, or length. Use this when the user has identified a feature and described which dimension should be driven, and you want to avoid manual dimension selection.")]
    public async Task<string> UpsertGlobalVariableAndBindFeatureDimensionByDescription(
        [Description("Exact SolidWorks feature name, for example Boss-Extrude1 or Sketch2.")] string featureName,
        [Description("Global variable name without surrounding quotes.")] string variableName,
        [Description("Right-hand-side expression, for example 100mm or 0.1.")] string expression,
        [Description("Natural-language description of the intended dimension, for example radius, diameter, height, width, or length.")] string dimensionDescription,
        [Description("When true, evaluates the equation immediately.")] bool solve = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(UpsertGlobalVariableAndBindFeatureDimensionByDescription),
            new { featureName, variableName, expression, dimensionDescription, solve },
            () => featureDimensions.UpsertGlobalVariableAndBindFeatureDimensionByDescription(
                featureName,
                variableName,
                expression,
                dimensionDescription,
                solve));
        return JsonSerializer.Serialize(result);
    }
}
