using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyModuleMateGraphNode(
    string ModuleToken,
    string Name,
    string Path,
    string HierarchyPath,
    double[]? SourceTransform,
    bool IsSuppressed,
    int SuppressionState,
    string SuppressionStateName,
    int VisibilityState,
    string? ReferencedConfiguration = null,
    int? SolvingState = null,
    string? SolvingStateName = null);

public record AssemblyModuleMateAdvancedOptions(
    int? WidthConstraintType,
    double? WidthPercentDistanceFromEnd,
    double? WidthDistanceFromEnd,
    bool? WidthFlipDimension,
    IReadOnlyList<int> WidthEndpointIndices,
    IReadOnlyList<int> TabEndpointIndices,
    int? SlotConstraint,
    double? SlotDistance,
    double? SlotPercent,
    bool? SlotFlipDirection,
    bool? DistanceFlipDimension,
    int? SourceFeatureErrorCode,
    bool? SourceFeatureIsWarning);

public record AssemblyModuleMateGraphEndpoint(
    int Index,
    string ModuleToken,
    string ModuleHierarchyPath,
    string LeafHierarchyPath,
    string RelativeLeafHierarchyPath,
    string LeafComponentName,
    string LeafComponentPath,
    string GeometryType,
    int BodyIndex,
    int FaceIndexInBody,
    double? FaceArea,
    double[]? FaceBoxLocal,
    double[]? FaceCenterLocal,
    double[]? FaceCenterWorld,
    double[]? FaceNormalLocal,
    double[]? FaceNormalWorld,
    string? SourceAssemblyPersistentReferenceBase64,
    string? SurfaceType = null,
    double[]? CylinderOriginLocal = null,
    double[]? CylinderOriginWorld = null,
    double[]? CylinderAxisLocal = null,
    double[]? CylinderAxisWorld = null,
    double? CylinderRadius = null);

internal sealed record MateGraphCylinderGeometry(
    double[] Origin,
    double[] Axis,
    double Radius);

public record AssemblyModuleMateGraphMate(
    string MateName,
    int MateType,
    string MateTypeName,
    int Alignment,
    string AlignmentName,
    double? Distance,
    double? Angle,
    bool IsSuppressed,
    bool IsBasicTwoFaceRebuildable,
    string? RebuildRejectionReason,
    IReadOnlyList<string> ModuleTokens,
    IReadOnlyList<string> ModuleHierarchyPaths,
    IReadOnlyList<AssemblyModuleMateGraphEndpoint> Endpoints,
    AssemblyModuleMateAdvancedOptions? AdvancedOptions = null);

public record AssemblyModuleMateBundle(
    string FirstModuleToken,
    string SecondModuleToken,
    string FirstModuleHierarchyPath,
    string SecondModuleHierarchyPath,
    int MateCount,
    int BasicTwoFaceRebuildableMateCount,
    IReadOnlyList<string> MateNames,
    IReadOnlyList<string> MateTypes,
    bool HasPositionDimension,
    bool HasCompoundPositioningMate,
    bool HasOrientationRelation,
    string InstallationRelationAssessment);

