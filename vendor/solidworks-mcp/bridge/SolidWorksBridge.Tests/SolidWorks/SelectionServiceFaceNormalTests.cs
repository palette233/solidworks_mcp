using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

public class SelectionServiceFaceNormalTests
{
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
