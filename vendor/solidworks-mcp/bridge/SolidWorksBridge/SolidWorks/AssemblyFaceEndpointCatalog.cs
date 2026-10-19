using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyFaceEndpointCatalogEntry(
    string EndpointId,
    string ModulePath,
    string? ModuleReferencedConfiguration,
    string? LeafReferencedConfiguration,
    string GeometryClass,
    string RecoveryConfidence,
    AssemblyModuleMateGraphEndpoint Endpoint);

public record AssemblyFaceEndpointCatalogResult(
    string SchemaVersion,
    string SourceAssemblyPath,
    IReadOnlyList<string> RequestedModuleTokens,
    int ModuleCount,
    int EndpointCount,
    bool SourceMateFacesOnly,
    bool PlanarOnly,
    double MinimumFaceArea,
    IReadOnlyList<AssemblyModuleMateGraphNode> Modules,
    IReadOnlyList<AssemblyFaceEndpointCatalogEntry> Endpoints,
    string? SavedJsonPath,
    IReadOnlyList<string> Diagnostics,
    string? CatalogMode = null,
    IReadOnlyList<string>? RequestedLeafSelectors = null);

public record AssemblyFaceEndpointSelectionResult(
    bool Success,
    string EndpointId,
    string ModuleHierarchyPath,
    string LeafHierarchyPath,
    string ResolutionStrategy,
    bool Zoomed,
    string Message);

