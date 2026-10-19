# 项目02静态碰撞分层求解与闭环测试

## 2026-08-17 求解方案 Replay 到完整原型及叶级 B-Rep

- 将 `demo/layout_previews/project02_selected_solution_replay.json` 中的八模组求解位姿 Replay 到项目02完整原型的另存副本；原型源文件仅以只读方式打开，没有被覆盖。
- 新装配体为 `demo/FL9A24D062A000_prototype_replay_solved_v1.SLDASM`。Replay 8/8 成功，最终重建状态为 `Fully Rebuilt`，另存和最终保存均为 0 错误、0 警告；主截图为 `demo/project02_prototype_replay_solved_v1.png`，六向视图位于 `demo/project02_prototype_replay_solved_v1_views/`。
- 从另存装配体重新读取八个指定实例的真实世界 AABB；原型中存在第二个 T401 实例，但本轮严格绑定求解对象 `T401AA-07388-0-1`，没有误检 `-2` 实例。
- 28 个模组对完成全覆盖路由：11 对通过严格膨胀 AABB 或普通 AABB 分离直接证明无干涉；0 对违反严格 AABB；17 对因框架、门洞或嵌套关系进入全量叶级 B-Rep。
- 17/17 个精确候选检查完整，未出现超时或失败。其中 13 对无干涉，4 对存在干涉，共 16 个干涉叶实体对：A100–A180 为 1 对、A180–A200 为 6 对、A200–A800 为 1 对、A300–A800 为 8 对。
- 当前状态为 `STATIC_COLLISION_INTERFERENCE_FOUND`，因此该装配体是“已保存的求解 Replay 诊断样本”，不是静态无干涉闭环结果，`productionReady` 不得置为 true。下一轮应把上述四组精确碰撞证据回灌为求解器占用体/通道约束，再重新求解，而不是在 SolidWorks 中手工移动单个模组。
- 宽阶段结果：`demo/layout_previews/project02_prototype_replay_solved_v1_3d_screening.json`；完整汇总：`demo/layout_previews/project02_prototype_replay_solved_v1_brep_summary.json`；逐叶证据：`demo/interference_prototype_replay_solved_v1/`。

## 2026-08-17 纯八模组装配体修正

- 复核发现历史 `FL9A24D062A000_8components_static_collision_v2.SLDASM` 是从已有容器装配体另存后 Replay，只验证了八个白名单模组的位姿，并未证明装配树中不存在机架、底座箱体等额外组件；历史文件名中的“8components”因此存在误导。
- 新增 `scripts/build_clean_project02_solution.py`：从空白装配体开始，仅插入 A100、A180、A200、A300、A500、A700、A800、T401 八个源模组，再应用 `project02_selected_solution_replay.json` 的求解位姿。
- A200 的目标姿态为单位矩阵，因此作为首个固定组件直接插入目标原点；其余七个组件写入完整三轴姿态和底面目标位置。
- Replay 前后均执行顶层组件名称和源文件路径白名单审计；要求顶层组件数恰好为 8，禁止缺失、额外、重复或路径替换。单元测试覆盖“残留底座组件必须失败”和“源路径错误必须失败”。
- 真实 SolidWorks 构建成功：插入 8/8，Replay 8/8，保存错误/警告均为 0，最终重建状态 `Fully Rebuilt`；前后两次顶层审计均为 8/8，无额外组件、无路径不匹配。
- 新装配体：`demo/FL9A24D062A000_8modules_clean_solved_v1.SLDASM`；主截图：`demo/project02_8modules_clean_solved_v1.png`；六向视图：`demo/project02_8modules_clean_solved_v1_views/`；机器摘要：`demo/layout_previews/project02_8modules_clean_solved_v1_result.json`。
- 六向视图确认历史底座箱体已经消失。当前状态仍为“求解布局展示和人工目测阶段”；本次只闭环了纯八模组构建、位姿应用、白名单和重建保存，不等价于全部叶级 B-Rep 无干涉。

## 目标

本轮面向粗复原阶段：在满足既有工艺、空间和交互硬约束的前提下生成 Top-3 布局，先由展示层选择，再把耗时的 SolidWorks B-Rep 限制到确有必要的组合。运动扫掠、软管、拖链及维护空间暂不纳入本轮验收。

## 已实现方案

