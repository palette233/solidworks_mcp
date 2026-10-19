using Moq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorksBridge.SolidWorks;
using SolidWorksMcpApp.Tools;

namespace SolidWorksBridge.Tests.SolidWorks;

public class FeatureDimensionServiceTests
{
    [Fact]
    public void ListFeatureDimensions_EnumeratesAllFeatureDisplayDimensions()
    {
        var feature = new Mock<Feature>();
        feature.Setup(f => f.Name).Returns("3D草图1");
        feature.Setup(f => f.GetTypeName2()).Returns("3DProfileFeature");

        var d1 = CreateDisplayDimension("D1@3D草图1", 1.0);
        var d2 = CreateDisplayDimension("D2@3D草图1", 2.0);
        var d3 = CreateDisplayDimension("D3@3D草图1", 3.0);

        feature.Setup(f => f.GetFirstDisplayDimension()).Returns(d1.display.Object);
        feature.Setup(f => f.GetNextDisplayDimension(d1.display.Object)).Returns(d2.display.Object);
        feature.Setup(f => f.GetNextDisplayDimension(d2.display.Object)).Returns(d3.display.Object);
        feature.Setup(f => f.GetNextDisplayDimension(d3.display.Object)).Returns((DisplayDimension)null!);
        feature.Setup(f => f.GetNextFeature()).Returns((Feature)null!);

        var doc = new Mock<IModelDoc2>();
        doc.Setup(d => d.FirstFeature()).Returns(feature.Object);
        doc.Setup(d => d.GetUserPreferenceToggle(It.IsAny<int>())).Returns(false);
        doc.Setup(d => d.SetUserPreferenceToggle(It.IsAny<int>(), It.IsAny<bool>()));

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(doc.Object);

        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var service = new FeatureDimensionService(manager.Object, Mock.Of<IEquationService>());

        var result = service.ListFeatureDimensions("3D草图1");

        Assert.Equal(3, result.Count);
        Assert.Collection(
            result,
            item => Assert.Equal("D1@3D草图1", item.DimensionToken),
            item => Assert.Equal("D2@3D草图1", item.DimensionToken),
            item => Assert.Equal("D3@3D草图1", item.DimensionToken));
        doc.Verify(d => d.SetUserPreferenceToggle(It.IsAny<int>(), true), Times.Once);
        doc.Verify(d => d.SetUserPreferenceToggle(It.IsAny<int>(), false), Times.Once);
    }

