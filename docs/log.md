# 操作记录

## 2026-06-25 - 干净装配体验证 Common Base / Capture / Replay

前置状态：
- 用户已删除旧的 `demo/ABC_arrange_demo.SLDASM`。
- 后端 `/api/health` 指向默认新版 MCP：
```text
mcpCwd=artifacts\solidworks-mcp
faceMappingPath=artifacts\solidworks-mcp\face_mappings.json
```

执行：
1. 调用 `POST /api/demo/reset`。
2. 调用 `POST /api/demo/initialize-common-base`，导入 A/B/C 并保存新的 `demo/ABC_arrange_demo.SLDASM`。
3. 调用 `POST /api/demo/finalize-common-base`。
4. 调用 `POST /api/demo/capture-common-base-layout`。
5. 调用 `POST /api/demo/apply-captured-layout`。

结果：
- `InitializeCommonBaseAssembly` 成功：
  - A/B/C 均 `inserted=true`。
  - 新文件已生成：`demo/ABC_arrange_demo.SLDASM`。
- `FinalizeCommonBaseAssembly` 返回 `bottom face orientation mismatch`：
  - A 作为基准，orientation check 通过。
  - B/C 的 Coincident mate 均创建成功，`bottomMateResult.errorName=swAddMateError_NoError`。
  - B/C 的 `orientationChecks.matchesBase=false`，因此 Common Base 仍未进入 `base ready`。
  - 本次结果表明“重复配合回归”已被代码层规避，当前剩余问题是底面朝向自动修正尚未完成。
- `CaptureCommonBaseLayoutFromAssembly` 成功：
  - 输出文件：`demo/captured_common_base_layout.json`。
  - A/B/C 均采集到 `bottomCenterWorld`、`bottomNormalWorld`、`sourceTransform` 和 `layout2d`。
- `ApplyCapturedCommonBaseLayout` 成功：
  - 输出截图：`demo/apply_captured_layout_result.png`。
  - A/B/C 均 `moveResult.success=true`。
  - B 根据 layout2d 移动约 `dy=-0.005m`。
  - C 根据 layout2d 移动约 `dy=+0.03m`。

补充说明：
- Python/PowerShell 输出中偶尔把“底面”显示为 `久中`，经 `unicode_escape` 检查，`demo_state.json` 中真实码点仍是 `\u5e95\u9762`。
- 这是控制台字符集显示问题，不是 state 或工具参数被写坏。

## 2026-06-25 - 修复 Common Base 重复配合回归

背景：
- 用户反馈 `Initialize` 后 A/B 已导入但默认隐藏，需要在组件树中手动显示。
- 用户执行 `Common Base` 后出现 `bottom face orientation mismatch`，并观察到 A-B、A-C 之间似乎存在重复的“重合”配合。

分析：
- 新增的朝向修正尝试逻辑会执行：
```text
AddMate -> ForceRebuild -> ProbeNormal -> mismatch -> Undo(1)
```
- 真实 SolidWorks 中 `Undo(1)` 可能撤销的是 `ForceRebuild`，而不是刚创建的 mate。
- 结果是每次 alignment 尝试都可能留下一个 Coincident mate，导致重复配合。

本次处理：
- 修改 `DemoTools.cs`。
- 移除通过多次 mate alignment 重试并撤销的逻辑。
- 恢复为每个目标组件只创建一次 Coincident mate。
- 保留配合后的 `orientationChecks`，用于报告 B/C 底面法向是否与 A 一致。
- 如果方向不一致，仍返回明确 mismatch，但不再留下重复配合。

