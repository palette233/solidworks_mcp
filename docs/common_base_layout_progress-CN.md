# 共底面布局复原功能进展

## 2026-06-25 - 干净装配体验证结果

验证流程：
- 删除旧 `demo/ABC_arrange_demo.SLDASM` 后，从后端接口重新执行：
  - `Reset`
  - `Initialize`
  - `Common Base`
  - `Capture Layout`
  - `Replay Layout`

结果：
- `InitializeCommonBaseAssembly` 成功，A/B/C 全部导入，并生成新的 `demo/ABC_arrange_demo.SLDASM`。
- `FinalizeCommonBaseAssembly` 仍返回 `bottom face orientation mismatch`。
- 但这次 B/C 的 `bottomMateResult` 均为 `swAddMateError_NoError`，说明底面重合配合创建成功。
- 失败原因来自 `orientationChecks`：
  - A 为基准，`matchesBase=true`。
  - B/C `matchesBase=false`。
- 这说明本轮修复已把问题从“重复创建配合/回归”收敛为“底面朝向自动修正尚未完成”。
- `CaptureCommonBaseLayoutFromAssembly` 成功，生成 `demo/captured_common_base_layout.json`。
- `ApplyCapturedCommonBaseLayout` 成功，生成 `demo/apply_captured_layout_result.png`，A/B/C 均完成基于 layout2d 的移动。

当前结论：
- `Initialize -> Capture Layout -> Replay Layout` 主链路可用。
- `Common Base` 的共面配合创建成功，但朝向一致性仍是待实现能力。
- 下一步应集中实现“根据法向显式旋转 B/C，使底面朝向与 A 一致”，不要再回到反复 mate/undo 的方案。

## 2026-06-25 - 已修复 Common Base 重复配合回归

修复目标：
- 保证已有通过验证的基础 Common Base 流程不被朝向检测功能破坏。
- 避免在一次 `FinalizeCommonBaseAssembly` 中反复创建/撤销 `Coincident` mate，从而避免 A-B、A-C 之间出现重复配合。

代码修改：
- 修改 `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/DemoTools.cs`。
- 移除通过多次 mate alignment 重试并 `Undo(1)` 的逻辑。
- `MateBottomFacesToFirstComponent()` 恢复为每个目标组件只创建一次底面重合配合。
- `FinalizeCommonBaseAssembly` 仍会在配合后执行 `orientationChecks`，用于报告 B/C 底面法向是否与 A 一致。
- 如果朝向不一致，工具仍返回清晰的 orientation mismatch，但不会再因为重试逻辑留下重复 mate。

验证：
```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：
- MCP app 构建通过，0 warning，0 error。
- 后端 Python 编译通过。
- 前端 TypeScript/Vite 构建通过。
- 已重新发布到默认 MCP 目录 `artifacts/solidworks-mcp`。
- 已重启默认 MCP 和后端，`/api/health` 确认后端指向：
  - `mcpCwd=artifacts/solidworks-mcp`
  - `faceMappingPath=artifacts/solidworks-mcp/face_mappings.json`

当前状态：
- 代码层修复和基础构建验证已完成。
- 真实 SolidWorks 自测暂未直接执行，因为当前打开/已有的 `demo/ABC_arrange_demo.SLDASM` 可能已经包含旧逻辑遗留的重复配合。
- 下一次真实测试建议先使用干净装配体：关闭并删除旧 `ABC_arrange_demo.SLDASM`，或手动删除旧的重复 Coincident mate 后再执行 `Initialize -> Common Base`。

## 目标

支持如下流程：

1. 打开原始装配体 `X`，其中包含 `A`、`B`、`C` 等第一层子装配体。
2. 记录或解析每个子装配体的底面。
3. 采集这些子装配体在原始装配体中的共同底平面布局关系。
4. 新建空白装配体，插入这些子装配体，完成共底面，然后按照采集到的二维布局移动组件，以近似复原原始装配关系。

## 推荐架构

整个流程拆成明确阶段：

1. `CaptureCommonBaseLayoutFromAssembly`
   - 读取第一层组件的 `Transform2`。
   - 选中已记录的底面。
   - 读取底面世界坐标中心点和法向。
   - 建立 `CommonBaseFrame`。
   - 将各个底面中心点投影成二维布局坐标。
   - 可选写出布局 JSON。

2. `InitializeCommonBaseAssembly`
   - 创建或打开目标装配体。
   - 插入组件。
   - 保存 `assemblyPath`。
   - 不做共面，不做移动。

3. `FinalizeCommonBaseAssembly`
   - 只执行一次底面共面配合。
   - 后端状态中写入 `commonBaseReady=true`。
   - 后续增强：配合后校验底面法向方向。

4. `MoveComponentsOnCommonBase`
   - 只在 `commonBaseReady=true` 后执行。
   - 按底面中心移动组件。
   - 后续增强：使用采集得到的 `baseFrame`，而不是固定 SolidWorks 参考平面。

## 已完成改动

### 面映射

修改：

- `SelectionService.FaceMappingProbeResult`
- `SelectionService.GetSelectedFaceMappingProbe`
- `SelectionService.RecordFaceMapping`
- `SelectionService.SelectFaceByName`

新增字段：

- `WorldNormal`
- `LocalNormal`

行为：

- 当被选中的面是平面时，记录/探测归一化法向。
- `face_mappings.json` 中新增 `localNormal` 和 `worldNormal`。
- 旧版没有 normal 的映射仍可继续使用。
- 当存在 `localNormal` 时，`SelectFaceByName` 会把法向作为候选面匹配的辅助因素。

### 组件 Transform2 采集

修改：

- `AssemblyService`
- `IAssemblyService`
- `AssemblyTools`
- `SolidWorksMcpHubTestClient`

新增：

- `ComponentPoseInfo`
- `IAssemblyService.ListComponentPoses(bool topLevelOnly = true)`
- MCP 工具 `list_component_poses`

返回信息包括：

- 组件名
- 源文件路径
- 层级路径
- 深度
- 原始 `Transform2`
- 平移量
- X/Y/Z 轴

### 共底面布局数学层

新增：

- `CommonBaseLayoutMath`
- `CommonBaseFrame`
- `CommonBaseLayout2d`

职责：

- 根据底面中心点、底面法向和组件 X 轴建立稳定的底平面坐标系。
- 将世界坐标点投影为二维布局坐标。
- 将二维布局坐标还原为底平面上的世界坐标点。
- 通过 `NormalsMatchDirection` 使用点积阈值判断法向方向是否一致。

### 共底面后的方向校验

修改：

- `DemoTools.FinalizeCommonBaseAssembly`
- `DemoTools.FinalizeCommonBaseCore`

新增：

- `DemoBottomOrientationCheck`
- `DemoCommonBaseResult.OrientationChecks`

行为：

- 底面 mate 并 rebuild 后，工具会重新选中/探测每个组件的底面。
- 第一个组件作为方向基准。
- 后续组件需要满足 `dot(worldNormal, baseWorldNormal) >= normalDotThreshold`。
- 默认阈值为 `0.95`。
- 如果某个组件的底面法向与基准方向相反，结果会 `Success=false`，并返回 `bottom face orientation mismatch`。
- 当前版本只做方向错误检测，不自动旋转或翻转组件。

### 布局采集 MCP 工具

修改：

- `DemoTools`

新增 MCP 工具：

- `capture_common_base_layout_from_assembly`

C# 方法：

- `CaptureCommonBaseLayoutFromAssembly`

内部方法：

- `CaptureCommonBaseLayoutCore`

输出结构：

- `DemoCapturedLayoutDocument`

当前能力：

- 如果传入源装配体路径，则打开该装配体；否则使用当前活动装配体。
- 默认采集所有第一层组件，也可以传入指定组件列表。
- 要求组件已经记录底面映射。
- 使用第一个有效组件或 `baseComponentName` 作为布局原点。
- 返回每个组件的 `Transform2`、底面中心点、底面法向和二维投影坐标。
- 可选写出 JSON 文件。

### 命令行脚本

新增：

- `scripts/capture_common_base_layout.py`

用途：

- 通过 `McpToolRunner` 调用 `capture_common_base_layout_from_assembly`。
- 打印采集到的布局 JSON。
- 可选写出布局 JSON 文件。

示例：

```cmd
python scripts\capture_common_base_layout.py ^
  --source D:\path\to\X.SLDASM ^
  --component A-1:底面 ^
  --component B-1:底面 ^
  --component C-1:底面 ^
  --base-component A-1 ^
  --output demo\captured_common_base_layout.json
