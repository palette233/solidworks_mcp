using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class EquationTools(StaDispatcher sta, IEquationService equations)
{
    [McpServerTool, Description("Create or update a SolidWorks global variable and immediately bind the currently selected display dimension to it. Use this for natural requests like 'define a global variable R = 100mm and link the selected radius to R'. Exactly one display dimension must already be selected. Prefer this over documentation search when the user is asking to perform the edit now.")]
    public async Task<string> UpsertGlobalVariableAndBindSelectedDimension(
        [Description("Global variable name without surrounding quotes.")] string name,
        [Description("Right-hand-side expression, for example 0.1, 100mm, or \"WIDTH\" / 2.")] string expression,
        [Description("When true, evaluates the equation immediately.")] bool solve = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(UpsertGlobalVariableAndBindSelectedDimension),
            new { name, expression, solve },
            () => equations.UpsertGlobalVariableAndBindSelectedDimension(name, expression, solve));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("List global variables currently defined in the active SolidWorks document's equation manager.")]
    public async Task<string> ListGlobalVariables()
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ListGlobalVariables),
            null,
            equations.ListGlobalVariables);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Read the currently selected SolidWorks display dimension and return the token/name needed for equation binding. Exactly one display dimension must be selected before calling this tool.")]
    public async Task<string> GetSelectedDimensionInfo()
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(GetSelectedDimensionInfo),
            null,
            equations.GetSelectedDimensionInfo);
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Create or update a SolidWorks global variable in the active document's equation manager. Use this when the user explicitly asks to define, add, set, or update a global variable. The expression can be a numeric literal like 0.025, or a larger equation expression accepted by SolidWorks. Prefer this over documentation search when the user is requesting an edit, not asking for API help.")]
    public async Task<string> UpsertGlobalVariable(
        [Description("Global variable name without surrounding quotes.")] string name,
        [Description("Right-hand-side expression, for example 0.025 or \"WIDTH\" / 2.")] string expression,
        [Description("When true, evaluates the equation immediately.")] bool solve = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(UpsertGlobalVariable),
            new { name, expression, solve },
            () => equations.UpsertGlobalVariable(name, expression, solve));
        return JsonSerializer.Serialize(result);
    }

    [McpServerTool, Description("Bind the currently selected SolidWorks display dimension to an existing global variable by creating or updating a dimension equation. Use this when the user asks to link, bind, drive, or associate a selected dimension with a named global variable. Exactly one dimension must be selected before calling this tool. Prefer this over documentation search when the edit can be executed directly.")]
    public async Task<string> BindSelectedDimensionToGlobalVariable(
        [Description("Existing global variable name without surrounding quotes.")] string globalVariableName,
        [Description("When true, evaluates the equation immediately.")] bool solve = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(BindSelectedDimensionToGlobalVariable),
            new { globalVariableName, solve },
            () => equations.BindSelectedDimensionToGlobalVariable(globalVariableName, solve));
        return JsonSerializer.Serialize(result);
    }
}
