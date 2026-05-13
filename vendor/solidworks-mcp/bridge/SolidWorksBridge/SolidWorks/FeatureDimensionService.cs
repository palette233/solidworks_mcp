using System.Reflection;
using SolidWorks.Interop.sldworks;

namespace SolidWorksBridge.SolidWorks;

public record FeatureDimensionCandidateInfo(
    int Index,
    string FeatureName,
    string FeatureType,
    string DimensionToken,
    string DisplayDimensionSelectionName,
    double? Value,
    string? FullName,
    string HeuristicLabel);

public record FeatureDimensionBindingResult(
    FeatureDimensionCandidateInfo SelectedDimension,
    GlobalVariableInfo GlobalVariable,
    SelectedDimensionBindingInfo Binding,
    string MatchReason);

public interface IFeatureDimensionService
{
    IReadOnlyList<FeatureDimensionCandidateInfo> ListFeatureDimensions(string featureName);
    FeatureDimensionBindingResult UpsertGlobalVariableAndBindFeatureDimensionByDescription(
        string featureName,
        string variableName,
        string expression,
        string dimensionDescription,
        bool solve = true);
    FeatureDimensionBindingResult EnsureFeatureDimensionAndBindGlobalVariable(
        string featureName,
        string variableName,
        string expression,
        string dimensionDescription,
        bool solve = true);
}

public class FeatureDimensionService : IFeatureDimensionService
{
    private readonly ISwConnectionManager _connectionManager;
    private readonly IEquationService _equations;

    public FeatureDimensionService(ISwConnectionManager connectionManager, IEquationService equations)
    {
        _connectionManager = connectionManager ?? throw new ArgumentNullException(nameof(connectionManager));
        _equations = equations ?? throw new ArgumentNullException(nameof(equations));
    }

    public IReadOnlyList<FeatureDimensionCandidateInfo> ListFeatureDimensions(string featureName)
    {
        var feature = FindFeature(featureName);
        var dimensions = EnumerateFeatureDimensions(feature)
            .Select((item, index) => new FeatureDimensionCandidateInfo(
                index,
                feature.Name,
                SafeGetFeatureTypeName(feature) ?? "unknown",
                item.DimensionToken,
                item.DisplayDimensionSelectionName,
                item.Value,
                item.FullName,
                BuildHeuristicLabel(item.DimensionToken, item.FullName)))
            .ToList();

        return dimensions.AsReadOnly();
    }

    public FeatureDimensionBindingResult UpsertGlobalVariableAndBindFeatureDimensionByDescription(
        string featureName,
        string variableName,
        string expression,
        string dimensionDescription,
        bool solve = true)
    {
        if (string.IsNullOrWhiteSpace(dimensionDescription))
        {
            throw new ArgumentException("dimensionDescription must not be empty.", nameof(dimensionDescription));
        }

        var candidates = ListFeatureDimensions(featureName);
        if (candidates.Count == 0)
        {
            throw new InvalidOperationException($"Feature '{featureName}' does not expose any bindable dimensions.");
        }

        var selected = ChooseBestCandidate(candidates, dimensionDescription);
        var globalVariable = _equations.UpsertGlobalVariable(variableName, expression, solve);
        var binding = _equations.BindDimensionTokenToGlobalVariable(selected.DimensionToken, globalVariable.Name, solve);

        return new FeatureDimensionBindingResult(
            selected,
            globalVariable,
            binding,
            $"Matched description '{dimensionDescription}' to '{selected.HeuristicLabel}'.");
    }

    public FeatureDimensionBindingResult EnsureFeatureDimensionAndBindGlobalVariable(
        string featureName,
        string variableName,
        string expression,
        string dimensionDescription,
        bool solve = true)
    {
        var candidates = ListFeatureDimensions(featureName);
        if (candidates.Count == 0)
        {
            TryAddMissingDrivingDimension(featureName, dimensionDescription);
            candidates = ListFeatureDimensions(featureName);
        }

        if (candidates.Count == 0)
        {
            throw new InvalidOperationException(
                $"Feature '{featureName}' still has no bindable dimensions after attempting to add one.");
        }

        return UpsertGlobalVariableAndBindFeatureDimensionByDescription(
            featureName,
            variableName,
            expression,
            dimensionDescription,
            solve);
    }

