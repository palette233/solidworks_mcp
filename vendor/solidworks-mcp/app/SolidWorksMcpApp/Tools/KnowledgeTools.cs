using ModelContextProtocol.Server;
using SolidWorksMcpApp.Logging;
using System.ComponentModel;
using System.Diagnostics;
using System.Text;

namespace SolidWorksMcpApp.Tools;

[McpServerToolType]
public class KnowledgeTools
{
    private static readonly string ProjectRoot = ResolveProjectRoot();
    private static readonly string QueryScriptPath = ResolveQueryScriptPath();
    private static readonly string IndexDir = ResolveIndexDir();

    [McpServerTool, Description("Search the local SOLIDWORKS API RAG index and return ranked knowledge snippets from the crawled SOLIDWORKS Web Help corpus. Use this only for documentation lookup, API explanation, or when no existing SolidWorks action tool matches the requested operation. Do not use this when the request is to create, edit, bind, define, save, or otherwise execute a modeling change and a direct action tool already exists.")]
    public async Task<string> SearchSolidWorksApiKnowledge(
        [Description("Natural-language question or API symbol query.")] string query,
        [Description("Maximum number of results to return.")] int topK = 6,
        [Description("When true, returns concatenated context blocks for downstream reasoning instead of short ranked summaries.")] bool contextOnly = false,
        [Description("Maximum number of characters in the returned context when contextOnly=true.")] int maxChars = 12000)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            throw new ArgumentException("query must not be empty.", nameof(query));
        }

        if (!File.Exists(QueryScriptPath))
        {
            throw new FileNotFoundException($"RAG query script was not found: {QueryScriptPath}");
        }

        if (!Directory.Exists(IndexDir))
        {
            throw new DirectoryNotFoundException($"RAG index directory was not found: {IndexDir}");
        }

        var arguments = new StringBuilder();
        arguments.Append('"').Append(QueryScriptPath).Append('"');
        arguments.Append(" --index-dir ").Append('"').Append(IndexDir).Append('"');
        arguments.Append(" --top-k ").Append(Math.Clamp(topK, 1, 20));
        if (contextOnly)
        {
            arguments.Append(" --context --max-chars ").Append(Math.Clamp(maxChars, 500, 50000));
        }
        arguments.Append(' ').Append('"').Append(query.Replace("\"", "\\\"")).Append('"');

        var psi = new ProcessStartInfo
        {
            FileName = "python",
            Arguments = arguments.ToString(),
            WorkingDirectory = ProjectRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        using var process = new Process { StartInfo = psi };
        process.Start();

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();

        var stdout = (await stdoutTask).Trim();
        var stderr = (await stderrTask).Trim();

        if (process.ExitCode != 0)
        {
            ServerLogBuffer.Append("ERROR", nameof(KnowledgeTools), $"RAG query failed for '{query}'. ExitCode={process.ExitCode}. stderr={stderr}");
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(stderr)
                    ? $"RAG query process failed with exit code {process.ExitCode}."
                    : $"RAG query process failed: {stderr}");
        }

        return stdout;
    }

    private static string ResolveProjectRoot()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("SOLIDWORKS_MCP_WORKSPACE");
        if (!string.IsNullOrWhiteSpace(configuredRoot) && Directory.Exists(configuredRoot))
        {
            return configuredRoot;
        }

        var current = AppContext.BaseDirectory;
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

        return Directory.GetCurrentDirectory();
    }

    private static string ResolveQueryScriptPath()
    {
        var configuredPath = Environment.GetEnvironmentVariable("SOLIDWORKS_API_RAG_QUERY_SCRIPT");
        if (!string.IsNullOrWhiteSpace(configuredPath))
        {
            return configuredPath;
        }

        return Path.Combine(ProjectRoot, "scripts", "query_rag.py");
    }

    private static string ResolveIndexDir()
    {
        var configuredPath = Environment.GetEnvironmentVariable("SOLIDWORKS_API_RAG_INDEX_DIR");
        if (!string.IsNullOrWhiteSpace(configuredPath))
        {
            return configuredPath;
        }

        return Path.Combine(ProjectRoot, "data", "solidworks_api_2025", "rag_index");
    }
}
