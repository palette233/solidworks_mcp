# 面映射功能链路记录

更新时间：2026-07-07

本文档用于记录当前项目中“面映射”相关功能的完整链路、现有能力边界、已知限制，以及下一步优化方向。它重点服务于 Common Base、Replay Layout、10+ 子装配体布局恢复等流程。

## 1. 功能目标

面映射功能的核心目标是：

1. 用户或程序在 SolidWorks 中确定某个组件的“底面”。
2. 系统把这个底面的几何特征记录到 `face_mappings.json`。
3. 后续在 Common Base、Replay Layout、验证等流程中，系统能根据记录重新选中同一个面。
4. 选中后读取该面的中心点、法向、面积等数据，用于共底面、朝向校验、移动复原和布局验证。

换句话说，面映射是从“人工或程序选中一个 IFace2”到“后续自动找回并操作这个面”的桥梁。

## 2. 当前完整链路

### 2.1 手动选面并记录

用户在 SolidWorks UI 中选中某个面，然后运行记录接口。

MCP 工具入口：

- `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/SelectionTools.cs`
- `RecordFaceMapping`

底层服务：

- `vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/SelectionService.cs`
- `RecordFaceMapping`
- `SaveFaceMapping`

当前记录内容包括：

- `leafComponentName`
- `leafComponentFullName`
- `localCenter`
- `localNormal`
- `worldNormal`
- `persistentReferenceBase64`
- `area`

记录结果写入：

- `artifacts/solidworks-mcp/face_mappings.json`

注意：当前 `RecordFaceMapping` 只负责记录“当前选中的面”，不负责判断该面是否真的为底面。

### 2.2 自动选回记录的面

后续需要操作底面时，会调用 `SelectFaceByName`。

底层服务：

- `vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/SelectionService.cs`
- `SelectFaceByName`

当前选面策略：

1. 从 `face_mappings.json` 读取组件名和面名对应的映射。
2. 如果存在 `persistentReferenceBase64`，优先用 SolidWorks Persistent Reference 找回面。
3. Persistent Reference 失败时，降级到几何匹配。
4. 几何匹配会先定位 `leafComponentFullName` 或 `leafComponentName`。
5. 在 leaf component 内扫描候选面。
6. 根据 `localCenter`、`area`、`localNormal` 计算候选面分数。
7. 选中分数最优且满足阈值的面。

### 2.3 选中后 probe 当前几何状态

选回面后，会调用 `GetSelectedFaceMappingProbe` 读取当前状态。

底层服务：

- `vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/SelectionService.cs`
- `GetSelectedFaceMappingProbe`

Probe 会返回：

- 当前选中面的 `WorldCenter`
- 当前选中面的 `LocalCenter`
- 当前选中面的 `WorldNormal`
- 当前选中面的 `LocalNormal`
- 面积 `Area`
- 包围盒 `Box`
- leaf component 信息

这个步骤的意义是：Common Base 和 Replay Layout 不直接相信旧记录，而是每次操作前读取“当前装配体状态下”的面中心和法向。

### 2.4 Common Base 使用面映射

Common Base 高层工具：

- `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/DemoTools.cs`
- `FinalizeCommonBaseAssembly`
- `FinalizeCommonBaseCore`
- `TryMateBottomFace`
- `ProbeBottomFaceOrientations`

流程：

1. 后端确认每个组件都有底面映射。
2. MCP 打开目标装配体。
3. 对每个组件调用 `SelectFaceByName` 选回底面。
4. 以第一个组件为 anchor。
5. 对其它组件执行 anchor 底面与 target 底面的 Coincident mate。
6. 重建并保存。
7. 再次选回每个底面，probe `worldNormal`。
8. 将其它组件底面法向与 anchor 法向做 dot product 校验。

如果法向不一致，会返回 orientation mismatch。

### 2.5 Replay Layout 使用面映射

Replay Layout 高层工具：

- `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/DemoTools.cs`
- `ApplyCapturedCommonBaseLayout`
- `ApplyCapturedCommonBaseLayoutCore`

流程：