    private Feature FindFeature(string featureName)
    {
        if (string.IsNullOrWhiteSpace(featureName))
        {
            throw new ArgumentException("featureName must not be empty.", nameof(featureName));
        }

        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");

        for (var feature = doc.FirstFeature() as Feature; feature != null; feature = feature.GetNextFeature() as Feature)
        {
            string? name = SafeGetFeatureName(feature);
            if (string.Equals(name, featureName.Trim(), StringComparison.OrdinalIgnoreCase))
            {
                return feature;
            }
        }

        throw new InvalidOperationException($"Feature '{featureName}' was not found in the active document.");
    }

    private static IEnumerable<(string DimensionToken, string DisplayDimensionSelectionName, string? FullName, double? Value)>
        EnumerateFeatureDimensions(Feature feature)
    {
        var displayDimension = feature.GetFirstDisplayDimension() as DisplayDimension;
        while (displayDimension != null)
        {
            var dimension = displayDimension.GetDimension2(0);
            if (dimension != null)
            {
                string? fullName = TryReadDimensionFullName(dimension);
                string? token = fullName;
                if (string.IsNullOrWhiteSpace(token))
                {
                    token = dimension.GetNameForSelection();
                }

                if (!string.IsNullOrWhiteSpace(token))
                {
                    string displaySelectionName = displayDimension.GetNameForSelection();
                    if (string.IsNullOrWhiteSpace(displaySelectionName))
                    {
                        displaySelectionName = token;
                    }

                    yield return (
                        token.Trim(),
                        displaySelectionName.Trim(),
                        fullName,
                        TryReadDimensionValue(dimension));
                }
            }

            displayDimension = displayDimension.GetNext5();
        }
    }

    private void TryAddMissingDrivingDimension(string featureName, string dimensionDescription)
    {
        var feature = FindFeature(featureName);
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var sketchFeature = ResolveOwningSketchFeature(feature);
        if (sketchFeature == null)
        {
            throw new InvalidOperationException(
                $"Feature '{featureName}' does not expose dimensions and no owning sketch feature was found for automatic dimension creation.");
        }

        bool wantsRadius = IsRadiusLike(dimensionDescription);
        bool wantsDiameter = IsDiameterLike(dimensionDescription);
        bool wantsHorizontal = IsHorizontalLike(dimensionDescription);
        bool wantsVertical = IsVerticalLike(dimensionDescription);
        bool wantsLength = IsLengthLike(dimensionDescription);

        if (!wantsRadius && !wantsDiameter && !wantsHorizontal && !wantsVertical && !wantsLength)
        {
            throw new InvalidOperationException(
                $"Automatic dimension creation currently supports radius, diameter, length, horizontal, vertical, width, and height descriptions. Description was '{dimensionDescription}'.");
        }

        if (!sketchFeature.Select2(false, -1))
        {
            throw new InvalidOperationException($"Could not select sketch feature '{sketchFeature.Name}'.");
        }

        var sketchManager = _connectionManager.SwApp!.SketchManager
            ?? throw new InvalidOperationException("No sketch manager is available.");
        sketchManager.InsertSketch(true);

        try
        {
            var sketch = sketchFeature.GetSpecificFeature2() as ISketch
                ?? throw new InvalidOperationException($"Feature '{sketchFeature.Name}' is not a sketch feature.");
            var segments = (object[]?)sketch.GetSketchSegments() ?? Array.Empty<object>();
            var selectionManager = doc.ISelectionManager
                ?? throw new InvalidOperationException("No selection manager is available.");

            foreach (var rawSegment in segments)
            {
                if (rawSegment is not ISketchSegment segment)
                {
                    continue;
                }

                doc.ClearSelection2(true);
                var selectData = selectionManager.CreateSelectData();
                if (!segment.Select4(false, selectData))
                {
                    continue;
                }

                object? created = TryCreateDimensionForSegment(doc, segment, dimensionDescription);

                if (created is DisplayDimension)
                {
                    doc.ClearSelection2(true);
                    return;
                }

                doc.ClearSelection2(true);
            }
        }
        finally
        {
            doc.ClearSelection2(true);
            sketchManager.InsertSketch(true);
        }

        throw new InvalidOperationException(
            $"Failed to add a driving dimension for sketch feature '{sketchFeature.Name}' using description '{dimensionDescription}'.");
    }

