# 待继续事项

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
