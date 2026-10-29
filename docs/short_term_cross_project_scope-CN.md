# 短期跨项目六类模组装配范围

## 2026-10-26 全型号×多基座规划覆盖更新

- 六类范围包含4种基座和17种移动模组，共68个精确组合。
- 已发布可执行26项；可直接进入CAD验证7项；待工程确认33项；当前权威目录无所需轴对、需换安装策略2项；待软件语义实现0项。
- Project05 G000的三个跨基座组合已从“缺混合模板”转为“确认精确槽定位轴＋纵向距离”，并保留四关系柔性拓扑。
- 0项待语义实现不等于全目录已可执行。只有26项精确发布允许正常CAD启动；其余组合继续在CAD前失败关闭。
- 碰撞/B-rep、实际紧固、动态工艺和生产放行仍不属于当前装配编排门禁。

## 1. 目标

当前短期目标只覆盖以下六类模组：

1. 箱体、机架与固定基座；
2. 产品传输与载具输送；
3. 条码扫描；
4. 喷嘴校准与标定；
5. 清洁与称重；
6. 排胶与废胶处理。

目标不是允许任意两个同类模组强行互换，而是在已登记接口允许的范围内，完成自然语言选择、语义端口匹配、完整配合、非原型位姿定位和累计CAD装配。

### 2026-10-26：统一六类报告已接入多基座参数化验证队列

统一就绪度入口现在同时读取直接机械发布、累计链证据和第五版参数化基准验证队列，并强制验证队列摘要及其`sourceCatalogDigest`与当前规范接口目录一致。当前17组参数化配对中，2组已完成精确配对发布，11组已具备非原型CAD验证包，2组等待明确位置参数，2组等待明确轴线选择；扫描与清洁/称重不再沿用旧的“全部跨项目硬不兼容”状态。

这项变化不把规划候选提升为直接机械互换：直接跨项目机械发布仍只覆盖Transport与Calibration；Scanner和CleaningWeighing显示为`parameterized_datum_pair_released`，表示各已有一组非原型CAD、保存重开和不可变发布证据，其余具体模组—基座组合仍需逐组验证。统一机器可读报告为`demo/global_assembly_catalog/short-term-cross-project-scope-v1/readiness.json`，当前摘要为`4f53026776054eddd8cc878290e1dc99edd25361306b98c742a7f501cc1a73d5`。

当前真实CAD队列首项为`Project01 GN00 → Project05 A000`。执行器两次均检测到评审装配体`case02_project03_8module_cross_project/...packet-007.SLDASM`及其叶文档仍在SolidWorks会话中，总计861个已加载文档，因此在CAD启动前安全拒绝；没有写入尝试文件、CAD结果或新装配体。该门禁不会自动关闭用户评审文件。

本轮统一报告专项回归通过，完整后端回归为`1759 passed, 3 subtests passed in 131.08s`；Python编译和差异格式检查通过。

### 本轮最新状态（2026-10-23）

已补齐 `Project05 P000 → Project03 AA00` 支承面＋400/200 mm显式位置参数端口，完成两模组验证，以及两种顺序的六类跨项目累计链：

`Project03 AA00 基座 → Project01 SS00 传输 → Project03 AI00 扫描 → Project01 BD00 校准 → Project03 AG00 清洁/称重 → Project05 P000 排胶杯`。

标准顺序及变序 `AA00 → AG00 → BD00 → SS00 → AI00 → P000` 均完成六模组清点、十五条真实激活配合、非原型初始位姿、逐包保存重开、P000追加前后原五模组与十二条配合不变和排胶杯有符号位置见证。只有AA00固定。独立只读对比确认两种顺序的相对位姿、配置、求解状态及配合等价，状态为`PASSED_SIX_ROLE_ORDER_EQUIVALENCE`。两种顺序均将P000放在最后，不宣称任意排列都已验证。

这是一条六类齐全、来自三个项目的Demo链，不是六类都跨基座直接互换：AI00与AG00仍使用Project03原生基座接口；P000采用显式支承定位Demo，孔位和实际固定方式未验证。直接机械兼容角色数仍为Transport、Calibration两类，不因累计数量增加而提升。

