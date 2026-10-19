# 项目03阶段冻结与恢复开发说明

更新时间：2026-09-01

## 1. 当前目标

项目03当前目标不是直接复刻原型或立即生成SolidWorks装配体，而是：从项目03自身PPT、配合关系和叶体几何中恢复项目专属参数，在通用装配顺序与约束类型下形成可审计的Top-3粗布局输入。

## 2. 已完成工作

1. 已识别AA00～AJ00共10个主要模组，并整理为8个布局对象：固定环境、传输、翻转定位、龙门/双阀、组合功能、标定、扫描和供胶。
2. 已导出29条跨模组配合和9组连接；恢复AA00–AE00支承面、双定位孔、58 mm孔距及项目03安装坐标。
3. 已恢复两个AD10/AD20工作位：安装坐标U约522/907 mm，中心距385 mm；AE90结构交叉验证最大偏差18.6 mm。
4. 已恢复AI00扫描基线：1个显式KEYENCE SR-X100，光轴沿`+worldY`，CAD光束100 mm，移动轴与传输方向平行。
5. 已恢复AG00/AH00共7个服务目标：2个清洁位、1个称重点、1个硬度检测点、2个排胶点和1个标定棱镜点。
6. 已恢复AB00/AC00双阀粗布局范围：900 mm流向尺度、1100 mm横向尺度、130 mm阀间距，公共范围约770×1100 mm。
7. 两个工作位与7个服务点共9个目标全部进入双阀公共范围；最小边界余量为6 mm，排胶杯1是高敏感目标。
8. 展示页已同步项目03证据卡，并修复“缺失项为0但仍有部分证据时误报粗布局闭环”的问题。
9. 后端Python测试150/150通过，前端TypeScript与Vite生产构建通过。

## 3. 当前门禁状态

- 缺失硬证据：0项。
- 部分证据：5项。
- `top3SolveReady=false`，暂不生成项目03 Top-3。
- 未对项目03执行Replay、另存新装配体或实体B-rep检查。
- 所有原型参数继续保持`engineeringConfirmed=false`、`vendorConfirmed=false`，仅授权粗布局。

仍为部分证据的项目：

1. `baseOperationFace`：操作侧暂由服务模组集中在`+worldX/+installationV`侧推断，尚无精确选面。
2. `barcodeFaceAndSide`：CAD只显示1个SR-X100和1个薄型身份头；PPT中的载具条码/RFID角色尚未完全对应。
3. `operationSideCapacity`：已有顶层空间关系，但维护通道和精确操作面容量未正式放行。
4. `moduleOccupancy`：已有大量叶体数据，尚未整理成项目03求解对象的多包围盒占用体。
5. `staticCollisionPolicy`：尚未完成28组布局对象对的严格AABB、条件B-rep和安装接触分类。

## 4. 已生成的关键机器证据

- `demo/layout_previews/project03_first_stage_geometry.json`
- `demo/layout_previews/project03_module_mate_graph.json`
- `demo/layout_previews/project03_work_positions.json`
- `demo/layout_previews/project03_scanner_geometry.json`
- `demo/layout_previews/project03_service_points.json`
- `demo/layout_previews/project03_dual_valve_reach.json`
- `demo/layout_previews/project03_migration_readiness.json`
- `demo/project03_parameter_package.json`

原始叶体证据：

- `project03_ae00_ad00_leaf_envelopes.json`
- `project03_ai00_leaf_envelopes.json`
- `project03_ag00_ah00_leaf_envelopes.json`
- `project03_ab00_ac00_leaf_envelopes.json`

## 5. 恢复开发后的推荐顺序

### 第一步：完成占用体与碰撞对分类

复用已采集的AB/AC、AD/AE、AG/AH、AI叶体，按工艺子树压缩为多包围盒。AJ00若确认属于外置普通供胶组件，首轮使用保守顶层AABB，不为其启动无必要的全叶采集。

将8个布局对象的28组对象对完整划分为：

- 普通实体关系：每侧膨胀1 mm的多包围盒严格分离；
- 龙门、传输、翻转、扫描及服务覆盖等框架/嵌套关系：允许宽相重叠，列入选案后的条件B-rep；
- 与AA00/AF00固定环境的支承安装关系：允许设计安装接触，但Replay后检查非法穿透。

