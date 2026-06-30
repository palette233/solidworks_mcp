# 演示版本固化与提交前清单

更新时间：2026-06-30

## 当前稳定能力

当前演示版本已验证通过以下闭环：

```text
参考装配体 X_reference_spread
  -> 捕获 layout2d x/y/theta
  -> 新建 assembly
  -> 导入 A/B/C
  -> Common Base
  -> Replay Layout2D
  -> 重新捕获并对比
```

验证结果：

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

## 推荐启动方式

后端推荐使用 direct stdio MCP 链路，避免旧 Hub/proxy 带来的 named pipe 生命周期问题。

PowerShell：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
$env:DEMO_MCP_MODE="bridge"
$env:DEMO_MCP_COMMAND="dotnet"
$env:DEMO_MCP_CWD="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
$env:DEMO_FACE_MAPPING_PATH="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json"
$env:DEMO_MCP_TIMEOUT_SECONDS="420"
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
npm run dev
```

## 推荐演示顺序

```text
Reset
Initialize
Common Base
Capture Layout
Replay Layout
```

## 提交前建议

建议提交：

- `apps/demo-backend/**` 源码和 README。
- `apps/demo-frontend/src/**` 源码和 README。
- `scripts/capture_common_base_layout.py`
- `scripts/apply_captured_common_base_layout.py`
- `scripts/face_mapping_record_probe.py`
- `scripts/face_mapping_verify_select.py`
- `vendor/solidworks-mcp/app/SolidWorksMcpApp/**` 中的 MCP 工具改动。
- `vendor/solidworks-mcp/bridge/SolidWorksBridge/**` 中的 SolidWorks service/math/selection 改动。
- `vendor/solidworks-mcp/bridge/SolidWorksBridge.Tests/**` 中新增或更新的测试代码。
- `docs/**` 中进展、问题、操作日志和本清单。
- `.gitignore`。

不建议提交：

- `demo/*.SLDASM`
- `demo/*.png`
- `demo/demo_state.json`
- `logs/**`
- `apps/demo-frontend/tsconfig.tsbuildinfo`
- 根目录临时文件：`cad_task.md`、`solve_problem.md`、`git`、`python`

可选提交：

- `demo/*.json` 中少量用于说明的 layout 样例。
- 若提交 layout JSON，建议只选择最终样例：
  - `demo/x_reference_layout2d_theta.json`
  - `demo/abc_replay_from_x_reference_theta_signfix_layout2d.json`

## Commit 建议

建议本地先 commit，不立即 push。

推荐 commit message：

```text
Add common-base layout2d theta replay workflow
```

commit 前建议执行：

```powershell
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
```

说明：

- `dotnet test` 当前可能被 Windows 应用控制策略阻止加载测试 DLL，这属于环境限制，不代表新增数学测试断言失败。
