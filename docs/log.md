# 操作记录

## 2026-08-17 - 完整原型 Replay 与分层静态干涉检查

1. 从完整项目02原型另存 `demo/FL9A24D062A000_prototype_replay_solved_v1.SLDASM`，应用八模组求解位姿；Replay 8/8、重建成功、保存 0 错误/0 警告，源原型未覆盖。
2. 新增 `scripts/prepare_project02_prototype_brep.py`，从完整原型的顶层组件中精确提取八个求解实例，并根据 `staticCollisionPolicy` 对全部 28 对进行实际 AABB 路由。
3. 宽阶段得到 11 对直接通过、0 对严格失败、17 对需精确 B-Rep；没有把 AABB 重叠误报为实体干涉。
4. 分六批完成 17/17 对全量叶级 B-Rep；13 对无干涉，4 对有干涉：A100–A180（1）、A180–A200（6）、A200–A800（1）、A300–A800（8），合计 16 对叶实体。
5. 新增 `scripts/summarize_project02_prototype_brep.py`，校验候选覆盖、完整性和意外结果，并输出 `demo/layout_previews/project02_prototype_replay_solved_v1_brep_summary.json`。最终状态为 `STATIC_COLLISION_INTERFERENCE_FOUND`，不能声明静态闭环。
6. 自动创建的隔离 SolidWorks 实例均在每批保存结果后按精确 PID 结束；用户原有 PID 41896 未受影响。

## 2026-08-17 - 从空白装配体生成纯八模组求解结果

1. 用户根据预览图指出历史“8 components”装配体仍含底座箱体。复核确认 `static_collision_v2` 从 `joint_v24` 另存而来，而 `joint_v24` 已含底座/机架；旧 8/8 统计只覆盖指定模组，不是全装配树审计。
2. 新增 `scripts/build_clean_project02_solution.py`，禁止复制任何现有容器；从空白装配体插入八个白名单源文件，并在 Replay 前后调用 `list_components` 核对数量、名称和绝对源路径。
3. 为避免 SolidWorks 自动固定首组件导致姿态不可改，以目标姿态为单位矩阵的 A200 作为首个组件，并在目标原点插入；随后对其余组件应用完整姿态和求解位置。
4. 新增 `apps/demo-backend/tests/test_clean_project02_solution.py`，4/4 通过：精确八组件通过、A200 首组件检查、残留底座拒绝、错误源路径拒绝；脚本 `py_compile` 通过。
5. 实机使用隔离 SolidWorks 会话构建成功：空白新建、8/8 插入、Replay 8/8、保存错误 0、警告 0、最终 `Fully Rebuilt`。Replay 前后审计均为实际顶层 8 个，无 extra/missing/duplicate/path mismatch。
6. 输出 `demo/FL9A24D062A000_8modules_clean_solved_v1.SLDASM`（约 45.6 MB）、主截图、六向视图和机器摘要。目测确认底座箱体不再存在。
7. 本轮没有执行全量叶级 B-Rep；交付状态为 `CLEAN_EIGHT_MODULE_REPLAY_SAVED_VISUAL_REVIEW_PENDING`，下一道闸门是用户目测选择是否继续定向精检。

## 2026-08-17 - 项目02静态碰撞 v2 Replay、保存回读与宽相闭环

1. Windows 重启后确认没有 `SLDWORKS.exe`，使用单 MCP 计划启动 SolidWorks、打开 v24 八模组容器、另存新目标、Replay、保存并导出主截图和六向视图；原型和 v24 均未覆盖。
2. v1 首次执行因启动包未携带 `face_mappings.json`，8 个底面全部未选择，业务 Replay 失败；修正脚本后会同时检查 MCP `isError` 和业务 `success=false`，v1 结果已明确标记为失败，不得作为求解装配体使用。
3. v2 显式传入 `artifacts/solidworks-mcp/face_mappings.json` 并在 Replay 前读取映射存储信息。8/8 底面选择、探测与移动成功；目标文件保存错误0、警告0，最终重建状态 Fully Rebuilt。
4. 真实保存回读 8/8 通过：最大 XY 误差 `3.954489072310906e-08 m`，最大角度误差 `2.842170943040401e-14°`，无缺失或额外组件。
5. 真实世界 AABB 宽相 28/28 完成：10 对严格 AABB 失败0，未分类0；11对无需 B-Rep，17对进入精确候选，减少比例39.29%。A800与A100实际投影覆盖率约86.80%，A200约88.16%，A700及其余要求完整包含的功能模组均为100%。
6. 六向视图目测未发现传输完全位于龙门外、功能模组明显越界、供胶压入龙门等粗大错误；A200–A500、A500–A700、A700–A800等密集区域仍须精确检查。当前停在用户目测闸门，不执行 B-Rep。
7. 每次独立直接 MCP 会话仍会由 DCOM 启动一个新的无窗口 SolidWorks；本轮 Replay、v2修正与保存回读分别留下3个实例。后续应把回读与B-Rep并入同一个长生命周期会话，避免继续增加实例。

正式粗布局文件：`demo/FL9A24D062A000_8components_static_collision_v2.SLDASM`。机器摘要：`demo/layout_previews/project02_static_collision_v2_closure_summary.json`。

## 2026-08-17 - 项目02新解 Replay 尝试被 DCOM 会话隔离阻断

1. 用户打开空白 SolidWorks 2024 SP5 会话后，MCP `solid_works_connect` 返回版本、许可证和 COM 连接成功；`list_documents=[]`、`get_active_document=null`，证明开始时没有打开文件。
2. 为选中方案增加通用 A500 锚点转换参数，成功生成 `demo/layout_previews/project02_selected_solution_replay.json`；8 个模组的相对布局不变，A500 被平移到 Replay 原点。
3. 新增 `scripts/replay_project02_selected_solution.py`，把“连接、打开8模组容器、另存新目标、Replay、保存、单视图截图、六视图截图”放入同一个 MCP 会话，避免跨 MCP 调用丢失活动文档。
4. 实机检查发现短生命周期 MCP 调用没有复用用户可见的 PID 74392，而是由 Windows DCOM 父进程 PID 1260 依次启动 PID 74484、82104、40404、78704 四个无窗口 SolidWorks 实例。系统同时拒绝 `Stop-Process` 和 `taskkill` 终止这些高权限实例。
5. 常驻 MCP Hub 虽可建立命名管道连接，但未进入 MCP `initialize/tools/call`，只读健康检查超过60秒无返回后已主动中止。
6. 本轮没有运行 Replay，没有创建 `demo/FL9A24D062A000_8components_static_collision_v1.SLDASM`，没有修改原型或 v24 容器。必须先由管理员任务管理器清理全部 SolidWorks/DCOM 残留，或重启 Windows，再只启动一个普通权限 SolidWorks 和匹配权限的 MCP。

机器可读记录：`demo/layout_previews/project02_replay_attempt_20260817.json`。

## 2026-08-17 - 项目02静态碰撞分层求解与离线闭环

1. 为 8 个模组的全部 28 个顶层组合建立穷尽式碰撞策略：10 对普通实体使用膨胀 AABB 严格分离，18 对门洞、框架、嵌套和结构通道组合采用“AABB 分离直接通过、重叠才做 B-Rep”。
2. 求解器加入严格 AABB 候选淘汰与条件 B-Rep 候选数排序；求解阶段不调用 SolidWorks B-Rep。展示层新增严格 AABB 数、B-Rep 候选上限、当前方案预计候选数和求解阶段调用数。
3. 新增负向单元测试，证明普通实体即使未做 B-Rep，膨胀 AABB 重叠也会硬失败；结构组合重叠只会进入精确检查队列，不会被误判为无干涉。
4. 后端单元测试 36/36、Python 编译检查、前端 TypeScript/Vite 生产构建全部通过。
5. 项目02自动离线闭环通过：工艺 13/13、空间 11/11、交互 36/36、策略覆盖 28/28、严格对失败 0、未分类 0、求解阶段 B-Rep 调用 0；执行耗时约 6 秒。
6. 历史 v24 投影宽相可直接避开 11/28 对 B-Rep，剩余 17 对需要健康 SolidWorks 会话执行叶体精确检查。当前状态为 `OFFLINE_STAGED_STATIC_COLLISION_CLOSED_EXACT_BREP_PENDING`，不得宣称静态实体无干涉已经最终闭环。
7. 历史 v24 布局在新规则下检出 A180–A700 仅约 1.47 mm 间隔，低于 20 mm 严格间隔；新求解投影约 58.67 mm，说明新硬约束确实阻止了该类旧问题。

机器可读摘要：`demo/layout_previews/project02_static_collision_closure_summary.json`。

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
## 2026-06-30 - 统一 face mapping 路径并完成真实闭环检验

现象：
- 前端执行 `Common Base` 后曾返回：

```text
FinalizeCommonBaseAssembly completed with bottom face orientation probe errors.
```

分析：
- `demo_state.json` 中显示 B/C 的 `SelectFaceByName` 被强校验拒绝：
  - B-1: `center distance 0.396203m > 0.002000m`
  - C-1: `center distance 0.148034m > 0.002000m`
- 进一步查看发现 MCP probe 的 `MappingPath` 指向：

```text
vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\face_mappings.json
```

- 但后端 health 指向：

```text
artifacts\solidworks-mcp\face_mappings.json
```

处理：
- 重启后端并显式设置：

```text
DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

验证：
- 调用 `/api/demo/verify-face-mappings`：
  - A/B/C 均通过 persistent reference 选面；
  - MCP probe 的 `MappingPath` 已统一为 `artifacts\solidworks-mcp\face_mappings.json`。
- 调用 `/api/demo/finalize-common-base`：
  - 返回 `FinalizeCommonBaseAssembly completed.`
  - `commonBaseReady=true`
  - B-1 自动执行 `PreMateTransform2` 朝向修正；
  - A/B/C `orientationChecks` 均 `matchesBase=true`。
- 用户随后完成 Replay Layout 检验：
  - `Replay Check success=true`
  - `maxXyError=1.2412670766236366e-16m`
  - `maxThetaErrorDegrees=0.0deg`

结论：
- 双 face mapping 路径是此次问题的根因。
- 统一路径后，真实闭环通过：`Verify Faces -> Common Base -> Replay Layout -> Replay Check`。

待办：
- 固化后端启动脚本，避免遗漏 `DEMO_FACE_MAPPING_PATH`。
- 在 Health 检查中加入 MCP 实际 mapping path 回显。
## 2026-06-30 - 完成启动脚本与 Health 固化

本次操作：
- 新增 `scripts/start_demo_backend.cmd`，固定后端启动时的 MCP 相关环境变量：
  - `DEMO_MCP_MODE=bridge`
  - `DEMO_MCP_COMMAND=dotnet`
  - `DEMO_MCP_CWD=vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64`
  - `DEMO_FACE_MAPPING_PATH=artifacts\solidworks-mcp\face_mappings.json`
  - `DEMO_MCP_TIMEOUT_SECONDS=420`
- MCP 新增 `get_face_mapping_store_info`，用于回显 MCP 实际使用的映射文件路径。
- 后端 `/api/demo/mcp-health` 增加 mapping path 一致性检查。
- 前端新增 `Health` 按钮和状态面板，展示：
  - MCP 状态；
  - active assembly 是否匹配；
  - backend/MCP mapping path 是否一致。
- README 和中英文进展/待办文档已同步更新。

待验证：
- C# MCP build。
- Python 后端 compile。
- 前端 TypeScript/Vite build。
- 重启新版 MCP 和后端后，访问 `/api/demo/mcp-health`，确认 `faceMappingPathsMatch=true`。

验证结果：
- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
- `python -m compileall apps\demo-backend\src` 通过。
- `cmd /c npm run build` 通过。
- `git diff --check` 通过。
- 后端服务级 dry-run `mcp_health()` 通过，能返回 `faceMappingPath`；dry-run 模式下 `mcpFaceMappingPath=None` 属于预期，因为没有真实连接 MCP。

仍需真实验证：
- 重启新版 MCP。
- 使用 `scripts\start_demo_backend.cmd` 启动后端。
- 前端点击 `Health` 或调用 `/api/demo/mcp-health`。
- 确认 `faceMappingPathsMatch=true`。
## 2026-06-30 - MCP Hub 管理脚本与项目化规划

本次操作：
- 新增 `scripts/check_mcp_hub.cmd`：
  - 检查 MCP DLL 是否存在。
  - 查询 `SolidWorksMcpApp` 相关进程。
  - 通过 `NamedPipeClientStream.Connect()` 检查 `SolidWorksMcpHub` pipe 是否可连接。
  - 当环境不允许读取进程 command line 时，降级为提示，不再输出未处理异常。
- 新增 `scripts/start_mcp_hub.cmd`：
  - 以 `dotnet SolidWorksMcpApp.dll --headless-hub` 启动 MCP Hub。
  - 自动设置 `DEMO_FACE_MAPPING_PATH`。
  - 支持 `/dry-run` 参数。
- 新增 `scripts/stop_mcp_hub.cmd`：
  - 默认停止 `--headless-hub` / `--hub` 进程。
  - `/all` 模式清理 SolidWorksMcpApp 相关进程。
  - 无法读取 command line 时采用保守策略，避免误杀无关 `dotnet.exe`。
- README 已补充脚本用法。
- 中英文进展文档已记录脚本能力和测试结果。
- 中英文待办文档已补充真实项目化能力详细规划。

非侵入式测试：
```text
cmd /c scripts\check_mcp_hub.cmd
cmd /c scripts\stop_mcp_hub.cmd
cmd /c scripts\start_mcp_hub.cmd /dry-run
```

真实临时 Hub 测试：
- 使用隐藏进程启动 `dotnet SolidWorksMcpApp.dll --headless-hub`。
- 运行 `scripts\check_mcp_hub.cmd`。
- 结果：
  - 成功识别临时 `dotnet.exe ... SolidWorksMcpApp.dll --headless-hub` 进程。
  - `Pipe status: connectable`。
  - 按 PID 停止临时进程后，`stopped=True`。

项目化规划重点：
- n 个子装配体自动发现。
- layout JSON 自动生成项目配置。
- 前端 layout bounds 自动缩放。
- Replay 后误差阈值可配置。
- 批量面映射验证与问题清单。
## 2026-06-30 - 项目化能力第一轮：自动缩放与阈值配置

本次操作：
- 前端 2D layout 画布从固定范围改为自动 bounds：
  - 读取当前组件 target；
  - 读取 layout JSON 中的 layout2d；
  - 自动计算 min/max 和 padding；
  - 动态显示 X/Y 轴。
- 前端新增 Replay 阈值输入：
  - `XY tol`
  - `Theta tol`
- 前端 Replay Check 改为显示：
  - 最大误差 / 阈值；
  - 每个组件误差 / 阈值。
- 后端新增环境变量：
  - `DEMO_REPLAY_XY_TOLERANCE_METERS`
  - `DEMO_REPLAY_THETA_TOLERANCE_DEGREES`
- `scripts/start_demo_backend.cmd` 已设置默认阈值。
- `POST /api/demo/apply-captured-layout` 支持请求体覆盖阈值。
- `state.lastRun.replayValidation` 会记录实际使用的阈值。

验证命令：
```text
python -m compileall apps\demo-backend\src
cmd /c npm run build
git diff --check
```

> 2026-08-18：项目02 v28 快速联合求解已在约 1.695 秒内生成完整八模组离线解；候选缓存、责任剪枝、受控热启动、20秒预算、2.5D扫描视线、最受限优先和 A200/A500 局部修复的功能意义、诊断过程与测试结果记录于 `docs/project02_v28_fast_solver_iteration-CN.md`。当前未执行 SolidWorks Replay/B-Rep，状态为 `V28_OFFLINE_LAYOUT_SOLVED_VISUAL_REVIEW_PENDING`。

验证结果：
- 后端 compile 通过。
- 前端 build 通过。
- diff check 通过。

服务级闭环：
- 构造 target/actual layout，误差为：
  - `xyError=0.0005m`
  - `thetaError=0.05deg`
- 严格阈值 `1e-6m / 1e-4deg` 下结果失败。
- 放宽阈值 `0.001m / 0.1deg` 下结果通过。

下一步建议：
- 做 `DiscoverLayoutComponentsFromAssembly` 最小只读版本。
- 后端新增 discovery endpoint。
- 前端新增 discovered components 表格。
## 2026-07-06 15:17:34 操作记录

- 对上一轮 10+ 项目化改动进行 review。
- 修复 Recursive 发现中的选择唯一性问题：
  - 前端发现选择从 `componentName` 改为 `hierarchyPath + componentName`。
  - 后端同步发现组件时增加重复 `componentName` 检查。
  - 出现重复名时返回 `blocked`，避免后续 SelectFace/Move 歧义。
- 验证记录：
  - `python -m compileall apps\demo-backend\src` 通过。
  - `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
  - `npm.cmd run build` 通过。
  - 临时后端测试：
    - 12 个唯一组件同步和 `project_config.json` 写出成功。
    - 重复 `componentName` 的递归候选被正确阻断。
- 未执行真实 SolidWorks 10+ 装配体闭环，因为当前对话中未提供装配体路径，也无法确认该装配体是否作为活动文档打开。

## 2026-07-06 15:09:37 操作记录

- 面向 10+ 子装配体场景增强了 Project Config 链路：
  - 前端 Discover 增加顶层/递归发现范围。
  - 增加 Include parts 开关。
  - 增加发现结果过滤、Select Visible、Clear。
  - Generate Config 增加 `project_config.json` 输出。
  - 侧栏新增 Face Mapping 状态矩阵。
- 后端新增 `project_config.json` 写出逻辑：
  - 包含 sourceAssemblyPath、targetAssemblyPath、baseComponentName、layoutJsonPath、faceMappingPath、replayTolerance、components。
- 验证记录：
  - `python -m compileall apps\demo-backend\src` 通过。
  - `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
  - `npm.cmd run build` 通过。
  - 使用临时后端状态模拟 12 个子装配体，验证同步组件和写出 `project_config.json` 成功。
- 未做真实 SolidWorks 10+ 装配体验证；后续需要用真实装配体测试 recursive discovery、批量面映射、Common Base 与 Replay。

## 2026-06-30 22:06:48 操作记录

- 实现 `n 个子装配体自动发现` 第一版：
  - 在 `DemoTools.cs` 中新增 `DiscoverLayoutComponentsFromAssembly` MCP 工具。
  - 工具读取顶层 resolved 子装配体，返回路径、层级、Transform2、坐标轴等信息。
- 实现 `layout JSON 自动生成项目配置` 的入口：
  - 后端新增发现、同步发现结果、生成项目 layout JSON 的接口。
  - 前端新增 Project Config 区域，可 Discover、Sync Selected、Generate Config。
- 验证记录：
  - `python -m compileall apps\demo-backend\src` 通过。
  - `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` 通过。
  - `npm.cmd run build` 通过。
  - 临时后端状态中调用 `sync_discovered_components`，确认可将发现组件写入 demo state。
- 注意：
  - `npm run build` 在 PowerShell 下被执行策略拦截，改用 `npm.cmd run build` 后通过。
  - 当前发现工具不自动识别底面，不处理 suppressed component。
## 2026-07-06 15:32:27 操作记录：test1.SLDASM 只读发现测试

- 用户已在 SolidWorks 中打开 `demo\test1.SLDASM`。
- 检查后端 `/api/health` 正常，MCP bridge 模式可用。
- 通过后端 discovery 接口执行三组只读测试：
  - `topLevelOnly + includeParts=false`：15 个顶层子装配体。
  - `recursive + includeParts=false`：174 个装配体候选。
  - `recursive + includeParts=true`：1870 个候选，其中包含 1696 个零件。
- 未执行 `Sync Selected`：
  - 原因是当前运行中的后端仍是旧进程，返回默认底面名 `??`。
  - 继续同步会把 `??` 写入状态，影响后续 Verify Faces。
- 已将结果和下一步计划记录到中英文进展文档与待办文档。

## 2026-07-06 15:32:27 操作记录：test1.SLDASM 顶层组件同步与 Verify Faces

- 使用 `scripts\start_demo_backend.cmd` 启动新版后端。
- `/api/demo/mcp-health` 确认：
  - 当前 SolidWorks 活动文档为 `demo\test1.SLDASM`。
  - backend/MCP face mapping 路径一致。
- 重新执行顶层发现：
  - 15 个顶层子装配体。
  - 默认底面名为 `底面`。
- 执行 `Sync Selected`：
  - 15 个组件已同步到 `demo_state.json`。
- 执行 `Verify Faces`：
  - 返回 `blocked`。
  - 15 个组件均缺少 `底面` 映射。
- 暂停后续 Common Base / Generate Config，等待用户在 SolidWorks 中逐个选择真实底面并记录。

## 2026-07-06 操作记录：记录 FL9A项目号A100.001-1 底面

- 用户已在 SolidWorks 中选中 `FL9A项目号A100.001` 的底面。
- 按当前 demo state 的实例名使用 `FL9A项目号A100.001-1` 记录。
- 首次用独立脚本调用时，MCP runner 连接失败：`server shut down unexpectedly`。
- 改用后端 `/api/demo/record-selected-face` 后成功记录。
- 发现中文参数在部分命令链路中可能退化为 `?`，导致临时生成错误 key：
  - `FL9A???A100.001-1 / ??`
- 已补强后端 `_repair_mojibake_face_mapping_key`：
  - 可将退化组件名和退化面名搬回真实 `componentName / faceName`。
- 已清理本次错误 key。
- 再次 `Verify Faces`：
  - 缺失映射数量从 15 降为 14。
  - `FL9A项目号A100.001-1` 不再在缺失清单中。

## 2026-07-06 操作记录：记录 FL9A项目号A200.001-1 底面

- 用户已在 SolidWorks 中选中 `FL9A项目号A200.001` 的底面。
- 按当前 demo state 的实例名使用 `FL9A项目号A200.001-1` 记录。
- 中途发现一次命令层 Unicode escape 写法错误，会导致传入字面量 `\u9879...` 而不是中文；该次调用未形成有效映射。
- 重新使用 JSON escape 方式传参后记录成功：
  - `record_face_mapping` 返回 `Success=true`。
  - `get_selected_face_mapping_probe` 返回 leaf 为 `FL5A项目号A200101.01-1`。
  - `face_mappings.json` 中已存在 `FL9A项目号A200.001-1 / 底面`。
- 再次 `Verify Faces`：
  - 缺失映射数量从 14 降为 13。
  - `FL9A项目号A200.001-1` 不再在缺失清单中。

## 2026-07-06 操作记录：自动记录剩余低优先级组件任意面

- 用户说明剩余 3 个组件不要求准确底面，只需要各自有一个可记录的面。
- 尝试通过 `list_entities` 枚举面时，大装配体环境下出现卡顿和超时。
- 新增并编译通过 MCP 工具 `record_first_face_mapping`：
  - 不枚举全部 face。
  - 直接在目标组件树下寻找第一个 solid-body face。
  - 找到后写入指定 face mapping。
- 执行结果：
  - `FL9A项目号A001.001-1` 成功。
  - `手动锁付工位-1` 成功。
  - `螺丝枪组件DDC-1` 失败：未找到 solid-body face。
- 重新启动后端并执行 `Verify Faces`：
  - `missingCount=1`
  - 剩余缺失：`螺丝枪组件DDC-1`。


## 2026-07-06 17:58:49 操作记录：排除无实体面组件后进行 14 组件链路测试

- 按用户要求，暂时排除 `螺丝枪组件DDC-1`，因为该组件在当前装配体上下文中没有找到可读取的 solid-body face。
- 将 `demo_state.json` 中的组件集调整为剩余 14 个顶层子装配体。
- 执行 `/api/demo/verify-face-mappings`：
  - `status=ok`
  - `missingCount=0`
  - 14 个组件的底面映射均已满足当前验证要求。
- 执行 `/api/demo/capture-project-layout`：
  - 成功生成 `demo/test1_14_layout2d.json`。
  - 成功生成 `demo/test1_14_project_config.json`。
  - layout 中包含 14 个组件，`missingFaceMappings=[]`，没有空 layout2d。
- 尝试目标侧闭环：新建 `demo/test1_14_replay.SLDASM` 并一次性导入 14 个组件。
  - 调用 `initialize_common_base_assembly` 后约 15 分钟超时。
  - 未生成目标装配体和初始化截图。
  - MCP 日志显示已进入 `InitializeCommonBaseAssembly started`，但未在超时前完成。
- 结论：源装配体的 14 组件发现、验证、layout/config 生成链路已通过；目标侧“一次性导入 14 个真实子装配体”仍不稳定，下一步需要做批量初始化、进度保存和失败隔离。
## 2026-07-06 操作记录：批量初始化与组件实例名修复

- 新增并构建 `AppendComponentsToCommonBaseAssembly`。
- 后端 Initialize 增加批量模式：
  - `DEMO_INITIALIZE_BATCH_SIZE=4`；
  - 14 个组件拆为 4 批执行；
  - 每批结果写入 `lastRun.initializationBatches`。
- 新增 `DEMO_TARGET_ASSEMBLY_PATH`，用于指定本轮测试目标文件。
- 首轮目标文件：
  - `demo/test1_14_replay_batched.SLDASM`
  - 14 组件批量 Initialize 成功。
- 在旧目标上执行批量 Common Base：
  - 不再 420 秒超时；
  - 第 1 批明确失败；
  - `orientationChecks` 指向 `FL9A项目号A600.001-2`；
  - 进一步 discovery 发现目标装配体实际实例名与源 layout 名不一致。
- 修复方式：
  - `AssemblyService` 新增 `RenameComponent(currentName, newName)`；
  - `DemoTools.PrepareComponent` 插入组件后，如果 SolidWorks 自动实例名和请求的 `componentName` 不一致，就立即重命名。
- 重新构建后进行 v2 测试：
  - 目标文件：`demo/test1_14_replay_batched_v2.SLDASM`
  - 14 组件批量 Initialize 再次成功；
  - 文件已生成，大小约 84MB；
  - v2 discovery 已完成并返回 14 个顶层组件。
- 用户在我进行精确 expected/actual 名称比对时要求先分析日志，因此本轮暂停在：
  - v2 已 Initialize；
  - v2 尚未完成 Common Base 和 Replay Layout。

## 2026-07-20 Generate Config 路径问题修复记录

1. 检查后端状态与 MCP 日志：
   - `/api/demo/capture-project-layout` 返回 200；
   - MCP 布局捕获成功，耗时约 86.3 秒；
   - 成功读取 5 个组件的 `x/y/theta`。
2. 定位到相对路径解释不一致：
   - 实际文件被 MCP 写入 `vendor/.../win-x64/demo`；
   - 后端状态期望文件位于仓库根目录 `demo`。
3. 修改 `DemoService.capture_project_layout()`：
   - 调用 MCP 前统一转换绝对路径；
   - 增加输出目录创建和落盘检查。
4. 新增 2 项路径回归测试并通过，`compileall` 通过。
5. 将本次有效捕获文件复制回仓库 `demo` 目录。
6. 调用后端 Layout 列表接口确认：
   - 文件可发现；
   - 组件数为 5；
   - 五个组件的面映射状态均为已找到。

## 2026-07-20 真实 5 组件 v3 闭环操作记录

1. 调整启动脚本：
   - 修改 `scripts/start_demo_backend.cmd`；
   - 外部已设置 timeout 和 batch size 时不再被脚本默认值覆盖。
2. 启动 v3 后端配置：
   - `DEMO_MCP_TIMEOUT_SECONDS=600`；
   - `DEMO_INITIALIZE_BATCH_SIZE=2`；
   - `DEMO_TARGET_ASSEMBLY_PATH=demo\FL9A24D062A000_replay_v3.SLDASM`。
3. 执行 Reset、选择布局并同步 5 个组件。
4. 执行 Initialize：
   - 3 批全部成功；
   - 总耗时约 232 秒。
5. 执行 Verify Faces：
   - 10 次工具调用；
   - 0 失败，0 缺失映射。
6. 执行 Common Base：
   - 4 批全部成功；
   - A700 与 A800 自动执行 `-90 deg` 朝向修正；
   - 所有组件最终法向与基准一致。
7. 执行 Replay Layout：
   - MCP 主调用耗时约 561 秒；
   - 自动验证成功；
   - 最大 XY 误差 `5.698078393147796e-15 m`；
   - 最大 theta 误差 `1.1368683772161603e-13 deg`。
8. 显式保存：
   - 首次直接使用 Python `McpClient(mode=stdio)` 时协议不匹配；
   - MCP 日志报 `Content-Length` 首字符 `C` 无法作为 JSON 解析；
   - 改用与后端一致的 `McpToolRunner bridge` 后，`save_document` 成功；
   - 返回 `Errors=0`、`Warnings=0`；
   - v3 装配体已于 `18:45:56` 落盘。
9. 输出文件：
   - `demo\FL9A24D062A000_replay_v3.SLDASM`；
   - `demo\apply_captured_layout_result.png`；
   - `demo\replay_validation_layout2d.json`；
   - `.tmp\common-base-v3-result.json`；
   - `.tmp\replay-v3-result.json`。

## 2026-07-22 T401 底面法向 fallback 实施与验证

1. 确认 T401 已记录底面可通过 persistent reference 稳定找回，但旧版 probe 返回 `normal=null`。
2. 在 `SelectionService` 中补充直接面法向、零曲率曲面求值、三角化以及保守轴对齐包围盒推断四级 fallback。
3. 结束锁住构建输出的旧 MCP Hub 进程，重新构建 Release MCP，构建成功。
4. 补齐测试代理的 `RecordFirstFaceMapping`、`RenameComponent` 转发，执行法向相关定向测试，8 项全部通过。
5. 通过后端 Verify Faces 让 T401 成为最后选中的映射面，真实 probe 得到：
   - `localNormal=[0,1,0]`；
   - `worldNormal≈[0,1,0]`；
   - 面积 `0.07806513323142808 m²`。
6. 重新记录 T401 映射，并恢复五组件顺序；最终五组件 Verify Faces 全部成功、无缺失映射。
7. 操作中曾因 PowerShell JSON 默认编码导致运行状态中文路径被错误转码；已立即使用 ASCII Unicode 转义重建状态并通过 MCP Health 确认活动装配体与状态路径完全一致，CAD 文件和面映射未受损。

## 2026-07-22 包含 T401 的五组件前端等价闭环操作记录

1. MCP Health、源装配体路径与五组件 Verify Faces 均通过。
2. Generate Config 等价调用成功：
   - `demo/FL9A24D062A000_5components_t401_layout2d.json`；
   - `demo/FL9A24D062A000_5components_t401_project_config.json`；
   - 捕获耗时约 120.5 秒。
3. 切换到新的目标路径并以 900 秒 timeout 重启后端。
4. Initialize 按 `2/2/1` 三批完成，耗时约 106.5 秒。
5. 目标装配体 Verify Faces 五项全部通过。
6. Common Base 四批全部成功，耗时约 442.7 秒；A800 自动修正，T401 无需修正，最终法向均匹配基准。
7. Replay Layout 与自动误差验证成功，耗时约 457.2 秒，五组件全部通过阈值。
8. 检查 `apply_captured_layout_result.png`：截图非空并可见完整恢复结果。
9. 在可见 SolidWorks 所在桌面会话中调用 `save_document`，返回 `Errors=0`、`Warnings=0`；目标文件修改时间更新为 `2026-07-22 13:36:38.201`。
## 2026-07-22 约束布局功能实现与测试记录

1. 检查现有 Layout2D、Transform2、Common Base、Replay、后端 API 和前端扩展点。
2. 在 `AssemblyService` 的组件姿态中加入世界包围盒，并同步到 Discover/Capture 输出；Release 构建通过。
3. 新增 `constraint_layout.py`，完成角色判断、投影矩形、中央传输通道、功能模组两侧放置、供胶外置、余量逐级放宽和非重叠验证。
4. 新增后端 `generate-constraint-layout` 接口和前端 Constraint Layout 操作区。
5. 自动测试结果：Python 7 项通过；.NET 定向 20 项通过；前端生产构建通过。
6. 重启后端并通过 MCP Health 确认当前活动文件为五组件目标装配体，face mapping 路径一致。
7. 第一次真实求解：几何捕获成功，但 A200 无法放入龙门内部，求解被安全阻止，CAD 未移动。
8. 增加 containment 软约束兜底后再次求解成功：A200 被明确标为外置，5 个矩形无重叠。
9. Replay 实测依次发现并处理：
   - 旋转已配合组件导致长时间阻塞，默认关闭旋转；
   - 求解器试图移动默认固定的 A500，改为固定 baseComponentName；
   - 每组件重建造成重复求解，改为批量 Transform2 后统一重建；
   - 为 Constraint Layout 增加顶层 mate 临时抑制/恢复。
10. 多次阻塞调用均已终止直连 MCP 子进程，未终止 SolidWorks；但超时前可能已有部分姿态变化，因此当前会话不再作为可信闭环样本。
11. 真实闭环当前完成到 Constraint Layout2D 生成与几何验证；最终 Replay/误差读回等待干净 SolidWorks 会话复测。
## 2026-07-22 18:10 约束布局干净闭环操作记录

1. 用户关闭未保存的中断会话，重新打开目标装配体。
2. 启动后端，MCP Health 验证活动文档与目标路径一致，面映射路径一致。
3. 调用 `POST /api/demo/generate-constraint-layout`：约 35 秒后成功生成干净几何捕获和约束布局 JSON。
4. 使用显式角色：A100=龙门、A800=传输、T401AA=供胶、A500/A200=功能模组；关闭新增 90 度旋转。
5. 求解验证结果：5 个组件、0 个包围盒重叠对；A200/A500 记录为软包围约束放宽。
6. 调用 `POST /api/demo/apply-captured-layout`：约 224 秒后成功返回。
7. 5 个组件的选面与移动全部成功；A500 作为固定锚点保持原位；最终重建成功。
8. 自动回采验证 5/5 通过，最大 XY 误差约 `1.95e-14 m`，最大角度误差 `0 deg`。
9. 输出截图：`demo/apply_captured_layout_result.png`；回采文件：`demo/replay_validation_layout2d.json`。
## 2026-07-23 Portal 架形穿越功能实现记录

1. 检查现有约束求解器，确认 AABB 模型会把 A200/A800 的合法穿越误判为碰撞。
2. 确认仓库已有 SolidWorks `CheckInterference` 实体干涉检查能力。
3. 在后端增加 Portal 配置、净空宽高估算、龙门内包围、允许 AABB 重叠及诊断输出。
4. 在 MCP Replay 结果中增加 `portalInterferenceChecks`，最终重建后对声明的 Portal/传输组件对执行实体干涉检查。
5. 前端增加 Portal 宽高比例和 Functional 模组的 Pass-through 选择。
6. 使用真实 A200/A800 捕获几何做无 CAD 求解验证：A200 位于龙门内，A200/A800 AABB 重叠被允许，普通重叠为 0。
7. 自动测试：后端 9 项通过，WorkflowService 19 项通过，前端和 MCP Release 构建通过。
8. 尝试真实闭环时，Device Guard 以 `0x800711C7` 阻止新版和当前发布 MCP。
9. 尝试使用 2026-06-25 历史 MCP Hub，管道可创建但当前客户端调用未可靠返回，已停止兼容性尝试。
10. 当前未修改或保存 SolidWorks 装配体；待系统允许新版 MCP 后继续实体闭环。

## 2026-07-23 17:10 Portal 真实闭环重试记录

1. 检查 Hub：发现一个 `dotnet` 进程，但 `\\.\pipe\SolidWorksMcpHub` 不可连接。
2. 结束该陈旧 Hub，仅保留用户的 SolidWorks 会话。
3. 使用 Release DLL 配置、统一面映射路径、五组件目标装配体和 `900s` 超时启动后端。
4. `/api/health` 成功；后端进程保持运行。
5. `/api/demo/mcp-health` 失败，MCP 子进程在客户端握手前退出。
6. 直接运行 `dotnet SolidWorksMcpApp.dll --stdio-direct` 和 `dotnet run`，均返回 `0x800711C7`。
7. 查询 Windows Code Integrity 日志：
   - 事件 `3033/3077`；
   - 策略 ID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`；
   - 原因是新版未签名 DLL 不满足企业签名级别。
8. 未继续重复启动，避免增加系统卡顿；未调用 SolidWorks 修改接口，装配体未发生变化。

## 2026-07-23 18:56 Portal Replay 超时定位与闭环记录

1. 确认本机未加入 Azure AD、域或 Workplace 管理；此前拦截源为 Windows Smart App Control。
2. 用户关闭 Smart App Control 后，新版 MCP Health 通过。
3. 成功生成真实五组件 Portal 几何和 Layout2D JSON。
4. 首次 Replay 在 900 秒后超时；终止仅卡住的 MCP 子进程，未终止 SolidWorks。
5. 在 `DemoTools.ApplyCapturedCommonBaseLayoutCore()` 增加逐阶段和逐组件日志。
6. 诊断日志确认 5/5 组件移动、顶层配合恢复和最终重建均成功，卡点为 `CheckInterference`。
7. 新增 `validatePortalInterference=false` 默认参数，并由后端 Replay 计划显式关闭同步干涉检查。
8. 增加回归测试，确认 Replay 默认不会触发 Portal 干涉检查；后端测试 10/10 通过。
9. MCP Release 构建通过，0 warning / 0 error。
10. 重启后端后再次 Replay，最新一次约 124 秒返回 `status=ok`。
11. 自动回采验证 5/5 通过：最大 XY 误差约 `6.74e-14 m`，最大 theta 误差 `0 deg`。
12. 当前后端保持运行在 `127.0.0.1:8000`；装配体尚未由本次操作显式保存。

## 2026-07-29 A700/A300 七组件闭环操作记录

1. 检查五组件项目配置、源文件和统一面映射；确认 A700 已有映射，A300 需要补录。
2. 新增七组件项目配置，将 A700/A300 作为功能模组加入，保留 A200 穿越 A800 的 Portal 规则。
3. 新增七组件求解回归测试；约束布局测试 `8/8` 通过。
4. 备份五组件 `demo_state.json`，切换到七组件状态并按 `4 + 3` 两批 Initialize；目标装配体创建成功。
5. 用户在 SolidWorks 中选中 A300 底面后，调用记录脚本写入 Persistent Reference、中心、面积和法向；七组件 Verify Faces 全部通过。
6. 执行批量 Common Base：第 1 批成功，第 2 批在客户端 `900 s` 超时。随后只读 Verify 证实七个底面已经共面且法向一致，状态恢复为 `commonBaseReady=true`。
7. 处理一次 Windows PowerShell 中文 JSON 乱码：恢复七组件中文源路径和 `底面` 字段，并改用 UTF-8 无 BOM 请求文件配合 `curl.exe --data-binary`。
8. 生成七组件约束几何和 Layout2D；二维约束验证成功。A500/A700/A300 被明确标记为 containment relaxed。
9. 执行 Replay，约 `898 s` 返回成功；自动回采最大 XY 误差约 `1.34e-15 m`，theta 误差 `0 deg`。
10. Replay 后再次 Verify Faces：七组件均成功，最大底面平面误差约 `1.7e-15 m`，法向点积最小值为 `1.0`。
11. 尝试显式保存时发现 Hub 不可连接；改用 direct 模式又连接到新建空白 SolidWorks 实例。已只关闭本次误启动的空实例，未终止原 SolidWorks 进程。
12. 本次七组件几何闭环成立；磁盘目标装配体仍是 Common Base 阶段保存版本。Replay 自动保存和 SolidWorks 目标实例绑定已记录为后续工程项。

## 2026-07-29 七组件最终求解与持久化记录

1. 使用已有七组件 Constraint Layout2D 执行 Replay，约 `684 s` 返回成功；七组件移动/旋转均无失败，最大 XY 误差约 `5.88e-15 m`。
2. 确认原 Replay 高层工具仅修改内存，不自动保存，且独立 `save_document` 可能连接到空白 SolidWorks 实例。
3. 修改 `DemoTools.ApplyCapturedCommonBaseLayoutCore()`，在同一 MCP/COM 会话末尾保存目标装配体，并在结果中返回 `saveResult`。
4. MCP Release 构建通过，0 warning / 0 error。
5. 使用新版 MCP 再执行幂等 Replay，约 `403 s` 完成主调用和自动回采。
6. 保存结果：Errors=0、Warnings=0；目标装配体修改时间更新为 `2026-07-29 15:23:47`。
7. 自动回采：最大 XY 误差约 `1.04e-14 m`，最大 theta 误差 `0 deg`，七组件全部通过。
8. 保存后 Verify Faces：14/14 工具调用成功，缺失映射 0；底面高度跨度约 `1.72e-15 m`，法向全部为全局 `+Y`。
9. 最终文件：`demo/FL9A24D062A000_7components_t401_replay.SLDASM`；截图：`demo/apply_captured_layout_result.png`。

## 2026-08-05 工艺语义约束布局

1. 新增 `demo_backend.process_constraints`，支持 Scanner、CCD、Calibration、Cleaning、Weighing 等模组语义和局部点位/区域。
2. 在 Constraint Layout 中接入自动/显式工艺硬约束、语义旋转和侧面偏好，并把工艺验证合并到最终 `validation.success`。
3. 扩展后端请求模型、服务参数和前端 JSON 配置入口；前端生产构建通过。
4. 后端 `unittest discover` 共 `16/16` 通过；专用约束覆盖成功布局、缺参阻断、显式硬约束失败、语义角色冲突，以及服务层输出文件闭环。
5. 新增 `docs/process_constraint_layout-CN.md` 说明配置格式、自动约束和当前边界。

## 2026-08-05 PPT/CAD 联合模组识别

1. 从六组 PPT 提取 Scanner、CCD、Calibration、Cleaning、Weighing 和 Glue draining cup 的文字与结构证据，并导出关键原始页用于视觉比对。
2. 通过 SolidWorks direct MCP 以只读方式打开各装配体，导出六向正交图和等轴测图；未调用保存工具。
3. 识别结论：A100=双阀点胶 XYZ 龙门，A200=CCD 产品定位运动模组，A300=双接废胶杯，A500=针头校准，A700=自动针头清洁，A800=传输/载具定位总成。
4. A900 初步为另一层/另一段传输；A600 完整解析超过十分钟，本次未完成。
5. 修正旧假设：A200 不再只是无语义 Portal 功能件；A300 不是称重模组。当前七组件尚未覆盖独立的 Scanner/Weighing 顶层组件。
6. direct 分析留下无窗口 SolidWorks 实例 `51164/51320/58580/18780/41888/52732/74572`，原有可见实例为 `69556`；普通 `Stop-Process`/`taskkill` 被系统拒绝。A800/A900 截图成功但 `close_document` 返回错误。未保存或改写任何源 CAD。
7. 新增 `docs/module_identification-CN.md`，记录证据、置信度、求解语义建议和待确认数据；图片位于 `demo/module_identification/`。

## 2026-08-05 真实模组参数核查与粗复原估计

- 联合 PPT 参数、已导出的 SolidWorks 六向视图、完整装配体顶视图、底面映射和包围盒完成七项待确认数据审计。
- 确认 A200=CCD、A300=双排胶杯、A500=校准、A700=清洁；A600 为扫描模组首要候选，称重模组仍未定位。
- 提取/估计 A300 双排胶点、A500 校准点、A700 清洁点、A800 条码及工作位、A100 保守公共可达区和 A200 移动覆盖区。
- 确认可达硬约束应为“服务点进入阀行程”，模块本体只另外承担碰撞、间隙和维护空间约束。
- 结论和临时值记录在 `docs/real_module_parameter_audit-CN.md`；未修改源 SolidWorks 文件，也未把估计值写入真实项目配置。

## 2026-08-05 称重占位与工艺参与式粗求解

1. 用户确认允许使用明确标记的称重占位模块完成粗复原。
2. 后端新增 `provisionalComponents`：根据公共底面和长宽高注入临时几何，输出 `assumptionWarnings`、占位数量及 `productionReady=false`。
3. 前端新增占位组件 JSON 输入和醒目的 `PROVISIONAL` 结果提示；几何占位没有真实文件时自动使用 `syncLayout=false`。
4. 修正真实参数的公共底面 V 轴方向；新增移动式 CCD 覆盖模式、服务点隔离模式和显式传输投影重叠许可。
5. 放置器现在先对齐传输工作位与双阀可达区、再对齐 CCD 移动覆盖区，并在候选阶段检查服务点可达与隔离约束。
6. 新增可重复请求、生成脚本和输出：
   - `demo/FL9A24D062A000_coarse_process_request.json`；
   - `scripts/generate_coarse_process_layout.py`；
   - `demo/FL9A24D062A000_coarse_process_layout2d.json`。
7. 闭环结果：8 个求解对象、11/11 工艺硬约束通过、非允许碰撞 0、允许投影重叠 9；由于称重不可 Replay 且 Scanner/A600 未纳入，`productionReady=false`。
8. 回归验证：后端 `20/20` 测试通过、`compileall` 通过、前端生产构建通过、生成输出 JSON 断言通过。

## 2026-08-05 A180 Scanner 与 A700/A730 真实工艺闭环

1. 用户确认 `A180=Scanner`，并在完整装配体中选择其底面；已记录 `FL9A24D062A180.001-1 / 底面`，叶零件为 `FL5A24D062A180001.01-1`。
2. 通过后台直连同一 SolidWorks 活动实例完成八组件持久引用复选：16 次选面/探测调用全部成功。
3. 用户确认 A700 同时包含清洁与称重功能，A730 为称重子模组；删除独立称重占位体，A700 作为组合实体进入求解。
4. 新增语义估计告警：`parameters.provisional=true` 会自动阻止 `productionReady=true`。
5. 新增显式 `lineOfSightTransparent`，用于标记 Portal 框架或具有高度分层、会产生 2.5D 假遮挡的实体；三维复核仍为必需项。
6. 真实布局输出：8 个真实 CAD 对象、13/13 工艺硬约束通过、非法重叠 0、允许投影重叠 3、占位体 0、`productionReady=false`。
7. 新建并保存 `demo/FL9A24D062A000_8components_real_process_replay.SLDASM`；Common Base 分 3 批完成，所有底面法向匹配。
8. Replay 复测通过：最大 XY 误差 `2.897767167584095e-14 m`，最大角度误差 `1.1368683772161603e-13°`。
9. 截图为 `demo/apply_captured_layout_result.png`；可重复验收命令为 `python scripts/validate_real_process_closure.py`。
10. 后端单元测试更新为 `22/22` 通过。

## 2026-08-06 原型对比驱动的真实八组件布局修正

1. 复核修正前 Replay 与原型装配体，确认 A800 位于龙门外、A700/A300 基本位于行程外，旧 `dualValveReach` 与 A100 包络的坐标系不一致。
2. 在约束求解器中增加原型位姿优先、传输/Portal/功能模组最低龙门重合率、阀行程完全包含于龙门，以及显式允许投影重叠组件对。
3. 修正真实项目配置：A100 公共可达区改为 A100 底面中心局部坐标；A800 工作位、A200 移动覆盖区改为各自局部坐标；A180 最大粗估工作距离收紧到 `0.35 m`。
4. 新增行程越界阻断和原型位姿保留回归测试；后端单元测试 `24/24` 通过。
5. 生成新布局：13/13 工艺硬约束、6/6 空间硬约束通过；A800/A200 龙门投影重合率分别为 86.8%/87.0%，A180/A500/A700/A300 为 100%，公共可达区 100% 位于龙门包络内。
6. 修正前各模组相对 A100/原型的最大二维误差为 A800 的 `1.676 m`；新目标直接保留满足硬约束的原型相对位姿，目标误差为 0。
7. SolidWorks Replay 已完成并生成截图；原目标文件以只读方式打开，直接保存返回 `swReadOnlySaveError`。
8. 通过 `save_document_as(saveAsCopy=true)` 安全另存当前内存装配体，避免改写原型 A180/A300 子装配体；输出 `demo/FL9A24D062A000_8components_real_process_corrected.SLDASM`，大小 36,730,480 字节。
9. 新文件已在 SolidWorks 中重新打开且布局保持正确；保存后底面坐标回采因 COM 队列占用分别在 420 秒和 120 秒超时，未取得逐组件保存后误差报告。
10. 新增离线评测脚本 `scripts/evaluate_real_process_layout.py`、机器可读结果和中文评测报告；`productionReady=false` 保持不变，待真实点位/行程和三维干涉验证。

## 2026-08-06 保存坐标复测与三维干涉宽相位

1. 重启干净 SolidWorks 会话并重新打开修正装配体，回采 8 个顶层 `Transform2/BoundingBoxWorld` 和 8 个命名底面；所有选择与探测成功。
2. 新增 `scripts/validate_saved_component_poses.py`；保存坐标验证 8/8 通过，最大平移误差 `3.8581e-14 m`、最大角度误差 `1.1369e-13°`、最大底面共面误差 `9.8637e-15 m`、底面法向点积最小值 `1.0`。
3. 直接调用 SolidWorks `ToolsCheckInterference2` 检查 A700–A300 超过 180 秒，终止的仅是该 MCP 客户端进程。
4. 新增 `scripts/screen_allowed_overlaps_3d.py`，对保存后的实际世界 AABB 执行 1 μm 保守宽相位；12 对中 A500–A700、A700–A300 两对有明确三维间隙，剩余 10 对保留 B-Rep 检查，其中 A180–A200 为浮点级近接触。
5. 在 `AssemblyService.CheckInterference` 加入双组件世界 AABB 快速排除；相交、接触、近接触、包围盒缺失均回落到实体算法。新增边界/归一化/缺失数据测试，`AssemblyServiceTests` 10/10 通过。
6. 发布 `artifacts/solidworks-mcp-aabb-preflight` 后复测 A700–A300：利用 `0.5051 mm` 实际间隙在约 28.2 秒内（含文档打开）返回 `HasInterference=false`，不再进入 180 秒阻塞路径。
7. 闭环脚本结果更新为 `PASS_WITH_BREP_INTERFERENCE_PENDING`；保存坐标项已通过，`productionReady=false` 继续保持，待剩余 10 对 B-Rep/最小间隙和真实工艺参数验证。
8. 全量 C# 回归首次发现 5 个 `SelectByName` mock 空引用和 5 个 Hub 环境集成失败；为 `ModelDocExtension` 缺失增加旧 COM `SelectByID` 回退后，Selection+Assembly 定向测试 49/49、非 Hub 集成测试 304/304 通过。5 个 Hub 可视化集成测试仍因当前本机 Hub 连接关闭失败，已与逻辑回归分离记录。
9. 尝试对浮点级近接触的 A180–A200 做隔离实体检查；宽相位按设计未短路，但限时执行未生成结果文件。已终止本次检查进程和本轮测试遗留的 5 个 Hub 代理，未终止 SolidWorks；该组件对继续保持 `needs_brep_check`，未作无干涉推断。
10. 将比较口径从“修正目标相对原型”为 0，增强为“保存后实际坐标相对原型”：逐组件相对 A100 复算后，最大误差为 A300 的 `4.0624e-14 m`，闭环脚本增加 `<=1e-9 m` 硬断言并通过。
11. 新增 `scripts/plan_remaining_interference_checks.py` 与 `demo/FL9A24D062A000_interference_check_plan.json`；将 10 对待检项分为 P0 近接触 2 对、P1 小相交 2 对、P2 大相交/预期穿越 6 对，并给出逐对实体、最小间隙和维护/运动空间检查顺序。

## 2026-08-06 去原型位置依赖求解测试

1. 审计发现 `preferSourceLayout=false` 仍存在两处隐性源位置依赖：服务点候选按原始锚点距离排序、供胶侧由原始位置决定。
2. 新增 `sourcePositionIndependent` 模式：禁止与 `preferSourceLayout` 同时启用；龙门归一化到求解原点；取消基于原型 A500 的最终固定平移；输出 `requiresAnchorTranslationBeforeReplay=true`。
3. 无原型模式的点位候选改为优先最大化龙门覆盖率、再靠近约束可行区域中心；点距离约束也参与生成锚点搜索区间，修复首次测试中 Scanner 到条码超限 7.59 mm 的顺序耦合失败。
4. 两组独立扰动位置分别求解，最大相对结果差 `8.33e-17 m`，证明输出不受输入原型位置影响；7/7 非龙门组件与原型相差超过 10 mm，最大差为 A300 的 `0.7158 m`。
5. 新解通过 13/13 工艺约束、6/6 空间约束、阀行程包含和非法重叠检查；A800 龙门覆盖 86.8%，其余功能模组 100%，containment relaxation 为 0。
6. 新增回归测试、可重复脚本、布局 JSON、验证 JSON 和 `docs/source_independent_layout_test-CN.md`。本轮不执行 CAD Replay；三维干涉、锚点转换和真实参数仍待验证，`productionReady=false`。

## 2026-08-06 去原型依赖布局 Replay 与三维干涉检查

1. 将无原型位置解整体平移到 A500 真实底面固定基准：`deltaU=-0.635 m`、`deltaV=+0.2575 m`；相对布局与 13/13 工艺、6/6 空间约束结果保持不变。
2. 从修正装配体的磁盘版本建立独立副本，执行 SolidWorks Replay；8/8 模组移动成功，7 个顶层配合临时抑制后恢复，统一重建和截图成功。
3. 审计发现当前 Hub 服务版本的 Replay 未自动更新磁盘时间戳；随后在同一 SolidWorks 会话显式调用 `save_document`，返回 `Errors=0 / Warnings=0`，文件时间更新为 `2026-08-06 10:15:53`。
4. 关闭目标文档并从磁盘重新打开，回采 8 个顶层位姿和底面；验证 8/8 通过，最大平移误差 `3.3364e-14 m`、最大角度误差 `1.2790e-13°`。
5. 对保存后实际世界 AABB 检查全部 28 对：13 对有大于 1 μm 的明确间隙，15 对保留精确 B-Rep 候选。
6. A100–T401 经 SolidWorks 检查工具的宽相位快速路径确认无干涉；A180–A200 进入精确 `ToolsCheckInterference2` 后超过 180 秒无结果，仅终止隔离检查器。
7. 生成 `docs/source_independent_replay_interference-CN.md` 和机器可读结果；最终状态 `PARTIAL_BREP_PENDING`，未发现已确认干涉，但不得表述为实体干涉全通过，`productionReady=false`。

## 2026-08-06 去原型布局方向、边界与传输净空修正闭环

1. 定位四类根因：Replay 只记录单轴角度导致 180° 翻转歧义；恢复旧顶层配合会覆盖新姿态；二维规划包络未用保存后的真实 AABB 复验；功能模组与传输线的投影重叠许可过宽。
2. 布局输出增加目标 X/Y/Z 三轴；Bridge/MCP 新增完整姿态写入，Replay 优先使用完整姿态并跳过已匹配组件。
3. 去原型模式下 7 个冲突顶层配合保持抑制但不删除；保存后验证 A180/A700/A300 等 8 个组件完整姿态误差均为 `0°`。
4. 增加传输低侧偏置和功能锚点偏置；A500/A700/A300 与 A800 保存后实际 AABB 净空分别为 `19.73/10.25/72.02 mm`。
5. 保存后龙门覆盖验证通过：A800 `86.30%`、A200 `85.49%`，A180/A500/A700/A300 `100%`。
6. 最终装配体为 `demo/FL9A24D062A000_8components_source_independent_corrected.SLDASM`；保存和重建成功，`Errors=0 / Warnings=0`，8/8 位姿复测通过。
7. 代码回归：后端 26/26、Bridge `AssemblyServiceTests` 10/10、Python compileall、MCP 应用 C# Release 构建均通过；双扰动最大相对差 `4.44e-16 m`，13/13 工艺、6/6 空间约束通过。测试工程仍有既有 nullable 编译警告。
8. 机器摘要为 `demo/FL9A24D062A000_source_independent_corrected_closure_summary.json`，状态 `TARGETED_LAYOUT_FIXES_CLOSED_BREP_PENDING`。剩余 13 对保守候选仍需精确 B-Rep/最小间隙检查，`productionReady=false`。

## 2026-08-06 建立布局约束与求解原则统一记录

1. 新建 `docs/layout_constraints_and_solver_principles-CN.md`，作为布局约束和求解原则的唯一持续维护文档。
2. 按当前代码实际行为区分代码硬约束、项目硬约束、确定性偏置、重叠放行、Replay后复验、临时估计和待实现约束。
3. 记录当前13项工艺硬约束、6项空间硬约束、A200 Portal白名单、去原型覆盖项、求解顺序和第一可行解原则。
4. 明确基础请求与实际去原型生成脚本的差异：实际关闭原型位置偏好、功能模组要求100%龙门覆盖，并注入传输/A700偏置。
5. 记录已确认缺口：传输中心线、CCD真实开口、A500–A200实体净空、供胶连接及全局多目标选择均未实现。
6. 规定今后任何约束新增、删除、放宽、收紧或临时覆盖，必须在同一代码变更中同步更新该文档及其变更记录。

## 2026-08-06 项目02去原型求解展示层闭环

1. 新增 `layout_preview.py`，离线读取项目02真实几何捕获和案例请求，使用通用约束执行去原型求解，不调用SolidWorks、不使用原型位姿。
2. 将去原型选项构造从测试脚本统一到后端，避免展示、测试使用不同规则。
3. 新增 `POST /api/demo/cases/project02/solve-preview`，输出完整求解结果和展示数据到 `demo/layout_previews/`。
4. 前端增加项目02展示面板：显示模组包围盒、方向、龙门中心线、双阀/CCD区域、工艺点、约束统计和观察项。
5. 增加50 mm传输中心偏差展示观察阈值；该阈值不参与求解。当前结果约174 mm，明确提示继续校准中心线规则。
6. 当前离线结果为13/13工艺、6/6空间、行程包含通过，非白名单重叠0对，允许重叠待复核7对，`productionReady=false`。
7. 新增3项展示层单元测试；后端29/29、前端生产构建、去原型双扰动测试及浏览器交互核验通过。
8. 新增 `docs/layout_solution_preview-CN.md`，记录使用方法、显示内容、观察结论和后续案例扩展原则。

## 2026-08-06 项目02通用约束第一轮快速校准

1. 组合试算确认：保持A500/A700/A300完整二维AABB与A800强制分离时，传输无法居中；允许三者作为“投影穿越、三维必检”候选后可得到中心偏差7.5 mm的可行解。
2. 取消 `-0.1815 m` 传输偏置，新增50 mm传输—龙门短轴中心偏差硬约束和10 mm非Portal功能模组龙门边界净空硬约束。
3. 扫描器新增50 mm最小工作距离，修复扫描原点与条码点重合、零长度视线仍通过的问题；项目02结果扫描距离为70 mm。
4. 展示层新增9对允许投影重叠的具体组合，便于人工区分A500–A800、A500–A200等风险。
5. 新结果为13/13工艺、11/11空间硬约束、阀行程包含全部通过，非法重叠0对，允许重叠9对，`productionReady=false`。
6. 可视化观察结论：中心性、扫描零距离和贴边问题已改善；下一轮应增加2.5D高度层、A200真实开口/空腔和功能模组简化占用体，避免继续用二维AABB偏置代替实体关系。

## 2026-08-06 项目02第二轮2.5D交互约束与测试闭环

1. 在核心放置器中新增交互硬约束阶段：粗AABB候选必须由简化交互包络分离或A200 Portal开口解释，否则求解失败；输出新增 `interactionEnvelope` 和 `constraintPlan.interactionValidation`。
2. A200增加开口平面区域和0~420 mm高度层；A800增加传输工作走廊；A500/A700/A300增加简化主体占用体和高度层。所有数值均在配置中注明来源与临时状态。
3. 项目02显式投影白名单收紧为0对；A180/A500/A700/A300与传输的粗重叠仅允许进入交互体复核，不再无条件放行。
4. 展示层新增交互体点划线、交互高度和“2.5D交互”指标；当前结果为工艺13/13、空间11/11、交互9/9、行程通过、非法重叠0、传输中心偏差7.515 mm。
5. 后端30/30单元测试通过，前端TypeScript/Vite生产构建通过；去原型双扰动最大相对差 `8.3267e-17 m`。
6. 新建SolidWorks副本并尝试Replay；当前SolidWorks COM在打开装配体前返回 `0x800706BE`。系统存在多个SolidWorks进程，安全审查拒绝强制结束全部实例，因此未冒险重启、未生成伪装的Replay成功文件。
7. 新增平移预测脚本 `scripts/project_saved_replay_poses.py`：用最近一次已保存并复测的CAD姿态为基线，在目标朝向完全相同的前提下施加求解平移。该结果只用于世界AABB宽相位，不冒充保存后的Replay或B-Rep证据。
8. 预测宽相结果为12/28对确定分离、16/28对保留精确B-Rep；真实龙门覆盖复算通过。待Replay副本明确命名为 `demo/FL9A24D062A000_8components_interaction_v2_pending_replay.SLDASM`。
9. 机器摘要写入 `demo/FL9A24D062A000_interaction_v2_closure_summary.json`；当时状态为 `SOLVER_2_5D_CLOSED_SOLIDWORKS_REPLAY_BLOCKED_COM_SESSION`，`productionReady=false`。

## 2026-08-06 项目02第二轮 SolidWorks Replay 与保存闭环

1. 用户确认已关闭工作并只保留干净会话后，原 COM 连接仍返回 `0x800706BE`；由于遗留 SolidWorks 进程权限不一致，未继续尝试强制结束进程。
2. 在 `SwConnectionManager` 增加显式 `forceNewInstance` 模式，并由 `SOLIDWORKS_MCP_FORCE_NEW_INSTANCE=1` 启用；默认行为保持优先复用 ROT，不影响既有调用。
3. 新增连接测试验证强制新实例会跳过 ROT 并直接创建实例；相关连接测试 21/21 通过，发布隔离运行包 `artifacts/solidworks-mcp-force-new/`。
4. 原临时副本曾因占用以只读方式打开；随后从已校验哈希的干净副本生成唯一正式文件，并在同一新实例中执行打开、8 模组 Replay、重建、保存、位姿和底面回采。
5. 正式文件为 `demo/FL9A24D062A000_8components_interaction_v2.SLDASM`，大小 `36,746,980` 字节；Replay 8/8 移动成功，保存 `Errors=0 / Warnings=0`。
6. `validate_saved_component_poses.py` 复测 8/8 通过：最大平移误差 `5.247e-15 m`，最大平面角误差 `1.279e-13°`，最大底面共面误差 `1.423e-14 m`，法向绝对对齐值最小为 `1.0`。
7. 保存后 28 对顶层组件世界 AABB 筛查通过：12 对确定分离，16 对保留精确 B-Rep 候选；龙门框架与内部模组的 6 对属于预期包围盒重叠。
8. 对非龙门候选 A500–A700 调用 SolidWorks `ToolsCheckInterference2`，150 秒内未返回；记录为 `timeout/unresolved`，未误判为无干涉。结果写入 `demo/interaction_v2_brep_A500_A700.json`。
9. 机器闭环摘要更新为 `LAYOUT_REPLAY_CLOSED_BREP_PENDING`。当前装配体已可用于展示与后续人工观察，但 A200 真实开口、简化占用体、16 对精确干涉、运动扫掠和管线尚未闭环，因此 `productionReady=false`。
10. 最终回归通过：Bridge 连接测试 21/21、后端单元测试 30/30、前端 TypeScript/Vite 生产构建、去原型双扰动测试均通过；双扰动最大相对布局差仍为 `8.3267e-17 m`。
11. 使用另一个隔离 SolidWorks 实例只从磁盘重开正式装配体，不执行 Replay 或移动；8 个顶层位姿与 8 个底面均成功读取，复测 8/8 通过。磁盘重开结果最大平移误差 `3.511e-16 m`、最大平面角误差 `1.279e-13°`，确认布局已实际持久化，而非仅存在于保存前内存。

## 2026-08-06 项目02第三轮扫掠区/实体占用约束完善与测试

1. 对当前9对粗AABB候选复核后确认，旧 `interactionBoundsLocal` 只表达简化服务区，不能充当完整实体占位；求解器新增默认完整AABB的 `hardBodyEnvelope`。
2. A800新增临时载具/产品扫掠区；A180、A500、A700、A300增加 `avoidTransportSweep` 硬约束，10 mm净空在候选生成阶段执行。
3. A200 Portal改为分类模式：A800沿长轴穿越，A180/A500/A700/A300的完整实体二维包络和高度必须包含于开口内。
4. CCD排序前移，保证Portal先于Scanner和服务模组建立；A180仍作为A200开口内设备，但不允许进入传输扫掠区。
5. 去原型双扰动回归通过：最大相对布局差 `8.3267e-17 m`；工艺13/13、空间11/11、交互9/9、行程包含通过，非法投影重叠0、containment relaxation 0。
6. 交互9项中，4项 `transportSweepClearance` 和5项Portal开口检查全部通过；A500位于扫掠区上侧，A700/A300位于下侧。
7. 展示层新增 `hardBodyEnvelope`、`transportSweepEnvelope` 和红色载具扫掠区；完整预览JSON已重新生成。
8. 回归测试：后端31/31、Python compileall、前端TypeScript/Vite生产构建全部通过。
9. 从v2复制独立v3装配体并尝试SolidWorks Replay；隔离MCP在20分钟内未返回，v3文件大小和时间戳未更新且无截图，按未决处理。仅终止本次Python/Runner/MCP进程，未终止SolidWorks。
10. v3副本仍被SolidWorks进程占用，无法安全改名；该文件当前仍是v2内容，不能作为第三轮成品。A700相对v2发生180°旋转，旧保存位姿不满足纯平移预测前提，因此未生成虚假的第三轮三维宽相位结论。
11. 当前状态：`OFFLINE_SWEEP_AND_BODY_CONSTRAINTS_CLOSED_SOLIDWORKS_REPLAY_TIMEOUT`，`productionReady=false`。
12. 浏览器首次冒烟测试连接到未重启的旧后端并复现扫描距离失败；确认磁盘新代码无误后，仅重启8000端口的本项目后端。再次点击“求解项目02”通过，页面显示8个模组、13/13工艺、11/11空间、9/9交互、7.5 mm中心偏差、1个红色载具扫掠区和4个简化交互框；点击A800后扫掠高度显示为 `0~0.380 m`。

## 2026-08-09 项目02第三轮 Replay、保存位姿与部分精确干涉闭环

1. 用户关闭可见文档并以管理员权限结束历史后台 SolidWorks 进程后，确认 `SLDWORKS_COUNT=0`，v2/v3 均解锁且 SHA-256 完全一致；v3 初始确认为未污染基准副本。
2. 首次 Replay 在多个组件已成功移动后，于 A200 的 `MoveComponent` 阶段发生 RPC 失败；日志定位到每次变换都重新递归 `IComponent2.GetChildren()` 的整树遍历。
3. 在 `AssemblyService` 新增 `ResolveComponentForTransform`：顶层变换目标优先调用 `IAssemblyDoc.GetComponentByName`，失败时才保留递归解析；`MoveComponent`、`RotateComponent`、`SetComponentOrientation` 同步使用该入口。
4. Bridge Release 构建通过；非 GUI 测试 305/305。完整测试运行 307 项通过，3 项既有 GUI 集成用例因 MCP 测试客户端故意未暴露工具而失败，并遗留的测试 SolidWorks 进程已清理。
5. 修正后的正式 Replay 完成：8/8 模组成功，最终重建成功，原位保存 `Errors=0 / Warnings=0`；v3 文件更新为 36,766,892 字节，截图写入 `demo/interaction_v3_replay_result.png`。
6. 从保存后的活动装配体回采 8 个顶层位姿和 8 个底面；`validate_saved_component_poses.py` 8/8 通过，最大平移误差 `5.3291e-15 m`、最大平面角误差 `1.2790e-13°`、最大完整姿态误差 `0°`、最大底面共面误差 `1.4199e-14 m`。
7. 真实世界 AABB 筛查 28 对：12 对确定分离，16 对保留精确候选；龙门覆盖复算全部通过，A800 覆盖率 `86.8%`，A200/A180/A500/A700/A300均满足各自阈值。
8. SolidWorks 精确检查已完成 5 对且均无实体干涉：A500–A200、A180–A200、A200–A300、A200–A700、A300–A700。此前重点担心的 A500–CCD 接触已由真实实体检查排除。
9. A180–A800、A200–A800、A300–A800 分别在 240/240/180 秒内超时；每次均仅结束对应 MCP/客户端进程，超时不计为通过。连续三组 A800 超时后，A500–A800、A700–A800暂缓，避免继续占用 SolidWorks。
10. 精确干涉摘要为：5 对完成且无干涉、3 对超时、8 对未完成（含6对A100结构包络候选和2对A800候选）；未发现已确认实体干涉，但不能宣称全部 B-Rep 通过。
11. 删除过时的 `interaction_v3_UNVERIFIED` 标记，新增 `demo/FL9A24D062A000_8components_interaction_v3_VERIFIED.md`；机器摘要更新为 `LAYOUT_REPLAY_POSE_CLOSED_PARTIAL_BREP_PENDING`。
12. 当前装配体可用于粗布局展示、人工观察和继续校准通用约束；完整 B-Rep、动态扫掠、拖链/软管和维护空间未闭环，故 `productionReady=false`。

## 2026-08-09 项目02第三轮叶级实体 B-Rep 全量闭环

1. 新增 `check_interference_by_leaf_bodies`：将两个顶层模组递归展开到叶级实体，复制实体并用组件 `Transform2/GetTotalTransform` 转换到顶层装配坐标，再用实体 AABB 预筛。
2. AABB 只用于排除确定分离的实体对；候选实体对依次调用 `IModeler.CheckInterferenceBetweenTwoBodies`、`CheckInterference3`，对未直接判定者再执行 `IBody2.Operations2(SWBODYINTERSECT)` 布尔求交。只有明确交集或成功且空交集才计为完成。
3. 全量复核 28 个顶层模组对：12 对由三维 AABB 证明分离，16 对精确候选全部完成，精确失败 0 对、待检查 0 对。
4. 16 对精确候选中 10 对无干涉、6 对有干涉，共发现 105 个干涉叶级实体对：A100–A800 1、A180–A200 11、A200–A700 1、A300–A800 74、A500–A800 10、A700–A800 8。
5. 旧 `ToolsCheckInterference2` 顶层组件检查曾把 A180–A200、A200–A700 判为无干涉；叶级展开后发现嵌套实体碰撞，因此旧结论由本节覆盖。A500–A200、A200–A300、A300–A700 仍确认无干涉。
6. A200–A800 的 114 个实体 AABB 候选经布尔求交全部为空，确认无实体干涉；这说明顶层/实体包围盒相交不能直接当作碰撞。
7. 机器摘要更新为 `LAYOUT_REPLAY_STATIC_BREP_INTERFERENCE_FOUND`，`success=false`、`productionReady=false`。当前 v3 装配体位姿持久化正确，但静态碰撞验收不通过，必须进入下一轮约束与求解校准。
8. C# Release 构建 0 警告/0 错误；此前完整回归仍为 307 通过、3 个既有 GUI 测试客户端能力缺口。实机精检结果文件为 `demo/FL9A24D062A000_interaction_v3_leaf_interference_*.json`。
## 2026-08-09 项目02第四轮约束校准与展示层复核

1. 根据v3全量叶级B-Rep的6组真实干涉，确认旧求解只表达载具扫掠区、漏掉传输固定导轨/支架禁入区；A200门洞与服务模组关系也过于粗糙。
2. `constraint_layout.py` 新增 `transportStaticKeepoutEnvelope`、`transportStaticKeepoutClearance`、服务簇候选排序、服务簇稀疏投影复核、可配置稀疏投影复核、CCD覆盖偏置、传输U向工艺偏置和供胶长轴锚定。
3. 项目02配置新增 A800 固定结构禁入区，A500/A700/A300组成 `dualValveServiceCluster`；A200覆盖向低侧偏置150 mm并扩展临时开口；T401放在龙门低侧68%长轴位置。
4. 修复 `prepare_source_independent_replay.py`：锚定A500时同步平移四类世界坐标包络，避免Replay文件中布局坐标与诊断包络不一致。
5. 展示层新增固定结构禁入区绘制与类型字段；浏览器实测成功显示 `carrier sweep`、`fixed rail keepout`、13/13、11/11、16/16和7.5 mm中心偏差。
6. 后端31/31单元测试、去原型双扰动测试、Python compileall和前端TypeScript/Vite生产构建通过。双扰动最大相对差为0，非法投影重叠0，containment relaxation 0。
7. 新的叶级工具结果增加相交叶实体对、双方世界AABB、AABB交叠区和判定方法字段；C#构建通过。由于SolidWorks残留进程均无窗口句柄且没有COM ROT注册，详细采集和新布局Replay没有执行；未强制关闭可能含未保存数据的实例。
8. 当前可交付的是离线第四轮解与展示结果；新三维装配体仍待干净SolidWorks会话闭环，`productionReady=false`。
9. 新增机器摘要 `demo/FL9A24D062A000_interaction_v4_offline_calibration_summary.json`；状态为 `OFFLINE_CONSTRAINT_CALIBRATION_CLOSED_SOLIDWORKS_REPLAY_PENDING`，不会覆盖v3的实体干涉证据。

## 2026-08-09 项目02 v5～v8 校准与闭环

1. 增加语义求解占地覆盖、去原型候选偏置优先级、求解后锚点微调及求解后投影CAD复核层；最终偏移后重新执行全部硬约束。
2. 确认真正基准轴为 `U≈-WorldZ`、`V≈-WorldX`、`N≈WorldY`。v6错误轴向导致8组/128个干涉实体对，随后按真实轴向修正。
3. v7精确检查降至4组/55对；v8只移动A200和A300后，离线约束达到13/13、11/11、15/15，传输中心偏差约7.515 mm。
4. v8 SolidWorks Replay 8/8、重建和保存成功，Errors=0、Warnings=0；磁盘重开姿态8/8通过，最大平移误差 `6.7924e-16 m`、完整姿态误差 `0°`。
5. v8三维AABB筛查28组，10组排除、18组进入精检；叶级B-Rep 18/18完成、失败0，最终剩余A100–A200 1对、A180–A200 5对、A500–A700 26对，共3组/32对。
6. 新增增量精检合并脚本 `scripts/merge_incremental_leaf_interference_results.py`；只复查发生姿态变化的组合，其余复用同姿态基线证据，并在汇总中显式记录来源。
7. 展示层暴露 `postSolveAllowedProjectedOverlapPairs`；单元测试增加求解后复核必须保留CAD验证标记的断言。
8. 当前最佳装配体为 `demo/FL9A24D062A000_8components_interaction_v8.SLDASM`，机器摘要为 `demo/FL9A24D062A000_interaction_v8_calibration_summary.json`。仍有3组静态干涉，`productionReady=false`；下一轮改为真实通道和多占用体建模，不继续盲调整体偏移。
9. 最终回归通过：Python `compileall`、后端31/31、前端TypeScript/Vite生产构建、去原型双扰动均成功；双扰动最大相对布局差为0，7个非龙门组件均与原型相差超过10 mm。自动化启动的无窗口SolidWorks进程已单独关闭，未影响其他会话。

## 2026-08-10 A200真实门洞、扫描通道和A500/A700多占用体

1. Bridge/MCP 新增叶实体包围盒采集，取得 A200 624、A500 62、A700 342 个实体证据；发布隔离运行包 `artifacts/solidworks-mcp-20260810-multibox`。
2. 求解器新增 `namedChannel`、`channelBodyBoxesLocal`、`occupancyBoxesLocal`、`multiBoxClearance` 和 `structureChannelContainment`，并把这些约束前移到候选生成/验证阶段。
3. A200 实测主门洞为 `[0.055,-0.1611]~[0.875,0.9975] m`、高度 `0~0.27 m`；A180 扫描头结构通道通过，A500/A700 各建立 3 个占用盒。
4. 修复多包围盒参与候选拒绝、视线遮挡、Portal 分类和求解后复核的若干旁路；去原型双扰动稳定为 0，结果为 13/13、11/11、19/19。
5. 后端 31/31、前端 TypeScript/Vite 构建通过。v10 Replay、保存及磁盘重开位姿复测通过，保存错误/警告为 0。
6. v10 叶级 B-Rep 16/16 完成，发现 5 组残差；原型同口径对照确认其中四组不是原设计接触。任务状态记录为 `REAL_CHANNEL_AND_MULTI_BOX_IMPLEMENTED_STATIC_BREP_RESIDUAL_5`，不得标记为完成或 `productionReady`。

## 2026-08-10 项目02结构骨架与联合求解

1. 新增 `scripts/build_structural_occupancy.py`，把叶体世界AABB转换为组件局部占用盒；修复 v8 捕获错误使用原型锚点的问题。
2. A100/A200/A800 使用精确干涉证据驱动的活动结构障碍（11/174/10盒），A500/A700 使用完整叶占用（62/342盒）。
3. 修复 A100 交互被整体跳过、真实占用体被投影白名单/传输扫掠旁路的问题；复杂功能件 AABB 假阳性显式降为 CAD 风险，不放宽动态扫掠硬约束。
4. 求解器增加有限候选联合 DFS、500节点上限、Top-3、评分、候选统计和碰撞矩阵。项目02用7个节点生成3个完整8模组方案。
5. 展示层增加方案切换、评分和节点数；预览 JSON/解 JSON 已更新。离线结果为13/13、11/11、34/34，双扰动相对布局差0。
6. 回归：constraint 24/24、preview 3/3、service paths 4/4，前端 TypeScript/Vite 构建通过。
7. CAD：v11因连接旧发布目录缺少底面映射而失败；v12改用 multibox 映射包但180秒超时，无结果文件、无截图、装配体时间未变化。本轮不得宣称 Replay/B-Rep 通过。
## 2026-08-10 项目02 A700 真实占地、快速求解与 v24 Replay

1. 修正 A700 `layoutFootprintBoundsLocal` 为实际范围 `[-0.13500001,-0.05600001,0.76389831,0.15550004]`；旧范围导致离线 100% 包含而真实 Replay 仅约 67.8% 的假通过。
2. 17×17、25×25 均匀网格和单纯龙门边界事件候选均未找到解。新增多包围盒/传输包络的解析碰撞边界修复搜索，参数带种子数、深度和候选总数硬上限。
3. 原型约束审计证明原型 A700 关系可行；失败不是物理空间无解。审计同时记录 A180 扫掠盒与 A300-A800 粗估约束偏保守，不把原型位姿用于候选生成。
4. 把 A700 放置优先级从 29 调为 15，求解顺序由 `A200 -> A180 -> A700` 改为 `A200 -> A700 -> A180`。单次完整求解从超过 300 秒降至约 3.76 秒。
5. Python compileall 与约束单元测试 26/26 通过；正式去原型双扰动测试在 8.7 秒内通过，最大相对差 `1.1102230246251565e-16 m`，工艺/空间/交互为 `13/13、11/11、36/36`。
6. 生成并 Replay `demo/FL9A24D062A000_8components_joint_v24.SLDASM`：8/8 移动、保存错误 0、保存警告 0，截图 `demo/joint_v24_replay_result.png`。重建调用成功但状态仍提示非冻结特征需重建。
7. 后续磁盘重开因 SolidWorks 多实例/COM 不健康失败：先是 ROT/COM 无法复用，后在隔离 Premium 实例 `OpenDoc6` 处发生 `0x800706BE`。未结束用户原型实例，也未宣称姿态或 B-Rep 已闭环。
8. 用 v23 已复测姿态进行同朝向平移投影宽相：A700 龙门覆盖率 100%，A800 86.8%，A200 88.2%；12/28 对确定分离，16/28 对待精确 B-Rep。该结果明确标记为非保存复测、非精确实体证据。
9. 当前状态为 `SOURCE_INDEPENDENT_LAYOUT_REPLAY_SAVED_REOPEN_AND_BREP_BLOCKED_BY_SW_RPC`，`productionReady=false`。

## 2026-08-17 项目 01/02/03/05/06 主要模组识别

1. 复核项目 02 既有识别链路，确认当前 8 个求解对象为 A100 龙门、A180 扫描、A200 产品 CCD、A300 排胶、A500 校准、A700 清洁＋称重、A800 输送＋定位、T401AA 供胶。
2. 通过 PPT 文字/流程、CAD 文件夹命名和 Windows Shell 离线缩略图，完成项目 01、03、05、06 主要子装配体的功能映射；全程未启动或修改 SolidWorks 源文件。
3. 项目 03 的 AA～AJ 平铺编号已分别识别为机架、龙门、Z 轴、顶升旋转、上层输送、下层回流、组合功能、校准、扫描和供胶，置信度为高，仍待装配树人工复选。
4. 确认跨项目不能采用“一个 CAD 对象只对应一种模组”的假设：项目 01/03 的组合功能模组承载清洁、称重、排胶和硬度检测；项目 02 的 A700 承载清洁和称重；项目 05/06 的 G000 承载校准和称重。
5. 新增 `docs/multi_project_module_identification-CN.md`、`demo/multi_project_module_manifest_v1.json` 和 `deliverables/module_identification_20260817/` 五组证据截图；JSON 格式校验及全部可直接解析的非空 CAD 编号存在性检查通过，缺失 0。

## 2026-08-18 项目02纯八模组 v3、全量精检与 v28 校准

1. 生成并保存纯八模组目标 `demo/FL9A24D062A000_8modules_clean_solved_v3.SLDASM`；前后顶层白名单 8/8、无额外底座/容器，主截图及六向视图已输出。
2. 保存后宽相路由 28/28：11 对直接分离，17 对进入叶级精检。17/17 均完整返回，11 对无干涉，6 对有干涉，共 57 个叶实体对：A100–A180 5、A100–A200 1、A100–A500 1、A180–A800 24、A200–A500 21、A300–A700 5。
3. A200–A800、A180–A200、A200–A300、A500–A700 等上一轮重点组合在 v3 中为 0 干涉；说明真实通道/多盒约束可以消除部分问题，但新姿态也会暴露其他结构接触，不能只做逐对局部修补。
4. 修复 B-Rep 汇总器只能识别 `batch*/` 子目录的问题；现递归读取批量结果，机器摘要正确报告 `STATIC_COLLISION_INTERFERENCE_FOUND`、完整 17、干涉 6/57、缺失 0。
5. `build_structural_occupancy.py` 改为从每个证据版本自己的 Replay 结果读取持久布局；修复旧证据错误绑定到可变最新 Replay 文件的问题。v28 占用体已重新构建，并加入 v3 六组精检证据。
6. 扫描模组 A180 固定为源方向，避免 v3 中 180° 反向；离线投影升级为保守平面刚体投影，支持旋转后的世界 AABB 宽相。
7. 求解候选交互验证改为增量复核新模组相关组合，单元测试通过；最终方案仍执行全组合验证。
8. v28 在 1 解/5 候选的快速校准模式下仍超过两分钟预算，已主动中止，未覆盖 v27 结果、未创建 v4 装配体、未再次运行 SolidWorks。下一项是多包围盒边界候选的去重、支配剪枝和责任盒局部化，而非继续消耗 CAD 精检时间。
9. 定时堆栈采样确认热点位于 `_occupancy_envelopes`、`_overlapping_envelope_pairs` 和候选过程约束复核，而非 SolidWorks/B-Rep。新增位姿占用体缓存、伙伴证据预筛选、候选相关模组增量复核及首个硬失败即停；27/27 约束单元测试和 Python 编译通过。
10. 优化后完整 v28 预览仍未在 60 秒快速闸门内结束；测试被主动中止，未写出新解。机器状态写入 `demo/layout_previews/project02_v28_iteration_status.json`，后续继续做失败分支候选缓存与责任盒支配剪枝。

## 2026-08-18 项目02方案 1 v4 Replay 与条件精检

1. 展示层 rank 1 已获用户授权，生成 A200 锚定的 `demo/layout_previews/project02_selected_solution_replay_v4.json`。
2. 从空白装配体生成 `demo/FL9A24D062A000_8modules_clean_solved_v4.SLDASM`；8/8 插入、8/8 Replay、前后白名单 8/8，保存无错误/警告，六向视图齐全，原型未覆盖。
3. 真实世界 AABB 完成 28/28 路由：13 对直接通过、严格 AABB 失败 0、15 对进入叶级 B-Rep。
4. 条件 B-Rep 15/15 完整返回：11 对无干涉；4 对有干涉，共 11 个叶实体对——A100–A200 2、A200–A700 2、A300–A800 4、A500–A800 3。
5. 结果写入 `demo/layout_previews/project02_8modules_clean_solved_v4_brep_summary.json`，状态为 `STATIC_COLLISION_INTERFERENCE_FOUND`。本次闭环证明分层检查能减少 13/28 的精检开销，但当前解仍需回灌四组叶级占用证据后重新求解，禁止手工挪动冒充求解闭环。
## 2026-08-18 项目02 v29/v30、v5/v6 分阶段修复

1. v29 回灌 v4 的 11 个真实干涉叶体证据，并将联合候选上限由 5 增至 12、搜索时限由 20 秒增至 60 秒。意义：修复证据增多后因过早截断造成的伪无解，同时不放宽硬约束。
2. 从展示层确认的 rank 1 生成 `demo/FL9A24D062A000_8modules_clean_solved_v5.SLDASM`；白名单 8/8、保存错误/警告 0，28 组宽相路由为 14 组直接排除和 14 组精检候选。意义：确认“求解—展示—确认—纯模组 Replay—宽相”的链路仍可闭环运行。
3. 对 v4 的四组历史失败执行优先精检并首个硬失败即停：A200–A700、A300–A800、A500–A800 均为 0，A100–A200 为 13。意义：三组问题已由通用约束消除，并避免为已失败候选继续消耗全量 B-Rep 时间。
4. 分别试验 A100–A200 的完整子装配体 AABB 和全部叶体 AABB 硬覆盖，均导致 A200 候选为 0，随后撤回；保留通用可选框架并修复精确盒数量元数据。意义：确认该组合属于非凸嵌套关系，不能用完整包围盒严格分离替代实体精检。
5. 生成 v30 占用证据并把 A100–A200 标记为 CAD-only；使用非原型修复种子后离线求解约 0.864 秒，指标为工艺 13/13、空间 11/11、交互 36/36、传输中心偏差约 7.5 mm；42/42 单元测试与 Python 编译检查通过。意义：保持快速求解，同时把复杂组合的最终责任明确留给精确门禁。
6. 生成 `demo/FL9A24D062A000_8modules_clean_solved_v6.SLDASM` 并先检查 A100–A200，检出 56 个干涉叶实体对，立即停止其余精检。意义：证明该修复方向恶化，快速淘汰候选，避免把耗时花在必然失败的全量检查上。
7. 新增机器状态 `demo/layout_previews/project02_v29_v30_v6_iteration_status.json`，明确状态为 `A100_A200_EXACT_BREP_REPAIR_PENDING`、`productionReady=false`。下一步为少量 U/V 二维候选搜索和单对精确门禁，通过后再做完整条件 B-Rep。
## 2026-08-18 A100–A200 有界候选、锁定语义与模型矛盾定位

1. 新增有界候选脚本 `scripts/generate_a100_a200_repair_candidates.py`，支持自定义 U/V 种子、去重、逐候选硬约束求解、失败原因持久化、非目标漂移统计和机器清单。意义：把反复手工移动/整套精检改为可审计的小预算搜索。
2. 第一版 6 个种子得到 4 个不重复解，但 A300 漂移约 593 mm；候选 1/5 的 A100–A200 精检为 22/11。意义：证明仅有硬约束通过还不足以称为“局部修复”，展示/漂移门禁必须在 CAD 前执行。
3. `ConstraintLayoutOptions` 新增 `warm_start_locked_components`，并通过展示层选项构造器传递；局部修复时锁定 A180/A300/A500/A700 与目标 A200。意义：只改变目标关系，防止求解器通过重排其他模组掩盖问题。
4. 修复锁定候选仍被 `collisionRepairSeedLimit` 扩展的问题；锁定组件现在自动关闭碰撞修复扩展。新增回归测试，验证求解结果与指定 A200 热启动位置一致。意义：使“锁定”从排序偏好变成真正硬语义。
5. v2 生成 6 个精确局部候选，非目标漂移均为 0，单候选约 0.04 秒；候选 1 Replay 为纯 8 模组、白名单 8/8、保存错误/警告 0，但 A100–A200 仍有 13 个干涉叶体，按策略停止其余精检。
6. 原型 A100–A200 参考精检为 0，相对位置约 `(0.100,-0.991) m`。以其为审计中心生成的 6 个 v3 精确候选，在锁定修复后全部离线失败：3 个由 A200–A800 叶占用盒拒绝，3 个由工艺约束拒绝。意义：明确当前瓶颈是通道/工艺约束模型与真实零干涉区域不一致，不是缺少更多 B-Rep 次数。
7. 锁定修复前曾把一个非请求位置 Replay 为 `demo/FL9A24D062A000_8modules_channel_repair_c01.SLDASM`，A100–A200 检出 130 个干涉叶体。该文件标记为回归反例，不得作为候选或成果装配体。
8. 相关回归 43/43、Python 编译和关键 JSON 解析通过；状态写入 `demo/layout_previews/project02_a100_a200_repair_iteration_status.json`。下一步复核 A200 门洞、A800 通过体与工作位约束的局部坐标后再生成 CAD。

## 2026-08-20 项目02 v31 条件 B-Rep 规则贯通与数值展示门禁

1. 修复多包围盒验证未读取成对条件 B-Rep 策略的问题。意义：非凸框架/门洞不再被叶 AABB 空角误杀，同时普通模组重叠仍保持硬拒绝。
2. 新增两项回归：条件 B-Rep 组合的叶盒重叠可延后但门洞过窄仍失败；非条件组合的叶盒重叠仍为硬失败。意义：证明本次不是全局放宽碰撞约束。
3. 重建 `FL9A24D062A000_structural_occupancy_v31.json`，将 A100–A200、A200–A800 设为 CAD-only 证据组合；原型 A200–A800 精确参考为 0，且当前门洞规则通过。意义：历史精检证据不再封死真实可用的非凸通道。
4. v31 去原型求解约 0.707 秒，得到 1 个八模组解：工艺 13/13、空间 11/11、交互 36/36、传输中心偏差约 7.515 mm、严格 AABB 失败 0、求解 B-Rep 0 次。意义：恢复快速迭代，不把耗时转移回 CAD。
5. 新增 `audit_project02_preview_gate.py` 与机器结果 `project02_v31_numerical_visual_gate.json`；数值门禁全部通过，列出顶层外形越界和五组优先 CAD 组合。意义：把“指标通过”和“人工目测通过”分开记录，避免误报。
6. 修复展示候选的 B-Rep 预计数使用搜索期旧值的问题；按最终物化候选重算后为 16 组。意义：保证后续真实 AABB/B-Rep 路由不漏组合。
7. 自动展示页检查因应用内浏览器 localhost 安全策略被阻止；A200 顶层外形低 V/高 U 越界约 139.6/104.9 mm，保留为人工复核项。当前没有健康 `sldworks.exe` 主进程，因此未物化视觉批准、未 Replay、未运行 B-Rep。
8. 回归通过：49/49 单元测试、Python 编译。状态写入 `demo/layout_previews/project02_v31_iteration_status.json`，为 `V31_NUMERICAL_GATE_PASSED_VISUAL_APPROVAL_PENDING`、`productionReady=false`。

## 2026-08-20 项目02 v32 CCD工艺轴与有限越界

1. 求解器新增 `maximumPortalGantryCenterOffsetMeters` 和 `maximumPortalGantryOverhangMeters`，并与既有最小轴向覆盖率共同组成 CCD—龙门三项空间硬约束。意义：不要求整个 CCD 顶层包围盒完全包含，但限制偏心和无限伸出。
2. A200 短轴偏置由 `-0.15` 改为 `0`，最小覆盖率由 `0.75` 提高到 `0.85`；项目02阈值为中心偏差 `30 mm`、单侧越界 `160 mm`。意义：恢复 CCD、传输和龙门的共同工艺轴。
3. 展示页新增覆盖率、中心偏差、最大越界三项指标，审计脚本升级为 v32；A300/A700 明确记录为非凸嵌套、条件 B-Rep 组合。意义：在进入 CAD 前即可解释边界合理性和精检路由。
4. 新解通过工艺 13/13、空间 13/13、交互 36/36；CCD 覆盖约 91.1%、中心偏差约 0.8 mm、最大单侧越界约 104.9 mm；预计条件 B-Rep 为 15/28 对。
5. A700–A200 仍有 7 组粗占用盒命中，列为人工目测和条件 B-Rep 优先项。后端测试 50/50 通过；状态保持 `productionReady=false`，未执行本轮 SolidWorks Replay。
6. 重启当前项目后端并通过真实 `POST /api/demo/cases/project02/solve-preview` 冒烟测试；前端 `5173` 与后端 `8000` 均可访问。意义：确认浏览器运行实例已加载 v32 代码，而不只是磁盘测试通过。

## 2026-08-20 项目02 v33 A300/A700 专项实体闭环

1. 原型审计得到 A300 相对 A700 锚点约 `(0, 0.1081) m`，原型精检为 0；v32 诊断 Replay 则检出 5 个干涉叶实体对。
2. 新增通用 `relativeAnchorWindow` 硬约束，并修复相对约束参考模组未进入候选缓存依赖的问题。意义：由实体失败反推工艺关系，而不是在 SolidWorks 中直接拖动组件。
3. v33 离线解通过 14/14 工艺、13/13 空间、36/36 交互约束；Replay 到 `demo/FL9A24D062A000_8modules_clean_solved_v33.SLDASM`，白名单 8/8、保存错误/警告 0。
4. v33 A300/A700 专项叶级 B-Rep 完整、失败 0、干涉 0。展示层新增相对锚点指标，机器状态写入 `demo/layout_previews/project02_v33_a300_a700_iteration_status.json`。
5. 回归 51/51、Python compileall、前端生产构建、v33 数值审计通过。当前只证明该模组对已消除干涉，其余条件组合未全部验收，`productionReady=false`。
6. 真实接口冒烟测试发现 8000 端口仍为旧后端，已仅结束 PID 50848 并启动当前版本；重新求解返回 14/14、13/13、36/36。应用内展示页已确认新增锚点差和复核项可见。

## 2026-08-24 项目02 A500–A700“距离8”配合导出重建闭环

1. 新增两个顶层子装配体直接配合的导出、候选发现和 RoundTrip MCP 工具；配合端点记录到叶组件、实体索引、面索引、面积和源持久引用。意义：不再只依赖最终位姿，可将面级设计意图作为中间态重建。
2. 候选发现由逐模组对重复遍历 MateGroup 改为单次遍历后分组。意义：消除项目02八模组候选搜索的主要重复耗时。
3. A180–A800 真实检查确认直接顶层配合为 0；候选搜索找到 A200–T401 的“距离28”和 A500–A700 的“距离8”。选用两个已明确功能模组之间的“距离8”作为 Demo。
4. 修复测试输出相对路径冲突并新增 `--roundtrip-only`；修复真实子装配体首次 `AddComponent5` 失败时缺少预加载重试。意义：保证禁止覆盖门禁不被绕过，同时兼容大型真实子装配体。
5. “距离8”实际为 50 mm 的反向对齐面—面距离配合。A500、A700 两端分别以实体/面索引 `0/11`、`0/3` 找回，AddMate 返回 `swAddMateError_NoError`。
6. 新装配体保存并重新打开成功，预期/观察配合数量为 1/1、类型均为 `swMateDISTANCE`；真实闭环状态为 `SUCCESS`。应用构建 0 错误/0 警告，装配服务测试 17/17 通过。
7. 证据：`demo/project02_A500_A700_distance8_roundtrip_v3.SLDASM`、`.mates.json`、`.result.json`；说明见 `docs/project02_mate_pair_roundtrip-CN.md`。

## 2026-08-25 项目02“需求 → 模组 → 布局求解”第一阶段 Demo

1. 新增项目02确定性需求规则引擎，覆盖点胶、传输、定位、扫码、视觉、校准、清洁、称重、排胶和供胶十类能力，并将能力映射到 A100、A180、A200、A300、A500、A700、A800、T401。意义：将自然语言需求与 CAD 模组标识解耦。
2. 新增工艺依赖闭包、否定识别、产品数量提取、必选/可选分级、推荐理由、缺失信息和能力覆盖审计。意义：推荐结果不仅给出“选什么”，还说明“为什么选”和“还缺什么”。
3. 新增 `/recommend-modules` 与 `/confirm-modules` 接口，并把最新推荐和确认结果持久化到 `demo/requirements/`。意义：形成可复核的中间数据，不让前端选择直接绕过后端规则。
4. 展示页新增项目02需求输入、能力标签、模组卡片、可选项选择和人工确认；完整八模组确认后自动衔接现有快速布局求解。意义：走通“提出需求—推荐模组—人工确认—布局展示”的最小业务闭环。
5. 当前求解器兼容性门禁明确限制为项目02完整八模组；子集可推荐，但不会误送入固定八模组求解器。意义：避免把尚未实现的动态子集求解包装成已完成能力。
6. 测试通过：专项 6/6、后端完整 57/57、Python 编译、前端生产构建、真实 HTTP 三接口闭环和浏览器展示复核。默认完整需求得到 10/10 能力覆盖、8 个必选模组；确认后求解为工艺 14/14、空间 13/13、2.5D交互 36/36。
7. 说明文档：`docs/project02_requirement_to_modules_demo-CN.md`。当前仍为 `productionReady=false`；本阶段没有替代 Replay、条件 B-Rep、运动扫掠和维护空间验收。

## 2026-08-25 项目02静态实体无干涉闭环 v34（离线分级阶段）

1. 新增 `static_collision_closure.py`，以模组对相对U/V/方向、精检完整性和源CAD修改时间共同判断旧B-rep证据能否复用。意义：全局平移不再触发重复精检，真实相对移动或几何修改仍会强制失效。
2. 规划器读取v33保存后回采的真实世界三维AABB，并按每侧10 mm膨胀执行宽相。18组条件策略组合中A200–A500、A200–T401、A300–A700、A500–A700四组可直接排除，剩余14组进入精检。意义：用保存实体证据缩小B-rep范围，而不是用二维展示边界冒充CAD结论。
3. 将待检组合划分为P0～P3：P0仅A100–A200；P1为A200–A700/A800；P2为历史干涉回归；P3为剩余组合。意义：主要阻塞失败时立即回灌，不为必然淘汰的方案运行后续精检。
4. `capture_leaf_interference_details.py` 新增 `--stop-on-first-interference`，批结果记录请求/完成数量和提前停止状态。意义：落实“首个硬失败即停”。
5. 新增 `run_project02_priority_brep_gate.py`，每次只执行一个批次，并在SolidWorks实例数超过1时拒绝运行。意义：避免多实例环境把精检结果绑定到错误文档。
6. 新增6项专项回归；后端完整63/63、Python编译通过。机器清单为 `demo/layout_previews/project02_v34_static_collision_execution_plan.json`。
7. 本机预检发现19个残留SolidWorks进程，P0执行器按设计拒绝运行。本轮状态为 `PRIORITY_BREP_READY_CAD_SESSION_CLEANUP_REQUIRED`，尚未宣称A100–A200或整机无干涉。说明见 `docs/project02_static_collision_v34-CN.md`。

## 2026-08-26 项目02 v34 真实联合修复与约束冲突定位

1. 修复专用模组候选生成时 A200 被默认重复偏移的问题；未显式指定 A200 偏移时现在保持原位。意义：局部修复不再破坏已闭环关系和证据复用。
2. 修复锁定 T401 未采用热启动位姿的问题；A100–A800 提升为早期精确门禁。意义：供胶和传输修复能够真实进入求解，并尽早淘汰龙门/传输错误解。
3. 新增 `exit_solid_works` 生命周期工具，以及 Replay/B-rep 批处理退出选项；工具要求显式确认文档已保存。实测当前DCOM环境中`ExitApp`返回后进程未退出，已增加15秒进程数复核并在未下降时返回失败。意义：避免把退出请求误报为已回收；管理员清理/重启仍不可替代。
4. 真实 Replay/B-rep 定位：原方案 A500–A700 为31对；A500 400 mm 后 A100–A500 为1对；450 mm 后 A100通过但 A200–A500为47对。
5. 联合窗口实验显示：A200轴向40–110 mm会碰龙门；30 mm时龙门两对通过但A200–A500仍有21对。A700避让又与A180膨胀体冲突，A180继续移动会越过龙门边界。
6. 当前确定为“几何语义重新标定后再求解”，不是继续逐对拖动。需复测A500服务点、A700/A730占用体、A180扫描占用/通道和A200门洞外框。状态写入 `project02_v34_constraint_conflict_status.json`，保持 `staticCollisionReady=false`。
7. 后端完整69/69、排除真实视觉集成项的C#单元回归312/312、compileall和MCP Release构建通过；完整C#视觉集成测试受当前多实例CAD环境和既有集成桩限制未全绿，已如实记录。
8. 本轮结束时仍有11个无窗口SolidWorks进程且普通权限无法结束；已停止继续CAD调用，防止实例继续累积。

## 2026-08-26 项目02 A500 标定服务区与结构前置门禁 v35

1. A100 新增 `calibrationServiceZone`，A500 通过通用 `serviceRegion` 自动形成专用服务点硬约束。意义：双阀可达不再等价于“龙门内任意夹缝都可放置”。
2. 新增 `protectedSpaceBoxesLocal`，为 A500 建立阀头垂直接近通道和维护侧保护带。意义：把非实体但必须保持为空的操作空间纳入候选淘汰，而不是等 Replay 后目测发现。
3. 新增 `hardOccupancyClearanceWith` 与成对叶盒净空。A500–A100/A200 顶层盒可重叠，但实测叶盒碰撞会在离线求解阶段硬失败；条件 B-Rep 复核义务不变。意义：同时保留门架空腔和提前拒绝实体明显冲突两种语义。
4. 去原型求解得到 1 个八模组解，工艺 15/15、空间 13/13、交互 38/38；A500–A100/A200 粗占用命中为 0，两项保护空间通过。
5. 后端完整回归 72/72，前端生产构建和数值展示审计通过。A500–A700 仍有 12 组粗命中，状态保持 `staticCollisionReady=false`、`productionReady=false`。
6. 本机仍有12个残留SolidWorks进程，本轮没有启动 CAD Replay/B-rep；下一步先在展示层目测方向、边界和明显接触，再进入单会话条件精检。

## 2026-08-26 项目02条件叶盒风险降序与展示 v36

1. 对 A500–A700、A700–A200 和四组历史高风险组合进行叶盒硬化试验，单次 60 秒均未收敛。意义：确认不能继续用“逐对硬化/逐对挪动”替代非凸结构的条件 B-Rep 路由。
2. 联合搜索新增条件叶盒预命中软排序和评分项。意义：不放宽既有硬约束，也不把 AABB 假阳性当实体干涉，同时优先输出后续 CAD 精检成本更低的解。
3. 新解继续通过 15/15 工艺、13/13 空间、38/38 交互约束；条件叶盒预命中由 23 降到 9（约减少 61%），只剩 A500–A700 为 6、A180–A200 为 3。
4. 预览数据新增保护空间、逐对叶盒风险和总命中数；前端新增保护空间框、风险连线/数字和优先复核列表。意义：使用者可以在 Replay 前区分“工艺保护空间”“宽相风险”和“实体干涉结论”。
5. 后端完整回归 73/73，Python compileall 与前端生产构建通过；当前预览已重新持久化。状态仍为 `staticCollisionReady=false`、`productionReady=false`，下一步是单会话 Replay 后优先精检两组残余风险。
6. 用户要求继续后已固化 v36 rank 1，选中布局为 8/8 模组，目标 v36 装配体尚不存在；新增 CAD 执行计划，固定 P0 A500–A700、P1 A180–A200。意义：系统恢复后可直接 Replay，不需重算或人工拼接命令。
7. 优先 B-Rep 执行器的证据输出由固定 v33 目录改为按当前装配体 stem 隔离。意义：避免不同 Replay 版本的叶级证据串用。
8. 单会话预检发现 12 个残留 SolidWorks；管理员清理仅结束 1 个，剩余 11 个主进程对 `Stop-Process` 和 `taskkill /F /T` 均拒绝访问。为保证证据归属，未启动新 SolidWorks、Replay 或 B-rep；状态为 `CAD_SESSION_CLEANUP_REQUIRED`。

## 2026-08-26 项目02 v36 CAD Replay 与 P0 实体门禁

1. 完全访问权限下用管理员 UAC `taskkill` 成功清空残留 SolidWorks 进程。意义：恢复单会话 CAD 自动化条件，无需重启系统。
2. 修复 `replay_project02_selected_solution.py` 的退出兼容性：主 Replay 成功证据先落盘，可选退出另行尝试。意义：旧 MCP 缺少退出工具时不再把成功的装配、保存和截图误判为整体失败。
3. v36 正式装配体已保存，8/8 模组、保存错误 0、警告 0，并生成六视图。重新打开后，保存前后世界变换与世界包围盒逐元素误差均为 0。
4. `validate_reopened_layout_capture.py` 增加 `--replay-result` 世界变换复核模式。意义：新装配体没有底面映射时仍可验证“磁盘保存—重新打开”的位姿稳定性。
5. 执行 P0 A500–A700 叶级 B-rep：21,266 个实体对经 AABB 降至 13 个精确候选，12 个实体干涉、0 个失败。门禁按设计阻断 P1，没有进行人工拖动。
6. 状态更新为 `P0_INTERFERENCE_FOUND_CONSTRAINT_FEEDBACK_REQUIRED`。下一版需将 A500/A510 与 A700/A720 的真实叶体占用回灌求解器，再生成 v37；当前仍不能宣称项目02全模组零干涉。

## 2026-08-26 项目02 v43 精确相对关系与 Replay 稳定性闭环

1. `relativeAnchorWindow` 增加精确中心候选，热启动增加 2/5 mm 局部细化；A500–A700 相对锚点稳定为 `(215, 52) mm`，离线门禁为工艺18/18、空间13/13、交互38/38。意义：用毫米级联合候选替代大范围碰撞修复，显著缩短求解并避免网格误差。
2. MCP Replay 新增 `sourceAnchorTransform`，以源组件局部锚点和目标基轴直接恢复刚体位姿，缺少旧字段时回退面探测。意义：降低面持久引用、拓扑索引和装配配置变化导致的错面风险。
3. v41 面探测 Replay 导致 A500–A700 53 对干涉；v42 源锚点 Replay 将顶层相对原点恢复到数值精度，但干净容器仍有11对，定位为子装配体内部柔性/配置状态漂移。
4. v43 在原型上下文 Replay 后，P0 A500–A700 为0对，完成闭环；P1 A180–A200 为3对，而原型基线为0，确认当前新解仍有真实布局问题。
5. 单独移动 A180 或 A180/A200 回原型相对位姿分别破坏龙门边界、CCD工艺轴或传输扫掠。下一步改为 A180/A200/A800 三模组联合校准，并将 A180–A200 设为早期 CAD 门禁。
6. 当前最新验证文件为 `demo/FL9A24D062A000_prototype_context_solved_v43.SLDASM`，它保留原型非目标上下文，不是纯八模组成品。状态为 `P0_CLOSED_P1_INTERFERENCE_REQUIRES_TRIAD_RECALIBRATION`，仍保持 `productionReady=false`。

## 2026-08-27 项目02 v44～v46 静态无干涉与重开闭环

1. 增加 A200–A800、A180–A200 联立相对窗口及事件锚点；修正 A200 外框中心与相机工艺轴混淆、扫描器不得接近传输扫掠的错误假设。
2. v44 A180–A800 精检发现 2 对干涉，回灌 `V>=228 mm` 扫描横向净空；候选排序改为条件 B-rep/叶盒风险优先，扫描相关叶盒候选降为 0。
3. v45 A200–T401 精检发现 12 对干涉；解除 T401 旧热启动锁定，新增 T401–A200 服务窗口并让供胶放置器参与窗口锚点、工艺和叶盒排序。新解 1.8 秒，工艺22/22、空间13/13、交互37/37，A200–T401 叶盒候选降为0。
4. v46 Replay 成功，8个目标模组均使用 `sourceAnchorTransform`，保存错误/警告为0，最终无需重建。A500–A700相对变换与v45最大差 `1.66e-9`，通过新脚本复用v45精确零干涉证据。
5. 从零进程重开v46后，8/8世界变换误差0，包围盒最大差 `7.34e-9 m`。修复重开验证器按目标模组过滤原型上下文并容纳10 nm重建噪声。
6. 状态升级为 `STATIC_COLLISION_AND_REOPEN_CLOSED`、`staticCollisionReady=true`；仍保持 `productionReady=false`。最新文件：`demo/FL9A24D062A000_prototype_context_solved_v46.SLDASM`。

## 2026-08-27 项目02 v47～v48 覆盖审计与原型基线等价验收

1. 对 v46 的条件组合继续审计，发现部分 `leaf AABB hit=0` 来自不完整占用覆盖；补做 A200–A800 精检得到 1 对干涉。此前 `STATIC_COLLISION_AND_REOPEN_CLOSED` 结论由本条明确撤回，后续以 v48 状态为准。
2. 收紧 A200–A800 原型支持相对窗口，v47 精检为 0；随后发现 A800–A700 有 8 对精确接触，再增加 A700–A800 服务侧相对窗口并生成 v48。
3. 新增 `compare_interference_pair_baseline.py`，按叶组件实例身份比较候选与原型的干涉集合。意义：不只比较干涉数量，能够识别是否新增了不同的碰撞对象。
4. 原型与 v48 的 A800–A700 均为同一 8 对，新增/缺失集合均为空；该组合在当前模组划分下包含 A720/A730 与 A860 的共享或嵌套机构边界，验收策略改为“相对原型无新增干涉”。
5. A100–A200、A100–A800、A200–A800、A500–A700 通过相对刚体变换门禁复用完整零干涉证据；后端完整回归 79/79、Python compileall、前端生产构建通过。
6. v48 求解约 1.35 秒，工艺23/23、空间13/13、交互37/37；Replay 保存成功。隔离磁盘重开时 SolidWorks 在 OpenDoc6 阶段退出，未生成 v48 重开位姿证据，状态为 `STATIC_COLLISION_BASELINE_EQUIVALENT_REOPEN_RETRY_REQUIRED`。
7. 最新装配体：`demo/FL9A24D062A000_prototype_context_solved_v48.SLDASM`；机器状态：`demo/layout_previews/project02_v48_cad_execution_plan.json`。静态分级碰撞门禁通过，但运动扫掠、软管、维护空间、真实服务点和其他项目校准仍未完成，`productionReady=false`。

## 2026-08-28 项目02全量模组级配合图

1. 新增 `ExportModuleMateGraph`，把A600加入结构基准节点，并一次导出全部请求模组之间的二元顶层配合、端点身份及持久引用。
2. 新增配合束归并：同一具体模组实例对的多条Distance/Coincident/Parallel/Width/Slot等配合形成一个安装关系候选；不把无向图冒充装配顺序。
3. 首次真实遍历发现“每端点线性扫描3336组件”的性能问题，改为一次性COM组件身份索引；意义是把端点归属从O(配合数×组件数)降为近似O(组件数+配合数)。
4. 修复轻量化组件被误判为压缩，以及两个T401实例被令牌合并的问题；当前记录真实压缩枚举，并按层级路径区分实例。
5. 项目02真实原型结果：10个实例、27条跨模组配合、10个配合束；A600是明显中心节点，A600–A800存在Width+Coincident定位束，A180只与A600直接配合而不与A800直接配合。
6. 机器校验全部通过，状态为 `PASS_READ_ONLY_GRAPH_EXPORT_SEMANTIC_CONSTRAINTS_PENDING`。这证明机械安装关系可以从原型提取，但操作面、条码/视场、工作位、服务点、双阀行程和装配先后仍需语义层。
7. 输出：`demo/layout_previews/project02_module_mate_graph_v2.json`、`.summary.md`、`.validation.json`；详细记录见 `docs/project02_module_mate_graph-CN.md`。
## 2026-08-28 · A600锚定装配顺序门禁

- 新增 `assembly_sequence.py`，将机械工程师确认的五阶段装配顺序编译为可审计就绪度计划。
- 项目02请求接入真实模组级配合图，并显式记录操作面、厂商XYZ和操作侧空间的确认状态。
- 展示页新增五阶段卡片，区分正式就绪、暂估证据和阻塞输入；当前八模组解不再被误称为A600锚定顺序解。
- 新增机器校验脚本及输出，状态为 `PASS_SEQUENCE_GATE_EXPLICITLY_BLOCKED_PENDING_MEASUREMENTS`。
- 后端完整回归81/81通过，前端生产构建通过，项目02Top-3粗排仍可生成。
- 修改意义：将“先箱体、再传输、再扫描、再功能侧、最后龙门”的工程原则变成可执行开发门禁，为下一步捕获A600和逐阶段替换暂估参数建立闭环。

### 操作面确认与服务侧规则

- 工程师确认A600为 `FL9A24D062A600.001`，当前选中正面大平面为现实操作面。
- 新增服务侧工程规则：A700/A500/A300优先靠近操作面；有效空间不足时切换至对侧。
- 顺序门禁现分别记录 `operationFaceConfirmed=true` 与尚未解析的局部 `operationSide=unknown`，避免把人工语义确认和坐标轴映射混为一项。
- 新增 `capture_project02_a600_operation_face.py`。只读探测发现当前MCP/COM连接进入无文档实例，因此主动拒绝写入面映射并清理测试实例；可见原型会话未受影响。
- 修改意义：让人工工程概念成为正式约束证据，同时保持几何记录必须精确、可复核的质量门禁。

## 2026-08-28 · A600三平面工程安装坐标系与顺序门禁闭环

- 配合图Schema升级到`solidworks-module-mate-graph/v1.2`，端点增加面局部/世界中心及法向，同时保留实体/面索引和持久引用。
- 从真实原型的`重合35`恢复A600传输支承/上部安装平面，从`宽度9`两张A600定位面恢复传输中心面，并结合已确认操作面构造右手工程坐标系。
- 生成 `project02_a600_installation_frame.json`：三平面残差接近机器精度，7/7检查通过，操作面映射为`front`。
- 顺序门禁新增安装坐标系证据读取；预览不再阻塞于底面或操作侧映射，只保留A600整体几何、厂商XYZ、扫描/条码、操作空间、双阀行程与服务点等真实缺口。
- 后端82/82、非集成C# 319/319及两项项目02机器校验通过。原型仅只读导出，没有移动、保存或覆盖。
- 修改意义：用“操作面＋上部支承面＋传输中心面”替代不必要的底面捕获，使装配顺序与机械工程师实际定位逻辑一致，并为A600→A800顺序求解提供稳定坐标中间态。

## 2026-08-28 · A600粗安装面、结构禁入区与A800原型接口

- 新增A600/A800只读采集器，并将叶体采集从“任一Body Box失败即中止”改为“保留成功体、报告失败体及覆盖率”。真实结果为708个有效体、2个失败体，覆盖率`99.718%`。
- 在A600工程坐标系中生成30 mm内缩安全边界、A800支承区、18个栅格合并硬禁入区；一个覆盖约92%平台的非凸上机架AABB进入条件结构，不作为实心硬障碍。
- 将A800原型位姿和包围盒转换到A600工程坐标系；包围盒中心相对传输中心面偏约`5.61 mm`。原型值只作为粗排种子和审计证据，厂商XYZ仍未确认。
- 顺序门禁第一阶段升级为`ready`，展示页新增A600安装边界/A800支承区/禁入区小地图及覆盖率说明；剩余4阶段继续阻塞真实缺口。
- 后端83/83、非集成C# 319/319、前端构建以及安装面、配合图、装配顺序机器校验通过。原型只读，未移动或保存。
- 修改意义：将站体结构第一次作为求解边界而非背景模型，同时通过覆盖率和条件结构路由避免保守AABB造成“整个平台不可用”的假失败。

## 2026-08-28 · A600–A800配合面派生接口

- 新增`build_project02_a800_mate_interface.py`，从真实`重合35＋宽度9`配合端点恢复A800安装接口，而不是使用偏离实体的组件原点。
- 运动学分析确认：Y、Z和姿态由配合束锁定，沿传输长轴X仍保留一个平移自由度；配合特征投影粗基准为`(0.3763,0,0) m`。
- 顺序门禁新增配合面证据和逐轴置信度，缺失项从“完整厂商XYZ”收缩为“长轴X端面/销孔基准确认”；展示页同步说明该证据边界。
- 后端84/84、前端构建、顺序门禁15/15检查通过。修改意义：复用装配设计信息减少人工输入，同时防止把原型特征站位误当厂商硬尺寸。

## 2026-08-28 · A600操作面连接恢复与精确记录

- 确认可见原型仍为唯一SolidWorks进程，当前所选正面大平面保持不变；仅清理了绑定到旧无文档实例的残留MCP进程。
- 以与SolidWorks相同权限恢复COM连接；只读探测确认所选面属于A600子树，世界中心约为 `(-0.894279, 0.025029, -0.305877) m`，世界法向约为 `(-1, 0, 0)`，面积约为 `0.373067 m²`。
- 已将该面正式记录为 `操作面`，包含叶组件层级路径、局部中心/法向、世界法向、面积和SolidWorks持久引用；没有移动、保存或覆盖原型装配体。
- `capture_project02_a600_operation_face.py` 的恢复探测改为轻量路径，默认不再遍历大型装配树；全量顶层位姿枚举改为显式 `--include-pose`，避免把成功连接误报成60秒超时。
- 后台MCP Hub已恢复；同权限代理复核再次读取同一选中面成功。修改意义：后续可以稳定复用原型会话继续捕获A600底面、局部坐标系和A600-A800安装接口，同时避免重复启动无文档SolidWorks实例。

## 2026-08-28 · A800案例锚点、扫描优先与A100逆向覆盖

- 项目02新增`caseSpecificPrototypeAnchor`：相对约束联合求解后整组平移，A800精确复用捕获锚点`(0.720,-0.405) m`；该值只在项目02生效。
- 取消A100热启动锁定，A180求解优先级升至1；A200和A500/A700/A300随后参与联合回溯。
- 新增功能模组操作面容量分支接口，输入未确认时保持不激活，不猜测侧别。
- 新增A100逆向覆盖报告；当前6个唯一工艺点、8条可达约束的锚点交集非空，所选A100锚点在交集内。
- 展示页改为明确显示“相对约束去原型”和“A800项目02案例锚点”，并增加逆向覆盖审查项。
- 修复Top-3候选仍使用锚定前内部坐标的问题；三个候选中的A800中心现在均为`(0.720,-0.405) m`，与主方案一致。
- 后端完整回归86/86、顺序门禁16/16、Python编译检查与前端生产构建通过。修改意义：在不推翻成熟联合碰撞搜索的前提下，使结果遵循“先固定传输、最后反求龙门”的机械装配解释。

## 2026-08-28 · A180扫描出光面/A800条码面采集门禁

- 在项目02CAD目录确认A180子树包含 `248004电气-sr-x100-0801A.SLDPRT`，与PPT识别的Keyence SR-X100一致；没有从A180联合包围盒猜测光学原点。
- 新增 `project02_optical_points.py` 和 `capture_project02_optical_point.py`，将选中面中心/法向转换成所属模组底面中心局部坐标，并保存叶零件身份、持久映射和几何指纹。
- 工具强制扫描面属于A180/SR-X100、条码面属于A800；两项齐全才允许写回请求。写回不会自动确认工作距离和光轴方向。
- 顺序求解第三阶段由一个笼统阻塞项拆成4个独立门禁；证据清单 `project02_scanner_barcode_points.json` 当前为空，明确等待工程师选面。
- 后端90/90、Python编译、前端生产构建、真实HTTP求解和顺序门禁16/16通过；仍生成3个候选，五阶段保持2/5 ready。
- 仅重启本项目8000端口后端以加载新代码；5173前端和原SolidWorks进程未重启。修改意义：下一轮可只做两次可复核的面选择，把扫描位置从暂估几何升级为真实工艺点，同时避免再次进入全装配树长时遍历。

## 2026-08-29 · A180 SR-X100出光侧自动识别与截图代审

- 新增SR-X100单叶零件的平面枚举、面索引直选、选择缩放、独立零件激活、保留缩放截图及六标准视图采集能力；不再扫描完整装配树。
- Codex检查六视图后确认：`Bottom`为中央镜头＋双照明孔的出光侧，局部方向为`-Y`；标签/按钮、接插件和侧壳面均被排除。
- 首轮候选截图暴露真实缺陷：平面法向误读了`PlaneParams[3..5]`根点，导致外壳面排名靠前。实现已改为读取`[0..2]`法向，并增加回归测试。
- 候选评分新增已复核局部出光方向与出光侧极值先验；`faceIndex=0`记录为高置信出光侧上的中等置信具体面，但尚未写回实测标志。
- 测试：SolidWorks法向专项9/9通过，SolidWorksMcpApp Release构建0警告/0错误，光学点Python单元测试6/6通过。
- SolidWorks在六视图完成后切回大型原型时无响应；本轮未强制结束进程，也未伪造最终持久面映射。证据：`demo/layout_previews/project02_scanner_optical_face_review.json`。
- 修改意义：把人工识图变为一次可审计的型号级先验，后续只需在恢复的SolidWorks会话中复核一个面，而不是让工程师从1908个面中搜索。

## 2026-08-29 · A180扫描光轴对称特征闭环

- 经SolidWorks逐面高亮，`faceIndex=0`确认为光学侧承载面、`1704`确认为外框，二者均被排除为扫描原点。
- `faceIndex=766/765`分别确认为中央镜头左右两侧的圆形照明窗口；两者局部法向均为`+Y`，面积约`45.0223 mm²`且相对差小于`3e-13`。
- 用两窗口中心中点得到SR-X100叶零件局部扫描光轴原点`(-1.2, 0.3, -20.6) mm`，窗口中心距约`19.3697 mm`。该结果标记为`CAD-inferred`，可用于粗布局，但不冒充直接选中的中央镜片面。
- 新增对称窗口中心推断函数及单元测试；Python光学点测试`7/7`通过。证据及四张排除/确认截图已写入`project02_scanner_optical_face_review.json`。
- 大型原型因`nvoglv64`崩溃，改用轻量8模组装配体加载完全相同的SR-X100叶零件完成只读复核；原型未移动、未保存、未覆盖。
- 修改意义：在导入模型缺少稳定中央镜片平面的情况下，以可测、可复算的对称实体恢复光轴中心，避免继续长时间盲扫1908个面，并保持“直接测量/几何推断/工程确认”证据边界。

## 2026-08-29 · A800真实条码面、2.5D扫描距离与展示求解恢复

- 在A800中确认5个`模拟二维码.SLDPRT`实例；按原型几何关系选定载具8实例，并将其10 mm × 10 mm上表面持久记录为`A800条码面`。
- A180扫描原点与A800条码点均转换到各自顶层模组底面中心坐标系并写回请求；原型源—目标三维距离为`127.085 mm`。
- 修复`pointDistance`只计算二维投影的问题：点高与`installationNormalOffsetMeters`合成公共标高，候选平面半径和视线高度使用同一口径。新增高度感知点距单元测试。
- 原型约束审计由扫描距离失败恢复为全通过。正式Top-3求解、命令行求解与真实HTTP求解均成功：8模组、工艺`23/23`、空间`13/13`、交互`37/37`。
- 统一`generate_real_process_layout.py`与展示/API求解入口，命令行现会加载结构占用和完整静态碰撞策略；更新数值门禁，使A800案例输出锚点不再被误判为相对求解依赖原型。
- 展示页人工代审：A180仍位于A800条码侧，传输中心偏差`7.5 mm`，A200覆盖`88.4%`且单侧越界`136.6 mm`在当前硬上限内；未发现新的整模组级明显穿透。A500–A700仍有一组`28`处叶盒宽相预命中，必须保留为Replay后条件B-rep项，尚未人工勾选“目测通过”。
- 测试：后端完整回归`97/97`；原型约束审计通过；项目02Top-3、真实HTTP、三模组离线审计和数值展示门禁通过；顺序门禁仍按预期阻塞于工作距离/光轴等工程确认。
- 修改意义：完成“CAD点证据→约束求解→展示目测”的本轮闭环，并把下一步工作明确收敛到A500–A700条件B-rep及扫描厂商参数确认，而不是继续盲调模组坐标。
## 2026-08-29 项目02真实扫描点方案 v52 Replay 与静态碰撞闭环

1. 展示层候选1通过人工方向/边界/明显接触预检后固化为 `project02_selected_solution.json`；求解门禁为工艺 `23/23`、空间 `13/13`、2.5D交互 `37/37`。意义：把真实扫描点的数值解与随后CAD证据绑定到同一候选，禁止测试过程中换解。
2. 从项目02原型另存并Replay为 `demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`。8个目标模组均使用 `sourceAnchorTransform`，最终Fully Rebuilt，保存错误/警告均为0，并输出六视图。意义：保留子装配体内部配置状态，同时不覆盖原型。
3. 保存后的真实世界AABB检查中，10组普通实体组合全部通过每侧10 mm膨胀分离。展示层完整多占用盒只在A500–A700记录28个预命中，重开后的真实叶级检查为21,266个实体对、0干涉、0失败。
4. 复用审计发现A100–A200和A200–A800相对v48变化约5 mm，A800–A700也超过复用阈值；三组占用覆盖均不完整，因此补做精检。结果：A100–A200为0；A200–A800的963,456个实体对经AABB降至197个精确检查且0干涉；A800–A700仍为8对，与原型叶实例集合完全相同，无新增/缺失。
5. 从零SolidWorks进程重新打开v52，8/8世界变换最大误差0、包围盒最大误差约`7.09e-11 m`；随后再次运行条件B-rep并得到相同结论。意义：证明结果已稳定写入磁盘，不是前一会话内存状态。
6. 机器状态写入 `demo/layout_previews/project02_v52_cad_execution_plan.json`，静态状态为 `STATIC_COLLISION_BASELINE_EQUIVALENT_AND_REOPEN_CLOSED`、`staticCollisionReady=true`。该结论仅覆盖静态分级碰撞；运动扫掠、软管、维护空间、厂商扫描距离及跨项目校准仍未完成，`productionReady=false`。
7. CAD证据写盘后，SolidWorks再次弹出既有“没能装入 Microsoft .NET Framework”模态提示并在关闭提示后退出；此时Replay、重开位姿和重开后B-rep文件均已落盘且解析通过。意义：将环境稳定性问题与方案/几何失败分开记录；下一次人工查看v52需重新启动SolidWorks。

## 2026-08-29 · 项目02双阀/扫描/操作侧工程估计约束

- 双阀语义由单一`dualValveReach`扩展为左阀、右阀和公共可达包络；A300左右排胶点分别约束到对应阀，三个区域均通过A100内含门禁。
- SR-X100接入官方70～1000 mm设备范围，并用原型127.085 mm建立项目02的100～160 mm暂定工艺带；新增有向光轴硬约束，rank 1为128.761 mm、4.953°，24/24工艺约束通过。
- 新增`estimate_project02_operation_side_capacity.py`：从A600坐标系、安装面、18个禁入区和原型服务模组世界包围盒生成非凸容量证据。操作面映射为V轴高侧；简单矩形净深229.8 mm不足以容纳349.8 mm服务簇，但原型证明可利用结构间通道，故粗布局暂选front。
- 展示页增加操作侧估计摘要；正式维护空间仍未确认，`productionReady=false`不变。
- 闭环测试：Python完整回归100/100，前端`tsc + vite build`通过，Top-3求解24/24、13/13、37/37，顺序门禁18/18，数值/条件B-rep路由门禁通过。
- 修改意义：以低成本等效包络替代过早的完整运动学建模，同时把关键估计变成可复算、可显示、可替换的约束数据。

## 2026-08-29 · Top-3复核与等价布局CAD闭环复用

- 发现5173展示页连接的8000后端仍是旧进程，页面只显示工艺`23/23`；仅重启项目后端后重新求解，新的`directedPointing`扫描光轴约束进入展示，恢复为`24/24`。意义：防止“代码已更新、运行态未加载”造成错误验收。
- 逐一复核Top-3：三案方向、边界和主体关系一致，仅A300沿服务簇方向存在毫米级候选差异；B-rep候选数和叶盒预命中相同。选择评分最低的rank 1并完成展示层固化。
- rank 1与v52 Replay时保存的8个`layout2d`参数逐项一致：最大XY误差`0 m`、最大角度误差`0°`、最大法向偏移误差`0 m`，源模组顶层文件在v52闭环后均未修改。
- 新增`layout_closure_reuse.py`与`audit_project02_cad_closure_reuse.py`。审计同时检查布局等价、展示审批版本、全部硬约束、`directedPointing`存在性、源文件时间戳及历史静态闭环；任一项变化即退回新Replay，否则复用v52的AABB/B-rep/重开证据。
- 新增只读`preview`与`verification-plan`接口；展示页刷新时加载已持久化预览和验证状态，不会因查看结果而重新求解。页面已实测显示`24/24`及“v52 CAD证据已复用，无需重复启动SolidWorks”。
- 当前输出`project02_current_cad_closure_reuse.json`状态为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`：`replayRequired=false`、`conditionalBrepRequired=false`、`staticCollisionReady=true`。本轮未启动SolidWorks，也未创建内容重复的v53装配体；有效实体仍为v52另存件。
- 回归：后端`103/103`通过，前端`tsc + vite build`通过，两个只读接口和展示文案实测通过，数值/路由门禁通过。`productionReady=false`保持不变。
- 修改意义：把“位姿未变则复用实体证据”从临时人工判断升级为机器门禁，避免每次约束文字或诊断增加后都重复执行数十万实体对检查。

## 2026-08-29 · A800五载具扫码站位证据化

- 新增`project02_scan_station.py`和`infer_project02_scan_station.py`，直接读取原型A800叶体捕获中的5个`模拟二维码.SLDPRT`实例，并以A180 CAD推断光学中心逐项计算三维距离。
- 排序结果：载具8约`127.560 mm`，载具7约`542.060 mm`，最近候选间隔约`414.501 mm`；载具8是唯一进入项目02暂定`100～160 mm`工艺带的候选。其直接条码面距离仍为`127.085 mm`，两者约`0.475 mm`差值来自“二维码薄片实体中心/上表面中心”口径差异。
- 将结论写入`project02_scan_station_inference.json`并接入顺序门禁；只有候选数为5、载具8唯一最近、唯一落入工艺带且请求引用同一载具时，才允许标记为粗布局可用。
- 展示页新增扫码站位摘要，显示候选数、载具8距离和与第二近候选的距离差；PLC触发点、移动滑台停靠位和量产公差继续标记为未确认，阶段3仍保持正式阻塞。
- 重新求解仍为Top-3，硬约束通过；rank 1与v52八模组位姿完全一致，CAD闭环审计再次返回`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，无需重复Replay或B-rep。
- 回归：后端`105/105`、顺序门禁`19/19`、前端`tsc + vite build`通过。
- 修改意义：把“载具8看起来靠近扫描器”的旧描述升级为五候选可复算排序，同时严格保留动态扫码控制参数的工程确认边界。

## 2026-08-30 · 动态扫码与服务空间粗约束闭环

- 新增载具8名义条码位置±5 mm动态停靠窗口；两个端点分别生成距离、视线和有向光轴硬约束，工艺约束由24条增至30条并全部通过。
- 新增A500/A700/A300保护空间：校准、清洁/称重和双排胶杯的垂直工艺通道，以及A500/A700的100 mm操作维护通道。保护空间产生20条净空审计，交互约束由37条增至55条并全部通过。
- 新增`project02_service_access_audit.json`和`project02_dual_valve_reach_audit.json`；后者证明公共行程严格等于左右阀等效包络交集，全部工作/服务点及三个包络通过当前粗模型。
- 最终Top-3仍为3个候选；rank 1八模组位姿与v52在XY、角度和法向偏移上误差均为0。审批后状态恢复为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，没有重复启动SolidWorks或B-Rep。
- 回归：后端`109/109`、前端生产构建、顺序门禁`20/20`通过；最终数值为工艺`30/30`、空间`13/13`、交互`55/55`。`staticCollisionReady=true`，但PLC停靠公差、实际维护包络和双阀轴限位未确认，因此`productionReady=false`。
- 修改意义：在保持既有零干涉CAD闭环的同时，补上此前最容易产生“静态能扫、动态扫不到”和“无碰撞但不可操作”误解的两类硬约束，并将SolidWorks成本限定在真正改变位姿时。

## 2026-08-30 · 工程参数接口与12场景鲁棒性审计

- 新增`demo/project02_engineering_inputs.json`与安全写回工具。未确认字段完全惰性；已确认的扫码、维护或阀行程数据必须完整有效，写回后强制重新求解并延后Replay判断到位姿比较完成。
- 新增12个离散压力场景：扫码±20 mm和维护空间1.5倍均保持当前rank 1；扫码±30 mm开始无解；阀行程每侧缩小25/50 mm可得到新布局但必须Replay，缩小75 mm无解。
- 展示页接入压力测试摘要，可直接区分“仍保持当前CAD闭环”“可求解但需要新Replay”和“当前规则下无解”。
- 最终rank 1位姿仍与v52完全一致，CAD状态继续为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，未启动SolidWorks。
- 回归：后端`114/114`、前端生产构建、顺序门禁`21/21`通过；8000后端已加载新代码，5173展示服务保持运行。
- 完整测试会有意生成一次持久化预览，从而把验证计划重置为“待目测”；最终审批与CAD复用审计现固定在全部测试之后执行，当前展示状态已恢复为`cad_closure_reused`。
- 修改意义：把后续实测参数替换从手工改JSON升级为显式工程输入门禁，并用压力测试提前确定最值得优先测量的是双阀真实行程。

## 2026-08-30 · A100轴证据与方向性行程敏感性闭环

- 新增A100内部配合图`demo/layout_previews/project02_a100_internal_mate_graph.json`及摘要；直连模式导出9个顶层子装配体、6条跨模组配合。
- 新增A100顶层叶体包围盒`demo/layout_previews/project02_a100_top_level_leaf_envelopes.json`，共388个叶体，覆盖完整。
- 新增`audit_project02_a100_axis_evidence.py`，输出`demo/layout_previews/project02_a100_valve_axis_inference.json`；明确`LimitDistance1`是普通距离配合而非限位。
- 求解库新增`with_valve_reach_directional_insets`，支持U/V方向分别缩小左右阀包络并重算公共交集。
- 结果：1040×860 mm可解但位姿最大变化42.25 mm；1000×820 mm在12与24候选下均无解，瓶颈为A300工艺域；保守整移动体包围盒档亦无解。
- 展示页新增“A100轴证据”说明，已在本地DOM验收可见。正式rank 1不变，重新审批后CAD闭环状态恢复为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`。
- 测试：后端`115/115`、装配顺序门禁通过、前端生产构建通过。

功能修改意义：把行程不确定性显式转化为可复算的方向性压力场景，并证明平衡档失败不是简单候选数不足，为下一步选择“测量真实限位”或“重构A300/A700工艺窗口”提供依据。

## 2026-08-30 · A300–A700约束消融与可解释失败诊断

- 联合搜索新增按组件/约束ID统计的`processConstraintFailureCounts`；平衡行程基线明确命中左右排胶点行程与A300–A700相对窗口，而非碰撞矩阵。
- 新增`scripts/audit_project02_a300_a700_constraint_ablation.py`及JSON/Markdown报告。基线约26秒无解；删除窄窗口约2.5秒可解；诊断性放宽窗口、软偏好、删除排胶点行程也均可解。
- 诊断性放宽分支保留两条排胶点行程硬约束，A300相对A700约`U=-50.0 mm / V=58.5 mm`；被标记为后续候选，不自动写回正式请求。
- 修正软约束候选语义：`hard=false`不再裁剪硬可行域，新增回归覆盖；Portal事件锚点只由硬相对窗口生成。
- 展示页已显示消融结论和“正式约束未修改”；DOM复核通过。后端更新后运行于8000，前端5173保持可访问。
- 正式Top-3重新生成并审批；8模组位姿相对v52误差全为0，闭环状态继续为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，没有启动SolidWorks。
- 回归：后端`117/117`、前端生产构建、装配顺序门禁通过。

功能修改意义：把“无解”从调参猜测变成可复算的因果诊断，并用硬约束、软偏好和有界放宽三种语义区分后续处理，减少无依据删约束或重复B-Rep。

## 2026-08-30 · A800安装坐标锚点与去源位姿闭环

- 将A800锚点从`sourceCapture`改为A600工程安装坐标中的显式`installationFramePoint`；当前点为`(0.5788,0.5350,0.115225) m`。
- 求解与展示报告现区分“是否读取源装配位姿”和“参数是否由原型标定”。当前分别为`false/true`，因此不再称为原型顶层位姿复刻，但仍保留长轴X待厂商确认的限制。
- 两组全模组源位姿扰动后，相对与绝对输出差异均为`0 m`；正式Top-3仍满足工艺`30/30`、空间`13/13`、交互`55/55`。
- 新rank 1与v52八模组刚体布局逐项零误差，CAD闭环机器审计继续为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，本轮未启动SolidWorks或重复B-Rep。
- `demo/project02_engineering_inputs.json`新增`transportInstallation`，未来厂商基准只需确认后显式写回；未确认字段保持完全惰性。
- 回归：后端`119/119`、前端TypeScript与Vite生产构建、工程输入干运行、去源位姿测试均通过。

功能修改意义：保持已验收v52不变的同时，移除求解对原型源坐标的直接依赖，并把剩余原型标定值收敛为可替换工程参数。

## 2026-08-30 · 项目02原型基线工程输入正式写回

- `transportInstallation`新增`prototypeBaseline`与`vendorConfirmed`双证据等级；原型基线可用于项目02粗布局，但不能被标记为厂商确认。
- 已将A800在A600安装坐标中的锚点`(0.5788,0.5350,0.115225) m`写入`demo/project02_engineering_inputs.json`，并通过`--apply`安全写回正式请求。
- 写回报告为`prototypeBaselineAcceptedForCoarseLayout`；动态扫码、双阀行程和维护空间未确认，均未修改正式请求。
- 两次源位姿扰动后的绝对/相对布局差异仍为0；正式Top-3与v52的最大XY和角度误差均为0。
- CAD闭环继续为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，`replayRequired=false`、`conditionalBrepRequired=false`、`staticCollisionReady=true`。
- 回归：后端`121/121`，前端TypeScript与Vite生产构建通过。

功能修改意义：完成“原型测量→有来源等级的工程输入→通用安装接口→求解→等价CAD路由”的参数化闭环，为后续替换厂商值和迁移其他项目提供稳定入口。

## 2026-08-30 · A100双阀原型行程基线写回与压力测试闭环

- 扩展`dualValveReach`工程输入，使其支持`prototypeBaselineAcceptedForCoarseLayout`和`vendorConfirmed`两级权威，并拒绝“原型基线同时声称厂商确认”的冲突输入。
- 已把项目02左右阀包络和`90 mm`阀头间距写入`demo/project02_engineering_inputs.json`；公共交集为`1107.2 × 960.8 mm`，正式请求仍明确标记为暂定行程。
- 新增`scripts/audit_project02_a100_prototype_baseline.py`与机器报告`demo/layout_previews/project02_a100_prototype_baseline_acceptance.json`，自动核对数据血缘、左右交集、正式请求写回、轴证据和压力场景。
- 当前基线可解且与v52位姿完全一致；`1040 × 860 mm`可解但位姿最大改变`42.25 mm`，`1000 × 820 mm`因A300工艺域无解。
- 决定暂不把诊断性A300–A700放宽窗口写入正式规则；只有未来确认采用更小行程时，才重新评估该有界窗口并触发新CAD闭环。
- 最终重新求解并审批rank 1，等价性审计为8/8位姿误差0、源CAD未变化，状态恢复为`cad_closure_reused`；未启动SolidWorks或重复B-Rep。
- 回归：后端`123/123`、前端TypeScript/Vite生产构建、去源位姿测试和A100基线审计全部通过。

功能修改意义：将当前最敏感的双阀行程从隐藏估计提升为可替换、可审计的项目级工程输入，并用压力测试明确下一次真正需要Replay的边界。

## 2026-08-30 · 动态扫码原型基线写回与压力边界闭环

- 将`dynamicScan`扩展为`prototypeBaselineAcceptedForCoarseLayout`与`vendorConfirmed`两级权威；保留旧`confirmed=true`正式输入兼容，并拒绝相互矛盾的来源标记。
- 已把载具8二维码面半宽形成的`±5 mm`停靠窗口写入`demo/project02_engineering_inputs.json`。请求端点、来源、作用轴和证据等级同步更新，但`dynamicScanStopToleranceConfirmed=false`保持不变。
- 新增`scripts/audit_project02_dynamic_scan_prototype_baseline.py`，输出`demo/layout_previews/project02_dynamic_scan_prototype_baseline_acceptance.json`，自动检查载具8、二维码尺寸、双端点、三类光学门禁和压力场景。
- 压力测试结果：`±5/±10/±20 mm`可解并保持v52；`±30/±50 mm`无解。正式基线仍为有直接CAD来源的`±5 mm`，没有把`±20 mm`求解余量误标为PLC公差。
- 展示接口已返回`dynamicScanInputAuthority=prototypeBaselineAcceptedForCoarseLayout`，并在页面标注“项目02原型基线”。
- 最终Top-3重新求解、rank 1审批和CAD等价性审计通过：8模组位姿误差0，`replayRequired=false`、`conditionalBrepRequired=false`、`staticCollisionReady=true`。
- 回归：后端`125/125`、前端TypeScript/Vite生产构建、去源位姿测试及动态扫码专项审计全部通过。

功能修改意义：把动态扫码从单点静态假设升级为可替换的工程输入和可审计的窗口约束，并用自动CAD路由避免对未改变的布局重复Replay。

## 2026-08-30 · A500/A700/A300分用途维护包络基线闭环

- `serviceAccess`新增原型基线/厂商确认双证据等级；当前三个功能模组包络已写入工程输入，均明确为`project02-only`且不声称最终人工工效确认。
- A500分别保留标定点上方阀头通道和后方操作维护带；A700分别保留清洁/称重共享服务通道和工具带；A300只保留双排胶杯上方进针通道，避免错误要求龙门阀头绕开工艺通道。
- 现有20条保护空间净空关系全部通过，A500不会再被接受在CCD与龙门支柱夹缝内。
- 新增`with_service_component_scale`和`scripts/audit_project02_service_component_robustness.py`，分别对A500/A700/A300运行`1.0/1.25/1.5`倍压力测试；九个场景均可解且保持v52。
- 放大结果没有写回正式基线；A710/A720清洁、A730称重、实际工具和人员维护动作仍待后续拆分或测量。
- 展示接口已返回`serviceAccessInputAuthority=prototypeBaselineAcceptedForCoarseLayout`，页面同步标注“项目02原型基线”。
- 最终Top-3重新求解并审批；8模组位姿误差0，CAD状态为`CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT`，无需Replay/B-Rep。
- 回归：后端`128/128`、前端TypeScript/Vite构建、去源位姿、动态扫码及维护空间审计全部通过。

功能修改意义：用方向明确的保护空间替代粗暴整模组膨胀，使求解器同时满足静态无干涉和基本可操作性，并把CAD验证成本继续限定在真实位姿变化上。

## 2026-08-30 · A700清洁/称重子功能拆分与项目参数包

- 审计A700现有三占用盒：A710/A720为清洁结构，A730为称重结构；确认旧共享服务点不对应两个实体中心。
- 工程输入新增`functionalPoints`接口，可在一个刚体模组内声明多个功能点、默认兼容别名及需要改绑的显式工艺约束。
- A710/A720占用并集中心形成清洁点`(395.8,-80.5) mm`；A730中心形成称重点`(0,0) mm`。A700仍作为单一刚体求解，未拆成三个独立摆放对象。
- 维护保护体从共享2盒拆为清洁/称重各2盒；总净空关系增至29条，龙门覆盖点增至7个，交互门禁增至`64/64`，全部通过。
- 新增`scripts/audit_project02_a700_functional_split.py`，验证点位确由占用体中心推导、清洁/称重约束分别绑定、维护方向为操作面外向-V侧。
- 重新运行分模组1.0/1.25/1.5倍压力测试，A500/A700/A300九个场景仍全部保持v52。
- 新增`scripts/build_project02_parameter_package.py`并生成`demo/project02_parameter_package.json`，区分可迁移规则、项目02数值、其他项目必需输入和剩余生产门禁。
- 最终Top-3与v52位姿误差0，CAD闭环继续复用；后端`129/129`、前端构建、去源位姿及专项审计全部通过。

功能修改意义：建立“一个真实子装配体、多个工艺功能端口”的通用能力，并把项目02已校准知识整理成可迁移但不会误复制案例常数的参数包。

## 2026-08-30 · 项目01跨案例参数骨架与展示门禁

- 读取多项目模组清单并核对项目01原型、01-PPT及10个独立主装配文件；10/10 CAD路径均已解析。
- 新增`project_migration.py`及`build_project01_parameter_skeleton.py`，生成`demo/project01_parameter_package.json`和`demo/layout_previews/project01_migration_readiness.json`。
- 将项目01归并为固定环境、输送/翻转组、龙门/双阀头组、四功能GN00、BD00、SM00、GJ00；形成6个待求解顶层对象，避免把内部刚性子模组错误独立移动。
- 明确项目01没有独立产品CCD，并设置11项几何证据缺口及1项部分碰撞策略；当前Top-3门禁保持关闭。
- 新增`GET /api/demo/cases/project01/migration-readiness`及展示页门禁面板；DOM实测已显示10/10、6、11、“项目02数值已隔离”和完整采集顺序。
- 回归结果：后端`130/130`、前端TypeScript及Vite构建通过；项目01专项测试通过；接口返回与JSON一致。未启动或修改SolidWorks，项目02 v52实体和闭环证据保持不变。

功能修改意义：把跨案例工作从“复制一个看起来像原型的布局”改成“先审计参数血缘和求解输入，再允许Top-3”，使后续几何采集和规则失效定位可重复、可展示。

## 2026-08-30 · 项目01配合图、安装接口与双工作区采集

- 通过直接stdio MCP只读打开项目01原型，未关闭或覆盖带未保存标记的项目02 v52。
- 导出10模组、27条跨模组配合、10个配合束；JJ00–SS00由1个重合面和2个同心孔定位，原型孔距58 mm。
- 生成项目01安装坐标：原点约`(-570.663,-227.161,-568.703) mm`，流向`+Z`、横向`+X`、上向`+Y`。
- 纠正拓扑：FF00直接安装到JJ00，并非SS00的刚性子组；求解对象改为7个。GN00直接安装到JJ00，并平行于SS00。
- 顶层10模组AABB完整；操作侧由GN00/BD00/GJ00服务簇相对SS00推断为`+X`，仍待精确面确认。
- 完成SS00 351叶/433体及FF00 334叶/1824体采集，失败0；识别两个重复SNAP CARRIER工位子树。
- 两工位局部平面坐标约`(475.0,-32.2) mm`与`(910.0,-13.0) mm`，缺失证据降至5项、部分证据4项，Top-3仍未放行。
- 新增项目01几何与工位分析器、生成脚本和测试；参数包、迁移门禁JSON及展示页数据已刷新。
- 完整回归`132/132`、前端TypeScript/Vite构建及展示页DOM验收通过；页面显示10/10模组、7个求解对象、5项缺失且项目02数值已隔离。

功能修改意义：把项目01从“仅知道有哪些模组”推进到“具有真实安装坐标和双工作区”的可计算状态，并在发现原假设错误时通过配合图自动纠正求解对象。

## 2026-08-30 · 项目01双读码器与载具条码侧闭环

- 只读采集SM00全部38叶/84体，失败0；新增通用六向正交视图导出脚本并输出SM00、SM10、SM20及关键扫描零件视图。
- 结合01-PPT第17页确认两个`FL209AG-00072`均为KEYENCE SR-X100：固定载具读码器沿`+worldX`侧扫，移动产品读码器沿`+worldY`上扫并沿`+worldZ`依次扫描四个产品。
- CAD显式红色光束均为200 mm。由光束近端恢复光学原点、由远端恢复目标代理点，并投影到JJ00–SS00安装坐标；载具条码面法向取光轴反向。
- `FL201AB-00043`确认是载具缺件检测传感器，仅记录检测角色，不作为第二类条码目标或工作距离输入。
- 新增`project01_scanner.py`、生成脚本、专项测试和`project01_scanner_geometry.json`；迁移参数包缺失项由5降至3。
- 展示页新增“KEYENCE SR-X100 × 2 / 载具侧扫 + 产品上扫 / 原型CAD光束200 mm”，DOM实测显示10/10模组、7个求解对象、3项缺失。
- 完整后端回归`133/133`、前端TypeScript/Vite生产构建通过；原型仅只读打开，未修改项目02 v52实体。

功能修改意义：把PPT语义、叶级CAD和安装坐标串成可复算的扫描约束，避免把检测传感器误识别为扫码器，并让后续跨案例求解可直接检查方向、距离和条码侧。

## 2026-08-30 · 项目01 GN00/BD00 服务端口闭环

- 只读采集GN00与BD00完整叶体：GN00为269个叶组件/290个实体，BD00为26个叶组件/52个实体，均无失败体。
- 结合01-PPT第18、24～27页与标准六视图，确认GN10=清洁、GN20=自动称重、FJ00=双排胶杯、GN30=胶水硬度测试台；BD00服务目标位于棱镜/光源端，不是相机壳体中心。
- 新增`project01_service_points.py`和生成脚本，将GN00四类功能展开为5个阀头目标，并增加BD00标定目标，共6个服务端口。
- 端口均携带世界坐标、传输安装坐标、接近方向、来源叶体、推断方法和置信度；清洁与标定点明确标为中等置信度原型代理。
- 生成`demo/layout_previews/project01_service_points.json`，同步更新项目01参数包与迁移门禁；缺失硬证据从3项降到1项，只剩双阀公共行程。
- 展示页新增“GN00 4类功能/5个阀头目标、BD00标定目标、共6个粗布局可达点”。
- 回归结果：后端`134/134`通过；前端TypeScript/Vite生产构建通过；实时API返回6个服务端口和仅1项缺失证据。

功能修改意义：建立“PPT功能语义→子装配体身份→显式叶体/子树代理点→安装坐标→迁移门禁”的可复算链路，为下一步从LM00/ZZ00反求公共行程和执行项目01首次Top-3求解提供实际覆盖目标。

## 2026-08-30 · 项目01 LM00/ZZ00 双阀公共行程闭环

- 只读采集LM00 161叶/411体与ZZ00 121叶/263体，失败0；导出两个模组的六向标准视图。
- 识别LM00横向双1.1 m光栅尺与输送方向0.9 m磁栅尺；识别ZZ10/ZZ20两个`FL237AA-00012`点胶阀总成，原型偏置约130 mm且沿安装坐标U方向。
- 新增`project01_valve_reach.py`、生成脚本、专项单元测试及`project01_dual_valve_reach.json`。
- 推导项目01双阀公共平面范围约`770 × 1100 mm`；两个传输工作区、GN00五个服务目标、BD00标定目标共8点全部通过，最小边界余量约36 mm。
- 参数包的`dualValveReach`由缺失升级为可用；项目01缺失硬证据清零，但Top-3仍等待四项部分证据完成。
- 展示页新增“公共范围770 × 1100 mm / 阀间距130 mm / 8个目标全部可达”。
- 回归结果：后端`135/135`通过；前端TypeScript/Vite生产构建通过；实时API返回0项缺失、4项部分证据。

功能修改意义：首次把项目01龙门结构转换为可计算的双阀公共覆盖域，并用所有工艺目标反向校验，避免复制项目02A100参数或仅凭龙门外框宣称可达。

## 2026-08-30 · 项目01多包围盒与静态碰撞门禁闭环

- 新增`project01_occupancy.py`、`build_project01_occupancy.py`及专项测试，生成`demo/layout_previews/project01_module_occupancy.json`。
- 8个布局对象的28组对象对实现全覆盖分类：12组严格多包围盒、9组条件B-rep、7组安装接触；求解阶段明确不调用B-rep。
- 7个结构/工艺模组共3357个叶体AABB被整理为31个子树占用盒；GJ00采用单一保守顶层AABB，JJ00/HL00保持固定环境。
- 原型复核发现3组普通对象对子树并集过于保守，改为伙伴限定叶体AABB；3组原型均0命中。FF00–GN00叶体AABB仍命中，升级为条件B-rep而非错误判死。
- 普通模组膨胀安全余量暂取每侧1 mm；操作侧`+worldX/+installationV`作为项目01原型粗布局基线放行，但保留工程确认债务。
- 迁移门禁升级为`PROJECT01_TOP3_INPUT_READY`：缺失0、部分0、10/10 CAD路径解析、7个可移动对象。展示页新增28组碰撞对统计与“求解不调用B-rep”说明。
- 为避免展示API传输7.5 MB叶体明细，迁移就绪接口仅返回约70 KB摘要，完整占用仍保存在独立机器证据文件中。
- 回归：后端`136/136`、前端TypeScript/Vite生产构建通过；实时API返回Top-3已就绪。未执行SolidWorks Replay或实体B-rep。

功能修改意义：把项目01从“几何证据齐全但不敢求解”推进到“可以快速生成Top-3并在选中后按需做CAD精检”，同时避免全量B-rep拖慢每次迭代。

## 2026-08-30 · 项目01专用顺序Top-3与展示闭环

- 新增`project01_layout.py`及专项测试，并在统一布局预览API中接入项目01分支；没有复制项目02的A600/A800/A100/A180数值。
- 实现项目01工程顺序：固定JJ00/HL00环境和SS00/FF00安装基准，保持SM00扫码几何，离散调整GN00/BD00/GJ00，最后由8个工艺目标反求LM00+ZZ00公共覆盖。
- 每轮检查125个GN00/BD00/GJ00联合组合，当前21个硬可行，输出3个候选。为便于会议目测，候选2/3分别相对基线移动GN00或BD00 30 mm；分数为`2.6435 / 32.6435 / 32.6435`。
- 生成`project01_solution.json`、`project01_preview.json`、`project01_verification_plan.json`和`project01_selected_solution.json`；重新求解后验证计划保持`awaiting_visual_review`，没有替用户选择或执行Replay。
- 展示页新增独立项目01 Top-3面板：8个布局对象、8个工艺目标、12组严格关系、9组条件B-rep、7组安装接触；明确标识求解期B-rep为0，41个叶AABB命中只用于精检排序。
- 修正展示语义：项目01不显示独立CCD、传输中心性或A200开口等项目02专属指标；新增候选差异和粗布局边界说明。
- 回归：后端`137/137`通过，前端TypeScript/Vite生产构建通过。未修改或Replay SolidWorks装配体。

功能修改意义：把项目01从“Top-3输入已就绪”推进到“可在浏览器快速比较三个硬约束候选”，用一次低成本人工目测淘汰明显不合理解，再把CAD加载和条件B-rep成本集中到唯一选中方案。

## 2026-08-30 · 项目01方案1人工选择

- 用户对项目01三套同视角布局截图完成比较后，明确选择方案1。
- 展示页人工目测门禁已通过，`project01_verification_plan.json`状态更新为`visual_review_approved`、`selectedSolutionRank=1`；方案1已物化到`project01_selected_solution.json`。
- 本步没有启动SolidWorks、没有Replay，也没有执行B-rep。下一阶段按门禁顺序执行Replay → 变换/AABB粗筛 → 仅对需要的条件对象对做叶级B-rep。

功能修改意义：把后续CAD和精确干涉检查锁定到唯一人工认可方案，避免再为方案2/3支付装配加载与B-rep成本。

## 2026-08-30 · 项目01方案1 Replay、条件B-rep与保存重开复核

- 新增`project01_replay.py`、`prepare_project01_selected_replay.py`和`replay_project01_selected_solution.py`，把8个求解对象可靠展开到10个真实顶层模组，并仅对用户批准的方案1创建独立装配体。
- 生成目标文件`demo/project01/FL9C24N074AA00_project01_solution1_v1.SLDASM`。方案1为求解器选出的原型等价最小位移解；Replay审计确认10/10顶层模组齐全，无遗漏或额外组件。
- 新增`project01_collision.py`和`screen_project01_replay.py`的保存后宽相筛查能力。12组严格多包围盒关系全部通过；9组条件关系展开为14组真实顶层模组对。
- 14组叶级B-rep全部完成，13组无实体干涉。ZZ00–GN00检出3个相交实体对；对原型执行同一对检查后，数量及零件文件对完全一致，结论为“原型工艺位已有接触，本次布局未新增干涉”。
- 新增`reopen_project01_solution1.py`并完成保存、关闭、重新打开复核；重开后10个顶层变换最大误差约`6.54e-9`，世界AABB最大误差约`2.17e-10 m`，文件持久化稳定。
- JJ00–ZZ00/HL00–ZZ00安装接触补充审计因叶零件`FL209AK-00001-1`无法返回实体包围盒而未完成。已生成结构化失败证据，明确区分“检查工具受限”和“存在干涉”。
- 新增`project01_solution1_v1_collision_summary.json`，总状态为`PROJECT01_NO_NEW_INTERFERENCE_PROTOTYPE_CONTACT_REVIEW_REQUIRED`；当前不可标记为生产就绪或全局零干涉。
- 新增3项专项测试，后端全量回归由137项增至140项，140/140通过；新增脚本全部通过Python语法检查。

功能修改意义：把项目01从二维候选和人工选择推进到真实SolidWorks文件、按需精检及磁盘重开证据闭环；同时保留工程决策门禁，避免把原型已有的工艺接触错误归因于新布局或直接忽略。

## 2026-08-31 · 项目01暂定接触放行与实体闭环完成

- 新增`project01_allowed_contact_policy.json`，把用户暂定允许的3处ZZ00–GN00相交限制到具体零件文件、具体子装配实例和出现次数；未列出的相交继续判为非法。
- `project01_collision.py`新增允许接触分类器及正反测试：真实3个命中全部精确匹配；伪造未登记实例会被拒绝，证明没有把整个模组对宽泛放行。
- 修改SolidWorks叶级干涉检查：实体无AABB时不再终止，而是跳过宽相筛选并直接进入B-rep内核检查；结果新增无AABB实体数和宽相绕过实体对数。
- 在真实目标装配体重跑JJ00–ZZ00与HL00–ZZ00。前者2个异常实体触发526次慢路径，789个候选全部完成、干涉0、失败0；后者AABB全部分离、干涉0。
- 更新闭环汇总与验证计划，状态升级为`PROJECT01_DEMO_CONDITIONALLY_PASSED`：检查未完成项0、非法干涉0、暂定允许接触3；生产就绪仍为否。
- 展示页新增三色实体闭环卡片，实时显示绿色无非法干涉、黄色暂定允许接触和红色非法干涉。浏览器实测文本与API一致，控制台错误0。
- 回归：Python后端142/142、非集成.NET 320/320、前端TypeScript/Vite生产构建通过。完整.NET套件323/325通过，2个既有可视集成用例因MCP测试客户端明确未暴露`ResolveComponentTarget`/`ListComponents`而失败，与本次改动无关。

功能修改意义：把“暂时认为可以接触”转换为机器可执行且默认拒绝未知情况的工程规则，并消除无AABB叶体造成的精检盲点，从而完成项目01可展示的条件无非法干涉闭环。

## 2026-08-31 · 项目03参数骨架与首阶段CAD证据

- 新增项目03独立迁移参数骨架，识别AA00～AJ00十个主要模组并按8个布局对象分组，其中固定环境为AA00+AF00、运动组为AB00+AC00；没有复制项目01/02数值。
- 导出项目03顶层位姿和模组配合图：15个顶层实例中10个为主要模组、5个为辅助散件；跨模组配合29条、连接束9组。
- 从AA00–AE00真实配合恢复项目03安装坐标：一个支承面、两个定位孔、孔距58 mm，流向约+worldZ、横向约+worldX、上向约+worldY。
- 根据AG00/AH00/AJ00服务簇推断操作侧候选为+worldX，中等置信度；没有把推断结果伪装为已确认操作面。
- 新增`project03_geometry.py`、参数/几何生成脚本及测试；参数包和展示门禁已同步更新。
- 展示页新增项目03卡片，实测显示10/10 CAD解析、7个可移动求解对象、6项缺失、4项部分证据，以及29条配合/9组连接和10+5实例分类。
- 回归：Python后端144/144通过，前端TypeScript/Vite生产构建通过；本轮没有Replay或修改SolidWorks装配体。

功能修改意义：把项目03从“只有模组身份”推进到“具有项目自身安装坐标、装配拓扑和可见证据债务”的可迁移状态，同时用门禁阻止过早生成Top-3和启动昂贵B-rep。

## 2026-08-31 · 项目03双工作位提取与门禁接入

- 首次代理方式的MCP初始化未返回，约24分钟后超时；确认并非叶体计算耗时。清理该次遗留hub后改用`--direct-stdio`，约100秒完成真实采集。该问题记录为后续CAD采集应优先使用直连模式的性能经验。
- AE00捕获194叶/832体、AD00捕获292叶/390体，失败0、覆盖完整。
- 从AD00识别两个重复AD10工作站及其AD20举升/旋转子树；从AE00识别三组沿输送轴等距排列的AE90结构，用作独立夹持/站间几何验证。
- 生成两个工作位：安装坐标U约522/907 mm、V约56.5 mm，中心距385 mm；相对AE90夹持中点最大偏差18.6 mm。
- 结合03-PPT第9、14页确认双工作位承担举升、25°旋转和点胶，缓存扫码位保持独立。当前仅用低U/高U命名，未擅自绑定A/B编号。
- 新增`project03_workstations.py`、构建脚本和2项测试；迁移门禁缺失项由6降至5，展示页新增双工作位证据卡并动态移除已完成采集步骤。
- 回归：Python后端146/146通过，前端TypeScript/Vite生产构建通过；浏览器实测展示文本、接口和JSON一致。

功能修改意义：以一次完整CAD采集同时解决工艺点和局部占用证据，把后续扫描与龙门可达约束锚定到真实工作站，而不是输送模组中心或人工估计坐标。

## 2026-08-31 · 项目03扫描几何提取与展示门禁接入

- 通过直连MCP只读采集AI00，覆盖30个叶组件、54个实体，失败0；采集约76秒完成。
- 从唯一显式`FL209AG-00072`的两实体结构自动区分壳体和光束，恢复+worldY光轴、100 mm CAD光束和安装坐标目标代理点。
- 从`FL412AI-00411`恢复与输送轴平行的无符号移动方向；结合03-PPT确认其承担4个产品条码的顺序扫描。
- 识别到独立薄型`FL201AQ-00046`身份头，但CAD中不存在第二条明确扫码光束。载具条码/RFID证据保持`partial`，没有虚构第二SR-X100。
- 新增`project03_scanner.py`、构建脚本、单元测试和门禁集成测试；生成`project03_scanner_geometry.json`，并同步更新项目03参数包与展示卡片。
- 项目03缺失硬证据由5项降至3项，部分证据为5项；Top-3仍关闭。展示层按项目实际数据显示1个SR-X100、100 mm光束及载具证据待澄清，不再套用项目01的“双读码器/200 mm”文案。
- 回归：Python后端148/148通过，前端TypeScript/Vite生产构建通过；本轮没有Replay、另存或修改SolidWorks装配体。

功能修改意义：完成项目03扫描模组从CAD/PPT证据到求解门禁和可视展示的闭环，并把“可用于粗布局”与“工程已确认”严格分离。

## 2026-08-31 · 项目03服务点与双阀覆盖闭环

- 直连只读采集AG00/AH00及AB00/AC00，四个模组共511个叶组件、927个实体，失败0；原型文件未修改。
- 新增`project03_service_points.py`：从AG12/AG13、AG20、AG30、AG40和AH10恢复2个清洁、1个称重、1个硬度、2个排胶和1个标定目标，共7点。
- 新增`project03_valve_reach.py`：从AB00尺度体和AC00双阀偏置恢复项目03专属公共范围，并验证2个工作位＋7个服务点共9点。
- 修复多实体轴件选择规则：由“最长实体”改为“满足长度阈值的最细尺度体”，避免把1060 mm结构导轨当作行程；最终使用900 mm流向、1100 mm横向原型尺度和130 mm阀间距。
- 当前公共范围为770×1100 mm，9/9目标可达，最小余量6 mm。PPT 800×650×100 mm行程作为未映射差异保留，不用于当前CAD门禁。
- 项目03缺失硬证据降至0，部分证据保持5；展示页将显示AG00 4类/6目标、AH00 1目标及双阀范围。Top-3仍因占用/碰撞和操作面等证据未闭环而关闭。
- 回归：Python后端150/150通过，前端TypeScript/Vite生产构建通过；尚未生成项目03候选、Replay或B-rep。

功能修改意义：在项目03上完成工艺目标和龙门公共覆盖的数值闭环，为下一步快速多包围盒筛选与Top-3放行提供了完整可达性输入。

## 2026-08-31 · 项目03阶段冻结并转向其他探索

- 新增`docs/project03_pause_handoff-CN.md`，集中记录项目03当前目标、已完成能力、5项部分证据、关键机器文件及恢复顺序。
- 当前冻结状态：10个模组和8个布局对象已识别；安装坐标、双工作位、扫描几何、7个服务点及双阀公共覆盖已闭环；缺失硬证据0、部分证据5、Top-3保持关闭。
- 恢复后的首要任务为多包围盒占用和28组碰撞对象对分类；完成前不启动项目03 Replay或全量B-rep。
- 本次冻结不删除进程、证据或生成文件，也不修改项目01/02既有装配体和验证结果。

功能修改意义：为短暂切换技术方向建立明确、可审计的恢复点，避免返回项目03时重复CAD采集、遗忘证据边界或越过Top-3门禁。

## 2026-08-31 · 项目02模组级配合重建A/B/C实验

- 新增全图重建接口和顺序实验脚本，支持`source_pose`、`mate_only`、`residual_anchors`三种模式，并对重合、距离、平行、槽口、宽度配合进行重建。
- 三组均完成独立新装配体创建、保存、关闭、重开复核：A为24/27配合、10/10位姿；B为24/27配合、7/10位姿；C为24/27配合、10/10位姿。
- B组直接证明当前“子装配体＋配合”不足以唯一恢复原型：A800偏移243.65 mm，两个T401偏移1206.49/894.10 mm且方向错误。
- C组按B组欠约束/位姿误差补入A500、A700、A800及两个T401的完整残差位姿，恢复10/10；该结果验证“配合图＋残差锚点”路线可行，但尚未实现最少标量锚点。
- 共同缺失的3条配合均涉及T401顶层零件面恢复；其余24条在重开后保留。未执行B-rep，本实验不构成实体无干涉结论。
- Release构建、Python语法检查和非集成.NET测试320/320通过；详细记录见`docs/project02_module_mate_reconstruction_ABC-CN.md`。

功能修改意义：把“只有配合能否恢复原型”的讨论转化为可重复对照实验，确认完整原型位姿不是唯一选择，但当前配合图必须补充少量安装基准/残差信息，才能稳定恢复全部模组。

## 2026-09-01 · 冻结项目02配合重建探索并恢复项目03

- 将项目02“子装配体＋配合关系恢复原型”冻结在A/B/C实验完成状态：24/27配合，A/C为10/10位姿，B为7/10；T401面寻址、A800单轴欠约束和A500/A700公共过约束留待未来专项处理。
- 在`project02_module_mate_reconstruction_ABC-CN.md`新增暂停边界和逐项恢复顺序，保留全部装配体、JSON、代码和测试证据；本阶段未运行B-rep。
- 重新核对项目03交接证据：10个模组、8个布局对象、29条配合、两个工作位、扫描几何、7个服务点及9/9双阀覆盖仍完整，无需重新采集。
- 更新`project03_pause_handoff-CN.md`为当前主交接入口；首个开发闭环仍为多包围盒占用体和28组碰撞对象对分类，完成前保持`top3SolveReady=false`，不Replay、不运行全量B-rep。

功能修改意义：建立两个技术方向之间的清晰切换点，防止项目02实验问题混入项目03布局求解，也避免项目03恢复时重复执行已经完成且耗时的SolidWorks叶体采集。

## 2026-09-01 · 项目03多占用体与28对碰撞门禁闭环

- 新增`project03_occupancy.py`及构建脚本，复用7个活动结构模组的2203个叶实体包围盒，压缩为38个工艺子树宽相占用盒；AA00/AF00固定环境与AJ00普通外置供胶使用顶层保守AABB。

### 2026-09-01 项目03唯一选案与实体闭环

- 新增项目03专用Top-3入口、展示页案例面板、Replay展开与保存脚本；92个可行候选中自主选择评分最低且位移为0的方案1。
- 方案1已Replay到独立目标`demo/project03/FL9A24D063A000_project03_solution1_v1.SLDASM`，10个主模组和5个辅助顶层件完整保存。
- 12/12严格AABB通过；9组条件叶级B-rep中7组无干涉，2组共8个交叠与原型逐体一致，新增干涉0。
- 新增`project03_closure.py`和保存重开脚本。关闭重开后最大变换误差约`4.0e-15`，无需重建，最终状态`PROJECT03_DEMO_BASELINE_EQUIVALENT_CLOSED`。
- 对AA00/AF00安装关系，16个成员对先由AABB排除5对。由于方案1所有位姿增量为0且目标是原型Save-As副本，余下11对使用可审计的原型位姿等价证书，避免重复执行无新增信息的全箱体叶级B-rep。
- 功能修改意义：完成第二个案例从证据参数化、Top-3、选案到真实CAD验证的闭环，并将昂贵精检限定在真实新增风险上。
- 后端完整回归155/155通过；前端生产构建通过。当前仅为“相对原型无新增干涉”的Demo结论，未声称绝对零接触或生产放行。
- 8个布局对象的28组关系已全分类：12组严格膨胀多AABB、9组条件B-rep、7组安装接触。严格原型基线失败0组；AG00–AH00保守子树预命中经叶体盒复核后为0。
- 求解阶段不调用B-rep。9组结构/嵌套关系只在候选被选中且Replay后进入叶级精检。
- 迁移门禁显式接受操作侧、操作侧容量和单束SR-X100站位为“原型粗布局基线”，同时保留精确操作面、维护空间、载具条码/RFID角色和厂商参数为工程债务。
- 项目03现为`missing=0`、`partial=0`、`top3SolveReady=true`、`PROJECT03_TOP3_INPUT_READY`；参数包、迁移JSON和展示卡已同步。
- 回归：Python后端152/152通过，前端TypeScript/Vite生产构建通过。本轮未Replay、未另存项目03装配体、未执行实体B-rep。

功能修改意义：完成项目03从“几何证据齐全但门禁关闭”到“可快速生成Top-3”的关键转换，以多包围盒宽相消除大部分不必要CAD精检，并确保粗布局估计不会被误标为工程确认。

## 2026-09-01 · 项目05参数骨架、配合图与安装基准

- 选择项目05作为项目01/03之后的下一通用约束迁移案例；建立11个真实模组、9个布局对象的独立参数骨架，未继承项目01/02/03数值。
- 只读导出项目05顶层位姿与模组配合图：13个相关实例、31条跨模组配合、10组配合束、2222个组件索引；正确识别N000/P000各一个抑制变体。
- 从A000–D000的重合、312 mm距离和宽度配合恢复安装坐标与传输居中关系，生成`project05_first_stage_geometry.json`。
- 新增项目05后端API、展示页状态卡、参数/几何脚本和测试；修正第一阶段状态及动态下一步列表。回归158/158、前端生产构建通过。
- D000/K000联合叶体捕获在第二次打开79 MB原型时超时，未进入叶体检查。捕获脚本已增加复用活动文档、单模组续跑、逐模组落盘和异常保留功能；未强制结束SolidWorks，也未修改任何原型。

功能修改意义：把跨案例迁移从“复制已知结果”推进到“用项目05自身配合恢复安装语义”，并把昂贵CAD采集拆成可恢复的小步骤，减少重复加载和整批失败风险。

## 2026-09-01 · 项目05 PPT工艺语义与独立子装配体捕获通道

- 将05-PPT第7、9、13、14、15页显式信息结构化为`project05_process_semantics.json`：缓存位扫码、两个顶升工作位、载具＋4产品顺序扫码、CCD双工位移动及视场/工作距离/精度。
- 门禁将工作位、条码侧和CCD由`missing`升级为`partial`，但保持真实CAD坐标、扫码光轴和CCD局部原点未完成；缺失/部分计数由8/5更新为5/8。
- 叶体接口新增`@root`，允许直接捕获独立子装配体的全部叶实体，后续用原型顶层变换回映整机坐标；Release构建0警告0错误，非集成.NET 320/320通过。
- K000真实验证未完成：强制新实例停在COM连接，复用后台实例停在`open_document`，均未进入`@root`叶体遍历。已停止MCP客户端，未关闭或保存用户文档，也未生成伪CAD结果。
- 新增`project05_local_capture.py`和映射脚本，对独立子装配体局部AABB的8个角点施加原型顶层刚体变换，生成保守整机世界AABB；不完整捕获和非唯一模组匹配默认拒绝。
- 回归：Python后端162/162、非集成.NET 320/320、前端生产构建通过。

功能修改意义：先利用低成本PPT证据缩小未知量，再为大型整机加载建立子装配体级采集通道；同时严格区分“接口已验证”和“真实CAD采集已完成”，防止进度被高估。

## 2026-09-01 项目05 K000工作位闭环与D000受控中止

- 完成K000独立`@root`真实叶体捕获及世界坐标回映：314个叶组件、530个实体、0失败。
- 新增项目05双工作位提取器与构建脚本；两个工作位中心距约415 mm，横向差与高度差近零，粗布局可用，PLC工作位1/2编号仍保留为工程债务。
- 生成`project05_work_positions.json`并接入项目05参数包；`transportWorkPositions=available`，门禁更新为missing=5、partial=7。
- 修正CAD完整证据被PPT部分证据覆盖的状态合并缺陷，并增加回归断言。
- D000独立捕获因SolidWorks/COM无CPU进展而受控中止；未生成不完整JSON、未修改CAD源文件。后续先用干净会话重试，再考虑一级子树分片。
- 回归：Python 164/164通过；前端TypeScript/Vite生产构建通过。

功能修改意义：把两个传输工作位从文字推断升级为真实CAD坐标约束，并将大型子装配体捕获故障隔离为可恢复步骤，避免阻塞整个跨项目迁移流程。

## 2026-09-01 项目05 36对碰撞策略与启动故障隔离

- 新增`project05_occupancy.py`、构建脚本和测试，完成9个布局对象全部36对分类：15严格、13条件B-rep、8安装接触。
- K000使用530个真实叶实体压缩形成的子树占用盒；其他模组使用显式保守顶层占位，不参与求解就绪放行。
- `staticCollisionPolicy`升级为available；`moduleOccupancy`保持partial。项目05门禁现为missing=5、partial=6、Top-3关闭。
- 干净D000捕获失败点定位到SolidWorks COM/启动阶段；直接启动停在隐藏splash。`lmutil lmstat`确认许可服务器和厂商守护正常，SolidWorks许可无占用。
- 服务重启因Windows权限不足被拒绝，未进行权限绕过或Windows重启。
- 回归：Python 166/166、前端TypeScript/Vite生产构建通过。

功能修改意义：先完成不依赖CAD在线会话的碰撞规则治理，同时用双门禁阻止保守占位盒被误报为完整无干涉证明。

## 2026-09-02 项目02降原型依赖求解与全链路计时

- 增加项目02`reduced-prototype`档位，移除旧Replay warm start、顶层源位姿锚定和9条历史相对位姿窗口；项目02安装、光学、行程和服务点等原型估计工程参数继续显式保留。
- 新命令行入口`solve_project_layout.py`可直接生成Top-3和展示JSON；当前rank 1通过21/21工艺、13/13空间及64/64交互门禁。连续两次运行8个模组位姿差为0。
- 修复重新求解后旧`project02_selected_solution.json`仍可能遗留的问题；现在重求解必定复位为`awaiting_visual_selection`，防止错版Replay。回归进一步发现该文件过去还兼作`calibrated` warm start，现已拆分为只读v52 Replay基准与当前人工选案两个职责。
- 新增统一`PipelineTiming`，并覆盖求解、选案、离线投影、AABB筛选、SolidWorks MCP Replay、逐工具调用、逐对叶级B-rep和优先B-rep门禁。
- 新增`project_saved_replay_poses.py`和`screen_source_independent_layout_3d.py`自身阶段计时，以及`scripts/summarize_project02_pipeline_timing.py`用于合并独立运行证据。
- 本轮28对三维宽相中严格AABB失败0，12对直接排除，16对等待真实Replay后的条件B-rep；所以当前仍是`staticInterferenceClosed=false`。
- 本轮性能量级：核心求解约3.7秒，离线投影约0.01～0.03秒，世界AABB筛选约0.02秒。Replay/B-rep未执行，计时汇总中明确标记`not-run`。
- 最终回归：后端168/168通过，McpToolRunner Release构建0警告0错误，前端TypeScript/Vite生产构建通过；最终展示文件重新切回`reduced-prototype`，旧选案与验证计划分别为`awaiting_visual_selection`和`awaiting_visual_review`。
- 详细运行说明：`docs/project02_timed_layout_pipeline-CN.md`；主要机器证据位于`demo/layout_previews/project02_*timing*.json`和`project02_reduced_prototype_*`。

功能修改意义：使项目02布局闭环可脱离助手按脚本分阶段运行，后续可以用真实时间数据优化SolidWorks加载、Replay和B-rep，而不是凭等待体感判断瓶颈。

## 2026-09-05 项目02 v22成对叶级约束与增量B-rep闭环

- `build_structural_occupancy.py`新增`--full-leaf-pair`，仅对指定高风险对象对加入完整叶实例占用；本轮A100–A300生成211/4个伙伴限定盒，结构模型升级到v42。
- v22在3.357秒内得到3个可行解，rank 1通过26/26工艺、13/13空间和65/65交互门禁；相对v21只移动A300。
- 独立九模组装配体增量更新、保存、关闭、重开成功，9/9组件和位姿通过，Fully Rebuilt；CAD阶段232.50秒。
- A300与A100/A200/A700/A800四组新B-rep全部0干涉；其余13组条件对通过相对位姿不变复用v20精检结果。
- 新增`consolidate_incremental_brep_closure.py`，合并严格AABB、当前精检、历史精检及相对位姿签名，并分别输出策略闭环和字面零干涉状态。
- 最终为`policyClosurePassed=true`、未接受失败0；A700–A800仍存在原型既有交叠的子集，所以`literalZeroInterference=false`。机器证据为`demo/layout_previews/project02_v22_incremental_brep_closure.json`。
- 回归67/67通过。

功能修改意义：将逐碰撞体试错升级为高风险对象对完整覆盖，并用可证明的结果复用把17组条件精检缩减为4组新检；同时防止把“无新增干涉”误报成“绝对零接触”。

## 2026-09-05 · 多项目标定包与求解迁移门禁

- 项目02参数包绑定最新v22增量B-rep闭环，新增统一证据字段，并显式区分粗布局可用、工程债务和生产确认。
- 新增`project_calibration.py`及构建脚本，将01/02/03/05/06不同格式的参数包归一为17类证据和一张跨项目缺口矩阵。
- 当前结果：01/02/03 `top3SolveReady=true`；05/06阻塞；全部项目`productionReady=false`。
- 06虽未建立参数包，但模组身份可由清单确认；独立CAD路径只标记为部分可用，避免把“知道CAD编号”误认为“全部子装配体可Replay”。
- 新增3项单元测试，覆盖准备状态汇总、CCD按能力启用、服务点别名归一和项目02求解范围缺口；相关离线定向回归73/73通过。
- 完整发现式回归进入现有`test_layout_preview`高代价布局求解，首项约90秒后超时/报错，已中止以避免重复长耗时；本轮没有启动SolidWorks或B-rep。

功能修改意义：建立可跨案例复用但不跨案例复制数值的机器门禁，为项目05/06后续开发提供明确采集顺序，并减少无输入条件下反复求解和SolidWorks精检的时间。

## 2026-09-05 · 项目02 v42依赖消融实验

- 新增`project02_ablation.py`和`run_project02_dependency_ablation.py`，冻结v22基线并运行A/B/C消融；求解请求可用内存覆盖且`persist=false`，不会污染当前选案。
- 从现有CAD叶体捕获生成574个无历史伙伴标记的分层几何盒；A100/A200及服务模组保留叶实例开口，传输等结构压缩到一级子树。
- A组3.33秒、3解、rank 1与v22位姿差0；B/C分别约103.78秒和90.02秒超时，均未越过A700候选验证，未启动SolidWorks或B-rep。
- 增加已知v22位姿在新几何模型下的直接复核，发现7项硬失败：6项估算维护空间、1项A300–A800叶AABB命中。由此确认B/C同时存在模型不等价与搜索成本问题。
- 新增4项消融单元测试；修正`test_layout_preview`中已落后于当前请求的6条移除约束、0.162 m门架外伸、24候选和26项工艺断言，定向回归通过。

功能修改意义：首次定量回答“是否只是复刻v42”，并建立在CAD之前判断新旧占用模型是否自洽的控制实验，防止把超时误判为无解或继续消耗B-rep时间。

## 2026-09-07 · 主线切回项目02配合关系恢复原型

- 按当前工作安排暂停v42依赖消融；其代码、冻结清单、A/B/C报告与7项几何不一致结论均保留，未继续求解、Replay或B-rep。
- 复核配合复原证据文件：项目02全量配合图、A500–A700距离8单配合闭环、A/B/C三组SLDASM与结果JSON均存在。
- 当前配合基线保持为10个实例、27条跨模组配合；A/B/C均完成24/27。A/C为10/10原型位姿，纯配合B为7/10。
- 恢复顺序固定为：T401三条失败配合最小复现 → A800自由度审计 → A500/A700过约束定位 → 完整6-DOF残差锚点压缩 → 非原型初始位姿下全量重建和重开复核。
- 本阶段不把实体无干涉作为成功判据；配合拓扑与最小定位信息闭环后，才进入独立AABB/B-rep验证。

功能修改意义：将“只有配合能否恢复原型”重新设为独立主线，并通过小装配体、自由度和最小锚点三层实验避免再次依赖原型初始位姿获得表面成功。

## 2026-09-07 · 项目02可编辑配合图基础闭环

- 新增不可变源配合图＋Patch＋Effective Graph编译链路，基础配合支持删除、参数修改和新增；保存源图/Patch哈希及逐操作审计。
- 新增`RebuildAssemblyFromMateGraph`，运行时只读取Effective Graph，不重新读取原型配合树；保存关闭重开后回读配合数量、类型、方向和数值。
- 修复引用配置未记录、叶零件未显式解析和按完整路径关闭失败三项隐藏依赖；源图Schema升级到v1.3。
- A500–A700完成50 mm基线、删除、修改60 mm、新增60 mm四组真实SolidWorks闭环，4/4通过；同面50/60 mm冲突被离线拒绝。
- 定向回归：Python 6/6、.NET 7/7；Release构建0错误0警告。详细记录见`docs/project02_editable_mate_graph-CN.md`。

功能修改意义：允许通过编辑中间数据而非修改原型CAD来验证配合变更，并为后续欠约束、过约束和最小配合集合实验提供可重复基础。

## 2026-09-07 · 项目02面端点目录与ID选面闭环

- 新增面端点目录Schema、稳定EndpointId、配置/层级/索引/几何指纹/持久引用记录，以及按ID和条件查询的离线选择器。
- Patch支持`endpointIds`并保存目录哈希；A500/A700两ID在两次真实目录构建中保持一致。
- 不使用`copyEndpointsFromMate`，仅凭两个ID新增60 mm距离关系；真实SLDASM创建、保存关闭重开和参数回读通过。
- 新增SolidWorks当前选面捕获与目录另存追加接口；已通过编译和离线追加测试，等待一次人工选择全新面的在线验收。
- 无边界全叶面扫描两次出现长COM等待，均主动终止且未写出文件；实现调整为“原配合种子目录＋指定叶/选中面按需扩展”。
- 回归：Python 14/14，.NET定向8/8，MCP Release构建0错误0警告；机器结论见`demo/mate_graph_edit/v5_endpoint_ids/face_endpoint_catalog_closure_v1.json`。

功能修改意义：将新增配合的几何端点从旧配合附属数据提升为可稳定引用的独立目录对象，并避免为日常选面重复扫描整棵SolidWorks装配树。

## 2026-09-07 · 人工新选面驱动配合重建闭环

- 从项目02原型当前选择中捕获A700新平面，生成`face:a700:a93b6607c982bd3f`并追加到3端点增量目录；该面不属于原`距离8`端点。
- 用新端点与A500端点建立垂直配合，未使用`copyEndpointsFromMate`；新装配体创建、保存、关闭、重开后回读1/1条配合。
- 修正垂直配合重开复核：Alignment对垂直关系没有几何语义，不再把SolidWorks字段规范化误判为失败；增加定向单元测试。
- 最终实体为`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular_rebuilt_v2.SLDASM`，结果JSON显示`success=true`、`parametersMatch=true`。
- 回归：.NET定向7/7通过，MCP Release构建0错误0警告；本轮未运行AABB/B-rep。

功能修改意义：首次证明人工指定的全新面可以跨越目录、Patch、CAD重建和重开回读完整链路，新增配合不再受限于原型已有配合面。

## 2026-09-07 · 指定叶扫描、目录合并与ID高亮闭环

- 新增`BuildLeafFaceEndpointCatalog`：按唯一模组＋唯一叶选择器扫描，带最大面数安全上限，不遍历兄弟叶或其他模组。
- A700的`FL5A24D062A720009.01-1`共检查1实体/99面，过滤得到34个平面端点；两次扫描34/34 ID一致，稳定运行约35.62秒。
- 新增不可变目录合并：3端点基础目录＋34端点叶目录得到36端点，新增33、同一人工真值面去重1；同ID允许世界坐标微小漂移和不同采集来源标签，但核心局部身份必须一致。
- 新增`SelectFaceEndpointFromCatalog`与命令行入口；人工真值面及纯扫描面均在SolidWorks按ID恢复、选中、缩放成功。
- 纯扫描端点`face:a700:ac51c9ef4bbe0f43`驱动新增垂直配合，真实装配体创建、保存、关闭、重开和参数回读1/1通过。
- 回归：Python 16/16、.NET定向7/7、MCP Release构建0错误0警告；未运行实体干涉检查。

功能修改意义：以有界单叶扫描替代高成本全树枚举，并证明扫描发现的非原配合面可以直接成为可编辑配合图的有效端点。

## 2026-09-07 · 面端点目录展示层MVP

- 后端新增面目录读取、SolidWorks端点高亮及只读Patch预览API；浏览器响应剔除持久引用。
- 前端新增36端点列表、模组/叶/法向/面积筛选、A/B选面、五类基础配合输入及Effective Graph预检结果展示。
- 实测A500 `face:a500:7d587bfd92815e6f`与A700 `face:a700:ac51c9ef4bbe0f43`生成垂直Patch预览成功；2模组、2有效配合、0警告。
- 实时MCP高亮A700端点成功；修正调用名为`select_face_endpoint_from_catalog`。
- 修正跨项目就绪面板对缺失可选数值直接`toFixed()`导致的白屏，缺值现在显示`n/a`。
- 验证：前端生产构建通过；Python定向15/15；MCP Release构建0错误0警告；浏览器完整交互通过。

功能修改意义：提供在CAD修改前浏览、筛选、核对几何端点并审计配合Patch的展示层，缩短“候选面发现—人工确认—重建实验”的反馈周期。

## 2026-09-07 · 展示层应用Patch与A500/A700过约束初诊

- 新增`POST /api/demo/mate-face-catalog/apply`：要求显式确认与未过期预览摘要；输出被限制到工作区专用目录并实行全产物不可覆盖。
- 展示页新增输出路径、风险确认和SolidWorks闭环结果；实测生成`demo/mate_graph_edit/ui_runs/project02_A500_A700_ui_20260907T103357Z.SLDASM`，请求/创建/重开为2/2/2，参数匹配通过。
- 新增`mate_overconstraint_audit.py`及分析脚本；A/B/C结果共同指向A600–A700的`宽度10`为首个过定义候选，`距离29`为次级候选，A500疑似经`距离8`传播。
- 新增定向测试覆盖确认门禁、摘要失效、路径越界、不可覆盖、真实产物要求与审计输出；前端生产构建通过。
- 下一步进行一个有界实验：删除`宽度10`重建A600+A700最小子图，不并行运行多组SolidWorks重建。

功能修改意义：把可视化Patch从只读建议升级成可审计、可恢复、不会误覆盖的CAD执行入口，并把长期反复的过约束问题压缩为单边因果验证。

## 2026-09-07 · A600/A700两阶段过约束隔离

- 编译A600+A700最小有效图：删除`宽度10`后剩余5条基础配合、0警告；真实重建5/5、重开5/5，`距离29`仍返回过定义。
- 第二图同时删除`宽度10`与`距离29`，剩余4条；真实重建4/4、重开4/4、参数一致，所有创建结果均为NoError。
- 两次耗时分别为248.10秒、214.98秒；生成的SLDASM分别约27.83 MB、27.82 MB。
- 原型源特征状态显示两条候选配合均无错误；结论分类为`reconstruction-redundancy-or-semantic-difference`，暂不将删除关系写入正式约束。
- 新增通用计时重建脚本、阶段二隔离分析器与测试；后端定向测试13/13通过。
- 机器报告：`demo/mate_graph_edit/diagnostics/project02_A600_A700_overconstraint_stage2_v1.json`。

功能修改意义：使用可证伪的删边实验明确了当前重建器与原型求解状态之间仍存在语义缺口，为后续补齐刚柔性、Width高级选项和重开组件状态提供直接依据。

## 2026-09-07 · A600/A700完整配合语义闭环

- 模组配合图schema升级至v1.4，新增顶层组件`SolvingState`及Width完整高级选项；重建前显式恢复组件刚/柔性。
- 可编辑图验收新增创建错误清零、组件不过约束、组件刚柔性一致三项严格门禁；展示页同步显示。
- 真实保留A600+A700全部6条原型关系完成另存和重开：6/6创建、6/6回读、全部NoError，Width10高级参数匹配；A600刚性完全约束，A700柔性欠约束且不过约束。
- 根因报告分类为`confirmed-missing-a700-flexible-solving-state`：旧重建遗漏A700柔性是过定义的决定性原因，删除Width10/Distance29不再是推荐修复。
- 产物入口：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_baseline_v1.SLDASM`及同名前缀结果文件；根因报告为`project02_A600_A700_full_semantics_audit_v1.json`。
- 回归：Python定向24/24、.NET定向29/29、前端生产构建通过；后台与展示页在线复核正常。未执行AABB/B-rep。

功能修改意义：把配合重建闭环从“条数与参数回读”提升为组件求解语义一致，并证明原型健康关系无需删减即可复原，为整机配合图重建消除关键阻塞。

## 2026-09-08 · 项目02去v42约束求解首次产出可行Top-3

- 新增保护空间`hard/advisory`分级、`conditionalBrepWith`伙伴路由、硬失败/软告警分离统计和展示警告。
- B/C构造时移除条件B-rep与历史强制叶盒硬分离的矛盾，不修改项目02主请求及v22基线。
- 新增v22兼容门禁和模组候选阶段诊断；A700在B/C分别消耗约11.70/28.33秒。
- B/C均成功生成3解，用时约13.69/30.72秒；C作为展示候选，CAD Replay保持锁定。
- 定向回归63/63通过；全程未启动SolidWorks或B-rep。

功能修改意义：证明不使用v42伙伴碰撞标记也能快速生成项目02完整候选，并把下一步成本从盲目CAD试错收敛为一次展示层人工选案。

## 2026-09-08 · 项目02去依赖候选只读展示闭环

- 新增B/C消融结果只读API和前端对比面板；显示Top-3、耗时、相对v22位移、硬门禁、维护告警及条件CAD风险。
- 浏览器实测B/C切换正常：B评分3.334、171处叶盒预命中；C评分2.793、117处叶盒预命中。
- C仅标记为“推荐目测”；面板不存在CAD批准或Replay操作，654.1 mm位移与15项CAD风险保持显式可见。
- 前端生产构建通过，约束与消融定向回归64/64通过；未启动SolidWorks或B-rep。

功能修改意义：把离线候选评估做成可见、可审计且不会误触CAD的中间门禁，为下一轮人工选案或约束回调提供低成本入口。

## 2026-09-08 · B/C九模组实体生成与分阶段计时

- 清理两个无窗口SolidWorks残留实例及会自动拉起嵌入式实例的旧headless hub，恢复单一可见SolidWorks 2024 SP5会话并通过MCP健康检查。
- 候选物化支持显式授权的方向旋转；C的A700按求解结果旋转180°。新增B/C CAD准备脚本、直接建装输入和定向测试。
- B从空白生成、C从独立B模组集合另存后切换位姿；两者均完成九模组保存、重开、位姿复核与完全重建，未复制原型总装。
- B端到端538.14秒，C端到端363.07秒；CAD阶段分别524.28/332.17秒。COM连接、全量位姿读取、重建和首次模组插入为主要瓶颈。
- 保存后世界AABB筛查耗时均低于0.04秒：B因A180–A700严格重叠被门禁拒绝；C严格失败0，17组待条件B-rep。
- 新增统一时间汇总`demo/layout_previews/project02_dependency_ablation/cad/project02_dependency_ablation_cad_timing_summary.json`，包含阶段时间戳、工具调用时间线、恢复事件和验证边界。

功能修改意义：完成离线候选到真实CAD实体的闭环，并用快速三维宽相在昂贵B-rep前淘汰B；同时给后续脚本化运行和性能优化建立可量化基线。

## 2026-09-08 · B/C功能模组叶级B-rep检查

- B精检A180–A700：86.17秒，0实体干涉；B的问题修正为“20 mm净距不满足”，不是实体碰撞。
- C精检6组功能模组对：总批次538.84秒，全部检查完整、布尔计算失败0。
- C确认A180–A200有5组、A300–A700有57组、A500–A700有34组叶实体干涉；A200–A300、A200–A500、A200–A700为0。
- C因此被实体门禁拒绝，停止其余低优先级B-rep；结果已写入独立干涉目录并纳入schema v3统一时间汇总。

功能修改意义：精确区分宽相假阳性、工程净距失败和真实实体穿透，并为扫描–CCD通道以及A700对A300/A500的候选期硬避让提供直接反馈。

## 2026-09-08 · 项目02碰撞反馈加固F组

- 新增`project02_collision_feedback.py`，将完整无计算失败的叶级B-rep批次转换为可审计硬约束；不接受中断检查或仅AABB证据。
- A180–A200、A300–A700、A500–A700三组已确认干涉升级为候选期硬避让；A700禁用造成大面积碰撞的180°候选。
- 新增独立求解脚本和完整阶段计时。F组首次22.03秒、重复21.20秒得到相同3解，Top-3位姿与排序完全一致，且均通过禁止姿态、确认碰撞对及拒绝位姿重复门禁。
- 只读展示页增加F组，与B/C并列且默认推荐目测；实际接口和浏览器加载通过，未覆盖标准项目02预览。
- 定向测试12/12、前端构建通过；全后端231通过、6项既有默认预览/warm-start测试失败，已记录为独立技术债。
- F组仍有A700–A800 100个叶盒宽相命中，下一步先目测，再做该对的选择性精确B-rep，不能宣称已完成零干涉闭环。

功能修改意义：让实体精检失败能够在下一轮求解前自动转成剪枝，而不是再次生成同类错误后手工移动；同时把已知碰撞消除与未知非凸关系验证严格分层。

## 2026-09-08 · A700–A800精确禁入域与H11安全无解

- H5/H6/H7的A700–A800精检均为15组干涉；修正H7错误复用历史CAD投影基线的问题，并强制后续迭代显式传入上一轮布局和保存位姿。
- H8九模组装配体生成、保存重开、位姿和尺寸审计通过，CAD耗时430.28秒；世界AABB筛查0.043秒，严格对象对失败0。
- H8 A700–A800完整叶级B-rep耗时228.82秒，检出28组干涉、计算失败0；零干涉门禁明确拒绝该实体。
- 固定步长反馈被精确叶AABB公共轴算法替代：本轮推导V+154.3、U+252.4、V-285.2、U-459.6 mm四个充分避让候选，并形成不对称相对位姿禁入矩形。
- H11在约20.85秒返回`NO_FEASIBLE_LAYOUT`，不再生成已知不安全CAD；无解原因、反馈证据、硬化请求、空预览和时间戳均已落盘。
- 修复CAD迭代无解时的未处理异常；批次精检失败返回非零状态；更正`reduced-prototype`说明为“无原型Replay warm start，但可使用不锁定位姿的上一轮独立求解种子”。
- 回归：后端定向90/90、Python编译、前端生产构建全部通过。

功能修改意义：将高成本B-rep结果转成有尺度依据的求解禁区，并在硬约束冲突时快速、安全地停止，而不是继续小步试错或输出碰撞方案。

## 2026-09-09 · 项目01/03第二候选独立装配体

- 物化项目01、项目03各自Top-3中的rank 2，使用独立选案JSON、独立Replay JSON和新目标文件，未覆盖原型及既有rank 1装配体。
- 项目01第二候选仅将GN00沿安装坐标U移动-30 mm；实体包含10/10顶层模组。保存重开后组件集合一致，最大变换元素误差约`6.54e-9`。
- 项目03第二候选仅将AH00沿安装坐标V移动-30 mm；实体包含15个顶层组件，其中10/10主模组、5个辅助件。保存重开最大变换元素误差约`7.30e-9`。
- 两案均通过12组普通实体严格AABB门禁，失败0组；各有9组门洞/嵌套条件关系仍路由到选择性叶级B-rep，7组安装接触关系仍待按原型基线或精检处理，故不宣称全实体零干涉或生产放行。
- 修正项目01/03 Replay位姿审计：非rank 1方案改为对比选案目标变换，而非错误地对比原型变换；项目03筛查脚本新增可参数化输入输出。
- 定向回归`test_project01_collision.py` 4/4通过。

实体产物：

- `demo/project01/FL9C24N074AA00_project01_solution2_v1.SLDASM`
- `demo/project03/FL9A24D063A000_project03_solution2_v1.SLDASM`

功能修改意义：证明Top-3不只是展示数据，非首选候选同样可以隔离选案、实体化、保存重开和进入分级干涉验证；同时消除审计器只适配原型等价rank 1的隐含限制。

## 2026-09-10 · 需求到模组功能现状复核与接续文档

- 复核项目02自然语言需求解析、能力依赖、模组推荐、人工确认、JSON留痕和展示页代码；确认推荐API仍只支持项目02。
- 明确当前输出粒度为模组代码与组件名，尚未返回校验后的完整CAD文件路径；确认后的任意模组子集尚不能动态驱动布局求解。
- 专项回归6/6通过，前端TypeScript/Vite生产构建通过。
- 新增现状文档`docs/requirement_to_modules_current_progress-CN.md`，统一记录功能边界、代码入口、测试证据、未完成事项和后续优先级。

功能修改意义：避免把“项目02模组推荐Demo”误表述为“跨项目文件级自动选型”，并把下一步收敛为版本化模组/文件注册表和项目02动态子集求解两个核心闭环。

## 2026-09-10 · 自然语言模组检索与前端专项交接

- 新增`docs/requirement_module_retrieval_frontend_handoff-CN.md`，面向新开发人员整理自然语言能力匹配、模组/文件检索和前端展示任务。
- 明确交接范围不包含动态子集求解、空间布局、SolidWorks Replay、配合重建或干涉检查。
- 文档包含现有代码与接口、数据源、建议注册表Schema、前端组件拆分、四阶段实施顺序、十类验收用例、本地启动命令及开发注意事项。

功能修改意义：将可独立并行开发的“需求检索与展示”从布局/CAD主线解耦，使新同学可以在不启动SolidWorks、不理解求解器内部实现的情况下完成可验收交付。

## 2026-09-15 · 项目02语义端口与增量配合图第一阶段

- 配合图Patch新增`addModule`/`addComponent`，可在有效图中加入新子装配体节点并建立配合边。
- 新增`semantic-port-catalog/v1`、连接模板和编译器，把工程端口稳定绑定到面注册表EndpointId，再生成可执行基础配合。
- 用真实A500/A700和原型`距离8`端点完成确定性样例：从仅含A700的图加入A500，生成50 mm距离关系；有效图为2模组/1配合，源图与原型不变。
- 新增目录加载、连接预览和确认执行API；使用摘要防过期、限制独立输出目录、拒绝覆盖，并固定采用独立重建模式。
- 展示页新增语义端口、面绑定、有效图摘要、执行边界与自由度警告；当前明确标记为局部关系，不宣称A500完成六自由度定位。
- 定向测试30/30、Python编译、前端生产构建、真实API联调和浏览器视觉验收通过；本轮未启动SolidWorks，未做实体干涉验证。
- 详细记录：`docs/project02_semantic_port_increment-CN.md`。

功能修改意义：首次把“在装配图中增加新组件并指定工程接口”表达为可追溯、可编辑、可预检的节点与边增量，为后续自然语言选端口和真实CAD增量装配建立稳定中间层。

## 2026-09-15 · 项目02 A500完整语义安装与实体闭环

- 从完整原型配合图确认A500由A600的`重合13＋宽度4＋距离27`主要定位，`距离8`只表达A500–A700的50 mm工艺间距。
- 面端点目录新增“按指定源配合提取”模式；复用持久引用EndpointId，不再为少量已知安装面执行全叶扫描。
- 语义模板新增四面宽度配合和有序多端点；新增`semantic-assembly-plan/v1`，可一次加入一个模组并连接多个既有模组。
- 新增固定上下文策略：A600/A700使用已知上下文位姿并固定，A500从确定性非原型初始位姿开始由配合定位。
- 阶段2实体实验3/3配合创建、保存重开及参数复核通过，A500为`swFullyConstrained`，耗时224.57秒。
- 反例实验把`距离8`作为第4条驱动配合后触发`swAddMateError_OverDefinedAssembly`，证明需区分驱动配合与验证关系。
- 新增`validate_only`语义；最终仅写入3条驱动配合，同时保留1条验证关系。最终装配体3/3配合重开一致、错误清零，A500/A600/A700均完全约束，耗时286.19秒。
- 后端相关测试33/33、C# EditableMateGraph测试7/7、前端生产构建通过。
- 详细记录：`docs/project02_semantic_port_increment-CN.md`；闭环报告：`demo/semantic_ports/project02_A500_full_installation_v2/semantic_assembly_closure.json`。

功能修改意义：把“新增组件＋单一距离边”的局部Demo升级为真实多端口安装闭环，并用负向实验识别冗余工艺尺寸，避免将完整语义错误地等同于全部驱动配合。

## 2026-09-21 · 项目02自然语言语义装配预检

- 新增`semantic-assembly-intent/v1`和项目02受控中文解析器，将需求提取为新增模组、固定上下文、刚柔性、工程关系、驱动/验证模式和独立输出策略；解析器不生成任何Face。
- 语义端口目录增加能力和别名，连接模板增加用途；新增确定性端口检索、评分、兼容模板选择和同分歧义阻断。
- 新增刚柔性一致性门禁；真实数据确认A500刚性、A700柔性与需求一致。
- 新增冗余约束门禁：把A500—A700的50 mm验证关系要求为驱动时直接拒绝，避免再次触发已验证的过约束。
- 新增只读`intent-preview` API、命令行预览脚本和前端自然语言审核区；展示结构化意图、端口选择依据、模板、刚柔性检查，再进入人工确认。
- 项目02真实预览成功选择2组端口，编译3条驱动配合和1条验证关系，完整定位证据为真；留痕文件为`demo/semantic_ports/project02_A500_full_installation_v2/natural_language_intent_preview.json`。
- 后端定向测试18/18、Python编译和前端生产构建通过；FastAPI真实HTTP联调中成功请求返回200，冗余驱动负例返回422并说明过约束原因。

功能修改意义：自然语言不再直接触碰CAD几何，而是先落到可审计意图，再由端口目录和面注册表确定性编译配合图；错误请求在SolidWorks启动前即可被阻断。

## 2026-09-21 · 语义增量装配的尺寸实测与实体发布门禁

- `validate_only`关系补齐完整面端点；SolidWorks保存重开后稳定恢复两个面并实测`距离8=49.999999999997 mm`，对50 mm目标的误差约`2.65e-12 mm`，0.1 mm容差内通过。
- 重建结果新增顶层模组世界变换和世界AABB；修复`ListComponentPoses(topLevelOnly=true)`仍递归全树的性能缺陷，真实三模组AABB采集降至0.617秒。
- 对A500/A600/A700三对顶层AABB重叠候选执行叶级B-rep：A500–A600为0干涉；A500–A700为11组；A600–A700为8组；内核失败0。
- 三对精检总计688.391秒，全流程691.143秒，证实主要耗时在叶级精确几何，而非宽相或求解。
- 新增`semantic-assembly-release-gate/v1`、生成脚本和测试；CAD重建、尺寸实测、完整精检必须全部通过。真实产物被明确拒绝发布：`REJECTED_BY_HARD_GATE`。
- 新增叶身份基线比较器，忽略新装配体根层级变化，同时保留重复实例身份。A500–A700当前11组与v42完全相同、相对原型0组全部为新增；A600–A700当前8组中4组匹配原型、4组新增。
- 发布门禁升级为基线感知：只有全部干涉模组对都有已确认基线且新增干涉为0时才能通过；本轮2/2基线覆盖完整，接受原型已有4组，仍因新增15组拒绝发布。
- 根因收敛为独立重插A700时内部柔性/配置姿态漂移：顶层Transform2、配置T和SolvingState=Flexible仍不足以恢复叶级状态。下一步改为在既有上下文副本中增量执行，或显式记录/恢复柔性子树内部位姿。
- 前端结果区分“重建/尺寸通过”和“实体安全待门禁”，不再把配合闭环误表述为零干涉闭环。
- 回归：Python定向18/18通过；C# EditableMateGraph 10/10通过；SolidWorksMcpApp Release构建0警告0错误；前端TypeScript/Vite生产构建通过。

功能修改意义：建立了“配合正确不等于实体安全”的机器硬边界，并把昂贵B-rep限制在顶层AABB候选对；今后碰撞方案将被否决，而不是作为可用解输出。

## 2026-09-21 · 项目02 A500保留柔性上下文的增量重配合闭环

- 新增上下文重配合执行器：复制完整项目02原型，在副本中抑制A500四条源关系，从确定性非源位姿用`重合13＋宽度4＋距离27`重建，`距离8`保持只验证。
- 修复性能路径：取消完整装配递归解析；端点按相对层级路径定向下钻；A700快速指纹只覆盖顶层和语义端点叶；多次全装重建合并为一次；重开后只读取3个目标配合。
- 正式V6用时474.04秒；3/3配合创建、保存重开及参数复核通过，A500完全约束，A700上下文最大变换误差`6.90e-14`。
- `距离8`保存重开后实测`49.999999999925 mm`，对50 mm目标误差约`7.47e-11 mm`，0.1 mm容差内通过。
- 条件叶级B-rep三对全部完成、内核失败0：A500–A700=0，A500–A600=0，A600–A700=4且与原型允许基线完全一致；新增干涉=0。
- 条件B-rep总耗时1400.06秒；统一发布门禁升级为可直接读取带逐对基线接受结论的批次格式，正式状态`RELEASE_ALLOWED`。
- Python语义安全/目录/意图回归22/22通过；C#配合图单测12/12通过；SolidWorksMcpApp Release构建0警告0错误；前端生产构建通过。
- 详细记录：`docs/project02_semantic_port_increment-CN.md`第10节；正式实体：`demo/semantic_ports/project02_A500_full_installation_v2/project02_A500_context_remate_V6.SLDASM`。

功能修改意义：证实第9节的15组新增干涉来自空白重插柔性A700，而不是A500端口或50 mm尺寸；通过保留父装配上下文从上游消除新增碰撞，完成语义装配到实体发布硬门禁的首个正向闭环。

## 2026-09-21：项目02 A500真正独立插入与实体发布闭环

- 新增`AssemblyContextIncrementalInsert.cs`和MCP工具`InsertComponentInAssemblyContextFromMateGraph`：复制原型上下文后删除原A500，从独立SLDASM插入新A500，并由有效配合图从确定性非源位姿恢复。意义：从“重配合已存在组件”升级为真正的增量装配。
- 后端语义装配增加`context_incremental`/`blank_rebuild`模式；项目02默认上下文增量插入，前端明确展示父级上下文保留与原型不修改。意义：避免把柔性A700重插进空白装配体造成内部叶姿态漂移。
- V7实体`demo/semantic_ports/project02_A500_full_installation_v2/project02_A500_context_insert_V7.SLDASM`闭环通过：原A500删除、A500-2独立插入、3/3配合、完全约束、距离8实测50 mm、A700上下文稳定。
- 三对条件B-rep完成：A500-2–A700为0、A500-2–A600为0、A600–A700为原型基线4组且无新增；统一门禁`RELEASE_ALLOWED`。精检批次耗时1469.69 s，重建命令474.86 s。
- 发现后台Hub初始化超时与新增实例后缀变化问题；本轮用直接stdio和结果中的`InsertedComponentName`完成闭环。后续精检编排必须自动解析真实实例名，并把连接耗时与B-rep耗时分开。
- 回归：Python 25/25、C#定向12/12、Release编译/发布、前端1581模块构建通过；完整C#集成测试因会连接当前CAD会话且长时间无输出而主动中止，未宣称全量通过。
- 详细记录见`docs/project02_semantic_port_increment-CN.md`第11节。下一步把条件B-rep异步编排、实例名映射和证据缓存接入API/展示层，再迁移其他模组与项目。

## 2026-09-22：项目02条件B-rep自动编排与证据缓存闭环

- 新增`semantic_assembly_closure.py`和`run_context_incremental_release_closure.py`：从V7重建结果自动解析A500真实新增实例后缀，从有效图解析A600/A700，并生成三组条件B-rep计划。
- 用装配体二进制、有效图、模组源文件和精检策略构成联合SHA-256证据键；只有路径、精检对、检查完整性和接受结论全部一致时才允许复用精确证据。
- 叶级精检新增装配体检查前后SHA校验，检查期间文件变化直接作为硬失败，避免把并发修改后的结果写入缓存。
- V7已有精检批次完成一次显式登记后，自动闭环仍为`RELEASE_ALLOWED`；首次登记与门禁耗时0.610453秒，重复运行安全命中缓存后仅0.092997秒，未再次启动SolidWorks/B-rep。
- 后端目录API和语义端口展示页新增最新实体闭环状态：显示实际实例映射、3/3精检、新增干涉0、缓存复用和编排耗时。
- 回归：后端相关测试25/25、Python编译、真实工作区摘要加载、前端1581模块生产构建均通过。
- 详细记录见`docs/project02_semantic_port_increment-CN.md`第12节；证据目录为`demo/semantic_ports/project02_A500_full_installation_v2/context_insert_v7_auto_closure/`。

功能修改意义：把实例后缀、精检对、允许基线、耗时B-rep和发布门禁从人工串联升级为可审计自动闭环，并以严格指纹缓存将相同实体的重复验收从约24.5分钟降到0.1秒量级。

## 2026-09-29：项目02自然语言有序多模组编排第一阶段

- 新增受控中文顺序解析器，支持“先/再/然后/接着/最后添加模组”，保留用户顺序并拒绝重复、缺项目编号或含糊命令；
- 新增项目02模组依赖与工艺策略表，逐步展开布置原则、前置模组、验收检查和实现状态；
- 新增安全门禁：只有全部步骤都具备已验证CAD执行能力时才允许启动整链；当前示例5步中仅A500为已验证单步，因此正确停留在预演阶段；
- 新增只读预演API、命令行脚本和JSON留痕，预演不启动SolidWorks、不修改原型；
- 前端新增步骤时间线，区分“顺序阻断”“规划完成待补CAD模板”“单步CAD已验证”，并显示具体能力缺口；
- 测试：新功能8/8，语义相关联合回归21/21，Python编译、前端1582模块生产构建、正确/错误顺序真实HTTP联调均通过。
- 详细记录：`docs/project02_semantic_port_increment-CN.md`第13节；预演产物：`demo/semantic_ports/project02_ordered_sequence_preview.json`。

功能修改意义：首次把多模组自然语言指令转成可审核的顺序计划和执行门禁；后续可逐个接入A800、A180等真实安装端口，而不需要改写自然语言层，也不会把尚未验证的模组错误送入耗时CAD流程。

## 2026-09-30：项目02 feedback10 九模组静态闭包推进

- 精确碰撞反馈已进入求解候选阶段；新增固定环境清晰锚点自适应禁区和单模组`postCaseAnchorBias`，v12三候选全部通过求解硬门禁。
- feedback9证明“顶层A100改为刚性”仍不足以保持叶状态，A100/A600仍出现2组新增接触，候选被拒绝。
- feedback10改用已验证A100静态刚性替换体且保持顶层Transform完全一致；A100变化关系中5对新B-rep为0干涉，2对命中精确缓存，1对严格AABB分离。
- 修复长路径精检证据写盘失败；兼容两种位姿目录格式和静态A100别名；新增36对象对闭包汇总器。
- 当前世界AABB与精检综合门禁为32/36接受，剩余A180/A200、A180/A800、A600/A700、A600/T401-1四对正在精检。候选装配体尚未发布。
- 焦点回归93项通过；未执行全仓所有长耗时CAD集成测试。详细记录见`docs/project02_full_machine_execution-roadmap-CN.md`第12节和`docs/layout_constraints_and_solver_principles-CN.md`第81节。

## 2026-09-30：自然语言真实CAD装配流程阶段1—4闭环

- 建立版本化项目装配档案，将项目02的顺序、依赖、实例数、CAD策略、碰撞策略和参数来源从分散硬编码迁移到统一JSON；配置测试18/18通过。
- 建立通用`assembly-intent/v1`、`assembly-plan/v1`及稳定摘要；自然语言、前端、作业和CAD执行可绑定同一计划；联合回归39/39通过。
- 建立作业级证据清单，对检查点装配体、CAD动作、碰撞门禁和事件日志登记路径与SHA-256；缺少实体安全证据时不允许静态验收；联合回归52/52通过。
- 建立全链只读审计器；项目02为9个语义阶段、10个CAD对象、45/45对象对已接受，现场CAD动作全部可编译，阻断项为0；审计测试14/14通过。
- 当前边界：静态Demo可回放且现场长链已具备启动条件；生产动态放行仍被A700真实状态和A100全行程证据阻断。
- 详细记录：`docs/natural_language_cad_assembly_pipeline-CN.md`。

## 2026-09-30：自然语言项目02完整现场CAD长链闭环

- 单一持久化作业`project02-job-9f7a6f346ee2`连续完成A800、A180、A700、A300、A500、A100、A200和双T401，8/8检查点提交，无失败、无回滚。
- 最终形成10个顶层CAD对象；逐步碰撞证据汇总为45/45唯一对象对接受，其中17对AABB严格分离、28对命中版本化B-rep缓存。
- CAD动作证据10/10，证据清单无缺失，静态整链放行；生产动态放行仍因A700真实状态和A100全行程证据保持关闭。
- 总耗时2447.483秒；A100单步761.254秒，是下一轮性能优化重点。
- 最终实体：`demo/semantic_ports/project02_ordered_jobs/project02-job-9f7a6f346ee2/cad-working/step-08-t401-attempt1-action2.SLDASM`。
- 统一索引：`demo/semantic_ports/project02_full_machine_increment_v1/latest_live_full_chain.json`；详细记录见`docs/natural_language_cad_assembly_pipeline-CN.md`。
- 本轮最终回归62/62通过，前端1582模块生产构建通过；后台重启后HTTP实测全链审计7/7、完整命令8步、执行门禁允许，前端5173返回200。
- 闭包读取器升级为优先加载`latest_live_full_chain.json`；展示页和API现指向本轮真实现场作业及其最终实体，仍保留历史闭包作为后续CAD动作模板来源。

## 2026-09-30：自然语言完整装配展示层只读验收

- 在不创建现场CAD作业的前提下刷新并检查`http://127.0.0.1:5173/`：完整命令已覆盖A600、A800、A180、A700、A300、A500、A100、A200及T401。
- 界面已明确区分“已验证产物回放”和“现场CAD逐步执行”，默认保持安全的回放模式。
- 最新实体闭环正确显示为9个语义阶段、45/45模组对接受，最终装配体指向`project02-job-9f7a6f346ee2`真实长链产物。
- 全链预检显示7/7通过，回放与现场长链均为可执行；同时明确提示生产动态发布尚未通过。
- 参数来源边界正确显示：7个模组仍含原型推断，静态Demo参数允许、生产参数拒绝；生产放行仍需A700真实状态/静态功能区确认、A100权威XYZ限位及连续扫掠与软管维护证据。

功能修改意义：展示层不再把历史模板或静态闭包误表述为最新结果；使用者能在启动SolidWorks前同时看到命令、执行模式、真实CAD证据、碰撞门禁和生产边界。

## 2026-09-30：项目02生产参数权威注册表闭环

- 新增9项参数级权威要求，覆盖A600/A800/A180/A700/A300/A500/A100/A200/T401；每项均记录基线来源、证据、必需字段和签认决定。
- 支持工程师/厂商签认现有基线，或提交字段完整的替换值；签认无责任人、时间、证据或替换缺字段时硬失败。
- 新增权威覆盖层编译器：9/9生产要求未闭环时拒绝生成；测试注册表9/9签认后可生成稳定摘要覆盖层。
- 当前真实结果：静态基线证据9/9存在，静态Demo继续允许；生产权威签认0/9，生产门禁继续拒绝，未虚构任何厂商数据。
- 原型依赖API和展示页增加“权威参数签认0/9”信息；后端定向回归31/31、前端1582模块生产构建通过。
- 证据：`demo/semantic_ports/project02_full_machine_increment_v1/parameter_authority_audit.json`；详细记录见`docs/natural_language_cad_assembly_pipeline-CN.md`第16节。

功能修改意义：把“去原型”从一次性改代码转为可逐项替换、签认、审计和回归的工程流程；外部参数到位后无需重写求解器即可升级生产门禁。

## 2026-09-30：项目01/03自然语言有序计划迁移

- 新增项目01和项目03版本化装配档案，分别采用自身的箱体、传输、翻转、扫描、功能、校准、供胶和龙门/双阀组，不复用项目02绝对位姿。
- 新增通用`ordered-assembly-command/v2`和`ordered-assembly-plan/v2`解析/计划器；两项目自然语言命令均生成7步有效顺序和稳定摘要。
- 项目01/03所有步骤当前标记为`layout_validated_cad_action_missing`，预演可审核但`safeToStartCad=false`；作业API对这两个项目显式硬拒绝。
- 多项目审计更新：01/03已从“缺版本化配置”推进到“缺7步项目专属CAD动作和完整静态闭包”；05/06仍停留在项目标定阶段。
- 测试：跨项目配置、解析、顺序反例、审计及API定向回归23/23通过；项目01 HTTP联调返回7步、7个实现缺口并禁止CAD。
- 证据：`demo/semantic_ports/project01_ordered_preview.json`、`project03_ordered_preview.json`及`demo/layout_previews/multi_project_assembly_pipeline_audit.json`。

功能修改意义：公共自然语言和计划层已跨项目复用，同时保持项目专属几何与CAD动作隔离；下一阶段可从项目03的AA00→AE00开始逐步补真实实体证据。

## 2026-09-30：项目03前两步真实增量CAD闭环

- 新增路径恢复硬门禁、AA00/AF00固定上下文、AE00/AD00三基准语义端口、工作包与闭包汇总器；旧图乱码路径按权威目录内唯一文件名恢复并登记SHA-256。
- AA00+AF00基座368.214秒；AE00插入155.829秒，3/3配合、完全约束、保存重开及3/3对象对闭包通过。
- 从AE00检查点累计插入AD00耗时140.879秒，3/3配合、完全约束、保存重开及6/6对象对静态闭包通过；最大顶层位姿误差`2.998e-15`。
- AE00–AD00复用原型叶级B-rep基线（6组既有交叠、0失败）；只证明无新增干涉，不宣称零接触。
- 项目03配置升级到`2026-09-30.3`，自然语言7步中2个静态CAD步骤已验证、剩余5个。
- 首次基座schema错误被5秒前置校验安全拦截且未生成实体；修正后闭环。阻塞仍为AD00 25°动态扫掠、6组既有交叠工程分类和AI00安装/光学端口。

功能修改意义：跨项目能力首次形成连续两个有真实CAD证据的增量检查点，并保留静态/动态发布边界。

## 2026-09-30：项目03 AI00第三步真实增量CAD闭环

- 新增AI00工作包与闭包：机械定位、光学验证、位姿审计和碰撞门禁使用同一可追溯证据链。
- 首轮5条关系全部驱动产生2个`swAddMateError_OverDefinedAssembly`，耗时143.860秒，被硬门禁拒绝。
- 修复为3条驱动配合+2条距离验证关系后，AI00从非源位姿成功恢复；3/3驱动、完全约束、求解清洁、保存重开通过，290 mm和10 mm实测误差均小于`2e-14 m`。
- 累计5模组最大Transform误差`7.05e-15`；10/10对象对按2对严格AABB、8对原型相对位姿等价闭合，AE00–AI00保留原型2对既有相交，不宣称绝对零干涉。
- 光学静态Demo通过；100 mm厂商工作距离、真实条码面和载具身份头角色未确认，生产门禁关闭。
- 项目03档案升级到`2026-09-30.4`，7步中3步有真实CAD证据，剩余4步；定向回归15/15通过。

功能修改意义：用真实CAD反例把“配合图中的关系”分成驱动关系和只验证关系，避免重建流程因冗余尺寸过约束，同时保留尺寸与工艺语义的验收价值。

## 2026-09-30：项目03 AG00第四步增量CAD闭环

- 新增AG00自由度诊断包和显式残差锚定包，六个服务目标作为只验证工艺端口，不参与机械驱动。
- 无锚点诊断：2/2配合成功且参数一致，但重开后未完全约束，145.240秒结果被拒绝，证实源平面+单孔留下1个转动自由度。
- 显式锚定：保留2条真实配合，原型顶层姿态仅作为可替换残差锚点；115.636秒完成独立插入、完全约束和保存重开。
- 累计6模组最大Transform误差`7.05e-15`；15/15对象对静态闭合，5对AABB分离、10对原型相对位姿等价，无新增干涉但不宣称绝对零干涉。
- 项目03档案升级到`2026-09-30.5`，7步中4步有静态CAD证据，剩余3步；相关回归14/14通过。

功能修改意义：形成可复用的“理论自由度分析 → 非锚定CAD反例 → 显式临时锚点 → 生产替换债务”流程，既不中断Demo累计装配，也不隐瞒原型参数依赖。

## 2026-09-30：项目03宏观10对象闭环与AC00柔性状态阻塞定位

- AH00、AJ00、AB00增量步骤完成真实CAD保存重开；AB00使用1驱动+1距离验证+显式残差锚点。
- AC00顶层独立插入通过，10个根节点最大Transform误差`5.86e-14`；45对宽相为22对AABB分离、23对候选。
- 原型/独立AC00完整子树对比：134节点中72节点不稳定，最大平移差340.851 mm；11个分支锚点在重开后漂移，顶层刚性不能固化嵌套状态；根节点预固定后同心配合过约束。
- 新增AC00静态快照选择器、配合前根锚定策略、宏观闭环汇总器和闭环感知的多项目审计；定向测试19/19、监控回归12/12通过。
- 状态固化为`PROJECT03_MACRO_STATIC_CAD_CLOSED_FULL_GEOMETRY_BLOCKED`。完整B-rep有意推迟，避免对错误内部状态做高成本无效检查。
- 阻塞：AC00父装配柔性内部状态尚无可移植表达。下一步导出内部配合/抑制/配置；若无命名配置，构建派生静态快照子装配体并要求134/134节点重开一致。

## 2026-10-01：项目03 AC00混合静态快照与10对象实体闭环

- 单次118叶展平长链因CAD无进展终止；分批流程定位到两个独立打开会触发关键数据修复的零件。
- 保留AC20/AC30/AC40刚性子装配，其余节点展平；34个顶层节点覆盖118个叶实例。
- 两批、总快照及三个刚性分支内部姿态全部保存重开通过；最大Transform误差`4.44e-16`。
- AC00快照增量插入九模组检查点成功，耗时127.028秒；最终10对象实体已保存，九个上下文根节点零漂移。
- AABB快筛45对：22对排除、23对待/正在精确B-rep；逐对结果持久化，发布门禁在23/23完成前保持关闭。
- 当前成果是完整静态几何混合复原，不是AC00运动/配合语义复原，也不是生产动态放行。

## 2026-10-01：项目03 45/45静态碰撞与有序装配整链闭环

- 23个AABB候选全部完成叶级B-rep，累计精检耗时6179.090秒；17个模组对为零干涉，6个模组对存在原型已有安装接触。
- 对候选AA00–AE00的1个内核失败对、原型AA00–AE00的4个失败对和原型AA00–AJ00的1个失败对执行SolidWorks官方干涉检查回退，均获得明确结果。
- 对低层布尔法报告的AA00–AE00三组、AA00–AJ00一组疑似新增叶组件接触再次执行官方检查，4/4均为无干涉，确认为低层算法误报。
- 最终覆盖45/45顶层对象对：22对AABB分离、23对有效精检、未解析对0、候选相对原型新增干涉0；状态为`PASSED_FULL_STATIC_GEOMETRY_NO_NEW_INTERFERENCE`。
- 项目03档案升级至`2026-10-01.1`；7个自然语言有序装配步骤全部具备静态CAD证据，多项目审计将项目03加入`orderedCadPipelineReadyProjects`。
- 新增官方复核请求构建器、静态碰撞闭环汇总器及回退正/负结果处理；项目03及相关定向回归31/31通过，前端TypeScript/Vite生产构建通过。
- 后端完整回归475通过、4失败；失败均为项目02既有历史warm-start种子与后续工艺硬约束不兼容，以及旧预览指标30/32断言，不涉及本轮项目03路径，作为独立测试债务保留。
- 最终实体：`demo/semantic_ports/project03_full_hybrid_static_v1/project03_full_10_object_hybrid_static_v1.SLDASM`；闭环：`demo/semantic_ports/project03_full_hybrid_static_v1/interference_closure.json`。
- 闭环登记18个装配体/位姿/精检/原型基线/官方复核文件的SHA-256；复用审计18/18通过，后续输入未变化时可跳过Replay和约103分钟B-rep。审计：`demo/semantic_ports/project03_full_hybrid_static_v1/closure_reuse_audit.json`。

功能修改意义：把“宏观位姿正确但内部柔性状态错误”的阻塞转化为可靠的混合静态快照，并以AABB、叶级B-rep、原型基线和官方复核四层证据完成项目03静态整链；同时继续把动态运动、原始配合语义和生产放行留在独立门禁中。

## 2026-10-01：项目01 SS00与FF00跨项目增量CAD闭环

- SS00：恢复JJ00/HL00固定环境，以1面+2孔完成独立SS00插入；3/3配合、完全约束、保存重开通过，姿态误差`9.21e-15`。
- SS00计时：固定环境重建259.192秒，增量插入48.454秒，姿态与AABB捕获后总计量320.336秒。
- JJ00固定环境首次全叶B-rep超过增量预算并中止；未产生伪精检证据。本步用哈希+姿态等价只声明相对原型无新增干涉。
- FF00工作包发现正式模组和ECN归档内同名零件；改为按顶层模组子树限定面端点文件检索。
- FF00第一次插入因重复提交旧SS00配合被保护性拒绝；改为新补丁只包含FF00的3条驱动配合，旧配合保留在源检查点。
- FF00修复后79.764秒完成静态插入，6/6顶层关系获得分类验收，状态`PROJECT01_FF00_STATIC_INCREMENT_CLOSED_DYNAMIC_BLOCKED`。
- 阻塞：FF00 `home/work/flip-25deg`三状态、25度扫掠体碰撞、厂商孔距与安装基准确认尚未完成。
- 定向回归：SS00/FF00工作包与闭环14/14通过；项目01版本化计划显示SS00可执行，FF00静态已验证但动态仍阻断整链。

功能修改意义：将项目03的可解释增量CAD流程真实迁移至项目01，并在迁移过程中新增模组子树版本选择和“新驱动配合/旧上下文配合”边界，防止误选历史零件和重复施加配合。

## 2026-10-01：项目01 SM00静态机械+光学Demo闭环

- 新增可复用的项目01三基准工作包编译器，后续BD00/GJ00/LM00可复用同一路径。
- SM00以1面+2孔、22 mm原型基准插入；63.693秒完成3/3配合、完全约束、保存重开。
- 5对象姿态误差`9.21e-15`，10/10对静态分类完成。
- 光学Demo门禁验证两台SR-X100、载具/产品扫码角色、光轴、移动轴和200 mm显式CAD光束；不宣称厂商工作距离已确认。
- 闭环状态`PROJECT01_SM00_STATIC_OPTICAL_DEMO_CLOSED`，本步定向测试4/4通过。
- 项目01自然语言计划现有SS00、SM00两个可执行步骤；FF00静态已通过但动态债务仍使整链保持关闭。

功能修改意义：把机械安装成功与光学工艺可用性拆成两个独立证据门禁；既允许静态Demo继续累计装配，又不把原型光束几何误报为厂商认证参数。

## 2026-10-01：项目01 GN00多基座增量与服务目标闭环

- 首次实现一个新模组同时从两个已有模组取基准：JJ00支承面+定位孔，SS00平行防转面。
- 2组语义连接编译为3条驱动配合；75.986秒完成独立GN00插入、完全约束、保存重开。
- 6对象位姿误差`5.33e-14`，15/15对静态分类完成。
- 清洁、称重、双排胶杯、硬度测试台5个服务目标通过粗布局验收；维护包络和插入深度仍是显式阻塞。
- 状态`PROJECT01_GN00_STATIC_SERVICE_DEMO_CLOSED`；本阶段工作包/闭环测试4/4通过。

功能修改意义：把“两个旧模组共同定位一个新模组”编译为可审核的多连接语义补丁，并将机械定位、服务目标和维护包络拆成独立门禁。

## 2026-10-01：项目01 BD00校准模组增量闭环

- 以1面+2孔、50 mm原型孔距插入BD00，78.649秒完成3/3配合、完全约束和保存重开。
- 7对象姿态误差`5.33e-14`，21/21对静态分类完成。
- 校准目标绑定BD00棱镜端目标堆栈；静态Demo通过，但设计基准、插入深度和精度公差未确认。
- 状态`PROJECT01_BD00_STATIC_CALIBRATION_DEMO_CLOSED`；本阶段工作包/闭环测试4/4通过。

功能修改意义：将“模组装到正确位置”与“工艺校准点选对实体”分层验证，避免位姿正确但服务目标语义错误。

## 2026-10-01：项目01 GJ00供胶模组静态增量闭环

- GJ00以1面+2孔、220 mm原型孔距定位；66.716秒完成增量插入和保存重开。
- 8对象姿态误差`5.33e-14`，28/28对静态分类完成。
- 刚性供胶本体静态Demo通过；软管中心线、弯曲半径、连续扫掠和维护路径未登记，不允许生产放行。
- 状态`PROJECT01_GJ00_STATIC_RIGID_DEMO_CLOSED_HOSE_BLOCKED`；工作包/闭环测试4/4通过。

功能修改意义：明确区分“供胶组件安装位置正确”与“柔性软管在全行程可用”，避免用刚体装配证据代替软管动态证据。

## 2026-10-01：项目01 LM00/ZZ00诊断与10功能模组静态闭环

- 编译LM00→JJ00和ZZ00→LM00真实配合工作包；面端点和持久引用正确，但多轮保存重开均暴露柔性内部行程漂移。v6虽3/3配合、参数一致、完全约束，LM00上下文仍漂移`0.656135801`，因此动态路线被硬拒绝。
- 扩展执行器以登记内部状态锚点和求解状态；18/18 C#定向测试通过并发布`publish-current6`。实验进一步证明：顶层完全约束不代表柔性子树工况唯一。
- 新增父上下文静态子集工具；从原型只保留LM00/ZZ00并保存重开。LM00 202/202、ZZ00 156/156组件在`1e-7`阈值内稳定。
- 将该静态子集增量插入此前8模组检查点，生成9个CAD顶层节点、10个功能模组的最终静态实体；插入`136.113 s`，保存重开通过。
- 36组顶层组合完成分层检查：17组AABB排除、15组复用既有上下文、4组新增相关叶级B-rep。BD00/FF00零干涉；GN00/JJ00交叠与原型基线完全相同，新增干涉0。
- 最终状态`PROJECT01_FULL_10_FUNCTIONAL_OBJECT_STATIC_DEMO_CLOSED`；不宣称绝对零干涉，不宣称动态或生产闭环。
- 项目01档案升级`2026-10-01.7`，自然语言7步静态计划实现缺口降为0；项目01、02、03均进入有序静态CAD链就绪列表。
- 实体：`demo/semantic_ports/project01_final_static_snapshot_increment_v1/project01_full_10_functional_object_static_v1.SLDASM`；闭环：`demo/semantic_ports/project01_final_static_snapshot_increment_v1/project01_full_static_closure.json`。

问题与阻塞：

- LM00/ZZ00独立柔性运动语义未恢复；需要内部运动配合、命名工况或权威行程限位。
- FF00 25°翻转扫掠未验证；GJ00软管连续扫掠与维护路径未验证。
- GN00–ZZ00、JJ00–LM00存在原型既有实体交叠，当前只证明未新增，仍需机械工程师分类是否为工艺进入、安装嵌入或CAD建模余量。
- 大型原型首次打开约78秒，JJ00–LM00单组原型B-rep总流程约345秒；后续应优先复用SHA-256绑定的精检缓存。

功能修改意义：把项目01从6步累计静态检查点推进为完整10功能模组实体闭环，并以真实失败证据明确静态快照与动态运动学的边界，避免将不充分的配合语义误报为生产可用。

## 2026-10-01：项目05工艺参数清零与结构占用续跑门禁

- 建立项目05版本化9对象、11活动主模组、8步自然语言装配档案；预演与依赖检查可用，8个CAD动作仍明确缺失。
- F000/M000叶体恢复扫码站和CCD双工位粗光学几何；G000/N000/P000恢复标定、称重、双清洁、双排胶共6个服务目标。
- 修正活动实例计数：N000-3和P000-1为抑制变体，N000/P000各只计一个活动顶层模组；P000内部自带两个排胶杯。
- 双阀公共平面行程使用B000的950L/800L轴证据、B000中心及P000双杯130 mm间距求交；2个工作位和6个服务点全部通过，最小余量2.87 mm，生产Z行程仍关闭。
- 操作侧`+V`及G/N/P剩余空间通过粗几何验证；胶供给显式排除在九对象Top-3之外并保留生产软管债务。
- K/F/M/G/N/P共6个模组升级为完整叶级多包围盒；A/E/D/B/Z仍为顶层占位，故`moduleOccupancy`是唯一粗求解阻塞。
- 默认及隔离实例两次B000捕获分别等待591秒和120秒，均阻塞于MCP initialize且未启动CAD捕获；仅停止客户端，SolidWorks主进程保持响应。
- 生成可恢复工作包`project05_structural_capture_plan.json`，固定续跑顺序A000→E000→D000→B000→Z000；项目05回归30/30通过，多项目审计已刷新。

问题与阻塞：

- 当前MCP初始化无法返回；需干净SolidWorks/MCP会话后才能补5个结构模组叶体。
- 11/11占用完成前不生成Top-3；8个项目05专属CAD动作和完整静态碰撞闭环尚未开始。
- 光学原点、条码面、Z行程、软件限位、维护扫掠和胶管路径仍是生产级债务，但不再阻塞粗静态参数准备。

功能修改意义：把项目05从“多项未知”收敛为一个可续跑的结构证据阻塞，并通过粗/生产双门禁避免用估计值冒充权威工程数据。

## 2026-10-01：项目05结构占用清零与Top-3展示闭环

- 安全清理无父进程残留MCP Hub并保留未保存SolidWorks主文档；完成A/E/D/B/Z真实叶体捕获，项目05结构覆盖达到11/11。
- A000 2个实体盒失败改由面盒并集回退；复测320叶/1412体、0失败，回退来源显式记录。
- 建立两层占用：4084个叶实体盒负责15组严格硬门禁，粗子树盒负责13组条件B-rep预筛和8组安装接触复核。
- 新增项目05确定性Top-3求解器与展示页入口。2197个组合中348个可行；3个候选均通过工艺、空间和交互3/3。
- 修复通用命令行计时产物只报路径不落盘的问题；项目05最近一次求解与持久化1.330秒。
- 定向Python回归7/7、前端生产构建通过；桥接定向.NET回归51/51通过。

问题与阻塞：候选尚未唯一批准；项目05 8步CAD动作、保存重开、条件B-rep和完整静态碰撞闭环待实现。当前参数仍来自项目05原型标定，不能宣称生产级去原型。

功能修改意义：只有一个经快速展示确认的候选会进入SolidWorks，降低重复Replay和全量B-rep成本，同时保持每个粗略或回退证据可追踪。

## 2026-10-01：项目05真实11模组静态闭环

- 选定约束解rank 1并展开9对象为11个活动模组，完成9阶段累计SolidWorks建装、另存、关闭、重开和审计；最终文件为`demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_cumulative.SLDASM`。
- 修复四项现场缺陷：SaveAs同标题重复打开、CloseDoc路径不可靠、顶层粗框与叶实体口径混比、原型实例后缀在新装配体失效。
- 重新发布含面盒回退的MCP，A000现场复测320叶/1412体/0失败；最终11模组叶实体范围审计全部通过。
- 15组严格叶AABB对零命中；13类条件关系预筛后8个组件对执行B-rep。原型既有D/K、D/F、B/M接触均无新增干涉，其余5对零干涉，装配体检查前后哈希一致。
- 闭环`project05_static_collision_release_closure.json`为`success=true`；定向回归10/10通过。成功路径累计2410.929秒（40.182分钟），逐阶段和逐工具计时已落盘。
- 桥接层Release构建0错误；全量.NET测试长时间无输出后仅中止测试进程，保留为测试基础设施性能债务。

功能修改意义：项目05已从“可展示Top-3”推进为“唯一选案可真实建装并获得分层碰撞证据”，但仍只属于原型标定的粗静态Demo，未宣称生产放行或跨项目去原型。

## 2026-10-01：项目05自然语言持久化作业闭环

- 通用化作业协议、作业ID和项目目录路由；项目05正式接入已验证CAD工件回放。
- 增加SLDASM与阶段证据JSON双存在硬门禁，以及累计工件连续前缀限制。
- 前端增加项目02/05选择、项目05作业创建和逐步状态展示；项目05现场CAD保持禁用。
- 后端回归56/56，前端构建通过。
- 真实工件链三场景通过：8步全链成功、D000暂停后恢复、K000失败回滚至D000后恢复。
- 证据：`demo/semantic_ports/project05_ordered_jobs/functional_closure/latest.json`。

问题与阻塞：项目05现场CAD动作适配器和任意子序列尚未实现；本轮是证据回放，不是重新运行SolidWorks；生产动态参数仍不完整。

功能修改意义：把自然语言计划、真实CAD阶段工件和可恢复状态机连成了可审计闭环，并明确区分快速回放与现场CAD执行。

## 2026-10-01：跨项目回放与项目05单步现场适配器

- 为项目01/03补齐逐步累计工件索引和SHA-256；项目01、03、05共22步真实历史工件回放全部成功。
- 展示页开放01/02/03/05选择；除项目02外仍禁用现场CAD。
- 项目05构建器支持单阶段窗口，新增持久化任务单步动作适配器；相关测试23/23通过。
- D000现场单阶段试运行205.494秒成功，顶层、位姿、叶实体和保存重开门禁通过。

问题与阻塞：K000至B000尚未通过新适配器整链现场实证和逐步碰撞门禁；项目05`live_cad`未开放。跨项目报告：`demo/semantic_ports/cross_project_artifact_replay/latest.json`。

功能修改意义：从跨项目“计划可解释”推进为“历史工件可逐步回放”，并首次证明项目05能由通用任务边界驱动一个真实新CAD阶段。

## 2026-10-01：项目05全动作现场适配器闭环与发布

- 泛化碰撞门禁的项目令牌识别和多成员步骤；B000步骤同时处理B000+Z000，安装接触按A000/E000和B000/Z000接口语义分类。
- B-rep缓存升级为`pair-brep-evidence-cache/v3`，键绑定源哈希、配置、相对位姿、策略、基线、检查器和证据，项目05现场运行后共19项。
- 从已验证D000检查点运行K/F/M/G/N/P/B七步现场长链，7/7成功，最终实体为`step08_B000_cumulative.SLDASM`，全部碰撞门禁未解决对为0。
- D000试点205.494秒，接续作业2638.693秒，总计2844.187秒（47.403分钟）；K/F/M/G/N/P/B分别耗时282.205/376.361/308.489/392.774/344.623/433.117/498.439秒。
- 新增`project05_live_adapter_closure.py`和闭环脚本，机器状态为`PROJECT05_LIVE_ADAPTER_FULL_ACTION_CHAIN_CLOSED_WITH_D000_SEED_HANDOFF`；明确`singleUninterruptedJob=false`、`productionReady=false`。
- API/UI开放项目05`live_cad`，但由上述闭环硬门禁控制；证据不完整则422拒绝。项目档案升级为`2026-10-01.4`并登记最终实体和闭环。
- 回归：发布门禁、动作适配器、碰撞门禁、缓存、状态机和项目档案56/56通过；前端生产构建通过。

问题与阻塞：当前是D000试点加七步接续，不是一次从A000开始的不间断作业；动态行程、软管、维护空间和精确光学参数仍未验收；项目01/03尚无现场动作适配器。

功能修改意义：自然语言命令现在可以受控触发项目05全部真实CAD动作，且每一步都绑定实体、保存重开、碰撞和计时证据；系统不会因为代码路径存在就绕过发布证据或误报生产就绪。

## 2026-10-01：项目05未播种不间断现场作业闭环

- 新增`run_project05_live_adapter_full.py`，创建不带外部检查点的8步现场作业，从版本化A000基座连续生成D/K/F/M/G/N/P/B。
- 作业`project05-job-8accc910d933`八步均一次成功，检查点输入输出连续，无回滚、错误或缺失证据；最终SLDASM约110.3 MB。
- 碰撞门禁逐步检查2/3/4/5/6/7/8/19组关系，全部接受且未解决对为0；17次版本化缓存命中，条件B-rep执行时间为0。
- 基线检索增加模组令牌兜底，实例后缀变化不再改变基线策略或使缓存漏命中；相关回归35/35通过。
- 发布闭环新增不间断检查点连续性审计，升级为`PROJECT05_LIVE_ADAPTER_UNINTERRUPTED_FULL_CHAIN_CLOSED`。
- 修复计时报告对“完整执行结果+嵌套阶段结果”的重复计数；新增通用计时报告脚本。总耗时2588.649秒，CAD动作2086.744秒，碰撞门禁498.098秒，编排/未归因约3.807秒。
- 项目档案升级为`2026-10-01.5`，登记最新实体、不间断摘要和计时报告。

问题与阻塞：生产动态证据和权威参数未完成；项目01/03尚无现场动作适配器；每步约62秒的新鲜位姿/AABB捕获是下一性能优化重点。

功能修改意义：关闭了“D000来自外部种子”的最后静态现场主链缺口，并用可审计计时证明缓存节省了条件B-rep成本，同时没有绕过新鲜几何门禁。

## 2026-10-01：项目03 AE00→AD00不间断现场前缀闭环

- 扩展项目03动作适配器，支持AE00传输模组及AD00举升翻转定位模组；AD00必须消费前一已提交检查点。
- 真实作业`project03-job-592fc47f762c`两步一次成功，无回滚；两步各创建3个驱动配合，目标完全约束，保存重开及配合参数复核通过。
- 碰撞门禁：AE00检查2对，AD00检查3对；AD00执行条件B-rep约89.430秒，未解决对为0。
- 新增两步闭包生成器和脚本，校验顺序、单次尝试、检查点连续性、动作证据、门禁证据、清单及最终装配体。
- API/UI发布边界升级为AE00或AE00→AD00连续前缀；AI00及后续请求保持拒绝。
- 整链476.967秒：CAD动作262.444秒，碰撞门禁213.856秒。后端定向回归41/41、前端生产构建通过。

问题与阻塞：AD00的25度动态扫掠未闭环；项目03安装基准仍来自原型；AI00光学目标和AE00/AI00既有干涉基线需在第三步现场动作前复核。

功能修改意义：首次证明项目03可沿统一持久化任务框架真实生成累计实体，并由机器证据控制发布边界；跨项目通用化不再停留于历史工件回放。

## 2026-10-01：项目03 AI00第三步真实CAD闭环

- 扩展项目03动作适配器和现场脚本，运行AE00→AD00→AI00单一持久化作业；三步一次提交、无回滚。
- AI00用3条驱动配合定位，以2条距离作为重开后的只验证关系；目标完全约束且验证误差低于`2e-14 m`。
- AI00局部门禁检查4对，原型AE00/AI00基线和零干涉策略均通过，未解决对为0。
- 新增三步闭包，API/UI只允许已实证连续前缀。总耗时768.742秒；后端44/44、前端构建通过。

问题与阻塞：扫描光学数据仍为代理；AG00只靠支承面+单孔会留下绕孔轴自由度，现有历史方案使用显式原型残差锚点。

功能修改意义：现场链已覆盖扫描语义和只验证关系，下一阶段可专注处理多功能模组的欠约束与维护包络。

## 2026-10-01：项目03全静态动作分段闭环

- 四步不间断作业AE/AD/AI/AG成功；AG两配合+显式原型残差锚点完全约束，5对局部门禁通过。
- AH尾部成功：3配合、6对关系、286.953秒；AJ尾部成功：3配合、7对关系、199.092秒。
- AB尾部封装为两动作原子步骤：AB00真实配合插入+AC00完整静态混合快照；两动作均重开通过，17对关系无未解决项，589.240秒。
- 新增分段全动作闭包，验证跨作业检查点连续性、动作证据数量、门禁、清单和最终实体。
- 项目档案升级到`2026-10-01.6`并登记最终实体、闭包和各段计时。

问题与阻塞：`singleUninterruptedJob=false`；AG/AB仍依赖原型残差锚点；AC00不保留内部运动语义；动态工况和权威参数未闭环。API/UI维持四步前缀，不提前开放七步。

功能修改意义：项目03自然语言顺序中的全部动作已得到真实CAD证据，但发布语义仍严格区分“分段覆盖”与“单次完整生成”。

## 2026-10-01：项目03单一持久化七步整链、恢复与45对独立审计

- 运行无外部种子的七步作业`project03-job-acc1cd320f35`；AE/AD/AI/AG/AH/AJ各1次成功，AB首次在保存后重开阶段失败并回滚到AJ检查点。
- 定位根因为SolidWorks桥接层未可靠关闭另存后的同标题文档；`AssemblyContextIncrementalInsert`新增按绝对路径关闭、同标题残留清理和重开前验证，并将修复后的桥接程序发布到`artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe`。
- 新增确定性恢复脚本，从最后成功检查点只重试AB；AB第2次成功，最终10对象实体、动作证据、检查点和清单完整。
- 新增正式全链闭包，验证单一持久化作业、连续检查点、每动作配合/语义/重开结果、局部门禁、故障恢复和最终实体。
- 对最终实体重新捕获位姿并独立枚举45对；22对严格AABB分离，23对命中与当前输入指纹一致的版本化精检证据，45/45通过、未解决对0。
- 计时审计补充每次尝试和已恢复失败耗时：总1498.977秒，成功CAD动作997.721秒，逐步门禁434.791秒，失败尝试61.055秒，编排残差1.812秒，未归因3.598秒。
- 项目03档案升级至`2026-10-01.7`，完整七步API/UI发布；桥接58/58、后端目标回归37/37及前端生产构建通过。

问题与阻塞：AG/AB仍依赖原型残差锚点；AC00只保留静态几何；AD00扫掠、龙门权威行程、光学、软管和维护空间尚未完成动态验收。

功能修改意义：项目03首次形成“自然语言计划—真实CAD逐步执行—故障回滚恢复—最终全对象碰撞审计—证据发布”的完整静态闭环，后续可集中解决去原型参数和动态工况，不再重复静态整链。

## 2026-10-01：AG00/AB00运行时原型顶层位姿依赖抽离

- 新增`project03_calibrated_parameters_v1.json`及校验器，将AG00防转残差和AB00 Width1替代姿态登记为带哈希、来源、适用自由度和替换要求的临时参数。
- 工作包编译器支持显式参数注入；新增消融器将源图AG00/AB00顶层位姿扰动到错误位置，确认编译锚点仍保持不变。
- 生成独立`calibrated_v2`工作包，并在真实CAD中从AI00、AJ00检查点分别插入AG00、AB00。AG00 2配合通过，耗时127.011秒；AB00 1驱动+40 mm验证通过，耗时134.137秒。
- 新增正式去运行时依赖闭包和负向回归；阶段测试11/11通过。项目03档案升级至`2026-10-01.8`。

问题与阻塞：临时参数仍源自原型，未成为厂商权威基准；AC00静态快照、动态扫掠、行程、光学、软管及维护空间未解决。

功能修改意义：原型依赖由执行期隐藏行为变为数据层显式接口，既能稳定复现实验，也能在获得真实基准后单点替换并触发受影响证据重算。

## 2026-10-01：项目03 AD00真实配置三状态验证

- 桥接层新增指定文档配置清单、实例Transform设置和引用配置设置；AD20确认包含`Default/0度/25度`。
- 完成左右`0/0`、`25/0`、`0/25`三态实体装配与8对/状态的分级碰撞检查；三态耗时约358.05、355.39、345.84秒。
- AA00、AB00、AI00全部通过。AE00隔离结果有接触，但原型基线也存在AD20–AE00接触；因柔性父上下文缺失，自动判读为“需完整上下文基线复核”，生产门禁保持关闭。
- 新增`project03_dynamic_configuration_assessment.py`及测试，档案升级到`2026-10-01.9`；长任务脚本升级为每个CAD调用后写入进度和耗时。

问题与阻塞：必须在完整十对象装配上下文中复现`0°/0°`叶级接触身份，再检查左右25°状态是否出现新实体对；之后仍需连续扫掠和厂商限位。

功能修改意义：取得了真实CAD配置证据，并建立了隔离状态与完整上下文门禁的分层，避免将柔性装配的上下文差异误报为新增干涉。

## 2026-10-01：AD00三离散状态完整上下文闭环

- 新增逐级副本构造、干净进程恢复、选择基线叶级多重集合比较和三状态闭包生成脚本。
- 未替换最终十对象装配的AD00–AE00直接基线为1对；0/0精确复现，25/0和0/25均无新增叶零件对。
- 修复历史I盘引用导致的实例路径误判；识别并接受`0度-_flexibleN`为0度柔性派生配置；B-rep完成后的文档关闭失败降级为清理警告。
- 进度清单采用原子替换，避免并发监控读取半写JSON。
- 正式状态`PASSED_PROJECT03_AD00_THREE_DISCRETE_FULL_CONTEXT_STATES`，档案升级到`2026-10-01.10`；目标回归14/14通过。

问题与阻塞：连续0至25度扫掠、厂商轴限位、速度和安全间隙未验证；当前结果仅放行三个离散端点，不放行生产动态动作。

功能修改意义：完成了真实CAD配置到整机上下文实体证据的闭环，并把剩余工作严格收敛到连续运动安全。

## 2026-10-01：连续扫掠代理与全仓回归

- 生成AD00 25°保守扫掠，1°步长、20 mm不确定性；7项宽相候选涉及AA/AB/AE/AI。
- 修正项目档案的扫掠文件路径；连续精检仍因缺少中间配置和权威转轴而阻塞。
- 全仓回归暴露并修复4项项目02陈旧测试夹具，不改生产约束；最终后端587项与3 subtests全部通过。
- 前端`npm.cmd run build`通过；桥接层Document/Assembly/AppBootstrapper目标测试84/84通过，最新程序已发布到`artifacts/solidworks-mcp-current`。

功能修改意义：确认本轮动态功能与既有项目01/02/05代码兼容，并将下一开发点收敛为可审计的中间角度运动适配器。
## 2026-10-02 — Project03 AD20 context-rebased dynamic collision closure

- Added nested total-transform diagnostics, arbitrary-depth solving-state control, lightweight-component resolution, and fixed duplicated nested hierarchy paths.
- Added rigid transform composition/relative/rebase helpers and six context-rebased AD20 snapshots at 0/5/10/15/20/25 degrees.
- Rebuilt every state through rigid AD10 parents into the final ten-object context, then independently reopened, remapped all expected leaf poses, and ran exact leaf-body B-rep checks.
- Superseded the old flexible three-state closure: its 0° and 25° full-context captures contained no moving leaves and were not valid dynamic evidence.
- Gate results: 0/5/10/15° passed with no new leaf-source interference pair; 20° failed with one new pair; 25° failed with two new pair classes and three new body-pair counts.
- First observed collision bracket is `(15°,20°]`; continuous path is not verified and production remains disabled.
- Aggregate evidence: `demo/semantic_ports/project03_ad20_context_rebased_dynamic_closure_v1.json`; recorded CAD evidence time 5870.410 seconds.
- Known instability: immediate reopen in the construction session can terminate SolidWorks; saved outputs were recovered and verified in clean processes. Vendor-authoritative motion/clearance data remain blocked.

Change significance: the dynamic release gate now rejects unsafe 20°/25° states using preserved rigid leaf poses and exact CAD evidence, instead of accepting a flexible-context false positive.

Regression closure: Python compile passed; rigid-transform tests 5/5; backend 592 passed plus 3 subtests; bridge Assembly/Document/AppBootstrapper tests 90/90.

## 2026-10-02 — Project03 natural-language dynamic preflight hard gate

- Added `project03_dynamic_release_gate.py` to parse and distinguish static assembly, discrete-pose validation, and continuous AD20 motion requests.
- Wired the evidence result into ordered-plan `safeToStartCad` and job creation; unsafe dynamic requests are rejected before SolidWorks is queued.
- Updated Project03 profile to `2026-10-02.1`, superseded the invalid flexible three-state artifact, and referenced the context-rebased six-state closure.
- Added an explainable frontend dynamic-gate card with collision bracket and evidence path.
- Persisted four command-level cases in `demo/semantic_ports/project03_dynamic_command_gate_demo_v1.json`: static allowed, 15° discrete allowed, 20° discrete rejected, 0→15° continuous rejected.
- Tests: focused 37/37, full backend 599 plus 3 subtests, frontend production build passed, bridge target tests remain 90/90.

Change significance: exact CAD collision evidence now controls whether a natural-language request may start an expensive CAD job; discrete samples can no longer be misrepresented as continuous-motion approval.

## 2026-10-02 — Project03 AD20 first-contact refinement

- Built and verified a rigid 16° full-context state; all 29 intended leaves mapped within `8.88e-16`, but exact B-rep reproduced the new AD20002/electrical-part interference.
- Stopped 17°–19° full-machine runs because 16° already bounds the full-state first observed collision to `(15°,16°]`.
- Added a two-leaf exact-B-rep refinement harness and sampled 15.0° through 16.0° at 0.1° increments in one SolidWorks session.
- The known pair is clear through 15.5° and collides from 15.6° onward; all 11 exact checks completed with zero kernel failures in 113.166 seconds.
- Updated the refined dynamic closure, Project03 profile `2026-10-02.2`, natural-language preflight evidence, and frontend explanation.

Change significance: repeated full-machine rebuilds are no longer required to localize this known collision; the local harness provides a fast structural-redesign loop while the whole-machine continuous gate remains correctly closed.

- Selector debugging was fail-closed: file-only identity matched 14 leaves, parent text in `Name` matched none, terminal `-7` matched two station branches, and the final `HierarchyPath` parent branch plus terminal instance uniquely selected the B-rep-reported leaf. No failed attempt reached mutation of source files.
- Final regression: backend 600 passed plus 3 subtests; bridge target suite 90/90; frontend production build passed. Aggregate recorded dynamic evidence time is 6933.920 seconds.

## 2026-10-02 — Unified cross-project release contract

- Added `assembly-release-contract/v1` as the single source of truth for static demo, live CAD, dynamic evidence, parameter authority, and production release.
- Added a read-only API and frontend card; all layers now show why a project is allowed or blocked instead of inferring production readiness from a static assembly result.
- Job creation now consumes the same contract and rejects unreleased replay/live-CAD modes before queueing SolidWorks work.
- Added `scripts/build_multi_project_assembly_release_contract.py` and persisted `demo/layout_previews/multi_project_assembly_release_contract_v1.json`.
- Current portfolio result: Project01/02/03/05 static demos are allowed; Project02/03/05 live CAD is explicitly allowed; no project is production-ready.
- Project03 preserves the full-state `(15°,16°]` collision bracket and pair-local `(15.5°,15.6°]` bracket while keeping continuous-motion release closed.
- Project06 fails closed because no versioned project assembly profile exists.
- Regression closure: focused 25/25, full backend 604 passed plus 3 subtests, frontend production build passed, and Python compilation passed.

Change significance: natural-language planning, API consumers, the UI, and portfolio audits now share one release decision model; adding evidence changes a versioned contract rather than relying on manual interpretation.

## 2026-10-02 — Project01 full live-CAD chain and controlled-resume closure

- Added the Project01 live runner for `SS00→FF00→SM00→GN00→BD00→GJ00→LM00`, a durable resume script, a v2 release closure, and API prefix enforcement.
- The first real run committed five steps and failed closed at GJ00. The uncommitted artifact was quarantined and the BD00 checkpoint remained authoritative.
- Fixed collision-gate result handling: a unique complete B-rep batch is now parsed even when the capture command returns non-zero for a real rejected interference; missing evidence and negative evidence are no longer conflated.
- Captured an independent Project01 prototype baseline for GJ00–JJ00. Candidate and prototype contain the same nine normalized interfering leaf pairs, with zero additions; release therefore uses `noNewInterferenceOverAcceptedBaseline`, not an unconditional contact whitelist.
- Resumed the same durable job from BD00. GJ00 passed on attempt 2, LM00 passed four strict-separation and four conditional-B-rep pairs, and all seven checkpoints committed.
- Final assembly: `demo/semantic_ports/project01_live_adapter_full_jobs/project01-job-87ef17fa93e0/cad-working/step-07-lm00-attempt1/step07_project01_full_10_functional_object_static.SLDASM`.
- Closure semantics are explicit: `singleDurableJob=true`, `singleUninterruptedJob=false`, `controlledResume=true`; failed output was never accepted.
- Added a per-attempt timing report. Total execution was 6040.783 s, wall clock 6559.862 s, recorded CAD actions 1286.494 s, and recorded exact B-rep batches 4239.588 s. The LM00 final gate alone used 1455.174 s.
- Updated Project01 profile to `2026-10-02.1`, enabled released live-CAD continuous prefixes in the API/UI, and regenerated the cross-project release contract. Project01/02/03/05 now allow static and released live CAD; none is production-ready.
- Regression: focused 39/39, timing-report 1/1, backend 612 plus 3 subtests, frontend production build, and Python compilation passed.

Change significance: Project01 now has a real, explainable, resumable CAD execution chain instead of static-artifact replay only. Remaining work is explicitly performance, dynamic motion, and parameter-authority closure—not basic incremental assembly execution.

## 2026-10-02 — Project01 live pair-cache reuse audit

- Recaptured nine top-level poses from the saved final assembly in SolidWorks; fresh capture took 86.705 s.
- Re-evaluated the LM00/ZZ00 final gate against the versioned pair cache: four pairs passed strict AABB separation, four matched exact B-rep fingerprints, and no pair remained unresolved.
- Cache evaluation took 0.070 s; total fresh-pose reuse gate took 86.775 s versus 1519.424 s for the first exact gate, a 94.289% reduction without rerunning B-rep.
- Profile advanced to `2026-10-02.2` and now references the persisted cache-reuse audit.

Change significance: repeated validation of an unchanged CAD result is now demonstrably cheap, while any source hash, relative pose, policy, or baseline change still invalidates the fingerprint and fails back to exact B-rep.

## 2026-10-09 — Global module catalog and semantic assembly context MVP

- Added a deterministic cross-project catalog for Project01/02/03/05: 34 CAD definitions, 52 semantic ports, 28 templates, and 50 compatibility records. Project06 fails explicitly because its profile is missing.
- Global identity is based on declared CAD component-name sets. Project tokens, labels, and functional categories remain aliases/provenance and cannot silently merge distinct CAD modules.
- Added endpoint-role portability evidence and template-specific portability, so a read-only unused slot endpoint does not block an otherwise recoverable installation template.
- Added versioned assembly contexts, natural-language module grounding, compatibility selection, immutable preview digests, confirmed graph-patch commits, and revision history.
- Added API routes and a frontend workbench for global search and incremental graph assembly.
- Added a global execution-manifest compiler that maps committed connections back to legacy port IDs, template IDs, endpoint catalogs, and base graph candidates without launching CAD.
- Closed a three-command graph demo for A600→A800→A180 with three instances and two semantic connections.
- Collision gate development was intentionally excluded by user scope. Every result states `collisionAssessment.status=not_evaluated`; no CAD or production safety claim is made.
- Evidence: `demo/global_assembly_catalog/v1/`, `demo/global_assembly_contexts/global-nl-demo-v1.json`, and `docs/global_module_semantic_ports-CN.md`.
- Tests: new 9/9, related backend 23/23, full backend 621 plus 3 subtests, Python compilation, API function smoke flow, and frontend production build passed.

Change significance: free composition now has a global, auditable intermediate representation. Missing ports remain visible blockers instead of being hidden by project-specific hard-coded sequences or guessed geometry.

## 2026-10-09 — Project02 A200 and dual-T401 global semantic closure

- Registered A200 with the source coincident mate and two ordered Slot mates, including their `SlotConstraint` advanced options and persistent face evidence.
- Registered T401 occurrence 1 against A600 (`coincident + 60 mm distance`) and occurrence 2 against A200 (`59 mm distance`).
- Extended global contexts to honor profile-declared instance capacity: the shared T401 CAD definition accepts exactly two instances and rejects a third.
- Added existing-target grounding so an explicit T401 command mentioning A600 or A200 selects the intended compatible connection.
- Generated a four-instance evidence context and a three-step execution manifest; every step is ready for the existing project adapter.
- Collision evaluation and live SolidWorks execution remained out of scope. Project02 source-pose case anchors are retained and are not vendor datums.
- Regression: focused 7/7 and full backend 624 plus 3 subtests passed.

Change significance: Project02 no longer has global-port gaps for A200/T401, and the graph layer now supports one CAD definition instantiated twice against different existing modules without silently exceeding the declared design count.

## 2026-10-09 — Project05 global semantic port migration

- Migrated eight Project05 installed objects to A000-backed mechanical ports, producing sixteen new ports and eight connection templates.
- Preserved 21 complete basic relations as driving mate steps. One Width and three Slot relations lack advanced options in the exported v1.2 graph and are retained as evidence-only relations instead of guessed CAD operations.
- Added a nine-instance, eight-connection global graph chain and compiled all eight connections to ready project-adapter packets.
- Corrected instance-capacity semantics: definitions composed of multiple distinct component names are one composite context instance; only repeated use of the same CAD source (such as Project02 T401) consumes a declared multi-instance capacity.
- Global catalog now contains 34 definitions, 74 ports, 39 templates, and 61 compatibility rows. All loaded-project module definitions have at least one port; only the missing Project06 profile remains a catalog-level blocker.
- Live SolidWorks and collision evaluation were not run. Project05 source-pose anchors remain case evidence, and four advanced relations still require a richer export or engineer confirmation.

Change significance: port coverage is complete for every currently loaded project, so the next engineering bottleneck is cumulative checkpoint/CAD-runner orchestration rather than missing module interfaces.

## 2026-10-09 — Global graph to cumulative project-runner binding

- Added `global-project-adapter-plan/v1` to resolve a unique project, validate engineering order, expand true repeated-source instances, locate a verified base checkpoint, and bind cumulative steps to an existing project CAD runner without launching SolidWorks.
- Project05 now compiles to a ready eight-step durable plan seeded by the verified A000 checkpoint. A temporary durable store proved job creation and external checkpoint seeding.
- The Project02 A600/A200/T401 partial evidence chain fails closed before CAD and reports the six missing predecessors instead of incorrectly starting the A200 step.
- Added the complete Project02 ten-instance semantic chain. Nine connections compile successfully and bind to eight durable steps; the two T401 instances are grouped into the existing runner's single two-action T401 stage using closure evidence.
- Added a read-only API, CLI compiler, and frontend readiness card. Project02/05 contexts now use the canonical cross-project catalog digest so saved contexts remain reopenable by the workbench.
- Collision evaluation remains deferred by explicit user scope; no CAD or B-rep operation was executed.

Change significance: semantic connectivity is no longer conflated with executable mechanical order. Complete chains can reuse the durable checkpoint engine, while incomplete chains stop before costly or unsafe CAD work.

Regression closure: focused global adapter/graph tests 13/13, full backend 630 plus 3 subtests, API function smoke, frontend production build, Python compilation, and scoped diff checks passed.

## 2026-10-09 — Explicit prepare-only global adapter jobs

- Added a confirmed `project-adapter-jobs` endpoint that compiles the plan again, checks the unified release contract, creates an idempotent queued job, and seeds the verified base checkpoint without scheduling CAD.
- The frontend requires an explicit checkbox and labels the action as prepare-only. The response reports both `executionStarted=false` and `solidWorksStarted=false`.
- Integration tests drove a real global Project05 plan through the durable state machine with a fake runner: idempotent reuse, pause after D000, checkpoint resume, K000 failure quarantine, rollback to D000, and tail-only retry all passed.
- Collision evaluation remained deferred and no SolidWorks process was started.

Change significance: expensive CAD execution is now separated from planning and job preparation by an auditable user-confirmation boundary, while recovery behavior is proven against the actual global adapter plan shape.

Regression closure: prepare/recovery integration 5/5, full backend 632 plus 3 subtests, frontend production build, Python compilation, and scoped diff checks passed.

## 2026-10-09 — Digest-bound explicit start and validated prefixes

- Added `stepLimit` so a prepared global adapter job may contain a one-step or short validated prefix instead of forcing a full eight-step run.
- Added a separate start endpoint requiring confirmation, the current context digest, and the expected step count. It recompiles and compares the current prefix before scheduling.
- Start scheduling is idempotent through `startRequestedAt`; duplicate requests do not enqueue duplicate SolidWorks work.
- Added fail-closed handling for runner initialization errors before the step executor starts, preserving the verified base checkpoint as rollback evidence.
- The frontend now has separate prepare and start confirmations and defaults to a one-step proof. No background task was executed in this development cycle.

Change significance: live CAD can now be introduced incrementally under a version-bound two-phase commit instead of jumping directly from graph preview to a full machine build.

## 2026-10-09 — Global job monitoring and context-bound resume

- Added one-second frontend polling for explicitly started global adapter jobs, including per-step status, attempt count, checkpoint, error, final committed checkpoint, and rollback mode.
- Added pause and cancel controls plus a separately confirmed resume action.
- Added a global-context-specific resume endpoint that revalidates the context digest, expected step count, current adapter-plan prefix, live-CAD mode, and unified release contract before scheduling work.
- Resume now clears stale start markers while retaining committed steps and the last valid checkpoint; only failed, cancelled, or interrupted steps return to pending.
- The simulated runner-initialization failure test now closes the loop through the dedicated resume endpoint and proves one-time rescheduling from the A000 checkpoint.
- Background tasks were inspected but not executed, so SolidWorks remained stopped and collision evaluation remained deferred.

Change significance: the first live one-step proof can now be observed and recovered without bypassing the version-bound execution contract.

## 2026-10-09 — Project02 A600-to-A800 live one-step proof

- Prepared and explicitly started `project02-job-e6ffd79bb6e6` with `stepLimit=1`; no downstream module was scheduled.
- Seeded from the verified A600 checkpoint and inserted a fresh A800 from its independent source assembly.
- Recreated `重合35` and `宽度9`; both mates resolved through source-assembly persistent references and passed reopen verification, including advanced Width options.
- The output reopened with the target fully constrained and a clean mate solve.
- CAD action duration was 98.165 s and durable-job duration was 100.207 s. The largest phases were context open (30.476 s), insertion (31.505 s), and mate rebuild (16.165 s).
- The existing A600/A800 pair gate reused a versioned B-rep cache and passed in 1.673 s under `noNewInterferenceOverAcceptedBaseline`; no exact B-rep run was needed. This is not an absolute zero-interference claim.
- Committed checkpoint: `demo/semantic_ports/project02_ordered_jobs/project02-job-e6ffd79bb6e6/cad-working/step-01-a800-attempt1-action1.SLDASM`.
- The installation still uses a Project02 case-pose anchor for residual DOF closure and is not yet vendor-datum independent.

Change significance: the global semantic graph, digest-bound job control, existing Project02 CAD runner, checkpoint commit, and reopen verification have now completed one real end-to-end SolidWorks step.

## 2026-10-09 — Checkpoint continuation and Project02 A180 live proof

- Added `seedJobId` to prepare a new durable job from a succeeded job checkpoint instead of replaying the validated prefix.
- Continuation planning locates the checkpoint in the current full plan, selects only the following contiguous slice, marks the first continuation step as an external verified seed, and records the source job and start index.
- Start and resume revalidate the current plan slice, seed files, source job status, and exact checkpoint identity.
- Added a frontend action to prepare the next step from a successful job without starting CAD.
- `project02-job-b96f2dade86b` consumed the A800 checkpoint from `project02-job-e6ffd79bb6e6` and executed only A180.
- `重合34` and `距离24` were created and survived reopen verification; the target was fully constrained with a clean mate solve.
- CAD duration was 36.882 s and durable-job duration was 38.923 s. A180/A600 and A180/A800 both reused versioned `zeroInterference` B-rep cache entries; the gate completed in 1.733 s with no exact B-rep run.
- Latest cumulative assembly: `demo/semantic_ports/project02_ordered_jobs/project02-job-b96f2dade86b/cad-working/step-02-a180-attempt1-action1.SLDASM`.
- Regression closure: continuation-focused 18/18, full backend 633 plus 3 subtests, frontend production build, and Python compilation passed.

Change significance: cumulative assembly can now advance one module at a time across separate durable jobs without reconstructing previously accepted modules.

## 2026-10-09 — Project02 live pause boundary and resume proof

- Prepared `project02-job-2b64c336a17e` from the A180 checkpoint with exactly two steps: A700 then A300.
- Requested pause only after A700 entered `running`. The worker completed and committed A700, then stopped before A300 with A700 attempt count 1 and A300 attempt count 0.
- Context-bound resume revalidated the job and source checkpoint. A700 remained committed and was not rerun; A300 ran once and committed successfully.
- A700 CAD action was 44.355 s and its pair gate 1.967 s. A300 CAD action was 40.773 s and its pair gate 2.425 s. Aggregate executor time across both runs was 90.337 s.
- A300 created `距离19`, `距离20`, and `重合39`; reopen verification, full constraint, and clean mate solve passed.
- AABB separation or versioned B-rep cache resolved every checked pair; no exact B-rep run was needed. Baseline-relative cache policies remain distinct from absolute zero interference.
- A700 exposed a portability gap: zero top-level driving mates were requested, while a case anchor plus two leaf-pose anchors fixed the module. This is adequate for Project02 reproduction but not a vendor-datum-independent global port.
- Final cumulative assembly: `demo/semantic_ports/project02_ordered_jobs/project02-job-2b64c336a17e/cad-working/step-04-a300-attempt1-action1.SLDASM`.

Change significance: real SolidWorks execution now proves cooperative pause at a committed step boundary and context-bound resume without replaying the completed module.

## 2026-10-09 — Project02 A500 live continuation proof

- Prepared `project02-job-9e45097d2c39` from the A300 checkpoint with A500 as the only step; no prior module was replayed.
- Recreated `重合13`, `宽度4`, and `距离27`. A500 used no case-pose anchor and no leaf-pose anchor.
- Reopen verification, full constraint, and clean mate solve passed.
- CAD action duration was 40.136 s and durable-job duration was 42.368 s.
- Five pair checks completed in 1.994 s: two strict AABB separations and three versioned cache hits, with no exact B-rep run.
- The A500/A800 cache uses `noNewInterferenceOverAcceptedBaseline`; A500/A600 and A500/A700 use `zeroInterference`.
- Latest cumulative assembly: `demo/semantic_ports/project02_ordered_jobs/project02-job-9e45097d2c39/cad-working/step-05-a500-attempt1-action1.SLDASM`.

Change significance: the cumulative chain now includes a service module fully located by recoverable top-level mate semantics rather than a prototype pose anchor.

## 2026-10-09 — Development acceptance layers and collision-gate scheduling rule

- Added `docs/development_execution_rules-CN.md` as the repository-level execution rule for the current natural-language/semantic-assembly work.
- Separated `DEMO_ASSEMBLED_COLLISION_NOT_EVALUATED` from `ENGINEERING_STATIC_VALIDATED`. Natural-language resolution, semantic-port recovery, mate creation, save/reopen, and non-blocking CAD health are the mandatory Demo closure; AABB and conditional B-rep are an asynchronous engineering-verification layer.
- Documented when exact interference checks are mandatory, when they may be deferred, what they actually validate, and what they cannot prove about reach, optics, motion, maintenance, or process feasibility.
- Required fail-closed wording: an unchecked candidate is “collision not evaluated”; a baseline-relative pass is “no new interference over the accepted baseline”, never absolute zero interference.
- Linked the rule from the global semantic-port record and the continuation entry point. Existing long-running jobs may finish as evidence, but their automatic B-rep coupling is not the default design for future Demo workflows.

Change significance: expensive leaf-level geometry validation no longer defines whether the natural-language assembly feature itself is complete, while production-facing claims still retain an explicit, auditable engineering gate.

## 2026-10-09 — Collision-free status explicitly deprioritized

- Recorded the user's clarification that proving whether the candidate is interference-free is not a key problem in the current development stage.
- Set the active priority to natural-language intent resolution, global module identity, semantic-port selection, stable geometric endpoint recovery, real mate creation, cumulative save/reopen, rollback, and checkpoint continuation.
- Collision status must still be reported truthfully, but an unevaluated or separately pending collision audit does not block completion of the current Demo assembly capability.
- Collision becomes a current blocker only when explicitly requested, required for engineering release, or when a suspected penetration prevents the assembly step itself from being meaningfully completed.

Change significance: prevents the project from spending its main iteration budget on long exact B-rep runs before the semantic assembly workflow itself is complete.

## 2026-10-09 — Demo assembly checkpoint separated from engineering collision checkpoint

- Added explicit `demo` and `engineering` validation profiles to durable live-CAD jobs. The default demo profile commits only after real mate execution, save/reopen verification, target constraint-state acceptance, and evidence persistence; it does not invoke B-rep.
- Added independent `assemblyStatus`, `collisionStatus`, `demoCheckpoint`, and `engineeringCheckpoint` fields while retaining `lastCommittedCheckpoint` for continuation compatibility.
- Updated Project01/02/03/05 CAD runners to share the same validation-profile behavior, and updated the evidence manifest to record the validation evidence kind.
- Updated the frontend to select a validation profile and display assembly and collision states independently.
- Extended `run_project02_live_tail.py` with a validation-profile switch.
- Real Project02 job `project02-job-635438e6d96f` resumed from the accepted A100 checkpoint and executed only A200 plus the two-action T401 stage. It succeeded in 162.979 seconds (A200 66.580 s, T401 96.110 s), produced complete evidence, and ended as `assembled / collision_not_evaluated`.
- Final demo assembly: `demo/semantic_ports/project02_ordered_jobs/project02-job-635438e6d96f/cad-working/tail-02-t401-attempt1-action2.SLDASM`.
- Focused backend regression passed 40/40; complete backend regression passed 641 tests plus 3 subtests; frontend TypeScript/Vite production build passed.

Change significance: the natural-language CAD chain can now produce an auditable ten-object assembly without synchronously paying the leaf-level collision cost; exact interference verification remains available as a separately identified engineering concern.

## 2026-10-09 — Independent engineering validation of immutable Demo checkpoints

- Added a durable engineering-validation job type bound to the exact path, byte count, and SHA-256 of a successful Demo checkpoint.
- The validator checks file identity before and after geometry analysis, performs no mate creation or component movement, and never quarantines the source Demo artifact.
- A rejection leaves the source assembly job succeeded and preserves its Demo checkpoint; only a passed validation creates an engineering checkpoint.
- Added confirmed create/status APIs, frontend polling, evidence display, and a Project02 CLI runner.
- Real validation `project02-engineering-validation-af30557143d1` checked the ten-object Demo assembly in 301.067 seconds. All 45 pairs were accepted under the configured static policies: 17 strict AABB separations and 28 cache/conditional-B-rep acceptances.
- The source file remained the same 67,801,194-byte artifact with SHA-256 `4e686e861b08360d2b8fec2663019c01a7a3680cdc88c453f8a69b6812519f17`.
- Regression closure: 646 backend tests plus 3 subtests passed; frontend TypeScript and Vite production build passed; Python compilation passed.

Change significance: the five-minute geometry audit is now optional and independently recoverable, while the three-minute natural-language assembly chain remains available for rapid iteration and review.

## 2026-10-09 — Durable multi-turn natural-language assembly ledger

- Added `assembly-conversation/v1` as a sidecar ledger linking each natural-language requirement and graph revision to prepared/executed CAD jobs and Demo checkpoints without changing the confirmed graph digest.
- Added `contextRevision` to project-adapter plans and bound every prepared durable job to its originating turn.
- Added a recovery API and frontend “load existing context” flow. The UI restores the latest successful Demo job as the next continuation seed and renders a turn/job timeline.
- Added legacy-context migration from graph history with explicit `unavailable-pre-ledger` markers for historical digests that cannot be reconstructed.
- Regression closure: 648 backend tests plus 3 subtests passed; frontend TypeScript/Vite production build passed. SolidWorks was not started.

Change significance: stepwise commands such as “install transport and show it, then add the scanner and show it” now have a persistent, auditable state chain instead of relying on volatile browser state.

## 2026-10-09 — Context-local selected-face semantic ports

- Added a context-local temporary semantic-port registry and face catalog backed by SolidWorks persistent face references and geometric fingerprints.
- Added API/UI paths to capture the currently selected planar face, bind it to an existing module instance, and retain it as a provisional port without modifying CAD.
- Added controlled Chinese parsing from two named temporary ports to coincident, parallel, perpendicular, distance, or angle mate drafts.
- Added fail-closed checks for module-token mismatch, non-planar selections, same-instance self-mates, ambiguous port counts, and missing numeric values.
- Kept execution disabled until the latest Demo checkpoint is adapted to an editable mate graph; the result is explicitly a draft, not an applied mate.
- Regression closure: 651 backend tests plus 3 subtests passed; frontend TypeScript/Vite production build passed.

Change significance: missing pre-authored semantic ports now have a bounded human-selection fallback while preserving stable geometry evidence and a clear no-CAD-modification boundary.

## 2026-10-09 — Demo-checkpoint mate-graph adapter and target-local patch compilation

- Added deterministic read-only export specifications for the latest successful Demo checkpoint, bound to context revision/digest, job/project identity, assembly path, size, timestamp, and SHA-256.
- Added immutable graph-binding manifests that verify the exported graph source and bind its SHA-256 to the unchanged checkpoint assembly.
- Selected-face capture now records the active SolidWorks assembly path before capturing the face; mixed-source temporary catalogs fail closed.
- Added compilation from a ready temporary-mate preview to `mate-graph-patch/v1` and a target-local effective graph. Every existing mate incident to the target is preserved, unrelated context-context mates are excluded, and the new selected-face mate is appended.
- Added confirmed read-only export and non-executing compile APIs plus frontend controls. Real remate remains a separate future confirmation.
- Regression closure: 656 backend tests plus 3 subtests passed; frontend TypeScript/Vite production build passed; Python compilation passed. SolidWorks was not started.

Change significance: the human-selected-face fallback now reaches an immutable, checkpoint-bound executable graph input without silently stacking a mate on top of unknown target constraints or modifying CAD during preview.

## 2026-10-09 — Controlled historical checkpoint import and current-graph proof

- Added a fail-closed historical Demo checkpoint importer. It attests successful-job state, assembly SHA-256, component-inventory identity, source-assembly identity, context revision/digest, and the exact module-token multiset before binding a pre-ledger job to the current conversation.
- Duplicate instances are now handled correctly: Project02 requires and observes two T401 instances while the SolidWorks graph exporter receives one deduplicated module token.
- Imported `project02-job-635438e6d96f` into revision 10 of `project02-full-static-graph-v1` without changing the job or CAD file. The signed attestation is `demo/global_assembly_contexts/checkpoint-imports/project02-full-static-graph-v1/project02-job-635438e6d96f-4e686e861b08.json`.
- Ran a real read-only SolidWorks export from the bound Demo checkpoint. It produced 10 modules, 19 inter-module mates, and 8 mate bundles.
- Bound the graph and unchanged assembly with SHA-256 evidence in `demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/project02-job-635438e6d96f-4e686e861b08.mate-graph.binding.json`.
- Regression closure: 659 backend tests plus 3 subtests passed; frontend TypeScript/Vite production build passed.

Change significance: the pre-ledger ten-object CAD result can now safely participate in the current multi-turn selected-face workflow, and downstream patches are guaranteed to compile against the real current checkpoint graph rather than a prototype or stale graph.

## 2026-10-09 — Project02 A700/A600 selected-face mate CAD closure

- Captured and registered one A700 planar face and one A600 planar face from the immutable ten-object Demo checkpoint.
- Fixed coincident-mate alignment inference to preserve the selected faces' observed world-normal relationship (`dot=-1`, anti-aligned).
- Added an explicit `sourceMateNamesToSuppress` edit policy so newly-added mates are not mistaken for source features that must already exist.
- Added validated target leaf-pose anchors to the patch compiler for flexible subassembly checkpoint-state restoration.
- Preserved v1 as failure evidence; v3 passed mate creation, save/reopen verification, case-anchor verification, 2/2 internal state anchors, and a 233/233 A700 subtree pose comparison.
- Final assembly: `demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a700-selected-face-coincident-v3.SLDASM`.
- Collision was not evaluated in this selected-face Demo closure.

## 2026-10-10 — Direct existing-component mate editing and staged closure

- Upgraded PatchAudit into an executable in-context edit plan: addMate creates only the new relation, updateMate replaces only the edited relation, and removeMate suppresses only the deleted relation.
- Existing targets are no longer removed, reinserted, or deliberately displaced for a selected-face add operation. Legacy graphs without PatchAudit retain the prior remate experiment path.
- Added a hash-bound direct-edit runner and completed two real Project02 A700/A600 executions. The final flexible-state audit passed save/reopen verification, source immutability, full target constraint, and a stable 2/2 A700 root/endpoint fingerprint with zero transform error.
- Final direct-edit artifact: `demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a700-a600-direct-mate-edit-v2-flex-audit.SLDASM`; runtime 89.985 s.
- Added conservative six-DOF Jacobian rank analysis. Tests prove one coincident plane leaves three DOF, two nonparallel planes leave one, and three orthogonal planes reach rank six. Unsupported geometry fails closed.
- Added a general rigid/flexible execution policy. Direct edits preserve and fingerprint parent-context flexible state; flexible reinsertion without internal anchors or an authoritative state is blocked.
- Added atomic ordered natural-language command sequences with per-turn context chaining and durable conversation records. Any ambiguous/blocked turn causes zero context writes.
- Added cross-project semantic-port readiness auditing. Projects 01/02/03/05 are graph-ready across 34 modules; Project06 remains explicitly blocked by its missing versioned profile.
- Collision/B-rep was not run and remains outside the current mandatory acceptance layer.

Change significance: the system now edits relations on existing CAD components, explains residual freedom before claiming closure, preserves flexible state by policy, and accepts resumable ordered natural-language graph commands without coupling the workflow to expensive geometry validation.

Regression closure: backend 674 plus 3 subtests passed; focused editable-mate C# tests 20/20 passed; MCP Release and frontend production builds passed. The full C# suite passed 354 tests and retained two unrelated pre-existing visual-integration failures caused by MCP test-client methods that intentionally throw for `ResolveComponentTarget` and `ListComponents`.

## 2026-10-10 — Project02 real multi-mate transaction closure

- Added fail-closed direct-mate transaction preflight with ordered PatchAudit validation, target-local graph checks, optional multi-operation enforcement, required six-DOF closure, and deterministic rejection of coincident/non-zero-distance or parallel/perpendicular contradictions on the same endpoints.
- Added a conservative width-mate center-plane row to the rigid-body Jacobian; Project02 A500/A600 now evaluates to rank 6 using its real coincident, width-centered, and distance relations.
- Changed the direct-edit runner to execute against a staging assembly and publish atomically only after SolidWorks save/reopen verification succeeds.
- Rebuilt all three real A500/A600 relations in one direct existing-component edit. SolidWorks created 3/3 relations, reported A500 fully constrained, reopened with matching parameters, preserved the immutable source SHA-256, and published `project02-job-635438e6d96f-a500-a600-three-mate-direct-edit-v1.SLDASM` in 94.719 seconds.
- Added hash-attested direct-edit checkpoint binding. The new entity is now the latest physical checkpoint for revision 10 and remains compatible with the next checkpoint mate-graph export.
- Added a confirmed backend binding API and negative tests proving failed/unpublished results cannot advance the conversation.
- Collision/B-rep was not executed and remains `not_evaluated` under the current scope.

Change significance: a complete set of real module-level mates is now preflighted, executed, published, and resumed as one auditable transaction instead of a sequence of irreversible trial edits.

Regression closure: 683 backend tests plus 3 subtests passed; focused editable-mate C# tests 21/21 passed; MCP Release build completed with 0 warnings/errors; frontend TypeScript/Vite production build passed.

## 2026-10-10 — Frontend and multi-selection work deferred

- Recorded frontend DOF visualization, endpoint highlighting, and multi-datum mouse selection as explicit productization TODOs.
- Preserved the existing selected-face capture, temporary-port, face-catalog, and stable endpoint schemas as compatibility boundaries.
- Reordered active development toward arbitrary physical-checkpoint continuation, advanced mate DOF models, cross-project real transaction proofs, and the missing Project06 profile.
- Collision/B-rep remains optional under the current Demo scope.

Change significance: backend assembly semantics and recoverable CAD execution can mature without waiting for UI work, while the already proven human-selection path remains available for later productization.

## 2026-10-10 — Direct-edit physical checkpoint continuation

- Added explicit `seedEditId` continuation alongside the existing `seedJobId` path; the selectors are mutually exclusive.
- A direct-edit seed must resolve uniquely in the conversation ledger, retain its source job identity, and pass assembly/evidence SHA-256 verification.
- The derived durable plan preserves the source job's completed process position while replacing its physical seed with the attested edited assembly.
- Added a closed unit workflow: Project05 D000 succeeds, an edited D000 entity is attested, and the next K000 job is seeded from that edited entity rather than the pre-edit checkpoint.
- Project02's current ten-object job is already at the end of its existing ordered plan, so no duplicate terminal step was created merely to claim a continuation success.

Change significance: post-assembly mate edits are now first-class durable continuation inputs instead of detached CAD artifacts.

Regression closure: 684 backend tests plus 3 subtests passed.

## 2026-10-10 — Advanced mate evidence, Project06 identity profile, and Project05 fail-closed proof

- Extended exported face endpoints with optional analytic-cylinder evidence: surface type, local/world cylinder origin and axis, and radius.
- Added a conservative concentric-mate Jacobian model. Complete parallel cylinder axes contribute four constraints; missing or incompatible geometry fails closed. Slot direction remains explicitly unsupported.
- Added a versioned Project06 identity-only profile covering 9 module tokens and 13 instances. All CAD execution, preview, and semantic-port gates remain disabled until real evidence exists.
- Regenerated the global catalog/readiness audit. Project06 is searchable but reports 0/9 semantic-port readiness instead of receiving invented ports.
- Added a generic module-pair multi-mate transaction builder and used a refreshed Project05 graph to compile the real D000/A000 coincident, distance, and width relations into a rank-6 transaction.
- Added hierarchy-first root recovery for assemblies relocated from vendor paths, and made direct-edit tool exceptions produce auditable failed results instead of abandoned staging files.
- Project05 live CAD trials did not publish an assembly: the lightweight copied assembly could not resolve deep endpoint leaves, while fully resolving A000 exceeded four minutes and was stopped. Failed copies were archived and the immutable source hash remained unchanged.
- Rebound Project02/Project05 derived contexts to the new catalog digest after adding Project06.
- Regression closure: 689 backend tests plus 3 subtests passed; 51 focused C# tests passed; MCP Release and Python compilation passed.

Change significance: cross-project graph compilation is now real and reusable, while the remaining Project05 CAD portability/performance blocker is isolated without weakening publication gates or misreporting preflight as reconstruction success.

## 2026-10-10 — Project05 resolved-session direct-edit closure

- Added an opt-in `preserveResolvedSourceSession` execution mode to the bridge, MCP tool, and atomic Python runner.
- The mode requires the source assembly to be the active document, verifies every graph endpoint before mutation, then saves the in-memory resolved state to the staging path instead of reopening a lightweight file copy.
- Added source-lock handling: a pre-open attested digest may be used when SolidWorks locks the source, but publication still requires a readable matching post-execution digest.
- Re-exported the real Project05 D000/A000 pair in the active session, compiled its three-mate rank-6 transaction, and executed it without recursively resolving the whole A000 root.
- The live result created/replaced 3/3 mates, reopened with matching parameters, reported D000 fully constrained, preserved component semantics, and left the source SHA-256 unchanged.
- Published assembly: `demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-three-mate-resolved-session-v7.SLDASM`; output SHA-256 `132090130f81f0d02082492cfa56d8d83a89c668b80e479d2729a020b021a380`.
- Total runtime was 109.181 seconds; reopen verification was the largest phase at 54.392 seconds.
- Added automated resolved-session runner tests for atomic success publication and exception-path staging archival.
- Regression closure: 691 backend tests plus 3 subtests passed; 51 focused C# tests passed; MCP Release build completed with 0 warnings/errors; Python compilation passed.

Change significance: the first non-Project02 real multi-mate transaction now reaches an authoritative save/reopen CAD closure, proving that the transaction model is portable when lightweight endpoint state is deliberately preserved.

## 2026-10-10 — Single-command resolved-session pair transaction

- Added `scripts/run_resolved_session_pair_transaction.py` to perform source hashing, pair-only graph export, transaction compilation, DOF preflight, resolved-session Save As, direct CAD edit, save/reopen verification, and atomic publication in one invocation.
- Added per-phase timing and immutable artifact manifests; outputs, evidence, and transaction directories refuse overwrite.
- Added automated success and CAD-exception tests. The success test proves the resolved-session flag reaches MCP and the staging file is atomically published; the failure test proves the staging file is archived and the official output remains absent.
- Completed a real Project05 D000/A000 run from the single command. It published 3/3 mates with rank 6, zero residual DOF, matching reopened parameters, full target constraint, stable component semantics, and an unchanged source hash.
- Published `project05-d000-a000-single-command-v8.SLDASM`, SHA-256 `ff8553cf5d9de07b4a84e4ca70a6b960d07c996cc1ccbc49a709706d0a195623`.
- Runtime: 171.311 s total; graph export/endpoint resolution 63.954 s, compile/preflight 0.019 s, same-session CAD execution 107.240 s.
- Regression closure: 693 backend tests plus 3 subtests passed; the previously completed 51 focused C# tests and zero-warning Release build remain valid for the unchanged bridge binary.

Change significance: the portable cross-project transaction is no longer a manually coordinated experiment; it is now one fail-closed command with machine-readable evidence and timing.

## 2026-10-10 — Project01 and Project03 single-command CAD proofs

- Ran the same single-command transaction against Project01 BD00/JJ00. The refreshed graph supplied two analytic concentric relations plus one coincident plane; conservative rank contributions were 4 + 1 + 1 = 6.
- Project01 created 3/3 mates, reopened with matching parameters, reported BD00 fully constrained, preserved component semantics and source hash, and published `project01-bd00-jj00-single-command-v1.SLDASM`.
- Ran the same command against Project03 AB00/AA00. The refreshed graph supplied the previously missing width-face/tab-face roles and constraint type; coincident, width, and distance contributed 3 + 1 + 2 = 6.
- Project03 created 3/3 mates, reopened with matching parameters, reported AB00 fully constrained, preserved component semantics and source hash, and published `project03-ab00-aa00-single-command-v1.SLDASM`.
- Added `demo/global_assembly_contexts/cross-project-pair-transaction-closure-v1.json`, covering real CAD evidence for Projects 01, 02, 03, and 05 while keeping Project06 identity-only.

Change significance: portability is now demonstrated across four project families and two different advanced mate patterns, rather than inferred from Project02-specific tests.

## 2026-10-10 — Durable semantic-connection pair transaction

- Added a versioned real-source registry for Projects 01/02/03/05 and an explicit disabled blocker for identity-only Project06.
- Added a compiler from one committed global semantic connection to a one-step, source-hash-bound real mate transaction plan.
- Added persistent pair jobs with stable plan-digest idempotency, explicit prepare/start separation, context/plan/source revalidation, serialized SolidWorks execution, retry attempts, and immutable evidence.
- Added backend APIs to preview, prepare, start, resume, and inspect the pair job. Preparing a job never starts SolidWorks; starting requires a second digest-bound confirmation.
- Completed the real Project05 `connection-001` job `project05-job-2fd5dca2ddd7`. It rebuilt 3/3 D000/A000 mates, reached rank 6 and zero residual DOF, passed save/reopen and component-semantic verification, preserved the source hash, and published a 74,211,198-byte assembly with SHA-256 `eb4ea21dede7e9603d308c19a4204423f6a0cbd7ee8ee63d4800d91929e340e1`.
- Runtime was 184.452 seconds at the durable-job layer: 74.333 seconds exporting/resolving, 0.023 seconds compiling/preflighting, and 109.532 seconds in same-session CAD execution.
- Regression closure: 699 backend tests plus 3 subtests passed. Collision/B-rep remained deliberately `not_evaluated`.

Change significance: committed semantic intent can now drive a recoverable, auditable real-CAD transaction without exposing SolidWorks process management to the caller.

## 2026-10-10 — Project02 independent cumulative pair-job closure

- Added registered independent-install strategies for Project02 A800/A600 and A180/A600.
- Added hash-attested `seedJobId` continuation: A180 compilation requires a succeeded A800 checkpoint and binds both its assembly and execution evidence.
- The plan/prepare/start APIs now carry the seed binding and recompile against the same seed before CAD scheduling.
- Updated the context-insert runner to close a verified output document, making the artifact reusable as the next immutable source.
- Tightened geometric endpoint recovery: up to 5% face-area drift is accepted only when bounding box and center agree within `1e-4 m`; normal checks remain strict.
- Real job `project02-job-fe64d9d23a25` inserted fresh A800 into the A600-only base, created 2/2 mates, fully constrained the target, passed save/reopen and semantic checks, closed the output, and preserved the source in 50.466 s.
- Real job `project02-job-0baa5e819a88` consumed that attested checkpoint and inserted fresh A180, again creating 2/2 mates with full constraint, save/reopen, semantic, close, and source-integrity checks in 44.002 s.
- Regression closure: 11/11 focused durable-pair tests and 704 backend tests plus 3 subtests passed; the earlier 25/25 focused C# tests and zero-error MCP Release build remain valid.
- Collision/B-rep was deliberately not evaluated and remains outside this stage gate.

Change significance: Project02 now has a real three-module cumulative construction path driven by committed semantic connections rather than direct editing of pre-existing components in the full prototype.

## 2026-10-10 — Project02 service-module cumulative closure

- Added explicit per-profile constraint policies: rigid targets require full constraint, while registered flexible mechanisms must still have an accepted constraint state and a clean SolidWorks solve.
- Added durable prior-checkpoint profiles for A700, A300, and A500.
- The first flexible A700 branch created 6/6 real mates but retained a valid residual root pose. A downstream A500 trial therefore measured 1.127733 m instead of the declared 0.05 m A500/A700 process spacing. The A500 job was rejected and its output quarantined despite its own 3/3 mates and full constraint succeeding.
- Added an A700 static-installation graph that retains all six real A700/A600 mates while applying a Project02-calibrated non-vendor root branch and two internal static-state anchors.
- Reran the affected chain from the last accepted A180 checkpoint. A700 job `project02-job-2fdc4c694816`, A300 job `project02-job-9ecc914162c2`, and A500 job `project02-job-7d59620b9434` all succeeded with save/reopen, semantic, close, and source-integrity evidence.
- The final A500/A700 reopened distance measured `0.049999999999941425 m`, an absolute error of about `5.86e-14 m` from the 50 mm target.
- Latest cumulative assembly: `demo/semantic_ports/project02_resolved_pair_jobs/project02-job-7d59620b9434/attempt-01/project02-job-7d59620b9434-a500-a600.SLDASM`.
- Regression closure: 19/19 focused service/pair tests and 707 backend tests plus 3 subtests passed. Collision/B-rep remains `not_evaluated`.

Change significance: the durable chain now rejects locally valid CAD placements that violate downstream process relations and repairs the governing constraints before recomputing the affected branch.

## 2026-10-10 — Project02十对象独立累计链闭环

- A100、A200和两个T401实例均从上一成功检查点独立插入并通过真实SolidWorks保存重开门禁；对应作业为`project02-job-0e2436fad5c6`、`project02-job-76a3eba2bb07`、`project02-job-dd84e4c4dd81`和`project02-job-0ff50cfd2992`。
- 编译器支持由版本化档案明确声明的非基座上下文安装，因此第二个T401可相对A200装配；未登记的非基座连接仍失败关闭。
- 两个T401共享同一零件定义，但有效图按层级实例区分；第二次插入得到`T401AA-07388-0-2`，没有移除第一实例。
- 新增累计链审计器，反向验证9个作业的种子链接、实体/证据摘要、源文件不变、输出关闭和注册顺序。审计确认A600加9次插入共10对象，顺序完整，执行耗时合计536.979秒。
- 最终实体：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-0ff50cfd2992/attempt-01/project02-job-0ff50cfd2992-t401-a200.SLDASM`；审计：`demo/semantic_ports/project02_resolved_pair_jobs/project02-full-static-chain-audit-v1.json`。
- 碰撞/B-rep、A100动态行程、A200光学工艺和T401维护可达性均未纳入本轮门禁，生产状态保持未放行。

功能修改意义：Project02的语义连接已形成可追溯的完整静态累计CAD链，而不是互不关联的局部成功文件；终态审计同时防止跳步、错种子和重复实例丢失。

## 2026-10-10 — Project02原型依赖审计与非原型初始位姿实验

- 新增逐安装步骤依赖审计和消融图生成器。9步全部使用原型提取配合几何，7步含顶层案例锚点，A700另含2个内部静态状态锚点；A500、A100已无顶层案例锚点。
- 对7个锚定步骤清空顶层案例锚点，从确定性非源位姿分别执行真实CAD插入；A500、A100复用已有无锚点正式证据。7次新CAD实验累计测量401.895秒。
- A300、A500、A100、A200共4/9通过非原型初始位姿门禁；A300和A200的正式图案例锚点已证明冗余，但尚未修改正式累计链。
- A800、A180、A700及两个T401均创建了全部请求配合并完成保存重开，但未达到完整可发布约束状态；实验件保留为诊断证据，未进入正式链。
- 下一步应先删除A300/A200冗余锚点并从A300阶段重跑下游链；再分别为A800纵向定位、A180扫描支架定位、A700操作侧服务定位和双T401安装基准补充机械语义。
- 审计：`demo/semantic_ports/project02_nonprototype_initial_pose_v1/prototype_dependency_audit.json`；结果：`demo/semantic_ports/project02_nonprototype_initial_pose_v1/nonprototype_initial_pose_cad_test.json`。
- 碰撞/B-rep、动态行程、CCD光学和维护空间未评估。

功能修改意义：首次以逐步真实CAD消融实验量化Project02的原型顶层位姿依赖，避免把独立文件插入误称为完全去原型。

## 2026-10-10 — Project-independent semantic transaction DAG

- Added `global-assembly-command-ir/v1` to every natural-language graph preview, normalizing the accepted intent into explicit `ADD` and `CONNECT` operations.
- Added `global-assembly-transaction-dag/v1`, which derives cumulative insert/connect transactions from the committed global graph without loading any project-specific fixed sequence.
- Added fail-closed validation for instance reachability, port ownership, template compatibility, endpoint portability, driving mate availability, CAD sources, and declared residual constraint semantics.
- Added a read-only transaction-DAG API and CLI. Neither starts SolidWorks; collision remains `not_evaluated`.
- Project05 compiled to eight generic-ready transactions with no blockers. Project02 compiled to nine transactions but correctly blocked A800 and A180 because their catalog templates explicitly declare incomplete location.
- Rebuilt a current-catalog natural-language A600→A800→A180 context; graph creation succeeded and the generic planner exposed the same two mechanical-datum gaps before CAD.
- Regression closure: 31 focused tests and 719 full backend tests plus 3 subtests passed; Python compilation passed. Repository-wide diff checking still reports pre-existing whitespace in unrelated dirty C# files, while the files changed in this stage contain no new trailing whitespace.

Change significance: the free-composition mainline now has a project-independent execution intermediate representation instead of treating each project runner's validated sequence as the planner.

## 2026-10-10 — Generic endpoint-complete CAD transaction packets

- Added `global-cad-transaction-packet/v1` and `global-cad-transaction-manifest/v1` on top of the project-independent DAG.
- Each packet binds the target CAD sources, semantic dependencies, cumulative input checkpoint, mate parameters, both endpoint-role candidate sets, verification requirements and a stable digest.
- Added a read-only manifest API and CLI; no SolidWorks process is started by compilation.
- Project05 produced eight endpoint-complete packets with zero blockers. Project02 produced nine packets but retained two underconstraint blockers and four authoritative-CAD-verification boundaries.
- Full backend regression: 721 tests plus 3 subtests passed. API smoke returned `global-cad-transaction-manifest/v1 ready_for_generic_executor_implementation 8`.

Change significance: the generic planner now emits an executor-facing CAD contract; the next task is to make the existing cumulative transaction engine consume it without a project fixed-sequence planner.

## 2026-10-10 — Project-independent two-packet cumulative CAD proof

- Added a digest-bound generic CAD packet execution plan and a single-packet runner that does not read project fixed-sequence profiles.
- Added a generic root-module wrapper. It inserts the root module as the only top-level context component, applies the effective graph's exact 16-value source transform, saves, closes, reopens, and verifies pose before target insertion.
- The first real attempt correctly failed because a root A000 document cannot resolve itself as a child context component. The second attempt exposed a missing Project05 distance flip option and rejected a 0.624 m mirrored placement.
- Switched Project05 semantic-port migration to the v2 source graph, preserving `DistanceFlipDimension=true`, then regenerated the global catalog, Project02/05 contexts, transaction DAGs, and CAD packet manifests.
- Generic packet 001 inserted D000 into an independently wrapped A000 context with 2/2 mates, complete reopened parameter agreement, accepted constraint state, `5.55e-17 m` case-anchor translation error, unchanged sources, and closed output.
- Generic packet 002 consumed packet 001 as its explicit immutable checkpoint and inserted K000 with 3/3 mates, full constraint, zero case-anchor translation error, complete reopened parameter agreement, and unchanged prior checkpoint.
- Regression closure: 10 focused tests and 725 backend tests plus 3 subtests passed after rebuilding stale catalog-bound contexts.
- Collision/B-rep remained `not_evaluated` by current scope.

Change significance: the project-independent path now reaches two consecutive real SolidWorks transactions; the second output is a true cumulative checkpoint rather than a prototype replay or a project-runner sequence step.

## 2026-10-10 — Durable manifest orchestrator, recovery, and cross-family proof

- Added `global-cad-manifest-job-plan/v1` and `scripts/run_global_cad_manifest_job.py` for digest-bound durable execution of a contiguous CAD packet manifest slice.
- Added automatic checkpoint chaining, boundary pause, resume from the last committed checkpoint, rejected-output quarantine, and failure rollback without reverse-mutating a CAD file.
- Added per-attempt timing/evidence files and preserved packet/manifest digests in every committed checkpoint.
- Real Project05 job `project05-job-642ab847f1cf` resumed from packet 002, paused after packet 003, failed safely before packet 004 by diagnostic injection, then resumed only the failed tail and completed packets 004-005. Final cumulative object set: A000/D000/K000/F000/M000/G000.
- Generalized first-packet preparation to evidence-backed multi-module base contexts and added explicit project-alias-to-effective-graph-token resolution.
- Real Project03 job `project03-job-4c038b2c1c11` recovered from the two newly exposed adapter failures and completed AA00/AF00 + AE00 through the same generic manifest runner.
- Added Project01 and Project03 cross-family smoke context builders. Project01 exposed the same composite-base requirement; Project03 supplied the completed real-CAD acceptance case.
- Regression closure: 732 backend tests plus 3 subtests passed; Python compilation passed. Collision/B-rep remains `not_evaluated` by scope.
- Closure: `demo/global_assembly_contexts/global-cad-manifest-orchestrator-closure-v1.json`.

Change significance: generic semantic packets are now operated as a recoverable persistent job rather than manual one-off scripts, and the execution contract has been proven outside the Project05 family.

## 2026-10-10 — Project01 regression, manifest APIs, and NL-to-job compilation

- Executed Project01 SS00 through the generic runner using the attested JJ00+HL00 composite base. Save/close/reopen and source integrity passed in 115.885 seconds.
- Added backend APIs for durable manifest-job create/list/status/start/pause/resume. Status exposes progress, failure, rollback, last checkpoint, attempts, timing, and events.
- Added direct natural-language sequence compilation into a global context, CAD manifest, and queued durable job; compilation never starts SolidWorks.
- Fixed zero-padded Chinese project-number disambiguation and existing-target/new-module resolution.
- Compiled non-fixed Project05 three-step and five-step contexts. Project02 A600/A800/A180 remains blocked before job creation because A800 and A180 are underconstrained.
- Executed the non-fixed three-step context as real CAD job `project05-job-09b1a2005ef9`: A000→G000→F000 succeeded in 378.139 seconds, with the second packet consuming the first immutable checkpoint. The output SHA-256 is `f500bfa6f223be6f7a76f15361c30b02532caa783b3605a7495bee5515ec0d31`.
- Focused closure: 16 tests passed. Full backend: 741 tests plus 3 subtests passed. Collision/B-rep remains `not_evaluated`; frontend work remains deferred.

Change significance: the generic runner is now externally operable through a backend contract, and controlled natural language can create executable jobs without project-specific fixed sequences.

## 2026-10-11 — Project02 A800/A180推定定位标准

- 新增版本化`project02-inferred-positioning-standard/v1`，统一记录需求表尺寸、A600工程坐标、A800真实安装配合、A180机械安装配合、扫码光学关系和剩余案例锚点。
- 建立七级证据权威顺序；只有厂商或工程师确认可以生产放行，CAD/原型/需求推定只允许Project02粗布局。
- A800明确为`重合35＋宽度9＋沿X案例锚点`；A180明确为`重合34＋距离24＋槽口3只读证据＋案例锚点`，并单独保留A180到A800条码目标的功能关系。
- A800/A180语义端口构建器均绑定定位标准版本和摘要；A180工作距离改由标准读取，消除构建器中的孤立常数。
- 新增审计脚本及产物，结果为`coarseLayoutReady=true`、`productionReady=false`，三项临时限制被明确列出。
- 聚焦测试6项通过；A800/A180构建器集成重建成功。

功能修改意义：Project02缺少厂商精确尺寸不再等同于“规则不可实现”，但系统会明确区分项目级粗布局基线和生产权威数据，避免隐式复制原型。

## 2026-10-11 — 推定定位标准接入通用事务清单

- 通用事务DAG和CAD事务包支持显式选择`project02-inferred-v1`；未选择时原有欠约束阻塞保持不变。
- 显式选择后，只有A800/A180已登记的案例剩余自由度被标记为`closed_by_explicit_project_baseline`，事务包携带标准版本、摘要和规则编号。
- 自然语言`A600→A800→A180`入口烟测成功：清单状态`ready_for_generic_executor_implementation`，2个事务包、0阻塞项，并创建未启动CAD的排队任务`project02-job-6e3c1b72de5d`。
- 聚焦回归18项通过，相关API/参数回归14项通过，后端全量回归`748 passed, 3 subtests passed`，Python编译通过。
- 现场SolidWorks打开了带未保存标记的Project05装配体，本轮未强行启动真实CAD短链；碰撞保持`not_evaluated`。

功能修改意义：Project02推定基线现在是用户显式选择、摘要锁定的执行输入，而不是编译器中的隐式例外；同时保持通用模式默认失败关闭。

## 2026-10-11 — Project02 A600→A800→A180真实累计CAD闭环

- 在用户清理其他SolidWorks装配体后，启动此前编译的持久作业`project02-job-6e3c1b72de5d`。
- A800步骤通过`重合35＋宽度9＋显式Project02案例锚点`完成独立插入，2/2配合成功，重开参数一致；步骤耗时`182.943 s`。
- A180步骤消费A800已提交的不可变检查点，通过`重合34＋距离24＋显式Project02案例锚点`完成独立插入，2/2配合成功，`距离24=0.272 m`重开一致；步骤耗时`32.787 s`。
- 作业总耗时`215.913 s`，状态为`succeeded / assembled`，回滚记录为空，碰撞状态保持`not_evaluated`。
- 最终装配体SHA-256为`88fd1f0ed67bf500b4ec97c3059778334dcb2debec4b16a0bc6bd8b233857334`。
- 额外执行独立保存重开健康检查：3个顶层对象、重建状态健康、文件哈希稳定，并输出最终截图；复核耗时`5.433 s`。
- 证据根目录：`demo/global_assembly_contexts/manifest_jobs/project02-job-6e3c1b72de5d/`。

功能修改意义：Project02缺少厂商精确定位数据时，已不再只停留在“标准可编译”；同一显式、版本化推定标准已经驱动通用执行器完成真实A600/A800/A180累计装配，并通过逐步保存、关闭、重开和最终独立复核。该成果仍严格限定为粗布局/Demo，不替代厂商生产数据。

## 2026-10-11 — 主线切回自然语言子模组级灵活装配

- 明确当前唯一优先目标为“自然语言→全局模组身份→语义端口→通用关系模板→配合图→动态事务DAG→累计SolidWorks装配”。
- Project02 A600/A800/A180闭环作为黄金回归保留，但不继续把生产放行、精密光学或Project02固定顺序作为核心开发目标。
- `productionReady`、碰撞/B-rep、动态行程和维护空间继续如实记录，但默认不阻塞自然语言编译、端口匹配、事务生成和Demo CAD执行。
- 在开发前必读规则中新增八阶段计划：冻结内核、端口覆盖矩阵、关系模板、自然语言多轮编译、动态CAD执行、跨项目实证、后端解释接口和系统测试矩阵。
- 立即执行入口收敛为：覆盖矩阵→首批通用支持集→12条自然语言测试→3条动态DAG→两项目族真实CAD链。

功能修改意义：把已有的多个项目实证和持久执行能力用于扩大通用组合覆盖，而不是继续在单个案例上追逐当前不要求的生产级验证。

## 2026-10-11 — 全局模组端口覆盖矩阵与选择门禁

- 新增`apps/demo-backend/src/demo_backend/global_module_port_coverage.py`，以签名全局目录为输入生成确定性的模组、端口、关系模板、兼容边和缺口优先级矩阵。
- 新增`global_module_port_coverage_matrix.json`：43个模组、61个兼容连接对、34个CAD端点就绪模组、9个阻断模组、59个CAD端点就绪连接对。
- 新增选择就绪度评估器和后端API；未知模组、跨项目重名、缺端口、缺CAD端点和连接子图不连通均在CAD启动前失败关闭。
- Project02 `A600+A800+A180`评估通过；Project06的9个缺口全部以`NO_SEMANTIC_PORT`记录并按P0/P1排序。
- 审计过程中发现重建目录会改变签名摘要并触发14项上下文回归失败。已恢复签名目录，将覆盖脚本改为默认只读；显式刷新只在内存中执行，不覆盖已签名文件。
- 新增6项覆盖矩阵测试；聚焦回归21项通过；完整后端回归`754 passed, 3 subtests passed`；Python编译通过。
- 本阶段没有启动SolidWorks，没有执行碰撞/B-rep，碰撞状态保持`not_evaluated`。

功能修改意义：系统首次能在生成自然语言装配任务前，机器化回答“哪些模组已经有端口、哪些关系可以落到CAD、哪些对象必须先补数据”，为通用自由组合建立可审计的能力边界。

## 2026-10-11 — 通用关系语义与自由度解释第一轮

- 新增`global_relation_semantics.py`：解析安装、重合、同轴、平行、垂直、距离、角度、居中、槽口和方位；统一毫米/厘米/米与角度参数。
- 修复“项目05 M000”被误解析为“5米”的词法边界问题；安装面中的“安装”也不再被误判成安装动作。
- 命令预览新增`relationIntent`和关系候选评估；复合安装束不得作为独立同轴/平行模板；距离值不一致、模糊对齐和缺少方位参考均在CAD前阻断。
- 命令IR、持久连接和事务DAG携带关系语义与模板自由度解释；驱动配合和只读验证关系分开统计。
- 新增关系能力矩阵、三条5模组首批支持链和14条语言测试基线；新增两个只读后端接口。
- 修复全局目录构建器读取共享`endpointCatalogPath`；生成独立迁移预览，没有覆盖签名目录。预览使A500/A700驱动距离端点可便携，但DAG因剩余自由度继续阻断完整定位。
- 聚焦回归35项通过；完整后端回归`772 passed, 3 subtests passed`；未启动SolidWorks，碰撞/B-rep未评估。

功能修改意义：关系编译从“挑到一个兼容端口就算成功”升级为“关系语义精确匹配＋端点便携性＋驱动/验证区分＋自由度门禁”。

## 2026-10-11 — 签名目录迁移与既有实例关系编辑

- 新增`global_catalog_migration.py`：比较目录版本并按上下文实际引用执行兼容性审计；迁移采用预览摘要、显式确认、新上下文和独立绑定证据，禁止覆盖源文件。
- 新增迁移CLI：`scripts/migrate_global_catalog_context.py`。
- Project02十对象上下文已由旧目录摘要`707e0cfcd85e...`迁移至候选目录摘要`89169ae6223d...`，0阻塞、0警告。
- 新增`global_relation_edits.py`及关系编辑API，支持已存在模组实例之间关系的新增、替换和删除。
- 动态事务DAG新增`ADD_RELATION / VERIFY_RELATION`事务；关系编辑不再误判为新增模组定位，驱动关系保留CAD过约束检查要求。
- A500/A700 50 mm独立距离关系提交成功；60 mm按未登记参数阻断。十对象关系图由9条连接增至10条。
- 新增9项迁移/关系编辑测试；完整后端回归`782 passed, 3 subtests passed`。
- 未启动SolidWorks，未进行碰撞或B-rep检查。

功能修改意义：全局目录可以安全演进，已有装配图无需重建；同时关系操作从“添加模组的附属动作”提升为可单独审计、修改和执行的图事务。

## 2026-10-11：Stage C第三轮——Project01主定位与防转组合闭合

- 新增Project01 GN00/JJ00独立重合、独立同心和GN00/SS00独立平行模板，全部复用既有面目录的持久引用与几何指纹。
- 在关系模板中增加显式互补声明；事务编排器只合并声明为同一目标插入、且指定了主模板ID的补充关系。
- 修复GN00主定位剩1个自由度时被提前阻断的问题。主定位与防转关系现合并为一个`INSERT_AND_CONNECT`步骤，组合剩余自由度为0。
- CAD事务包保留DAG操作类型；组合插入包包含2条连接、3个配合步骤，状态为可交给通用执行器。
- 增加消融测试：删除防转关系后仍严格返回欠约束阻塞，未引入启发式自由度相减。
- 新增可复现实验脚本`scripts/run_project01_declared_relation_closure.py`和证据`demo/global_assembly_catalog/v1/relation-v2-preview/project01-gn00-standalone-parallel-closure.json`。
- 聚焦回归16项通过；全量回归首次发现覆盖矩阵的预期兼容边数量仍为61，已按新增6条有向兼容边更新为67。
- 新增12条命令级关系矩阵并全部通过；覆盖新增/替换/删除、精确基础关系、未登记距离、重复关系、歧义、未知实例、模板误用和摘要失配。
- 机器可读矩阵位于`demo/global_assembly_catalog/v1/relation-v2-preview/global_relation_command_matrix.json`。
- Project01组合闭合、Project03组合基座和Project05八步长链三种动态DAG均通过项目无关编译。
- 修正后后端全量回归为`788 passed, 3 subtests passed`。
- 本轮未启动SolidWorks；未执行碰撞/B-rep；签名目录`global_module_catalog.json`未被覆盖。

功能修改意义：把“一个完整安装模板”扩展为“多条有证据的关系共同定位”，为自然语言分步装配和后续新增/修改配合共用同一事务模型奠定基础。

## 2026-10-11：Project01多连接事务真实CAD闭环

- `global_cad_packet_executor.py`新增目标模组配合精确覆盖门禁；请求与有效图按名称、类型、方向、距离和角度逐项比较，多出或缺少均阻断。
- 新增事务执行图投影，现场只解析本次目标及其实际连接上下文；权威图和投影图分别记录路径与摘要。
- `global_cad_manifest_orchestrator.py`步骤记录增加操作、连接数和请求配合数。
- Project01持久任务`project01-job-066a20f791a4`：第一包SS00成功（64.981秒）；第二包初次因无关FF00解析失败（19.205秒）并自动回滚；修复后从SS00检查点恢复，GN00成功（69.251秒）。
- GN00结果：3/3配合创建、目标完全约束、求解干净、保存关闭重开成功、参数一致；源检查点未改变。
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-066a20f791a4/packet-runs/packet-002-attempt-02/project01-cross-family-relation-v2-v1-packet-002.SLDASM`。
- 闭环报告：`demo/global_assembly_contexts/project01-relation-v2-real-cad-closure.json`。
- 专项回归14项通过；全量后端回归`791 passed, 3 subtests passed`；碰撞/B-rep未评估。

功能修改意义：验证了同一新增模组可以由两个既有模组上的三条配合共同定位，并证明持久编排器能在真实CAD失败后保留前序成果、修复后从最近检查点继续。

补充：结果装配体已正确关闭，但现场遗留一个由适配器临时打开的`FL9C24N074GN00.001 *`窗口；源文件未保存、时间戳未改变。`run_context_mate_graph_insert.py`已新增“执行前文档清单＋只关闭本次新打开目标源”的清理逻辑，Python语法检查通过；因独立MCP清理进程启动失败，本轮未能现场验证该新增分支，也未强制结束SolidWorks进程。

## 2026-10-11：Project02既有实例关系编辑/验证分流

- 通用数据包执行器新增`direct_existing_component_mate_edit`和`read_only_existing_relation_verification`策略。
- 修复关系局部执行图未同步更新`ModuleCount`、`InterModuleMateCount`和配合束计数的问题。
- A500/A700 50 mm驱动新增真实CAD实验返回`swAddMateError_OverDefinedAssembly`；事务失败关闭、源文件未变、输出未发布。
- 同一关系以`VERIFY_RELATION`执行成功：重开测量`0.0499999999999968 m`，绝对误差约`3.2e-15 m`，0项配合变更，源文件未变，另存输出已发布。
- 成功运行目录：`demo/global_assembly_contexts/generic_packet_runs/project02-a500-a700-spacing-verify-real-v2-20261011/`；真实验证总耗时约`91.933 s`。
- 全量后端回归：`797 passed, 3 subtests passed`。碰撞/B-rep未执行。

### 持久后缀任务补充

- 关系事务包新增`relationModuleTokens`，不再依赖新增目标模组字段。
- 持久编排器支持在摘要完整的阻断清单中选择全部就绪的后缀包，并强制使用外部验证检查点作为种子。
- `packet-010`模拟故障回滚到`packet-009`，恢复后仅重试失败包并成功提交。
- 全量后端回归更新为`799 passed, 3 subtests passed`；本补充未再次启动SolidWorks。

## 2026-10-11：历史检查点种子转换与持久VERIFY_RELATION实证

- 新增`global_manifest_seed_import.py`和转换脚本，外部种子同时校验历史签认、文件哈希、迁移谱系、实例集合、清单摘要、计划摘要和前缀包摘要。
- 生成Project02 packet-009外部种子证据，装配体SHA-256保持`4e686e861b08360d2b8fec2663019c01a7a3680cdc88c453f8a69b6812519f17`。
- 持久作业`project02-job-da6d6a5ec4ed`只执行packet-010并成功提交；任务耗时约`109.955 s`。
- 新装配体SHA-256：`8cbc0eaadaddfab03011671403f1e009d1b99199ea9b1c5d0ccf4d601bc74279`；实测距离`0.0499999999999968 m`，0项配合修改。
- Project03已有只读距离端点，但仍嵌在复合安装模板；跨项目下一步是登记独立验证模板。
- 全量后端回归：`802 passed, 3 subtests passed`；碰撞/B-rep未执行。
# 2026-10-11 Project03跨项目关系闭环

- 新增 `global_relation_template_derivation.py`，受控派生复合模板中的只读验证关系。
- 新增既有大装配体的上下文子集种子签认与命令行转换器。
- 修复 Project03 `ValidationRelations` 缺少 `alignment` 时的距离/角度只读匹配。
- `project03-job-ac77c693ae78` 真实CAD成功：AA00—AB00距离5实测40.00000000000188 mm，零配合变更，源文件不变，保存重开通过。
- 本轮意义：Project02通用关系事务链首次在Project03真实CAD证据上复用成功。
- 测试：805 passed，3 subtests passed。

# 2026-10-11 Project01跨项目平行关系闭环

- 新增注册式关系模板派生流程，区分`extract_validate_only`与`existing_mate_observation`。
- SolidWorks只读验证新增无向法向夹角测量，平行目标为0 rad。
- 建立Project01 GN00—SS00平行验证上下文、清单、既有装配体子集种子和持久作业。
- 作业`project01-job-8a21b33ff155`成功：夹角0、误差0、容差`1e-6 rad`；0项配合修改；源文件不变；保存重开通过。
- CAD总耗时约149.74秒，主要耗时为打开解析55.29秒、保存关闭35.55秒、重开验证49.82秒。
- Python全量回归`807 passed, 3 subtests passed`；C#非可视化集成回归`363 passed`。C#全量的2项既有可视化集成失败源于测试客户端明确不暴露接口，与本轮改动无关。

功能修改意义：关系语义、端口恢复和持久CAD事务在第三个项目族上复用成功，并覆盖方向关系而非仅距离标量。

# 2026-10-11 Project01重合验证与关系目录发布

- 新增`swMateCOINCIDENT`只读几何验证，同时测量平面距离与无向法向夹角。
- 新增GN00—JJ00重合观察模板、上下文、事务清单、种子签认和持久作业。
- 作业`project01-job-14a100663758`成功：距离约`2.60e-16 m`，夹角0，0项配合修改，源文件不变。
- 新增关系目录发布门禁；`relation-v4-20261011`绑定3条派生模板与3份真实CAD通过证据。
- 发布范围明确排除驱动关系、碰撞/B-rep与生产放行。
- 全量回归：Python `809 passed, 3 subtests passed`；C#非可视化集成`365 passed`。

功能修改意义：新增关系只有在派生证据、真实CAD证据和目录摘要全部一致时才能进入固定发布版本。

# 2026-10-11 关系发布运行时接入与同轴几何准备

- 发布清单新增可迁移相对路径、发布目录文件SHA-256，并对完整最终清单重新计算摘要。
- 默认关系能力和自然语言关系预览绑定`relation-v4-20261011`；新增发布信息接口。
- 自然语言重合、平行、40 mm距离均命中唯一发布模板；同轴因未发布而阻断。
- API补齐`operation=verify`；新增`executionMode=verify|drive`，当前发布版拒绝驱动模式。
- C#只读验证新增圆柱面轴线恢复及同轴径向距离/角度联合测量。
- 回归：Python `811 passed, 3 subtests passed`；C#非可视化`367 passed`。未启动SolidWorks，未执行碰撞/B-rep。

功能修改意义：固定发布目录真正进入运行时选择链；同轴验证已完成算法和测试准备，待真实CAD证据后才能发布。

# 2026-10-11 Project01同轴真实CAD验证与relation-v5发布

- 关系派生注册表升级为v2，加入GN00定位孔—JJ00安装孔独立同轴观察模板。
- 持久作业`project01-job-6028bd3d279b`通过：径向轴距`8.755986498829282e-17 m`、轴角0、0项配合修改、源文件不变、保存重开通过。
- 两端恢复策略均为`BodyFaceIndex+RuntimeCylinderSurface`。
- CAD耗时约137.99秒；打开解析45.74秒、保存关闭48.21秒、重开验证34.37秒。
- 发布不可变目录`relation-v5-20261011`，绑定4条派生模板与4份真实CAD证据，摘要`387575b777e857b5cbd6694d625258c866d0b9fcb9fe84e6f34902386d7afa60`。
- 默认关系入口切换到v5；同轴只读请求放行到端点选择，驱动请求继续失败关闭。
- 定向Python回归`18 passed`；最终全量Python回归`812 passed, 3 subtests passed`；C#非可视化回归`367 passed`。碰撞/B-rep未执行且不属于本轮关系语义验收。

功能修改意义：第四种关系类型完成了从自然语言选择到真实CAD证据发布的完整闭环，下一阶段可把开发重点转向驱动型关系的自由度与过约束安全预检。

# 2026-10-11 驱动关系自由度与过约束预检

- `preflight_direct_mate_transaction`新增严格冗余修改门禁和显式驱动决策。
- 新增`relation_driving_preflight.py`，联合已发布自然语言关系模板与有效配合图，输出可驱动试验、仅验证、阻断三类结果。
- 新增`POST /api/demo/global-relation-driving/preflight`，全程不启动SolidWorks。
- 真实Project05 A000—D000图：约束秩6、剩余自由度0、无冗余，机械层可进入驱动试验；v5发布权限仍使整体结果保持只读。
- 自动生成正常、冗余、缺失槽口几何三类证据报告：`demo/global_assembly_contexts/relation-driving-preflight-v1/report.json`。
- 对历史真实CAD驱动作业重新审计，13/13检查通过；报告为`demo/semantic_ports/project05_resolved_pair_jobs/project05-job-2fd5dca2ddd7/attempt-01/driving-pilot-audit-v1.json`。
- 定向回归`18 passed`；最终全量后端回归`821 passed, 3 subtests passed`。本轮没有启动SolidWorks，没有执行碰撞/B-rep。

功能修改意义：在CAD启动前即可拒绝冗余或几何不足的关系，同时避免把只读模板误当成驱动模板；Project05三配合束成为首个限定驱动发布候选。

# 2026-10-11 Project05限定驱动候选与冷会话CAD复验

- 新增`scripts/build_project05_d000_scoped_driving_candidate.py`，从真实有效图和既有面目录生成A000—D000三配合候选。
- 旧目录缺失的`宽度17`已补齐4个端点角色及宽度/标签分组；8个端点身份全部复用，没有重新猜面。
- 全局目录构建器新增`additional_semantic_catalog_paths`；候选移出默认扫描范围，修复正式目录兼容边由67误增至68以及D000安装模板二义性。
- 发布清单新增`authorizedDrivingTemplateIds`逐模板授权；非驱动模板、未知模板和未授权匹配均在CAD前阻断。
- 冷会话直接CAD试验耗时8.35秒后失败关闭：3条请求配合、0条实际创建，三个失败均为目标叶零件未解析；原型文件未变化。
- 同会话全量解析重试在约4分钟尚未生成`source-graph.json`，受控停止；只清理残留`SolidWorksMcpApp`，保留正常响应的SolidWorks主进程。
- 证据：`demo/global_assembly_catalog/v1/driving-v1-preview/evidence.json`；失败结果：`demo/semantic_ports/project05_D000_A000_scoped_driving_v2/cad/current-cad-rerun-v1.result.json`。
- 最终Python全量回归：`824 passed, 3 subtests passed`。本轮未修改C#，未执行碰撞/B-rep。

功能修改意义：候选配合语义、端点身份和权限边界已经闭合；未完成部分被明确定位为Project05冷启动叶组件解析与性能问题，而不是继续盲目修改配合或放宽发布门禁。

# 2026-10-11 Project05小上下文驱动闭环与relation-v6专用发布

- 从历史已通过三配合副本裁剪A000/D000静态上下文：删除11个无关顶层组件，重开2个组件路径与根位姿一致，耗时88.87秒。
- `run_context_direct_mate_edit.py`新增`--prepare-resolved-source-session`，同一MCP会话内打开源、解析全部轻量组件，再执行配合事务。
- 当前CAD闭环成功：3/3配合创建或替换，D000完全约束，组件语义和重开参数一致，源上下文未修改；总耗时158.54秒。
- 输出装配体：`demo/global_assembly_catalog/v1/driving-v1-preview/project05_D000_A000_scoped_driving_v2/cad-cache/project05-a000-d000-remated-v1.SLDASM`，SHA-256=`08f10d06157730b1b23b69de2dba174cbe15624248c18ad48ed51bb61a807a7a`。
- 发布验证器新增`context-direct-mate-edit-run/v1`严格证据判定；发布脚本支持`--authorize-driving-template`。
- 生成专用发布`relation-v6-project05-driving-20261011`，只授权Project05 A000—D000三配合模板；默认v5未切换。
- 自然语言“在A000上安装D000输送模组”在显式v6清单下唯一匹配，严格预检返回`ready_for_driving_cad_trial`。
- 最终Python全量回归：`827 passed, 3 subtests passed`。本轮未修改C#，未执行碰撞/B-rep。

功能修改意义：首个驱动关系已经形成“自然语言选择—逐模板授权—自由度预检—小上下文解析—真实配合重建—保存重开—专用发布”的完整证据链。

# 2026-10-11 Project05非原型位姿门禁、独立插入闭环与relation-v7

- 装配上下文新增`relationReleaseBinding`，记录发布ID、发布摘要、目录摘要和逐模板驱动授权；命令预览、DAG、执行清单与CAD事务包继续携带并校验该绑定。
- 新增`--displace-target-before-remate`实验模式以及目标变换矩阵审计。首次扰动证明D000实际移动，但原位三配合未将其拉回；解除固定后又产生三条过定义配合。失败副本均隔离，源文件未变化。
- 发布规则升级：驱动关系必须有非原型初始位姿证据，原位替换配合不能作为充分证据。历史v6因此自动失效。
- 改用`context_incremental_insert`：删除旧D000，从独立模块文件插入非case-anchor实例，再建立完整三配合束。真实CAD结果3/3成功、`MateSolveClean=true`、D000完全约束、重开参数一致、源文件不变，耗时约62.93秒。
- 输出实体：`demo/global_assembly_catalog/v1/driving-v1-preview/project05_D000_A000_scoped_driving_v2/cad-cache/project05-a000-d000-fresh-insert-v1.SLDASM`，SHA-256=`17ee4ce5f48f0892945da0fd5bc4ae449bdedb951c13f8ed429bb8f6d4196467`。
- 新发布：`demo/global_assembly_catalog/releases/relation-v7-project05-driving-independent-20261011/release-manifest.json`。
- 新增可复现自然语言事务脚本`scripts/build_project05_v7_natural_language_transaction.py`；生成一条ready CAD包及报告`demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/report.json`。
- 最终回归：Python `831 passed, 3 subtests passed`；C#非可视化`367 passed`。完整C#测试另有2项既有可视化集成测试因测试客户端故意不开放接口而失败，与本次改动无关。
- 本轮未执行碰撞/B-rep。

功能修改意义：纠正了“完全约束等于配合驱动成功”的错误假设，并把真正独立于原型顶层位姿的CAD证据接入自然语言发布与事务链。

# 2026-10-11 Project05 v7通用持久执行与恢复闭环

- 发布绑定校验下沉到通用CAD执行边界：任务创建、每包启动和单包计划都会重新验证发布清单、目录摘要及逐模板驱动授权。
- 修复执行计划误排除四面宽度配合的问题；仅结构完整的宽度配合可越过旧`IsBasicTwoFaceRebuildable=false`标志。
- 真实作业`project05-job-f299afc4e4fc`成功：A000基座包装、D000独立插入、3/3配合创建、完全约束、保存关闭重开和源文件不变全部通过；总耗时281.54秒。
- 恢复作业`project05-job-54f7f53bffbc`：attempt-01在CAD前故障注入且无污染；resume后的attempt-02约197.88秒成功并提交检查点。
- 输出证据总表：`demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/durable-executor-closure.json`。
- Python全量回归：`834 passed, 3 subtests passed`。碰撞/B-rep未执行。

功能修改意义：首个发布驱动模板已经从自然语言ready事务进入通用持久CAD执行、失败回滚和恢复机制，为下一项目族复用提供了可审计基线。

# 2026-10-11 Project01 v9跨项目族发布与累计CAD闭环

- 汇总当前版SS00、GN00独立插入证据，生成Project01限定驱动候选；两个目标均为独立子装配体插入、`TargetCaseAnchored=false`、3/3配合、完全约束、保存重开通过。
- 关系编辑接入发布白名单；未授权模板和预览后发布绑定变化均在提交前拒绝。新增定向测试后通过`28 passed`。
- 首次v8候选错误选择`GN00_to_SS00_anti_rotation`安装模板作为独立关系；系统因`supportsStandaloneRelation=false`及白名单不匹配失败关闭，未启动CAD。
- 修正为`GN00_SS00_standalone_parallel`，发布`relation-v9-project01-driving-independent-20261011`，授权SS00安装、GN00主定位和GN00/SS00防转三条模板。
- 自然语言命令被编译为2个累计CAD包；对A/B对称候选显式记录`newSide`、端口和目标实例，避免遍历顺序决定方向。
- 真实持久作业`project01-job-9cb5c4c0c647`成功：SS00包60.18秒，GN00包59.74秒，总计120.11秒。两包均3/3配合、独立插入、完全约束、求解干净、保存关闭重开一致、源文件不变。
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-9cb5c4c0c647/packet-runs/packet-002-attempt-01/project01-jj00-ss00-gn00-v8-driving-v1-packet-002.SLDASM`，SHA-256=`0a7f2a8160dad34d050434deb31c5b5fd9a816817b1f0511c309f3f1172d24c9`。
- 闭环证据：`demo/global_assembly_contexts/project01-jj00-ss00-gn00-v8-driving-v1/durable-executor-closure.json`。
- 最终Python全量回归：`836 passed, 3 subtests passed`。碰撞/B-rep未执行。

功能修改意义：同一套自然语言目录、逐模板发布、关系编辑、DAG、持久执行和CAD检查点机制已跨Project05、Project01复用，并能处理新增模组同时依赖两个既有模组的约束组合。

# 2026-10-11 一等模板组合与基座包装缓存

- 全局模组目录新增`templateCombinations`；Project01登记GN00主定位＋SS00防转精确组合，组合后预计剩余自由度0。
- 新目录预览：43个模组、74个端口、42个模板、1个组合、67条兼容边；声明组合闭环重新编译为2个ready事务。
- 新增`global_cad_base_context_cache.py`及缓存导入脚本；缓存键绑定源SHA-256、基座令牌、16值变换和适配器版本，缓存证据和实体均做摘要复核。
- 已导入Project02 A600和Project05 A000两项合格包装缓存。
- Project05真实CAD复跑命中缓存，`executionDecision=reuse_verified_cache`；没有执行新的包装子进程，D000插入约57.69秒，3/3配合、完全约束、保存关闭重开和源文件不变全部通过。
- 输出：`demo/global_assembly_contexts/cache_validation/project05-cad-run/project05-a000-d000-cache-hit.SLDASM`；执行信封同目录。
- 定向回归49项通过；最终全量后端回归：`842 passed, 3 subtests passed`。碰撞/B-rep未执行。

功能修改意义：目录开始原生表达多关系共同定位，执行链同时消除了重复根包装的主要时间浪费；性能优化没有绕过发布授权、配合创建和保存重开门禁。

# 2026-10-11 v10组合发布、Project03审计与命令级解释

- 发布器新增模板组合授权；组合成员必须全部已派生、获逐模板授权且组合声明精确成员、完整定位、零剩余自由度。
- 发布`relation-v10-project01-combination-driving-20261011`，显式授权GN00主定位＋SS00防转组合；旧v9发布继续可验证加载。
- CAD执行授权新增逐包组合完整性检查；部分成员负例在SolidWorks前拒绝。
- 通用DAG编译器直接从`templateCombinations`拉取同一新增模组的补自由度关系；删除旧`completesWithLegacyTemplateIds`提示后仍可正确生成组合事务。
- 新增Project03模板闭合审计：11条安装模板中6条原子闭合候选、5条需语义补全；AE00无原型位姿补齐编译ready，AG00诊断模板因余1自由度且无组合被阻断。
- 新增命令审计摘要：Project01 v10四条自然语言命令4/4映射到模组、端口角色、模板、组合、自由度、DAG和packet。
- 持久步骤证据增加总耗时、CAD耗时、缓存命中和预计节省包装时间字段。
- 定向回归43项通过；最终全量后端回归`846 passed, 3 subtests passed`。本轮未重新执行SolidWorks，未执行碰撞/B-rep。

功能修改意义：多关系组合不再只可解释而是被发布和执行边界强制；跨项目迁移能够识别原型锚点假闭合；自然语言选择结果形成面向用户的可追溯证据。

# 2026-10-11 Project03 AE00 v11驱动发布与通用CAD闭环

- 新增`global_cad_driving_evidence.py`，将真实插入结果分为发布候选、需补checkpoint和阻断三档。
- 修复模板锚点标记只检查说明文字的缺陷；现同时检查旧ID和全局ID，AC00锚点模板被正确阻断。
- 盘点Project03：AD00、AE00、AI00、AH00、AJ00历史结果均通过独立插入和完全约束语义，但旧信封不具备发布级文档生命周期证明。
- AE00当前checkpoint复验成功：非原型初始位姿、无case/leaf anchor、3/3配合、完全约束、保存关闭重开、源文件不变、目标源会话清洁；耗时约78.97秒。
- 发布`relation-v11-project03-ae00-driving-20261011`，仅授权AE00三基准模板。
- 两条自然语言命令编译为1个通用CAD包；项目无关执行器真实复跑约72.01秒，全部门禁通过。
- 最终实体：`demo/global_assembly_contexts/project03-aa00-ae00-v11-driving-v1/cad-run-packet-001/project03-aa00-ae00-v11-driving-v1-packet-001.SLDASM`。
- 闭环报告：`demo/global_assembly_contexts/project03-aa00-ae00-v11-driving-v1/closure-report.json`。
- 最终后端回归：`850 passed, 3 subtests passed`；SolidWorks主进程仍正常响应；碰撞/B-rep未执行。

功能修改意义：第三项目族首次通过同一自然语言编译、不可变发布、通用CAD执行和保存重开链路；同时避免把历史旧证据或锚点假闭合误发布。

# 2026-10-11 Project03 v12 AE00—AD00累计闭环

- AD00以v11 AE00通用输出为源完成checkpoint刷新：独立非原型位姿插入、3/3配合、完全约束、无锚点、源文件不变及保存重开通过，约87.64秒。
- 证据盘点更新为2条发布候选、3条待checkpoint刷新；AC00及其他锚点/残余自由度模板继续阻断。
- 发布`relation-v12-project03-ae00-ad00-driving-20261011`，仅授权AE00、AD00两条模板。
- 三条自然语言命令编译为2个累计CAD包，命令审计完整。
- 持久作业`project03-job-cea5e3c2ac90`成功：packet-001约74.21秒，packet-002约86.88秒，总执行约161.36秒；第二包输入与第一包提交实体完全一致。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-cea5e3c2ac90/packet-runs/packet-002-attempt-01/project03-aa00-ae00-ad00-v12-driving-v1-packet-002.SLDASM`，SHA-256=`cef85fd8dd72d8a9313f7d23b2f65cbd91baac752546b0a06576df522d897819`。
- 闭环报告：`demo/global_assembly_contexts/project03-aa00-ae00-ad00-v12-driving-v1/durable-executor-closure.json`。
- 全量后端回归`850 passed, 3 subtests passed`；碰撞/B-rep未执行。

功能修改意义：第三项目族从单包验证升级为真实累计检查点装配，证明后续模组确实追加在前一CAD结果上。

# 2026-10-11 Project03 v13三包累计闭环与通用任务证据

- 通用CAD清单计划新增命令审计绑定；任务目录在创建和完成阶段自动生成`command-audit.json`与`timing-report.json`。
- 自然语言通用编译器新增DAG落盘和分阶段计时；计时器能够忽略非JSON日志并读取CAD的`PhaseDurationsSeconds`。
- AI00以v12最终实体为输入完成checkpoint刷新：非原型初始位姿、无锚点、3/3驱动配合、2/2距离验证、完全约束、求解干净、源文件不变、保存关闭重开通过，约95.62秒。
- 发布`relation-v13-project03-ae00-ad00-ai00-driving-20261011`，授权AE00、AD00、AI00三条当前证据模板。
- 建立四条自然语言命令和三包CAD事务；任务`project03-job-d7ecc82db4f1`前两包成功，第三包首次因执行器错误要求验证距离出现在驱动配合图而在CAD前失败，并回滚至packet-002。
- 修复通用包执行器：按`applicationMode=validate_only`分离只读关系，驱动图严格匹配3条配合，验证图严格匹配2条距离；恢复时只重跑packet-003。
- 最终任务成功：总执行260.231秒，CAD动作257.644秒，失败尝试0.111秒；保存关闭累计97.611秒，重开复核累计61.208秒。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-d7ecc82db4f1/packet-runs/packet-003-attempt-02/project03-aa00-ae00-ad00-ai00-v13-driving-v1-packet-003.SLDASM`，SHA-256=`dbbd82e7a51a86a3f7145178ca1a4286f8b9b20abddabe8403f2230c0022f639`。
- 闭环报告：`demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-v13-driving-v1/durable-executor-closure.json`。碰撞/B-rep未执行。
- 修复未绑定发布清单的普通自然语言任务审计寻址：按清单`catalogDigest`匹配默认全局目录，并优先读取与上下文同目录、同名的`*.transaction-dag.json`；两类三步/五步非固定顺序任务均能生成完整审计。
- 通用任务计划及单包执行计划现同时输出`requestedDrivingMateCount`、`requestedValidationRelationCount`和`requestedRelationCount`；兼容字段`requestedMateCount`明确只表示真正驱动CAD位姿的关系数。AI00因此显示为3条驱动＋2条验证，而不是5条驱动。
- 最终全量后端回归：`854 passed, 3 subtests passed`。

功能修改意义：Project03自然语言链扩展到三包；通用执行器首次完整证明“自动审计—失败关闭—检查点恢复—驱动/验证分流—统一计时”的闭环。

# 2026-10-11 Project03 v14四包累计闭环

- 在AH00与AJ00之间按证据盘点建议选择AH00：它是标定服务模组，已有直接连接AA00的三基准闭合语义，历史3/3配合、完全约束且无锚点，只缺当前checkpoint证据。
- 首次AH00 checkpoint刷新被安全拒绝：旧有效图仍包含当前v13累计实体中不存在、且与AH00配合无关的AG00。输出副本已关闭并保留为`failed-attempt-01`证据，没有改动v13源实体。
- `run_context_mate_graph_insert.py`新增`--project-target-context`：按目标模组投影执行图，只保留目标、直接驱动上下文和相关配合；禁止为满足旧图而虚构或复制无关原型模组。
- 投影后AH00 checkpoint复验成功：89.32秒、3/3配合、完全约束、无case/叶位姿锚点、求解干净、源文件不变、输出与目标源文档关闭。
- 发布`relation-v14-project03-ae00-ad00-ai00-ah00-driving-20261011`，不可变授权AE00、AD00、AI00、AH00四条驱动模板。
- 新增可按任意已授权token顺序构建Project03累计事务的脚本`build_project03_released_cumulative_transaction.py`；五条自然语言命令生成4个CAD包，命令审计5/5完整。
- 持久作业`project03-job-884766b7b8c5`四包一次成功：AE00 76.59秒、AD00 90.47秒、AI00 97.47秒、AH00 90.90秒，总执行356.14秒，CAD动作352.60秒。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-884766b7b8c5/packet-runs/packet-004-attempt-01/project03-aa00-ae00-ad00-ai00-ah00-v14-driving-v1-packet-004.SLDASM`，SHA-256=`d481a84417724503542fe977b595e1872a0f8b9b7a4c9b3c228d13cdaa590f25`。
- 闭环报告：`demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-ah00-v14-driving-v1/durable-executor-closure.json`；全部13项检查通过。
- 全量后端回归：`855 passed, 3 subtests passed`。碰撞/B-rep未执行。

功能修改意义：累计自然语言装配由三包扩展到四包，并把“有效图含未装入的无关原型模组”从现场故障转化为可复用的目标上下文投影能力；新增模组仍完全由发布端口和配合求解定位。

# 2026-10-11 Project03 v15五包累计闭环

- AJ00发布级checkpoint刷新通过：目标上下文投影后仅依赖AA00，3/3驱动配合、完全约束、无case/叶位姿锚点、求解干净、保存关闭重开及源文件不变均通过。
- Project03当前5条原子闭合候选AE00、AD00、AI00、AH00、AJ00已全部取得当前发布级证据；证据审计结果为`releaseCandidateCount=5`、`checkpointRefreshRequiredCount=0`。
- 发布`relation-v15-project03-five-module-driving-20261011`，只授权上述5条有当前证据的驱动模板；AG00、AB00、AC00继续保持阻断。
- 六条自然语言命令被编译为5个累计CAD包，持久作业`project03-job-ab65b73736c8`一次成功，无失败和回滚。
- 各包CAD动作耗时：AE00约81.97秒、AD00约92.53秒、AI00约98.93秒、AH00约91.81秒、AJ00约89.57秒；总执行约460.68秒，CAD动作约454.80秒。
- 闭环报告14项检查全部通过，包括5/5包提交、检查点连续、6/6命令审计、所有目标完全约束、求解干净、AI00两条只读验证通过、AH00/AJ00各创建3条驱动配合。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-ab65b73736c8/packet-runs/packet-005-attempt-01/project03-aa00-ae00-ad00-ai00-ah00-aj00-v15-driving-v1-packet-005.SLDASM`，SHA-256=`493a76d9fd4d46b5b429f8447645cc699658f94c9c73d713040c196114f31e3c`。
- 闭环报告：`demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-ah00-aj00-v15-driving-v1/durable-executor-closure.json`。
- 全量后端回归：`855 passed, 3 subtests passed`。碰撞/B-rep未执行。

功能修改意义：Project03当前所有无锚点原子闭合候选都已进入同一条可恢复的自然语言累计装配链；系统已证明能够在不复制原型顶层位姿的前提下，把5个独立子装配体连续定位到同一真实CAD结果中。

# 2026-10-11 发布绑定自然语言混合命令与Project01兼容性回归

- 通用自然语言清单编译器新增`releaseManifestPath`输入，命令到模板的解析和CAD任务计划可直接受不可变发布白名单约束；命令行新增`--release-manifest`。
- 修复迁移目录中“同一安装模板两端候选完全对称”造成的假二义性：只对`installation`模板、相同接口类型且各配合端点角色对称的情况合并A/B等价候选；普通距离/对齐关系仍要求人工确认。
- 有序命令序列新增“已有实例关系编辑”分支：当一句话引用恰好两个已安装模组且关系类型不是安装时，原子事务会转入关系预览与提交，不再误判为新增模组。
- 会话台账现能记录关系编辑产生的`connectionId`，因此“安装模组”和“追加配合”可在同一命令审计中追溯。
- Project01真实发布目录兼容性用例通过：`安装JJ00 → 安装SS00 → 安装GN00 → GN00与SS00保持平行`，4条命令生成2个累计CAD包，组合闭合关系落在GN00包中。
- 生成排队任务`project01-job-3463d334efad`；发布权限已验证，命令审计完整，按本轮兼容性边界未启动SolidWorks。
- 全量后端回归：`856 passed, 3 subtests passed`。

功能修改意义：自然语言主线不再局限于“每句话增加一个模组”，已经支持在同一原子序列中混排模组安装与既有模组间关系追加，并在第二项目族上证明发布授权、端口选择和组合闭合均可复用。

# 2026-10-11 通用驱动证据发布器与Project05顺序兼容性

- 新增通用模块`driving_relation_release_publisher.py`和命令行`publish_driving_relation_release.py`；发布输入从链长专用Python常量改为`driving-relation-release-spec/v1`声明文件。
- 规格逐模板声明项目、作用域、全局/旧模板ID、checkpoint证据、预期驱动配合数和可选组合；发布器统一检查目录存在性、模板身份、位姿驱动语义、零自由度声明、证据通过状态和可选库存候选状态。
- 发布器自动生成候选证据、不可变目录副本、发布清单和发布报告；发布阶段不重复启动SolidWorks，碰撞/B-rep保持`not_evaluated`。
- 使用五模板规格发布`relation-v16-project03-generic-driving-20261011`；其目录摘要、5条授权模板和5份验证证据与v15完全一致，证明不再需要v11～v15式链长专用证据脚本。
- Project05发布绑定兼容用例：自然语言`建立A000基础环境 → 将D000安装到A000`绑定v7发布，生成1个D000包，任务`project05-job-f4401985f282`已排队、命令审计完整、CAD未启动。
- Project05非固定顺序语义用例：`M000→F000→P000→G000`与`G000→P000→F000→M000`均生成4个包，顺序分别保留在任务`project05-job-b879015dbbe9`与`project05-job-9102717b152f`中。
- 兼容性汇总11项检查全部通过：`demo/global_assembly_contexts/project05-release-order-compatibility-v1/report.json`。
- 明确边界：Project05当前只有D000具备独立位姿发布授权；其余两组顺序只证明语义编译兼容，不代表可启动发布级CAD执行。
- 全量后端回归：`860 passed, 3 subtests passed`。

功能修改意义：关系发布流程从“每增长一节链就复制一个脚本”升级为数据驱动发布；同时证明发布白名单与非固定顺序编译可以分层验证，不会把未取得真实CAD证据的模板越权放行。

# 2026-10-11 Project05双模板发布与真实顺序互换闭环

- 通用发布器补齐`templateCombinations`校验：组合必须精确匹配成员、成员逐一获授权、完整定位且剩余自由度为0；重复引用同一CAD证据时按文件去重计数。
- Project01、Project05旧发布迁移为声明式规格，分别生成v17组合发布与v18 D000发布；后续不再复制链长专用发布脚本。
- 新增Project05附加模组证据审计。F000/M000/G000历史结果虽为3/3配合和完全约束，但仍依赖案例锚点；P000还缺第三定位关系及严格checkpoint，因此全部先失败关闭。
- 新增非锚点执行图构建器；F000从确定性非原型初始位姿真实插入A000，3/3配合、完全约束、无case/叶位姿锚点、求解干净、源文件不变、保存关闭重开全部通过，约40.94秒。
- 首版F000候选暴露有效图路径不可移植问题；v19仅保留为开发证据，不作为执行基线。v2候选改用工作区相对路径，并发布`relation-v20-project05-d000-f000-portable-driving-20261011`。
- 同一v20发布下完成两条真实累计CAD链：`D000→F000`作业`project05-job-26669ac03021`约132.69秒；`F000→D000`作业`project05-job-5a25aa745c3e`约113.56秒。
- 四个CAD包均为3/3配合、完全约束、无case/叶位姿锚点、保存关闭重开一致、源文件不变；两条最终实体均存在且摘要与证据一致。
- 顺序闭环报告：`demo/global_assembly_contexts/project05-release-permutation-v2/closure-report.json`；新增定向回归9项通过，最终全量后端回归`867 passed, 3 subtests passed`。碰撞/B-rep保持`not_evaluated`。

功能修改意义：Project05从“未发布模板可按不同顺序编译”升级为“两个独立获授权模组可按正反顺序真实累计装配”；同时用非锚点实证和不可变发布证明，结果不是复刻原型顶层位姿。

# 2026-10-11 Project05 M000非锚点升级与三模组顺序闭环

- 在M000 CCD模组与G000功能模组之间优先选择M000：其工艺价值更高，原型端口图已有3条有效安装配合，适合直接验证非锚点闭合。
- M000执行图移除案例锚点和叶位姿锚点，改为确定性非原型初始位姿；真实checkpoint一次通过，约38.91秒，3/3配合、完全约束、求解干净、保存关闭重开、源文件不变和会话清洁均通过。
- Project05附加模组审计正确把M000从“案例锚点阻断”升级为“非锚点证据已通过、原目录待提升”；未直接修改旧模板掩盖版本差异。
- 候选构建器由单目标扩展为可重复`--target`的多目标目录构建；F000与M000候选连同D000基线合并成同一v3目录，均保留各自checkpoint证据。
- 发布`relation-v21-project05-d000-f000-m000-portable-driving-20261011`，授权D000、F000、M000三个独立闭合模板，目录摘要`be9b3e9eafea3c27163d02817b51c08900a19116ea7b85c8a11b61db111d62ac`。
- 自然语言顺序`D000→F000→M000`生成并执行3包任务`project05-job-5ccdb04e298d`，约183.72秒；反向`M000→F000→D000`任务`project05-job-2797a59ca15e`约161.63秒。
- 六个CAD包全部通过3/3配合、完全约束、无case/叶位姿锚点、求解干净、源文件不变和保存关闭重开；两个最终实体均存在且摘要匹配证据。
- 顺序汇总器改为参数化`--case/--release-id/--output`，不再写死两模组任务；v3报告位于`demo/global_assembly_contexts/project05-release-permutation-v3/closure-report.json`。
- 新增定向回归11项通过，最终全量后端回归`869 passed, 3 subtests passed`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：Project05自然语言自由组合从两个附加模组扩展到三个，并在同一不可变发布下完成真实正反顺序长链；候选目录和闭环报告也从单案例脚本升级为可复用的多目标/多链工具。

# 2026-10-11 Project05 G000柔性语义与四模组顺序闭环

- G000从确定性非原型初始位姿执行无锚点checkpoint，3/3配合、外部安装约束状态通过、求解干净、源文件不变、保存关闭重开一致；其内部机构按原图声明保持`swComponentFlexibleSolving`，因此`TargetFullyConstrained=false`不是外部安装失败。
- 统一真实CAD证据评估、不可变发布门禁和排列闭环报告：刚性模组要求完全约束；柔性模组必须满足`TargetConstraintStateAccepted=true`与`ComponentSemanticsMatch=true`，并单独记录内部柔性观察，不能把内部运动误判为整模组欠约束。
- 首次v22尝试因旧发布门禁仍硬性要求完全约束而失败关闭，目录只保留候选证据；修复并新增回归后以新ID发布`relation-v23-project05-four-addon-portable-driving-20261011`，未覆盖失败版本。
- v5候选目录统一合并D000、F000、M000、G000四条已验证模板，目录摘要`530aa2d9055ed368c09450504930cfe9fd540036db131298d341ee4d8dc45a94`。
- 正序`D000→F000→M000→G000`真实作业`project05-job-79b398759907`四包一次通过，总执行约277.59秒；逆序`G000→M000→F000→D000`作业`project05-job-b1c6ba3274a5`四包一次通过，总执行约239.25秒。
- 八个CAD包均创建3/3驱动配合、无case/叶位姿锚点、源文件不变、保存关闭重开及输出摘要复核通过；G000在链首和链尾均保持合法内部柔性。
- 闭环报告：`demo/global_assembly_contexts/project05-release-permutation-v4/closure-report.json`；两条最终实体均存在。碰撞/B-rep保持`not_evaluated`。
- 定向回归25项通过，最终全量后端回归`874 passed, 3 subtests passed`。

功能修改意义：自然语言自由组合由三个刚性附加模组扩展到包含柔性机构的四模组真实CAD链；系统开始正确区分“整模组安装定位”与“子装配体内部运动”，并以正反顺序证明发布端口不依赖固定插入次序。

# 2026-10-11 Project05 P000剩余自由度定量审计

- 刚体配合自由度分析器新增确定性零空间基，除报告约束秩和剩余自由度数量外，还能指出未被约束的主导平移/转动分量。
- Project05附加模组审计现自动加载各目标有效图并附带`dofAnalysis`，不再仅凭“两条/三条配合”的数量判断机械闭合。
- P000现有`重合43＋平行14`的刚体约束秩为4/6，明确剩余`tx`、`tz`两个平移自由度；报告新增`RIGID_BODY_DOF_NOT_CLOSED`阻断。
- 结论：P000不能靠一次非原型初始位姿运行直接升级为发布模板；需新增两个独立方向的位置基准，或新增能一次约束二维位置的孔/销/槽接口，再执行checkpoint。
- 定向测试8项通过，最终全量后端回归仍为`874 passed, 3 subtests passed`。

功能修改意义：下一步机械语义采集有了明确目标，不再通过反复启动SolidWorks试错，也避免用原型位姿把两个真实剩余自由度掩盖成“已安装”。

# 2026-10-11 Project05 P000自由槽闭合与五模板发布

- 从原型配合定义确认`槽口6`为`swSlotMateConstraintOption_Free`：它只限制横槽方向和姿态，允许P000沿槽方向平移；`重合43＋平行14＋槽口6`的约束秩为5/6，剩余`tx`。
- 从已导出的P000/A000真实面目录选择两个稳定侧平面，得到X向安装距离`345.122535 mm`；该值明确标记为`prototype_estimate / notVendorDatum / productionReady=false`。
- 追加上述距离后，静态刚体约束秩达到6/6；独立插入checkpoint创建4/4配合、完全约束、求解干净、无case/叶位姿锚点，并通过保存、关闭、重开、参数复核和源文件不变检查。
- 通用CAD事务执行器现将“两个端点＋显式`SlotConstraint`”的槽口配合识别为可重建关系；Free的枚举值0不再被误判为空值。
- 修复重复引用同一子装配体文件时的重开解析：优先按插入时实例名绑定新目标，再解析其余上下文，避免同路径多个P000实例产生二义性。
- 建立P000八端点语义包和四配合模板`P000_to_A000_nonanchor_driving_v2`，发布`relation-v25-project05-five-addon-portable-driving-20261011`，同时授权D000/F000/M000/G000/P000五个附加模组。
- `v24`发布保留为路径缺陷审计证据：其P000有效图只登记局部文件名，不能由通用执行器解析；`v25`改为工作区相对路径，后续执行只能绑定v25或更高版本。
- 两条真实CAD累计链全部通过：`P000→F000`作业`project05-job-86d75a60f96b`约74.47秒，`F000→P000`作业`project05-job-fa4696e9edc0`约70.35秒；四个包均通过配合数量、约束状态、求解、保存重开、源文件保护和输出摘要门禁。
- 五附加模组非固定顺序链`P000→G000→M000→F000→D000`作业`project05-job-95635fd2a287`一次成功，总执行约208.59秒；P000四配合与G000内部柔性在同一累计实体中均保持合法语义。
- 五包耗时依次约35.79、38.12、41.63、37.59、54.83秒；每包均消费前一提交检查点，未发生失败、回滚或重新执行。
- 五模组闭环报告：`demo/global_assembly_contexts/project05-release-five-addon-pgmfd-v7/orchestrator-closure.json`；最终实体为该作业`packet-005`的SLDASM。
- 顺序闭环报告：`demo/global_assembly_contexts/project05-release-permutation-v5-p000-f000/closure-report.json`。碰撞/B-rep保持`not_evaluated`。
- P000首包命中A000只读基座缓存，估计避免约227.71秒重复准备；本次首包约35.10秒。
- 最终全量Python回归为`885 passed, 3 subtests passed`；C#定向回归为`62 passed`。

功能修改意义：P000从“知道还缺沿槽定位”升级为“具有可解释参数来源、可发布语义端口和真实正反顺序累计CAD证据”；五模组长链进一步证明P000可与刚性、柔性模组共同按非固定顺序连续装配，系统不再依赖原型Transform或项目固定步骤补位。

# 2026-10-11 Project05 N000自由槽审计、六模板发布与顺序闭环

- 从Project05原型确认N000与A000的安装关系为`重合42＋平行13＋槽口4`；`槽口4`是`SlotConstraint=Free`，槽长约50 mm，槽轴沿世界X方向。
- N000侧配合端点是槽壁平面，A000侧是定位销圆柱面。自由度分析器已支持“平面槽壁＋圆柱销”组合，并使用显式槽轴和参考点计算槽口约束。
- 原始三关系刚体秩为5/6，唯一剩余自由度为沿槽方向的`tx`；因此原型中的Free槽口不能单独证明N000安装位置唯一。
- 从已导出的N000/A000真实面目录选取稳定侧平面，得到X向距离`465 mm`，并明确标记为`prototype_estimate / notVendorDatum / productionReady=false`。加入该距离后约束秩为6/6。
- 首次真实CAD checkpoint虽然机械上4/4配合、完全约束、保存重开均通过，但发布证据把新建距离配合误列为“应抑制的源配合”，流程因此失败关闭。实现已修正为只抑制原装配中已有的`重合42、平行13、槽口4`。
- 修正后的实体为`demo/semantic_ports/project05_n000_locator_discovery_v1/cad/project05-n000-derived-x-distance-checkpoint-v2.SLDASM`；约52.22秒完成，4/4配合、完全约束、求解干净、无case/叶位姿锚点、源文件不变，并通过保存关闭重开复核。
- 建立N000非锚点驱动端口`N000_to_A000_nonanchor_driving_v2`，并发布`relation-v26-project05-six-addon-portable-driving-20261011`；同一不可变发布共授权D000/F000/M000/G000/P000/N000六个模板。
- 组合候选生成器曾把F000/M000/G000错误指向v6目录，通用发布器因缺少模板而拒绝发布；修正为按各模板实际版本目录聚合后，v26才成功生成，证明发布门禁能阻止不完整目录进入运行态。
- 两条真实累计CAD链全部通过：`N000→P000`作业`project05-job-5e6978657ca2`约74.40秒，`P000→N000`作业`project05-job-17ff4d4d9055`约72.67秒；四个包均创建4/4配合并通过完全约束、求解、保存重开、源保护和无锚点检查。
- 顺序闭环报告为`demo/global_assembly_contexts/project05-release-permutation-v6-n000-p000/closure-report.json`；碰撞/B-rep按当前主线保持`not_evaluated`。
- 最终全量Python回归为`889 passed, 3 subtests passed`。

功能修改意义：N000不再依靠原型初始位姿暗中固定Free槽口方向；系统能够识别真实“槽壁平面＋定位销”接口、定量指出剩余自由度，并以显式工程标量、不可变发布和正反顺序实体链证明该端口可被自然语言累计装配流程复用。

# 2026-10-11 Project05 K000、B000审计与8/8发布闭环

- K000原型安装束为`重合4＋平行2＋同心5`。刚体雅可比秩为6/6：重合贡献3个独立约束、平行补1个、同心补2个，无剩余自由度，不需要新增原型估计尺寸。
- K000去案例锚点checkpoint从确定性非原型初始位姿插入，3/3配合、完全约束、求解干净、保存关闭重开一致、无case/叶位姿锚点，源装配不变；执行约53.40秒。
- K000候选与v26六模板完整聚合后发布`relation-v27-project05-seven-addon-portable-driving-20261011`。`K000→N000`和`N000→K000`真实累计链分别约78.27秒和75.41秒，均通过同一发布授权及逐包生命周期门禁。
- 自然语言首次写成“建立A000基础环境”时，因Project05/06均存在A000而在CAD前返回`MODULE_SELECTION_REQUIRED`；改为“项目05 A000机架基础环境”后唯一解析。这一失败关闭证实跨项目同名模组不会被静默误选。
- B000原型安装束为`重合37＋同心1＋平行1`，刚体雅可比秩同样为6/6。B000在源装配中为柔性求解组件，端口审计明确区分“整组相对A000的外部安装自由度已闭合”和“组内Z轴机构运动语义保留”。
- B000去案例锚点checkpoint通过：3/3配合、外部完全约束、组件语义匹配、求解干净、保存关闭重开一致、无case/叶位姿锚点；执行约58.05秒。
- 发布`relation-v28-project05-all-eight-addon-portable-driving-20261011`，一次性重新验签B000、D000、F000、G000、K000、M000、N000、P000共8个模板，发布摘要`9f84fb069688a0fae6f2a7eed91c0fe9ec05b9f806174ab72d09bd8d25f51224`。
- `B000→K000`与`K000→B000`真实累计链分别约78.57秒和80.10秒；两条最终SLDASM存在，全部4个包通过配合计数、约束状态、求解、保存重开、源保护及无锚点检查。
- K000/N000顺序报告：`demo/global_assembly_contexts/project05-release-permutation-v7-k000-n000/closure-report.json`；B000/K000顺序报告：`demo/global_assembly_contexts/project05-release-permutation-v8-b000-k000/closure-report.json`。
- 最终全量Python回归为`895 passed, 3 subtests passed`；碰撞/B-rep继续为`not_evaluated`。

功能修改意义：Project05当前定义的8个待装模组全部从“原型位姿案例”升级为有面端点、配合束、自由度证明、非锚点真实CAD证据和不可变发布授权的可执行语义端口；刚性顶升模组与柔性龙门运动组均能由自然语言按非固定顺序累计装配。

# 2026-10-11 Project02 A800/A180发布级自然语言累计装配闭环

- 完成A800、A180严格无锚点checkpoint：均为3/3配合、完全约束、求解干净、源文件不变、保存关闭重开通过，耗时约56.68秒和54.84秒。
- A180曾追加X距离以消除静态残余自由度，但真实CAD报告过约束；回退为原始`重合34＋距离24＋Free槽口3`后通过，确认高级配合应由真实CAD裁决。
- 新增Project02双目标候选构建器和2项自动测试；候选模板进入全局目录兼容矩阵。
- v29因有效图路径不可移植在CAD启动前失败关闭；修复后新建v30不可变发布，没有覆盖失败记录。
- 三句自然语言命令成功生成两包真实CAD累计链，作业`project02-job-d13cf4819eaa`约73.09秒完成，最终实体保存并重开验证通过。
- 闭环报告：`demo/global_assembly_contexts/project02-release-a800-a180-v2/closure-report.json`；碰撞/B-rep为`not_evaluated`。

功能修改意义：Project02的A600→A800→A180已不再依赖原型顶层位姿或人工补位，成为可以被自然语言和通用持久编排器直接调用的发布级机械装配链。

# 2026-10-11 Project02 A500与A700无锚点端口扩展

- A500安装束`重合13＋宽度4＋距离27`从确定性非原型初始位姿通过严格checkpoint：3/3配合、完全约束、求解干净、无case/叶位姿锚点、源文件不变、保存关闭重开一致，约36.71秒。
- A500原语义包还包含面向A700的50 mm只读间距关系。执行图现将其登记为延迟验证，等A700实际存在后再测量；该关系不驱动A500安装，也不再错误阻断当前步骤。
- v31不可变发布授权A800、A180、A500三条端口；自然语言作业`project02-job-1df2c96d2a7c`按A800→A180→A500完成三包真实累计CAD执行，总计约111.49秒。
- 三步闭环报告：`demo/global_assembly_contexts/project02-release-a800-a180-a500-v3/closure-report.json`；最终实体位于该作业`packet-003`目录，摘要`400908835e580ee3acca1b53f8008de71d19654803e58ee61268997618755414`。
- A700旧执行图含一个整模组案例锚点和两个内部叶位姿锚点。新执行图全部移除，从确定性非原型初始位姿使用`平行1＋平行2＋距离6＋重合38＋宽度10＋距离29`六配合求解。
- A700严格checkpoint一次通过：6/6配合、外部安装状态接受、内部柔性语义保持、求解干净、无锚点、源文件不变和保存关闭重开一致，约46.99秒。
- 新候选目录把A800/A180/A500/A700四条已验证端口合并，发布`relation-v32-project02-a800-a180-a500-a700-portable-driving-20261011`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：Project02累计装配从“传输＋扫描”扩展到校准和柔性清洁/称重服务模组；安装关系、未来工艺验证与内部机构运动首次被明确分层。

# 2026-10-11 Project02 A300无锚点端口与五包累计闭环

- A300现有三配合束静态自由度为6/6，但旧图用原型case锚点选择距离配合的正确半空间。
- 新执行图移除A300 case锚点，从确定性非原型初始位姿求解，并保留`距离20`已经CAD验证的归一化创建方向。
- 严格checkpoint约43.11秒通过：3/3配合、完全约束、参数重开一致、求解干净、无case/叶位姿锚点、源文件不变。
- 新候选目录合并A800/A180/A500/A700/A300五条端口，发布`relation-v33-project02-five-addon-portable-driving-20261011`。
- 自然语言五包作业`project02-job-68696a91e2bc`一次通过，总执行约196.87秒；最终实体摘要为`7d1ea91213844fb4e55e6f3224c138424cc85bd8fb9975b57c81f6a6d12ade32`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-five-addon-v5/closure-report.json`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：系统可以显式表达并复核距离配合的安装分支，A300不再需要原型顶层位姿补位；Project02发布级自然语言链扩展至五个附加模组。

# 2026-10-11 Project02 A200权威槽口验证与六包累计闭环

- A200原始安装束为`重合26＋槽口1＋槽口2`，两个槽口为定距模式；旧执行图仍包含A200 case锚点。
- 静态自由度模型因端点目录缺少槽轴方向而不能计算两个高级槽口；流程明确把这一情况标记为“分析元数据不足”，没有自动追加可能过约束的关系。
- 去case/叶位姿锚点后，真实CAD checkpoint约51.27秒通过：3/3配合、完全约束、求解干净、参数重开一致、源文件不变。
- A200加入六目标候选目录，发布`relation-v34-project02-six-addon-portable-driving-20261011`。
- 自然语言六包作业`project02-job-0761271ce4f9`一次通过，总耗时约244.12秒；最终实体摘要为`639bfbd5215090cdb299aff166b8969f954b99b47204eebbc30633947db1fa8d`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-six-addon-v6/closure-report.json`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：系统能够在静态分析不完备时，以严格范围内的真实CAD证据安全裁决高级配合束；Project02发布级累计装配扩展至六个附加模组。

# 2026-10-11 Project02 A100与七包自然语言累计装配闭环

- 新增`build_project02_a100_nonanchor_checkpoint_graph.py`，从A100顶层安装图投影A600/A100，只保留`重合8、重合9、距离9`。
- 删除全部case/叶位姿锚点并改用确定性初始位姿；静态外部刚体自由度为6/6，同时强制保留A100柔性求解语义。
- A100真实checkpoint成功：3/3配合、完全约束、组件语义一致、求解干净、保存关闭重开一致、源文件不变，约78.79秒。
- 候选目录扩展至七个附加模组，发布`relation-v35-project02-seven-addon-portable-driving-20261011`，发布摘要`c50f978e95a95a753c703e8d6bc30934b67eb89d587dd522956f01d7763c62d6`。
- 自然语言持久作业`project02-job-3a22a673ec04`一次完成A800→A180→A500→A700→A300→A200→A100七包真实累计装配，总耗时`308.3974 s`。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project02-job-3a22a673ec04/packet-runs/packet-007-attempt-01/project02-release-seven-addon-v7-packet-007.SLDASM`，SHA-256为`c9050b327e650fe2f1c62ed38e6d6acf54fe30d76a5275f55d3d4b13505b0ed5`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-seven-addon-v7/closure-report.json`；碰撞/B-rep依照当前主线保持`not_evaluated`。
- 新增A100执行图单测并扩展七目标候选测试；全量回归在加入A100前为`906 passed, 3 subtests passed`，加入后将重新执行。

功能修改意义：龙门首次以“外部安装闭合、内部运动保留”的方式进入通用自然语言长链，证明系统不需要复制原型内部叶位姿也能重建主设备结构。

# 2026-10-11 Project02双T401与九包自然语言累计装配闭环

- 新增T401无锚点图构建器与单测。T401-1连接A600，静态自由度由5/6补齐到6/6；T401-2连接A200，静态自由度由3/6补齐到6/6。
- T401-1严格CAD checkpoint约73.42秒完成，T401-2约48.95秒完成；均为3/3配合、完全约束、求解干净、无case/叶位姿锚点、源文件不变并通过保存关闭重开。
- 新增两个T401候选包构建器，发布`relation-v36-project02-nine-addon-portable-driving-20261011`；发布摘要`dedbfaa72726fa08999117d38974d1967c6ccc32b05302a4b7a173fa323ecdb8`，授权9条驱动模板。
- 修复自然语言解析器：多个被提及定义都已存在时，若只有一个仍有声明实例容量，则将其唯一识别为新增实例。对应回归覆盖“A200已满、T401仍可添加第二套”的场景。
- 10句自然语言命令成功编译为9包持久作业`project02-job-28dac4c3a894`；A800→A180→A500→A700→A300→A200→A100→T401-1→T401-2全部一次成功，总耗时`409.164366 s`。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project02-job-28dac4c3a894/packet-runs/packet-009-attempt-01/project02-release-nine-addon-v8-packet-009.SLDASM`，SHA-256为`3422d91065a446d0294f5f44b600f572ff4d848e5840a6979099b6429c64b482`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-nine-addon-v8/closure-report.json`；碰撞/B-rep依照当前主线保持`not_evaluated`。
- 定向回归`12 passed`；全量后端回归`911 passed, 3 subtests passed`。

功能修改意义：主线从“七个不同模组直接连接A600”扩展到“同一T401定义的两个实例分别连接A600和A200”，自然语言、端口目录、发布、持久编排及真实CAD证据已贯通非星形累计装配。

## 2026-10-11 双T401暂停恢复与通用组件语义报告

- 首次用步骤汇总证据创建第8包起始作业时被种子门禁拒绝；未启动CAD。改用`execution-envelope.json`后，同一幂等作业`project02-job-4885035c7bc0`完成种子验签。
- 第8包T401-1约52.09秒成功提交后主动暂停；恢复作业仅执行第9包T401-2，约50.88秒成功，两个步骤尝试次数均为1，总执行约103.32秒。
- `build_global_cad_manifest_orchestrator_closure.py`新增逐包组件求解语义摘要：外部安装状态、完全约束观察、求解干净、组件语义匹配、内部刚性/柔性模式及柔性保持结论。
- 新增1项闭环报告自动测试；Project02真实报告确认A700、A200、A100内部柔性保持，全部9包外部安装约束状态被接受。
- 汇总文件：`demo/global_assembly_contexts/project02-release-nine-addon-v8/orchestrator-closure.json`；碰撞状态仍为`not_evaluated`。
- 最终全量后端回归：`912 passed, 3 subtests passed`。

功能修改意义：验证了重复实例非星形长链能够安全暂停和继续，同时把“外部定位闭合、内部运动保留”提升为通用证据字段。

## 2026-10-11 跨项目关系拓扑审计与长链参数来源摘要

- 新增`relation_topology_audit.py`与`build_relation_topology_audit.py`，对项目配置中的`requires`和真实有效配合图中的`ModuleTokens`分别建模。
- 自动测试覆盖：工艺依赖不得臆造机械边、锚点图不得冒充便携非星形关系、未知模组必须显式报告、组合模组成员后缀需归一到功能模组。
- 已生成`demo/global_assembly_catalog/relation-topology-audit-v1.json`，审计Project01/02/03/05共70个有效图文件。
- 审计确认Project01 GN00—SS00、Project02 A200—T401和A500—A700具有无位姿锚点的非星形机械边；Project03与Project05当前有效图没有独立非星形机械边。
- Project03 AI00→AE00、AH00→AG00等依赖只表示工艺或顺序上下文；真实配合仍直接连接AA00。流程不再把这些依赖误报为跨模组安装接口。
- 通用编排闭环报告新增`parameterAuthority`摘要，按长链实际模组列出参数要求、基线权威等级和证据完整性；该信息当前不作为Demo执行门禁。
- 已重新生成Project02九包/暂停恢复报告：完整链显示1项`cad-measured`、7项`prototype-calibrated`模组参数来源；重复T401按同一参数要求聚合。
- 定向回归：关系拓扑4项、参数权威与闭环报告5项全部通过；碰撞/B-rep未执行。

功能修改意义：跨项目扩展开始依据真实机械图而不是文字依赖猜边；长链报告同时具备“怎么连接、是否有锚点、参数从哪里来”的可审计信息。

## 2026-10-11 Project01拓扑验签发布与真实非星形累计装配

- 通用驱动发布器新增可选拓扑前置条件：`relationTopologyAuditPath`绑定机器可读审计，`requiredMechanicalEdges`声明必须存在的机械边及是否要求无位姿锚点证据。
- 自动回归证明：GN00—SS00真实边可发布；仅存在于`assemblyPolicy.requires`的BD00→GN00依赖不能冒充机械边，发布会失败关闭。
- 生成不可变发布`relation-v37-project01-topology-attested-combination-driving-20261011`，摘要`a810189da19bcb7497e3f1aa881c6ca314eea235ce6f35abeaf5c36635b9045f`。
- 以四句自然语言创建作业`project01-job-e14773eac13f`，两包分别插入SS00和GN00；GN00包同时创建对JJ00的主定位和对SS00的防转平行关系。
- SS00包耗时88.68秒，GN00包耗时86.69秒，总执行175.54秒；两包均3/3配合、约束状态接受、求解干净、保存关闭重开及参数复核通过，未使用case锚点。
- 最终实体SHA-256：`59772f4d1aabab53956315267ce37a5b39668d0126cd039a9bbaaf4c037ea87c`；闭环报告为`demo/global_assembly_contexts/project01-topology-attested-nonstar-v1-orchestrator-closure.json`。
- Project01尚未建立参数权威注册表，因此闭环报告诚实返回`parameterAuthority.status=not_registered`，但不阻塞当前Demo。
- 最终全量后端回归：`917 passed, 3 subtests passed`；碰撞/B-rep仍为`not_evaluated`。

功能修改意义：同一套自然语言、发布、持久编排和CAD执行机制已在Project01与Project02两种不同非星形结构上通过，且发布层可以阻止把工艺依赖误当配合。

# 2026-10-11 机械边语义分级与Project02混合安装/验证实证

- 新增`relation_topology_audit.py`语义分级：单模板驱动、模板组合成员、只读验证、不完整旧驱动和无模板分别报告；生成`demo/global_assembly_catalog/relation-semantic-topology-audit-v2.json`。
- 审计汇总为31条可驱动机械边、1条只读验证边、1条组合闭合成员边、12条不完整旧驱动模板。Project01 GN00—SS00由模板组合闭合；Project02 A500—A700只允许只读验证。
- 修复自然语言现有实例关系编译：出现“验证/校验/检查/核对/测量”时生成`VERIFY_RELATION`，发布边界分别计算驱动授权与验证授权。
- 11条Project02自然语言命令生成10包作业`project02-job-18edf66ae566`；前9包一次成功，耗时合计约408秒，第10包只读验证约133秒失败。
- 失败测量：期望`0.05 m`，实际`1.127733027490121 m`，误差`1.077733027490121 m`；端点均恢复成功、源装配体SHA未变化、无配合修改，第9包实体安全保留。
- 初步审计确认A700为`swComponentFlexibleSolving`且配合引用`A710004`运动叶件；后续顶层位姿证据进一步证明，首要失败发生在A700外部安装位姿，而不是仅发生在内部工艺状态。

功能修改意义：系统没有把“关系存在”误提升为驱动配合，也没有通过改尺寸或搬模组掩盖失败；初步诊断随后由顶层位姿证据继续校正。

# 2026-10-11 外部位姿前置门禁与只读关系快检

- 新增`relation_validation_preconditions.py`和版本化目录`relation-validation-preconditions-v1.json`；Project02距离8现在要求`project02/a700/external-placement-equivalence`证据。
- v3快速探针记录顶层位姿：A500最大变换差约`6.77e-15`，A700整体沿Z偏移`1.177733 m`。根因报告升级到v2并优先诊断`failed_with_external_module_pose_branch_mismatch`，不再提前归因于内部状态。
- 刚性求解试验创建6/6配合且参数一致，但A700仍未完全约束、顶层偏移`0.134183 m`，距离8测得`0.084183 m`；据此否定“强制刚性即可修复”。
- 新增`relation_driving_safety.py`和`relation-driving-safety-v1.json`，运行时撤销v33/v36中的A700不安全驱动模板。相同11条命令以v11重新编译，`0.238150 s`内在CAD和作业创建前返回驱动撤销及外部位姿证据缺失两项明确阻塞。
- 新增`VerifyRelationsInAssemblyContextFromMateGraph`及Python v3运行封套；校验只打开保存检查点、解析端点并测量，不再重建、保存、关闭重开CAD副本。
- 现场快速探针耗时`9.776 s`，SolidWorks内部阶段为：打开/解析`5.66 s`、测量`1.63 s`、关闭`0.58 s`；与旧路径约`133 s`相比降低约92.6%，测量结果完全一致。
- 新增`relation_validation_state_audit.py`与命令行分析器；机器可读报告现在先比较端点所属模组顶层位姿，只在外部位姿稳定后才允许诊断内部状态。
- 测试：相关Python定向回归58项通过；SolidWorks MCP App Release构建0警告0错误；桥接层非集成测试367项通过。完整桥接测试中的既有可视化集成用例因测试客户端未暴露`ResolveComponentTarget`失败，与本轮改动无关，已中止其余长时集成测试并保留说明。
- 全量后端回归最终为`933 passed, 3 subtests passed`。
- 碰撞/B-rep未执行，保持`not_evaluated`。

功能修改意义：错误从“10包真实CAD运行到最后才发现”前移到“约0.24秒编译期明确拒绝”；更重要的是，系统能区分“配合参数一致”和“柔性模组顶层真正就位”，不会继续发布已由实体验据证伪的驱动模板。

# 2026-10-11 柔性驱动证据发布规则加固

- `global_cad_driving_evidence.py`新增`portablePlacementProven`与外部位姿见证分类；柔性目标仅有`TargetConstraintStateAccepted=true`时，仍可说明CAD检查点执行完成，但残余自由度标记为`unclassified_without_external_placement_witness`，不得再声称外部安装已闭合。
- 通用不可变发布器在模板声明`internalFlexibilityPreserved=true`时，新增`externalPlacementEquivalence`硬检查；后续柔性模板没有外部位姿等价证据将无法发布。
- 新增`reassess_driving_insert_portability.py`并对A700历史检查点复审：历史检查点本身通过，但`portablePlacementProven=false`；报告为`demo/semantic_ports/project02_a700_nonanchor_v1/a700-portability-reassessment-v2.json`。
- 历史v33/v36发布保持不可变；运行时安全目录负责撤销已证伪模板，新发布规则负责阻止同类模板再次进入不可变发布，形成“历史可审计＋运行时止损＋未来发布防复发”的三层闭环。

功能修改意义：本轮不仅拦住一个A700案例，还修复了证据模型中的普遍性漏洞——“柔性组件仍有自由度”必须证明这些自由度只属于内部机构，不能靠布尔接受值自动推断。

# 2026-10-11 A700项目级标定回退短链闭环

- 从v36作业第3包的`A600+A800+A180+A500`检查点出发，用`static_snapshot_effective.json`重新插入A700；该策略明确使用1个Project02 case位姿锚点和2个内部叶状态锚点，不宣称跨项目可移植。
- 插入事务耗时`39.35 s`：独立A700实例插入、完全约束、求解干净、保存关闭重开通过；结果为`demo/semantic_ports/project02_a700_nonanchor_v1/project02-a700-calibrated-fallback-v1.SLDASM`。
- 随后使用只读快检在`5.06 s`内测得距离8为`0.04999999999999682 m`，误差`3.18e-15 m`；A700顶层最大位姿差`1.11e-16`，源文件未变化且无配合修改。
- 机器可读策略决策为`a700-driving-strategy-decision-v1.json`：无锚点候选撤销、强制刚性方案拒绝、Project02标定快照作为显式回退；`automaticSelectionAllowed=false`，避免把项目特例伪装成通用语义端口。

功能修改意义：主线既不会继续执行错误的无锚点模板，也保留了一个已由当前CAD链复测通过的Project02 Demo路径；后续可在不阻塞其他模组自然语言装配的情况下，单独研发A700真正可移植端口。

# 2026-10-11 A700显式项目回退的自然语言—持久任务—真实CAD闭环

- 新增显式驱动策略选择：未确认继续阻断；只有模板/策略匹配且`confirmed=true`时启用Project02标定快照。
- 新增`calibrated_static_snapshot_insert`通用事务策略，绑定图和验证证据SHA-256，并在执行计划中声明`portable=false`。
- 编排器新增回退专用验收：case锚点、2个叶姿态锚点、约束状态和保存重开全部通过才提交检查点。
- 自然语言编译`project02-explicit-a700-fallback-v14`成功，耗时`0.186045 s`，生成4包作业`project02-job-b261643c012a`。
- 真实CAD长链A800→A180→A500→A700一次成功，总耗时`163.834979 s`；A700包耗时约`42.55 s`。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project02-job-b261643c012a/packet-runs/packet-004-attempt-01/project02-explicit-a700-fallback-v14-packet-004.SLDASM`。
- 只读复测距离8为`0.0499999999999968 m`，误差约`3.18e-15 m`，验证耗时`5.2515 s`。
- 定向回归`45 passed`；最终全量后端回归`938 passed, 3 subtests passed`，耗时`85.27 s`。
- 碰撞/B-rep未执行，保持`not_evaluated`。

功能修改意义：A700已证伪的旧模板不会再被静默执行；项目特例可经显式确认进入统一自然语言和持久编排链，同时仍与真正通用、去原型的语义端口保持清晰边界。

# 2026-10-11 主线回归全目录语义端口覆盖

- A700可移植性改为独立已知问题，不再阻塞其他模组端口接入；已有Project02显式标定回退继续保留，且维持`portable=false`边界。
- 开发主线调整为：导出原型同层级模组配合关系，恢复配合几何端点，以机械知识区分安装接口、工艺接口和内部运动关系，再形成全局语义端口、兼容类型及复合安装模板。
- 新增覆盖质量分层：候选发现、稳定恢复、兼容连接、外部位姿闭合、真实CAD验证。禁止用“每个模组至少有一个端口”代替完整装配能力。
- 端口数量由真实机械接口决定；通过端口类型和兼容规则复用模板，不对所有模组对进行二次方穷举。

功能修改意义：后续投入优先扩大自然语言自由组合的机械知识覆盖面，避免继续被单个柔性模组专项牵制。

# 2026-10-11 全目录模组角色与语义端口半自动初标

- 汇总当前全局目录中的43个模组、74个语义端口、39个关系模板和61条兼容连接，并结合项目01/02/03/05/06工艺PPT、项目04参考PPT及双阀点胶需求表完成角色与端口初标。
- 生成审阅工作簿：`outputs/module_role_port_review_20261011/全目录模组角色与语义端口人工审阅表_v1.xlsx`。
- 工作簿包含概览、模组角色简表、人工审阅、端口明细、依据与规则五个工作表；黄色单元格为人工输入区。
- 从43个模组中筛出15项优先审阅项：9项P0（当前无端口，均为Project06）和6项P1（复合角色、部分覆盖或已知专项边界）。
- 公式错误扫描结果为0；五个工作表均完成渲染预览检查。

功能修改意义：把全目录覆盖从逐模组手工摸索转换为“系统先生成角色/端口建议—人工只审阅不确定项—确认后批量进入端口补齐”的短反馈闭环。

# 2026-10-12 建议角色批量接受

- 用户暂时接受人工审阅清单中的全部15项建议角色。
- 已将15项“人工确认角色”回填为系统建议角色，并将审阅状态更新为“角色已确认，其他待审”。
- 独立装配判断、端口集合和几何端点没有随本次操作自动确认，仍保留为下一轮审阅内容。
- 原工作簿被查看程序占用，未强制覆盖；另存为`全目录模组角色与语义端口人工审阅表_v1_已接受建议角色.xlsx`。
- 更新版完成公式错误扫描和渲染检查：建议角色已接受15项，其他项目仍待审15项，公式错误0项。

功能修改意义：角色分类已从候选状态转为当前开发基线，后续可直接围绕安装端口、工艺端口和兼容关系补齐开展工作，不再重复确认模组角色名称。

# 2026-10-12 跨项目同角色模组替换MVP

- 新增独立角色覆盖层：43/43模组角色已写入机器可读配置，原权威目录保持不变。
- 新增端口规范覆盖：74/74既有语义端口获得接口类别、用途、槽位角色与端点角色；原接口事实未被覆盖。
- 新增兼容判定与候选目录生成：只有主角色、接口类别、驱动拓扑、定位特征几何不变量、可移植性与零剩余自由度均满足时才生成替换关系。
- 选定Project03 AH00替换Project01 BD00作为首个MVP。两者均使用支承面和双定位孔，且双定位孔中心距均为50 mm；离线编译得到1个事务包、3条驱动配合，无阻塞项。
- 新增后端预览API和可重复构建脚本，输出到`demo/cross_project_substitution/mvp-v1/`。
- 第一次实体作业在0.13秒内失败关闭：事务包缺少唯一有效配合图，SolidWorks未被调用，也没有输出需要回滚。
- 新增跨项目有效图组合器，将Project03 AH00三个源端点与Project01 JJ00三个目标槽位端点组成两模组三配合执行图；未使用原型顶层或叶级位姿锚点。
- 修正后计划预检为`exact`：目标`FL9A24D063AH00`、基座`JJ00`、请求/有效图均为3条配合。
- 真实作业`project03-job-d75711e079d8`成功，总耗时185.60秒，CAD适配器32.43秒；3/3配合、完全约束、求解干净、保存关闭重开、参数一致和源文件保护均通过。
- 新实体装配体SHA-256为`86433a77155ed2714fcdc3dae6bfde082da1d41d986e4db47685c5fb3b1e4d84`；碰撞/B-rep保持`not_evaluated`。
- 核心资产二次构建SHA-256一致；有效图及关联执行回归44项通过。
- SolidWorks实体闭环完成后，已无保存关闭基座原型及其2个残留叶零件；原型源文件关闭后SHA-256仍为`db427cab6352ee140b4c4c971702d8c444761b10da3de38ca4da1dfed3e89df0`，会话恢复为0个打开文档。
- 修复`create_global_cad_base_wrapper.py`的会话泄漏：记录运行前文档基线，只无保存关闭本次新增文档；`sessionRestoredToBaseline`和清理错误现在进入运行证据及成功门禁。新增2项清理测试后，全量后端回归为`947 passed, 3 subtests passed`，耗时46.86秒。
- 当前边界：跨项目配合驱动与实体保存重开已经完成；碰撞/B-rep仍未执行，状态保持`not_evaluated`，不应把本次结果描述为实体无干涉结论。

功能修改意义：完成“角色确认结果→端口规范化→跨项目兼容判断→组合有效图→自然语言装配上下文→CAD事务清单→真实SolidWorks保存重开”的第一条跨项目替换闭环，为后续按接口族批量扩展跨项目组合提供薄层实现基础。

# 2026-10-12 全目录替换矩阵与跨项目传输模组实体闭环

- 新增`build_cross_project_candidate_matrix.py`，只读消费全局目录及Project01/02/03/05最新不可变发布，生成43模组、118个有向同角色跨项目组合的覆盖矩阵。
- 初版分级结果：4项`ready_for_effective_graph_composition`、6项模板待消歧、58项缺端口/模板、50项已知不兼容；随后通过端口方向和安装配置消歧升级为最终矩阵。
- 新增“原子安装束至少两项驱动配合”规则，排除单条辅助防转边冒充完整安装端口；可执行关系由校准接口扩展到传输接口。
- 使用Project03 AE00替换Project01 SS00。两者定位孔中心距均为58 mm，编译为1包3配合，离线耗时`0.100604 s`。
- 真实作业`project03-job-e64acfa17a55`耗时`76.232518 s`，CAD适配器`72.359413 s`；基座缓存命中，估算避免`152.346006 s`重复准备。
- AE00从确定性非源初始位姿插入，3/3配合、完全约束、求解干净、组件语义一致、保存关闭重开和源保护全部通过；实体SHA-256为`d6746c57b475c219b9d40ba32fc3fde11b42fe0f23905a4d6758ef632b66ffbb`。
- 将SolidWorks文档基线恢复提升到整个事务包边界。缓存命中情况下仍自动关闭2个残留铰链叶零件，0文档开始、0文档结束，无清理错误。
- 定向回归14项通过；全量后端回归`950 passed, 3 subtests passed`，耗时60.30秒。碰撞/B-rep保持`not_evaluated`。

功能修改意义：全目录语义端口建设已有可量化缺口清单，跨项目替换已从单一校准样例扩展到传输接口，并消除了真实CAD执行后的会话污染。

# 2026-10-12 安装端口方向与多配置自动消歧

- 规范端口新增`portDirection`、`portPurpose`、`ownerRole`和`installationProfileId`，区分模组自身需要的安装端口、对外提供的子模组槽位、验证端口和工艺端口。
- A200→A600被识别为自身安装；T401-2→A200被识别为A200提供的`child_module_slot`。A200自身安装候选由2个纠正为1个。
- T401保留`T401-1→A600`与`T401-2→A200`两个真实安装配置；安装配置对选择器通过目标槽位提供方角色进行评分，基础箱体场景唯一选择T401-1。
- 修正矩阵判定优先级：缺端口优先报告缺口，硬性机械冲突优先于模板歧义，只有多个完整兼容候选同分时才要求人工指定配置。
- 原6项待消歧全部被解释：A200↔M000以及T401↔GJ00/AJ00均因配合拓扑不一致、定位几何不可比较而改判`incompatible`，不会启动SolidWorks。
- 最终矩阵：4项可组合、0项待消歧、58项缺端口/模板、56项不兼容；摘要`3a6ea08b71ebc3f5a2bd09822720f056af8531eb2e95cb1936c6472cced802ac`。
- 新增端口方向、A200子槽位、T401双向多配置选择与矩阵分类回归；定向测试11项通过，全量后端回归`953 passed, 3 subtests passed`，耗时47.55秒。
- 碰撞/B-rep未执行，保持独立可选后验验证。

功能修改意义：模板消歧从人工挑选改为机械上下文自动选择，并且不会用“消歧成功”掩盖接口拓扑和安装尺寸不兼容。

# 2026-10-12 活动目录端口/模板缺口清零

- Project01 GN00通过已发布的`JJ00主安装＋SS00防转`精确组合进入完整安装配置；防转关系仍不被单独计为原子安装端口。
- 从Project03原型配合图恢复AB00完整三关系：重合、四面宽度居中和40 mm距离；8个原端点均复用持久引用。
- 真实CAD从独立、非原型初始位姿插入AB00，3/3配合创建、完全约束、求解干净、保存关闭重开和高级参数复核全部通过；总耗时123.23秒。
- 发布不可变目录`relation-v39-project03-ab00-complete-driving-20261012`；目录摘要`ce458e4ecc4378a3b85098c9c3999c8281c1e8f4dad43dd52662e24816322a30`。
- 全目录矩阵更新为：4项可组合、0项机械复核、0项消歧、48项缺端口/模板、66项不兼容；48项缺口全部属于已延期Project06。
- 当前活动范围Project01/02/03/05的`needs_endpoint_or_template`为0；机械不兼容关系保持失败关闭，不以伪模板换取覆盖率。
- 定向回归34项通过；完整后端回归`958 passed, 3 subtests passed`，耗时47.93秒。
- 碰撞/B-rep未执行，仍为独立可选后验验证。

功能修改意义：在不扩张架构的前提下，完成了当前活动项目的端口和模板空白清零，并把延期项目、机械不兼容和真实待补缺口明确分开。

# 2026-10-12 不兼容接口工程分层与扫描模组转接需求

- 将66项活动有向不兼容记录去重为33组机械接口问题：28组安装拓扑不同、3组定位图案尺寸不一致、2组安装上下文架构不同。
- 新增`cross_project_interface_triage.py`和构建脚本，生成机器可读分层、工程动作和失败关闭策略。
- Project03 AI00替换Project01 SM00样例中，识别到200 mm与22 mm双定位孔距冲突，生成双接口转接件需求；未虚构转接件CAD。
- 自然语言替换预览现返回`engineeringDisposition`，包含不兼容类型、178 mm差值、所需工程资产和`fail_closed_before_cad`结论。
- 构建产物位于`demo/cross_project_substitution/incompatibility-triage-v1/`；碰撞/B-rep继续不作为当前门禁。
- 定向回归18项、完整后端回归`964 passed, 3 subtests passed`，均通过。

功能修改意义：系统能够把不兼容结果转化为具体工程输入，同时保持没有实体转接件就不启动CAD的安全边界。

# 2026-10-12 备用槽位发现与A600校准接口定向采集

- 新增`cross_project_alternate_slot_discovery.py`，对活动目录中56个有向安装拓扑不一致关系扫描目标基座已登记备用槽位；结果全部为`no_registered_alternate_slot`。
- 明确该结果只代表语义目录没有证据，不代表CAD实体必然没有其他孔系或安装面。
- 新增`cross_project_slot_acquisition.py`，把Project03 AH00→Project02 A600的缺口编译为失败关闭的定向几何采集请求。
- 请求绑定A600真实CAD、AH00支承面＋双定位孔接口、50 mm孔距、±0.5 mm工程筛选容差、A500原生槽位所在静止叶零件和实体索引12。
- 现有A600的708个实体包围盒、粗安装平台和安装坐标系均被明确判定为“不足以证明孔拓扑”，没有虚构备用槽位或转接件。
- 自动筛选回退方案为人工选择两个定位面和一个支承面；端点发布前维持`TARGET_SLOT_GEOMETRY_NOT_REGISTERED`并禁止启动跨项目CAD事务。
- 生成产物：`demo/cross_project_substitution/alternate-slot-discovery-v1/project02_A600_calibration_slot_acquisition/`。
- 新增采集结果筛选器，可在叶级面目录中筛选平行圆柱轴、轴间垂距、匹配支承面与50 mm孔距；候选命中后仍要求人工复核和端点恢复测试。
- 现有A500有界目录负例闭环得到4个平面、0个圆柱、0个候选，正确维持失败关闭；结果保存为`existing_catalog_screening.json`。
- 默认500面上限首次安全失败，没有保存残缺目录；将上限显式调整为2000后，只读取同一静止叶零件，约8～9分钟得到1521个面端点。
- 实测筛选输入为850个平面和587个圆柱面；严格加入同实体、同半径、共同支承面及孔轴覆盖条件后，从松筛29组收敛为Body 72上的2组有效50 mm孔列，孔半径均为2.10 mm。
- 依据已声明的机械装配顺序，选择更靠近操作面的孔列：A600坐标`xIntoMachine=0.1613 m`；保留`0.1863 m`孔列作为备用，不删除证据。
- 选中端点为一个支承面`aa08402291331a23`及两个定位圆柱面`1e8d1d2e490e3c0a`、`adf246feb6c09278`；三者均带装配体持久引用。
- 新增候选端口封装和独立恢复证据脚本；SolidWorks逐面恢复3/3成功，总耗时7.22秒，未创建配合、未保存或修改原型。
- 候选端口状态为`endpoint_recovered_pending_cross_project_cad`，仅允许后续候选验证；尚未写入全局发布目录，也不宣称可移植。
- 定向测试7项通过；完整后端回归`973 passed, 3 subtests passed`，耗时79.57秒。碰撞/B-rep仍不参与当前端口采集验收。

功能修改意义：把“缺少备用槽位”从抽象阻塞推进为三个可稳定恢复的真实CAD端点；同时以候选状态隔离未完成的跨项目配合验证，避免把几何筛选命中误发布为可用安装接口。

# 2026-10-12 A600/AH00跨项目备用槽位发布闭环

- 稳定化A600双孔角色分配：按局部横向坐标而非EndpointId顺序确定孔1/孔2，并记录角色映射证据。
- 新增`cross_project_slot_cad_validation.py`，编译A600与Project03 AH00的三配合、无case锚点、无叶位姿锚点候选有效图。
- 真实CAD执行成功：51.00秒完成独立插入、3/3配合、完全约束、求解、保存关闭重开和参数复核；6个端点均使用持久引用恢复。
- 输出装配体：`demo/cross_project_substitution/alternate-slot-discovery-v1/project02_A600_calibration_slot_acquisition/cad-validation-v1/project02-a600-project03-ah00-candidate-v1.SLDASM`；SHA-256为`f200d28f604d62f111cf08cbb12fd6f345c526a5544f36ab09809c4499514829`。
- 新增`cross_project_slot_release.py`和发布脚本，验证源文件摘要不变后，将候选封装为6端点语义包；碰撞状态保持`not_evaluated`。
- 全局目录支持端口级`projectId`，同一语义包可同时解析Project02 A600与Project03 AH00。
- 发现v40错误使用通用目录作为Project02发布基线，导致候选矩阵遮蔽v36既有授权；保留v40审计记录，新增项目发布谱系合并器。
- v41从Project02 v36增量加入1端口、1模板、2兼容边，保留原51模板；发布目录`relation-v41-project02-a600-project03-ah00-driving-20261012`，摘要`fcb252fc498f57294582dcd6cfc7a9bf298e6652a842a7044e356bab0cef4962`。
- 重建候选矩阵与备用槽位报告；AH00→Project02 A500替换方向现能发现A600槽位并判定可用。
- 定向测试16项通过；完整后端回归`985 passed, 3 subtests passed`，耗时48.31秒。

功能修改意义：完成从未登记实体孔系到可被自然语言组合层发现和调用的跨项目语义安装端口的完整证据链，并补上项目发布谱系保护，防止新增能力造成既有能力回退。

# 2026-10-12 A600/AH00操作面侧自然语言真实装配闭环

- 为已验证A600备用校准槽位补充`operator_side`方位语义，未改变模板编号、6个端点和三配合几何。
- 发布v42不可变目录：`relation-v42-project02-a600-ah00-operation-side-language-20261012`；摘要`2a06dc78b251681ffcba56768ae709815776139fa9ebee3ffed8d8fc64edd8ef`。
- 两条中文命令离线编译成功，约0.180秒生成发布绑定的1包3配合任务；任务号`project-global-job-cd04eec0deb6`。
- 首次执行发现编排器和单包执行器错误地用Project02槽位证据过滤Project03目标别名；在0.12秒内CAD前失败关闭。修复后增加跨项目别名回归。
- 第二次尝试真实CAD成功：87.88秒完成，CAD适配器70.02秒；基座缓存命中并估算避免128.50秒准备。
- 3/3配合、完全约束、求解干净、保存关闭重开、参数复核、源文件保护、输出关闭和会话恢复均通过。
- 输出：`demo/global_assembly_contexts/manifest_jobs/project-global-job-cd04eec0deb6/packet-runs/packet-001-attempt-02/project02-a600-ah00-operation-side-v1-packet-001.SLDASM`，SHA-256 `3b012f542ef6862041b9e188059b717188eec6581bd655d6b0a0b8222d0c5017`。
- 用v42重建全目录候选矩阵和备用槽位报告；活动范围端口/模板空白保持0，A600备用槽位能力未回退。
- 定向测试39项通过；完整后端回归`991 passed, 3 subtests passed`，耗时49.16秒。碰撞/B-rep未执行。

功能修改意义：完成“中文方位命令→唯一跨项目槽位→发布授权→持久任务→真实CAD检查点”的端到端闭环，并保留前置失败、修复和重试的完整审计证据。

# 2026-10-12 Project01 JJ00与Project03 AE00传输模组自然语言直接安装

- 将跨项目发布合并逻辑抽为通用薄层入口；A600/AH00包装函数改为复用该入口，避免继续复制项目对专用合并代码。
- 新增Project01 JJ00/Project03 AE00证据检查：两个可移植端口、有效兼容记录、零剩余自由度声明、独立非case锚定插入、3/3配合、完全约束、保存重开和源会话保护全部必须通过。
- 新增发布脚本`scripts/release_project01_jj00_project03_ae00_transport.py`，从Project01 v38谱系发布v43；授权模板`template/cross-project/ae00-to-project01-ss00-slot/97aed2cb02`。
- 两条自然语言命令在0.128秒内编译为1包3配合，持久任务为`project03-job-f18e29248c09`。
- 新真实CAD执行耗时122.23秒，CAD适配器101.34秒；JJ00缓存命中，估算避免152.35秒准备。
- 输出：`demo/global_assembly_contexts/manifest_jobs/project03-job-f18e29248c09/packet-runs/packet-001-attempt-01/project01-jj00-project03-ae00-transport-v1-packet-001.SLDASM`，SHA-256 `6ee13d82b634ae0c853d454893cba125ff788a40ff3e830feea799768d4982d8`。
- 3/3配合、完全约束、求解干净、保存关闭重开和参数复核通过；碰撞/B-rep保持`not_evaluated`。
- 候选矩阵已读取v43。活动4个有向关系因同时存在原生与已发布跨项目模板而显示待消歧；记录为下一步报告语义修正，不属于CAD能力失败。
- 定向回归39项通过；完整后端回归`994 passed, 3 subtests passed in 48.92s`。

功能修改意义：用不同角色、不同基座和新持久任务再次证明自然语言跨项目安装主线可复用，正式排除仅对A600/AH00特例生效的风险。

# 2026-10-12 已发布直接关系分层与用户摘要闭环

- 修正候选矩阵：跨项目执行模板不再重复作为原生安装profile参与发现，消除了4项虚假的模板消歧。
- 新矩阵在活动范围显示1项已发布直接执行、3项可组合有效图、0项待几何复核、0项待模板消歧、0项端口/模板缺失、66项已知不兼容；Project06延期缺口仍为48项。
- 新增`global_manifest_job_user_summary.py`与`scripts/build_global_manifest_job_user_summary.py`，从真实持久作业生成紧凑JSON和Markdown证据；随后接入通用作业产物刷新流程，状态接口可直接返回摘要路径与状态。
- 为`project03-job-f18e29248c09`和`project-global-job-cd04eec0deb6`生成用户摘要；两者均通过3/3配合、完全约束、求解干净和保存重开门禁，并保留`collisionStatus=not_evaluated`。
- 新增“配合创建数不足不得显示通过”和“作业自动生成摘要”的测试；最终定向回归16项通过，完整后端回归`998 passed, 3 subtests passed`。
- 候选矩阵增加按角色和项目方向的聚合表；新摘要`92a203dfcc98d2bb43953ba10e8b0935d56ceb4d81475d199e935d45abd5b474`显示活动可组合关系仅集中在Calibration和Transport，其他角色的活动关系属于已知不兼容而非端口空白。

# 2026-10-12 活动目录端口/槽位发布基本完成

- 新增通用跨项目直接安装证据构建器和发布脚本，定向测试覆盖成功发布及配合数不足失败关闭。
- 发布v44：Project03 AH00安装到Project01 JJ00校准槽位；发布v45：Project01 BD00安装到Project03 AA00校准槽位；发布v46：Project01 SS00安装到Project03 AA00传输槽位。
- 候选矩阵授权审计从“只读每项目最新发布”修正为“扫描全部不可变发布并按模板去重”；当前共识别5条跨项目直接执行模板。
- 当前活动矩阵70个方向：4个已发布直接执行、66个明确不兼容、0个待发布、0个待复核、0个待消歧、0个端口/模板缺口；Project06延期48项。
- 新增闭合状态`basic_active_coverage_closed`，矩阵摘要`998cbc66d153c8d55b620d23d7d9e36fa39f090cc1e2b9149fbb920729080817`。
- 发布绑定任务`project01-job-86a04eaa623c`完成BD00→Project03校准槽位真实CAD复验，3/3配合、完全约束、保存重开通过。
- 发布绑定任务`project01-job-b601e1a0748d`完成SS00→Project03传输槽位真实CAD复验，3/3配合、完全约束、保存重开通过。
- 发布绑定任务`project03-job-d18e11cad8d2`补齐AH00→Project01校准槽位真实CAD复验，3/3配合、完全约束、保存重开通过；至此活动矩阵4个直接执行方向均具备发布绑定实证。
- 修复英文`transport slot`被误识别为槽配合的问题，并保留显式`pin in slot / slot mate`语义。
- 定向回归52项通过；完整后端回归`1002 passed, 3 subtests passed in 73.19s`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：现有活动项目中所有已有直接兼容机械证据的跨项目端口已发布并经过自然语言真实CAD验证，端口/槽位补齐工作达到第一轮基本完成，而没有把硬不兼容关系伪装成可组合。

# 2026-10-12 Project03双槽位累计装配顺序闭环

- 发布v47，同时授权Project01 SS00→Project03传输槽位与Project01 BD00→Project03校准槽位。
- 自然语言累计任务`project01-job-a6148a40bdc8`按`AA00→SS00→BD00`执行成功，总耗时222.36秒。
- 自然语言累计任务`project01-job-38931a61c370`按`AA00→BD00→SS00`执行成功，总耗时233.36秒。
- 两条链各含2个真实CAD包；第二包均消费第一包输出，四包全部3/3配合、约束接受、求解干净、保存关闭重开和参数复核通过。
- 新增顺序兼容闭环构建器、命令行脚本和正负回归；报告位于`demo/cross_project_substitution/cumulative-project03-v1/order-closure.*`。
- 报告判定`semanticResultEquivalent=true`、`binaryIdentityRequired=false`；两个最终SLDASM摘要不同但不构成失败。
- 候选矩阵切换到Project03 v47，活动范围仍为4项直接执行、66项不兼容、0项未决；矩阵摘要`e642a0d18eb42a90bee3c3f630239bf3aed843a79cac10440267346cad6cca84`。
- 定向回归11项通过；完整后端回归`1005 passed, 3 subtests passed in 83.26s`。
- 碰撞/B-rep保持`not_evaluated`。

功能修改意义：证明两个跨项目模组能够在同一新装配体中以相反顺序累计安装，而不是只能分别完成单包演示。

# 2026-10-12 自然语言装配失败原因可解释化

- 新增`assembly-user-failure-explanation/v1`，统一底层阻塞码为用户原因、解释、建议动作和重试条件。
- 候选矩阵、跨项目替换预览、发布关系预览和全局清单编译均返回`userFailureExplanation`。
- 持久任务状态和用户摘要增加CAD失败解释；Markdown摘要会直接展示原因码和建议。
- 当前矩阵解释分布：56项安装拓扑不兼容、6项定位图案不一致、4项安装上下文不兼容、24项缺自身端口、24项目标槽位未登记。
- 四类示例报告覆盖拓扑不兼容、定位尺寸冲突、目标槽位未登记和驱动关系未授权；均未启动SolidWorks。
- 最新矩阵摘要`c5fd405bcc676ed9a125246651fb73b5ad9288f38e7f7ea6ac5547c1a14a3702`，原4项直接执行、66项活动硬不兼容及48项延期缺口数量不变。
- 定向回归51项、完整后端回归`1010 passed, 3 subtests passed in 76.02s`。
- 碰撞/B-rep保持`not_evaluated`。

功能修改意义：用户不再需要阅读底层JSON或异常字符串才能判断失败原因和下一步工程动作，且解释层没有放宽任何机械约束。
# 2026-10-12 Scanner第三角色备用槽位有界发现

- 保持Project06延期，仅分析Project01/03的Scanner跨项目组合。
- 新增`cross_project_scanner_slot_discovery.py`和构建脚本，区分0.5 mm发现容差与1 µm直接兼容容差。
- Project03扫描支承叶零件目录包含242个面；对Project01 SM00的22 mm要求，仅发现22.360679775 mm近似孔距，保持不兼容。
- Project01扫描支承叶零件目录包含232个面；对Project03 AI00的200 mm要求发现6组精确孔对，选出离原生扫描工位最近的一组。
- 选定支承面及两个定位面均完成SolidWorks只读恢复，3/3成功，总耗时6.090315秒。
- 候选中心相对原生扫描工位偏移约349.716 mm，故未创建配合、未发布端口；后续需验证光轴、工作距离和条码目标区。
- 新增确定性、角色错误、容差失效及双方向候选选择测试；定向回归16项通过。
- 本轮打开的Project01、Project03顶层原型已无保存关闭；未执行碰撞/B-rep。

功能修改意义：在不放宽机械规则的前提下，系统开始能够从真实静态支承几何中发现未登记槽位，同时明确阻止“孔距相同即功能兼容”的错误发布。

# 2026-10-12 Scanner候选工艺预检

- 新增`cross_project_scanner_process_preflight.py`及构建脚本，消费机械候选、端点恢复证据和全局目录。
- 预检把扫描光轴/原点、工作距离范围、传输条码目标点、候选位姿和光学命中结果设为独立门槛。
- 当前AI00→Project01备用孔系机械条件已满足，但缺少AI00光学端口、工作距离范围和SS00条码目标点，状态为`blocked_before_cad_missing_functional_semantics`。
- 预检在CAD前返回`cadInsertionAllowed=false`，未创建配合、未保存装配体、未发布端口。
- 新增4项正负测试；完整后端回归`1019 passed, 3 subtests passed`。
- Project06未参与；碰撞/B-rep未执行。

功能修改意义：跨项目Scanner扩展现在具备功能级失败关闭，不再把“安装孔完全匹配”误认为“扫描功能已经可用”。

# 2026-10-12 基座—传输—扫描—功能模组累计装配闭环

- 创建v48不可变发布，同时授权Project01 SS00→Project03 AA00传输槽位、Project03 AI00→AA00扫描槽位和Project01 BD00→AA00校准槽位。
- 四条自然语言命令在0.194021秒内编译为三包持久任务`project-global-job-163f19364c24`。
- 真实CAD顺序为`AA00→SS00→AI00→BD00`；三包均一次成功、3/3驱动配合、完全约束、保存关闭重开通过。
- SS00、AI00、BD00分别耗时144.483388秒、241.382240秒和143.332913秒，总执行529.505085秒。
- AI00三条关系驱动定位，两个原型距离关系只做验证，未产生过约束。
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project-global-job-163f19364c24/packet-runs/packet-003-attempt-01/cross-project-p03-ss00-ai00-bd00-v1-packet-003.SLDASM`。
- 新增`natural-language-complete-demo-chain-closure/v1`及5项正负测试；机械链通过，跨项目扫码功能仍待光轴/目标/工作距离验证。
- Project06未引入；碰撞/B-rep保持`not_evaluated`。
- 定向回归20项通过；完整后端回归`1024 passed, 3 subtests passed in 81.17s`。

功能修改意义：首次取得自然语言驱动的四角色真实累计装配实体，后续工作从“能否装起来”转为“扫描器能否针对跨项目传输目标完成工艺”。

# 2026-10-12 AI00—SS00动态条码通道只读验证

- 新增`cross_project_scanner_transport_process_validation.py`、构建脚本和4项单元测试。
- 将Project03 AI00的100 mm CAD光束与Project01 SS00产品条码通道代理变换到最终累计装配体坐标系。
- 验证按动态载具工艺分解为流向站位、横向通道、高度和有向工作距离，而不是错误要求固定世界点重合。
- AI00扫描站位于SS00保守纵向包络内，横向误差`0.402 mm`，粗几何对齐通过。
- 推算所需工作距离`79.500 mm`；KEYENCE官方SR-X100读取距离为`70–1000 mm`，静态Demo距离门槛通过。
- 四角色闭合状态升级为`complete_demo_chain_passed`；最终装配体未重跑也未修改。
- 条码仍为原型代理面，码尺寸、视野和现场触发未验证，因此工程/生产状态保持未放行。
- Project06、碰撞和B-rep均未引入。
- 定向回归12项通过；完整后端回归`1031 passed, 3 subtests passed in 81.22s`。

功能修改意义：以不到1秒的离线计算复用既有CAD证据，避免重复约9分钟的机械长链，并使“基座＋传输＋扫描＋功能模组”自然语言静态Demo真正闭合；真实条码面与现场工艺留作非阻塞工程增强。

# 2026-10-12 项目总体交接文档

- 新增 `docs/project_handoff_overview-CN.md`，统一记录当前主线目标、技术路线、系统架构、代码和证据入口、项目覆盖、已验证的跨项目四角色 CAD 链、能力边界、非主线分支、复现命令和后续优先级。
- 特别记录当前 Git 工作区存在大量未提交/未跟踪文件；现有 `041f281` 提交不能代表最新能力，交接前必须建立检查点提交或完整工作区快照。
- 明确当前验收边界：真实配合、保存重开和静态工艺代理属于主线证据；碰撞/B-rep、动态全行程和生产放行暂不作为当前硬门禁。
- 本次修改的意义：为另一位开发者提供单一可信入口，避免将布局求解、配合图重建、需求检索和自然语言累计装配四条路线混淆，也避免误把静态 Demo 证据表述为生产就绪。

# 2026-10-12 展示页 Project05 异构迁移数据兼容修复

- 修复 `ProjectMigrationReadinessPanel` 把 Project01/03 的 `servicePoints.combinedServiceModule`、`calibrationModule` 和 `dualValveReach.commonReachInstallationFrameMeters` 结构强加给 Project05，导致 React 根节点未捕获异常后整页灰屏的问题。
- `servicePoints` 现兼容 Project05 的独立模组汇总结构；缺少组合服务/标定汇总时显示通用服务端口数量。
- `dualValveReach` 同时兼容旧版公共范围和 Project05 的 `commonPlanarReachInstallationMeters`、`dualValvePitch` 表达。
- 为三个旧迁移就绪面板增加局部错误边界；后续单个历史面板结构异常时只显示该项目告警，不再拖垮自然语言装配等整页功能。
- 前端生产构建通过；浏览器重新加载后恢复 `43` 个CAD模组、`74` 个语义端口、`61` 条兼容关系和自然语言增量装配操作区，未出现新的运行时渲染错误。

功能修改意义：保障今晚演示入口可用，并将历史布局迁移面板与当前自然语言装配主线隔离，避免非主线数据结构差异造成全局不可用。

# 2026-10-12 自然语言模组装配演示操作手册

- 新增 `docs/demo_operation_runbook-CN.md`，把今晚演示拆分为目录检索、Project02中文三模组图预览、跨项目四角色正式编译、真实SolidWorks复核、工艺证据、失败关闭、检查点恢复和人工选面兜底等多个Case。
- 对每个Case分别说明操作界面、可直接复制的命令、按钮顺序、预期结果、机械语义和汇报边界。
- 明确区分只读查看、图上下文写入、排队任务创建和真实CAD启动，避免在会议中误启动约9分钟长链或误把碰撞未评估结果描述为工程放行。
- 记录五分钟、十分钟和技术讨论三种演示组合，以及前端、SolidWorks或自然语言预览异常时的备用路径。

功能修改意义：使演示者可以不依赖开发上下文，按清单稳定复现当前能力，同时准确表达“已实现什么”和“尚未验证什么”。

# 2026-10-12 全局装配工作台工程师交互层改造

- 将原先“输入内部编号、直接生成图补丁”的开发者式入口改为五步引导：选择当前装配、描述工程意图、确认具体模组、检查并确认、创建CAD任务。
- 自然语言输入支持工程场景描述，并提供校准、扫描、传输—扫描顺序三个可直接套用的示例；输入区明确提示无需知道项目号或A600/A700等内部编号。
- 当自然语言对应多个CAD定义时，以候选卡片显示模组名称、来源案例别名、类别、语义端口数量和接口完整度；工程师选择后重新执行接口预检。
- 当方案可执行时，按自然语言显示所选模组、目标模组、关系用途和跨项目可复用性；端口ID与模板ID收进“技术追溯”，避免干扰普通使用者。
- 将后端阻塞码翻译为工程师可理解的原因，同时保留原始错误码；歧义、缺少目标模组、缺少端口或兼容模板时继续失败关闭，不创建CAD任务。
- 增加显式人工确认：只有方案状态为`ready`且用户勾选“确认所选模组和装配关系”后，才允许写入装配会话。
- 原来的按编号/类别检索保留在折叠的“专家工具”中，便于排查和直接指定，不再占用主交互流程。
- 浏览器实测闭环：普通工程描述返回3个候选并停在确认阶段；选择Project03喷嘴校准模组后，因空上下文缺少安装目标而正确阻断；明确添加A600时方案可确认，勾选后上下文由修订0更新为修订1并新增1个模组。
- 前端生产构建通过；页面运行日志无warning/error。碰撞与B-rep仍维持独立、可选的后验验证，不作为当前自然语言装配交互硬门禁。

功能修改意义：把已有目录、语义端口、兼容模板和CAD执行能力组织成符合机械工程师认知的“描述—消歧—检查—确认”流程，降低误选模组和错误装配风险，同时没有放宽既有机械约束。

# 2026-10-12 全局装配工作台回退与撤销闭环

- 为歧义或阻塞预览增加四类恢复入口：返回修改需求、重新选择候选模组、按阻塞原因先补充安装基座、放弃本次操作；这些操作只处理尚未提交的预览，不修改装配上下文。
- 每次装配图提交前保存按修订编号组织的上下文快照，命令序列同时保存中间修订，形成可追溯恢复证据。
- 新增`undo-latest`后端接口和前端二次确认区；只允许撤销最新一轮且尚未绑定CAD任务或实体修改的图提交。
- 最新轮次一旦存在CAD任务或实体修改证据，后端与前端均失败关闭，避免语义图回退而SolidWorks实体仍停留在新状态。
- 撤销时同时恢复上一版实例、连接、历史、修订号和摘要，并重置与旧摘要绑定的上下文临时端口；被撤销轮次移入会话台账的`rolledBackTurns`审计区，不静默删除历史证据。
- 接口冒烟：阻塞校准模组预览前后均为修订0、模组0；基座提交由修订0变为1，撤销后恢复为修订0、模组0。
- 浏览器实测：空上下文选择校准模组时显示“返回修改需求 / 重新选择模组 / 先补充安装基座 / 放弃本次操作”；基座提交后显示“撤销上一轮”，进入二次确认时明确展示轮次和原始需求。
- 定向后端回归11项通过，前端生产构建通过；页面控制台无warning/error。

功能修改意义：失败方案现在有可理解的继续路径，已提交但尚未进入CAD的误操作也能安全回退；同时以CAD证据为边界，避免把“撤销图命令”错误等同于“撤销真实装配体”。

# 2026-10-12 累计装配第二轮提交故障修复与四步流程复测

- 定位到`global-demo`/`meeting-demo-scanner-line`第二轮A800分析已经达到`ready`，目标为A600且关系模板完整；会话仍为1个模组并非识别失败。
- 根因是撤销后重新建立基座会复用修订号1，而旧实现仅以`revision-000001.json`命名快照；新的修订1摘要不同，A800提交前归档因此报“修订快照1已存在但摘要不同”。
- 快照归档现支持同一修订号的摘要分支文件；新提交历史记录父`sourceContextDigest`，撤销时按父摘要或历史前缀唯一选择正确分支，不覆盖既有审计证据。
- 新增“回滚→另一条修订1分支→继续添加A800”的回归测试；相关后端测试`23 passed`，实时API验证得到修订2、2个模组、1条连接，父摘要一致。
- 前端将最后一步改名为“写入装配会话”，明确“勾选仅确认意图，还需点击提交按钮”；成功后直接显示新修订号和当前模组数。前端生产构建通过。
- 在隔离会话实测工程语言四步链：A600→A800→A180→A500，最终修订4、4个模组、3条结构连接。
- 发现原演示稿两处表达需修正：A180当前结构连接为A180→A600，A180↔A800是扫码工艺验证而非直接安装关系；含“操作侧”的A500命令因模板未声明侧向基准而被安全阻断，去掉该限定后可成功提交。

功能修改意义：修复了图级撤销产生的真实提交阻塞，并把演示脚本从“预期可行”升级为经API闭环验证、且不夸大现有结构/工艺语义的可复现流程。

# 2026-10-12 装配会话与CAD任务刷新恢复修复

- 定位前端刷新后内容消失的根因：装配上下文、会话台账和最近CAD任务仅保存在React内存中；加载已有会话时还会主动清空`preparedJob`，后台持久数据并未丢失。
- 前端现在将最近使用的会话名称保存在浏览器本地存储；页面启动时自动从后端恢复装配上下文、自然语言会话台账、上下文临时端口、执行清单、项目适配计划和最近绑定的CAD任务。
- 异步恢复期间显示“正在恢复最近使用的装配会话…”，恢复后标题显示“正在编辑：会话名”，避免刷新瞬间误显示为空白会话。
- 恢复逻辑只执行只读查询，不创建任务、不启动SolidWorks，也不恢复任何用户确认勾选，避免刷新造成重复执行或默认授权。
- 真实页面刷新复核：`global-demo`恢复为修订3、3个模组、3轮自然语言命令；任务`project02-job-54bc1353ab73`恢复为`succeeded`、`assembled`、2/2检查点，并重新显示A800/A180步骤与最终装配体路径。
- 最终装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-54bc1353ab73/cad-working/step-02-a180-attempt1-action1.SLDASM`；碰撞状态仍明确为“未评估”。
- 前端生产构建通过；会话、项目适配计划和任务API定向后端回归`14 passed`。

功能修改意义：页面刷新不再打断演示和任务观察；前端状态重新以后台持久台账为事实来源，同时保持所有会造成CAD副作用的操作必须再次由用户明确确认。
# 2026-10-14 — Project05完整累计装配链闭环

- 使用v61单一不可变发布，从A000空白固定环境按自然语言依次累计加入D000、F000、M000、G000、N000、P000和B000。
- CAD持久任务`project05-job-72463661a6a2`七包首次执行全部成功；逐包真实配合数为`3/3、3/3、3/3、4/4、4/4、4/4、3/3`，均为非原型初始位姿、零案例/叶级锚点，并完成源文件不变、保存关闭重开和配合参数复核。
- 最终实体为`demo/global_assembly_contexts/manifest_jobs/project05-job-72463661a6a2/packet-runs/packet-007-attempt-01/project05-complete-seven-addon-v2-packet-007.SLDASM`，累计耗时约`874.467 s`。
- 新增CAD前完整链预检；历史v59因D000使用`source_pose`被拒绝，v61七包全部通过。
- 严格闭合器新增同一发布、目录摘要和模板ID绑定的双初始位姿证据引用，G000外部位姿通过发布级重复收敛证明，内部柔性保持不变。
- 修复多发布证据收集覆盖旧模板身份的问题；最终后端回归`1096 passed, 3 subtests passed`。
- 碰撞、B-rep、扫描工艺和动态行程仍为独立后验项，本轮均未宣称通过。

功能修改意义：首次形成“基座＋传输＋扫描＋CCD＋校准/称重＋清洁＋排胶杯＋龙门”的完整自然语言累计实体链，并使每包非原型位姿和外部定位证据可机器审计。