求解阶段不得调用SolidWorks B-rep。

### 第二步：处理三项工程性部分证据

短期Demo可考虑把`+worldX/+installationV`操作侧作为项目03原型粗布局基线显式放行，但保留精确操作面和维护空间为生产债务。

载具条码/RFID差异可保留为非阻塞工程债务：维持薄型身份头原型位置，不虚构第二SR-X100或第二光束。

### 第三步：开放项目03 Top-3

按以下工程顺序求解：

`AA00固定环境 → AE00传输安装 → AD00双工作位 → AI00扫描 → AG00/AH00功能区 → AJ00供胶 → AB00/AC00反求公共覆盖`

快速生成3个通过相同硬约束的候选，只进入展示页目测，不自动Replay。

### 第四步：唯一选案后的CAD闭环

用户选择唯一候选后：

1. Replay到独立项目03装配体并另存；
2. 复测顶层模组变换；
3. 执行严格膨胀AABB；
4. 仅对宽相重叠且相对位姿变化的条件对象对执行叶级B-rep；
5. 保存、关闭、重新打开并复测坐标和干涉；
6. 若检出原型既有工艺接触，必须精确到零件实例和次数进行工程确认，不得扩大为整模组白名单。

## 6. 恢复时的首个动作

恢复项目03开发时，直接从“项目03多包围盒占用与28组碰撞对分类”开始。当前无需重新采集已完成的六个活动模组，也不应提前启动Replay或全量B-rep。

## 7. 2026-09-01 恢复开发状态

项目02“导出配合关系＋子装配体恢复原型”探索已经冻结，当前正式回转项目03。本文件再次成为项目03开发的主交接入口。

恢复核对结果：

- 关键JSON和四组完整叶体证据均仍存在，无需重新运行SolidWorks采集；
- 10/10模组CAD路径已解析，8个布局对象分组保持有效；
- 29条跨模组配合和9组连接已提取；
- 两个工作位、AI00扫描几何、AG00/AH00七个服务目标和AB00/AC00双阀覆盖均已接入参数包；
- 9/9工艺目标进入770×1100 mm粗公共范围，最小余量仍为6 mm；
- `missingRequiredEvidence=[]`、`partialEvidence=5`、`top3SolveReady=false`；
- 尚未生成项目03 Top-3、未Replay、未另存项目03目标装配体，也未执行项目03 B-rep。

恢复后的首个开发闭环固定为：

1. 将现有叶体数据按8个布局对象及工艺子树压缩为多包围盒占用体；
2. 枚举8个布局对象的28组无序对象对；
3. 分类为严格膨胀AABB、条件B-rep候选、允许安装接触三类；
4. 生成机器可读的项目03占用与碰撞策略JSON；
5. 增加单元测试和门禁校验，将`moduleOccupancy`、`staticCollisionPolicy`由`partial`推进到可用；
6. 再处理操作面/维护空间和载具条码身份的工程性部分证据，决定是否以原型粗布局基线显式放行；
7. 门禁满足后才开放Top-3展示，用户选择唯一候选前不进入SolidWorks Replay。

本轮恢复不会继承项目01/02的数值坐标、行程、扫码距离、接触白名单或模组占用体，只复用约束类型、分级碰撞策略和验证流程。

## 8. 2026-09-01 多占用体与28对碰撞门禁完成

本轮已完成恢复后的首个开发闭环，且全过程未启动SolidWorks、未Replay、未执行B-rep：

- 复用AB00/AC00、AD00/AE00、AG00/AH00、AI00四组既有叶体证据，共2203个实体包围盒；
- 按项目03工艺子树压缩为38个求解宽相占用盒；AA00/AF00作为固定安装环境、AJ00作为普通外置供胶对象，首轮使用顶层保守AABB；
- 8个布局对象的28组无序对象对已全覆盖：12组严格膨胀多AABB、9组条件B-rep、7组安装接触；
- 严格关系原型基线失败0组。AG00–AH00的子树并集发生保守预命中，自动降级到两侧叶体盒比较后命中0组，没有被误判为实体干涉；
- 9组条件关系在原型宽相中均有预命中，符合龙门门洞、输送/翻转嵌套、扫描靠近载具路径、阀头覆盖服务区等结构特征；它们只进入“选中方案Replay后”的叶级B-rep队列；
- 求解期B-rep调用数保持0。