1. 读取 layout JSON。
2. 将 layout2d 中的 `x/y/theta` 转换成共同底平面上的目标位置。
3. 如果存在 `theta`，先按底平面法向做平面内旋转。
4. 调用 `SelectFaceByName` 选回当前底面。
5. 调用 `GetSelectedFaceMappingProbe` 读取当前底面中心。
6. 用 `目标底面中心 - 当前底面中心` 计算移动向量。
7. 调用 `MoveComponent` 完成位置恢复。

## 3. 后端与前端中的调用位置

后端入口：

- `apps/demo-backend/src/demo_backend/services/demo_service.py`
- `verify_face_mappings`
- `_finalize_common_base_plan`
- `_apply_captured_layout_plan`
- `_ensure_common_base_ready_batched`

前端主要通过按钮触发：

- Verify Faces
- Common Base
- Replay Layout
- Generate Config
- Upload Layout JSON

后端不会直接操作 SolidWorks COM，而是生成 MCP tool call plan，由 MCP 工具执行实际 SolidWorks 操作。

## 4. 当前已实现能力

当前已经具备：

1. 手动选中面并记录。
2. 自动选回已记录面。
3. 记录和使用 Persistent Reference。
4. Persistent Reference 失败后的几何匹配 fallback。
5. 记录面中心、面积、法向。
6. Verify Faces 批量验证映射。
7. Common Base 中按底面执行 Coincident mate。
8. Common Base 后进行底面法向一致性检查。
9. Replay Layout 中基于底面中心移动组件。
10. Replay Layout 中支持 layout2d theta 平面内旋转恢复。
11. 10+ 组件场景下分批 Common Base。

## 5. 当前功能限制

### 5.1 不能自动判断真实底面

当前系统能记录和找回“一个面”，但不能稳定自动判断“哪个面是真实底面”。

原因：

- SolidWorks API 层只知道几何面，不知道业务语义。
- “底面”依赖用户意图、装配姿态、重力方向或共同基准面定义。
- 某些组件的真实底面可能被遮挡、很小、分裂成多个面，或者不是最大平面。

### 5.2 手动记录质量直接影响后续所有结果

如果用户选错面，后续会出现：

- Common Base 把错误的面配合到一起。
- Replay Layout 用错误的面中心计算移动量。
- Orientation check 显示 mismatch 或 probe error。
- 组件位置看似移动成功，但几何复原结果错误。

### 5.3 Persistent Reference 并非跨场景绝对稳定

Persistent Reference 在同一文档上下文内较稳定，但在以下场景可能失败：

- 组件重新导入到新装配体。
- 装配体另存。
- 组件实例名变化。
- 文件版本或内部拓扑变化。
- 同一个零件被多次实例化。

因此 Persistent Reference 应作为优先路径，但仍需要几何 fallback。

### 5.4 leaf component 名称变化会导致映射失效

当前映射保存了 `leafComponentFullName`，例如：

```text
A-1/SubAsm-1/Part-1
```

如果新装配体中实例名从 `Part-2` 变成 `Part-1`，或顶层组件名变化，直接查找会失败。

目前已有部分 name adaptation / target layout 处理，但真实项目中还需要更稳的 source-to-target component identity 映射。

### 5.5 小面或复杂面可能无法读取稳定法向

当前法向主要依赖平面参数。如果遇到：

- 很小的面
- 非标准平面
- 退化面
- 被导入几何导致的异常面

可能出现 `normal=null` 或 near-zero normal。

这会影响：

- Common Base orientation check
- 自动朝向修正
- Replay theta 参考

### 5.6 几何匹配仍可能误选相似面

当前 fallback 主要依据：

- localCenter
- area
- localNormal

如果一个零件上存在多个相似平面，例如对称面、重复孔面、阵列面，仍有误选风险。

### 5.7 批量 Common Base 的耗时和稳定性问题

10+ 组件场景下，耗时主要来自：

- 多次 SelectFaceByName
- 面候选扫描
- SolidWorks mate 求解
- Force rebuild
- 组件数量增加后的 COM 调用开销

底面映射质量差时，会增加重试、误配合、诊断和人工修复成本。

## 6. 当前问题可能原因归纳

