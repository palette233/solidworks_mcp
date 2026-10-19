using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Diagnostics;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyContextLeafPoseComparison(
    bool Stable,
    int BeforeCount,
    int AfterCount,
    int MissingAfterCount,
    int AddedAfterCount,
    double? MaximumTransformElementError,
    double Tolerance,
    IReadOnlyList<string> MissingAfter,
    IReadOnlyList<string> AddedAfter);

public record AssemblyContextMateGraphReconstructionResult(
    bool Success,
    string SourceAssemblyPath,
    string EffectiveMateGraphPath,
    string OutputAssemblyPath,
    string TargetModuleToken,
    IReadOnlyList<string> SuppressedSourceMateNames,
    int RequestedMateCount,
    int CreatedMateCount,
    bool Reopened,
    bool ReopenedMateParametersMatch,
    bool TargetFullyConstrained,
    bool ComponentSemanticsMatch,
    IReadOnlyList<AssemblyModuleMateExperimentMateResult> MateResults,
    IReadOnlyList<AssemblyEditableMateVerification> MateVerifications,
    IReadOnlyList<AssemblySemanticValidationResult> ValidationResults,
    IReadOnlyDictionary<string, AssemblyContextLeafPoseComparison> ContextPoseComparisons,
    IReadOnlyDictionary<string, double> PhaseDurationsSeconds,
    IReadOnlyList<string> Diagnostics,
    string ExecutionMode = "legacy_context_remate",
    IReadOnlyList<string>? PreservedSourceMateNames = null,
    IReadOnlyList<string>? CreatedOrReplacedMateNames = null,
    IReadOnlyList<string>? RemovedOrReplacedSourceMateNames = null,
    bool TargetComponentReinserted = false,
    bool TargetComponentExplicitlyDisplaced = false,
    IReadOnlyList<double>? TargetTransformBefore = null,
    IReadOnlyList<double>? TargetTransformAfterDisplacement = null,
    IReadOnlyList<double>? TargetTransformAfterRemate = null,
    double? InitialDisplacementMaximumElementDelta = null,
    double? ReturnToSourcePoseMaximumElementError = null,
    bool? TargetReturnedToSourcePose = null);

public record AssemblyContextDirectMateEditPlan(
    bool UsesPatchAudit,
    IReadOnlyList<string> SourceMateNamesToSuppress,
    IReadOnlyList<string> EffectiveMateNamesToCreate,
    IReadOnlyList<string> EffectiveMateNamesToPreserve,
    IReadOnlyList<string> RemovedMateNames);

public record AssemblyContextRelationVerificationResult(
    bool Success,
    string SourceAssemblyPath,
    string EffectiveMateGraphPath,
    string TargetModuleToken,
    int RequestedValidationRelationCount,
    int PassedValidationRelationCount,
    IReadOnlyList<AssemblySemanticValidationResult> ValidationResults,
    IReadOnlyList<AssemblyContextValidationModulePose> ModulePoses,
    IReadOnlyDictionary<string, double> PhaseDurationsSeconds,
    IReadOnlyList<string> Diagnostics,
    string ExecutionMode = "read_only_existing_relation_verification");

public record AssemblyContextValidationModulePose(
    string ModuleToken,
    string HierarchyPath,
    IReadOnlyList<double>? SourceTransform,
    IReadOnlyList<double>? CurrentTransform,
    double? MaximumTransformElementDelta);