实体及证据分别位于`demo/cross_project_substitution/six-role-project03-base-v1/standard/`和`reordered/`。完整外层执行合计分别为550.056秒和558.914秒，均复用已验证的单基座缓存，不是冷启动基准。专项进展与首包上下文问题修复见`docs/project05_p000_mounting_interface_confirmation-CN.md`第8节；统一计时见[six-role耗时摘要](../demo/cross_project_substitution/six-role-project03-base-v1/timing-summary-CN.md)。

## 2. 当前证据

- 六类模组在Project01、Project02、Project03和Project05活动范围内均已有可移植端口或已验证基座槽位；Project06继续暂缓。
- Project05已有覆盖六类角色的完整累计实体链，可证明每类角色均能由端口与配合束完成非原型位姿安装。
- Project03八模组跨项目Case02已经公司机械工程师确认，满足本阶段展示需求；其中传输与校准为跨项目直接安装。
- 当前已发布的直接跨项目互换角色仍只有`Transport`和`Calibration`。
- Scanner各原生槽位与Cleaning/Weighing已知跨项目方向具有机械硬不兼容证据；不得为了扩大覆盖而放宽接口门禁。
- Scanner已发现`Project03 AI00 → Project01 JJ00`的6组200 mm备用槽位候选，选定的3个端点已全部稳定恢复；22个孔位/方向候选均已完成位姿和扫码通道代理计算。机械三基准可严密对齐，但当前最佳光轴仍偏离Project01 SS00条码通道代理`49.402 mm`，超过`5 mm`容差，因此路线被工艺代理验证阻断，未进入CAD，也不属于已发布兼容关系。
- Cleaning/Weighing已将Project01 GN00从“JJ00主定位＋SS00方向基准”升级为JJ00单一基座上的“一面两孔”端口。GN00从非原型初始位姿完成3/3真实配合、完全约束及保存重开，并形成不可变发布`relation-v65-project01-gn00-base-only-two-hole-driving-20261022`。Project03 AG00同样已有一面两孔发布，但两者定位孔距分别为`204 mm`与`170 mm`，相差`34 mm`，因此原生槽位仍不兼容。
- 在Project03 AA00限定静止承载叶中已找到两组精确`204 mm`孔距候选，距AG00原生工位约`552 mm`和`593 mm`，目标圆柱半径均为`5 mm`。孔距命中只证明几何候选；孔用途、支承面、紧固方式以及该区域是否允许布置清洁/称重模组仍待机械确认，因此没有建立端口、没有启动跨项目CAD。
- 反向检查Project01 JJ00已登记静止叶时，`0.2 mm`工程容差内没有AG00所需的`170 mm`等半径双孔槽位；放宽到`0.5 mm`只得到一组`170.238 mm`近似孔对。系统明确拒绝以放宽容差发布该路线。
- WasteCup已将Project05 P000的支承定位Demo接入Project02四模组检查点，形成`A600 → A800 → A180 → A500 → P000`五模组累计装配。追加包以支承重合＋80/390 mm显式位置参数，从非原型位姿创建3条真实配合并保存重开；原四模组位姿和九条配合保持不变。当前状态为`support_position_cumulative_demo_verified`。本轮只重跑P000一包，耗时395.258秒，额外只读累计复核34.351秒。孔位匹配作为可选后续研究；实际固定方式暂未验证，不计为直接机械互换兼容。

机器可读报告：

- `demo/global_assembly_catalog/short-term-cross-project-scope-v1/readiness.json`；
- `docs/evidence/cross-project-case02-mechanical-review-decision.json`；
- `GET /api/demo/short-term-cross-project-scope`。

## 3. 当前状态

当前总体状态为：

`stage_demo_ready_cross_project_expansion_in_progress`

含义：

- 本阶段展示所需核心能力已经成立；
- 六类端口基础覆盖已经完成；
- 已有完整角色链和机械评审通过的跨项目案例；
- 但不能宣称六类模组均可在所有项目间直接互换。

## 4. 后续开发顺序

### 4.1 Scanner

保留现有原生孔距、槽位和光学语义门禁。`Project03 AI00 → Project01 JJ00`备用200 mm槽位已经完成候选位姿求解：安装面与双孔轴残差均接近零，但最佳扫码通道横向误差为`49.402 mm`，当前状态为`alternate_slot_blocked_process_proxy_mismatch`。下一步不是直接运行CAD，而是由机械/工艺人员确认真实条码面和载具停位；若目标不变则否决该备用槽位，若目标代理需修正则登记真实目标后重算。禁止通过放宽容差制造兼容结论。