已执行验证：
```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：
- MCP app 构建通过，0 warning，0 error。
- 后端 Python 编译通过。
- 前端构建通过。

发布与运行：
- 已发布修复后的 MCP 到默认目录 `artifacts\solidworks-mcp`。
- 已停止旧 `SolidWorksMcpApp` 和旧后端。
- 已启动默认目录下的新 `SolidWorksMcpApp.exe`。
- 已启动后端，并通过 `/api/health` 确认：
```text
mcpCwd=artifacts\solidworks-mcp
faceMappingPath=artifacts\solidworks-mcp\face_mappings.json
```

尚未执行的真实自测：
- 当前 `demo/ABC_arrange_demo.SLDASM` 可能已经被旧逻辑写入重复配合。
- 为避免误判，下一次真实测试应先使用干净装配体：
  - 关闭并删除旧 `demo/ABC_arrange_demo.SLDASM`；或
  - 在 SolidWorks 中手动删除旧的重复 Coincident mate 后保存。
- 然后再执行 `Initialize -> Common Base -> Capture Layout -> Replay Layout`。

## 2026-06-24 11:31-11:34 - layout2d 回放真实验证

目标：

- 验证新增的 `ApplyCapturedCommonBaseLayout` 是否能读取 `demo/captured_common_base_layout.json`，并根据其中的 `layout2d` 移动当前 SolidWorks 装配体中的 A/B/C。

执行过程：

1. 停止旧 MCP 进程：

```cmd
taskkill /IM SolidWorksMcpApp.exe /F
```

结果：

- 成功停止两个旧的 `SolidWorksMcpApp.exe` 进程。

2. 启动新版 MCP：

```cmd
Start-Process -FilePath "D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp-20260624-112354\SolidWorksMcpApp.exe" -WorkingDirectory "D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp-20260624-112354" -WindowStyle Hidden
```

结果：

- 新版 MCP 从 `artifacts\solidworks-mcp-20260624-112354` 启动成功。

3. 首次执行 layout2d 回放：

```cmd
python scripts\apply_captured_common_base_layout.py --layout demo\captured_common_base_layout.json --assembly demo\ABC_arrange_demo.SLDASM --mcp-cwd artifacts\solidworks-mcp-20260624-112354 --screenshot demo\apply_captured_layout_result.png
```

结果：

- MCP 工具返回通用错误。
- 查看日志后发现原因是脚本把相对路径传给 MCP，MCP 在发布目录下查找 `demo\captured_common_base_layout.json`，导致文件找不到。

修复：

- 修改 `scripts/apply_captured_common_base_layout.py`，将 `--layout`、`--assembly`、`--screenshot` 转换为绝对路径后再传给 MCP。
- 执行 `python -m py_compile scripts\apply_captured_common_base_layout.py`，语法检查通过。

4. 重新启动新版 MCP 并再次执行回放命令。

结果：

- 工具返回：

```text
ApplyCapturedCommonBaseLayout completed.
```

- A/B/C 三个组件均返回 `moveResult.success=true`。
- B 根据 captured layout2d 被移动约：

```text
deltaY = -0.01000000000000002 m
```

- C 的移动量接近 0，说明其当前底面中心已基本在 captured layout2d 对应位置。
- 输出截图已生成：

```text
demo\apply_captured_layout_result.png
```

截图文件大小：

```text
219521 bytes
```

结论：

- 第一版“根据 captured layout2d 移动复原”的真实 SolidWorks 验证已通过。
- 当前功能已经可以完成：读取 captured layout JSON -> 计算目标底面中心 -> 调用 MoveComponent 移动组件。

备注：

- 结果中 `bottomFaceName` 的中文显示为 `久中`，属于中文编码/显示问题，但本次工具调用仍能成功选面和移动。后续可统一处理中文 face name 的显示与状态编码。

## 2026-06-24 - 前端接入 layout2d 回放能力

目标：

- 将已经验证通过的 `ApplyCapturedCommonBaseLayout` 能力接入 demo 前端。
- 尽量不影响现有 `Initialize`、`Common Base`、`Arrange` 流程。

代码修改：

1. 后端新增 MCP 工具名常量：

```text
apps/demo-backend/src/demo_backend/mcp_tools.py
APPLY_CAPTURED_COMMON_BASE_LAYOUT_TOOL = "apply_captured_common_base_layout"
```

2. 后端新增服务方法：

```text
DemoService.apply_captured_layout()
DemoService._apply_captured_layout_plan()
```

作用：

- 读取当前 `demo_state.json` 中保存的 `assemblyPath`。
- 使用固定布局文件 `demo/captured_common_base_layout.json`。
- 调用 MCP 工具 `apply_captured_common_base_layout`。
- 输出截图到 `demo/apply_captured_layout_result.png`。

3. 后端新增 API：

```text
POST /api/demo/apply-captured-layout
```

4. 后端截图接口调整：

```text
GET /api/demo/screenshot
```

现在会优先读取最近一次工具返回的 `lastRun.screenshotPath`，因此 `Replay Layout` 生成的截图也能在前端结果区展示。

5. 前端新增 API 函数：

```text
applyCapturedLayout()
```

6. 前端工具栏新增按钮：

```text
Replay Layout
```

该按钮会调用 `/api/demo/apply-captured-layout`，用于把 captured layout2d 回放到当前 SolidWorks 装配体。

验证：

```cmd
python -m compileall apps\demo-backend\src scripts\apply_captured_common_base_layout.py
```

结果：

- 后端 Python 编译通过。

```cmd
cmd /c npm.cmd run build
```

结果：

- 前端 TypeScript/Vite 构建通过。

备注：

- 直接在 PowerShell 中运行 `npm run build` 会被本机执行策略拦截，因为 PowerShell 尝试加载 `npm.ps1`。
- 使用 `cmd /c npm.cmd run build` 可以绕过该问题。
- 本次修改只完成前端/后端接入与构建验证，没有再次真实点击前端按钮触发 SolidWorks 移动；真实移动能力此前已经通过脚本完成验证。

## 2026-06-24 - 创建原始装配体对照组 X_reference

目标：

- 为后续 demo 准备一个“原始装配体 / 对照组”文件。
- 先完成新建 assembly、导入 A/B/C、保存为 `demo/X_reference.SLDASM`。
- 暂不记录底面；到需要人工选择真实底面时再提醒用户操作。

执行方式：

- 通过 `McpToolRunner` 调用 MCP 工具：

```text
initialize_common_base_assembly
```

核心参数：

```text
outputAssemblyPath = demo/X_reference.SLDASM
A filePath = demo/testdata/A.SLDASM
B filePath = demo/testdata/B.SLDASM
C filePath = demo/testdata/C.SLDASM
screenshotPath = demo/X_reference_initial.png
```

执行结果：

- MCP 返回 `success=true`。
- A/B/C 三个子装配体均 `inserted=true`。
- 装配体已保存：

```text
demo/X_reference.SLDASM
```

- 初始截图已生成：

```text
demo/X_reference_initial.png
```

备注：

- 本次只是创建对照组文件的初始版本。
- 下一步需要用户在 SolidWorks 中逐个选择 A/B/C 的真实底面，然后运行记录/验证脚本。
- 记录完底面后，才适合继续执行共底面、手动调整位置、保存为正式对照组 X。

## 2026-06-24 - A 底面记录前的活动文档检查

目标：

- 用户已在 SolidWorks 中选中 A 的底面，准备记录为 `A-1:底面`。

执行情况：

1. 首次调用记录脚本时误传了脚本暂不支持的 `--mcp-cwd` 参数，因此没有执行 MCP 记录。
2. 使用默认 MCP 目录再次调用后，MCP 日志显示：

```text
No active document. Open or create a document first.
```

结论：

- 当时 MCP 连接到的 SolidWorks 会话没有活动文档，因此无法读取用户选择的面。
- 该次没有成功记录 A 底面。

处理：

- 改用创建 `X_reference.SLDASM` 时使用的 MCP 目录：

```text
artifacts/solidworks-mcp-20260624-112354
```

- 查询活动文档返回 `null`。
- 随后调用 `open_document` 打开：

```text
demo/X_reference.SLDASM
```

结果：

- `X_reference.SLDASM` 已成功打开为 SolidWorks assembly。
- 由于重新打开文档会清空此前选择，下一步需要用户重新选中 A 的真实底面后再记录。

## 2026-06-24 - A 底面重新记录仍失败，定位为多个 SolidWorks 实例问题

目标：

- 用户重新选中 A 的底面后，再次尝试记录 `A-1:底面`。

执行：

- 使用创建 `X_reference.SLDASM` 时同一版 MCP：

```text
artifacts/solidworks-mcp-20260624-112354
```

- 调用：

```text
record_face_mapping
get_selected_face_mapping_probe
select_face_by_name
get_selected_face_mapping_probe
```

结果：

- `record_face_mapping` 返回失败：

```text
No active document. Open or create a document first.
```

- `get_selected_face_mapping_probe` 同样返回无活动文档。

进一步检查：

- 本机当前存在多个 `SLDWORKS.exe` 进程。
- MCP 连接到的 SolidWorks 实例没有活动文档，而用户选面的 SolidWorks UI 很可能属于另一个实例。

结论：

- 这不是选面本身失败，而是 MCP 与用户正在操作的 SolidWorks 实例不一致。
- 需要先收敛到一个 SolidWorks 实例，再重新打开 `X_reference.SLDASM`、重新选择 A 底面并记录。

## 2026-06-24 - A 底面第三次记录尝试仍未成功

目标：

- 用户再次重新选中 A 的底面后，尝试记录 `A-1:底面`。

本次改进：

- 改用 Python 直接构造 UTF-8 JSON 调用 `McpToolRunner`，避免 PowerShell 将中文 `底面` 编码成 `??`。

执行工具顺序：

```text
get_active_document
record_face_mapping
get_selected_face_mapping_probe
select_face_by_name
get_selected_face_mapping_probe
```

结果：

- `get_active_document` 返回：

```text
null
```

- `record_face_mapping` 仍返回：

```text
No active document. Open or create a document first.
```

结论：

- 即使绕开 PowerShell 编码问题，MCP 仍然看不到活动 SolidWorks 文档。
- 当前阻塞点仍是 MCP 连接的 SolidWorks 实例与用户正在操作/选面的 SolidWorks 实例不一致，或 MCP 连接到的实例没有活动模型文档。

## 2026-06-24 13:22 CST - 尝试强制关闭 SolidWorks 残留进程失败

目标：

- 用户确认执行后，尝试强制关闭所有残留 `SLDWORKS.exe` 进程，以便重新建立干净的单实例 SolidWorks 会话。

执行命令：

```cmd
taskkill /IM SLDWORKS.exe /F
```

结果：

- 系统返回 `Access is denied`。
- 以下进程仍然存在：

```text
62596
87920
100640
101952
106564
106876
111136
114044
```

结论：

- 当前 Codex 进程权限不足以结束这些 SolidWorks 进程。
- 需要用户通过任务管理器以管理员权限结束，或在管理员 CMD/PowerShell 中执行同一条命令。

## 2026-06-24 13:31-13:36 CST - 尝试用常驻 MCP Hub 记录 A 底面仍未成功

背景：

- 用户关闭残留 SolidWorks 后，重新打开了干净状态。
- 通过 MCP 打开 `demo/X_reference.SLDASM` 时，`get_active_document` 曾返回正确的 `X_reference`。
- 用户随后重新选中 A 的底面。

尝试 1：

- 使用短连接 `McpToolRunner` 调用：

```text
get_active_document
record_face_mapping
get_selected_face_mapping_probe
select_face_by_name
get_selected_face_mapping_probe
```

结果：

```text
get_active_document = null
record_face_mapping = No active document. Open or create a document first.
```

分析：

- 短连接 MCP 仍不能稳定复用用户当前选面的 SolidWorks 活动会话。

尝试 2：

- 启动常驻 `SolidWorksMcpApp.exe`，希望后续记录通过同一个 Hub 连接。
- 常驻 Hub 启动成功：

```text
Hub pipe server starting on 'SolidWorksMcpHub'
```

- 但继续用 `McpToolRunner --proxy` 时，proxy 与常驻 Hub 冲突，返回：

```text
The server shut down unexpectedly.
```

尝试 3：

- 改用后端 `pipe` 模式直接连接常驻 Hub。
- 第一次沙箱内访问 pipe 被拒绝。
- 提升权限后可以连接到 Hub，日志显示：

```text
Hub handshake received
Hub ready sent
Starting MCP session
```

- 但工具调用没有返回，最终超时。

当前状态：

- 常驻 MCP 进程存在。
- 又出现了 3 个 `SLDWORKS.exe` 进程。
- 面记录仍未成功。

结论：

- 当前阻塞已经不是单纯“用户没选中面”，而是 SolidWorks COM 会话/MCP Hub/短连接 runner 之间的会话稳定性问题。
- 继续在当前混乱会话里反复记录，成功率较低。

建议：

- 彻底关闭 SolidWorks 和 `SolidWorksMcpApp.exe`。
- 从一个明确的流程重新开始：
  1. 启动常驻 MCP。
  2. 通过常驻 MCP 打开 `X_reference.SLDASM`。
  3. 确认 `get_active_document` 返回 `X_reference`。
  4. 用户在同一 SolidWorks 窗口中选面。
  5. 通过同一个常驻 MCP/pipe 记录。
- 后续应新增一个专门的 face recording helper，避免混用 short-lived proxy 和 persistent hub。

## 2026-06-24 13:38-13:42 CST - 清理后重新打开 X_reference 的结果

背景：

- 用户确认已完成：
  1. 关闭所有 SolidWorks；
  2. 关闭 `SolidWorksMcpApp.exe`。

检查：

- 未发现残留 `SLDWORKS.exe` 或 `SolidWorksMcpApp.exe`。
- `demo/X_reference.SLDASM` 存在。
- 新版 MCP 可执行文件存在。

执行：

- 启动常驻 MCP Hub 成功：

```text
Hub pipe server starting on 'SolidWorksMcpHub'
```

- 但直接 pipe 方式仍不稳定。
- 随后停止坏状态 MCP Hub，改用 proxy 自动启动方式打开：

```text
demo/X_reference.SLDASM
```

结果：

- `open_document` 成功。
- 同一 MCP 会话内 `get_active_document` 返回：

```text
Path = D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\X_reference.SLDASM
Title = X_reference
Type = 2
```

- 当前只剩一个 `SLDWORKS.exe` 进程。

后续验证：

- 再次开启新的短连接 MCP 会话查询：

```text
get_active_document = null
list_documents = []
```

结论：

- MCP 可以在“打开文档的同一会话内”看到 `X_reference`。
- 但该短连接 MCP 会话结束后，下一次会话仍不能稳定继承已打开文档状态。
- 当前能自动完成的步骤已完成；后续需要用户在唯一的 SolidWorks UI 会话中手动打开 `X_reference.SLDASM` 并选中 A 的真实底面，再尝试记录。

建议：

- 不再通过短连接 MCP 打开后马上让用户选面。
- 用户应在当前唯一 SolidWorks UI 中手动打开：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\X_reference.SLDASM
```

