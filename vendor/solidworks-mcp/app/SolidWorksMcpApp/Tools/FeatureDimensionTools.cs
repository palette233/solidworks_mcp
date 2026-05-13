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