public partial class AssemblyService
{
    /// <summary>Select one catalog endpoint in its source assembly for visual review.</summary>
    public AssemblyFaceEndpointSelectionResult SelectFaceEndpointFromCatalog(
        string catalogPath,
        string endpointId,
        bool zoomToSelection = true)
    {
        if (string.IsNullOrWhiteSpace(catalogPath))
            throw new ArgumentException("catalogPath must not be empty.", nameof(catalogPath));
        string normalizedCatalog = Path.GetFullPath(catalogPath);
        if (!File.Exists(normalizedCatalog))
            throw new FileNotFoundException($"Face endpoint catalog was not found: {normalizedCatalog}", normalizedCatalog);
        if (string.IsNullOrWhiteSpace(endpointId))
            throw new ArgumentException("endpointId must not be empty.", nameof(endpointId));
        var catalog = JsonSerializer.Deserialize<AssemblyFaceEndpointCatalogResult>(
            File.ReadAllText(normalizedCatalog, Encoding.UTF8),
            MatePairJsonOptions)
            ?? throw new InvalidOperationException("Face endpoint catalog deserialized to null.");
        if (!string.Equals(catalog.SchemaVersion, "solidworks-face-endpoint-catalog/v1", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException($"Unsupported face endpoint catalog schema: {catalog.SchemaVersion}");
        var matches = catalog.Endpoints
            .Where(item => string.Equals(item.EndpointId, endpointId.Trim(), StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (matches.Length != 1)
            throw new InvalidOperationException($"EndpointId '{endpointId}' resolved to {matches.Length} catalog entries; expected exactly one.");
        var entry = matches[0];

        _cm.EnsureConnected();
        var (assembly, document, topLevelInstances) = OpenMatePairSource(catalog.SourceAssemblyPath);
        var diagnostics = new List<string>();
        var roots = ResolveMateGraphRoots(topLevelInstances, [entry.Endpoint.ModuleToken], diagnostics);
        if (roots.Count != 1)
            throw new InvalidOperationException($"Catalog module '{entry.Endpoint.ModuleToken}' resolved to {roots.Count} source instances; expected exactly one.");
        var leaf = ResolveGraphTargetLeaf(roots[0].Instance.Component, entry.Endpoint)
            ?? throw new InvalidOperationException($"Could not resolve catalog leaf '{entry.Endpoint.RelativeLeafHierarchyPath}'.");
        var face = ResolveGraphTargetFace(leaf, entry.Endpoint, out string strategy)
            ?? throw new InvalidOperationException($"Could not resolve face for EndpointId '{entry.EndpointId}'.");
        document.ClearSelection2(true);
        var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
        selectData.Mark = 0;
        if (!((IEntity)face).Select4(false, selectData))
            throw new InvalidOperationException($"Resolved face '{entry.EndpointId}' could not be selected.");
        bool zoomed = false;
        if (zoomToSelection)
        {
            try
            {
                dynamic dynamicDocument = document;
                dynamicDocument.ViewZoomtoSelection();
                zoomed = true;
            }
            catch
            {
                try
                {
                    ((object)document).GetType().InvokeMember(
                        "ViewZoomToSelection",
                        BindingFlags.InvokeMethod | BindingFlags.Public | BindingFlags.Instance,
                        binder: null,
                        document,
                        args: null);
                    zoomed = true;
                }
                catch
                {
                    zoomed = false;
                }
            }
        }
        return new AssemblyFaceEndpointSelectionResult(
            true,
            entry.EndpointId,
            entry.Endpoint.ModuleHierarchyPath,
            entry.Endpoint.LeafHierarchyPath,
            strategy,
            zoomed,
            $"Selected catalog endpoint '{entry.EndpointId}' in the source assembly.");
    }

    /// <summary>
    /// Enumerate faces from one uniquely selected leaf component only.  This is the bounded
    /// interactive path between a small source-mate seed catalog and an unsafe whole-subtree
    /// face traversal.
    /// </summary>
    public AssemblyFaceEndpointCatalogResult BuildLeafFaceEndpointCatalog(
        string sourceAssemblyPath,
        string moduleToken,
        string leafSelector,
        string? outputPath = null,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        int maximumFaceCount = 500,
        bool saveJson = true)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);
        if (string.IsNullOrWhiteSpace(moduleToken))
            throw new ArgumentException("moduleToken must not be empty.", nameof(moduleToken));
        if (string.IsNullOrWhiteSpace(leafSelector))
            throw new ArgumentException("leafSelector must not be empty.", nameof(leafSelector));
        if (!double.IsFinite(minimumFaceArea) || minimumFaceArea < 0)
            throw new ArgumentOutOfRangeException(nameof(minimumFaceArea));
        if (maximumFaceCount <= 0)
            throw new ArgumentOutOfRangeException(nameof(maximumFaceCount));

        string token = moduleToken.Trim();
        string selector = leafSelector.Trim();
        var diagnostics = new List<string>();
        var (assembly, document, topLevelInstances) = OpenMatePairSource(sourceAssemblyPath);
        var roots = ResolveMateGraphRoots(topLevelInstances, [token], diagnostics);
        var root = ResolveCatalogModuleRoot(roots, token, selector, diagnostics);
        try { root.Instance.Component.SetSuppression2((int)swComponentSuppressionState_e.swComponentFullyResolved); }
        catch (Exception ex) { diagnostics.Add($"Resolving module root was best-effort: {ex.Message}"); }

        var component = ResolveCatalogLeafComponent(root.Instance.Component, selector, out string leafHierarchy, out string relativeHierarchy);
        try { component.SetSuppression2((int)swComponentSuppressionState_e.swComponentFullyResolved); }
        catch (Exception ex) { diagnostics.Add($"Resolving selected leaf was best-effort: {ex.Message}"); }
        document.ForceRebuild3(false);

        int suppressionState = MateGraphComponentSuppressionState(root.Instance.Component);
        var module = new AssemblyModuleMateGraphNode(
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
        var leaf = new ComponentInstance(
            component,
            new ComponentInstanceInfo(
                leafHierarchy.Split('/').LastOrDefault() ?? leafHierarchy,
                component.GetPathName() ?? string.Empty,
                leafHierarchy,
                leafHierarchy.Count(character => character == '/')));

        object bodyInfo;
        var bodies = (component.GetBodies3((int)swBodyType_e.swAllBodies, out bodyInfo) as object[] ?? [])
            .OfType<IBody2>()
            .ToArray();
        var indexedFaces = new List<(int BodyIndex, int FaceIndex, IFace2 Face)>();
        for (int bodyIndex = 0; bodyIndex < bodies.Length; bodyIndex++)
        {
            var faces = (bodies[bodyIndex].GetFaces() as object[] ?? []).OfType<IFace2>().ToArray();
            for (int faceIndex = 0; faceIndex < faces.Length; faceIndex++)
            {
                indexedFaces.Add((bodyIndex, faceIndex, faces[faceIndex]));
                if (indexedFaces.Count > maximumFaceCount)
                    throw new InvalidOperationException(
                        $"Leaf '{relativeHierarchy}' exposes more than maximumFaceCount={maximumFaceCount} faces; narrow the leaf or raise the explicit safety limit.");
            }
        }

        string? moduleConfiguration = SafeReferencedConfiguration(root.Instance.Component);
        string? leafConfiguration = SafeReferencedConfiguration(component);
        var entries = new List<AssemblyFaceEndpointCatalogEntry>();
        foreach (var indexed in indexedFaces)
        {
            double area = PairSafeFaceArea(indexed.Face);
            if (area < minimumFaceArea)
                continue;
            var normal = SelectionService.TryGetPlanarFaceNormal(indexed.Face);
            if (planarOnly && normal == null)
                continue;
            var endpoint = BuildMateGraphEndpoint(document, 0, root, leaf, component, indexed.Face);
            // Preserve the enumeration indices explicitly; these are also verified by the
            // geometric fingerprint during reconstruction.
            endpoint = endpoint with { BodyIndex = indexed.BodyIndex, FaceIndexInBody = indexed.FaceIndex };
            string geometryClass = normal == null ? "Surface" : "Plane";
            entries.Add(new AssemblyFaceEndpointCatalogEntry(
                BuildFaceEndpointId(endpoint, moduleConfiguration, leafConfiguration, geometryClass),
                root.Instance.Info.Path,
                moduleConfiguration,
                leafConfiguration,
                geometryClass,
                endpoint.SourceAssemblyPersistentReferenceBase64 == null
                    ? "LEAF_SCOPED_CONFIGURATION_INDEX_PLUS_FINGERPRINT"
                    : "LEAF_SCOPED_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
                endpoint));
        }

        var unique = entries
            .GroupBy(item => item.EndpointId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderByDescending(item => item.Endpoint.FaceArea ?? 0)
            .ThenBy(item => item.Endpoint.BodyIndex)
            .ThenBy(item => item.Endpoint.FaceIndexInBody)
            .ToArray();
        diagnostics.Add($"Leaf-scoped scan resolved '{selector}' to '{relativeHierarchy}' and inspected {indexedFaces.Count} faces across {bodies.Length} solid bodies.");
        diagnostics.Add($"Accepted {unique.Length} faces after planarOnly={planarOnly} and minimumFaceArea={minimumFaceArea.ToString("R", CultureInfo.InvariantCulture)} filters.");
        diagnostics.Add("No sibling leaf faces or other module subtrees were enumerated.");
        diagnostics.Add("EndpointId is stable for the same file, referenced configuration and topology; it is not claimed stable after topology-changing edits.");

        var result = new AssemblyFaceEndpointCatalogResult(
            "solidworks-face-endpoint-catalog/v1",
            Path.GetFullPath(sourceAssemblyPath),
            [token],
            1,
            unique.Length,
            false,
            planarOnly,
            minimumFaceArea,
            [module],
            unique,
            null,
            diagnostics.AsReadOnly(),
            "leaf_scoped",
            [selector]);
        if (!saveJson)
            return result;
        string path = Path.GetFullPath(outputPath ?? Path.Combine(
            Path.GetDirectoryName(result.SourceAssemblyPath)!,
            $"{Path.GetFileNameWithoutExtension(result.SourceAssemblyPath)}_{SanitizeCatalogFileToken(selector)}_face_endpoint_catalog.json"));
        if (File.Exists(path))
            throw new IOException($"Refusing to overwrite an existing face endpoint catalog: {path}");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var saved = result with { SavedJsonPath = path };
        File.WriteAllText(path, JsonSerializer.Serialize(saved, MatePairJsonOptions));
        return saved;
    }

    /// <summary>
    /// Convert the first face selected in the active assembly into one catalog entry. This is the
    /// bounded escape hatch for useful faces omitted by the fast source-mate seed catalog.
    /// </summary>
    public AssemblyFaceEndpointCatalogEntry CaptureSelectedFaceEndpoint(string moduleToken)
    {
        if (string.IsNullOrWhiteSpace(moduleToken))
            throw new ArgumentException("moduleToken must not be empty.", nameof(moduleToken));
        _cm.EnsureConnected();
        var assembly = GetAssemblyDoc();
        var document = (IModelDoc2)assembly;
        var selection = document.ISelectionManager
            ?? throw new InvalidOperationException("Selection manager is unavailable.");
        IFace2? face = null;
        IComponent2? leafComponent = null;
        for (int index = 1; index <= selection.GetSelectedObjectCount2(-1); index++)
        {
            if (selection.GetSelectedObjectType3(index, -1) != (int)swSelectType_e.swSelFACES)
                continue;
            face = selection.GetSelectedObject6(index, -1) as IFace2;
            leafComponent = selection.GetSelectedObjectsComponent3(index, -1) as IComponent2;
            if (face != null)
                break;
        }
        if (face == null || leafComponent == null)
            throw new InvalidOperationException("Select one component face in the active assembly first.");

        var diagnostics = new List<string>();
        var roots = ResolveMateGraphRoots(PairEnumerateTopLevelInstances(assembly), [moduleToken.Trim()], diagnostics);
        if (roots.Count != 1)
            throw new InvalidOperationException($"Module token '{moduleToken}' resolved to {roots.Count} top-level instances; expected exactly one.");
        var root = roots[0];
        string leafHierarchy = leafComponent.Name2 ?? string.Empty;
        if (!string.Equals(leafHierarchy, root.Instance.Info.HierarchyPath, StringComparison.OrdinalIgnoreCase)
            && !leafHierarchy.StartsWith(root.Instance.Info.HierarchyPath + "/", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException($"The selected face is not inside module '{root.Instance.Info.HierarchyPath}'.");
        var leaf = new ComponentInstance(
            leafComponent,
            new ComponentInstanceInfo(
                leafHierarchy.Split('/').LastOrDefault() ?? leafHierarchy,
                leafComponent.GetPathName() ?? string.Empty,
                leafHierarchy,
                leafHierarchy.Count(character => character == '/')));
        var endpoint = BuildMateGraphEndpoint(document, 0, root, leaf, leafComponent, face);
        var normal = SelectionService.TryGetPlanarFaceNormal(face);
        string geometryClass = normal == null ? "Surface" : "Plane";
        string? moduleConfiguration = SafeReferencedConfiguration(root.Instance.Component);
        string? leafConfiguration = SafeReferencedConfiguration(leafComponent);
        return new AssemblyFaceEndpointCatalogEntry(
            BuildFaceEndpointId(endpoint, moduleConfiguration, leafConfiguration, geometryClass),
            root.Instance.Info.Path,
            moduleConfiguration,
            leafConfiguration,
            geometryClass,
            endpoint.SourceAssemblyPersistentReferenceBase64 == null
                ? "SELECTED_FACE_CONFIGURATION_INDEX_PLUS_FINGERPRINT"
                : "SELECTED_FACE_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
            endpoint);
    }

    /// <summary>
    /// Enumerate stable, module-local face endpoint descriptors. The catalog is deliberately
    /// separate from the mate graph so a new mate can reference faces that had no source mate.
    /// </summary>
    public AssemblyFaceEndpointCatalogResult BuildFaceEndpointCatalog(
        string sourceAssemblyPath,
        IReadOnlyList<string> moduleTokens,
        string? outputPath = null,
        bool sourceMateFacesOnly = true,
        bool planarOnly = true,
        double minimumFaceArea = 1e-8,
        bool saveJson = true)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);
        if (moduleTokens == null || moduleTokens.Count == 0)
            throw new ArgumentException("At least one module token is required.", nameof(moduleTokens));
        if (!double.IsFinite(minimumFaceArea) || minimumFaceArea < 0)
            throw new ArgumentOutOfRangeException(nameof(minimumFaceArea));

        var tokens = moduleTokens
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var diagnostics = new List<string>();
        var (assembly, document, topLevelInstances) = OpenMatePairSource(sourceAssemblyPath);
        if (!sourceMateFacesOnly)
        {
            try { assembly.ResolveAllLightWeightComponents(true); }
            catch (Exception ex) { diagnostics.Add($"ResolveAllLightWeightComponents was best-effort: {ex.Message}"); }
        }
        var roots = ResolveMateGraphRoots(topLevelInstances, tokens, diagnostics);
        var modules = roots.Select(root =>
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
                SafeReferencedConfiguration(root.Instance.Component));
        }).OrderBy(item => item.ModuleToken, StringComparer.OrdinalIgnoreCase).ToArray();

        var entries = new List<AssemblyFaceEndpointCatalogEntry>();
        if (sourceMateFacesOnly)
        {
            var sourceGraph = ExportModuleMateGraph(sourceAssemblyPath, tokens, saveJson: false);
            var moduleByHierarchy = sourceGraph.Modules.ToDictionary(item => item.HierarchyPath, StringComparer.OrdinalIgnoreCase);
            foreach (var endpoint in sourceGraph.Mates.SelectMany(item => item.Endpoints).Where(item => item.GeometryType == "Face"))
            {
                if (endpoint.FaceArea is double area && area < minimumFaceArea)
                    continue;
                if (planarOnly && endpoint.FaceNormalLocal == null)
                    continue;
                if (!moduleByHierarchy.TryGetValue(endpoint.ModuleHierarchyPath, out var module))
                    continue;
                string endpointId = BuildFaceEndpointId(endpoint, module.ReferencedConfiguration, null, "Plane");
                entries.Add(new AssemblyFaceEndpointCatalogEntry(
                    endpointId,
                    module.Path,
                    module.ReferencedConfiguration,
                    null,
                    "Plane",
                    endpoint.SourceAssemblyPersistentReferenceBase64 == null
                        ? "CONFIGURATION_INDEX_PLUS_GEOMETRIC_FINGERPRINT"
                        : "SOURCE_MATE_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
                    endpoint));
            }
            diagnostics.Add("Seed mode indexed faces already referenced by source mates; arbitrary new faces should be added later by leaf-scoped or selected-face capture.");
        }
        else
        {
            foreach (var root in roots)
            {
                var components = new List<IComponent2> { root.Instance.Component };
                CatalogTraverseComponents(root.Instance.Component, components);
                foreach (var component in components)
                {
                    string hierarchy = component.Name2 ?? root.Instance.Info.HierarchyPath;
                    var leaf = new ComponentInstance(
                        component,
                        new ComponentInstanceInfo(
                            hierarchy.Split('/').LastOrDefault() ?? hierarchy,
                            component.GetPathName() ?? string.Empty,
                            hierarchy,
                            hierarchy.Count(character => character == '/')));
                    object bodyInfo;
                    var bodies = (component.GetBodies3((int)swBodyType_e.swAllBodies, out bodyInfo) as object[] ?? [])
                        .OfType<IBody2>()
                        .ToArray();
                    foreach (var body in bodies)
                    {
                        foreach (var face in (body.GetFaces() as object[] ?? []).OfType<IFace2>())
                        {
                            double area = PairSafeFaceArea(face);
                            if (area < minimumFaceArea)
                                continue;
                            var normal = SelectionService.TryGetPlanarFaceNormal(face);
                            if (planarOnly && normal == null)
                                continue;
                            var endpoint = BuildMateGraphEndpoint(document, 0, root, leaf, component, face, includePersistentReference: false);
                            string geometryClass = normal == null ? "Surface" : "Plane";
                            string? leafConfiguration = SafeReferencedConfiguration(component);
                            string endpointId = BuildFaceEndpointId(
                                endpoint,
                                SafeReferencedConfiguration(root.Instance.Component),
                                leafConfiguration,
                                geometryClass);
                            entries.Add(new AssemblyFaceEndpointCatalogEntry(
                                endpointId,
                                root.Instance.Info.Path,
                                SafeReferencedConfiguration(root.Instance.Component),
                                leafConfiguration,
                                geometryClass,
                                "CONFIGURATION_INDEX_PLUS_GEOMETRIC_FINGERPRINT",
                                endpoint));
                        }
                    }
                }
            }
        }

        var unique = entries
            .GroupBy(item => item.EndpointId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderBy(item => item.Endpoint.ModuleToken, StringComparer.OrdinalIgnoreCase)
            .ThenBy(item => item.Endpoint.RelativeLeafHierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ThenBy(item => item.Endpoint.BodyIndex)
            .ThenBy(item => item.Endpoint.FaceIndexInBody)
            .ToArray();
        if (unique.Length != entries.Count)
            diagnostics.Add($"Collapsed {entries.Count - unique.Length} duplicate endpoint identifiers.");
        diagnostics.Add("EndpointId is stable for the same file, referenced configuration and topology; it is not claimed stable after topology-changing edits.");

        var result = new AssemblyFaceEndpointCatalogResult(
            "solidworks-face-endpoint-catalog/v1",
            Path.GetFullPath(sourceAssemblyPath),
            tokens,
            modules.Length,
            unique.Length,
            sourceMateFacesOnly,
            planarOnly,
            minimumFaceArea,
            modules,
            unique,
            null,
            diagnostics.AsReadOnly());
        if (!saveJson)
            return result;
        string path = Path.GetFullPath(outputPath ?? Path.Combine(
            Path.GetDirectoryName(result.SourceAssemblyPath)!,
            $"{Path.GetFileNameWithoutExtension(result.SourceAssemblyPath)}_face_endpoint_catalog.json"));
        if (File.Exists(path))
            throw new IOException($"Refusing to overwrite an existing face endpoint catalog: {path}");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var saved = result with { SavedJsonPath = path };
        File.WriteAllText(path, JsonSerializer.Serialize(saved, MatePairJsonOptions));
        return saved;
    }

    private static void CatalogTraverseComponents(IComponent2 parent, ICollection<IComponent2> results)
    {
        foreach (var child in (parent.GetChildren() as object[] ?? []).OfType<IComponent2>())
        {
            results.Add(child);
            CatalogTraverseComponents(child, results);
        }
    }

    private static MateGraphRoot ResolveCatalogModuleRoot(
        IReadOnlyList<MateGraphRoot> roots,
        string moduleToken,
        string leafSelector,
        ICollection<string> diagnostics)
    {
        if (roots.Count == 1)
            return roots[0];

        // Duplicate top-level instances (Project 02 has two T401 parts) must be addressable
        // without scanning either sibling.  An exact top-level hierarchy/name selector wins;
        // file-stem matching is deliberately excluded because both T401 instances share a file.
        var exact = roots.Where(root =>
            string.Equals(root.Instance.Info.HierarchyPath, leafSelector, StringComparison.OrdinalIgnoreCase)
            || string.Equals(root.Instance.Info.Name, leafSelector, StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (exact.Length == 1)
        {
            diagnostics.Add(
                $"Module token '{moduleToken}' matched {roots.Count} roots; exact top-level selector '{leafSelector}' selected '{exact[0].Instance.Info.HierarchyPath}'.");
            return exact[0];
        }

        string preview = string.Join(", ", roots.Select(root => root.Instance.Info.HierarchyPath));
        throw new InvalidOperationException(
            $"Module token '{moduleToken}' resolved to {roots.Count} top-level instances. "
            + $"Leaf selector '{leafSelector}' matched {exact.Length} roots; use one exact top-level instance name. Candidates: {preview}");
    }

    private static IComponent2 ResolveCatalogLeafComponent(
        IComponent2 moduleRoot,
        string selector,
        out string hierarchyPath,
        out string relativeHierarchyPath)
    {
        string rootHierarchy = moduleRoot.Name2 ?? string.Empty;
        var components = new List<IComponent2> { moduleRoot };
        CatalogTraverseComponents(moduleRoot, components);
        var candidates = components.Select(component =>
        {
            string hierarchy = component.Name2 ?? string.Empty;
            string relative = hierarchy.StartsWith(rootHierarchy + "/", StringComparison.OrdinalIgnoreCase)
                ? hierarchy[(rootHierarchy.Length + 1)..]
                : string.Equals(hierarchy, rootHierarchy, StringComparison.OrdinalIgnoreCase) ? string.Empty : hierarchy;
            string leafName = hierarchy.Split('/').LastOrDefault() ?? hierarchy;
            string fileStem = Path.GetFileNameWithoutExtension(component.GetPathName() ?? string.Empty);
            return new { Component = component, Hierarchy = hierarchy, Relative = relative, LeafName = leafName, FileStem = fileStem };
        }).ToArray();
        var exact = candidates.Where(item =>
            string.Equals(item.Hierarchy, selector, StringComparison.OrdinalIgnoreCase)
            || string.Equals(item.Relative, selector, StringComparison.OrdinalIgnoreCase)
            || string.Equals(item.LeafName, selector, StringComparison.OrdinalIgnoreCase)
            || string.Equals(item.FileStem, selector, StringComparison.OrdinalIgnoreCase)).ToArray();
        var matches = exact.Length > 0 ? exact : candidates.Where(item =>
            item.Relative.Contains(selector, StringComparison.OrdinalIgnoreCase)
            || item.LeafName.Contains(selector, StringComparison.OrdinalIgnoreCase)
            || item.FileStem.Contains(selector, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (matches.Length != 1)
        {
            string preview = string.Join(", ", matches.Take(8).Select(item => item.Relative));
            throw new InvalidOperationException(
                $"Leaf selector '{selector}' resolved to {matches.Length} components inside '{rootHierarchy}'; expected exactly one.{(preview.Length == 0 ? string.Empty : $" Matches: {preview}")}");
        }
        hierarchyPath = matches[0].Hierarchy;
        relativeHierarchyPath = matches[0].Relative;
        return matches[0].Component;
    }

    private static string SanitizeCatalogFileToken(string value)
    {
        var invalid = Path.GetInvalidFileNameChars().ToHashSet();
        return new string(value.Select(character => invalid.Contains(character) ? '_' : character).ToArray());
    }

    internal static string BuildFaceEndpointId(
        AssemblyModuleMateGraphEndpoint endpoint,
        string? moduleConfiguration,
        string? leafConfiguration,
        string geometryClass)
    {
        static string Values(double[]? values) => values == null
            ? string.Empty
            : string.Join(",", values.Select(value => value.ToString("R", CultureInfo.InvariantCulture)));
        string payload = string.Join("|", new[]
        {
            endpoint.ModuleHierarchyPath,
            moduleConfiguration ?? string.Empty,
            endpoint.RelativeLeafHierarchyPath,
            endpoint.LeafComponentPath,
            leafConfiguration ?? string.Empty,
            endpoint.BodyIndex.ToString(CultureInfo.InvariantCulture),
            endpoint.FaceIndexInBody.ToString(CultureInfo.InvariantCulture),
            endpoint.FaceArea?.ToString("R", CultureInfo.InvariantCulture) ?? string.Empty,
            Values(endpoint.FaceCenterLocal),
            Values(endpoint.FaceNormalLocal),
            geometryClass,
        });
        string digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
        return $"face:{endpoint.ModuleToken.ToLowerInvariant()}:{digest[..16]}";
    }
}
