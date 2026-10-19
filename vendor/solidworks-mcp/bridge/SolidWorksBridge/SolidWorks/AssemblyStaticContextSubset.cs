using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Diagnostics;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyStaticContextSubsetComponent(
    string Name,
    string Path,
    double[] ExpectedWorldTransform,
    double[]? ReopenedWorldTransform,
    double? MaximumTransformElementError,
    int? SolvingStateBefore,
    int? SolvingStateAfter);

public record AssemblyStaticContextSubsetResult(
    bool Success,
    string ExecutionMode,
    string SourceAssemblyPath,
    string OutputAssemblyPath,
    int SourceTopLevelComponentCount,
    int RequestedKeepCount,
    int DeletedTopLevelComponentCount,
    int ReopenedTopLevelComponentCount,
    bool Reopened,
    bool PathsMatch,
    bool RootPosesMatch,
    double PoseTolerance,
    IReadOnlyList<AssemblyStaticContextSubsetComponent> Components,
    IReadOnlyDictionary<string, double> PhaseDurationsSeconds,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    public AssemblyStaticContextSubsetResult CreateAssemblyStaticContextSubset(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        IReadOnlyList<string> keepComponentPaths)
    {
        var stopwatch = Stopwatch.StartNew();
        double previous = 0;
        var phases = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        void Complete(string name)
        {
            double now = stopwatch.Elapsed.TotalSeconds;
            phases[name] = now - previous;
            previous = now;
        }

        string source = Path.GetFullPath(sourceAssemblyPath ?? string.Empty);
        string output = Path.GetFullPath(outputAssemblyPath ?? string.Empty);
        if (!File.Exists(source))
            throw new FileNotFoundException($"Source assembly was not found: {source}", source);
        if (!string.Equals(Path.GetExtension(source), ".SLDASM", StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetExtension(output), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Source and output paths must end in .SLDASM.");
        if (File.Exists(output))
            throw new IOException($"Refusing to overwrite an existing assembly: {output}");
        var requestedPaths = (keepComponentPaths ?? [])
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(Path.GetFullPath)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (requestedPaths.Length < 1)
            throw new ArgumentException("At least one component source path must be retained.");
        foreach (string path in requestedPaths)
            if (!File.Exists(path))
                throw new FileNotFoundException($"Requested component source was not found: {path}", path);

        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        File.Copy(source, output, overwrite: false);
        Complete("validate-and-copy-source");
        var diagnostics = new List<string>
        {
            "The source parent assembly was copied and never modified.",
            "The result is a static parent-context checkpoint for geometry and collision review.",
            "Original hierarchy completeness and motion semantics are explicitly not claimed.",
        };

        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        sw.OpenDoc(output);
        sw.ActivateDoc(output);
        var assembly = GetAssemblyDoc();
        var document = (IModelDoc2)assembly;
        var roots = PairEnumerateTopLevelInstances(assembly);
        int sourceCount = roots.Count;
        var kept = roots.Where(root => requestedPaths.Contains(Path.GetFullPath(root.Info.Path), StringComparer.OrdinalIgnoreCase)).ToArray();
        var missing = requestedPaths.Where(path => !kept.Any(root => string.Equals(Path.GetFullPath(root.Info.Path), path, StringComparison.OrdinalIgnoreCase))).ToArray();
        var duplicated = requestedPaths.Where(path => kept.Count(root => string.Equals(Path.GetFullPath(root.Info.Path), path, StringComparison.OrdinalIgnoreCase)) != 1).ToArray();
        if (missing.Length > 0 || duplicated.Length > 0)
            throw new InvalidOperationException(
                $"Static subset selectors must resolve exactly once. Missing={string.Join(";", missing)}, nonUnique={string.Join(";", duplicated)}");
        var expected = kept.ToDictionary(
            item => Path.GetFullPath(item.Info.Path),
            item => new
            {
                item.Info.Name,
                Transform = PairTransformArray(item.Component.GetTotalTransform(true) as MathTransform)
                    ?? PairTransformArray(item.Component.Transform2)
                    ?? throw new InvalidOperationException($"No root transform for {item.Info.Name}."),
                Solving = SafeComponentSolvingState(item.Component),
            },
            StringComparer.OrdinalIgnoreCase);
        Complete("open-and-resolve-roots");

        var deleted = roots.Where(root => !requestedPaths.Contains(Path.GetFullPath(root.Info.Path), StringComparer.OrdinalIgnoreCase)).ToArray();
        document.ClearSelection2(true);
        try
        {
            var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
            bool append = false;
            foreach (var item in deleted)
            {
                if (!item.Component.Select4(append, selectData, false))
                    throw new InvalidOperationException($"Could not select component for deletion: {item.Info.HierarchyPath}");
                append = true;
            }
            if (deleted.Length > 0 && !document.Extension.DeleteSelection2(0))
                throw new InvalidOperationException("SolidWorks failed to delete one or more unrequested top-level components.");
        }
        finally
        {
            document.ClearSelection2(true);
        }
        document.ForceRebuild3(true);
        Complete("delete-unrequested-context");

        // Preserve the parent-context checkpoint as a static artifact.  Fixing the
        // roots closes top-level drift; flexible solving is then restored so the
        // surviving LM/ZZ relation may retain its already solved internal branch.
        var survivingRoots = PairEnumerateTopLevelInstances(assembly);
        foreach (var item in survivingRoots)
        {
            FixGraphBaseComponent(document, assembly, item.Component);
            string path = Path.GetFullPath(item.Info.Path);
            if (expected[path].Solving is int solving)
                RestoreStaticSubsetSolvingState(document, assembly, item.Component, solving, diagnostics);
        }
        document.ForceRebuild3(true);
        Complete("freeze-static-checkpoint");

        var save = sw.SaveDocAs(output, sourcePath: null, saveAsCopy: false);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");
        string title = document.GetTitle() ?? Path.GetFileName(output);
        try { sw.CloseDoc(title); } catch (Exception ex) { diagnostics.Add($"Close before reopen was best-effort: {ex.Message}"); }
        Complete("save-and-close");

        const double tolerance = 1e-8;
        bool reopened = false;
        bool pathsMatch = false;
        bool posesMatch = false;
        var comparisons = new List<AssemblyStaticContextSubsetComponent>();
        try
        {
            sw.OpenDoc(output);
            sw.ActivateDoc(output);
            reopened = true;
            var reopenedRoots = PairEnumerateTopLevelInstances(GetAssemblyDoc());
            pathsMatch = reopenedRoots.Count == requestedPaths.Length
                && requestedPaths.All(path => reopenedRoots.Count(root => string.Equals(Path.GetFullPath(root.Info.Path), path, StringComparison.OrdinalIgnoreCase)) == 1);
            foreach (string path in requestedPaths)
            {
                var root = reopenedRoots.SingleOrDefault(item => string.Equals(Path.GetFullPath(item.Info.Path), path, StringComparison.OrdinalIgnoreCase));
                double[]? observed = root == null ? null
                    : PairTransformArray(root.Component.GetTotalTransform(true) as MathTransform)
                        ?? PairTransformArray(root.Component.Transform2);
                double? error = observed == null ? null : expected[path].Transform.Zip(observed, (a, b) => Math.Abs(a - b)).Max();
                comparisons.Add(new AssemblyStaticContextSubsetComponent(
                    expected[path].Name,
                    path,
                    expected[path].Transform,
                    observed,
                    error,
                    expected[path].Solving,
                    root == null ? null : SafeComponentSolvingState(root.Component)));
            }
            posesMatch = comparisons.Count == requestedPaths.Length
                && comparisons.All(item => item.MaximumTransformElementError is <= tolerance);
            Complete("reopen-and-verify");
            int reopenedCount = reopenedRoots.Count;
            phases["total"] = stopwatch.Elapsed.TotalSeconds;
            return new AssemblyStaticContextSubsetResult(
                reopened && pathsMatch && posesMatch,
                "static_parent_context_subset",
                source,
                output,
                sourceCount,
                requestedPaths.Length,
                deleted.Length,
                reopenedCount,
                reopened,
                pathsMatch,
                posesMatch,
                tolerance,
                comparisons.AsReadOnly(),
                phases,
                diagnostics.AsReadOnly());
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Static subset reopen verification failed: {ex.Message}");
            Complete("reopen-and-verify");
            phases["total"] = stopwatch.Elapsed.TotalSeconds;
            return new AssemblyStaticContextSubsetResult(
                false, "static_parent_context_subset", source, output, sourceCount,
                requestedPaths.Length, deleted.Length, 0, reopened, pathsMatch, false,
                tolerance, comparisons.AsReadOnly(), phases, diagnostics.AsReadOnly());
        }
    }

    private static void RestoreStaticSubsetSolvingState(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 component,
        int solvingState,
        ICollection<string> diagnostics)
    {
        try
        {
            int suppression = component.GetSuppression();
            if (suppression == (int)swComponentSuppressionState_e.swComponentLightweight)
                suppression = (int)swComponentSuppressionState_e.swComponentFullyResolved;
            bool visible = component.Visible == (int)swComponentVisibilityState_e.swComponentVisible;
            bool excludeFromBom;
            bool isEnvelope;
            try { excludeFromBom = component.ExcludeFromBOM; } catch { excludeFromBom = false; }
            try { isEnvelope = component.IsEnvelope(); } catch { isEnvelope = false; }
            document.ClearSelection2(true);
            var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
            if (!component.Select4(false, selectData, false))
                throw new InvalidOperationException("component selection failed");
            assembly.CompConfigProperties5(
                suppression,
                solvingState,
                visible,
                true,
                component.ReferencedConfiguration ?? string.Empty,
                excludeFromBom,
                isEnvelope);
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Could not restore solving state {solvingState} for '{component.Name2}': {ex.Message}");
        }
        finally
        {
            document.ClearSelection2(true);
        }
    }
}
