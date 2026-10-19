using System.Text.Json;
using SolidWorks.Interop.swconst;
using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

public class AssemblyEditableMateGraphTests
{
    [Fact]
    public void FaceMetricFingerprint_AllowsSmallAreaDriftWhenBoxAndCenterMatch()
    {
        double score = AssemblyService.GraphFaceMetricFingerprintScore(
            actualArea: 0.00933064,
            actualBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedArea: 0.0095942,
            expectedBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedCenter: [0.0125, 0, -0.2694999975]);

        Assert.True(double.IsFinite(score));
    }

    [Fact]
    public void FaceMetricFingerprint_RejectsAreaDriftWithoutBoxEvidence()
    {
        double score = AssemblyService.GraphFaceMetricFingerprintScore(
            actualArea: 0.00933064,
            actualBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedArea: 0.0095942,
            expectedBox: null,
            expectedCenter: [0.0125, 0, -0.2694999975]);

        Assert.Equal(double.PositiveInfinity, score);
    }

    [Fact]
    public void FaceMetricFingerprint_RejectsLargeAreaOrBoxDrift()
    {
        double largeArea = AssemblyService.GraphFaceMetricFingerprintScore(
            actualArea: 0.007,
            actualBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedArea: 0.0095942,
            expectedBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedCenter: [0.0125, 0, -0.2694999975]);
        double shiftedBox = AssemblyService.GraphFaceMetricFingerprintScore(
            actualArea: 0.00933064,
            actualBox: [0.014, -0.00890003, -0.539000025, 0.01400006, 0.00890003, 0.00000003],
            expectedArea: 0.0095942,
            expectedBox: [0.01249997, -0.00890003, -0.539000025, 0.01250003, 0.00890003, 0.00000003],
            expectedCenter: [0.0125, 0, -0.2694999975]);

        Assert.Equal(double.PositiveInfinity, largeArea);
        Assert.Equal(double.PositiveInfinity, shiftedBox);
    }

