# 项目02：降原型依赖布局与分阶段计时运行说明

更新时间：2026-09-02

## 1. 本轮目标与状态

当前目标是快速得到项目02的合理粗布局，并让求解、展示审批、离线宽相、SolidWorks Replay、条件B-rep等阶段各自留下可机读时间戳和耗时，便于后续直接运行脚本定位性能瓶颈。

已实现`reduced-prototype`求解档位：不读取旧Replay作为warm start，不复制原型顶层位姿，也不使用9条由历史原型/碰撞回灌形成的模组对相对位姿窗口。它仍保留项目02原型估计出的工程输入，包括A600/A800安装基准、扫码点与粗工作距离、双阀公共行程、功能服务点、维护空间和局部候选规则。因此当前应称为“降原型顶层位姿依赖”，不能称为“完全去原型”。

当前离线实测可生成3个候选。A600已作为0自由度固定环境根模组加入结果，因此每个候选显示9个对象；rank 1满足：A600安装门禁8/8、工艺约束21/21、空间约束13/13、交互约束64/64，10组严格包围盒关系无失败。九对象共36对，其中原8模组保持18组条件B-rep，新增8组A600关系按安装接触/结构嵌套单独复核。当前`staticInterferenceClosed=false`，尚未宣称实体零干涉。

## 2. 推荐运行顺序

在仓库根目录执行：

```powershell
python scripts\solve_project_layout.py --project project02 --profile reduced-prototype --output demo\layout_previews\project02_reduced_prototype_pipeline_run.json
```

该命令只求解并刷新展示数据，不自动批准候选，也不启动SolidWorks。每次重新求解都会把旧`project02_selected_solution.json`置为`awaiting_visual_selection`，避免把上一轮选案误用于本轮Replay。旧`calibrated`档位的warm start已改为只读版本化证据`project02_prototype_context_optical_solved_v52_result.json`，不再与当前人工选案共用文件。展示层中的A600虚线框表示固定箱体/安装环境；它参与安装门禁，但不是自由搜索变量。

展示页确认方向、边界和明显接触后，才使用同一命令增加`--approve-rank 1`批准对应候选。批准动作会单独记录计时，但会重新执行一次确定性求解；如后续需要消除这次重复求解，可再拆出独立`approve_project_layout.py`轻量命令。

在未启动SolidWorks前，可执行保守离线投影与宽相：

```powershell
python scripts\project_saved_replay_poses.py --target-layout demo\layout_previews\project02_solution.json --baseline-replay demo\FL9A24D062A000_joint_v24_replay_result.json --baseline-poses demo\FL9A24D062A000_joint_v24_projected_poses.json --output-poses demo\layout_previews\project02_reduced_prototype_projected_poses.json --output-report demo\layout_previews\project02_reduced_prototype_projection_report.json

python scripts\screen_source_independent_layout_3d.py --layout demo\layout_previews\project02_solution.json --poses demo\layout_previews\project02_reduced_prototype_projected_poses.json --assembly demo\FL9A24D062A000_8components_joint_v24.SLDASM --output demo\layout_previews\project02_reduced_prototype_3d_screening.json
```

这一步只将已保存的SolidWorks包围盒按新平面位姿刚体投影，用于宽相风险预估；它不是实际Replay，也不是B-rep证据。

合并已有计时证据：

```powershell
python scripts\summarize_project02_pipeline_timing.py
```

默认输出`demo/layout_previews/project02_pipeline_timing_summary.json`。尚未运行的Replay或B-rep会明确显示为`not-run`，不会被误算为零耗时。

## 3. 计时数据格式

所有新计时采用同一结构：

- `runId`：本次运行唯一标识；
- `pipeline`：流水线名称；
- `startedAtUtc`、`finishedAtUtc`：ISO 8601时间戳；
- `durationSeconds`：基于单调时钟的真实持续时间；
- `stages[]`：阶段名、顺序、开始/结束时间、耗时、状态及可选对象数量；
- 失败阶段记录`status=failed`和`errorType`。

