using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Text;
using System.Text.Json;
using System.Diagnostics;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyEditableMateGraphPolicy(
    string? BaseModuleToken,
    string? InitialPlacementMode,
    bool SourceGraphImmutable,
    IReadOnlyList<string>? FixedModuleTokens = null,
    IReadOnlyList<string>? CaseAnchoredModuleTokens = null,
    IReadOnlyList<AssemblyContextLeafPoseAnchor>? TargetLeafPoseAnchors = null,
    bool FixCaseAnchorBeforeMates = false,
    IReadOnlyList<string>? SourceMateNamesToSuppress = null,
    int InitialPlacementVariant = 0);

public record AssemblyMateGraphPatchOperation(
    int Index,
    string Operation,
    string? MateName,
    IReadOnlyDictionary<string, JsonElement>? Before = null,
    IReadOnlyDictionary<string, JsonElement>? After = null);

public record AssemblyMateGraphPatchAudit(
    string? PatchSchemaVersion,
    string? PatchSha256,
    int OperationCount,
    IReadOnlyList<AssemblyMateGraphPatchOperation>? Operations,
    IReadOnlyList<string>? Warnings);

public record AssemblyContextLeafPoseAnchor(
    string RelativeLeafHierarchyPath,
    double[] Transform,
    string? Evidence = null,
    bool FixAfterApply = false,
    int? SolvingState = null);

public record AssemblySemanticValidationTolerance(
    double? DistanceMeters,
    double? AngleRadians);

public record AssemblySemanticValidationRelation(
    string RelationName,
    int RelationType,
    string RelationTypeName,
    IReadOnlyList<string> EndpointIds,
    IReadOnlyList<AssemblyModuleMateGraphEndpoint> Endpoints,
    double? ExpectedDistanceMeters,
    double? ExpectedAngleRadians,
    AssemblySemanticValidationTolerance? Tolerance,
    string? Status);

public record AssemblySemanticAssemblyPlanAudit(
    IReadOnlyList<AssemblySemanticValidationRelation>? ValidationRelations);

public record AssemblyEditableMateGraphDocument(
    string SchemaVersion,
    int ModuleCount,
    int InterModuleMateCount,
    IReadOnlyList<AssemblyModuleMateGraphNode> Modules,
    IReadOnlyList<AssemblyModuleMateGraphMate> Mates,
    AssemblyEditableMateGraphPolicy? EditPolicy,
    AssemblySemanticAssemblyPlanAudit? SemanticAssemblyPlanAudit = null,
    AssemblyMateGraphPatchAudit? PatchAudit = null);

public record AssemblySemanticValidationResult(
    string RelationName,
    string RelationTypeName,
    bool EndpointsResolved,
    double? ExpectedDistanceMeters,
    double? MeasuredDistanceMeters,
    double? AbsoluteErrorMeters,
    double? ToleranceMeters,
    bool Passed,
    IReadOnlyList<string> EndpointResolutionStrategies,
    string Message,
    double? ExpectedAngleRadians = null,
    double? MeasuredAngleRadians = null,
    double? AbsoluteAngleErrorRadians = null,
    double? AngleToleranceRadians = null);

public record AssemblyEditableMateVerification(
    string ExpectedMateName,
    string? ObservedMateName,
    bool Found,
    bool TypeMatches,
    bool AlignmentMatches,
    bool DistanceMatches,
    bool AngleMatches,
    bool AdvancedOptionsMatch,
    double? ExpectedDistance,
    double? ObservedDistance,
    double? ExpectedAngle,
    double? ObservedAngle);

public record AssemblyEditableMateComponentStatus(
    string ModuleToken,
    string SourceHierarchyPath,
    string? TargetHierarchyPath,
    int ConstrainedStatus,
    string ConstrainedStatusName,
    int? ExpectedSolvingState,
    string? ExpectedSolvingStateName,
    int? ObservedSolvingState,
    string? ObservedSolvingStateName,
    bool SolvingStateMatches,
    double[]? WorldTransform,
    double[]? BoundingBoxWorld);