新机器文件：

- `demo/layout_previews/project03_module_occupancy.json`
- `scripts/build_project03_occupancy.py`
- `apps/demo-backend/src/demo_backend/project03_occupancy.py`
- `apps/demo-backend/tests/test_project03_occupancy.py`

门禁决定：根据此前已授权的粗复原目标，显式接受`+worldX/+installationV`操作侧、AA00及服务簇容量、单束SR-X100与原型载具站位作为“项目03原型粗布局基线”。因此：

- `missingRequiredEvidence=[]`；
- `partialEvidence=[]`；
- `top3SolveReady=true`；
- `status=PROJECT03_TOP3_INPUT_READY`。

这些放行不等于工程确认。精确AA00操作面、维护空间、身份头究竟读取载具条码还是RFID、厂商扫码距离和实际双阀行程仍记录在`engineeringConfirmationDebt`，不得用于生产放行。

测试结果：

- Python后端完整回归152/152通过；
- 前端TypeScript检查和Vite生产构建通过；
- 展示页参数卡可显示8对象、28对、2203个叶实体包围盒及12/9/7分类；
- 本轮没有生成项目03候选装配体，也没有CAD实体无干涉结论。

功能修改意义：把“已有大量叶体数据”转化为可直接参与求解的低成本空间门禁，并将B-rep成本严格推迟到唯一选案之后；同时把估计基线与工程确认分层，使项目03首次Top-3能够开始而不会伪造厂商参数。

下一步：实现项目03专用顺序Top-3，遵循`AA00固定环境 → AE00传输 → AD00工作位 → AI00扫描 → AG00/AH00服务区 → AJ00供胶 → AB00/AC00反求覆盖`，先在展示层人工目测，用户选择前仍禁止Replay。

## 9. 2026-09-01 Top-3、唯一选案与Replay完成

项目03已从“输入就绪”推进到可保存、可重开的唯一方案实体闭环：

- 项目03专用顺序求解复用通用约束框架，但只加载项目03的模组、占用体、工作位、扫描几何、服务点和双阀范围；
- 快速搜索得到92个可行候选并保留Top-3，求解阶段B-rep调用数为0；
- 自主选择方案1：三项候选均通过硬约束，方案1总评分最低、总位移为0，并保持项目03原型工艺关系；
- 方案1是“通用约束求解得到的原型等价解”，并非绕过求解直接复制原型；当前证据和目标函数共同使原型位姿成为最优解；
- 8个求解对象已展开为10个主模组，连同原型5个辅助顶层件Replay并另存；主模组10/10，无缺失；
- 保存重开复测通过：15个顶层实例集合一致，10个主模组、5个辅助件，关闭前后最大变换元素误差约`4.0e-15`，文档无需重建。

目标装配体：

- `demo/project03/FL9A24D063A000_project03_solution1_v1.SLDASM`

主要机器证据：

- `demo/layout_previews/project03_solution.json`
- `demo/layout_previews/project03_preview.json`
- `demo/layout_previews/project03_selected_solution.json`
- `demo/layout_previews/project03_selected_solution_replay.json`
- `demo/layout_previews/project03_solution1_v1_replay_result.json`
- `demo/layout_previews/project03_solution1_v1_reopened_capture.json`
- `demo/screenshots/project03_solution1_v1_reopened.png`

功能修改意义：项目03首次验证了“案例专属证据 → 通用约束类型 → 快速Top-3 → 唯一选案 → 独立SolidWorks实体”的迁移路径，证明主线不再只对项目02有效。

## 10. 2026-09-01 分级干涉验证闭环

方案1按“严格AABB先行、条件关系精检、安装关系按位姿变化决定验证成本”完成验证：

