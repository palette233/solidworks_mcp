using Microsoft.Extensions.Logging.Abstractions;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;
using System.Text.Json;
using System.Text.Json.Nodes;

static string FindWorkspaceRoot()
{
    var dir = new DirectoryInfo(AppContext.BaseDirectory);
    while (dir is not null)
    {
        if (Directory.Exists(Path.Combine(dir.FullName, "vendor", "solidworks-mcp")) &&
            Directory.Exists(Path.Combine(dir.FullName, "apps", "demo-backend")))
        {
            return dir.FullName;
        }

        dir = dir.Parent;
    }

    return Directory.GetCurrentDirectory();
}

static object? ToObject(JsonNode? node)
{
    if (node is null)
    {
        return null;
    }

    if (node is JsonValue value)
    {
        return value.GetValue<JsonElement>().ValueKind switch
        {
            JsonValueKind.String => value.GetValue<string>(),
            JsonValueKind.Number => value.GetValue<JsonElement>().TryGetInt64(out var integer)
                ? integer
                : value.GetValue<double>(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => value.GetValue<JsonElement>().ToString(),
        };
    }

    if (node is JsonArray array)
    {
        return array.Select(ToObject).ToArray();
    }

    if (node is JsonObject obj)
    {
        return obj.ToDictionary(pair => pair.Key, pair => ToObject(pair.Value));
    }

    return null;
}

static string[] ReadStringArray(JsonObject? root, string name, string[] fallback)
{
    if (root?[name] is not JsonArray array)
    {
        return fallback;
    }

    return array
        .Select(item => item?.GetValue<string>())
        .Where(item => !string.IsNullOrWhiteSpace(item))
        .Select(item => item!)
        .ToArray();
}

var input = await Console.In.ReadToEndAsync();
var root = JsonNode.Parse(input)?.AsObject()
    ?? throw new InvalidOperationException("Expected a JSON object on stdin.");

var workspace = FindWorkspaceRoot();
var defaultApp = Path.Combine(
    workspace,
    "vendor",
    "solidworks-mcp",
    "app",
    "SolidWorksMcpApp",
    "bin",
    "Release",
    "net8.0-windows",
    "win-x64",
    "SolidWorksMcpApp.dll");

var serverCommand = root["serverCommand"]?.GetValue<string>() ?? "dotnet";
var serverArguments = ReadStringArray(
    root,
    "serverArguments",
    [defaultApp, "--proxy", "--client", "DemoBackendArrange"]);
var workingDirectory = root["workingDirectory"]?.GetValue<string>() ?? Path.GetDirectoryName(defaultApp);

var transport = new StdioClientTransport(
    new StdioClientTransportOptions
    {
        Name = "solidworks-demo-backend-runner",
        Command = serverCommand,
        Arguments = serverArguments,
        WorkingDirectory = workingDirectory,
    },
    NullLoggerFactory.Instance);

await using var client = await McpClient.CreateAsync(transport, loggerFactory: NullLoggerFactory.Instance);

var results = new JsonArray();
foreach (var toolNode in root["tools"]?.AsArray() ?? [])
{
    var toolObject = toolNode?.AsObject()
        ?? throw new InvalidOperationException("Each tool entry must be a JSON object.");
    var toolName = toolObject["tool"]?.GetValue<string>()
        ?? throw new InvalidOperationException("Each tool entry requires a tool name.");
    var arguments = ToObject(toolObject["arguments"]) as Dictionary<string, object?>
        ?? new Dictionary<string, object?>();

    var callResult = await client.CallToolAsync(toolName, arguments);
    var content = new JsonArray();
    foreach (var text in callResult.Content.OfType<TextContentBlock>())
    {
        content.Add(new JsonObject
        {
            ["type"] = "text",
            ["text"] = text.Text,
        });
    }

    results.Add(new JsonObject
    {
        ["tool"] = toolName,
        ["content"] = content,
        ["isError"] = callResult.IsError,
    });
}

var output = new JsonObject
{
    ["results"] = results,
};

Console.WriteLine(output.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