### 4.2 Cleaning/Weighing

Project01 GN00与Project03 AG00现在都具备真实CAD验证的一面两孔安装端口，端口拓扑已经可比较；但二者定位孔距分别为`204 mm`与`170 mm`，原生槽位不能直接互换。Project03基座有界搜索已经找到两组`204 mm`几何候选，下一步先由机械工程师确认孔用途、支承面、紧固方式和工位区域；确认合理后再登记端口并做非原型位姿CAD闭环。若确认不属于安装槽位，则保持不兼容，不进入改孔或新增转接件路线。

反向的`AG00 → Project01 JJ00`路线在当前限定叶上没有严格命中；`170.238 mm`近似孔对不进入后续CAD。当前优先评审Project03 AA00上的两组精确`204 mm`候选。

### 4.3 WasteCup

**当前优先路线：支承面＋显式位置参数 Demo。** 用户已明确不把孔位匹配作为该 Demo 的硬性条件。以下孔槽筛选为保留的历史取证，不再阻断支承定位装配；其接口未知状态也不能因此被修改为“直接机械兼容”。

**Project02前一阶段累计闭环（2026-10-23，最新Project03六类链见文首）：** 在既有四模组检查点追加P000成功，五模组重开齐全，原四模组变换、固定/约束状态及原九条配合的类型、方向、距离与激活状态均保持不变。新增三条配合均激活、错误码为0，P000未固定且完全约束。源检查点和只读复核前后的输出SHA-256均不变。

- 自然语言需求为“请在当前设备箱体的支承面上增加一套排胶杯，用于收集废胶；采用支承面和位置参数定位演示，实际固定方式暂不验证。”具体P000型号已明确选择，80/390 mm由显式配方提供，不宣称从自由文本自动推导尺寸。
- 复用现有编译器和CAD包执行器：执行模式仍为`datum_placement_demo`，`support_position_demo`只是其中的参数化策略，不新建执行框架。默认直接安装模式继续阻断这个未验证固定方式的模板。
- 新关系发布为`relation-p000-support-position-demo-20261023-v1`；证据目录为`demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-chain-v3/`，闭环文件`chain-closure.json`，状态`PASSED_SUPPORT_POSITION_CHAIN_DEMO`。
- 新实体为同目录`project02-four-plus-project05-p000-support-v3.SLDASM`；本轮复用了前四模组检查点，只执行一个追加包，不是从空白重跑，也不是八模组整机或六类完整覆盖。
- 后续可复用此追加入口扩展其他已验证模组；清洁/称重跨项目接口仍单独保留其待确认状态，不能借本次排胶杯Demo一并宣称兼容。

现有三基准定位Demo的`80 mm / 390 mm`距离只描述演示位姿。本轮完整原型配合图复核发现，P000与A000实际有`重合43＋平行14＋槽口6`三条关系；此前只读取旧两平面模板，漏掉了槽口关系。安装板四处半圆柱面与四处长直壁组成两条闭合长圆槽，原型明确使用其中一条槽，另一条槽也与基座圆柱孔对位。两处Ø5圆孔存在，但对外安装用途未证实。原先将其作为主要孔系、排除槽端的结论已经修正。

孔槽安装路线的来源状态为`source_slot_installation_confirmed_target_interface_pending`，可以进入A600限定静止安装区的只读孔位匹配。语义签名为“支承面＋双长圆槽＋显式沿槽位置”，匹配时应检查横向间距和槽内可调范围，不能把长圆槽当作固定圆孔对。原型自由槽尚留1个沿槽平移自由度；既有CAD已验证增加显式安装距离可闭合，但其345.122535 mm数值属于Project05案例，不能原样移植。该路线在目标接口与位置参数确认后才进行孔槽驱动的非原型CAD验证；当次源接口核查没有新建装配体或发布关系。

详细图文证据：[P000安装接口确认](project05_p000_mounting_interface_confirmation-CN.md)。