- 12组普通实体严格膨胀AABB全部通过，失败0组；
- 9组条件对象对完成叶级B-rep，7组完全无干涉；
- `AE00–AD00`检出6个实体交叠，`AE00–AI00`检出2个实体交叠；逐体与原型复核后，两组的实体身份和次数均完全一致，新增干涉0个；
- 安装环境拆为AA00、AF00后共16个成员对，成员级包围盒直接排除5对、11对宽相重叠；
- AA00首个全叶布尔检查耗时过长且不能产生新信息，因此停止低收益重复计算。方案1全部模组位姿增量为0，目标文件又是原型Save-As副本，可严格推出安装穿透集合与原型相同，故以“原型位姿等价证书”判定无新增安装穿透；
- 最终状态为`PROJECT03_DEMO_BASELINE_EQUIVALENT_CLOSED`：Demo闭环通过、相对原型无新增干涉，但不宣称绝对零接触，也不宣称生产放行。

闭环证据：

- `demo/layout_previews/project03_solution1_v1_3d_screening.json`
- `demo/interference_project03_solution1_v1/conditional/`
- `demo/interference_project03_prototype/conditional_hits/`
- `demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AD00.json`
- `demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AI00.json`
- `demo/layout_previews/project03_solution1_v1_closure.json`
- `demo/layout_previews/project03_verification_plan.json`

当前工程债务：

- AE00–AD00的6个、AE00–AI00的2个原型既有交叠仍需机械工程师确认是否属于预期安装/工艺接触；
- 后续只要任一模组位姿增量不为0，就不得复用安装等价捷径，必须对宽相相交成员对执行精确B-rep或应用经工程师确认的实例级接触规则；
- 精确操作面、维护空间、厂商扫码距离和实际双阀行程仍未达到生产参数精度。

功能修改意义：将最昂贵的全量B-rep从固定流程改为“有新增几何风险才执行”，同时保留可审计的数学适用条件；这既显著降低原型等价方案的验证时间，也不会把原型已有接触伪装成零干涉。

测试结果：后端完整回归155/155通过，前端TypeScript检查和Vite生产构建通过。

下一步主线：以同一工作流迁移项目01、05、06；每个项目只补案例专属模组映射、安装基准、工艺点和占用体，不复制项目03数值。若候选位姿发生变化，则完整执行严格AABB、条件B-rep和安装成员对精检。

## 11. 2026-09-09 第二候选实体化

- 用户指定项目03 Top-3的rank 2后，将AH00沿安装坐标V移动-30 mm，其余求解对象保持候选定义位姿；该结果不是原型等价解。
- 已另存为`demo/project03/FL9A24D063A000_project03_solution2_v1.SLDASM`，未覆盖原型和方案1。
- 顶层审计为15个组件：10个主模组全部存在，另保留5个原型辅助顶层件。
- 保存关闭后重新打开，保存前后最大变换元素误差约`7.30e-9`，文档无需重建。
- 12组严格AABB对象对全部通过；9组条件B-rep关系和7组安装接触关系保持待验证。因此当前结论为“第二候选实体化与快速门禁通过”，不是“绝对零干涉闭环”。

功能修改意义：把项目03由只能交付原型等价方案1推进到可交付非首选、非原型等价候选，并验证选案位姿能够稳定写入独立SolidWorks装配体。

## 2026-09-30：增量CAD链推进到AD00

- 不再Replay完整原型：独立AA00+AF00建立基座，从非源初始位姿依次插入独立AE00和AD00，并由真实面配合恢复。
- AE00检查点：3/3配合、完全约束、保存重开、3/3对象对闭包通过；实体为`demo/semantic_ports/project03_AE00_first_increment_v1/step01_AA00_AF00_AE00_increment.SLDASM`。
- AD00静态检查点：3/3配合、完全约束、保存重开、6/6对象对闭包通过；实体为`demo/semantic_ports/project03_AD00_second_increment_v1/step02_AA00_AF00_AE00_AD00_increment.SLDASM`。
- 两步最大顶层Transform元素误差约`2.998e-15`，均未使用目标模组顶层原型位姿锚点。
- 项目03档案升级到`2026-09-30.3`：7个增量步骤中2个具备静态CAD证据，剩余5个。
- 阻塞：AD00的25°翻转扫掠未验证；AE00–AD00原型既有6组叶体交叠待工程分类；AI00尚缺安装端口与光学联合门禁。

下一步：恢复AA00–AI00顶层安装配合，把100 mm原型光束、AE00缓存扫码位和无遮挡作为验证关系；静态检查点通过后再进入AG00。

## 2026-09-30：AI00第三个真实增量CAD动作已闭环

