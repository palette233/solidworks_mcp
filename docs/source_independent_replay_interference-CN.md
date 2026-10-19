# 去原型依赖布局：SolidWorks Replay 与三维干涉检查

## 结论

- 已完成扫描方向、完整三轴姿态、功能模组龙门覆盖，以及 A500/A700/A300 与 A800 传输线接触问题的修正和保存后复测。
- 修正装配体保存、重建成功，`Errors=0 / Warnings=0`；8/8 模组持久化位姿通过，最大平移误差 `2.4425e-15 m`，完整姿态误差 `0°`。
- A500–A800、A700–A800、A300–A800 的实际世界 AABB 净空分别为 `19.73 mm`、`10.25 mm`、`72.02 mm`，可直接证明三组实体不接触。
- A800/A200 与龙门投影重合率为 `86.30%/85.49%`，A180/A500/A700/A300 为 `100%`，全部达到各自硬约束下限。
- 28 对顶层组件中，实际 AABB 已证明 15 对分离，仍有 13 对保守候选需要精确 B-Rep/最小间隙复核。
- 当前状态为 `TARGETED_LAYOUT_FIXES_CLOSED_BREP_PENDING`：本轮指出的问题已闭环，但整机尚不能宣称无干涉，`productionReady=false` 保持不变。

## Replay 输入与输出

- 输入布局：`demo/FL9A24D062A000_source_independent_replay_layout2d.json`
- 目标装配体：`demo/FL9A24D062A000_8components_source_independent_corrected.SLDASM`
- Replay 结果：`demo/FL9A24D062A000_source_independent_corrected_replay_result.json`
- 保存后位姿验证：`demo/FL9A24D062A000_source_independent_corrected_pose_validation.json`
- 三维宽相位：`demo/FL9A24D062A000_source_independent_corrected_3d_screening.json`
- 闭环摘要：`demo/FL9A24D062A000_source_independent_corrected_closure_summary.json`
- 截图：`demo/source_independent_corrected_replay_result.png`

## 修正内容

1. 布局结果增加目标 X/Y/Z 三轴，不再用单一 `thetaDegrees + thetaAxis` 推断姿态，修复 A180 扫描器及 A700/A300 的 180° 翻转歧义。
2. SolidWorks Replay 直接写入完整正交姿态框架并保留平移；保存后逐轴复测，所有组件轴向误差均为 `0°`。
3. 去原型模式下，旧装配体中与新自由布局冲突的 7 个顶层配合保持抑制。配合未删除，可恢复；否则恢复旧配合会把修正姿态重新拖回原位置。
4. 新增真实保存位姿 AABB 的龙门覆盖和指定传输净空硬复验，避免只验证求解器二维规划包络。
5. 传输工作段向低侧偏置 `181.5 mm`，A700 向高侧偏置 `51.8 mm`；偏置后仍通过 13/13 工艺约束和 6/6 空间约束。

## 三维检查口径

1. 从保存后重新读取的 `BoundingBoxWorld` 对全部 28 对执行 1 μm 保守宽相位。
2. 任一轴间隙大于 1 μm，可证明实体不相交；相交、接触或近接触均保留为精确候选。
3. 精确候选使用隔离进程调用 SolidWorks B-Rep 接口，并设置硬超时；超时不能解释为无干涉。

机器可读结果以本页“Replay 输入与输出”中的 corrected 文件为准；未带 `corrected` 的文件保留为修正前历史记录。

## 后续

精确 B-Rep 接口对大型嵌套子装配体仍可能长时间阻塞。下一步应优先实现按轻量化表示、零件实体集合或最小间隙 API 的候选对复核；在剩余 13 对精确候选、运动扫掠体和维护抽出空间完成前，不提升生产就绪状态。

回归验证：后端 `unittest` 26/26、Bridge `AssemblyServiceTests` 10/10 通过，Python `compileall` 通过，MCP 应用 C# Release 构建 0 警告/0 错误；去原型双扰动测试最大相对差 `4.44e-16 m`，Replay、持久化位姿验证和三维宽相位脚本均通过。测试工程编译仍报告既有 nullable 警告，不影响本次测试通过结论。

## 2026-08-09 第三轮 v3 更新

第三轮装配体 `demo/FL9A24D062A000_8components_interaction_v3.SLDASM` 已完成 Replay、保存和保存后位姿复测，不再是未验证副本。

- 8/8 Replay、最终重建和保存通过，`Errors=0 / Warnings=0`；
- 保存后位姿与底面 8/8 通过，最大平移误差 `5.3291e-15 m`；
- 28 对世界 AABB 中12对确定分离，16对为精确候选；
- 精确完成5对，均无实体干涉：A500–A200、A180–A200、A200–A300、A200–A700、A300–A700；
- A180–A800、A200–A800、A300–A800精确检查超时；其余6对龙门结构包络和2对A800候选尚未完成。

