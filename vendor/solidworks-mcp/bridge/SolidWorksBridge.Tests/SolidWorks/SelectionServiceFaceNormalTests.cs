using Moq;
using SolidWorks.Interop.sldworks;
using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

public class SelectionServiceFaceNormalTests
{
    [Fact]
    public void TryGetPlanarFaceNormal_UsesPlaneParamsNormalNotRootPoint()
    {
        var surface = new Mock<ISurface>();
        surface.Setup(item => item.IsPlane()).Returns(true);
        surface.SetupGet(item => item.PlaneParams).Returns(
            new double[] { 0, -2, 0, 10, 20, 30 });
        var face = new Mock<IFace2>();
        face.Setup(item => item.GetSurface()).Returns(surface.Object);
        face.Setup(item => item.FaceInSurfaceSense()).Returns(true);

        var normal = SelectionService.TryGetPlanarFaceNormal(face.Object);

        Assert.Equal([0d, -1d, 0d], normal);
    }

    [Fact]
    public void TryGetPlanarFaceNormal_UsesDirectFaceNormalForImportedPlanarFace()
    {
        var surface = new Mock<ISurface>();
        surface.Setup(item => item.IsPlane()).Returns(false);
        var face = new Mock<IFace2>();
        face.Setup(item => item.GetSurface()).Returns(surface.Object);
        face.SetupGet(item => item.Normal).Returns(new double[] { 0, -4, 0 });

        var normal = SelectionService.TryGetPlanarFaceNormal(face.Object);

        Assert.Equal([0d, -1d, 0d], normal);
    }

    [Fact]
    public void TryInferAxisAlignedPlanarFaceNormal_UsesBodyCenterForNegativeDirection()
    {
        double[] faceBox = [-0.195, -1e-7, -0.0965, 0.195, 1e-7, 0.1135];
        double[] bodyBox = [-0.195, -1e-7, -0.0965, 0.195, 0.04, 0.1135];

        var normal = SelectionService.TryInferAxisAlignedPlanarFaceNormal(faceBox, bodyBox);

        Assert.Equal([0d, -1d, 0d], normal);
    }

    [Fact]
    public void TryInferAxisAlignedPlanarFaceNormal_UsesBodyCenterForPositiveDirection()
    {
        double[] faceBox = [-0.2, 0.02, -0.1, 0.2, 0.0200001, 0.1];
        double[] bodyBox = [-0.2, -0.02, -0.1, 0.2, 0.0200001, 0.1];

        var normal = SelectionService.TryInferAxisAlignedPlanarFaceNormal(faceBox, bodyBox);

        Assert.Equal([0d, 1d, 0d], normal);
    }

    [Fact]
    public void TryInferAxisAlignedPlanarFaceNormal_RejectsFaceWithoutThinAxis()
    {
        double[] faceBox = [-0.2, -0.1, -0.1, 0.2, 0.1, 0.1];
        double[] bodyBox = [-0.2, -0.1, -0.1, 0.2, 0.1, 0.1];

        Assert.Null(SelectionService.TryInferAxisAlignedPlanarFaceNormal(faceBox, bodyBox));
    }

    [Fact]
    public void TryInferAxisAlignedPlanarFaceNormal_RejectsCenterPlaneWithAmbiguousDirection()
    {
        double[] faceBox = [-0.2, -1e-7, -0.1, 0.2, 1e-7, 0.1];
        double[] bodyBox = [-0.2, -0.05, -0.1, 0.2, 0.05, 0.1];

        Assert.Null(SelectionService.TryInferAxisAlignedPlanarFaceNormal(faceBox, bodyBox));
    }

    [Fact]
    public void TryFitTriangleNormalFromTessellation_FitsPlainTriangleCoordinates()
    {
        double[] triangles =
        [
            0, 0, 0,
            1, 0, 0,
            0, 1, 0,
            1, 0, 0,
            1, 1, 0,
            0, 1, 0,
        ];

        var normal = SelectionService.TryFitTriangleNormalFromTessellation(triangles);

        Assert.NotNull(normal);
        Assert.Equal(0, normal![0], precision: 9);
        Assert.Equal(0, normal[1], precision: 9);
        Assert.Equal(1, normal[2], precision: 9);
    }

    [Fact]
    public void TryFitTriangleNormalFromTessellation_FitsStridedVertexRecords()
    {
        double[] triangles =
        [
            0, 0, 2, 0, 0, 1, 0.1, 0.1, 0,
            1, 0, 2, 0, 0, 1, 0.2, 0.1, 0,
            0, 1, 2, 0, 0, 1, 0.1, 0.2, 0,
        ];

        var normal = SelectionService.TryFitTriangleNormalFromTessellation(triangles);

        Assert.NotNull(normal);
        Assert.Equal(0, normal![0], precision: 9);
        Assert.Equal(0, normal[1], precision: 9);
        Assert.Equal(1, normal[2], precision: 9);
    }

    [Fact]
    public void TryFitTriangleNormalFromTessellation_ReturnsNullForDegenerateData()
    {
        double[] triangles =
        [
            0, 0, 0,
            1, 0, 0,
            2, 0, 0,
        ];

        Assert.Null(SelectionService.TryFitTriangleNormalFromTessellation(triangles));
    }
}