```

### 验证脚本

修改：

- `scripts/face_mapping_verify_select.py`

新增行为：

- 如果映射中存在 `localNormal`，验证脚本会比较选中面法向，计算 `1 - abs(dot)`。
- 没有 normal 的旧映射仍按叶子组件、局部中心点和面积验证。

## 已执行测试

命令：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m py_compile scripts\capture_common_base_layout.py scripts\face_mapping_record_probe.py scripts\face_mapping_verify_select.py
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter CommonBaseLayoutMathTests
```

结果：

- MCP App 编译通过。
- Python 脚本语法检查通过。
- `CommonBaseLayoutMathTests` 通过 5 个测试。

## 当前阶段进度

### 第一阶段：稳定 Demo 流程

状态：基本完成。

已有工具：

- `InitializeCommonBaseAssembly`
- `FinalizeCommonBaseAssembly`
- `MoveComponentsOnCommonBase`

### 第二阶段：底面朝向控制

状态：已完成检测能力，尚未做自动修正。

已完成：

- 记录/探测平面底面的 local/world normal。
- 在 `FinalizeCommonBaseAssembly` 后校验底面 world normal 方向。
- 当 B/C 与 A 方向不一致时返回明确的 `bottom face orientation mismatch`。

待完成：

- 根据 normal 在 mate 前或 mate 时选择更合适的 mate alignment。
- 后续可选：自动旋转或翻转组件修正方向。

### 第三阶段：提高面映射可靠性

状态：部分增强。

已完成：

- `localNormal` 已保存，并作为选择匹配的辅助因素。

待完成：

- SolidWorks Persistent Reference。
- center + area + normal + topology hints 的 fallback。
- 共底面后自动重新探测并检测映射漂移。

### 第四阶段：前端流程调整

状态：本轮未改。

已有：

- Initialize / Common Base / Arrange 已拆开。
- 已有二维拖动。

待完成：

- 增加 Capture Layout UI。
- 增加显式 Verify Bottom Faces UI。
- 显示每个组件的 `layout2d` 和状态。
- 使用采集布局作为前端画布初始状态。

## 下一步建议

发布新版 MCP 并进行一次真实 SolidWorks 验证：

1. 重新记录底面，让映射中包含 `localNormal/worldNormal`。
2. 执行 `InitializeCommonBaseAssembly`。
3. 执行 `FinalizeCommonBaseAssembly`。
4. 查看返回 JSON 中的 `orientationChecks`。
5. 如果方向校验全部通过，再执行 `MoveComponentsOnCommonBase`。

真实验证稳定后，再实现方向不一致时的自动修正。

## 问题记录

### 2026-06-22 16:53:57 CST - Common Base 在底面朝向校验阶段失败

现象：

- `InitializeCommonBaseAssembly` 在 `2026-06-22 16:52:30 CST` 成功执行，并保存了 `demo/ABC_arrange_demo.SLDASM`。
- `FinalizeCommonBaseAssembly` 在 `2026-06-22 16:53:57 CST` 执行，参数中包含 `normalDotThreshold=0.95`。
- B、C 的底面配合返回 `swAddMateError_NoError`，说明 mate 共面步骤本身没有失败。
- 工具最终返回 `Success=false`，错误信息为 `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`

原因分析：

- 当前 `face_mappings.json` 中已经出现 `localNormal` 和 `worldNormal`，说明新版记录法向的代码已经生效。
- 但 A-1 的底面记录中，`localNormal` 和 `worldNormal` 都是 `[0,0,0]`，这是无效法向。
- `FinalizeCommonBaseAssembly` 使用 A-1 作为底面朝向基准。由于 A 的基准法向是零向量，B/C 与 A 做 dot product 朝向校验时无法通过，最终被判定为 `bottom face orientation mismatch`。
- 因此，本次失败主要不是移动失败，也不是 mate 失败，而是“面映射中的基准法向无效”导致的朝向校验失败。

后续处理项：

- 记录面和校验面时，应拒绝缺失或接近零长度的 normal，不能继续保存或使用 `[0,0,0]`。
- 返回更明确的错误，例如 `A-1 bottom face normal unavailable; please re-record a planar bottom face`。
- 修正校验逻辑后，需要重新记录 A-1 的真实平面底面，确保 A 的法向有效。
- 后端 `lastRun` 和前端结果中应保留 `orientationChecks`，避免以后只能依赖 MCP 日志排查类似问题。

### 2026-06-22 17:20 CST - 已实现零法向保护

修改内容：

- 新增 `CommonBaseLayoutMath.IsValidNormal(...)`。
- 修改 `CommonBaseLayoutMath.NormalsMatchDirection(...)`，零向量或接近零长度的法向不会再通过朝向匹配。
- 修改 `SelectionService.TryGetPlanarFaceNormal(...)` 和局部到世界向量转换逻辑，无效平面法向现在返回 `null`，不再返回 `[0,0,0]`。
- 修改面选择匹配逻辑，历史映射中如果存在零法向，则不再把它作为 normal 匹配因子。
- 修改 `FinalizeCommonBaseAssembly` 的朝向探测逻辑：如果选中的底面没有有效平面世界法向，会返回更明确的 bottom-face normal probe error。
- 增加零法向拒绝的单元测试。

验证命令：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter CommonBaseLayoutMathTests
```

验证结果：

- MCP App Release 编译通过，0 warning，0 error。
- `CommonBaseLayoutMathTests` 通过 6 个测试。

下一步真实验证：

- 发布并重启新版 MCP。
- 重新记录 A-1 的底面，新的映射中不应再出现 `[0,0,0]` normal。
- 再执行 `FinalizeCommonBaseAssembly`，检查返回结果中的 `orientationChecks`。

### 2026-06-22 17:35 CST - 后端 faceMappingPath 仍指向旧 MCP 产物目录

现象：

- 后端 `/api/health` 返回的 `mcpCwd` 已经是 `artifacts/solidworks-mcp`，这说明 MCP 启动目录已经指向新版产物。
- 但同一个返回中，`faceMappingPath` 仍然是 `artifacts/solidworks-mcp-20260615-demo-mate/face_mappings.json`。
- 这会导致后端调用新版 MCP 工具，但预检查面映射时仍读取旧目录下的 `face_mappings.json`，从而造成测试结果混乱。

原因：

- `DEMO_MCP_CWD` 只控制后端从哪个目录启动 MCP 命令。
- `DEMO_FACE_MAPPING_PATH` 单独控制后端读取哪个 `face_mappings.json`。
- 只修改 `DEMO_MCP_CWD` 不够；如果没有显式设置 `DEMO_FACE_MAPPING_PATH`，后端仍会使用 `config.py` 中旧的默认路径。

解决方法：

启动后端时，同时设置 MCP 工作目录和面映射文件路径：

```cmd
set DEMO_MCP_MODE=bridge
set DEMO_LLM_MODE=dry-run
set DEMO_MCP_CWD=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp
set DEMO_MCP_COMMAND=SolidWorksMcpApp.exe
set DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

验证方式：

- 重启后端后，调用 `/api/health`。
- `mcpCwd` 和 `faceMappingPath` 都应指向 `artifacts/solidworks-mcp`。
- 当前用户已确认该项符合预期。

### 2026-06-22 18:32:47 CST - Common Base 共面成功，但 B 朝向不一致导致 Arrange 被阻止

现象：

