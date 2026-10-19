# Common Base / Transform2 / Layout2D 新人操作手册

## 1. 文档目标

本文用于帮助新成员快速跑通以下闭环：

```text
启动 SolidWorks 与前后端
→ 在参考装配体中记录并验证底面
→ 读取 Transform2 并生成 Layout2D JSON
→ 初始化新的目标装配体
→ 执行 Common Base
→ Replay Layout
→ 检查位置与平面内旋转误差
```

这里所说的“记录 Transform2”，并不是手工复制一组矩阵，而是调用
`capture_common_base_layout_from_assembly`，读取组件的 `Transform2`，再转换为以基准组件为参考的
`x / y / thetaDegrees` 布局数据。

## 2. 核心概念

| 名称 | 含义 |
| --- | --- |
| 参考装配体 X | 已经具有目标布局的装配体，用于采集 Layout2D |
| 目标装配体 | 新建并导入各子装配体的文件，用于执行 Common Base 和 Replay |
| 底面映射 | 组件实例名和真实底面之间的可重复选择关系，保存在 `face_mappings.json` |
| Common Base | 将各组件记录的底面配合到共同基准面 |
| Transform2 | SolidWorks 组件相对于装配体的完整变换，包含平移和旋转 |
| Layout2D | 从 Transform2 和底面几何中提取的平面布局，主要包含 `x`、`y` 和 `thetaDegrees` |
| Replay Layout | 在目标装配体中恢复 Layout2D 的平面位置和旋转 |

关键运行文件：

```text
artifacts\solidworks-mcp\face_mappings.json
demo\demo_state.json
demo\captured_common_base_layout.json
```

组件实例名必须保持一致。例如参考装配体中记录的是 `A-1`，目标装配体中也应存在 `A-1`。

## 3. 环境要求

需要安装：

- Windows 和 SolidWorks；
- .NET 8 SDK；
- Python 3；
- Node.js 和 npm。

所有命令默认从项目根目录执行：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
```

首次使用或 C# 代码更新后执行：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet build apps\demo-backend\tools\McpToolRunner\McpToolRunner.csproj -c Release
```

首次启动前端时执行一次：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
```

## 4. 启动系统

### 4.1 启动 SolidWorks

启动 SolidWorks，并确认没有残留的错误对话框、配合冲突窗口或正在重建的文档。

如果准备采集参考布局，打开参考装配体 X；如果准备恢复布局，可以先只启动 SolidWorks，随后由
Initialize 创建或打开目标装配体。

### 4.2 启动后端

打开一个新的 CMD 窗口：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
scripts\start_demo_backend.cmd
```

该脚本默认配置：

- 后端地址：`http://127.0.0.1:8000`；
- MCP 模式：`bridge`；
- MCP 实际连接：`SolidWorksMcpApp.dll --stdio-direct`；
- 超时：420 秒；
- 面映射文件：`artifacts\solidworks-mcp\face_mappings.json`。

看到以下信息表示后端已启动：

```text
Uvicorn running on http://127.0.0.1:8000
```

如果出现 WinError 10048，说明 8000 端口已经被另一个后端占用。先检查：

```cmd
netstat -ano | findstr :8000
```

确认 PID 后，只终止对应进程：

```cmd
taskkill /PID <PID> /F
```

不要直接终止所有 `python.exe` 或 `dotnet.exe`。

### 4.3 检查后端和 SolidWorks MCP

另开一个 CMD：

```cmd
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:8000/api/demo/mcp-health
```

重点检查：

- `status` 为 `ok`；
- `mcpMode` 为 `bridge`；
- `faceMappingPathsMatch` 为 `true`；
- 活动文档路径与当前操作目标一致。

后端主流程使用 `--stdio-direct`，通常不需要单独启动 MCP Hub。

只有在明确测试 Hub/proxy 模式时才运行：

```cmd
scripts\start_mcp_hub.cmd
scripts\check_mcp_hub.cmd
```

### 4.4 启动前端

打开新的 CMD 窗口：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

可以在浏览器中打开，也可以在 VS Code 的 Simple Browser 中打开。

## 5. 记录并验证底面

### 5.1 为脚本指定稳定的直接连接方式

在准备运行面记录脚本的 CMD 窗口中执行：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
set DEMO_MCP_COMMAND=dotnet
set DEMO_MCP_CWD=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64
set DEMO_MCP_ARGS=SolidWorksMcpApp.dll --stdio-direct
set DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

