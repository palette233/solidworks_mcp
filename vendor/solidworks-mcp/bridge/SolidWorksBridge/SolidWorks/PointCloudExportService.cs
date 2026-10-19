using System.Reflection;
using System.Text.Json;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SolidWorksBridge.SolidWorks;

public record PointCloudPoint(double X, double Y, double Z, string? ComponentName = null, int BodyIndex = -1, int FaceIndex = -1);

public record PointCloudExportResult(
    string OutputPath,
    string Format,
    int PointCount,
    int BodyCount,
    int FaceCount,
    int VertexCount,
    double[]? BoundingBox,
    IReadOnlyList<PointCloudPoint> SamplePoints,
    string Message);

public interface IPointCloudExportService
{
    PointCloudExportResult ExportCurrentDocumentPointCloud(
        string outputPath,
        int maxPoints = 50000,
        int samplePointCount = 200,
        bool includeTessellation = true);
}

public class PointCloudExportService : IPointCloudExportService
{
    private readonly ISwConnectionManager _connectionManager;

    public PointCloudExportService(ISwConnectionManager connectionManager)
    {
        _connectionManager = connectionManager ?? throw new ArgumentNullException(nameof(connectionManager));
    }

    public PointCloudExportResult ExportCurrentDocumentPointCloud(
        string outputPath,
        int maxPoints = 50000,
        int samplePointCount = 200,
        bool includeTessellation = true)
    {
        if (string.IsNullOrWhiteSpace(outputPath))
        {
            throw new ArgumentException("outputPath must not be empty.", nameof(outputPath));
        }

        if (maxPoints <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxPoints), maxPoints, "maxPoints must be greater than zero.");
        }

        if (samplePointCount < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(samplePointCount), samplePointCount, "samplePointCount must not be negative.");
        }

        _connectionManager.EnsureConnected();
        var doc = _connectionManager.SwApp!.IActiveDoc2
            ?? throw new InvalidOperationException("No active document.");

        var bodyContexts = EnumerateBodyContexts(doc).ToList();
        var points = new List<PointCloudPoint>(Math.Min(maxPoints, 4096));
        var seen = new HashSet<string>(StringComparer.Ordinal);
        int faceCount = 0;
        int vertexCount = 0;

        foreach (var (body, componentName, bodyIndex) in bodyContexts)
        {
            if (points.Count >= maxPoints)
            {
                break;
            }

            foreach (var vertex in ((object[]?)body.GetVertices() ?? Array.Empty<object>()).OfType<IVertex>())
            {
                vertexCount++;
                var point = ToPoint(vertex.GetPoint(), componentName, bodyIndex, faceIndex: -1);
                AddPoint(points, seen, point, maxPoints);
            }

            var faces = ((object[]?)body.GetFaces() ?? Array.Empty<object>()).OfType<IFace2>().ToList();
            for (int faceIndex = 0; faceIndex < faces.Count && points.Count < maxPoints; faceIndex++)
            {
                var face = faces[faceIndex];
                faceCount++;

                if (includeTessellation)
                {
                    foreach (var point in TryReadFaceTessellationPoints(face, componentName, bodyIndex, faceIndex))
                    {
                        AddPoint(points, seen, point, maxPoints);
                        if (points.Count >= maxPoints)
                        {
                            break;
                        }
                    }
                }

                if (points.Count >= maxPoints)
                {
                    break;
                }

                foreach (var point in SampleFaceBox(face, componentName, bodyIndex, faceIndex))
                {
                    AddPoint(points, seen, point, maxPoints);
                    if (points.Count >= maxPoints)
                    {
                        break;
                    }
                }
            }
        }

        var normalizedOutputPath = Path.GetFullPath(outputPath);
        Directory.CreateDirectory(Path.GetDirectoryName(normalizedOutputPath)
            ?? throw new InvalidOperationException($"Could not resolve output directory for '{outputPath}'."));

        var payload = new
        {
            documentTitle = SafeGetDocumentTitle(doc),
            documentPath = SafeGetDocumentPath(doc),
            units = "meters",
            format = "solidworks-mcp.point-cloud.v1",
            pointCount = points.Count,
            bodyCount = bodyContexts.Count,
            faceCount,
            vertexCount,
            boundingBox = ComputeBoundingBox(points),
            points,
        };

        var options = new JsonSerializerOptions { WriteIndented = false };
        File.WriteAllText(normalizedOutputPath, JsonSerializer.Serialize(payload, options));

        var sample = points.Take(samplePointCount).ToList().AsReadOnly();
        return new PointCloudExportResult(
            normalizedOutputPath,
            "solidworks-mcp.point-cloud.v1+json",
            points.Count,
            bodyContexts.Count,
            faceCount,
            vertexCount,
            payload.boundingBox,
            sample,
            points.Count == 0
                ? "Exported an empty point cloud. The active document did not expose solid body geometry."
                : $"Exported {points.Count} point-cloud points from the active SolidWorks document.");
    }

    private static IEnumerable<(IBody2 Body, string? ComponentName, int BodyIndex)> EnumerateBodyContexts(IModelDoc2 doc)
    {
        int bodyIndex = 0;
        if (doc is IPartDoc part)
        {
            foreach (var body in GetBodies(part))
            {
                yield return (body, null, bodyIndex++);
            }

            yield break;
        }

        if (doc is IAssemblyDoc assembly)
        {
            var components = (object[]?)assembly.GetComponents(true) ?? Array.Empty<object>();
            foreach (var component in EnumerateAssemblyComponentsRecursive(components.OfType<IComponent2>()))
            {
                foreach (var body in GetBodies(component))
                {
                    yield return (body, component.Name2, bodyIndex++);
                }
            }

            yield break;
        }

        throw new InvalidOperationException("Point-cloud export is only supported for part and assembly documents.");
    }

    private static IEnumerable<PointCloudPoint> TryReadFaceTessellationPoints(
        IFace2 face,
        string? componentName,
        int bodyIndex,
        int faceIndex)
    {
        double[]? values = InvokeTessellationMethod(face, "GetTessTriangles", true)
            ?? InvokeTessellationMethod(face, "GetTessTriangles", false)
            ?? InvokeTessellationMethod(face, "GetTessTriangles");

        if (values == null || values.Length < 3)
        {
            yield break;
        }

        for (int i = 0; i + 2 < values.Length; i += 3)
        {
            yield return new PointCloudPoint(values[i], values[i + 1], values[i + 2], componentName, bodyIndex, faceIndex);
        }
    }

    private static double[]? InvokeTessellationMethod(IFace2 face, string methodName, params object[] args)
    {
        try
        {
            var method = ((object)face).GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.Public);
            if (method == null)
            {
                return null;
            }

            var parameters = method.GetParameters();
            if (parameters.Length != args.Length)
            {
                return null;
            }

            return ToDoubleArray(method.Invoke(face, args));
        }
        catch (TargetInvocationException)
        {
            return null;
        }
        catch (ArgumentException)
        {
            return null;
        }
    }

    private static IEnumerable<PointCloudPoint> SampleFaceBox(IFace2 face, string? componentName, int bodyIndex, int faceIndex)
    {
        var box = ToDoubleArray(face.GetBox());
        if (box == null || box.Length < 6)
        {
            yield break;
        }

        double minX = box[0];
        double minY = box[1];
        double minZ = box[2];
        double maxX = box[3];
        double maxY = box[4];
        double maxZ = box[5];
        double midX = (minX + maxX) / 2d;
        double midY = (minY + maxY) / 2d;
        double midZ = (minZ + maxZ) / 2d;

        yield return new PointCloudPoint(midX, midY, midZ, componentName, bodyIndex, faceIndex);
        yield return new PointCloudPoint(minX, minY, minZ, componentName, bodyIndex, faceIndex);
        yield return new PointCloudPoint(maxX, minY, minZ, componentName, bodyIndex, faceIndex);
        yield return new PointCloudPoint(minX, maxY, minZ, componentName, bodyIndex, faceIndex);
        yield return new PointCloudPoint(maxX, maxY, maxZ, componentName, bodyIndex, faceIndex);
    }

    private static PointCloudPoint? ToPoint(object? raw, string? componentName, int bodyIndex, int faceIndex)
    {
        var values = ToDoubleArray(raw);
        return values is { Length: >= 3 }
            ? new PointCloudPoint(values[0], values[1], values[2], componentName, bodyIndex, faceIndex)
            : null;
    }

    private static void AddPoint(
        List<PointCloudPoint> points,
        HashSet<string> seen,
        PointCloudPoint? point,
        int maxPoints)
    {
        if (point == null || points.Count >= maxPoints)
        {
            return;
        }

        string key = $"{Math.Round(point.X, 9):R},{Math.Round(point.Y, 9):R},{Math.Round(point.Z, 9):R},{point.ComponentName}";
        if (seen.Add(key))
        {
            points.Add(point);
        }
    }

    private static double[]? ComputeBoundingBox(IReadOnlyList<PointCloudPoint> points)
    {
        if (points.Count == 0)
        {
            return null;
        }

        return
        [
            points.Min(point => point.X),
            points.Min(point => point.Y),
            points.Min(point => point.Z),
            points.Max(point => point.X),
            points.Max(point => point.Y),
            points.Max(point => point.Z),
        ];
    }

    private static double[]? ToDoubleArray(object? raw)
    {
        return raw switch
        {
            null => null,
            double[] doubles => doubles,
            object[] objects => objects.OfType<double>().ToArray(),
            _ => null,
        };
    }

    private static IEnumerable<IComponent2> EnumerateAssemblyComponentsRecursive(IEnumerable<IComponent2> components)
    {
        foreach (var component in components)
        {
            yield return component;

            var children = (object[]?)component.GetChildren() ?? Array.Empty<object>();
            foreach (var child in EnumerateAssemblyComponentsRecursive(children.OfType<IComponent2>()))
            {
                yield return child;
            }
        }
    }

    private static IEnumerable<IBody2> GetBodies(IPartDoc part)
    {
        return ((object[]?)part.GetBodies2((int)swBodyType_e.swSolidBody, true) ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    private static IEnumerable<IBody2> GetBodies(IComponent2 component)
    {
        return (component.GetBodies3((int)swBodyType_e.swSolidBody, out _) as object[] ?? Array.Empty<object>())
            .OfType<IBody2>();
    }

    private static string? SafeGetDocumentTitle(IModelDoc2 doc)
    {
        try
        {
            return doc.GetTitle();
        }
        catch
        {
            return null;
        }
    }

    private static string? SafeGetDocumentPath(IModelDoc2 doc)
    {
        try
        {
            return doc.GetPathName();
        }
        catch
        {
            return null;
        }
    }
}
