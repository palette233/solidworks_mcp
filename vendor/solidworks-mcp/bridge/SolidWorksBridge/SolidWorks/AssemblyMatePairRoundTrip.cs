using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyMatePairModuleInfo(
    string Name,
    string Path,
    string HierarchyPath,
    double[]? SourceTransform);

public record AssemblyMatePairEndpointInfo(
    int Index,
    string ModuleHierarchyPath,
    string LeafHierarchyPath,
    string RelativeLeafHierarchyPath,
    string LeafComponentName,
    string LeafComponentPath,
    string GeometryType,
    int BodyIndex,
    int FaceIndexInBody,
    double Area,
    string? SourceAssemblyPersistentReferenceBase64);

public record AssemblyMatePairMateInfo(
    string MateName,
    int MateType,
    string MateTypeName,
    int Alignment,
    string AlignmentName,
    double? Distance,
    bool CanRebuild,
    string? RejectionReason,
    IReadOnlyList<AssemblyMatePairEndpointInfo> Endpoints);

public record AssemblyMatePairExportResult(
    string SourceAssemblyPath,
    string RequestedFirstModuleSelector,
    string RequestedSecondModuleSelector,
    AssemblyMatePairModuleInfo? FirstModule,
    AssemblyMatePairModuleInfo? SecondModule,
    int DirectMateCount,
    int RebuildableMateCount,
    IReadOnlyList<AssemblyMatePairMateInfo> Mates,
    string? SavedJsonPath,
    IReadOnlyList<string> Diagnostics);

public record AssemblyMatePairCandidateInfo(
    string FirstModuleHierarchyPath,
    string SecondModuleHierarchyPath,
    int DirectMateCount,
    int RebuildableMateCount,
    int Score,
    IReadOnlyList<string> MateNames,
    IReadOnlyList<string> MateTypes);

public record AssemblyMatePairCandidateResult(
    string SourceAssemblyPath,
    int CandidateCount,
    IReadOnlyList<AssemblyMatePairCandidateInfo> Candidates,
    IReadOnlyList<string> Diagnostics);

public record AssemblyMatePairRebuildItemResult(
    string MateName,
    int MateType,
    string MateTypeName,
    bool Success,
    int ErrorStatus,
    string ErrorName,
    string Message,
    IReadOnlyList<string> EndpointResolutionStrategies);

public record AssemblyMatePairVerificationResult(
    bool Reopened,
    int ExpectedMateCount,
    int ObservedMateCount,
    bool MateCountMatches,
    bool MateTypeMultisetMatches,
    IReadOnlyList<string> ExpectedMateTypes,
    IReadOnlyList<string> ObservedMateTypes,
    IReadOnlyList<string> Diagnostics);