- 然后选中 `A-1` 底面，再执行记录。

## 2026-06-24 13:50 CST - 手动打开 UI 后记录 A 底面仍失败

背景：

- 用户确认已经在 SolidWorks UI 中打开 `X_reference.SLDASM`，并选中 `A-1` 的真实底面。

执行：

- 使用 Python 直接构造 UTF-8 JSON，调用：

```text
get_active_document
record_face_mapping(A-1, 底面)
get_selected_face_mapping_probe
select_face_by_name(A-1, 底面)
get_selected_face_mapping_probe
```

结果：

- `get_active_document` 返回：

```text
null
```

- `record_face_mapping` 返回：

```text
No active document. Open or create a document first.
```

进一步检查：

- 当前又出现多个 `SLDWORKS.exe` 进程。
- 进程数量为 5 个。
- MCP 仍连接到了没有活动文档的 SolidWorks 实例。

结论：

- 这次仍未成功记录 A 底面。
- 主要阻塞仍是 SolidWorks 多实例/COM 会话不一致，而不是用户选面动作本身。

建议：

- 后续不要继续依赖当前手动选面 + 短连接 MCP 的方式。
- 更稳妥的工程改法是新增一个“一次性记录向导/常驻记录模式”，或者新增“连接指定活动 SolidWorks 实例/显示当前 MCP 连接实例”的诊断工具。

## 2026-06-24 14:05 CST - 使用既有 layout2d 样本准备演示环境

背景：

- 为了下午演示优先跑通“根据已捕获 layout2d 复原位置”的主链路，暂时暂停重新制作 `X_reference` 和重新记录底面。
- 改用此前已经验证过的 `demo/captured_common_base_layout.json` 作为演示样本。

已执行检查：

- 确认 `demo/captured_common_base_layout.json` 存在。
- 确认 `demo/testdata/A.SLDASM`、`B.SLDASM`、`C.SLDASM` 存在。
- 确认新版 MCP 发布目录 `artifacts/solidworks-mcp-20260624-112354` 中存在 `SolidWorksMcpApp.exe` 和 `face_mappings.json`。

已启动服务：

- 已启动 MCP：`artifacts/solidworks-mcp-20260624-112354/SolidWorksMcpApp.exe`。
- 已启动后端：`http://127.0.0.1:8000`。
- 已启动前端：`http://127.0.0.1:5173`。
- 后端健康检查返回 OK，且当前配置指向：
  - `mcpMode=bridge`
  - `mcpCwd=artifacts/solidworks-mcp-20260624-112354`
  - `faceMappingPath=artifacts/solidworks-mcp-20260624-112354/face_mappings.json`

注意：

