using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using SolidWorksBridge.SolidWorks;
using SolidWorksMcpApp;
using SolidWorksMcpApp.Ipc;
using SolidWorksMcpApp.Logging;
using System.Diagnostics;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Windows.Forms;

// Explicit Main is required so [STAThread] can be applied for WinForms.
internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        try { Run(args); }
        catch (Exception ex)
        {
            var t = Path.Combine(Path.GetTempPath(), "sw_mcp_crash.txt");
            File.WriteAllText(t, ex.ToString());
            MessageBox.Show(ex.Message + "\n\nDetails written to:\n" + t,
                "SolidWorks MCP – Startup Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    static void Run(string[] args)
    {
        // ── Proxy mode (spawned by VS Code / Claude Desktop) ─────────────
        // MCP clients pass --proxy; the exe relays stdin/stdout to the Hub.
        if (args.Contains("--proxy")) { RunProxy(args); return; }

        // ── Direct stdio mode (backend automation, no Hub/proxy) ─────────
        if (args.Contains("--stdio-direct") || args.Contains("--direct"))
        {
            RunDirectStdio();
            return;
        }

        // ── Headless Hub mode (used by backend automation) ───────────────
        // Keeps the named-pipe Hub alive without depending on a tray UI.
        if (args.Contains("--headless-hub") || args.Contains("--hub"))
        {
            RunHub(useTray: false);
            return;
        }

        // ── Tray / Hub mode (double-click, one singleton) ─────────────────
        RunHub(useTray: true);
    }

    static void RunHub(bool useTray)
    {
        ServerState.InitLogFile();
        WireGlobalExceptionLogging();
        ServerLogBuffer.Append("INFO", "App", $"Session log file: {ServerState.LogFilePath}");

        using var mutex = new Mutex(true, "Global\\SolidWorksMcpServer_TrayInstance", out bool createdNew);
        if (!createdNew)
        {
            ServerLogBuffer.Append("WARN", "App", "Tray startup skipped because another hub instance is already running.");
            MessageBox.Show(Strings.AlreadyRunning, Strings.AppTitle,
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        using var cts = new CancellationTokenSource();

        // Shared services: one StaDispatcher + one Bridge connection for ALL sessions.
        var sharedSvc = BuildSharedServices();

        // Hub pipe server: each connecting Proxy gets a full MCP session on its pipe.
        new HubPipeServer(cts.Token, async (pipe, client, ct) =>
        {
            var sessionHost = BuildMcpSessionHost(pipe, sharedSvc);
            try
            {
                await sessionHost.RunAsync(ct);
            }
            catch (OperationCanceledException)
            {
                // Hub shutting down.
            }
            catch (Exception ex)
            {
                ServerLogBuffer.Append("ERROR", "Hub", $"MCP session runner failed for {client.Name}.", ex);
                throw;
            }
        }).Start();

        if (useTray)
        {
            ApplicationConfiguration.Initialize();
            using var tray = new TrayApplicationContext(cts);
            Application.Run(tray);
        }
        else
        {
            ServerLogBuffer.Append("INFO", "App", "Headless Hub service started.");
            using var wait = new ManualResetEventSlim(false);
            Console.CancelKeyPress += (_, e) =>
            {
                e.Cancel = true;
                wait.Set();
            };
            AppDomain.CurrentDomain.ProcessExit += (_, _) => wait.Set();
            wait.Wait();
        }

        // Tray closed → cancel everything.
        cts.Cancel();
        if (sharedSvc is IDisposable d) d.Dispose();
    }

    static void RunDirectStdio()
    {
        ServerState.InitLogFile();
        WireGlobalExceptionLogging();
        ServerLogBuffer.Append("INFO", "App", $"Direct stdio session log file: {ServerState.LogFilePath}");

        var sharedSvc = BuildSharedServices();
        var builder = Host.CreateApplicationBuilder(Array.Empty<string>());
        builder.Logging.ClearProviders();
        builder.Logging.AddProvider(new ErrorFileLoggerProvider(ServerState.LogFilePath));

        builder.Services.AddSingleton(sharedSvc.GetRequiredService<StaDispatcher>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISwConnectionManager>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IDocumentService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISelectionService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISketchService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IFeatureService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IAssemblyService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IAssemblyEntityAnnotationService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IEquationService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IPointCloudExportService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IFeatureDimensionService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IWorkflowService>());

        builder.Services.AddTransient<SolidWorksMcpApp.Tools.ConnectionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.DocumentTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.SelectionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.SketchTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.FeatureTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.AssemblyTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.DemoTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.AssemblyEntityAnnotationTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.EquationTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.FeatureDimensionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.GeometryTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.KnowledgeTools>();

        builder.Services
            .AddMcpServer()
            .WithStdioServerTransport()
            .WithToolsFromAssembly();

        using var host = builder.Build();
        host.Run();

        if (sharedSvc is IDisposable d) d.Dispose();
    }

    static void WireGlobalExceptionLogging()
    {
        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
        {
            if (e.ExceptionObject is Exception ex)
            {
                ServerLogBuffer.Append("FATAL", "App", "Unhandled process exception.", ex);
            }
            else
            {
                ServerLogBuffer.Append("FATAL", "App", $"Unhandled non-exception object: {e.ExceptionObject}");
            }
        };

        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            ServerLogBuffer.Append("ERROR", "App", "Unobserved task exception.", e.Exception);
            e.SetObserved();
        };
    }

    // ── Proxy mode ───────────────────────────────────────────────────────

    static void RunProxy(string[] args)
    {
        var clientName = GetArg(args, "--client") ?? "MCP Client";

        // Connect to Hub; if it is not running yet, auto-start it and retry.
        var pipe = ConnectToHubOrStart();
        if (pipe is null)
        {
            Environment.Exit(1);
            return;
        }

        // Send connect handshake.
        var connectMsg  = JsonSerializer.Serialize(new { type = "connect", clientName, pid = Environment.ProcessId });
        var connectBytes = Encoding.UTF8.GetBytes(connectMsg + "\n");
        pipe.Write(connectBytes);
        pipe.Flush();

        // Wait for "ready" — read synchronously one byte at a time so we
        // don't accidentally buffer the first MCP bytes.
        var readyLine = ReadLineSync(pipe);
        if (readyLine is null || !readyLine.Contains("\"ready\""))
        {
            pipe.Dispose();
            Environment.Exit(1);
            return;
        }

        // Relay: stdin → pipe (MCP requests) and pipe → stdout (MCP responses), concurrently.
        var stdin  = Console.OpenStandardInput();
        var stdout = Console.OpenStandardOutput();
        var t1 = stdin.CopyToAsync(pipe);
        var t2 = pipe.CopyToAsync(stdout);
        Task.WhenAny(t1, t2).GetAwaiter().GetResult();

        pipe.Dispose();
    }

    // ── Shared services (STA + Bridge) — one set per Hub process ─────────

    static IServiceProvider BuildSharedServices()
    {
        var sc = new ServiceCollection();
        sc.AddLogging(b =>
        {
            b.ClearProviders();
            b.AddProvider(new ErrorFileLoggerProvider(ServerState.LogFilePath));
        });

        sc.AddSingleton<StaDispatcher>();

        sc.AddSingleton<ISwConnectionManager>(sp =>
        {
            var sta = sp.GetRequiredService<StaDispatcher>();
            var inner = sta.InvokeAsync(() =>
            {
                var connector = new SwComConnector();
                return (ISwConnectionManager)new SwConnectionManager(connector);
            }).GetAwaiter().GetResult();

            return new ConnectionLoggingSwConnectionManager(
                inner,
                () => sp.GetRequiredService<ISelectionService>());
        });

        sc.AddSingleton<IDocumentService>(sp  => new DocumentService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<ISelectionService>(sp => new SelectionService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<ISketchService>(sp    => new SketchService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IFeatureService>(sp   => new FeatureService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IAssemblyService>(sp  => new AssemblyService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IAssemblyEntityAnnotationService>(sp => new AssemblyEntityAnnotationService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IEquationService>(sp  => new EquationService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IPointCloudExportService>(sp => new PointCloudExportService(sp.GetRequiredService<ISwConnectionManager>()));
        sc.AddSingleton<IFeatureDimensionService>(sp => new FeatureDimensionService(
            sp.GetRequiredService<ISwConnectionManager>(),
            sp.GetRequiredService<IEquationService>()));
        sc.AddSingleton<IWorkflowStageLogger, ServerLogWorkflowStageLogger>();
        sc.AddSingleton<IWorkflowService>(sp  => new WorkflowService(
            sp.GetRequiredService<IDocumentService>(),
            sp.GetRequiredService<IAssemblyService>(),
            sp.GetRequiredService<ISelectionService>(),
            sp.GetRequiredService<ISwConnectionManager>(),
            sp.GetRequiredService<IWorkflowStageLogger>()));

        return sc.BuildServiceProvider();
    }

    // ── Per-session MCP host (one per connected Proxy client) ────────────

    static IHost BuildMcpSessionHost(System.IO.Stream pipeStream, IServiceProvider sharedSvc)
    {
        var builder = Host.CreateApplicationBuilder(Array.Empty<string>());
        builder.Logging.ClearProviders();
        builder.Logging.AddProvider(new ErrorFileLoggerProvider(ServerState.LogFilePath));

        // Re-use the shared singleton instances so all clients share one STA queue and one COM world.
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<StaDispatcher>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISwConnectionManager>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IDocumentService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISelectionService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<ISketchService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IFeatureService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IAssemblyService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IAssemblyEntityAnnotationService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IEquationService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IPointCloudExportService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IFeatureDimensionService>());
        builder.Services.AddSingleton(sharedSvc.GetRequiredService<IWorkflowService>());

        builder.Services.AddTransient<SolidWorksMcpApp.Tools.ConnectionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.DocumentTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.SelectionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.SketchTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.FeatureTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.AssemblyTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.DemoTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.AssemblyEntityAnnotationTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.EquationTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.FeatureDimensionTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.GeometryTools>();
        builder.Services.AddTransient<SolidWorksMcpApp.Tools.KnowledgeTools>();

        builder.Services
            .AddMcpServer()
            .WithStreamServerTransport(pipeStream, pipeStream)   // bidirectional pipe
            .WithToolsFromAssembly();

        return builder.Build();
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    /// <summary>
    /// Reads one \n-terminated line from the stream synchronously, one byte at a time.
    /// Only used during the startup handshake where latency is irrelevant.
    /// </summary>
    static string? ReadLineSync(System.IO.Stream stream)
    {
        var buf = new List<byte>(128);
        var b   = new byte[1];
        while (true)
        {
            int n = stream.Read(b, 0, 1);
            if (n == 0) return null;
            if (b[0] == (byte)'\n') return Encoding.UTF8.GetString(buf.ToArray()).TrimEnd('\r');
            buf.Add(b[0]);
        }
    }

    static string? GetArg(string[] args, string name)
    {
        var idx = Array.IndexOf(args, name);
        return idx >= 0 && idx + 1 < args.Length ? args[idx + 1] : null;
    }

    static NamedPipeClientStream? ConnectToHubOrStart()
    {
        var pipe = TryConnectToHub(800);
        if (pipe is not null) return pipe;

        using var startMutex = new Mutex(false, "Global\\SolidWorksMcpServer_AutoStart");
        bool ownsStartMutex = false;
        try
        {
            ownsStartMutex = startMutex.WaitOne(TimeSpan.FromSeconds(12));

            pipe = TryConnectToHub(500);
            if (pipe is not null) return pipe;

            if (ownsStartMutex)
                StartHubProcess();

            var deadline = DateTime.UtcNow.AddSeconds(12);
            while (DateTime.UtcNow < deadline)
            {
                pipe = TryConnectToHub(1000);
                if (pipe is not null) return pipe;

                Thread.Sleep(250);
            }
        }
        finally
        {
            if (ownsStartMutex)
                startMutex.ReleaseMutex();
        }

        return null;
    }

    static NamedPipeClientStream? TryConnectToHub(int timeoutMs)
    {
        var pipe = new NamedPipeClientStream(".", HubPipeServer.PipeName,
            PipeDirection.InOut, PipeOptions.Asynchronous);
        try
        {
            pipe.Connect(timeoutMs);
            return pipe;
        }
        catch
        {
            pipe.Dispose();
            return null;
        }
    }

    static void StartHubProcess()
    {
        var launch = ResolveCurrentAppLaunch();

        var psi = new ProcessStartInfo
        {
            FileName = launch.FileName,
            UseShellExecute = true,
            WorkingDirectory = launch.WorkingDirectory,
        };
        foreach (var argument in launch.Arguments)
            psi.ArgumentList.Add(argument);

        Process.Start(psi);
    }

    static (string FileName, string WorkingDirectory, string[] Arguments) ResolveCurrentAppLaunch()
    {
        var processPath = Environment.ProcessPath
            ?? throw new InvalidOperationException("Process path is unavailable.");
        var commandLine = Environment.GetCommandLineArgs();

        // When the app is launched as `dotnet SolidWorksMcpApp.dll --proxy`,
        // Environment.ProcessPath points to dotnet.exe. Starting that path alone
        // only launches bare dotnet and the proxy observes "server shut down".
        // Preserve the DLL path and start a stable headless Hub instead.
        if (Path.GetFileName(processPath).Equals("dotnet.exe", StringComparison.OrdinalIgnoreCase)
            && commandLine.Length >= 2
            && commandLine[1].EndsWith(".dll", StringComparison.OrdinalIgnoreCase))
        {
            var dllPath = Path.GetFullPath(commandLine[1]);
            return (
                processPath,
                Path.GetDirectoryName(dllPath) ?? Directory.GetCurrentDirectory(),
                [dllPath, "--headless-hub"]);
        }

        return (
            processPath,
            Path.GetDirectoryName(processPath) ?? Directory.GetCurrentDirectory(),
            ["--headless-hub"]);
    }
}
