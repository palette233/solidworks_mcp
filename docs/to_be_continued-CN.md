# 待继续事项

## 当前开发规则入口

- 开始自然语言装配、语义端口、真实CAD累计装配或碰撞验证工作前，先阅读`docs/development_execution_rules-CN.md`。
- 当前近期目标是`DEMO_ASSEMBLED_COLLISION_NOT_EVALUATED`：配合、保存重开和结构健康闭环必须完成，实体干涉门禁默认异步、按需执行。
- “有无干涉”不是当前关键问题；下一阶段优先完成自然语言逐步装配、语义端口到真实几何的恢复、累计保存重开、失败回滚与继续追加。
- 正式无干涉复核或工程交付才升级到`ENGINEERING_STATIC_VALIDATED`；未执行精检不得表述为无干涉。

## 2026-10-11：Project02九附加实例闭环后的主线续作

已完成：

- A800、A180、A500、A700、A300、A200、A100均取得确定性非原型初始位姿、无case/叶位姿锚点的独立真实CAD checkpoint；
- A100顶层安装关系与内部柔性运动状态已经分层，未复制36个原型内部叶位姿；
- v36不可变发布一次授权七个不同附加模组和两套T401实例共九条安装端口；
- T401-1通过A600安装端口加入，T401-2通过A200安装端口加入，已验证非星形装配图；
- 十句自然语言命令形成九包持久作业，并在约409.16秒内完成累计保存、关闭、重开及逐包验签；
- 最终实体与机器可读闭环报告均已生成；碰撞/B-rep未执行，符合当前主线边界。

下一步建议顺序：

1. 已完成容量边界：第二套T401可由剩余实例容量唯一解析，第三套在CAD前以`MODULE_INSTANCE_CAPACITY_REACHED`失败关闭；
2. 已完成跨项目关系拓扑审计：Project01的GN00—SS00是可移植非星形机械边；Project03的AI00→AE00、AH00→AG00只是工艺/顺序依赖，不能伪装成配合；
3. 已为长链闭环报告增加参数来源等级摘要；Project02原型估计与CAD测量来源可直接读取，但该摘要不作为当前Demo执行门禁；
4. 下一步优先把关系拓扑审计接入发布前检查，并以Project01 GN00组合关系做持久编排恢复/重复回归；之后再选择新的、确有机械非星形边的项目族扩展；
5. 前端点选与碰撞/B-rep继续作为非前置待办。

当前无人工输入阻塞。下一项开发目标是把“工艺依赖≠机械配合”的拓扑审计固化到发布门禁，并复核Project01非星形组合在当前持久执行器下的恢复能力。

### 2026-10-11：拓扑门禁与Project01非星形实证已完成

- 通用发布器已支持`relationTopologyAuditPath + requiredMechanicalEdges`，声明的机械边不存在或只有位姿锚点证据时，发布在CAD前失败关闭。
- 新发布`relation-v37-project01-topology-attested-combination-driving-20261011`明确验签GN00—SS00无锚点机械边，并授权SS00安装、GN00主定位及GN00—SS00防转组合。
- 四句自然语言成功编译并真实执行`JJ00基础环境→SS00→GN00＋GN00/SS00平行防转`；作业`project01-job-e14773eac13f`两包均为3/3配合、求解干净、约束状态接受、保存关闭重开通过、无case锚点。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project01-job-e14773eac13f/packet-runs/packet-002-attempt-01/project01-topology-attested-nonstar-v1-packet-002.SLDASM`；总执行约175.54秒。
- 全量后端回归：`917 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 将拓扑报告摘要绑定进不可变发布清单，而不只保存在发布候选证据中，便于运行时和交接方直接验签；
2. 给Project01建立参数来源注册表，至少覆盖SS00安装基准、GN00定位束及原型估计服务点，使跨项目报告与Project02字段一致；
3. 对Project02 A500—A700现有非星形边做语义用途复核：区分安装驱动、只读工艺间距和可能冗余关系，禁止因“图中有边”自动授权驱动；
4. 再选择一个第三项目族；若没有真实非星形机械边，应明确报告“当前结构为星形”，而不是制造测试关系。

当前无人工输入阻塞。下一阶段先做“拓扑证据随发布清单传播＋Project01参数来源登记”，无需再次运行SolidWorks。

### 2026-10-11：机械边语义分级、外部位姿安全门禁与只读快检

- v38发布`relation-v38-project01-topology-bound-combination-driving-20261011`已把拓扑审计摘要与SHA直接绑定到不可变发布清单；Project01参数来源已登记到`demo/project01_parameter_package.json`。
- 新增`relation-semantic-topology-audit-v2.json`，不再把“图中存在机械边”自动解释为位姿驱动。当前识别31条可驱动机械边、1条只读验证边和1条依靠模板组合共同闭合的成员边；12条旧模板仍被明确标记为不完整驱动模板。
- Project02的A500—A700“距离8”被确认是只读工艺关系，不参与A500或A700外部安装。进一步的顶层位姿复测纠正了初步判断：首要问题不是未命名的内部工艺状态，而是A700外部安装本身落入了错误位姿分支。
- 11条自然语言命令曾生成10包作业`project02-job-18edf66ae566`：前9包安装全部成功，第10包测得`1.127733 m`而非`0.05 m`，失败后安全保留第9包检查点，源文件未变化、没有修改配合。
- 快速探针显示A500顶层与基准等价，而A700整体沿Z偏移`1.177733 m`；强制刚性试验仍偏移`0.134183 m`，且未完全约束。因此“全部配合参数相同”不足以证明柔性模组安装位姿等价。
- 新增运行时驱动安全目录`relation-driving-safety-v1.json`，撤销v33/v36中已被CAD证据证伪的A700驱动模板；新增外部位姿等价验证前置条件。相同11命令的v11编译在`0.238 s`内、CAD启动和作业创建前同时阻断错误安装与无效验证。
- 新增专用只读SolidWorks接口`VerifyRelationsInAssemblyContextFromMateGraph`：只打开已保存检查点并测量，不重建配合、不保存、不二次重开；相同失败探针由约`133 s`降至`9.78 s`，测量结果保持一致。
- 根因报告：`demo/global_assembly_contexts/manifest_jobs/project02-job-18edf66ae566/packet-runs/packet-010-attempt-01/relation-state-dependency-audit.json`；带顶层位姿的快速探针：同目录`fast-readonly-probe-v3.result.json`。
- 持久任务状态已区分`assemblyStatus`和`validationStatus`：后续只读验证失败不再把已提交装配检查点误报为装配失败。
- 驱动证据模型新增`portablePlacementProven`；通用发布器对声明保留内部柔性的模板强制要求外部位姿见证。A700历史检查点被重新分类为“执行闭环通过，但不可移植外部安装未证明”。
- 全量后端回归：`933 passed, 3 subtests passed`；SolidWorks桥接层非集成测试`367 passed`。
- 碰撞/B-rep仍为独立可选后验验证，本轮未执行。

下一步主线：

1. 从A700静止安装件、底板、销孔或槽中重建不依赖内部运动叶件的外部安装端口；
2. 用确定性非源初始位姿完成短链`A600→A500→A700`，要求A700顶层位姿等价、完全约束且50 mm只读测量通过；
3. 通过后以新模板ID和新不可变发布替代被撤销模板，再恢复九附加模组长链；
4. 只有外部位姿等价后仍存在测量差异，才继续建立A700命名内部状态；
5. 前端点选及碰撞/B-rep继续保留为非前置待办。

当前无必须由用户确认的问题。最近可执行目标是完成“A700静止安装端口重建→三模组短链→外部位姿与50 mm快检”的闭环。

过渡方案已复测：Project02标定快照从四模组检查点重新插入A700，插入`39.35 s`、只读复测`5.06 s`，距离8误差`3.18e-15 m`且顶层位姿等价。该方案只作为显式Project02回退，不自动替代通用端口。

## Common Base 朝向自动修正仍待实现

### 时间

- 2026-06-25

### 最新验证结果

- 删除旧 `ABC_arrange_demo.SLDASM` 后，重新执行 `Initialize -> Common Base`。
- A/B/C 导入成功。
- B/C 的 Coincident mate 创建成功，`bottomMateResult.errorName=swAddMateError_NoError`。
- `FinalizeCommonBaseAssembly` 最终仍返回 `bottom face orientation mismatch`。
- 原因是 `orientationChecks` 中 B/C 的 `matchesBase=false`。

### 当前结论

- 重复配合回归已经收敛。
- 剩余核心问题是：如何自动旋转 B/C，使其记录底面的法向方向与 A 一致。

### 后续实现建议

- 读取 A/B/C 记录底面的 `worldNormal`。
- 以 A 的 `worldNormal` 为目标方向。
- 对 B/C 计算从当前 normal 到目标 normal 的旋转轴与旋转角。
- 对组件应用显式旋转后，再执行或刷新 Coincident mate。
- 旋转完成后再次 probe 底面 normal，确认 dot product 达到阈值。

## Common Base 朝向修复的最新状态

### 时间

- 2026-06-25

### 当前状态

- 原先的“多种 Coincident mate alignment 重试 + Undo(1)”方案在真实测试中暴露出回归风险：可能留下重复 Coincident mate。
- 当前已经先回退到稳定策略：每个目标组件只创建一次 Coincident mate，然后统一做朝向检测与报告。
- `FinalizeCommonBaseAssembly` 仍会返回 `orientationChecks`，用于判断 B/C 底面法向是否和 A 一致。
- 如果方向不一致，当前仍会报 orientation mismatch，但不会再通过重复配合重试去自动修正。

### 待验证

- 需要使用干净装配体重新验证 `Initialize -> Common Base`。
- 验证重点：
  - 每个目标组件只新增一条必要的 Coincident mate；
  - 不再出现重复定义的重合配合；
  - 三个底面是否共面；
  - 如果 B/C 底面法向与 A 不一致，前端仍应显示明确的 orientation mismatch。

### 后续方案

- 如果业务要求自动修正 B/C 底面朝向，下一步应根据法向向量显式计算修正旋转，在 mate 前或 mate 后主动旋转组件。
- 不建议再使用“反复添加/撤销 mate alignment”的方式试探 SolidWorks 行为。

## Initialize 后组件已导入但默认隐藏

### 时间

- 2026-06-25

### 现象

- `Initialize` 后，用户在 SolidWorks UI 中一开始只明显看到 C。
- 检查后确认 A/B 已经导入，但在组件树中默认处于未显示/隐藏状态。
- 手动在组件树中设置显示后，A/B 可以正常看到。

### 影响

- 这不是插入失败，但会影响演示观感，也容易误判为 `InitializeCommonBaseAssembly` 没有导入完整组件。

### 后续优化

- 在 `InitializeCommonBaseAssembly` 插入组件后，显式调用组件显示/取消隐藏逻辑。
- 或在工具返回结果中增加组件可见性状态，发现隐藏时给出提示。
- 可以配合一次 `ZoomToFit` 或视图刷新，减少 UI 中“只看到部分组件”的误解。

## 小面底面法向 Fallback

### 背景

在 Common Base 校验过程中，`A-1` 上某个较小的面可以被现有面映射逻辑记录并重新选中，但它的 `localNormal` 和 `worldNormal` 会记录为 `null`。

后来选择同一组件上更大的明确平面后，normal 能够正常记录。这说明当前 normal 记录逻辑对标准平面有效，但某些小面或歧义面并不是稳定的 normal 来源。

### 当前行为

当前实现主要通过以下 SolidWorks API 读取面法向：

- `IFace2.GetSurface()`
- `ISurface.IsPlane()`
- `ISurface.PlaneParams`
- `IFace2.FaceInSurfaceSense()`

如果该路径无法得到有效非零法向，映射会保存为：

```json
"localNormal": null,
"worldNormal": null
```

这是零法向保护修复后的预期行为，避免把 `[0,0,0]` 这种无效法向继续作为 Common Base 的朝向基准。

### 问题

部分小面仍然可以用于测试“记录/选中”准确性，但不适合作为 Common Base 的底面参考，因为 Common Base 朝向校验需要有效平面法向。

可能原因：

- 该面没有被 SolidWorks 识别为简单平面。
- 该面是小分割面、过渡面、薄面、倒角面或拓扑歧义面。
- 鼠标/射线选择可能选到了视觉上靠近底面的窄侧面。
- 嵌套装配体变换暴露了不稳定或缺失的面元数据。

### 后续方案

如果后续必须支持小面，可以增加 fallback normal 提取逻辑：

1. 优先尝试当前 `PlaneParams` 路径。
2. 如果 `PlaneParams` 失败，则通过 SolidWorks API 收集几何采样点：
   - 面三角化 / tessellation 数据，
   - 面边界 / loop 顶点，
   - 可用时读取边曲线端点。
3. 使用采样点拟合平面。
4. 从拟合平面计算 normal。
5. 校验拟合 normal：
   - 采样点数量足够，
   - 点不共线，
   - 点到平面残差足够小，
   - normal 长度大于阈值。
6. 保存 normal 来源，例如：

```json
"normalSource": "planeParams"
```

或：

```json
"normalSource": "fittedFromFaceSamples"
```

### 验收标准

- 对 `PlaneParams` 失败的小平面，可以通过拟合得到有效 `localNormal/worldNormal`。
- 对非平面或噪声较大的面，应明确拒绝，而不是生成误导性 normal。
- `face_mapping_record_probe.py` 能打印 normal 来源。
- `face_mapping_verify_select.py` 能一致地比较拟合 normal。
- `FinalizeCommonBaseAssembly` 只在拟合质量足够高时使用 fitted normal。

### 当前建议

不要让该增强阻塞当前 demo 验证。当前阶段优先使用更大、更明确的平面底面，先验证完整流程：

1. 初始化装配体。
2. 记录带有效 normal 的底面。
3. 执行 Common Base。
4. 从前端坐标移动组件。

## 自动修正底面朝向

### 背景

`FinalizeCommonBaseAssembly` 当前已经能在创建共面 mate 后检测底面朝向不一致的问题。最近一次验证中，A/B/C 已经实现共面，C 的底面朝向与 A 一致，但 B 的底面相对 A 翻转。

前端正确显示：

```text
FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.
error / base pending
```

并且由于 `commonBaseReady=false`，`Arrange` 被禁用。

### 当前行为

- A/B/C 的底面可以被选中。
- B/C 的 coincident mate 可以成功创建。
- 朝向校验会将各组件底面 `worldNormal` 与 A 的基准 normal 比较。
- 如果任一组件 normal 与 A 不一致，则 Common Base 不会进入 ready 状态。

当前行为是安全的，但只能检测问题，还不能自动修复组件朝向。

### 问题

完整装配复原流程中，共底面应同时满足：

- 底面共面，
- 底面法向一致，
- 后续二维移动不会破坏该共面关系。

如果 B 已共面但上下翻转，当前流程会阻止移动。这保护了模型正确性，但如果没有人工修正，就无法完成自动 demo。

### 后续方案

给 MCP 高层 Common Base 流程增加自动朝向修正：

1. 读取 A 的底面 normal 作为基准。
2. 读取其他组件的底面 normal。
3. 如果某个组件 normal 与 A 相反：
   - 先尝试另一种 mate alignment，或
   - 围绕合适的面内轴旋转/翻转组件，再重新配合并验证。
4. 修正后重新 probe 底面 normal。
5. 仅当以下条件全部满足时设置 `commonBaseReady=true`：
   - mate 创建成功，
   - 底面共面，
   - 底面 normal 与基准一致。

### 验收标准

- 当某个组件初始上下翻转时，A/B/C 仍能无需人工翻转进入 Common Base ready。
- 自动修正不会把组件移出共同底面。
- `orientationChecks` 能清楚记录修正前/后的 normal 和修正动作。
- 前端能显示 Common Base 是直接完成，还是经过自动修正后完成。

### 当前建议

作为后续增强处理。当前验证阶段优先验证新引入的 Transform2 采集/布局功能，并将当前 orientation mismatch 结果视为“朝向保护逻辑有效”的证据。

## 相较于纯 Transform2 插件，当前链路的优势

### 问题

相较于纯粹的 Transform2 插件，当前项目的“前端 + 后端 + MCP + Transform2 复现核心功能”链路有什么优势？

### 回答

纯 Transform2 插件通常适合做直接的矩阵级流程：

```text
读取组件 Transform2
保存姿态矩阵
在另一个装配体中恢复矩阵
```

这对精确复制位姿很有用，但当前项目的目标更接近“可解释、可交互、可分阶段验证的装配复原流程”。

### 主要优势

1. 更贴近目标业务流程。

   当前项目不是只恢复原始组件位姿，而是引入了共底面语义：

   ```text
   导入子装配体
   对齐底面
   将底面中心投影到共同二维平面
   在二维布局中移动组件
   ```

   这比盲目恢复完整 Transform2 矩阵更贴近当前 demo 目标。

2. 有可控的前端交互。

   前端允许用户查看状态、拖动二维矩形块、编辑坐标、执行分阶段操作。演示链路更直观：

   ```text
   前端二维布局变化
   -> 后端发送目标数据
   -> MCP 调用 SolidWorks 工具
   -> SolidWorks 中组件移动
   ```

3. 可以分阶段验证。

   当前流程拆成：

   ```text
   Initialize
   Record / Verify Face Mapping
   Common Base
   Capture Layout
   Arrange
   ```

   每一步都能单独测试，这对 CAD 自动化调试很重要。

4. 具有底面语义，而不仅是矩阵。

   Transform2 本身不知道哪个面是底面。当前链路额外引入：

   - `RecordFaceMapping`
   - `SelectFaceByName`
   - `bottomFaceName`
   - `bottomCenterWorld`
   - `bottomNormalWorld`
   - `orientationChecks`

   这些信息让系统知道“哪个面应该共面、哪个方向算底面朝下、二维布局应该投影到哪个平面”。

5. 更适合高层 MCP 工具和大模型编排。

   当前项目将复杂 SolidWorks 操作封装成稳定高层 MCP 工具：

   - `InitializeCommonBaseAssembly`
   - `FinalizeCommonBaseAssembly`
   - `MoveComponentsOnCommonBase`
   - `CaptureCommonBaseLayoutFromAssembly`

   大模型或外部应用可以调用有语义的高层操作，而不是临场组合大量低级 API。

6. 更容易扩展成半自动装配复原工作台。

   当前架构可以继续扩展为：

   - 自动识别底面，
   - 自动修正底面朝向，
   - Transform2 / layout 捕获，
   - 前端人工微调，
   - 后端状态持久化，
   - 多轮迭代装配复原。

### 取舍

如果目标只是完全恢复原始位置和姿态，纯 Transform2 插件更直接，也可能更精确：

```text
复制原始 transform
粘贴原始 transform
```

当前项目更适合以下目标：

```text
可解释
可交互
可分阶段验证
有底面语义
可被 LLM/MCP 调用
支持二维布局复原和人工调整
```

### 总结

纯 Transform2 插件更像“矩阵级位姿复制工具”。当前项目更像“带前端交互、后端状态、底面语义、MCP 编排和 Transform2 布局采集能力的装配布局复原流程”。

## MCP 发布目录与运行目录一致性

### 背景

在实现第一版 layout2d 回放流程时，MCP App 编译成功。但发布到 `artifacts/solidworks-mcp` 时，旧的 MCP 进程仍在运行，发布脚本无法覆盖正在使用的 exe，因此自动发布到了新目录：

```text
artifacts/solidworks-mcp-20260624-112354
```

随后使用 `apply_captured_common_base_layout.py` 指向新目录测试时，工具尚未执行，MCP 连接阶段就失败：

```text
System.IO.IOException: The server shut down unexpectedly.
```

新发布目录的日志显示：

```text
Tray startup skipped because another hub instance is already running.
```

### 问题

新增 MCP 工具已经存在于新发布的 exe 中，但当前实际运行的 Hub 仍然是旧的 `artifacts/solidworks-mcp` 实例。因此，在停止旧 MCP 并启动新 MCP 之前，无法验证新增工具。

### 下一次测试的处理方式

测试新发布的 MCP 工具前，需要：

1. 关闭旧的 `SolidWorksMcpApp.exe` 进程。
2. 启动新发布目录中的 MCP，或在关闭旧进程后重新发布到 `artifacts/solidworks-mcp`。
3. 将 `face_mappings.json` 复制或重新记录到当前实际运行的 MCP 目录。
4. 再次执行命令行测试。

### 当前建议

下一次验证时二选一：

- 直接从 `artifacts/solidworks-mcp-20260624-112354` 启动新版 MCP；
- 或先停止旧 MCP，再重新发布到 `artifacts/solidworks-mcp`，继续使用默认脚本路径。

## PowerShell npm 执行策略导致前端构建命令失败

### 背景

前端接入 `Replay Layout` 后，需要运行前端构建验证。

### 现象

在 PowerShell 中直接运行：

```cmd
npm run build
```

会报错：系统禁止运行 `npm.ps1`。

### 当前处理

使用 CMD 入口可以正常构建：

```cmd
cmd /c npm.cmd run build
```

### 建议

- 这不是前端代码错误，而是 Windows PowerShell Execution Policy 的环境限制。
- 后续在 Windows 上给出演示/测试命令时，建议优先写 `cmd /c npm.cmd ...`，避免演示前被 PowerShell 策略拦截。

## 前端 Replay Layout 仍需真实 UI 级验证

### 当前状态

- `ApplyCapturedCommonBaseLayout` 已通过命令行脚本完成真实 SolidWorks 验证。
- 前端已经新增 `Replay Layout` 按钮。
- 后端已经新增 `/api/demo/apply-captured-layout`。
- 前端构建已通过。

### 待验证

下一步需要在真实运行环境中验证：

1. 启动新版 MCP。
2. 启动后端。
3. 启动前端。
4. 确认 `ABC_arrange_demo.SLDASM` 已初始化或已打开。
5. 点击前端 `Replay Layout`。
6. 确认 SolidWorks 中组件位置按 captured `layout2d` 回放。
7. 确认前端 Result 和 Screenshot 区域同步更新。

## 多个 SolidWorks 实例导致 MCP 看不到用户选择的面

### 时间

- 2026-06-24

### 现象

- 用户在 SolidWorks 中选中了 `A-1` 的底面。
- MCP 调用 `record_face_mapping` 时返回：

```text
No active document. Open or create a document first.
```

### 分析

- 当前机器上存在多个 `SLDWORKS.exe` 进程。
- MCP 通过 COM 连接到的 SolidWorks 实例没有活动文档。
- 用户实际选中底面的 SolidWorks UI 很可能属于另一个实例。

### 影响

- 手动选面记录依赖“用户操作的 SolidWorks 实例”和“MCP 连接的 SolidWorks 实例”是同一个。
- 如果不是同一个实例，即使用户已经选中正确面，MCP 也无法读取该选择。

### 临时处理建议

1. 保存需要保留的 SolidWorks 文档。
2. 关闭多余的 SolidWorks 窗口/进程，只保留一个实例。
3. 重新通过 MCP 或手动打开：

```text
demo/X_reference.SLDASM
```

4. 在该唯一实例中重新选中 A 的真实底面。
5. 再运行记录脚本。

### 后续优化方向

- 增加一个 MCP health 工具，返回当前连接的 SolidWorks 进程、活动文档标题、活动文档路径。
- 在记录面之前自动检查活动文档是否为预期的 `X_reference.SLDASM`。
- 如果检测到多个 SolidWorks 进程，给出明确提示。

## 真实验证 Common Base 底面朝向感知 mate 重试

### 时间

- 2026-06-25

### 当前状态

- `FinalizeCommonBaseAssembly` 已经改为尝试多种 Coincident mate alignment。
- 每次 mate 成功后，会重新读取目标组件底面法向。
- 如果目标法向与基准组件不一致，会撤销刚创建的 mate，并尝试下一种 alignment。
- 当前代码已通过构建验证。

### 待验证

仍需要在真实 SolidWorks 中使用新版 MCP 做一次验证：

1. 发布新版 MCP。
2. 停止旧的 `SolidWorksMcpApp.exe`。
3. 启动新发布的 MCP。
4. 初始化包含 A/B/C 的装配体。
5. 必要时重新记录/验证底面。
6. 执行 `FinalizeCommonBaseAssembly`。
7. 确认：
   - 三个底面共面；
   - B/C 底面法向与 A 一致；
   - 前端不再显示 `bottom face orientation mismatch`。

### 剩余风险

如果 SolidWorks 对某些面组合的三种 Coincident mate alignment 都解析成相同的物理朝向，那么当前重试机制仍会返回 `BottomFaceOrientationMismatch`。这种情况下，下一步需要根据法向向量显式计算修正旋转，在 mate 前或 mate 后主动旋转组件。

## 真实验证小面 normal fallback 与前端 Capture Layout

### 时间

- 2026-06-25

### 当前状态

- 已实现小面 normal fallback：
  - 主路径：`PlaneParams`；
  - 备用路径：tessellated normals；
  - 备用路径：从 tessellated triangle points 拟合平面 normal。
- 已用单元测试覆盖 triangle normal fitting 辅助逻辑。
- 前端已新增 `Capture Layout`。
- 后端已新增 `/api/demo/capture-common-base-layout`。
- 最新 MCP 发布目录为：`artifacts/solidworks-mcp-20260625-163843`。

### 待真实验证

1. 从 `artifacts/solidworks-mcp-20260625-163843` 重启 MCP。
2. 打开或初始化一个包含 A/B/C 且具备底面映射的装配体。
3. 选择并记录此前容易 `normal=null` 的小底面。
4. 检查 `face_mappings.json`，确认 `localNormal` 和 `worldNormal` 不再是 `null`。
5. 在前端点击 `Capture Layout`。
6. 确认 `demo/captured_common_base_layout.json` 已更新。
7. 在前端点击 `Replay Layout`。
8. 确认组件位置按新捕获的 layout2d 回放。

### 剩余风险

- SolidWorks tessellation API 在不同面类型和文档状态下可能表现不同。如果 tessellated normals 和 tessellated triangle points 都不可用，小面仍可能返回 `normal=null`。
- 如果某些拓扑的三角点顺序不稳定，拟合出的 normal 方向可能还需要结合周边几何或组件 transform 做进一步方向校正。

## Common Base 底面朝向自动修正仍需二阶段方案

### 时间

- 2026-06-25

### 当前进展

- 已完成第一版显式旋转修正：
  - 根据 A 的底面 normal 和 B/C 的底面 normal 计算旋转轴、旋转角；
  - 尝试正向角度和反向角度；
  - 失败时回滚组件；
  - 返回 `orientationCorrections` 供日志分析。
- 单元测试和构建验证已通过。

### 真实验证问题

- B 在旋转后重新 probe 记录底面时，normal 变成 `null`，导致工具无法确认旋转是否真的修正了底面朝向。
- C 在 mate 前 normal 与 A 一致，但 Coincident mate 后又变为 mismatch，说明“mate 求解”本身可能改变组件朝向。
- 因此，当前第一版“mate 前显式旋转”仍不足以稳定解决底面朝向一致性。

### 后续推荐方案

1. 将自动修正拆成两段：
   - mate 前可做一次预修正；
   - mate 后必须再做一次 orientation check 和二次显式修正。
2. 二次修正时优先保持已经建立的共面关系：
   - 尽量绕共同底面法向或底面中心进行受控旋转；
   - 修正后重新移动底面中心，避免 layout2d 坐标漂移。
3. 增强旋转后的面重新识别：
   - 记录更多几何特征，例如 normal、area、local center、leaf full name；
   - 当 SelectFaceByName 选中后 normal=null 时，增加候选面扫描 fallback。
4. 增加诊断工具：
   - 列出当前装配体中的 mates；
   - 标记是否存在重复 Coincident mate；
   - 输出每个组件的底面 normal、bottom center、Transform2。
5. 在真实 SolidWorks 中建立最小验证样本：
   - 只包含 A/B 两个组件；
   - 单独验证“共面后朝向修正”；
   - 再扩展到 A/B/C 和更多组件。

### 暂不建议

- 暂不继续通过反复添加/撤销 mate alignment 猜测 SolidWorks 行为。此前已经观察到这会带来重复配合风险。

### 2026-06-26 更新

- 已按该方案接入第一版 `PostMate` 二阶段修正：
  - 先建立一次 Coincident mate；
  - rebuild；
  - 再根据底面 normal 做显式旋转修正；
  - 最后再做 orientation check。
- `orientationCorrections` 已新增 `Stage` 字段，当前值预期为 `PostMate`。

仍待继续：

1. 发布新版 MCP 并做真实 SolidWorks 验证。
2. 如果 B 仍出现旋转后 `normal=null`，需要实现候选面扫描 fallback。
3. 如果 mate 后显式旋转受到配合约束影响，需要考虑：
   - 临时抑制相关 mate 后修正；
   - 或改为在建立 mate 前先通过 Transform2 直接设置姿态，再只做一次共面验证；
   - 或新增专用 Transform2 设置接口，避免 `RotateComponent` 乘法顺序不确定。
4. 补充 mate 诊断工具，列出当前 assembly 中的 mate，便于确认是否仍有重复配合。

### 2026-06-26 追加：PostMate 旋转默认关闭

- 真实运行中已观察到 `Common Base` timeout。
- 判断原因是 PostMate 阶段对已建立 Coincident mate 的组件执行 `RotateComponent`，可能触发 SolidWorks 长时间约束求解。
- 当前已将 `enablePostMateOrientationCorrection` 默认设为 `false`。
- 后续若继续实现自动朝向修正，优先考虑：
  1. 新增 mate 诊断和 mate suppression 能力；
  2. 在抑制相关 mate 后旋转，再恢复 mate；
  3. 或直接用 Transform2 设置初始姿态，再建立 mate；
  4. 避免在强约束状态下直接旋转组件。

### 2026-06-26 追加：已选择并实现方案 3

- 已接入“mate 前 Transform2 朝向预修正”。
- `enablePreMateOrientationCorrection` 默认 `true`。
- 默认流程不再等待 PostMate 旋转，而是在建立 mate 前修正组件姿态。
- PostMate 旋转仍保留为实验开关，但默认关闭。

仍待继续：

1. 发布新版 MCP 并进行真实 SolidWorks 验证。
2. 如果 B/C 修正后仍无法稳定 probe normal，需要实现候选面扫描 fallback。
3. 如果 Transform2 旋转方向仍不稳定，需要新增更明确的 Transform2 设置接口，而不是依赖当前 `RotateComponent` 的矩阵乘法行为。

### 2026-06-26 追加：新版 MCP 启动受 Device Guard 影响

- 新发布的 `artifacts\solidworks-mcp\SolidWorksMcpApp.exe` 被 Windows Device Guard 阻止。
- 当前可行方向是使用构建输出 DLL：

```text
dotnet vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\SolidWorksMcpApp.dll
```

- 但该 DLL 需要有一个稳定的前台/托盘会话保持运行。
- 后端已改为通过 `dotnet <dll> --proxy --client DemoBackendArrange` 连接 MCP。
- 后续需要解决发布 exe 的信任/签名/白名单问题，或固定采用 DLL 启动方式并写入正式启动脚本。

### 2026-06-26 追加：建议新增 MCP direct stdio 模式

背景：

- `SolidWorksMcpHub` 命名管道/托盘 Hub 在多次联调中反复出现连接不稳定、权限隔离、Device Guard 阻止 exe、proxy 无法连接 Hub 等问题。
- 这些问题会干扰前端/后端/MCP 的核心 demo 链路验证。

建议方案：

- 在 MCP app 中新增一个 direct stdio 模式，例如：

```cmd
dotnet SolidWorksMcpApp.dll --stdio
```

- 该模式下 MCP app 不启动托盘 Hub，也不连接 `SolidWorksMcpHub`。
- 后端直接以子进程方式启动 MCP app，并通过 stdin/stdout 通信。
- 这样后端和 MCP 是父子进程关系，避免：
  - 命名管道权限隔离；
  - Hub 是否已启动的问题；
  - proxy 自动连接 Hub 的不确定性；
  - Device Guard 对新发布单文件 exe 的拦截。

推荐实现步骤：

1. 在 `SolidWorksMcpApp` 中新增 `--stdio` 参数分支。
2. `--stdio` 分支直接构建 MCP session host，使用当前进程 stdin/stdout 作为 transport。
3. 后端新增或复用 `DEMO_MCP_MODE=stdio`，命令改为：

```cmd
DEMO_MCP_COMMAND=dotnet
DEMO_MCP_ARGS=<SolidWorksMcpApp.dll> --stdio
DEMO_MCP_CWD=<SolidWorksMcpApp.dll 所在目录>
```

4. 保留现有 `--proxy` / Hub 模式，用于托盘场景。
5. Demo 联调默认使用 direct stdio 模式。

收益：

- 启动链路更短。
- 不依赖 Hub 常驻进程。
- 更适合自动化测试和前后端联调。
- 遇到错误时，stderr/stdout 更容易被后端捕获并展示。

### 2026-06-26 追加：Common Base 超时复盘

- 最新一次 `Common Base` 前端返回 `MCP execution failed: TimeoutError:`。
- MCP Hub 日志显示 `FinalizeCommonBaseAssembly` 实际已经完成：
  - 开始时间：16:42:48
  - 完成时间：16:46:02
  - 总耗时：约 194.6 秒
- 后端当前默认 `DEMO_MCP_TIMEOUT_SECONDS=180`，因此后端在 MCP 完成前约 14.6 秒先超时返回。
- 这次不是 Hub/Proxy 连接失败，而是 SolidWorks 侧真实执行耗时超过后端默认 timeout。
- MCP 返回的真实结果仍是 `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`，说明 `commonBaseReady=false` 是合理状态。

后续计划：

1. 短期测试时将 `DEMO_MCP_TIMEOUT_SECONDS` 提高到 420 秒，先完整拿到 MCP 返回结果。
2. 进一步给 `FinalizeCommonBaseAssembly` 增加阶段耗时日志，拆分统计 probe、PreMate 修正、mate、rebuild、save、screenshot 等耗时。
3. 将截图导出改为可选，Common Base 验证阶段优先减少截图/保存带来的额外耗时。
4. 继续推进 direct stdio MCP 模式，降低 Hub/proxy 启动链路的不确定性。

### 2026-06-26 追加：朝向诊断已可见，待真实运行确认

- 已将 MCP 返回的 `orientationCorrections` 与 `orientationChecks` 保存到 `demo_state.json`。
- 前端已新增 `Orientation` 诊断面板，用于查看：
  - 修正是否被触发；
  - 修正前/后的 world normal；
  - 旋转轴与角度；
  - 最终每个组件与 A 的 dot 值；
  - 具体哪个组件 mismatch。
- 待下一次真实 `Common Base` 运行后，根据诊断结果决定：
  1. 如果 PreMate 修正没有触发，检查面映射 normal 和修正判断逻辑。
  2. 如果 PreMate 修正成功但 mate 后失败，优先考虑 Transform2 初始姿态设置接口或 mate 后受控修正。
  3. 如果某个组件 normal 读取异常，继续实现候选面扫描 fallback。

### 2026-06-26 追加：SelectFaceByName 需要从“移动鲁棒”升级到“旋转/mate 鲁棒”

- 当前面映射已经不是早期的纯 world center 记录，已经支持 leaf-local center、area、normal，因此对普通组件移动是有一定鲁棒性的。
- 但最新 Common Base 诊断显示：
  - B/C 最终 probe 到的 face area 与记录底面 area 明显不一致；
  - 说明旋转或 mate 求解后，当前候选面评分可能选到了相邻小面。
- 后续需要增强：
  1. area/normal 作为强约束，而不是弱惩罚；
  2. 选面后必须校验 probe 结果与记录值；
  3. 返回候选面评分诊断；
  4. 如果无可靠候选，明确返回失败，而不是继续 mate；
  5. 统一 MCP 实际使用和后端检查使用的 `face_mappings.json` 路径。

### 2026-06-26 追加：SelectFaceByName 强校验已完成，仍待真实验证

- 已完成 area/normal/center 强约束与 top candidates 诊断。
- 预期行为：
  - 如果 B/C 的真实底面可被可靠找回，`SelectFaceByName` 返回 `Success=true`；
  - 如果只能找到相邻小面/侧面，`SelectFaceByName` 返回 `Success=false`，并说明 center/area/normal 哪个条件失败。
- 仍待完成：
  1. 停止旧 MCP 后发布/启动新版 MCP；
  2. 真实 SolidWorks 中重新执行 `Common Base`；
  3. 根据 `faceSelection.diagnostics` 判断是否需要放宽阈值或继续做 Persistent Reference；
  4. 统一 `face_mappings.json` 路径。

### 2026-06-26 追加：强校验真实验证后的新结论

- 新版 MCP 已构建并完成一次真实 `Common Base` 验证。
- 强校验已生效：
  - B-1 最终 orientation check 被拒绝，原因 `center distance 0.407875m > 0.002000m`；
  - C-1 最终 orientation check 被拒绝，原因 `center distance 0.280773m > 0.002000m`。
- 这说明当前问题已经不再是“误选小面后仍返回成功”，而是更清晰地暴露为：

```text
旋转/mate 后，旧 face mapping 中保存的 leaf-local center 已经不适合作为后续强约束。
```

后续优先级：

1. 统一 `face_mappings.json` 路径。
2. 研究并实现 SolidWorks Persistent Reference，用 persistent reference 找回同一个 IFace2。
3. 在没有 persistent reference 前，考虑在 PreMate 修正/共面配合后重新写入 post-common-base face mapping snapshot。
4. Common Base 流程中，如果强校验失败，返回“映射已因姿态变化失效，需要重新记录或刷新映射”，而不是继续自动修正。

### 2026-06-26 追加：Persistent Reference 已接入，待干净状态重录验证

已完成：

- 后端和 MCP 的默认 `face_mappings.json` 路径已统一到：

```text
artifacts\solidworks-mcp\face_mappings.json
```

- `RecordFaceMapping` 已尝试写入 SolidWorks Persistent Reference：

```json
"persistentReferenceBase64": "..."
```

- `SelectFaceByName` 已改为：
  1. 优先用 `persistentReferenceBase64` 调用 SolidWorks `GetObjectByPersistReference3`；
  2. 若持久引用不存在或解析失败，再使用当前的 leaf-local center / area / normal 强校验候选面逻辑。
- `InitializeCommonBaseAssembly` 已增加已有文件复用逻辑，避免 reset 后同名 assembly 仍打开时再次 SaveAs 失败。

当前限制：

- 现有 A/B/C 映射是旧数据，没有 `persistentReferenceBase64` 字段。
- 当前 `ABC_arrange_demo.SLDASM` 已经过 Common Base / mate / rotation 尝试，B/C 旧几何映射无法再通过强校验自动选中，因此不能在这个状态下自动 “SelectFaceByName -> RecordFaceMapping” 刷新持久引用。
- 因此 Persistent Reference 代码已接入，但还没有完成真实链路验证。

推荐下一步验证：

1. 回到干净初始化状态：
   - 删除或关闭旧的 `ABC_arrange_demo.SLDASM`；
   - `Reset`；
   - `Initialize`；
   - 不先执行 `Common Base`。
2. 在 SolidWorks UI 中依次选中 A/B/C 的真实底面，并运行记录脚本或前端记录功能。
3. 检查 `artifacts\solidworks-mcp\face_mappings.json`，确认 A/B/C 都出现：

```json
"persistentReferenceBase64": "..."
```

4. 再执行 `Common Base`，观察：
   - `SelectFaceByName` 是否通过 persistent reference 成功；
   - B/C 是否仍出现 center distance 大偏差；
   - orientationChecks 是否仍失败。

如果仍失败：

- 优先实现 post-common-base face mapping snapshot：
  - Common Base 前记录旧映射；
  - PreMate / mate 后，用当前已知选中的底面重新写一份 `postCommonBaseMapping`；
  - 后续 orientation check / Replay Layout 优先使用该快照。
- 同时继续评估 Persistent Reference 在保存、重开、子装配体旋转、mate 求解后的稳定性。

### 2026-06-29 追加：中文 faceName 在命令行链路中的编码问题

- 通过后端调试接口记录 A-1 底面时发现，PowerShell / here-string 里直接传中文 `底面`，在进入 MCP 工具参数后可能变成 `??`。
- 如果直接写入映射文件，会生成错误键：

```json
"??": {
  "persistentReferenceBase64": "..."
}
```

- 当前已在后端 `record_selected_face` 调试路径中增加临时修复：
  - 若 MCP 写出 `??`；
  - 且后端请求中的原始 faceName 是 `底面`；
  - 则将 `??` 映射复制回 `底面` 并删除 `??`。

仍待完善：

1. 从根源统一 CLI / MCP runner / proxy 的 UTF-8 编码，避免中文参数被替换成 `??`。
2. 面记录脚本在 Windows CMD/PowerShell 下建议：
   - 直接省略 `--face`，使用脚本默认的 `\u5e95\u9762`；
   - 或显式传 ASCII 名称，如 `bottom`，避免控制台编码问题。
3. 长期建议支持中文显示名与内部稳定 key 分离，例如内部统一使用 `bottom`，前端显示 `底面`。

### 2026-06-29 追加：Persistent Reference 验证结论

- A/B/C 底面均重新记录并写入 `persistentReferenceBase64` 后，`Common Base` 已真实运行通过。
- `orientationChecks` 显示 A/B/C 均通过 Persistent Reference 选中底面，且 `matchesBase=true`。
- 此前 B/C 的 `center distance ... > 0.002m` 问题在本次验证中消失。

待继续：

1. 继续验证 `Replay Layout`，确认 Common Base 成功后 layout2d 回放仍能正确移动组件。
2. 仍需解决中文 faceName 在命令行链路中可能变成 `??` 的根因。
3. `post-common-base face mapping snapshot` 暂时降级为备用方案：如果后续更多真实装配体中 Persistent Reference 失效，再实现该 fallback。
### 2026-06-29 追加：MCP Hub/Proxy 链路需要稳定化

现象：

- 在尝试自动制作 `demo\X_reference.SLDASM` 时，后端正式接口与临时 MCP 调用均在连接阶段失败：

```text
System.IO.IOException: The server shut down unexpectedly.
```

- 重启 MCP Hub 后，日志只显示：

```text
Hub pipe server starting on 'SolidWorksMcpHub'
托盘服务已启动
```

但随后进程退出，直接 pipe 连接返回：

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

待处理方向：

1. 将 MCP Hub 启动方式脚本化，避免手动/隐藏/可见窗口启动行为不一致。
2. 启动后增加健康检查：
   - 确认 `dotnet`/`SolidWorksMcpApp` 进程存在；
   - 确认 `\\.\pipe\SolidWorksMcpHub` 可连接；
   - 执行一次轻量工具，如 `Ping` 或 `ListComponents`。
3. 若 `dotnet SolidWorksMcpApp.dll` 作为托盘/Hub 会话不稳定，优先实现或恢复 direct stdio MCP 模式，减少 Hub/proxy 中间层。
4. 后端启动前应检查 MCP health，避免用户点击前端按钮后才暴露 `server shut down unexpectedly`。

影响：

- 当前 `X_reference` 自动制作流程被阻塞。
- 现有 CAD 操作方案本身仍可复用，待 Hub/Proxy 链路恢复后继续执行即可。

### 2026-06-29 追加：操作链路不稳定的根因与当前修复

本次排查结论：

- 最大的不稳定源不是 `MoveComponent` / `RotateComponent` 本身，而是 MCP Hub/proxy 启动与连接链路。
- DLL 启动模式下，`dotnet SolidWorksMcpApp.dll --proxy` 中的 `Environment.ProcessPath` 实际指向 `dotnet.exe`。
- 旧逻辑在自动拉起 Hub 时可能只启动裸 `dotnet.exe`，导致 proxy 侧看到：

```text
System.IO.IOException: The server shut down unexpectedly.
```

- 手动或脚本启动托盘 Hub 时，还可能遇到命名管道生命周期不稳定：

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

已完成的止血修复：

1. 新增 `SolidWorksMcpApp --stdio-direct`，后端可直接走 MCP stdio，不经过 Hub/proxy。
2. 新增 `SolidWorksMcpApp --headless-hub`，需要 Hub 时可无托盘保持前台会话。
3. 修复 DLL 模式下 proxy 自动启动 Hub 的逻辑，避免启动裸 `dotnet`。
4. 后端默认改为优先使用 direct stdio。
5. `McpToolRunner` 增加 stdin BOM 容错，降低 PowerShell 调试命令误报。

仍需继续：

1. 给 direct stdio 模式补正式启动说明和健康检查命令。
2. 后端 `/api/health` 增加 MCP 轻量工具探测，而不仅是配置回显。
3. 前端按钮执行前先显示 MCP health 状态，避免用户点击后才看到底层连接错误。
4. 长期保留 Hub/proxy，但将其降级为可选模式；演示和自动化优先 direct stdio。

### 2026-06-29 追加：旋转操作为何仍可能不稳定

即使 MCP 链路已稳定，旋转仍有 CAD 约束层面的风险：

- `RotateComponent` 本质上修改组件 `Transform2`。
- 如果组件已经被 common-base mate、其他重合配合、固定状态或子装配体内部约束影响，SolidWorks 可能触发复杂求解。
- 在 mate 后绕任意轴旋转尤其危险，可能导致长时间重建、旋转被约束抵消，或者面映射结果变化。

当前较稳策略：

- 对于制作 `X_reference` 这类对照装配体，优先在已共底面的状态下绕共同底面法向旋转。
- 对于“自动朝向修正”，优先在 mate 前修正姿态，避免在强约束状态下旋转。
- 对于真实装配体复原，长期更推荐记录并恢复完整 `Transform2` 或显式目标姿态，而不是只依赖增量旋转。

### 2026-06-29 追加：底面中心 world/local 坐标语义需要继续验证

本次制作 `X_reference_spread` 时发现：

- B/C 的 `sourceTransform` 已经随 `MoveComponent` 改变。
- 但旧版 `CaptureCommonBaseLayoutFromAssembly` 捕获到的 `layout2d` 没有变化。
- 原因是 `GetSelectedFaceMappingProbe` 把 `IFace2.GetBox()` 的中心当成 world center 使用。
- 在嵌套子装配体/leaf component 场景中，该中心更接近 leaf/local 坐标，需要通过 `IComponent2.GetTotalTransform(true)` 转成 assembly world center。

已完成修复：

- `GetSelectedFaceMappingProbe` 改为：
  - `localCenter = BoxCenter(face.GetBox())`
  - `worldCenter = GetTotalTransform(true) * localCenter`
- `RecordFaceMapping` 也同步保存更明确的 leaf-local center。
- 重新捕获 `X_reference_spread` layout2d 已成功。

仍需继续关注：

1. 旧 face mapping 中的 `localCenter` 是按旧逻辑记录的；当前 A/B/C 依赖 Persistent Reference，不受影响。
2. 如果未来遇到没有 Persistent Reference 的旧映射，geometry fallback 可能仍需要兼容旧 localCenter 语义。
3. 下一步 Replay Layout 需要验证修正后的 world center 是否也能正确驱动移动复原。

### 2026-06-29 追加：Replay Layout 闭环已通过，但姿态回放仍待做

闭环验证结论：

- 新建 assembly、导入 A/B/C、执行 Common Base、Replay `x_reference_layout2d.json` 已通过。
- replay 后再次捕获 layout2d，与目标 layout2d 的误差约 `2.78e-17`，可视作完全一致。

已修复的问题：

- `ApplyCapturedCommonBaseLayout` 原本使用 `GetSelectedFaceCenter()` 计算当前底面中心。
- 该接口没有走 `GetTotalTransform(true)`，在嵌套组件场景下会导致 replay 偏移。
- 现已改为使用 `GetSelectedFaceMappingProbe().WorldCenter`。

仍待继续：

1. 当前 replay 只恢复底面中心的 2D 位置，不恢复组件自身旋转姿态。
2. `X_reference_spread` 中 B/C 的 `sourceTransform` 已包含旋转信息，后续可实现 Transform2 姿态回放：
   - 先对齐底面法向；
   - 再恢复绕底面法向的平面内旋转角；
   - 最后恢复 layout2d 位置。
3. `GetSelectedFaceCenter()` 仍可能在其他旧流程中被使用，建议后续逐步替换为 probe world center 或修复其内部实现。

### 2026-06-29 追加：layout2d 平面内 theta 回放已完成，完整 3D 姿态仍待做

已完成：

- `layout2d` 已新增 `thetaDegrees/thetaAxis`。
- 捕获时会从组件 `Transform2` 的 X/Y/Z 轴中选择最适合投影到共底面的轴作为 theta 参考轴。
- 回放时会先恢复 theta，再重新 probe 底面中心并恢复 x/y。
- 真实 SolidWorks 闭环已通过：

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

过程中发现：

- `RotateComponent` 的角度正方向与 layout 投影数学正方向相反。
- 当前只在 `ApplyCapturedCommonBaseLayout` 的 theta 回放中对角度取反，没有修改底层 `RotateComponent`，避免影响已有功能。

仍待继续：

1. 当前完成的是“共底面平面内朝向”恢复，不是完整 3D `Transform2` 姿态恢复。
2. 如果未来需要恢复任意 3D 姿态，应设计明确的 `SetComponentTransform2` 或“保存/恢复完整 Transform2”工具。
3. `dotnet test` 目前被 Windows 应用控制策略阻止加载测试 DLL，需要后续解决测试运行环境或使用替代测试 runner。

### 2026-06-30 追加：n 组件项目化能力的后续注意事项

已完成第一轮：

- 状态和前端不再强依赖固定 A/B/C，可由 layout JSON 中的 `components` 同步出 n 个组件。
- 前端支持选择/上传 layout JSON，并显示每个组件的 `x/y/theta`。
- 已加入批量面映射验证入口。

仍待继续：

1. 当前上传的是 layout JSON 内容，不上传 CAD 文件本体。
   - 真实项目中，子装配体文件路径仍需要在 layout JSON 中可被本机访问。
   - 后续若需要 Web 上传 CAD 文件，需要单独设计文件存储、路径映射和安全策略。
2. 批量面映射真实验证依赖当前 SolidWorks 活动装配体。
   - 如果打开的是错误 assembly，即使映射文件存在，`select_face_by_name` 仍可能失败。
   - 后续可在验证前增加 active document / assemblyPath 一致性检查。
3. 前端画布仍使用固定世界范围。
   - n 组件或更大布局时，应根据 layout bounds 自动缩放。
4. 当前 n 组件同步主要来自 captured layout JSON。
   - 后续可增加“从原始装配体自动发现顶层组件并批量生成配置”的工具。
### 2026-06-30 追加：前端真实闭环后续优化计划

本次前端上传 `x_reference_layout2d_theta.json` 后，`Initialize -> Verify Faces -> Common Base -> Replay Layout` 已通过真实 SolidWorks 验证，并通过二次 capture 复核了 `x/y/theta` 误差。

仍建议继续补齐：

1. MCP / 后端健康检查稳定化
   - `/api/health` 目前主要检查后端配置。
   - 后续应增加 MCP Hub 可连接性、可用工具列表、SolidWorks active document 的轻量检查。
2. Active assembly 一致性检查
   - 在 `Verify Faces`、`Common Base`、`Replay Layout` 前检查当前 SolidWorks 活动装配体是否与 `demo_state.json.assemblyPath` 一致。
   - 避免用户重启 SolidWorks 或切换窗口后，对错误 assembly 执行操作。
3. 前端画布自动缩放
   - 当前前端布局视图仍偏固定范围。
   - n 个组件或大尺寸 layout 时，应根据 layout bounds 自动 fit。
4. n 组件自动发现
   - 当前 n 组件主要由 layout JSON 的 `components` 驱动。
   - 后续应支持从原始装配体自动发现顶层子装配体，生成待记录/待验证清单。
5. 编码显示问题
   - PowerShell/日志中仍可能把 `底面`、角度符号等显示为乱码。
   - 功能不受影响，但建议后续统一 CLI 输出编码和日志编码策略。
6. Replay 后自动误差报告
   - 当前已可手动二次 capture 并比较。
   - 后续可在 `Replay Layout` 后自动 capture 当前布局，直接返回每个组件的 `xy_error/theta_error`。
### 2026-06-30 追加：健康检查与 Replay 误差报告后的待办

已完成：
- 后端已增加 `/api/demo/mcp-health`。
- `Verify Faces` 前已增加 active assembly 一致性检查。
- `Replay Layout` 后已自动 capture 当前布局并写入 `state.lastRun.replayValidation`。
- 前端已显示 `Replay Check`。

仍待继续：

1. 将 MCP Health 做成前端显式按钮或状态灯
   - 当前接口已存在，但前端没有独立入口。
   - 后续可以在工具栏增加 `Health` 按钮，显示 active document 与 state assembly 是否一致。
2. 对 `Common Base` 和 `Replay Layout` 前也增加更温和的一致性提示
   - 这些工具会通过 `assemblyPath` 打开目标文件，因此不一定要直接 blocked。
   - 更适合返回 warning，让用户知道 SolidWorks 当前窗口可能不是目标 assembly。
3. Replay 自动复核的阈值可配置化
   - 当前默认 `xyError <= 1e-6m`，`thetaError <= 1e-4deg`。
   - 真实大装配体可能需要根据单位、复杂度和 SolidWorks 解算误差调整阈值。
4. 将 `demo/replay_validation_layout2d.json` 纳入忽略策略
   - 该文件是运行时复核产物，不建议提交。
5. 真实 SolidWorks 再验证
   - 重启后端；
   - 前端执行 `Replay Layout`；
   - 检查 `Replay Check` 是否显示 matched，且误差接近 0。
### 2026-06-30 追加：双 face_mappings 路径问题已确认并需固化

已确认问题：
- 后端 health 显示的 `faceMappingPath` 是 `artifacts\solidworks-mcp\face_mappings.json`。
- MCP 直接 probe 时曾使用 `vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\face_mappings.json`。
- 这会导致后端认为映射存在，但 MCP 实际使用旧映射，最终表现为 B/C 选面失败或 orientation probe error。

临时解决：
- 重启后端时显式设置 `DEMO_FACE_MAPPING_PATH`。
- 真实验证已通过。

仍待固化：
1. 新增后端启动脚本
   - 统一设置：
     - `DEMO_MCP_MODE`
     - `DEMO_MCP_COMMAND`
     - `DEMO_MCP_CWD`
     - `DEMO_FACE_MAPPING_PATH`
     - `DEMO_MCP_TIMEOUT_SECONDS`
2. 在 `/api/health` 或 `/api/demo/mcp-health` 中增加一次 MCP 侧 mapping path 回显
   - 目前 `mcp-health` 只读 active document。
   - 后续可以增加轻量 probe 或专门工具，明确显示 MCP 实际使用的 `face_mappings.json`。
3. 前端 Health 状态灯
   - 显示 MCP 连接状态；
   - 显示 active assembly 是否匹配；
   - 显示 mapping path 是否统一。
### 2026-06-30 追加：MCP/后端启动与 Health 固化已完成，后续仍需补长期稳定项

本轮已完成：
- 新增正式后端启动脚本 `scripts/start_demo_backend.cmd`，固定 MCP 模式、DLL 启动目录、统一 face mapping 路径和 420 秒超时。
- MCP 新增 `get_face_mapping_store_info`，用于回显 MCP 进程实际使用的 `face_mappings.json`。
- 后端 `/api/demo/mcp-health` 已能返回：
  - active assembly 是否匹配 `demo_state.json.assemblyPath`；
  - 后端 mapping path；
  - MCP mapping path；
  - 两者是否一致。
- 前端新增 `Health` 按钮和状态面板。

仍待继续：
1. 将 `scripts/start_demo_backend.cmd` 纳入正式使用说明和日常测试流程。
2. 如未来继续遇到 MCP Hub 多实例/旧进程问题，补充独立的 MCP Hub 管理脚本：
   - 查询当前 hub 进程；
   - 显示启动路径；
   - 一键停止旧 hub；
   - 一键以 DLL 方式启动新版 hub。
3. Health 目前依赖新 MCP 工具，旧 MCP 未重启时会报 unknown tool；这正好可以提醒用户当前运行的不是新版 MCP。
### 2026-06-30 追加：真实项目化能力详细规划

目标：
- 从当前 A/B/C 演示，推进到“原始装配体 X 由 n 个子装配体组成”的通用工作流。
- 支持从 X 捕获 layout2d，再在新 assembly 中导入 n 个子装配体、共底面、按 layout2d 恢复位置和 theta。

推荐分阶段实现：

#### 阶段 1：n 个子装配体自动发现

目标：
- 给定原始装配体 X，自动列出可作为布局单元的子装配体/零件。

建议新增 MCP 高层工具：
```text
DiscoverLayoutComponentsFromAssembly
```

输入：
- `sourceAssemblyPath`
- `scope`：`topLevelOnly` / `recursive`
- `includeParts`
- `includeSuppressed=false`

输出：
- `assemblyPath`
- `components[]`：
  - `componentName`
  - `componentPath`
  - `filePath`
  - `isAssembly`
  - `isSuppressed`
  - `transform`
  - `candidateBottomFaces` 初版可为空，后续再自动候选。

后端变化：
- 新增 `ProjectLayoutConfig` 或扩展现有 `DemoState`，支持 n 个组件。
- 新增接口：
  - `POST /api/demo/discover-components`
  - `POST /api/demo/import-discovered-components`

前端变化：
- 增加“源装配体路径”输入。
- 显示 discovered components 表格。
- 允许用户勾选哪些组件参与 layout replay。

风险：
- 真实装配体可能存在嵌套子装配体、轻量化组件、虚拟组件、压缩组件。
- 第一版建议只支持 top-level resolved components，避免一次吃太多复杂度。

#### 阶段 2：layout JSON 自动生成配置

目标：
- 从原始装配体 X 一键生成可 replay 的 layout JSON。

建议增强现有 `CaptureCommonBaseLayoutFromAssembly`：
- 确保输出包含：
  - `sourceAssemblyPath`
  - `baseComponentName`
  - `basePlane`
  - `createdAt`
  - `components[]`：
    - `componentName`
    - `filePath`
    - `bottomFaceName`
    - `layout2d.x`
    - `layout2d.y`
    - `layout2d.thetaDegrees`
    - `layout2d.thetaAxis`
    - `sourceTransform`
    - `faceMappingFound`
    - `faceMappingPath`

后端新增流程：
```text
Discover -> Verify Faces -> Capture Layout JSON -> Save Project Config
```

前端变化：
- 增加“Capture from Source Assembly”按钮。
- 捕获成功后自动加载 layout JSON。
- 表格中显示每个组件的 filePath 是否存在、face mapping 是否存在。

风险：
- 如果底面映射缺失，capture 不应直接失败整个项目；应返回“哪些组件缺失映射”的清单。

#### 阶段 3：前端 layout bounds 自动缩放

目标：
- 支持 n 个组件和大范围 layout，不再依赖固定 `WORLD_BOUNDS`。

实现建议：
- 根据当前 `state.components[].target` 与 `layoutInfo.components[].layout2d` 计算 bounds。
- padding 取最大尺寸的 10%-20%。
- bounds 最小宽高给默认值，避免所有组件重叠时画布塌缩。
- 保留手动 reset view / fit view。

前端数据：
- `worldBounds = computeLayoutBounds(components, layoutInfo)`
- block size 初版继续使用固定 fallback，后续可根据真实 bounding box 做比例显示。

风险：
- UI 画布只是 2D 操作视图，不应暗示其矩形尺寸等同真实 CAD 外形。

#### 阶段 4：Replay 后误差阈值可配置

目标：
- 不同项目可根据尺寸、单位、装配复杂度设置误差容忍度。

后端建议：
- 新增设置：
  - `DEMO_REPLAY_XY_TOLERANCE_METERS`
  - `DEMO_REPLAY_THETA_TOLERANCE_DEGREES`
- 或在 Replay 请求体中传：
  - `xyToleranceMeters`
  - `thetaToleranceDegrees`
- `state.lastRun.replayValidation` 中记录实际阈值。

前端建议：
- 增加 compact settings 区：
  - XY tolerance
  - Theta tolerance
- Replay Check 显示：
  - `actual / tolerance`
  - 每个组件是否通过。

风险：
- 阈值过松会掩盖实际复原失败；默认值应保持严格，用户显式修改才放宽。

#### 阶段 5：批量面映射验证与问题清单

目标：
- n 个组件场景下，一个组件映射错误不应让用户只能从日志里找问题。

建议：
- `Verify Faces` 返回结构化表格：
  - componentName
  - faceName
  - selected
  - persistentReferenceUsed
  - centerError
  - areaError
  - normalDot
  - result
  - recommendedAction
- 前端高亮失败组件，并给出“重新记录此组件底面”的操作提示。

#### 推荐实施顺序

1. 先做前端 layout bounds 自动缩放。已完成。
   - 纯前端，风险最低，立刻提升 n 组件可用性。
2. 再做 Replay 阈值可配置。已完成。
   - 后端对比逻辑已存在，改动集中。
3. 再做 n 组件 discovery。下一步建议优先处理。
   - 涉及 SolidWorks 真实树遍历，测试成本更高。
4. 最后做 layout JSON 自动生成配置与批量问题清单。
   - 需要把 discovery、face mapping、capture 三块串成完整项目化工作流。

### 2026-06-30 追加：项目化能力第一轮完成后的下一步

已完成：
- 前端 layout bounds 自动缩放。
- Replay 阈值可配置。
- Replay Check 显示 `actual / tolerance`。

下一步建议：
1. 实现 `DiscoverLayoutComponentsFromAssembly` 的最小版本。
   - 只扫描 top-level resolved components。
   - 先返回 `componentName/filePath/isAssembly/transform`。
   - 不急着自动识别底面。
2. 后端新增 discovery 接口。
   - `POST /api/demo/discover-components`
   - 结果先不直接覆盖当前 state，而是返回候选列表。
3. 前端新增 discovered components 表格。
   - 允许用户选择组件。
   - 允许用户把选择结果同步到 state。
4. 之后再做“从 source assembly 捕获并生成 layout JSON 项目配置”。

注意：
- Discovery 应先保持只读，不修改 SolidWorks 文档。
- 第一轮不要自动推断底面，避免引入新的几何误判风险。
## 2026-06-30 22:06:48 待继续：n 组件发现后的真实项目化补齐

本轮已实现 `DiscoverLayoutComponentsFromAssembly`、后端同步接口和前端 Project Config 入口，但仍有以下限制：

1. 发现范围第一版以顶层 resolved 子装配体为主。
   - `recursive` 参数已预留，但真实项目中是否应包含嵌套子装配体，需要结合装配结构策略确认。
   - suppressed / lightweight / hidden 组件暂未做稳定发现与恢复。
2. 底面仍需人工记录或已有映射。
   - 发现组件只会填入默认 `bottomFaceName=底面`。
   - 后续需要自动建议底面候选，或提供批量面映射任务清单。
3. 项目 layout JSON 生成依赖当前组件列表和 face mapping。
   - 如果某个组件名称与映射不一致，Capture Project Layout 会被面映射校验阻断。
   - 后续需要在 UI 中显示“发现组件 / 已映射 / 未映射 / 可捕获”的矩阵状态。
4. 真实项目配置还缺少可复用配置文件。
   - 建议后续生成 `project_config.json`，包含 sourceAssemblyPath、component list、bottomFaceName、baseComponentName、outputPath、replay tolerances。
   - 前端可加载该配置，一键执行 discovery -> verify -> capture -> replay。
## 2026-07-06 15:17:34 待继续：真实 Recursive 发现的组件唯一性策略

- 已增加重复 `componentName` 阻断，避免递归发现后同步到不安全状态。
- 但这只是保护机制，不是最终解决方案。
- 后续如果必须支持递归层级中的同名组件，需要选择一种长期策略：
  1. 让 MCP 工具支持使用 `hierarchyPath` 精确定位组件；
  2. 或在同步时为递归组件生成稳定别名，并让后续 SelectFace/Move 支持该别名；
  3. 或业务上规定 layout 单元只能选择顶层组件，递归结果只用于检查和辅助。
- 下一步真实测试时，需要记录 10+ 装配体中是否存在重复实例名、嵌套同名组件、lightweight/suppressed 组件。

## 2026-07-06 15:09:37 待继续：10+ 子装配体真实闭环验证

本轮已补齐发现筛选、项目配置输出和面映射矩阵，但以下问题仍需要后续真实验证或继续实现：

1. 递归发现策略需要项目规则。
   - 已支持 `topLevelOnly` 与 `recursive` 参数。
   - 但真实装配体中，哪些嵌套子装配体应作为布局单元，仍需要结合业务定义。
2. suppressed / lightweight / hidden 组件仍不是稳定能力。
   - 当前发现仍主要依赖 resolved 组件。
   - 后续需要明确是否自动 resolve lightweight，以及是否报告 suppressed 组件。
3. 面映射矩阵还是状态展示，不是自动修复。
   - 已能显示 Missing/Ready/Verified。
   - 后续应增加“按组件触发记录/重录底面”的前端流程，以及自动底面候选推荐。
4. `project_config.json` 已生成，但还不能一键加载并驱动全流程。
   - 后续应支持导入 project config，自动恢复 source path、component list、layout path、tolerance 等配置。
5. Common Base 对 10+ 组件仍需重点压测。
   - 需要验证分批执行、失败组件隔离、重复 mate 诊断等能力。
## 2026-07-06 15:32:27 待继续：test1.SLDASM 后续项目化闭环

- 已完成只读发现验证：
  - 顶层发现 15 个子装配体。
  - 递归装配体发现 174 个 assembly。
  - 递归包含零件发现 1870 个候选。
- 下一步需要在重启后端后继续验证：
  1. 确认发现结果默认底面名从 `??` 归一化为 `底面`。
  2. 使用 `Top-level components` 选择 15 个顶层子装配体并执行 `Sync Selected`。
  3. 执行 `Verify Faces`，生成缺失底面映射清单。
  4. 对缺失项分批记录底面，避免一次处理 15+ 个组件时难以定位错误。
  5. 映射通过后执行 `Generate Config`，产出 `project_config.json` 和 layout JSON。
- 风险：
  - 真实装配体中 15 个顶层子装配体不一定全部都应作为布局恢复单元，需要结合业务含义筛选。
  - 递归包含零件的 1870 个候选规模过大，当前不建议直接同步。
  - 如果后续仍需支持递归布局单元，必须继续推进层级路径定位或稳定别名机制，避免同名组件歧义。

### 当前阻塞点：15 个顶层组件缺少底面映射

- `Sync Selected` 已完成，当前 demo state 已切换为 `test1.SLDASM` 的 15 个顶层子装配体。
- `Verify Faces` 返回 `blocked`，15 个组件均缺少 `底面` 映射。
- 下一步测试顺序：
  1. 在 SolidWorks 当前 `test1.SLDASM` 中，逐个选择每个顶层子装配体的真实底面。
  2. 对每个选中的面调用 `Record Selected Face` 或脚本记录：
     `python scripts\face_mapping_record_probe.py --component "<componentName>" --face 底面`
  3. 每记录 3 到 5 个组件后运行一次 `Verify Faces`，避免 15 个组件全部记录完才发现某个面选错。
  4. 当 `Verify Faces` 对 15 个组件全部通过后，再继续 `Generate Config`。
  5. 若计划测试新装配体复原，再进入 `Initialize -> Common Base -> Replay Layout`。

### 2026-07-06 追加：无实体面的顶层组件处理

- `螺丝枪组件DDC-1` 在当前测试中无法通过 `record_first_face_mapping` 自动记录：
  - MCP 在该组件下未找到 solid-body face。
  - 这通常意味着该组件未解析、外部引用缺失、组件本身不含实体体，或实体在当前装配上下文不可见/不可读。
- 后续可选方案：
  1. 在项目配置中排除该组件，不作为 layout recovery 单元。
  2. 在 SolidWorks 中 resolve/open 该组件源文件，确认其实体体是否可见，再重新记录。
  3. 实现 Partial Mode：Common Base / Replay Layout 只处理已映射组件，并明确列出跳过项。
  4. 若业务上该组件必须参与布局，需补充“无实体组件”的替代锚点策略，例如使用参考面、坐标系或包围盒代理点。

### 2026-07-06 追加：14 组件目标装配体一次性导入超时

- 已验证 14 组件源侧链路：
  - `Verify Faces` 通过。
  - `test1_14_layout2d.json` 生成成功。
  - `test1_14_project_config.json` 生成成功。
- 但目标侧一次性 Initialize 失败：
  - `initialize_common_base_assembly` 尝试导入 14 个真实子装配体超过 15 分钟未返回。
  - 未生成 `demo\test1_14_replay.SLDASM`。
- 后续建议：
  1. 将 Initialize 拆成批处理：
     - 新建空 assembly。
     - 每次插入 1 到 3 个组件。
     - 每步保存并返回进度。
  2. 在 C# 侧增加插入进度日志：
     - 当前第几个组件。
     - 组件路径。
     - 插入耗时。
     - 失败原因。
  3. 增加失败隔离：
     - 某个组件插入失败或超时，不阻塞整个项目。
     - 返回 skipped/failed 列表。
  4. 对大装配体优先测试“已存在目标 assembly 的 replay”，再测试“从空白 assembly 批量插入”。
  5. 前端增加大装配体模式：
     - 分批 Initialize。
     - 显示进度。
     - 允许跳过失败组件。
## 2026-07-06 追加：14 组件闭环测试下一步

当前已解决：

- 14 个组件一次性 Initialize 超时的问题，已通过批量追加导入缓解。
- 目标装配体实例名与源 layout `componentName` 不一致的问题，已通过插入后重命名修复。
- Common Base 一次性处理 14 个组件超时的问题，已改为批量处理；旧目标上已能返回具体失败批次，而不是直接超时。

仍需继续验证：

1. 在 `demo/test1_14_replay_batched_v2.SLDASM` 上重新执行目标实例名比对：
   - 期望：目标装配体 14 个顶层组件名与 `demo_state.json` 中 14 个 `componentName` 完全一致。
2. 执行批量 Common Base：
   - 期望：不再出现 `component not found`；
   - 如果失败，应根据 `commonBaseBatches` 和 `orientationChecks` 定位具体组件。
3. 执行 Replay Layout：
   - 期望：读取 `demo/test1_14_layout2d.json`，移动目标装配体 14 个组件。
4. 执行 Replay Check：
   - 期望：生成误差报告；
   - 若误差过大，下一步再区分是底面映射问题、实例名问题，还是 theta/旋转恢复问题。
## 2026-07-06 追加：14 组件测试暴露的真实底面映射问题

本轮测试说明：

- 批量 Initialize 和 Replay 调用链已经可以在 14 组件目标装配体上运行。
- 但 Common Base 不能依赖“随便选一个面”作为底面：
  - 任意面可能没有稳定 normal；
  - 即使有 normal，也可能与真实底面方向无关；
  - 会导致 Common Base orientation mismatch；
  - 后续 Replay Check 会出现局部大误差。

具体观察：

- `FL9A项目号A300.001-1` 和 `FL9A项目号A900.001-2` 在刷新任意面映射后，可以 probe normal，但法向与基准不一致。
- Replay Layout 的工具调用本身成功，但 `FL9A项目号A900.001-1` 出现约 `1.59m` 的 XY 误差。

建议下一步：

1. 增加“底面候选自动识别”能力：
   - 遍历组件实体面；
   - 过滤面积过小的面；
   - 优先选择法向接近全局/common-base 方向的较大平面；
   - 输出候选列表让用户确认。
2. 前端增加批量面映射状态：
   - Ready；
   - Missing；
   - Probe failed；
   - Normal mismatch；
   - Low confidence candidate。
3. Common Base 前增加预检：
   - 如果某个面是 `record_first_face_mapping` 低置信度补出来的，不应直接进入 Common Base；
   - 应提示用户确认真实底面。
4. 对重复实例名场景实现稳定 instance mapping：
   - 源组件名与目标导入实例名可能不同；
   - 当前临时方案是生成 `test1_14_layout2d_target_names.json`；
   - 长期应在初始化结果中返回 sourceName -> targetName 映射，并自动更新 layout/state。

## 2026-07-22 待完善：MCP 与 SolidWorks 桌面会话绑定

- 在受限/沙箱会话中直接启动 `--stdio-direct` 时，可能连接到没有打开文档的另一个 SolidWorks COM 实例；同一命令在可见 SolidWorks 所在桌面会话执行时可正确连接并保存。
- 后续应让后端暴露正式的 Save 接口，或在连接配置中显式锁定 SolidWorks 进程 ID，避免依赖启动者桌面会话和 ROT 的隐式选择。

## 2026-07-22 待实现：约束驱动的合理布局生成

### 1. 目标与工作流位置

新增一条与原始布局复原并行的分支：

```text
现有：源装配体 -> Capture Layout2D -> Common Base -> Replay Layout
新增：角色/包围盒 -> 约束求解 -> Constraint Layout2D -> Replay/Move
```

求解器只负责生成目标二维位置和旋转角；组件移动、回读验证、截图和保存继续复用当前稳定链路。

### 2. MVP 输入模型

- Common Base 已完成，所有底面法向与全局 `+Y` 同向。
- Y 坐标固定，决策变量只有 `(x, z, theta)`。
- 第一版 `theta` 取值限制为 `0/90/180/270°`；旋转 90° 或 270°时交换投影包围盒的宽度和深度。
- 组件角色：`gantry`、`transport`、`functional`、`glue`。
- 名称规则提供默认分类，项目 JSON 映射拥有更高优先级，例如：

```json
{
  "components": {
    "龙门模组-1": { "role": "gantry" },
    "传输模组-1": { "role": "transport" },
    "供胶模组-1": { "role": "glue" },
    "检测模组-1": { "role": "functional" }
  }
}
```

### 3. 空间与约束定义

- 将每个组件世界包围盒投影到 XZ 平面，得到中心、宽度、深度和旋转后的占用矩形。
- 龙门矩形 `G=[xmin,xmax]×[zmin,zmax]` 是布局边界，不直接作为完整实体障碍物；龙门内部的真实结构碰撞交由 SolidWorks 干涉检查。
- 根据龙门较长边自动确定中央传输走廊方向。

硬约束：

1. Y 高度和底面共面关系保持不变。
2. 功能模组之间不得重叠或接触。
3. 功能模组不得与传输模组重叠或接触。
4. 供胶模组必须位于龙门包围盒外部。
5. 所有输出位置必须在配置的全局求解边界内。

高优先级软约束：

1. 传输模组中心尽量靠近龙门中央，并沿龙门长边布置；允许沿长边少量超出。
2. 功能模组尽量位于龙门包围盒内部，并分配到传输走廊两侧。
3. 供胶模组尽量邻近龙门，满足配置的目标距离。

可放宽约束：

- 功能模组到龙门边界的 X 向间距初始为龙门 X 边长的 5%，Z 向间距初始为龙门 Z 边长的 5%。
- 无解时按 `5% -> 3% -> 1% -> 0` 逐级求解，每次放宽必须记录到结果中。
- 在可行解中继续优化总移动距离、整体紧凑度和传输走廊两侧的分布均衡性。

### 4. 输出格式与现有链路集成

输出继续兼容现有 Layout2D，并增加求解来源和验证信息：

```json
{
  "layoutSource": "constraint-solver",
  "baseComponentName": "龙门模组-1",
  "components": [
    {
      "componentName": "传输模组-1",
      "role": "transport",
      "layout2d": {
        "x": 0.0,
        "y": 0.0,
        "thetaDegrees": 0,
        "thetaAxis": "y"
      }
    }
  ],
  "constraintValidation": {
    "success": true,
    "appliedMarginRatio": 0.05,
    "relaxedConstraints": []
  }
}
```

当底面法向为 `+Y` 时，Layout2D 的两个平面坐标对应全局 X、Z；实现时应使用 `baseFrame` 的两个切向轴表达，避免将求解器硬编码到特定世界坐标系。

### 5. 建议实施阶段

1. **角色与几何输入**：增加项目角色映射模型；读取组件 Transform2 和包围盒；生成 XZ 投影数据。
2. **独立求解核心**：实现不依赖 SolidWorks 的纯数据约束求解模块，支持离散旋转、区域约束、非重叠约束和分级 margin relaxation。
3. **后端接口**：新增 `generate-constraint-layout`，输入组件角色和参数，输出 Constraint Layout2D、求解状态、放宽记录和约束诊断。
4. **执行集成**：将求解结果交给现有 Replay/Move 链路；保持 Common Base、面映射和移动服务不变。
5. **前端分支**：增加 `Captured Layout / Constraint Layout` 模式选择、角色编辑、求解参数和结果预览；求解成功后才允许 Apply。
6. **真实验证**：回读 Transform2/包围盒，检查数值约束，再调用 SolidWorks interference check 检查真实实体干涉。

### 6. 测试与验收标准

单元测试：

- 名称分类与 JSON 覆盖优先级。
- 包围盒在四种离散角度下的尺寸交换。
- 两矩形接触、重叠和安全间距判断。
- 传输走廊方向、功能模组两侧区域和供胶外部区域计算。
- `5/3/1/0%` 放宽顺序及诊断记录。
- 相同输入产生稳定、可复现的输出。

合成场景测试：

- `1 gantry + 1 transport + 1 glue + 2~4 functional` 可行场景必须生成无硬约束违规布局。
- 空间不足场景必须逐级放宽 margin，而不是返回无诊断的失败。
- 硬约束确实不可满足时必须返回 `infeasible` 和冲突说明，不得继续移动 SolidWorks 组件。

真实闭环验收：

1. Initialize 与 Common Base 成功。
2. Constraint Layout2D 生成成功且包含全部参与组件。
3. Apply 后回读的 XZ/theta 误差满足配置阈值。
4. 包围盒约束复检无硬违规。
5. SolidWorks interference check 无不允许的实体干涉。
6. 截图、求解报告、验证报告和目标装配体均成功保存。

### 7. 暂不纳入 MVP

- 任意连续角度旋转。
- 多个龙门或多个传输走廊的联合规划。
- 基于精确 B-Rep 的实时碰撞约束求解。
- 自动推断复杂工艺方向和装配顺序。
- VLM 自动判断组件角色或布局合理性。
## 2026-07-22 17:55 待继续：Constraint Layout 的 SolidWorks 执行事务

约束布局生成已经在真实五组件数据上成功，但 CAD 执行层仍有以下问题：

1. **超时不是事务回滚**
   - 一次带旋转 Replay 超时前已部分改变多个组件姿态。
   - 强制结束 MCP 只会结束调用，不会自动恢复 Transform2。
   - 后续需要在 Apply 前保存所有目标组件 Transform2，失败或超时时提供显式 rollback 工具。
2. **已配合大组件的 Transform2 可能长时间求解**
   - 默认关闭 Constraint Layout 的自动旋转。
   - 已加入固定 base component、零位移跳过、批量重建和临时 mate 抑制。
   - 当前受污染会话中仍阻塞，需要在干净 SolidWorks 会话复测，区分“代码仍有问题”和“文档求解状态已损坏”。
3. **mate 抑制范围需要进一步收窄**
   - MVP 仅对 `layoutKind=constraintGenerated` 生效，并扫描顶层 MateGroup 子特征。
   - 正式版本应在 Common Base 创建 mate 时为特征添加稳定前缀，只抑制本工作流创建的 mate，避免影响目标装配体中其他顶层配合。
4. **需要阶段日志和取消点**
   - 当前高层 COM 日志只有开始/结束，阻塞时无法判断停在 suppress、select/probe、Transform2 setter、restore 还是 rebuild。
   - 应为每个阶段和组件写进度日志，并支持后端取消后触发安全恢复。
5. **真实几何还需最终干涉检查**
   - 当前只保证投影包围盒不重叠。
   - 在 Apply 稳定后，应调用 SolidWorks `CheckInterference` 输出最终物理干涉报告。

下一次人工恢复步骤：关闭当前测试装配体且不要保存，重启 SolidWorks，重新打开干净的 `FL9A24D062A000_5components_t401_replay.SLDASM`，再执行 Health -> Generate Constraint Layout（rotation off）-> Replay Layout。
## 2026-07-22 18:10 闭环后遗留优化

- Constraint Layout 的真实 Replay 已成功，不再属于功能阻塞项。
- 当前主要遗留问题转为性能和运行环境稳定性：
  1. 5 组件大型嵌套装配体 Replay 仍耗时约 224 秒；需要增加逐组件耗时、配合抑制、Transform2 写入、重建和回采阶段日志。
  2. 系统中同时存在多个 `SLDWORKS.exe` 实例时，COM 活动文档选择存在潜在歧义；后续应增加目标进程/文档实例诊断和单实例启动检查。
  3. 当前对 Constraint Layout 临时抑制顶层 MateGroup。后续应只抑制影响参与组件的配合，并明确记录恢复结果。
  4. 约束求解目前使用世界 AABB 投影，适合基础验证；后续可升级为 OBB、凸包或 SolidWorks 干涉检查，以减少保守间距和假重叠。
## 2026-07-23 Portal 功能后续项

1. 在系统策略中允许新版 `SolidWorksMcpApp.dll`/`SolidWorksMcpApp.exe`，补做 A200/A800 的真实 Replay 和 B-Rep 干涉验证。
2. 当前 Portal 净空由外包围盒乘宽高比例估算，属于候选生成规则；后续应从子零件、截面或实体几何自动提取左右支撑和顶部横梁，得到真实净空。
3. `CheckInterference` 能验证“不相交”，但不能证明达到正的最小间距；后续增加组件间最小距离测量。
4. A500 仍受固定侧带划分限制。后续实现“龙门内部减去已占用区域”的二维自由空间装箱，并允许安全的 90 度候选姿态。
5. 对 Portal 实体检查增加耗时和匹配组件诊断，避免嵌套子装配体内部既有干涉造成误报。

### 企业策略放行所需信息

- 阻止来源：Windows Code Integrity，而不是 AppLocker。
- 事件 ID：`3033`、`3077`。
- 策略 ID：`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`。
- 被阻止文件：`vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.dll`。
- 文件状态：`NotSigned`。
- SHA-256：`7A13AAB8829F3169391BE530A41E1A43BB961F8457225E6F397DD2C6562F7E52`。
- 推荐处理：由企业 IT 对正式发布产物进行可信代码签名，或在上述 Code Integrity 策略中按签名发布者/受控路径放行。仅执行 `Unblock-File`、复制目录或改用 `dotnet run` 无法绕过该策略。
- 放行后的验收顺序：
  1. `MCP Health`；
  2. 生成带 A200/A800 Portal 声明的 Constraint Layout；
  3. Replay；
  4. 检查 `portalInterferenceChecks`；
  5. 回采 XY/theta 误差并保存截图。

## 2026-07-23 18:56 Portal 后续项更新

- 上述“企业策略”判断已被后续排查修正：实际为本机 Windows Smart App Control，设备未加入学校/企业管理。关闭后新版 MCP 已可运行。
- Portal 生成、Replay 和 XY/theta 回采验证已经完成真实闭环，不再是功能阻塞项。
- 剩余核心问题是 `AssemblyService.CheckInterference()` 对该大型嵌套组件对可能长时间不返回。后续建议：
  1. 新增独立的 Portal 干涉验证 MCP 工具和后端按钮，不再放在 Replay 主事务内；
  2. 在独立进程中执行干涉检查，提供硬超时并允许安全终止 MCP 子进程；
  3. 记录参与检查的实际叶组件、实体数量、调用耗时和 SolidWorks 返回码；
  4. 在 B-Rep 检查稳定前，以 Portal 净空规则和允许 AABB 重叠作为布局生成依据，并明确标记“实体干涉未验证”；
  5. 正式发布仍建议对 MCP 产物签名，避免依赖关闭 Smart App Control。

## 2026-07-29：七组件闭环后的工程遗留项

1. **Common Base 超时语义不准确**
   - 七组件第二批在客户端 `900 s` 超时，但 SolidWorks 仍继续完成了共面和保存。
   - 后续应为批处理增加阶段检查点、后台任务 ID 和结果查询，区分“几何失败”与“响应超时但任务已完成”。
2. **Replay 性能接近超时上限**
   - 七组件 Replay 约 `898 s`，已经接近当前 `900 s` 阈值。
   - 需要记录逐组件姿态读取、Persistent Reference 选面、Transform2 写入、mate 恢复和最终重建耗时，并减少重复 COM/重建调用。
3. **Replay 最终保存未内建**
   - `ApplyCapturedCommonBaseLayoutCore()` 当前完成重建和截图后直接返回，没有自动保存目标装配体。
   - 本次 Replay 的几何回采已通过，但磁盘文件仍停留在 Common Base 保存时间；后续应增加 `saveAfterReplay`（默认开启）或由后端在成功后显式调用保存工具。
4. **多 SolidWorks 实例绑定不稳定**
   - 直接 MCP 保存尝试启动了新的空白 `SLDWORKS.exe`，而不是附着到原 Replay 会话。
   - 应增加进程 ID、活动文档路径和会话标识诊断；目标文档不匹配时禁止写操作，避免对错误实例执行命令。
5. **中文 API 请求编码需要固化**
   - Windows PowerShell 的 `Invoke-RestMethod` 曾将 `底面` 和中文源路径写成乱码，导致面映射假缺失。
   - 测试脚本应统一使用 UTF-8 无 BOM 请求文件和 `curl.exe --data-binary`，或提供仓库内 Python/CLI 客户端封装。
6. **软约束仍需业务细化**
   - A500、A700、A300 在七组件布局中触发 containment relaxation。
   - 需要按功能模组类型引入侧区、顺序、朝向和优先级约束，避免“数学可行但业务含义偏弱”的布局。

### 2026-07-29 状态更新

- “Replay 最终保存未内建”已经解决：保存现已在同一 MCP/COM 会话中执行，并通过真实七组件装配体验证。
- 仍需继续的是 Replay/Common Base 性能、超时任务状态查询、多 SolidWorks 实例预检，以及 A500/A700/A300 的业务级软约束细化。

## 2026-08-05：工艺语义约束后续事项

已完成配置驱动的 Scanner、CCD、校准、清洁和称重 2.5D硬约束闭环。下一步按优先级处理：

1. **真实项目数据确认**
   - 已初步确认 A100=点胶龙门、A200=CCD、A300=双接废胶杯、A500=校准、A700=清洁、A800=传输；下一步复核 A600/A900，并定位 Scanner/Weighing 的真实装配层级。
   - 提供载具/产品条码点、工作位定位点、校准/清洁/称重点相对各组件底面中心的 `U/V` 偏移。
   - 提供 Scanner/CCD 工作距离、CCD视场、双阀左右行程和清洁隔离距离。
   - 决定 A300 是否新增 `glue_drain` 专用语义类型，或暂以显式 `pointInRegion` 约束建模。
2. **真实七模组验证**
   - 建立项目专用 `moduleSemantics` 配置；
   - 生成布局并检查 `processValidation`；
   - 仅在硬约束通过后执行 Replay、坐标复测、截图和保存。
3. **求解能力增强**
   - 当前仍为语义感知的规则式放置，下一阶段引入离散侧面、顺序和旋转的回溯或 CP-SAT 搜索；
   - 输出多个候选并按紧凑度、管线长度和运动距离排序。
4. **三维验证增强**
   - 将二维视线升级为三维光锥/射线检查；
   - 将 AABB 间距升级为 OBB/实体最小距离；
   - 增加阀头安全Z高度与运动扫掠体检查。
## 2026-08-05 称重占位粗求解后续

- 已完成几何称重占位的求解闭环；输入、脚本和输出分别为 `demo/FL9A24D062A000_coarse_process_request.json`、`scripts/generate_coarse_process_layout.py`、`demo/FL9A24D062A000_coarse_process_layout2d.json`。
- 当前结果为 8 对象、11/11 工艺硬约束通过、非允许碰撞 0，但 `productionReady=false`。
- 不能直接执行完整 SolidWorks Replay：称重占位体尚无真实 `.SLDPRT`，且 Scanner/A600 的身份、底面映射和几何捕获尚未完成。
- 下一步优先级：稳定加载并确认 A600；制作明确着色/命名的称重占位 SLDPRT；补录两者底面；重新捕获后再做 Replay、坐标复测、截图、三维干涉检查和保存。

## 2026-08-05 A180/A700 闭环后的剩余事项

此前“确认 A600 Scanner、制作称重占位 SLDPRT”的阻塞项已经解除：Scanner 为 A180，称重位于 A700/A730 内部，真实 8 组件 Replay 已完成。

下一步只需精化参数，而不必再寻找模组身份：

1. 捕获 A180 真实光轴点与 A800 条码面中心，将临时 `0.70 m` 上限替换为实测距离；
2. 捕获 A800 工作位 1/2、A500 校准点、A700 清洁点和 A730 称重点；
3. 读取 A100 左右阀真实行程并计算公共可达区；
4. 用三维射线/光锥复核 A200 Portal 与 A300 的 2.5D 视线透明假设；
5. 运行 SolidWorks 实体干涉与维护抽出空间检查后，才允许把 `productionReady` 升为 true。

## 2026-08-06 布局修正后的剩余事项

原型偏离和龙门/阀行程硬约束问题已经修正；修正装配体已保存为 `demo/FL9A24D062A000_8components_real_process_corrected.SLDASM`。后续按优先级处理：

1. 保存后坐标回采已完成：8/8 顶层位姿和 8/8 底面通过，最大 XY 误差 `3.8581e-14 m`、最大 theta 误差 `1.1369e-13°`，该项不再阻塞。
2. 从实际运动轴或装配约束提取 A100 左右胶阀行程，替换“龙门包络 10% 内缩”的临时公共可达区。
3. 捕获 A180 光轴点、A800 条码面及工作位 1/2、A200 相机光轴/移动行程、A500 校准点、A700 清洁点、A730 称重点和 A300 排胶点。
4. 12 对允许 AABB 投影重叠已完成世界坐标三维宽相位：按 1 μm 保守阈值排除 A500–A700、A700–A300 两对；剩余 10 对执行隔离进程 B-Rep、最小距离、阀头 Z 安全高度和维护抽出空间检查。A180–A200 为浮点级近接触，必须保留复核。
5. 在上述真实参数和三维检查完成前继续保持 `productionReady=false`。

## 2026-08-06 保存坐标与干涉宽相位闭环后的剩余事项

- 已实现 `CheckInterference` 双组件世界 AABB 快速排除：仅当任一轴间隙大于 1 μm 时短路；相交、接触、近接触或包围盒缺失均继续调用 SolidWorks 实体算法。
- A700–A300 的原始实体检查超过 180 秒；优化后利用 `0.5051 mm` 明确间隙，在约 28.2 秒内（含打开文档）返回无干涉，证明宽相位路径生效。
- 下一步重点不是再次回采坐标，而是将剩余 10 对拆为独立进程逐对检查，记录硬超时、组件解析和结果；对真正 AABB 相交的组合仍不得用宽相位代替 B-Rep 结论。
- 已生成 `demo/FL9A24D062A000_interference_check_plan.json`：P0 两对、P1 两对、P2 六对；执行顺序从 A180–A200、A200–A700 开始，再检查 A200/A800 与 A300，最后处理 Portal/传输等大范围预期穿越关系。
- `productionReady=false` 继续保持，直到真实工艺点/行程、剩余实体干涉、最小间隙、运动扫掠体和维护空间均通过。

## 2026-08-06 去原型位置依赖测试后的事项

- 已完成两组独立扰动的无原型位置求解，输出稳定且与原型显著不同，13/13 工艺约束、6/6 空间约束、0 非法重叠、0 containment relaxation。
- 当前去除的是“原型组件位置依赖”；CAD 投影外形、原始姿态轴及临时工艺参数仍作为输入，不能表述为完全不依赖 CAD 原型数据。
- 新布局尚未 Replay。下一步先将龙门原点坐标转换为 Common Base 可执行锚点，再针对新布局重新生成三维 AABB/B-Rep 检查清单；不能复用原型优先解的三维筛选结果。
- 在 CAD Replay 前，建议先增加最小间隙与运动/维护空间目标函数，否则当前结果只能称为硬约束可行解，不能称为综合最优解。

## 2026-08-06 去原型布局 Replay 后的事项

- 新布局已完成 A500 锚点转换、SolidWorks Replay、保存和保存后复测；该项不再阻塞。
- 全 28 对三维宽相位已完成：13 对已证明分离，15 对仍需精确实体复核；首个 A180–A200 精确调用 180 秒超时。
- 后续优先优化精确检查路径：按顶层组件提取轻量化实体/零件体，或引入稳定的最小间隙接口，再逐对完成 15 个候选；超时不得当作无干涉。
- 仍需补充真实工艺点、双阀公共行程、运动扫掠体和维护抽出空间；在这些项目完成前保持 `productionReady=false`。

## 2026-08-10 v10 后续校准

- 已完成 A200 实测门洞、A180 命名扫描结构通道、A500/A700 三包围盒占用体及其求解/展示/Replay 接入。
- 离线硬约束与保存位姿均已闭环，但叶级 B-Rep 仍有 5 组残差：A100–A200、A100–A500、A200–A700、A200–A800、A300–A800。
- 下一轮必须新增或校准三类几何：A100 内部净空/结构禁入带、A200 门框外侧固定结构占用、A800 A860 顶升结构禁入区。不能再用 `postSolveAllowedProjectedOverlapPairs` 把这五组解释成通过。
- 原型 A300–A800 有 2 个实体对接触，需记录具体允许安装接触面；在接触面未明确前，目标仍按“不得扩大干涉”处理。
- v10 装配体和完整证据可以作为本轮诊断基线，但不能作为无干涉最终方案。

## 2026-08-10 联合求解闭环后的剩余事项

- 已完成结构障碍构建、有限候选联合回溯、碰撞矩阵和 Top-3 展示；项目02双扰动、后端31项测试和前端生产构建通过。
- 首选 Replay 输入为 `demo/FL9A24D062A000_source_independent_replay_layout2d.json`。失败诊断副本 `joint_v11` 使用了错误的旧底面映射，未发生组件平移，不得使用。
- `joint_v12` 从原型重新复制并改用 `artifacts/solidworks-mcp-20260810-multibox`，但 MCP/COM 调用在180秒内无返回，且未生成结果或截图；文件时间未变化，不能视为已保存方案。
- 下一次干净 SolidWorks 会话应优先完成方案1 Replay、8/8位姿复测、28对宽相位和全部叶级 B-Rep。若发现残差，将相交结构叶体自动追加到障碍集后重新求解，而不是增加组件对 U/V 偏移。
- A500/A700复杂叶 AABB 的4项假阳性风险仍需CAD精检；动态载具、顶升、拖链/软管及维护抽出空间仍为独立验收项。
## 2026-08-10 后续接续点：v24 磁盘重开与精确实体复测

当前可直接打开的粗布局装配体为 `demo/FL9A24D062A000_8components_joint_v24.SLDASM`。Replay 已保存成功，但 SolidWorks 多实例残留导致后续 `OpenDoc6` RPC 失败。

下一次接续必须先由用户保存需要保留的文档，并关闭所有 SolidWorks 窗口；确认任务管理器中无残留 `SLDWORKS.exe` 后，只启动一个干净实例。然后按顺序执行：

1. 从磁盘打开 v24，不做 Replay，捕获 8 个目标模组的姿态、底面和世界 AABB；用 100 nm 平移容差复测。
2. 要求 A700 对龙门真实投影覆盖率为 100%，A800 不低于 75%，A200 不低于 75%，其余功能模组为 100%。
3. 对宽相保留的 16 对执行叶级精确 B-Rep；任何确认干涉都必须返回约束校准，不得靠人工逐组平移掩盖。
4. 精确静态检查通过后，再做运动扫掠、软管/拖链和维护抽出空间检查。

本轮已生成的投影文件 `demo/FL9A24D062A000_joint_v24_projected_poses.json` 与 `demo/FL9A24D062A000_joint_v24_aabb_screening_projected.json` 仅用于宽相预判，不能替代上述磁盘重开和 B-Rep。

## 2026-08-24 配合关系 Demo 后续

- A500–A700 的“距离8”已完成面级导出、新装配体重建、保存和重开复核，不再是阻塞项。
- 下一步优先增加“按配合特征名或 SolidWorks 当前选择直接导出”，避免大型装配体中的候选搜索。
- 分别选择真实重合、同心、平行配合完成同样闭环，验证当前基础配合白名单。
- Demo 稳定后，再把中间态扩展为以顶层子装配体为节点、以配合及面身份为边的图，并支持一个组件对多个组件的批量重建。

## 2026-08-25 需求驱动模组推荐 Demo 后续

- 专用接续说明已整理到 `docs/project02_requirement_to_modules_handoff-CN.md`，后续开发以其中的阶段划分、验收标准和检查清单为准。
- 项目02第一阶段已走通“自然语言需求—能力与依赖—模组推荐—人工确认—完整八模组布局求解”，不再缺少前端演示入口或后端审计数据。
- 当前优先事项是把求解器从固定八模组改成由确认模组集合动态构造变量和约束；在完成前，非完整八模组方案只允许推荐，不允许进入布局求解。
- 将项目02规则从 Python 常量迁移为版本化配置，并增加规则冲突、同义词和澄清问题回归测试。
- 待项目02动态子集求解稳定后，复用统一能力本体接入项目01、03、05、06；项目差异只放在配置层，不复制整套代码。
- 需求推荐闭环不改变 CAD 验收状态：布局方案仍需人工展示门禁、SolidWorks Replay、条件 B-Rep、运动扫掠和维护空间检查，`productionReady` 继续保持 false。

## 2026-08-25 项目02静态实体无干涉 v34 接续

- 离线分级、保存装配体世界AABB宽相、相对位姿证据复用和首个硬失败即停均已实现；10/10严格AABB通过，18组条件策略组合缩减为14组待精检。
- 下一步不是重新求解或全量B-rep，而是先清理当前19个残留SolidWorks进程，然后只执行P0的A100–A200叶级精检。
- P0失败时必须把具体叶实体局部占用回灌A100净空/A200外框模型后重新求解；禁止在SolidWorks中手工拖动。
- P0通过后才执行P1（A200–A700/A800）、P2历史回归和P3剩余组合；最后保存重开并复测。
- 详细状态、批次和命令入口见 `docs/project02_static_collision_v34-CN.md` 与 `demo/layout_previews/project02_v34_static_collision_execution_plan.json`。

## 2026-08-26 项目02静态实体闭环最新接续点

- 已完成真实联合候选 Replay 和关键叶级 B-rep，确认当前不是网络中断；局部移动只会在龙门、CCD、校准、清洁称重和扫描之间转移干涉。
- 已修复“专项修复误动 A200”和“T401 锁定位姿未生效”，并增加 SolidWorks 批处理退出请求及进程退出复核。当前 DCOM 环境中 `ExitApp` 未实际减少进程，不能称为自回收已闭环。
- 当前最小冲突证据：A200轴向30 mm、A500轴向450 mm/横向100 mm时，A100–A200和A100–A500为0，但A200–A500仍有21个干涉叶体对。
- 不再继续坐标试探。下一步优先从真实装配体复测 A500 校准服务点、A700/A730实体占用、A180扫描占用/通道和A200门洞外框；更新语义后一次性联合求解。
- 更新后的候选先检查五对：A100–A200、A100–A500、A200–A500、A500–A700、A180–A700；全部通过后再恢复其余分级B-rep和保存重开。
- 机器状态：`demo/layout_previews/project02_v34_constraint_conflict_status.json`；详细实验表见 `docs/project02_static_collision_v34-CN.md` 第8节。
- 继续 CAD 前必须由管理员任务管理器清理当前11个无窗口 `SLDWORKS.exe`，或重启 Windows；普通权限命令和 UI 均无法关闭这些实例。

## 2026-08-28 项目02模组级配合图后的新接续点

- 全量只读Mate图已完成：10个具体实例、27条跨模组配合、10个配合束，机器校验通过。
- 原型证实A600是安装关系中心，A600–A800具有直接定位束；A180机械上直接安装于A600，但与A800没有直接Mate。
- 下一步不再继续用“A100先固定、其余模组围绕龙门搜索”的旧顺序调坐标。
- 第一优先级：在A600稳定记录操作面和站体坐标系，并明确A800厂商XYZ安装尺寸。
- 第二优先级：记录A800条码点/工作位1/2、A180视场、A500/A700/A300服务点和双阀行程。
- 第三优先级：实现A600→A800→A180→功能模组侧别分支→A100覆盖反求的顺序化求解与展示门禁。
- 完成展示层目测后再Replay和条件B-Rep；配合图不替代工艺语义和实体检查。
- 详细结果与输出见 `docs/project02_module_mate_graph-CN.md`。

## 2026-08-28 A600锚定顺序门禁后的接续点

- 五阶段装配顺序门禁已实现并进入展示页；后端81/81、前端生产构建和机器校验均通过。
- 当前五阶段均为正式阻塞，属于“证据存在、实测参数未齐”的预期状态，不是代码失败。
- 第一动作只做A600：捕获真实几何、底面、箱体局部坐标系和操作面；在此之前不要继续优化八模组相对窗口。
- 第二动作确认A800相对A600的厂商XYZ。配合图中的原型相对变换只能作对照，不能自动升级为厂商硬参数。
- 随后依次捕获扫描/条码、操作侧空间、双阀行程与服务点；每补齐一阶段，都用 `project02_assembly_sequence_validation.json` 检查门禁状态变化。
- 详细实现、意义和验收结果见 `docs/project02_assembly_sequence-CN.md`。

### 操作面人工确认补充

- 已确认 `FL9A24D062A600.001` 即A600，当前SolidWorks中选中的青色正面大平面就是操作面；其工程含义是人员面向该面操作。
- 已把“A700/A500/A300优先靠近操作面，操作侧空间不足才转移到对侧”写入项目02正式策略和展示门禁。
- 通过Windows界面确认了选中面，但两次MCP探测均连接到新建的无文档SolidWorks实例；为避免写错，未写入 `face_mappings.json`，测试实例已按精确PID清理，原有可见会话保留。
- 下一动作是恢复MCP到可见原型会话的绑定，再运行 `scripts/capture_project02_a600_operation_face.py`，获取面中心、法向、持久引用和A600世界包围盒；人工确认本身不需要重复。

## 2026-08-28 A600工程安装坐标系完成后的接续点

- 上一条“继续捕获A600底面”的计划已被工程语义纠正：项目02上部模组安装不需要底面作为首要基准。
- 操作面已精确记录；模组配合图v1.2新增端点局部/世界中心与法向。`重合35`恢复传输支承/上部安装平面，`宽度9`两定位面恢复传输中心面。
- 已生成右手A600工程安装坐标系，7/7几何检查通过，操作侧已解析为`front`。输出为 `demo/layout_previews/project02_a600_installation_frame.json`。
- 后端顺序门禁已读取该坐标系，不再要求“底面/操作侧映射”；82/82后端测试、319/319非集成C#测试、两项项目02机器校验通过。
- 下一优先级是把A600整体几何、上表面有效安装区域和禁入结构接入求解器，然后把A600–A800原型接口换算到工程坐标系并请工程师确认厂商XYZ。
- 底面仅在后续整机落地高度、脚轮/地脚或完整箱体包络校验时按需补录。

## 2026-08-28 A600粗安装面与A800原型接口后的接续点

- A600阶段已从阻塞升级为`ready`：安全安装边界、A800支承区、18个硬禁入区和1个条件结构已接入顺序门禁与展示页小地图。
- 真实只读采集为708个有效叶体、2个失败体，覆盖率`99.718%`。失败体和非凸上机架仍是最终条件复核项，不能把当前模型称为完整B-Rep等价。
- A800原型包围盒中心在A600工程坐标系中约为`(0.5713,-0.00561,0.04911) m`，中心轴关系合理；CAD组件原点偏离实体，不作为厂商XYZ。
- 当前五阶段为1/5正式就绪，剩余输入依次是：厂商A600–A800基准XYZ、扫描/条码点、服务侧容量、双阀行程及工作/服务点。
- 下一优先动作：确认A800接口基准。若短期Demo允许使用原型测量，应明确选择“配合面基准”或“包围盒中心基准”，不要使用组件原点。
- 回归状态：后端83/83、非集成C# 319/319、前端生产构建及三项项目02机器校验通过。

## 2026-08-28 A600–A800配合面接口后的接续点

- 已解析`重合35＋宽度9`的全部六个配合面端点，恢复A800相对A600的支承高度、横向中心和姿态。
- 配合面派生粗基准为`XYZ=(376.3,0,0) mm`；Y/Z和姿态由配合约束，X只是原型中Width特征所在站位。
- 第二阶段仍保持阻塞，但剩余输入已缩小为A800沿传输长轴X的厂商端面、销孔或安装孔系基准确认，不再要求重复测量完整XYZ。
- 下一动作应优先在A800/A600图纸、配合树或选定安装孔系中寻找能约束X的第三类关系；若确实不存在，Demo可暂用376.3 mm并显式标记为原型测量种子。
- 回归状态：后端84/84、前端生产构建、顺序门禁15/15检查通过。

## 2026-08-28 项目02顺序求解下一接续点

- A800已获准复用项目02原型顶层位姿，并作为仅限项目02的案例锚点；不可把该值写入跨项目通用规则。
- A180已调整为A800后的首个功能候选，现有条码侧、工作距离和视线硬约束继续生效；下一步优先实测扫描原点与条码点，替换暂估值。
- 服务模组“操作侧空间足够则同侧，否则对侧”的分支代码已具备；仍需操作面到求解器`low/high`轴映射及可用/需求宽度。
- A100已输出由6个目标点、8条约束形成的锚点交集；下一步捕获双阀真实行程、工作位1/2和服务点后重新求交。
- 在上述三类实测完成前，可以生成、展示和Replay粗布局，但不得标记为完整顺序求解或`productionReady`。

## 2026-08-28 A180/A800光学点位采集接续点

- 已识别A180内真实扫描器叶零件为 `248004电气-sr-x100-0801A.SLDPRT`，与PPT中的Keyence SR-X100一致。
- 已新增两步面采集工具和空证据清单；当前未捕获任何光学面，状态为`WAITING_FOR_ENGINEER_FACE_SELECTION`，没有把暂估点升级为实测。
- 第三阶段现在分别显示4个阻塞项：A180出光面、A800条码面、工作距离确认、光轴方向确认。
- 下一次实际操作只需工程师在可见原型中选择A180内SR-X100出光平面；随后执行 `python scripts/capture_project02_optical_point.py --target scanner --proxy`。再选择A800条码承载面，执行 `python scripts/capture_project02_optical_point.py --target barcode --proxy --apply`。
- 当前可见SolidWorks会话与MCP/COM所有权曾发生错绑；在确认代理确实连接到可见原型前，不应运行上述写入命令，避免新建后台无文档实例或记录错误面。
- 回归：后端90/90、前端生产构建、真实HTTP求解和顺序门禁16/16均通过；展示页已加载最新后端。

## 2026-08-29 A180出光侧复核后的接续点

- 六视图和CAD探测已确认SR-X100出光侧为SolidWorks `Bottom`视图，窗口处于几何低`Y`侧；CAD平面返回局部`+Y`法线，但该符号不再直接解释为光束方向。
- 已修复平面法向读取错误并重新生成`project02_scanner_face_candidates.json`。高亮已排除`faceIndex=0/1704`外壳结构，并确认`faceIndex=766/765`是左右对称照明窗口。
- 两窗口中心的中点为叶零件局部`(-1.2, 0.3, -20.6) mm`，已转换为A180底面坐标`u=-36.5 mm、v=-221.4 mm、高度=236.8 mm`。
- A800中发现5个`模拟二维码`实例；与原型扫描投影最近的`ASM-8`上表面已直接测量并记录持久引用，A800底面坐标为`u=-133.108 mm、v≈0 mm、高度=1 mm`。原型两点距离约`127.1 mm`，位于当前50–350 mm临时范围内。
- 剩余阻塞项缩减为：确认SR-X100实际配置工作距离、确认扫码时运动滑台位置及`ASM-8`确为生产缓冲扫码载具。`scanOriginMeasured=false`仍正确，因为中央镜片面不是直接实测。
- 大型原型直接打开曾在NVIDIA OpenGL模块崩溃；当前改用轻量8模组装配体加载同一SR-X100叶零件完成复核，原型未移动、未保存、未覆盖。

## 2026-08-29 真实光学点进入求解后的接续点

- 修复真实点接入后暴露的二维距离误判：扫描工作距离现包含A180/A800安装标高和点相对底面高度。原型复算约`127.085 mm`，第一候选约`128.76 mm`。
- 正式Top-3展示、命令行和真实HTTP求解均恢复；工艺`23/23`、空间`13/13`、交互`37/37`，数值展示门禁通过。
- 阶段3提示已区分“未捕获”和“CAD推断待确认”：当前不再要求重复寻找不存在的中央镜片平面，但仍需工程确认推断原点、实际工作距离/动态扫码位及有向光轴。
- 下一次CAD验证先Replay目测选中的方案，再优先检查A500–A700：当前有`28`处叶盒宽相预命中。不得无差别重跑全部顶层组合。
- 操作面侧容量、双阀真实行程、工作位和服务点仍含暂估数据，`productionReady=false`保持不变。

## 2026-08-29 v52 Replay与静态碰撞关闭后的接续点

- rank 1已固化并Replay为 `demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`；保存、Fully Rebuilt和六视图导出成功，原型未覆盖。
- 10组普通实体组合通过保存后膨胀世界AABB硬门禁；A500–A700条件精检为0干涉。
- 占用覆盖不完整的四组已处理：A100–A800复用相对位姿不变的完整零干涉证据；A100–A200、A200–A800重检为0；A800–A700的8对接触与原型完全一致且无新增/缺失。
- 从零SolidWorks进程重开后，8/8世界变换误差0、包围盒最大误差约`7.09e-11 m`；静态状态为`STATIC_COLLISION_BASELINE_EQUIVALENT_AND_REOPEN_CLOSED`。
- 当前装配体是保留原型上下文的新另存件，不是只含8个顶层模组的干净装配体。若会议展示需要干净目标，应单独修复/完成“保留子装配体状态、隐藏非目标上下文”的隔离流程，不能重新插入空白装配体导致内部配置漂移。
- 下一优先级不再是继续静态拖动或无差别B-rep，而是确认SR-X100实际工作距离与动态扫码位、补齐双阀真实行程/工作位/服务点，以及验证运动扫掠、软管和维护空间；完成后再推进01/03/05/06通用约束校准。
- 机器证据：`demo/layout_previews/project02_v52_cad_execution_plan.json`；`productionReady=false`保持不变。
- 最后一次自动化检查结束后，SolidWorks仍出现既有.NET加载提示并退出；当前无SolidWorks进程。下次查看v52应从干净会话直接打开上述新文件，不需重新求解或重做已完成证据。

## 2026-08-29 工程估计约束闭环后的接续点

- 最新展示数据为`demo/layout_previews/project02_preview.json`；操作侧容量证据为`demo/layout_previews/project02_operation_side_capacity.json`；离线求解结果为`demo/FL9A24D062A000_real_process_layout2d.json`。
- 新方案已通过工艺24/24、空间13/13、交互37/37并生成3个候选；尚未由用户在展示层选择并固化，因此本轮没有覆盖v52 CAD验收件，也没有启动SolidWorks Replay。
- 下一优先动作是先在展示页目测新Top-3的扫描方向、功能模组是否确实位于操作面侧、A500/A700/A300是否仍有明显接触；确认候选后再固化一个方案并执行条件B-rep，而不是立即全量精检。
- 需要继续确认的工程输入：SR-X100中央扫描原点/动态滑台停靠与载具8身份、工具与耗材更换维护包络、双阀X/Y/Z真实限位及左右阀头间距。
- 当前左右阀包络使用A300两排胶点90 mm间距估计，扫描工艺带使用原型127.085 mm附近100～160 mm，均不得提升为跨项目通用或生产确认参数。

## 2026-08-29 Top-3复核与CAD证据复用后的接续点

- 展示服务已加载最新代码，项目02当前为工艺`24/24`、空间`13/13`、2.5D交互`37/37`；rank 1已完成Top-3目测与固化。
- rank 1与v52实际Replay输入的8个布局参数完全一致，且源模组顶层CAD文件未在v52闭环后修改；因此审计结果允许直接复用v52的保存、重开、世界AABB和条件B-rep证据。
- 当前静态闭环复用证据：`demo/layout_previews/project02_current_cad_closure_reuse.json`；验证计划状态：`cad_closure_reused`。本轮没有必要生成重复的v53文件。
- 展示页点击顶部`Refresh`即可同时恢复持久化Top-3和验证状态；不要点击“重新求解”来单纯查看结果，因为重新求解会生成新预览版本并要求重新绑定目测审批。
- 继续使用的实体装配体：`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`。只有候选布局、法向偏移、源模组文件或历史证据发生变化时，才创建新版本并重新Replay/B-rep。
- 下一优先级仍是补齐生产性输入，而不是重复静态检查：确认动态扫码停靠位与SR-X100光轴/工作距离，确认操作侧非凸维护包络，测量双阀X/Y/Z限位及左右阀头间距；之后再判断是否产生真正不同的新布局。
- 完整后端回归`103/103`、前端生产构建和项目02数值门禁通过；`productionReady=false`保持不变。

## 2026-08-29 五载具扫码站位审计后的接续点

- `demo/layout_previews/project02_scan_station_inference.json`已对A800的5个二维码载具逐项排序。载具8距A180光学中心约`127.560 mm`，第二近载具7约`542.060 mm`，距离差约`414.501 mm`；载具8是唯一处于项目02`100～160 mm`暂定工艺带的候选。
- 因此载具8可作为项目02入口/缓存扫码站位的粗布局证据，展示页和顺序门禁均已接入；该结论不是PLC触发位置、滑台动态停靠位置或生产公差确认。
- 当前rank 1仍与v52刚体布局完全一致，静态CAD闭环继续复用，实体装配体仍为`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`。
- 下一步优先确认A180实际扫描动作：扫描器是否固定、载具是否在缓存位停靠、PLC触发时载具8的允许位置公差。若只能给出近似值，应记录为项目02估计带，不得提升为跨项目通用参数。
- 随后处理操作面侧维护包络和双阀X/Y/Z限位；只有这些信息改变模组位姿时才重新Replay和条件B-rep。
- 当前回归`105/105`、顺序门禁`19/19`、前端构建通过；`staticCollisionReady=true`、`productionReady=false`。

## 2026-08-30 当前接续点

- 当前rank 1仍与v52完全同位姿，静态CAD闭环已按等价布局复用；实体文件继续使用`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`。
- 动态扫码粗窗口已进入求解：载具8名义点沿传输方向±5 mm的两个端点均通过距离、视线和光轴约束。下一步需要用PLC触发位置及真实停靠公差替换±5 mm几何估计。
- A500/A700/A300已建立保护空间，当前20条净空门禁通过。下一步需要工程师确认真实工具、更换耗材和人工操作包络，并把A700的A710/A720清洁与A730称重需求分开。
- 左右阀及公共行程的静态等效审计已通过。下一步优先测量左右阀X/Y/Z极限和阀头间距；只有实测结果改变可达域并导致位姿变化时，才重新Replay及条件B-Rep。
- 当前回归`109/109`、顺序门禁`20/20`、工艺`30/30`、空间`13/13`、交互`55/55`；`productionReady=false`是正确状态。

## 2026-08-30 工程参数接口后的接续点

- 工程参数统一填写于`demo/project02_engineering_inputs.json`，默认全部`confirmed=false`。没有可靠数据时不要改为true；干运行命令为`python scripts/apply_project02_engineering_inputs.py`，正式写回必须显式增加`--apply`。
- 离散压力测试表明扫码停靠从当前±5 mm放宽到±20 mm仍保持v52位姿，±30 mm已无解；因此真实PLC公差仍需确认，但短期风险低于阀行程。
- 维护保护空间放大到1.5倍仍保持当前位姿；下一步应采集真实包络尺寸，尤其拆分A710/A720清洁和A730称重需求。
- 双阀行程是当前最高优先级：每侧缩小25 mm便会改变求解位姿，缩小75 mm无解。优先测量左右阀X/Y/Z限位和阀头间距，随后用工程输入工具写回并重新求解。
- 若新参数求解位姿不变，自动复用v52；若位姿变化，先展示审批再Replay和条件B-Rep。不得因参数文件变化而无条件启动SolidWorks。

## 2026-08-30 A100轴证据采集后的接续点

- A100内部9个顶层子装配体和388个叶体已只读采集；`LimitDistance1=382.899 mm`已确认是普通距离配合，只代表当前桥架位置，真实轴上下限仍缺失。
- 当前10%内缩公共行程为`1107.2 × 960.8 mm`并保持v52位姿。几何乐观档`1040 × 860 mm`可解，但最大位姿变化`42.25 mm`，若选用必须重新Replay。
- 几何平衡档`1000 × 820 mm`即使把联合候选从12提高到24仍无解；失败集中在A300排胶杯工艺域，而不是碰撞矩阵。下一步不建议继续单纯增加搜索时间。
- 优先路线：先获取A100两个平移轴的机械/软件极限与阀尖偏移；若暂时仍无法测量，则专项审计A300–A700的`relativeAnchorWindow`、排胶点和上方进针/维护保护空间，判断哪些属于可校准通用约束、哪些只是原型硬编码。
- 新证据已显示在5173项目02展示页；当前正式装配体仍为`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`，无需生成重复文件。
- 机器证据：`project02_a100_internal_mate_graph.json`、`project02_a100_top_level_leaf_envelopes.json`、`project02_a100_valve_axis_inference.json`。

## 2026-08-30 A300–A700消融后的接续点

- 已证明`1000 × 820 mm`无解由“左右排胶点必须可达”与“A300–A700原型窄窗口”共同造成；求解器现在会直接报告具体失败约束ID。
- 诊断性有界放宽可恢复可解，并保持A300相对A700约`U=-50.0 mm / V=58.5 mm`；完全软化也可解，但可能产生约565 mm的服务簇漂移，因此不建议直接作为正式规则。
- 正式请求尚未改动，当前展示/实体仍是与v52完全等价的rank 1；静态CAD证据继续复用。
- 下一步需要二选一证据：优先测量A100真实U/V轴限位；若短期无法测量，则由机械工程师确认A300与A700允许的相对安装范围或至少确认`U±100 mm / V=20～200 mm`诊断窗口是否符合工艺。
- 得到确认后再把选定窗口写回正式请求并重新求解。若位姿改变，必须经过展示目测、Replay、保存后AABB、A300–A700及受影响条件组合B-Rep、重开复核；不得复用v52。
- 诊断机器证据：`demo/layout_previews/project02_a300_a700_constraint_ablation.json`及同名`.summary.md`。

## 2026-08-30 A800安装基准接口后的接续点

- A800已不再读取几何捕获中的原型顶层位置；它由A600工程安装坐标中的显式锚点定位。任意扰动8个源模组位置后，输出绝对/相对布局差异均为0。
- 当前锚点数值仍含一个明确限制：沿传输长轴X来自项目02原型测量，Y/Z与姿态来自A600–A800配合面。它可用于当前粗复原，但不能直接复制到01/03/05/06。
- 当前rank 1与v52位姿完全等价，静态CAD闭环已复用；有效实体仍为`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`，无需创建v53。
- 厂商A800安装基准应填写在`demo/project02_engineering_inputs.json`的`transportInstallation`中；未获得可靠数值前保持`confirmed=false`。
- 下一步优先级仍是获取A800长轴端面/销孔/孔系基准与A100真实行程。前者完成绝对安装通用化，后者决定是否需要采用A300–A700放宽窗口并产生新布局。

## 2026-08-30 原型基线写回后的接续点

- 项目02现已明确采用原型A800安装点作为`prototypeBaselineAcceptedForCoarseLayout`，无需等待厂商尺寸即可继续短期Demo；该值不会被标记为厂商确认，也不会迁移为其他项目常数。
- 当前Top-3和实体仍与v52完全等价，静态CAD证据继续复用。除非后续参数改变模组位姿，否则不要重复启动SolidWorks、Replay或B-Rep。
- 下一开发重点转为A100行程与A300–A700工艺域：优先继续从原型A100几何、配合和当前阀头位置构造“原型基线行程”，同样采用`prototypeBaseline/acceptedForCoarseLayout/vendorConfirmed=false`证据等级。
- 在原型行程基线上运行方向性压力测试，选择仍可解且机械上可信的最小包络；随后评估A300–A700是否必须采用`U±100 mm、V=20～200 mm`有界放宽候选。
- 若产生新位姿，按“展示目测→Replay→保存后AABB→受影响组合条件B-Rep→重开复核”闭环；若位姿不变，继续复用v52。

## 2026-08-30 A100原型行程基线接入后的接续点

- A100左右阀和公共行程已经作为`project02-only`原型基线安全写回；当前公共范围`1107.2 × 960.8 mm`可解并保持v52位姿，静态CAD闭环继续复用。
- 不应立即放宽A300–A700正式窗口。只有厂商/实测行程接近`1040 × 860 mm`或更小时，才启用已有消融报告中的有界放宽候选并重新求解。
- 下一优先输入是动态扫码停靠公差和A500/A700/A300真实维护包络。建议沿用相同证据等级：先把项目02原型估计写成`prototypeBaseline`，再由厂商或现场实测值替换。
- 项目02生产级未完成项仍包括：A100真实U/V/Z限位与阀尖偏移、PLC扫码触发/停靠公差、SR-X100实际配置工作距离、运动扫掠、软管/线缆和人工维护验证；因此`productionReady=false`保持正确。
- 当上述输入造成位姿变化时，再执行“展示审批→Replay→保存后膨胀AABB→仅受影响结构对条件B-Rep→重开复核”；位姿不变时不得重复消耗SolidWorks验证时间。
- 机器证据：`demo/layout_previews/project02_a100_prototype_baseline_acceptance.json`与`demo/layout_previews/project02_current_cad_closure_reuse.json`。

## 2026-08-30 动态扫码原型基线接入后的接续点

- 载具8沿传输U轴`±5 mm`动态扫码窗口已成为项目02原型基线；两个端点均检查工作距离、无遮挡视线和有向光轴。该值不代表PLC或量产停靠公差。
- 已测试的布局保持范围到`±20 mm`，`±30 mm`首次无解。下一步若获得PLC触发与夹具停靠数据，直接替换`demo/project02_engineering_inputs.json`中的`dynamicScan`并重新求解；不得根据压力测试自行把正式值提高到20 mm。
- 当前rank 1与v52完全同位姿，继续使用`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`，无需生成新装配体或重复B-Rep。
- 下一开发重点进入A500/A700/A300维护包络：从原型占用和操作面关系形成项目02基线，分别表达标定通道、排胶杯进针/拆卸空间、清洁/称重工具通道；不能只使用一个统一放大比例。
- 若维护包络写回后位姿不变，继续复用v52；若改变位姿，先在展示层比较Top-3，再仅对受影响组合执行Replay、膨胀AABB和条件B-Rep。
- 机器证据：`demo/layout_previews/project02_dynamic_scan_prototype_baseline_acceptance.json`、`project02_parameter_robustness.json`与`project02_current_cad_closure_reuse.json`。

## 2026-08-30 分用途维护包络接入后的接续点

- A500/A700/A300的项目02维护包络已正式参数化，20条净空门禁通过；三个模组单独放大到1.5倍仍保持v52，说明当前解具有一定粗布局余量。
- 下一步不建议继续无依据放大矩形。优先从A700原型子树拆分A710/A720清洁与A730称重的实体占用、服务点和维护方向；A500补充标定件更换动作，A300补充排胶杯拆卸方向。
- 若短期无法获取工程师实测，可继续使用原型叶体、服务点与操作面方向构造子模组级`prototypeBaseline`，但必须保留`authoritativeForFinalMaintenance=false`。
- 当前有效实体仍为`demo/FL9A24D062A000_prototype_context_optical_solved_v52.SLDASM`；所有已写回基线均保持该位姿，因此无需新版本。
- 完成A700内部拆分后，重新生成Top-3。仅当刚体位姿或参与碰撞的源CAD发生变化时，才执行Replay和受影响组合的条件B-Rep。
- 项目02粗布局功能约束趋于完整后，应开始建立“项目级参数包”，并选择项目01作为首个跨案例迁移试验，检验通用规则与项目02常数是否已经正确分离。
- 机器证据：`demo/layout_previews/project02_service_access_audit.json`、`project02_service_component_robustness.json`和`project02_current_cad_closure_reuse.json`。

## 2026-08-30 A700子功能拆分及参数包后的接续点

- A700已从“清洁/称重共享点”升级为单刚体内两个功能端口：A710/A720清洁点与A730称重点分别进入双阀可达和维护空间门禁。
- 当前点位来自占用盒中心，只授权粗布局。后续如能定位清洁夹持中心、针头实际擦拭位置或称重杯有效中心，应通过`serviceAccess.functionalPoints`替换并重新求解。
- 项目02粗布局参数包位于`demo/project02_parameter_package.json`。其中`portableRuleTemplates`可迁移，`projectSpecificParameters`和`doNotCopyAsUniversalConstants`不得直接复制到01/03/05/06。
- 当前rank 1继续复用v52；展示页刷新后可看到A700内部功能拆分及两个局部点位，无需启动SolidWorks。
- 下一开发动作建议选择项目01作为跨案例试验：先只提取A600等价箱体、传输基准和模组身份，建立项目01参数包骨架；随后逐项填入扫描、双阀和服务点，观察通用规则首次失效的位置。
- 跨案例阶段暂不追求一次完成CAD Replay。先以项目01原型做“参数提取→通用求解→Top-3展示→与原型相对关系对比”，确认规则可迁移后再选择一个候选进入CAD检查。
- 机器证据：`demo/layout_previews/project02_a700_functional_split.json`、`project02_service_access_audit.json`、`project02_current_cad_closure_reuse.json`及`demo/project02_parameter_package.json`。

## 2026-08-30 项目01参数骨架后的接续点

- 项目01的10个主要模组已全部识别并定位到独立CAD文件；当前按6个顶层对象求解，项目02数值常量已被明确隔离。
- 当前不应直接点击项目01 Top-3或进行Replay。还缺11项硬几何证据，静态碰撞策略也只完成分类框架；此时出图会混淆“模组识别成功”和“布局可求解”。
- 下一次SolidWorks采集应使用项目01原型，按以下顺序只读提取：JJ00操作面/顶部安装面 → JJ00-SS00安装基准及SS00/FF00工位 → SM00光轴与条码面 → GN00四功能点及BD00标定点 → LM00/ZZ00公共行程 → 多包围盒与碰撞对分类。
- 第一批优先完成前两项，因为它们决定项目01的工程坐标和传输固定位置；没有这两个基准，扫描、服务模组和龙门坐标都无法可靠表达。
- 当缺失证据清零后，才进入“通用约束Top-3→展示目测→与项目01原型相对关系对比”。只有选中候选后才Replay，并先做膨胀AABB，再对结构/嵌套组合做条件B-Rep。
- 当前机器入口：`demo/project01_parameter_package.json`、`demo/layout_previews/project01_migration_readiness.json`；展示页`http://127.0.0.1:5173/`已可看到迁移门禁。

## 2026-08-30 项目01首批几何采集后的接续点

- JJ00顶部安装面和JJ00–SS00安装接口已由真实配合恢复；两个FF00载具/产品工作区也已进入项目01坐标。无需再次采集这三项。
- 操作侧当前推断为`+worldX`、置信度中等；要从`partial`升级为`available`，仍需机械工程师选择一次JJ00精确操作面，或从门体/控制面板结构获得唯一证据。
- 下一批优先级改为：先定位SS00/载具条码面与SM00出光轴；随后定位BD00标定点和GN00清洁、称重、排胶、硬度检测四端口；最后从LM00/ZZ00叶体构造项目01双阀公共行程。
- 当前还缺5项硬证据，Top-3按钮应继续保持关闭。不得用项目02的SR-X100坐标、A100行程或A700功能点填充项目01。
- 当前SolidWorks已打开项目01原型；若继续CAD采集，优先复用此会话，避免重新加载约3111个组件。不要关闭带未保存标记的项目02 v52文档。
- 新机器证据：`project01_module_mate_graph.json`、`project01_top_level_poses.json`、`project01_first_stage_geometry.json`、`project01_ss00_ff00_leaf_envelopes.json`和`project01_work_positions.json`。

## 2026-08-30 项目01扫描基线完成后的接续点

- SM00双读码器角色、光学原点、光轴、200 mm原型光束基线和载具条码侧已恢复；这两项无需再次人工选面即可用于粗布局。
- 当前仍缺3项首轮求解硬证据：BD00标定服务点、GN00清洁/称重/排胶/硬度检测四功能点、LM00/ZZ00双阀公共行程。下一步按此前顺序先做GN00/BD00叶体语义与服务点，再反求双阀覆盖。
- 产品扫码器的四个具体行程停点尚未提取；短期可用“移动轴平行输送方向、上扫四个产品”的工艺约束，进入动态扫码精化时再从直线导轨/载具产品间距恢复停点。
- 200 mm是CAD中显式红色光束长度，只授权`project01-only`粗布局；厂商SR-X100实际配置距离到达后应替换参数并重新求解。
- 机器证据：`demo/layout_previews/project01_sm00_leaf_envelopes.json`、`project01_scanner_geometry.json`以及`demo/screenshots/project01_scanner_module_views/`。
- 展示页已同步显示2个SR-X100和3项剩余硬证据；Top-3仍应保持关闭，直至三项全部完成并补齐占用/碰撞门禁。

## 2026-08-30 项目01功能/标定服务点完成后的接续点

- GN00四类功能和BD00标定目标已恢复，共形成6个阀头可达目标；`calibrationServicePoint`和`combinedServiceFunctionPoints`已从缺失升级为可用于粗布局。
- 当前唯一缺失硬证据是`dualValveReach`。下一步应只读采集LM00/ZZ00叶体、滑轨/滑块轴向与双阀头当前几何，构造项目01专属左右阀及公共行程原型基线。
- 双阀行程不得复制项目02的A100矩形或90 mm间距；应在项目01安装坐标中分别验证两个传输工作区、GN00五个目标和BD00标定目标是否可达。
- 清洁点和BD00标定点仍是中等置信度代理。首次Top-3可使用，但在最终Replay前应尽量用实际擦拭中心、棱镜标定面或工程师选面替换。
- GN00/BD00完整叶盒同时可作为后续多包围盒占用输入；完成LM00/ZZ00后，再补齐精确操作面、占用体与碰撞对分类，随后开放项目01 Top-3展示，而不是提前生成伪方案。
- 机器证据：`demo/layout_previews/project01_gn00_bd00_leaf_envelopes.json`、`project01_service_points.json`和`demo/screenshots/project01_service_module_views/`。

## 2026-08-30 项目01双阀公共行程完成后的接续点

- 项目01所有“缺失硬证据”已清零；双阀公共范围约`770 × 1100 mm`，8个传输/服务目标全部可达，最小边界余量约36 mm。
- 当前仍不应直接Replay。Top-3门禁剩余四项`partial`：精确JJ00操作面、操作侧容量、多包围盒占用体、静态碰撞对分类。
- 下一步优先把已有顶层/叶级AABB整理成求解对象占用体：普通实体模组使用膨胀多包围盒严格分离；机架、龙门、传输、翻转等结构/嵌套组合允许宽相重叠并列为条件B-rep候选。
- 操作面短期可继续使用服务簇集中侧`+worldX`作为项目01原型基线，但必须保持中等置信度；如能获得工程师选面，再升级为精确面法向与维护侧。
- 完成占用与碰撞策略后，应先生成项目01 Top-3二维展示并与原型比较，不立即创建SolidWorks新装配体；只有用户选中候选后才进入Replay和条件B-rep。
- 行程基线不是生产参数：未来获得实际X/Y/Z限位、阀尖偏置或限位开关数据后，应替换`project01_dual_valve_reach.json`并重新求解。
- 机器证据：`demo/layout_previews/project01_lm00_zz00_leaf_envelopes.json`、`project01_dual_valve_reach.json`和`demo/screenshots/project01_valve_reach_views/`。

## 2026-08-30 项目01碰撞门禁放行后的接续点

- 项目01首轮Top-3输入已放行：缺失0、部分0。完整占用证据为`demo/layout_previews/project01_module_occupancy.json`，轻量门禁摘要为`project01_migration_readiness.json`。
- 下一开发动作是建立项目01专用求解请求和展示数据，不得把项目02的A600/A800坐标、A100行程或A500/A700/A300相对窗口直接套入。
- 首轮候选应保持SS00项目01安装基准，随后约束SM00扫码点/光轴、GN00/BD00操作侧容量、LM00+ZZ00对两个工作区和6个服务点的公共覆盖；GJ00只受外侧服务空间与普通碰撞约束。
- 先快速生成3个候选并在展示层比较方向、边界、工艺顺序和明显接触；此阶段禁止自动Replay，也不运行全量B-rep。
- 用户选定候选后，再与项目01自身原型比较相对关系。只有选中方案才Replay，先跑严格AABB，随后对相对位姿变化且宽相重叠的9组条件对象对做叶级B-rep；与JJ00/HL00的7组安装关系检查非法穿透但允许安装面接触。
- 当前操作面、扫描CAD光束、双阀刻度行程和部分服务点都是`project01-only`原型粗布局基线。厂商/工程师数据到达后应替换并强制重新求解；当前`engineeringConfirmed=false`和生产门禁不能取消。
- 本轮没有修改、另存或Replay任何SolidWorks装配体。

## 2026-08-30 项目01 Top-3展示完成后的接续点

- 项目01专用顺序求解和展示已经闭环：125个联合组合中21个硬可行，当前Top-3均满足同一套粗布局硬约束；候选2/3相对基线具有30 mm可见差异。
- 当前验证计划为`awaiting_visual_review`，不存在已批准候选。下一步应由用户在`http://127.0.0.1:5173/`的项目01面板切换候选，检查方向、是否越出箱体/龙门合理区域、功能模组维护侧、扫描关系和明显接触。
- 若三个方案均不合理，应记录具体违规现象并回到参数/约束层修正，不应手工拖动CAD模组掩盖问题；若有合理候选，则明确选择其排名并批准下一阶段。
- 仅对被批准方案执行Replay并另存新装配体。Replay后先复核8个模组变换和严格AABB，再只对9组条件对象对中“宽相重叠且相对位姿改变”的组合运行叶级B-rep；7组安装接触关系检查非法穿透但允许设计安装接触。
- 条件B-rep通过后再保存、关闭、重新打开并复测坐标与干涉，形成项目01实体闭环。未完成这些步骤前，只能称为粗布局可行候选，不能称为全模组零干涉最终解。
- 当前候选1仍是项目01原型参数下的最小位移最优解，因此本轮验证的是跨项目框架和约束流程，不等同于完全去原型参数依赖。后续应逐步用厂商基准、操作面和维护空间数据替换项目01原型标定值。

## 2026-08-30 项目01方案1批准后的接续点

- 用户已选择并批准项目01方案1；验证计划为`visual_review_approved`，不得重新求解覆盖该选择，除非用户明确要求重新生成候选。
- 下一步只对方案1执行SolidWorks Replay并另存新装配体。先校验8个展示对象映射到真实项目01子装配体的变换与固定/可移动语义，再应用位姿。
- Replay后先执行严格多包围盒和安装接触非法穿透检查；仅对仍有宽相重叠且相对位姿改变的条件对象对运行叶级B-rep，不做全装配体无差别精检。
- 若粗筛或B-rep失败，应把失败对象对反馈到约束层重新求解，而不是直接在SolidWorks中手动移动模组。通过后再保存、关闭、重新打开并复测。

## 2026-08-30 项目01方案1实体检查后的接续点

- 方案1已Replay到独立装配体并完成保存重开复核；12组严格AABB全部通过，14组条件顶层对象对的叶级B-rep全部完成，13组无干涉。
- 唯一未能直接放行的是ZZ00–GN00的3处实体相交。原型中存在完全相同的3个零件对，因此本次布局没有新增干涉，但当前仍不能称为“全模组零干涉”。
- 下一步优先由机械/工艺工程师判断：这3处是否是双阀处于清洁、排胶或检测工作位时的允许工艺接触。若允许，应在规则中登记对象对、工艺状态及允许接触零件；若不允许，应增加阀头退避Z位或静态净空规则后重新求解。
- 安装接触精检仍有一个工具性缺口：JJ00中的`FL209AK-00001-1`无法返回实体包围盒，使JJ00–ZZ00/HL00–ZZ00专项审计未完整结束。应增加“无包围盒叶体直接进入精确实体比较”或“经审核的非实体叶体跳过”策略，不能把读取失败计为通过。
- 在上述工程语义和工具缺口解决前，目标装配体可用于方案展示和原型等价粗复原，但`productionReady`必须保持`false`。
- 主要证据：`project01_solution1_v1_collision_summary.json`、`project01_solution1_v1_3d_screening.json`、条件B-rep目录、原型基线目录及`project01_solution1_v1_reopened_capture.json`。

## 2026-08-31 项目01条件通过后的接续点

- 项目01方案1已达到`PROJECT01_DEMO_CONDITIONALLY_PASSED`：严格AABB、条件B-rep、变化相关安装关系和保存重开均完成；非法干涉0、检查未完成项0。
- 3个ZZ00–GN00实体接触按精确实例白名单暂定放行，只适用于项目01方案1静态工艺位Demo。生产放行前仍需机械/工艺工程师确认，确认后把`engineeringConfirmed`及证据人/时间写回；若否决则删除规则并引入退避Z位重新求解。
- 无AABB实体降级功能已在真实JJ00–ZZ00中验证，但慢路径产生526次额外B-rep。后续项目仍应优先用AABB排除普通对象对，只在异常实体和结构嵌套对上使用该路径。
- 展示页已能区分绿色无非法干涉、黄色暂定允许接触和红色非法干涉，可作为项目01会议Demo的最终结果页。
- 下一案例建议进入项目03：先复用“模组识别→配合/安装坐标→扫描与功能端口→双阀覆盖→分级碰撞→Top-3”的规则模板，再从项目03原型提取自身数值。禁止复制项目01的操作面坐标、200 mm扫码光束、770×1100 mm行程或接触白名单。
- 项目03首次迭代只需做到参数门禁与Top-3展示，不应立即运行全量B-rep；待用户选定唯一候选后再Replay并按相同分级策略精检。

## 2026-08-31 项目03首阶段几何恢复后的接续点

- 项目03已完成10个主要模组解析、15个顶层实例分类、29条跨模组配合与9组连接提取；AA00–AE00安装坐标和58 mm定位孔距已恢复，无需重复采集。
- 当前Top-3仍正确关闭。还缺6项：AE00/AD00工作位、条码面与所在侧、AI00扫码光轴/工作距离、AB00/AC00公共行程、AH00标定服务点、AG00清洁/称重/排胶/硬度检测端口。
- 优先顺序保持：先从AE00/AD00和PPT恢复两个工作区；再从AI00叶体与扫码器结构恢复光轴和条码目标；随后提取AG00/AH00工艺端口；最后用AB00/AC00轴结构反求双阀公共覆盖。
- 同步补齐项目03多包围盒：普通实体对用膨胀AABB硬分离，框架/门洞/嵌套对列入条件B-rep；5个顶层辅助散件需明确归属到固定环境或对应主模组，不能独立参与求解。
- 精确AA00操作面仍待确认。短期允许使用服务簇所在`+worldX`侧作中等置信度粗布局基线，但维护空间和最终生产门禁不能据此放行。
- 缺失项和部分项清零后才生成项目03 Top-3并在展示层目测；本阶段不Replay。用户选中唯一候选后，才另存新装配体、执行严格AABB和条件叶级B-rep、保存重开复核。
- 机器证据：`demo/layout_previews/project03_module_mate_graph.json`、`project03_top_level_poses.json`、`project03_first_stage_geometry.json`、`project03_migration_readiness.json`和`demo/project03_parameter_package.json`。

## 2026-08-31 项目03双工作位完成后的接续点

- AE00/AD00双工作位已恢复并接入参数包，无需重复全树采集。两个粗布局点为U约522/907 mm、V约56.5 mm，中心距385 mm；实际A/B编号仍待PLC站号或入料方向证据。
- 下一步改为AI00扫描几何：优先利用已采集的AE00三组AE90结构和PPT“缓存位扫码”语义，定位唯一缓存扫码区；随后只读采集AI00叶体，区分载具读码器、产品读码器、直线模组和可能的显式光束/视线结构。
- 扫描约束必须分别记录：扫描光学原点、光轴方向、粗工作距离、目标条码侧、缓存停靠点以及产品顺序扫描移动方向。不得用项目01的200 mm光束或项目02的A180坐标替代。
- 工作位点目前是AD20包络中心，只用于平面可达。后续如能识别四个产品/载具点胶面，应增加局部目标集合；在此之前保持`engineeringConfirmed=false`。
- 完成AI00后，预计缺失项由5降至3；再依次提取AG00/AH00服务端口、AB00/AC00双阀公共行程，最后完成占用体/碰撞分类和操作面容量确认。
- 采集性能经验：代理hub初始化曾超时，直连stdio约100秒完成1222个实体的数据读取。后续项目03专项采集优先直连，且先做子树枚举再抓必要模组，避免把连接等待误判为CAD计算耗时。
- 机器证据：`demo/layout_previews/project03_ae00_ad00_leaf_envelopes.json`、`project03_work_positions.json`、更新后的`project03_migration_readiness.json`与`demo/project03_parameter_package.json`。

## 2026-08-31 项目03扫描几何完成后的接续点

- AI00产品扫码光轴与100 mm项目03 CAD基线已恢复，`scannerWorkingDistanceAndAxis`无需重复采集；机器证据为`project03_ai00_leaf_envelopes.json`和`project03_scanner_geometry.json`。
- 载具身份读取仍是部分证据：PPT描述RFID/条码同步读取，CAD只显示一个SR-X100和一个薄型身份头。短期粗布局可保留身份头原型位置；生产级条码侧和设备角色仍需BOM、标签面或工程师确认。
- 当前还缺3项硬证据。下一步优先同时处理AG00组合功能端口与AH00标定点，因为二者直接构成龙门必须覆盖的服务目标；随后用AB00/AC00自身轴结构反求双阀公共行程并验证全部工作/服务点。
- 之后补齐项目03多包围盒和碰撞对分类，并决定是否以+worldX操作侧原型基线暂时放行精确操作面债务。缺失与部分证据未清零前继续禁止Top-3。
- 扫描移动轴目前只有无符号方向；PLC四产品停点、缓存停车公差和SR-X100厂商距离到达后，应替换原型代理并重新求解，不能把100 mm CAD光束当作设备规格。
- 延续快速闭环原则：参数证据齐全后先生成Top-3和展示目测，只有用户选中唯一候选才Replay并执行严格AABB及条件叶级B-rep。

## 2026-08-31 项目03工艺可达闭环后的接续点

- 项目03缺失硬证据已经清零；当前2个工作位和7个服务点全部进入770×1100 mm CAD原型公共范围。最小余量仅6 mm，后续任何行程或端口替换都必须重新验证。
- 当前仍有5项`partial`，不能立即开放Top-3：精确操作面、载具条码/RFID角色、操作侧容量、多包围盒占用、静态碰撞策略。
- 下一开发重点是项目03占用体和碰撞对象对分类。优先复用已采集的AE00/AD00、AI00、AG00/AH00、AB00/AC00叶体；AJ00若拓扑普通且位于外侧，可先用保守顶层包围盒，避免无必要全叶采集。
- 对普通实体关系使用1 mm/侧膨胀多包围盒硬分离；龙门—输送/翻转/服务/标定/扫描及扫描—输送等框架、嵌套、工艺覆盖关系列为条件B-rep，求解期不调用SolidWorks内核。
- 操作侧可暂以服务簇所在`+worldX/+installationV`原型基线接受用于粗布局，但必须在参数包中保留中等置信度和生产确认债务；载具条码/RFID差异同理可作为非阻塞工程债务，但不能伪造第二光束。
- 占用和碰撞分类完成后，如5项partial均可按“原型粗布局基线”显式放行，才生成项目03 Top-3并在展示层目测；用户选择前禁止Replay和全量B-rep。
- 新机器证据：`project03_ag00_ah00_leaf_envelopes.json`、`project03_service_points.json`、`project03_ab00_ac00_leaf_envelopes.json`和`project03_dual_valve_reach.json`。

## 2026-08-31 项目03短暂停止开发的恢复入口

- 项目03当前阶段已冻结，完整恢复说明见`docs/project03_pause_handoff-CN.md`。
- 当前关键状态为：缺失硬证据0项、部分证据5项、`top3SolveReady=false`；尚未生成项目03候选或执行Replay/B-rep。
- 恢复后的第一个开发动作固定为“多包围盒占用体＋28组对象对碰撞分类”，无需重新采集AB/AC、AD/AE、AG/AH或AI。
- 占用门禁完成后，再决定以项目03原型基线暂时放行操作侧与载具身份读取证据，随后才开放Top-3展示。
- 当前转向其他探索方向不会改变项目01已经完成的Demo条件闭环，也不会覆盖项目02既有v52实体证据。

## 2026-08-31 项目02配合重建A/B/C实验后的接续点

- A/B/C三组已完成，机器证据位于`demo/mate_reconstruction_experiments/`；详细结论见`docs/project02_module_mate_reconstruction_ABC-CN.md`。
- 当前配合图重建能力为24/27，缺失`重合14`、`距离10`、`距离28`，均由T401顶层零件面无法稳定恢复导致；优先解决该局部问题，不要重新全量扫描模组树。
- 纯配合B组只有7/10位姿匹配，证明现有配合不足以唯一恢复原型。下一步应对A800和两个T401的剩余自由度做图/几何分析，而不是继续增加完整原型变换。
- C组当前使用5个完整6-DOF残差锚点，是保守Demo，不是最小信息方案。目标是将其压缩为端面/孔轴/距离/方向等工程可解释基准，并重新执行C组。
- 本轮没有B-rep结论。只有配合达到稳定可重建、最小锚点方案保存重开通过后，才对最终唯一装配体执行分级AABB和条件B-rep。
- 曾尝试距离`CreateMate`实体绑定和T401零件文档回退，SolidWorks进程级退出；该路径已回退。后续相关改动必须先在T401双零件的小装配体上隔离验证，再接入10模组整体验证。

## 2026-09-01 当前开发方向：恢复项目03

- 项目02配合重建研究已暂停，恢复入口保留在`docs/project02_module_mate_reconstruction_ABC-CN.md`第8节；除非用户明确回转，不继续T401、A800自由度或A500/A700过约束实验。
- 当前主任务恢复到`docs/project03_pause_handoff-CN.md`。无需重新采集AB/AC、AD/AE、AG/AH、AI叶体，也无需重新识别10个模组、两个工作位、扫描点、7个服务点或双阀范围。
- 下一步固定为生成项目03多包围盒占用体，并完成8个布局对象的28组对象对分类：普通对采用每侧1 mm膨胀AABB硬分离，框架/嵌套/工艺覆盖对列入选案后条件B-rep，固定环境安装关系允许设计接触但禁止非法穿透。
- 完成占用和碰撞策略后，更新迁移门禁与测试；随后再决定是否以项目03原型粗布局基线暂时放行操作面、维护空间和载具身份读取的部分证据。
- 仅在`top3SolveReady=true`后生成3个候选并进入展示目测；用户选择唯一候选前禁止Replay，选择后才进行严格AABB、条件B-rep和保存重开闭环。

## 2026-09-01 项目03占用门禁完成后的接续点

- 项目03多占用体已生成：7个结构模组共2203个叶实体盒，压缩成38个子树占用盒；AA00/AF00和AJ00分别采用固定环境/普通外置对象的顶层保守盒。
- 28组对象对已全覆盖，分类为12组严格多AABB、9组条件B-rep、7组安装接触；严格原型基线失败0组，求解期B-rep为0。
- 操作侧、操作容量和单束SR-X100站位已按“原型粗布局基线”显式放行，工程确认债务仍保留。当前`missing=0`、`partial=0`、`top3SolveReady=true`。
- 下一步不再采集CAD，也不进入Replay；应实现项目03专用顺序Top-3并在展示页比较3个候选。
- 求解顺序固定为：AA00/AF00固定 → AE00传输基准 → AD00双工作位 → AI00扫描 → AG00/AH00操作侧服务区 → AJ00供胶与维护 → AB00/AC00反求覆盖。
- 用户目测选择唯一候选后，才Replay至独立项目03装配体；先跑12组严格多AABB，再只对实际宽相命中的条件对执行叶级B-rep，最后保存重开复核。
- 关键文件：`demo/layout_previews/project03_module_occupancy.json`、`project03_migration_readiness.json`、`demo/project03_parameter_package.json`；回归152/152及前端生产构建通过。

## 2026-09-01 项目03迁移主线最新状态

- 项目03已完成专用Top-3、唯一选案、SolidWorks Replay、分级干涉验证和保存重开复测；不再处于“尚未生成候选”状态。
- 自主选定方案1：92个可行候选中的最低评分解，全部模组Replay位移为0，属于约束求解得到的原型等价最优解。
- 最新装配体：`demo/project03/FL9A24D063A000_project03_solution1_v1.SLDASM`。
- 最终Demo状态：`PROJECT03_DEMO_BASELINE_EQUIVALENT_CLOSED`。12/12严格AABB通过；9组条件B-rep有7组无干涉，另2组共8个交叠均为原型既有，新增干涉0；关闭重开坐标稳定。
- 该结论是“相对原型无新增干涉”，不是绝对零接触，也不是生产放行。AE00–AD00和AE00–AI00的原型交叠仍需工程确认。
- 机器结论入口：`demo/layout_previews/project03_solution1_v1_closure.json`；详细交接见`docs/project03_pause_handoff-CN.md`第9、10节。
- 后续宏观主线转向项目01、05、06的同流程迁移。每个案例复用约束类型和门禁流程，但重新提取自己的模组映射、基准、工艺点和占用体；任何非零位姿候选都必须执行实际安装成员对精检，不能使用项目03的原型等价捷径。

## 2026-09-01 项目05通用约束迁移接续点

- 项目01与项目03已完成案例闭环，宏观主线已选择项目05作为下一迁移案例；详细恢复入口为`docs/project05_migration_handoff-CN.md`。
- 项目05已识别11个真实主模组并归并为9个布局对象；已导出13个顶层相关实例、31条跨模组配合和10组配合束。N000/P000各有一个抑制变体，活动主模组仍为11个。
- 已从A000–D000配合恢复项目05自身安装坐标：流向约`+worldZ`、横向约`+worldX`、上向约`+worldY`、安装面Y约656 mm、机架到传输横向距离312 mm，且传输在1400 mm机架宽度内居中。
- 05-PPT工艺语义已接入：缓存位扫码、两个独立顶升工作位、CCD在工作位1/2间移动，以及19×14.25 mm视场和110±2 mm工作距离。门禁现为缺失5项、部分8项、`top3SolveReady=false`；工作位和CCD已从“语义未知”降为“CAD坐标待捕获”。
- D000/K000首次联合叶体捕获在重新打开79 MB原型时超时，未进入叶体遍历。已把捕获器改为“复用活动文档＋单模组增量＋失败保留成果”；SolidWorks恢复后先捕获K000，再捕获D000，不重复同时加载两个目标。
- 新增`@root`独立子装配体叶体捕获模式和“局部AABB八角点→整机世界AABB”回映器；Release构建、非集成.NET 320/320、后端162/162及前端生产构建通过。K000真实采集仍被本机SolidWorks新实例COM连接/后台`open_document`阻塞，尚无K000叶体结果。本阶段未生成Top-3、未Replay、未保存或修改项目05原型。

## 2026-09-01 项目05 K000双工作位真实几何闭环

- K000独立子装配体的`@root`叶级捕获已真实完成：314个叶组件、530个实体、0失败，并成功按原型顶层位姿回映到项目05整机坐标；上一节“K000尚无结果”的状态由本节取代。
- 从两个重复的`FL9C254098KA00.001/header 点胶位置`工艺子树恢复两个粗工作位；两点同高、同传输横向坐标，中心距约415 mm，符合05-PPT“两独立顶升工作位”的语义。
- 新增`project05_workstations.py`与`build_project05_work_positions.py`，生成`project05_work_positions.json`；工作位证据已由`partial`升级为`available`，当前门禁为缺失5项、部分7项。
- 修正项目05证据合并顺序：完整CAD几何不得被PPT部分证据降级；新增测试后Python回归164/164、前端生产构建通过。
- D000独立捕获本次停在SolidWorks加载/COM等待阶段，CPU采样无增长且没有输出文件；已只中止本次桥接进程，未修改任何CAD源文件。该耗时不是B-rep干涉检查。
- 下一步先在干净会话重试D000；若复现，改为一级子树分片，恢复缓存扫码位。随后捕获F000/M000形成扫描与CCD光学约束，再处理服务点、双阀公共可达域和多占用体。

功能修改意义：首次把项目05的PPT工艺语义与真实子装配体叶级几何闭环为可直接求解的工作点，同时建立证据优先级，避免状态机因低等级资料覆盖真实测量而倒退。

## 2026-09-01 项目05碰撞策略骨架与SolidWorks启动诊断

- 建立项目05九个布局对象的完整36对关系表：15对严格膨胀多AABB、13对结构/光学/嵌套条件B-rep、8对机架安装接触；求解阶段B-rep调用数保持0。
- 扫描—顶升、扫描—CCD在原型顶层占位盒中重叠，结合共同传输工艺路径和稀疏结构，归入“宽相可重叠、Replay后条件B-rep”，避免顶层单盒误杀原型。
- 只有K000当前具备完整叶级多包围盒，其余模组明确标注为顶层保守占位；因此`staticCollisionPolicy=available`，但`moduleOccupancy=partial`、`solverOccupancyReady=false`。
- 项目05门禁更新为缺失5项、部分6项；Top-3继续关闭。
- 干净会话D000重试未进入模型加载：COM未创建SolidWorks主进程；直接启动又停在隐藏`dummy splash parent`。FlexNet`lmstat`确认服务器和`SW_D`正常、SolidWorks许可0/1000占用，故不再把问题归因为许可不足或D000/B-rep耗时。
- Windows拒绝当前令牌重启FlexNet服务；未绕过权限、未重启Windows。CAD在线采集恢复后，继续D000→F000/M000；离线代码无需回退。
- 回归：Python 166/166通过，前端生产构建通过。

功能修改意义：把“碰撞规则是否完整”和“实体几何是否齐全”拆成两个独立门禁；即使SolidWorks暂时不可启动，也能完成对象对治理，并确保占位盒不会被误当成零干涉证据。

## 2026-09-02 当前主线恢复入口：项目02降原型依赖布局

- 当前主线已暂时聚焦项目02。`reduced-prototype`档位已移除旧Replay warm start、源顶层位姿复制和9条历史相对位姿窗口，但仍保留项目02原型估计的安装、光学、双阀行程和服务点参数；不能称为完全去原型。
- 当前Top-3可解，rank 1通过21/21工艺、13/13空间和64/64交互约束；连续两次求解位姿一致。新求解会自动废止旧选案，必须重新目测并批准唯一候选。
- 离线三维宽相已完成：28对中12对可直接排除，严格AABB失败0，16对需真实Replay后条件B-rep。当前状态不是实体零干涉闭环。
- 下一步先在展示页确认Top-3，再批准唯一候选；随后Replay到新的独立八模组装配体，按真实世界AABB缩减条件对并运行叶级B-rep，最后保存重开复核。
- 全链路时间戳已接入。恢复时先阅读`docs/project02_timed_layout_pipeline-CN.md`，运行`python scripts\summarize_project02_pipeline_timing.py`查看已完成和未运行阶段，不要无依据重复启动SolidWorks。
- 项目01、03现有闭环和项目05迁移证据保持不变；本轮不覆盖其装配体或JSON。

## 2026-09-03 项目02九对象求解接续点

- A600已按固定环境根模组加入每个Top-3候选，0自由度；当前结果不再只是“8个悬空模组”，而是“A600固定箱体＋8个可布局模组”。
- 最新`reduced-prototype`候选通过A600安装8/8、工艺21/21、空间13/13、交互64/64；36对碰撞关系无未分类项。
- 每次求解仍会废止旧选案。下一步必须先在展示层目测九对象方向、箱体边界和明显接触，再批准唯一方案；不得直接沿用此前的八模组选案。
- 批准后用完整项目02原型作为只读源另存新装配体。Replay保持A600原世界位姿，只移动其余8个模组；随后按18组条件B-rep和8组A600安装接触分别复核，最后保存重开。
- A600关系的验收不是“实体完全不接触”，而是“允许设计安装接触、禁止材料非法穿透”。当前99.718%叶体AABB覆盖率不足以直接给出生产放行结论。

## 2026-09-03 项目02九模组直接生成最新接续点

- 已完成不复制原型总装、不调用Replay的v2九模组直接装配体：`demo/FL9A24D062A000_9modules_direct_solved_v2.SLDASM`；保存重开后9/9组件、源路径和位姿通过。
- v2宽相36/36分类完成，严格AABB失败0。条件B-rep完成7/17对；A100相关前6对无干涉，A180–A200检出1对真实相交，故v2只能作为直接生成能力证据，不能作为零干涉最终解。
- 已把A180扫描头限制到A200的命名结构通道，并修正旧通道的轴向失配；`reduced-prototype`仅保留该几何/B-rep支持的模组局部接口窗口。新rank 1通过22/22工艺、13/13空间、65/65交互，目标位姿为`demo/layout_previews/project02_a600_fixed_projected_poses_v3.json`。
- v3 CAD生成被本机SolidWorks启动故障阻塞：提示“.NET Framework无法装入”，错误报告指向`nvoglv64`，确认后退出；当前不存在有效v3 SLDASM，禁止把v2重命名或宣称为v3。
- CAD恢复后优先从v2直接装配体做增量位姿更新并另存v3，随后执行：关闭重开9/9位姿复核 → 36对真实世界AABB → 仅实际重叠的条件B-rep → A600安装接触审查。任何B-rep失败继续回灌约束，不在CAD中手工拖动。
- 新入口：`scripts/build_direct_project02_nine_module_solution.py --source-direct-assembly ...`。该路径不依赖项目02原型总装，只复用系统自己已生成并验证的九模组容器。

## 2026-09-03 项目02最新接续点：v14推荐、A700–A800待闭环

- 当前推荐九模组实体为`demo/FL9A24D062A000_9modules_direct_solved_v14_correct_normal_heights.SLDASM`。其安装高度已按公共安装坐标系绝对高度修正，保存重开9/9位姿通过；它不是零干涉最终解。
- v14高风险B-rep已证明A200–A800、A200–A300、A300–A800、A500–A800均为0干涉。唯一已确认失败为A700–A800，共4对，集中在A700的A720/A730与A800的A860升降板。
- `demo/FL9A24D062A000_structural_occupancy_v38.json`已保存这些碰撞的对象对局部占用证据。整组强制AABB硬分离会导致无解，因此保持为软反馈＋条件B-rep，不得误报为硬约束已经闭环。
- v15通过整体平移A700尝试修复，但精检增加为6对，已淘汰。后续不要继续围绕A700做无依据的整体平移。
- 下一步先确认A800/A860在原型中的引用配置、刚性/柔性求解状态及其升降板对应的工艺静止状态。若碰撞只发生在某一运动快照，应确定布局验收所用的安全/待机配置，或按多个离散工艺状态分别检查；若待机状态仍碰撞，再把A720/A730对A860的局部禁入区转为硬约束。
- A700–A800修复后，再从v14尚未执行的11组条件对象对继续叶级B-rep，并保存重开复核。仍坚持“宽相毫秒级筛选→高风险对精检→首错即停→证据回灌”，不对已知无效版本做全量精检。
- 2026-09-03回归：Python编译通过；布局求解器56/56、法向高度投影3/3通过；`reduced-prototype`约2–2.4 s生成3个硬可行候选，25/25工艺、13/13空间、65/65交互校验通过。新增测试确认模组级龙门边界净空会进入最终空间硬门禁，而不只参与候选生成。

功能修改意义：本轮已把剩余实体问题定位到具体子机构和工艺状态，后续从“反复移动整个模组”转为“验证运动机构配置并施加局部禁入”，能够减少误约束、无解和重复B-rep时间。

## 2026-09-05 项目02最新接续点：v22无未接受干涉闭环

- 当前推荐九模组实体已升级为`demo/FL9A24D062A000_9modules_direct_solved_v22_full_leaf_candidate.SLDASM`；它由约束求解结果直接更新独立九模组装配体，不是复制原型总装。
- A100–A300已启用伙伴限定的完整叶实例占用，避免A300在A100不同支架间逐次产生新碰撞；v22通过26/26工艺、13/13空间和65/65交互约束。
- 保存重开9/9组件、路径和位姿通过，Fully Rebuilt。36对宽相中10组严格AABB失败0，19组免B-rep，17组为条件对。
- 只有A300相对v20/v21发生变化，因此重新精检A300–A100/A200/A700/A800四对，全部原始0干涉；其余13组由相对刚体变换不变安全复用v20证据。
- 机器结论`demo/layout_previews/project02_v22_incremental_brep_closure.json`为`policyClosurePassed=true`、未接受失败0。A700–A800仍保留原型既有交叠的子集，故`literalZeroInterference=false`；不能对外表述为所有实体绝对零接触。
- 下一步优先做两件事：一是由机械工程师确认A700–A800/A860接触是否属于允许工艺状态；二是修正直接建装总计时只有一个顶层stage的问题，并将“求解→投影→快筛→增量建装→增量B-rep→证据合并”封装为单条可恢复命令。若确认要求字面零交叠，再撤销原型基线例外并针对A860安全位置重新求解。

功能修改意义：项目02已从反复碰撞反馈进入可审计的条件闭环；后续工作不再是盲目移动模组，而是确认唯一剩余接触的工程语义并降低CAD运行成本。

## 2026-09-05 多项目参数标定门禁接续点

- 已建立01/02/03/05/06统一标定证据模型和机器可读缺口矩阵：`demo/layout_previews/multi_project_calibration_readiness.json`。
- 当前粗布局Top-3输入状态：01、02、03可用；05、06阻塞。该状态只代表输入齐全，不代表生产放行或完全去原型。
- 项目02参数包已从旧v52证据更新为v22闭环，明确记录策略闭环通过但`literalZeroInterference=false`；A700-A800工艺接触、供胶接口及第二T401范围仍为工程债务。
- 项目05下一步不应直接求解：先补扫描轴/工作距离、CCD CAD光轴、双阀公共行程、功能服务点和多占用体。
- 项目06已有模组身份清单，但尚无独立参数包；先解析各模组CAD路径和箱体—传输安装基准，再进入光学、服务点、行程及碰撞策略标定。
- 统一规则、字段含义和操作顺序见`docs/multi_project_calibration_and_solver_migration-CN.md`。
- 本轮离线定向回归73/73通过；全发现式回归在现有`test_layout_preview`慢求解路径超时，未继续占用环境，后续应单独为该套测试提供轻量fixture或显式慢测试标记。

功能修改意义：把后续迁移从“逐项目凭经验继续”升级为同一证据门禁驱动，能够在启动SolidWorks或B-rep之前判断是否值得求解，并直接给出缺失输入。

## 2026-09-05 项目02 v42依赖消融接续点

- 已建立版本化A/B/C离线实验和v22 SHA-256冻结清单；实验不会覆盖当前展示选案，也不会启动SolidWorks。
- A组3.33秒稳定复现v22；B/C移除v42历史伙伴反馈后均停在A700候选验证并触发90秒超时。该结果是不确定，不是无解证明。
- 无历史几何占用体已修正A100/A200门洞被一级大盒填实的问题，现为574个分层盒；A100–A700维护空间失败计数由2520降到840，但尚未得到A700可接受候选。
- 新增已知位姿兼容审计：v22自身在完整几何规则下有7项硬失败，6项来自未确认维护空间，1项为A300–A800叶AABB命中。说明当前不能只靠延长搜索时间解决问题。
- 下一步先拆分约束置信度：未确认100 mm维护带降为软评分/人工警告，阀头垂直通道及已确认实体禁入保持硬约束；非凸叶AABB命中转条件B-rep。随后重新运行B/C。
- 只有B/C出现相对v22实质变化且硬可行的Top-3，才进入展示、选案和CAD；在此之前不要重复Replay或全量B-rep。
- 详细说明与命令见`docs/project02_dependency_ablation-CN.md`，机器报告见`demo/layout_previews/project02_dependency_ablation_report.json`。

功能修改意义：用对照实验确认v42是伙伴限定的历史碰撞知识而非位姿文件，同时把下一步从盲目加时/跑CAD收敛为维护空间证据分级和非凸宽相语义修正。

## 2026-09-07 当前主线切换：项目02配合关系恢复原型

- v42依赖消融路线暂时冻结：A组可重复v22，B/C在A700阶段超时，已知v22位姿在完整几何模型下仍有7项不一致；恢复时从`docs/project02_dependency_ablation-CN.md`继续，不删除或覆盖现有报告。
- 当前主线切回“子装配体＋配合关系＋最少安装基准恢复项目02原型”，不运行布局约束求解。
- 已有基线：10个模组实例、27条跨模组配合；A/B/C均重建24条。A、C达到10/10原型位姿，纯配合B达到7/10，证明当前配合不足以唯一恢复全部模组。
- 三条公共失败为T401相关`重合14`、`距离10`、`距离28`；非T401关键问题为A800疑似剩余1个X向平移自由度，以及A500/A700公共过约束。
- 下一步不得先重跑完整A/B/C。先在A600/A200/T401小装配体解决3条面寻址，再做A800六自由度扰动与A500/A700逐条配合审计，最后把C组完整变换锚点压缩为最少工程基准。
- 详细状态、成功判据和文件入口见`docs/project02_module_mate_reconstruction_ABC-CN.md`第9节。

功能修改意义：明确暂停一条仍存在模型不一致的布局路线，把资源集中到可用小实验闭环验证的配合图复原，同时保留两条路线各自的恢复入口和证据边界。

## 2026-09-07 项目02可编辑配合图接续点

- 第一阶段Demo已完成：不可变源图＋Patch可生成Effective Graph，支持基础配合删除、参数修改和新增；冲突输入在SolidWorks前被拒绝。
- A500–A700真实闭环4/4通过：50 mm基线、删除、改60 mm、新增60 mm均完成新建装配体、保存、关闭、重开和参数回读。
- 模组图已补充`ReferencedConfiguration`并升级到v1.3；重建显式预加载源子装配体和解析轻量化子树，不再要求原型预先打开。
- 下一步优先开发面端点目录/选择器，使新增关系不再依赖复用已有端点；随后用逐条删边定位A500/A700首次过约束，再处理T401三条失败面和Width/Slot编辑。
- 详细入口：`docs/project02_editable_mate_graph-CN.md`。本阶段没有执行AABB/B-rep，不能从配合闭环推导实体无干涉。

功能修改意义：中间配合数据已从“只能查看”变成“可编辑、可审计、可重建”，后续自由度与冗余研究可以直接改Patch并重复实验。

## 2026-09-07 面端点目录与选择器接续点

- 已完成A500/A700原配合端点种子目录，包含2个高置信度平面端点；连续两次真实捕获的EndpointId及持久引用一致。
- Patch已支持直接填写两个`endpointIds`，编译器从目录展开完整端点并记录目录SHA-256；不使用`copyEndpointsFromMate`的60 mm距离配合完成创建、保存、关闭、重开和参数回读。
- 新增按ID查询、模组/面积/叶路径过滤、配合端点兼容性检查，以及SolidWorks当前选面捕获和另存增量目录接口。
- 全量叶面扫描在复杂装配树上出现长时间COM等待，已停止且未产出错误目录。后续固定采用“原配合种子＋指定叶零件/当前选面按需扩展”，不把全树枚举放入交互路径。
- 下一步需要人工选定A500或A700一张未参与原配合的新平面，执行一次`capture_selected_face_endpoint.py`真实增量验收；随后接入候选面高亮界面并开展A500/A700删边过约束实验。

功能修改意义：面已经成为可独立寻址、查询和复用的一等数据对象，新增配合不再依赖复制旧关系；按需扩展策略同时控制了SolidWorks遍历成本。

## 2026-09-07 人工新选面验收后的接续点

- 人工选择的A700新平面已捕获为`face:a700:a93b6607c982bd3f`，并追加到`project02_A500_A700_seed_plus_selected_v1.json`；叶零件、配置、Body/Face索引、面积、局部/世界中心、法向和持久引用均已记录。
- 该新面与A500目录端点建立垂直配合；新SLDASM保存、关闭、重开后1/1配合回读成功，证明新面可用于真实重建，而不只是目录查询。
- 已修正垂直配合Alignment无语义却被严格比较的问题；定向测试7/7及Release构建通过。
- 当前验收实体：`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular_rebuilt_v2.SLDASM`；结果：同名`.result.json`。
- 下一步优先开发“指定叶零件的有限候选面扫描＋SolidWorks高亮确认”，随后用目录端点开展A500/A700逐条删边过约束实验。继续禁止无边界全装配树面枚举。

功能修改意义：解除“新增关系只能复用旧配合面”的核心限制，并为后续由用户选择任意两面、编辑配合关系提供已验证的CAD执行基础。

## 2026-09-07 指定叶扫描验收后的接续点

- 已新增有边界的单叶面目录接口、脚本和最大面数保护；当前选择A700的`FL5A24D062A720009.01-1`作为真实样例，不再递归扫描整个A700。
- 单叶包含1实体/99面，在面积`1e-5 m²`及仅平面条件下得到34个端点；两次扫描34/34 ID一致，人工真值面被自动找回。
- 3端点基础目录与叶目录合并后为36端点：新增33、去重1。目录合并比较局部身份字段，允许世界坐标浮点微差和采集来源标签不同。
- 已实现按EndpointId在SolidWorks中恢复、选中并缩放；人工真值面和纯扫描新增面均通过。
- 纯扫描新增面`face:a700:ac51c9ef4bbe0f43`已驱动真实新配合，装配体保存、关闭、重开后1/1配合及参数通过。
- 验收实体：`demo/mate_graph_edit/project02_A500_A700_leaf_scanned_perpendicular_rebuilt_v1.SLDASM`；结果为同名`.result.json`。
- 下一步不再开发全树扫描；优先将候选列表、方向/面积筛选和ID高亮接入展示层，然后开展A500/A700逐条删边的过约束定位实验。

功能修改意义：指定叶扫描已经完成“发现候选面—目录合并—视觉确认—配合重建”的闭环，后续可以把精力转向候选语义排序和多配合约束诊断。

## 2026-09-07 面端点展示层验收后的接续点

- 本地展示页已新增“面端点目录与选择器”，默认加载A500/A700合并目录的36个端点；支持模组、叶零件、法向、面积筛选。
- 界面已完成A500面A＋A700扫描面B选择，垂直配合Patch预检返回2个模组、2条有效配合、0项警告。
- 展示页可通过实时MCP按EndpointId高亮SolidWorks面；`face:a700:ac51c9ef4bbe0f43`已真实恢复、选中和缩放成功。
- 已修复项目05可选数值缺失导致整页白屏，以及McpToolRunner工具名必须使用snake_case的联调问题。
- 前端生产构建通过；Python定向测试15/15；MCP Release构建0错误0警告。
- 展示层当前刻意只读：不会应用Patch、创建或保存装配体。下一步建议增加带明确目标路径和二次确认的“应用Patch并另存”动作，再开展A500/A700逐条删边过约束审计。

功能修改意义：面端点与配合Patch已具备可视化人工审核入口，后续CAD重建只需处理用户明确选定的候选面和Patch，不再靠命令行猜测或重复全树扫描。

## 2026-09-07 · 展示层真实另存闭环与过约束接续点

- 展示页已增加目标路径、预览摘要校验和显式确认；仅允许另存到`demo/mate_graph_edit/ui_runs`，且Patch、Effective Graph、结果与SLDASM均禁止覆盖。
- 浏览器真实创建`demo/mate_graph_edit/ui_runs/project02_A500_A700_ui_20260907T103357Z.SLDASM`；请求2、创建2、重开回读2，参数匹配通过，四类审计产物齐全。
- A/B/C三种既有恢复结果的共同首个过定义配合是A600–A700的`宽度10`，次级为`距离29`；A500没有直接首发错误，更可能经A500–A700的`距离8`传播。
- 初诊报告：`demo/mate_graph_edit/diagnostics/project02_A500_A700_overconstraint_stage1_v1.json`。
- 下一步唯一优先实验：构造A600+A700最小子图并删除`宽度10`后重建；如果A700恢复正常，再加回A500与`距离8`验证传播链。实施前需补齐Width编辑执行能力或复用支持Width的全量重建器。
- 本轮没有执行AABB或B-rep，因此“配合重建成功”仍不能解释为“实体零干涉”。

功能修改意义：机械工程师现在可从展示层安全提交经过预检的面级变更，并获得不可覆盖的CAD与审计结果；下一轮过约束工作已收敛为一条可证伪的最小实验。

## 2026-09-07 · A600/A700最小隔离实验后的接续点

- 仅删除`宽度10`的两模组实验完成：5/5创建、5/5重开、参数一致，但`距离29`仍报告过定义；耗时248.10秒。
- 同时删除`宽度10`和`距离29`的实验完成：4/4创建、4/4重开、参数一致，全部创建返回NoError；耗时214.98秒。
- 原型中的两条源特征错误码均为0且不是Warning，因此当前证据指向“重建冗余或语义差异”，不能直接认定原型设计错误，也不能把删边写成正式通用规则。
- 对照报告：`demo/mate_graph_edit/diagnostics/project02_A600_A700_overconstraint_stage2_v1.json`。
- 新增通用脚本`scripts/run_effective_mate_graph_rebuild.py`，支持单个Effective Graph的计时、不可覆盖重建和结果审计。
- 下一步优先补充：重开后顶层模组`GetConstrainedStatus()`、源`SolvingState`、Width高级参数及创建顺序；然后重建一次保留全部6条关系的A600+A700完整语义基线。
- 本轮未执行AABB/B-rep；配合错误消失不等于实体零干涉。

功能修改意义：最小实验已经否定“宽度10是唯一根因”，并防止团队把为消除错误码而删减健康源配合的临时方法误用为工程规则。

## 2026-09-07 · 完整语义基线后的接续点

- 模组配合图已升级为v1.4，完整保存顶层组件刚/柔性状态与Width面组、高级约束参数；重建和重开复核也已覆盖这些字段。
- A600+A700保留原型全部6条关系的真实闭环已通过：6/6创建、6/6重开、全部NoError、Width参数一致、A600刚性/A700柔性一致，两个组件均不过约束。
- 根因已确认：此前把A700按默认刚性重建，才使健康的`宽度10`和`距离29`依次报告过定义。不得再把删除这两条关系当作正式修复。
- 当前实体：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_baseline_v1.SLDASM`；机器根因报告：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_audit_v1.json`。
- 下一步唯一主线：导出并审计项目02完整顶层v1.4图，确认所有组件的配置、刚柔性、端点和高级配合语义齐全，再执行一次完整重建。随后才进行分层AABB与条件B-rep；本轮没有完成实体零干涉验证。

功能修改意义：将过约束问题从“删哪条配合”转化为“是否完整恢复组件求解语义”，为完整项目02的可靠复原建立了可重复的严格基线。

## 2026-09-08 当前主线恢复：项目02约束求解生成方案

- 当前主线从“可编辑配合图/原型配合复原”切回“依据通用约束与项目级标定参数生成项目02布局方案”。配合图路线保留现有v1.4完整语义基线，不继续扩展完整项目02重建，除非后续布局建装需要读取刚柔性或安装配合证据。
- 当前可信布局基线仍为v22：`demo/FL9A24D062A000_9modules_direct_solved_v22_full_leaf_candidate.SLDASM`。该装配体由约束求解位姿直接更新独立九模组容器，不复制项目02原型总装；A600固定，A100/A180/A200/A300/A500/A700/A800/T401按求解结果布置。
- v22离线与CAD闭环为：Top-3求解约3.357秒，rank 1通过26/26工艺、13/13空间、65/65交互约束；保存重开9/9位姿通过；10/10严格AABB通过；17/17条件对象对均有实体证据；`policyClosurePassed=true`且无未接受干涉。
- 验收边界保持不变：`literalZeroInterference=false`。A700–A800仍保留4个原型既有叶级交叠，按`noNewInterferenceOverAcceptedBaseline`通过但尚未经机械工程师确认；当前九对象只包含一个T401，供胶接口和第二T401范围仍是工程债务。
- 不能把v22称为完全去原型：`reduced-prototype`已移除原型顶层位姿复制和旧Replay warm start，但仍使用项目02原型/PPT估计的A600–A800安装基准、扫码几何、服务点、双阀粗行程和部分维护空间，并依赖v42伙伴限定的历史碰撞反馈。
- v42依赖消融A组可在约3.33秒重复得到v22；B/C移除历史伙伴标记后均在A700阶段超时，尚未证明无解。已接受v22位姿放入完整几何语义后出现7项不一致：6项来自`confirmed=false`的维护空间，1项为A300–A800叶AABB命中。
- 恢复后的第一个开发动作固定为约束证据分级：未确认维护带降为软评分/人工警告；真实实体禁入、安装、扫码和点胶可达继续作为硬约束；非凸框架/门洞的叶AABB命中只路由到条件B-rep，不直接判为实体干涉。
- 第二步增加“已接受位姿兼容门禁”和A700候选阶段计数/耗时诊断，然后重新运行B/C。只有得到不同的硬可行Top-3，才进入展示页目测、唯一选案、九模组直接建装、36对AABB和增量条件B-rep；若仍超时，先优化候选剪枝，不直接增加SolidWorks运行。
- 求解、投影、建装和精检继续沿用`docs/project02_timed_layout_pipeline-CN.md`的时间戳协议。任何碰撞失败必须回灌为有来源的约束或占用语义，禁止在SolidWorks中手工拖动成品掩盖求解问题。

功能修改意义：明确了布局求解主线的当前可交付基线、原型依赖边界和唯一恢复顺序，避免把配合图复原、布局求解与实体干涉三类验收混为同一问题，也避免重新执行已经完成的v22 CAD闭环。

## 2026-09-08 去v42离线求解已越过首个门禁

- 已完成保护空间硬/软证据分级、条件B-rep伙伴分流、v22兼容门禁和模组级候选耗时诊断；主请求/v22基线未被覆盖。
- v22在无v42伙伴标记的574盒几何模型下确认硬失败为0；5条粗估维护空间作为人工告警，15项非凸宽相风险进入条件CAD队列。
- B/C现均可生成3个完整硬可行解：B约13.69秒、C约30.72秒；C与v22最大平移差约654 mm，证明不是复制旧位姿。
- 当前只推荐C进入展示层，候选文件为`demo/layout_previews/project02_dependency_ablation/variant_c_preview.json`；CAD门禁仍锁定，未执行Replay或B-rep。
- 下一步：在展示层并排查看B/C rank 1，重点检查A700方向与操作侧、A300/A700明显接触、CCD/传输/龙门边界和供胶可维护性。若C目测通过，再批准唯一解并执行九模组直接建装与按风险排序的条件B-rep；若不通过，优先收紧A700通用候选/操作侧规则，不回退到v42位姿复制。

功能修改意义：主线从“去历史后A700超时”推进到“已有可供人工选择的独立Top-3”，下一次SolidWorks成本只会花在目测批准的唯一候选上。

## 2026-10-01 项目05当前接续点

- 项目05工艺参数粗布局证据已清零：2个工作位、F000扫码站、M000 CCD双工位、6个G/N/P服务目标、操作侧容量和双阀公共平面行程均已有独立JSON证据。
- 双阀粗范围覆盖全部8个目标，最小平面余量约2.87 mm；真实Z行程、软件限位、阀尖和维护扫掠仍禁止生产放行。
- K/F/M/G/N/P叶级多包围盒完成，A000/E000/D000/B000/Z000未完成；`moduleOccupancy`是唯一Top-3粗求解阻塞。
- B000捕获两次均在MCP initialize阻塞，未进入CAD加载；主SolidWorks会话未被结束。恢复时禁止重复采集已完成6个模组。
- 唯一下一步：在干净MCP会话按A000→E000→D000→B000→Z000逐个捕获并即时落盘，运行`build_project05_occupancy.py`直到11/11。之后才允许Top-3、人工选案、8步CAD动作和条件B-rep。
- 权威接续文档：`docs/project05_migration_handoff-CN.md`第7节；机器工作包：`demo/layout_previews/project05_structural_capture_plan.json`。

功能修改意义：下一次开发无需重新分析PPT或重复服务点/光学/行程标定，只需解除MCP会话阻塞并补齐5个结构占用体。

## 2026-10-01 项目05新的接续点

- 旧的“A/E/D/B/Z结构捕获阻塞”已经解除：11/11主模组完整，9对象共4084个叶实体盒，粗Top-3门禁已打开。
- 已生成项目05三候选；2197个组合中348个硬可行，最近一次求解持久化1.330秒。展示页已可切换方案1/2/3并审批。
- 当前候选1为最小位移的原型标定基线；候选2/3分别移动不同服务模组30 mm。尚未形成唯一选案，严禁直接批量Replay三套。
- 恢复后的唯一动作：先比较Top-3并审批一套；再逐步实现项目05 8个CAD动作，每步另存重开和严格叶AABB门禁；最后仅对13类风险对做条件B-rep并审计8组安装接触。
- 当前可交付范围是“项目05原型标定的粗静态约束解”；精确光学端口、Z限位、维护扫掠、胶管路径和跨项目去原型仍为生产级债务。
- 关键入口：`docs/project05_migration_handoff-CN.md`第8节、`demo/layout_previews/project05_preview.json`、`project05_pipeline_timing.json`。

功能修改意义：主线已从“补证据”切换为“唯一选案→真实CAD执行→实体碰撞闭环”，后续不应再重复已完成的结构捕获。

## 2026-10-01 项目05最新接续点：粗静态CAD闭环已完成

- rank 1已完成9阶段、11模组真实CAD累计装配；最终文件：`demo/semantic_ports/project05_ordered_direct_rank1_v7/step08_B000_cumulative.SLDASM`。
- 每阶段保存重开、组件白名单和位姿通过；最终11模组完整叶实体范围通过。运行时实例名已按源文件路径稳定解析。
- 15组严格叶AABB全部零命中；条件对预筛后的8组B-rep全部接受。D/K、D/F、B/M只保留原型既有接触，新增干涉为0。
- 机器闭环：`project05_static_collision_release_closure.json`，`success=true`、`productionReleased=false`；成功路径计时40.182分钟。
- 旧的“候选未选、CAD动作未实现、条件B-rep未完成”状态已失效，不得重复执行结构捕获或三候选批量Replay。

下一步主线：

1. 将9阶段真实CAD证据回写到项目05统一配置/自然语言档案，使步骤状态从“已编译待验证”升级为“现场CAD已验证”。
2. 把当前项目05专用顺序脚本抽象为通用异步作业执行器，补任意子序列、检查点恢复、失败回滚和结果查询。
3. 对原型估计参数建立来源/置信度/版本字段，优先替换扫码工作距离、CCD端口、Z限位、阀尖和维护扫掠；再开展跨项目迁移。
4. 将SHA-256、源几何版本和相对位姿纳入叶体/B-rep缓存键，避免重复约7分钟精检。

功能修改意义：后续开发重点已从“证明项目05能建出来”转为“统一数据契约、通用执行器、去原型参数与跨项目迁移”。

## 2026-10-01 项目05最新接续点：持久化自然语言作业已闭环

- 跨项目作业协议`ordered-assembly-job/v2`已启用；项目05可用自然语言生成8步计划并创建持久化证据回放作业。
- 真实工件全链、暂停恢复、受控失败回滚恢复均通过；最新报告：`demo/semantic_ports/project05_ordered_jobs/functional_closure/latest.json`。
- 展示页可选择项目05并查看逐步状态、尝试次数、检查点和实体路径；项目05`live_cad`被明确禁用。
- 56项后端回归和前端生产构建均通过。

当前唯一开发顺序：

1. 把项目05 9阶段专用CAD动作封装成统一动作适配器，先支持完整顺序和连续前缀，再支持安全任意子序列；每步仍需独立另存、重开和碰撞硬门禁。
2. 为项目01/03补`sequence + steps + assemblyPath + evidencePath`逐步工件索引，之后才能复用同一持久化作业接口；不得只因已有最终装配体就宣称逐步任务就绪。
3. 将几何SHA-256、源文件版本、配置名和相对位姿纳入缓存键，减少现场CAD与B-rep重复成本。
4. 用权威扫码、CCD、行程、服务点和维护扫掠数据替换原型估计，再做动态工况与跨项目生产迁移。

明确边界：`validated_artifact_replay`只复用真实已验收工件，不重新启动SolidWorks；只有`live_cad`动作适配器闭环后，才能宣称自然语言命令本次生成了新实体。

功能修改意义：恢复时无需再重复项目05真实长链和B-rep；下一阶段应集中解决“现场通用动作适配器”和“跨项目逐步索引”，而不是重复离线计划或最终装配体审计。

## 2026-10-01 新接续点：跨项目回放完成，项目05现场适配器完成首步实证

- 项目01/03逐步索引已补齐，项目01/03/05共22步真实历史工件回放全部通过；展示页已支持四项目选择。
- 项目05构建器已能单阶段运行，单步动作适配器代码和23项测试通过。
- D000真实试运行成功：205.494秒，新装配体、阶段结果、顶层/位姿/叶实体/保存重开审计均有效。
- 现有B-rep缓存键已确认绑定源SHA、配置、相对位姿、策略、基线、检查器和证据哈希，无需重写。

下一步唯一顺序：

1. 将项目05碰撞门禁的模组识别从项目02硬编码扩展到B000+Z000等多成员步骤。
2. 用新适配器运行K000至B000现场长链；每一步先AABB/缓存，仅对缓存未命中的条件对执行B-rep。
3. 完成长链失败回滚与续跑实证后，才开放项目05`live_cad`。
4. 再处理权威工程参数与动态工况；当前生产门禁保持关闭。

关键新实体：`demo/semantic_ports/project05_live_adapter_pilot_v1/step01_D000_cumulative.SLDASM`。

功能修改意义：后续不再需要证明单步CAD能否工作，而应集中验证多成员碰撞语义和完整现场任务链。

## 2026-10-01 最新接续点：项目05全动作现场适配器已闭环

- K000至B000的7步现场CAD接续作业全部成功；结合D000独立试点，D/K/F/M/G/N/P/B八个动作均已有真实CAD证据。
- 最终实体：`demo/semantic_ports/project05_live_adapter_jobs/project05-job-634ac5fcf9cf/cad-working/step-08-b000-attempt1/step08_B000_cumulative.SLDASM`。
- 机器闭环：`demo/semantic_ports/project05_live_adapter_jobs/project05_live_adapter_closure.json`；`allActionsLiveCadValidated=true`、`liveCadApiMayStart=true`、`productionReady=false`。
- 项目05 API/UI 已允许选择`live_cad`，但后端会读取闭环文件；闭环缺失或失败时拒绝启动。
- 实测总耗时47.403分钟；相关后端回归56/56、前端生产构建通过。

下一步顺序：

1. 运行一次从A000基座开始、D000到B000不中断的完整作业，验证首步创建、暂停恢复和失败回滚在同一现场链中成立。
2. 将碰撞基线检索从运行时实例名进一步收敛为“模组令牌+源SHA+配置+相对位姿”，避免实例后缀变化导致缓存漏命中。
3. 为项目01/03实现项目专属现场动作适配器；先选一个小阶段实证，再开放对应`live_cad`，不得直接复用项目05动作。
4. 用权威行程、光学端口、维护扫掠和软管参数替换原型估计，建立静态Demo门禁与动态生产门禁的独立发布状态。

功能修改意义：后续不应重复项目05分段长链；重点转为单次不间断作业、实例名无关缓存、跨项目现场适配器和权威动态工程参数。

## 2026-10-01 最新接续点：项目05不间断现场作业已完成

- 单一未播种作业从A000基座连续执行8个动作并成功结束；此前“需要再跑一次不间断作业”的事项已关闭。
- 最新实体：`demo/semantic_ports/project05_live_adapter_full_jobs/project05-job-8accc910d933/cad-working/step-08-b000-attempt1/step08_B000_cumulative.SLDASM`。
- 发布闭环：`demo/semantic_ports/project05_live_adapter_jobs/project05_live_adapter_closure.json`，状态`PROJECT05_LIVE_ADAPTER_UNINTERRUPTED_FULL_CHAIN_CLOSED`。
- 总耗时43.144分钟；80.61%为CAD动作，19.24%为每步新鲜位姿/AABB门禁。本轮条件B-rep为0秒，证明版本化缓存命中有效。
- 计时重复计数问题已修复；回归覆盖闭环、碰撞、缓存、API和计时。

后续唯一主线：

1. 从项目01或03选择一个最小现场阶段，建立其项目专属动作适配器并做单步真实CAD试点；不能把项目05路径硬套到其他项目。
2. 将模块、安装端口、工艺目标、碰撞策略和动作实现进一步移入统一项目档案，减少主程序中的项目分支。
3. 按权威程度替换原型估计参数，先解决行程限位与动态运动，再解决光学基准、软管和维护空间；保持静态与生产发布状态分离。
4. 性能优化优先缓存每步已安装上下文的叶实体/AABB捕获；自然语言解析和规划无需优先优化。

功能修改意义：项目05静态现场主链已完成；下一阶段从“证明能运行”转为“跨项目通用配置、动态工程验收和几何捕获性能优化”。

## 2026-10-01 最新接续点：项目03 AE00→AD00现场前缀已发布

- 单一作业`project03-job-592fc47f762c`连续安装AE00和AD00，两步配合创建、完全约束、保存重开、碰撞门禁和检查点连续性全部通过。
- 最新实体：`demo/semantic_ports/project03_live_adapter_chain_jobs/project03-job-592fc47f762c/cad-working/step-02-ad00-attempt1/step02_AA00_AF00_AE00_AD00_increment.SLDASM`。
- 发布闭包：`demo/semantic_ports/project03_live_adapter_chain_jobs/project03_ae00_ad00_live_adapter_closure.json`；API/UI仅允许AE00或AE00→AD00连续前缀。
- 总耗时476.967秒；AD00条件B-rep约89.430秒；回归41/41、前端构建通过。

下一步唯一顺序：

1. 审查AI00有效配合图、扫描光轴/目标区以及AE00/AI00原型基线，形成第三步动作规范。
2. 用AE00→AD00检查点现场插入AI00；完成配合、保存重开、条件B-rep和计时后，才把API前缀扩展到AI00。
3. 单独完成AD00 25度翻转扫掠；静态前缀发布不得冒充动态生产放行。
4. 后续按AG00→AH00→AJ00→AB00推进；存在残差锚点或柔性状态的步骤必须先消除或显式建模，不得默认为普通三基准刚性安装。

功能修改意义：恢复时无需重跑AE00/AD00；下一阶段聚焦AI00第三步和AD00动态工况，而不是重复历史工件回放。

## 2026-10-01 最新接续点：项目03三步现场前缀已发布

- AE00→AD00→AI00三步不间断真实作业成功；最终实体：`demo/semantic_ports/project03_live_adapter_three_step_jobs/project03-job-9c67704d73e5/cad-working/step-03-ai00-attempt1/step03_AA00_AF00_AE00_AD00_AI00_increment.SLDASM`。
- AI00的3驱动配合、2距离验证、保存重开和4对碰撞门禁全部通过；发布闭包和计时报告位于同一作业根目录。
- API/UI现场执行边界已扩展到三步连续前缀；AG00及后续保持关闭。

下一步唯一顺序：

1. 审查AG00锚定版配合图：支承面+单孔只约束5自由度，明确第6自由度来自何种工程防转规则。
2. 若只能使用原型残差角度，必须将其声明为临时静态锚点并写入闭包，不能称为去原型解；若能从第二孔/边/方向恢复，则改成显式端口。
3. 现场执行第四步后，完成维护包络和AD00/AG00、AB00/AG00等条件关系门禁，再决定是否发布AG00前缀。
4. AD00 25度扫掠和AI00权威光学参数保持独立生产阻塞，不与静态前缀混淆。

功能修改意义：接续开发应集中解决AG00剩余自由度，而不是重复前三步或绕过语义缺口。

## 2026-10-01 最新接续点：项目03所有静态动作已分段实证

- AE/AD/AI/AG四步不间断前缀通过；AH、AJ、AB从前一验证检查点依次接续通过。
- AB步骤内部原子执行AB00配合插入和AC00静态快照插入；最终实体、两份动作证据和17对局部门禁均有效。
- 分段全链闭包：`demo/semantic_ports/project03_live_adapter_ab00_tail_jobs/project03_segmented_full_live_adapter_closure.json`。

下一步唯一顺序：

1. 新建不带外部种子的七步作业，从AA00/AF00基座连续执行AE→AD→AI→AG→AH→AJ→AB。
2. 复用本轮绑定源SHA、配置、相对位姿、策略和证据哈希的B-rep缓存；每步仍必须重新捕获位姿/AABB。
3. 若七步全部一次提交，则生成不间断发布闭包并开放完整项目03现场API/UI；若失败，回滚到最后检查点并只修复失败动作。
4. 完整静态发布后，再分别处理AG/AB去原型防转基准、AC00柔性语义、AD00运动扫掠和权威工艺参数。

功能修改意义：当前无需再证明某个动作“能否运行”，而应完成一次不间断整链和生产动态债务分离。

## 2026-10-01 最新接续点：项目03七步持久化整链和最终45对门禁已关闭

- 单一作业`project03-job-acc1cd320f35`已从AA00/AF00基座连续执行AE→AD→AI→AG→AH→AJ→AB，并生成最终10对象装配体。
- AB首次在另存后重开时因同标题文档残留失败；桥接层已改为按绝对路径关闭并检查同标题残留，随后从AJ检查点只重试AB成功。该过程已形成故障—回滚—恢复证据。
- 正式闭包：`demo/semantic_ports/project03_live_adapter_full_jobs/project03_full_live_adapter_closure.json`。
- 最终独立45对审计：`demo/semantic_ports/project03_live_adapter_full_jobs/independent_collision_audit/project03_final_independent_collision_audit.json`，45/45通过、未解决对0。
- 项目03完整七步自然语言顺序已向API/UI发布；计时报告已覆盖每次尝试及失败恢复成本。

下一步唯一顺序：

1. 将AG00/AB00原型残差防转锚点改为显式工程端口或可配置临时参数，并运行去原型消融；没有权威基准时必须继续标注为估计值。
2. 为AD00建立25度翻转扫掠，为A100补充权威行程/工艺覆盖，为扫描与标定补充光学目标，为软管和维护区补充动态包络。
3. 任何源几何、配置、相对位姿或碰撞策略变化后，令版本化缓存失效并重跑受影响的条件B-rep，不复用过期结果。
4. 完成项目03去原型与动态门禁后，按同一项目档案、动作适配器和证据契约迁移到项目01/05/06。

功能修改意义：后续开发重点已从“静态整链能否执行”转为“去除临时原型参数并补齐动态生产语义”，无需重复已经关闭的七步静态实证。

## 2026-10-01 最新接续点：AG00/AB00运行时顶层位姿读取已抽离

- 版本化临时参数集：`demo/semantic_ports/project03_calibrated_parameters_v1.json`。
- 扰动原型顶层位姿后，AG00/AB00编译锚点保持不变；编译消融和真实CAD动作闭包为`demo/semantic_ports/project03_deprototype_ablation_v1/project03_deprototype_closure.json`。
- AG00、AB00各自从权威七步作业检查点重新插入并保存重开成功；总CAD动作耗时261.148秒。
- 项目档案升级至`2026-10-01.8`。当前可声明“运行时顶层位姿依赖已抽离”，不能声明“参数已去原型”或“生产基准已确认”。

下一步唯一顺序：

1. 为AD00建立静态起点/25度终点/扫掠体三态证据，并对每一态执行局部碰撞门禁。
2. 把AG00六个服务目标、AH00校准点和AE00两个工作位纳入A100/AB00公共覆盖动态验证；使用当前原型估计行程时必须标注非权威。
3. 为AJ00补软管连续包络和维护通道代理，先形成保守门禁，再等待最小弯曲半径和工程间隙确认。
4. 动态门禁闭环后，再用真实第二定位基准/Width安装基准替换版本化临时参数，并令相关碰撞缓存失效重算。

功能修改意义：接续工作不再需要调试静态锚点执行器，应转入运动扫掠和工艺覆盖；显式参数接口为将来替换权威值保留了确定入口。

## 2026-10-01 最新接续点：AD00真实0°/25°配置已验证，完整上下文基线待闭环

- AD20文件已确认具有`0度`和`25度`真实配置；左右`0/0`、`25/0`、`0/25`三组独立证据装配体均完成配置切换、几何变化、保存和候选碰撞检查。
- AA00、AB00、AI00候选全部通过；AE00在隔离上下文中存在接触。原型也已有AD20–AE00叶级接触，且AE00柔性状态无法由隔离装配忠实复现，因此本轮状态为`PROJECT03_AD00_CONFIGURATION_STATES_VERIFIED_FULL_CONTEXT_BASELINE_RECHECK_REQUIRED`，不是动态失败，也不是生产通过。
- 机器证据：`demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v4/project03_ad00_dynamic_configuration_assessment.json`；档案版本`2026-10-01.9`。

下一步唯一顺序：

1. 复制左右AD10父装配并分别固化嵌套AD20配置，禁止改写源文件。
2. 复制AD00并替换两侧AD10，再复制最终十对象装配体并替换顶层AD00，保留AE00及其他上下文。
3. 先只做`0°/0°`基线复现；要求AD00–AE00叶级接触身份与原型基线一致，否则停止并修复复制/柔性上下文。
4. 基线复现通过后再做左右25°两态；只允许基线接触的子集或等集，任何新叶级实体对直接否定该状态。
5. 三态通过后再建立0°到25°连续扫掠体，并用厂商限位替换原型估计。

功能修改意义：后续不再对隔离装配结果做人工猜测，而以“完整父上下文+叶级身份差集”为动态碰撞硬门禁。

## 2026-10-01 最新接续点：AD00三离散状态完整上下文已通过

- `0/0`、`25/0`、`0/25`三状态已用逐级副本在最终十对象上下文重建、保存、干净进程重开并完成AD00–AE00叶级B-rep。
- 直接上下文基线和三状态均为同一1个已知叶零件对；新增接触0，精检失败0，源文件SHA不变。
- 正式闭包：`demo/semantic_ports/project03_ad00_three_state_full_context_closure_v1.json`；档案版本`2026-10-01.10`。
- 构造器已经处理历史盘符引用、柔性派生配置后缀、长会话重开崩溃、B-rep完成后关闭RPC失败和进度JSON半写等问题。

下一步唯一顺序：

1. 用0°和25°端点的同一叶体建立连续扫掠代理；先采用保守包络离散5至9个中间角度。
2. 每个中间角度只对保守候选执行宽相；宽相重叠时运行条件B-rep，并沿用直接上下文1对基线的“无新增叶对”规则。
3. 确认左右动作是否可同时发生；未确认前分别验证左右单侧扫掠，不宣称双侧并行动作安全。
4. 获得厂商轴限位、速度和最小安全间隙后替换角度估计，令相关动态缓存失效重算。

功能修改意义：完整上下文基线复核已经关闭，当前动态主线从“端点真假”转为“端点之间连续路径是否安全”。

## 2026-10-01 最新接续点：连续扫掠宽相已生成

- 25°、1°步长、20 mm轴不确定性的保守扫掠共报告7项候选，模块集合为AA00、AB00、AE00、AI00。
- 该代理已能避免对所有模组做连续态全量B-rep，但不能替代真实中间角度实体；权威转轴、硬限位和安全间隙仍缺失。
- 当前全仓状态：后端587项与3个subtests全部通过，前端生产构建通过，桥接层目标测试84/84通过。

下一步建议先新增“中间角度输入接口”：若CAD没有5°/10°/15°/20°配置，则从厂商转轴与限位生成只作用于AD20运动叶体的受控变换副本；每个角度在完整上下文中仅检查AA00、AB00、AE00、AI00。没有权威转轴前，只能标记为估计演示，不得开启生产门禁。
## 2026-10-02 最新接续点：AD20 真实中间态发现 20°/25°新增干涉

- 此前 `project03_ad00_three_state_full_context_closure_v1.json` 已被标记为过期：柔性嵌套 AD20 没有保持命令的叶零件位姿，不能证明25°状态安全。
- 已建立上下文校正运动：以整机0°真实位姿为基准，叠加原生配置0°→25°的相对运动；0/5/10/15/20/25°均生成刚性快照并经过保存重开、位姿复测和精确叶级 B-rep。
- 0/5/10/15°采样通过；20°出现1个新增叶源对；25°出现2类、共3个新增叶体干涉计数。首次观测碰撞位于 `(15°,20°]`。
- 汇总证据：`demo/semantic_ports/project03_ad20_context_rebased_dynamic_closure_v1.json`；六状态累计记录耗时5870.410秒，生产门禁保持关闭。

下一步唯一顺序：

1. 将当前动态门禁接入自然语言装配作业发布条件：请求行程包含20°或25°时直接返回不可发布，不允许靠人工移动后继续。
2. 在需求方接受的情况下，把演示行程暂时限制为不超过15°，并明确它只是离散采样上限，不是连续安全上限。
3. 在15°至20°之间增加1°或更细采样，只精检已经识别出的相邻叶零件对，定位首碰角度；同时生成连续扫掠/保守包络。
4. 获得厂商转轴、硬限位、速度、最小安全间隙和允许接触分类后，替换当前原型推断运动，令全部相关缓存失效并重跑。
5. 若生产确需25°，优先调整 AD20 运动件、邻近电气件或 AE43 的几何/位置，再从0°重新执行全段门禁。

问题与阻塞：当前运动是从原型配置推断而非厂商确认；连续路径未证明；同一 SolidWorks 会话内构造后立即重开不稳定，现阶段必须用干净进程复核已保存工件。

功能修改意义：项目03动态主线从“端点看似通过”推进为“能在真实叶级证据上拒绝不安全行程”，剩余工作已收敛为首碰定位、连续路径验证和权威参数替换。

闭环测试：脚本语法检查通过，刚体变换5/5、完整后端592项及3个subtests、桥接层目标测试90/90全部通过。

## 2026-10-02 最新接续点：AD20动态硬门禁已进入自然语言作业入口

- `ordered_assembly_planner`新增项目03动态请求解析和证据判定；项目配置升级为`2026-10-02.1`并引用上下文校正闭包。
- 静态装配命令不冒充动态放行；15°只按离散静态姿态放行；20°/25°及所有未证明连续路径在启动CAD前拒绝。
- API作业创建、`safeToStartCad`和前端门禁卡片已贯通；四案例闭环证据为`demo/semantic_ports/project03_dynamic_command_gate_demo_v1.json`。
- 完整后端599项+3 subtests、前端生产构建、桥接层90/90目标测试通过。

下一步唯一顺序：先在15°–20°间做局部加密采样并生成连续扫掠证据；然后把经确认的连续安全上限写入同一动态闭包，使自然语言“翻转到X度”能够在不改执行器代码的情况下由拒绝转为放行。若25°必须可用，则先修改结构或布局，不能放宽门禁。

问题与阻塞：尚无连续动作可以被生产门禁放行；15°离散姿态只是已保存状态证据；运动参数仍为原型推断。

功能修改意义：低成本预演已先于高成本SolidWorks执行过滤动态风险，后续连续证据只需替换闭包数据即可进入现有装配流程。

## 2026-10-02 最新接续点：已知碰撞叶对首碰定位到 `(15.5°,15.6°]`

- 16°整机刚性状态完成保存重开、29/29位姿复测和叶级B-rep，确认新增干涉，不再运行17°–19°整机链。
- 双零件局部夹具对15.0°–16.0°按0.1°采样；15.5°最后无干涉，15.6°首次干涉，11/11精检完整、内核失败0、耗时113.166秒。
- 项目配置升级到`2026-10-02.2`；动态命令门禁展示整机离散区间 `(15°,16°]` 和已知叶对局部区间 `(15.5°,15.6°]`，并明确后者不代表整机连续安全。

下一步唯一顺序：围绕该叶对提出结构/位置整改候选（移动AE43-2电气件、修改AD20002运动件避让或降低机械限位），先在局部夹具中验证到25°无碰撞，再回到完整整机状态和全候选扫掠复核。若不整改，则生产动态命令继续全部拒绝，静态装配和离散姿态证据仍可独立使用。

问题与阻塞：现有布局无法实现25°无碰撞行程；其他叶对连续安全尚未证明；缺少厂商权威限位和允许结构调整范围。

功能修改意义：已将“动态不安全”转化为明确零件对和可量化的首碰角度，下一阶段可以做定向结构优化，而不是继续盲目全装B-rep。

闭环测试：完整后端600项+3 subtests、桥接层90/90、前端生产构建全部通过；动态证据累计记录6933.920秒。

## 2026-10-02 最新接续点：统一发布契约已贯通API、展示页和跨项目审计

- 新增统一契约，明确分离“静态演示可用”“现场CAD可启动”“动态路径已验证”“生产可发布”四层能力。
- 项目01/02/03/05静态演示均已放行；项目02/03/05现场CAD已显式放行；当前没有项目达到生产发布条件。
- 项目03动态闭包已进入统一契约：15°为通过的整机离散点，16°失败；已知叶对首碰在15.5°至15.6°之间，但整机连续路径仍未证明。
- API：`/api/demo/semantic-assembly-sequence/release-contract?projectId=project03`；跨项目证据：`demo/layout_previews/multi_project_assembly_release_contract_v1.json`。
- 展示页已能列出生产阻塞原因，不再把静态成功误报为动态或生产成功。
- 创建证据回放或现场CAD作业时会先执行同一统一契约；未放行的能力不会进入后台队列。

下一步唯一顺序：

1. 由需求方确认项目03是否必须达到25°，以及允许调整AD20002运动件、AE43-2电气件或机械限位中的哪一项。
2. 若允许结构整改，先用双零件局部夹具把候选改动验证到目标角度无碰撞，再回到完整整机上下文验证离散状态。
3. 对整改后0°至目标角度执行全候选连续扫掠；只有连续路径与安全间隙均通过，才把动态闭包标记为productionReady。
4. 按同一契约为项目02补A700/A100动态证据，为项目05补服务点与B000/Z000权威行程；项目01先补现场CAD适配器。
5. 项目06先完成模组身份、CAD路径、安装基准和碰撞策略标定，再创建项目配置，不能直接复制其他项目结论。

问题与阻塞：缺少项目03结构调整授权和厂商权威运动参数；项目01/02/05动态闭包未建立；项目06基础配置缺失。上述阻塞不影响现有静态演示和已放行的现场CAD链，但阻止生产发布。

功能修改意义：后续每项工作都会改变统一契约中的一个明确状态，开发进度、展示结果和安全门禁不再由人工口头解释。

闭环测试：目标测试25/25、完整后端604项+3 subtests、前端生产构建及Python语法检查全部通过。

## 2026-10-02 最新接续点：项目01现场CAD七步静态长链已闭合

- 项目01已完成 `SS00→FF00→SM00→GN00→BD00→GJ00→LM00` 七步真实CAD累计装配；每步均具备动作结果、保存重开、碰撞门禁、检查点和证据清单。
- 首轮在GJ00按硬门禁失败，未提交失败工件；原型复测证明GJ00—JJ00的9个叶级关系均为原型固有且候选没有新增关系。
- 同一持久化作业从BD00检查点受控恢复，只重跑GJ00、LM00并最终7/7成功；闭包明确不是物理时间上无中断。
- 最终装配体：`demo/semantic_ports/project01_live_adapter_full_jobs/project01-job-87ef17fa93e0/cad-working/step-07-lm00-attempt1/step07_project01_full_10_functional_object_static.SLDASM`。
- 证据闭包：`demo/semantic_ports/project01_live_adapter_full_jobs/project01_full_live_adapter_closure.json`；计时报告：同作业目录下`timing-report.json`。
- 总执行6040.783秒，B-rep批次累计4239.588秒；LM00最后4对精检是最大热点。
- 项目01已加入统一契约的现场CAD允许集合，API/界面仅允许已发布顺序的连续前缀；生产门禁仍关闭。
- 已用新鲜SolidWorks位姿复测验证对象对缓存：最终门禁从1519.424秒降至86.775秒（含位姿捕获），减少94.289%，8/8对象对通过且没有重跑B-rep。

下一步唯一顺序：

1. 为首次出现的新对象对增加叶级占用体/实体包围盒缓存和分层宽相，优先消除“顶层重叠但叶级无候选”的数分钟枚举。
2. 为项目01登记FF00的home/work/flip状态和连续扫掠候选，并将动态命令接入同一发布门禁。
3. 将LM00/ZZ00刚性快照逐步替换为可复测的安装端口、权威行程和独立运动状态；取得厂商数据前仍只允许静态演示。
4. 按相同闭包模板继续项目02的A700/A100动态证据和项目05权威服务点/行程；项目06仍需先完成基础配置。

问题与阻塞：FF00动态状态、LM00/ZZ00权威行程、供胶软管扫掠和维护空间没有闭合；8个模组仍使用原型推断参数；“无新增原型干涉”不等于绝对零干涉。这些问题不影响项目01已发布的静态现场CAD链，但阻止生产发布。

功能修改意义：后续性能优化和动态验证都有可量化的现有证据作为基线，不再需要重复整条长链来定位耗时或失败步骤。

闭环测试：项目01闭包检查全部通过；目标39/39、计时1/1、完整后端612项+3 subtests、前端生产构建通过。

## 2026-10-09 最新接续点：跨项目全局模组与语义端口MVP

- 已把项目01、02、03、05的34个CAD模组定义汇入全局目录；项目编号与A600/SM00等编号仅作为历史别名，去重只依赖可审计的CAD组件身份。
- 已汇总52个语义端口、28个连接模板和50条兼容关系，并区分“端口整体证据”与“具体模板实际使用角色”的可迁移性。
- 已建立版本化装配上下文、自然语言检索、歧义确认、图补丁预览、摘要确认写入和修订历史；全局连接还能编译回既有项目端口、模板和基础配合图候选。
- 展示页已增加跨项目工作台；三步命令`A600→A800→A180`形成3个实例、2条连接、3个修订，图层闭环成功。
- 本轮按用户要求不开发碰撞门禁；所有上下文和界面均标记`not_evaluated`，不宣称实体无干涉。

下一步唯一顺序：先补项目02 A200/T401端口，再迁移项目05九个模组端口，然后在已完成的执行清单上补累计源装配体选择和SolidWorks增量执行；项目06在基础档案建立后纳入。详见`docs/global_module_semantic_ports-CN.md`。

当前阻塞：项目02 A200/T401无安装端口，项目05没有全局端口证据，项目06无配置；部分旧端口仍依赖原型实例。以上阻塞不会被自动猜面或伪造模板绕过。

功能修改意义：自然语言自由组合已经拥有跨项目统一中间表达和可审计停止条件，后续工作从“重写一套求解器”收敛为“补端口证据并编译到现有CAD执行器”。

闭环测试：新增9/9、相关后端23/23、全量后端621项及3个subtests、Python语法检查、API函数级烟雾测试及前端生产构建通过。

## 2026-10-09 最新接续点：项目02 A200与双T401进入全局语义装配链

- A200已登记`重合26、槽口1、槽口2`的真实面级端口和槽口高级参数；第一套T401登记到A600的`重合14、距离10`，第二套登记到A200的`距离28`。
- 全局目录更新为34个CAD定义、58个语义端口、31个模板、53条兼容关系，其中56个端口具备完整局部恢复证据；项目02 A200/T401的“无端口”阻塞已关闭。
- 全局上下文支持目录声明的同源多实例，项目02 T401允许2套，第三套失败关闭；命令中提及A600/A200可作为连接目标提示。
- `A600→A200→T401-1→T401-2`形成4实例、3连接、4修订；3/3执行步骤均为`ready_for_project_adapter`。
- 本轮不启动SolidWorks，不执行碰撞门禁；A200/T401仍使用项目02源位姿案例锚点，不能解释为厂商通用安装基准。

下一步唯一顺序：先把项目05已有九模组证据迁移为全局端口；然后为执行清单实现累计源装配体选择、检查点和既有CAD增量执行器接驳；再补前端多实例序号与端口选择。项目06待基础档案建立后纳入，碰撞门禁继续按用户范围延期。

功能修改意义：项目02全局图层已不再缺A200/T401，并首次闭合“同源CAD零件两次实例化、分别连接不同上下文”的可解释装配场景。

闭环测试：A200/T401与全局上下文目标测试7/7、全量后端624项及3个subtests通过；证据见`demo/semantic_ports/project02_a200_t401_installations_v1/`和`demo/global_assembly_contexts/project02-a200-t401-evidence-v1*`。

## 2026-10-09 最新接续点：项目05九对象全局端口迁移完成

- D000、K000、F000、M000、G000、N000、P000、B000已建立到A000的全局机械端口；形成9实例、8连接、9修订，8/8执行清单步骤可交给项目适配器。
- 25条原型关系中21条作为驱动配合；旧v1.2配合图缺少高级参数的`宽度17`、`槽口1/4/6`只作来源证据，不猜测创建参数。
- 全局目录更新为34个CAD定义、74个语义端口、39个模板、61条兼容关系，72个端口具备完整局部恢复证据；所有已加载项目的`MODULE_HAS_NO_SEMANTIC_PORT`阻塞已清零。
- 当前唯一目录级硬阻塞是项目06缺少版本化项目配置。项目02/05仍使用项目案例锚点，并非厂商通用安装基准。

下一步唯一顺序：实现执行清单到累计源装配体、持久检查点和既有项目CAD runner的绑定；先用项目05完整九对象图链验证，再接项目02完整链。之后补展示页的多实例序号、端口选择和人工选面回退。碰撞门禁继续延期。

功能修改意义：已加载项目不再因“没有语义端口”停止；开发主线正式从端口资料迁移转入可恢复、可暂停的真实CAD执行编排。

闭环测试：目标测试10/10、全量后端627项及3个subtests、前端生产构建通过。证据见`demo/semantic_ports/project05_global_installation_ports_v1/`和`demo/global_assembly_contexts/project05-full-static-graph-v1*`。

## 2026-10-09 最新接续点：全局图已接入累计检查点与项目runner计划

- 新增`global-project-adapter-plan/v1`：唯一识别项目、展开同源多实例、核对机械装配顺序、读取已验证基座、生成累计步骤，并绑定既有项目runner；编译过程不启动SolidWorks。
- 项目05完整九对象链输出`ready_for_durable_job`，A000作为外部已验证基座，后续D000至B000共8步严格使用“上一已提交检查点”。临时任务库已验证创建任务和播种基座成功。
- 项目02 A200/T401局部链输出`blocked`，明确缺少A800、A180、A700、A300、A500、A100；阻塞计划无法创建持久执行任务。
- 项目02完整十实例链已补建，9/9语义连接可编译，机械顺序为`exact`，输出8个累计任务步骤。两套T401按既有runner证据合并为一个含两次CAD动作的步骤，避免重复插入。
- 展示页已增加项目执行计划、顺序类别、基座、累计步骤与阻塞原因。项目02/05证据上下文也已统一到跨项目主目录摘要，消除保存后无法由工作台加载的问题。
- 碰撞门禁仍按用户范围延期；本轮无SolidWorks进程、无B-rep、无实体安全结论。

下一步唯一顺序：增加“只创建并播种排队任务、不启动SolidWorks”的显式确认接口；随后用模拟runner闭合逐步提交、暂停、恢复、失败回滚和幂等。现场CAD仍由用户另行明确触发，碰撞门禁不偷偷带回本阶段。

功能修改意义：把“语义端口可连接”与“工程顺序可执行”分离，错误或不完整的自然语言链会在昂贵CAD动作之前失败关闭；正确完整链则能直接复用现有持久任务和项目runner，而无需重写装配执行器。

闭环测试：项目适配与相关全局图目标测试13/13、全量后端630项及3个subtests、API函数级烟雾测试、前端生产构建、Python语法与定向差异检查全部通过。

## 2026-10-09 最新接续点：全局适配任务可显式排队但不会误启动CAD

- 新增项目适配排队接口，必须`confirmed=true`；只创建`queued`任务并播种A600/A000基座，明确返回`executionStarted=false`、`solidWorksStarted=false`。
- 展示页增加人工确认复选框和“创建排队任务（不执行CAD）”；计划查看、编译和未确认请求均不会产生任务。
- 上下文摘要作为默认幂等依据；重复准备同一上下文会复用任务。
- 模拟runner闭环通过：D000后暂停并从D000恢复；K000失败产物隔离、回滚到D000，恢复后只重试失败尾部；初始输入确认来自A000外部已验证检查点。
- API隔离测试确认未确认请求被拒绝，确认请求的全部步骤保持`pending`，没有后台任务和SolidWorks进程。

下一步唯一顺序：增加独立的“明确启动”端点和二次确认信息；先运行单步/短前缀验证参数传递，再由用户决定是否运行完整现场CAD长链。碰撞门禁继续延期，不能把保存成功解释为实体安全。

功能修改意义：用户可以提前准备、检查并复用装配任务，而不会因为打开页面或生成计划意外占用SolidWorks；任务状态机的恢复和回滚已由全局计划真实驱动，而不只是孤立单元测试。

闭环测试：排队与恢复专项5/5、全量后端632项及3个subtests、API隔离测试、前端生产构建、Python语法和定向差异检查全部通过。

## 2026-10-09 最新接续点：二次确认启动与短前缀范围已实现

- 排队任务支持`stepLimit=1..N`；界面默认建议1步，完整项目02/05计划均可安全裁剪为连续短前缀。
- 新增独立启动接口：二次确认同时绑定上下文摘要和步骤数，启动前重新编译当前计划并检查项目、前缀、执行模式和统一发布契约。
- 同一任务重复启动请求只调度一次；HTTP请求本身不直接运行SolidWorks，后台任务才会进入项目runner。
- runner初始化前失败会将任务置为`failed`、回滚到A600/A000基座并写入证据，不会卡在`queued`。
- 前端已分离“创建排队任务”和“明确启动CAD任务”两个动作。本轮测试只检查后台任务是否正确登记，没有执行登记的任务，因此SolidWorks未启动。

下一步需要用户明确选择首次真实单步实证：建议项目05的D000或项目02的A800。单步通过后再扩展2至3步短前缀，完整8步长链最后执行。

功能修改意义：现场CAD执行现在有两道人为确认、上下文版本绑定、执行范围限制和重复调度保护；可以从最低成本单步开始验证，不再只能在“完全不执行”和“直接跑完整长链”之间二选一。

## 2026-10-09 最新接续点：全局任务监控与版本绑定恢复已实现

- 展示页对已启动任务进行1秒轮询，逐步显示状态、尝试次数、检查点、错误、最后有效装配体和回滚策略。
- 已接入暂停和取消请求；失败、暂停或取消后，恢复操作需要新的人工确认。
- 新增全局上下文专用恢复接口。恢复前重新核对`contextDigest`、步骤数、当前项目适配计划前缀、执行模式和统一发布许可，防止使用旧上下文继续运行。
- 恢复状态机会清除旧的启动标记，保留成功步骤和最后检查点，只把失败、取消或运行中断的步骤恢复为`pending`；随后幂等地登记一个后台任务。
- 模拟runner初始化失败后，任务正确失败并回滚到A000；通过专用恢复接口后保持A000检查点、待执行D000，并且只产生一个后台调度对象。
- 本轮仍未真正执行BackgroundTasks，因此没有启动SolidWorks，也没有新增碰撞结论。

下一步唯一顺序：由用户明确选择项目02的A800或项目05的D000，执行一次真实单步CAD实证；成功后复核保存文件、检查点和界面状态，再决定是否扩大到2至3步。碰撞门禁继续按用户要求暂缓。

功能修改意义：首次真实CAD试验不再是不可见的长时间黑箱；失败时能知道发生在哪一步、保留了哪个装配体，并且恢复操作仍受当前图版本约束。

## 2026-10-09 最新接续点：项目02 A800真实单步已成功

- 用户选择项目02后，通过正式准备和二次确认接口创建`project02-job-e6ffd79bb6e6`，严格执行A800一步。
- 从A600已验证基座插入A800，成功创建`重合35`与`宽度9`；保存关闭、重开复核、配合参数复核和完全约束检查均通过。
- 输出装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-e6ffd79bb6e6/cad-working/step-01-a800-attempt1-action1.SLDASM`。
- CAD动作98.165秒，持久任务总耗时100.207秒；A600/A800对象对门禁复用B-rep缓存，1.673秒完成，没有重新做精确B-rep。
- 门禁语义为`noNewInterferenceOverAcceptedBaseline`，只能证明未增加超过已接受原型基线的干涉，不能宣称绝对零干涉。
- 本次仍使用项目02案例位姿锚点闭合残余自由度；尚未替换为厂商权威安装基准。

下一步唯一顺序：把本次A800检查点登记为两步短链的累计输入，再执行A180扫描模组，验证A800不重跑、A180独立提交、失败时回滚到A800。两步通过后再安排真实暂停/恢复，完整长链仍不自动执行。

功能修改意义：全局自然语言图已经第一次通过正式持久任务和真实SolidWorks runner生成新的可重开装配体，主线从“调度机制可测试”推进到“项目02真实单步已实证”。

## 2026-10-09 最新接续点：A800检查点续跑A180已成功

- 新增`seedJobId`续跑契约：仅接受同项目、同上下文、状态成功且文件完整的最后检查点；自动选择完整机械顺序中的下一段连续步骤。
- 启动/恢复前重新核对当前计划切片和来源检查点，防止上下文修改、来源任务变化或文件丢失后继续运行。
- 前端新增“以上一检查点准备下一步（不启动CAD）”，仍保留独立启动确认。
- 真实任务`project02-job-b96f2dade86b`直接以A800检查点为输入，只执行A180，没有重跑A800。
- A180的`重合34`、`距离24`创建成功，保存重开、完全约束与干净求解通过；CAD动作36.882秒，任务总耗时38.923秒。
- A180与A600/A800两对通过既有`zeroInterference`缓存，门禁1.733秒，无精确B-rep重算。
- 最新累计装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-b96f2dade86b/cad-working/step-02-a180-attempt1-action1.SLDASM`。

下一步唯一顺序：从A180检查点准备`A700→A300`两步续跑任务；A700进入运行后请求暂停，执行器应先提交A700，再在A300开始前停住。随后通过上下文绑定恢复接口只执行A300。若A700动作过短无法及时发出暂停，则不强杀SolidWorks，改用下一组两步任务或受控测试钩子验证边界暂停。

功能修改意义：持久任务已经由“同一任务内续跑”扩展为“跨成功任务复用累计CAD检查点”；后续无需为了加入一个模组而从A600重复构建全部前序模组。

## 2026-10-09 最新接续点：A700→A300真实暂停恢复闭环已成功

- 任务`project02-job-2b64c336a17e`从A180检查点执行`A700→A300`。
- 暂停请求在A700处于运行中时登记；A700完成并提交后，任务在A300开始前暂停，A300尝试次数保持0。
- 专用恢复接口重新校验上下文、计划切片和来源检查点；恢复后A700没有重跑，A300执行一次并成功提交。
- A700动作44.355秒、门禁1.967秒；A300动作40.773秒、门禁2.425秒；任务两段累计执行90.337秒。
- A300创建`距离19`、`距离20`、`重合39`三项配合，保存重开、完全约束和干净求解均通过。
- 最新装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-2b64c336a17e/cad-working/step-04-a300-attempt1-action1.SLDASM`。
- 新识别阻塞：A700没有顶层驱动配合，使用案例位姿锚点和2个叶级锚点定位。当前结果适合项目02复现，不足以宣称跨项目通用安装。

下一步唯一顺序：从A300检查点执行A500单步，重点复核A500与现有A180/A700/A300/A800的对象对门禁；同时保留A700端口通用化任务，等待工程师选面或更完整配合图后替换案例锚点。A500通过后再进入A100两动作。

功能修改意义：暂停和恢复不再只是模拟runner测试；真实SolidWorks长动作已经证明只能在已提交步骤边界停住，并能从该检查点继续而不重跑成功步骤。

## 2026-10-09 最新接续点：A500校准模组单步已成功

- 任务`project02-job-9e45097d2c39`从A300检查点只执行A500，所有前序模组均未重跑。
- A500由`重合13`、`宽度4`、`距离27`三项真实顶层配合定位；`TargetCaseAnchored=false`、叶级锚点数为0。
- 保存重开、配合复核、完全约束和干净求解通过。CAD动作40.136秒，任务总耗时42.368秒。
- 5组对象对门禁1.994秒完成：2组AABB严格分离，3组版本化缓存命中，无精确B-rep重算。
- 最新装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-9e45097d2c39/cad-working/step-05-a500-attempt1-action1.SLDASM`。
- A500/A800仍采用原型基线相对策略，不能宣称绝对零干涉；A700的0项顶层配合问题仍保留为独立通用化阻塞。

下一步唯一顺序：从A500检查点执行A100龙门步骤。A100包含两个CAD动作，必须验证动作1输出成为动作2输入、两个动作分别保存重开、门禁只在最终累计结果通过后提交A100检查点。任何动作失败都应回滚到A500。

功能修改意义：项目02累计链已推进到校准模组，并首次在本轮证明一个不依赖案例锚点的功能模组可以从语义配合完整恢复。

## 2026-10-09 最新接续点：十对象Demo累计装配已闭环，碰撞验证已解耦

- 新增`demo`/`engineering`验证档位，任务和前端分开展示装配状态与碰撞状态。
- 真实任务`project02-job-635438e6d96f`从A100检查点只执行A200和T401，没有重跑A800至A100，也没有同步执行B-rep。
- A200与两套T401共三次真实CAD插入均通过保存、关闭、重开和目标约束状态验证。
- 最终实体：`demo/semantic_ports/project02_ordered_jobs/project02-job-635438e6d96f/cad-working/tail-02-t401-attempt1-action2.SLDASM`。
- 状态：`succeeded`、`assemblyStatus=assembled`、`collisionStatus=not_evaluated`；证据清单完整。
- 总耗时162.979秒，其中A200为66.580秒，T401双动作为96.110秒。

下一步唯一顺序：把工程碰撞验证封装为对现有`demoCheckpoint`运行的独立作业，而不是在装配执行器内重做CAD动作；之后将前端的单次命令扩展为多轮会话式追加，并加入“鼠标选面→登记临时语义端口→继续自然语言装配”的人工兜底。

功能修改意义：项目02已经形成可打开、可续装、证据完整的十对象Demo实体；当前主线阻塞从“CAD累计装配是否可行”转移到“如何让用户在多轮命令和未建端口场景下稳定使用”。

## 2026-10-09 最新接续点：独立工程验证闭环已完成

- 已实现对不可变`demoCheckpoint`单独发起工程验证，来源实体以SHA-256绑定，验证前后复核一致性。
- 真实验证`project02-engineering-validation-af30557143d1`通过当前静态门禁：45/45对象对闭合，总耗时301.067秒。
- 来源作业`project02-job-635438e6d96f`仍保持`succeeded / assembled`，并新增`collisionStatus=passed`及独立`engineeringCheckpoint`；`demoCheckpoint`没有改变。
- 验证只证明当前静态状态及当前基线策略，不证明运动扫掠、维护空间或生产可用。

下一步唯一顺序：转入多轮会话式自然语言追加。首先让同一上下文保存“用户命令→图补丁→Demo检查点”的轮次关系，使“先安装传输并展示，再添加扫描并展示”能在界面中连续执行；随后接入鼠标选面生成临时语义端口的人工兜底。

功能修改意义：碰撞验证已不再是主线阻塞；下一阶段可以专注用户实际操作方式和未建语义端口时的可用性。

## 2026-10-09 最新接续点：多轮自然语言会话已可持久恢复

- 已建立独立会话台账，持久记录“命令→图修订→CAD任务→Demo检查点”。
- 页面可加载既有上下文并恢复最近成功任务作为下一轮续跑来源；刷新后不再丢失`seedJobId`。
- 创建任务时按`contextRevision`绑定到准确轮次；旧上下文从`history`迁移，未知历史摘要不做推断。
- 完整回归：后端648项及3个subtests通过；前端生产构建通过；本阶段未运行SolidWorks。

下一步唯一顺序：实现“鼠标选面→记录稳定几何端点→生成上下文局部临时语义端口→自然语言引用该端口→预览配合→确认后执行”的人工兜底。先做纯数据和预览闭环，再选择项目02的一对低风险面进行一次真实CAD验证。

功能修改意义：主流程已有可恢复的多轮状态，下一阶段应解决端口目录不完整时用户如何继续，而不是继续增加项目专用自然语言规则。

## 2026-10-09 最新接续点：人工选面到配合草案已闭环

- 已实现当前SolidWorks选中平面到稳定面端点、上下文临时端口和自然语言基础配合草案的数据链。
- 临时端口与全局目录隔离；支持重合、平行、垂直、距离和角度；歧义、同实例和缺少数值均阻断。
- 展示页已提供选面登记和临时配合命令区域，但本阶段不会直接执行配合。
- 完整回归：后端651项及3个subtests通过；前端生产构建通过。

下一步唯一顺序：针对最近成功`demoCheckpoint`导出/读取当前累计装配体的可编辑配合图，将临时端点目录合并为该检查点的执行目录；然后把临时配合草案编译为现有`mate-graph-patch/v1`，先做预览摘要与摘要绑定测试，最后由用户选定项目02的两个面做一次真实新增配合、另存、重开复核。

功能修改意义：只有补齐“当前检查点配合图适配器”，人工选面产生的草案才能安全落到真实累计装配体；直接跳到CAD执行会缺少实例路径、刚柔性和既有配合语义，风险更高。

## 2026-10-09 最新接续点：临时选面配合已编译到检查点局部图

- 已实现成功Demo检查点的只读配合图导出规格与SHA-256绑定清单。
- 已实现“保留目标模组全部既有配合 + 新增用户选面配合”的目标局部图编译，输出`mate-graph-patch/v1`和有效图。
- 选面时现在记录活动SolidWorks装配体路径，避免把其他文档中的面端点误用到当前检查点。
- 前端提供明确确认的只读导出与非执行型编译界面；当前仍不会自动修改CAD。
- 完整回归：后端656项及3个subtests通过；前端生产构建通过。

下一步唯一顺序：在SolidWorks中打开当前项目02 Demo检查点，由用户或工程师选择两个低风险、来自不同模组的真实平面；在展示页登记端口并编译局部图。检查摘要和保留配合列表无误后，再新增一个独立“确认真实重配”作业，调用现有装配上下文重配执行器，输出新文件并完成保存、关闭、重开和新增配合复核。失败必须保留原Demo检查点且不得覆盖源文件。

功能修改意义：下一步不再研究新的数据格式，而是对已经贯通的“自然语言—选面—端点—补丁—局部配合图”做第一次真实CAD落地验证。

现场阻塞：现有十对象任务`project02-job-635438e6d96f`早于会话台账机制，其任务计划没有`contextRevision/contextDigest`，系统不会自动把它冒充为任一新上下文的检查点。真实验证前应二选一：生成一个由当前上下文正式绑定的新Demo任务；或另行实现“历史检查点受控导入”，用完整模组清单、装配体SHA-256和当前上下文摘要显式签认，不能直接手改台账。

## 2026-10-09 最新接续点：历史检查点阻塞已解除，当前配合图已绑定

- 已实现并实际执行“预检—显式确认—提交前复核—签认绑定”的历史检查点导入；上段现场阻塞已解除。
- `project02-job-635438e6d96f` 已绑定到 `project02-full-static-graph-v1` 修订10。十实例清单完全匹配，包含两个 T401 实例；原任务和原装配体均未修改。
- 签认文件：`demo/global_assembly_contexts/checkpoint-imports/project02-full-static-graph-v1/project02-job-635438e6d96f-4e686e861b08.json`。
- 已从当前 Demo 装配体只读导出并绑定配合图：10个模组、19条跨模组配合、8个配合束。
- 配合图：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/project02-job-635438e6d96f-4e686e861b08.mate-graph.json`；绑定清单为同目录同名前缀的 `.mate-graph.binding.json`。
- 完整回归：后端659项及3个子测试通过；前端生产构建通过。

下一步唯一顺序：打开上述 Demo 检查点，由用户在两个不同模组上各选一个低风险平面；在展示页登记两个临时端口并用自然语言生成配合草案；编译目标模组局部配合图并人工核对“保留的既有配合 + 新增配合”。核对通过后再新增真实重配作业，必须另存新装配体、关闭重开、验证新增配合和目标约束状态；任何失败都不得覆盖或污染当前 Demo 检查点。

功能修改意义：人工选面兜底已经从孤立的面记录，推进到与当前真实累计装配体及其真实配合语义绑定；接下来只剩第一次受控 CAD 落地，而不是继续增加中间数据格式。

## 2026-10-10 清单级持久编排完成后的接续点

已完成：通用CAD事务清单的自动连续执行、步骤边界暂停/恢复、失败回滚、逐包摘要锁定、逐次计时与证据索引；项目05六模组累计长链和项目03跨项目族实体均真实通过。汇总见`demo/global_assembly_contexts/global-cad-manifest-orchestrator-closure-v1.json`。

下一步建议顺序：

1. 用已支持的组合基座能力对项目01执行一次真实SS00首包回归，确认JJ00+HL00上下文与项目03采用同一通用规则；
2. 为持久编排命令增加后端API和前端任务状态展示，使暂停、恢复、失败原因和最后检查点无需读取JSON；
3. 将更多自然语言上下文直接编译成清单任务，验证非固定项目顺序的三至五步组合；
4. 单独补Project02 A800/A180缺失机械定位语义，在清单转为ready前不得启动CAD；
5. 碰撞/B-rep继续保持独立、可选的后验工程验证，不纳入当前装配编排验收。

当前非阻塞边界：运行中CAD动作不会被强杀，暂停仅在事务包提交边界生效；多模组基座缺少唯一`step00`保存重开证据时失败关闭。

## 2026-10-10 后端任务API和自然语言清单任务接续点

已完成：

- 项目01 `JJ00+HL00→SS00`通过与项目03相同的组合基座规则完成真实CAD回归，作业`project01-job-90be4101aaf4`耗时约115.9秒。
- 持久清单编排已开放创建、列表、状态、启动、暂停、恢复API；状态含失败原因、回滚、最后检查点、步骤耗时和事件流。
- 自然语言序列可直接编译为上下文、CAD清单和排队任务；三步及五步非固定Project05顺序已形成正式证据。
- Project02 A800/A180缺少完整定位时保持`blocked_before_job_creation`，不启动CAD。
- 全量后端741项及3个subtests通过；碰撞/B-rep未评估。

后续顺序：

1. 三步非固定顺序真实CAD短链已经成功：`A000→G000→F000`总耗时378.139秒，未读取Project05固定顺序。
2. 前端继续暂缓；产品展示需要时再消费现有API。
3. 单独补齐Project02 A800纵向安装基准和A180扫描支架定位基准，再验证清单由blocked转为ready。
4. 扩大自然语言案例到其他已登记项目族，不把项目固定顺序写回通用编译器；五步Project05案例当前已编译排队但未执行CAD。
5. 碰撞/B-rep继续作为独立可选工程验证。

## 2026-10-11 最新接续点：A800/A180推定定位标准已闭环

- 已将需求文件、真实CAD配合、几何推定和Project02原型测量统一为版本化定位标准。
- A800规则为`重合35＋宽度9＋沿X案例锚点`；A180规则为`重合34＋距离24＋槽口3只读证据＋案例锚点`，扫码光学作为A180到A800的独立功能关系。
- A800/A180语义端口构建器均绑定定位标准版本与摘要；审计结果为`coarseLayoutReady=true`、`productionReady=false`。
- 标准、审计和测试详见`docs/project02_inferred_positioning_standard-CN.md`；机器审计位于`demo/positioning_standards/project02_positioning_standard_v1.audit.json`。
- 聚焦回归6项通过；本轮未启动SolidWorks、未运行碰撞/B-rep。

下一步唯一顺序：让通用事务DAG在用户显式选择该标准时，把A800/A180从`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`转换为`ready-with-project-baseline`，并把标准版本、摘要和临时限制写进CAD事务包；默认无基线模式仍必须失败关闭。完成纯编译回归后，再决定是否执行真实A600→A800→A180短链。

功能修改意义：Project02不再因厂商数据缺失而只能停留在口头规则，但案例基线也不会被静默冒充为通用或生产参数。

## 2026-10-11 最新接续点：显式基线已使A800/A180通用清单就绪

- 通用DAG和CAD事务包现支持显式选择`project02-inferred-v1`；默认不选择时仍阻断A800/A180。
- 自然语言`A600→A800→A180`已生成2个无阻塞事务包和排队任务`project02-job-6e3c1b72de5d`，CAD尚未启动。
- 清单：`demo/global_assembly_contexts/project02-positioning-standard-v1-smoke.cad-transaction-manifest.json`；编译报告为同名前缀`.natural-language-compilation.json`。
- 全量后端回归`748 passed, 3 subtests passed`。
- 当前SolidWorks活动文档为带未保存标记的Project05装配体，真实短链执行被主动暂缓，避免污染现场文件。

上述现场阻塞已经解除。用户清理其他装配体后，任务`project02-job-6e3c1b72de5d`已完成A800→A180两包真实短链：A800耗时`182.943 s`，A180耗时`32.787 s`，总耗时`215.913 s`；两步保存、关闭、重开、配合参数和检查点连续性均通过。最终装配体与证据位于`demo/global_assembly_contexts/manifest_jobs/project02-job-6e3c1b72de5d/`，独立复核为3个顶层对象、文件哈希稳定、重建健康。

下一步建议顺序：

1. 保留该三对象短链作为Project02推定定位标准的最小真实回归基线；
2. 将A180到A800条码目标区的工作距离、光轴朝向和无遮挡检查由当前功能关系描述升级为可执行的只读几何验证，不修改CAD位姿；
3. 对A800和A180各执行一次去案例锚点欠约束审计，明确厂商数据最终需要补齐的自由度和端口；
4. 在不引入项目固定顺序的前提下，将同一标准扩展到Project02下一类服务模组；
5. 碰撞/B-rep继续作为独立可选后验验证，不改变当前装配编排主线。

当前边界：该闭环证明的是“显式Project02粗布局基线可以驱动真实累计装配”，不代表厂商尺寸已确认，也不把`productionReady=false`提升为生产可用。

## 2026-10-11 最新主线调整：自然语言驱动的子模组级灵活装配

上一节中“优先升级A180光学只读验证”的建议已降为后续可选工程验证，不再是当前唯一下一步。当前主线以`docs/development_execution_rules-CN.md`第25节为准：扩大自然语言命令、全局模组目录、语义端口、通用关系模板、动态事务DAG和真实累计CAD执行的自由组合覆盖。

当前已具备：

- 版本化自然语言命令中间态；
- 全局模组身份、语义端口和配合图基础；
- 项目无关事务DAG与CAD事务包；
- 自动连续执行、暂停恢复、失败回滚和不可变检查点；
- Project01/02/03/05真实CAD证据；
- Project02 `A600→A800→A180`最新三对象闭环。

当前核心缺口：

- 全局模组的语义端口和关系模板覆盖仍不均匀；
- 仍有部分模组只能通过项目级案例适配器闭合自由度；
- 任意3～5步自然语言子集尚未形成系统化编译与CAD测试矩阵；
- 多轮追加虽已有会话台账和检查点基础，尚未对广泛模组组合完成端到端验收；
- 跨项目组合的端口兼容性必须由目录证据决定，不能仅凭功能名称拼装。

下一步唯一顺序：先生成机器可读的全局端口覆盖矩阵和缺口优先级；随后选定首批通用支持集，补齐关系模板与结构化阻塞信息；再建立12条自然语言编译测试、3条动态DAG，并执行Project02扩展链及另一项目族的真实CAD链。碰撞/B-rep、生产放行、精密光学和动态工艺保持独立非阻塞状态。

功能修改意义：后续开发不再围绕Project02生产参数无限细化，而是利用现有Project02实证作为回归基线，提升系统对不同模组子集、顺序和自然语言表达的通用装配能力。

## 2026-10-11 阶段B完成：全局端口覆盖矩阵

- 已新增机器可读的全局模组—端口—关系模板—CAD端点覆盖矩阵：`demo/global_assembly_catalog/v1/global_module_port_coverage_matrix.json`。
- 当前目录统计为43个模组、61个兼容连接对；43个可自然语言检索，34个具备语义图和CAD端点，59个连接对可形成CAD端点关系。
- 新增选择就绪度判断：允许使用定义ID、`项目:模组`或唯一模组号；未知、重名、缺端口、连接子图不连通都会在CAD前结构化阻断。
- Project02 `A600+A800+A180`已验证为`ready`；Project06共9个模组因缺少语义端口保持阻断，其中8个P0、1个P1。
- 新增两个只读后端接口：`GET /api/demo/global-module-port-coverage`和`POST /api/demo/global-module-port-coverage/selection-readiness`。
- 审计工具默认只读签名全局目录，避免重建目录时改变摘要并破坏既有上下文绑定。
- 完整后端回归：`754 passed, 3 subtests passed`；本阶段未启动SolidWorks，碰撞状态仍为`not_evaluated`。

下一步唯一顺序：进入阶段C，从34个CAD端点就绪模组中选定首批跨项目支持集；建立不少于12条自然语言关系测试；补齐安装、重合、对齐、距离、同轴和侧向关系的通用模板与自由度解释；再选3条合法3～5步链生成动态事务DAG。Project06只有在端口有真实证据后才解锁。

功能修改意义：后续不再靠逐个项目试错寻找“哪些模组能装”，而是先由覆盖矩阵和就绪度接口决定能力边界，把真正缺端口的对象与已经可执行的组合明确分开。

## 2026-10-11 阶段C第一轮：关系语义、自由度解释与迁移预览

- 新增`global_relation_semantics.py`，将自然语言关系归一为安装、重合、同轴、平行、垂直、距离、角度、居中、槽口和方位关系。
- 复合安装模板不能被拆借为独立基础配合；“只让F000与A000同轴”会因没有独立同轴模板而阻断，但“把F000安装到A000”仍可选择完整安装束。
- 模板现在明确区分驱动步骤和`validate_only`步骤，并给出自由度闭合、欠约束、需CAD验证或历史CAD闭合等解释。
- 当前签名目录：39个模板、35个复合安装模板、2个独立距离模板、0个同时满足便携端点和驱动定位的独立基础关系模板。
- 已修复全局目录构建器忽略`endpointCatalogPath`的问题。迁移预览恢复A500/A700共享面目录后，可得到1个便携驱动距离模板；但单一距离仍欠约束，DAG继续阻断把它当成完整安装。
- 首批支持集：Project02 `A600/A800/A180/A500/A700`，Project03 `AA00/AE00/AI00/AH00/AJ00`，Project05 `A000/M000/F000/P000/G000`；三个子图均为`ready`。
- 新增14条关系语言基线和后端接口；全量回归`772 passed, 3 subtests passed`。

证据文件：

- `demo/global_assembly_catalog/v1/global_relation_capability_matrix.json`；
- `demo/global_assembly_catalog/v1/global_relation_initial_support_set.json`；
- `demo/global_assembly_catalog/v1/global_relation_language_cases.json`；
- `demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json`；
- `demo/global_assembly_catalog/v1/refresh-preview/global_relation_capability_matrix.json`。

下一步唯一顺序：建立签名目录版本迁移和旧上下文重绑定机制；迁移A500/A700共享面目录但不直接覆盖当前目录；补充至少一组可便携的独立重合/同轴/平行模板；建立“修改已有关系”事务；最后用首批支持集形成不少于12条命令级编译测试和3条动态DAG。

功能修改意义：系统现在能区分“自然语言听懂了”“有精确端点模板”“该关系能驱动位置”“关系足以闭合自由度”四个不同层级，避免把理解成功误报为可装配成功。

## 2026-10-11 阶段C第二轮：目录迁移与关系编辑事务

- 已实现候选全局目录对旧上下文的无损迁移预览和摘要确认提交；不覆盖`global_module_catalog.json`，也不修改源上下文。
- 真实Project02十对象上下文迁移结果为`ready`，0阻塞、0警告；新上下文为`demo/global_assembly_contexts/project02-full-static-graph-catalog-refresh-v1.json`。
- 迁移计划与绑定证据位于`demo/global_assembly_catalog/migrations/707e0cfcd85e-to-89169ae6223d/`。
- 已新增既有实例之间关系的新增、替换和删除接口；A500/A700 50 mm关系可精确匹配并提交，60 mm未登记关系按预期阻断。
- 关系编辑已进入动态DAG：驱动关系生成`ADD_RELATION`并要求CAD检查过约束；只读关系生成`VERIFY_RELATION`；不再产生`POST_INSERT_CONNECTION_NOT_SCHEDULED`。
- 真实十对象关系编辑上下文：`demo/global_assembly_contexts/project02-full-static-graph-relation-edit-v1.json`；验证证据：`demo/global_assembly_catalog/migrations/707e0cfcd85e-to-89169ae6223d/project02-full-static-a500-a700-relation-edit-validation.json`。
- 完整后端回归：`782 passed, 3 subtests passed`；未启动SolidWorks，碰撞/B-rep保持`not_evaluated`。

下一步唯一顺序：为首批支持集登记独立重合/同轴/平行端点模板；将`ADD_RELATION`事务下沉为CAD事务包；扩充到12条命令级测试和3条动态DAG；选一个低风险关系做真实CAD另存、重开和参数复核。

当前边界：A500/A700单独50 mm关系只能表达一个几何条件；若用它定位新插入模组仍然欠约束。它用于已安装实例的关系编辑时，可以进入CAD求解，但CAD必须检查是否与原有安装配合过约束。

## 2026-10-11 阶段C第三轮：Project01组合约束已闭合

- 已登记GN00/JJ00独立重合、独立同心和GN00/SS00独立平行三类便携关系；候选目录现为42个模板、67条兼容边。
- 防转平行模板明确声明它与`GN00_to_JJ00_primary`互补；DAG只在这项目录证据存在时把两条连接合并到同一GN00插入事务。
- Project01三模组上下文已从签名目录安全迁移并重建。SS00形成第1个事务；GN00主定位与防转关系形成第2个事务，共3个配合步骤。
- DAG状态为`ready_for_generic_cad_executor`，CAD事务清单为`ready_for_generic_executor_implementation`，0阻塞。
- 删除防转连接的消融测试仍返回`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`，证明没有使用通用自由度减法放宽门禁。
- 复现脚本：`scripts/run_project01_declared_relation_closure.py`；证据：`demo/global_assembly_catalog/v1/relation-v2-preview/project01-gn00-standalone-parallel-closure.json`。
- 本轮没有启动SolidWorks，没有执行碰撞/B-rep。
- 12条命令级关系矩阵全部通过；Project01、Project03、Project05三种动态DAG形态均通过项目无关编译。
- 命令矩阵证据：`demo/global_assembly_catalog/v1/relation-v2-preview/global_relation_command_matrix.json`。
- 后端全量回归为`788 passed, 3 subtests passed`。

下一步：把Project02既有实例关系编辑、Project01组合闭合、Project05长链统一成可持久执行任务；随后选一个低风险代表关系执行真实CAD另存、重开与配合参数复核。Project06继续因缺端口而阻断。

功能修改意义：自由组合不再要求每个模组只有一条“全定位模板”，可以由明确登记的主定位和补充关系共同闭合，同时继续对未登记组合失败关闭。

## 2026-10-11 接续点：Project01多连接事务已完成真实CAD闭环

- Project01动态链包含两个累计事务：`SS00`为1条连接/3个配合，`GN00`为2条连接/3个配合。
- 新增有效图精确覆盖门禁。事务请求与目标模组实际重建配合必须在名称、类型、方向、距离和角度上完全一致；隐藏的额外配合也会阻断。
- 新增事务执行投影。它保留权威图作证据，只把本次目标、实际上下文和本次配合交给现场适配器，解决原型图中`FF00/SM00`尚未装入时的错误解析。
- 持久任务`project01-job-066a20f791a4`首次在第二包失败后回滚到已提交的`SS00`检查点；修复后恢复任务，仅重试`GN00`，第一包尝试次数仍为1。
- `GN00`最终3/3配合创建成功、完全约束、保存关闭重开成功、配合参数复核一致；恢复尝试耗时约69.25秒。
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-066a20f791a4/packet-runs/packet-002-attempt-02/project01-cross-family-relation-v2-v1-packet-002.SLDASM`。
- 闭环摘要：`demo/global_assembly_contexts/project01-relation-v2-real-cad-closure.json`；全量回归`791 passed, 3 subtests passed`。
- 碰撞/B-rep未执行，状态仍为`not_evaluated`，不影响本轮自然语言装配编排验收。

下一步建议：把相同的“精确图覆盖＋执行投影”机制用于既有实例的`ADD_RELATION/VERIFY_RELATION`真实CAD事务，再扩充第二组跨项目的多连接自然语言案例；无需回到项目固定顺序或人工拖动模组。

功能修改意义：多关系共同定位一个新模组已经从纯编译推进为可恢复的真实CAD能力，下一轮可以集中验证“修改既有装配关系”，而不是继续修补Project01专用执行路径。

会话卫生待复核：本轮成功结果关闭后，SolidWorks仍显示由适配器临时打开且带未保存标记的`FL9C24N074GN00.001`。源文件时间戳未变化；自动清理调用因MCP传输启动失败而未执行。运行脚本已改为记录执行前已打开文档，并仅关闭本次新打开的目标源；该新增清理分支已通过语法检查，尚需下一次真实CAD事务现场验证。当前窗口应关闭且不要保存。

## 2026-10-11 接续点：既有实例关系编辑已完成真实CAD分流闭环

- 已把`ADD_RELATION`和`VERIFY_RELATION`下沉为两种不同的通用CAD执行策略；两者都复用同一稳定面端点和目录摘要，但只有前者允许改写配合。
- A500/A700 50 mm驱动新增实验因`swAddMateError_OverDefinedAssembly`失败；失败工件未发布，源十对象检查点SHA-256保持不变。该结果说明验证性距离不能自动转为额外驱动配合。
- A500/A700 50 mm只读验证实验成功：0条驱动配合、0条补丁、0项配合变更；重开测量为`0.0499999999999968 m`，误差约`3.2e-15 m`，结果另存并发布。
- 成功证据：`demo/global_assembly_contexts/generic_packet_runs/project02-a500-a700-spacing-verify-real-v2-20261011/`；失败证据：`demo/global_assembly_contexts/generic_packet_runs/project02-a500-a700-add-relation-real-20261011/`。
- 全量后端回归：`797 passed, 3 subtests passed`；碰撞/B-rep仍为`not_evaluated`。

下一步唯一顺序：把`VERIFY_RELATION`接入持久清单作业的暂停、恢复和失败回滚回归；再选择第二个项目族的一条低风险只读距离/角度关系，验证相同执行器不依赖Project02编号。随后再扩充自然语言多轮关系命令，暂不把碰撞精检拉回主线。

功能修改意义：通用系统已经能对“已安装实例之间的关系”做安全选择——需要改变约束时真实求解，需要确认现状时只读测量；这消除了把工艺验证关系重复写入CAD导致过约束的主要风险。

### 关系事务持久编排补充（2026-10-11）

- `VERIFY_RELATION`包现显式带有`relationModuleTokens=[A500,A700]`，可建立从第10包开始的持久后缀任务。
- 编排器允许在清单整体含早期阻塞时选择全部就绪的后缀，但完整摘要和所有包摘要仍必须有效，选中包自身有阻塞则拒绝。
- 模拟闭环已覆盖外部packet-009种子、packet-010故障回滚、恢复仅重试packet-010和最终提交；全量后端为`799 passed, 3 subtests passed`。
- 下一步先实现“历史检查点签认→通用清单种子证据”转换器，再运行一次真实持久`VERIFY_RELATION`；随后再迁移第二项目族。

## 2026-10-11 接续点：真实持久VERIFY_RELATION已闭环

- 新增`global-cad-manifest-external-seed/v1`，将历史签认、检查点哈希、迁移上下文、实例集合、清单/计划摘要和packet-009摘要绑定为不可篡改证据。
- 转换证据：`demo/global_assembly_contexts/manifest-seeds/project02-spacing-validation-v2-packet009.external-seed.json`。
- 正式作业：`project02-job-da6d6a5ec4ed`，状态`succeeded/assembled`；只执行packet-010，没有重跑前九包。
- 新检查点：`demo/global_assembly_contexts/manifest_jobs/project02-job-da6d6a5ec4ed/packet-runs/packet-010-attempt-01/project02-full-static-graph-spacing-validation-v2-packet-010.SLDASM`。
- 真实结果：实测`0.0499999999999968 m`，0项配合修改，源检查点不变；任务约`109.955 s`。
- 全量后端：`802 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步唯一顺序：为Project03从现有AB00/AI00稳定端点派生一条独立`validate_only`距离模板；建立已有实例关系上下文和只读关系包；选择已保存重开的Project03累计检查点作为受控种子；运行同一持久验证器。不得把复合安装模板中的单个距离步骤直接当成独立关系。
# 2026-10-11：已完成 Project03 首个跨项目真实关系验证

- 已将 `AA00—AB00 距离5=40 mm` 从复合安装模板安全派生为独立 `validate_only` 模板。
- 已将 Project03 10对象历史全装检查点以“上下文实例精确子集”方式签认为事务种子，额外8对象显式留痕。
- 持久任务 `project03-job-ac77c693ae78` 已成功；重开实测 `0.04000000000000188 m`，误差 `1.880440247958859E-15 m`，容差 `1E-06 m`。
- 零配合创建/修改/删除；源装配体未变化；碰撞/B-rep未执行。
- 全量后端回归：`805 passed, 3 subtests passed`。
- 下一步：把模板派生接入正式目录构建，再选择第三项目族的只读关系；驱动型跨项目关系必须另做过约束预检。

# 2026-10-11：已完成 Project01 第三个项目族验证

- 已建立版本化关系派生注册表和可重复候选目录构建脚本，Project03距离与Project01平行关系均由注册表生成。
- Project01 GN00—SS00既有驱动平行配合被登记为独立只读观察模板；源配合和源目录未修改。
- 持久任务`project01-job-8a21b33ff155`成功：两个真实面恢复成功，重开实测夹角0、误差0、容差`1e-6 rad`。
- 配合请求/创建均为0；源装配体SHA-256不变；结果另存并重开通过。
- 输出：`demo/global_assembly_contexts/manifest_jobs/project01-job-8a21b33ff155/packet-runs/packet-003-attempt-01/project01-gn00-ss00-parallel-validation-v1-packet-003.SLDASM`。
- 全量后端回归`807 passed, 3 subtests passed`；桥接层非可视化集成回归`363 passed`。
- 下一步：统一发布关系目录版本；扩充同轴/重合/角度只读关系；驱动型关系另建自由度与过约束预检；优化大装配体重开耗时。

本轮功能意义：同一持久关系事务链已在Project02、Project03、Project01三个项目族上获得真实CAD证据，并从距离测量扩展到方向测量。

# 2026-10-11：重合验证和关系目录发布已完成

- 新增Project01 GN00—JJ00平面重合只读验证，必须同时满足距离与夹角容差。
- 持久作业`project01-job-14a100663758`成功：距离误差约`2.60e-16 m`、角度误差0、0项配合修改、源文件不变、保存重开通过。
- 已生成发布目录`demo/global_assembly_catalog/releases/relation-v4-20261011/global_module_catalog.json`及`release-manifest.json`。
- 发布清单绑定3条派生模板和3份真实CAD验证证据，目录摘要为`c54fb4ac283e52fc9f097460240adc07c3fec68140775de07daff0fd0265bba2`。
- 回归：Python `809 passed, 3 subtests passed`；C#非可视化集成`365 passed`。
- 下一步：让默认自然语言关系入口显式选择发布目录；再评估同轴端点的轴线恢复能力，最后才进入驱动型关系的自由度与过约束预检。

本轮功能意义：已验证能力不再散落在preview和单次实验中，而是形成了可由后续编译器稳定引用的版本化关系目录。

# 2026-10-11：发布目录已接入默认关系入口，同轴测量器已就绪

- 发布清单新增仓库相对目录路径、发布文件SHA-256和覆盖完整字段的发布摘要；复制到其他工作区后可按相对路径校验。
- 新增`GET /api/demo/global-relation-release`；默认能力查询和自然语言关系预览使用`relation-v4-20261011`。
- 自然语言预览已能把重合、平行、40 mm距离映射到各自唯一的已发布模板；同轴尚未发布，明确返回阻塞。
- API关系编辑请求已支持`operation=verify`；自然语言预览新增`executionMode=verify|drive`，当前驱动请求按发布范围失败关闭。
- SolidWorks验证器新增圆柱轴线恢复、径向轴距和无向轴角测量；33项定向测试通过。
- 全量回归：Python `811 passed, 3 subtests passed`；C#非可视化`367 passed`。

下一步唯一主线：从Project01 GN00—JJ00已登记的`locating_hole`端点派生独立同轴观察模板，建立只读上下文与事务包，在已签认装配体上完成一次真实CAD保存重开验证；通过后再发布下一版关系目录。驱动型关系继续保持预检阻断，直到自由度闭合与过约束策略取得独立证据。

本轮功能意义：运行时已不会误用preview模板；同轴从“缺少算法”推进到“只缺端点模板登记和真实CAD证据”。

# 2026-10-11：Project01 同轴真实 CAD 闭环与 v5 发布完成

- 已从版本化派生注册表生成 GN00—JJ00 独立同轴观察模板。
- 持久任务 `project01-job-6028bd3d279b` 成功：两端圆柱面均以 `BodyFaceIndex+RuntimeCylinderSurface` 恢复，径向轴距约 `8.76e-17 m`，轴角 `0 rad`。
- 请求/创建配合均为0；源装配体SHA-256不变；另存、关闭、重开复核通过。
- 结果装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-6028bd3d279b/packet-runs/packet-003-attempt-01/project01-gn00-jj00-concentric-validation-v1-packet-003.SLDASM`。
- 已发布 `relation-v5-20261011`，绑定4条派生模板、4份真实CAD证据，目录摘要 `387575b777e857b5cbd6694d625258c866d0b9fcb9fe84e6f34902386d7afa60`。
- 默认自然语言关系入口已切换到v5；同轴验证可选，同轴驱动仍阻断。
- CAD约 `137.99 s`；碰撞/B-rep未执行且不属于本轮验收。
- 最终回归：Python `812 passed, 3 subtests passed`；C#非可视化 `367 passed`。

下一步唯一主线：建立驱动型关系的自由度与过约束预检，先在不启动CAD的情况下区分“可以新增的驱动约束”“只允许验证的冗余关系”和“必然过约束的请求”，然后选一个小装配关系做真实CAD驱动闭环。

本轮功能意义：同轴已从算法准备状态进入正式、可审计的Demo发布能力；后续风险重心从“能否找面并测量”转向“能否安全改变装配自由度”。

# 2026-10-11：驱动关系启动前预检第一阶段完成

- 新增自然语言驱动关系预检接口，将已发布语义证据与有效配合图的六自由度分析联合起来。
- 输出三类明确结果：`ready_for_driving_cad_trial`、`verification_only`、`blocked`。
- 直接配合编辑器启用严格冗余门禁；新增/更新关系不贡献独立约束时，在CAD前返回`REDUNDANT_MUTATING_RELATION`。
- 用真实Project05 A000—D000配合图完成闭环：约束秩6、剩余自由度0、机械层为驱动候选；因v5重合模板仅只读发布，整体结果仍为`verification_only`。
- 冗余配合样例被降级为只读验证；缺少方向几何的槽口样例被阻断。
- 证据：`demo/global_assembly_contexts/relation-driving-preflight-v1/report.json`。
- 历史Project05真实CAD驱动闭环经新门禁重审13/13通过，形成`driving-pilot-audit-v1.json`；它只证明重合+距离+宽度三配合束，不证明单关系可驱动。
- 定向回归：`18 passed`；最终全量后端回归：`821 passed, 3 subtests passed`。本阶段未启动SolidWorks，也未执行碰撞/B-rep。

下一步唯一主线：把Project05 A000—D000三配合束登记成限定作用域驱动模板，但先保持preview状态；随后用当前严格门禁和当前桥接版本重新执行一次真实CAD副本事务。只有新作业继续满足完全约束、无冗余、保存重开和源文件不变，才考虑发布首个允许驱动的目录版本。

本轮功能意义：驱动关系已从“统一交给CAD碰运气”推进为“语义权限+自由度证据双门禁”，并已有真实历史证据候选支撑下一阶段。

## 2026-10-11：驱动候选登记后的续作顺序

已完成：Project05 A000—D000三配合限定候选、8端点复用、宽度高级选项补齐、逐模板驱动授权机制、preview与正式目录隔离；全量回归`824 passed, 3 subtests passed`。

当前阻塞：冷会话直接执行时深层叶零件未解析，3条配合实际创建数为0；全量同会话导出在约4分钟内尚未生成首阶段图文件。原型未修改，候选未发布。

下一步唯一顺序：

1. 从已成功保存重开的Project05结果或原型解析会话建立A000—D000专用、版本化小上下文；
2. 绑定源装配体、叶零件集合、端点目录和有效图SHA-256，缓存失配时才重建；
3. 用当前严格预检在该上下文执行完整三配合束；
4. 验证3/3创建、目标完全约束、保存关闭重开、参数一致、源文件不变；
5. 通过后生成新的真实CAD证据，再发布只授权该模板ID的首个驱动目录版本；
6. 未通过时继续保持`candidate_only_not_released`，不得为了演示放宽门禁。

碰撞/B-rep仍是独立、可选的后验工程验证，不属于本阶段驱动配合语义验收。

## 2026-10-11：限定驱动闭环完成后的下一步

上述小上下文、3/3配合重建和专用v6发布均已完成。默认只读发布未改变。最终回归为`827 passed, 3 subtests passed`。

后续建议顺序：

1. 把`releaseManifestPath`显式选择接入更上层的装配命令/任务清单，使“安装D000”可从预览进入持久事务，而不只停在关系预检接口；
2. 为小上下文建立版本化缓存索引，源副本、组件路径、端点目录或有效图任一哈希变化时自动失效；
3. 对同一A000—D000模板做一次非原型初始位姿试验，证明最终位姿由三配合求解而不是继承缓存位姿；
4. 再选择第二个项目族的闭合安装束重复上述流程，验证逐模板驱动发布机制不是Project05硬编码；
5. 前端、碰撞/B-rep和生产放行仍不是当前主线验收条件。

## 2026-10-11：v7独立插入证据完成后的续作

已完成：

- 发布摘要已贯穿自然语言上下文、命令预览、DAG、执行清单和CAD事务包；绑定上下文不能再偷换目录。
- 非原型初始位姿门禁发现并隔离了原位重建假阳性。
- Project05 D000已通过“删除旧实例—独立文件重新插入—三配合定位—保存重开”的真实CAD闭环。
- v6驱动授权在新规则下失效；v7只授权已取得独立插入证据的A000—D000模板。
- 可复现脚本：`scripts/build_project05_v7_natural_language_transaction.py`。

下一步唯一主线：

1. 让通用CAD包执行器直接消费v7生成的`cad-transaction-manifest.json`，而不是由专用实验脚本旁路执行；
2. 执行器启动前再次校验发布摘要、目标CAD源文件摘要及面端点目录摘要；
3. 将`context_incremental_insert`的成功证据自动回写到持久任务检查点，支持暂停、恢复和失败回滚；
4. 用第二个项目族的一组闭合安装束重复“独立插入＋非原型位姿”实验，验证不是Project05专用逻辑；
5. 暂不增加碰撞/B-rep和前端工作，保持其为可选后验能力。

当前无人工输入阻塞。技术阻塞仅剩：旧`legacy-project-adapter-manifest`仍要求`base*_graph.json`而显示blocked；通用CAD事务清单已经ready，应以通用执行器作为主线，不再修补旧适配器。

## 2026-10-11：v7持久执行已完成，主线后移

已完成：通用执行器直接消费v7自然语言CAD事务包；发布摘要和逐模板授权在任务创建、步骤启动、执行计划三处复核；A000包装、D000独立插入、3/3配合、保存重开、检查点提交均通过；故障注入后恢复闭环通过。证据见`demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/durable-executor-closure.json`。

下一步顺序：

1. 从Project01或Project03选择一组已有完整端点、有效配合图和零剩余自由度的闭合安装束，生成候选驱动模板；
2. 对其执行独立子装配体、非原型初始位姿CAD试验，通过后发布第二个逐模板驱动版本；
3. 用同一自然语言上下文、事务DAG和持久执行器完成跨项目真实闭环，证明执行机制不含Project05硬编码；
4. 为首包单基座包装建立按源文件SHA-256、基座变换和适配器版本绑定的只读缓存，减少当前145—228秒的重复包装成本；
5. 继续不把前端和碰撞/B-rep纳入本阶段验收。

无人工输入阻塞。风险在于第二项目族可能缺少能独立闭合6自由度的完整配合束；若不足，应失败关闭并记录缺失关系，不得用原型顶层位姿或隐式固定补齐。

## 2026-10-11：第二项目族闭环完成后的主线

已完成：Project01 SS00首包与GN00第二包均通过非case-anchor独立插入；GN00同时依赖JJ00主定位和SS00防转关系；v9逐模板发布、自然语言编辑、两包持久执行和保存重开闭环均通过。证据报告为`demo/global_assembly_contexts/project01-jj00-ss00-gn00-v8-driving-v1/durable-executor-closure.json`。

下一步顺序：

1. 把首包基座包装缓存做成通用、只读、按源SHA-256/基座变换/适配器版本自动失效的缓存，避免不同项目反复包装相同环境；
2. 把“组合安装束”作为一等目录对象，明确主定位模板、补自由度模板、适用实例图和整体剩余自由度，避免再依赖脚本知道模板组合；
3. 选择Project03的一组端口完整关系，优先验证跨项目目录选择与组合图编译；如缺少闭合关系则输出可解释阻塞，不补原型顶层位姿；
4. 增加命令级审计摘要，使用户能直接看到每条自然语言命令选择的模组、端口、模板、自由度贡献和CAD包归属；
5. 前端和碰撞/B-rep继续不作为当前主线验收项。

当前无人工输入阻塞。Project01上下文目录仍沿用早期`v8-driving-v1`命名，但实际绑定和执行的是v9不可变发布；后续新上下文应统一改用v9命名，不影响已提交检查点的审计有效性。

## 2026-10-11：组合目录和基座缓存完成后的续作

已完成：

- Project01主定位＋防转已升级为全局目录的一等模板组合，事务编译能用目录证据说明组合后剩余自由度为0；
- Project02 A600与Project05 A000的既有合格包装结果已导入内容寻址缓存；
- Project05真实首包复跑命中缓存，只执行约57.69秒的D000插入，3/3配合及保存重开通过；
- 全量后端回归为`842 passed, 3 subtests passed`。

下一步建议顺序：

1. 将一等模板组合随下一版不可变关系目录正式发布，并在发布清单中显式列出获准组合ID；
2. 选择Project03关系完整的一组模组，先用同一组合对象编译；若仍有剩余自由度则输出缺失端口/关系，不引入原型顶层位姿；
3. 为自然语言命令生成命令级审计摘要，直接展示所选模组、端口、模板、模板组合、自由度贡献和CAD包归属；
4. 在持久任务汇总中增加“缓存节省时间”统计，区分计划、缓存查找、CAD配合执行和保存重开的实际耗时；
5. 前端和碰撞/B-rep继续保持非当前主线，除非用户重新提升其优先级。

当前无人工输入阻塞。缓存只覆盖根模组包装，不能替代各包真实配合执行；Project03若缺少闭合组合，应失败关闭而不是复制原型位姿。

## 2026-10-11：v10组合发布与Project03审计后的续作

已完成：

- Project01模板组合已进入不可变v10发布，并贯穿发布绑定、DAG、CAD清单和逐包执行复核；
- 组合部分成员负例已在CAD前阻断；旧发布绑定保持兼容；
- Project03 11条安装模板已分类，AE00为无项目位姿补齐的原子闭合正例，AG00诊断模板和锚点模板形成可解释阻塞；
- 命令级审计摘要已覆盖Project01 v10全部4条命令；
- 持久步骤证据已预留缓存节省时间与CAD耗时分项；
- 全量后端回归为`846 passed, 3 subtests passed`。

下一步建议顺序：

1. 从Project03的6条原子闭合候选中选择已有最完整真实独立插入证据的一条，建立逐模板驱动候选和不可变发布；
2. 用同一持久执行器完成Project03非原型初始位姿CAD复验；若只有原型锚点证据则保持候选，不发布；
3. 把命令级审计摘要接入通用任务结果，而非仅由Project01构建脚本生成；
4. 扩展任务汇总器，将每包缓存命中、节省包装时间、CAD配合耗时和保存重开耗时形成统一报告；
5. 暂不提升前端和碰撞/B-rep优先级。

当前无需人工输入。Project03下一步的主要风险不是代码复用，而是候选模板是否已有足够的非原型初始位姿真实CAD证据。

## 2026-10-11：Project03 v11真实闭环后的续作

已完成：

- 修复锚点模板分类遗漏，Project03原子闭合候选由6条校正为5条；
- 建立真实CAD证据分级，五条历史成功记录均被标为需补checkpoint，而非直接发布；
- AE00完成非原型初始位姿checkpoint复验并发布v11；
- 两条自然语言命令编译为1个受控CAD包，并由通用执行器真实执行通过；
- 输出装配体、命令审计、CAD结果和闭环报告均已保存；
- 全量后端回归为`850 passed, 3 subtests passed`。

下一步建议顺序：

1. 将`global-command-audit/v1`从项目构建脚本下沉到通用持久作业结果，让每个任务自动产生命令—端口—模板—CAD包映射；
2. 将每包的CAD阶段耗时、保存重开耗时、缓存命中和节省时间汇总为统一任务时间报告；
3. 按机械链价值而非批量刷新，优先为Project03 AD00补一次checkpoint，再验证AA00→AE00→AD00两包累计事务；
4. 对AI00、AH00、AJ00仅在其进入自然语言目标链时刷新，避免重复消耗SolidWorks时间；
5. AG00、AB00、AC00继续保持语义阻断，直至补足非锚点关系；前端和碰撞/B-rep仍非当前主线。

当前无人工输入阻塞。需要注意：AE00实体执行复用了已验证的AA00+AF00复合基座上下文，这属于明确登记的基座环境，不是用AE00原型顶层位姿补齐目标自由度。

## 2026-10-11：Project03 v12两包累计闭环后的续作

已完成：

- AD00发布级checkpoint复验通过；
- v12不可变发布同时授权AE00和AD00；
- 三条自然语言命令生成2个累计CAD包；
- 持久作业两包一次成功，第二包严格消费第一包检查点；
- 最终实体及闭环报告已保存，总执行约161.36秒；
- 全量后端回归保持`850 passed, 3 subtests passed`。

下一步建议顺序：

1. 将命令审计生成逻辑接入通用持久任务创建/完成阶段，使Project01、03、05任务无需项目脚本也自动带审计摘要；
2. 将现有每包时间字段聚合为统一任务性能报告，区分编译、缓存、CAD、保存和重开；
3. 选择AI00作为下一条机械链候选，但仅在前两项完成后执行一次checkpoint刷新和三包累计验证；
4. AH00、AJ00按需求进入时再刷新，避免为暂未使用的模板重复启动SolidWorks；
5. AG00、AB00、AC00继续阻断，前端和碰撞/B-rep继续延后。

当前无人工输入阻塞。主线已从“证明第三项目族可运行”转入“把审计和性能证据通用化，再扩展第三包”。

## 2026-10-11：Project03 v13三包闭环后的续作

已完成：

- 命令审计已下沉到通用任务计划和任务目录；新任务自动生成`command-audit.json`；
- 统一计时报告已接入通用任务创建与执行，能够统计CAD阶段、保存关闭、重开、缓存和失败恢复耗时；
- AI00完成发布级checkpoint刷新，Project03发布候选增至3条；
- v13不可变发布授权AE00、AD00、AI00；四条自然语言命令编译为3个累计CAD包；
- 真实任务完成失败关闭、从第二包检查点恢复以及第三包成功提交；最终实体、审计、时间报告和闭环报告均已保存；
- AI00的3条驱动配合与2条只读距离关系已在通用执行层正确分流。
- 普通目录任务与发布绑定任务均能自动解析审计所需的目录、上下文和事务DAG；三步/五步非固定自然语言顺序回归通过；
- 任务计划与单包计划已拆分驱动配合数、只读验证数和总关系数；AI00稳定显示为`3+2=5`；
- 全量后端回归为`854 passed, 3 subtests passed`。

下一步建议顺序：

1. 把通用命令审计和计时产物加入API状态的稳定回归，并补一次Project01/Project05兼容性抽查；
2. 根据自然语言目标链价值选择AH00或AJ00中的一个刷新checkpoint，验证第四包累计链；不批量刷新暂未使用模板；
3. AG00、AB00、AC00继续保持语义阻断，直至取得无锚点闭合关系；
4. 前端、碰撞和B-rep继续保持非当前主线。

当前无人工输入阻塞。v13结果属于`assembled / collision not evaluated`，不能表述为无干涉或生产放行。

## 2026-10-11：Project03 v14四包闭环后的续作

已完成：

- AH00发布级checkpoint刷新通过，Project03发布候选增至4条；
- checkpoint工具新增目标上下文投影，不再要求累计实体解析与当前目标无关的旧原型模组；
- v14不可变发布授权AE00、AD00、AI00、AH00；
- 五条自然语言命令生成4个累计CAD包，通用持久任务四包一次成功；
- 最终实体、5/5命令审计、统一计时和13项闭环检查均已保存；
- 全量后端回归为`855 passed, 3 subtests passed`。

下一步建议顺序：

1. 用同一通用事务构建器选择AJ00刷新最后一条当前可闭合候选，验证第五包累计链；
2. 在执行AJ00前先确认其有效图投影后只依赖AA00，继续拒绝无关旧原型模组；
3. 完成后针对Project01或Project05做一次“非固定token顺序”兼容性抽查，验证通用构建与计数字段没有Project03特化；
4. AG00、AB00、AC00仍保持语义阻断，不使用原型锚点补齐；
5. 前端、碰撞和B-rep继续保持非当前主线。

当前无人工输入阻塞。v14结果属于`assembled / collision not evaluated`，不能表述为无干涉或生产放行。

## 2026-10-11：Project03 v15五包闭环后的续作

已完成：

- AJ00发布级checkpoint刷新通过，Project03当前5条原子闭合候选已全部具备当前证据；
- v15不可变发布授权AE00、AD00、AI00、AH00、AJ00；
- 六条自然语言命令生成5个累计CAD包，通用持久任务一次成功；
- 最终实体、6/6命令审计、统一计时和14项闭环检查均已保存；
- 五个目标均完全约束、求解干净，源文件未改写，输出均保存关闭；
- 全量后端回归为`855 passed, 3 subtests passed`。

下一步建议顺序：

1. 对Project01或Project05执行一次非固定token顺序兼容性抽查，确认通用构建器、发布授权和计数字段没有Project03特化；
2. 将Project03候选发布脚本中重复的链长专用逻辑收敛为通用“证据集合→不可变发布”构建器，避免后续每增加一个模组就新增脚本；
3. AG00、AB00、AC00继续保持语义阻断，只有取得无锚点闭合关系后才允许加入通用链；
4. 前端、碰撞和B-rep继续保持非当前主线。

当前无人工输入阻塞。v15结果属于`assembled / collision not evaluated`，不能表述为无干涉或生产放行。

## 2026-10-11：发布绑定混合命令兼容性完成后的续作

已完成：

- 通用自然语言清单入口可显式绑定不可变关系发布；
- 同一有序命令序列可原子混排“添加模组”和“给两个已有模组增加关系”；
- 对称安装端口的等价A/B候选可安全归一，非安装关系不放宽选择门禁；
- Project01四条混合命令已生成2个累计包和排队任务，发布权限与命令审计均完整；
- 全量后端回归为`856 passed, 3 subtests passed`。

下一步建议顺序：

1. 将Project03链长专用的候选发布脚本收敛为参数化证据发布器，输入模板及checkpoint清单即可生成不可变发布；
2. 用Project05执行一次不同自然语言顺序的发布绑定编译，验证单模板项目族不会被Project01的组合关系逻辑影响；
3. 再决定是否启动Project01两包真实CAD作业；在此之前任务保持`queued / CAD not started`，避免把静态兼容性抽查误表述为实体闭环；
4. AG00、AB00、AC00继续语义阻断；前端、碰撞和B-rep继续保持非当前主线。

当前无人工输入阻塞。

## 2026-10-12：A600/AH00备用槽位发布后的续作

已完成：

- Project02 A600操作面侧50 mm双孔校准槽位已完成定向采集、3/3端点恢复和真实CAD验证；
- Project03 AH00从非原型初始位姿以`重合＋同心＋同心`完成独立插入和完全约束；
- 结果保存、关闭、重开及配合参数复核通过，源A600/AH00文件摘要未变；
- 跨项目端口包、端口级项目归属和全局模板已经形成；
- v41从Project02 v36发布谱系增量合并，保留原九模组授权并新增A600/AH00模板；
- 全量后端回归`985 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 把“明确目标基座/槽位”的自然语言选择接到新模板，验证命令能够消除AH00原生AA00槽位与A600备用槽位之间的配置歧义；
2. 用v41执行一次发布绑定的自然语言短链，不再手工传入有效图，验证目录选择→事务编译→真实CAD的最终调用路径；
3. 将同一套定向采集与发布流程应用到一个不同接口族，优先选择价值高且局部叶零件明确的扫描或CCD槽位，证明流程不只适用于50 mm双孔校准接口；
4. 继续按全目录缺口优先级补端口，不进行所有模组两两穷举；机械硬不兼容保持失败关闭；
5. 前端、鼠标点选和碰撞/B-rep仍按用户要求暂缓，不阻塞自然语言模组级组合主线。

当前没有人工输入阻塞。活动Project02发布应使用v41；v40仅保留为发布基线选错的审计样例，不应绑定后续任务。

## 2026-10-11：A700显式标定回退进入通用持久编排器后的续作

已完成：

- 自然语言编译器新增显式`drivingStrategySelections`；A700旧无锚点模板仍保持撤销，只有模板ID、策略ID和`confirmed=true`同时匹配时才允许切换回退。
- 安全目录为回退图与验证证据绑定SHA-256，并明确`project02-only / portable=false / automaticSelectionAllowed=false`。
- 通用CAD事务新增`calibrated_static_snapshot_insert`策略；执行器验证1个顶层case锚点、2个内部叶姿态锚点、约束状态与保存关闭重开，不把来源6条配合误报为本轮创建配合。
- 持久编排器在检查点提交前增加标定回退专用硬复核，证据写入`calibratedFallbackVerification`。
- 5句自然语言命令在`0.186045 s`内生成4包持久任务`project02-job-b261643c012a`，随后A800→A180→A500→A700完整执行一次成功，总耗时`163.834979 s`。
- 逐包耗时：A800 `40.93 s`、A180 `39.54 s`、A500 `40.25 s`、A700 `42.55 s`；均只尝试一次并提交检查点。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project02-job-b261643c012a/packet-runs/packet-004-attempt-01/project02-explicit-a700-fallback-v14-packet-004.SLDASM`。
- 最终只读复测耗时`5.2515 s`，距离8为`0.0499999999999968 m`，在`0.0001 m`公差内通过，且源装配体未改、无配合修改。
- 全量后端回归`938 passed, 3 subtests passed`，耗时`85.27 s`。
- 实体干涉/B-rep未执行，状态保持`not_evaluated`。

下一步建议顺序：

1. 为回退步骤增加“向后续只读验证包提供外部位姿等价证据”的通用前驱证据机制，使A500—A700的50毫米验证可以作为同一持久任务的下一包自动执行；
2. 从A710/A730静止安装成员建立A700外部位姿见证；若顶层柔性包装仍无法稳定恢复，则把A710/A720/A730建模为一个逻辑复合模组；
3. 新的可迁移A700模板必须从确定性非源初始位姿执行，无case/叶锚点，并通过外部位姿等价、保存重开和50毫米只读测量后使用新模板ID发布；
4. 可迁移模板完成后，重新运行Project02九附加模组长链，并将相同的柔性外部位姿见证机制迁移到Project03或Project05；
5. 前端、鼠标点选与碰撞/B-rep仍维持待办，不阻塞当前后端语义装配主线。

当前无人工输入阻塞。需要特别保持边界：本轮恢复了Project02 Demo连续装配能力，但尚未解决A700跨项目、去原型的真正通用端口。

## 2026-10-11：Project02四端口发布后的主线续作

已完成：

- A500严格无锚点checkpoint与A700柔性外部安装checkpoint均已通过；
- A800、A180、A500、A700统一进入v32不可变发布；
- 自然语言四步链已生成4包真实累计实体并完成逐包保存关闭重开；
- 最终实体与闭环报告均已固化，碰撞/B-rep继续为可选后验项。

下一步按以下顺序推进：

1. 审计A300排胶杯真实安装关系，区分其对A600的安装驱动和对A700/A500的工艺间距；
2. 若A300外部自由度可由现有真实配合封闭，则执行非原型初始位姿checkpoint并加入下一不可变发布；若不能，输出明确剩余自由度与所缺机械基准；
3. A300通过后扩展为五包自然语言累计链，再评估A200 CCD和A100龙门端口；
4. 每个新增模组坚持“独立checkpoint→候选目录→不可变发布→自然语言累计实体→闭环报告”的证据顺序；
5. 实体干涉/B-rep暂不作为主线阻塞条件，只保留`collisionStatus=not_evaluated`。

当前无需用户补充信息；优先复用原型中已导出的配合、面目录和组件状态，无法封闭时再记录具体缺口。

## 2026-10-11：Project02六端口发布后的主线续作

当前完成：A800、A180、A500、A700、A300、A200均已取得独立无锚点checkpoint，进入v34不可变发布，并完成六包自然语言累计实体闭环。

后续顺序：

1. 审计A100龙门的顶层外部安装束，生成一份只删除“整模组定位锚点”、不篡改内部机构状态的执行图；
2. 对A100的内部叶姿态锚点分类：外部安装无关的静态展示状态、必须保留的机构配置、以及可由内部配合自行求解的冗余记录；
3. 先验证A100单独相对A600的非原型初始位姿checkpoint，再把它加入六包最终实体形成七包链；
4. A100通过后再处理两套T401。T401安装上下文是A200而非A600，应验证“新增模组连接到已插入模组”的非星形累计关系；
5. 碰撞/B-rep仍不进入当前主线门禁。

当前没有需要用户确认的问题。A100的难点是内部机构状态分层，不是缺少顶层安装配合；应避免为追求快速发布而删除全部内部状态信息。

## 2026-10-11：Project02传输与扫描端口发布后的续作

已完成：

- A800、A180稳定面端点和高级配合参数已进入候选包；
- 两个模组均完成严格无锚点CAD checkpoint；
- v30不可变发布授权A800/A180两条驱动模板；
- “A600基础环境→A800→A180”自然语言真实累计链成功，最终实体、逐包证据、时间统计和闭环报告齐全；
- v29路径错误在CAD前失败关闭，已由v30修复，未覆盖旧发布；
- 碰撞/B-rep未执行，符合当前验收边界。

下一步建议顺序：

1. 运行全量后端回归，固定Project02新增端口不破坏Project01/03/05既有链；
2. 以同样流程优先审计A700或A500：端点目录→配合束→静态自由度→非锚点checkpoint→候选→新发布；
3. 至少再获得两个Project02功能模组的发布授权后，执行一条非固定顺序的三至四模组自然语言累计链；
4. 对A180增加只读光轴—条码目标区验证，但不把光学验证误当成机械定位配合；
5. 继续保持前端、碰撞和B-rep为非当前主线，不阻塞语义端口覆盖率和自由组合能力扩展。

当前无人工输入阻塞。下一目标优先选择配合端点证据较完整、能最快进入真实累计链的Project02功能模组。

## 2026-10-11：N000完成后的主线状态与续作

已完成：

- N000原型三关系已完成自由度审计，确认Free槽口保留唯一`tx`；“平面槽壁＋圆柱定位销”已纳入自由度分析。
- 以原型测得的465 mm侧平面距离显式封闭剩余自由度，参数已标为Demo估计值而非厂商基准。
- N000非原型初始位姿真实checkpoint通过，4/4配合、完全约束、求解干净、无case/叶位姿锚点，并通过保存关闭重开。
- Project05 v26不可变发布已授权D000/F000/M000/G000/P000/N000六个模板。
- `N000→P000`与`P000→N000`两条真实累计CAD链通过，同一发布下顺序可交换。
- 全量后端回归为`889 passed, 3 subtests passed`；碰撞/B-rep未执行且不属于当前主线验收。

下一步建议顺序：

1. 对Project05 K000执行与P000/N000相同的面目录、原型配合、刚体秩和剩余自由度审计；不得先以源Transform补位。
2. 若K000具有Free槽、长孔或平行导向，优先寻找能够封闭剩余自由度的真实孔/销/侧平面；没有厂商尺寸时允许建立明确标记的原型估计参数。
3. K000通过非原型初始位姿checkpoint后，生成独立候选包并发布v27，不覆盖v26。
4. 再审计Project05 B000；只有端口语义和自由度闭合后才进入发布。
5. 六个已授权附加模组可补跑一条代表性的六模组长链，验证长链累计性；无需穷举全部排列。
6. 前端点选、碰撞/B-rep和生产放行继续不作为当前自然语言模组级自由组合主线的前置条件。

当前无人工输入阻塞。下一项工作是K000端口审计。

## 2026-10-11：Project05 8/8端口审计完成后的主线状态

已完成：

- K000三配合刚体秩6/6，非原型初始位姿checkpoint、v27发布和K000/N000正反顺序实体链全部通过。
- B000三配合刚体秩6/6，非原型初始位姿checkpoint通过；外部安装完全约束且B000柔性组件语义保持一致。
- v28不可变发布授权Project05全部8个待装对象：D000、K000、F000、M000、G000、N000、P000、B000。
- B000/K000正反顺序真实累计CAD链通过；Project05当前范围的端口审计进度由6/8提升为8/8。
- 裸`A000`跨项目歧义已形成失败关闭实证，显式写“项目05 A000”后才能进入CAD。
- 全量后端回归为`895 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 不再继续逐个审计Project05模组；对v28执行一条代表性8模组自然语言长链，验证完整链累计保存重开、任务恢复和计时，不穷举8!排列。
2. 长链通过后，把同一审计流水线迁移至Project02，优先处理当前明确阻断的A800、A180，再复核A700、A300、A500、A100。
3. Project03已发布的5个模组保持回归基线；AG00、AB00、AC00仅在进入目标链时补足非锚点关系。
4. Project01继续保留SS00/GN00组合关系基线；是否扩展其他模组由自然语言目标链决定。
5. Project06仍为0/9可执行端口，待Project02迁移验证后再批量建立面目录和安装束。
6. 前端点选、碰撞/B-rep和生产放行仍不是当前自然语言模组级自由组合主线的前置条件。

当前无人工输入阻塞。下一项建议工作是Project05 v28代表性8模组长链；若优先追求跨项目覆盖，则可直接转入Project02 A800/A180审计。

## 2026-10-11：Project05四附加模组与柔性G000闭环后的续作

已完成：

- G000取得非原型初始位姿、无case/叶位姿锚点的真实checkpoint；外部安装位姿闭合，内部机构保持原声明柔性；
- 发布门禁已区分刚性完全约束与柔性约束状态接受，且仍要求配合求解、语义匹配、保存重开和源文件保护；
- v23不可变发布授权D000、F000、M000、G000四条独立安装模板；
- `D→F→M→G`与`G→M→F→D`两条真实CAD累计链共8包全部通过；
- 机器可读报告位于`demo/global_assembly_contexts/project05-release-permutation-v4/closure-report.json`；
- 全量后端回归为`874 passed, 3 subtests passed`，碰撞/B-rep未执行。

下一步建议顺序：

1. 处理P000：当前只有两条定位关系，先补第三关系或形成独立的剩余自由度证明；未闭合前不得强制发布；
2. 把Project05专用的checkpoint图构建、候选提升与排列汇总继续收敛成项目无关入口，使后续token不再新增专用脚本；
3. 用通用入口在另一个已具备端口证据的项目族做一次柔性/刚性混合回归，验证本轮语义不是G000特例；
4. 前端和鼠标点选仍作为待办；碰撞/B-rep继续是可选后验工程检查，不阻塞自然语言模组级组合主线。

当前无人工输入阻塞。v22为失败关闭的开发证据，不应绑定执行；后续Project05四模组任务应只使用v23或更高发布。

P000后续已进一步收敛：解析其现有有效图得到约束秩4/6，剩余自由度为`tx`与`tz`两个平移方向。下一轮不应盲目运行两配合checkpoint，而应先从原型面目录/安装结构中寻找两个独立位置基准，或一个二维定位接口；补齐后再做无锚点CAD验证。分析结果已写入`project05-addon-driving-evidence-audit.json`。

## 2026-10-11：Project05 P000无锚点闭合后的续作

已完成：

- 识别原型`槽口6`为Free槽口；纳入自由度分析后，原有三关系由秩4/6提升到5/6，只剩沿槽`tx`，不再误报同时缺`tx/tz`；
- 用真实面目录中的P000 body0/face1与A000 body0/face23建立X向距离，值为`345.122535 mm`，权限标记为原型估计而非厂商尺寸；
- 四关系有效图从确定性非原型初始位姿完成4/4真实CAD配合、完全约束和保存重开闭环；
- P000模板已纳入v25不可变发布；D000/F000/M000/G000/P000共5个附加模组获得独立驱动授权；
- `P000→F000`与`F000→P000`两种顺序均完成真实累计装配，闭环报告状态为`passed`；
- `P000→G000→M000→F000→D000`五附加模组长链一次完成，证明P000与柔性G000可在同一非固定顺序累计实体中共存；
- 通用排列汇总器已从“每包固定3条配合”改为核对“请求配合数等于实际创建数”，可覆盖P000四配合模板；
- 碰撞/B-rep仍未执行，符合当前主线边界。

下一步建议顺序：

1. 将P000候选构建逻辑并入项目无关的“有效图＋checkpoint→语义包→不可变发布”入口，减少最后一个Project05专用脚本；
2. 对N000执行同样的自由槽审计。若原型槽口仍为Free，先计算剩余自由度并补显式工程标量，禁止用原型Transform封闭；
3. 将`prototype_estimate`参数集中写入版本化参数权限表，未来拿到厂商尺寸时通过新版本替换，不能静默改写v25；
4. 为五模组长链增加一份模板/端点/配合数摘要报告，便于前端或交接方直接展示，不必读取庞大的持久作业JSON；
5. 前端与鼠标点选继续作为待办；实体干涉/B-rep仍是独立可选后验验证，不阻塞自然语言模组级组合主线。

当前没有人工输入阻塞。`v24`因P000有效图路径不可移植而不能作为执行基线，必须使用`v25`或更高版本。

## 2026-10-11：Project05双模组发布级顺序互换完成后的续作

已完成：

- Project01、Project05发布已迁移到通用JSON规格；组合授权由通用发布器统一校验；
- Project05 M000/F000/P000/G000完成证据审计，明确区分案例锚点依赖、checkpoint缺失和关系不闭合；
- F000完成非原型初始位姿、无case/叶位姿锚点的真实CAD checkpoint，并形成可移植的全局模板候选；
- v20不可变发布同时授权D000、F000两个独立闭合模板；
- `D000→F000`与`F000→D000`两条发布绑定自然语言链均完成真实CAD累计执行；四个包全部通过3/3配合、完全约束、保存关闭重开和源文件不变门禁；
- 机器可读闭环报告已生成：`demo/global_assembly_contexts/project05-release-permutation-v2/closure-report.json`；
- 新增定向回归9项通过，最终全量后端回归`867 passed, 3 subtests passed`；碰撞/B-rep未执行，符合当前验收边界。

下一步建议顺序：

1. 运行全量后端回归，确认本轮发布、审计、候选提升和顺序报告没有破坏既有Project01/02/03链；
2. 按价值选择M000或G000中的一个，复用F000流程刷新非锚点checkpoint，扩展到Project05三附加模组的非固定顺序链；
3. P000先补足第三定位语义或独立自由度证明，在此之前继续失败关闭；
4. 将“证据审计→非锚点图→候选提升→发布→排列闭环”的项目05脚本继续收敛为项目无关命令，避免为每个token复制入口；
5. 前端和碰撞/B-rep继续保持非当前主线，不阻塞自然语言模组级自由组合。

当前无人工输入阻塞。v19的F000图路径不可移植，已由v20取代；后续执行应只绑定v20或更高版本。

## 2026-10-11：Project05三附加模组真实顺序闭环后的续作

已完成：

- M000 CCD模组完成非原型初始位姿、无case/叶位姿锚点checkpoint；
- 候选构建器支持一次合并多个已验证目标，F000与M000形成同一可移植v3目录；
- v21不可变发布同时授权D000、F000、M000三个独立闭合模板；
- 两条四句自然语言命令分别编译为`D→F→M`与`M→F→D`三个累计包；
- 两条真实CAD长链和全部六个包均通过发布、配合、完全约束、保存关闭重开及源文件保护门禁；
- 参数化闭环报告生成器已验证三模组链，报告为`demo/global_assembly_contexts/project05-release-permutation-v3/closure-report.json`；
- 定向回归11项通过，最终全量后端回归`869 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 执行全量后端回归，固定本轮三模组能力基线；
2. 将G000按同一非锚点流程升级，目标是四个独立附加模组中的任意有序子集可编译、可累计执行；
3. 对“任意子集”增加抽样策略，而不是执行所有排列：单模组checkpoint、正反全链、一个中间子集即可覆盖端口独立性和累计连续性；
4. P000继续阻断，先补第三定位关系或可靠的剩余自由度证明；
5. 把Project05专名的非锚点图/候选提升工具逐步改成项目无关入口，为Project01/03/05共用；
6. 前端和实体干涉/B-rep继续不是当前主线验收项。

当前无人工输入阻塞。三模组最终实体是不同插入顺序形成的独立SLDASM，二进制摘要可以不同；验收依据为配合、约束、生命周期和发布证据一致。

## 2026-10-12：A600操作面侧跨项目自然语言安装闭环后的续作

已完成：

- A600备用校准槽位与Project03 AH00已有真实三基准CAD证据；
- v42补充`operator_side`语义并完成新的不可变发布；
- “先添加A600，再把AH00安装到A600操作面侧校准槽位”可由自然语言唯一编译；
- 发布绑定持久任务已真实执行，3/3配合、完全约束、保存关闭重开和会话恢复均通过；
- 修复槽位证据项目与目标模组项目混淆的问题；完整后端回归`991 passed, 3 subtests passed`。

下一步建议顺序：

1. 把“方位词→模板`sideSemantics`”覆盖报告推广到其他已登记槽位，先只补有明确机械证据的`operator_side/opposite_operator_side`，不得自动猜测；
2. 选择另一个活动项目中的已发布`provided`槽位，执行同样的自然语言直接安装闭环，验证该能力不是A600/AH00硬编码；
3. 在自然语言任务摘要中直接展示选中的槽位端口、方位语义、模板编号和证据项目，减少阅读大JSON的成本；
4. 继续按角色和复用价值扩展端口覆盖；机械不兼容关系保持失败关闭，不通过放宽语义制造“可组合”；
5. 前端鼠标点选、碰撞/B-rep、动态行程和生产参数继续作为独立后续工作，不阻塞模组级自然语言组合主线。

当前没有必须由用户补充的信息。最新Demo状态为`DEMO_ASSEMBLED_COLLISION_NOT_EVALUATED`，不能表述为无干涉或生产可用。

## 2026-10-11：通用证据发布与Project05兼容性完成后的续作

已完成：

- 链长专用证据脚本已被参数化发布器取代；Project03五模板通过一份JSON规格生成v16不可变发布；
- 正向发布、错误配合数量失败关闭均有自动测试；
- Project05 v7发布绑定的A000→D000自然语言编译通过，任务已排队但未启动CAD；
- Project05四个附加模组按两种不同顺序均完成语义图、DAG、4包清单、命令审计和任务创建；
- 兼容性报告明确区分“已发布可执行”和“仅语义编译”；
- 全量后端回归为`860 passed, 3 subtests passed`。

下一步建议顺序：

1. 将现有Project01/Project05驱动发布也迁移为相同规格文件，删除后续继续复制专用发布脚本的需要；
2. 为Project05 M000/F000/P000/G000逐一进行证据审计，只有取得非原型初始位姿checkpoint的模板才进入新发布；
3. 至少获得两个Project05附加模组的发布授权后，再做真正的“发布绑定多模组顺序互换”测试；当前只有D000，不能诚实宣称发布层已验证排列组合；
4. 可选择执行已排队的A000→D000实体任务做重复回归，但这不是继续扩展自然语言自由组合能力的前置条件；
5. 前端、碰撞和B-rep继续保持非当前主线。

当前无人工输入阻塞。

## 2026-10-12：Project01 JJ00与Project03 AE00自然语言直接安装后的续作

已完成：

- 将跨项目发布目录合并逻辑从A600/AH00专用路径抽为通用薄层函数；
- 以Project01 v38为谱系基线，把已验证AE00/JJ00传输安装束发布为v43不可变目录；
- “先添加JJ00基座，再把AE00安装到JJ00传输安装位”完成离线编译、发布授权、持久任务和真实CAD闭环；
- 新任务`project03-job-f18e29248c09`通过3/3配合、完全约束、保存关闭重开和参数复核；输出实体SHA-256为`6ee13d82b634ae0c853d454893cba125ff788a40ff3e830feea799768d4982d8`；
- 证明自然语言直接安装链已覆盖Calibration和Transport两种角色，不是A600/AH00硬编码；
- 定向回归39项、全量后端回归`994 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 调整候选覆盖报告：把已经取得不可变发布授权的跨项目直接关系标为`released_direct_execution`，不要与尚未选择安装配置的候选共同显示为“待消歧”；
2. 生成面向使用者的短摘要，直接展示命令、源模组、目标槽位、端口、模板、配合数、发布ID、CAD结果和耗时，不要求阅读作业大JSON；
3. 从当前已登记端口中选择第三种角色或另一种目标基座做直接安装；若没有兼容槽位，应明确返回机械不兼容或转接需求，不放宽规则制造成功；
4. 继续扩展全目录端口覆盖和跨项目同角色替换；A700专项、前端鼠标点选、碰撞/B-rep、动态行程和生产参数仍不阻塞当前主线。

当前没有必须由用户提供的数据。下一步优先是修正“候选发现”和“已发布可执行”在报告层的状态混淆，而不是重新做CAD几何解析。

## 2026-10-12：候选状态修正与跨项目任务摘要后的续作

已完成：

- 已发布跨项目执行模板与原生安装profile完成分层，不再产生虚假“待消歧”；
- 活动范围当前为1项已发布直接执行、3项可组合有效图、0项待几何复核、0项待消歧、0项端口/模板缺失和66项已知不兼容；
- 两条真实跨项目自然语言任务均生成一页式用户摘要，完整展示命令、端口、模板、发布、3/3配合、完全约束、保存重开、输出路径和耗时；
- 摘要保持碰撞/B-rep为`not_evaluated`，不改变当前主线验收边界；
- 用户摘要已接入通用持久作业产物刷新流程；状态接口直接返回摘要JSON、Markdown路径和状态，不再依赖人工脚本；
- 覆盖报告已增加按角色和项目方向聚合；当前第三种角色没有现成可直接组合候选，Calibration尚有两个未发布可组合方向，Transport尚有一个反向未发布可组合方向；
- 完整后端回归为`998 passed, 3 subtests passed`。

下一步建议顺序：

1. 优先把现有可组合但未发布的Transport反向关系或Calibration另一目标基座做成第三条直接执行证据；这比强行追求第三种角色更符合现有机械证据；
2. 为失败关闭的自然语言任务增加更短的用户原因码和建议动作，使摘要不仅展示失败，还能告诉用户缺端口、机械不兼容或缺发布授权；
3. 若确需第三种角色，应从原型配合图中新增真实provided槽位或走转接接口需求包，而不是放宽已确认不兼容的规则；
4. 继续保留Project06延期、A700专项、前端鼠标点选和碰撞/B-rep为独立后续，不阻塞自然语言模组级灵活组合主线。

当前没有必须由用户补充的信息。下一步优先把现有未发布可组合方向变成直接执行证据，并补失败任务的简短原因码。

## 2026-10-12：活动目录端口/槽位第一轮闭合后的续作

已完成：

- Calibration与Transport的4个有向跨项目同角色替换方向均取得不可变发布授权；
- 其中新增BD00→Project03与SS00→Project03均完成发布绑定自然语言真实CAD复验；
- AH00→Project01也已补齐发布绑定自然语言真实CAD复验；结合此前AE00→Project01证据，活动矩阵4个直接执行方向全部使用同一通用主线完成实证；
- 活动范围待发布、待几何复核、待消歧、端口/模板缺口均为0；66项硬不兼容有明确机械原因；
- 覆盖矩阵新增`basic_active_coverage_closed`，未决方向数为0；
- 历史授权不再因项目最新发布切换而从报告消失；
- 英文“安装到transport slot”与SolidWorks槽配合语义完成区分；
- 完整后端回归`1002 passed, 3 subtests passed`；碰撞/B-rep未执行。

下一步建议顺序：

1. 将当前第一轮闭合状态作为基线，不再继续机械无依据地补端口；
2. 若要扩大“可组合”数量，优先从66项不兼容中选择业务价值最高的角色，新增真实provided槽位或实际转接件，而不是放宽拓扑/几何规则；
3. Project06仍延期；决定接入时先完成角色简表、required/provided端口和原生安装束迁移，再重建矩阵；
4. 为失败关闭任务继续补用户级原因和建议动作，使`incompatible`能够直接说明孔距、拓扑或上下文架构差异；
5. 前端鼠标点选、自动猜面、碰撞/B-rep、动态行程和生产参数继续作为独立后续，不影响本轮端口/槽位覆盖闭合。

当前没有必须由用户确认的信息。第一轮“补端口和补槽位”已基本完成；后续新增端口应由新机械需求或新项目接入驱动。

## 2026-10-12：Project03双槽位顺序兼容闭环后的续作

已完成：

- v47把BD00校准和SS00传输两个跨项目安装模板绑定到同一不可变发布；
- `AA00→SS00→BD00`与`AA00→BD00→SS00`两条自然语言累计链均完成真实CAD执行；
- 每条链的第二包严格消费第一包输出，四个包全部完成3/3配合、定位约束、求解、保存关闭重开和参数复核；
- 顺序报告判定语义结果等价，并明确SLDASM二进制完全一致不是验收要求；
- 活动覆盖仍为4项已发布直接执行、66项明确不兼容和0项未决；碰撞/B-rep未评估。

下一步建议顺序：

1. 为失败任务补齐用户级原因码和建议动作，把拓扑不兼容、孔距不一致、缺provided槽位、缺发布授权分别用短摘要表达；
2. 选择真实业务需要的第三种角色。只有原型中存在可登记目标槽位或已有实际转接件时才新增端口，不为提高覆盖率制造虚假兼容；
3. 若决定接入Project06，先做角色和required/provided端口迁移，再重建矩阵；不要直接复制Project05标签并假定兼容；
4. 前端鼠标点选、A700专项、碰撞/B-rep、动态行程和生产参数继续独立延期。

当前没有必须由用户确认的信息。最有价值的近期开发是“失败原因可解释化”，而不是继续重复运行已闭合的Calibration/Transport组合。

## 2026-10-12：失败原因可解释化完成后的续作

已完成：

- 候选矩阵、跨项目替换预览、发布关系预览、清单编译、持久任务状态和用户摘要已共用同一失败解释层；
- 拓扑不兼容、孔距/定位图案冲突、安装上下文不兼容、缺模组端口、缺目标槽位、缺发布授权和CAD运行失败均有独立原因码；
- 每条解释包含中文说明、建议动作、重试条件、底层阻塞码和CAD启动边界；
- 已生成四类用户可读演示报告，全部在CAD前失败关闭；
- 机械兼容性、发布权限和碰撞边界没有被解释层修改。

下一步建议顺序：

1. 冻结当前Calibration/Transport双角色基线及失败解释格式，避免继续修改已闭合关系；
2. 与需求方选择第三种真正有跨项目替换价值的角色，再从原型中登记一个真实provided槽位或确认已有实体转接件；
3. 若暂无第三角色业务输入，则转向Project06目录接入：先做角色简表和原生required/provided端口迁移，再评估兼容性；
4. 前端只需消费现有`userFailureExplanation`，暂不要求新建复杂交互；碰撞/B-rep和动态验证继续独立延期。

当前没有技术阻塞。下一项开发需要的是业务优先级：选择第三种角色，或者正式接入Project06。
## 2026-10-12：扫描模组备用槽位发现后的续作

已完成：

- Project06继续暂缓；第三个高价值角色选择为Scanner；
- 证实Project01 `SM00` 的 `22 mm` 孔距与Project03原生扫描支承上的最近孔距相差 `0.36068 mm`，直接互换保持失败关闭；
- 在Project01 `JJ00`静态扫描支承叶零件上发现6组精确 `200 mm` 孔对，可作为Project03 `AI00`的备用机械安装候选；
- 选定候选的1个支承面和2个定位面均已在SolidWorks中稳定恢复，`3/3`通过；
- 候选距原生扫描工位约 `349.716 mm`，因此未创建配合、未发布端口，避免将机械孔距匹配误当成扫码功能兼容；
- 原型整机仅用于只读面目录提取，扫描结束后已关闭本轮打开的Project01、Project03顶层原型，未保存源文件。

下一步建议顺序：

1. 从Project01原型和PPT提取条码目标区、扫描器光轴方向及可接受工作距离，形成只读光学验证输入；
2. 对选定 `200 mm` 候选先做离线位姿计算，判断AI00在该孔系上的光轴能否指向目标区；不满足则直接否定，不启动CAD；
3. 只有光学预检通过时，才执行非原型初始位姿三配合CAD短链、保存关闭重开和参数复核；
4. 机械与光学均通过后再建立provided扫描槽位、required端口映射和不可变发布；
5. 若候选光学不通过，将Scanner方向记录为“需要真实转接接口”，再转向下一高价值角色，不继续无边界扫描。

当前没有需要用户补充的必需信息。最关键的未决项不是面是否能找到，而是备用孔系对应的扫码视线是否满足工艺。

## 2026-10-12：扫描候选工艺预检后的续作

已完成：

- 新增统一工艺预检，机械孔系、端点稳定性、扫描光轴、工作距离和条码目标点分别判断；
- 当前AI00→Project01备用孔系在CAD前失败关闭，缺少三类功能语义：`AI00`扫描原点/光轴、扫描工作距离范围、`SS00`条码目标点；
- 没有创建“看似成功但不能扫码”的装配体，也没有污染活动端口目录；
- 完整后端回归`1019 passed, 3 subtests passed`。

后续只需针对明确缺口做小范围补充：

1. 从AI00原型中选择扫描器出光端面/中心并确认朝向，登记`point_axis`端口；
2. 从Project03资料或型号参数登记工作距离范围，并标记证据来源和置信度；
3. 从Project01 SS00原型的扫描停靠位选择真实条码面中心，登记`point_plane`目标；
4. 使用三配合候选位姿计算光轴—目标夹角和距离；不通过则直接否定该备用孔系；
5. 仅在离线工艺计算通过后执行真实CAD短链。

这些动作均不要求引入Project06，也不要求先做碰撞/B-rep。

## 2026-10-12：首条四角色自然语言机械演示链完成后的续作

已完成：

- v48统一授权SS00传输、AI00扫描和BD00校准三个安装模板；
- 四条自然语言成功编译为`AA00→SS00→AI00→BD00`三包累计任务；
- 真实SolidWorks执行一次成功，三包均3/3配合、完全约束、保存关闭重开通过；
- 最终装配体已保存，累计执行时间约529.51秒；
- 演示链闭合器已将机械成功与扫码工艺待验证分开；
- Project06、碰撞/B-rep均未引入。
- 定向回归20项、完整后端回归`1024 passed, 3 subtests passed`。

下一步建议：

1. 不再重复机械长链；优先从既有Project03 AI00资料提取扫描原点、光轴和100 mm粗工作距离基线；
2. 在Project01 SS00的扫码停靠状态中建立条码目标点或目标区；
3. 将两者变换到最终累计装配体坐标系，离线计算距离与有向夹角；
4. 工艺计算通过时将结果写入只读验证关系；不通过时保留机械演示链，但明确该跨项目传输—扫描组合不具备功能兼容性；
5. 完成功能验证后再补一种不同自然语言顺序的四角色编译/执行测试，验证自动依赖排序或顺序兼容。

当前无需用户提供必需信息。主线机械演示链已经打通，下一阻塞集中在跨项目扫码工艺语义，而非配合执行器。

## 2026-10-12：AI00—SS00扫码粗几何闭合后的续作

已完成：

- 复用既有原型证据，将AI00扫描原点、光轴、CAD端点和SS00动态条码通道换算到同一安装坐标系；
- 扫描站落在SS00保守传输区间内，光轴朝向条码通道；
- 横向误差`0.402 mm`，粗几何对齐通过；
- 推算实际所需工作距离`79.500 mm`，与100 mm CAD名义端点相差约`20.504 mm`；
- KEYENCE官方SR-X100规格确认读取距离为`70–1000 mm`，79.500 mm在范围内；
- 静态功能Demo已通过，四角色闭合状态为`complete_demo_chain_passed`，没有重跑CAD长链；
- 工程/生产状态继续失败关闭，因为条码仍是代理面，码尺寸、视野和现场触发未验证。

下一步建议：

1. 在SS00载具或产品叶零件上登记真实条码面中心、法向和随载具运动的局部坐标；
2. 用真实面替换当前Project01扫描光束端点代理，重新计算横向误差、有向距离和视线关系；
3. 加入实际码尺寸与79.5 mm距离下的视野覆盖判断，并补现场触发/停位证据；
4. 上述工程确认不阻塞当前Demo，下一主线可转向不同自然语言输入顺序的编译测试；
5. 机械CAD长链无需重复执行，除非端口、模板或源几何发生变化。

当前没有必须由用户确认的信息；自然语言四角色静态Demo已闭合，剩余扫码项属于后续工程精度提升。

## 2026-10-14：Project05完整累计装配链完成后的续作

- 已完成`A000 → D000 → F000 → M000 → G000 → N000 → P000 → B000`七包自然语言累计CAD任务；7/7包首次成功，真实配合、非原型初始位姿、零锚点、源文件不变及逐包保存关闭重开均有证据。
- 最终实体位于`demo/global_assembly_contexts/manifest_jobs/project05-job-72463661a6a2/packet-runs/packet-007-attempt-01/project05-complete-seven-addon-v2-packet-007.SLDASM`。
- v59预检发现D000仍用`source_pose`并在CAD前停止；D000完成双初始位姿刷新后，统一使用v61不可变发布执行正式链。
- 新增完整链预检脚本；今后任何`source_pose`、案例锚点、叶级锚点、未授权模板、错误累计输入或编译阻塞都必须在启动CAD前拒绝。
- 严格闭合器现在可引用同一发布、目录和模板严格绑定的柔性模组双初始位姿见证；G000机械外部位姿已证明，但内部柔性仍保留。
- 本轮总执行约`874.467 s`，主要时间消耗在大装配打开/解析以及逐包保存重开，而不是配合创建本身。
- 碰撞、B-rep、F000—D000扫码工艺和B000动态行程均保持独立后验状态，未纳入机械累计链通过条件。

下一步建议：先冻结v61机械长链，不重复运行SolidWorks；将同一完整链编译成另一种合法自然语言输入顺序，验证依赖排序与结果一致性。若后续需要工程精度升级，再分别启动扫码只读工艺验证、碰撞/B-rep或动态行程专项，而不修改本轮机械闭合结论。

最终回归：`1096 passed, 3 subtests passed`。多发布证据合并的旧模板覆盖问题也已修复，历史跨项目备用槽位测试恢复通过。

## 2026-10-14：Project03扩展跨项目8模组累计链闭环

已完成：

- 先用兼容矩阵审计跨项目候选，否定了定位尺寸或拓扑不兼容的GJ00、FF00、GN00、LM00组合，没有为了增加跨项目数量而强行装配；
- 建立证据驱动的8顶层模组链：`AA00基座 → Project01 SS00传输 → Project03 AI00扫描 → Project01 BD00校准 → Project03 AD00定位 → Project03 AJ00供胶 → Project03 AG00清洁称重 → Project03 AB00龙门`；
- 发布统一不可变关系目录`relation-v62-project03-expanded-cross-project-chain-driving-20261014`，7个驱动模板由同一发布授权；
- 8条自然语言命令成功编译为7包持久CAD任务`project-global-job-95917567c133`；
- 真实SolidWorks累计执行完成，7/7包均为3/3配合、完全约束、求解干净、零案例锚点、零叶级位姿锚点、源文件不变并通过保存关闭重开；
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project-global-job-95917567c133/packet-runs/packet-007-attempt-01/nl-project03-expanded-cross-project-v2-packet-007.SLDASM`；
- 机器可读闭合证据：`demo/cross_project_substitution/expanded-project03-v1/real-cad-long-chain-closure.json`，状态`passed`；
- 完整任务累计执行记录约`1652.195 s`；有效成功包墙钟时间分别约114.1、268.6、127.9、168.1、147.4、190.5、208.0秒。首次SS00包的冗余清理等待和AG00的图路径预检失败不计入有效配合执行时间，但保留在任务审计中；
- 修复两项通用问题：发布绑定候选过滤/对称模板去重；非原型有效图文件名解析及适配器自清理证据复用；
- Project05旧回归改为从不可变revision快照在内存重建，避免活动演示会话覆盖测试输入。

能力边界：

- 本次证明的是“自然语言清单 → 同一发布授权 → 非原型初始位姿逐包插入 → 真实配合 → 保存重开”的机械累计链；
- 碰撞、B-rep、扫描工艺、龙门动态行程和生产参数未执行，保持`not_evaluated`或独立后验状态；
- 跨项目替换目前只包括已有直接机械兼容证据的SS00和BD00，其余项目01候选仍需真实转接接口或新的兼容证据。

下一步建议：

1. 冻结v62与本次8模组实体，不重复执行已经闭合的7包CAD链；
2. 用不同自然语言输入顺序编译同一8模组目标，验证依赖排序与候选结果一致性，CAD可先只做清单级验证；
3. 选择一个新的、接口证据充分的跨项目角色扩展替换覆盖；没有直接兼容证据时只生成显式转接接口需求，不启动CAD；
4. 若要优化演示体验，再把逐包状态、耗时和中间装配体缩略图接入现有前端；
5. 碰撞/B-rep及动态工艺继续作为可选专项，不回灌为本轮机械链验收条件。

## 2026-10-15：八模组自然语言乱序输入自动重排闭环

已完成：

- 新增发布证据排序层`released-installation-dependency-ordering/v1`；工程师不再必须先输入基座、再严格按CAD装配顺序描述功能模组；
- 输入故意打乱为`龙门 → 清洁称重 → 传输 → 基座 → 供胶 → 校准 → 扫描 → 定位`；系统唯一识别AA00基座后，自动生成`基座 → 传输 → 扫描 → 校准 → 定位 → 供胶 → 清洁称重 → 龙门`；
- 排序只使用v62不可变发布中的完整安装模板、可移植端口和零剩余自由度声明，没有读取原型顶层位姿；
- 生成新的7包持久任务`project-global-job-5ff11649a4f2`，状态`queued`，`cadStarted=false`；自然语言解析、排序、装配图和清单编译总耗时约`1.949 s`；
- 新清单与已完成真实CAD闭环的标准清单语义投影摘要均为`a3795532e328e6e473b28c144586ba2aead7d4ef3b2a1fefde480c108f110a0b`；发布、模组顺序、端口、模板、配合参数、累计输入和自由度完全一致；
- 因语义计划完全等价，没有重复运行约20分钟的SolidWorks长链；既有实体证据继续作为该计划的机械执行基线；
- 后端API模型与通用命令行增加`autoOrderByReleasedDependencies`选项；默认关闭，避免改变历史有序命令的行为；
- 定向回归`24 passed`。

关键产物：

- 乱序编译报告：`demo/global_assembly_contexts/nl-project03-expanded-cross-project-autoorder-v1.natural-language-compilation.json`；
- 乱序CAD清单：`demo/global_assembly_contexts/nl-project03-expanded-cross-project-autoorder-v1.cad-transaction-manifest.json`；
- 语义等价报告：`demo/cross_project_substitution/expanded-project03-v1/autoorder-semantic-equivalence.json`。

后续建议：冻结本次自动排序基线；下一步从全局兼容矩阵中筛选第三种具有直接机械兼容证据的跨项目角色。若不存在直接兼容项，应输出明确的不兼容/转接接口需求，而不是为提高跨项目模组数量强行启动CAD。

## 2026-10-15：跨项目第三角色准备度审计与全量回归

已完成：

- 新增通用审计脚本`scripts/report_cross_project_role_readiness.py`，将跨项目候选矩阵按模组角色归并，区分“发布执行模板数量”和“真正形成直接替换闭环的角色数量”；
- 当前目录共有5条已发布跨项目执行模板，兼容矩阵中有4个已发布方向对，但只覆盖2类可直接替换角色：`Transport`与`Calibration`；
- `CCD`、`Scanner`、`Cleaning`、`CleaningWeighing`、`Gantry`、`GlueSupply`、`Positioning`和`WasteCup`均没有已发布的直接跨项目替换方向对；
- 因此`thirdDirectRoleAvailable=false`。本轮没有为增加跨项目模组数量而启动CAD，也没有把缺端口/模板或不兼容项伪装成可执行组合；
- 机器可读报告：`demo/cross_project_substitution/expanded-project03-v1/third-cross-project-role-readiness.json`；
- 中文审计报告：`demo/cross_project_substitution/expanded-project03-v1/third-cross-project-role-readiness-CN.md`；
- 完整后端回归通过：`1108 passed, 3 subtests passed in 143.85s`。

当前结论：

1. 已完成八模组无序自然语言输入的确定性依赖重排，并证明其CAD语义与已实体验证的标准长链完全一致；
2. 已冻结可诚实演示的跨项目范围：传输与校准两类角色；
3. 第三类跨项目角色的下一步不是重复运行长链，而是优先从业务价值最高的角色中补齐真实端口、槽位和兼容证据；
4. 碰撞、B-rep、动态工艺和生产参数继续作为独立后验项，本轮均未评估。

## 2026-10-15：第三类跨项目角色——WasteCup基准定位CAD闭环

已完成：

- 对Project02 A300与Project05 P000的原生安装关系进行对比，确认二者配合拓扑不同，不能诚实宣称为直接机械接口兼容；直接跨项目替换角色仍只有`Transport`与`Calibration`。
- 从P000既有面端点目录中唯一选出三个正交平面基准，并映射到Project02 A600原A300槽位的纵向、横向和支撑基准；生成2条距离配合与1条重合配合。
- 新执行图不读取P000原型顶层位姿，不使用案例锚点或叶级位姿锚点；目标从确定性的非原型初始位姿独立插入。
- 真实SolidWorks短链通过：3/3配合创建，目标完全约束，配合求解干净，源装配体未改变，保存关闭重开后3条配合类型、方向和参数均保持。
- 输出装配体：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/project02-A600-project05-P000-datum-v1.SLDASM`。
- 闭合证据：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/datum-placement-demo-closure.json`；中文摘要：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/datum-placement-demo-closure-CN.md`。
- CAD墙钟耗时约`218.015 s`，工具内部约`164.242 s`；主要耗时为打开/解析约61.748秒、配合重建约38.604秒、保存关闭约35.177秒和重开复核约24.064秒。
- 角色准备度报告已增加独立的`datumPlacementDemoRoles`层：WasteCup成为第三类“跨项目基准定位Demo”角色，但`thirdDirectRoleAvailable`仍为`false`。

能力边界与问题：

- 本轮证明的是“语义端口＋配合图可从非原型位姿独立定位P000”，不是孔系、螺栓、紧固件或实体转接件兼容证明。
- P000三个目标面在本次运行中通过`BodyFaceIndex`恢复；源拓扑不变时已经保存重开验证，零件拓扑变化后必须重新登记或复验。
- 碰撞、B-rep、维护空间、排胶工艺可达性和生产参数均未评估，继续保持独立后验状态。
- 当前不能把该模板静默加入自然语言默认直接装配目录；需先增加`direct_installation`与`datum_placement_demo`显式策略分流。

后续规划：

1. 保持Transport、Calibration为默认直接跨项目替换角色，WasteCup只在显式“概念布局/基准定位Demo”策略下候选；
2. 将关系用途字段和失败解释接入自然语言编译器，防止基准定位模板被普通工程安装请求误选；
3. 以本次P000短链为已闭合证据，不重复运行SolidWorks；下一步在离线测试中验证显式策略选择、默认阻断和可解释摘要；
4. 若需求方后续需要物理直装，再补孔系/转接件尺寸和实体安装证据；这不是当前自然语言灵活装配主线的阻塞项。

功能修改意义：第三类跨项目角色已经在不依赖原型位姿的真实CAD中证明了语义基准定位能力，同时没有把“能定位”夸大为“能直接安装”，为后续自然语言概念布局与工程直装的双模式奠定证据基础。

### 2026-10-15：自然语言关系执行模式分流

已完成：

- 新增统一策略层`relation_execution_policy.py`，支持`direct_installation`与`datum_placement_demo`两种互斥执行模式；缺省固定为直接安装。
- 全局自然语言候选选择在端口匹配后、关系语义评估前执行证据等级过滤；普通工程安装看不到Demo级模板。
- 多轮命令序列和自然语言持久任务可从顶层传播`relationExecutionMode`，连接图同时保存模式与模板证据等级。
- 最终全局CAD清单编译器再次复核模板用途与连接模式；手工篡改上下文或旧上下文错误恢复均不能绕过门禁。
- 定向回归`25 passed`，覆盖默认只选直接安装、显式模式只选基准定位、未知模式失败关闭、编译阶段二次门禁及既有自然语言流程不回退。

当前尚未做：

- P000→A600基准定位模板尚未写入新的全局不可变关系发布，因此用户界面当前不会出现该Demo选项；现有v62发布及默认工程装配行为保持不变。
- 下一步需要生成独立的WasteCup Demo语义端口包和候选全局目录，将本轮真实CAD闭合证据绑定到模板，再执行“默认模式阻断／显式模式允许”的真实目录级自然语言编译对照。
- 只有上述对照通过后，才把WasteCup基准定位作为可选步骤加入更长累计链；仍不把它计入直接机械替换统计。

功能修改意义：先补安全策略、后接入候选模板，避免为了扩展跨项目角色而改变既有装配语义或把Demo证据提升成工程直装证据。

### 2026-10-15：WasteCup Demo真实目录接入与自然语言对照

已完成：

- 从P000/A600六个真实面端点生成独立语义端口包，新增两个三平面基准端口和模板`P000_to_A600_cross_project_datum_placement_demo_v1`。
- 该模板同时声明`installation`功能用途与`datum_placement_demo`证据等级，完整定位3条配合参数来自已完成的真实CAD闭环。
- 基于v62目录生成隔离候选目录，不修改v62不可变发布，也不影响现有长链。
- 使用工程描述“请在当前设备箱体上安装一套Project05排胶杯模组，用于收集点胶头排出的废胶。”完成对照：
  - 缺省`direct_installation`：状态`blocked`，原因`RELATION_EXECUTION_MODE_MISMATCH`；
  - 显式`datum_placement_demo`：状态`ready`，关系意图识别为`installation`，最终清单状态`ready_for_project_adapter`、1步；
  - 两组均`cadStarted=false`，没有重复运行SolidWorks。
- 关键产物目录：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/semantic-package-v1/`；对照报告：`policy-compilation-comparison.json`。

当前边界：

- 候选目录已证明策略与编译链正确，但尚未制作新的不可变关系发布，也尚未在前端暴露模式选择。
- 真实CAD证据已存在，无需再次运行相同P000→A600短链；后续发布只能绑定已有闭合证据。
- 下一步应增加Demo专用不可变发布元数据，并将模式与证据等级显示在任务摘要；之后再把该可选步骤接入更长累计链的离线编译。

功能修改意义：WasteCup不再只是孤立CAD实验，而是已经进入“自然语言→真实全局目录→证据等级门禁→CAD项目适配器清单”的完整上游链路，同时默认工程装配保持安全失败关闭。

### 2026-10-15：WasteCup Demo不可变发布与发布绑定编译闭环

已完成：

- 发布独立版本`relation-v63-project02-project05-wastecup-datum-demo-20261015`，只授权一个P000→A600三平面基准放置模板；未修改v62长链发布。
- 发布清单新增证据类别元数据：执行模式固定为`datum_placement_demo`，模板证据类别同名，`directMechanicalInterfaceCompatible=false`，碰撞/B-rep为`not_evaluated`。
- 发布加载器、便携绑定和摘要校验均会复核元数据与模板用途；旧发布没有该字段时保持兼容。
- 发布绑定复用了既有真实CAD结果：非原型初始位姿、零案例锚点、零叶级锚点、3/3真实配合、完全约束、保存关闭重开均已通过；本轮未再次启动SolidWorks。
- 用新发布完成自然语言双路径编译：
  - 缺省`direct_installation`被`RELATION_EXECUTION_MODE_MISMATCH`阻断；
  - 显式`datum_placement_demo`提交成功，形成修订2、2个实例、1条连接和1个CAD事务包；
  - 两者使用同一工程描述和同一不可变发布，差异只来自工程师显式选择的证据模式。
- 机器可读对照：`demo/global_assembly_catalog/releases/relation-v63-project02-project05-wastecup-datum-demo-20261015/release-policy-compilation-comparison.json`。
- 发布清单：`demo/global_assembly_catalog/releases/relation-v63-project02-project05-wastecup-datum-demo-20261015/release-manifest.json`。

测试结果：

- 发布元数据与策略定向测试：`19 passed`；
- 最终后端完整回归：`1121 passed, 3 subtests passed in 172.03s`；
- 正式发布后离线编译成功；上下文`wastecup-v63-demo`的CAD事务清单状态为`ready_for_generic_executor_implementation`，包数为1；
- 首次发布后验证曾因上下文ID超过长度边界被安全拒绝，脚本已改为短ID并支持“已有不可变文件内容一致则复核、不一致则拒绝”，未覆盖发布文件。

当前边界与后续：

1. 本次只完成两模组Demo发布，不把WasteCup计入直接跨项目兼容角色；
2. 前端尚未提供证据模式切换与醒目标识；可先继续用后端/脚本验证，不阻塞主线；
3. 若扩展更长累计链，应创建包含直接安装模板与Demo模板的明确组合策略，或把Demo步骤作为独立可选包追加，不能让单一隔离发布越权授权其他关系；
4. 下一优先级仍是补齐更多刚性模组的完整直装端口和兼容关系；碰撞、B-rep与动态工艺保持后验。

功能修改意义：WasteCup基准定位能力现在具备“真实CAD证据—不可变发布—自然语言显式选择—事务包编译”的完整可审计链路，同时默认工程直装行为仍严格失败关闭。

### 2026-10-15：Project02直接安装链追加Project05 WasteCup Demo的多发布离线闭环

目标：

- 在不把Demo模板混入直接安装发布的前提下，将Project02已有四模组实体链`A600+A800+A180+A500`与Project05 P000排胶杯基准定位步骤组合为五模组累计计划。

发现并修复的问题：

- v63上游自然语言与CAD事务清单编译通过，但通用CAD执行计划预检发现其有效图只保留A600，缺少目标P000模组记录；因此执行器无法唯一解析目标模组。
- 保留v63作为问题审计历史，没有覆盖发布文件；生成`semantic-package-v2`，执行图包含A600、P000和3条真实配合，同时仍保持零案例锚点、零叶级位姿锚点。
- 新发布`relation-v64-project02-project05-wastecup-executable-demo-20261015`继承相同真实CAD证据和证据等级边界，并通过默认阻断/显式Demo放行对照。

新增能力：

- 新增`multi_release_cad_chain.py`，可把不同不可变发布组合为分阶段累计链；各阶段独立复核授权，不能互相越权。
- 将v64单包清单的累计输入从登记基座重基为“上一阶段已提交检查点”；目标模组、端口、配合和发布摘要不变，并重新计算包/清单摘要。
- 复用v31真实三包闭合结果作为阶段1：A600基座后依次加入A800、A180、A500，最终检查点文件与闭合SHA-256一致。
- 阶段2使用v64追加P000；通用执行计划已成功解析目标`P000`、3条配合、精确图覆盖、前一阶段实体输入和独立发布授权。

结果：

- 多发布链状态：`ready_for_staged_execution`；
- 顶层模组数：5；累计事务包数：4；
- 阶段1：`direct_installation`，v31，3包，真实CAD闭合已通过；
- 阶段2：`datum_placement_demo`，v64，1包，执行计划`ready_for_adapter_execution`；
- 本轮只构建和验签离线执行计划，`cadStarted=false`，碰撞/B-rep为`not_evaluated`。

关键产物：

- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/multi-release-chain.json`；
- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/wastecup-append.cad-transaction-manifest.json`；
- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/wastecup-append.execution-plan.json`；
- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/offline-closure.json`；
- v64发布：`demo/global_assembly_catalog/releases/relation-v64-project02-project05-wastecup-executable-demo-20261015/`。

测试：

- 多发布链、WasteCup目录、发布和通用执行器定向回归：`38 passed`。
- 后端完整回归：`1124 passed, 3 subtests passed in 159.52s`。

后续：

1. 可在干净SolidWorks会话中仅执行阶段2，把P000真实追加到v31最终检查点，形成五模组实体；无需重复执行阶段1三包。
2. 执行前再次验签v31检查点、v64发布、执行图和事务计划；输出必须另存，不能覆盖v31实体。
3. 若暂不需要实体演示，可继续优先补齐CCD、清洁称重等刚性模组的直接安装端口和跨项目兼容矩阵。

现场状态：完整回归结束后进行了只读`list_documents`探测；当前长期运行的SolidWorks/MCP代理在30秒内未返回初始化响应。因此没有贸然启动阶段2实体写入，也没有结束用户进程。五模组实体执行保持为已计划、未执行；离线计划本身已通过全部摘要与端点检查。

功能修改意义：更长跨项目累计链现在可以同时包含工程直装和显式概念布局步骤，而不牺牲发布隔离、证据可解释性和默认失败关闭原则。

### 2026-10-15：五模组多发布累计链现场CAD闭环

已完成：

- 在干净SolidWorks 2024 SP5会话中恢复直连通信；最初超时来自只读探针误用`Content-Length`帧格式，改用执行器一致的`newline + --stdio-direct`后连接、文档清点均正常。
- 复用v31已通过的最终检查点`A600+A800+A180+A500`，未重复执行前三个CAD包，也未修改该检查点。
- 仅执行v64的P000追加包：Project05排胶杯从确定性非原型初始位姿插入，案例锚点0、叶级位姿锚点0，创建2条距离配合和1条重合配合。
- 现场结果为3/3配合创建、求解干净、目标完全约束、保存关闭重开成功、配合参数一致、源检查点摘要前后一致。
- 二次重开清点确认输出包含5个顶层模组：Project02 A600、A800、A180、A500与Project05 P000；清点后SolidWorks恢复为0个打开文档。
- 输出装配体：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/project02-four-native-plus-project05-p000-demo.SLDASM`，SHA-256为`5cfc71538ba4daa954cfc50200da517383382b7a0f0e623d9972c8c416b79f6c`。
- 现场闭合证据：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/extended-chain-v2/live-closure.json`；原始运行证据位于`live-run-v2/`。

耗时：

- 追加包墙钟耗时约`151.897 s`；
- 打开并解析图根约`39.108 s`；
- 从非原型位姿插入P000约`6.248 s`；
- 重建3条驱动配合约`71.388 s`；
- 保存关闭约`15.220 s`；
- 重开复核约`17.157 s`。

边界：

1. P000阶段是显式`datum_placement_demo`，不是直接孔系/紧固件兼容证明；
2. 三条配合确定的位姿与原型保存位姿平移相差约`1.410233 m`，但本Demo的目标是验证语义基准独立定位，因此没有用原型位姿回灌；
3. 碰撞、B-rep、维护空间和工艺可达性均为`not_evaluated`；
4. 当前实体证明“跨项目五模组累计链可执行”，不应描述为生产可安装方案。

后续建议：

- 若优先扩展主线，应继续为CCD、清洁称重、排胶杯和龙门等刚性角色补直接安装端口与跨项目兼容证据；
- 若优先演示，可直接打开本次五模组文件，并同时展示`live-closure.json`中的3/3配合、零锚点、保存重开和五模组清单；
- 只有需求方明确要求工程可安装性时，才追加孔系/转接件、碰撞/B-rep与工艺可达性验证。

功能修改意义：离线多发布计划已经完成真实CAD落地，证明系统可在不重跑既有阶段、也不借用原型位姿的情况下，把Project05模组追加到Project02累计链中，并保留清晰的证据等级和能力边界。
