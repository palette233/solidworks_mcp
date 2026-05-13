using System.Reflection;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SwDimension = SolidWorks.Interop.sldworks.Dimension;

namespace SolidWorksBridge.SolidWorks;

public record GlobalVariableInfo(
    string Name,
    string Equation,
    int EquationIndex,
    double? Value,
    bool WasCreated,
    bool WasUpdated);

public record SelectedDimensionBindingInfo(
    string GlobalVariableName,
    string DimensionToken,
    string Equation,
    int EquationIndex,
    bool WasCreated,
    bool WasUpdated);

public record GlobalVariableBindingWorkflowResult(
    GlobalVariableInfo GlobalVariable,
    SelectedDimensionBindingInfo Binding);

public record SelectedDimensionInfo(
    string DimensionToken,
    string DisplayDimensionSelectionName,
    double? Value,
    string? FullName);

public interface IEquationService
{
    GlobalVariableInfo UpsertGlobalVariable(string name, string expression, bool solve = true);
    SelectedDimensionBindingInfo BindSelectedDimensionToGlobalVariable(string globalVariableName, bool solve = true);
    SelectedDimensionBindingInfo BindDimensionTokenToGlobalVariable(string dimensionToken, string globalVariableName, bool solve = true);
    IReadOnlyList<GlobalVariableInfo> ListGlobalVariables();
    SelectedDimensionInfo GetSelectedDimensionInfo();
    GlobalVariableBindingWorkflowResult UpsertGlobalVariableAndBindSelectedDimension(string name, string expression, bool solve = true);
}

public class EquationService : IEquationService
{
    private readonly ISwConnectionManager _connectionManager;

    public EquationService(ISwConnectionManager connectionManager)
    {
        _connectionManager = connectionManager ?? throw new ArgumentNullException(nameof(connectionManager));
    }