- A/B/C 的底面映射均可用于选面。
- `FinalizeCommonBaseAssembly` 能选中底面，并为 B、C 创建共面 mate。
- B、C 的 mate 结果均为 `swAddMateError_NoError`。
- SolidWorks UI 中三个底面已经共面。
- B 的底面朝向与 A 不一致，C 的底面朝向与 A 一致。
- 前端显示 `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`
- 前端状态保持为 `error / base pending`，`Arrange` 暂时无法点击。

分析：

- 当前共面 mate 的几何操作已经成功。
- 朝向校验正确识别出 B 虽然共面但相对 A 翻转，因此没有将 `commonBaseReady` 置为 `true`。
- 这是当前实现的预期保护行为：目前已经能检测朝向问题，但还不能自动修正朝向。

后续：

- “自动修正底面朝向”已记录到 `docs/to_be_continued.md`，作为长期增强任务。
- 当前验证可以先转向新引入的 Transform2 采集/布局功能。

### 2026-06-22 18:40 CST - 干净状态下 Transform2/layout2d 采集验证通过

现象：

- 用户在干净 Initialize 后、尚未执行 Common Base 的状态下，重新运行 `capture_common_base_layout.py`。
- `CaptureCommonBaseLayoutFromAssembly` 返回 `success=true`。
- `missingFaceMappings=[]`。
- A/B/C 都成功返回：
  - `sourceTransform`，
  - `componentTranslation`，
  - `componentXAxis`，
  - `bottomCenterWorld`，
  - `bottomNormalWorld`，
  - `layout2d`，
  - 成功的 face selection 和 face probe。
- A 作为基准组件，`layout2d` 为 `{ x: 0, y: 0 }`。
- B 的 `layout2d` 约为 `{ x: 0.218, y: 0 }`。
- C 的 `layout2d` 约为 `{ x: -0.0195, y: 0.012 }`。
- A/B/C 的 `faceProbe.area` 与当前 `face_mappings.json` 中记录的面积一致，说明这次干净状态采集中没有再选错面。

分析：

- Transform2 采集和共同底面二维投影逻辑已经在干净状态下验证通过。
- 生成的 JSON 可以作为后续在新 assembly 中复原组件二维位置关系的布局蓝图。
- B 的底面 normal 仍然与 A/C 不一致，因此“自动修正底面朝向”仍是后续独立增强项。

状态：

- Transform2/layout 捕获：已验证。
- 自动修正底面朝向：待完成。
- 将捕获的 `layout2d` 自动应用到新 assembly：待完成。

### 2026-06-24 11:24 CST - 第一版 layout2d 回放工具已实现

已实现：

- 新增 MCP 工具 `ApplyCapturedCommonBaseLayout`。
- 新增命令行脚本 `scripts/apply_captured_common_base_layout.py`。
- 新工具读取 `CaptureCommonBaseLayoutFromAssembly` 生成的 JSON。
- 对每个组件，工具会：
  - 读取 captured `layout2d`，
  - 通过 `baseFrame` 将 layout2d 转回目标世界坐标底面中心点，
  - 选中该组件已记录的底面，
  - 读取当前底面中心，
  - 计算 delta 并调用 `MoveComponent` 移动组件。