执行脚本期间不要同时点击前端的 Common Base 或 Replay Layout。

### 5.2 记录底面

1. 在 SolidWorks 中打开参考装配体。
2. 在组件树或图形区找到组件实例。
3. 用鼠标选中该组件的真实底面。
4. 保持选择不变，执行：

```cmd
python scripts\face_mapping_record_probe.py --component A-1 --face 底面
```

将 `A-1` 替换为实际组件实例名。

成功输出应包含：

- `RecordFaceMapping` 的 `Success: true`；
- `localCenter`；
- `area`；
- `localNormal` 和 `worldNormal`；
- 正确的 `MappingPath`。

### 5.3 验证底面映射

```cmd
python scripts\face_mapping_verify_select.py --component A-1 --face 底面
```

预期结果：

```text
RESULT: PASS
```

验证脚本会清空选择，通过映射重新选择底面，再比较：

- 叶子零件路径；
- 局部中心；
- 面积；
- 局部法向。

如果出现 `FAIL`，不要继续 Common Base。先检查：

- 组件实例名是否正确；
- 当前活动装配体是否正确；
- 记录脚本和验证脚本是否使用同一个 `face_mappings.json`；
- 选中的是否为平面；
- 组件版本或装配层级是否发生变化。

对所有参与恢复的组件重复“记录 + 验证”。

## 6. 从参考装配体采集 Transform2 / Layout2D

确保：

- 参考装配体 X 是当前活动文档；
- 各组件已经处于希望复原的最终布局；
- 各组件真实底面已经共面，且底面法向符合预期；
- 各组件底面映射验证为 PASS；
- 组件实例名与未来目标装配体中的名称一致。

三个组件示例：

```cmd
python scripts\capture_common_base_layout.py ^
  --source "D:\path\X_reference.SLDASM" ^
  --component "A-1:底面" ^
  --component "B-1:底面" ^
  --component "C-1:底面" ^
  --base-component "A-1" ^
  --output "demo\x_reference_layout2d.json"
```

如果省略所有 `--component`，脚本会尝试采集顶层组件。正式测试建议显式列出参与恢复的组件。

检查输出 JSON：

```cmd
type demo\x_reference_layout2d.json
```

每个组件应至少包含：

```json
{
  "componentName": "B-1",
  "bottomFaceName": "底面",
  "layout2d": {
    "x": 0.2,
    "y": 0.1,
    "thetaDegrees": 30.0
  }
}
```

`x/y/thetaDegrees` 是相对于共同底平面和基准组件的布局关系，不是简单复制世界坐标。

## 7. 在新装配体中恢复布局

### 7.1 准备目标文件

关闭参考装配体，或至少确保后续操作时目标装配体是 SolidWorks 当前活动文档。

注意：

- 前端 Reset 只重置 `demo_state.json`；
- Reset 不会关闭 SolidWorks 文档；
- Reset 不会删除旧的目标 `.SLDASM`；
- 如果要从零开始，应先关闭、备份、改名或删除旧目标文件。

如果需要指定新的目标装配体路径，应在启动后端前执行：

```cmd
set DEMO_TARGET_ASSEMBLY_PATH=D:\path\X_replay_test.SLDASM
scripts\start_demo_backend.cmd
```

### 7.2 前端操作顺序

推荐顺序：

```text
Reset
→ 选择或 Upload Layout JSON
→ Verify Faces
→ Initialize
→ Verify Faces
→ Common Base
→ Replay Layout
```

具体含义：

1. `Reset`：清空后端运行状态。
2. `Upload JSON` 或选择已有 JSON：载入参考布局，并将组件列表同步到前端状态。
3. 第一次 `Verify Faces`：检查组件是否都有底面映射。
4. `Initialize`：新建或打开目标 assembly，并导入组件；不执行共面和移动。
5. 第二次 `Verify Faces`：确认目标装配体中的组件仍能选回记录的底面。
6. `Common Base`：建立共同底面，成功后应显示 `base ready`。
7. `Replay Layout`：根据 JSON 的 `x/y/thetaDegrees` 恢复位置和平面内旋转。

`Initialize` 和 `Common Base` 可能耗时较长。按钮处于 Busy 状态时不要重复点击。

### 7.3 成功判据

Common Base 成功：

- `status = ok`；
- `commonBaseReady = true`；
- `orientationChecks` 没有错误；
- SolidWorks 中各底面共面且方向符合预期。