- 8 个顶层模组共有 28 个组合，全部在 `staticCollisionPolicy` 中显式分类，不允许漏配或重复。
- 10 对普通实体采用每侧 10 mm 膨胀 AABB 严格分离；失败时求解候选立即淘汰。
- 18 对门洞、框架、嵌套或结构通道组合采用条件 B-Rep：AABB 分离直接通过，重叠才进入精确检查。
- 求解阶段不调用 B-Rep；Top-3 在硬约束可行的前提下，优先减少预计精确检查数量。
- 展示层显示严格 AABB 对数、预计 B-Rep 候选数和求解阶段调用数，避免把“待精确检查”误报成“无干涉”。

## 闭环测试结果

| 检查项 | 结果 |
|---|---:|
| 后端单元测试 | 36/36 通过 |
| Python 编译检查 | 通过 |
| 前端 TypeScript/Vite 构建 | 通过 |
| 工艺硬约束 | 13/13 |
| 空间硬约束 | 11/11 |
| 交互硬约束 | 36/36 |
| 顶层组合分类 | 28/28 |
| 严格 AABB | 10 对，失败 0 |
| 求解阶段 B-Rep | 0 次 |
| 历史姿态投影宽相 | 11 对直接通过，17 对待精确 B-Rep |

自动闭环选择 Top-3 中预计精确检查最少且评分最优的方案，本次选中 rank 1。求解器内部预计条件候选为 16 对；将结果投影到历史 v24 的真实同朝向包围盒后为 17 对。差异来自求解占用体与历史 CAD 世界包围盒的建模粒度不同，最终以 Replay 后的真实世界 AABB 路由为准。

## 已证明的防错行为

- 对历史 v24 布局回归时，新规则检出 A180–A700 只有约 1.47 mm 间隔，低于严格规则要求的 20 mm，因此硬失败且不浪费 B-Rep。
- 新方案的投影间隔约 58.67 mm，同一组合通过严格 AABB。
- 单元测试覆盖“普通实体重叠必须失败”和“结构组合重叠必须转入 B-Rep、不得直接宣称通过”两条关键分支。

## 当前边界与下一道闸门

当前完成的是软件功能、求解约束和离线宽相闭环，不是最终 SolidWorks 实体无干涉证明。由于 SolidWorks 当前仍受“没能装入 Microsoft .NET Framework”启动故障影响，本轮没有对新方案执行 Replay 和叶体 B-Rep。恢复健康会话后，只需对宽相输出的 17 个候选组合执行精确检查；全部为零干涉后，才能把 `staticInterferenceClosed` 改为 `true`。

2026-08-17 后续复测中，可见 SolidWorks 已能启动，但短生命周期 MCP 被 Windows DCOM 导向4个无窗口高权限实例，未稳定复用用户可见会话；系统拒绝结束这些实例。为防止写入错误会话，Replay 在目标文件创建前中止。因此当前阻断点已从“.NET 无法启动”收敛为“SolidWorks/MCP 权限与 COM 会话不一致”。

同日重启后的单会话 v2 Replay 已成功创建并保存 `demo/FL9A24D062A000_8components_static_collision_v2.SLDASM`。8/8 模组移动成功，保存错误/警告均为0，保存回读最大 XY 误差约 `3.95e-8 m`。真实 AABB 宽相中10对严格组合全部通过，11对直接排除，17对待精确 B-Rep。六向视图已生成并完成代理目测，仍等待用户确认后才进入耗时精检。

## 关键产物

- 配置：`demo/FL9A24D062A000_real_process_request.json`
- 选中方案：`demo/layout_previews/project02_selected_solution.json`
- 验证计划：`demo/layout_previews/project02_verification_plan.json`
- 宽相结果：`demo/layout_previews/project02_static_collision_screening.json`
- 闭环摘要：`demo/layout_previews/project02_static_collision_closure_summary.json`

## 2026-08-18 纯八模组 v3 Replay 与精确复核