2026-10-23追加：已完成A600三处限定安装叶的匹配，其中原生排胶杯支承叶新增读取112面、未命中合适圆孔对；已有传输/扫描安装板上找到8对较优备用几何候选。候选孔距86.117652 mm，按共同可调区间中点得到沿槽11.844678/38.155322 mm参数。具体孔用途、有限支承区域及安装侧仍待确认，因此未启动新CAD装配、未执行保存重开、未发布关系。当前进展不是“无候选”，而是“已有尺寸化候选及参数，目标接口尚未确认”。新证据：`demo/cross_project_substitution/wastecup-project05-to-project02-v1/a600-slot-match-v1/slot-match-report.json`。测试52项通过。

2026-10-23后续调整及新CAD结果：采用支承面与位置参数，不要求孔对匹配，从非原型初始位姿`variant=1`重新插入P000，建立3/3真实配合，完全约束、求解干净、保存关闭重开及参数复核通过；案例锚点和叶级锚点均未使用，源上下文未改写，装配执行耗时167.665秒。额外23.735秒只读重开核查确认仅A600固定、P000非固定、3条实际配合均未压缩且错误码为0，文件SHA-256未变；两阶段合计约191.400秒。只读打开有需要重建警告32，未宣称整机完全无警告。新产物为`demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-demo-v2/project02-A600-project05-P000-support-demo-v2.SLDASM`；同目录`datum-placement-demo-closure.json`状态为`PASSED_SUPPORT_POSITION_DEMO`。`80 mm / 390 mm`属于可编辑Demo设计参数，不是厂商孔位尺寸。图中目标`SourceTransform`为identity占位，因此旧`ExternalPlacementEquivalencePassed=false`不作为本轮验收失败；本轮不验收原型位姿等价。实际固定方式明确`not_verified`，该成果只提升基准定位Demo证据，不增加直接机械互换角色数。

机器可读证据：

- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/p000_physical_attachment_candidate.json`；
- `demo/cross_project_substitution/wastecup-project05-to-project02-v1/mechanical_interface_gap_audit.json`。

### 4.4 累计装配回归

区分直接机械安装与显式支承定位Demo两类阶段证据；可以先复用已验证检查点追加单包，再扩展到完整角色链，不能用旧全链证明新策略已执行。

每增加一个新的直接跨项目角色，至少执行：

1. 非原型初始位姿单包闭环；
2. 保存、关闭、重开及配合参数复核；
3. 加入六类完整累计链；
4. 更换添加顺序的兼容性测试；
5. 不兼容负例的CAD前失败关闭。

对支承定位Demo，已完成单包、Project02五模组累计闭环及Project03两种实际顺序的六类累计闭环；同样检查非原型位姿、真实激活配合、保存重开、上游组件/配合不变，但不以孔位、紧固件或生产放行为门槛。两套变序文件独立绑定证据，比较结论见`demo/cross_project_substitution/six-role-project03-base-v1/order-comparison-v1/`；不能推广为全部排列已验证。

## 5. 验收边界

- 原型顶层位姿默认禁止使用；显式调试模式除外。
- 原生槽位不兼容与备用槽位候选必须同时保留；备用候选不能覆盖或删除原生接口结论。
- 备用槽位只有在稳定端点、必要工艺语义、非原型CAD配合和保存重开均通过后，才能升级为`alternate_slot_released`。
- 基准定位Demo不等于直接机械兼容。
- 对用户明确选择的支承定位Demo，孔位匹配与实际固定方式不作为硬门禁；必须公开位置参数及固定方式未验证边界，且不能将该例统计为直接机械互换兼容。
- 碰撞、B-rep和动态工艺仍为独立后验项，不作为当前范围硬门禁。
- 只有不可变发布授权、非原型CAD闭环和机械评审均具备时，才可表述为“已验证跨项目直接安装”。

本轮修改意义：把分散的端口、兼容矩阵、累计链和机械评审证据汇总为单一可执行范围状态，防止“单模组端口已存在”被误解为“任意跨项目自由组合已经完成”。

2026-10-23累计链接入的意义：证明支承面与显式位置参数不仅能生成单独排胶杯小装配，也能通过现有自然语言编译与通用事务包追加到已有功能链；新增累计状态不会抬高直接机械兼容计数，避免“Demo定位成功”被误读为“实际固定已验证”。