- 当前系统里仍检测到多个 `SLDWORKS.exe` 进程。
- 演示时如果前端 MCP 操作出现 SolidWorks 活动文档异常，优先使用此前已验证通过的 `Replay Layout` 样本与截图结果进行展示，不再现场继续排查多实例问题。

## 2026-06-25  - 修复 Common Base 底面朝向一致性：代码级实现

目标：

- 解决 `Common Base` 阶段“底面已共面，但 B/C 的底面朝向可能与 A 不一致”的核心遗留问题。

本次修改：

- 修改 `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/DemoTools.cs`。
- `FinalizeCommonBaseAssembly` 现在会先读取第一个组件底面的世界法向作为基准。
- 对其他组件创建 Coincident mate 时，会依次尝试 `Closest`、`AntiAligned`、`None` 三种 alignment。
- 每次 mate 成功后立即 rebuild 并重新读取目标底面法向。
- 如果法向不一致，则调用 `Undo(1)` 撤销刚创建的 mate，再尝试下一种 alignment。
- 如果所有 alignment 都无法得到一致法向，则返回 `BottomFaceOrientationMismatch`，避免误报成功。

验证：

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

结果：

- 构建通过。
- 0 warning，0 error。

备注：

- 本次完成的是代码级修复。
- 已尝试发布到 `artifacts/solidworks-mcp-20260625-orientation`，但目标 exe 正被占用，发布脚本自动改用：

```text
artifacts\solidworks-mcp-20260625-161303
```

- 已把 `artifacts\solidworks-mcp\face_mappings.json` 复制到新发布目录。
- 仍需重启新版 MCP 后，在真实 SolidWorks 中验证 `Common Base` 是否不再出现 orientation mismatch。

## 2026-06-25 - 小面 normal fallback 与 Capture Layout 产品化

目标：

- 增强小面记录鲁棒性，减少 `normal=null`。
- 将 Transform2/Layout2D 从脚本能力推进到前端可操作流程。

代码修改：

- `SelectionService.TryGetPlanarFaceNormal()`：
  - 优先使用 `PlaneParams`；
  - 失败后尝试读取 tessellated normals；
  - 再失败则从 tessellated triangle points 拟合平面法向。
- 新增 `SelectionServiceFaceNormalTests`，测试 tessellation 点数据拟合 normal。
- 后端新增 `/api/demo/capture-common-base-layout`。
- `DemoService` 新增 `capture_common_base_layout()`。
- 前端新增 `Capture Layout` 按钮。

验证命令：

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter FullyQualifiedName~SelectionServiceFaceNormalTests
python -m compileall apps\demo-backend\src scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
cmd /c npm.cmd run build
```

验证结果：

- MCP app 构建通过，0 warning，0 error。
- 新增 normal fallback 单元测试通过 3/3。
- 后端 Python 编译通过。
- 前端构建通过。
- 测试项目存在若干既有 nullable warning，不来自本次新增测试。

发布：

- 目标目录 `artifacts\solidworks-mcp-20260625-smallface-layout` 被占用回避逻辑改写为：

```text
artifacts\solidworks-mcp-20260625-163843
```

- 已复制 `face_mappings.json` 到新发布目录。

待真实验证：

- 使用新版 MCP 验证真实小面是否不再出现 `normal=null`。
- 使用前端 `Capture Layout` 更新 `demo/captured_common_base_layout.json`。
- 使用前端 `Replay Layout` 验证按新捕获 layout2d 回放。
- 同时验证 Common Base 底面朝向一致性修复。

## 2026-06-25 - 已切换到新版 MCP 并重启后端

用户确认：

- SolidWorks 文件已保存，可以停止旧 MCP 并启动新版。

执行：

- 停止旧 `SolidWorksMcpApp.exe` 进程。
- 启动新版 MCP：

```text
artifacts\solidworks-mcp-20260625-163843\SolidWorksMcpApp.exe
```

- 重启后端，并设置：

```text
DEMO_MCP_MODE=bridge
DEMO_LLM_MODE=dry-run
DEMO_MCP_COMMAND=SolidWorksMcpApp.exe
DEMO_MCP_CWD=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp-20260625-163843
DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp-20260625-163843\face_mappings.json
```

验证：

- 当前只有一个 `SolidWorksMcpApp` 进程，路径为 `artifacts\solidworks-mcp-20260625-163843`。
- 后端 `http://127.0.0.1:8000/api/health` 返回 OK，且 `mcpCwd` 和 `faceMappingPath` 均指向新版目录。
- 前端 `http://127.0.0.1:5173` 仍在监听。

注意：

- 当前仍存在多个 `SLDWORKS.exe` 进程。MCP 已成功切换，但如果后续测试涉及“读取用户手动选择的面”，仍可能受到 SolidWorks 多实例 COM 连接不一致影响。

## 2026-06-25 - Common Base 底面朝向自动修正第一版实现与真实验证

目标：

- 在 `FinalizeCommonBaseAssembly` 阶段，尽量自动修正 B/C 等目标组件的底面法向，使其与基准组件 A 的底面法向一致。
- 避免此前通过反复创建/撤销 mate alignment 导致重复“重合”配合的回归。

本次实现：

- 新增 `DemoBottomOrientationCorrection` 结果结构，用于返回每个组件的修正尝试、旋转轴、旋转角、旋转前后 probe、回滚结果和提示信息。
- 新增 `CommonBaseLayoutMath.CalculateNormalAlignmentRotation()`，根据两个 normal 计算显式旋转轴和角度。
- `FinalizeCommonBaseAssembly` 的新流程为：
  - 先读取第一个组件的底面 `worldNormal` 作为基准；
  - 对后续组件先尝试显式旋转，使目标底面 normal 与基准 normal 对齐；
  - 旋转后重新选中/探测记录的底面；
  - 如果探测失败或方向仍不一致，尝试相反角度；
  - 两次都失败时回滚旋转，不把组件留在错误尝试姿态；
  - 再进入原有的单次 Coincident mate 共面流程；
  - 最后统一返回 `orientationCorrections` 和 `orientationChecks`。
- 增加 `NormalizeComponentLayout()`，把直接 MCP runner 场景中被编码成 `??` 的底面名兜底恢复为 `底面`，避免命令行测试误判为缺少面映射。

本地验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过。
- `CommonBaseLayoutMathTests` 与 `SelectionServiceFaceNormalTests` 通过，合计 9/9。
- 后端 Python 编译通过。
- 前端构建通过。

发布与真实验证：

- 已发布并启动新版 MCP：`artifacts\solidworks-mcp`。
- 使用直接 MCP runner 创建 `demo/ABC_orientation_test_v3.SLDASM` 并调用：
  - `InitializeCommonBaseAssembly`：成功，A/B/C 均插入。
  - `FinalizeCommonBaseAssembly`：仍返回失败，消息为 `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`

真实验证发现：

- B 的显式旋转修正被触发，但旋转后重新探测底面时出现 `worldNormal=null` / `localNormal=null`，提示 `Selected face has no valid planar normal.`，因此修正无法确认成功，最终回滚。
- C 在 mate 前的 probe 显示 normal 与 A 一致，但 Coincident mate 后最终 `orientationChecks` 又变为 mismatch，说明 SolidWorks 的 mate 求解仍可能改变目标组件朝向。
- mate 创建本身没有再次出现重复创建/撤销导致的明显回归，`bottomMateResult.errorName` 为 `swAddMateError_NoError`。