    [Fact]
    public void ContextLeafPoseAnchor_DeserializesOptionalFixAfterApplyFlag()
    {
        const string json = """
            {
              "relativeLeafHierarchyPath": "LM10-1/Carriage-1",
              "transform": [1,0,0,0,1,0,0,0,1,0.1,0.2,0.3,1,0,0,0],
              "evidence": "prototype static state",
              "fixAfterApply": true,
              "solvingState": 1
            }
            """;

        var anchor = JsonSerializer.Deserialize<AssemblyContextLeafPoseAnchor>(
            json,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        Assert.NotNull(anchor);
        Assert.True(anchor!.FixAfterApply);
        Assert.Equal(1, anchor.SolvingState);
        Assert.Equal("LM10-1/Carriage-1", anchor.RelativeLeafHierarchyPath);
        Assert.Equal(16, anchor.Transform.Length);
    }

    [Fact]
    public void SelectGraphModuleRootIndex_DistinguishesSameFileOccurrences()
    {
        var roots = new[]
        {
            new ComponentInstanceInfo("T401AA-07388-0-1", "C:\\cad\\T401.SLDPRT", "T401AA-07388-0-1", 0),
            new ComponentInstanceInfo("T401AA-07388-0-2", "C:\\cad\\T401.SLDPRT", "T401AA-07388-0-2", 0),
        };

        int? selected = AssemblyService.SelectGraphModuleRootIndex(
            roots,
            "C:\\cad\\T401.SLDPRT",
            "T401",
            "T401AA-07388-0-2",
            allowUniquePathFallback: false);

        Assert.Equal(1, selected);
    }

    [Fact]
    public void SelectGraphModuleRootIndex_DoesNotReuseFirstOccurrenceForMissingSecondTarget()
    {
        var roots = new[]
        {
            new ComponentInstanceInfo("T401AA-07388-0-1", "C:\\cad\\T401.SLDPRT", "T401AA-07388-0-1", 0),
        };

        int? selected = AssemblyService.SelectGraphModuleRootIndex(
            roots,
            "C:\\cad\\T401.SLDPRT",
            "T401",
            "T401AA-07388-0-2",
            allowUniquePathFallback: false);

        Assert.Null(selected);
    }

    [Fact]
    public void SelectGraphModuleRootIndex_AllowsLegacyUniquePathFallback()
    {
        var roots = new[]
        {
            new ComponentInstanceInfo("renamed-instance-4", "C:\\cad\\A200.SLDASM", "renamed-instance-4", 0),
        };

        int? selected = AssemblyService.SelectGraphModuleRootIndex(
            roots,
            "C:\\cad\\A200.SLDASM",
            "A200",
            "A200-1",
            allowUniquePathFallback: true);

        Assert.Equal(0, selected);
    }

    [Fact]
    public void SelectGraphModuleRootIndex_UsesUniqueHierarchyWhenAssemblyWasRelocated()
    {
        var roots = new[]
        {
            new ComponentInstanceInfo(
                "FL9C254098A000.001-1",
                @"D:\vendor-old\FL9C254098A000.001.SLDASM",
                "FL9C254098A000.001-1",
                0),
            new ComponentInstanceInfo(
                "FL9C254098D000.001-1",
                @"D:\vendor-old\FL9C254098D000.001.SLDASM",
                "FL9C254098D000.001-1",
                0),
        };

        int? selected = AssemblyService.SelectGraphModuleRootIndex(
            roots,
            @"D:\current-data\FL9C254098A000.001.SLDASM",
            "A000",
            "FL9C254098A000.001-1",
            allowUniquePathFallback: true);

        Assert.Equal(0, selected);
    }

    [Fact]
    public void CompareContextLeafPoses_AcceptsStableTransforms()
    {
        var before = new Dictionary<string, double[]>
        {
            ["part.sldprt|root/part-1"] = Enumerable.Range(0, 16).Select(value => (double)value).ToArray(),
        };
        var after = before.ToDictionary(item => item.Key, item => item.Value.ToArray());
        after["part.sldprt|root/part-1"][9] += 1e-10;

        var result = AssemblyService.CompareContextLeafPoses(before, after, 1e-8);

        Assert.True(result.Stable);
        Assert.Equal(1e-10, result.MaximumTransformElementError!.Value, 12);
    }

    [Fact]
    public void CompareContextLeafPoses_RejectsMissingOrMovedLeaf()
    {
        var before = new Dictionary<string, double[]>
        {
            ["part.sldprt|root/part-1"] = new double[16],
            ["tool.sldprt|root/tool-1"] = new double[16],
        };
        var after = new Dictionary<string, double[]>
        {
            ["part.sldprt|root/part-1"] = new double[16],
        };
        after["part.sldprt|root/part-1"][10] = 0.001;

        var result = AssemblyService.CompareContextLeafPoses(before, after, 1e-8);

        Assert.False(result.Stable);
        Assert.Equal(1, result.MissingAfterCount);
        Assert.Equal(0.001, result.MaximumTransformElementError);
    }

    [Fact]
    public void LoadAndValidateEditableMateGraph_AcceptsValidTwoModuleDistanceGraph()
    {
        using var fixture = EditableGraphFixture.Create();

        var graph = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);

        Assert.Equal(2, graph.ModuleCount);
        Assert.Single(graph.Mates);
        Assert.Equal(0.05, graph.Mates[0].Distance);
        Assert.True(graph.EditPolicy!.SourceGraphImmutable);
    }

    [Fact]
    public void BuildContextDirectMateEditPlan_CreatesOnlyNewMateAndPreservesSourceMate()
    {
        using var fixture = EditableGraphFixture.Create();
        var source = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var existing = source.Mates[0];
        var added = existing with { MateName = "NL_A500_A700_added", Distance = 0.06 };
        var graph = source with
        {
            InterModuleMateCount = 2,
            Mates = new[] { existing, added },
            PatchAudit = new AssemblyMateGraphPatchAudit(
                "mate-graph-patch/v1", "digest", 1,
                new[] { new AssemblyMateGraphPatchOperation(0, "addMate", added.MateName) },
                [])
        };

        var plan = AssemblyService.BuildContextDirectMateEditPlan(graph);

        Assert.True(plan.UsesPatchAudit);
        Assert.Empty(plan.SourceMateNamesToSuppress);
        Assert.Equal(new[] { added.MateName }, plan.EffectiveMateNamesToCreate);
        Assert.Equal(new[] { existing.MateName }, plan.EffectiveMateNamesToPreserve);
    }