- AI00从确定性非源位姿插入AA00/AF00/AE00/AD00累计检查点，未使用目标顶层位姿锚点。
- 第一轮5条源关系全部驱动导致两个同心配合过约束，143.860秒后由参数、完全约束和求解清洁门禁共同拒绝；失败实体未被发布为检查点。
- 第二轮采用3条驱动（重合8、同心31、同心32）和2条只验证距离（290 mm、10 mm），237.021秒完成CAD动作；保存重开、完全约束和参数一致均通过。
- 两个距离复测误差小于`2e-14 m`；5个顶层模组最大Transform元素误差`7.05e-15`。
- 10对对象中2对AABB严格分离，8对依赖相同源文件/相同相对位姿证明无新增穿透；AE00–AI00原型完整B-rep基线含2对既有相交，未把它误报为绝对零干涉。
- SR-X100的`+worldY`光轴和100 mm CAD光束代理保持，但厂商工作距离、真实条码面和载具身份头角色未确认，故生产门禁关闭。
- 项目03配置为`2026-09-30.4`：7步中3步具备静态CAD证据，剩余AG00、AH00、AJ00、AB00四步。

证据：`demo/semantic_ports/project03_AI00_third_increment_v1/step03_AI00_incremental_closure.json`；实体：`demo/semantic_ports/project03_AI00_third_increment_v1/step03_AA00_AF00_AE00_AD00_AI00_increment_v2.SLDASM`。

下一步：建立AG00安装端口，将固定安装驱动、6个服务目标和维护包络分成不同语义层；先完成静态增量实体，再根据工艺状态判断哪些服务目标需要动态检查。

## 2026-09-30：AG00第四个增量CAD动作已闭环（带显式残差锚点）

- AA00–AG00原型只有1个重合和1个同心。非源位姿诊断中2条配合本身均成功，但保存重开后AG00未完全约束，CAD确认剩余1个绕孔轴转动自由度；该145.240秒结果被拒绝。
- 第二版保留2条真实配合，并显式登记项目03原型顶层姿态为临时残差锚点；115.636秒完成独立插入，完全约束、求解清洁、保存重开通过。
- 六个工艺目标分离为只验证端口：清洁2、称重1、硬度测试1、排胶2；机械配合不再承担工艺点语义。
- 累计6模组最大Transform误差`7.05e-15`；15个对象对中5对AABB严格分离、10对以源文件/相对位姿等价证明无新增穿透。
- 项目03配置升级到`2026-09-30.5`，7步中4步具备静态CAD证据，剩余AH00、AJ00、AB00。
- 生产阻塞：必须以第二定位基准或防转方向规则替代原型姿态锚点，并确认服务点插入深度、维护包络和动态扫掠。

证据：`demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AG00_incremental_closure.json`；实体：`demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AA00_AF00_AE00_AD00_AI00_AG00_increment.SLDASM`。

下一步：恢复AA00–AH00安装关系，校准棱镜中心只作为工艺验证目标；先做自由度诊断，再决定是否需要临时残差锚点。

## 2026-09-30：有序增量链推进到10对象宏观静态闭环

已完成：

- AH00、AJ00各以3条基础配合完成独立增量插入、完全约束、保存重开；
- AB00以1条驱动重合、1条40 mm距离验证及显式残差锚点完成静态安装；
- AC00独立顶层插入、10对象根节点位姿和保存重开通过；最大根节点Transform误差`5.86e-14`；
- 45对顶层对象完成宽相，22对严格AABB分离、23对等待条件B-rep；
- 新增当前源码执行器独立构建目录`publish-current2`，支持无驱动静态快照和“配合前固定根节点”诊断策略；
- 新增机器闭环`demo/semantic_ports/project03_full_machine_increment_v1/project03_macro_static_closure.json`，多项目审计能区分宏观静态通过与完整几何阻塞。

AC00关键诊断：

- 原型子树134节点；独立文件在正确根位姿下仍有72节点不一致，最大平移差340.851 mm；
- 11个最小分支锚点可应用，但柔性和刚性顶层两种方案都不能在保存重开后固化嵌套状态；
- 先固定根节点再建立外部关系时，同心配合过约束；
- 因此当前问题不是顶层布局，而是父装配柔性状态缺少可移植表达。

当前状态：