计时已覆盖：

- 求解请求/参数加载、几何加载、候选求解、碰撞策略编译、装配顺序、展示数据和持久化；
- 人工选案物化与验证计划持久化；
- 离线位姿投影和28对世界AABB宽相；
- SolidWorks MCP Replay总会话及每一个工具调用；
- 条件叶级B-rep总批次及逐模组对；
- 优先B-rep门禁和结果复用。

报告最后一次“写入自身计时对象”的小文件重写不计入对应持久化阶段，JSON中有`note`明确说明，避免循环计时。

## 4. 本轮性能基线

2026-09-03的A600接入回归中：核心求解约3.46秒，A600固定环境附加与8条安装门禁约0.012秒，离线九组件位姿投影约0.027秒，36对AABB/安装接触分类约0.024秒。Replay与条件B-rep尚未对本轮新候选执行，因此它们仍是预计的主要CAD端性能风险，不能用离线耗时代替。

## 5. 下一步

1. 在展示页目测当前Top-3并批准唯一候选。
2. 使用包含A600的完整项目02源装配体执行一次真实SolidWorks Replay；不得覆盖原型或旧闭环装配体。Replay脚本保持A600原位，只移动另外8个模组。
3. 先根据真实Replay世界AABB排除普通模组对，再只对仍重叠的条件对象对做叶级B-rep；A600的8组关系按“允许正常安装接触、禁止非法穿透”单独复核。
4. 将Replay/B-rep计时汇入总报告，按“SolidWorks启动/文档加载、布局应用、重建保存、视图导出、逐对B-rep”排序寻找瓶颈。
5. 若布局方向不合理，回到通用工艺约束和候选规则修订；若仅实体相交，则将失败对象对回灌为可解释的占用/净空约束后重新求解，禁止人工移动成品掩盖求解缺陷。

功能修改意义：把“由助手串行执行一次完整闭环”改造成可由用户独立运行、逐阶段审计和测量的脚本流程；同时使新求解自动废止旧选案，保证布局、Replay与性能数据属于同一版本。

## 6. 2026-09-03 九模组直接生成实测

- v2空白装配体直接生成成功：`demo/FL9A24D062A000_9modules_direct_solved_v2.SLDASM`。它只包含A600固定环境和8个求解模组，未复制原型总装；保存重开后9/9组件、路径和位姿一致。
- v2真实宽相：36对中10对严格AABB通过，19对无需B-rep，17对进入条件B-rep，8对A600安装接触单列；宽相本身通过，但`staticInterferenceClosed=false`。
- 条件B-rep批次用时111.336秒，共完成7/17对并提前停止。前6对A100结构组合无干涉；A180–A200用时9.241秒，检出1个实体对相交。其余10对因早停未执行。
- B-rep反馈回灌后，v3离线求解用时3.832秒，通过22/22工艺、13/13空间和65/65交互约束；离线位姿投影用时0.028秒。
- v3第一次建装复用了做过B-rep的活动CAD会话，SolidWorks失去响应且未写盘；清理后第二次从零进程启动，桌面诊断确认“.NET Framework无法装入”，错误报告故障模块为`nvoglv64`。软件OpenGL安全启动仍被.NET提示阻断，故v3装配体、回采位姿和截图当前不存在。
- 后续恢复命令应使用已验证v2独立装配体作直接增量源：`python scripts\build_direct_project02_nine_module_solution.py --source-direct-assembly demo\FL9A24D062A000_9modules_direct_solved_v2.SLDASM --poses demo\layout_previews\project02_a600_fixed_projected_poses_v3.json --target-assembly demo\FL9A24D062A000_9modules_direct_solved_v3.SLDASM ...`。这不是原型Replay；它只减少重复插入九个大型子装配体的CAD开销。

功能修改意义：量化证明秒级瓶颈不在求解，而在SolidWorks装载、保存和精确实体运算；同时用“首个失败即停”把本轮B-rep从17对缩减到7对，避免在已知无效布局上继续消耗CAD时间。