    [Fact]
    public void BuildContextDirectMateEditPlan_UpdateSuppressesOldAndCreatesEffectiveMate()
    {
        using var fixture = EditableGraphFixture.Create();
        var source = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var updated = source.Mates[0] with { Distance = 0.06 };
        var before = new Dictionary<string, JsonElement>
        {
            ["MateName"] = JsonSerializer.SerializeToElement(source.Mates[0].MateName),
            ["Distance"] = JsonSerializer.SerializeToElement(0.05),
        };
        var graph = source with
        {
            Mates = new[] { updated },
            PatchAudit = new AssemblyMateGraphPatchAudit(
                "mate-graph-patch/v1", "digest", 1,
                new[] { new AssemblyMateGraphPatchOperation(0, "updateMate", updated.MateName, before) },
                [])
        };

        var plan = AssemblyService.BuildContextDirectMateEditPlan(graph);

        Assert.Equal(new[] { source.Mates[0].MateName }, plan.SourceMateNamesToSuppress);
        Assert.Equal(new[] { updated.MateName }, plan.EffectiveMateNamesToCreate);
        Assert.Empty(plan.EffectiveMateNamesToPreserve);
    }

    [Fact]
    public void BuildContextDirectMateEditPlan_AppliesMultipleUpdatesAsOneBatch()
    {
        using var fixture = EditableGraphFixture.Create();
        var source = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var first = source.Mates[0] with { MateName = "mount-coincident", MateType = 0, Distance = null };
        var second = source.Mates[0] with { MateName = "mount-width", MateType = 11, Distance = null };
        var third = source.Mates[0] with { MateName = "mount-distance", MateType = 5 };
        var mates = new[] { first, second, third };
        var operations = mates.Select((mate, index) =>
            new AssemblyMateGraphPatchOperation(index, "updateMate", mate.MateName)).ToArray();
        var graph = source with
        {
            InterModuleMateCount = mates.Length,
            Mates = mates,
            EditPolicy = source.EditPolicy! with
            {
                SourceMateNamesToSuppress = mates.Select(item => item.MateName).ToArray()
            },
            PatchAudit = new AssemblyMateGraphPatchAudit(
                "mate-graph-patch/v1", "digest", operations.Length, operations, [])
        };

        var plan = AssemblyService.BuildContextDirectMateEditPlan(graph);

        Assert.True(plan.UsesPatchAudit);
        Assert.Equal(3, plan.SourceMateNamesToSuppress.Count);
        Assert.Equal(3, plan.EffectiveMateNamesToCreate.Count);
        Assert.Empty(plan.EffectiveMateNamesToPreserve);
        Assert.Empty(plan.RemovedMateNames);
    }

    [Fact]
    public void LoadAndValidateEditableMateGraph_RejectsCountMismatch()
    {
        using var fixture = EditableGraphFixture.Create(moduleCountOverride: 3);

        var error = Assert.Throws<InvalidOperationException>(
            () => AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath));