- `macroStaticPassed=true`；
- `fullGeometryClosed=false`；
- `naturalLanguageOrderedCadPipelineReady=false`；
- 不执行23对发布级B-rep，不宣称零干涉。

下一步唯一主线：先导出AC00内部配合、抑制和柔性父上下文状态，优先编译命名工作配置；若不可行，则生成派生静态快照子装配体。134/134节点重开对比通过后，再执行23对条件B-rep和整链发布审计。

## 2026-10-01：AC00混合静态快照已替代错误内部状态

已完成：

- 全叶一次性构建因CAD无进展被安全终止；20件分批策略定位到两个只能在父装配上下文稳定加载的零件文件。
- AC20、AC30、AC40按原生刚性子装配保留，其余节点静态展平；34个快照节点覆盖118个源叶实例。
- 两批、总快照、三个刚性分支内部姿态均完成保存重开复核；分支比较共98个节点，全部稳定。
- 快照已作为第10个对象插入九模组检查点；新增对象完全约束，九个上下文根节点零漂移。
- 最终实体为`demo/semantic_ports/project03_full_hybrid_static_v1/project03_full_10_object_hybrid_static_v1.SLDASM`。
- 45对静态对象对全部完成：22对AABB排除，23对完成逐对B-rep；精检结果按对持久化并完成原型基线复核。

问题与阻塞：

- 当前快照保留完整静态几何，不保留AC00原始内部配合图、层级和运动语义。
- `FL5A24D063AC40006.01`与`24D063-KK50-AS2`存在独立打开关键数据修复错误；保留所属刚性子装配是当前可靠规避方案。
- 23对精检中17对为零干涉，6对仅包含原型已有安装接触；候选新增干涉为0。静态状态已升级为“完整几何、相对原型无新增干涉”，但不宣称绝对零接触。
- 生产路线仍需AC00命名工作配置或可移植柔性状态、AG00/AB00真实防转基准、AD00/AJ00动态扫掠和权威行程。

最终证据：`demo/semantic_ports/project03_full_hybrid_static_v1/interference_closure.json`；目标实体：`demo/semantic_ports/project03_full_hybrid_static_v1/project03_full_10_object_hybrid_static_v1.SLDASM`。项目03档案和多项目审计已刷新，静态自然语言有序装配链具备完整证据。下一阶段只处理生产动态债务：AC00可移植柔性状态、AG00/AB00真实防转基准、AD00/AJ00动态扫掠和权威行程。

## 2026-10-01：单一持久化七步现场链已取代分段接续状态

- 当前权威作业为`demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/job.json`，不再以分段尾部实验作为发布依据。
- 七步动作在一个作业内从固定基座累计执行；AB保存重开故障修复后从最后检查点恢复成功，未重跑前六步。
- 最终装配体为`demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/cad-working/step-07-ab00-attempt2/step07b_project03_full_10_object_hybrid_static.SLDASM`。
- 最终10对象45对独立静态门禁全部通过；机器闭包为`demo/semantic_ports/project03_live_adapter_full_jobs/project03_full_live_adapter_closure.json`。
- 项目03完整七步API/UI已经开放；总耗时及失败恢复成本已单独记账。

仍未解决：AG/AB真实防转基准、AC00内部柔性语义、AD00翻转扫掠、权威行程/光学/软管/维护参数。静态闭包已完成，但生产动态闭包仍是下一阶段。

功能修改意义：交接基线从“完整几何可拼装”升级为“自然语言七步可在真实CAD中累计生成、失败可恢复、最终45对可审计”，后续不应再从旧分段工件继续开发。

## 2026-10-01：AG00/AB00临时锚点已改为版本化项目参数

- 两个目标的临时姿态不再在执行时隐式读取配合图中的原型顶层`SourceTransform`，而从`project03_calibrated_parameters_v1.json`显式注入。
- 原型顶层位姿扰动消融通过；AG00和AB00分别从AI00、AJ00检查点完成真实CAD插入、保存重开和约束验证。
- 机器闭包状态为`PROJECT03_RUNTIME_POSE_DEPENDENCY_REDUCED_CAD_VALIDATED`，总CAD动作耗时261.148秒。
- 该改动只降低运行时依赖。参数来源仍为原型标定，`engineeringConfirmed=false`，生产状态保持关闭。