结论：

- 代码层面的第一版“显式旋转 + 失败回滚 + 结果可观测”已完成。
- 真实 SolidWorks 验证表明该版本还没有完全解决 Common Base 底面朝向一致性。
- 下一步应把修正策略调整为“mate 后二次修正/验证”，并增强旋转后面映射重新识别与 normal fallback。

## 2026-06-26 - Common Base 二阶段 PostMate 朝向修正接入

目标：

- 落实上一轮结论：先让 SolidWorks 建立一次底面共面 mate，再在 mate 后做 orientation check 和显式旋转修正。
- 避免 mate 前修正后又被 Coincident mate 求解改变朝向的问题。

本次修改：

- 修改 `FinalizeCommonBaseAssembly` 的内部流程：
  - 打开目标 assembly；
  - 准备组件和面映射；
  - 先调用 `MateBottomFacesToFirstComponent()` 做一次共面 mate；
  - `ForceRebuild`；
  - 再调用 `CorrectBottomFaceOrientations(..., stage: "PostMate")` 做 mate 后法向修正；
  - 再次 `ForceRebuild`；
  - 最后调用 `ProbeBottomFaceOrientations()` 生成最终 `orientationChecks`。
- 不再在 mate 前默认旋转组件。
- `DemoBottomOrientationCorrection` 新增 `Stage` 字段，后续日志可以区分修正发生在 `PostMate` 阶段。
- 保留失败回滚策略：如果显式旋转无法确认成功，会回滚组件，避免把失败姿态残留在装配体中。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过，0 warning，0 error。
- normal/math 与小面 normal fallback 测试通过：9/9。
- 后端 Python 编译通过。
- 前端构建通过。

待真实验证：

- 需要发布新版 MCP，并在真实 SolidWorks 中重新执行 `Initialize -> Common Base`。
- 重点观察：
  - 是否仍出现 `bottom face orientation mismatch`；
  - `orientationCorrections[*].stage` 是否为 `PostMate`；
  - B/C 的 `orientationChecks` 是否最终与 A 匹配；
  - 是否仍存在重复 Coincident mate 或隐藏组件回归。

## 2026-06-26 - 发布并重启 PostMate 新版 MCP

执行：

```cmd
powershell -ExecutionPolicy Bypass -File .\scripts\publish_solidworks_mcp.ps1 -OutputDir artifacts\solidworks-mcp-20260626-postmate
```

结果：

- 发布脚本实际输出到默认目录：

```text
artifacts\solidworks-mcp
```

- 新版 `SolidWorksMcpApp.exe` 时间戳为 `2026-06-26 14:47:47`。
- 已启动新版 MCP：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\SolidWorksMcpApp.exe
```

- 当前运行进程：

```text
Id=116080
Path=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\SolidWorksMcpApp.exe
```

- 最新日志显示 Hub pipe server 已启动在：

```text
SolidWorksMcpHub
```

下一步：

- 重启或确认后端指向 `artifacts\solidworks-mcp`。
- 执行真实 SolidWorks 验证：`Initialize -> Common Base`，重点检查 `orientationCorrections[*].stage=PostMate` 与最终 `orientationChecks`。

## 2026-06-26 - 后端已重启并指向 PostMate 新版 MCP

执行过程：

- 常规 `Start-Process` / CMD 后台启动方式在当前工具会话中未能保活 `uvicorn`。
- 新增临时启动脚本：

```text
.tmp/run_demo_backend_postmate.py
```

- 使用 `pythonw.exe` 启动该脚本，让后端独立后台运行。

当前结果：

- 后端进程：

```text
ProcessName=pythonw
Id=125620
```

- `http://127.0.0.1:8000/api/health` 返回 OK。
- 后端配置确认：

```text
mcpMode=bridge
llmMode=dry-run
mcpCwd=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp
faceMappingPath=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

说明：

- 当前后端已经连接到新版 MCP 发布目录。
- 下一步可以通过前端或接口测试 `Initialize -> Common Base`，重点观察 `orientationCorrections[*].stage=PostMate`。

## 2026-06-26 - Common Base Timeout 排查与安全回退

现象：

- 前端点击 `Common Base` 后显示：

```text
MCP execution failed: TimeoutError:
```

- 后端 HTTP 日志显示 `/api/demo/finalize-common-base` 返回了 `200 OK`，但 `demo_state.json` 中 `lastRun.status=error`。
- MCP 日志中 `FinalizeCommonBaseAssembly started` 之后没有 `completed` 记录，说明工具内部未返回。

分析：

- 后端 MCP client 默认超时时间为 180 秒。
- `FinalizeCommonBaseAssembly` 从 15:14:22 开始后超过 180 秒未返回，因此后端包装为 `TimeoutError`。
- 当前最可疑位置是新接入的 `PostMate` 二阶段修正：
  - 先创建 Coincident mate；
  - 再尝试对已经被 mate 约束的组件执行 `RotateComponent`；
  - SolidWorks 约束求解器可能进入长时间求解或等待，导致 MCP 工具不返回。

处理：

- 为 `FinalizeCommonBaseAssembly` 增加实验开关：

```text
enablePostMateOrientationCorrection=false
```

- 默认关闭 mate 后旋转修正。
- 默认流程现在为：
  - 建立一次底面 Coincident mate；
  - rebuild；
  - 读取 `orientationChecks`；
  - 如方向不一致，返回明确的 mismatch，但不再默认旋转已配合组件。
- 这样优先恢复 `Common Base` 的可返回性，避免前端 timeout。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过，0 warning，0 error。
- 后端编译通过。
- 前端构建通过。

重启：

- 已停止旧 MCP 与后端进程。
- 已重新发布到：

```text
artifacts\solidworks-mcp
```

- 已启动新版 MCP：

```text
ProcessName=SolidWorksMcpApp
Id=103076
```

- 已启动后端：

```text
ProcessName=pythonw
Id=93848
```

- `http://127.0.0.1:8000/api/health` 返回 OK，且后端指向 `artifacts\solidworks-mcp`。

下一步：

- 重新点击 `Common Base`。
- 预期不再 timeout。
- 如果底面朝向仍不一致，前端应快速返回 `bottom face orientation mismatch`，而不是卡住。

## 2026-06-26 - 方案 3：PreMate Transform2 朝向预修正

目标：

- 实现自动朝向修正，但避免在已建立 Coincident mate 的强约束状态下旋转组件。
- 采用“先用 Transform2 摆正姿态，再建立 mate”的流程。

本次修改：

- `FinalizeCommonBaseAssembly` 新增参数：

```text
enablePreMateOrientationCorrection=true
```

- 默认启用 mate 前 Transform2 朝向预修正。
- `enablePostMateOrientationCorrection` 保持默认 `false`。
- 新默认流程：
  1. 根据已记录底面映射自动 probe A/B/C 底面 normal；
  2. 以 A 的底面 `worldNormal` 为基准；
  3. 对 B/C 在 mate 前调用 Transform2 旋转修正；
  4. 修正后自动重新 probe 底面 normal；
  5. 若修正确认失败则回滚该组件姿态；
  6. 然后执行单次 Coincident mate；
  7. 最后做 `orientationChecks`。