        Assert.Contains("count fields", error.Message);
    }

    [Fact]
    public void LoadAndValidateEditableMateGraph_AcceptsWidthMateWithAdvancedOptions()
    {
        using var fixture = EditableGraphFixture.Create(mateTypeOverride: (int)swMateType_e.swMateWIDTH);

        var graph = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);

        var mate = Assert.Single(graph.Mates);
        Assert.Equal((int)swMateType_e.swMateWIDTH, mate.MateType);
        Assert.Equal(4, mate.Endpoints.Count);
        Assert.Equal(new[] { 0, 1 }, mate.AdvancedOptions!.WidthEndpointIndices);
        Assert.Equal(new[] { 2, 3 }, mate.AdvancedOptions.TabEndpointIndices);
    }

    [Fact]
    public void VerifyEditableMate_RecognizesRebuiltNameAndParameters()
    {
        using var fixture = EditableGraphFixture.Create();
        var graph = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var expected = Assert.Single(graph.Mates);
        var observed = expected with { MateName = "MCP_GRAPH_距离8" };

        var verification = AssemblyService.VerifyEditableMate(expected, new[] { observed });

        Assert.True(verification.Found);
        Assert.True(verification.TypeMatches);
        Assert.True(verification.AlignmentMatches);
        Assert.True(verification.DistanceMatches);
        Assert.True(verification.AngleMatches);
    }

    [Fact]
    public void VerifyEditableMate_RejectsChangedDistance()
    {
        using var fixture = EditableGraphFixture.Create();
        var graph = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var expected = Assert.Single(graph.Mates);
        var observed = expected with { MateName = "MCP_GRAPH_距离8", Distance = 0.06 };

        var verification = AssemblyService.VerifyEditableMate(expected, new[] { observed });

        Assert.True(verification.Found);
        Assert.False(verification.DistanceMatches);
    }

    [Fact]
    public void VerifyEditableMate_IgnoresNormalizedAlignmentForPerpendicularMate()
    {
        using var fixture = EditableGraphFixture.Create(mateTypeOverride: (int)swMateType_e.swMatePERPENDICULAR);
        var graph = AssemblyService.LoadAndValidateEditableMateGraph(fixture.GraphPath);
        var expected = Assert.Single(graph.Mates);
        var observed = expected with
        {
            MateName = "MCP_GRAPH_垂直1",
            Alignment = expected.Alignment == (int)swMateAlign_e.swMateAlignALIGNED
                ? (int)swMateAlign_e.swMateAlignANTI_ALIGNED
                : (int)swMateAlign_e.swMateAlignALIGNED,
        };

        var verification = AssemblyService.VerifyEditableMate(expected with { MateName = "垂直1" }, new[] { observed });

        Assert.True(verification.Found);
        Assert.True(verification.TypeMatches);
        Assert.True(verification.AlignmentMatches);
    }

    [Fact]
    public void BuildFaceEndpointId_IsDeterministicAndConfigurationSensitive()
    {
        var endpoint = EditableGraphFixture.Endpoint(0, "A500", "A500-1") with
        {
            FaceArea = 0.123,
            FaceCenterLocal = new[] { 0.1, 0.2, 0.3 },
            FaceNormalLocal = new[] { 0.0, 0.0, 1.0 },
        };

        string first = AssemblyService.BuildFaceEndpointId(endpoint, "Default", "Default", "Plane");
        string repeated = AssemblyService.BuildFaceEndpointId(endpoint, "Default", "Default", "Plane");
        string changedConfiguration = AssemblyService.BuildFaceEndpointId(endpoint, "Alt", "Default", "Plane");

        Assert.Equal(first, repeated);
        Assert.NotEqual(first, changedConfiguration);
        Assert.StartsWith("face:a500:", first);
    }

    [Fact]
    public void MeasureParallelPlaneDistance_ReturnsNormalSeparation()
    {
        double? distance = AssemblyService.MeasureParallelPlaneDistance(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 2.0 },
            new[] { 0.4, -0.2, 0.05 },
            new[] { 0.0, 0.0, -1.0 });

        Assert.NotNull(distance);
        Assert.Equal(0.05, distance!.Value, 12);
    }

    [Fact]
    public void MeasureParallelPlaneDistance_IgnoresInPlaneOffset()
    {
        double? distance = AssemblyService.MeasureParallelPlaneDistance(
            new[] { 1.0, 2.0, 3.0 },
            new[] { 1.0, 0.0, 0.0 },
            new[] { 1.0, 25.0, -19.0 },
            new[] { -1.0, 0.0, 0.0 });

        Assert.Equal(0.0, distance!.Value, 12);
    }

    [Fact]
    public void MeasureParallelPlaneDistance_RejectsNonParallelPlanes()
    {
        double? distance = AssemblyService.MeasureParallelPlaneDistance(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 1.0, 0.0, 0.0 },
            new[] { 0.05, 0.0, 0.0 },
            new[] { 0.0, 1.0, 0.0 });

        Assert.Null(distance);
    }

    [Theory]
    [InlineData(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)]
    [InlineData(1.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0)]
    [InlineData(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, Math.PI / 2.0)]
    public void MeasureUndirectedNormalAngle_ReturnsSmallestPlaneAngle(
        double ax, double ay, double az,
        double bx, double by, double bz,
        double expected)
    {
        double? angle = AssemblyService.MeasureUndirectedNormalAngle(
            new[] { ax, ay, az },
            new[] { bx, by, bz });

        Assert.NotNull(angle);
        Assert.Equal(expected, angle!.Value, 12);
    }

    [Fact]
    public void MeasureUndirectedNormalAngle_RejectsZeroVector()
    {
        double? angle = AssemblyService.MeasureUndirectedNormalAngle(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 1.0 });

        Assert.Null(angle);
    }

    [Fact]
    public void MeasureCoincidentPlaneDeviation_ReturnsDistanceAndUndirectedAngle()
    {
        var deviation = AssemblyService.MeasureCoincidentPlaneDeviation(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 1.0 },
            new[] { 0.2, -0.4, 0.0002 },
            new[] { 0.0, 0.0, -2.0 });

        Assert.NotNull(deviation);
        Assert.Equal(0.0002, deviation!.Value.DistanceMeters, 12);
        Assert.Equal(0.0, deviation.Value.AngleRadians, 12);
    }

    [Fact]
    public void MeasureCoincidentPlaneDeviation_RejectsNonParallelPlanes()
    {
        var deviation = AssemblyService.MeasureCoincidentPlaneDeviation(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 1.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 1.0, 0.0 });

        Assert.Null(deviation);
    }

    [Fact]
    public void MeasureCoaxialCylinderDeviation_AcceptsOppositeAxesAndAxialOffset()
    {
        var deviation = AssemblyService.MeasureCoaxialCylinderDeviation(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 2.0 },
            new[] { 0.0, 0.0, 0.8 },
            new[] { 0.0, 0.0, -1.0 });

        Assert.NotNull(deviation);
        Assert.Equal(0.0, deviation!.Value.DistanceMeters, 12);
        Assert.Equal(0.0, deviation.Value.AngleRadians, 12);
    }

    [Fact]
    public void MeasureCoaxialCylinderDeviation_ReportsRadialAndAngularError()
    {
        var deviation = AssemblyService.MeasureCoaxialCylinderDeviation(
            new[] { 0.0, 0.0, 0.0 },
            new[] { 0.0, 0.0, 1.0 },
            new[] { 0.003, 0.004, 0.7 },
            new[] { 0.0, 1.0, 1.0 });

        Assert.NotNull(deviation);
        Assert.Equal(0.005, deviation!.Value.DistanceMeters, 12);
        Assert.Equal(Math.PI / 4.0, deviation.Value.AngleRadians, 12);
    }

    [Fact]
    public void MapSourceWorldPointToCurrentModulePose_AppliesOnlyTopLevelPoseDelta()
    {
        double[] source =
        [
            1, 0, 0,
            0, 1, 0,
            0, 0, 1,
            10, 20, 30,
            1, 0, 0, 0,
        ];
        double[] current =
        [
            0, 1, 0,
            -1, 0, 0,
            0, 0, 1,
            100, 200, 300,
            1, 0, 0, 0,
        ];

        var mapped = AssemblyService.MapSourceWorldPointToCurrentModulePose(
            new[] { 11.0, 22.0, 33.0 }, source, current);

        Assert.Equal(new[] { 98.0, 201.0, 303.0 }, mapped);
    }

    [Fact]
    public void MapSourceWorldVectorToCurrentModulePose_RotatesWithoutTranslation()
    {
        double[] identity =
        [
            1, 0, 0,
            0, 1, 0,
            0, 0, 1,
            0, 0, 0,
            1, 0, 0, 0,
        ];
        double[] current =
        [
            0, 1, 0,
            -1, 0, 0,
            0, 0, 1,
            9, 8, 7,
            1, 0, 0, 0,
        ];

        var mapped = AssemblyService.MapSourceWorldVectorToCurrentModulePose(
            new[] { 1.0, 0.0, 0.0 }, identity, current);

        Assert.Equal(new[] { 0.0, 1.0, 0.0 }, mapped);
    }

    private sealed class EditableGraphFixture : IDisposable
    {
        private readonly string _directory;
        public string GraphPath { get; }

        private EditableGraphFixture(string directory, string graphPath)
        {
            _directory = directory;
            GraphPath = graphPath;
        }

        public static EditableGraphFixture Create(int? moduleCountOverride = null, int? mateTypeOverride = null)
        {
            string directory = Path.Combine(Path.GetTempPath(), $"editable-mate-graph-{Guid.NewGuid():N}");
            Directory.CreateDirectory(directory);
            string firstPath = Path.Combine(directory, "A500.SLDASM");
            string secondPath = Path.Combine(directory, "A700.SLDASM");
            File.WriteAllBytes(firstPath, []);
            File.WriteAllBytes(secondPath, []);
            var modules = new[]
            {
                new AssemblyModuleMateGraphNode("A500", "A500-1", firstPath, "A500-1", null, false, 3, "resolved", 1),
                new AssemblyModuleMateGraphNode("A700", "A700-1", secondPath, "A700-1", null, false, 3, "resolved", 1),
            };
            int mateType = mateTypeOverride ?? (int)swMateType_e.swMateDISTANCE;
            var endpoints = mateType == (int)swMateType_e.swMateWIDTH
                ? new[]
                {
                    Endpoint(0, "A500", "A500-1"),
                    Endpoint(1, "A500", "A500-1"),
                    Endpoint(2, "A700", "A700-1"),
                    Endpoint(3, "A700", "A700-1"),
                }
                : new[]
                {
                    Endpoint(0, "A500", "A500-1"),
                    Endpoint(1, "A700", "A700-1"),
                };
            var advanced = mateType == (int)swMateType_e.swMateWIDTH
                ? new AssemblyModuleMateAdvancedOptions(
                    (int)swMateWidthOptions_e.swMateWidth_Centered,
                    -1, -1, false,
                    new[] { 0, 1 }, new[] { 2, 3 },
                    null, null, null, null, null, 0, false)
                : null;
            var mates = new[]
            {
                new AssemblyModuleMateGraphMate(
                    "距离8", mateType, ((swMateType_e)mateType).ToString(),
                    (int)swMateAlign_e.swMateAlignANTI_ALIGNED, "swMateAlignANTI_ALIGNED",
                    0.05, null, false, true, null,
                    new[] { "A500", "A700" }, new[] { "A500-1", "A700-1" }, endpoints, advanced),
            };
            var graph = new AssemblyEditableMateGraphDocument(
                "editable-module-mate-graph/v1",
                moduleCountOverride ?? modules.Length,
                mates.Length,
                modules,
                mates,
                new AssemblyEditableMateGraphPolicy("A500", "source_pose", true));
            string graphPath = Path.Combine(directory, "effective.json");
            File.WriteAllText(graphPath, JsonSerializer.Serialize(graph));
            return new EditableGraphFixture(directory, graphPath);
        }

        internal static AssemblyModuleMateGraphEndpoint Endpoint(int index, string token, string hierarchyPath) =>
            new(index, token, hierarchyPath, $"{hierarchyPath}/Leaf-1", "Leaf-1", "Leaf-1", "Leaf.SLDPRT",
                "Face", 0, index + 1, 0.01, null, null, null, null, null, null);

        public void Dispose() => Directory.Delete(_directory, recursive: true);
    }
}