下一阶段：AD00 25度扫掠、双阀动态覆盖、AJ00软管/维护包络；之后才用真实机械基准替换AG/AB临时参数。

功能修改意义：剩余原型依赖已经从隐藏行为转为显式、带哈希、可替换的项目参数，不再需要修改执行器代码才能接入未来厂商基准。

## 2026-10-01：AD00三组真实配置状态已完成隔离实证

- AD20配置清单确认`0度`和`25度`为真实CAD配置；左右三态均成功切换并产生预期几何变化。
- AA00、AB00、AI00的局部碰撞门禁通过；AE00在隔离装配中出现接触，但原型基线已有AD20–AE00接触，且隔离装配没有保留AE00柔性父上下文。
- 当前正式判读为`PROJECT03_AD00_CONFIGURATION_STATES_VERIFIED_FULL_CONTEXT_BASELINE_RECHECK_REQUIRED`；不得将隔离AE00结果直接解释为布局失败或动态安全通过。
- 原始闭包与判读文件均位于`demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v4/`；项目档案版本为`2026-10-01.9`。

下一阶段只做完整上下文验证：先复制AD10/AD00/最终装配体构造`0°/0°`状态，复现原型AD00–AE00叶级接触身份；只有基线完全可复现，才继续左右25°状态和连续扫掠。所有复制文件必须位于独立证据目录，源文件前后哈希不得变化。

功能修改意义：交接边界已从“尚无真实25°状态”推进到“离散状态真实，但必须解决柔性父上下文的基线复现”。

## 2026-10-01：AD00完整上下文三状态闭环已通过

- 直接基线、`0/0`、`25/0`、`0/25`均在最终十对象上下文完成全叶精检；三状态都只含同一1对已知AD00–AE00接触，无新增叶级实体对。
- 所有状态均由独立副本构造，源AD10、AD00和最终装配体SHA保持不变；构造与验证使用不同SolidWorks会话。
- 机器闭包：`demo/semantic_ports/project03_ad00_three_state_full_context_closure_v1.json`；状态`PASSED_PROJECT03_AD00_THREE_DISCRETE_FULL_CONTEXT_STATES`。
- 项目03档案为`2026-10-01.10`，离散端点门禁关闭，生产动态门禁仍关闭。

下一阶段：以5至9个中间角度或保守扫掠包络验证0°到25°连续路径；缺少厂商限位时必须标记为原型估计。不要重复三端点B-rep，也不要把端点通过表述为连续运动已放行。

功能修改意义：动态债务已缩小为连续路径、权威限位和安全间隙，不再包含真实配置、完整上下文或端点碰撞的不确定性。

## 2026-10-01：连续扫掠接续边界

- 保守扫掠代理已按1°采样生成，候选仅为AA00、AB00、AE00、AI00，共7项工作位—模组关系。
- 真实CAD只有0°与25°配置；中间角度尚不能由配置直接验证。下一阶段必须引入权威转轴/限位，或明确标记为原型估计的受控运动叶体变换。
- 全仓回归已收口：后端587项+3 subtests、前端构建、桥接层84项目标测试全部通过。

功能修改意义：交接人应直接实现连续中间态适配器，不再重做离散端点、直接上下文基线或全仓夹具修复。
## 2026-10-02：AD20 上下文校正中间态闭环（交接更新）

### 已完成

- 修复嵌套组件层级路径重复问题，新增总变换读取、任意层级刚柔性切换和轻量化解析能力。
- 证明旧柔性全上下文0°和25°捕获结果实际上相同（运动叶数为0），因此旧三状态闭包不能作为动态安全依据。
- 用完整上下文0°位姿与原生配置运动增量重建六个刚性状态：0/5/10/15/20/25°。
- 每个状态均完成：29叶快照（0°左右双侧58叶）、AD10父装配固化、十对象整机替换、保存、干净进程恢复、位姿逐项复测、条件叶级 B-rep、源文件哈希不变检查。
- 结果：0/5/10/15°无新增干涉；20/25°失败。机器汇总位于 `demo/semantic_ports/project03_ad20_context_rebased_dynamic_closure_v1.json`。

### 问题