- 已从空白装配体创建 `demo/FL9A24D062A000_8modules_clean_solved_v3.SLDASM`，只含 A100、A180、A200、A300、A500、A700、A800、T401 八个顶层模组；Replay 前后白名单均为 8/8，无机架底座或原型容器残留，重建、保存和截图完成。
- 保存后的 28 个模组对全部完成分层路由：11 对由三维 AABB 直接排除，17 对进入叶级 B-Rep；17/17 精检均完整返回，其中 11 对无干涉、6 对存在干涉，共 57 个叶实体对。
- 剩余干涉为 A100–A180（5）、A100–A200（1）、A100–A500（1）、A180–A800（24）、A200–A500（21）、A300–A700（5）。A200–A800 已由旧方案的 1 对干涉降为 0，说明结构证据回灌有效，但尚未实现整体静态闭环。
- v28 已把 v3 的精检证据重新构建为版本绑定的局部占用体，并把 A180 朝向固定为源装配方向，防止扫描模组 180° 反装。历史证据不再读取会被覆盖的通用 Replay 文件，而是读取各版本保存结果中的持久布局。
- 当前瓶颈已从 SolidWorks 精检转移到离线候选生成：多包围盒边界修复会产生大量候选，v28 在快速迭代时间预算内尚未得到完整解，因此未创建 v4 CAD 装配体，也未再次启动 SolidWorks。
- 已实现候选相关模组增量复核、位姿占用体缓存、碰撞伙伴证据预筛选和首个硬失败即停；约束单元测试 27/27 通过。完整 v28 预览求解仍超过 60 秒，已按快速迭代闸门主动中止，未把超时冒充可行或不可行结论。
- 机器汇总：`demo/layout_previews/project02_8modules_clean_solved_v3_brep_summary.json`；状态为 `STATIC_COLLISION_INTERFERENCE_FOUND`，`productionReady=false`。
- v28 状态：`demo/layout_previews/project02_v28_iteration_status.json`。

## 2026-08-18 方案 1 纯八模组 v4 Replay 与条件 B-Rep

- 用户在展示层确认继续后，将 rank 1 物化为 `demo/layout_previews/project02_selected_solution.json`，并以 A200 为固定锚点生成 `project02_selected_solution_replay_v4.json`；锚点平移不改变八模组相对布局。
- 从空白装配体创建 `demo/FL9A24D062A000_8modules_clean_solved_v4.SLDASM`。插入、Replay 均为 8/8；Replay 前后顶层白名单均为 8/8；无额外底座或原型容器；重建完成，保存错误/警告均为 0；原型源文件未覆盖。
- 保存后的真实世界 AABB 对 28/28 模组对完成分层路由：13 对直接排除，严格 AABB 失败 0，对剩余 15 对执行条件叶级 B-Rep。15/15 精检完整返回，11 对无干涉，4 对有干涉，共 11 个叶实体对。
- 干涉组合为：A100–A200（2）、A200–A700（2）、A300–A800（4）、A500–A800（3）。A200–A800、A180–A800、A100–A180、A200–A500 等组合已精检为零干涉。
- 机器汇总：`demo/layout_previews/project02_8modules_clean_solved_v4_brep_summary.json`；状态为 `STATIC_COLLISION_INTERFERENCE_FOUND`，不得标记为静态闭环或生产可用。
- 本次验证的意义：证明“展示层确认 → 纯模组 Replay → 世界 AABB 宽相 → 条件 B-Rep”的分层链路可以完整运行，并把 28 对全量精检缩减到 15 对；同时说明当前结构占用体仍未覆盖上述四组真实干涉，下一轮应把逐叶证据回灌到通用约束并重新求解，不在 SolidWorks 中手工移动模组。
## 2026-08-18 v29/v30 证据回灌、v5/v6 优先门禁

- v29 合并了 v4 的 11 个干涉叶实体对。由于新增占用证据压缩了可行域，将联合候选上限由 5 调整为 12、搜索时限由 20 秒调整为 60 秒后，离线求解恢复为约 5 秒完成；相关 42 项单元测试及 Python 编译检查通过。
- v5 从空白装配体生成并保存 8 个白名单模组，Replay 前后均为 8/8，保存错误和警告均为 0。三维宽相阶段对 28 组模组对完成路由：14 组直接排除，14 组进入条件 B-Rep 候选。
- 按“历史失败优先、首个硬失败即停”复核 v4 的四组干涉：A200–A700、A300–A800、A500–A800 已降为 0；A100–A200 仍有 13 个干涉叶实体对，因此未消耗时间继续做全部精检。
- 曾分别尝试把 A100–A200 建模为“完整子装配体 AABB 硬约束”和“全部叶体 AABB 硬约束”。两者都会使 A200 无候选，属于非凸框架/嵌套关系的保守假阴性，已撤回；代码保留为可选机制，但项目 02 默认禁用。
- v30 将 A100–A200 明确标为 `cadOnlyPair`，允许求解阶段的包围盒重叠，但要求 Replay 后以叶级 B-Rep 作最终判定；配合非原型修复种子，离线求解约 0.864 秒，工艺/空间/交互约束分别为 13/13、11/11、36/36，传输中心偏差约 7.5 mm。
- v6 同样完成纯 8 模组 Replay、重建和无错误保存，但 A100–A200 优先门禁检出 56 个干涉叶实体对。该候选比 v5 更差，已立即停止其余 B-Rep 检查，不能标记为闭环或可生产。
- 当前结论：三组历史干涉已通过通用约束消除，剩余瓶颈集中为 A100–A200 非凸嵌套关系。下一轮采用有限数量的 U/V 二维修复候选，逐个只跑 A100–A200 精确门禁；仅首个通过者再执行完整条件 B-Rep。
- 机器可读状态：`demo/layout_previews/project02_v29_v30_v6_iteration_status.json`。
## 2026-08-18 A100–A200 有界局部修复与门禁复测