Replay Layout 成功：

- 每个组件的 `xyError` 小于配置阈值；
- 每个组件的 `thetaErrorDegrees` 小于配置阈值；
- `replayValidation.success = true`；
- SolidWorks 中的视觉布局与参考装配体一致。

默认阈值：

```text
XY：0.000001 m
Theta：0.0001 deg
```

## 8. 无前端的命令行验证

直接采集：

```cmd
python scripts\capture_common_base_layout.py --source "D:\path\X_reference.SLDASM" --output "demo\captured_common_base_layout.json"
```

直接恢复：

```cmd
python scripts\apply_captured_common_base_layout.py ^
  --layout "demo\captured_common_base_layout.json" ^
  --assembly "D:\path\X_replay_test.SLDASM" ^
  --screenshot "demo\apply_captured_layout_result.png"
```

命令行脚本适合定位 MCP/C# 问题；前端完整流程适合验证后端状态机和演示交互。

## 9. 常见故障

### 后端端口被占用

现象：`WinError 10048`。

处理：查找 8000 端口 PID，只终止对应进程，然后重新启动后端。

### MCP server shut down unexpectedly

检查：

- `SolidWorksMcpApp.dll` 是否已经 Release build；
- `DEMO_MCP_CWD` 是否指向正确目录；
- SolidWorks 是否已经打开；
- 是否存在未处理的 SolidWorks 模态对话框；
- 是否混用了 Hub/proxy 和 `--stdio-direct`；
- 后端与脚本是否同时操作 SolidWorks。

### Initialize 后生成了错误的新装配体

检查：

- `DEMO_TARGET_ASSEMBLY_PATH`；
- `demo\demo_state.json` 中的 `assemblyPath`；
- 旧目标装配体是否仍在 SolidWorks 中打开；
- 是否在启动后端后才修改环境变量。

### Common Base 被阻塞

通常原因：

- 缺少底面映射；
- 底面验证失败；
- 当前活动装配体与 state 中记录的装配体不一致；
- 底面 normal 无法读取；
- mate 或方向检查失败。

### Replay 位置正确但旋转不正确

检查 Layout JSON 是否包含：

```text
thetaDegrees
thetaAxis
```

并检查 Replay 返回的 `currentThetaDegrees`、`targetThetaDegrees`、
`deltaThetaDegrees` 和 `thetaErrorDegrees`。

## 10. 新成员给大模型助手的基础 Prompt

下面的 Prompt 可以在新会话开始时直接发送给大模型助手：

```text
你正在协助我维护一个 SolidWorks 自动装配项目。

项目根目录：
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp

项目目标：
从参考装配体读取各子装配体的 Transform2，生成相对于共同底平面的
Layout2D（x、y、theta）；在新的 assembly 中导入相同组件，完成 Common Base，
再通过 Replay Layout 恢复参考装配体的平面位置和旋转。

当前稳定链路：
1. 记录并验证底面映射；
2. Capture Layout 读取 Transform2 并生成 Layout JSON；
3. Reset；
4. 选择或上传 Layout JSON；
5. Initialize，只导入组件；
6. Verify Faces；
7. Common Base；
8. Replay Layout；
9. 检查 xyError 和 thetaErrorDegrees。

重要约束：
- 后端优先使用 SolidWorksMcpApp.dll --stdio-direct；
- 面映射统一使用 artifacts\solidworks-mcp\face_mappings.json；
- 不要混用不同发布目录中的 face_mappings.json；
- Reset 不会关闭 SolidWorks 文档，也不会删除 assembly 文件；
- 调用 MCP 前必须确认 SolidWorks 当前活动装配体；
- 不要重复点击 Initialize 或 Common Base；
- 不要直接结束所有 python.exe 或 dotnet.exe，只处理已确认的 PID；
- 不要删除或覆盖 SLDASM 文件，除非我明确同意；
- SolidWorks 中手工选面的步骤由我完成，你在我确认“已选中”后再运行记录脚本；
- 诊断时先读取日志、demo_state.json、health 和 mcp-health，再提出结论；
- 修改代码时保持最小侵入，并运行相应 build、Python compile 或前端 build；
- 不要撤销工作区中与当前任务无关的修改。

关键脚本：
- scripts\start_demo_backend.cmd
- scripts\face_mapping_record_probe.py
- scripts\face_mapping_verify_select.py
- scripts\capture_common_base_layout.py
- scripts\apply_captured_common_base_layout.py

请先检查当前进程、端口、后端健康状态、MCP 配置和 SolidWorks 活动文档，
然后用“当前状态、发现的问题、已执行操作、下一步需要我做什么”的格式回复。
能安全独立完成的检查和测试请直接执行；只有需要我操作 SolidWorks UI 时再暂停。
```