    public GlobalVariableInfo UpsertGlobalVariable(string name, string expression, bool solve = true)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException("Global variable name must not be empty.", nameof(name));
        }

        if (string.IsNullOrWhiteSpace(expression))
        {
            throw new ArgumentException("Global variable expression must not be empty.", nameof(expression));
        }

        var doc = GetActiveModel();
        var equationManager = GetEquationManager(doc);
        string normalizedName = name.Trim();
        string normalizedExpression = expression.Trim();
        string equation = BuildGlobalVariableEquation(normalizedName, normalizedExpression);

        int? existingIndex = FindGlobalVariableIndex(equationManager, normalizedName);
        bool wasCreated = false;
        bool wasUpdated = false;
        int finalIndex;

        if (existingIndex.HasValue)
        {
            finalIndex = UpdateEquation(equationManager, existingIndex.Value, equation, solve);
            wasUpdated = true;
        }
        else
        {
            finalIndex = AddEquation(equationManager, equation, solve, preferAllConfigurations: true);
            wasCreated = true;
        }

        doc.EditRebuild3();

        return new GlobalVariableInfo(
            normalizedName,
            ReadEquation(equationManager, finalIndex),
            finalIndex,
            TryReadEquationValue(equationManager, finalIndex),
            wasCreated,
            wasUpdated);
    }

    public SelectedDimensionBindingInfo BindSelectedDimensionToGlobalVariable(string globalVariableName, bool solve = true)
    {
        if (string.IsNullOrWhiteSpace(globalVariableName))
        {
            throw new ArgumentException("Global variable name must not be empty.", nameof(globalVariableName));
        }

        var doc = GetActiveModel();
        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("No selection manager is available.");

        string dimensionToken = ResolveSelectedDimensionToken(selectionManager);
        return BindDimensionTokenToGlobalVariable(dimensionToken, globalVariableName, solve);
    }

    public SelectedDimensionBindingInfo BindDimensionTokenToGlobalVariable(string dimensionToken, string globalVariableName, bool solve = true)
    {
        if (string.IsNullOrWhiteSpace(dimensionToken))
        {
            throw new ArgumentException("dimensionToken must not be empty.", nameof(dimensionToken));
        }

        if (string.IsNullOrWhiteSpace(globalVariableName))
        {
            throw new ArgumentException("Global variable name must not be empty.", nameof(globalVariableName));
        }

        var doc = GetActiveModel();
        var equationManager = GetEquationManager(doc);

        string normalizedToken = dimensionToken.Trim();
        string normalizedName = globalVariableName.Trim();
        string equation = BuildDimensionBindingEquation(normalizedToken, normalizedName);

        int? existingIndex = FindEquationIndexByLeftHandSide(equationManager, normalizedToken);
        bool wasCreated = false;
        bool wasUpdated = false;
        int finalIndex;

        if (existingIndex.HasValue)
        {
            finalIndex = UpdateEquation(equationManager, existingIndex.Value, equation, solve);
            wasUpdated = true;
        }
        else
        {
            finalIndex = AddEquation(equationManager, equation, solve, preferAllConfigurations: false);
            wasCreated = true;
        }

        doc.EditRebuild3();

        return new SelectedDimensionBindingInfo(
            normalizedName,
            normalizedToken,
            ReadEquation(equationManager, finalIndex),
            finalIndex,
            wasCreated,
            wasUpdated);
    }

    public IReadOnlyList<GlobalVariableInfo> ListGlobalVariables()
    {
        var doc = GetActiveModel();
        var equationManager = GetEquationManager(doc);
        var variables = new List<GlobalVariableInfo>();

        for (int index = 0; index < equationManager.GetCount(); index++)
        {
            if (!equationManager.GlobalVariable[index])
            {
                continue;
            }

            string equation = ReadEquation(equationManager, index);
            if (!TryParseLeftHandSideToken(equation, out var name))
            {
                continue;
            }

            variables.Add(new GlobalVariableInfo(
                name,
                equation,
                index,
                TryReadEquationValue(equationManager, index),
                WasCreated: false,
                WasUpdated: false));
        }

        return variables.AsReadOnly();
    }

    public SelectedDimensionInfo GetSelectedDimensionInfo()
    {
        var doc = GetActiveModel();
        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("No selection manager is available.");

        var selection = ResolveSelectedDimensionSelection(selectionManager);
        string? fullName = TryReadDimensionFullName(selection.Dimension);

        return new SelectedDimensionInfo(
            selection.DimensionToken,
            selection.DisplayDimensionSelectionName,
            TryReadDimensionValue(selection.Dimension),
            fullName);
    }

    public GlobalVariableBindingWorkflowResult UpsertGlobalVariableAndBindSelectedDimension(string name, string expression, bool solve = true)
    {
        var globalVariable = UpsertGlobalVariable(name, expression, solve);
        var binding = BindSelectedDimensionToGlobalVariable(globalVariable.Name, solve);
        return new GlobalVariableBindingWorkflowResult(globalVariable, binding);
    }

    private IModelDoc2 GetActiveModel()
    {
        _connectionManager.EnsureConnected();
        return _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
    }

    private static EquationMgr GetEquationManager(IModelDoc2 doc)
    {
        return doc.GetEquationMgr()
            ?? throw new InvalidOperationException("The active document does not expose an equation manager.");
    }

    private static string BuildGlobalVariableEquation(string name, string expression)
        => $"\"{EscapeEquationToken(name)}\" = {expression}";

    private static string BuildDimensionBindingEquation(string dimensionToken, string globalVariableName)
        => $"\"{EscapeEquationToken(dimensionToken)}\" = \"{EscapeEquationToken(globalVariableName)}\"";

    private static string EscapeEquationToken(string value) => value.Replace("\"", "\"\"");

    private static int? FindGlobalVariableIndex(EquationMgr equationManager, string globalVariableName)
    {
        for (int index = 0; index < equationManager.GetCount(); index++)
        {
            if (!equationManager.GlobalVariable[index])
            {
                continue;
            }

            string equation = ReadEquation(equationManager, index);
            if (TryParseLeftHandSideToken(equation, out var token)
                && string.Equals(token, globalVariableName, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }

        return null;
    }

    private static int? FindEquationIndexByLeftHandSide(EquationMgr equationManager, string leftHandSideToken)
    {
        for (int index = 0; index < equationManager.GetCount(); index++)
        {
            string equation = ReadEquation(equationManager, index);
            if (TryParseLeftHandSideToken(equation, out var token)
                && string.Equals(token, leftHandSideToken, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }

        return null;
    }

    private static string ReadEquation(EquationMgr equationManager, int index)
    {
        object? value = InvokeIndexedProperty(equationManager, "Equation", index, setValue: null);
        return Convert.ToString(value) ?? string.Empty;
    }

    private static int UpdateEquation(EquationMgr equationManager, int index, string equation, bool solve)
    {
        int result = equationManager.SetEquationAndConfigurationOption(
            index,
            equation,
            (int)swInConfigurationOpts_e.swAllConfiguration,
            null!);

        if (result < 0)
        {
            InvokeIndexedProperty(equationManager, "Equation", index, equation);
            result = index;
        }

        if (solve)
        {
            equationManager.EvaluateAll();
        }

        return result;
    }

    private static int AddEquation(EquationMgr equationManager, string equation, bool solve, bool preferAllConfigurations)
    {
        int result = -1;
        if (preferAllConfigurations)
        {
            result = equationManager.Add3(
                -1,
                equation,
                solve,
                (int)swInConfigurationOpts_e.swAllConfiguration,
                null!);
        }

        if (result < 0)
        {
            result = equationManager.Add2(-1, equation, solve);
        }

        if (result < 0)
        {
            throw new InvalidOperationException($"SolidWorks failed to add equation: {equation}");
        }

        return result;
    }

    private static double? TryReadEquationValue(EquationMgr equationManager, int index)
    {
        try
        {
            return equationManager.Value[index];
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static string ResolveSelectedDimensionToken(ISelectionMgr selectionManager)
        => ResolveSelectedDimensionSelection(selectionManager).DimensionToken;

    private static (DisplayDimension DisplayDimension, SwDimension Dimension, string DimensionToken, string DisplayDimensionSelectionName)
        ResolveSelectedDimensionSelection(ISelectionMgr selectionManager)
    {
        int selectedCount = selectionManager.GetSelectedObjectCount2(-1);
        if (selectedCount != 1)
        {
            throw new InvalidOperationException(
                $"Exactly one dimension must be selected. Current selection count: {selectedCount}.");
        }

        int selectedType = selectionManager.GetSelectedObjectType3(1, -1);
        if (selectedType != (int)swSelectType_e.swSelDIMENSIONS)
        {
            throw new InvalidOperationException(
                $"The current selection is not a dimension. Selected type: {Enum.GetName(typeof(swSelectType_e), selectedType) ?? selectedType.ToString()}.");
        }

        var displayDimension = selectionManager.GetSelectedObject6(1, -1) as DisplayDimension
            ?? throw new InvalidOperationException("The selected dimension could not be resolved as a display dimension.");

        var dimension = displayDimension.GetDimension2(0)
            ?? throw new InvalidOperationException("The selected display dimension did not resolve to a model dimension.");

        string? token = TryReadDimensionToken(dimension);
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new InvalidOperationException("The selected dimension does not expose a usable equation token.");
        }

        string displaySelectionName = displayDimension.GetNameForSelection();
        if (string.IsNullOrWhiteSpace(displaySelectionName))
        {
            displaySelectionName = token.Trim();
        }

        return (displayDimension, dimension, token.Trim(), displaySelectionName.Trim());
    }

    private static string? TryReadDimensionToken(SwDimension dimension)
    {
        string? fullName = TryReadDimensionFullName(dimension);
        if (!string.IsNullOrWhiteSpace(fullName))
        {
            return fullName;
        }

        try
        {
            var name = dimension.Name;
            if (!string.IsNullOrWhiteSpace(name))
            {
                return name;
            }
        }
        catch (COMException)
        {
        }

        return null;
    }

    private static string? TryReadDimensionFullName(SwDimension dimension)
    {
        try
        {
            var runtimeType = ((object)dimension).GetType();
            var fullNameProperty = runtimeType.GetProperty("FullName", BindingFlags.Instance | BindingFlags.Public);
            if (fullNameProperty?.CanRead == true)
            {
                var fullName = Convert.ToString(fullNameProperty.GetValue(dimension));
                if (!string.IsNullOrWhiteSpace(fullName))
                {
                    return fullName;
                }
            }
        }
        catch (TargetInvocationException)
        {
        }
        catch (COMException)
        {
        }

        try
        {
            var selectionName = dimension.GetNameForSelection();
            if (!string.IsNullOrWhiteSpace(selectionName))
            {
                return selectionName;
            }
        }
        catch (COMException)
        {
        }

        return null;
    }

    private static double? TryReadDimensionValue(SwDimension dimension)
    {
        try
        {
            return dimension.SystemValue;
        }
        catch (COMException)
        {
            return null;
        }
    }

    private static bool TryParseLeftHandSideToken(string equation, out string token)
    {
        token = string.Empty;
        if (string.IsNullOrWhiteSpace(equation))
        {
            return false;
        }

        int startQuote = equation.IndexOf('"');
        if (startQuote < 0)
        {
            return false;
        }

        int endQuote = equation.IndexOf('"', startQuote + 1);
        if (endQuote <= startQuote)
        {
            return false;
        }

        token = equation.Substring(startQuote + 1, endQuote - startQuote - 1).Replace("\"\"", "\"");
        return !string.IsNullOrWhiteSpace(token);
    }

    private static object? InvokeIndexedProperty(object target, string propertyName, int index, string? setValue)
    {
        var args = setValue is null ? new object[] { index } : new object[] { index, setValue };
        return target.GetType().InvokeMember(
            propertyName,
            setValue is null ? BindingFlags.GetProperty : BindingFlags.SetProperty,
            binder: null,
            target,
            args);
    }
}
