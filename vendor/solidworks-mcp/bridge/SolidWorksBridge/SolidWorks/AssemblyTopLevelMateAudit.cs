using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using System.Text.Json;

namespace SolidWorksBridge.SolidWorks;

public record AssemblyTopLevelMateAuditEntry(
    string MateName,
    int MateType,
    string MateTypeName,
    int Alignment,
    string AlignmentName,
    int EntityCount,
    IReadOnlyList<string> ComponentNames,
    double? Distance,
    double? Angle,
    bool IsSuppressed,
    AssemblyModuleMateAdvancedOptions? AdvancedOptions);

public record AssemblyTopLevelMateAuditResult(
    string SchemaVersion,
    string SourceAssemblyPath,
    int MateCount,
    IReadOnlyList<AssemblyTopLevelMateAuditEntry> Mates,
    string? SavedJsonPath,
    IReadOnlyList<string> Diagnostics);

public record AssemblySlotMateUpdateResult(
    bool Success,
    string AssemblyPath,
    string MateName,
    AssemblyModuleMateAdvancedOptions? Before,
    AssemblyModuleMateAdvancedOptions? After,
    bool RebuildSucceeded,
    bool Saved,
    IReadOnlyList<string> Diagnostics);

public partial class AssemblyService
{
    /// <summary>
    /// Read only top-level mate feature metadata. Unlike ExportModuleMateGraph this intentionally
    /// does not resolve faces, bodies, persistent references, or module ownership, so it remains
    /// suitable for diagnosing large or flexible subassemblies whose complete endpoint export is
    /// too expensive or unstable.
    /// </summary>
    public AssemblyTopLevelMateAuditResult AuditTopLevelMateFeatures(
        string sourceAssemblyPath,
        string? outputPath = null,
        bool saveJson = true)
    {
        if (string.IsNullOrWhiteSpace(sourceAssemblyPath))
            throw new ArgumentException("sourceAssemblyPath must not be empty.", nameof(sourceAssemblyPath));
        if (!File.Exists(sourceAssemblyPath))
            throw new FileNotFoundException($"Source assembly was not found: {sourceAssemblyPath}", sourceAssemblyPath);

        var diagnostics = new List<string>();
        var (_, document, _) = OpenMatePairSource(sourceAssemblyPath);
        var entries = new List<AssemblyTopLevelMateAuditEntry>();
        foreach (var feature in EnumerateTopLevelMateFeatures(document))
        {
            IMate2? mate = null;
            try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
            if (mate == null)
            {
                diagnostics.Add($"Feature '{feature.Name}' did not expose IMate2 and was skipped.");
                continue;
            }

            int mateType = PairSafeMateType(mate);
            int entityCount = PairSafeMateEntityCount(mate);
            var componentNames = new List<string>();
            for (int index = 0; index < entityCount; index++)
            {
                var component = PairSafeReferenceComponent(PairSafeMateEntity(mate, index));
                string? name = null;
                try { name = component?.Name2; } catch { }
                if (!string.IsNullOrWhiteSpace(name)
                    && !componentNames.Contains(name, StringComparer.OrdinalIgnoreCase))
                {
                    componentNames.Add(name);
                }
            }

            entries.Add(new AssemblyTopLevelMateAuditEntry(
                feature.Name ?? "Mate",
                mateType,
                PairMateTypeName(mateType),
                PairSafeMateAlignment(mate),
                PairAlignmentName(PairSafeMateAlignment(mate)),
                entityCount,
                componentNames.AsReadOnly(),
                PairSafeDistance(feature, mateType),
                MateGraphSafeAngle(feature, mateType),
                PairSafeFeatureSuppressed(feature),
                ReadGraphMateAdvancedOptions(feature, mate, mateType)));
        }

        diagnostics.Add("This lightweight audit intentionally omits endpoint geometry and persistent references.");
        var result = new AssemblyTopLevelMateAuditResult(
            "solidworks-top-level-mate-audit/v1",
            Path.GetFullPath(sourceAssemblyPath),
            entries.Count,
            entries.AsReadOnly(),
            null,
            diagnostics.AsReadOnly());

        if (!saveJson)
            return result;

        string path = Path.GetFullPath(outputPath ?? Path.Combine(
            Path.GetDirectoryName(sourceAssemblyPath)!,
            $"{Path.GetFileNameWithoutExtension(sourceAssemblyPath)}_top_level_mate_audit.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var saved = result with { SavedJsonPath = path };
        File.WriteAllText(path, JsonSerializer.Serialize(saved, new JsonSerializerOptions { WriteIndented = true }));
        return saved;
    }

    /// <summary>
    /// Change one named top-level Slot mate in an explicitly supplied assembly copy. Callers are
    /// responsible for supplying a non-prototype path; the method refuses unsaved documents and
    /// records the before/after values for closure evidence.
    /// </summary>
    public AssemblySlotMateUpdateResult UpdateTopLevelSlotMate(
        string assemblyPath,
        string mateName,
        int constraint,
        double distance = 0,
        double percent = 0,
        bool flipDirection = false,
        bool save = true)
    {
        if (string.IsNullOrWhiteSpace(assemblyPath))
            throw new ArgumentException("assemblyPath must not be empty.", nameof(assemblyPath));
        if (!File.Exists(assemblyPath))
            throw new FileNotFoundException($"Assembly was not found: {assemblyPath}", assemblyPath);
        if (string.IsNullOrWhiteSpace(mateName))
            throw new ArgumentException("mateName must not be empty.", nameof(mateName));
        if (constraint is < 0 or > 3)
            throw new ArgumentOutOfRangeException(nameof(constraint), "Slot constraint must be Free=0, Center=1, Distance=2, or Percent=3.");
        if (percent is < 0 or > 100)
            throw new ArgumentOutOfRangeException(nameof(percent), "Slot percent must be in [0, 100].");

        var diagnostics = new List<string>();
        var (_, document, _) = OpenMatePairSource(assemblyPath);
        var feature = EnumerateTopLevelMateFeatures(document)
            .FirstOrDefault(candidate => string.Equals(candidate.Name, mateName, StringComparison.OrdinalIgnoreCase));
        if (feature == null)
            throw new InvalidOperationException($"Top-level mate feature '{mateName}' was not found in {assemblyPath}.");

        IMate2? mate = null;
        try { mate = feature.GetSpecificFeature2() as IMate2; } catch { }
        if (mate == null || PairSafeMateType(mate) != (int)swMateType_e.swMateSLOT)
            throw new InvalidOperationException($"Feature '{mateName}' is not a Slot mate.");

        var before = ReadGraphMateAdvancedOptions(feature, mate, PairSafeMateType(mate));
        if (feature.GetDefinition() is not ISlotMateFeatureData slot)
            throw new InvalidOperationException($"Feature '{mateName}' did not expose ISlotMateFeatureData.");

        bool modified = false;
        slot.Constraint = constraint;
        slot.Distance = distance;
        slot.Percent = percent;
        slot.FlipDirection = flipDirection;
        modified = feature.ModifyDefinition(slot, document, null);

        if (!modified)
            diagnostics.Add("SolidWorks returned false from ModifyDefinition.");
        bool rebuilt = false;
        try { rebuilt = document.EditRebuild3(); }
        catch (Exception ex) { diagnostics.Add($"Rebuild failed: {ex.Message}"); }

        bool saved = false;
        if (save && modified)
        {
            int errors = 0;
            int warnings = 0;
            try { saved = document.Save3(1, ref errors, ref warnings); }
            catch (Exception ex) { diagnostics.Add($"Save failed: {ex.Message}"); }
            if (!saved || errors != 0 || warnings != 0)
                diagnostics.Add($"Save3 result={saved}, errors={errors}, warnings={warnings}.");
        }

        AssemblyModuleMateAdvancedOptions? after = null;
        var refreshedFeature = EnumerateTopLevelMateFeatures(document)
            .FirstOrDefault(candidate => string.Equals(candidate.Name, mateName, StringComparison.OrdinalIgnoreCase));
        if (refreshedFeature != null)
        {
            IMate2? refreshedMate = null;
            try { refreshedMate = refreshedFeature.GetSpecificFeature2() as IMate2; } catch { }
            if (refreshedMate != null)
                after = ReadGraphMateAdvancedOptions(refreshedFeature, refreshedMate, PairSafeMateType(refreshedMate));
        }

        bool success = modified
            && after?.SlotConstraint == constraint
            && (!save || saved);
        return new AssemblySlotMateUpdateResult(
            success,
            Path.GetFullPath(assemblyPath),
            mateName,
            before,
            after,
            rebuilt,
            saved,
            diagnostics.AsReadOnly());
    }
}