public record AssemblyMatePairRoundTripResult(
    bool Success,
    bool UsedAutomaticFallback,
    string SourceAssemblyPath,
    string OutputAssemblyPath,
    string ExportJsonPath,
    AssemblyMatePairExportResult Export,
    IReadOnlyList<AssemblyMatePairRebuildItemResult> RebuildResults,
    AssemblyMatePairVerificationResult Verification,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    private static readonly string[] DefaultProject02MateModuleTokens =
    [
        "A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401"
    ];

    private static readonly JsonSerializerOptions MatePairJsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public AssemblyMatePairExportResult ExportMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string? outputPath = null,
        bool saveJson = true)
    {
        ValidateMatePairSourceArguments(sourceAssemblyPath, firstModuleSelector, secondModuleSelector);
        var diagnostics = new List<string>();
        var (assembly, document, roots) = OpenMatePairSource(sourceAssemblyPath);
        var first = ResolveMatePairModule(roots, firstModuleSelector);
        var second = ResolveMatePairModule(roots, secondModuleSelector);
        if (first == null || second == null)
        {
            if (first == null)
                diagnostics.Add($"First module selector '{firstModuleSelector}' did not resolve to one top-level component.");
            if (second == null)
                diagnostics.Add($"Second module selector '{secondModuleSelector}' did not resolve to one top-level component.");

            return SaveMatePairExportIfRequested(new AssemblyMatePairExportResult(
                Path.GetFullPath(sourceAssemblyPath),
                firstModuleSelector,
                secondModuleSelector,
                first == null ? null : ToMatePairModule(first),
                second == null ? null : ToMatePairModule(second),
                0,
                0,
                Array.Empty<AssemblyMatePairMateInfo>(),
                null,
                diagnostics.AsReadOnly()), outputPath, saveJson);
        }

        if (string.Equals(first.Info.HierarchyPath, second.Info.HierarchyPath, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("The two module selectors resolved to the same top-level component.");

        var pairInstances = PairEnumerateModuleSubtrees([first, second]);
        var mates = EnumeratePairMates(document, pairInstances, first, second, diagnostics);
        var result = new AssemblyMatePairExportResult(
            Path.GetFullPath(sourceAssemblyPath),
            firstModuleSelector,
            secondModuleSelector,
            ToMatePairModule(first),
            ToMatePairModule(second),
            mates.Count,
            mates.Count(mate => mate.CanRebuild),
            mates.AsReadOnly(),
            null,
            diagnostics.AsReadOnly());
        return SaveMatePairExportIfRequested(result, outputPath, saveJson);
    }

    public AssemblyMatePairCandidateResult FindMatePairCandidates(
        string sourceAssemblyPath,
        IReadOnlyList<string>? allowedModuleTokens = null,
        int maxResults = 10)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);
        if (maxResults < 1)
            throw new ArgumentOutOfRangeException(nameof(maxResults), "maxResults must be at least 1.");

        var diagnostics = new List<string>();
        var (_, document, topLevelInstances) = OpenMatePairSource(sourceAssemblyPath);
        var tokens = allowedModuleTokens is { Count: > 0 }
            ? allowedModuleTokens.Where(token => !string.IsNullOrWhiteSpace(token)).ToArray()
            : DefaultProject02MateModuleTokens;
        var roots = topLevelInstances
            .Where(instance => tokens.Any(token => PairContains(instance.Info, token)))
            .OrderBy(instance => instance.Info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToList();
        var moduleInstances = PairEnumerateModuleSubtrees(roots);

        var candidates = new List<AssemblyMatePairCandidateInfo>();
        var groupedMates = EnumerateCandidatePairMates(document, moduleInstances, roots);
        foreach (var group in groupedMates.Values)
        {
            var mates = group.Mates;
            int rebuildable = mates.Count(mate => mate.CanRebuild);
            if (rebuildable == 0)
                continue;

            // Prefer a small, demonstrable set of basic mates. More than three direct mates is
            // still valid, but less suitable for the first face-identity round-trip demo.
            int mateCountPenalty = Math.Abs(rebuildable - 2) * 20 + Math.Max(0, mates.Count - 3) * 15;
            int simpleMateBonus = mates.Count(mate => mate.MateType is
                (int)swMateType_e.swMateCOINCIDENT or
                (int)swMateType_e.swMatePARALLEL or
                (int)swMateType_e.swMateDISTANCE) * 10;
            int score = 200 + rebuildable * 30 + simpleMateBonus - mateCountPenalty;
            candidates.Add(new AssemblyMatePairCandidateInfo(
                group.First.Info.HierarchyPath,
                group.Second.Info.HierarchyPath,
                mates.Count,
                rebuildable,
                score,
                mates.Select(mate => mate.MateName).ToArray(),
                mates.Select(mate => mate.MateTypeName).ToArray()));
        }

        var ranked = candidates
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => candidate.RebuildableMateCount)
            .ThenBy(candidate => candidate.FirstModuleHierarchyPath, StringComparer.OrdinalIgnoreCase)
            .Take(maxResults)
            .ToList();
        if (ranked.Count == 0)
            diagnostics.Add("No pair of allowed top-level modules has a directly rebuildable two-face basic mate.");

        return new AssemblyMatePairCandidateResult(
            Path.GetFullPath(sourceAssemblyPath),
            ranked.Count,
            ranked.AsReadOnly(),
            diagnostics.AsReadOnly());
    }

    public AssemblyMatePairRoundTripResult RoundTripMatePair(
        string sourceAssemblyPath,
        string firstModuleSelector,
        string secondModuleSelector,
        string outputAssemblyPath,
        string? exportJsonPath = null,
        bool allowAutomaticFallback = true,
        IReadOnlyList<string>? allowedModuleTokens = null)
    {
        ValidateMatePairSourceArguments(sourceAssemblyPath, firstModuleSelector, secondModuleSelector);
        if (string.IsNullOrWhiteSpace(outputAssemblyPath))
            throw new ArgumentException("outputAssemblyPath must not be empty.", nameof(outputAssemblyPath));
        string normalizedOutput = Path.GetFullPath(outputAssemblyPath);
        if (!string.Equals(Path.GetExtension(normalizedOutput), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("outputAssemblyPath must end in .SLDASM.", nameof(outputAssemblyPath));
        if (File.Exists(normalizedOutput))
            throw new IOException($"Refusing to overwrite an existing round-trip assembly: {normalizedOutput}");

        string normalizedJson = Path.GetFullPath(exportJsonPath ?? Path.ChangeExtension(normalizedOutput, ".mates.json"));
        if (File.Exists(normalizedJson))
            throw new IOException($"Refusing to overwrite an existing mate export: {normalizedJson}");

        var diagnostics = new List<string>();
        bool usedFallback = false;
        var export = ExportMatePair(sourceAssemblyPath, firstModuleSelector, secondModuleSelector, normalizedJson, saveJson: true);
        if (export.RebuildableMateCount == 0 && allowAutomaticFallback)
        {
            var candidates = FindMatePairCandidates(sourceAssemblyPath, allowedModuleTokens, maxResults: 10);
            var best = candidates.Candidates.FirstOrDefault();
            if (best != null)
            {
                usedFallback = true;
                diagnostics.Add($"Preferred pair had no rebuildable direct face mate; selected fallback pair '{best.FirstModuleHierarchyPath}' + '{best.SecondModuleHierarchyPath}'.");
                if (File.Exists(normalizedJson))
                    File.Delete(normalizedJson);
                export = ExportMatePair(sourceAssemblyPath, best.FirstModuleHierarchyPath, best.SecondModuleHierarchyPath, normalizedJson, saveJson: true);
            }
        }

        if (export.FirstModule == null || export.SecondModule == null || export.RebuildableMateCount == 0)
        {
            var failedVerification = new AssemblyMatePairVerificationResult(false, 0, 0, false, false, [], [], ["No rebuildable mate was exported."]);
            return new AssemblyMatePairRoundTripResult(false, usedFallback, Path.GetFullPath(sourceAssemblyPath), normalizedOutput, normalizedJson, export, [], failedVerification, diagnostics.AsReadOnly());
        }

        var rebuildableMates = export.Mates.Where(mate => mate.CanRebuild).ToList();
        Directory.CreateDirectory(Path.GetDirectoryName(normalizedOutput)!);
        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        string template = sw.GetDefaultTemplatePath(SwDocType.Assembly);
        sw.NewDoc(template);
        var targetAssembly = GetAssemblyDoc();
        var targetDocument = (IModelDoc2)targetAssembly;

        var firstInserted = InsertPairModule(targetAssembly, export.FirstModule);
        var secondInserted = InsertPairModule(targetAssembly, export.SecondModule);
        ApplyPairSourceTransform(firstInserted, export.FirstModule.SourceTransform);
        ApplyPairSourceTransform(secondInserted, export.SecondModule.SourceTransform);
        targetDocument.ForceRebuild3(false);

        var rebuildResults = new List<AssemblyMatePairRebuildItemResult>();
        foreach (var mate in rebuildableMates)
            rebuildResults.Add(RebuildPairMate(targetDocument, targetAssembly, firstInserted, secondInserted, export, mate));

        targetDocument.ForceRebuild3(false);
        var save = sw.SaveDocAs(normalizedOutput, sourcePath: null, saveAsCopy: false);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");

        string firstTargetName = firstInserted.Name2 ?? Path.GetFileNameWithoutExtension(export.FirstModule.Path);
        string secondTargetName = secondInserted.Name2 ?? Path.GetFileNameWithoutExtension(export.SecondModule.Path);
        try
        {
            sw.CloseDoc(normalizedOutput);
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Close before verification was best-effort and returned: {ex.Message}");
        }

        AssemblyMatePairVerificationResult verification;
        try
        {
            sw.OpenDoc(normalizedOutput);
            sw.ActivateDoc(normalizedOutput);
            var observed = ExportMatePair(normalizedOutput, firstTargetName, secondTargetName, saveJson: false);
            var expectedTypes = rebuildResults.Where(result => result.Success).Select(result => result.MateTypeName).OrderBy(value => value).ToArray();
            var observedTypes = observed.Mates.Where(mate => mate.CanRebuild).Select(mate => mate.MateTypeName).OrderBy(value => value).ToArray();
            bool countMatches = observed.RebuildableMateCount == expectedTypes.Length;
            bool typesMatch = expectedTypes.SequenceEqual(observedTypes, StringComparer.OrdinalIgnoreCase);
            verification = new AssemblyMatePairVerificationResult(
                true,
                expectedTypes.Length,
                observed.RebuildableMateCount,
                countMatches,
                typesMatch,
                expectedTypes,
                observedTypes,
                observed.Diagnostics);
        }
        catch (Exception ex)
        {
            verification = new AssemblyMatePairVerificationResult(false, rebuildResults.Count(result => result.Success), 0, false, false, [], [], [$"Reopen verification failed: {ex.Message}"]);
        }

        bool success = rebuildResults.Count == rebuildableMates.Count
            && rebuildResults.All(result => result.Success)
            && verification.Reopened
            && verification.MateCountMatches
            && verification.MateTypeMultisetMatches
            && File.Exists(normalizedOutput)
            && File.Exists(normalizedJson);
        return new AssemblyMatePairRoundTripResult(
            success,
            usedFallback,
            Path.GetFullPath(sourceAssemblyPath),
            normalizedOutput,
            normalizedJson,
            export,
            rebuildResults.AsReadOnly(),
            verification,
            diagnostics.AsReadOnly());
    }

    internal static bool IsSupportedMatePairType(int mateType) => mateType is
        (int)swMateType_e.swMateCOINCIDENT or
        (int)swMateType_e.swMateCONCENTRIC or
        (int)swMateType_e.swMatePARALLEL or
        (int)swMateType_e.swMateDISTANCE;

    internal static string CanonicalMatePairKey(string first, string second) =>
        string.Compare(first, second, StringComparison.OrdinalIgnoreCase) <= 0
            ? $"{first}|{second}"
            : $"{second}|{first}";

    private static void ValidateMatePairSourceArguments(string sourceAssemblyPath, string firstModuleSelector, string secondModuleSelector)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);
        if (string.IsNullOrWhiteSpace(firstModuleSelector))
            throw new ArgumentException("firstModuleSelector must not be empty.", nameof(firstModuleSelector));
        if (string.IsNullOrWhiteSpace(secondModuleSelector))
            throw new ArgumentException("secondModuleSelector must not be empty.", nameof(secondModuleSelector));
    }

    private (IAssemblyDoc Assembly, IModelDoc2 Document, IReadOnlyList<ComponentInstance> Instances) OpenMatePairSource(string sourceAssemblyPath)
    {
        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        string path = Path.GetFullPath(sourceAssemblyPath);
        var active = sw.IActiveDoc2 as IModelDoc2;
        string activePath = active?.GetPathName() ?? string.Empty;
        if (active == null
            || string.IsNullOrWhiteSpace(activePath)
            || !string.Equals(Path.GetFullPath(activePath), path, StringComparison.OrdinalIgnoreCase))
        {
            sw.OpenDoc(path);
            sw.ActivateDoc(path);
        }
        var assembly = GetAssemblyDoc();
        return (assembly, (IModelDoc2)assembly, PairEnumerateTopLevelInstances(assembly));
    }

    private static IReadOnlyList<ComponentInstance> PairEnumerateTopLevelInstances(IAssemblyDoc assembly)
    {
        var roots = (assembly.GetComponents(true) as object[] ?? [])
            .OfType<IComponent2>()
            .Select(component =>
            {
                string name = component.Name2 ?? "Component";
                return new ComponentInstance(
                    component,
                    new ComponentInstanceInfo(name, component.GetPathName() ?? string.Empty, name, 0));
            })
            .ToList();
        return roots.AsReadOnly();
    }

    private static IReadOnlyList<ComponentInstance> PairEnumerateModuleSubtrees(IReadOnlyList<ComponentInstance> roots)
    {
        var results = new List<ComponentInstance>();
        foreach (var root in roots)
        {
            results.Add(root);
            PairTraverseModuleSubtree(root.Component, root.Info.HierarchyPath, root.Info.Depth, results);
        }
        return results.AsReadOnly();
    }

    private static void PairTraverseModuleSubtree(
        IComponent2 parent,
        string parentHierarchy,
        int parentDepth,
        ICollection<ComponentInstance> results)
    {
        foreach (var child in (parent.GetChildren() as object[] ?? []).OfType<IComponent2>())
        {
            // In an assembly context SolidWorks may return Name2 as either the
            // local occurrence name ("AD10-1") or an already-qualified path
            // ("AD00-1/AD10-1").  Appending the latter verbatim duplicates the
            // parent prefix and produces a hierarchy path that cannot be resolved
            // on the next API call.  Persist only the leaf occurrence segment.
            string rawName = child.Name2 ?? "Component";
            int separator = rawName.LastIndexOf('/');
            string name = separator >= 0 ? rawName[(separator + 1)..] : rawName;
            string hierarchy = $"{parentHierarchy}/{name}";
            results.Add(new ComponentInstance(
                child,
                new ComponentInstanceInfo(name, child.GetPathName() ?? string.Empty, hierarchy, parentDepth + 1)));
            PairTraverseModuleSubtree(child, hierarchy, parentDepth + 1, results);
        }
    }

    private static ComponentInstance? ResolveMatePairModule(IReadOnlyList<ComponentInstance> roots, string selector)
    {
        string normalized = selector.Trim();
        var exact = roots.Where(root =>
            string.Equals(root.Info.Name, normalized, StringComparison.OrdinalIgnoreCase)
            || string.Equals(root.Info.HierarchyPath, normalized, StringComparison.OrdinalIgnoreCase)
            || string.Equals(root.Info.Path, normalized, StringComparison.OrdinalIgnoreCase)).ToList();
        if (exact.Count == 1)
            return exact[0];

        var contains = roots.Where(root => PairContains(root.Info, normalized)).ToList();
        return contains.Count == 1 ? contains[0] : null;
    }

    private static bool PairContains(ComponentInstanceInfo info, string token) =>
        info.Name.Contains(token, StringComparison.OrdinalIgnoreCase)
        || info.HierarchyPath.Contains(token, StringComparison.OrdinalIgnoreCase)
        || Path.GetFileNameWithoutExtension(info.Path).Contains(token, StringComparison.OrdinalIgnoreCase);

    private static AssemblyMatePairModuleInfo ToMatePairModule(ComponentInstance instance) => new(
        instance.Info.Name,
        instance.Info.Path,
        instance.Info.HierarchyPath,
        PairTransformArray(instance.Component.Transform2));

    private static List<AssemblyMatePairMateInfo> EnumeratePairMates(
        IModelDoc2 document,
        IReadOnlyList<ComponentInstance> instances,
        ComponentInstance first,
        ComponentInstance second,
        ICollection<string> diagnostics)
    {
        var results = new List<AssemblyMatePairMateInfo>();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
                continue;

            var endpoints = new List<AssemblyMatePairEndpointInfo>();
            bool referencesFirst = false;
            bool referencesSecond = false;
            int entityCount = PairSafeMateEntityCount(mate);
            for (int index = 0; index < entityCount; index++)
            {
                IMateEntity2? entity = PairSafeMateEntity(mate, index);
                IComponent2? component = PairSafeReferenceComponent(entity);
                object? reference = PairSafeReference(entity);
                var componentInstance = component == null ? null : instances.FirstOrDefault(instance => IsSameComponentInstance(instance.Component, component));
                if (componentInstance == null)
                    continue;

                ComponentInstance? owner = null;
                if (PairIsSameOrChild(componentInstance.Info.HierarchyPath, first.Info.HierarchyPath))
                {
                    referencesFirst = true;
                    owner = first;
                }
                else if (PairIsSameOrChild(componentInstance.Info.HierarchyPath, second.Info.HierarchyPath))
                {
                    referencesSecond = true;
                    owner = second;
                }

                if (owner != null && reference is IFace2 face)
                    endpoints.Add(BuildPairEndpoint(document, index, owner, componentInstance, component!, face));
            }

            if (!referencesFirst || !referencesSecond)
                continue;

            int mateType = PairSafeMateType(mate);
            int alignment = PairSafeMateAlignment(mate);
            double? distance = PairSafeDistance(feature, mateType);
            string? rejection = null;
            if (entityCount != 2)
                rejection = $"The mate has {entityCount} entities; the demo requires exactly two.";
            else if (endpoints.Count != 2)
                rejection = "Both mate endpoints must be faces owned by the requested modules.";
            else if (!IsSupportedMatePairType(mateType))
                rejection = $"Mate type {PairMateTypeName(mateType)} is outside the demo basic-mate subset.";
            else if (mateType == (int)swMateType_e.swMateDISTANCE && distance == null)
                rejection = "Distance mate value could not be read.";

            results.Add(new AssemblyMatePairMateInfo(
                feature.Name ?? "Mate",
                mateType,
                PairMateTypeName(mateType),
                alignment,
                PairAlignmentName(alignment),
                distance,
                rejection == null,
                rejection,
                endpoints.AsReadOnly()));
        }

        if (results.Count == 0)
            diagnostics.Add($"No direct top-level mate was found between '{first.Info.HierarchyPath}' and '{second.Info.HierarchyPath}'.");
        else if (results.All(result => !result.CanRebuild))
            diagnostics.Add("Direct mates exist, but none satisfy the two-face basic-mate demo gate.");
        return results;
    }

    private static Dictionary<string, CandidateMateGroup> EnumerateCandidatePairMates(
        IModelDoc2 document,
        IReadOnlyList<ComponentInstance> instances,
        IReadOnlyList<ComponentInstance> roots)
    {
        var groups = new Dictionary<string, CandidateMateGroup>(StringComparer.OrdinalIgnoreCase);
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
                continue;

            int entityCount = PairSafeMateEntityCount(mate);
            var resolved = new List<(ComponentInstance Owner, ComponentInstance Leaf, IComponent2 Component, IFace2 Face, int Index)>();
            for (int index = 0; index < entityCount; index++)
            {
                IMateEntity2? entity = PairSafeMateEntity(mate, index);
                IComponent2? component = PairSafeReferenceComponent(entity);
                object? reference = PairSafeReference(entity);
                if (component == null || reference is not IFace2 face)
                    continue;

                var leaf = instances.FirstOrDefault(instance => IsSameComponentInstance(instance.Component, component));
                if (leaf == null)
                    continue;
                var owner = roots.FirstOrDefault(root => PairIsSameOrChild(leaf.Info.HierarchyPath, root.Info.HierarchyPath));
                if (owner != null)
                    resolved.Add((owner, leaf, component, face, index));
            }

            var owners = resolved
                .Select(item => item.Owner)
                .GroupBy(owner => owner.Info.HierarchyPath, StringComparer.OrdinalIgnoreCase)
                .Select(group => group.First())
                .ToList();
            if (owners.Count != 2)
                continue;

            var first = owners.OrderBy(owner => owner.Info.HierarchyPath, StringComparer.OrdinalIgnoreCase).First();
            var second = owners.OrderBy(owner => owner.Info.HierarchyPath, StringComparer.OrdinalIgnoreCase).Last();
            string key = CanonicalMatePairKey(first.Info.HierarchyPath, second.Info.HierarchyPath);
            if (!groups.TryGetValue(key, out var group))
            {
                group = new CandidateMateGroup(first, second, []);
                groups.Add(key, group);
            }

            var endpoints = resolved
                .Where(item => string.Equals(item.Owner.Info.HierarchyPath, first.Info.HierarchyPath, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(item.Owner.Info.HierarchyPath, second.Info.HierarchyPath, StringComparison.OrdinalIgnoreCase))
                .Select(item => BuildPairEndpoint(document, item.Index, item.Owner, item.Leaf, item.Component, item.Face))
                .ToList();
            int mateType = PairSafeMateType(mate);
            int alignment = PairSafeMateAlignment(mate);
            double? distance = PairSafeDistance(feature, mateType);
            string? rejection = null;
            if (entityCount != 2)
                rejection = $"The mate has {entityCount} entities; the demo requires exactly two.";
            else if (endpoints.Count != 2)
                rejection = "Both mate endpoints must be faces owned by the candidate modules.";
            else if (!IsSupportedMatePairType(mateType))
                rejection = $"Mate type {PairMateTypeName(mateType)} is outside the demo basic-mate subset.";
            else if (mateType == (int)swMateType_e.swMateDISTANCE && distance == null)
                rejection = "Distance mate value could not be read.";

            group.Mates.Add(new AssemblyMatePairMateInfo(
                feature.Name ?? "Mate",
                mateType,
                PairMateTypeName(mateType),
                alignment,
                PairAlignmentName(alignment),
                distance,
                rejection == null,
                rejection,
                endpoints.AsReadOnly()));
        }

        return groups;
    }

    private sealed record CandidateMateGroup(
        ComponentInstance First,
        ComponentInstance Second,
        List<AssemblyMatePairMateInfo> Mates);

    private static AssemblyMatePairEndpointInfo BuildPairEndpoint(
        IModelDoc2 document,
        int index,
        ComponentInstance owner,
        ComponentInstance leaf,
        IComponent2 component,
        IFace2 face)
    {
        var faceIndex = PairFindFaceIndex(component, face);
        string? persistent = null;
        try
        {
            var bytes = PairToByteArray(document.Extension.GetPersistReference3(face));
            if (bytes is { Length: > 0 })
                persistent = Convert.ToBase64String(bytes);
        }
        catch { }

        string relative = PairRelativeHierarchy(leaf.Info.HierarchyPath, owner.Info.HierarchyPath);
        return new AssemblyMatePairEndpointInfo(
            index,
            owner.Info.HierarchyPath,
            leaf.Info.HierarchyPath,
            relative,
            leaf.Info.Name,
            leaf.Info.Path,
            "Face",
            faceIndex.BodyIndex,
            faceIndex.FaceIndex,
            PairSafeFaceArea(face),
            persistent);
    }

    private static (int BodyIndex, int FaceIndex) PairFindFaceIndex(IComponent2 component, IFace2 target)
    {
        object bodyInfo;
        // Mate references may legally target sheet/surface bodies.  Restricting endpoint
        // identity to solid bodies made those faces exportable but impossible to re-find.
        var bodies = (component.GetBodies3((int)swBodyType_e.swAllBodies, out bodyInfo) as object[] ?? []).OfType<IBody2>().ToArray();
        for (int bodyIndex = 0; bodyIndex < bodies.Length; bodyIndex++)
        {
            var faces = (bodies[bodyIndex].GetFaces() as object[] ?? []).OfType<IFace2>().ToArray();
            for (int faceIndex = 0; faceIndex < faces.Length; faceIndex++)
            {
                if (PairComIdentityEquals(faces[faceIndex], target))
                    return (bodyIndex, faceIndex);
            }
        }
        return (-1, -1);
    }

    private IComponent2 InsertPairModule(IAssemblyDoc targetAssembly, AssemblyMatePairModuleInfo module)
    {
        if (!File.Exists(module.Path))
            throw new FileNotFoundException($"Module source file was not found: {module.Path}", module.Path);
        var targetDocument = (IModelDoc2)targetAssembly;
        string targetPath = targetDocument.GetPathName() ?? string.Empty;
        string targetTitle = targetDocument.GetTitle() ?? string.Empty;
        var component = targetAssembly.AddComponent5(module.Path, 0, "", false, "", 0, 0, 0) as IComponent2;
        if (component == null)
        {
            var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
            sw.OpenDoc(module.Path);
            if (!string.IsNullOrWhiteSpace(targetPath))
                sw.ActivateDoc(targetPath);
            else if (!string.IsNullOrWhiteSpace(targetTitle))
                sw.ActivateDocByTitle(targetTitle);
            component = targetAssembly.AddComponent5(module.Path, 0, "", false, "", 0, 0, 0) as IComponent2;
        }
        if (component == null)
            throw new InvalidOperationException($"SolidWorks failed to insert module: {module.Path}");
        return component;
    }

    private void ApplyPairSourceTransform(IComponent2 component, double[]? transform)
    {
        if (transform is not { Length: >= 13 })
            return;
        try
        {
            var math = (IMathUtility?)_cm.SwApp?.GetMathUtility();
            var created = math?.CreateTransform(transform) as MathTransform;
            if (created != null)
                component.Transform2 = created;
        }
        catch
        {
            // Original placement is a convergence aid, not the identity key. Mate rebuild can still proceed.
        }
    }

    private static AssemblyMatePairRebuildItemResult RebuildPairMate(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 firstRoot,
        IComponent2 secondRoot,
        AssemblyMatePairExportResult export,
        AssemblyMatePairMateInfo mate)
    {
        var strategies = new List<string>();
        document.ClearSelection2(true);
        int selected = 0;
        foreach (var endpoint in mate.Endpoints.OrderBy(endpoint => endpoint.Index))
        {
            bool isFirst = string.Equals(endpoint.ModuleHierarchyPath, export.FirstModule!.HierarchyPath, StringComparison.OrdinalIgnoreCase);
            var root = isFirst ? firstRoot : secondRoot;
            var leaf = ResolvePairTargetLeaf(root, endpoint);
            if (leaf == null)
                return PairRebuildFailure(mate, $"Could not resolve target leaf for endpoint #{endpoint.Index}: {endpoint.RelativeLeafHierarchyPath}", strategies);
            var face = ResolvePairTargetFace(leaf, endpoint, out string strategy);
            strategies.Add($"endpoint#{endpoint.Index}: {strategy}");
            if (face == null)
                return PairRebuildFailure(mate, $"Could not resolve target face for endpoint #{endpoint.Index}.", strategies);

            var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
            selectData.Mark = 1;
            if (!((IEntity)face).Select4(selected > 0, selectData))
                return PairRebuildFailure(mate, $"SolidWorks failed to select endpoint #{endpoint.Index}.", strategies);
            selected++;
        }

        int errors = 0;
        object? created = assembly.AddMate5(
            mate.MateType,
            mate.Alignment,
            false,
            mate.Distance ?? 0,
            0,
            0,
            0, 0,
            0, 0, 0,
            false, false, 0,
            out errors);
        document.ClearSelection2(true);
        var error = SolidWorksApiErrorFactory.DecodeValue<swAddMateError_e>(errors);
        bool success = created != null && (swAddMateError_e)errors == swAddMateError_e.swAddMateError_NoError;
        if (success)
            PairTryRenameCreatedMate(created!, $"MCP_PAIR_{mate.MateName}");
        return new AssemblyMatePairRebuildItemResult(
            mate.MateName,
            mate.MateType,
            mate.MateTypeName,
            success,
            errors,
            error.Name ?? "Unknown",
            success ? "Mate rebuilt from exported face endpoints." : error.Description ?? "SolidWorks failed to rebuild mate.",
            strategies.AsReadOnly());
    }

    private static AssemblyMatePairRebuildItemResult PairRebuildFailure(AssemblyMatePairMateInfo mate, string message, IReadOnlyList<string> strategies) =>
        new(mate.MateName, mate.MateType, mate.MateTypeName, false, 0, "EndpointResolutionFailed", message, strategies);

    private static IComponent2? ResolvePairTargetLeaf(IComponent2 targetRoot, AssemblyMatePairEndpointInfo endpoint)
    {
        var items = new List<(IComponent2 Component, string RelativePath)> { (targetRoot, string.Empty) };
        PairTraverseTargetLeaves(targetRoot, string.Empty, items);
        var exactRelative = items.Where(item => string.Equals(item.RelativePath, endpoint.RelativeLeafHierarchyPath, StringComparison.OrdinalIgnoreCase)).ToList();
        if (exactRelative.Count == 1)
            return exactRelative[0].Component;

        var samePath = items.Where(item => string.Equals(item.Component.GetPathName(), endpoint.LeafComponentPath, StringComparison.OrdinalIgnoreCase)).ToList();
        return samePath.Count == 1 ? samePath[0].Component : null;
    }

    private static void PairTraverseTargetLeaves(IComponent2 parent, string parentRelative, ICollection<(IComponent2 Component, string RelativePath)> results)
    {
        foreach (var child in (parent.GetChildren() as object[] ?? []).OfType<IComponent2>())
        {
            string name = child.Name2 ?? "Component";
            string relative = string.IsNullOrEmpty(parentRelative) ? name : $"{parentRelative}/{name}";
            results.Add((child, relative));
            PairTraverseTargetLeaves(child, relative, results);
        }
    }

    private static IFace2? ResolvePairTargetFace(IComponent2 leaf, AssemblyMatePairEndpointInfo endpoint, out string strategy)
    {
        strategy = "BodyFaceIndex";
        object bodyInfo;
        var bodies = (leaf.GetBodies3((int)swBodyType_e.swAllBodies, out bodyInfo) as object[] ?? []).OfType<IBody2>().ToArray();
        if (endpoint.BodyIndex >= 0 && endpoint.BodyIndex < bodies.Length)
        {
            var faces = (bodies[endpoint.BodyIndex].GetFaces() as object[] ?? []).OfType<IFace2>().ToArray();
            if (endpoint.FaceIndexInBody >= 0 && endpoint.FaceIndexInBody < faces.Length)
            {
                var indexed = faces[endpoint.FaceIndexInBody];
                if (PairAreaMatches(indexed, endpoint.Area))
                    return indexed;
            }
        }

        strategy = "UniqueAreaFallback";
        var areaMatches = bodies
            .SelectMany(body => (body.GetFaces() as object[] ?? []).OfType<IFace2>())
            .Where(face => PairAreaMatches(face, endpoint.Area))
            .ToList();
        return areaMatches.Count == 1 ? areaMatches[0] : null;
    }

    private static bool PairAreaMatches(IFace2 face, double expected)
    {
        double actual = PairSafeFaceArea(face);
        double tolerance = Math.Max(1e-10, Math.Abs(expected) * 1e-6);
        return Math.Abs(actual - expected) <= tolerance;
    }

    private static void PairTryRenameCreatedMate(object created, string name)
    {
        try
        {
            Feature? feature = created as Feature;
            if (feature == null)
            {
                var method = created.GetType().GetMethod("GetFeature") ?? created.GetType().GetMethod("IGetFeature");
                feature = method?.Invoke(created, null) as Feature;
            }
            if (feature != null)
                feature.Name = name;
        }
        catch { }
    }

    private static AssemblyMatePairExportResult SaveMatePairExportIfRequested(AssemblyMatePairExportResult result, string? outputPath, bool saveJson)
    {
        if (!saveJson)
            return result;
        string path = Path.GetFullPath(outputPath ?? Path.Combine(
            Path.GetDirectoryName(result.SourceAssemblyPath)!,
            $"{Path.GetFileNameWithoutExtension(result.SourceAssemblyPath)}_{SanitizePairFilePart(result.RequestedFirstModuleSelector)}_{SanitizePairFilePart(result.RequestedSecondModuleSelector)}_mates.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var saved = result with { SavedJsonPath = path };
        File.WriteAllText(path, JsonSerializer.Serialize(saved, MatePairJsonOptions));
        return saved;
    }

    private static string SanitizePairFilePart(string value)
    {
        var invalid = Path.GetInvalidFileNameChars();
        return new string(value.Select(character => invalid.Contains(character) || character is '/' or '\\' ? '_' : character).ToArray());
    }

    private static string PairRelativeHierarchy(string hierarchy, string owner)
    {
        if (string.Equals(hierarchy, owner, StringComparison.OrdinalIgnoreCase))
            return string.Empty;
        return hierarchy.StartsWith(owner + "/", StringComparison.OrdinalIgnoreCase)
            ? hierarchy[(owner.Length + 1)..]
            : hierarchy;
    }

    private static bool PairIsSameOrChild(string candidate, string owner) =>
        string.Equals(candidate, owner, StringComparison.OrdinalIgnoreCase)
        || candidate.StartsWith(owner + "/", StringComparison.OrdinalIgnoreCase);

    private static int PairSafeMateEntityCount(IMate2 mate) { try { return mate.GetMateEntityCount(); } catch { return 0; } }
    private static IMateEntity2? PairSafeMateEntity(IMate2 mate, int index) { try { return mate.MateEntity(index); } catch { return null; } }
    private static object? PairSafeReference(IMateEntity2? entity) { try { return entity?.Reference; } catch { return null; } }
    private static IComponent2? PairSafeReferenceComponent(IMateEntity2? entity) { try { return entity?.ReferenceComponent; } catch { return null; } }
    private static int PairSafeMateType(IMate2 mate) { try { return mate.Type; } catch { return (int)swMateType_e.swMateUNKNOWN; } }
    private static int PairSafeMateAlignment(IMate2 mate) { try { return mate.Alignment; } catch { return (int)swMateAlign_e.swAlignNONE; } }
    private static double PairSafeFaceArea(IFace2 face) { try { return face.GetArea(); } catch { return 0; } }
    private static double? PairSafeDistance(IFeature feature, int mateType)
    {
        if (mateType != (int)swMateType_e.swMateDISTANCE)
            return null;
        try { return (feature.GetDefinition() as IDistanceMateFeatureData)?.Distance; } catch { return null; }
    }

    private static string PairMateTypeName(int mateType) => ((swMateType_e)mateType).ToString();
    private static string PairAlignmentName(int alignment) => ((swMateAlign_e)alignment).ToString();
    private static double[]? PairTransformArray(MathTransform? transform) => transform?.ArrayData is double[] values ? values.ToArray() : null;
    private static byte[]? PairToByteArray(object? value) => value switch
    {
        byte[] bytes => bytes,
        Array array => array.Cast<object>().Select(Convert.ToByte).ToArray(),
        _ => null,
    };

    private static bool PairComIdentityEquals(object first, object second)
    {
        IntPtr firstPtr = IntPtr.Zero;
        IntPtr secondPtr = IntPtr.Zero;
        try
        {
            firstPtr = Marshal.GetIUnknownForObject(first);
            secondPtr = Marshal.GetIUnknownForObject(second);
            return firstPtr == secondPtr;
        }
        catch { return ReferenceEquals(first, second); }
        finally
        {
            if (firstPtr != IntPtr.Zero) Marshal.Release(firstPtr);
            if (secondPtr != IntPtr.Zero) Marshal.Release(secondPtr);
        }
    }
}