- `orientationCorrections[*].stage` 预期为：

```text
PreMateTransform2
```

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过，0 warning，0 error。
- normal/math 与小面 normal fallback 测试通过：9/9。
- 后端编译通过。
- 前端构建通过。

待真实验证：

- 需要重新发布并重启 MCP/后端后测试 `Initialize -> Common Base`。
- 重点观察：
  - 是否不再 timeout；
  - `orientationCorrections[*].stage` 是否为 `PreMateTransform2`；
  - B/C 的最终 `orientationChecks` 是否匹配 A；
  - 如果 B 仍出现旋转后 `normal=null`，则下一步需要做候选面扫描 fallback。

运行环境问题：

- 发布后的单文件：

```text
artifacts\solidworks-mcp\SolidWorksMcpApp.exe
```

被 Windows Device Guard 阻止运行。
- 改用构建输出 DLL：

```text
vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\SolidWorksMcpApp.dll
```

前台运行可以启动 Hub，但从当前工具环境后台启动不能稳定保活。
- 后端启动脚本 `.tmp/run_demo_backend_postmate.py` 已改为使用：

```text
DEMO_MCP_COMMAND=dotnet
DEMO_MCP_ARGS=<SolidWorksMcpApp.dll> --proxy --client DemoBackendArrange
```

- 真实测试前需要确保 MCP Hub 已经手动或可靠地运行起来。

## 2026-06-29 MCP 直连稳定化与 X_reference 制作验证

本次目标：

- 排查“移动/旋转/保存/捕获 layout2d”链路不稳定的原因。
- 优先修复影响自动化执行的 MCP 连接问题。
- 继续完成 `X_reference` 制作和 layout2d 捕获。

主要发现：

- 最大问题不在 CAD 操作计划，而在 MCP Hub/proxy 链路。
- DLL 启动模式下，`dotnet SolidWorksMcpApp.dll --proxy` 的 `Environment.ProcessPath` 指向 `dotnet.exe`。
- 旧逻辑自动拉起 Hub 时可能只启动裸 `dotnet`，导致：

```text
System.IO.IOException: The server shut down unexpectedly.
```

完成修改：

- `SolidWorksMcpApp` 增加 `--stdio-direct`，后端可以直接通过 stdio 调用 MCP 工具。
- `SolidWorksMcpApp` 增加 `--headless-hub`，保留无托盘 Hub 作为备选。
- 修复 DLL 模式下 proxy 自动启动 Hub 的逻辑。
- 后端默认 MCP 参数在 DLL 场景下优先使用 `--stdio-direct`。
- `McpToolRunner` 增加 stdin BOM 容错，方便 PowerShell 临时调试。

验证命令与结果：

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet build apps\demo-backend\tools\McpToolRunner\McpToolRunner.csproj -c Release
python -m compileall apps\demo-backend\src
```

结果均通过。

通过 direct stdio MCP 完成：

1. 打开 `demo\ABC_arrange_demo.SLDASM`。
2. 移动 B-1 / C-1。
3. 绕共同底面法向旋转 B-1 / C-1。
4. 保存为 `demo\X_reference.SLDASM`。
5. 捕获 `demo\x_reference_layout2d.json`。
6. 导出 `demo\x_reference_result.png`。

生成文件：

```text
demo\X_reference.SLDASM
demo\x_reference_layout2d.json
demo\x_reference_result.png
```

结论：

- 当前自动化链路建议优先使用 direct stdio，不再依赖 Hub/proxy。
- 本次绕共同底面法向旋转验证通过，layout2d 中 B/C 的 `sourceTransform` 已包含旋转信息。
- 旋转操作仍有约束求解风险，后续真实复杂装配体中仍应避免在强约束状态下做任意轴旋转。

## 2026-06-29 X_reference_spread 制作与 layout2d 重新捕获

目标：

- 在保持底面共面的前提下，让 B/C 相对 A 产生更明显的位置差异。
- 重新生成可用于后续 Replay Layout 的布局数据。

执行：

- 由于共同底面法向接近全局 `Y`，本次只沿 `X/Z` 平面移动：
  - B-1：`deltaX=0.12, deltaY=0, deltaZ=0`
  - C-1：`deltaX=-0.10, deltaY=0, deltaZ=0.06`
- 原 `X_reference.SLDASM` 处于已打开/共享状态，直接保存失败：

```text
swReadOnlySaveError
```

- 改为另存：

```text
demo\X_reference_spread.SLDASM
```

中途问题：

- 第一次捕获失败是因为 PowerShell 中文参数 `底面` 进入 MCP 后变成 `??`。
- 改用 Python 生成 JSON，并用 `\u5e95\u9762` 传参后解决。
- 第二次捕获时发现 B/C 的 `sourceTransform` 已变化，但 `layout2d` 没变。
- 原因是 `GetSelectedFaceMappingProbe` 将 `IFace2.GetBox()` 中心误当成 world center。

修复：

- `SelectionService.GetSelectedFaceMappingProbe` 改为使用 `IComponent2.GetTotalTransform(true)` 将 leaf/local center 转成 assembly world center。
- `SelectionService.RecordFaceMapping` 同步保存更清晰的 leaf-local center。

验证：

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
- 重新捕获成功：

```text
demo\x_reference_layout2d.json
```

- 重新截图成功：

```text
demo\x_reference_spread_result.png
```

关键结果：

```text
A-1: layout2d=(0, 0)
B-1: layout2d=(0.552681, 0.180535)
C-1: layout2d=(0.258654, 0.144401)
```

共面检查：

- A/B/C 的 `bottomCenterWorld.Y` 都约为 `-0.499264`。
- A/B/C 的 `bottomNormalWorld` 都接近 `[0, -1, 0]`。

结论：

- 已获得更明显差异的参考装配体 `demo\X_reference_spread.SLDASM`。
- 已获得对应 layout2d `demo\x_reference_layout2d.json`。
- 下一步可以进入“新建空白 assembly -> 导入 A/B/C -> Common Base -> Replay Layout -> 对比 X_reference_spread”的闭环测试。

## 2026-06-29 新 Assembly 闭环 Replay Layout 测试

目标：

- 新建空白装配体。
- 导入 A/B/C。
- 执行 Common Base。
- Replay `demo\x_reference_layout2d.json`。
- 再次捕获 replay 后的 layout2d，对比 `X_reference_spread` 的目标布局。

生成文件：

```text
demo\ABC_replay_from_x_reference.SLDASM
demo\abc_replay_initialize.png
demo\abc_replay_common_base.png
demo\abc_replay_from_x_reference_result.png
demo\abc_replay_from_x_reference_layout2d.json
```

第一次执行结果：

- `InitializeCommonBaseAssembly` 成功。
- `FinalizeCommonBaseAssembly` 成功。
- B-1 的底面法向自动通过 `PreMateTransform2` 修正，最终 orientation check 通过。
- `ApplyCapturedCommonBaseLayout` 返回成功。
- 但重新捕获 layout2d 后发现 B/C 与目标不一致。

问题定位：

- replay 内部仍调用旧的 `GetSelectedFaceCenter()`。
- 该接口返回的中心没有经过 `GetTotalTransform(true)`，在嵌套组件场景中不是正确的 assembly world center。

修复：

- 将 `ApplyCapturedCommonBaseLayout` 中的当前底面中心读取改为：

```text
GetSelectedFaceMappingProbe().WorldCenter
```

验证：

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
- 重新执行 Replay Layout。
- 再次捕获 `demo\abc_replay_from_x_reference_layout2d.json`。

最终对比：

```text
A-1 expected=(0, 0), actual=(0, 0), error=0
B-1 expected=(0.5526811272380519, 0.1805345745326763),
    actual=(0.5526811272380519, 0.18053457453267627),
    error=2.78e-17