验证命令：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m py_compile scripts\apply_captured_common_base_layout.py scripts\capture_common_base_layout.py
```

验证结果：

- 编译通过，0 warning，0 error。
- Python 脚本语法检查通过。

真实测试状态：

- 发布到 `artifacts/solidworks-mcp` 时，旧 MCP exe 仍在运行，无法覆盖。
- 发布脚本自动创建了 `artifacts/solidworks-mcp-20260624-112354`。
- 使用新目录测试脚本时，工具尚未执行，MCP 连接阶段失败，原因是已有旧 Hub 正在运行。
- 该运行目录问题已记录到 `docs/to_be_continued.md`。

当前状态：

- 第一版根据 captured layout2d 移动组件的代码已完成。
- 真实 SolidWorks 验证需要先干净重启新版 MCP。

### 2026-06-24 11:34 CST - 第一版 layout2d 回放真实验证通过

执行命令：

```cmd
taskkill /IM SolidWorksMcpApp.exe /F
python scripts\apply_captured_common_base_layout.py --layout demo\captured_common_base_layout.json --assembly demo\ABC_arrange_demo.SLDASM --mcp-cwd artifacts\solidworks-mcp-20260624-112354 --screenshot demo\apply_captured_layout_result.png
```

发现并修复的问题：

- 第一次执行时，脚本把相对路径传给 MCP。
- MCP 会基于发布目录解析相对路径，因此找不到 `demo/captured_common_base_layout.json`。
- 已修改 `scripts/apply_captured_common_base_layout.py`，将 layout JSON、assembly path、screenshot path 转为绝对路径后再传给 MCP。

执行结果：

- `ApplyCapturedCommonBaseLayout` 成功完成。
- A/B/C 三个组件均返回 `moveResult.success=true`。
- B 按 captured layout 计算后移动约 `deltaY=-0.01000000000000002m`。
- 已导出截图 `demo/apply_captured_layout_result.png`。

当前状态：

- 第一版根据 captured layout2d 移动复原的端到端验证已通过。
- 后续仍需将该能力接入前端，并进一步清理中文 face name 的显示/编码问题。

### 2026-06-24 - layout2d 回放能力已接入前端

已完成：

- 后端新增 `POST /api/demo/apply-captured-layout`。
- 后端新增 `DemoService.apply_captured_layout()`，内部调用 MCP 工具 `apply_captured_common_base_layout`。
- 后端截图接口 `GET /api/demo/screenshot` 已调整为优先展示最近一次工具返回的截图路径。
- 前端新增 `applyCapturedLayout()` API。
- 前端工具栏新增 `Replay Layout` 按钮。
- 该按钮用于把 `demo/captured_common_base_layout.json` 中记录的 `layout2d` 回放到当前 `assemblyPath` 指向的装配体。

验证：

```cmd
python -m compileall apps\demo-backend\src scripts\apply_captured_common_base_layout.py
cmd /c npm.cmd run build
```

结果：

- 后端 Python 编译通过。
- 前端 TypeScript/Vite 构建通过。

当前状态：

- `layout2d` 回放能力已完成“脚本验证 + 前端按钮接入”。
- 下一步可以在真实 SolidWorks 会话中通过前端点击 `Replay Layout` 做一次 UI 级验证。

### 2026-06-25 - 已实现 Common Base 底面朝向感知的 mate 重试

目标：

- 修复 Common Base 当前核心遗留问题：重合配合可以让底面共面，但可能让目标组件的底面法向与基准组件相反，导致“底面朝上/朝下不一致”。

已实现：

- 修改 `DemoTools.FinalizeCommonBaseCore()`，让 `FinalizeCommonBaseAssembly` 使用带法向检查的底面配合流程。
- `MateBottomFacesToFirstComponent()` 新增可选 `normalDotThreshold` 参数。
- 在 `FinalizeCommonBaseAssembly` 中，先读取第一个组件底面的世界法向作为基准。
- 对后续组件，依次尝试三种 Coincident mate alignment：
  - `Closest`
  - `AntiAligned`
  - `None`
- 每次成功创建 mate 后，立即 rebuild，并重新读取目标组件底面法向。
- 如果目标法向与基准法向不一致，则调用 `Undo(1)` 撤销刚创建的 mate，并尝试下一种 alignment。
- 如果三种 alignment 都不能得到一致法向，则返回 `BottomFaceOrientationMismatch`，不再把错误朝向误报为成功。
- 旧的 `ArrangeComponentsOnCommonBase` 路径仍传入 `normalDotThreshold: null`，继续使用原有简单 mate 流程；本次改动主要约束在显式的 `FinalizeCommonBaseAssembly` 阶段。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

结果：

- 构建通过，0 warning，0 error。

当前状态：

- 代码层实现已完成。
- 已发布新版 MCP 到 `artifacts/solidworks-mcp-20260625-161303`，并复制 `face_mappings.json` 到该目录。
- 仍需要重启新版 MCP 后，在真实 SolidWorks 中验证。
- 如果 SolidWorks 对某些面组合的三种 alignment 都无法产生正确物理朝向，工具现在会明确失败，而不是错误地给出 base ready。

### 2026-06-25 - 已增强小面 normal fallback，并产品化 Capture Layout

目标：

- 提升小平面记录的鲁棒性，减少小面 `normal=null` 导致的面映射/共面验证失败。
- 将 Transform2/Layout2D 流程从“脚本可用”推进到“前后端可操作”，让捕获和回放都能通过前端按钮完成。

已实现：

- 修改 `SelectionService.TryGetPlanarFaceNormal()`：
  - 仍优先使用 `ISurface.PlaneParams`；
  - 如果 `PlaneParams` 失败，尝试读取 SolidWorks tessellation normal；
  - 如果 tessellation normal 也不可用，则尝试从 tessellated triangle points 拟合平面法向；
  - 如果 SolidWorks 能提供 `FaceInSurfaceSense()`，仍会做 face sense 修正。
- 新增 tessellation normal 拟合辅助逻辑。
- 新增 `SelectionServiceFaceNormalTests` 单元测试，覆盖：
  - 普通三角点数据拟合法向；
  - 带 stride 的 vertex record 数据拟合法向；
  - 退化三角形返回 null。
- 后端新增 MCP 工具常量 `CAPTURE_COMMON_BASE_LAYOUT_TOOL`。
- 后端新增接口 `POST /api/demo/capture-common-base-layout`。
- 后端新增 `DemoService.capture_common_base_layout()`，输出到 `demo/captured_common_base_layout.json`。
- 前端新增 `captureCommonBaseLayout()` API。
- 前端工具栏新增 `Capture Layout` 按钮，和 `Replay Layout` 形成“捕获布局 → 回放布局”的可操作流程。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter FullyQualifiedName~SelectionServiceFaceNormalTests
python -m compileall apps\demo-backend\src scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过，0 warning，0 error。
- 新增 normal fallback 单元测试通过：3/3。
- 后端 Python 编译通过。
- 前端 TypeScript/Vite 构建通过。
- 测试项目仍有既有 nullable warning，不来自本次新增测试文件。

发布：

- 已发布到 `artifacts/solidworks-mcp-20260625-163843`。
- 已复制 `face_mappings.json` 到该目录。

当前状态：

- 代码级实现和本地测试已完成。
- 仍需要在真实 SolidWorks 中验证：
  - 小面 fallback 是否能让真实小面记录出 normal；
  - 前端 `Capture Layout`；
  - 前端 `Replay Layout`；
  - 最新发布版本中的 Common Base 底面朝向一致性修复。

### 2026-06-25 - 发现 Common Base 朝向重试引发重复配合回归

现象：

- `Initialize` 后 A/B/C 均已导入成功，但 A/B 在 SolidWorks 中默认不显示，需要在组件树中手动设置显示。
- 执行 `Common Base` 后报错：

```text
FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.
```

- 用户在 SolidWorks 中观察到 A-B、A-C 之间似乎出现了重复定义的“重合”配合关系。

分析：

- 新增的 orientation-aware mate retry 流程为：

```text
AddMate -> ForceRebuild -> ProbeNormal -> mismatch -> Undo(1)
```

- 这里的风险是 `Undo(1)` 可能撤销的是 `ForceRebuild`，而不是刚创建的 mate。
- 这样会导致每次尝试 alignment 都留下一个 Coincident mate，最终造成重复配合。
- 这属于新功能对已通过基础功能的回归影响。

处理方向：

- 先恢复基础稳定性：不要在同一次 Common Base 中反复创建/撤销 mate。
- 短期修复为：每个目标组件只创建一次 Coincident mate，然后统一做 orientation probe/report。
- 如果方向不一致，仍返回清晰的 orientation mismatch，但不再产生重复 mate。
- 后续“自动修正底面朝向”应改为显式旋转组件，而不是通过反复添加/撤销 mate alignment 猜测 SolidWorks 行为。

### 2026-06-25 - Common Base 底面朝向显式旋转修正第一版

目标：

- 在不重复创建/撤销 mate 的前提下，尝试用 normal 向量计算显式旋转，自动修正 B/C 等组件的底面朝向。

已完成：

- 新增 `CommonBaseLayoutMath.CalculateNormalAlignmentRotation()`，根据源 normal 和目标 normal 计算旋转轴、旋转角。
- 新增 `DemoBottomOrientationCorrection`，让 `FinalizeCommonBaseAssembly` 返回每个组件的朝向修正尝试细节。
- `FinalizeCommonBaseAssembly` 新增修正流程：
  - 以第一个组件底面 `worldNormal` 作为基准；
  - 对后续组件先尝试按 normal 差异显式旋转；
  - 旋转后重新 probe 记录底面；
  - 如果正向角度失败，回滚并尝试反向角度；
  - 如果仍失败，回滚组件，不把失败尝试残留在装配体中；
  - 再执行单次 Coincident mate；
  - 最后统一返回 `orientationCorrections` 与 `orientationChecks`。
- 增加 `NormalizeComponentLayout()`，处理命令行 MCP runner 中中文 `底面` 被传成 `??` 的测试兼容问题。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- 构建通过。
- normal 计算与小面 normal fallback 相关单元测试通过：9/9。
- 后端编译通过。
- 前端构建通过。

真实 SolidWorks 验证结果：

- `InitializeCommonBaseAssembly` 成功创建并插入 A/B/C。
- `FinalizeCommonBaseAssembly` 仍失败，返回 `bottom face orientation mismatch`。
- B 的修正逻辑被触发，但旋转后重新 probe 记录底面时 normal 变为 `null`，无法确认修正成功，最终回滚。
- C 在 mate 前 normal 与 A 一致，但 mate 后最终检查又变为 mismatch，说明 Coincident mate 求解仍可能改变组件朝向。
- 未观察到此前“反复 mate retry 导致重复配合”的同类回归，说明重复配合风险已有缓解。

当前状态：

- 第一版显式旋转修正已经实现，并且失败时会回滚。
- 真实验证仍未通过，Common Base 底面朝向一致性仍是未完成项。
- 下一步建议改为：先 mate 共面，再做一次 mate 后朝向检查与显式旋转修正；同时增强旋转后面映射重新识别能力。

### 2026-06-26 - 已接入 mate 后 PostMate 二阶段朝向修正

目标：

- 避免“mate 前已经修正，但 Coincident mate 后又变向”的问题。
- 让 `FinalizeCommonBaseAssembly` 变成：先共面，再修正朝向，再最终检查。

已完成：

- 调整 `FinalizeCommonBaseAssembly` 内部顺序：
  - 先调用 `MateBottomFacesToFirstComponent()` 建立一次底面共面 mate；
  - `ForceRebuild`；
  - 再调用 `CorrectBottomFaceOrientations(..., stage: "PostMate")`；
  - 再次 `ForceRebuild`；
  - 最后调用 `ProbeBottomFaceOrientations()` 生成最终检查结果。
- `DemoBottomOrientationCorrection` 新增 `Stage` 字段。
- 当前修正只在 `PostMate` 阶段执行，方便真实日志定位问题。
- 保留失败回滚策略，避免失败修正残留错误姿态。

验证：

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- MCP app 构建通过，0 warning，0 error。
- normal/math 与小面 normal fallback 相关测试通过：9/9。
- 后端编译通过。
- 前端构建通过。

当前状态：

- 二阶段 PostMate 修正已完成代码接入。
- 尚未发布新版 MCP 做真实 SolidWorks 验证。
- 真实验证时需重点看 B/C 的最终 `orientationChecks` 是否匹配 A，以及是否出现重复 mate 或组件隐藏回归。

### 2026-06-26 - Common Base Timeout 后安全回退

现象：

- 点击 `Common Base` 后前端返回 `MCP execution failed: TimeoutError:`。
- MCP 日志显示 `FinalizeCommonBaseAssembly started` 后没有 completed。
- 后端默认 180 秒超时后返回错误。

原因判断：

- 新增的 PostMate 修正会在 Coincident mate 已经建立后尝试 `RotateComponent`。
- 这会让 SolidWorks 在已有配合约束下重新求解组件姿态，可能长时间卡住。

已修改：

- 为 `FinalizeCommonBaseAssembly` 新增实验开关 `enablePostMateOrientationCorrection`，默认 `false`。
- 默认 Common Base 现在只做：
  - 建立底面共面 mate；
  - rebuild；
  - probe orientation；
  - 快速返回结果。
- 如果朝向不一致，返回 `bottom face orientation mismatch`，但不会默认旋转已配合组件。

验证：

- MCP app 构建通过。
- 后端编译通过。
- 前端构建通过。
- 已重新发布并重启 MCP/后端。

当前状态：

- 系统已恢复到安全默认流程。
- 下一次点击 `Common Base` 预期不再 timeout。
- 自动修正朝向仍保留为实验能力，但默认不启用。

### 2026-06-26 - 方案 3：PreMate Transform2 朝向预修正已接入

目标：

- 实现自动朝向修正，同时避免在已有 mate 约束下直接旋转组件。
- 采用“先 Transform2 修正姿态，再建立 Coincident mate”的流程。

已修改：

- `FinalizeCommonBaseAssembly` 新增 `enablePreMateOrientationCorrection`，默认 `true`。
- `enablePostMateOrientationCorrection` 继续默认 `false`。
- 默认流程变为：
  - 读取已记录底面映射并 probe normal；
  - 以第一个组件 A 的底面 normal 为基准；
  - 在 mate 前对 B/C 进行 Transform2 旋转修正；
  - 修正后自动重新 probe normal；
  - 修正失败时回滚组件姿态；
  - 再建立底面 Coincident mate；
  - 最后执行 `orientationChecks`。
- 修正结果中的 `stage` 预期为 `PreMateTransform2`。

验证：

- MCP app 构建通过，0 warning，0 error。
- normal/math 与小面 normal fallback 测试通过：9/9。
- 后端编译通过。
- 前端构建通过。

当前状态：

- 代码级实现已完成。
- 尚未发布新版 MCP 做真实 SolidWorks 验证。
- 如果真实验证仍出现 `normal=null`，下一步需要增强“旋转后根据候选面重新识别底面”的 fallback。

### 2026-06-26 - 后续联调基础设施计划：direct stdio MCP

背景：

- 当前 `Common Base` 真实验证的主要阻碍已从几何逻辑转为 MCP 启动/连接链路。
- Hub/proxy 模式多次受到 Device Guard、命名管道权限、进程会话差异影响。

计划：

- 后续新增 MCP direct stdio 模式，让后端直接启动 MCP 子进程。
- 该模式将作为前后端 demo 联调的推荐路径。
- Hub/托盘模式保留，用于桌面常驻使用。

当前影响：

- PreMate Transform2 朝向预修正代码已经完成。
- 在 direct stdio 模式实现前，真实验证仍可通过手动启动 Hub + 后端尝试，但稳定性较差。

### 2026-06-26 - Common Base 超时原因确认

观察结果：

- 前端显示 `error / base pending` 和 `MCP execution failed: TimeoutError:`。
- 后端状态文件写入 error，`commonBaseReady=false`。
- MCP Hub 日志显示 `FinalizeCommonBaseAssembly` 从 16:42:48 执行到 16:46:02，耗时约 194.6 秒后完成。

结论：

- 后端默认 timeout 为 180 秒，短于本次 SolidWorks 实际执行耗时。
- 因此前端看到的是后端等待 MCP 结果超时，而不是 MCP 工具完全没有返回。
- MCP 工具真实返回为 `bottom face orientation mismatch`，说明共底面/朝向一致性仍未通过最终检查。

下一步：

- 重启后端时设置 `DEMO_MCP_TIMEOUT_SECONDS=420`。
- 再执行一次 `Common Base`，让后端完整拿到 MCP 返回的 orientation correction/check 结果。
- 随后根据具体 `orientationChecks` 判断是 PreMate Transform2 未生效，还是 mate 后求解改变了组件朝向。

### 2026-06-26 - 朝向诊断结果已接入后端状态与前端展示

目标：

- 解决 `Common Base` 失败时只能看到 `bottom face orientation mismatch`，无法判断具体失败组件的问题。
- 让下一次运行后可以直接查看 B/C 是否尝试修正、修正前后 normal，以及最终谁没有匹配 A 的底面法向。

已完成：

- 后端 `DemoService._last_run_from_payload()` 已保存：
  - `orientationCorrections`
  - `orientationChecks`
  - `missingFaceMappings`
- 前端 `api.ts` 已补充 `OrientationCorrection`、`OrientationCheck`、`FaceProbe` 类型。
- 前端结果区新增 `Orientation` 诊断面板：
  - `Corrections` 展示阶段、是否应用、旋转角度、旋转轴、修正前/后 world normal、消息。
  - `Checks` 展示每个组件是否匹配基准、dot 值、阈值、最终 world normal、消息。

验证：

```cmd
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- 后端编译检查通过。
- 前端 TypeScript/Vite 构建通过。

