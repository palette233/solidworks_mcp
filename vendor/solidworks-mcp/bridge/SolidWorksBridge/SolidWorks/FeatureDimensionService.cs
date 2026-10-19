using System.Reflection;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

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

public enum CartesianAxis
{
    X,
    Y,
    Z,
}

public record SquareTubeLengthUpdateResult(
    string FeatureName,
    string SketchFeatureName,
    string SketchType,
    CartesianAxis Axis,
    string UnitExpression,
    double NewLengthMeters,
    double? PreviousLengthMeters,
    double? UpdatedLengthMeters,
    double SegmentLengthMeters,
    double DirectionAlignment,
    bool CreatedDrivingDimension,
    string DisplayDimensionSelectionName,
    string? DimensionToken,
    string Message);

public enum CircularReferenceDimensionKind
{
    Radius,
    Diameter,
}

public enum AddDimensionKind
{
    Smart,
    Distance,
    Horizontal,
    Vertical,
    Radius,
    Diameter,
    Angle,
}

public enum AddDimensionRole
{
    Reference,
    Driving,
}

public record DimensionTargetInfo(
    SelectableEntityType EntityType,
    int EntityIndex,
    string? ComponentName);

public record AddDimensionResult(
    AddDimensionKind DimensionKind,
    AddDimensionRole DimensionRole,
    DimensionTargetInfo FirstTarget,
    DimensionTargetInfo? SecondTarget,
    double X,
    double Y,
    double Z,
    string DisplayDimensionSelectionName,
    string? DimensionToken,
    double? Value,
    string Message);

public record ReferenceCircularDimensionResult(
    CircularReferenceDimensionKind DimensionKind,
    SelectableEntityType EntityType,
    int EntityIndex,
    string? ComponentName,
    double X,
    double Y,
    double Z,
    string DisplayDimensionSelectionName,
    string? DimensionToken,
    double? Value,
    string Message);

internal sealed record SquareTubeLengthSketchResolution(
    Feature SketchFeature,
    FeatureDimensionService.AxisSegmentCandidate Segment,
    int Score,
    string Reason);

internal sealed record NamedSquareTubeDimensionResolution(
    Feature? SketchFeature,
    DisplayDimension? DisplayDimension,
    Dimension Dimension,
    int Score);

public interface IFeatureDimensionService
{
    IReadOnlyList<FeatureDimensionCandidateInfo> ListFeatureDimensions(string featureName);
    SquareTubeLengthUpdateResult SetSquareTubeLength(string featureName, CartesianAxis axis, string lengthExpression, string? dimensionName = null);
    AddDimensionResult AddDimension(
        AddDimensionKind dimensionKind,
        AddDimensionRole dimensionRole,
        SelectableEntityType firstEntityType,
        int firstEntityIndex,
        SelectableEntityType? secondEntityType = null,
        int? secondEntityIndex = null,
        string? firstComponentName = null,
        string? secondComponentName = null,
        double x = 0.02,
        double y = 0.02,
        double z = 0);
    ReferenceCircularDimensionResult AddReferenceCircularDimension(
        CircularReferenceDimensionKind dimensionKind,
        SelectableEntityType entityType,
        int entityIndex,
        string? componentName = null,
        double x = 0.02,
        double y = 0.02,
        double z = 0);
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
        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var feature = FindFeature(featureName);
        var previousDisplayFeatureDimensions = TryGetDisplayFeatureDimensions(doc);

        try
        {
            TrySetDisplayFeatureDimensions(doc, true);

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
        finally
        {
            if (previousDisplayFeatureDimensions.HasValue)
            {
                TrySetDisplayFeatureDimensions(doc, previousDisplayFeatureDimensions.Value);
            }
        }
    }

    public SquareTubeLengthUpdateResult SetSquareTubeLength(
        string featureName,
        CartesianAxis axis,
        string lengthExpression,
        string? dimensionName = null)
    {
        if (string.IsNullOrWhiteSpace(lengthExpression))
        {
            throw new ArgumentException("lengthExpression must not be empty.", nameof(lengthExpression));
        }

        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var feature = FindFeature(featureName);
        double newLengthMeters = ParseLengthExpressionToMeters(lengthExpression);

        if (!string.IsNullOrWhiteSpace(dimensionName)
            && TryResolveSquareTubeDimensionByName(doc, feature, dimensionName, out var namedResolution))
        {
            return UpdateSquareTubeNamedDimension(
                doc,
                feature,
                namedResolution,
                axis,
                lengthExpression,
                newLengthMeters);
        }

        var sketchResolution = ResolveSquareTubeLengthControllingSketch(feature, axis, doc)
            ?? throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(dimensionName)
                    ? $"Feature '{featureName}' does not expose a parent-owned 2D or 3D length-control sketch with a line segment aligned to axis {axis}."
                    : $"Dimension '{dimensionName}' was not found in the square-tube parent sketch scope, and feature '{featureName}' does not expose a fallback length-control sketch with a line segment aligned to axis {axis}.");
        var sketchFeature = sketchResolution.SketchFeature;
        var sketch = sketchFeature.GetSpecificFeature2() as ISketch
            ?? throw new InvalidOperationException($"Feature '{sketchFeature.Name}' is not a sketch feature.");

        var targetSegment = sketchResolution.Segment;

        bool createdDrivingDimension = false;
        DisplayDimension displayDimension;
        Dimension dimension;

        if (!sketchFeature.Select2(false, -1))
        {
            throw new InvalidOperationException($"Could not select sketch feature '{sketchFeature.Name}'.");
        }

        var sketchManager = _connectionManager.SwApp!.SketchManager
            ?? throw new InvalidOperationException("No sketch manager is available.");
        sketchManager.InsertSketch(true);