C-1 expected=(0.25865398947636403, 0.14440055932749202),
    actual=(0.25865398947636403, 0.144400559327492),
    error=2.78e-17
```

结论：

- “参考装配体捕获 layout2d -> 新建 assembly -> 导入子装配体 -> 共底面 -> 根据 layout2d 恢复二维位置”的核心闭环已验证通过。
- 当前验证的是 2D 位置恢复，不包含完整旋转姿态恢复。

## 2026-06-29 Layout2D theta 回放功能实现与闭环验证

本次目标：

- 在已有 x/y 位置回放基础上，补充 `thetaDegrees/thetaAxis`。
- 让 Replay Layout 不仅移动到底面中心目标位置，也能恢复组件绕共底面法向的平面内旋转。

代码修改：

- `CommonBaseLayout2d` 新增：
  - `ThetaDegrees`
  - `ThetaAxis`
- `CommonBaseLayoutMath` 新增：
  - `ProjectPointWithRotation`
  - `CalculateBestInPlaneRotation`
  - `CalculateInPlaneRotationForAxis`
  - `NormalizeAngleDegrees`
  - `DeltaAngleDegrees`
- `DemoCapturedLayoutComponent` 新增：
  - `ComponentYAxis`
  - `ComponentZAxis`
- `CaptureCommonBaseLayoutFromAssembly`：
  - 捕获组件 Transform2 的 X/Y/Z 轴。
  - 从 X/Y/Z 中选择投影到共底面上最长的轴作为 `thetaAxis`。
- `ApplyCapturedCommonBaseLayout`：
  - 读取目标 `thetaDegrees/thetaAxis`。
  - 先计算当前 theta 与目标 theta 差值并旋转。
  - 旋转后重新 probe 底面中心。
  - 再移动到底面中心目标位置。

编译与单元测试：

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

结果：通过，0 error。

```text
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter "FullyQualifiedName~CommonBaseLayoutMathTests"
```

结果：测试 DLL 被 Windows 应用控制策略阻止加载。该问题属于环境限制，不是测试断言失败。

真实 SolidWorks 验证 1：重新捕获参考布局

输出：

```text
demo\x_reference_layout2d_theta.json
```

捕获到的关键 theta：

```text
A-1 theta=0deg, thetaAxis=x
B-1 theta=-20deg, thetaAxis=y
C-1 theta=15deg, thetaAxis=x
```

真实 SolidWorks 验证 2：第一次回放

结果：

- x/y 位置恢复正确。
- theta 符号相反：

```text
B-1 target=-20deg, actual=20deg
C-1 target=15deg, actual=-15deg
```

问题判断：

- `RotateComponent` 的角度正方向与 layout2d 投影数学正方向相反。
- 为避免影响其他已有旋转功能，只在 `ApplyCapturedCommonBaseLayout` 的 theta 回放中对角度取反。

真实 SolidWorks 验证 3：符号修复后再次回放

生成文件：

```text
demo\ABC_replay_from_x_reference_theta_signfix.SLDASM
demo\abc_replay_theta_signfix_initialize.png
demo\abc_replay_theta_signfix_common_base.png
demo\abc_replay_theta_signfix_result.png
demo\abc_replay_from_x_reference_theta_signfix_layout2d.json
```

最终对比：

```text
A-1
  xy_error=0
  theta_error=0deg
B-1
  xy_error=0
  theta_error=0deg
C-1
  xy_error=1.11e-16m
  theta_error=0deg