- 20°：`FL5A24D063AD20002.01` 与 `24D063电气-FL201AB-00181(2)` 新增1个实体干涉计数。
- 25°：上述干涉增至2个计数，并新增 `FL5A24D063AD20002.01` 与 `FL5B24D063AE43001.01` 的1个干涉计数。
- 0°刚性基线比历史柔性原型少2个旧接触计数，因此只采用“不得出现新增叶源对”的安全子集判定，不把柔性接触缺失误判为失败。
- 构造会话内立即关闭并重开可能使 SolidWorks 退出；独立干净进程可恢复、复测和精检，构造清单中的 `ERROR` 不等于实体证据丢失。

### 阻塞点

- 0°–25°当前不是无碰撞行程；连续路径尚未证明。
- 缺少厂商确认的转轴、硬限位、速度、最小安全间隙和允许接触类别。
- 15°只是最后一个已通过的离散采样点，不能直接作为生产安全限位。

### 下一步

先把20/25°失败接入发布硬门禁；随后对15°–20°做局部加密采样和连续扫掠，仅检查已识别的碰撞候选；若需求必须达到25°，需修改结构/相对布局后重跑。所有新结果继续采用“独立目录、副本构造、保存重开、位姿复测、条件 B-rep、源哈希不变”的证据契约。

功能修改意义：交接基线已从错误的柔性端点证明切换为可复查的刚性中间态证据，系统会拒绝不安全动态方案，而不是生成后再靠目测纠错。

闭环测试：脚本语法检查通过；刚体变换5/5；完整后端592项及3个subtests；桥接层Assembly/Document/AppBootstrapper目标测试90/90。

## 2026-10-02：自然语言动态请求硬门禁（交接更新）

- 新增 `project03_dynamic_release_gate.py`，对受控中文命令中的AD20离散姿态/连续动作进行证据判定。
- 更新 `project03.json` 至`2026-10-02.1`，旧三状态闭包明确标记为superseded，权威引用切换到上下文校正六状态闭包。
- 计划预演、作业创建API和前端门禁卡片已贯通；拒绝发生在SolidWorks排队前。
- 命令级证据：`demo/semantic_ports/project03_dynamic_command_gate_demo_v1.json`；预期四案全部符合：静态通过、15°离散通过、20°离散拒绝、0°→15°连续拒绝。
- 回归：完整后端599项+3 subtests，前端生产构建通过，桥接层90/90。

问题与阻塞：没有任何连续翻转命令获得生产放行；需要先取得连续扫掠证据。当前解析器是受控规则，不是任意自然语言运动规划器。

功能修改意义：项目03已经具备“命令—证据—发布判定”的动态安全闭环入口，后续几何实证可数据化升级门禁，无需再次改造作业编排骨架。

## 2026-10-02：AD20首碰加密（交接更新）

- 新增16°全上下文刚性状态；29叶位姿误差最大约`8.88e-16`，B-rep新增1个叶对，整机离散首碰区间为`(15°,16°]`。
- 新增局部双零件精检脚本 `run_project03_ad20_first_contact_pair_refinement.py`；目标固定为AE43-2分支第7电气件与AD20002-1运动件。
- 0.1°采样结果：15.0–15.5°零干涉，15.6–16.0°每点1个干涉；证据路径为`demo/semantic_ports/project03_ad20_first_contact_pair_refinement_v4/project03_ad20_first_contact_pair_refinement.json`。
- 聚合闭包为`project03_ad20_context_rebased_dynamic_refinement_closure_v1.json`，项目档案版本`2026-10-02.2`。

问题与阻塞：局部夹具仅定位已知叶对首碰；不得用它放行整机连续动作。要实现25°必须先取得可修改结构/位置的工程授权与厂商运动参数。

功能修改意义：后续整改可以先用两零件夹具快速筛选，再只对通过候选做整机复核，显著降低SolidWorks长链迭代成本。

调试记录：局部夹具v1只按文件名选择，命中14个重复实例；v2把父分支误写到`Name`条件，命中0个；v3仅加叶实例号仍命中AE43-1/AE43-2两个实例；v4使用`HierarchyPath`父分支+末端实例号唯一解析成功。前三次均在B-rep前停止，没有修改源文件。

闭环测试：完整后端600项+3 subtests、桥接层90/90、前端生产构建通过；动态证据累计记录6933.920秒。