public partial class AssemblyService
{
    /// <summary>
    /// Open an existing saved checkpoint and measure declared validation
    /// relations without rebuilding mates, saving the model, or creating a CAD
    /// copy.  The caller may copy the verified checkpoint at filesystem level
    /// after a successful result to advance an immutable transaction chain.
    /// </summary>
    public AssemblyContextRelationVerificationResult VerifyRelationsInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false)
    {
        var stopwatch = Stopwatch.StartNew();
        double previousPhaseEnd = 0;
        var phaseDurations = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        void CompletePhase(string name)
        {
            double current = stopwatch.Elapsed.TotalSeconds;
            phaseDurations[name] = current - previousPhaseEnd;
            previousPhaseEnd = current;
        }

        var graph = LoadAndValidateEditableMateGraph(effectiveMateGraphPath);
        var validationRelations = graph.SemanticAssemblyPlanAudit?.ValidationRelations ?? [];
        if (validationRelations.Count == 0)
            throw new InvalidOperationException("Read-only verification requires at least one ValidationRelation.");
        if (graph.Mates.Any(mate => !mate.IsSuppressed))
            throw new InvalidOperationException("Read-only verification refuses active driving mates.");
        if ((graph.PatchAudit?.Operations ?? []).Count > 0)
            throw new InvalidOperationException("Read-only verification refuses mutating PatchAudit operations.");

        string source = Path.GetFullPath(sourceAssemblyPath ?? string.Empty);
        if (!File.Exists(source))
            throw new FileNotFoundException($"Source context assembly was not found: {source}", source);
        if (!string.Equals(Path.GetExtension(source), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Source path must end in .SLDASM.");
        if (!graph.Modules.Any(module =>
                string.Equals(module.ModuleToken, targetModuleToken, StringComparison.OrdinalIgnoreCase)
                || string.Equals(module.HierarchyPath, targetModuleToken, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidOperationException($"Target selector '{targetModuleToken}' is not present in the validation graph.");

        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        IModelDoc2 document;
        bool openedHere = false;
        if (preserveResolvedSourceSession)
        {
            document = sw.IActiveDoc2 as IModelDoc2
                ?? throw new InvalidOperationException("Resolved-session verification requires an active assembly.");
            string activePath = document.GetPathName() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(activePath)
                || !string.Equals(Path.GetFullPath(activePath), source, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException(
                    $"Resolved-session verification requires active source '{source}', but active document is '{activePath}'.");
        }
        else
        {
            var alreadyOpen = sw.GetOpenModelDocument(source);
            if (alreadyOpen == null)
            {
                sw.OpenDoc(source);
                openedHere = true;
            }
            sw.ActivateDoc(source);
            document = alreadyOpen ?? sw.IActiveDoc2 as IModelDoc2
                ?? throw new InvalidOperationException("Could not activate the source assembly.");
        }
        var assembly = document as IAssemblyDoc
            ?? throw new InvalidOperationException("The source document is not an assembly.");
        var roots = ResolveContextGraphRoots(graph, PairEnumerateTopLevelInstances(assembly));
        CompletePhase("open-and-resolve-graph-roots");

        var results = new List<AssemblySemanticValidationResult>();
        foreach (var relation in validationRelations)
            results.Add(MeasureSemanticValidationRelation(roots, relation, graph.Modules));
        var modulePoses = graph.Modules.Select(module =>
        {
            roots.TryGetValue(module.HierarchyPath, out var root);
            double[]? current = root == null ? null : PairTransformArray(root.Transform2);
            return new AssemblyContextValidationModulePose(
                module.ModuleToken,
                module.HierarchyPath,
                module.SourceTransform,
                current,
                MaximumTransformElementDelta(module.SourceTransform, current));
        }).ToArray();
        CompletePhase("measure-validation-relations");

        var diagnostics = new List<string>
        {
            "Read-only verification opened the saved checkpoint and measured declared relations without rebuilding or mutating mates.",
            "No CAD Save, Save As, rebuild, or second reopen was performed.",
        };
        if (openedHere)
        {
            string title = document.GetTitle() ?? Path.GetFileName(source);
            try { sw.CloseDoc(title); }
            catch (Exception ex) { diagnostics.Add($"Close after verification was best-effort: {ex.Message}"); }
        }
        CompletePhase("close-source");
        phaseDurations["total"] = stopwatch.Elapsed.TotalSeconds;
        int passed = results.Count(item => item.Passed);
        return new AssemblyContextRelationVerificationResult(
            passed == validationRelations.Count,
            source,
            Path.GetFullPath(effectiveMateGraphPath),
            targetModuleToken,
            validationRelations.Count,
            passed,
            results.AsReadOnly(),
            modulePoses,
            phaseDurations,
            diagnostics.AsReadOnly());
    }

    /// <summary>
    /// Apply an editable mate-graph patch to components that already exist in an
    /// assembly context.  New mates are added in place; updated mates suppress only
    /// the source relation they replace; removed mates are suppressed.  Legacy
    /// graphs without PatchAudit keep the previous displace/remate behaviour.
    /// </summary>
    public AssemblyContextMateGraphReconstructionResult RemateComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken,
        bool preserveResolvedSourceSession = false,
        bool forceInitialDisplacement = false)
    {
        var stopwatch = Stopwatch.StartNew();
        double previousPhaseEnd = 0;
        var phaseDurations = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        void CompletePhase(string name)
        {
            double current = stopwatch.Elapsed.TotalSeconds;
            phaseDurations[name] = current - previousPhaseEnd;
            previousPhaseEnd = current;
        }

        var graph = LoadAndValidateEditableMateGraph(effectiveMateGraphPath);
        string source = Path.GetFullPath(sourceAssemblyPath ?? string.Empty);
        string output = Path.GetFullPath(outputAssemblyPath ?? string.Empty);
        if (!File.Exists(source))
            throw new FileNotFoundException($"Source context assembly was not found: {source}", source);
        if (!string.Equals(Path.GetExtension(source), ".SLDASM", StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetExtension(output), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Source and output paths must end in .SLDASM.");
        if (File.Exists(output))
            throw new IOException($"Refusing to overwrite an existing assembly: {output}");

        var targetMatches = graph.Modules.Where(module =>
            string.Equals(module.ModuleToken, targetModuleToken, StringComparison.OrdinalIgnoreCase)
            || string.Equals(module.HierarchyPath, targetModuleToken, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (targetMatches.Length != 1)
            throw new InvalidOperationException($"Target selector '{targetModuleToken}' resolved to {targetMatches.Length} graph modules; expected one.");
        var targetModule = targetMatches[0];
        var activeMates = graph.Mates.Where(mate => !mate.IsSuppressed).ToArray();
        var editPlan = BuildContextDirectMateEditPlan(graph);
        var matesToCreate = activeMates.Where(mate =>
            editPlan.EffectiveMateNamesToCreate.Contains(mate.MateName, StringComparer.OrdinalIgnoreCase)).ToArray();
        var preservedMates = activeMates.Where(mate =>
            editPlan.EffectiveMateNamesToPreserve.Contains(mate.MateName, StringComparer.OrdinalIgnoreCase)).ToArray();
        var validationRelations = graph.SemanticAssemblyPlanAudit?.ValidationRelations ?? [];
        if (activeMates.Any(mate => mate.Endpoints.All(endpoint =>
                !string.Equals(endpoint.ModuleHierarchyPath, targetModule.HierarchyPath, StringComparison.OrdinalIgnoreCase))))
            throw new InvalidOperationException("Every driving mate in the context-remate experiment must reference the target module.");

        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        var diagnostics = new List<string>
        {
            preserveResolvedSourceSession
                ? "The already-open resolved source document was saved under the staging output path before any mate mutation; the source file was not overwritten."
                : "The source assembly file was copied before any CAD mutation.",
            editPlan.UsesPatchAudit
                ? "PatchAudit is authoritative: existing components remain in place and only add/update/remove mate operations are applied."
                : "Legacy graph without PatchAudit: the target is displaced and all graph mates are rebuilt.",
            forceInitialDisplacement
                ? "The target is deliberately moved to a deterministic non-source pose after source-mate suppression, before the requested mate bundle is rebuilt."
                : "No extra initial-pose perturbation was requested.",
            preserveResolvedSourceSession
                ? "All graph endpoints were verified in the active resolved source session before Save As; no whole-root resolve is requested by this operation."
                : "The complete source assembly is not recursively resolved; only endpoint leaves are resolved on demand while rebuilding mates.",
            "Leaf-pose drift is audited only for flexible fixed-context modules, because rigid context is governed by its top-level transform.",
        };

        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        IAssemblyDoc assembly;
        IModelDoc2 document;
        IReadOnlyDictionary<string, IComponent2> rootsByGraphHierarchy;
        if (preserveResolvedSourceSession)
        {
            var active = sw.IActiveDoc2 as IModelDoc2
                ?? throw new InvalidOperationException("Resolved-session execution requires the source assembly to be the active SolidWorks document.");
            string activePath = active.GetPathName() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(activePath)
                || !string.Equals(Path.GetFullPath(activePath), source, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException(
                    $"Resolved-session execution requires active source '{source}', but the active document is '{activePath}'.");
            assembly = active as IAssemblyDoc
                ?? throw new InvalidOperationException("The active resolved source document is not an assembly.");
            document = active;
            rootsByGraphHierarchy = ResolveContextGraphRoots(graph, PairEnumerateTopLevelInstances(assembly));
            VerifyResolvedSessionGraphEndpoints(document, assembly, rootsByGraphHierarchy, activeMates);
            var initialSave = sw.SaveDocAs(output, sourcePath: source, saveAsCopy: false);
            if (initialSave.Errors != 0)
                throw new InvalidOperationException(
                    $"Resolved source Save As returned errors={initialSave.Errors}, warnings={initialSave.Warnings}.");
            CompletePhase("validate-and-save-resolved-session");
        }
        else
        {
            File.Copy(source, output, overwrite: false);
            CompletePhase("validate-and-copy-source");
            sw.OpenDoc(output);
            sw.ActivateDoc(output);
            assembly = GetAssemblyDoc();
            document = (IModelDoc2)assembly;
            rootsByGraphHierarchy = ResolveContextGraphRoots(graph, PairEnumerateTopLevelInstances(assembly));
        }
        CompletePhase("open-and-resolve-graph-roots");

        string excludedPoseModule = editPlan.UsesPatchAudit
            ? "__direct_edit_preserves_all_existing_modules__"
            : targetModule.HierarchyPath;
        var poseBefore = CaptureFixedContextLeafPoses(graph, rootsByGraphHierarchy, excludedPoseModule);
        var targetTransformBefore = PairTransformArray(
            rootsByGraphHierarchy[targetModule.HierarchyPath].GetTotalTransform(true) as MathTransform)
            ?? PairTransformArray(rootsByGraphHierarchy[targetModule.HierarchyPath].Transform2);
        CompletePhase("capture-flexible-context-before");

        var sourceMateNames = editPlan.SourceMateNamesToSuppress
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var suppressed = SuppressNamedTopLevelMateFeatures(document, sourceMateNames);
        var missingSuppressions = sourceMateNames.Except(suppressed, StringComparer.OrdinalIgnoreCase).ToArray();
        if (missingSuppressions.Length > 0)
            diagnostics.Add($"Source mate features not suppressed: {string.Join(", ", missingSuppressions)}.");
        CompletePhase("suppress-source-mates");

        bool explicitlyDisplaced = forceInitialDisplacement || !editPlan.UsesPatchAudit;
        if (explicitlyDisplaced)
        {
            if (forceInitialDisplacement)
                UnfixContextTargetComponent(
                    document,
                    assembly,
                    rootsByGraphHierarchy[targetModule.HierarchyPath]);
            var baseModule = graph.Modules.FirstOrDefault(module =>
                string.Equals(module.ModuleToken, graph.EditPolicy?.BaseModuleToken ?? "A600", StringComparison.OrdinalIgnoreCase))
                ?? graph.Modules.First();
            var displaced = BuildDeterministicExperimentTransform(baseModule.SourceTransform, graph.Modules.Count + 1);
            ApplyGraphTransform(rootsByGraphHierarchy[targetModule.HierarchyPath], displaced);
        }
        var targetTransformAfterDisplacement = PairTransformArray(
            rootsByGraphHierarchy[targetModule.HierarchyPath].GetTotalTransform(true) as MathTransform)
            ?? PairTransformArray(rootsByGraphHierarchy[targetModule.HierarchyPath].Transform2);
        CompletePhase("displace-target");

        var mateResults = matesToCreate
            .Select(mate => RebuildGraphMate(document, assembly, rootsByGraphHierarchy, mate, mate.AdvancedOptions))
            .ToList();
        ApplyGraphComponentSolvingState(
            document,
            assembly,
            rootsByGraphHierarchy[targetModule.HierarchyPath],
            targetModule,
            diagnostics);
        // Perform one full rebuild after the complete suppression/displacement/
        // mate batch.  Rebuilding after every intermediate mutation multiplied
        // full-assembly solve time without adding a verification boundary.
        document.ForceRebuild3(false);
        CompletePhase("rebuild-driving-mates");

        var save = sw.SaveDocAs(output, sourcePath: null, saveAsCopy: false);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");
        string title = document.GetTitle() ?? Path.GetFileName(output);
        try { sw.CloseDoc(title); } catch (Exception ex) { diagnostics.Add($"Close before reopen was best-effort: {ex.Message}"); }
        CompletePhase("save-and-close");

        bool reopened = false;
        bool targetFullyConstrained = false;
        bool semanticsMatch = false;
        var verifications = new List<AssemblyEditableMateVerification>();
        var validationResults = new List<AssemblySemanticValidationResult>();
        var poseComparisons = new Dictionary<string, AssemblyContextLeafPoseComparison>(StringComparer.OrdinalIgnoreCase);
        double[]? targetTransformAfterRemate = null;
        try
        {
            sw.OpenDoc(output);
            sw.ActivateDoc(output);
            reopened = true;
            var reopenedAssembly = GetAssemblyDoc();
            var reopenedRoots = PairEnumerateTopLevelInstances(reopenedAssembly);
            var reopenedByGraphHierarchy = ResolveContextGraphRoots(graph, reopenedRoots);
            var requestedReopenedNames = matesToCreate.Select(item => $"MCP_GRAPH_{item.MateName}")
                .Concat(preservedMates.Select(item => item.MateName))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
            var reopenedMates = ReadNamedContextMates((IModelDoc2)reopenedAssembly, requestedReopenedNames);
            foreach (var expected in matesToCreate)
                verifications.Add(VerifyContextEditableMate(expected, reopenedMates));
            foreach (var expected in preservedMates)
                verifications.Add(VerifyEditableMate(expected, reopenedMates));
            foreach (var relation in validationRelations)
                validationResults.Add(MeasureSemanticValidationRelation(reopenedByGraphHierarchy, relation, graph.Modules));

            var target = reopenedByGraphHierarchy[targetModule.HierarchyPath];
            targetTransformAfterRemate = PairTransformArray(target.GetTotalTransform(true) as MathTransform)
                ?? PairTransformArray(target.Transform2);
            targetFullyConstrained = SafeGraphConstrainedStatus(target) == (int)swConstrainedStatus_e.swFullyConstrained;
            int? observedSolvingState = SafeComponentSolvingState(target);
            semanticsMatch = targetModule.SolvingState == null || targetModule.SolvingState == observedSolvingState;
            var poseAfter = CaptureFixedContextLeafPoses(graph, reopenedByGraphHierarchy, excludedPoseModule);
            foreach (var item in poseBefore)
            {
                poseAfter.TryGetValue(item.Key, out var after);
                poseComparisons[item.Key] = CompareContextLeafPoses(item.Value, after ?? new Dictionary<string, double[]>(), 1e-8);
            }
            CompletePhase("reopen-and-verify");
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Context reopen verification failed: {ex.Message}");
            CompletePhase("reopen-and-verify");
        }

        bool mateParametersMatch = verifications.Count == activeMates.Length
            && verifications.All(item => item.Found && item.TypeMatches && item.AlignmentMatches
                && item.DistanceMatches && item.AngleMatches && item.AdvancedOptionsMatch);
        bool validationPassed = validationResults.Count == validationRelations.Count
            && validationResults.All(item => item.Passed);
        bool contextStable = poseComparisons.Count == poseBefore.Count
            && poseComparisons.Values.All(item => item.Stable);
        bool targetConstraintStateAccepted = editPlan.UsesPatchAudit
            ? SafeDirectEditConstraintAccepted(targetFullyConstrained, rootsByGraphHierarchy[targetModule.HierarchyPath])
            : targetFullyConstrained;
        double? displacementDelta = MaximumTransformElementDelta(
            targetTransformBefore, targetTransformAfterDisplacement);
        double? returnError = MaximumTransformElementDelta(
            targetTransformBefore, targetTransformAfterRemate);
        bool? returnedToSourcePose = returnError.HasValue
            ? returnError.Value <= 1e-8
            : null;
        bool initialPoseExperimentPassed = !forceInitialDisplacement
            || (displacementDelta.HasValue
                && displacementDelta.Value > 1e-8
                && returnedToSourcePose == true);
        if (forceInitialDisplacement && !initialPoseExperimentPassed)
            diagnostics.Add(
                $"Initial-pose independence gate failed: displacementDelta={displacementDelta}, returnError={returnError}.");
        bool success = reopened
            && mateResults.Count == matesToCreate.Length
            && mateResults.All(item => item.Success)
            && missingSuppressions.Length == 0
            && mateParametersMatch
            && validationPassed
            && targetConstraintStateAccepted
            && semanticsMatch
            && contextStable
            && initialPoseExperimentPassed;
        phaseDurations["total"] = stopwatch.Elapsed.TotalSeconds;
        return new AssemblyContextMateGraphReconstructionResult(
            success,
            source,
            Path.GetFullPath(effectiveMateGraphPath),
            output,
            targetModule.ModuleToken,
            suppressed.AsReadOnly(),
            activeMates.Length,
            mateResults.Count(item => item.Success),
            reopened,
            mateParametersMatch,
            targetFullyConstrained,
            semanticsMatch,
            mateResults.AsReadOnly(),
            verifications.AsReadOnly(),
            validationResults.AsReadOnly(),
            poseComparisons,
            phaseDurations,
            diagnostics.AsReadOnly(),
            editPlan.UsesPatchAudit ? "direct_existing_component_mate_edit" : "legacy_context_remate",
            preservedMates.Select(item => item.MateName).ToArray(),
            matesToCreate.Select(item => item.MateName).ToArray(),
            sourceMateNames,
            false,
            explicitlyDisplaced,
            targetTransformBefore,
            targetTransformAfterDisplacement,
            targetTransformAfterRemate,
            displacementDelta,
            returnError,
            returnedToSourcePose);
    }

    private static double? MaximumTransformElementDelta(
        IReadOnlyList<double>? left,
        IReadOnlyList<double>? right)
    {
        if (left == null || right == null || left.Count != right.Count || left.Count == 0)
            return null;
        double maximum = 0;
        for (int index = 0; index < left.Count; index++)
            maximum = Math.Max(maximum, Math.Abs(left[index] - right[index]));
        return maximum;
    }

    private static void UnfixContextTargetComponent(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 component)
    {
        document.ClearSelection2(true);
        var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
        if (!component.Select4(false, selectData, false))
            throw new InvalidOperationException(
                $"Could not select target component '{component.Name2}' for unfixing.");
        assembly.UnfixComponent();
        document.ClearSelection2(true);
    }

    private static void VerifyResolvedSessionGraphEndpoints(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IReadOnlyDictionary<string, IComponent2> roots,
        IReadOnlyList<AssemblyModuleMateGraphMate> mates)
    {
        var unresolved = new List<string>();
        foreach (var mate in mates)
        {
            foreach (var endpoint in mate.Endpoints)
            {
                if (ResolveGraphPersistentTargetFace(document, endpoint) != null)
                    continue;
                if (!roots.TryGetValue(endpoint.ModuleHierarchyPath, out var root))
                {
                    unresolved.Add($"{mate.MateName}#{endpoint.Index}:module-root");
                    continue;
                }
                var leaf = ResolveGraphTargetLeaf(assembly, root, endpoint);
                if (leaf == null
                    || ResolveGraphTargetFace(document, leaf, endpoint, out _) == null)
                    unresolved.Add($"{mate.MateName}#{endpoint.Index}:{endpoint.RelativeLeafHierarchyPath}");
            }
        }
        if (unresolved.Count > 0)
            throw new InvalidOperationException(
                "The active source session does not currently expose every graph endpoint: "
                + string.Join(", ", unresolved));
    }

    private static bool SafeDirectEditConstraintAccepted(bool fullyConstrained, IComponent2 sourceTarget)
    {
        if (fullyConstrained)
            return true;
        int status = SafeGraphConstrainedStatus(sourceTarget);
        return status != (int)swConstrainedStatus_e.swOverConstrained;
    }

    internal static AssemblyContextDirectMateEditPlan BuildContextDirectMateEditPlan(
        AssemblyEditableMateGraphDocument graph)
    {
        var activeNames = graph.Mates.Where(item => !item.IsSuppressed)
            .Select(item => item.MateName)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var operations = graph.PatchAudit?.Operations;
        if (operations == null)
        {
            var legacySuppressed = graph.EditPolicy?.SourceMateNamesToSuppress?.Count > 0
                ? graph.EditPolicy.SourceMateNamesToSuppress
                : activeNames.ToArray();
            return new AssemblyContextDirectMateEditPlan(
                false,
                legacySuppressed.ToArray(),
                activeNames.ToArray(),
                [],
                []);
        }

        var create = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var suppress = new HashSet<string>(
            graph.EditPolicy?.SourceMateNamesToSuppress ?? [],
            StringComparer.OrdinalIgnoreCase);
        var removed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var operation in operations.OrderBy(item => item.Index))
        {
            string kind = operation.Operation?.Trim() ?? string.Empty;
            string mateName = operation.MateName?.Trim() ?? string.Empty;
            if (kind.Equals("addMate", StringComparison.OrdinalIgnoreCase))
            {
                if (!string.IsNullOrWhiteSpace(mateName))
                    create.Add(mateName);
                continue;
            }
            if (kind.Equals("removeMate", StringComparison.OrdinalIgnoreCase))
            {
                if (!string.IsNullOrWhiteSpace(mateName))
                {
                    suppress.Add(mateName);
                    removed.Add(mateName);
                }
                continue;
            }
            if (kind.Equals("updateMate", StringComparison.OrdinalIgnoreCase))
            {
                string sourceName = mateName;
                if (operation.Before != null
                    && operation.Before.TryGetValue("MateName", out var beforeName)
                    && beforeName.ValueKind == System.Text.Json.JsonValueKind.String)
                    sourceName = beforeName.GetString() ?? sourceName;
                if (!string.IsNullOrWhiteSpace(sourceName))
                    suppress.Add(sourceName);
                if (!string.IsNullOrWhiteSpace(mateName))
                    create.Add(mateName);
            }
        }
        var unknownCreates = create.Where(name => !activeNames.Contains(name)).ToArray();
        if (unknownCreates.Length > 0)
            throw new InvalidOperationException(
                $"PatchAudit create/update operations reference mates outside the effective graph: {string.Join(", ", unknownCreates)}.");
        var preserve = activeNames.Except(create, StringComparer.OrdinalIgnoreCase).ToArray();
        return new AssemblyContextDirectMateEditPlan(
            true,
            suppress.ToArray(),
            create.ToArray(),
            preserve,
            removed.ToArray());
    }

    private static Dictionary<string, IComponent2> ResolveContextGraphRoots(
        AssemblyEditableMateGraphDocument graph,
        IReadOnlyList<ComponentInstance> roots)
    {
        var result = new Dictionary<string, IComponent2>(StringComparer.OrdinalIgnoreCase);
        foreach (var module in graph.Modules)
        {
            var selected = ResolveGraphModuleRoot(module, roots, allowUniquePathFallback: true);
            if (selected == null)
                throw new InvalidOperationException($"Could not uniquely resolve context module '{module.ModuleToken}' from '{module.Path}'.");
            result[module.HierarchyPath] = selected.Component;
        }
        return result;
    }

    internal static int? SelectGraphModuleRootIndex(
        IReadOnlyList<ComponentInstanceInfo> roots,
        string modulePath,
        string moduleToken,
        string moduleHierarchyPath,
        bool allowUniquePathFallback)
    {
        // A relocated assembly can preserve component occurrence identity while its
        // stored external-reference path still points at the vendor's old directory.
        // The hierarchy path is therefore stronger than absolute path equality.
        var hierarchyMatches = roots
            .Select((info, index) => (info, index))
            .Where(item => string.Equals(
                item.info.HierarchyPath,
                moduleHierarchyPath,
                StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (hierarchyMatches.Length == 1)
            return hierarchyMatches[0].index;
        if (hierarchyMatches.Length > 1)
            return null;

        var pathMatches = roots
            .Select((info, index) => (info, index))
            .Where(item => string.Equals(item.info.Path, modulePath, StringComparison.OrdinalIgnoreCase))
            .ToArray();
        string expectedName = moduleHierarchyPath.Replace('\\', '/').Split('/').Last();
        var exactMatches = pathMatches.Where(item =>
            string.Equals(item.info.HierarchyPath, moduleHierarchyPath, StringComparison.OrdinalIgnoreCase)
            || string.Equals(item.info.Name, expectedName, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (exactMatches.Length == 1)
            return exactMatches[0].index;
        if (exactMatches.Length > 1)
            return null;
        if (!allowUniquePathFallback)
            return null;
        var tokenMatches = pathMatches.Where(item =>
            item.info.Name.Contains(moduleToken, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (tokenMatches.Length == 1)
            return tokenMatches[0].index;
        return pathMatches.Length == 1 ? pathMatches[0].index : null;
    }

    private static ComponentInstance? ResolveGraphModuleRoot(
        AssemblyModuleMateGraphNode module,
        IReadOnlyList<ComponentInstance> roots,
        bool allowUniquePathFallback)
    {
        int? index = SelectGraphModuleRootIndex(
            roots.Select(item => item.Info).ToArray(),
            module.Path,
            module.ModuleToken,
            module.HierarchyPath,
            allowUniquePathFallback);
        return index == null ? null : roots[index.Value];
    }

    private static List<string> SuppressNamedTopLevelMateFeatures(IModelDoc2 document, IReadOnlyList<string> names)
    {
        var requested = names.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var changed = new List<string>();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            if (!requested.Contains(feature.Name))
                continue;
            try
            {
                if (feature.IsSuppressed()
                    || feature.SetSuppression((int)swFeatureSuppressionAction_e.swSuppressFeature))
                    changed.Add(feature.Name);
            }
            catch { }
        }
        return changed;
    }

    private static AssemblyEditableMateVerification VerifyContextEditableMate(
        AssemblyModuleMateGraphMate expected,
        IReadOnlyList<AssemblyModuleMateGraphMate> observed)
    {
        string expectedName = $"MCP_GRAPH_{expected.MateName}";
        var exact = observed.Where(item =>
            string.Equals(item.MateName, expectedName, StringComparison.OrdinalIgnoreCase)).ToArray();
        return VerifyEditableMate(expected with { MateName = expectedName }, exact);
    }

    private static IReadOnlyList<AssemblyModuleMateGraphMate> ReadNamedContextMates(
        IModelDoc2 document,
        IReadOnlyList<string> names)
    {
        var requested = names.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var result = new List<AssemblyModuleMateGraphMate>();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            string name = feature.Name ?? string.Empty;
            if (!requested.Contains(name))
                continue;
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
                continue;
            int mateType = PairSafeMateType(mate);
            int alignment = PairSafeMateAlignment(mate);
            result.Add(new AssemblyModuleMateGraphMate(
                name,
                mateType,
                PairMateTypeName(mateType),
                alignment,
                PairAlignmentName(alignment),
                PairSafeDistance(feature, mateType),
                MateGraphSafeAngle(feature, mateType),
                PairSafeFeatureSuppressed(feature),
                true,
                null,
                [],
                [],
                [],
                ReadGraphMateAdvancedOptions(feature, mate, mateType)));
        }
        return result.AsReadOnly();
    }

    private static Dictionary<string, Dictionary<string, double[]>> CaptureFixedContextLeafPoses(
        AssemblyEditableMateGraphDocument graph,
        IReadOnlyDictionary<string, IComponent2> roots,
        string targetHierarchyPath)
    {
        var result = new Dictionary<string, Dictionary<string, double[]>>(StringComparer.OrdinalIgnoreCase);
        foreach (var module in graph.Modules.Where(module =>
                     !string.Equals(module.HierarchyPath, targetHierarchyPath, StringComparison.OrdinalIgnoreCase)
                     && module.SolvingState == (int)swComponentSolvingOption_e.swComponentFlexibleSolving))
        {
            var poses = new Dictionary<string, double[]>(StringComparer.OrdinalIgnoreCase);
            var root = roots[module.HierarchyPath];
            double[]? rootTransform = null;
            try { rootTransform = PairTransformArray(root.GetTotalTransform(true) as MathTransform); } catch { }
            rootTransform ??= PairTransformArray(root.Transform2);
            if (rootTransform is { Length: >= 13 })
                poses[$"ROOT|{module.HierarchyPath}"] = rootTransform;

            // A flexible module can contain hundreds of leaves.  For the fast
            // context gate, fingerprint only leaves that are semantic endpoints
            // in the effective mate/validation graph.  The later targeted B-Rep
            // gate remains the authoritative proof that all collision-sensitive
            // flexible leaves retained a valid solved pose.
            var endpointPaths = graph.Mates.SelectMany(mate => mate.Endpoints)
                .Concat(graph.SemanticAssemblyPlanAudit?.ValidationRelations?.SelectMany(item => item.Endpoints) ?? [])
                .Where(endpoint => string.Equals(endpoint.ModuleHierarchyPath, module.HierarchyPath, StringComparison.OrdinalIgnoreCase))
                .Select(endpoint => endpoint.RelativeLeafHierarchyPath)
                .Where(path => !string.IsNullOrWhiteSpace(path))
                .Distinct(StringComparer.OrdinalIgnoreCase);
            foreach (string relativePath in endpointPaths)
            {
                var leaf = ResolveGraphTargetLeafByRelativePath(root, relativePath);
                if (leaf == null)
                    continue;
                double[]? transform = null;
                try { transform = PairTransformArray(leaf.GetTotalTransform(true) as MathTransform); } catch { }
                transform ??= PairTransformArray(leaf.Transform2);
                if (transform is { Length: >= 13 })
                    poses[$"ENDPOINT|{relativePath}"] = transform;
            }
            result[module.ModuleToken] = poses;
        }
        return result;
    }

    internal static AssemblyContextLeafPoseComparison CompareContextLeafPoses(
        IReadOnlyDictionary<string, double[]> before,
        IReadOnlyDictionary<string, double[]> after,
        double tolerance)
    {
        var missing = before.Keys.Except(after.Keys, StringComparer.OrdinalIgnoreCase).OrderBy(value => value).ToArray();
        var added = after.Keys.Except(before.Keys, StringComparer.OrdinalIgnoreCase).OrderBy(value => value).ToArray();
        double? maximum = null;
        foreach (string key in before.Keys.Intersect(after.Keys, StringComparer.OrdinalIgnoreCase))
        {
            var left = before[key];
            var right = after[key];
            if (left.Length != right.Length)
            {
                maximum = double.PositiveInfinity;
                break;
            }
            for (int index = 0; index < left.Length; index++)
            {
                double error = Math.Abs(left[index] - right[index]);
                maximum = maximum == null ? error : Math.Max(maximum.Value, error);
            }
        }
        bool stable = missing.Length == 0 && added.Length == 0 && (maximum ?? 0) <= tolerance;
        return new AssemblyContextLeafPoseComparison(
            stable,
            before.Count,
            after.Count,
            missing.Length,
            added.Length,
            maximum,
            tolerance,
            missing,
            added);
    }
}
