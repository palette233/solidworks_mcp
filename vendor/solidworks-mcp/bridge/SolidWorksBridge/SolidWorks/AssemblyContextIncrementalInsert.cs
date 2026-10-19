using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Diagnostics;
using System.Text.Json;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyContextIncrementalInsertResult(
    bool Success,
    string ExecutionMode,
    string SourceAssemblyPath,
    string EffectiveMateGraphPath,
    string OutputAssemblyPath,
    string TargetModuleToken,
    string TargetModuleSourcePath,
    string RemovedOriginalComponentName,
    string InsertedComponentName,
    bool OriginalComponentRemoved,
    bool IndependentComponentInserted,
    bool TargetCaseAnchored,
    bool CaseAnchorPoseMatch,
    double? CaseAnchorTranslationErrorMeters,
    double? CaseAnchorRotationError,
    IReadOnlyList<string> SuppressedSourceMateNames,
    int RequestedMateCount,
    int CreatedMateCount,
    bool Reopened,
    bool ReopenedMateParametersMatch,
    bool TargetFullyConstrained,
    bool TargetConstraintStateAccepted,
    bool ExternalPlacementEquivalencePassed,
    double? ExternalPlacementTranslationErrorMeters,
    double? ExternalPlacementRotationError,
    IReadOnlyList<double>? ReopenedTargetRootTransform,
    bool MateSolveClean,
    bool ComponentSemanticsMatch,
    IReadOnlyList<AssemblyModuleMateExperimentMateResult> MateResults,
    IReadOnlyList<AssemblyEditableMateVerification> MateVerifications,
    IReadOnlyList<AssemblySemanticValidationResult> ValidationResults,
    IReadOnlyDictionary<string, AssemblyContextLeafPoseComparison> ContextPoseComparisons,
    int RequestedTargetLeafPoseAnchorCount,
    int AppliedTargetLeafPoseAnchorCount,
    AssemblyContextLeafPoseComparison? TargetLeafPoseAnchorComparison,
    IReadOnlyDictionary<string, double> PhaseDurationsSeconds,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    /// <summary>
    /// Copy an assembly context, optionally remove an existing target instance, insert a fresh
    /// instance from the target module file at a deterministic non-source pose, and locate it
    /// exclusively through the effective mate graph. This supports both replacement experiments
    /// and true cumulative insertion into a context where the target is not present yet.
    /// </summary>
    public AssemblyContextIncrementalInsertResult InsertComponentInAssemblyContextFromMateGraph(
        string sourceAssemblyPath,
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string targetModuleToken)
    {
        var stopwatch = Stopwatch.StartNew();
        double previousPhaseEnd = 0;
        var phaseDurations = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        string? progressTracePath = null;
        void TraceProgress(string eventType, string? phase = null, string? mateName = null, bool? success = null)
        {
            if (string.IsNullOrWhiteSpace(progressTracePath))
                return;
            File.AppendAllText(
                progressTracePath,
                JsonSerializer.Serialize(new
                {
                    eventType,
                    phase,
                    mateName,
                    success,
                    elapsedSeconds = stopwatch.Elapsed.TotalSeconds,
                    timestampUtc = DateTimeOffset.UtcNow,
                }) + System.Environment.NewLine);
        }
        void CompletePhase(string name)
        {
            double current = stopwatch.Elapsed.TotalSeconds;
            phaseDurations[name] = current - previousPhaseEnd;
            previousPhaseEnd = current;
            TraceProgress("phase-complete", phase: name);
        }

        var graph = LoadAndValidateEditableMateGraph(effectiveMateGraphPath);
        string source = Path.GetFullPath(sourceAssemblyPath ?? string.Empty);
        string output = Path.GetFullPath(outputAssemblyPath ?? string.Empty);
        progressTracePath = output + ".context-insert.progress.jsonl";
        if (!File.Exists(source))
            throw new FileNotFoundException($"Source context assembly was not found: {source}", source);
        if (!string.Equals(Path.GetExtension(source), ".SLDASM", StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetExtension(output), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Source and output paths must end in .SLDASM.");
        if (File.Exists(output))
            throw new IOException($"Refusing to overwrite an existing assembly: {output}");
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        File.WriteAllText(
            progressTracePath,
            JsonSerializer.Serialize(new
            {
                eventType = "transaction-start",
                sourceAssemblyPath = source,
                outputAssemblyPath = output,
                targetModuleToken,
                timestampUtc = DateTimeOffset.UtcNow,
            }) + System.Environment.NewLine);

        var targetMatches = graph.Modules.Where(module =>
            string.Equals(module.ModuleToken, targetModuleToken, StringComparison.OrdinalIgnoreCase)
            || string.Equals(module.HierarchyPath, targetModuleToken, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (targetMatches.Length != 1)
            throw new InvalidOperationException($"Target selector '{targetModuleToken}' resolved to {targetMatches.Length} graph modules; expected one.");
        var targetModule = targetMatches[0];
        var caseAnchorSelectors = graph.EditPolicy?.CaseAnchoredModuleTokens ?? [];
        bool targetCaseAnchored = caseAnchorSelectors.Any(selector =>
            string.Equals(selector, targetModule.ModuleToken, StringComparison.OrdinalIgnoreCase)
            || string.Equals(selector, targetModule.HierarchyPath, StringComparison.OrdinalIgnoreCase));
        bool fixCaseAnchorBeforeMates = targetCaseAnchored
            && graph.EditPolicy?.FixCaseAnchorBeforeMates == true;
        var unmatchedCaseAnchors = caseAnchorSelectors.Where(selector =>
            !string.Equals(selector, targetModule.ModuleToken, StringComparison.OrdinalIgnoreCase)
            && !string.Equals(selector, targetModule.HierarchyPath, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (unmatchedCaseAnchors.Length > 0)
            throw new InvalidOperationException(
                "A context-insert transaction may case-anchor only its inserted target; unexpected selectors: "
                + string.Join(", ", unmatchedCaseAnchors));
        if (!File.Exists(targetModule.Path))
            throw new FileNotFoundException($"Independent target module file was not found: {targetModule.Path}", targetModule.Path);
        var activeMates = graph.Mates.Where(mate => !mate.IsSuppressed).ToArray();
        var validationRelations = graph.SemanticAssemblyPlanAudit?.ValidationRelations ?? [];
        if (activeMates.Any(mate => mate.Endpoints.All(endpoint =>
                !string.Equals(endpoint.ModuleHierarchyPath, targetModule.HierarchyPath, StringComparison.OrdinalIgnoreCase))))
            throw new InvalidOperationException("Every driving mate in the context-insert experiment must reference the inserted target module.");

        File.Copy(source, output, overwrite: false);
        CompletePhase("validate-and-copy-source");
        var diagnostics = new List<string>
        {
            "The source context file was copied before mutation and is never overwritten.",
            "A fresh target instance is inserted from its independent module file; an existing target instance is removed when present.",
            "The inserted target starts at a deterministic non-source pose and is located only by the effective driving mate graph.",
            "Existing context modules keep their parent-assembly configuration and solving state.",
        };
        if (targetCaseAnchored)
            diagnostics.Add(
                "The target uses an explicit project-case source-pose anchor to close residual degrees of freedom that are not fixed by the available source mate bundle; this is not a vendor datum.");
        if (fixCaseAnchorBeforeMates)
            diagnostics.Add(
                "The case-anchored target root is fixed before driving mates are created, so external mates act on the target's flexible internal components instead of translating the entire target root.");

        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        // A retried durable step writes the same job-local file name in a new
        // attempt directory.  If the failed attempt left that title open,
        // OpenDoc6 rejects the new path even though the paths differ.  Clear the
        // exact/job-unique title before the initial open as well as before the
        // later save/reopen verification.
        CloseSavedOutputBeforeReopen(sw, output, diagnostics);
        sw.OpenDoc(output);
        sw.ActivateDoc(output);
        var assembly = GetAssemblyDoc();
        var document = (IModelDoc2)assembly;
        var roots = PairEnumerateTopLevelInstances(assembly);
        int graphSourceReuseCount = graph.Modules.Count(module =>
            string.Equals(module.Path, targetModule.Path, StringComparison.OrdinalIgnoreCase));
        // A cumulative insert must not treat a different occurrence of the same
        // source file as the target to replace.  This is essential for the two
        // Project02 T401 instances: when inserting occurrence -2, occurrence -1
        // is already present and must remain untouched.  Replacement is allowed
        // only when the graph hierarchy/terminal instance name matches exactly.
        var originalTargetInstance = ResolveGraphModuleRoot(
            targetModule,
            roots,
            allowUniquePathFallback: false);
        bool originalTargetWasPresent = originalTargetInstance != null;
        var rootsByGraphHierarchy = ResolveContextGraphRootsForIncrementalInsert(
            graph,
            roots,
            targetModule.HierarchyPath);
        if (originalTargetInstance != null)
            rootsByGraphHierarchy[targetModule.HierarchyPath] = originalTargetInstance.Component;
        CompletePhase("open-and-resolve-graph-roots");

        var poseBefore = CaptureFixedContextLeafPoses(graph, rootsByGraphHierarchy, targetModule.HierarchyPath);
        CompletePhase("capture-flexible-context-before");

        var drivingSourceMateNames = activeMates.Select(mate => mate.MateName)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        // A compiled incremental graph may contain newly-added mates that do not
        // exist in the source assembly yet.  Only the immutable source mates named
        // by the compiler must be suppressed before the original target is removed.
        // Falling back to all active mates preserves backward compatibility with
        // graphs produced before SourceMateNamesToSuppress was introduced.
        var sourceDrivingMateNamesToSuppress = graph.EditPolicy?.SourceMateNamesToSuppress
            ?.Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray()
            ?? drivingSourceMateNames;
        var validationSourceMateNames = validationRelations.Select(relation => relation.RelationName)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var sourceMateNames = sourceDrivingMateNamesToSuppress
            .Concat(validationSourceMateNames)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var suppressed = originalTargetWasPresent
            ? SuppressNamedTopLevelMateFeatures(document, sourceMateNames)
            : [];
        var missingDrivingSuppressions = sourceDrivingMateNamesToSuppress
            .Except(suppressed, StringComparer.OrdinalIgnoreCase)
            .Where(_ => originalTargetWasPresent)
            .ToArray();
        var missingValidationSuppressions = validationSourceMateNames
            .Except(suppressed, StringComparer.OrdinalIgnoreCase)
            .Where(_ => originalTargetWasPresent)
            .ToArray();
        if (missingDrivingSuppressions.Length > 0)
            diagnostics.Add($"Driving source mate features not suppressed: {string.Join(", ", missingDrivingSuppressions)}.");
        if (missingValidationSuppressions.Length > 0)
            diagnostics.Add(
                "Validation-only source mate features were not present or could not be suppressed before the original target was removed: "
                + string.Join(", ", missingValidationSuppressions)
                + ". This is non-fatal because validation relations are measured after rebuilding and do not drive the inserted target.");
        CompletePhase("suppress-source-mates");

        string removedOriginalName = originalTargetInstance?.Component.Name2 ?? "<target-not-present>";
        bool originalRemoved = originalTargetInstance == null
            || DeleteContextTargetComponent(document, originalTargetInstance.Component);
        if (!originalRemoved)
            throw new InvalidOperationException($"SolidWorks failed to remove original target component '{removedOriginalName}'.");
        if (originalTargetInstance != null)
            rootsByGraphHierarchy.Remove(targetModule.HierarchyPath);
        else
            diagnostics.Add("The target was absent from the source context; cumulative insertion proceeded without a removal step.");
        CompletePhase("remove-original-target");

        var insertedTarget = InsertGraphModule(assembly, targetModule);
        string insertedName = insertedTarget.Name2 ?? targetModule.ModuleToken;
        var baseModule = graph.Modules.FirstOrDefault(module =>
            string.Equals(module.ModuleToken, graph.EditPolicy?.BaseModuleToken ?? "A600", StringComparison.OrdinalIgnoreCase))
            ?? graph.Modules.First();
        int initialPlacementVariant = graph.EditPolicy?.InitialPlacementVariant ?? 0;
        if (initialPlacementVariant < 0)
            throw new InvalidOperationException("InitialPlacementVariant must be non-negative.");
        int initialPlacementSeed = graph.Modules.Count + 11 + initialPlacementVariant * 17;
        var initialTransform = targetCaseAnchored
            ? targetModule.SourceTransform
            : BuildDeterministicExperimentTransform(baseModule.SourceTransform, initialPlacementSeed);
        ApplyGraphTransform(insertedTarget, initialTransform);
        diagnostics.Add(
            $"Deterministic non-source placement variant={initialPlacementVariant}, seed={initialPlacementSeed}; "
            + "the variant affects only the pre-mate pose and never drives final placement.");
        rootsByGraphHierarchy[targetModule.HierarchyPath] = insertedTarget;
        CompletePhase("insert-target-at-deterministic-pose");

        // Flexible subassemblies must be restored before mate creation.  Applying the
        // source solving state only after rebuilding the mate bundle can make a healthy
        // source graph appear over-defined (Project02 A700/Distance29 is the regression
        // case).  Re-apply after the bundle as a defensive persistence check below.
        ApplyGraphComponentSolvingState(document, assembly, insertedTarget, targetModule, diagnostics);
        int requestedTargetLeafPoseAnchorCount = graph.EditPolicy?.TargetLeafPoseAnchors?.Count ?? 0;

        if (fixCaseAnchorBeforeMates)
        {
            document.ForceRebuild3(true);
            var observedBeforeMates = PairTransformArray(insertedTarget.Transform2);
            (double preMateTranslationError, double preMateRotationError) = GraphTransformError(
                targetModule.SourceTransform,
                observedBeforeMates);
            if (preMateTranslationError > 1e-7 || preMateRotationError > 1e-7)
                diagnostics.Add(
                    $"Pre-mate case-anchor pose drifted before fixation: translation={preMateTranslationError:G9} m, rotationResidual={preMateRotationError:G9}.");
            else
            {
                FixGraphBaseComponent(document, assembly, insertedTarget);
                // FixComponent can silently switch a flexible subassembly back to rigid
                // solving.  Restore the declared solving semantics so parent-context
                // mates may still drive its internal mechanism while the root remains
                // fixed in the calibrated installation frame.
                ApplyGraphComponentSolvingState(
                    document,
                    assembly,
                    insertedTarget,
                    targetModule,
                    diagnostics);
            }
        }

        var mateResults = new List<AssemblyModuleMateExperimentMateResult>();
        foreach (var mate in activeMates)
        {
            TraceProgress("mate-start", mateName: mate.MateName);
            var mateResult = RebuildGraphMate(
                document,
                assembly,
                rootsByGraphHierarchy,
                mate,
                mate.AdvancedOptions,
                detail => TraceProgress("mate-detail", phase: detail, mateName: mate.MateName));
            mateResults.Add(mateResult);
            TraceProgress("mate-complete", mateName: mate.MateName, success: mateResult.Success);
        }
        double? caseAnchorTranslationError = null;
        double? caseAnchorRotationError = null;
        bool caseAnchorPoseMatch = !targetCaseAnchored;
        if (targetCaseAnchored)
        {
            document.ForceRebuild3(true);
            var observed = PairTransformArray(insertedTarget.Transform2);
            (double translationError, double rotationError) = GraphTransformError(targetModule.SourceTransform, observed);
            caseAnchorTranslationError = translationError;
            caseAnchorRotationError = rotationError;
            caseAnchorPoseMatch = translationError <= 1e-7 && rotationError <= 1e-7;
            if (!caseAnchorPoseMatch)
                diagnostics.Add(
                    $"Case-anchor pose drifted before fixation: translation={translationError:G9} m, rotationResidual={rotationError:G9}.");
            else if (!fixCaseAnchorBeforeMates)
                FixGraphBaseComponent(document, assembly, insertedTarget);
        }
        ApplyGraphComponentSolvingState(document, assembly, insertedTarget, targetModule, diagnostics);
        int appliedTargetLeafPoseAnchorCount = ApplyTargetLeafPoseAnchors(
            document,
            assembly,
            insertedTarget,
            graph.EditPolicy?.TargetLeafPoseAnchors,
            diagnostics);
        document.ForceRebuild3(true);
        CompletePhase("rebuild-driving-mates");

        var save = sw.SaveDocAs(output, sourcePath: null, saveAsCopy: false);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");
        // The public bridge close contract accepts a path and resolves the exact open
        // model before passing its title to ISldWorks.CloseDoc.  Passing GetTitle()
        // back into that path-based contract is ambiguous after Save As: the title can
        // omit the extension and the close can be silently ignored.  The subsequent
        // OpenDoc6 then fails with swFileWithSameTitleAlreadyOpen.  Close by the saved
        // path and verify that neither the exact path nor the generated (job-unique)
        // title remains open before the transaction continues.
        CloseSavedOutputBeforeReopen(sw, output, diagnostics);
        CompletePhase("save-and-close");

        bool reopened = false;
        bool targetFullyConstrained = false;
        bool semanticsMatch = false;
        bool independentInserted = false;
        var verifications = new List<AssemblyEditableMateVerification>();
        var validationResults = new List<AssemblySemanticValidationResult>();
        var poseComparisons = new Dictionary<string, AssemblyContextLeafPoseComparison>(StringComparer.OrdinalIgnoreCase);
        AssemblyContextLeafPoseComparison? targetLeafPoseAnchorComparison = null;
        bool externalPlacementEquivalencePassed = false;
        double? externalPlacementTranslationError = null;
        double? externalPlacementRotationError = null;
        double[]? reopenedTargetRootTransform = null;
        try
        {
            sw.OpenDoc(output);
            sw.ActivateDoc(output);
            reopened = true;
            var reopenedAssembly = GetAssemblyDoc();
            var reopenedRoots = PairEnumerateTopLevelInstances(reopenedAssembly);
            var reopenedTargets = reopenedRoots.Where(root =>
                string.Equals(root.Info.Path, targetModule.Path, StringComparison.OrdinalIgnoreCase)).ToArray();
            var reopenedInsertedTarget = reopenedTargets.Where(root =>
                string.Equals(root.Info.Name, insertedName, StringComparison.OrdinalIgnoreCase)
                || string.Equals(root.Info.HierarchyPath, insertedName, StringComparison.OrdinalIgnoreCase)).ToArray();
            if (reopenedInsertedTarget.Length == 0)
            {
                var graphResolvedTarget = ResolveGraphModuleRoot(
                    targetModule,
                    reopenedRoots,
                    allowUniquePathFallback: graphSourceReuseCount == 1);
                reopenedInsertedTarget = graphResolvedTarget == null ? [] : [graphResolvedTarget];
            }
            independentInserted = reopenedInsertedTarget.Length == 1;
            if (!independentInserted)
                diagnostics.Add(
                    $"Expected one reopened target instance '{insertedName}' sourced from '{targetModule.Path}', "
                    + $"found {reopenedInsertedTarget.Length} exact instances among {reopenedTargets.Length} same-file instances.");
            if (!independentInserted)
                throw new InvalidOperationException(
                    $"Could not uniquely resolve the reopened inserted target '{insertedName}'.");

            // The source assembly may legitimately contain another occurrence of the
            // same target file (Project05 has two P000 occurrences).  Resolving the
            // whole graph from path/token first is ambiguous after the replacement
            // receives a new occurrence suffix.  Resolve fixed context independently,
            // then bind the target by the exact name captured at insertion time.
            var reopenedByGraphHierarchy = ResolveContextGraphRootsForIncrementalInsert(
                graph,
                reopenedRoots,
                targetModule.HierarchyPath);
            reopenedByGraphHierarchy[targetModule.HierarchyPath]
                = reopenedInsertedTarget[0].Component;

            var reopenedMates = ReadNamedContextMates(
                (IModelDoc2)reopenedAssembly,
                activeMates.Select(item => $"MCP_GRAPH_{item.MateName}").ToArray());
            foreach (var expected in activeMates)
                verifications.Add(VerifyContextEditableMate(expected, reopenedMates));
            foreach (var relation in validationRelations)
                validationResults.Add(MeasureSemanticValidationRelation(reopenedByGraphHierarchy, relation, graph.Modules));

            var target = reopenedByGraphHierarchy[targetModule.HierarchyPath];
            targetFullyConstrained = SafeGraphConstrainedStatus(target) == (int)swConstrainedStatus_e.swFullyConstrained;
            int? observedSolvingState = SafeComponentSolvingState(target);
            semanticsMatch = targetModule.SolvingState == null || targetModule.SolvingState == observedSolvingState;
            var observedTargetTransform = PairTransformArray(target.Transform2);
            reopenedTargetRootTransform = observedTargetTransform;
            (double targetTranslationError, double targetRotationError) = GraphTransformError(
                targetModule.SourceTransform,
                observedTargetTransform);
            externalPlacementTranslationError = targetTranslationError;
            externalPlacementRotationError = targetRotationError;
            externalPlacementEquivalencePassed = !targetCaseAnchored
                && requestedTargetLeafPoseAnchorCount == 0
                && targetTranslationError <= 1e-8
                && targetRotationError <= 1e-8;
            diagnostics.Add(
                "External placement witness compares the reopened target root transform with the graph-declared target transform; "
                + "it is validation-only and never drives component placement.");
            var poseAfter = CaptureFixedContextLeafPoses(graph, reopenedByGraphHierarchy, targetModule.HierarchyPath);
            foreach (var item in poseBefore)
            {
                poseAfter.TryGetValue(item.Key, out var after);
                poseComparisons[item.Key] = CompareContextLeafPoses(item.Value, after ?? new Dictionary<string, double[]>(), 1e-8);
            }
            if (requestedTargetLeafPoseAnchorCount > 0)
            {
                var expectedAnchors = (graph.EditPolicy?.TargetLeafPoseAnchors ?? [])
                    .ToDictionary(item => item.RelativeLeafHierarchyPath, item => item.Transform, StringComparer.OrdinalIgnoreCase);
                var observedAnchors = CaptureTargetLeafPoseAnchors(target, graph.EditPolicy?.TargetLeafPoseAnchors);
                targetLeafPoseAnchorComparison = CompareContextLeafPoses(expectedAnchors, observedAnchors, 1e-8);
            }
            CompletePhase("reopen-and-verify");
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Context-insert reopen verification failed: {ex.Message}");
            CompletePhase("reopen-and-verify");
        }

        bool mateParametersMatch = verifications.Count == activeMates.Length
            && verifications.All(item => item.Found && item.TypeMatches && item.AlignmentMatches
                && item.DistanceMatches && item.AngleMatches && item.AdvancedOptionsMatch);
        bool validationPassed = validationResults.Count == validationRelations.Count
            && validationResults.All(item => item.Passed);
        bool contextStable = poseComparisons.Count == poseBefore.Count
            && poseComparisons.Values.All(item => item.Stable);
        bool targetIsSourceFlexible = targetModule.SolvingState
            == (int)swComponentSolvingOption_e.swComponentFlexibleSolving;
        bool targetConstraintStateAccepted = targetFullyConstrained
            || (targetIsSourceFlexible && semanticsMatch);
        bool targetLeafPoseAnchorsAccepted = requestedTargetLeafPoseAnchorCount == 0
            || (appliedTargetLeafPoseAnchorCount == requestedTargetLeafPoseAnchorCount
                && targetLeafPoseAnchorComparison?.Stable == true);
        bool mateSolveClean = mateResults.Count == activeMates.Length
            && mateResults.All(item => item.Success
                && string.Equals(
                    item.ErrorName,
                    nameof(swAddMateError_e.swAddMateError_NoError),
                    StringComparison.Ordinal));
        bool success = reopened
            && originalRemoved
            && independentInserted
            && mateSolveClean
            && missingDrivingSuppressions.Length == 0
            && mateParametersMatch
            && validationPassed
            && caseAnchorPoseMatch
            && targetConstraintStateAccepted
            && semanticsMatch
            && contextStable
            && targetLeafPoseAnchorsAccepted;
        phaseDurations["total"] = stopwatch.Elapsed.TotalSeconds;
        return new AssemblyContextIncrementalInsertResult(
            success,
            "context_incremental_insert",
            source,
            Path.GetFullPath(effectiveMateGraphPath),
            output,
            targetModule.ModuleToken,
            targetModule.Path,
            removedOriginalName,
            insertedName,
            originalRemoved,
            independentInserted,
            targetCaseAnchored,
            caseAnchorPoseMatch,
            caseAnchorTranslationError,
            caseAnchorRotationError,
            suppressed.AsReadOnly(),
            activeMates.Length,
            mateResults.Count(item => item.Success),
            reopened,
            mateParametersMatch,
            targetFullyConstrained,
            targetConstraintStateAccepted,
            externalPlacementEquivalencePassed,
            externalPlacementTranslationError,
            externalPlacementRotationError,
            reopenedTargetRootTransform,
            mateSolveClean,
            semanticsMatch,
            mateResults.AsReadOnly(),
            verifications.AsReadOnly(),
            validationResults.AsReadOnly(),
            poseComparisons,
            requestedTargetLeafPoseAnchorCount,
            appliedTargetLeafPoseAnchorCount,
            targetLeafPoseAnchorComparison,
            phaseDurations,
            diagnostics.AsReadOnly());
    }

    private static Dictionary<string, IComponent2> ResolveContextGraphRootsForIncrementalInsert(
        AssemblyEditableMateGraphDocument graph,
        IReadOnlyList<ComponentInstance> roots,
        string targetHierarchyPath)
    {
        var result = new Dictionary<string, IComponent2>(StringComparer.OrdinalIgnoreCase);
        foreach (var module in graph.Modules)
        {
            if (string.Equals(module.HierarchyPath, targetHierarchyPath, StringComparison.OrdinalIgnoreCase))
                continue;
            var selected = ResolveGraphModuleRoot(module, roots, allowUniquePathFallback: true);
            if (selected == null)
                throw new InvalidOperationException(
                    $"Could not uniquely resolve context module '{module.ModuleToken}' from '{module.Path}'.");
            result[module.HierarchyPath] = selected.Component;
        }
        return result;
    }

    private void ApplyGraphTransformToLeaf(IComponent2 component, double[] transform)
        => ApplyGraphTransform(component, transform);

    private int ApplyTargetLeafPoseAnchors(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 targetRoot,
        IReadOnlyList<AssemblyContextLeafPoseAnchor>? anchors,
        ICollection<string> diagnostics)
    {
        int applied = 0;
        foreach (var anchor in anchors ?? [])
        {
            var leaf = ResolveGraphTargetLeafByRelativePath(targetRoot, anchor.RelativeLeafHierarchyPath);
            if (leaf == null)
            {
                diagnostics.Add($"Target leaf pose anchor could not resolve '{anchor.RelativeLeafHierarchyPath}'.");
                continue;
            }
            try
            {
                ApplyAnchorComponentSolvingState(
                    document,
                    assembly,
                    leaf,
                    anchor,
                    diagnostics);
                ApplyGraphTransformToLeaf(leaf, anchor.Transform);
                if (anchor.FixAfterApply)
                {
                    FixGraphBaseComponent(document, assembly, leaf);
                    diagnostics.Add(
                        $"Target state anchor fixed '{anchor.RelativeLeafHierarchyPath}' after applying its prototype checkpoint transform.");
                }
                applied++;
            }
            catch (Exception ex)
            {
                diagnostics.Add($"Target leaf pose anchor failed for '{anchor.RelativeLeafHierarchyPath}': {ex.Message}");
            }
        }
        return applied;
    }

    private static void ApplyAnchorComponentSolvingState(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 component,
        AssemblyContextLeafPoseAnchor anchor,
        ICollection<string> diagnostics)
    {
        if (anchor.SolvingState is not int solvingState)
            return;
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
                throw new InvalidOperationException("anchor component selection failed");
            bool changed = assembly.CompConfigProperties5(
                suppression,
                solvingState,
                visible,
                true,
                component.ReferencedConfiguration ?? string.Empty,
                excludeFromBom,
                isEnvelope);
            if (!changed || component.Solving != solvingState)
                diagnostics.Add(
                    $"Target state anchor solving state for '{anchor.RelativeLeafHierarchyPath}' was not restored exactly.");
            else
                diagnostics.Add(
                    $"Target state anchor restored solving state {solvingState} for '{anchor.RelativeLeafHierarchyPath}'.");
        }
        catch (Exception ex)
        {
            diagnostics.Add(
                $"Target state anchor solving state restore failed for '{anchor.RelativeLeafHierarchyPath}': {ex.Message}");
        }
        finally
        {
            document.ClearSelection2(true);
        }
    }

    private static Dictionary<string, double[]> CaptureTargetLeafPoseAnchors(
        IComponent2 targetRoot,
        IReadOnlyList<AssemblyContextLeafPoseAnchor>? anchors)
    {
        var result = new Dictionary<string, double[]>(StringComparer.OrdinalIgnoreCase);
        foreach (var anchor in anchors ?? [])
        {
            var leaf = ResolveGraphTargetLeafByRelativePath(targetRoot, anchor.RelativeLeafHierarchyPath);
            double[]? transform = leaf == null ? null : PairTransformArray(leaf.Transform2);
            if (transform is { Length: >= 13 })
                result[anchor.RelativeLeafHierarchyPath] = transform;
        }
        return result;
    }

    private static void CloseSavedOutputBeforeReopen(
        ISldWorksApp sw,
        string outputPath,
        ICollection<string> diagnostics)
    {
        string normalizedOutput = Path.GetFullPath(outputPath);
        string outputFileName = Path.GetFileName(normalizedOutput);
        string outputStem = Path.GetFileNameWithoutExtension(normalizedOutput);

        // First use the normal path-based close contract.
        sw.CloseDoc(normalizedOutput);

        static bool IsConflict(
            SwDocumentInfo document,
            string normalizedPath,
            string fileName,
            string stem)
        {
            bool exactPath = !string.IsNullOrWhiteSpace(document.Path)
                && string.Equals(
                    Path.GetFullPath(document.Path),
                    normalizedPath,
                    StringComparison.OrdinalIgnoreCase);
            bool samePathFileName = !string.IsNullOrWhiteSpace(document.Path)
                && string.Equals(
                    Path.GetFileName(document.Path),
                    fileName,
                    StringComparison.OrdinalIgnoreCase);
            bool sameTitle = string.Equals(document.Title, fileName, StringComparison.OrdinalIgnoreCase)
                || string.Equals(document.Title, stem, StringComparison.OrdinalIgnoreCase);
            return exactPath || samePathFileName || sameTitle;
        }

        // Close any stale same-title instance left by a SolidWorks Save As identity
        // transition. The generated output names are job-local, so this cannot match
        // a user source document unless that source already violates the unique-title
        // precondition that OpenDoc6 itself enforces.
        var conflicts = sw.ListDocs()
            .Where(document => IsConflict(document, normalizedOutput, outputFileName, outputStem))
            .ToArray();
        foreach (var conflict in conflicts)
        {
            string selector = !string.IsNullOrWhiteSpace(conflict.Path)
                ? conflict.Path
                : conflict.Title;
            sw.CloseDoc(selector);
        }

        var remaining = sw.ListDocs()
            .Where(document => IsConflict(document, normalizedOutput, outputFileName, outputStem))
            .ToArray();
        if (remaining.Length > 0)
        {
            throw new InvalidOperationException(
                $"Saved output remained open before reopen: '{normalizedOutput}'. "
                + "Open conflicts: "
                + string.Join(", ", remaining.Select(item => $"{item.Title} [{item.Path}]")));
        }

        diagnostics.Add(
            conflicts.Length == 0
                ? "Saved output document was closed by exact path before reopen."
                : $"Closed {conflicts.Length} stale same-title saved-output document(s) before reopen.");
    }

    private static bool DeleteContextTargetComponent(IModelDoc2 document, IComponent2 component)
    {
        document.ClearSelection2(true);
        try
        {
            var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
            if (!component.Select4(false, selectData, false))
                return false;
            return document.Extension.DeleteSelection2(0);
        }
        finally
        {
            document.ClearSelection2(true);
        }
    }
}