```

结论：

- “捕获 layout2d x/y/theta -> 新建 assembly -> Common Base -> Replay Layout2D x/y/theta -> 重新捕获验证”的闭环已通过。
- 当前 theta 是 Transform2 选定轴在共底面上的投影角，适合恢复共底面上的平面布局和朝向。
- 完整 3D 姿态恢复仍应作为后续独立能力处理。

脚本稳定性补充：

- `scripts\capture_common_base_layout.py` 默认改为使用构建输出 DLL 的 `--stdio-direct`。
- `scripts\apply_captured_common_base_layout.py` 默认改为使用构建输出 DLL 的 `--stdio-direct`。
- 两个脚本仍可通过环境变量覆盖：

```text
DEMO_MCP_COMMAND
DEMO_MCP_ARGS
DEMO_MCP_CWD
```

- 已执行：

```text
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
```

结果：通过。

## 2026-06-30 演示版本提交前整理

背景：

- 演示版本已经完成。
- 当前策略调整为：先稳定工程链路，再本地 commit，暂不 push。
- 目标是避免把临时 CAD、截图、日志、缓存和 IDE 临时文件混入提交。

执行内容：

1. 更新 `.gitignore`

忽略：

```text
demo/**/*.SLDASM
demo/*.png
demo/*.json
logs/
apps/demo-frontend/tsconfig.tsbuildinfo
/cad_task.md
/solve_problem.md
/git
/python
```

保留最终 layout JSON 样例：

```text
!demo/x_reference_layout2d_theta.json
!demo/abc_replay_from_x_reference_theta_signfix_layout2d.json
```

2. 更新 README

- `apps/demo-backend/README.md`
  - 改为 direct stdio MCP 链路说明。
  - 补充后端启动命令、health check、当前接口。
- `apps/demo-frontend/README.md`
  - 补充当前演示流程。
  - 明确推荐按钮顺序：

```text
Reset -> Initialize -> Common Base -> Capture Layout -> Replay Layout
```

3. 新增固化清单

```text
docs/demo_stabilization_checklist-CN.md
docs/demo_stabilization_checklist.md
```

4. 执行检查

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py apps\demo-backend\src
```

结果：

- build 通过，0 error。
- Python compileall 通过。

当前建议的本地提交命令：

```text
git add .gitignore
git add apps/demo-backend apps/demo-frontend/src apps/demo-frontend/README.md
git add scripts/capture_common_base_layout.py scripts/apply_captured_common_base_layout.py scripts/face_mapping_record_probe.py scripts/face_mapping_verify_select.py
git add vendor/solidworks-mcp/app/SolidWorksMcpApp vendor/solidworks-mcp/bridge/SolidWorksBridge vendor/solidworks-mcp/bridge/SolidWorksBridge.Tests
git add docs
git add demo/x_reference_layout2d_theta.json demo/abc_replay_from_x_reference_theta_signfix_layout2d.json
git commit -m "Add common-base layout2d theta replay workflow"
```

说明：

- 暂不 push。
- 若希望完全不提交 demo JSON 样例，可以跳过最后一条 `git add demo/...`。

## 2026-06-30 真实项目化能力第一轮补齐

本次目标：

- 不再把流程强绑定到 A/B/C 三个组件。
- 前端可以选择或上传 layout JSON。
- 前端能展示每个组件的 layout2d x/y/theta。
- 增加批量底面映射验证，降低单个组件映射错误导致 Common Base / Replay 失败的概率。

代码变更：

后端：

- `DemoState` 新增：

```text
layoutJsonPath
layoutInfo
```

- 新增模型：

```text
Layout2d
LayoutComponentSummary
LayoutJsonInfo
SelectLayoutJsonRequest
UploadLayoutJsonRequest
```

- 新增接口：

```text
GET  /api/demo/layout-json-files
POST /api/demo/select-layout-json
POST /api/demo/upload-layout-json
POST /api/demo/verify-face-mappings
```

- `ApplyCapturedCommonBaseLayout` 优先使用 state 中的 `layoutJsonPath`。
- 选择或上传 layout JSON 后，会解析 `components` 并同步任意数量组件到 state。
- 批量验证逻辑先检查本地 `face_mappings.json`，再生成每个组件的 `select_face_by_name` 和 `get_selected_face_mapping_probe` 调用。

前端：

- 新增 Layout JSON 面板：
  - 下拉选择已有 layout JSON；
  - 上传本地 JSON；
  - 展示每个组件的 x/y/theta；
  - 显示当前 layout 文件路径。
- 坐标表新增：
  - Layout X
  - Layout Y
  - Theta
- 工具栏新增：

```text
Verify Faces
```

- Replay 结果中新增 theta target/current/delta 展示。
- 组件颜色 fallback 改为根据组件 id/name hash，支持 n 个组件。

验证命令：

```text
python -m compileall apps\demo-backend\src
cmd /c npm run build
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

验证结果：

- 后端 Python 编译通过。
- 前端 TypeScript/Vite build 通过。
- MCP App build 通过。

后端非 CAD 闭环：

```text
list_layout_json_files()
select_layout_json(demo/x_reference_layout2d_theta.json)
upload_layout_json(uploaded_theta_test.json)
verify_face_mappings()
```

结果：

- layout JSON 可列出。
- 选择 `x_reference_layout2d_theta.json` 成功，组件目标 x/y 同步到 layout2d。
- 上传测试 JSON 成功，并写入 `demo/uploaded_layouts/`。
- 当前 dry-run 环境下，批量验证生成 6 个计划调用：3 个组件 × select/probe。

注意：

- 真正执行批量 face mapping 验证，需要 SolidWorks 当前活动装配体中包含对应组件实例。
- n 组件真实验证时，应先打开或初始化包含这 n 个组件的目标 assembly。
## 2026-06-30 - 前端上传 layout JSON 真实闭环复核

目标：
- 复核“真实项目化第一轮补齐”后，前端上传 layout JSON 的完整链路是否可用。
- 验证上传 `x_reference_layout2d_theta.json` 后，能否在 SolidWorks 中复原 A/B/C 的 `x/y/theta`。

用户执行：

```text
Reset
Upload x_reference_layout2d_theta.json
Initialize
Verify Faces
Common Base
Replay Layout
```

后端日志：
- `POST /api/demo/reset` -> 200
- `POST /api/demo/upload-layout-json` -> 200
- `POST /api/demo/initialize-common-base` -> 200
- `POST /api/demo/verify-face-mappings` -> 200
- `POST /api/demo/finalize-common-base` -> 200
- `POST /api/demo/apply-captured-layout` -> 200

状态文件关键结果：
- `assemblyPath=demo\ABC_arrange_demo.SLDASM`
- `commonBaseReady=true`
- `layoutJsonPath=demo\uploaded_layouts\x_reference_layout2d_theta.json`
- `lastRun.status=ok`
- `lastRun.toolSuccess=true`
- `lastRun.toolMessage=ApplyCapturedCommonBaseLayout completed.`

Replay 细节：
- A/B/C 均通过 Persistent Reference 选面。
- B-1 执行 theta replay，目标 `-20deg`，移动成功。
- C-1 执行 theta replay，目标 `15deg`，移动成功。

额外复核：
- 使用 MCP 对 replay 后的当前 `ABC_arrange_demo.SLDASM` 再次 capture layout。
- 与上传的 `x_reference_layout2d_theta.json` 对比：
  - A-1: `xy_error=0.0m`, `theta_error=0.0deg`
  - B-1: `xy_error=1.72e-15m`, `theta_error=0.0deg`
  - C-1: `xy_error=1.78e-15m`, `theta_error=0.0deg`

结论：
- 前端上传 layout JSON、批量面验证、Common Base、Replay Layout 的真实闭环通过。
- 当前版本可作为 A/B/C JSON-driven layout replay 的稳定演示基线。
- 后续建议把二次 capture 对比自动接入 Replay 结果，形成前端可见的误差报告。
## 2026-06-30 - 工程链路稳定性增强：Health / Active Assembly / Replay Check

目标：
- 按下一步规划补齐工程链路稳定性，而不是继续改底层几何逻辑。
- 重点解决：
  - MCP/活动文档状态不可见；
  - Verify Faces 可能对错误 assembly 操作；
  - Replay 后缺少自动误差报告。

修改：
- 后端新增模型 `McpHealthResult`。
- 后端新增接口：

```text
GET /api/demo/mcp-health
```

- `DemoService.mcp_health()` 调用 MCP `get_active_document`，返回 active document 与 `demo_state.json.assemblyPath` 的匹配情况。
- `verify_face_mappings()` 在真实 MCP 模式下先检查 active assembly 是否与 state 一致；不一致时返回 blocked。
- `apply_captured_layout()` replay 成功后自动追加一次 capture：

```text
capture_common_base_layout_from_assembly
```

- 后端将 capture 结果与目标 layout JSON 对比，生成：
  - `maxXyError`
  - `maxThetaErrorDegrees`
  - 每个组件的 `xyError/thetaErrorDegrees`
- 结果写入：

```text
state.lastRun.replayValidation
```

- 前端新增 `Replay Check` 区域，用于显示 replay 误差。

验证命令：

```text
python -m compileall apps\demo-backend\src
cmd /c npm run build
```

验证结果：
- 后端编译通过。
- 前端 build 通过。

服务级 dry-run 验证：

```text
mcp_health() -> dry-run
list_layout_json_files() -> 10 files
select_layout_json(demo/x_reference_layout2d_theta.json) -> ok, componentCount=3
verify_face_mappings() -> dry-run, 6 planned calls
_compare_layout_payloads(target, target) -> success=True, max errors = 0
```

遇到的问题：
- `fastapi.testclient.TestClient` 在当前环境缺少 `httpx2`，无法使用。
- 已改为直接实例化 `DemoService` 进行服务级 dry-run 验证，避免新增依赖。

待真实验证：
- 重启后端后，在前端执行一次 `Replay Layout`。
- 检查右侧 `Replay Check` 是否显示 `matched`，且 A/B/C 误差接近 0。