public record AssemblyEditableMateGraphReconstructionResult(
    bool Success,
    string EffectiveMateGraphPath,
    string OutputAssemblyPath,
    string BaseModuleToken,
    string InitialPlacementMode,
    int RequestedModuleCount,
    int RequestedActiveMateCount,
    int AttemptedMateCount,
    int CreatedMateCount,
    int FailedMateCount,
    bool Reopened,
    int ReopenedModuleCount,
    int ReopenedMateCount,
    bool ReopenedMateParametersMatch,
    bool MateCreationErrorsClear,
    bool TransientMateCreationErrorsResolvedOnReopen,
    bool ReopenedMateFeatureErrorsClear,
    bool ReopenedComponentsNotOverConstrained,
    bool ReopenedComponentSemanticsMatch,
    IReadOnlyList<AssemblyModuleMateExperimentMateResult> MateResults,
    IReadOnlyList<AssemblyEditableMateVerification> MateVerifications,
    IReadOnlyList<AssemblyEditableMateComponentStatus> ComponentStatuses,
    IReadOnlyList<AssemblySemanticValidationResult> ValidationResults,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    private static readonly JsonSerializerOptions EditableMateGraphJsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    /// <summary>
    /// Rebuild a new assembly from an already-compiled editable mate-graph JSON.  Unlike the
    /// A/B/C experiment, this method never re-exports mates from the source prototype.
    /// </summary>
    public AssemblyEditableMateGraphReconstructionResult RebuildAssemblyFromMateGraph(
        string effectiveMateGraphPath,
        string outputAssemblyPath,
        string? baseModuleToken = null,
        string? initialPlacementMode = null)
    {
        var rebuildClock = Stopwatch.StartNew();
        long previousPhaseMilliseconds = 0;
        void MarkPhase(string phase, IList<string>? targetDiagnostics = null)
        {
            long elapsed = rebuildClock.ElapsedMilliseconds;
            long delta = elapsed - previousPhaseMilliseconds;
            previousPhaseMilliseconds = elapsed;
            string message = $"TIMING {phase}: phaseSeconds={delta / 1000.0:F3}, totalSeconds={elapsed / 1000.0:F3}";
            targetDiagnostics?.Add(message);
            Console.Error.WriteLine($"[AssemblyRebuildPhase] {message}");
        }

        var graph = LoadAndValidateEditableMateGraph(effectiveMateGraphPath);
        MarkPhase("load-effective-graph");
        string normalizedOutput = Path.GetFullPath(outputAssemblyPath ?? string.Empty);
        if (!string.Equals(Path.GetExtension(normalizedOutput), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("outputAssemblyPath must end in .SLDASM.", nameof(outputAssemblyPath));
        if (File.Exists(normalizedOutput))
            throw new IOException($"Refusing to overwrite an existing assembly: {normalizedOutput}");

        string baseSelector = string.IsNullOrWhiteSpace(baseModuleToken)
            ? graph.EditPolicy?.BaseModuleToken ?? "A600"
            : baseModuleToken.Trim();
        string placementMode = (string.IsNullOrWhiteSpace(initialPlacementMode)
            ? graph.EditPolicy?.InitialPlacementMode ?? "deterministic"
            : initialPlacementMode).Trim().ToLowerInvariant().Replace('-', '_');
        if (placementMode is not ("deterministic" or "source_pose"))
            throw new ArgumentException("initialPlacementMode must be deterministic or source_pose.", nameof(initialPlacementMode));

        var baseMatches = graph.Modules.Where(module =>
            string.Equals(module.ModuleToken, baseSelector, StringComparison.OrdinalIgnoreCase)
            || string.Equals(module.HierarchyPath, baseSelector, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (baseMatches.Length != 1)
            throw new InvalidOperationException($"Base selector '{baseSelector}' resolved to {baseMatches.Length} modules; expected exactly one.");
        var baseModule = baseMatches[0];
        var fixedModules = new Dictionary<string, AssemblyModuleMateGraphNode>(StringComparer.OrdinalIgnoreCase)
        {
            [baseModule.HierarchyPath] = baseModule,
        };
        foreach (string selector in graph.EditPolicy?.FixedModuleTokens ?? [])
        {
            var matches = graph.Modules.Where(module =>
                string.Equals(module.ModuleToken, selector, StringComparison.OrdinalIgnoreCase)
                || string.Equals(module.HierarchyPath, selector, StringComparison.OrdinalIgnoreCase)).ToArray();
            if (matches.Length != 1)
                throw new InvalidOperationException($"Fixed module selector '{selector}' resolved to {matches.Length} modules; expected exactly one.");
            fixedModules[matches[0].HierarchyPath] = matches[0];
        }
        var activeMates = graph.Mates.Where(mate => !mate.IsSuppressed).ToArray();
        IReadOnlyList<AssemblySemanticValidationRelation> validationRelations =
            graph.SemanticAssemblyPlanAudit?.ValidationRelations ?? [];
        var diagnostics = new List<string>
        {
            "The effective mate graph was read from JSON; the source prototype mate tree was not enumerated.",
            $"Fixed context modules: {string.Join(", ", fixedModules.Values.Select(item => item.ModuleToken))}.",
        };
        MarkPhase("validate-policy", diagnostics);

        Directory.CreateDirectory(Path.GetDirectoryName(normalizedOutput)!);
        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        MarkPhase("connect-solidworks", diagnostics);
        // Do not open every module as a standalone document before creating the
        // target assembly.  Large flexible modules can spend minutes resolving
        // in an irrelevant standalone context.  AddComponent5 loads each source
        // directly into the target assembly and InsertGraphModule retains a
        // guarded standalone-open fallback if SolidWorks requires it.
        diagnostics.Add("Module source documents are loaded on demand by AddComponent5; the prototype assembly is not opened or enumerated.");
        string template = sw.GetDefaultTemplatePath(SwDocType.Assembly);
        sw.NewDoc(template);
        MarkPhase("create-target-assembly", diagnostics);
        var targetAssembly = GetAssemblyDoc();
        var targetDocument = (IModelDoc2)targetAssembly;

        var orderedModules = graph.Modules
            .OrderBy(module => string.Equals(module.HierarchyPath, baseModule.HierarchyPath, StringComparison.OrdinalIgnoreCase) ? 0 : 1)
            .ThenBy(module => module.ModuleToken, StringComparer.OrdinalIgnoreCase)
            .ThenBy(module => module.HierarchyPath, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var insertedBySourceHierarchy = new Dictionary<string, IComponent2>(StringComparer.OrdinalIgnoreCase);
        var targetNameBySourceHierarchy = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (int index = 0; index < orderedModules.Length; index++)
        {
            var module = orderedModules[index];
            var inserted = InsertGraphModule(targetAssembly, module);
            MarkPhase($"insert-module-{module.ModuleToken}", diagnostics);
            insertedBySourceHierarchy.Add(module.HierarchyPath, inserted);
            targetNameBySourceHierarchy.Add(module.HierarchyPath, inserted.Name2 ?? Path.GetFileNameWithoutExtension(module.Path));
            bool isBase = string.Equals(module.HierarchyPath, baseModule.HierarchyPath, StringComparison.OrdinalIgnoreCase);
            bool isFixedContext = fixedModules.ContainsKey(module.HierarchyPath);
            double[]? transform = placementMode == "source_pose" || isBase || isFixedContext
                ? module.SourceTransform
                : BuildDeterministicExperimentTransform(baseModule.SourceTransform, index);
            ApplyGraphTransform(inserted, transform);
        }
        try
        {
            targetAssembly.ResolveAllLightWeightComponents(true);
            diagnostics.Add("All inserted module subtrees were explicitly resolved before face recovery.");
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Explicit lightweight resolution was best-effort: {ex.Message}");
        }
        MarkPhase("resolve-components", diagnostics);
        targetDocument.ForceRebuild3(false);
        MarkPhase("initial-force-rebuild", diagnostics);
        foreach (var fixedModule in fixedModules.Values)
            FixGraphBaseComponent(targetDocument, targetAssembly, insertedBySourceHierarchy[fixedModule.HierarchyPath]);
        MarkPhase("fix-context-modules", diagnostics);

        var mateResults = new List<AssemblyModuleMateExperimentMateResult>();
        foreach (var mate in activeMates)
            mateResults.Add(RebuildGraphMate(targetDocument, targetAssembly, insertedBySourceHierarchy, mate, mate.AdvancedOptions));
        MarkPhase("rebuild-mates", diagnostics);
        // Restore the graph's flexible/rigid state after the parent mate graph
        // is complete so flexible internal DOF are solved in their final context.
        foreach (var module in orderedModules)
        {
            ApplyGraphComponentSolvingState(
                targetDocument,
                targetAssembly,
                insertedBySourceHierarchy[module.HierarchyPath],
                module,
                diagnostics);
        }
        MarkPhase("apply-solving-state", diagnostics);
        targetDocument.ForceRebuild3(false);
        MarkPhase("final-force-rebuild", diagnostics);

        var save = sw.SaveDocAs(normalizedOutput, sourcePath: null, saveAsCopy: false);
        MarkPhase("save-assembly", diagnostics);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");
        string savedDocumentTitle = targetDocument.GetTitle() ?? Path.GetFileName(normalizedOutput);
        try { sw.CloseDoc(savedDocumentTitle); }
        catch (Exception ex) { diagnostics.Add($"Close before verification was best-effort: {ex.Message}"); }

        bool reopened = false;
        int reopenedModuleCount = 0;
        int reopenedMateCount = 0;
        var verifications = new List<AssemblyEditableMateVerification>();
        var componentStatuses = new List<AssemblyEditableMateComponentStatus>();
        var validationResults = new List<AssemblySemanticValidationResult>();
        IReadOnlyList<AssemblyModuleMateGraphMate> reopenedMates = [];
        try
        {
            sw.OpenDoc(normalizedOutput);
            sw.ActivateDoc(normalizedOutput);
            reopened = true;
            var reopenedAssembly = GetAssemblyDoc();
            reopenedModuleCount = PairEnumerateTopLevelInstances(reopenedAssembly).Count;
            var reopenedRoots = PairEnumerateTopLevelInstances(reopenedAssembly);
            var reopenedBySourceHierarchy = new Dictionary<string, IComponent2>(StringComparer.OrdinalIgnoreCase);
            foreach (var module in graph.Modules)
            {
                string targetName = targetNameBySourceHierarchy[module.HierarchyPath];
                var target = reopenedRoots.SingleOrDefault(item =>
                    string.Equals(item.Info.Name, targetName, StringComparison.OrdinalIgnoreCase));
                int constrainedStatus = target == null
                    ? (int)swConstrainedStatus_e.swUnknownConstraint
                    : SafeGraphConstrainedStatus(target.Component);
                int? observedSolvingState = target == null ? null : SafeComponentSolvingState(target.Component);
                if (target != null)
                    reopenedBySourceHierarchy[module.HierarchyPath] = target.Component;
                componentStatuses.Add(new AssemblyEditableMateComponentStatus(
                    module.ModuleToken,
                    module.HierarchyPath,
                    target?.Info.HierarchyPath,
                    constrainedStatus,
                    GraphConstrainedStatusName(constrainedStatus),
                    module.SolvingState,
                    module.SolvingStateName,
                    observedSolvingState,
                    target == null ? null : SafeComponentSolvingStateName(target.Component),
                    module.SolvingState == null || module.SolvingState == observedSolvingState,
                    target == null ? null : PairTransformArray(target.Component.Transform2),
                    target == null ? null : GetComponentBoundingBox(target.Component)));
            }
            var moduleTokens = graph.Modules.Select(module => module.ModuleToken).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            if (moduleTokens.Length >= 2)
            {
                var reopenedGraph = ExportModuleMateGraph(normalizedOutput, moduleTokens, saveJson: false);
                reopenedMates = reopenedGraph.Mates;
                reopenedMateCount = reopenedGraph.InterModuleMateCount;
                foreach (var expected in activeMates)
                    verifications.Add(VerifyEditableMate(expected, reopenedGraph.Mates));
            }
            else
            {
                diagnostics.Add("Single-module base assembly has no inter-module mate graph to re-export.");
            }
            foreach (var relation in validationRelations)
                validationResults.Add(MeasureSemanticValidationRelation(reopenedBySourceHierarchy, relation, graph.Modules));
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Reopen verification failed: {ex.Message}");
        }
        MarkPhase("reopen-and-verify", diagnostics);

        int createdCount = mateResults.Count(item => item.Success);
        bool parameterMatch = verifications.Count == activeMates.Length
            && verifications.All(item => item.Found && item.TypeMatches && item.AlignmentMatches && item.DistanceMatches && item.AngleMatches && item.AdvancedOptionsMatch);
        bool creationErrorsClear = mateResults.All(item =>
            item.Success
            && string.Equals(item.ErrorName, nameof(swAddMateError_e.swAddMateError_NoError), StringComparison.Ordinal));
        bool reopenedMateFeatureErrorsClear = reopenedMates.Count == activeMates.Length
            && reopenedMates.All(item => (item.AdvancedOptions?.SourceFeatureErrorCode ?? 0) == 0);
        bool transientCreationErrorsResolved = !creationErrorsClear
            && reopenedMateFeatureErrorsClear
            && parameterMatch;
        bool componentsNotOverConstrained = componentStatuses.Count == graph.Modules.Count
            && componentStatuses.All(item => item.ConstrainedStatus != (int)swConstrainedStatus_e.swOverConstrained);
        bool componentSemanticsMatch = componentStatuses.Count == graph.Modules.Count
            && componentStatuses.All(item => item.SolvingStateMatches);
        bool validationRelationsPassed = validationResults.Count == validationRelations.Count
            && validationResults.All(item => item.Passed);
        bool success = reopened
            && File.Exists(normalizedOutput)
            && reopenedModuleCount == graph.Modules.Count
            && createdCount == activeMates.Length
            && reopenedMateCount == activeMates.Length
            && parameterMatch
            && (creationErrorsClear || transientCreationErrorsResolved)
            && componentsNotOverConstrained
            && componentSemanticsMatch
            && validationRelationsPassed;
        return new AssemblyEditableMateGraphReconstructionResult(
            success,
            Path.GetFullPath(effectiveMateGraphPath),
            normalizedOutput,
            baseModule.ModuleToken,
            placementMode,
            graph.Modules.Count,
            activeMates.Length,
            mateResults.Count,
            createdCount,
            mateResults.Count - createdCount,
            reopened,
            reopenedModuleCount,
            reopenedMateCount,
            parameterMatch,
            creationErrorsClear,
            transientCreationErrorsResolved,
            reopenedMateFeatureErrorsClear,
            componentsNotOverConstrained,
            componentSemanticsMatch,
            mateResults.AsReadOnly(),
            verifications.AsReadOnly(),
            componentStatuses.AsReadOnly(),
            validationResults.AsReadOnly(),
            diagnostics.AsReadOnly());
    }

    private static AssemblySemanticValidationResult MeasureSemanticValidationRelation(
        IReadOnlyDictionary<string, IComponent2> roots,
        AssemblySemanticValidationRelation relation,
        IReadOnlyList<AssemblyModuleMateGraphNode> modules)
    {
        var modulesByHierarchy = modules.ToDictionary(item => item.HierarchyPath, StringComparer.OrdinalIgnoreCase);
        var strategies = new List<string>();
        var centers = new List<double[]>();
        var normals = new List<double[]>();
        var cylinderOrigins = new List<double[]>();
        var cylinderAxes = new List<double[]>();
        bool isConcentric = relation.RelationType == (int)swMateType_e.swMateCONCENTRIC;
        foreach (var endpoint in relation.Endpoints.OrderBy(item => item.Index))
        {
            if (!roots.TryGetValue(endpoint.ModuleHierarchyPath, out var root))
                return ValidationFailure(relation, strategies, $"No reopened root for {endpoint.ModuleHierarchyPath}.");
            var leaf = ResolveGraphTargetLeaf(root, endpoint);
            if (leaf == null)
                return ValidationFailure(relation, strategies, $"Could not resolve validation leaf {endpoint.RelativeLeafHierarchyPath}.");
            var face = ResolveGraphTargetFace(leaf, endpoint, out string strategy);
            strategies.Add($"endpoint#{endpoint.Index}: {strategy}");
            if (face == null)
                return ValidationFailure(relation, strategies, $"Could not resolve validation face #{endpoint.Index}.");

            if (isConcentric)
            {
                MateGraphCylinderGeometry? runtimeCylinder = null;
                try
                {
                    var surface = face.GetSurface() as ISurface;
                    if (surface != null && surface.IsCylinder())
                        runtimeCylinder = TryParseCylinderSurfaceParameters(ToDoubleArray(surface.CylinderParams));
                }
                catch
                {
                    // Fall through to exported analytic geometry when the runtime
                    // face proxy refuses direct surface interrogation.
                }
                double[]? localOrigin = runtimeCylinder?.Origin
                    ?? endpoint.CylinderOriginLocal?.Take(3).ToArray();
                double[]? localAxis = runtimeCylinder?.Axis
                    ?? endpoint.CylinderAxisLocal?.Take(3).ToArray();
                if (localOrigin is not { Length: >= 3 } || localAxis is not { Length: >= 3 })
                    return ValidationFailure(
                        relation,
                        strategies,
                        "Concentric validation requires two recoverable cylindrical faces with analytic axes.");

                double[] worldOrigin;
                double[]? worldAxis;
                if (modulesByHierarchy.TryGetValue(endpoint.ModuleHierarchyPath, out var cylinderModule)
                    && endpoint.CylinderOriginWorld is { Length: >= 3 } sourceWorldOrigin
                    && endpoint.CylinderAxisWorld is { Length: >= 3 } sourceWorldAxis
                    && cylinderModule.SourceTransform is { Length: >= 13 } cylinderSourceTransform
                    && PairTransformArray(root.Transform2) is { Length: >= 13 } cylinderCurrentTransform)
                {
                    worldOrigin = MapSourceWorldPointToCurrentModulePose(
                        sourceWorldOrigin, cylinderSourceTransform, cylinderCurrentTransform);
                    worldAxis = MapSourceWorldVectorToCurrentModulePose(
                        sourceWorldAxis, cylinderSourceTransform, cylinderCurrentTransform);
                    strategies[^1] += "+CylinderAxisModulePoseDelta";
                }
                else
                {
                    worldOrigin = MateGraphLocalToWorld(localOrigin, leaf);
                    worldAxis = MateGraphLocalToWorldVector(localAxis, leaf);
                    strategies[^1] += runtimeCylinder != null
                        ? "+RuntimeCylinderSurface"
                        : "+ExportedCylinderAxis";
                }
                if (worldAxis is not { Length: >= 3 })
                    return ValidationFailure(relation, strategies, "Could not transform cylinder axis to world coordinates.");
                cylinderOrigins.Add(worldOrigin);
                cylinderAxes.Add(worldAxis);
                continue;
            }

            var box = ToDoubleArray(face.GetBox());
            double[]? localCenter = endpoint.FaceCenterLocal is { Length: >= 3 }
                ? endpoint.FaceCenterLocal.Take(3).ToArray()
                : box is { Length: >= 6 }
                    ?
                    [
                        (box[0] + box[3]) / 2.0,
                        (box[1] + box[4]) / 2.0,
                        (box[2] + box[5]) / 2.0,
                    ]
                    : null;
            double[]? localNormal = endpoint.FaceNormalLocal is { Length: >= 3 }
                ? endpoint.FaceNormalLocal.Take(3).ToArray()
                : SelectionService.TryGetPlanarFaceNormal(face);
            if (localCenter is not { Length: >= 3 } || localNormal is not { Length: >= 3 })
                return ValidationFailure(relation, strategies, "Validation relation requires two planar faces with measurable local geometry.");
            double[] worldCenter;
            double[]? worldNormal;
            if (modulesByHierarchy.TryGetValue(endpoint.ModuleHierarchyPath, out var module)
                && endpoint.FaceCenterWorld is { Length: >= 3 } sourceWorldCenter
                && endpoint.FaceNormalWorld is { Length: >= 3 } sourceWorldNormal
                && module.SourceTransform is { Length: >= 13 } sourceModuleTransform
                && PairTransformArray(root.Transform2) is { Length: >= 13 } currentModuleTransform)
            {
                // Flexible descendants can report Transform2/GetTotalTransform in
                // their owning subassembly frame after a context insertion.  Map
                // the source world-space face geometry through the top-level module
                // pose delta instead; this is stable for the verified unchanged
                // module subtree and avoids double-transforming assembly-context
                // face boxes.
                worldCenter = MapSourceWorldPointToCurrentModulePose(
                    sourceWorldCenter, sourceModuleTransform, currentModuleTransform);
                worldNormal = MapSourceWorldVectorToCurrentModulePose(
                    sourceWorldNormal, sourceModuleTransform, currentModuleTransform);
                strategies[^1] += "+ModulePoseDelta";
            }
            else
            {
                worldCenter = MateGraphLocalToWorld(localCenter, leaf);
                worldNormal = MateGraphLocalToWorldVector(localNormal, leaf);
            }
            centers.Add(worldCenter);
            if (worldNormal is not { Length: >= 3 })
                return ValidationFailure(relation, strategies, "Could not transform validation face normal to world coordinates.");
            normals.Add(worldNormal);
        }
        if (isConcentric)
        {
            if (cylinderOrigins.Count != 2 || cylinderAxes.Count != 2)
                return ValidationFailure(relation, strategies, "Concentric validation requires exactly two cylindrical face endpoints.");
            var measured = MeasureCoaxialCylinderDeviation(
                cylinderOrigins[0], cylinderAxes[0], cylinderOrigins[1], cylinderAxes[1]);
            if (measured == null)
                return ValidationFailure(relation, strategies, "Cylinder axes are not measurable.");
            double expectedDistance = relation.ExpectedDistanceMeters ?? 0.0;
            double expectedAngle = relation.ExpectedAngleRadians ?? 0.0;
            double distanceTolerance = relation.Tolerance?.DistanceMeters ?? 1e-6;
            double angleTolerance = relation.Tolerance?.AngleRadians ?? 1e-6;
            double distanceError = Math.Abs(measured.Value.DistanceMeters - expectedDistance);
            double angleError = Math.Abs(measured.Value.AngleRadians - expectedAngle);
            bool passed = distanceError <= distanceTolerance && angleError <= angleTolerance;
            return new AssemblySemanticValidationResult(
                relation.RelationName,
                relation.RelationTypeName,
                true,
                expectedDistance,
                measured.Value.DistanceMeters,
                distanceError,
                distanceTolerance,
                passed,
                strategies.AsReadOnly(),
                passed
                    ? "Reopened cylinder axes are coaxial within distance and angle tolerances."
                    : "Reopened cylinder axes are outside the coaxial tolerances.",
                expectedAngle,
                measured.Value.AngleRadians,
                angleError,
                angleTolerance);
        }

        if (centers.Count != 2 || normals.Count != 2)
            return ValidationFailure(relation, strategies, "Validation relation requires exactly two face endpoints.");
        if (relation.RelationType == (int)swMateType_e.swMateDISTANCE)
        {
            double? measured = MeasureParallelPlaneDistance(centers[0], normals[0], centers[1], normals[1]);
            if (measured == null)
                return ValidationFailure(relation, strategies, "Validation faces are not parallel planes.");
            double? expected = relation.ExpectedDistanceMeters;
            double tolerance = relation.Tolerance?.DistanceMeters ?? 1e-6;
            double? error = expected == null ? null : Math.Abs(measured.Value - expected.Value);
            bool passed = error is double errorValue && errorValue <= tolerance;
            return new AssemblySemanticValidationResult(
                relation.RelationName,
                relation.RelationTypeName,
                true,
                expected,
                measured,
                error,
                tolerance,
                passed,
                strategies.AsReadOnly(),
                passed
                    ? "Reopened face-to-face distance is within tolerance."
                    : "Reopened face-to-face distance is outside tolerance.");
        }

        if (relation.RelationType == (int)swMateType_e.swMatePARALLEL)
        {
            double? measured = MeasureUndirectedNormalAngle(normals[0], normals[1]);
            if (measured == null)
                return ValidationFailure(relation, strategies, "Validation face normals are not measurable.");
            double expected = relation.ExpectedAngleRadians ?? 0.0;
            double tolerance = relation.Tolerance?.AngleRadians ?? 1e-6;
            double error = Math.Abs(measured.Value - expected);
            bool passed = error <= tolerance;
            return new AssemblySemanticValidationResult(
                relation.RelationName,
                relation.RelationTypeName,
                true,
                null,
                null,
                null,
                null,
                passed,
                strategies.AsReadOnly(),
                passed
                    ? "Reopened face normals are parallel within tolerance."
                    : "Reopened face normals are outside the parallel-angle tolerance.",
                expected,
                measured,
                error,
                tolerance);
        }

        if (relation.RelationType == (int)swMateType_e.swMateCOINCIDENT)
        {
            var measured = MeasureCoincidentPlaneDeviation(
                centers[0], normals[0], centers[1], normals[1]);
            if (measured == null)
                return ValidationFailure(relation, strategies, "Validation faces are not measurable parallel planes.");
            double expectedDistance = relation.ExpectedDistanceMeters ?? 0.0;
            double expectedAngle = relation.ExpectedAngleRadians ?? 0.0;
            double distanceTolerance = relation.Tolerance?.DistanceMeters ?? 1e-6;
            double angleTolerance = relation.Tolerance?.AngleRadians ?? 1e-6;
            double distanceError = Math.Abs(measured.Value.DistanceMeters - expectedDistance);
            double angleError = Math.Abs(measured.Value.AngleRadians - expectedAngle);
            bool passed = distanceError <= distanceTolerance && angleError <= angleTolerance;
            return new AssemblySemanticValidationResult(
                relation.RelationName,
                relation.RelationTypeName,
                true,
                expectedDistance,
                measured.Value.DistanceMeters,
                distanceError,
                distanceTolerance,
                passed,
                strategies.AsReadOnly(),
                passed
                    ? "Reopened planes are coincident within distance and angle tolerances."
                    : "Reopened planes are outside the coincidence tolerances.",
                expectedAngle,
                measured.Value.AngleRadians,
                angleError,
                angleTolerance);
        }

        return ValidationFailure(relation, strategies, $"Validation relation type {relation.RelationTypeName} is not implemented.");
    }

    internal static double[] MapSourceWorldPointToCurrentModulePose(
        IReadOnlyList<double> sourceWorldPoint,
        IReadOnlyList<double> sourceModuleTransform,
        IReadOnlyList<double> currentModuleTransform)
    {
        var local = InverseRigidTransformPoint(sourceWorldPoint, sourceModuleTransform);
        return ApplyRigidTransformPoint(local, currentModuleTransform);
    }

    internal static double[]? MapSourceWorldVectorToCurrentModulePose(
        IReadOnlyList<double> sourceWorldVector,
        IReadOnlyList<double> sourceModuleTransform,
        IReadOnlyList<double> currentModuleTransform)
    {
        if (sourceWorldVector.Count < 3 || sourceModuleTransform.Count < 13 || currentModuleTransform.Count < 13)
            return null;
        double scale = sourceModuleTransform[12] == 0 ? 1.0 : sourceModuleTransform[12];
        double[] local =
        [
            (sourceModuleTransform[0] * sourceWorldVector[0] + sourceModuleTransform[1] * sourceWorldVector[1] + sourceModuleTransform[2] * sourceWorldVector[2]) / scale,
            (sourceModuleTransform[3] * sourceWorldVector[0] + sourceModuleTransform[4] * sourceWorldVector[1] + sourceModuleTransform[5] * sourceWorldVector[2]) / scale,
            (sourceModuleTransform[6] * sourceWorldVector[0] + sourceModuleTransform[7] * sourceWorldVector[1] + sourceModuleTransform[8] * sourceWorldVector[2]) / scale,
        ];
        return MateGraphNormalize(
        [
            currentModuleTransform[0] * local[0] + currentModuleTransform[3] * local[1] + currentModuleTransform[6] * local[2],
            currentModuleTransform[1] * local[0] + currentModuleTransform[4] * local[1] + currentModuleTransform[7] * local[2],
            currentModuleTransform[2] * local[0] + currentModuleTransform[5] * local[1] + currentModuleTransform[8] * local[2],
        ]);
    }

    private static double[] InverseRigidTransformPoint(
        IReadOnlyList<double> world,
        IReadOnlyList<double> transform)
    {
        double scale = transform[12] == 0 ? 1.0 : transform[12];
        double dx = world[0] - transform[9] * scale;
        double dy = world[1] - transform[10] * scale;
        double dz = world[2] - transform[11] * scale;
        return
        [
            (transform[0] * dx + transform[1] * dy + transform[2] * dz) / scale,
            (transform[3] * dx + transform[4] * dy + transform[5] * dz) / scale,
            (transform[6] * dx + transform[7] * dy + transform[8] * dz) / scale,
        ];
    }

    private static double[] ApplyRigidTransformPoint(
        IReadOnlyList<double> local,
        IReadOnlyList<double> transform)
    {
        double scale = transform[12] == 0 ? 1.0 : transform[12];
        double x = local[0] * scale;
        double y = local[1] * scale;
        double z = local[2] * scale;
        return
        [
            transform[9] * scale + transform[0] * x + transform[3] * y + transform[6] * z,
            transform[10] * scale + transform[1] * x + transform[4] * y + transform[7] * z,
            transform[11] * scale + transform[2] * x + transform[5] * y + transform[8] * z,
        ];
    }

    internal static double? MeasureParallelPlaneDistance(
        IReadOnlyList<double> firstCenter,
        IReadOnlyList<double> firstNormal,
        IReadOnlyList<double> secondCenter,
        IReadOnlyList<double> secondNormal)
    {
        if (firstCenter.Count < 3 || secondCenter.Count < 3 || firstNormal.Count < 3 || secondNormal.Count < 3)
            return null;
        double firstLength = Math.Sqrt(firstNormal.Take(3).Sum(value => value * value));
        double secondLength = Math.Sqrt(secondNormal.Take(3).Sum(value => value * value));
        if (firstLength <= 1e-12 || secondLength <= 1e-12)
            return null;
        double dot = Enumerable.Range(0, 3)
            .Sum(index => firstNormal[index] * secondNormal[index]) / (firstLength * secondLength);
        if (Math.Abs(dot) < 0.999999)
            return null;
        double signed = Enumerable.Range(0, 3)
            .Sum(index => (secondCenter[index] - firstCenter[index]) * firstNormal[index] / firstLength);
        return Math.Abs(signed);
    }

    internal static double? MeasureUndirectedNormalAngle(
        IReadOnlyList<double> firstNormal,
        IReadOnlyList<double> secondNormal)
    {
        if (firstNormal.Count < 3 || secondNormal.Count < 3)
            return null;
        double firstLength = Math.Sqrt(firstNormal.Take(3).Sum(value => value * value));
        double secondLength = Math.Sqrt(secondNormal.Take(3).Sum(value => value * value));
        if (firstLength <= 1e-12 || secondLength <= 1e-12)
            return null;
        double dot = Enumerable.Range(0, 3)
            .Sum(index => firstNormal[index] * secondNormal[index]) / (firstLength * secondLength);
        return Math.Acos(Math.Clamp(Math.Abs(dot), 0.0, 1.0));
    }

    internal static (double DistanceMeters, double AngleRadians)? MeasureCoincidentPlaneDeviation(
        IReadOnlyList<double> firstCenter,
        IReadOnlyList<double> firstNormal,
        IReadOnlyList<double> secondCenter,
        IReadOnlyList<double> secondNormal)
    {
        double? distance = MeasureParallelPlaneDistance(
            firstCenter, firstNormal, secondCenter, secondNormal);
        double? angle = MeasureUndirectedNormalAngle(firstNormal, secondNormal);
        if (distance == null || angle == null)
            return null;
        return (distance.Value, angle.Value);
    }

    internal static (double DistanceMeters, double AngleRadians)? MeasureCoaxialCylinderDeviation(
        IReadOnlyList<double> firstOrigin,
        IReadOnlyList<double> firstAxis,
        IReadOnlyList<double> secondOrigin,
        IReadOnlyList<double> secondAxis)
    {
        if (firstOrigin.Count < 3 || secondOrigin.Count < 3
            || firstAxis.Count < 3 || secondAxis.Count < 3)
            return null;
        var first = MateGraphNormalize(firstAxis.Take(3).ToArray());
        var second = MateGraphNormalize(secondAxis.Take(3).ToArray());
        if (first == null || second == null)
            return null;
        double dot = Enumerable.Range(0, 3).Sum(index => first[index] * second[index]);
        double angle = Math.Acos(Math.Clamp(Math.Abs(dot), 0.0, 1.0));
        double[] delta =
        [
            secondOrigin[0] - firstOrigin[0],
            secondOrigin[1] - firstOrigin[1],
            secondOrigin[2] - firstOrigin[2],
        ];
        double[] cross =
        [
            delta[1] * first[2] - delta[2] * first[1],
            delta[2] * first[0] - delta[0] * first[2],
            delta[0] * first[1] - delta[1] * first[0],
        ];
        double distance = Math.Sqrt(cross.Sum(value => value * value));
        return (distance, angle);
    }

    private static AssemblySemanticValidationResult ValidationFailure(
        AssemblySemanticValidationRelation relation,
        IReadOnlyList<string> strategies,
        string message) =>
        new(
            relation.RelationName,
            relation.RelationTypeName,
            false,
            relation.ExpectedDistanceMeters,
            null,
            null,
            relation.Tolerance?.DistanceMeters,
            false,
            strategies,
            message);

    internal static AssemblyEditableMateGraphDocument LoadAndValidateEditableMateGraph(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("effectiveMateGraphPath must not be empty.", nameof(path));
        string normalized = Path.GetFullPath(path);
        if (!File.Exists(normalized))
            throw new FileNotFoundException($"Effective mate graph was not found: {normalized}", normalized);
        var graph = JsonSerializer.Deserialize<AssemblyEditableMateGraphDocument>(
            File.ReadAllText(normalized, Encoding.UTF8),
            EditableMateGraphJsonOptions)
            ?? throw new InvalidOperationException("Effective mate graph JSON deserialized to null.");
        if (!string.Equals(graph.SchemaVersion, "editable-module-mate-graph/v1", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException($"Unsupported editable mate graph schema: {graph.SchemaVersion}");
        if (graph.Modules == null || graph.Mates == null)
            throw new InvalidOperationException("Effective mate graph must contain Modules and Mates arrays.");
        if (graph.ModuleCount != graph.Modules.Count || graph.InterModuleMateCount != graph.Mates.Count)
            throw new InvalidOperationException("Effective mate graph count fields do not match their arrays.");
        if (graph.Modules.Select(item => item.HierarchyPath).Distinct(StringComparer.OrdinalIgnoreCase).Count() != graph.Modules.Count)
            throw new InvalidOperationException("Module HierarchyPath values must be unique.");
        foreach (var module in graph.Modules)
        {
            if (string.IsNullOrWhiteSpace(module.Path) || !File.Exists(module.Path))
                throw new FileNotFoundException($"Module source file was not found: {module.Path}", module.Path);
        }
        var modulePaths = graph.Modules.Select(item => item.HierarchyPath).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var supported = new HashSet<int>
        {
            (int)swMateType_e.swMateCOINCIDENT,
            (int)swMateType_e.swMateCONCENTRIC,
            (int)swMateType_e.swMatePERPENDICULAR,
            (int)swMateType_e.swMatePARALLEL,
            (int)swMateType_e.swMateTANGENT,
            (int)swMateType_e.swMateDISTANCE,
            (int)swMateType_e.swMateANGLE,
            (int)swMateType_e.swMateWIDTH,
            (int)swMateType_e.swMateSLOT,
        };
        foreach (var mate in graph.Mates)
        {
            if (!supported.Contains(mate.MateType))
                throw new InvalidOperationException($"Editable MVP does not yet support imported mate type {mate.MateTypeName} ({mate.MateType}).");
            bool isWidth = mate.MateType == (int)swMateType_e.swMateWIDTH;
            int expectedEndpointCount = isWidth ? 4 : 2;
            if (mate.Endpoints.Count != expectedEndpointCount
                || mate.Endpoints.Any(item => !string.Equals(item.GeometryType, "Face", StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException($"Imported mate '{mate.MateName}' must contain exactly {expectedEndpointCount} face endpoints.");
            if (mate.Endpoints.Any(item => !modulePaths.Contains(item.ModuleHierarchyPath)))
                throw new InvalidOperationException($"Imported mate '{mate.MateName}' references a module outside Modules.");
            if (isWidth)
            {
                var advanced = mate.AdvancedOptions
                    ?? throw new InvalidOperationException($"Imported Width mate '{mate.MateName}' is missing AdvancedOptions.");
                var endpointIndices = mate.Endpoints.Select(item => item.Index).ToHashSet();
                var widthIndices = advanced.WidthEndpointIndices.ToArray();
                var tabIndices = advanced.TabEndpointIndices.ToArray();
                if (widthIndices.Length != 2 || tabIndices.Length != 2
                    || widthIndices.Concat(tabIndices).Distinct().Count() != 4
                    || widthIndices.Concat(tabIndices).Any(index => !endpointIndices.Contains(index)))
                    throw new InvalidOperationException($"Imported Width mate '{mate.MateName}' has invalid width/tab endpoint groups.");
            }
            if (mate.MateType == (int)swMateType_e.swMateSLOT
                && mate.AdvancedOptions?.SlotConstraint == null)
                throw new InvalidOperationException($"Imported Slot mate '{mate.MateName}' is missing SlotConstraint in AdvancedOptions.");
        }
        return graph;
    }

    internal static AssemblyEditableMateVerification VerifyEditableMate(
        AssemblyModuleMateGraphMate expected,
        IReadOnlyList<AssemblyModuleMateGraphMate> observed)
    {
        var actual = observed.FirstOrDefault(item =>
            string.Equals(item.MateName, expected.MateName, StringComparison.OrdinalIgnoreCase)
            || string.Equals(item.MateName, $"MCP_GRAPH_{expected.MateName}", StringComparison.OrdinalIgnoreCase)
            || item.MateName.EndsWith(expected.MateName, StringComparison.OrdinalIgnoreCase));
        bool distanceMatches = NullableScalarMatches(expected.Distance, actual?.Distance, 1e-8);
        bool angleMatches = NullableScalarMatches(expected.Angle, actual?.Angle, 1e-8);
        // SOLIDWORKS may normalize the alignment field of a perpendicular mate when
        // saving/reopening it.  Perpendicular geometry has no aligned/anti-aligned
        // alternative, so alignment is not a semantic parameter for this mate type.
        bool alignmentMatches = expected.MateType == (int)swMateType_e.swMatePERPENDICULAR
            || actual?.Alignment == expected.Alignment;
        bool advancedOptionsMatch = GraphAdvancedOptionsMatch(expected, actual);
        return new AssemblyEditableMateVerification(
            expected.MateName,
            actual?.MateName,
            actual != null,
            actual?.MateType == expected.MateType,
            alignmentMatches,
            distanceMatches,
            angleMatches,
            advancedOptionsMatch,
            expected.Distance,
            actual?.Distance,
            expected.Angle,
            actual?.Angle);
    }

    private static bool GraphAdvancedOptionsMatch(
        AssemblyModuleMateGraphMate expected,
        AssemblyModuleMateGraphMate? actual)
    {
        if (expected.MateType is not (
            (int)swMateType_e.swMateWIDTH
            or (int)swMateType_e.swMateSLOT
            or (int)swMateType_e.swMateDISTANCE))
            return true;
        if (actual?.AdvancedOptions == null || expected.AdvancedOptions == null)
            return false;
        var left = expected.AdvancedOptions;
        var right = actual.AdvancedOptions;
        if (expected.MateType == (int)swMateType_e.swMateWIDTH)
        {
            return left.WidthConstraintType == right.WidthConstraintType
                && NullableScalarMatches(left.WidthPercentDistanceFromEnd, right.WidthPercentDistanceFromEnd, 1e-8)
                && NullableScalarMatches(left.WidthDistanceFromEnd, right.WidthDistanceFromEnd, 1e-8)
                && left.WidthFlipDimension == right.WidthFlipDimension
                && left.WidthEndpointIndices.OrderBy(value => value).SequenceEqual(right.WidthEndpointIndices.OrderBy(value => value))
                && left.TabEndpointIndices.OrderBy(value => value).SequenceEqual(right.TabEndpointIndices.OrderBy(value => value));
        }
        if (expected.MateType == (int)swMateType_e.swMateSLOT)
        {
            return left.SlotConstraint == right.SlotConstraint
                && NullableScalarMatches(left.SlotDistance, right.SlotDistance, 1e-8)
                && NullableScalarMatches(left.SlotPercent, right.SlotPercent, 1e-8)
                && left.SlotFlipDirection == right.SlotFlipDirection;
        }
        return left.DistanceFlipDimension == right.DistanceFlipDimension;
    }

    private static bool NullableScalarMatches(double? expected, double? actual, double tolerance)
    {
        if (expected == null || actual == null)
            return expected == null && actual == null;
        return Math.Abs(expected.Value - actual.Value) <= tolerance;
    }
}