## 11. 分阶段 Prompt 模板

### 11.1 启动与健康检查

```text
请帮助我恢复本项目的运行环境：
1. 检查 8000 和 5173 端口；
2. 检查 Release 版 SolidWorksMcpApp.dll 和 McpToolRunner.dll 是否存在；
3. 启动或确认后端；
4. 执行 /api/health 和 /api/demo/mcp-health；
5. 启动或确认前端。

不要结束不相关进程。若 SolidWorks 当前活动文档与 demo_state.json 不一致，
请明确告诉我两个路径，不要直接执行几何操作。
```

### 11.2 记录底面

```text
SolidWorks 中当前打开的是参考装配体：
<参考装配体路径>

我要为组件 <组件实例名> 记录名为“底面”的面映射。
请先确认脚本使用：
artifacts\solidworks-mcp\face_mappings.json

我会手工选中真实底面。当我回复“已选中”后，请运行记录脚本，
展示 localCenter、area、localNormal、worldNormal、persistent reference 状态和映射路径；
然后运行验证脚本，并明确输出 PASS 或 FAIL。
```

### 11.3 捕获 Transform2 / Layout2D

```text
参考装配体路径：<X_reference.SLDASM>
参与组件：<A-1、B-1、C-1 或其他组件>
基准组件：<A-1>
输出文件：<demo\x_reference_layout2d.json>

请先确认所有组件底面映射验证通过，再调用
scripts\capture_common_base_layout.py。
完成后检查每个组件是否包含 filePath、bottomFaceName、x、y、
thetaDegrees 和 thetaAxis，并总结该布局是否适合用于 Replay。
```

### 11.4 初始化、共面与恢复

```text
请根据布局文件 <layout JSON 路径> 完成一次恢复闭环。

目标装配体路径：<目标 SLDASM 路径>

严格按以下阶段执行并逐阶段验证：
Reset/载入布局 → Initialize → Verify Faces → Common Base → Replay Layout。

每一阶段完成后检查 demo_state.json 和工具返回值。
Initialize 只负责导入组件；Common Base 只负责共底面；
Replay 负责恢复 x/y/theta。若某阶段失败，不要继续下一阶段，
请指出具体组件、底面映射、normal、mate 或误差信息。
```

### 11.5 日志分析

```text
刚才执行 <Initialize/Common Base/Replay Layout> 后出现：
<粘贴前端错误>

请结合以下信息诊断：
- 后端日志；
- MCP 日志；
- demo\demo_state.json；
- artifacts\solidworks-mcp\face_mappings.json；
- SolidWorks 当前活动文档；
- 最近生成的 layout JSON 和截图。

请区分“直接证据”和“推测”，给出最可能原因、次要可能原因，
以及最小风险的下一步验证。此时先诊断，不修改代码。
```

### 11.6 请求大模型修改代码

```text
请修复以下问题：
<问题描述>

要求：
- 先阅读现有调用链和当前未提交修改；
- 保留已验证通过的 Initialize、Common Base 和 Replay 行为；
- 最小化修改范围；
- 为新增或修改功能补充针对性测试；
- 运行 C# build、Python compile/test、前端 build 中适用的检查；
- 不修改或提交 demo 生成的 SLDASM、截图和运行时状态；
- 将修改点、测试结果和遗留问题记录到项目对应的中英文进展文档；
- 完成后列出修改文件、验证结果和仍需人工执行的 SolidWorks 测试。
```

## 12. 新成员操作原则

1. 一次只执行一个 SolidWorks 几何操作，等待完成后再继续。
2. 始终确认活动装配体、目标装配体路径和组件实例名。
3. 底面验证不通过时，不执行 Common Base。
4. Common Base 未成功时，不执行 Replay Layout。
5. 不把前端显示 `ok` 等同于几何结果正确，必须检查误差和 SolidWorks UI。
6. 修改代码前先保留一份已验证通过的 Layout JSON 和测试装配体。
7. 遇到超时先确认 SolidWorks 是否仍在计算，不要立即重复调用。