    private static FeatureDimensionCandidateInfo ChooseBestCandidate(
        IReadOnlyList<FeatureDimensionCandidateInfo> candidates,
        string dimensionDescription)
    {
        var description = dimensionDescription.Trim().ToLowerInvariant();
        var scored = candidates
            .Select(candidate => new
            {
                Candidate = candidate,
                Score = ScoreCandidate(candidate, description)
            })
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Candidate.Index)
            .ToList();

        if (scored.Count == 0 || scored[0].Score <= 0)
        {
            throw new InvalidOperationException(
                $"Could not match description '{dimensionDescription}' to any feature dimension. Call ListFeatureDimensions first.");
        }

        return scored[0].Candidate;
    }

    private static int ScoreCandidate(FeatureDimensionCandidateInfo candidate, string description)
    {
        int score = 0;
        string token = candidate.DimensionToken.ToLowerInvariant();
        string label = candidate.HeuristicLabel.ToLowerInvariant();
        string fullName = candidate.FullName?.ToLowerInvariant() ?? string.Empty;

        foreach (var word in description.Split([' ', ',', ';', '/', '\\', '-', '_'], StringSplitOptions.RemoveEmptyEntries))
        {
            if (label.Contains(word))
            {
                score += 5;
            }

            if (fullName.Contains(word))
            {
                score += 4;
            }

            if (token.Contains(word))
            {
                score += 3;
            }
        }

        if (description.Contains("radius") || description.Contains("半径"))
        {
            if (label.Contains("radius") || token.Contains("r@"))
            {
                score += 20;
            }
        }

        if (description.Contains("diameter") || description.Contains("直径"))
        {
            if (label.Contains("diameter") || token.Contains("dia"))
            {
                score += 20;
            }
        }

        if (description.Contains("length") || description.Contains("高度") || description.Contains("长度"))
        {
            if (label.Contains("length") || label.Contains("depth") || label.Contains("height"))
            {
                score += 12;
            }
        }

        if (description.Contains("width") || description.Contains("horizontal") || description.Contains("宽") || description.Contains("水平"))
        {
            if (label.Contains("width") || label.Contains("horizontal"))
            {
                score += 12;
            }
        }

        if (description.Contains("height") || description.Contains("vertical") || description.Contains("高") || description.Contains("垂直"))
        {
            if (label.Contains("height") || label.Contains("vertical"))
            {
                score += 12;
            }
        }

        return score;
    }

    private static string BuildHeuristicLabel(string dimensionToken, string? fullName)
    {
        string source = fullName ?? dimensionToken;
        var lowered = source.ToLowerInvariant();

        if (lowered.Contains("radius") || lowered.Contains("r@"))
        {
            return "radius";
        }

        if (lowered.Contains("diameter") || lowered.Contains("dia"))
        {
            return "diameter";
        }

        if (lowered.Contains("depth"))
        {
            return "depth";
        }

        if (lowered.Contains("height"))
        {
            return "height";
        }

        if (lowered.Contains("length"))
        {
            return "length";
        }

        if (lowered.Contains("horizontal") || lowered.Contains("width"))
        {
            return "width";
        }

        if (lowered.Contains("vertical"))
        {
            return "height";
        }

        if (lowered.Contains("angle"))
        {
            return "angle";
        }

        return "dimension";
    }

    private static bool IsRadiusLike(string description)
    {
        var value = description.Trim().ToLowerInvariant();
        return value.Contains("radius") || value.Contains("半径");
    }

    private static bool IsDiameterLike(string description)
    {
        var value = description.Trim().ToLowerInvariant();
        return value.Contains("diameter") || value.Contains("直径");
    }

    private static bool IsHorizontalLike(string description)
    {
        var value = description.Trim().ToLowerInvariant();
        return value.Contains("width") || value.Contains("horizontal") || value.Contains("宽") || value.Contains("水平");
    }

    private static bool IsVerticalLike(string description)
    {
        var value = description.Trim().ToLowerInvariant();
        return value.Contains("height") || value.Contains("vertical") || value.Contains("高") || value.Contains("竖") || value.Contains("垂直");
    }

    private static bool IsLengthLike(string description)
    {
        var value = description.Trim().ToLowerInvariant();
        return value.Contains("length") || value.Contains("distance") || value.Contains("长度") || value.Contains("距离");
    }

    private static Feature? ResolveOwningSketchFeature(Feature feature)
    {
        if (IsSketchFeature(feature))
        {
            return feature;
        }

        for (var sub = feature.GetFirstSubFeature() as Feature; sub != null; sub = sub.GetNextSubFeature() as Feature)
        {
            if (IsSketchFeature(sub))
            {
                return sub;
            }
        }

        return null;
    }

    private static bool IsSketchFeature(Feature feature)
    {
        string? typeName = SafeGetFeatureTypeName(feature);
        return string.Equals(typeName, "ProfileFeature", StringComparison.OrdinalIgnoreCase)
            || string.Equals(typeName, "3DProfileFeature", StringComparison.OrdinalIgnoreCase);
    }

    private static object? TryCreateDimensionForSegment(IModelDoc2 doc, ISketchSegment segment, string dimensionDescription)
    {
        if (IsDiameterLike(dimensionDescription))
        {
            return doc.AddDiameterDimension2(0.02, 0.02, 0);
        }

        if (IsRadiusLike(dimensionDescription))
        {
            return doc.AddRadialDimension2(0.02, 0.02, 0);
        }

        if (segment is ISketchLine sketchLine)
        {
            if (IsHorizontalLike(dimensionDescription))
            {
                return doc.AddHorizontalDimension2(0.02, 0.02, 0);
            }

            if (IsVerticalLike(dimensionDescription))
            {
                return doc.AddVerticalDimension2(0.02, 0.02, 0);
            }

            if (IsLengthLike(dimensionDescription))
            {
                return doc.AddDimension2(0.02, 0.02, 0);
            }

            if (TryGetLineOrientation(sketchLine, out bool horizontal, out bool vertical))
            {
                if (horizontal)
                {
                    return doc.AddHorizontalDimension2(0.02, 0.02, 0);
                }

                if (vertical)
                {
                    return doc.AddVerticalDimension2(0.02, 0.02, 0);
                }
            }

            return doc.AddDimension2(0.02, 0.02, 0);
        }

        return null;
    }

    private static bool TryGetLineOrientation(ISketchLine line, out bool horizontal, out bool vertical)
    {
        horizontal = false;
        vertical = false;

        try
        {
            var start = line.IGetStartPoint2();
            var end = line.IGetEndPoint2();
            if (start == null || end == null)
            {
                return false;
            }

            double dx = Math.Abs(end.X - start.X);
            double dy = Math.Abs(end.Y - start.Y);
            const double tolerance = 1e-8;
            horizontal = dy <= tolerance && dx > tolerance;
            vertical = dx <= tolerance && dy > tolerance;
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static string? TryReadDimensionFullName(Dimension dimension)
    {
        try
        {
            var runtimeType = ((object)dimension).GetType();
            var fullNameProperty = runtimeType.GetProperty("FullName", BindingFlags.Instance | BindingFlags.Public);
            if (fullNameProperty?.CanRead == true)
            {
                return Convert.ToString(fullNameProperty.GetValue(dimension));
            }
        }
        catch (TargetInvocationException)
        {
        }

        return null;
    }

    private static double? TryReadDimensionValue(Dimension dimension)
    {
        try
        {
            return dimension.SystemValue;
        }
        catch
        {
            return null;
        }
    }

    private static string? SafeGetFeatureName(Feature feature)
    {
        try
        {
            return feature.Name;
        }
        catch
        {
            return null;
        }
    }

    private static string? SafeGetFeatureTypeName(Feature feature)
    {
        try
        {
            return feature.GetTypeName2();
        }
        catch
        {
            return null;
        }
    }
}