下一步：

- 重启后端与前端。
- 再执行 `Common Base`。
- 查看前端 `Orientation` 面板或 `demo/demo_state.json` 中的 `orientationCorrections` / `orientationChecks`，定位具体 mismatch 来源。

### 2026-06-26 - 面映射移动鲁棒性现状与新问题确认

现状：

- 此前已实现过“组件移动后面映射仍可找回”的第一版能力。
- `RecordFaceMapping` 当前记录：
  - leaf component short/full name；
  - leaf-local center；
  - local/world normal；
  - area。
- `SelectFaceByName` 当前逻辑：
  - 根据 leaf full name 找到真实叶子组件；
  - 只扫描该 leaf component 的 bodies/faces；
  - 用 leaf-local center 距离作为主评分；
  - area mismatch 作为小权重惩罚；
  - localNormal dot 作为小权重惩罚。

本次真实运行暴露的新问题：

- B/C 在 `Common Base` 后最终 `orientationChecks` 选中的面 area 明显小于记录底面：
  - B 记录 area 约 `0.009411`，最终 probe area 约 `0.000960`；
  - C 记录 area 约 `0.006229`，最终 probe area 约 `0.001248`。
- 这说明当前选面 fallback 确实能在“移动”后工作，但在“旋转 + mate 求解”后仍可能选到相邻小面/侧面。
- 当前评分里 area 和 normal 的权重偏弱，中心点在旋转/配合后又可能靠近多个候选面，因此容易误选。

下一步建议：

1. 增强 `SelectFaceByName` 候选面评分：
   - area 误差从小权重改为强过滤或强惩罚；
   - localNormal dot 从小权重改为强过滤；
   - leaf full name 必须匹配；
   - 当最佳候选 area/normal/center 超出阈值时返回失败，而不是返回 `Success=true`。
2. 在 `FaceMappingResult` 或新增诊断结果中返回候选面评分摘要，方便判断为什么选中了某个面。
3. 在 `Common Base` 中，如果 SelectFaceByName 选面后 probe 发现 area/normal 与记录值不一致，应中止并提示重新记录或触发候选扫描 fallback。
4. 统一 `face_mappings.json` 路径，避免后端检查和 MCP 实际选面使用不同映射文件。

### 2026-06-26 - SelectFaceByName 强校验与候选面诊断已实现

目标：

- 避免 `SelectFaceByName` 在旋转/mate 后误选相邻小面仍返回 `Success=true`。
- 让错误在选面阶段暴露，而不是继续进入 mate 和 orientation check。

已完成：

- 扩展 `FaceMappingResult`，新增可选 `Diagnostics`。
- 新增：
  - `FaceMappingSelectionDiagnostics`
  - `FaceMappingCandidateDiagnostic`
- `SelectFaceByName` 现在会返回 top candidates 诊断，包括：
  - rank；
  - score；
  - center distance；
  - area；
  - area relative error；
  - normal dot；
  - local center；
  - local normal；
  - reject reason。
- 候选面强校验阈值：
  - local center 距离 `<= 0.002m`；
  - area 相对误差 `<= 0.05`；
  - local normal dot `>= 0.95`。
