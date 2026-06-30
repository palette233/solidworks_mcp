using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

public class CommonBaseLayoutMathTests
{
    [Fact]
    public void ProjectPoint_UsesAnchorOriginAndProjectedAxes()
    {
        var frame = CommonBaseLayoutMath.CreateFrame(
            origin: [10, 20, 30],
            normal: [0, 0, 1],
            preferredUAxis: [1, 0, 0]);

        var layout = CommonBaseLayoutMath.ProjectPoint([12, 25, 99], frame);

        Assert.Equal(2, layout.X, precision: 9);
        Assert.Equal(5, layout.Y, precision: 9);
    }

    [Fact]
    public void PointFromLayout_RoundTripsProjectedPointOnPlane()
    {
        var frame = CommonBaseLayoutMath.CreateFrame(
            origin: [1, 2, 3],
            normal: [0, 0, 2],
            preferredUAxis: [2, 0, 0]);
        var layout = new CommonBaseLayout2d(0.25, -0.5);

        var world = CommonBaseLayoutMath.PointFromLayout(layout, frame);
        var roundTrip = CommonBaseLayoutMath.ProjectPoint(world, frame);

        Assert.Equal(layout.X, roundTrip.X, precision: 9);
        Assert.Equal(layout.Y, roundTrip.Y, precision: 9);
        Assert.Equal(3, world[2], precision: 9);
    }

    [Fact]
    public void ProjectPointWithRotation_UsesBestProjectedComponentAxis()
    {
        var frame = CommonBaseLayoutMath.CreateFrame(
            origin: [0, 0, 0],
            normal: [0, 0, 1],
            preferredUAxis: [1, 0, 0]);

        var layout = CommonBaseLayoutMath.ProjectPointWithRotation(
            point: [2, 3, 9],
            frame,
            xAxis: [0, 0, 1],
            yAxis: [0, 0.5, 0],
            zAxis: [1, 0, 0]);

        Assert.Equal(2, layout.X, precision: 9);
        Assert.Equal(3, layout.Y, precision: 9);
        Assert.Equal("z", layout.ThetaAxis);
        Assert.Equal(0, layout.ThetaDegrees!.Value, precision: 9);
    }

    [Fact]
    public void DeltaAngleDegrees_UsesShortestWrappedDifference()
    {
        Assert.Equal(20, CommonBaseLayoutMath.DeltaAngleDegrees(170, -170), precision: 9);
        Assert.Equal(-20, CommonBaseLayoutMath.DeltaAngleDegrees(-170, 170), precision: 9);
    }

    [Fact]
    public void CreateFrame_ReplacesPreferredAxisWhenParallelToNormal()
    {
        var frame = CommonBaseLayoutMath.CreateFrame(
            origin: [0, 0, 0],
            normal: [1, 0, 0],
            preferredUAxis: [2, 0, 0]);

        Assert.Equal(0, CommonBaseLayoutMath.Dot(frame.UAxis, frame.Normal), precision: 9);
        Assert.Equal(1, CommonBaseLayoutMath.Dot(frame.Normal, frame.Normal), precision: 9);
        Assert.Equal(1, CommonBaseLayoutMath.Dot(frame.UAxis, frame.UAxis), precision: 9);
        Assert.Equal(1, CommonBaseLayoutMath.Dot(frame.VAxis, frame.VAxis), precision: 9);
    }

    [Fact]
    public void NormalsMatchDirection_RejectsOppositeNormals()
    {
        Assert.True(CommonBaseLayoutMath.NormalsMatchDirection([0, 0, 2], [0, 0, 1]));
        Assert.False(CommonBaseLayoutMath.NormalsMatchDirection([0, 0, -2], [0, 0, 1]));
    }

    [Fact]
    public void NormalsMatchDirection_UsesDotThreshold()
    {
        Assert.True(CommonBaseLayoutMath.NormalsMatchDirection([0.98, 0, 0.2], [1, 0, 0], 0.95));
        Assert.False(CommonBaseLayoutMath.NormalsMatchDirection([0.8, 0, 0.6], [1, 0, 0], 0.95));
    }

    [Fact]
    public void NormalsMatchDirection_RejectsZeroNormals()
    {
        Assert.False(CommonBaseLayoutMath.IsValidNormal([0, 0, 0]));
        Assert.False(CommonBaseLayoutMath.NormalsMatchDirection([0, 0, 0], [0, 0, 1]));
        Assert.False(CommonBaseLayoutMath.NormalsMatchDirection([0, 0, 1], [0, 0, 0]));
    }

    [Fact]
    public void CalculateNormalAlignmentRotation_ReturnsZeroAngleForAlignedNormals()
    {
        var rotation = CommonBaseLayoutMath.CalculateNormalAlignmentRotation([0, 2, 0], [0, 1, 0]);

        Assert.NotNull(rotation);
        Assert.Equal(0, rotation.AngleDegrees, precision: 9);
        Assert.Equal(1, CommonBaseLayoutMath.Dot(rotation.Axis, rotation.Axis), precision: 9);
    }

    [Fact]
    public void CalculateNormalAlignmentRotation_ReturnsRightHandAxisForQuarterTurn()
    {
        var rotation = CommonBaseLayoutMath.CalculateNormalAlignmentRotation([1, 0, 0], [0, 1, 0]);

        Assert.NotNull(rotation);
        Assert.Equal(90, rotation.AngleDegrees, precision: 9);
        Assert.Equal(0, rotation.Axis[0], precision: 9);
        Assert.Equal(0, rotation.Axis[1], precision: 9);
        Assert.Equal(1, rotation.Axis[2], precision: 9);
    }

    [Fact]
    public void CalculateNormalAlignmentRotation_HandlesOppositeNormals()
    {
        var rotation = CommonBaseLayoutMath.CalculateNormalAlignmentRotation([0, 0, 1], [0, 0, -1]);

        Assert.NotNull(rotation);
        Assert.Equal(180, rotation.AngleDegrees, precision: 9);
        Assert.Equal(1, CommonBaseLayoutMath.Dot(rotation.Axis, rotation.Axis), precision: 9);
        Assert.Equal(0, CommonBaseLayoutMath.Dot(rotation.Axis, [0, 0, 1]), precision: 9);
    }
}