因此本轮比旧 corrected 结果进一步排除了 A500–CCD 等关键接触风险，但仍属于 `PARTIAL_BREP_PENDING`。完整机器结果见 `demo/FL9A24D062A000_interaction_v3_closure_summary.json`。

## 2026-08-09 v3 叶级 B-Rep 最终复核（覆盖上节旧结论）

为解决大型 A800 子装配体在 `ToolsCheckInterference2` 中持续超时的问题，已改为按叶级实体展开：实体变换到顶层装配坐标后先做 AABB 预筛，再由 SolidWorks Modeler 与布尔交集进行精确判定。

- 28 个顶层模组对中，12 对由三维 AABB 确定分离；
- 16 个精确候选全部完成，精确失败 0、待检查 0；
- 10 对无干涉，6 对有干涉，共 105 个干涉叶级实体对；
- 干涉组合为：A100–A800（1）、A180–A200（11）、A200–A700（1）、A300–A800（74）、A500–A800（10）、A700–A800（8）；
- A200–A800 虽有 114 个实体 AABB 候选，但布尔交集全部为空，确认无实体干涉。

旧顶层组件检查对嵌套子装配体覆盖不足，曾将 A180–A200、A200–A700 记录为无干涉；该结论现由叶级实体结果覆盖。A500–A200 仍确认无干涉。

最终状态为 `LAYOUT_REPLAY_STATIC_BREP_INTERFERENCE_FOUND`：Replay、保存和位姿复测已闭环，但当前 v3 布局未通过静态碰撞验收，不能作为“合理无干涉方案”交付。动态扫掠、拖链/软管和维护空间也仍未完成，因此 `productionReady=false`。

## 2026-08-09 v8 去原型Replay与精确干涉复测

- 正式装配体：`demo/FL9A24D062A000_8components_interaction_v8.SLDASM`；8/8组件移动、重建和保存成功，保存错误/警告均为0。
- 独立SolidWorks实例仅从磁盘重开该装配体，8/8姿态复测通过：最大平移误差 `6.7924e-16 m`、完整姿态误差 `0°`、底面误差 `4.2079e-15 m`。
- 三维宽相位检查共28组：10组确定分离，18组进入叶级B-Rep；18/18完成，失败叶实体对0。
- 精确结果为3组/32个叶实体对：A100–A200 1、A180–A200 5、A500–A700 26。A200–A700、A200–A800、A200–T401、A300–A700、A300–A800等本轮关注组合均已确认无实体干涉。
- 相比v4的8组/52个实体对，v8减少为3组/32个实体对；但静态干涉仍非零，状态为 `CALIBRATED_LAYOUT_REPLAY_POSE_CLOSED_STATIC_BREP_REMAINING_3`，不得标记为实体闭环成品。
- 证据汇总：`demo/FL9A24D062A000_interaction_v8_combined_brep_summary.json`；校准摘要：`demo/FL9A24D062A000_interaction_v8_calibration_summary.json`。

## 2026-08-10 A200真实门洞、扫描通道与多包围盒 v10 复核

- A200 门洞改用 624 个叶实体包围盒提取的净空：局部范围 `[0.055,-0.1611]~[0.875,0.9975] m`，高度 `0~0.27 m`。A800 使用 `throughLongAxis`；A180 使用命名结构通道 `scannerStructureChannel`。
- A180 通道只检查扫描头及安装座，不再要求整个扫描模组进入门洞；A500、A700 分别使用 3 个叶实体聚合占用盒参与净空和视线判断。
- 去原型双扰动结果完全一致，离线结果为工艺 `13/13`、空间 `11/11`、交互 `19/19`、非法投影重叠 `0`；后端 `31/31` 和前端生产构建通过。
- v10 Replay 8/8、重建和保存成功，保存错误/警告均为 0。磁盘重开复测 8/8 通过，最大平面误差 `3.3307e-16 m`、最大角度误差 `1.1369e-13°`。
- 三维 AABB 排除 12/28 对；16 个候选全部完成叶级 B-Rep，失败/未完成为 0。A180–A200、A180–A800 均无干涉；A500–A700 间隙 `71.66 mm`，A180–A700 间隙 `92.22 mm`。
- v10 仍有 5 组实体相交：A100–A200 `18`、A100–A500 `3`、A200–A700 `84`、A200–A800 `2`、A300–A800 `11` 个叶实体对。
- 同口径原型复核中，A100–A200、A100–A500、A200–A700、A200–A800 均为 0，证明这四组是新布局残差；原型 A300–A800 本身有 2 个实体对接触，但 v10 增至 11 个，仍不能按安装接触放行。

