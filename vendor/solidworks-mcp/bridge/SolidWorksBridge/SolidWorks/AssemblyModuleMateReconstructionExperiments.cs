using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyModuleMateExperimentMateResult(
    string MateName,
    string MateTypeName,
    bool Success,
    int ErrorStatus,
    string ErrorName,
    string Message,
    IReadOnlyList<string> EndpointResolutionStrategies,
    AssemblyModuleMateAdvancedOptions? AdvancedOptions);

public record AssemblyModuleMateExperimentComponentResult(
    string ModuleToken,
    string SourceHierarchyPath,
    string TargetHierarchyPath,
    int ConstrainedStatus,
    string ConstrainedStatusName,
    double TranslationErrorMeters,
    double RotationMatrixMaxAbsError,
    bool MatchesSourcePose,
    double[]? SourceTransform,
    double[]? ObservedTransform);

public record AssemblyModuleMateReconstructionExperimentResult(
    bool Success,
    string Mode,
    string SourceAssemblyPath,
    string OutputAssemblyPath,
    string BaseModuleToken,
    IReadOnlyList<string> ResidualAnchorModuleSelectors,
    string ResidualAnchorSemantics,
    int SourceModuleCount,
    int SourceMateCount,
    int AttemptedMateCount,
    int CreatedMateCount,
    int FailedMateCount,
    bool Reopened,
    int ReopenedModuleCount,
    int ReopenedMateCount,
    int PoseMatchCount,
    IReadOnlyList<AssemblyModuleMateExperimentMateResult> MateResults,
    IReadOnlyList<AssemblyModuleMateExperimentComponentResult> ComponentResults,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    /// <summary>
    /// Rebuild Project 02's module-level mate graph in a new assembly. This deliberately supports
    /// three research modes: source_pose, mate_only, and residual_anchors. It never overwrites an
    /// existing assembly and never edits the source assembly or child module files.
    /// </summary>
    public AssemblyModuleMateReconstructionExperimentResult RunModuleMateReconstructionExperiment(
        string sourceAssemblyPath,
        string outputAssemblyPath,
        string mode,
        string baseModuleToken = "A600",
        IReadOnlyList<string>? moduleTokens = null,
        IReadOnlyList<string>? residualAnchorModuleSelectors = null,
        double poseToleranceMeters = 1e-5,
        double rotationTolerance = 1e-6)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);
        if (string.IsNullOrWhiteSpace(outputAssemblyPath))
            throw new ArgumentException("outputAssemblyPath must not be empty.", nameof(outputAssemblyPath));

        string normalizedOutput = Path.GetFullPath(outputAssemblyPath);
        if (!string.Equals(Path.GetExtension(normalizedOutput), ".SLDASM", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("outputAssemblyPath must end in .SLDASM.", nameof(outputAssemblyPath));
        if (File.Exists(normalizedOutput))
            throw new IOException($"Refusing to overwrite an existing experiment assembly: {normalizedOutput}");

        string normalizedMode = (mode ?? string.Empty).Trim().ToLowerInvariant().Replace('-', '_');
        if (normalizedMode is not ("source_pose" or "mate_only" or "residual_anchors"))
            throw new ArgumentException("mode must be source_pose, mate_only, or residual_anchors.", nameof(mode));
        if (poseToleranceMeters <= 0 || rotationTolerance <= 0)
            throw new ArgumentOutOfRangeException(nameof(poseToleranceMeters), "Pose tolerances must be positive.");

        var residualSelectors = (residualAnchorModuleSelectors ?? [])
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var diagnostics = new List<string>();
        var graph = ExportModuleMateGraph(sourceAssemblyPath, moduleTokens, saveJson: false);

        var baseMatches = graph.Modules.Where(module =>
            string.Equals(module.ModuleToken, baseModuleToken, StringComparison.OrdinalIgnoreCase)
            || string.Equals(module.HierarchyPath, baseModuleToken, StringComparison.OrdinalIgnoreCase)).ToList();
        if (baseMatches.Count != 1)
            throw new InvalidOperationException($"Base selector '{baseModuleToken}' resolved to {baseMatches.Count} graph nodes; expected exactly one.");
        var baseModule = baseMatches[0];

        Directory.CreateDirectory(Path.GetDirectoryName(normalizedOutput)!);
        _cm.EnsureConnected();
        var sw = _cm.SwApp ?? throw new InvalidOperationException("SolidWorks is not connected.");
        string template = sw.GetDefaultTemplatePath(SwDocType.Assembly);
        sw.NewDoc(template);
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
            insertedBySourceHierarchy.Add(module.HierarchyPath, inserted);
            targetNameBySourceHierarchy.Add(module.HierarchyPath, inserted.Name2 ?? Path.GetFileNameWithoutExtension(module.Path));

            bool isBase = string.Equals(module.HierarchyPath, baseModule.HierarchyPath, StringComparison.OrdinalIgnoreCase);
            bool isResidualAnchor = residualSelectors.Any(selector =>
                string.Equals(selector, module.ModuleToken, StringComparison.OrdinalIgnoreCase)
                || string.Equals(selector, module.HierarchyPath, StringComparison.OrdinalIgnoreCase));
            double[]? initialTransform = normalizedMode switch
            {
                "source_pose" => module.SourceTransform,
                "residual_anchors" when isBase || isResidualAnchor => module.SourceTransform,
                "mate_only" when isBase => module.SourceTransform,
                _ => BuildDeterministicExperimentTransform(baseModule.SourceTransform, index),
            };
            ApplyGraphTransform(inserted, initialTransform);
        }
        targetDocument.ForceRebuild3(false);
        FixGraphBaseComponent(targetDocument, targetAssembly, insertedBySourceHierarchy[baseModule.HierarchyPath]);

        var mateResults = new List<AssemblyModuleMateExperimentMateResult>();
        foreach (var mate in graph.Mates.Where(item => !item.IsSuppressed))
        {
            mateResults.Add(RebuildGraphMate(
                targetDocument,
                targetAssembly,
                insertedBySourceHierarchy,
                mate,
                mate.AdvancedOptions));
        }
        // A flexible subassembly solves its internal residual DOF against the
        // parent assembly. Restore flexibility only after all external mates
        // exist, otherwise SolidWorks can retain an arbitrary intermediate
        // internal pose even when the final top-level transform is correct.
        foreach (var module in orderedModules)
        {
            ApplyGraphComponentSolvingState(
                targetDocument,
                targetAssembly,
                insertedBySourceHierarchy[module.HierarchyPath],
                module,
                diagnostics);
        }
        targetDocument.ForceRebuild3(false);

        var save = sw.SaveDocAs(normalizedOutput, sourcePath: null, saveAsCopy: false);
        if (save.Errors != 0)
            diagnostics.Add($"SolidWorks save returned errors={save.Errors}, warnings={save.Warnings}.");
        string savedDocumentTitle = targetDocument.GetTitle() ?? Path.GetFileName(normalizedOutput);
        try { sw.CloseDoc(savedDocumentTitle); }
        catch (Exception ex) { diagnostics.Add($"Close before verification was best-effort: {ex.Message}"); }

        bool reopened = false;
        int reopenedMateCount = 0;
        int reopenedModuleCount = 0;
        var componentResults = new List<AssemblyModuleMateExperimentComponentResult>();
        try
        {
            sw.OpenDoc(normalizedOutput);
            sw.ActivateDoc(normalizedOutput);
            reopened = true;
            var reopenedAssembly = GetAssemblyDoc();
            var reopenedRoots = PairEnumerateTopLevelInstances(reopenedAssembly);
            reopenedModuleCount = reopenedRoots.Count;
            foreach (var sourceModule in graph.Modules)
            {
                string targetName = targetNameBySourceHierarchy[sourceModule.HierarchyPath];
                var target = reopenedRoots.SingleOrDefault(item =>
                    string.Equals(item.Info.Name, targetName, StringComparison.OrdinalIgnoreCase));
                double[]? observed = target == null ? null : PairTransformArray(target.Component.Transform2);
                (double translationError, double rotationError) = GraphTransformError(sourceModule.SourceTransform, observed);
                int constrainedStatus = target == null ? (int)swConstrainedStatus_e.swUnknownConstraint : SafeGraphConstrainedStatus(target.Component);
                componentResults.Add(new AssemblyModuleMateExperimentComponentResult(
                    sourceModule.ModuleToken,
                    sourceModule.HierarchyPath,
                    target?.Info.HierarchyPath ?? targetName,
                    constrainedStatus,
                    GraphConstrainedStatusName(constrainedStatus),
                    translationError,
                    rotationError,
                    translationError <= poseToleranceMeters && rotationError <= rotationTolerance,
                    sourceModule.SourceTransform,
                    observed));
            }

            var reopenedGraph = ExportModuleMateGraph(normalizedOutput, moduleTokens, saveJson: false);
            reopenedMateCount = reopenedGraph.InterModuleMateCount;
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Reopen verification failed: {ex.Message}");
        }

        int createdCount = mateResults.Count(result => result.Success);
        int poseMatchCount = componentResults.Count(result => result.MatchesSourcePose);
        bool success = reopened
            && File.Exists(normalizedOutput)
            && createdCount == graph.InterModuleMateCount
            && reopenedMateCount == graph.InterModuleMateCount
            && poseMatchCount == graph.ModuleCount;
        if (normalizedMode == "mate_only" && !success)
            diagnostics.Add("A failed mate-only result is an experimental finding: the exported mate graph did not uniquely recover every source pose from the deterministic non-source initial placement.");
        if (normalizedMode == "residual_anchors")
            diagnostics.Add("Residual anchors in experiment v1 are conservative full component source transforms for only the listed modules; reducing each anchor to scalar free-axis parameters is a later refinement.");

        return new AssemblyModuleMateReconstructionExperimentResult(
            success,
            normalizedMode,
            Path.GetFullPath(sourceAssemblyPath),
            normalizedOutput,
            baseModule.ModuleToken,
            residualSelectors,
            normalizedMode == "residual_anchors"
                ? "Full source transform only for listed residual-anchor modules; all other non-base modules start from a deterministic non-source grid."
                : normalizedMode == "source_pose"
                    ? "All module source transforms are convergence aids before mate recreation."
                    : "Only the base uses its source transform; all other modules start from a deterministic non-source grid.",
            graph.ModuleCount,
            graph.InterModuleMateCount,
            mateResults.Count,
            createdCount,
            mateResults.Count - createdCount,
            reopened,
            reopenedModuleCount,
            reopenedMateCount,
            poseMatchCount,
            mateResults.AsReadOnly(),
            componentResults.AsReadOnly(),
            diagnostics.AsReadOnly());
    }

    private Dictionary<string, AssemblyModuleMateAdvancedOptions?> ReadSourceAdvancedMateOptions()
    {
        var result = new Dictionary<string, AssemblyModuleMateAdvancedOptions?>(StringComparer.OrdinalIgnoreCase);
        var document = (IModelDoc2)GetAssemblyDoc();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
                continue;
            result[feature.Name ?? "Mate"] = ReadGraphMateAdvancedOptions(feature, mate, PairSafeMateType(mate));
        }
        return result;
    }

    private static AssemblyModuleMateAdvancedOptions? ReadGraphMateAdvancedOptions(
        IFeature feature,
        IMate2 mate,
        int mateType)
    {
        bool sourceWarning = false;
        int sourceError = 0;
        try { sourceError = feature.GetErrorCode2(out sourceWarning); } catch { }
        try
        {
            if (mateType == (int)swMateType_e.swMateWIDTH && feature.GetDefinition() is IWidthMateFeatureData width)
            {
                var widthObjects = GraphObjectArray(width.WidthSelection);
                var tabObjects = GraphObjectArray(width.TabSelection);
                return new AssemblyModuleMateAdvancedOptions(
                    width.ConstraintType,
                    width.PercentDistanceFromEnd,
                    width.DistanceFromEnd,
                    width.FlipDimension,
                    GraphMateEndpointIndices(mate, widthObjects),
                    GraphMateEndpointIndices(mate, tabObjects),
                    null, null, null, null,
                    null, sourceError, sourceWarning);
            }
            if (mateType == (int)swMateType_e.swMateSLOT && feature.GetDefinition() is ISlotMateFeatureData slot)
            {
                return new AssemblyModuleMateAdvancedOptions(
                    null, null, null, null, [], [],
                    slot.Constraint,
                    slot.Distance,
                    slot.Percent,
                    slot.FlipDirection,
                    null, sourceError, sourceWarning);
            }
            if (mateType == (int)swMateType_e.swMateDISTANCE && feature.GetDefinition() is IDistanceMateFeatureData distance)
            {
                return new AssemblyModuleMateAdvancedOptions(
                    null, null, null, null, [], [],
                    null, null, null, null,
                    distance.FlipDimension, sourceError, sourceWarning);
            }
            if (sourceError != 0)
            {
                return new AssemblyModuleMateAdvancedOptions(
                    null, null, null, null, [], [],
                    null, null, null, null,
                    null, sourceError, sourceWarning);
            }
        }
        catch
        {
            // The rebuild result will retain a diagnostic if default options are insufficient.
        }
        return null;
    }

    private static IReadOnlyList<int> GraphMateEndpointIndices(IMate2 mate, IReadOnlyList<object> candidates)
    {
        var indices = new List<int>();
        int count = PairSafeMateEntityCount(mate);
        for (int index = 0; index < count; index++)
        {
            object? reference = PairSafeReference(PairSafeMateEntity(mate, index));
            if (reference != null && candidates.Any(candidate => PairComIdentityEquals(candidate, reference)))
                indices.Add(index);
        }
        return indices;
    }

    private static IReadOnlyList<object> GraphObjectArray(object? value)
    {
        if (value is null)
            return [];
        if (value is object[] array)
            return array.Where(item => item != null).ToArray()!;
        if (value is Array generic)
            return generic.Cast<object>().Where(item => item != null).ToArray();
        return [value];
    }

    private IComponent2 InsertGraphModule(IAssemblyDoc targetAssembly, AssemblyModuleMateGraphNode module)
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
            if (!string.IsNullOrWhiteSpace(targetPath)) sw.ActivateDoc(targetPath);
            else if (!string.IsNullOrWhiteSpace(targetTitle)) sw.ActivateDocByTitle(targetTitle);
            component = targetAssembly.AddComponent5(module.Path, 0, "", false, "", 0, 0, 0) as IComponent2;
        }
        if (component == null)
            throw new InvalidOperationException($"SolidWorks failed to insert module: {module.Path}");
        if (!string.IsNullOrWhiteSpace(module.ReferencedConfiguration))
        {
            try { component.ReferencedConfiguration = module.ReferencedConfiguration; }
            catch { }
        }
        try { component.SetSuppression2((int)swComponentSuppressionState_e.swComponentFullyResolved); } catch { }
        return component;
    }

    private void ApplyGraphTransform(IComponent2 component, double[]? transform)
    {
        if (transform is not { Length: >= 13 })
            return;
        var math = (IMathUtility?)_cm.SwApp?.GetMathUtility();
        var created = math?.CreateTransform(transform) as MathTransform;
        if (created != null)
            component.Transform2 = created;
    }

    private static void ApplyGraphComponentSolvingState(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IComponent2 component,
        AssemblyModuleMateGraphNode module,
        ICollection<string> diagnostics)
    {
        if (module.SolvingState is not int solvingState)
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
                throw new InvalidOperationException("component selection failed");
            bool changed = assembly.CompConfigProperties5(
                suppression,
                solvingState,
                visible,
                true,
                component.ReferencedConfiguration ?? string.Empty,
                excludeFromBom,
                isEnvelope);
            if (!changed || component.Solving != solvingState)
                diagnostics.Add($"Solving state for '{module.ModuleToken}' was not restored exactly.");
        }
        catch (Exception ex)
        {
            diagnostics.Add($"Solving state restore for '{module.ModuleToken}' failed: {ex.Message}");
        }
        finally
        {
            document.ClearSelection2(true);
        }
    }

    private static double[] BuildDeterministicExperimentTransform(double[]? baseTransform, int index)
    {
        double baseX = baseTransform is { Length: >= 12 } ? baseTransform[9] : 0;
        double baseY = baseTransform is { Length: >= 12 } ? baseTransform[10] : 0;
        double baseZ = baseTransform is { Length: >= 12 } ? baseTransform[11] : 0;
        int slot = Math.Max(1, index);
        int column = (slot - 1) % 3;
        int row = (slot - 1) / 3;
        double angle = (8 + slot * 3) * Math.PI / 180.0;
        double c = Math.Cos(angle);
        double s = Math.Sin(angle);
        return
        [
            c, s, 0,
            -s, c, 0,
            0, 0, 1,
            baseX + (column - 1) * 0.42,
            baseY + 0.55 + row * 0.36,
            baseZ + 0.30 + row * 0.12,
            1, 0, 0, 0,
        ];
    }

    private static void FixGraphBaseComponent(IModelDoc2 document, IAssemblyDoc assembly, IComponent2 component)
    {
        document.ClearSelection2(true);
        var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
        component.Select4(false, selectData, false);
        try { assembly.FixComponent(); } catch { }
        document.ClearSelection2(true);
    }

    private static AssemblyModuleMateExperimentMateResult RebuildGraphMate(
        IModelDoc2 document,
        IAssemblyDoc assembly,
        IReadOnlyDictionary<string, IComponent2> roots,
        AssemblyModuleMateGraphMate mate,
        AssemblyModuleMateAdvancedOptions? advanced,
        Action<string>? progress = null)
    {
        var strategies = new List<string>();
        var resolved = new Dictionary<int, IFace2>();
        foreach (var endpoint in mate.Endpoints.OrderBy(item => item.Index))
        {
            progress?.Invoke($"endpoint-{endpoint.Index}-leaf-start");
            if (!roots.TryGetValue(endpoint.ModuleHierarchyPath, out var root))
                return GraphMateFailure(mate, $"No inserted root for endpoint module {endpoint.ModuleHierarchyPath}.", strategies, advanced);
            // A copied assembly preserves assembly-level persistent references even when
            // external component paths still point at a vendor directory.  Resolve that
            // authoritative identity before requiring a leaf traversal; leaf/index/
            // fingerprint recovery remains the fallback for rebuilt or reinserted modules.
            var persistentFace = ResolveGraphPersistentTargetFace(document, endpoint);
            if (persistentFace != null)
            {
                strategies.Add($"endpoint#{endpoint.Index}: SourceAssemblyPersistentReference");
                resolved[endpoint.Index] = persistentFace;
                progress?.Invoke($"endpoint-{endpoint.Index}-resolved");
                continue;
            }
            var leaf = ResolveGraphTargetLeaf(assembly, root, endpoint);
            if (leaf == null)
                return GraphMateFailure(mate, $"Could not resolve target leaf for endpoint #{endpoint.Index}: {endpoint.RelativeLeafHierarchyPath}.", strategies, advanced);
            progress?.Invoke($"endpoint-{endpoint.Index}-face-start");
            var face = ResolveGraphTargetFace(document, leaf, endpoint, out string strategy);
            strategies.Add($"endpoint#{endpoint.Index}: {strategy}");
            if (face == null)
                return GraphMateFailure(mate, $"Could not resolve target face for endpoint #{endpoint.Index}.", strategies, advanced);
            resolved[endpoint.Index] = face;
            progress?.Invoke($"endpoint-{endpoint.Index}-resolved");
        }

        document.ClearSelection2(true);
        try
        {
            object? created;
            int errorStatus = 0;
            if (mate.MateType == (int)swMateType_e.swMateWIDTH)
            {
                var widthIndices = advanced?.WidthEndpointIndices.Count == 2
                    ? advanced.WidthEndpointIndices
                    : mate.Endpoints.OrderBy(item => item.Index).Take(2).Select(item => item.Index).ToArray();
                var tabIndices = advanced?.TabEndpointIndices.Count == 2
                    ? advanced.TabEndpointIndices
                    : mate.Endpoints.OrderBy(item => item.Index).Skip(2).Take(2).Select(item => item.Index).ToArray();
                if (!SelectGraphFaces(document, resolved, widthIndices, 1, appendFirst: false)
                    || !SelectGraphFaces(document, resolved, tabIndices, 16, appendFirst: true))
                    return GraphMateFailure(mate, "SolidWorks failed to select width/tab endpoint faces.", strategies, advanced);
                created = assembly.AddMate5(
                    mate.MateType, mate.Alignment, advanced?.WidthFlipDimension ?? false,
                    0, 0, 0, 0, 0, 0, 0, 0,
                    false, false,
                    advanced?.WidthConstraintType ?? (int)swMateWidthOptions_e.swMateWidth_Centered,
                    out errorStatus);
            }
            else if (mate.MateType == (int)swMateType_e.swMateSLOT)
            {
                if (!SelectGraphFaces(document, resolved, mate.Endpoints.OrderBy(item => item.Index).Select(item => item.Index).ToArray(), 1, appendFirst: false))
                    return GraphMateFailure(mate, "SolidWorks failed to select slot endpoint faces.", strategies, advanced);
                var data = assembly.CreateMateData((int)swMateType_e.swMateSLOT) as ISlotMateFeatureData;
                if (data == null)
                    return GraphMateFailure(mate, "CreateMateData did not return ISlotMateFeatureData.", strategies, advanced);
                data.MateAlignment = mate.Alignment;
                data.Constraint = advanced?.SlotConstraint ?? (int)swSlotMateConstraintOptions_e.swSlotMateConstraintOption_Free;
                if (advanced?.SlotDistance is double distance) data.Distance = distance;
                if (advanced?.SlotPercent is double percent) data.Percent = percent;
                if (advanced?.SlotFlipDirection is bool flip) data.FlipDirection = flip;
                created = assembly.CreateMate(data);
                if (created is IFeature featureData)
                {
                    var definition = featureData.GetDefinition() as IMateFeatureData;
                    errorStatus = definition?.ErrorStatus ?? 0;
                }
            }
            else if (mate.MateType == (int)swMateType_e.swMateDISTANCE)
            {
                if (!SelectGraphFaces(document, resolved, mate.Endpoints.OrderBy(item => item.Index).Select(item => item.Index).ToArray(), 1, appendFirst: false))
                    return GraphMateFailure(mate, "SolidWorks failed to select distance mate endpoint faces.", strategies, advanced);
                created = assembly.AddMate5(
                    mate.MateType, mate.Alignment, advanced?.DistanceFlipDimension ?? false,
                    mate.Distance ?? 0,
                    mate.Distance ?? 0,
                    mate.Distance ?? 0,
                    0, 0, 0, 0, 0,
                    false, false, 0,
                    out errorStatus);
            }
            else
            {
                progress?.Invoke("basic-select-start");
                if (!SelectGraphFaces(document, resolved, mate.Endpoints.OrderBy(item => item.Index).Select(item => item.Index).ToArray(), 1, appendFirst: false))
                    return GraphMateFailure(mate, "SolidWorks failed to select basic mate endpoint faces.", strategies, advanced);
                progress?.Invoke("basic-add-mate-start");
                created = assembly.AddMate5(
                    mate.MateType, mate.Alignment, false,
                    mate.Distance ?? 0,
                    mate.Distance ?? 0,
                    mate.Distance ?? 0,
                    0, 0,
                    mate.Angle ?? 0,
                    mate.Angle ?? 0,
                    mate.Angle ?? 0,
                    false, false, 0,
                    out errorStatus);
                progress?.Invoke("basic-add-mate-complete");
            }
            document.ClearSelection2(true);
            bool createdFeature = created != null;
            bool success = createdFeature;
            if (createdFeature)
                PairTryRenameCreatedMate(created!, $"MCP_GRAPH_{mate.MateName}");
            var error = SolidWorksApiErrorFactory.DecodeValue<swAddMateError_e>(errorStatus);
            return new AssemblyModuleMateExperimentMateResult(
                mate.MateName,
                mate.MateTypeName,
                success,
                errorStatus,
                error.Name ?? "Unknown",
                success
                    ? errorStatus == 0
                        ? "Mate rebuilt from exported module-graph endpoints."
                        : $"Mate feature was created, but SolidWorks reported {error.Name}; compare with the exported source feature status."
                    : error.Description ?? "SolidWorks failed to rebuild mate.",
                strategies.AsReadOnly(),
                advanced);
        }
        catch (Exception ex)
        {
            document.ClearSelection2(true);
            return GraphMateFailure(mate, ex.Message, strategies, advanced);
        }
    }

    private static bool SelectGraphFaces(
        IModelDoc2 document,
        IReadOnlyDictionary<int, IFace2> resolved,
        IReadOnlyList<int> indices,
        int mark,
        bool appendFirst)
    {
        bool append = appendFirst;
        foreach (int index in indices)
        {
            if (!resolved.TryGetValue(index, out var face))
                return false;
            var selectData = (SelectData)document.ISelectionManager.CreateSelectData();
            selectData.Mark = mark;
            if (!((IEntity)face).Select4(append, selectData))
                return false;
            append = true;
        }
        return indices.Count > 0;
    }

    private static AssemblyModuleMateExperimentMateResult GraphMateFailure(
        AssemblyModuleMateGraphMate mate,
        string message,
        IReadOnlyList<string> strategies,
        AssemblyModuleMateAdvancedOptions? advanced) =>
        new(mate.MateName, mate.MateTypeName, false, -1, "EndpointOrCreationFailure", message, strategies, advanced);

    private static IComponent2? ResolveGraphTargetLeaf(
        IAssemblyDoc assembly,
        IComponent2 targetRoot,
        AssemblyModuleMateGraphEndpoint endpoint)
    {
        // GetComponents(false) is a flat SolidWorks occurrence index.  It exposes
        // qualified Name2 values for lightweight descendants without recursively
        // resolving every sibling branch, which is exactly the identity exported
        // by the module mate graph.
        try
        {
            var flat = (assembly.GetComponents(false) as object[] ?? [])
                .OfType<IComponent2>()
                .ToArray();
            string relativeSuffix = "/" + endpoint.RelativeLeafHierarchyPath;
            var flatMatches = flat.Where(component =>
                    string.Equals(component.Name2, endpoint.LeafHierarchyPath, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(component.Name2, endpoint.RelativeLeafHierarchyPath, StringComparison.OrdinalIgnoreCase)
                    || (component.Name2?.EndsWith(relativeSuffix, StringComparison.OrdinalIgnoreCase) ?? false))
                .ToArray();
            if (flatMatches.Length == 0)
            {
                string expectedLeafName = GraphLeafName(endpoint.LeafComponentName);
                string expectedFileName = Path.GetFileName(endpoint.LeafComponentPath);
                flatMatches = flat.Where(component =>
                        string.Equals(GraphLeafName(component.Name2), expectedLeafName, StringComparison.OrdinalIgnoreCase)
                        && string.Equals(
                            Path.GetFileName(component.GetPathName()),
                            expectedFileName,
                            StringComparison.OrdinalIgnoreCase))
                    .ToArray();
            }
            if (flatMatches.Length == 1)
            {
                try
                {
                    flatMatches[0].SetSuppression2(
                        (int)swComponentSuppressionState_e.swComponentFullyResolved);
                }
                catch { }
                return flatMatches[0];
            }
        }
        catch { }

        // GetComponentByName can resolve a fully-qualified occurrence without
        // recursively expanding a large lightweight module.  This is the preferred
        // fallback when an assembly-level persistent face reference is unavailable.
        try
        {
            if (!string.IsNullOrWhiteSpace(endpoint.LeafHierarchyPath)
                && assembly.GetComponentByName(endpoint.LeafHierarchyPath) is IComponent2 direct)
            {
                try
                {
                    direct.SetSuppression2(
                        (int)swComponentSuppressionState_e.swComponentFullyResolved);
                }
                catch { }
                return direct;
            }
        }
        catch { }

        return ResolveGraphTargetLeafWithoutAssembly(targetRoot, endpoint);
    }

    private static IComponent2? ResolveGraphTargetLeaf(
        IComponent2 targetRoot,
        AssemblyModuleMateGraphEndpoint endpoint) =>
        ResolveGraphTargetLeafWithoutAssembly(targetRoot, endpoint);

    private static IComponent2? ResolveGraphTargetLeafWithoutAssembly(
        IComponent2 targetRoot,
        AssemblyModuleMateGraphEndpoint endpoint)
    {

        // The endpoint catalogue already contains the path relative to the module
        // root.  Follow that path first so a mate involving one leaf of a large
        // production module does not enumerate and resolve thousands of unrelated
        // descendants.  The former exhaustive scan remains as a compatibility
        // fallback for legacy catalogues with incomplete or renamed paths.
        var direct = ResolveGraphTargetLeafByRelativePath(targetRoot, endpoint.RelativeLeafHierarchyPath);
        if (direct != null)
        {
            try { direct.SetSuppression2((int)swComponentSuppressionState_e.swComponentFullyResolved); } catch { }
            return direct;
        }

        var items = new List<(IComponent2 Component, string RelativePath)> { (targetRoot, string.Empty) };
        GraphTraverseTargetLeaves(targetRoot, string.Empty, items);
        var exact = items.Where(item => string.Equals(item.RelativePath, endpoint.RelativeLeafHierarchyPath, StringComparison.OrdinalIgnoreCase)).ToList();
        if (exact.Count == 1)
            return exact[0].Component;

        string expectedLeafName = GraphLeafName(endpoint.LeafComponentName);
        var samePath = items
            .Where(item => string.Equals(item.Component.GetPathName(), endpoint.LeafComponentPath, StringComparison.OrdinalIgnoreCase))
            .ToList();
        var samePathAndName = samePath
            .Where(item => string.Equals(GraphLeafName(item.Component.Name2), expectedLeafName, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (samePathAndName.Count == 1)
            return samePathAndName[0].Component;
        if (samePath.Count == 1)
            return samePath[0].Component;

        string expectedSuffix = GraphInstanceSuffix(expectedLeafName);
        var suffixMatch = samePath
            .Where(item => string.Equals(GraphInstanceSuffix(GraphLeafName(item.Component.Name2)), expectedSuffix, StringComparison.OrdinalIgnoreCase))
            .ToList();
        return suffixMatch.Count == 1 ? suffixMatch[0].Component : null;
    }

    private static IComponent2? ResolveGraphTargetLeafByRelativePath(IComponent2 targetRoot, string? relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath))
            return targetRoot;

        IComponent2 current = targetRoot;
        foreach (string segment in relativePath.Split('/', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var matches = (current.GetChildren() as object[] ?? [])
                .OfType<IComponent2>()
                .Where(child => string.Equals(GraphLeafName(child.Name2), segment, StringComparison.OrdinalIgnoreCase))
                .ToArray();
            if (matches.Length != 1)
                return null;
            current = matches[0];
        }
        return current;
    }

    private static void GraphTraverseTargetLeaves(
        IComponent2 parent,
        string parentRelative,
        ICollection<(IComponent2 Component, string RelativePath)> results)
    {
        foreach (var child in (parent.GetChildren() as object[] ?? []).OfType<IComponent2>())
        {
            string name = GraphLeafName(child.Name2);
            string relative = string.IsNullOrEmpty(parentRelative) ? name : $"{parentRelative}/{name}";
            results.Add((child, relative));
            GraphTraverseTargetLeaves(child, relative, results);
        }
    }

    private static string GraphLeafName(string? value)
    {
        string name = value ?? "Component";
        int slash = name.LastIndexOf('/');
        return slash >= 0 ? name[(slash + 1)..] : name;
    }

    private static string GraphInstanceSuffix(string value)
    {
        int dash = value.LastIndexOf('-');
        return dash >= 0 ? value[dash..] : value;
    }

    private static IFace2? ResolveGraphTargetFace(
        IComponent2 leaf,
        AssemblyModuleMateGraphEndpoint endpoint,
        out string strategy) =>
        ResolveGraphTargetFace(null, leaf, endpoint, out strategy);

    private static IFace2? ResolveGraphTargetFace(
        IModelDoc2? document,
        IComponent2 leaf,
        AssemblyModuleMateGraphEndpoint endpoint,
        out string strategy)
    {
        var persistent = document == null ? null : ResolveGraphPersistentTargetFace(document, endpoint);
        if (persistent != null)
        {
            strategy = "SourceAssemblyPersistentReference";
            return persistent;
        }

        strategy = "BodyFaceIndex";
        object bodyInfo;
        var bodies = (leaf.GetBodies3((int)swBodyType_e.swAllBodies, out bodyInfo) as object[] ?? []).OfType<IBody2>().ToArray();
        if (endpoint.BodyIndex >= 0 && endpoint.BodyIndex < bodies.Length)
        {
            var faces = (bodies[endpoint.BodyIndex].GetFaces() as object[] ?? []).OfType<IFace2>().ToArray();
            if (endpoint.FaceIndexInBody >= 0 && endpoint.FaceIndexInBody < faces.Length)
            {
                var indexed = faces[endpoint.FaceIndexInBody];
                if (endpoint.FaceArea == null || GraphFaceFingerprintCompatible(indexed, endpoint))
                    return indexed;
            }
        }

        strategy = "GeometricFingerprint";
        if (endpoint.FaceArea == null)
            return null;
        var ranked = bodies
            .SelectMany(body => (body.GetFaces() as object[] ?? []).OfType<IFace2>())
            .Select(face => (Face: face, Score: GraphFaceFingerprintScore(face, endpoint)))
            .Where(item => double.IsFinite(item.Score))
            .OrderBy(item => item.Score)
            .ToList();
        if (ranked.Count == 0)
        {
            strategy = "PartDocumentGeometricFingerprint";
            return ResolveGraphPartDocumentFace(leaf, endpoint);
        }
        if (ranked.Count == 1 || ranked[0].Score + 1e-9 < ranked[1].Score)
            return ranked[0].Face;
        return null;
    }

    private static IFace2? ResolveGraphPersistentTargetFace(
        IModelDoc2 document,
        AssemblyModuleMateGraphEndpoint endpoint)
    {
        if (string.IsNullOrWhiteSpace(endpoint.SourceAssemblyPersistentReferenceBase64))
            return null;
        try
        {
            var bytes = Convert.FromBase64String(endpoint.SourceAssemblyPersistentReferenceBase64);
            int error = 0;
            var persistent = document.Extension.GetObjectByPersistReference3(bytes, out error) as IFace2;
            return persistent != null
                && (endpoint.FaceArea == null || GraphFaceFingerprintCompatible(persistent, endpoint))
                ? persistent
                : null;
        }
        catch
        {
            // Freshly inserted modules and topology edits normally fall through to
            // leaf-scoped body/face indices and geometric fingerprints.
            return null;
        }
    }

    private static IFace2? ResolveGraphPartDocumentFace(IComponent2 leaf, AssemblyModuleMateGraphEndpoint endpoint)
    {
        IModelDoc2? model = null;
        try { model = leaf.GetModelDoc2() as IModelDoc2; } catch { }
        if (model is not IPartDoc part)
            return null;
        var ranked = (part.GetBodies2((int)swBodyType_e.swAllBodies, true) as object[] ?? [])
            .OfType<IBody2>()
            .SelectMany(body => (body.GetFaces() as object[] ?? []).OfType<IFace2>())
            .Select(face => (Face: face, Score: GraphFaceFingerprintScore(face, endpoint)))
            .Where(item => double.IsFinite(item.Score))
            .OrderBy(item => item.Score)
            .ToList();
        if (ranked.Count == 0 || (ranked.Count > 1 && ranked[0].Score + 1e-9 >= ranked[1].Score))
            return null;
        try { return leaf.GetCorrespondingEntity(ranked[0].Face) as IFace2; }
        catch { return null; }
    }

    private static bool GraphAreaMatches(IFace2 face, double expected)
    {
        double actual = PairSafeFaceArea(face);
        double tolerance = Math.Max(1e-10, Math.Abs(expected) * 1e-6);
        return Math.Abs(actual - expected) <= tolerance;
    }

    private static bool GraphFaceFingerprintCompatible(IFace2 face, AssemblyModuleMateGraphEndpoint endpoint) =>
        double.IsFinite(GraphFaceFingerprintScore(face, endpoint));

    private static double GraphFaceFingerprintScore(IFace2 face, AssemblyModuleMateGraphEndpoint endpoint)
    {
        if (endpoint.FaceArea is not double expectedArea)
            return double.PositiveInfinity;
        var box = ToDoubleArray(face.GetBox());
        double metricScore = GraphFaceMetricFingerprintScore(
            PairSafeFaceArea(face),
            box,
            expectedArea,
            endpoint.FaceBoxLocal,
            endpoint.FaceCenterLocal);
        if (!double.IsFinite(metricScore))
            return double.PositiveInfinity;

        double normalPenalty = 0;
        if (endpoint.FaceNormalLocal is { Length: >= 3 } expectedNormal
            && SelectionService.TryGetPlanarFaceNormal(face) is { Length: >= 3 } actualNormal)
        {
            double dot = Math.Abs(
                expectedNormal[0] * actualNormal[0]
                + expectedNormal[1] * actualNormal[1]
                + expectedNormal[2] * actualNormal[2]);
            if (dot < 0.999999)
                return double.PositiveInfinity;
            normalPenalty = 1 - dot;
        }
        return metricScore + normalPenalty;
    }

    internal static double GraphFaceMetricFingerprintScore(
        double actualArea,
        double[]? actualBox,
        double expectedArea,
        double[]? expectedBox,
        double[]? expectedCenter)
    {
        if (!double.IsFinite(actualArea) || !double.IsFinite(expectedArea)
            || actualArea <= 0 || expectedArea <= 0)
            return double.PositiveInfinity;
        if (actualBox is not { Length: >= 6 })
            return double.PositiveInfinity;

        double cx = (actualBox[0] + actualBox[3]) / 2.0;
        double cy = (actualBox[1] + actualBox[4]) / 2.0;
        double cz = (actualBox[2] + actualBox[5]) / 2.0;
        double centerDistance = 0;
        if (expectedCenter is { Length: >= 3 })
        {
            double dx = cx - expectedCenter[0];
            double dy = cy - expectedCenter[1];
            double dz = cz - expectedCenter[2];
            centerDistance = Math.Sqrt(dx * dx + dy * dy + dz * dz);
            if (centerDistance > 1e-4)
                return double.PositiveInfinity;
        }

        double areaDifference = Math.Abs(actualArea - expectedArea);
        double strictAreaTolerance = Math.Max(1e-10, Math.Abs(expectedArea) * 1e-6);
        double relativeAreaDifference = areaDifference / Math.Max(Math.Abs(expectedArea), 1e-12);
        double boxDifference = 0;
        if (expectedBox is { Length: >= 6 })
        {
            boxDifference = Enumerable.Range(0, 6)
                .Max(index => Math.Abs(actualBox[index] - expectedBox[index]));
            if (boxDifference > 1e-4)
                return double.PositiveInfinity;
        }

        if (areaDifference > strictAreaTolerance)
        {
            // Rebuilt/imported SolidWorks faces can keep the same support plane,
            // local extent and normal while their reported trimmed area changes
            // slightly.  Only permit that drift when the stronger box+center
            // identity is present; never turn area tolerance into a broad search.
            if (expectedBox is not { Length: >= 6 } || expectedCenter is not { Length: >= 3 }
                || relativeAreaDifference > 0.05)
                return double.PositiveInfinity;
        }

        return centerDistance + boxDifference + relativeAreaDifference * 1e-6;
    }

    private static (double TranslationError, double RotationError) GraphTransformError(double[]? expected, double[]? observed)
    {
        if (expected is not { Length: >= 12 } || observed is not { Length: >= 12 })
            return (double.PositiveInfinity, double.PositiveInfinity);
        double dx = expected[9] - observed[9];
        double dy = expected[10] - observed[10];
        double dz = expected[11] - observed[11];
        double rotation = Enumerable.Range(0, 9).Max(index => Math.Abs(expected[index] - observed[index]));
        return (Math.Sqrt(dx * dx + dy * dy + dz * dz), rotation);
    }

    private static int SafeGraphConstrainedStatus(IComponent2 component)
    {
        try { return component.GetConstrainedStatus(); }
        catch { return (int)swConstrainedStatus_e.swUnknownConstraint; }
    }

    private static string GraphConstrainedStatusName(int value) => Enum.IsDefined(typeof(swConstrainedStatus_e), value)
        ? ((swConstrainedStatus_e)value).ToString()
        : $"Unknown({value})";
}