- 如果最佳候选不满足阈值，`SelectFaceByName` 返回失败，并在 `Diagnostics.FailureReason` 中说明原因。

验证：

```cmd
dotnet build vendor\solidworks-mcp\bridge\SolidWorksBridge\SolidWorksBridge.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

结果：

- `SolidWorksBridge` 构建通过。
- 后端编译检查通过。
- 前端构建通过。
- 完整 MCP App 构建暂时被正在运行的 `.NET Host (124880)` 锁住输出 DLL，需停止旧 MCP 后再发布/验证。

下一步：

- 停止旧 MCP Hub。
- 重新构建/启动新版 MCP。
- 重新执行 `Common Base`。
- 如果 B/C 仍被选错，预期会在 `faceSelection.diagnostics` 中直接看到最佳候选为什么被拒绝。

### 2026-06-26 - SelectFaceByName 强校验真实验证结果

测试动作：

- 停止旧 MCP Hub。
- 构建新版 MCP App。
- 后台启动新版 MCP Hub。
- 调用后端：
  - `POST /api/demo/reset`
  - `POST /api/demo/initialize-common-base`
  - `POST /api/demo/finalize-common-base`

验证结果：

- `InitializeCommonBaseAssembly` 成功重新生成 `demo/ABC_arrange_demo.SLDASM`。
- `FinalizeCommonBaseAssembly` 返回：

```text
FinalizeCommonBaseAssembly completed with bottom face orientation probe errors.
```

- 初始选面与 mate：
  - A-1 face selection 成功；
  - B-1 face selection 成功，`swAddMateError_NoError`；
  - C-1 face selection 成功，`swAddMateError_NoError`。
- PreMate 修正：
  - B-1 触发旋转修正，但修正验证失败并回滚；
  - C-1 未旋转，因为 mate 前 normal 已匹配 A。
- 最终 orientation check：
  - A-1 成功，`matchesBase=true`；
  - B-1 被强校验拦截，`faceSelection.success=false`，原因：

```text
center distance 0.407875m > 0.002000m
```

  - C-1 被强校验拦截，`faceSelection.success=false`，原因：

```text
center distance 0.280773m > 0.002000m
```

结论：

- 强校验已经生效：它没有继续把明显偏离记录位置的候选面当作底面。
- 当前失败已经从“误选小面后继续 mate/orientation mismatch”升级为“选面阶段明确失败并给出诊断”。
- 更深层问题是：组件旋转/mate 后，记录的 leaf-local center 与真实候选面 local center 发生大偏移，说明当前基于 leaf-local center 的映射无法覆盖这种姿态变化。

下一步：

1. 优先统一 `face_mappings.json` 路径，避免记录文件漂移。
2. 评估改用更稳定的 face persistent reference。
3. 或在 Transform2 旋转/配合后更新映射中的 localCenter，再做后续 probe。
4. 如果暂时不做 persistent reference，可为 Common Base 专门保存“共面前/后映射快照”，避免旋转后仍用旧 localCenter 作为强约束。

### 2026-06-26 - face_mappings 路径统一与 Persistent Reference 第一版

目标：

- 让后端和 MCP 使用同一份 `face_mappings.json`，避免“后端检查通过，但 MCP 实际读取另一份映射”的漂移。
- 在记录面时尝试保存 SolidWorks Persistent Reference，后续优先通过持久引用找回同一个 `IFace2`。
- 在真实验证中确认新增逻辑不会破坏当前 Initialize / Common Base 链路。

已完成：

- 后端默认 `DEMO_FACE_MAPPING_PATH` 已统一为：

```text
artifacts\solidworks-mcp\face_mappings.json
```

- `SelectionService` 已支持：
  - 通过 `DEMO_FACE_MAPPING_PATH` 解析映射文件路径；
  - 保存映射前自动创建目录；
  - `RecordFaceMapping` 记录 `persistentReferenceBase64`；
  - `SelectFaceByName` 优先通过 `persistentReferenceBase64` 调用 SolidWorks `GetObjectByPersistReference3` 找回面；
  - Persistent Reference 失败时继续回退到当前的几何候选面强校验。
- `DemoTools.HasFaceMapping` 已改为读取同一环境变量路径。
- `InitializeCommonBaseAssembly` 增加已有 assembly 复用逻辑：
  - 如果 `demo\ABC_arrange_demo.SLDASM` 已存在，则打开/复用该文件；
  - 不再盲目新建 assembly 后覆盖保存，避免 SolidWorks `SaveAs3` 因同名文件已打开而失败。

验证：

```cmd
python -m compileall apps\demo-backend\src
dotnet build vendor\solidworks-mcp\bridge\SolidWorksBridge\SolidWorksBridge.csproj -c Release
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

结果：

- 后端编译检查通过。
- `SolidWorksBridge` 构建通过。
- `SolidWorksMcpApp` 构建通过。
- 已启动新版 MCP Hub，并显式设置：