当前状态为 `REAL_CHANNEL_AND_MULTI_BOX_IMPLEMENTED_STATIC_BREP_RESIDUAL_5`。指定的几何表达功能已经建立并通过单元/展示/Replay/重开测试，但静态实体闭环尚未完成，`productionReady=false`。

## 2026-08-10 联合求解 Top-3 与 Replay 状态

- 新求解器以 A100+A800 为固定骨架，对 A200/A180/A700/A500/A300 执行有界联合回溯；7个节点得到3个完整方案，首选方案离线为工艺13/13、空间11/11、交互34/34。
- 去原型双扰动最大相对布局差为0；结果写入 `demo/FL9A24D062A000_source_independent_layout2d.json`，A500锚定后的首选 Replay 输入为 `demo/FL9A24D062A000_source_independent_replay_layout2d.json`。
- `demo/FL9A24D062A000_8components_joint_v11.SLDASM` 是失败诊断副本：错误连接旧MCP目录，8/8底面映射缺失，没有执行平移，不得作为新方案。
- `demo/FL9A24D062A000_8components_joint_v12.SLDASM` 从原型重新复制；使用 multibox 发布包后调用180秒超时，未输出 Replay JSON/截图，文件时间未变化。因此 v12 也尚不是已应用布局。
- 当前准确状态为 `JOINT_TOP3_OFFLINE_CLOSED_SOLIDWORKS_REPLAY_BLOCKED`。v10 的5组静态干涉证据仍是最近一次完整CAD结论；新联合方案必须完成Replay、重开位姿和叶级B-Rep后才能覆盖它。
## 2026-08-09 第四轮离线校准状态

- 旧v3的叶级B-Rep共确认6组干涉：A100–A800、A180–A200、A200–A700、A300–A800、A500–A800、A700–A800。
- 新求解把“载具运动走廊”和“传输固定结构禁入区”拆开，并把A500/A700/A300移动到禁入带同一侧的阀服务簇；A200向低侧移动，供胶组件回到龙门低侧服务区附近。
- 新去原型解已写入 `demo/FL9A24D062A000_source_independent_layout2d.json`；A500锚定后的Replay输入为 `demo/FL9A24D062A000_source_independent_replay_layout2d.json`。
- 当前只完成离线求解、双扰动、展示层和构建测试。SolidWorks没有可用COM实例，故尚无新装配体、保存位姿或新叶级B-Rep结果；不得把本节解释为干涉已经消除。
## 2026-08-10：v24 真实占地修正后的闭环状态

- 正式粗布局副本：`demo/FL9A24D062A000_8components_joint_v24.SLDASM`。
- 去原型双扰动测试通过；两次输入对每个源组件施加不同平移，求解结果相对龙门的最大差为 `1.1102230246251565e-16 m`，确认没有恢复原型坐标。
- SolidWorks Replay 8/8 成功，原位保存 `errors=0 / warnings=0`，截图为 `demo/joint_v24_replay_result.png`。重建调用返回成功，但文档状态仍为 `swModelRebuildStatus_NonFrozenFeatureNeedsRebuild`。
- Replay 后尝试用隔离会话从磁盘重开 v24：首次无法复用 ROT/COM；强制隔离实例获得 Premium 许可证后，在 `OpenDoc6` 发生 `0x800706BE` RPC 失败。因此本轮没有伪造“磁盘重开姿态通过”或“精确 B-Rep 通过”。
- COM 不健康期间仅执行明确标注的同朝向平移投影宽相检查。该检查以已复测的 v23 落盘姿态为基线，不是新的保存姿态或精确实体证据。结果：A700 对龙门覆盖率 100%，A800 86.8%，A200 88.2%，A180/A500/A300 均为 100%；28 对中 12 对由三维 AABB 排除，16 对保留给精确 B-Rep。
- 投影宽相中 A500-A700 全 AABB 间隙约 `12.466 mm`，A300-A700 约 `8.108 mm`，A180-A700 约 `1.470 mm`；多包围盒硬约束仍为 36/36 通过。全 AABB 重叠不能直接解释为实体干涉，尤其是龙门稀疏框架、A200 门洞和传输穿越关系。
- 当前状态：`SOURCE_INDEPENDENT_LAYOUT_REPLAY_SAVED_REOPEN_AND_BREP_BLOCKED_BY_SW_RPC`，`productionReady=false`。恢复干净 SolidWorks 会话后必须补做：磁盘重开 8 模组姿态复测、实际世界 AABB、16 对叶级精确 B-Rep。