- 新增 `scripts/generate_a100_a200_repair_candidates.py`，把单次全局重求解改为最多 6 个局部种子、求解硬约束预筛、非目标漂移门禁、A100–A200 单对 B-Rep 优先门禁和首个硬失败即停。
- 第一版候选虽离线可行，但 A300 相对基线漂移约 593 mm。候选 1/5 的 A100–A200 分别仍有 22/11 个干涉叶体；视觉层已判定其不是局部修复。由此新增 1 mm 非目标漂移门禁，禁止这类方案进入 CAD。
- 求解器新增 `warm_start_locked_components`。A180/A300/A500/A700 与目标 A200 可按热启动锁定；锁定组件不得被碰撞修复器追加、偏移或重新排序。修正后 6 个 v2 候选的非目标漂移均为 0，单候选求解约 0.04 秒。
- v2 局部候选 1 已生成 `demo/FL9A24D062A000_8modules_local_repair_c01.SLDASM`，Replay 前后白名单 8/8、保存错误/警告 0；A100–A200 精检仍为 13 个干涉叶体，因此未执行其余条件 B-Rep。
- 原型参考中的 A100–A200 精检为 0，相对位置约 `(U=+0.100 m, V=-0.991 m)`。该信息只用于校准搜索区带；修复锁定语义后，附近 6 个精确候选全部被当前模型拒绝，其中 3 个失败于 A200–A800 叶占用盒，3 个失败于工艺约束。
- 锁定语义修复前生成的通道候选曾出现 130 个 A100–A200 干涉叶体。该装配体仅保留为回归反例，不是有效候选，原因是锁定后的 A200 仍被碰撞修复扩展。
- 当前瓶颈已经从“找不到平移量”收敛为“约束模型矛盾”：已知零干涉的通道邻域被 A200–A800 占用体或工艺区带拒绝。下一步先复核这两类约束的局部坐标和门洞/通过体归属，再生成 CAD；继续盲跑 B-Rep 没有价值。
- 回归：43/43 单元测试、Python 编译和 6 份关键 JSON 解析通过。机器状态：`demo/layout_previews/project02_a100_a200_repair_iteration_status.json`；`productionReady=false`。

## 2026-08-20 v31 分层碰撞策略闭环

- 已把成对静态策略贯通到多包围盒验证：条件 B-Rep 组合的叶级 AABB 重叠只生成 CAD 待检项；普通实体组合仍用膨胀 AABB/多盒严格分离。
- A200–A800 同时保留门洞硬约束。“允许包围盒重叠”只避免非凸结构假阳性，不等于允许传输体穿墙；短轴、净高或指定通过体不满足时仍直接淘汰。
- v31 离线解为 8 模组、13/13 工艺、11/11 空间、36/36 交互、严格 AABB 失败 0、求解内 B-Rep 0 次；展示候选预计有 16 组条件 B-Rep。
- 数值视觉门禁全部通过，但自动浏览器检查因 localhost 安全策略未执行，不能自动授予视觉批准。A200 顶层外形存在约 139.6 mm/104.9 mm 两向越界，必须由展示页人工确认其方向、边界和明显接触。
- 叶占用宽相把 A700–A200 标为当前最高优先级（7 个粗碰撞盒对）；另外 A100–A800、A100–A200、A800–A700、A800–A200 因非凸占用覆盖不足进入条件精检队列。
- 当前未启动 SolidWorks Replay：一是人工视觉门禁未完成，二是系统没有健康的 `sldworks.exe` 主进程。避免在门禁未通过时重复消耗 CAD 加载与 B-Rep 时间。
- 机器结果：`demo/layout_previews/project02_v31_numerical_visual_gate.json`；迭代状态：`demo/layout_previews/project02_v31_iteration_status.json`。