    [Fact]
    public void SetSquareTubeLength_WithDimensionName_UpdatesNamedParentSketchDimension()
    {
        var lengthDimension = CreateDisplayDimension("D3@3D鑽夊浘1", 1.0);
        lengthDimension.dimension
            .Setup(d => d.SetSystemValue3(
                1.5,
                (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,
                null!))
            .Returns((int)swSetValueReturnStatus_e.swSetValue_Successful);

        var lengthSketch = new Mock<Feature>();
        lengthSketch.Setup(f => f.Name).Returns("3D鑽夊浘1");
        lengthSketch.Setup(f => f.GetTypeName2()).Returns("3DProfileFeature");
        lengthSketch.Setup(f => f.GetFirstDisplayDimension()).Returns(lengthDimension.display.Object);
        lengthSketch.Setup(f => f.GetNextDisplayDimension(lengthDimension.display.Object)).Returns((DisplayDimension)null!);
        lengthSketch.Setup(f => f.GetNextSubFeature()).Returns((Feature)null!);

        var parentFeature = new Mock<Feature>();
        parentFeature.Setup(f => f.Name).Returns("WeldmentParent");
        parentFeature.Setup(f => f.GetFirstSubFeature()).Returns(lengthSketch.Object);

        var tubeFeature = new Mock<Feature>();
        tubeFeature.Setup(f => f.Name).Returns("Structural Member1");
        tubeFeature.Setup(f => f.GetTypeName2()).Returns("StructuralMember");
        tubeFeature.Setup(f => f.GetOwnerFeature()).Returns(parentFeature.Object);
        tubeFeature.Setup(f => f.GetNextFeature()).Returns((Feature)null!);

        var doc = new Mock<IModelDoc2>();
        doc.Setup(d => d.FirstFeature()).Returns(tubeFeature.Object);
        doc.Setup(d => d.EditRebuild3()).Returns(true);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(doc.Object);

        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var service = new FeatureDimensionService(manager.Object, Mock.Of<IEquationService>());

        var result = service.SetSquareTubeLength("Structural Member1", CartesianAxis.Z, "1500mm", "D3@3D鑽夊浘1");

        Assert.Equal("D3@3D鑽夊浘1", result.DimensionToken);
        Assert.Equal("3D鑽夊浘1", result.SketchFeatureName);
        Assert.Contains("explicitly named", result.Message);
        lengthDimension.dimension.Verify(d => d.SetSystemValue3(
            1.5,
            (int)swSetValueInConfiguration_e.swSetValue_InThisConfiguration,
            null!), Times.Once);
        doc.Verify(d => d.EditRebuild3(), Times.Once);
    }

    [Theory]
    [InlineData("x", CartesianAxis.X)]
    [InlineData("X", CartesianAxis.X)]
    [InlineData("y", CartesianAxis.Y)]
    [InlineData("z", CartesianAxis.Z)]
    public void ParseCartesianAxis_ParsesSupportedAxes(string value, CartesianAxis expected)
    {
        var axis = ToolArgumentParsing.ParseCartesianAxis(value, nameof(value));

        Assert.Equal(expected, axis);
    }

    [Fact]
    public void ParseCartesianAxis_WithUnsupportedValue_Throws()
    {
        Assert.Throws<ArgumentException>(() => ToolArgumentParsing.ParseCartesianAxis("xy", "axis"));
    }

    [Fact]
    public void ChooseAxisAlignedSegment_PrefersSegmentMostAlignedToRequestedAxis()
    {
        var sketch = new Mock<ISketch>();
        var xLine = CreateSketchLine((0, 0, 0), (1.2, 0.01, 0));
        var yLine = CreateSketchLine((0, 0, 0), (0.01, 2.5, 0));
        var zLine = CreateSketchLine((0, 0, 0), (0.01, 0.01, 0.8));
        sketch.Setup(s => s.GetSketchSegments()).Returns(new object[]
        {
            xLine.segment.Object,
            yLine.segment.Object,
            zLine.segment.Object,
        });

        var chosenX = FeatureDimensionService.ChooseAxisAlignedSegment(sketch.Object, CartesianAxis.X);
        var chosenY = FeatureDimensionService.ChooseAxisAlignedSegment(sketch.Object, CartesianAxis.Y);
        var chosenZ = FeatureDimensionService.ChooseAxisAlignedSegment(sketch.Object, CartesianAxis.Z);

        Assert.Same(xLine.segment.Object, chosenX.Segment);
        Assert.Same(yLine.segment.Object, chosenY.Segment);
        Assert.Same(zLine.segment.Object, chosenZ.Segment);
    }

    [Fact]
    public void ChooseAxisAlignedSegment_WhenNoCandidateMatches_Throws()
    {
        var sketch = new Mock<ISketch>();
        var diagonal = CreateSketchLine((0, 0, 0), (1, 1, 0));
        sketch.Setup(s => s.GetSketchSegments()).Returns(new object[] { diagonal.segment.Object });

        var error = Assert.Throws<InvalidOperationException>(() =>
            FeatureDimensionService.ChooseAxisAlignedSegment(sketch.Object, CartesianAxis.X));

        Assert.Contains("aligned with axis X", error.Message);
    }

    [Theory]
    [InlineData("1200mm", 1.2)]
    [InlineData("120cm", 1.2)]
    [InlineData("1.2m", 1.2)]
    [InlineData("1.2", 1.2)]
    public void ParseLengthExpressionToMeters_SupportsExpectedUnits(string expression, double expected)
    {
        double actual = InvokeParseLengthExpressionToMeters(expression);

        Assert.Equal(expected, actual, precision: 10);
    }

    [Fact]
    public void ResolveSquareTubeLengthControllingSketchFeature_PrefersParentLengthSketchOverProfileSketch()
    {
        var profileSketch = new Mock<Feature>();
        profileSketch.Setup(f => f.Name).Returns("Sketch1");
        profileSketch.Setup(f => f.GetTypeName2()).Returns("ProfileFeature");
        profileSketch.Setup(f => f.GetNextSubFeature()).Returns((Feature?)null);

        var tubeFeature = new Mock<Feature>();
        tubeFeature.Setup(f => f.Name).Returns("Structural Member1");
        tubeFeature.Setup(f => f.GetTypeName2()).Returns("StructuralMember");
        tubeFeature.Setup(f => f.GetFirstSubFeature()).Returns(profileSketch.Object);

        var lengthSketch = new Mock<Feature>();
        lengthSketch.Setup(f => f.Name).Returns("3D草图1");
        lengthSketch.Setup(f => f.GetTypeName2()).Returns("3DProfileFeature");
        lengthSketch.Setup(f => f.GetNextSubFeature()).Returns((Feature?)null);

        var parentFeature = new Mock<Feature>();
        parentFeature.Setup(f => f.Name).Returns("WeldmentParent");
        parentFeature.Setup(f => f.GetTypeName2()).Returns("Weldment");
        parentFeature.Setup(f => f.GetFirstSubFeature()).Returns(lengthSketch.Object);

        tubeFeature.Setup(f => f.GetOwnerFeature()).Returns(parentFeature.Object);

        var method = typeof(FeatureDimensionService).GetMethod(
            "ResolveSquareTubeLengthControllingSketchFeature",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);

        Assert.NotNull(method);
        var resolved = method!.Invoke(null, [tubeFeature.Object]) as Feature;

        Assert.Same(lengthSketch.Object, resolved);
    }

    [Fact]
    public void ResolveSquareTubeLengthControllingSketch_RequiresAxisLineAndSkipsProfileSketch()
    {
        var profileSketch = new Mock<Feature>();
        var profile = new Mock<ISketch>();
        var profileLine = CreateSketchLine((0, 0, 0), (0.04, 0, 0));
        profile.Setup(s => s.GetSketchSegments()).Returns(new object[] { profileLine.segment.Object });
        profileSketch.Setup(f => f.Name).Returns("Sketch1");
        profileSketch.Setup(f => f.GetTypeName2()).Returns("ProfileFeature");
        profileSketch.Setup(f => f.GetSpecificFeature2()).Returns(profile.Object);

        var lengthSketch = new Mock<Feature>();
        var length = new Mock<ISketch>();
        var lengthLine = CreateSketchLine((0, 0, 0), (0, 0, 1.2));
        length.Setup(s => s.GetSketchSegments()).Returns(new object[] { lengthLine.segment.Object });
        lengthSketch.Setup(f => f.Name).Returns("3D草图1");
        lengthSketch.Setup(f => f.GetTypeName2()).Returns("3DProfileFeature");
        lengthSketch.Setup(f => f.GetSpecificFeature2()).Returns(length.Object);

        profileSketch.Setup(f => f.GetNextSubFeature()).Returns(lengthSketch.Object);
        lengthSketch.Setup(f => f.GetNextSubFeature()).Returns((Feature?)null);

        var parentFeature = new Mock<Feature>();
        parentFeature.Setup(f => f.Name).Returns("WeldmentParent");
        parentFeature.Setup(f => f.GetFirstSubFeature()).Returns(profileSketch.Object);

        var tubeFeature = new Mock<Feature>();
        tubeFeature.Setup(f => f.Name).Returns("Structural Member1");
        tubeFeature.Setup(f => f.GetTypeName2()).Returns("StructuralMember");
        tubeFeature.Setup(f => f.GetOwnerFeature()).Returns(parentFeature.Object);
        tubeFeature.Setup(f => f.GetFirstSubFeature()).Returns(profileSketch.Object);

        var method = typeof(FeatureDimensionService).GetMethod(
            "ResolveSquareTubeLengthControllingSketch",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);

        Assert.NotNull(method);
        var resolved = method!.Invoke(null, [tubeFeature.Object, CartesianAxis.Z, null]);
        var sketchFeature = resolved!.GetType().GetProperty("SketchFeature")!.GetValue(resolved) as Feature;
        var segment = resolved.GetType().GetProperty("Segment")!.GetValue(resolved) as FeatureDimensionService.AxisSegmentCandidate;

        Assert.Same(lengthSketch.Object, sketchFeature);
        Assert.Same(lengthLine.segment.Object, segment!.Segment);
    }

    [Fact]
    public void ScoreLengthControlSketchCandidate_PrefersChineseSketchNamesOverGenericSketch()
    {
        var englishSketch = new Mock<Feature>();
        englishSketch.Setup(f => f.Name).Returns("Sketch1");

        var chineseSketch = new Mock<Feature>();
        chineseSketch.Setup(f => f.Name).Returns("3D草图1");

        var method = typeof(FeatureDimensionService).GetMethod(
            "ScoreLengthControlSketchCandidate",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);

        Assert.NotNull(method);
        int englishScore = (int)method!.Invoke(null, [englishSketch.Object])!;
        int chineseScore = (int)method.Invoke(null, [chineseSketch.Object])!;

        Assert.True(chineseScore > englishScore);
    }

    private static double InvokeParseLengthExpressionToMeters(string expression)
    {
        var method = typeof(FeatureDimensionService).GetMethod(
            "ParseLengthExpressionToMeters",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic);

        Assert.NotNull(method);
        return (double)method!.Invoke(null, [expression])!;
    }

    private static (Mock<DisplayDimension> display, Mock<Dimension> dimension) CreateDisplayDimension(
        string fullName,
        double systemValue)
    {
        var display = new Mock<DisplayDimension>();
        var dimension = new Mock<Dimension>();

        dimension.Setup(d => d.FullName).Returns(fullName);
        dimension.Setup(d => d.GetNameForSelection()).Returns(fullName);
        dimension.SetupGet(d => d.SystemValue).Returns(systemValue);
        display.Setup(d => d.GetDimension2(0)).Returns(dimension.Object);
        display.Setup(d => d.GetNameForSelection()).Returns(fullName);

        return (display, dimension);
    }

    private static (Mock<ISketchSegment> segment, Mock<ISketchLine> line) CreateSketchLine(
        (double X, double Y, double Z) start,
        (double X, double Y, double Z) end)
    {
        var segment = new Mock<ISketchSegment>();
        var line = new Mock<ISketchLine>();
        var startPoint = new Mock<SketchPoint>();
        var endPoint = new Mock<SketchPoint>();

        startPoint.SetupGet(p => p.X).Returns(start.X);
        startPoint.SetupGet(p => p.Y).Returns(start.Y);
        startPoint.SetupGet(p => p.Z).Returns(start.Z);
        endPoint.SetupGet(p => p.X).Returns(end.X);
        endPoint.SetupGet(p => p.Y).Returns(end.Y);
        endPoint.SetupGet(p => p.Z).Returns(end.Z);

        line.As<ISketchSegment>();
        line.Setup(l => l.IGetStartPoint2()).Returns(startPoint.Object);
        line.Setup(l => l.IGetEndPoint2()).Returns(endPoint.Object);

        segment.As<ISketchLine>();
        segment.As<ISketchLine>().Setup(l => l.IGetStartPoint2()).Returns(startPoint.Object);
        segment.As<ISketchLine>().Setup(l => l.IGetEndPoint2()).Returns(endPoint.Object);

        return (segment, line);
    }
}
