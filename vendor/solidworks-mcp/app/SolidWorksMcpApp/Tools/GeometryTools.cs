using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using System.ComponentModel;
using System.Text.Json;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class GeometryTools(StaDispatcher sta, IPointCloudExportService pointCloud)
{
    [McpServerTool, Description("Export the active SolidWorks part or assembly as a JSON point cloud for model inspection. The tool saves all collected points to outputPath and returns metadata plus a small sample so the model can reason about the current 3D shape.")]
    public async Task<string> ExportCurrentPointCloud(
        [Description("Output JSON file path for the point cloud. Example: C:\\exports\\active-point-cloud.json")] string outputPath,
        [Description("Maximum number of unique points to export. Higher values improve shape fidelity but produce larger files.")] int maxPoints = 50000,
        [Description("Number of points to include directly in the MCP response as a preview sample.")] int samplePointCount = 200,
        [Description("When true, tries to read SolidWorks face tessellation points before falling back to vertices and face boxes.")] bool includeTessellation = true)
    {
        var result = await sta.InvokeLoggedAsync(
            nameof(ExportCurrentPointCloud),
            new { outputPath, maxPoints, samplePointCount, includeTessellation },
            () => pointCloud.ExportCurrentDocumentPointCloud(outputPath, maxPoints, samplePointCount, includeTessellation));
        return JsonSerializer.Serialize(result);
    }
}