public record AssemblyModuleMateGraphResult(
    string SchemaVersion,
    string SourceAssemblyPath,
    IReadOnlyList<string> RequestedModuleTokens,
    int ModuleCount,
    int InterModuleMateCount,
    int MateBundleCount,
    int IgnoredIntraModuleMateCount,
    int IgnoredUnresolvedMateCount,
    IReadOnlyList<AssemblyModuleMateGraphNode> Modules,
    IReadOnlyList<AssemblyModuleMateGraphMate> Mates,
    IReadOnlyList<AssemblyModuleMateBundle> MateBundles,
    string? SavedJsonPath,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    private static readonly string[] DefaultProject02MateGraphModuleTokens =
    [
        "A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"
    ];

    /// <summary>
    /// Export a read-only graph of all direct top-level mate features whose endpoints resolve into
    /// two known top-level module subtrees. The graph deliberately records geometry identity and
    /// groups multiple mate features between the same module pair into one installation bundle.
    /// It does not claim that the undirected mate graph is the mechanical assembly sequence.
    /// </summary>
    public AssemblyModuleMateGraphResult ExportModuleMateGraph(
        string sourceAssemblyPath,
        IReadOnlyList<string>? moduleTokens = null,
        string? outputPath = null,
        bool saveJson = true)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);

        var tokens = (moduleTokens is { Count: > 0 } ? moduleTokens : DefaultProject02MateGraphModuleTokens)
            .Where(token => !string.IsNullOrWhiteSpace(token))
            .Select(token => token.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (tokens.Length < 2)
            throw new ArgumentException("At least two non-empty module tokens are required.", nameof(moduleTokens));

        var diagnostics = new List<string>();
        var (assembly, document, topLevelInstances) = OpenMatePairSource(sourceAssemblyPath);
        var roots = ResolveMateGraphRoots(topLevelInstances, tokens, diagnostics);
        ResolveDirectPartRootsForStableMateEndpoints(document, roots, diagnostics);
        var instanceByComIdentity = BuildMateGraphComponentIndex(assembly, roots, diagnostics);

        var modules = roots
            .Select(root =>
            {
                int suppressionState = MateGraphComponentSuppressionState(root.Instance.Component);
                return new AssemblyModuleMateGraphNode(
                    root.Token,
                    root.Instance.Info.Name,
                    root.Instance.Info.Path,
                    root.Instance.Info.HierarchyPath,
                    PairTransformArray(root.Instance.Component.Transform2),
                    suppressionState == (int)swComponentSuppressionState_e.swComponentSuppressed,
                    suppressionState,
                    MateGraphSuppressionStateName(suppressionState),
                    PairSafeComponentVisibility(root.Instance.Component),
                    SafeReferencedConfiguration(root.Instance.Component),
                    SafeComponentSolvingState(root.Instance.Component),
                    SafeComponentSolvingStateName(root.Instance.Component));
            })
            .OrderBy(module => module.ModuleToken, StringComparer.OrdinalIgnoreCase)
            .ThenBy(module => module.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToList();

        int ignoredIntra = 0;
        int ignoredUnresolved = 0;
        var mates = new List<AssemblyModuleMateGraphMate>();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
                continue;

            int entityCount = PairSafeMateEntityCount(mate);
            var endpoints = new List<AssemblyModuleMateGraphEndpoint>();
            for (int index = 0; index < entityCount; index++)
            {
                IMateEntity2? entity = PairSafeMateEntity(mate, index);
                IComponent2? component = PairSafeReferenceComponent(entity);
                object? reference = PairSafeReference(entity);
                if (component == null)
                    continue;

                long componentIdentity = MateGraphComIdentity(component);
                if (componentIdentity == 0 || !instanceByComIdentity.TryGetValue(componentIdentity, out var indexed))
                    continue;

                endpoints.Add(BuildMateGraphEndpoint(document, index, indexed.Owner, indexed.Leaf, component, reference));
            }

            var owners = endpoints
                .GroupBy(endpoint => endpoint.ModuleHierarchyPath, StringComparer.OrdinalIgnoreCase)
                .Select(group => group.First())
                .ToList();
            if (owners.Count < 2)
            {
                if (owners.Count == 1)
                    ignoredIntra++;
                else
                    ignoredUnresolved++;
                continue;
            }
            if (owners.Count > 2)
            {
                ignoredUnresolved++;
                diagnostics.Add($"Mate '{feature.Name}' references {owners.Count} known modules and was not reduced to a binary graph edge.");
                continue;
            }

            int mateType = PairSafeMateType(mate);
            int alignment = PairSafeMateAlignment(mate);
            double? distance = PairSafeDistance(feature, mateType);
            double? angle = MateGraphSafeAngle(feature, mateType);
            string? rejection = MateGraphRebuildRejection(entityCount, endpoints, mateType, distance);
            var advancedOptions = ReadGraphMateAdvancedOptions(feature, mate, mateType);
            mates.Add(new AssemblyModuleMateGraphMate(
                feature.Name ?? "Mate",
                mateType,
                PairMateTypeName(mateType),
                alignment,
                PairAlignmentName(alignment),
                distance,
                angle,
                PairSafeFeatureSuppressed(feature),
                rejection == null,
                rejection,
                owners.Select(owner => owner.ModuleToken).OrderBy(value => value, StringComparer.OrdinalIgnoreCase).ToArray(),
                owners.Select(owner => owner.ModuleHierarchyPath).OrderBy(value => value, StringComparer.OrdinalIgnoreCase).ToArray(),
                endpoints.OrderBy(endpoint => endpoint.Index).ToArray(),
                advancedOptions));
        }

        var bundles = BuildModuleMateBundles(mates, modules);
        if (modules.Count < tokens.Length)
            diagnostics.Add($"Resolved {modules.Count} module instances for {tokens.Length} requested tokens. See per-token diagnostics.");
        if (mates.Count == 0)
            diagnostics.Add("No binary inter-module top-level mate feature was resolved for the requested module set.");
        diagnostics.Add("Mate edges are undirected design relations; assembly precedence must be supplied or inferred separately.");

        var result = new AssemblyModuleMateGraphResult(
            "solidworks-module-mate-graph/v1.4",
            Path.GetFullPath(sourceAssemblyPath),
            tokens,
            modules.Count,
            mates.Count,
            bundles.Count,
            ignoredIntra,
            ignoredUnresolved,
            modules.AsReadOnly(),
            mates.AsReadOnly(),
            bundles,
            null,
            diagnostics.AsReadOnly());
        return SaveModuleMateGraphIfRequested(result, outputPath, saveJson);
    }

    internal static IReadOnlyList<AssemblyModuleMateBundle> BuildModuleMateBundles(
        IReadOnlyList<AssemblyModuleMateGraphMate> mates,
        IReadOnlyList<AssemblyModuleMateGraphNode> modules)
    {
        var moduleByHierarchy = modules.ToDictionary(module => module.HierarchyPath, StringComparer.OrdinalIgnoreCase);
        var bundles = new List<AssemblyModuleMateBundle>();
        foreach (var group in mates
            .Where(mate => mate.ModuleHierarchyPaths.Count == 2)
            .GroupBy(mate => CanonicalMatePairKey(mate.ModuleHierarchyPaths[0], mate.ModuleHierarchyPaths[1]), StringComparer.OrdinalIgnoreCase))
        {
            var orderedHierarchies = group.First().ModuleHierarchyPaths.OrderBy(value => value, StringComparer.OrdinalIgnoreCase).ToArray();
            var groupMates = group.OrderBy(mate => mate.MateName, StringComparer.OrdinalIgnoreCase).ToArray();
            bool hasPosition = groupMates.Any(mate => mate.MateType == (int)swMateType_e.swMateDISTANCE);
            bool hasCompoundPositioning = groupMates.Any(mate => mate.MateType is
                (int)swMateType_e.swMateWIDTH or
                (int)swMateType_e.swMateSLOT);
            bool hasOrientation = groupMates.Any(mate => mate.MateType is
                (int)swMateType_e.swMateCOINCIDENT or
                (int)swMateType_e.swMateCONCENTRIC or
                (int)swMateType_e.swMatePARALLEL or
                (int)swMateType_e.swMateWIDTH or
                (int)swMateType_e.swMateSLOT or
                (int)swMateType_e.swMateANGLE);
            bool hasPositionRelation = hasPosition || hasCompoundPositioning;
            string assessment = hasPositionRelation && hasOrientation
                ? "POSITION_AND_ORIENTATION_BUNDLE_CANDIDATE"
                : hasPositionRelation
                    ? "POSITION_DIMENSION_ONLY_PARTIAL_RELATION"
                    : hasOrientation
                        ? "ORIENTATION_OR_CONTACT_ONLY_PARTIAL_RELATION"
                        : "UNCLASSIFIED_PARTIAL_RELATION";
            moduleByHierarchy.TryGetValue(orderedHierarchies[0], out var first);
            moduleByHierarchy.TryGetValue(orderedHierarchies[1], out var second);
            bundles.Add(new AssemblyModuleMateBundle(
                first?.ModuleToken ?? string.Empty,
                second?.ModuleToken ?? string.Empty,
                orderedHierarchies[0],
                orderedHierarchies[1],
                groupMates.Length,
                groupMates.Count(mate => mate.IsBasicTwoFaceRebuildable),
                groupMates.Select(mate => mate.MateName).ToArray(),
                groupMates.Select(mate => mate.MateTypeName).Distinct(StringComparer.OrdinalIgnoreCase).ToArray(),
                hasPosition,
                hasCompoundPositioning,
                hasOrientation,
                assessment));
        }
        return bundles
            .OrderBy(bundle => bundle.FirstModuleToken, StringComparer.OrdinalIgnoreCase)
            .ThenBy(bundle => bundle.SecondModuleToken, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static IReadOnlyList<MateGraphRoot> ResolveMateGraphRoots(
        IReadOnlyList<ComponentInstance> topLevelInstances,
        IReadOnlyList<string> tokens,
        ICollection<string> diagnostics)
    {
        var roots = new List<MateGraphRoot>();
        foreach (string token in tokens)
        {
            var matches = topLevelInstances.Where(instance => PairContains(instance.Info, token)).ToList();
            if (matches.Count == 0)
            {
                diagnostics.Add($"Module token '{token}' did not match a top-level component.");
                continue;
            }
            if (matches.Count > 1)
                diagnostics.Add($"Module token '{token}' matched {matches.Count} top-level instances; all instances are preserved as separate graph nodes.");
            roots.AddRange(matches.Select(instance => new MateGraphRoot(token, instance)));
        }
        return roots
            .GroupBy(root => root.Instance.Info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .ToArray();
    }

    private static IReadOnlyDictionary<long, MateGraphIndexedComponent> BuildMateGraphComponentIndex(
        IAssemblyDoc assembly,
        IReadOnlyList<MateGraphRoot> roots,
        ICollection<string> diagnostics)
    {
        var index = new Dictionary<long, MateGraphIndexedComponent>();
        var flatComponents = (assembly.GetComponents(false) as object[] ?? [])
            .OfType<IComponent2>()
            .ToArray();
        foreach (var component in flatComponents)
        {
            string hierarchy = component.Name2 ?? "Component";
            var owner = roots
                .Where(root => string.Equals(hierarchy, root.Instance.Info.Name, StringComparison.OrdinalIgnoreCase)
                    || hierarchy.StartsWith(root.Instance.Info.Name + "/", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(root => root.Instance.Info.Name.Length)
                .FirstOrDefault();
            if (owner == null)
                continue;

            long identity = MateGraphComIdentity(component);
            if (identity == 0)
                continue;
            int depth = hierarchy.Count(character => character == '/');
            var leaf = new ComponentInstance(
                component,
                new ComponentInstanceInfo(
                    hierarchy.Split('/').LastOrDefault() ?? hierarchy,
                    component.GetPathName() ?? string.Empty,
                    hierarchy,
                    depth));
            index.TryAdd(identity, new MateGraphIndexedComponent(owner, leaf));
        }

        foreach (var root in roots)
        {
            long identity = MateGraphComIdentity(root.Instance.Component);
            if (identity != 0)
                index.TryAdd(identity, new MateGraphIndexedComponent(root, root.Instance));
        }
        diagnostics.Add($"Built one-pass component identity index for {index.Count} instances from {flatComponents.Length} assembly components.");
        return index;
    }

    private static void ResolveDirectPartRootsForStableMateEndpoints(
        IModelDoc2 document,
        IReadOnlyList<MateGraphRoot> roots,
        ICollection<string> diagnostics)
    {
        int attempted = 0;
        int resolved = 0;
        foreach (var root in roots)
        {
            if (!string.Equals(Path.GetExtension(root.Instance.Info.Path), ".SLDPRT", StringComparison.OrdinalIgnoreCase))
                continue;
            attempted++;
            try
            {
                int result = root.Instance.Component.SetSuppression2(
                    (int)swComponentSuppressionState_e.swComponentFullyResolved);
                if (result >= 0)
                    resolved++;
            }
            catch (Exception ex)
            {
                diagnostics.Add(
                    $"Fully resolving direct part root '{root.Instance.Info.HierarchyPath}' for stable mate endpoints was best-effort: {ex.Message}");
            }
        }
        if (attempted == 0)
            return;
        try { document.ForceRebuild3(false); }
        catch (Exception ex) { diagnostics.Add($"Rebuilding after direct-part resolution was best-effort: {ex.Message}"); }
        diagnostics.Add($"Resolved {resolved}/{attempted} direct part roots before mate endpoint extraction to avoid lightweight proxy geometry fingerprints.");
    }

    private static AssemblyModuleMateGraphEndpoint BuildMateGraphEndpoint(
        IModelDoc2 document,
        int index,
        MateGraphRoot owner,
        ComponentInstance leaf,
        IComponent2 component,
        object? reference,
        bool includePersistentReference = true)
    {
        int bodyIndex = -1;
        int faceIndex = -1;
        double? area = null;
        double[]? faceBoxLocal = null;
        double[]? faceCenterLocal = null;
        double[]? faceCenterWorld = null;
        double[]? faceNormalLocal = null;
        double[]? faceNormalWorld = null;
        string? surfaceType = null;
        double[]? cylinderOriginLocal = null;
        double[]? cylinderOriginWorld = null;
        double[]? cylinderAxisLocal = null;
        double[]? cylinderAxisWorld = null;
        double? cylinderRadius = null;
        string geometryType = reference switch
        {
            IFace2 => "Face",
            IEdge => "Edge",
            IVertex => "Vertex",
            null => "Unresolved",
            _ => reference.GetType().Name,
        };
        if (reference is IFace2 face)
        {
            (bodyIndex, faceIndex) = PairFindFaceIndex(component, face);
            area = PairSafeFaceArea(face);
            faceBoxLocal = ToDoubleArray(face.GetBox());
            if (faceBoxLocal is { Length: >= 6 })
            {
                faceCenterLocal =
                [
                    (faceBoxLocal[0] + faceBoxLocal[3]) / 2.0,
                    (faceBoxLocal[1] + faceBoxLocal[4]) / 2.0,
                    (faceBoxLocal[2] + faceBoxLocal[5]) / 2.0,
                ];
                faceCenterWorld = MateGraphLocalToWorld(faceCenterLocal, component);
            }

            faceNormalLocal = SelectionService.TryGetPlanarFaceNormal(face);
            if (faceNormalLocal is { Length: >= 3 })
            {
                surfaceType = "Plane";
                faceNormalWorld = MateGraphLocalToWorldVector(faceNormalLocal, component);
            }

            try
            {
                var surface = face.GetSurface() as ISurface;
                if (surface != null && surface.IsCylinder())
                {
                    var cylinder = TryParseCylinderSurfaceParameters(ToDoubleArray(surface.CylinderParams));
                    if (cylinder != null)
                    {
                        surfaceType = "Cylinder";
                        cylinderOriginLocal = cylinder.Origin;
                        cylinderOriginWorld = MateGraphLocalToWorld(cylinder.Origin, component);
                        cylinderAxisLocal = cylinder.Axis;
                        cylinderAxisWorld = MateGraphLocalToWorldVector(cylinder.Axis, component);
                        cylinderRadius = cylinder.Radius * MateGraphWorldScale(component);
                    }
                }
            }
            catch
            {
                // Imported topology and lightweight proxies can reject analytic-surface
                // queries. Keep the endpoint usable through its existing face fingerprint.
            }
        }

        string? persistent = null;
        if (includePersistentReference && reference != null)
        {
            try
            {
                var bytes = PairToByteArray(document.Extension.GetPersistReference3(reference));
                if (bytes is { Length: > 0 })
                    persistent = Convert.ToBase64String(bytes);
            }
            catch { }
        }

        return new AssemblyModuleMateGraphEndpoint(
            index,
            owner.Token,
            owner.Instance.Info.HierarchyPath,
            leaf.Info.HierarchyPath,
            PairRelativeHierarchy(leaf.Info.HierarchyPath, owner.Instance.Info.HierarchyPath),
            leaf.Info.Name,
            leaf.Info.Path,
            geometryType,
            bodyIndex,
            faceIndex,
            area,
            faceBoxLocal,
            faceCenterLocal,
            faceCenterWorld,
            faceNormalLocal,
            faceNormalWorld,
            persistent,
            surfaceType,
            cylinderOriginLocal,
            cylinderOriginWorld,
            cylinderAxisLocal,
            cylinderAxisWorld,
            cylinderRadius);
    }

    internal static MateGraphCylinderGeometry? TryParseCylinderSurfaceParameters(double[]? values)
    {
        if (values is not { Length: >= 7 })
            return null;
        if (values.Take(7).Any(value => double.IsNaN(value) || double.IsInfinity(value)))
            return null;
        var axis = MateGraphNormalize([values[3], values[4], values[5]]);
        if (axis == null || values[6] <= 0)
            return null;
        return new MateGraphCylinderGeometry(
            [values[0], values[1], values[2]],
            axis,
            values[6]);
    }

    private static double[] MateGraphLocalToWorld(double[] local, IComponent2 component)
    {
        var transform = MateGraphWorldTransform(component);
        var raw = transform?.ArrayData as double[];
        if (raw is not { Length: >= 13 })
            return [.. local];

        double scale = raw[12] == 0 ? 1.0 : raw[12];
        double x = local[0] * scale;
        double y = local[1] * scale;
        double z = local[2] * scale;
        return
        [
            raw[9] * scale + raw[0] * x + raw[3] * y + raw[6] * z,
            raw[10] * scale + raw[1] * x + raw[4] * y + raw[7] * z,
            raw[11] * scale + raw[2] * x + raw[5] * y + raw[8] * z,
        ];
    }

    private static double[]? MateGraphLocalToWorldVector(double[] local, IComponent2 component)
    {
        var transform = MateGraphWorldTransform(component);
        var raw = transform?.ArrayData as double[];
        if (raw is not { Length: >= 13 })
            return MateGraphNormalize(local);

        return MateGraphNormalize(
        [
            raw[0] * local[0] + raw[3] * local[1] + raw[6] * local[2],
            raw[1] * local[0] + raw[4] * local[1] + raw[7] * local[2],
            raw[2] * local[0] + raw[5] * local[1] + raw[8] * local[2],
        ]);
    }

    private static IMathTransform? MateGraphWorldTransform(IComponent2 component)
    {
        try { return component.GetTotalTransform(true) ?? component.Transform2; }
        catch { return component.Transform2; }
    }

    private static double MateGraphWorldScale(IComponent2 component)
    {
        try
        {
            var raw = MateGraphWorldTransform(component)?.ArrayData as double[];
            return raw is { Length: >= 13 } && Math.Abs(raw[12]) > 1e-12
                ? Math.Abs(raw[12])
                : 1.0;
        }
        catch { return 1.0; }
    }

    private static double[]? MateGraphNormalize(double[] vector)
    {
        double length = Math.Sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);
        return length < 1e-9
            ? null
            : [vector[0] / length, vector[1] / length, vector[2] / length];
    }

    private static string? MateGraphRebuildRejection(
        int entityCount,
        IReadOnlyList<AssemblyModuleMateGraphEndpoint> endpoints,
        int mateType,
        double? distance)
    {
        if (entityCount != 2)
            return $"The mate has {entityCount} entities; the pair round-trip demo requires exactly two.";
        if (endpoints.Count != 2 || endpoints.Any(endpoint => endpoint.GeometryType != "Face"))
            return "Both endpoints must resolve to faces for the current pair round-trip demo.";
        if (!IsSupportedMatePairType(mateType))
            return $"Mate type {PairMateTypeName(mateType)} is read-only in graph v1.";
        if (mateType == (int)swMateType_e.swMateDISTANCE && distance == null)
            return "Distance value could not be read.";
        return null;
    }

    private static double? MateGraphSafeAngle(IFeature feature, int mateType)
    {
        if (mateType != (int)swMateType_e.swMateANGLE)
            return null;
        try { return (feature.GetDefinition() as IAngleMateFeatureData)?.Angle; } catch { return null; }
    }

    private static bool PairSafeFeatureSuppressed(IFeature feature) { try { return feature.IsSuppressed(); } catch { return false; } }
    private static int PairSafeComponentVisibility(IComponent2 component) { try { return component.Visible; } catch { return -1; } }
    private static int MateGraphComponentSuppressionState(IComponent2 component)
    {
        try { return component.GetSuppression(); }
        catch { return -1; }
    }
    private static string MateGraphSuppressionStateName(int state) => state < 0
        ? "Unknown"
        : ((swComponentSuppressionState_e)state).ToString();

    private static long MateGraphComIdentity(object value)
    {
        IntPtr pointer = IntPtr.Zero;
        try
        {
            pointer = Marshal.GetIUnknownForObject(value);
            return pointer.ToInt64();
        }
        catch { return 0; }
        finally
        {
            if (pointer != IntPtr.Zero)
                Marshal.Release(pointer);
        }
    }

    private static AssemblyModuleMateGraphResult SaveModuleMateGraphIfRequested(
        AssemblyModuleMateGraphResult result,
        string? outputPath,
        bool saveJson)
    {
        if (!saveJson)
            return result;
        string path = Path.GetFullPath(outputPath ?? Path.Combine(
            Path.GetDirectoryName(result.SourceAssemblyPath)!,
            $"{Path.GetFileNameWithoutExtension(result.SourceAssemblyPath)}_module_mate_graph.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var saved = result with { SavedJsonPath = path };
        File.WriteAllText(path, JsonSerializer.Serialize(saved, MatePairJsonOptions));
        return saved;
    }

    private sealed record MateGraphRoot(string Token, ComponentInstance Instance);
    private sealed record MateGraphIndexedComponent(MateGraphRoot Owner, ComponentInstance Leaf);
}