## 7. 2026-09-03 v10–v15闭环计时与决策

| 阶段/版本 | 结果 | 用时 |
|---|---:|---:|
| v10 A500–A700精检 | 0干涉 | 精检9.27 s，总会话71.90 s |
| v11九模组生成 | 9/9保存重开通过 | 200.51 s |
| v11 A200–A300精检 | 0干涉 | 精检10.28 s，总会话73.72 s |
| v12九模组生成 | 9/9保存重开通过 | 225.16 s |
| v12 A200–A800精检 | 仍有干涉 | 精检27.45 s，总会话90.35 s |
| v13九模组生成 | 9/9保存重开通过 | 229.45 s |
| v13 A200–A800精检 | 仍有干涉 | 精检27.83 s，总会话90.80 s |
| v14九模组生成 | 9/9保存重开通过 | 226.24 s |
| v14 36对宽相 | 严格失败0，条件候选16 | 0.036 s |
| v14高风险B-rep | 前4组0干涉；A700–A800为4对 | 171.78 s（首个失败即停） |
| v15九模组生成 | 9/9保存重开通过 | 227.84 s |
| v15 A700–A800精检 | 6对干涉，劣于v14 | 精检34.51 s，总会话97.64 s |

当前推荐实体版本是`demo/FL9A24D062A000_9modules_direct_solved_v14_correct_normal_heights.SLDASM`。v15仅作为“整体平移A700无效”的反例保留。最新离线回归求解耗时约2.04 s，3个候选均通过25/25工艺、13/13空间和65/65交互检查，说明时间瓶颈仍在SolidWorks建装和叶级精检。

功能修改意义：把多轮耗时结果统一为可比较的版本链，明确停止继续尝试无方向的整模组平移；后续先解决A860工艺状态/配置，再运行剩余条件对，可避免每轮重复消耗约3–4分钟建装和数分钟精检。

## 8. 2026-09-05 v22成对叶级约束与增量闭环实测

| 阶段 | 结果 | 用时 |
|---|---:|---:|
| v42占用模型生成 | A100–A300增加211/4个成对叶实例盒 | <1 s |
| v22 Top-3求解 | 26/26工艺、13/13空间、65/65交互 | 3.357 s |
| 位姿投影 | 仅A300变化，位移172.4 mm | 0.023 s |
| 投影AABB快筛 | 严格失败0，19/36对免B-rep | 0.021 s |
| 独立九模组增量建装 | 保存重开9/9、Fully Rebuilt | 232.50 s |
| A300四组增量B-rep | A100/A200/A700/A800均0干涉 | 114.10 s |
| 证据合并 | 4组新检＋13组相对位姿不变复用 | <1 s |

- 新装配体：`demo/FL9A24D062A000_9modules_direct_solved_v22_full_leaf_candidate.SLDASM`。
- 机器可读闭环：`demo/layout_previews/project02_v22_incremental_brep_closure.json`。
- 闭环状态：17/17条件对有有效证据、10/10严格AABB通过、未接受失败0；A700–A800保留1组原型既有接触类别，因此不是字面零接触。
- 本次计时再次表明：解析求解、投影、宽相合计不足4秒；主要成本仍是SolidWorks连接/打开/保存/重开约155秒，以及按需叶级B-rep约114秒。后续优化优先复用已打开文档、减少重复保存重开，并按相对位姿复用精检结果，而不是削减求解候选。
- 当前直接建装报告的顶层`timing.stageCount=1`只统计了入口阶段，但`steps[*].timing`已完整记录每次SolidWorks调用；该汇总层级不完整属于可观测性债务，不影响本轮几何结论。

功能修改意义：首次用可机器复核的相对位姿签名完成跨版本B-rep结果复用，把17组条件精检压缩为4组真实新检；同时给出准确性能瓶颈，为后续脚本化运行和CAD端耗时优化提供依据。
