using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace SolidWorksMcpApp;

/// <summary>
/// Merges the SolidWorks MCP server entry into Claude Desktop and VS Code
/// configuration files at startup, so users don't need to configure
/// anything manually after installation.
/// </summary>
internal static class AutoConfigService
{
    private static readonly JsonSerializerOptions s_writeOpts =
        new() { WriteIndented = true };
    private const string WorkspaceEnvName = "SOLIDWORKS_MCP_WORKSPACE";
    private const string QueryScriptEnvName = "SOLIDWORKS_API_RAG_QUERY_SCRIPT";
    private const string IndexDirEnvName = "SOLIDWORKS_API_RAG_INDEX_DIR";

    /// <summary>
    /// Writes MCP server entries to Claude Desktop and VS Code configs.
    /// Runs silently — any failure is swallowed so it never crashes the app.
    /// </summary>
    public static void WriteConfigs()
    {
        var exePath = Environment.ProcessPath
                      ?? throw new InvalidOperationException("Process path is unavailable.");

        TryWriteClaudeConfig(exePath);
        TryWriteVsCodeConfig(exePath);
    }

    // ── Claude Desktop ────────────────────────────────────────────────────

    private static void TryWriteClaudeConfig(string exePath)
    {
        try
        {
            var dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Claude");
            var file = Path.Combine(dir, "claude_desktop_config.json");

            var root = ReadOrEmpty(file);

            if (root["mcpServers"] is not JsonObject mcpServers)
            {
                mcpServers = new JsonObject();
                root["mcpServers"] = mcpServers;
            }

            mcpServers["solidworks"] = CreateClaudeServerConfig(exePath);

            Directory.CreateDirectory(dir);
            File.WriteAllText(file, root.ToJsonString(s_writeOpts));
        }
        catch
        {
            // Best-effort; ignore all errors.
        }
    }

    // ── VS Code ───────────────────────────────────────────────────────────

    private static void TryWriteVsCodeConfig(string exePath)
    {
        try
        {
            var file = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Code", "User", "mcp.json");

            var root = ReadOrEmpty(file);

            if (root["servers"] is not JsonObject servers)
            {
                servers = new JsonObject();
                root["servers"] = servers;
            }

            servers["solidworks"] = CreateVsCodeServerConfig(exePath);

            var dir = Path.GetDirectoryName(file)!;
            Directory.CreateDirectory(dir);
            File.WriteAllText(file, root.ToJsonString(s_writeOpts));
        }
        catch
        {
            // Best-effort; ignore all errors.
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private static JsonObject ReadOrEmpty(string filePath)
    {
        if (!File.Exists(filePath))
            return new JsonObject();

        try
        {
            return JsonNode.Parse(File.ReadAllText(filePath)) as JsonObject
                   ?? new JsonObject();
        }
        catch
        {
            return new JsonObject();
        }
    }

    internal static JsonObject CreateClaudeServerConfig(string exePath)
    {
        var env = CreateRagEnvironment(exePath);
        return new JsonObject
        {
            ["command"] = exePath,
            ["args"] = new JsonArray("--proxy", "--client", "Claude Desktop"),
            ["env"] = env
        };
    }

    internal static JsonObject CreateVsCodeServerConfig(string exePath)
    {
        var env = CreateRagEnvironment(exePath);
        return new JsonObject
        {
            ["type"] = "stdio",
            ["command"] = exePath,
            ["args"] = new JsonArray("--proxy", "--client", "VS Code"),
            ["env"] = env
        };
    }

    internal static string CreateOpenClawCommand(string exePath)
    {
        var payload = new JsonObject
        {
            ["command"] = exePath,
            ["args"] = new JsonArray("--proxy", "--client", "OpenClaw"),
            ["env"] = CreateRagEnvironment(exePath)
        };

        var escapedPayload = payload.ToJsonString().Replace("'", "''");
        return $"$config = '{escapedPayload}'; openclaw mcp set solidworks $config";
    }

    private static JsonObject CreateRagEnvironment(string exePath)
    {
        var workspaceRoot = ResolveWorkspaceRoot(exePath);
        var queryScriptPath = Path.Combine(workspaceRoot, "scripts", "query_rag.py");
        var indexDirPath = Path.Combine(workspaceRoot, "data", "solidworks_api_2025", "rag_index");

        return new JsonObject
        {
            [WorkspaceEnvName] = workspaceRoot,
            [QueryScriptEnvName] = queryScriptPath,
            [IndexDirEnvName] = indexDirPath,
        };
    }

    private static string ResolveWorkspaceRoot(string exePath)
    {
        var configured = Environment.GetEnvironmentVariable(WorkspaceEnvName);
        if (!string.IsNullOrWhiteSpace(configured) && Directory.Exists(configured))
        {
            return configured;
        }

        var exeDir = Path.GetDirectoryName(exePath)
            ?? throw new InvalidOperationException("Executable directory is unavailable.");

        var current = exeDir;
        for (var i = 0; i < 8; i++)
        {
            if (File.Exists(Path.Combine(current, "scripts", "query_rag.py")))
            {
                return current;
            }

            var parent = Directory.GetParent(current);
            if (parent is null)
            {
                break;
            }

            current = parent.FullName;
        }

        return exeDir;
    }
}