        try
        {
            doc.ClearSelection2(true);
            var selectionManager = doc.ISelectionManager
                ?? throw new InvalidOperationException("No selection manager is available.");
            var selectData = selectionManager.CreateSelectData()
                ?? throw new InvalidOperationException("Could not create selection data.");

            if (!targetSegment.Segment.Select4(false, selectData))
            {
                throw new InvalidOperationException(
                    $"Failed to select the sketch segment aligned with axis {axis} in sketch '{sketchFeature.Name}'.");
            }

            var resolved = TryResolveExistingDisplayDimension(sketchFeature, targetSegment, axis);
            if (resolved == null)
            {
                object? created = CreateDrivingDimensionForSegment(doc, targetSegment.Segment, axis, targetSegment);
                displayDimension = created as DisplayDimension
                    ?? throw new InvalidOperationException(
                        $"SolidWorks did not create a driving dimension for the selected axis-{axis} sketch segment.");
                dimension = displayDimension.GetDimension2(0)
                    ?? throw new InvalidOperationException("The created display dimension did not resolve to a model dimension.");
                createdDrivingDimension = true;
            }
            else
            {
                displayDimension = resolved.Value.DisplayDimension;
                dimension = resolved.Value.Dimension;
            }

            if (dimension.DrivenState == (int)swDimensionDrivenState_e.swDimensionDriven)
            {
                dimension.DrivenState = (int)swDimensionDrivenState_e.swDimensionDriving;
            }

            double? previousLength = TryReadDimensionValue(dimension);
            SetDimensionSystemValue(dimension, newLengthMeters);
            doc.EditRebuild3();

            string displaySelectionName = displayDimension.GetNameForSelection();
            if (string.IsNullOrWhiteSpace(displaySelectionName))
            {
                displaySelectionName = TryReadDimensionFullName(dimension)
                    ?? dimension.GetNameForSelection()
                    ?? string.Empty;
            }

            string? token = TryReadDimensionFullName(dimension) ?? dimension.GetNameForSelection();
            double? updatedLength = TryReadDimensionValue(dimension);

            return new SquareTubeLengthUpdateResult(
                feature.Name,
                sketchFeature.Name,
                SafeGetFeatureTypeName(sketchFeature) ?? "unknown",
                axis,
                lengthExpression.Trim(),
                newLengthMeters,
                previousLength,
                updatedLength,
                targetSegment.LengthMeters,
                targetSegment.AlignmentScore,
                createdDrivingDimension,
                displaySelectionName.Trim(),
                string.IsNullOrWhiteSpace(token) ? null : token.Trim(),
                createdDrivingDimension
                    ? $"Created a new driving dimension on sketch '{sketchFeature.Name}' and updated the square-tube length."
                    : $"Updated the existing driving dimension on sketch '{sketchFeature.Name}'.");
        }
        finally
        {
            doc.ClearSelection2(true);
            sketchManager.InsertSketch(true);
        }
    }

    public ReferenceCircularDimensionResult AddReferenceCircularDimension(
        CircularReferenceDimensionKind dimensionKind,
        SelectableEntityType entityType,
        int entityIndex,
        string? componentName = null,
        double x = 0.02,
        double y = 0.02,
        double z = 0)
    {
        var result = AddDimension(
            dimensionKind == CircularReferenceDimensionKind.Diameter
                ? AddDimensionKind.Diameter
                : AddDimensionKind.Radius,
            AddDimensionRole.Reference,
            entityType,
            entityIndex,
            firstComponentName: componentName,
            x: x,
            y: y,
            z: z);

        return new ReferenceCircularDimensionResult(
            dimensionKind,
            result.FirstTarget.EntityType,
            result.FirstTarget.EntityIndex,
            result.FirstTarget.ComponentName,
            result.X,
            result.Y,
            result.Z,
            result.DisplayDimensionSelectionName,
            result.DimensionToken,
            result.Value,
            result.Message);
    }

    public AddDimensionResult AddDimension(
        AddDimensionKind dimensionKind,
        AddDimensionRole dimensionRole,
        SelectableEntityType firstEntityType,
        int firstEntityIndex,
        SelectableEntityType? secondEntityType = null,
        int? secondEntityIndex = null,
        string? firstComponentName = null,
        string? secondComponentName = null,
        double x = 0.02,
        double y = 0.02,
        double z = 0)
    {
        if (dimensionRole == AddDimensionRole.Driving)
        {
            throw new InvalidOperationException(
                "AddDimension currently creates SolidWorks reference/display dimensions on selected topology. Use sketch dimension tools or EnsureFeatureDimensionAndBindGlobalVariable for driving dimensions.");
        }

        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");
        var selectionManager = doc.ISelectionManager
            ?? throw new InvalidOperationException("No selection manager is available.");

        var first = ResolveTopologyEntity(doc, firstEntityType, firstEntityIndex, firstComponentName);
        TopologyEntityCandidate? second = null;
        if (secondEntityType.HasValue || secondEntityIndex.HasValue)
        {
            if (!secondEntityType.HasValue || !secondEntityIndex.HasValue)
            {
                throw new ArgumentException("Both secondEntityType and secondEntityIndex are required when adding a two-target dimension.");
            }

            second = ResolveTopologyEntity(doc, secondEntityType.Value, secondEntityIndex.Value, secondComponentName);
        }

        var resolvedKind = ResolveDimensionKind(dimensionKind, first, second);
        ValidateDimensionTargets(resolvedKind, first, second);

        doc.ClearSelection2(true);
        try
        {
            var selectData = selectionManager.CreateSelectData()
                ?? throw new InvalidOperationException("Could not create selection data.");

            if (!first.Entity.Select4(false, selectData))
            {
                throw new InvalidOperationException($"Failed to select {firstEntityType} at index {firstEntityIndex}.");
            }

            if (second != null && !second.Entity.Select4(true, selectData))
            {
                throw new InvalidOperationException($"Failed to select {second.EntityType} at index {second.Index}.");
            }

            object? rawDimension = CreateDimension(doc, resolvedKind, x, y, z);

            var displayDimension = rawDimension as DisplayDimension
                ?? throw new InvalidOperationException(
                    $"SolidWorks did not create a {resolvedKind.ToString().ToLowerInvariant()} dimension from the selected entities.");

            var dimension = displayDimension.GetDimension2(0);
            string displaySelectionName = displayDimension.GetNameForSelection();
            if (string.IsNullOrWhiteSpace(displaySelectionName))
            {
                displaySelectionName = TryReadDimensionFullName(dimension)
                    ?? dimension?.GetNameForSelection()
                    ?? string.Empty;
            }

            string? token = dimension == null
                ? null
                : TryReadDimensionFullName(dimension) ?? dimension.GetNameForSelection();

            return new AddDimensionResult(
                resolvedKind,
                dimensionRole,
                ToDimensionTargetInfo(first),
                second == null ? null : ToDimensionTargetInfo(second),
                x,
                y,
                z,
                displaySelectionName.Trim(),
                string.IsNullOrWhiteSpace(token) ? null : token.Trim(),
                dimension == null ? null : TryReadDimensionValue(dimension),
                $"Added {dimensionRole.ToString().ToLowerInvariant()} {resolvedKind.ToString().ToLowerInvariant()} dimension.");
        }
        finally
        {
            doc.ClearSelection2(true);
        }
    }

    private static AddDimensionKind ResolveDimensionKind(
        AddDimensionKind dimensionKind,
        TopologyEntityCandidate first,
        TopologyEntityCandidate? second)
    {
        if (dimensionKind != AddDimensionKind.Smart)
        {
            return dimensionKind;
        }

        return second == null && first.EntityType == SelectableEntityType.Face
            ? AddDimensionKind.Radius
            : AddDimensionKind.Distance;
    }

    private static void ValidateDimensionTargets(
        AddDimensionKind dimensionKind,
        TopologyEntityCandidate first,
        TopologyEntityCandidate? second)
    {
        if (dimensionKind is AddDimensionKind.Radius or AddDimensionKind.Diameter)
        {
            if (second != null)
            {
                throw new ArgumentException($"{dimensionKind} dimensions require exactly one target.");
            }

            if (first.EntityType != SelectableEntityType.Face && first.EntityType != SelectableEntityType.Edge)
            {
                throw new ArgumentException($"{dimensionKind} dimensions require a circular/cylindrical face or circular edge target.");
            }

            return;
        }

        if (dimensionKind == AddDimensionKind.Angle && second == null)
        {
            throw new ArgumentException("Angle dimensions require two edge or line-like targets.");
        }

        if (dimensionKind is AddDimensionKind.Distance or AddDimensionKind.Horizontal or AddDimensionKind.Vertical or AddDimensionKind.Angle)
        {
            return;
        }

        throw new ArgumentOutOfRangeException(nameof(dimensionKind), dimensionKind, "Unsupported dimension kind.");
    }

    private static object? CreateDimension(IModelDoc2 doc, AddDimensionKind dimensionKind, double x, double y, double z)
        => dimensionKind switch
        {
            AddDimensionKind.Radius => doc.AddRadialDimension2(x, y, z),
            AddDimensionKind.Diameter => doc.AddDiameterDimension2(x, y, z),
            AddDimensionKind.Horizontal => doc.AddHorizontalDimension2(x, y, z),
            AddDimensionKind.Vertical => doc.AddVerticalDimension2(x, y, z),
            AddDimensionKind.Distance or AddDimensionKind.Angle => doc.AddDimension2(x, y, z),
            _ => throw new ArgumentOutOfRangeException(nameof(dimensionKind), dimensionKind, "Unsupported dimension kind.")
        };

    private static DimensionTargetInfo ToDimensionTargetInfo(TopologyEntityCandidate candidate)
        => new(candidate.EntityType, candidate.Index, candidate.ComponentName);

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

    private static TopologyEntityCandidate ResolveTopologyEntity(
        IModelDoc2 doc,
        SelectableEntityType entityType,
        int index,
        string? componentName)
    {
        var candidate = EnumerateTopologyEntities(doc, entityType, componentName)
            .FirstOrDefault(item => item.Index == index);

        if (candidate == null)
        {
            string scope = string.IsNullOrWhiteSpace(componentName)
                ? string.Empty
                : $" for component '{componentName}'";
            throw new InvalidOperationException($"Could not find {entityType} at index {index}{scope}.");
        }

        return candidate;
    }

    private sealed record TopologyEntityCandidate(
        int Index,
        IEntity Entity,
        SelectableEntityType EntityType,
        string? ComponentName);

    private static IEnumerable<TopologyEntityCandidate> EnumerateTopologyEntities(
        IModelDoc2 doc,
        SelectableEntityType entityType,
        string? componentName)
    {
        var all = EnumerateBodyContexts(doc)
            .SelectMany(context => EnumerateTopologyEntitiesForBody(context.Body, context.ComponentName))
            .Where(candidate => candidate.EntityType == entityType)
            .Where(candidate => string.IsNullOrWhiteSpace(componentName)
                || string.Equals(candidate.ComponentName, componentName, StringComparison.OrdinalIgnoreCase))
            .ToList();

        for (int index = 0; index < all.Count; index++)
        {
            yield return all[index] with { Index = index };
        }
    }

    private static IEnumerable<(IBody2 Body, string? ComponentName)> EnumerateBodyContexts(IModelDoc2 doc)
    {
        if (doc is IPartDoc part)
        {
            foreach (var body in GetBodies(part))
            {
                yield return (body, null);
            }

            yield break;
        }

        if (doc is IAssemblyDoc assembly)
        {
            var components = (object[]?)assembly.GetComponents(true) ?? Array.Empty<object>();
            foreach (var component in EnumerateAssemblyComponentsRecursive(components.OfType<IComponent2>()))
            {
                foreach (var body in GetBodies(component))
                {
                    yield return (body, component.Name2);
                }
            }

            yield break;
        }

        throw new InvalidOperationException("Topology selection is only supported for part and assembly documents.");
    }

    private static IEnumerable<TopologyEntityCandidate> EnumerateTopologyEntitiesForBody(IBody2 body, string? componentName)
    {
        foreach (var face in ((object[]?)body.GetFaces() ?? Array.Empty<object>()).OfType<IFace2>())
        {
            yield return new TopologyEntityCandidate(-1, (IEntity)face, SelectableEntityType.Face, componentName);
        }

        foreach (var edge in ((object[]?)body.GetEdges() ?? Array.Empty<object>()).OfType<IEdge>())
        {
            yield return new TopologyEntityCandidate(-1, (IEntity)edge, SelectableEntityType.Edge, componentName);
        }

        foreach (var vertex in ((object[]?)body.GetVertices() ?? Array.Empty<object>()).OfType<IVertex>())
        {
            yield return new TopologyEntityCandidate(-1, (IEntity)vertex, SelectableEntityType.Vertex, componentName);
        }
    }

    private static IEnumerable<IComponent2> EnumerateAssemblyComponentsRecursive(IEnumerable<IComponent2> components)
    {
        foreach (var component in components)
        {
            yield return component;

            var children = (object[]?)component.GetChildren() ?? Array.Empty<object>();
            foreach (var child in EnumerateAssemblyComponentsRecursive(children.OfType<IComponent2>()))
            {
                yield return child;
            }
        }
    }

    private static IEnumerable<IBody2> GetBodies(IPartDoc part)
    {
        return ((object[]?)part.GetBodies2((int)swBodyType_e.swSolidBody, true) ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    private static IEnumerable<IBody2> GetBodies(IComponent2 component)
    {
        return (component.GetBodies3((int)swBodyType_e.swSolidBody, out _) as object[] ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    private static IEnumerable<(string DimensionToken, string DisplayDimensionSelectionName, string? FullName, double? Value)>
        EnumerateFeatureDimensions(Feature feature)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var displayDimension = feature.GetFirstDisplayDimension() as DisplayDimension;
        while (displayDimension != null)
        {
            if (TryCreateFeatureDimensionItem(displayDimension, out var item))
            {
                string key = $"{item.DimensionToken}|{item.DisplayDimensionSelectionName}";
                if (seen.Add(key))
                {
                    yield return item;
                }
            }

            displayDimension = SafeGetNextFeatureDisplayDimension(feature, displayDimension);
        }
    }

    private static DisplayDimension? SafeGetNextFeatureDisplayDimension(Feature feature, DisplayDimension current)
    {
        try
        {
            return feature.GetNextDisplayDimension(current) as DisplayDimension;
        }
        catch
        {
            try
            {
                return current.GetNext5();
            }
            catch
            {
                return null;
            }
        }
    }

    private static bool? TryGetDisplayFeatureDimensions(IModelDoc2 doc)
    {
        try
        {
            return doc.GetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDisplayFeatureDimensions);
        }
        catch
        {
            return null;
        }
    }

    private static void TrySetDisplayFeatureDimensions(IModelDoc2 doc, bool enabled)
    {
        try
        {
            doc.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDisplayFeatureDimensions, enabled);
        }
        catch
        {
        }
    }

    private static bool TryCreateFeatureDimensionItem(
        DisplayDimension displayDimension,
        out (string DimensionToken, string DisplayDimensionSelectionName, string? FullName, double? Value) item)
    {
        item = default;
        var dimension = displayDimension.GetDimension2(0);
        if (dimension == null)
        {
            return false;
        }

        string? fullName = TryReadDimensionFullName(dimension);
        string? token = fullName;
        if (string.IsNullOrWhiteSpace(token))
        {
            token = dimension.GetNameForSelection();
        }

        if (string.IsNullOrWhiteSpace(token))
        {
            return false;
        }

        string displaySelectionName = displayDimension.GetNameForSelection();
        if (string.IsNullOrWhiteSpace(displaySelectionName))
        {
            displaySelectionName = token;
        }

        item = (
            token.Trim(),
            displaySelectionName.Trim(),
            fullName,
            TryReadDimensionValue(dimension));
        return true;
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

    private static Feature? ResolveSquareTubeLengthControllingSketchFeature(Feature feature)
        => ResolveSquareTubeLengthControllingSketch(feature, CartesianAxis.X, doc: null)?.SketchFeature
            ?? ResolveSquareTubeLengthControllingSketchByNameOnly(feature);

    private static Feature? ResolveSquareTubeLengthControllingSketchByNameOnly(Feature feature)
    {
        var parentFeatures = ResolveSquareTubeParentFeatureCandidates(feature);
        var directOwnerSketch = ResolveOwningSketchFeature(feature);
        string? directOwnerSketchName = directOwnerSketch == null ? null : SafeGetFeatureName(directOwnerSketch);

        return parentFeatures
            .SelectMany(EnumerateFeatureTree)
            .Where(IsSketchFeature)
            .Where(candidate => !string.Equals(SafeGetFeatureName(candidate), directOwnerSketchName, StringComparison.OrdinalIgnoreCase))
            .Select(candidate => new
            {
                Sketch = candidate,
                Score = ScoreSquareTubeLengthSketchCandidate(candidate)
            })
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => SafeGetFeatureName(candidate.Sketch), StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault()
            ?.Sketch;
    }

    private static SquareTubeLengthSketchResolution? ResolveSquareTubeLengthControllingSketch(Feature feature, CartesianAxis axis, IModelDoc2? doc)
    {
        var parentFeatures = ResolveSquareTubeParentFeatureCandidates(feature);
        var directOwnerSketch = ResolveOwningSketchFeature(feature);
        string? directOwnerSketchName = directOwnerSketch == null ? null : SafeGetFeatureName(directOwnerSketch);
        var candidates = new List<SquareTubeLengthSketchResolution>();

        foreach (var parent in parentFeatures)
        {
            foreach (var sketchFeature in EnumerateFeatureTree(parent).Where(IsSketchFeature))
            {
                if (string.Equals(SafeGetFeatureName(sketchFeature), directOwnerSketchName, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (TryCreateLengthSketchResolution(sketchFeature, axis, out var resolution))
                {
                    candidates.Add(resolution);
                }
            }
        }

        if (doc != null)
        {
            foreach (var sketchFeature in EnumerateDocumentFeatures(doc).Where(IsSketchFeature))
            {
                if (string.Equals(SafeGetFeatureName(sketchFeature), directOwnerSketchName, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (TryCreateLengthSketchResolution(sketchFeature, axis, out var resolution))
                {
                    candidates.Add(resolution with
                    {
                        Score = resolution.Score - 250,
                        Reason = resolution.Reason + " Used document-wide fallback because no parent feature candidate produced a better match."
                    });
                }
            }
        }

        return candidates
            .GroupBy(candidate => candidate.SketchFeature, ReferenceEqualityComparer.Instance)
            .Select(group => group.OrderByDescending(candidate => candidate.Score).First())
            .OrderByDescending(candidate => candidate.Score)
            .ThenByDescending(candidate => candidate.Segment.LengthMeters)
            .ThenBy(candidate => SafeGetFeatureName(candidate.SketchFeature), StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();
    }

    private static bool TryCreateLengthSketchResolution(
        Feature sketchFeature,
        CartesianAxis axis,
        out SquareTubeLengthSketchResolution resolution)
    {
        resolution = null!;
        if (sketchFeature.GetSpecificFeature2() is not ISketch sketch)
        {
            return false;
        }

        var segment = TryChooseAxisAlignedSegment(sketch, axis);
        if (segment == null)
        {
            return false;
        }

        int score = ScoreSquareTubeLengthSketchCandidate(sketchFeature);
        score += ScoreLengthControlSegment(segment);
        string reason = $"Matched sketch '{SafeGetFeatureName(sketchFeature)}' because it contains an axis-{axis} line segment and scored {score}.";
        resolution = new SquareTubeLengthSketchResolution(sketchFeature, segment, score, reason);
        return true;
    }

    private static bool TryResolveSquareTubeDimensionByName(
        IModelDoc2 doc,
        Feature feature,
        string dimensionName,
        out NamedSquareTubeDimensionResolution resolution)
    {
        resolution = null!;
        string normalizedName = NormalizeDimensionLookupName(dimensionName);
        if (string.IsNullOrWhiteSpace(normalizedName))
        {
            return false;
        }

        var scopedMatches = EnumerateSquareTubeDimensionSearchFeatures(feature)
            .Where(IsSketchFeature)
            .SelectMany(sketchFeature => EnumerateNamedDimensions(sketchFeature)
                .Where(candidate => DimensionNameMatches(candidate.DisplayDimension, candidate.Dimension, normalizedName))
                .Select(candidate => new NamedSquareTubeDimensionResolution(
                    sketchFeature,
                    candidate.DisplayDimension,
                    candidate.Dimension,
                    ScoreSquareTubeLengthSketchCandidate(sketchFeature))))
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => SafeGetFeatureName(candidate.SketchFeature!), StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();

        if (scopedMatches != null)
        {
            resolution = scopedMatches;
            return true;
        }

        var directDimension = TryGetDocumentParameter(doc, dimensionName);
        if (directDimension != null)
        {
            resolution = new NamedSquareTubeDimensionResolution(
                null,
                null,
                directDimension,
                0);
            return true;
        }

        return false;
    }

    private static SquareTubeLengthUpdateResult UpdateSquareTubeNamedDimension(
        IModelDoc2 doc,
        Feature feature,
        NamedSquareTubeDimensionResolution resolution,
        CartesianAxis axis,
        string lengthExpression,
        double newLengthMeters)
    {
        var dimension = resolution.Dimension;
        if (dimension.DrivenState == (int)swDimensionDrivenState_e.swDimensionDriven)
        {
            dimension.DrivenState = (int)swDimensionDrivenState_e.swDimensionDriving;
        }

        double? previousLength = TryReadDimensionValue(dimension);
        SetDimensionSystemValue(dimension, newLengthMeters);
        doc.EditRebuild3();
        double? updatedLength = TryReadDimensionValue(dimension);

        string displaySelectionName = resolution.DisplayDimension?.GetNameForSelection() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(displaySelectionName))
        {
            displaySelectionName = TryReadDimensionFullName(dimension)
                ?? dimension.GetNameForSelection()
                ?? string.Empty;
        }

        string? token = TryReadDimensionFullName(dimension) ?? dimension.GetNameForSelection();
        string sketchFeatureName = SafeGetFeatureName(resolution.SketchFeature!) ?? "(direct dimension)";
        string sketchType = resolution.SketchFeature == null
            ? "direct-dimension"
            : SafeGetFeatureTypeName(resolution.SketchFeature) ?? "unknown";

        return new SquareTubeLengthUpdateResult(
            feature.Name,
            sketchFeatureName,
            sketchType,
            axis,
            lengthExpression.Trim(),
            newLengthMeters,
            previousLength,
            updatedLength,
            previousLength ?? updatedLength ?? newLengthMeters,
            1d,
            false,
            displaySelectionName.Trim(),
            string.IsNullOrWhiteSpace(token) ? null : token.Trim(),
            resolution.SketchFeature == null
                ? "Updated the explicitly named square-tube length dimension by document parameter lookup."
                : $"Updated the explicitly named square-tube length dimension in sketch '{sketchFeatureName}'.");
    }

    private static IEnumerable<Feature> EnumerateSquareTubeDimensionSearchFeatures(Feature feature)
    {
        var roots = new List<Feature>();

        void Add(Feature? candidate)
        {
            if (candidate == null)
            {
                return;
            }

            if (!roots.Any(existing => ReferenceEquals(existing, candidate)))
            {
                roots.Add(candidate);
            }
        }

        foreach (var parent in ResolveSquareTubeParentFeatureCandidates(feature))
        {
            Add(parent);
        }

        Add(feature);

        var directOwnerSketch = ResolveOwningSketchFeature(feature);
        string? directOwnerSketchName = directOwnerSketch == null ? null : SafeGetFeatureName(directOwnerSketch);
        var visited = new HashSet<Feature>();

        foreach (var root in roots)
        {
            if (visited.Add(root))
            {
                yield return root;
            }

            foreach (var candidate in EnumerateFeatureTree(root))
            {
                if (!visited.Add(candidate))
                {
                    continue;
                }

                if (string.Equals(SafeGetFeatureName(candidate), directOwnerSketchName, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                yield return candidate;
            }
        }
    }

    private static IEnumerable<(DisplayDimension DisplayDimension, Dimension Dimension)> EnumerateNamedDimensions(Feature feature)
    {
        var displayDimension = feature.GetFirstDisplayDimension() as DisplayDimension;
        while (displayDimension != null)
        {
            var dimension = displayDimension.GetDimension2(0);
            if (dimension != null)
            {
                yield return (displayDimension, dimension);
            }

            displayDimension = SafeGetNextFeatureDisplayDimension(feature, displayDimension);
        }
    }

    private static bool DimensionNameMatches(DisplayDimension displayDimension, Dimension dimension, string normalizedName)
    {
        return DimensionNameMatches(TryReadDimensionFullName(dimension), normalizedName)
            || DimensionNameMatches(SafeGetDimensionSelectionName(dimension), normalizedName)
            || DimensionNameMatches(SafeGetDisplayDimensionSelectionName(displayDimension), normalizedName);
    }

    private static bool DimensionNameMatches(string? candidate, string normalizedName)
    {
        if (string.IsNullOrWhiteSpace(candidate))
        {
            return false;
        }

        string normalizedCandidate = NormalizeDimensionLookupName(candidate);
        return string.Equals(normalizedCandidate, normalizedName, StringComparison.OrdinalIgnoreCase)
            || string.Equals(NormalizeDimensionShortName(normalizedCandidate), NormalizeDimensionShortName(normalizedName), StringComparison.OrdinalIgnoreCase);
    }

    private static string NormalizeDimensionLookupName(string value)
        => value.Trim().Trim('"').Trim('\'');

    private static string NormalizeDimensionShortName(string value)
    {
        int atIndex = value.IndexOf('@');
        return atIndex <= 0 ? value : value[..atIndex];
    }

    private static Dimension? TryGetDocumentParameter(IModelDoc2 doc, string dimensionName)
    {
        foreach (string candidateName in EnumerateDocumentParameterNames(dimensionName))
        {
            try
            {
                var dimension = doc.Parameter(candidateName) as Dimension;
                if (dimension != null)
                {
                    return dimension;
                }
            }
            catch
            {
            }
        }

        return null;
    }

    private static string? SafeGetDimensionSelectionName(Dimension dimension)
    {
        try
        {
            return dimension.GetNameForSelection();
        }
        catch
        {
            return null;
        }
    }

    private static string? SafeGetDisplayDimensionSelectionName(DisplayDimension displayDimension)
    {
        try
        {
            return displayDimension.GetNameForSelection();
        }
        catch
        {
            return null;
        }
    }

    private static IEnumerable<string> EnumerateDocumentParameterNames(string dimensionName)
    {
        string trimmed = NormalizeDimensionLookupName(dimensionName);
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            yield break;
        }

        yield return trimmed;

        if (trimmed.StartsWith("D", StringComparison.OrdinalIgnoreCase)
            && trimmed.Length > 1
            && char.IsDigit(trimmed[1]))
        {
            yield return $"\"{trimmed}\"";
        }
    }

    private static Feature? ResolveParentFeature(Feature feature)
    {
        try
        {
            var owner = feature.GetOwnerFeature() as Feature;
            if (owner != null)
            {
                return owner;
            }
        }
        catch
        {
        }

        try
        {
            var parents = feature.GetParents() as object[] ?? Array.Empty<object>();
            return parents.OfType<Feature>().FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }

    private static IReadOnlyList<Feature> ResolveSquareTubeParentFeatureCandidates(Feature feature)
    {
        var candidates = new List<Feature>();

        void Add(Feature? candidate)
        {
            if (candidate == null)
            {
                return;
            }

            if (!candidates.Any(existing => ReferenceEquals(existing, candidate)))
            {
                candidates.Add(candidate);
            }
        }

        var parent = ResolveParentFeature(feature);
        Add(parent);

        foreach (var candidate in SafeGetFeatureParents(feature))
        {
            Add(candidate);
        }

        if (parent != null)
        {
            foreach (var candidate in SafeGetFeatureParents(parent))
            {
                Add(candidate);
            }
        }

        return candidates.AsReadOnly();
    }

    private static IEnumerable<Feature> EnumerateSubFeatures(Feature feature)
    {
        for (var sub = SafeGetFirstSubFeature(feature); sub != null; sub = SafeGetNextSubFeature(sub))
        {
            yield return sub;
        }
    }

    private static IEnumerable<Feature> EnumerateFeatureTree(Feature root)
    {
        var stack = new Stack<Feature>(EnumerateSubFeatures(root).Reverse());
        var visited = new HashSet<Feature>();

        while (stack.Count > 0)
        {
            var current = stack.Pop();
            if (!visited.Add(current))
            {
                continue;
            }

            yield return current;

            foreach (var child in EnumerateSubFeatures(current).Reverse())
            {
                stack.Push(child);
            }
        }
    }

    private static IEnumerable<Feature> EnumerateDocumentFeatures(IModelDoc2 doc)
    {
        var visited = new HashSet<Feature>();
        for (var feature = SafeGetFirstFeature(doc); feature != null; feature = SafeGetNextFeature(feature))
        {
            if (visited.Add(feature))
            {
                yield return feature;
            }

            foreach (var child in EnumerateFeatureTree(feature))
            {
                if (visited.Add(child))
                {
                    yield return child;
                }
            }
        }
    }

    private static int ScoreLengthControlSketchCandidate(Feature sketchFeature)
    {
        string rawName = (SafeGetFeatureName(sketchFeature) ?? string.Empty).Trim();
        string name = rawName.ToLowerInvariant();
        int score = 0;

        if (rawName.Contains("3D草图", StringComparison.OrdinalIgnoreCase)
            || rawName.Contains("3D Sketch", StringComparison.OrdinalIgnoreCase)
            || rawName.Contains("3DSketch", StringComparison.OrdinalIgnoreCase))
        {
            score += 600;
        }

        if (rawName.Contains("草图", StringComparison.OrdinalIgnoreCase))
        {
            score += 320;
        }

        if (name.Contains("length", StringComparison.Ordinal))
        {
            score += 500;
        }

        if (name.Contains("path", StringComparison.Ordinal))
        {
            score += 350;
        }

        if (name.Contains("guide", StringComparison.Ordinal))
        {
            score += 250;
        }

        if (name.Contains("x", StringComparison.Ordinal)
            || name.Contains("y", StringComparison.Ordinal)
            || name.Contains("z", StringComparison.Ordinal))
        {
            score += 80;
        }

        if (name.StartsWith("sketch", StringComparison.Ordinal)
            || string.Equals(name, "sketch", StringComparison.Ordinal)
            || name.Contains(" sketch", StringComparison.Ordinal))
        {
            score -= 260;
        }

        if (name.Contains("profile", StringComparison.Ordinal)
            || name.Contains("section", StringComparison.Ordinal)
            || name.Contains("cross", StringComparison.Ordinal))
        {
            score -= 400;
        }

        return score;
    }

    private static bool IsSketchFeature(Feature feature)
    {
        string? typeName = SafeGetFeatureTypeName(feature);
        return string.Equals(typeName, "ProfileFeature", StringComparison.OrdinalIgnoreCase)
            || string.Equals(typeName, "3DProfileFeature", StringComparison.OrdinalIgnoreCase);
    }

    private static int ScoreSquareTubeLengthSketchCandidate(Feature sketchFeature)
    {
        string rawName = (SafeGetFeatureName(sketchFeature) ?? string.Empty).Trim();
        string name = rawName.ToLowerInvariant();
        string typeName = SafeGetFeatureTypeName(sketchFeature) ?? string.Empty;
        int score = 0;

        if (rawName.Contains("3D草图", StringComparison.OrdinalIgnoreCase)
            || rawName.Contains("3D Sketch", StringComparison.OrdinalIgnoreCase)
            || rawName.Contains("3DSketch", StringComparison.OrdinalIgnoreCase))
        {
            score += 600;
        }

        if (rawName.Contains("草图", StringComparison.OrdinalIgnoreCase))
        {
            score += 320;
        }

        if (string.Equals(typeName, "3DProfileFeature", StringComparison.OrdinalIgnoreCase))
        {
            score += 180;
        }

        if (name.Contains("length", StringComparison.Ordinal))
        {
            score += 500;
        }

        if (name.Contains("path", StringComparison.Ordinal))
        {
            score += 350;
        }

        if (name.Contains("guide", StringComparison.Ordinal))
        {
            score += 250;
        }

        if (name.Contains("x", StringComparison.Ordinal)
            || name.Contains("y", StringComparison.Ordinal)
            || name.Contains("z", StringComparison.Ordinal))
        {
            score += 80;
        }

        if (name.StartsWith("sketch", StringComparison.Ordinal)
            || string.Equals(name, "sketch", StringComparison.Ordinal)
            || name.Contains(" sketch", StringComparison.Ordinal))
        {
            score -= 380;
        }

        if (name.Contains("profile", StringComparison.Ordinal)
            || name.Contains("section", StringComparison.Ordinal)
            || name.Contains("cross", StringComparison.Ordinal))
        {
            score -= 400;
        }

        return score;
    }

    private static int ScoreLengthControlSegment(AxisSegmentCandidate candidate)
    {
        int score = (int)Math.Round(candidate.AlignmentScore * 300d);
        score += (int)Math.Min(300d, candidate.LengthMeters * 100d);
        return score;
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

    internal sealed record AxisSegmentCandidate(
        ISketchSegment Segment,
        ISketchLine SketchLine,
        double LengthMeters,
        double DeltaX,
        double DeltaY,
        double DeltaZ,
        double AlignmentScore);

    internal static AxisSegmentCandidate ChooseAxisAlignedSegment(ISketch sketch, CartesianAxis axis)
    {
        var selected = TryChooseAxisAlignedSegment(sketch, axis);
        if (selected != null)
        {
            return selected;
        }

        throw new InvalidOperationException(
            $"The sketch does not contain any line segment aligned with axis {axis}. Only straight sketch lines are supported.");
    }

    internal static AxisSegmentCandidate? TryChooseAxisAlignedSegment(ISketch sketch, CartesianAxis axis)
    {
        var segments = (object[]?)sketch.GetSketchSegments() ?? Array.Empty<object>();
        var candidates = new List<AxisSegmentCandidate>();

        foreach (var rawSegment in segments)
        {
            if (rawSegment is not ISketchLine line || rawSegment is not ISketchSegment segment)
            {
                continue;
            }

            var candidate = CreateAxisSegmentCandidate(segment, line, axis);
            if (candidate != null)
            {
                candidates.Add(candidate);
            }
        }

        return candidates
            .OrderByDescending(candidate => candidate.AlignmentScore)
            .ThenByDescending(candidate => candidate.LengthMeters)
            .FirstOrDefault();
    }

    internal static AxisSegmentCandidate? CreateAxisSegmentCandidate(ISketchSegment segment, ISketchLine line, CartesianAxis axis)
    {
        try
        {
            var start = line.IGetStartPoint2();
            var end = line.IGetEndPoint2();
            if (start == null || end == null)
            {
                return null;
            }

            double dx = end.X - start.X;
            double dy = end.Y - start.Y;
            double dz = end.Z - start.Z;
            double length = Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
            if (length <= 1e-9)
            {
                return null;
            }

            double axisComponent = axis switch
            {
                CartesianAxis.X => Math.Abs(dx),
                CartesianAxis.Y => Math.Abs(dy),
                CartesianAxis.Z => Math.Abs(dz),
                _ => 0d,
            };

            double alignment = axisComponent / length;
            if (alignment < 0.95d)
            {
                return null;
            }

            return new AxisSegmentCandidate(segment, line, length, dx, dy, dz, alignment);
        }
        catch
        {
            return null;
        }
    }

    private static (DisplayDimension DisplayDimension, Dimension Dimension)? TryResolveExistingDisplayDimension(
        Feature sketchFeature,
        AxisSegmentCandidate targetSegment,
        CartesianAxis axis)
    {
        var displayDimension = sketchFeature.GetFirstDisplayDimension() as DisplayDimension;
        while (displayDimension != null)
        {
            var dimension = displayDimension.GetDimension2(0);
            if (dimension != null && IsDimensionCompatibleWithAxis(dimension, targetSegment, axis))
            {
                return (displayDimension, dimension);
            }

            displayDimension = SafeGetNextFeatureDisplayDimension(sketchFeature, displayDimension);
        }

        return null;
    }

    private static bool IsDimensionCompatibleWithAxis(Dimension dimension, AxisSegmentCandidate targetSegment, CartesianAxis axis)
    {
        try
        {
            var fullName = TryReadDimensionFullName(dimension)?.ToLowerInvariant() ?? string.Empty;
            string axisToken = axis.ToString().ToLowerInvariant();
            if (fullName.Contains(axisToken))
            {
                return true;
            }

            double? currentValue = TryReadDimensionValue(dimension);
            if (!currentValue.HasValue)
            {
                return false;
            }

            return Math.Abs(currentValue.Value - targetSegment.LengthMeters) <= 1e-6;
        }
        catch
        {
            return false;
        }
    }

    private static object? CreateDrivingDimensionForSegment(
        IModelDoc2 doc,
        ISketchSegment segment,
        CartesianAxis axis,
        AxisSegmentCandidate candidate)
    {
        return axis switch
        {
            CartesianAxis.X => doc.AddHorizontalDimension2(GetDimensionAnchor(candidate, axis).X, GetDimensionAnchor(candidate, axis).Y, GetDimensionAnchor(candidate, axis).Z),
            CartesianAxis.Y => doc.AddVerticalDimension2(GetDimensionAnchor(candidate, axis).X, GetDimensionAnchor(candidate, axis).Y, GetDimensionAnchor(candidate, axis).Z),
            CartesianAxis.Z => doc.AddDimension2(GetDimensionAnchor(candidate, axis).X, GetDimensionAnchor(candidate, axis).Y, GetDimensionAnchor(candidate, axis).Z),
            _ => doc.AddDimension2(0.02, 0.02, 0),
        };
    }

    private static (double X, double Y, double Z) GetDimensionAnchor(AxisSegmentCandidate candidate, CartesianAxis axis)
    {
        var start = candidate.SketchLine.IGetStartPoint2();
        var end = candidate.SketchLine.IGetEndPoint2();
        if (start == null || end == null)
        {
            return (0.02, 0.02, 0);
        }

        double midX = (start.X + end.X) / 2d;
        double midY = (start.Y + end.Y) / 2d;
        double midZ = (start.Z + end.Z) / 2d;
        const double offset = 0.01d;

        return axis switch
        {
            CartesianAxis.X => (midX, midY + offset, midZ),
            CartesianAxis.Y => (midX + offset, midY, midZ),
            CartesianAxis.Z => (midX + offset, midY + offset, midZ),
            _ => (0.02, 0.02, 0),
        };
    }

    private static void SetDimensionSystemValue(Dimension dimension, double systemValueMeters)
    {
        int status;
        try
        {
            status = dimension.SetSystemValue3(
                systemValueMeters,
                (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,
                null!);
        }
        catch
        {
            status = (int)swSetValueReturnStatus_e.swSetValue_Failure;
        }

        if (status == (int)swSetValueReturnStatus_e.swSetValue_Successful)
        {
            return;
        }

        if (status == (int)swSetValueReturnStatus_e.swSetValue_DrivenDimension)
        {
            throw new InvalidOperationException("The matched sketch dimension is driven/reference-only and cannot be used to control square-tube length.");
        }

        try
        {
            dimension.SystemValue = systemValueMeters;
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"Failed to set dimension value. SolidWorks status={((swSetValueReturnStatus_e)status)}.",
                ex);
        }
    }

    private static double ParseLengthExpressionToMeters(string value)
    {
        string normalized = value.Trim().ToLowerInvariant();
        if (normalized.EndsWith("mm", StringComparison.Ordinal))
        {
            return double.Parse(normalized[..^2], System.Globalization.CultureInfo.InvariantCulture) / 1000d;
        }

        if (normalized.EndsWith("cm", StringComparison.Ordinal))
        {
            return double.Parse(normalized[..^2], System.Globalization.CultureInfo.InvariantCulture) / 100d;
        }

        if (normalized.EndsWith("m", StringComparison.Ordinal))
        {
            return double.Parse(normalized[..^1], System.Globalization.CultureInfo.InvariantCulture);
        }

        return double.Parse(normalized, System.Globalization.CultureInfo.InvariantCulture);
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

    private static IReadOnlyList<Feature> SafeGetFeatureParents(Feature feature)
    {
        try
        {
            return (feature.GetParents() as object[] ?? Array.Empty<object>())
                .OfType<Feature>()
                .ToList()
                .AsReadOnly();
        }
        catch
        {
            return Array.Empty<Feature>();
        }
    }

    private static Feature? SafeGetFirstSubFeature(Feature feature)
    {
        try
        {
            return feature.GetFirstSubFeature() as Feature;
        }
        catch
        {
            return null;
        }
    }

    private static Feature? SafeGetNextSubFeature(Feature feature)
    {
        try
        {
            return feature.GetNextSubFeature() as Feature;
        }
        catch
        {
            return null;
        }
    }

    private static Feature? SafeGetFirstFeature(IModelDoc2 doc)
    {
        try
        {
            return doc.FirstFeature() as Feature;
        }
        catch
        {
            return null;
        }
    }

    private static Feature? SafeGetNextFeature(Feature feature)
    {
        try
        {
            return feature.GetNextFeature() as Feature;
        }
        catch
        {
            return null;
        }
    }
}