| 现象 | 可能原因 |
| --- | --- |
| Verify Faces 失败 | 映射缺失、组件名变化、leaf component 找不到、Persistent Reference 失效 |
| Common Base orientation mismatch | 记录的不是同向底面、选回了错误面、组件初始姿态不一致 |
| Probe normal unavailable | 面不是稳定平面、小面读取失败、几何退化 |
| Replay Layout 位置误差大 | 底面中心选错、layout JSON 中组件名不匹配、theta 未正确恢复 |
| 10+ 组件流程卡顿 | mate/rebuild/COM 调用累积，或错误映射导致 SolidWorks 长时间求解 |
| 同一组件源装配体验证通过，目标装配体失败 | source/target 实例名、层级路径或 persistent reference 上下文不同 |

## 7. 下一步优化方向

### 7.1 增强底面自动候选能力

目标：不要直接让用户在复杂装配体中手动找底面，而是提供候选列表。

候选面评分可以考虑：

- 面积较大。
- 法向接近指定基准方向。
- 与其它组件候选面接近共同平面。
- 面中心在组件包围盒低位。
- 面类型为平面。
- 排除过小面、孔内壁、小倒角面。

产出：

- 新增 `ListBottomFaceCandidates`
- 前端展示候选面列表
- 用户确认后记录

### 7.2 强化 SelectFaceByName 的强校验

目标：宁可报错，也不要静默选错。

优化点：

- Persistent Reference 选中后，也重新 probe 并和记录数据比较。
- 几何 fallback 选中后，输出候选面诊断。
- 如果 center/area/normal 偏差超过阈值，返回失败。
- 后端 Verify Faces 将工具内部失败聚合为 blocked/error。

### 7.3 增加 post-common-base mapping snapshot

目标：Common Base 后保存一份目标装配体当前状态下的面快照。

用途：

- 后续 Replay Layout 优先使用 post-common-base snapshot。
- 减少组件姿态变化导致的映射漂移。
- 便于比较 Common Base 前后面中心和法向变化。

### 7.4 引入更稳定的组件身份映射

目标：解决 source assembly 到 target assembly 的组件名变化问题。

可以记录：

- 原始文件路径
- 顶层实例名
- leaf component path
- 文件名 stem
- 配置名
- transform signature
- 用户选择的 source-target 对应关系

后续生成 project config 时，应保存 source component 与 target component 的映射表。

### 7.5 小面 normal fallback

目标：当 PlaneParams 失败时，仍尽量获得可用法向。

候选方案：

1. 用 face 三角化结果拟合平面。
2. 用边界点拟合平面。
3. 用邻近共面候选面推断。
4. 用用户指定 normal 覆盖。

### 7.6 面映射质量等级

目标：让系统明确知道某个映射是否适合真实共底面。

建议分级：

- `manual_verified`: 用户手动选中并 Verify PASS。
- `persistent_verified`: Persistent Reference 可稳定选回。
- `geometry_verified`: 几何 fallback 可选回。
- `first_face_placeholder`: 自动第一面记录，仅占位，不建议 Common Base。
- `invalid`: 缺失或校验失败。

Common Base 和 Replay 可以拒绝使用低质量映射，或者要求用户确认。

## 8. 推荐近期实施顺序

1. 先实现 SelectFaceByName 的强校验和候选诊断。
2. 再做 post-common-base mapping snapshot。
3. 然后实现底面候选列表，减少人工找面成本。
4. 最后完善 source-target component identity 映射，支撑 10+ 真实项目。

这条路线的优点是渐进、风险低，并且不会破坏当前已经能演示的稳定链路。

## 9. 与当前主需求的关系

主需求是：

```text
记录原始装配体 X 中多个子装配体的 layout2d，
在新 assembly 中导入这些子装配体，
使它们共底面，
再根据 layout2d 恢复位置和 theta。
```

面映射在其中承担两个关键角色：

1. 定义每个组件参与共底面的“底面”。
2. 在 Replay 阶段提供当前底面中心，从而将 layout2d 的目标位置转换为 MoveComponent 的移动量。

因此，面映射质量越高，Common Base 和 Replay Layout 的准确性、耗时和稳定性都会越好。