```text
DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

- 后端 `/api/health` 显示 `faceMappingPath` 已指向统一路径。
- 自动接口验证：
  - `POST /api/demo/reset` 成功；
  - `POST /api/demo/initialize-common-base` 成功，返回已有 `ABC_arrange_demo.SLDASM` 被复用；
  - `POST /api/demo/finalize-common-base` 仍返回面映射/朝向 probe 错误。

本次重要结论：

- 路径统一已生效，最新 probe 中 `mappingPath` 指向：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

- 当前 A/B/C 映射是旧数据，还没有 `persistentReferenceBase64` 字段，因此这次 Common Base 仍走几何 fallback。
- B/C 在已发生姿态变化的 assembly 中仍无法通过强校验：
  - B-1 最佳候选被拒绝：`center distance 0.407875m > 0.002000m`
  - C-1 最佳候选被拒绝：`center distance 0.280773m > 0.002000m`
- 这说明 Persistent Reference 代码已接入，但需要在干净状态下重新记录底面后，才能真实验证“通过持久引用找回同一个面”的效果。

下一步：

1. 在干净的初始化状态下重新记录 A/B/C 底面，使映射文件写入 `persistentReferenceBase64`。
2. 再执行 Common Base，验证 `SelectFaceByName` 是否优先通过 Persistent Reference 成功选回原始面。
3. 若 Persistent Reference 在装配体保存/重开后仍失效，则实现 post-common-base face mapping snapshot，作为 Common Base 后的自动刷新映射。

### 2026-06-29 - A-1 底面 Persistent Reference 记录验证

- 已通过后端新增的 `POST /api/demo/record-selected-face` 调试接口，记录当前 SolidWorks 中已选中的 A-1 底面。
- 已确认 `artifacts\solidworks-mcp\face_mappings.json` 中 A-1 的 `底面` 映射写入了 `persistentReferenceBase64`。
- 发现 Windows PowerShell / here-string 中直接传中文 `底面` 时，参数可能在进入 MCP 前变成 `??`。
- 已在后端增加临时修复：当 MCP 写出 `??` 映射键时，如果后端请求的原始 `faceName` 是 `底面`，会将 `??` 下的新映射搬回 `底面`。
- 实测使用 ASCII Unicode escape 发送 `\u5e95\u9762` 后，A-1 的 `底面` 键已正确带有 Persistent Reference。

下一步：

1. 继续在 SolidWorks UI 中手动选中 B-1 真实底面并记录。
2. 再选中 C-1 真实底面并记录。
3. 确认 A/B/C 的 `底面` 均含 `persistentReferenceBase64` 后，再执行 Common Base。

### 2026-06-29 - Persistent Reference + Common Base 真实验证通过

测试动作：

- 手动在 `ABC_arrange_demo.SLDASM` 中依次选中 A/B/C 的真实底面。
- 通过后端 `POST /api/demo/record-selected-face` 记录三者底面。
- 确认 `artifacts\solidworks-mcp\face_mappings.json` 中：
  - A-1 `底面` 含 `persistentReferenceBase64`；
  - B-1 `底面` 含 `persistentReferenceBase64`；
  - C-1 `底面` 含 `persistentReferenceBase64`。
- 通过后端接口执行：

```text
POST /api/demo/finalize-common-base
```

验证结果：

- 后端返回：

```text
status=ok
commonBaseReady=true
```

- `orientationChecks`：
  - A-1：`matchesBase=true`，通过 Persistent Reference 选中底面；
  - B-1：`matchesBase=true`，通过 Persistent Reference 选中底面；
  - C-1：`matchesBase=true`，通过 Persistent Reference 选中底面。
- `orientationCorrections`：
  - B-1：`PreMateTransform2` 未旋转，提示底面 normal 已匹配；
  - C-1：`PreMateTransform2` 未旋转，提示底面 normal 已匹配。

结论：

- Persistent Reference 已解决此前 Common Base 后 B/C 旧几何映射出现 `center distance ... > 0.002m` 的核心问题。
- 当前版本已经能在 A/B/C 三个底面重新记录后，稳定完成 Common Base。
- 下一步可继续验证 `Replay Layout`，确认共底面成功后再根据 layout2d 移动复原。
### 2026-06-29 - Replay Layout 后端真实验证通过

测试动作：

- 在 `Common Base` 已完成且 `commonBaseReady=true` 的状态下，检查 `demo/captured_common_base_layout.json`。
- 确认捕获数据有效：
  - `success=true`
  - `baseComponentName=A-1`
  - 共 3 个组件：A-1、B-1、C-1
  - `layout2d` 中 A 位于原点，B/C 有相对二维布局坐标。
- 通过后端接口执行：

```text
POST /api/demo/apply-captured-layout
```

验证结果：

- 后端返回：

```text
status=ok
lastRunStatus=ok
commonBaseReady=true
```

- MCP 返回：

```text
ApplyCapturedCommonBaseLayout completed.
```

- A/B/C 均通过 Persistent Reference 选回底面。
- A/B/C 的移动均返回成功。
- 已生成结果截图：

```text
demo\apply_captured_layout_result.png
```

结论：

- 当前版本已经跑通“Common Base 后，根据已捕获 layout2d 移动复原组件位置”的后端核心链路。
- Persistent Reference 对 Replay Layout 阶段仍然有效，未再出现此前 B/C 因几何映射漂移导致的选面失败。
- 下一步建议在 SolidWorks UI 中人工确认最终位置效果，并通过前端 `Replay Layout` 按钮做一次端到端验证。
### 2026-06-29 - X_reference 制作尝试被 MCP Hub/Proxy 链路阻塞

目标：

- 基于当前已共底面的 `ABC_arrange_demo.SLDASM`。
- 在不破坏共底面的前提下，对 B-1/C-1 做平面内移动与绕底面法向旋转。
- 另存为：

```text
demo\X_reference.SLDASM
```

- 从 `X_reference.SLDASM` 捕获新的 layout2d：

```text
demo\x_reference_layout2d.json
```

本次执行情况：

- 已设计待执行 MCP 计划：
  1. `OpenDocument(ABC_arrange_demo.SLDASM)`
  2. `MoveComponent(B-1, dx=0.04, dy=0, dz=0.03)`
  3. `RotateComponent(B-1, axis=(0,-1,0), angle=20deg)`
  4. `MoveComponent(C-1, dx=-0.03, dy=0, dz=0.04)`
  5. `RotateComponent(C-1, axis=(0,-1,0), angle=-15deg)`
  6. `SaveDocumentAs(demo\X_reference.SLDASM, saveAsCopy=true)`
  7. `CaptureCommonBaseLayoutFromAssembly(..., output=demo\x_reference_layout2d.json)`
- 实际执行时，后端正式接口和临时 MCP 计划均失败于 MCP 连接阶段：

```text
MCP execution failed: McpProtocolError: Unhandled exception.
System.IO.IOException: The server shut down unexpectedly.
```

- 尝试重启 MCP Hub 后，日志显示 Hub 启动过，但随后命名管道不可用：

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

- 因此本次未生成：

```text
demo\X_reference.SLDASM
demo\x_reference_layout2d.json
demo\x_reference_result.png
```

结论：

- 当前阻塞点不是 CAD 操作逻辑，而是 MCP Hub/Proxy 连接链路不稳定。
- 在 MCP Hub 管道恢复前，无法继续自动移动/旋转/保存 SolidWorks 文档。
- 恢复后可直接复用本节中的 MCP 计划继续制作 `X_reference`。

### 2026-06-29 - MCP 直连链路稳定化与 X_reference 验证通过

本次修复目标：

- 降低对 `SolidWorksMcpHub` 命名管道和托盘会话的依赖。
- 修复 `dotnet SolidWorksMcpApp.dll --proxy` 场景下自动拉起 Hub 不稳定的问题。
- 继续完成此前被阻塞的 `X_reference` 制作、旋转、保存和 layout2d 捕获流程。

完成的代码修改：

- `SolidWorksMcpApp` 新增 `--stdio-direct` 模式，后端自动化可直接通过 MCP stdio 调用工具，不再经过 Hub/proxy。
- `SolidWorksMcpApp` 新增 `--headless-hub` 模式，用于在需要命名管道时启动无托盘 Hub。
- 修复 DLL 启动模式下 proxy 自动启动 Hub 的问题：之前 `Environment.ProcessPath` 指向 `dotnet.exe`，可能只启动裸 `dotnet`，导致 `server shut down unexpectedly`。
- 后端默认 MCP 参数改为：当 `DEMO_MCP_COMMAND=dotnet` 且 `DEMO_MCP_CWD` 指向包含 `SolidWorksMcpApp.dll` 的目录时，自动使用 `SolidWorksMcpApp.dll --stdio-direct`。
- `McpToolRunner` 增加 stdin BOM 容错，避免 PowerShell 临时调试命令因 BOM 报 JSON 解析错误。

验证结果：

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
- `dotnet build apps\demo-backend\tools\McpToolRunner\McpToolRunner.csproj -c Release` 通过。
- `python -m compileall apps\demo-backend\src` 通过。
- 通过 direct stdio MCP 链路执行了：
  1. 打开 `demo\ABC_arrange_demo.SLDASM`；
  2. 对 B-1 / C-1 执行平面内移动；
  3. 对 B-1 / C-1 绕共同底面法向旋转；
  4. 另存为 `demo\X_reference.SLDASM`；
  5. 从 `X_reference.SLDASM` 捕获 layout2d 到 `demo\x_reference_layout2d.json`；
  6. 打开 `X_reference.SLDASM` 并导出截图 `demo\x_reference_result.png`。

生成文件：

```text
demo\X_reference.SLDASM
demo\x_reference_layout2d.json
demo\x_reference_result.png
```

关键观察：

- `x_reference_layout2d.json` 中 `success=true`。
- A/B/C 均通过 Persistent Reference 选回底面。
- B/C 的 `sourceTransform` 已体现旋转矩阵，说明旋转动作确实进入布局捕获数据。
- A/B/C 的底面 world normal 仍接近共同方向 `[0, -1, 0]`，说明本次绕共同底面法向旋转没有破坏共底面关系。

结论：

- 本次主要不稳定源是 MCP Hub/proxy 启动链路，而不是本次 CAD 操作计划本身。
- 当前已经有一条更稳定的后端自动化路线：`McpToolRunner -> dotnet SolidWorksMcpApp.dll --stdio-direct -> SolidWorks COM`。
- 旋转操作仍有 CAD 约束层面的长期风险，但本次在“已共底面、绕底面法向旋转”的场景下验证通过。

### 2026-06-29 - X_reference_spread 对照组与 layout2d 重新捕获

目标：

- 在 `X_reference.SLDASM` 的基础上，让 B-1 / C-1 在保持底面共面的前提下继续产生明显位置差异。
- 重新捕获 layout2d，作为后续“新 assembly 中恢复参考布局”的目标数据。

执行动作：

- 由于当前共同底面法向接近全局 `Y` 方向，本次只沿全局 `X/Z` 移动，避免沿 `Y` 破坏共面。
- 对 B-1 执行：

```text
deltaX=0.12, deltaY=0, deltaZ=0
```

- 对 C-1 执行：

```text
deltaX=-0.10, deltaY=0, deltaZ=0.06
```

- 因 `X_reference.SLDASM` 处于已打开/共享状态，直接保存原文件返回 read-only save error；因此另存为：

```text
demo\X_reference_spread.SLDASM
```

过程中发现并修复：

- 初次捕获时，B/C 的 `sourceTransform` 已变化，但 `layout2d` 没变化。
- 根因是 `GetSelectedFaceMappingProbe` 将 `IFace2.GetBox()` 的中心直接当成 world center 使用；在嵌套子装配体场景中，该中心更接近 leaf/local 坐标，顶层组件移动后不会正确反映到 world center。
- 已修复为：
  - `localCenter = BoxCenter(face.GetBox())`
  - `worldCenter = leafComponent.GetTotalTransform(true) * localCenter`
  - normal 也优先使用 total transform 转到 world。

验证结果：

- 重新构建 `SolidWorksMcpApp` 通过。
- 重新捕获 `demo\x_reference_layout2d.json` 成功，`success=true`。
- 输出截图：

```text
demo\x_reference_spread_result.png
```

捕获到的关键 layout2d：

```text
A-1: x=0, y=0
B-1: x=0.552681, y=0.180535
C-1: x=0.258654, y=0.144401
```

共面验证：

- A/B/C 的 `bottomCenterWorld.Y` 均约为 `-0.499264`。
- A/B/C 的 `bottomNormalWorld` 均接近 `[0, -1, 0]`。

结论：

- 已获得一个更适合后续恢复测试的参考装配体：

```text
demo\X_reference_spread.SLDASM
```

- 已获得对应目标布局：

```text
demo\x_reference_layout2d.json
```

- 下一步可以在新的空白 assembly 中导入 A/B/C，执行 Common Base，然后 Replay 这份 layout2d，验证是否能恢复到 `X_reference_spread` 的布局。

### 2026-06-29 - 新 Assembly 闭环 Replay Layout 验证通过

测试目标：

- 新建空白 assembly。
- 导入 A/B/C。
- 执行 Common Base。
- Replay `demo\x_reference_layout2d.json`。
- 再次捕获 replay 后的 layout2d，与 `X_reference_spread` 的目标 layout2d 对比。

生成文件：

```text
demo\ABC_replay_from_x_reference.SLDASM
demo\abc_replay_initialize.png
demo\abc_replay_common_base.png
demo\abc_replay_from_x_reference_result.png
demo\abc_replay_from_x_reference_layout2d.json
```

执行结果：

- `InitializeCommonBaseAssembly` 成功。
- `FinalizeCommonBaseAssembly` 成功。
- B-1 在 Common Base 阶段触发 `PreMateTransform2` 自动朝向修正，最终 `orientationChecks` 通过。
- A/B/C 均通过 Persistent Reference 找回底面。
- `ApplyCapturedCommonBaseLayout` 成功。

中途发现并修复：

- 第一次 replay 后重新捕获 layout2d，与目标值不一致。
- 原因是 `ApplyCapturedCommonBaseLayout` 仍使用旧的 `GetSelectedFaceCenter()`，该接口返回的中心没有经过 `GetTotalTransform(true)` 转换。
- 已改为使用 `GetSelectedFaceMappingProbe().WorldCenter` 作为当前底面中心。

最终数值对比：

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

- “从参考装配体捕获 layout2d -> 新建 assembly 导入组件 -> 共底面 -> replay layout2d 恢复位置”的核心闭环已经跑通。
- 当前 replay 验证的是底面中心的 2D 位置恢复；组件自身旋转姿态的完整恢复仍属于后续 Transform2 姿态回放增强。

### 2026-06-29 - Layout2D 平面内旋转 theta 回放闭环通过

目标：

- 在已有 `layout2d.x/y` 位置恢复基础上，增加 `layout2d.thetaDegrees/thetaAxis`。
- 捕获参考装配体中组件绕共底面法向的平面内旋转。
- 在新建 assembly 中执行 Common Base 后，同时恢复底面中心位置和组件平面内旋转。

实现要点：

- `CommonBaseLayout2d` 新增：
  - `ThetaDegrees`
  - `ThetaAxis`
- 捕获 layout 时同时保存组件 `Transform2` 的 `XAxis/YAxis/ZAxis`。
- 由于某些组件的 `XAxis` 可能接近共底面法向，不能固定使用 X 轴表示 theta。
- 新增 `ProjectPointWithRotation()`，会从 X/Y/Z 中选择投影到共底面上长度最大的轴作为 `thetaAxis`。
- 回放 layout 时：
  1. 读取当前组件对应 `thetaAxis` 的 Transform2 轴向；
  2. 计算当前 theta 与目标 theta 的差值；
  3. 先绕 `baseFrame.Normal` 做平面内旋转；
  4. 重新 probe 底面中心；
  5. 再执行平移，使底面中心到达目标 `layout2d.x/y`。

中途发现并修复：

- 第一次真实闭环中，x/y 位置完全恢复，但 theta 符号相反：
  - B-1 目标 `-20deg`，实际 `+20deg`。
  - C-1 目标 `+15deg`，实际 `-15deg`。
- 判断原因是 `RotateComponent` 的角度正方向与 layout 投影数学正方向相反。
- 为避免影响其他已有旋转功能，仅在 `ApplyCapturedCommonBaseLayout` 的 theta 回放中对角度取反。

验证：

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
- 新增 `CommonBaseLayoutMathTests` 用例，但 `dotnet test` 被 Windows 应用控制策略阻止加载测试 DLL，不是断言失败。
- 真实 SolidWorks 闭环验证通过：

```text
参考布局：demo\x_reference_layout2d_theta.json
回放装配体：demo\ABC_replay_from_x_reference_theta_signfix.SLDASM
回放后捕获：demo\abc_replay_from_x_reference_theta_signfix_layout2d.json
```

最终对比：

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

结论：

- “捕获参考装配体 layout2d 位置 + theta -> 新建 assembly -> Common Base -> Replay Layout2D 位置与平面内旋转”的闭环已跑通。
- 当前 theta 表示的是选定组件 Transform2 轴在共底面上的投影角，不等价于完整 3D 姿态恢复；但已满足“在共底面上按 layout2d 恢复平面布局和朝向”的阶段目标。

### 2026-06-30 - 演示版本提交前工程链路整理

目标：

- 演示版本已完成后，先稳定工程链路，再本地 commit，暂不 push。
- 降低 `git status` 噪音，避免误提交临时 CAD 文件、截图、运行日志和 IDE 缓存。
- 补齐复现说明，便于后续自己回归测试或整理 PR。

完成内容：

- 更新 `.gitignore`：
  - 忽略 `demo/**/*.SLDASM`、`demo/*.png`、`demo/*.json` 中间产物。
  - 仅放行最终 layout 样例：
    - `demo/x_reference_layout2d_theta.json`
    - `demo/abc_replay_from_x_reference_theta_signfix_layout2d.json`
  - 忽略 `logs/`、`apps/demo-frontend/tsconfig.tsbuildinfo` 和根目录临时文件。
- 更新 `apps/demo-backend/README.md`：
  - 改为当前稳定的 direct stdio MCP 链路说明。
  - 更新后端启动、health check 和主要接口列表。
- 更新 `apps/demo-frontend/README.md`：
  - 更新前端演示流程说明。
  - 明确推荐顺序：`Reset -> Initialize -> Common Base -> Capture Layout -> Replay Layout`。
- 新增提交前清单：
  - `docs/demo_stabilization_checklist-CN.md`
  - `docs/demo_stabilization_checklist.md`

验证：

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py apps\demo-backend\src
```

结果：

- build 通过，0 error。
- Python compileall 通过。

当前提交策略建议：

- 先本地 commit，不 push。
- 提交源码、脚本、测试、文档、`.gitignore` 和两份最终 layout JSON 样例。
- 不提交 CAD 二进制、截图、日志、runtime state 和缓存文件。
