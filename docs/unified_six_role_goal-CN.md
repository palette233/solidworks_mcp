# 六类跨项目累计装配统一入口 Goal

启动：2026-10-28。当前状态：本Goal规定的统一入口、代表性累计链及异常测试验收完成。逐项依据见`docs/unified_six_role_acceptance-CN.md`；操作见`docs/unified_six_role_operation-CN.md`。不代表全部68项工位组合已完成，57项未覆盖清单继续保留。

## 目标与边界

在Project01/02/03/05当前登记六类范围内，根据已确认模组、目标基座及工位要求，通过同一入口选择接口、生成配合参数并完成真实累计装配。新增组合以补配置数据为主，不增加逐案例专用装配脚本。

六类为：基座、传输、扫描、校准、清洁/称重、排胶/废胶。Project06、CCD/龙门/供胶扩展、A700内部机构和新前端不在本轮。碰撞/B-rep、真实紧固、实际扫码/排胶与生产放行不是本轮完成条件。

保持既有CAD执行器、端口/面目录、配合图、发布与持久编排；只固定基座，目标从非原型初始位姿插入，不以根/叶位姿锚点补约束。允许有来源和坐标定义的原型测量/估计；不静默复制来源原型世界位姿。

## 完整验收清单

| ID | 必须交付/验证 | 当前状态与证据 |
|---|---|---|
| S1 | 冻结六类型号、基座范围，区分接口、工位、实验及缺口 | scope-v8：4基座、17移动模组、68精确配对；63当前接口权威、12配置工位、11项规则绑定实体验证（4项绑定新Demo发布、7项累计实体复核）；57项尚未达到该工位验证口径，不能混算全目录覆盖 |
| S2 | 工位/功能点/区域与定位规则可登记，新增组合主要补数据 | registry-v11登记12项规则及一个位置参数变体；11项绑定实际实体后验，杯口支持分离捕获坐标；其他未登记配对保留缺口，不能宣称全目录完成 |
| S3 | 普通累计入口自动选择、推导、执行、运行后复核及检查点 | 已接通同一CLI的compile/run/resume，V1五包均独立重开、复核当前工位后提交检查点；CAD成功而后检失败时仅重试后检，不重复插入 |
| S4 | 换型/换基座/改参数重算关联，多实例明确消歧 | 三条整链覆盖换型/换基座，参数变体已真实复用。扫描逻辑实例已接入前置检查点证据与当前CAD组件名绑定；101项专项通过，四条既有链的真实保存证据复算通过。重复型号多实例的完整CAD插入尚未实测，不能外推为已支持任意多实例链 |
| S5 | 合格新Demo配方进入正常发布选择，保留执行类型 | GN00/P000→AA00、AG00/P000→JJ00新Demo配方在完整链复用；BD00→JJ00补精确直接接口；GN00+10mm参数配方发布后普通入口真实复用通过。类型不升级为机械紧固兼容 |
| V1 | 当前六类方案从空白基座构建 | 已完成full-chain-v1：AA00/SS00/AI00/BD00/GN00/P000，6组件15顶层配合，仅基座固定，五包当前工位通过；完整工艺未知 |
| V2 | 同一基座至少替换一种同角色模组的六类链 | 已完成full-chain-v2-ah00；AH00替代BD00，五包保存重开及工位通过，6组件15顶层配合，仅AA00固定；最终重开警告位1，实际工艺未知 |
| V3 | 另一种基座上的六类链 | full-chain-jj00-v2五包完成：JJ00/SS00/SM00/BD00/AG00/P000，1087.336秒，6组件15激活配合、仅基座固定；五包工位及全链连续性通过。三组总体覆盖2基座、3来源项目，最终打开警告32保留 |
| V4 | 合法变序与位置参数变化 | GN00+10mm新CAD及11项参数对比通过；变序链五包完成，10项最终状态对比一致。新发布经普通入口再次执行成功，506.412秒，工位后检及检查点提交通过；此次复用为基座加GN00两组件，不冒充新增六模组链 |
| V5 | 暂停恢复、失败后继续 | V2首包真实暂停；第二包启动前注入失败后恢复并完成整条五包真实CAD，不重插首包。记录见full-chain-v2-ah00/run-attempts |
| V6 | 缺工位、关联歧义、证据失效负例 | 当前v11下A800→AA00缺规则拒绝；重复传输实例使扫描DEPENDENCY_AMBIGUOUS；+10mm旧发布拒绝。规则/计划/保存状态/实体摘要失效测试通过，汇总见验收报告 |
| A1 | 每包身份/参数、非原型、真实激活配合、外部约束、保存重开、原上下文保全、声明几何条件 | current-chain-audit-v1.json以当前代码重算四条链20包，全部通过；非原型依据实际执行诊断与无锚点审计，不冒称捕获了初始数值矩阵 |
| D1 | 统一命令/示例、实体、覆盖报告、测试及耗时、剩余缺口 | 操作指南、逐项验收报告、scope-v8逐项缺口、实际文件SHA/路径、分阶段时间及日志齐备；文档示例重新compile验证成功 |

## 执行安排

1. 当前权威范围审计；把接口发布与目标工位规则分开计数。
2. 将已验证服务区、杯口与扫描关联提取为有来源的数据，保留旧命令兼容。
3. 在现有普通累计入口增加规则选择、当前上下文绑定及运行后复核，保留正常发布授权和暂停恢复。
4. 依据现有真实证据发布新Demo配方，并选择至少三条有区别的六类输入清单。
5. 串行执行CAD、变序/改参/恢复测试，逐包取证；不并发操纵SolidWorks。
6. 对照上表审计全部要求；未完成项不得通过缩小Goal范围消除。

## 既有成果的使用方式

`demo/role_station_strengthening_20261028/functional-chain-v1/`是可信的4→5→6实验证据：6组件15配合、目标代理几何通过，完整工艺未知。它可用于提取规则和建立新配方证据，不算本Goal的三条新统一入口六类链。

原有暂停恢复、接口选择、参数语言解析等能力保留，不重复开发。新规则和新运行分别计时，不把离线计算或历史装配重开算作新的CAD构建。

## 阶段记录

### 2026-10-28 14:50 第二基座整链完成

- full-chain-jj00-v2完成五包，14:31:35—14:49:43，1087.336秒。最终6组件、15激活配合，仅JJ00固定、五个新增模组完全约束；打开错误0、警告位32保留，不宣称零警告。
- 当前工位五包均通过，完整工艺未知；全链前驱/非原型/保存重开/上下文连续性离线重验通过（0.343秒）。详细文件、SHA与各包耗时见该目录README-CN.md。
- 现已取得三组不同六类链与额外变序链。仍需完成参数变体普通入口执行、最终逐项审计和交付汇总，不能立即标记Goal完成。
- 在确认原CAD执行进程终止后，串行启动gn00-plus10mm-released-compile-v3普通发布复用（会话15420），不是重跑JJ00链。

### 2026-10-28 14:48 已有累计实体绑定至工位规则

- registry-v11将7项传输、扫描、校准规则绑定到已经提交的实际累计CAD、独立重开和工位计划，状态为experimental_cad_verified；这不改变其原有机械执行发布，也不把其升格为新参数化Demo发布。
- scope-v8重新验证后：12配置、11实体规则验证，其中4项绑定新Demo发布、7项累计证据；总68配对的57项仍缺该工位验证。`experimentalEvidenceOnlyPairCount=7`仅指本层工位证据登记方式，不意味着其底层机械接口没有发布。
- 新请求chain-jj00-six-role-v4使用registry-v11通过统一plan-stations，5/5就绪，5.692秒；只是离线规划，不另开CAD。正在运行的v3链继续使用不可变registry-v10，四包已提交，末包P000正在执行。

### 2026-10-28 14:44 tests-v8全后端回归完成

- tests-v8完成：2319 passed、3 subtests passed，643.00秒，JUnit见`demo/unified_six_role_goal_20261028/tests-v8-junit.xml`。
- 收集后新增的薄入口包装测试已单独随直接编译器5 passed（0.41秒）；累计日志事件更新已随入口30 passed（0.97秒）。不把这两次专项伪装为包含在tests-v8快照内，也不需要为仅日志变更重新运行实体装配。
- JJ00清洁/称重包保存完成，重开验证仍进行；只有前三包提交完成。保持现有CAD执行会话78358，禁止重复启动。

### 2026-10-28 14:42 换型与变序的全链连续性审计

- 使用既有`build_functional_chain_closure.py`重新核对full-chain-v2-ah00与full-chain-reordered-v1的全部5包：实际前驱SHA、非原型插入、真实配合、保存重开、源文件和已有上下文保全均通过。报告分别为各目录`cad-continuity-audit.json`，耗时2.818秒、1.859秒，未运行CAD。
- 此报告仅审计CAD连续性，`proxyGeometryPassed=null`和`functionalPassed=null`；每包工位代理验证仍以相应station-postcheck及原始postcheck为准，不因requiredRoles空列表而声称完整工艺通过。
- JJ00链s03校准CAD作业120.932秒，独立重开与工位后检文件已生成并提交stage-closure；全链尚待清洁/称重、排胶杯。本次读取日志已核实进程仍运行，没有重启任务。

### 2026-10-28 14:40 扫描关联通过与日志阶段澄清

- JJ00链s02-scanner真实CAD执行约106.925秒，随后独立重开56.531秒，当前工位后检`cadPassed=true`、`proxyGeometryPassed=true`、`functionalPassed=null`；检查点已提交，进入s03-calibration。原始阶段stdout的succeeded仅表示CAD作业成功，不能提前表述为后检成功。
- 普通入口后续运行新增`cad_job_finished`和`stage_checkpoint_committed`两种日志事件，并记录`checkpointCommitted`、后检待完成标志、包含后检的总阶段耗时。保留原durationSeconds含义，不反向伪造当前已在运行进程的计时字段。
- 相关30项测试通过（0.97秒），包括事件顺序、未提交/已提交状态及总阶段耗时关系。该修改晚于当前整链启动和tests-v8收集，完整回归与专项证据分别报告。

### 2026-10-28 14:36 运行观察与覆盖清单刷新

- 现有CAD执行会话78358仍运行，s01-transport已成功提交检查点（157.086秒）；继续原任务，不重复启动CAD。全后端会话98968仍运行，不将中间百分比计为通过。
- scope-v7由当前registry-v10重新生成，11.056秒：68精确配对、63接口权威、12配置工位、4规则绑定发布验证。64项尚未达到这一更严格的规则绑定验证口径，不代表64项完全没有历史实体证据；清单逐配对给出缺口。
- 增加薄JSON候选入口的包装回归，确认计时不污染摘要、生成包可被发布器重读、已有目录拒绝覆盖。直接编译器5 passed，0.41秒；该新增测试晚于tests-v8收集，需与全量结果分开标注。

### 2026-10-28 14:32 BD00/JJ00补证发布，第二基座整链运行

- 修正契约层“同发布即可复用”的误推断：旧r9引用在BD00/JJ00契约中标明geometryProvenanceOnly，必须有精确配对发布才视为可执行；其他既有精确配对授权保留。
- 增加薄JSON命令`compile_direct_interface_candidate.py`调用原通用编译器，不新增逐组合装配算法。配置`bd00-jj00-direct-candidate-v1.json`明确源文件、端点和基座；生成包重读验证摘要，计时独立保存。
- BD00/JJ00真实CAD89.732秒，独立重开31.168秒，2组件3激活配合、仅基座固定、目标完全约束且无锚点。首次独立复核因默认配合名不适用而失败，改用实际名称重查通过，未重插模组。实体与全部证据见`demo/unified_six_role_goal_20261028/jj00-bd00-cad-v1/`。
- 新精确发布`relation-direct-project01-bd00-project01-jj00-d6a780341f7b`已接入契约生成器；更新新版本工位规则与registry-v10，不改旧已用规则。接口/契约/发布/工位联合131 passed，15.28秒。
- 新请求`chain-jj00-six-role-v3.json`编译5/5通过，5.025秒。`full-chain-jj00-v2`开始真实累计CAD（会话78358），顺序SS00→SM00→BD00→AG00→P000；尚未取得整链完成结论。并行离线全后端回归tests-v8正在执行，不能提前算通过。

### 2026-10-28 14:25 精确驱动授权前检修复

- 自动接口发布解析现在重新认证不可变发布，并要求授权驱动模板的端口拥有者与所选双方模组精确匹配。模板仅存在于目录、未被授权，或者授权属于另一配对，均返回`released_pair_driving_template_missing`，不启动CAD。
- BD00→JJ00旧r9目录误报已就绪的问题已在统一接口权威入口阻断；未修改旧发布，也未将历史七模组插入结果冒充本轮非原型证据。第二基座完整链仍未完成，下一步补该精确配对的新验证和发布，再以新chainId重编。
- 增加真实旧配对拒绝、未授权模板拒绝、授权其他基座拒绝测试。合成F000单元测试显式模拟认证边界，不放宽生产认证器。接口前检与工位规则联合56 passed，6.11秒。
- 本次仅离线开发测试，没有运行SolidWorks。已有JJ00的AG00/P000独立验证结果不变；不能把它们当作已完成六类累计链。
- 随后加入参数化定位编译器的联合回归：87 passed，10.57秒（14:24:35启动）；这是本次代码专项验证，不替代完整后端回归或真实CAD验证。

### 2026-10-28 14:17 完整链编译发现旧校准授权缺口

- full-chain-jj00-v1在s03-calibration编译阻断，NO_COMPATIBLE_PORT_PAIR，整链未启动CAD。此前两包只生成计划，不是已装配。
- 查明calibration契约构建脚本将BD00→JJ00证据指向relation-v9，但该发布authorizedDrivingTemplateIds仅含GN00相关及SS00驱动关系；工位前检错误地信任了配对目录的就绪标记。普通自然语言执行层仍正确拒绝。
- v50虽名称含calibration，实际授权AH00→JJ00，不是BD00，不能按发布名称替换引用。下一步核对BD00历史真实闭环和可发布模板，修正精确授权检查/数据，再重编整链；不绕过、不固定组件、不以更换型号掩盖缺口。

### 2026-10-28 14:16 第二基座六类链编译

- AG00→JJ00候选完成：CAD90.614秒、独立重开52.443秒，总143.185秒；当前服务区域代理验证通过，工艺未知。已发布relation-station-ag00-jj00-20261028-v1，摘要6561380e917b6d6b203eee352a9a1ac4bf5c33736bcb6312a0bbfd8d1224dc64。
- station-rules-v9同时登记JJ00清洁和杯口新发布，chain-jj00-six-role-v2使用统一入口编译。目标链JJ00/SS00/SM00/BD00/AG00/P000覆盖Project01/03/05，完整累计实测尚待。
- P000普通发布计划无预生成validationPackage的后检已通过（released-plan-postcheck.json），验证运行后重新构建配合图时仍保留横向翻转；这是复核已有实体，不另计新CAD构建。

### 2026-10-28 14:14 JJ00排胶闭环通过并发布

- jj00-p000-cad-v1完成：CAD125.166秒、独立重开62.065秒，总187.346秒，源/图不变；当前verify-station通过CAD与杯口投影，functionalPassed=null。
- 已发布relation-station-p000-jj00-20261028-v1（摘要65263ca341042ba903f882b3d0fc55f21b7f66548de941bc645dfadfebee8e8d），station-rules-v8登记规则证据。普通compile入口自动绑定成功（6.027秒，ready_not_started），未把编译就绪当成累计实测。
- 方向参数同样接入普通运行后的重编译复核路径，避免无预生成validationPackage时回到旧方向。方向非法输入、实际配合图和规则相关联合70 passed（5.69秒）。
- 下一候选jj00-ag00-cad-v1已串行启动，尚在执行。第二基座完整六类链仍待清洁配方通过并登记后执行。

### 2026-10-28 14:10 JJ00杯口参数贯通与方向修复

- 原型测量v2通过（58.258秒，部分引用/轻化状态如实保留，非CAD验收）；P000/JJ00严格重开通过（39.475秒，2组件3配合，警告0）。四杯报告完整状态绑定成功（0.700秒）。
- 推导位置为纵向0.5440824749305696m、横向0.47100000000002495m、支承0；平面匹配残差3.33e-16m，杯口高度差71.5mm，三维中心不重合。等高/实际排胶未作为本轮验收，不宣称工艺通过。
- 新增cup-p000-jj00-v1规则与station-rules-v7注册表、单包候选输入，复用统一plan-stations入口。发现旧编译接口遗漏距离跨基准面时的翻转；补充显式三布尔方向参数，在实例化模板前写入槽位参数副本，历史目录不变。
- 新增真实编译回归验证lateral=true确实写入effectiveGraph；初次测试抓到“仅报告翻转、实际图仍False”，已修复并通过。旧v1/v2候选未执行，v3才是待验证候选。此前专项65通过，最终修改后仍需联合回归。
- 已启动jj00-p000-cad-v1，使用现有候选执行器与SHA绑定源/图；只固定JJ00、无根/叶锚点，随后保存重开和当前杯口后检。尚无CAD通过结论。

### 2026-10-28 原型缺引用测量与CAD验收分离

- 增强诊断确认fileExists=True、documentReturned=True、openErrors=2、warnings=0，不能将其描述为原型主文件不存在。仅对原型局部测量增加显式双开关容错；必须核验指定目标/基座解析状态、源文件和有限变换，记录部分引用状态，不证明完整原型通过。
- 未指定CaptureOnly时该容错参数在连接CAD前即拒绝；真实CAD验收仍拒绝错误码。CLI防误用与杯口专项48 passed（3.96秒）。正在执行显式原型测量，尚未产生成功证据。

### 2026-10-28 06:37 四杯几何采集完成

- P000/JJ00两杯扫描全部成功，各17面，130.26秒与127.00秒；结束后恢复文档基线，连带打开的基座引用零件也由既有清理器关闭，没有保存源文件。
- geometry-only-report.json由现有杯口解析入口生成，四份目录均存在解析杯口证据（0.011秒）；该报告不含stationSuggestion，不代表位置配方已形成或工位已通过。
- 全部扫描结束后，使用增强诊断的同一CaptureOnly入口复核原型打开问题。尚缺原型及来源双模组的保存状态绑定，目标参数推导仍不得验收。

### 2026-10-28 06:33 原型状态读取异常诊断

- 原型CaptureOnly读取退出1，OpenDoc6报告错误2（本地swconst枚举swFileNotFoundError），未产生状态报告；不能将两份成功面目录替代缺失的保存状态见证。
- 同一路径先前有界面扫描成功，尚不足以判断是主文件或引用问题。增强既有只读脚本错误信息，附带warnings/documentReturned/fileExists/path，不改变拒绝条件；PowerShell语法解析通过。
- 已串行启动P000/JJ00来源杯1采集。未同时启动另一CAD操作、未结束用户进程，后续在采集结束后继续诊断原型状态读取。

### 2026-10-28 第二基座杯口测量继续与负向证据核对

- 原型GN00第一杯有界扫描完成，17个面端点，172.907秒：连接2.986秒、扫描133.624秒、清理36.278秒。未请求保存源文件，文档基线恢复成功；证据为jj00-cup-measurement-v1/gn00-cup-1.json及其timing.json。
- 第二杯继续串行采集。上述只读面目录用于分析JJ00原生杯口工位，不是新候选装配验收，也不授权使用原型世界位姿固定新增模组。
- 失效计划实测：negative-stale-plan-v1.json仅在隔离副本中将planDigest置为失效值，统一verify-station入口以STATION_PLAN_CHANGED拒绝，未启动CAD且未生成通过报告。原始计划和CAD证据未改动。
- V2完整链已完成，修正验收表V5遗留的“尚在运行”措辞；不改变历史运行记录。
- tests-v7完整后端回归已结束：2305 passed、3 subtests passed，457.55秒，JUnit见tests-v7/backend-junit.xml。该运行启动后新增compare-states入口及3项专项测试，另有35项比较器/入口专项通过；不将全量结果误称为已覆盖启动后新增的全部代码。
- 随后对当前版本的累计入口、状态比较、杯口和工位注册表联合回归：120 passed，4.31秒。首杯解析得到一个杯口候选（内半径34mm、外沿34.5mm），叶路径为GN00内FJ00/FL00002-00549-1；解析结果仅用于测量，未执行新装配。
- 已准备jj00-cup-measurement-v1/cup-function-point-request.json，显式分离原型GN00与P000/JJ00历史双模组的状态证据；待其余面采集和两份只读状态完成后执行，不能将该输入文件视为已验证工位。
- 第二杯扫描成功，17个面端点、153.20秒，文档基线恢复成功。两只杯解析内半径均34mm，模块局部中心沿Z相差130mm；这只是原生工位测量，尚未证明P000放置匹配。随后串行启动原型CaptureOnly状态采集，用于绑定保存文件与组件位姿，未启动新装配。

### 2026-10-28 06:24 变序链完成且最终状态等价

- full-chain-reordered-v1五包全部完成，1007.506秒（含逐包独立重开/工位后检），6组件15顶层配合，仅AA00固定，最终重开警告位1；顺序为校准→传输→清洁→杯→扫描。
- 同一compare-states入口与V1最终状态比较10项全通过，位姿、刚柔配置、配合参数一致；不是只凭组件数量判断变序等价。详见变序目录README与order-comparison.json。
- 三条当前新完整运行均在AA00（原顺序、AH00换型、变序）；Goal另基座要求仍未满足。已串行启动JJ00原型GN00第一杯叶扫描，句柄7477，尚未报告结果。

### 2026-10-28 06:23 统一状态比较入口与参数变化证据

- 同一CLI新增compare-states薄入口，直接复用datum_chain_verification比较器；先核验两份状态所绑定的真实装配体SHA，拒绝CaptureOnly，再比较组件、配合和显式预期参数。没有新增装配执行器。
- compare-gn00-plus10mm-v1.json实测报告parameter-comparison.json成功：11项检查通过，只有GN00按基座局部+X移动10mm，其他组件位姿/刚柔配置和原有配合保全；允许三条新旧模板配合名显式一一映射，不按名称近似猜测。新增入口与既有比较测试35 passed（2.97秒）。
- 变序扫描末包CAD203.471秒成功，等待独立重开和当前扫描目标代理后检。tests-v7全量仍运行，开始后仅新增compare-states薄入口；最终应结合此次专项并明确快照边界。

### 2026-10-28 06:19 全目录覆盖刷新

- scope-v6实际运行26.382秒：4基座、17移动模组、68精确配对，63项执行权威，11项规则配置，2项规则绑定发布验证；参数变体不重复计为新配对。66项尚未达到规则绑定发布验证口径，不代表这66项都没有任何历史CAD。
- 变序杯包当前工位后检通过，扫描末包执行中。tests-v5完整回归2297 passed、3 subtests passed，495.57秒；该轮开始后新增代码仅有专项验证，最终代码仍需一次全量回归。

### 2026-10-28 06:17 默认配方回归与原型只读测量准备

- registry-v6默认六类请求5/5准备通过，2.420秒；GN00仍自动选择relation-station-gn00-aa00-20261028-v1，requiresFreshCadValidation=false。+10mm选择独立新发布，二者不覆盖，证据在default-recipe-regression-v6及gn00-plus10mm-released-compile-v3。
- 复用verify_p000_support_demo_state.ps1增加CaptureOnly开关，读取原型时只要求文件未改变、只读、所选模组唯一；单独输出assembly-measurement-readonly-state/v1和cadAcceptanceEvaluated=false，不要求原型满足新装配的固定/配合条件。完整闭环明确拒绝这种仅测量快照替代CAD验收。PowerShell语法解析通过；闭环/杯口/规则111 passed（5.69秒）。尚未现场运行原型测量模式。
- 该改动为第二基座GN00原生杯测量服务，不改变新增模组必须真实配合定位的验收条件。变序CAD及早期启动的完整回归仍运行，等待空闲后串行采集。

### 2026-10-28 06:14 多参数配方接入普通入口

- registry-v6新增parameterRecipes登记+10mm变体；规划器在默认授权不匹配时才查找精确参数变体，重算其原计划的真实工位后验并校验发布CAD摘要。规则、参数、几何、发布不匹配或重复候选均拒绝；旧默认配方保留。
- 普通compile输入candidate-aa00-gn00-plus10mm-released-v1.json成功，6.030秒，产物gn00-plus10mm-released-compile-v3，ready_not_started、targetStationPreflightPassed=true、targetStationValidated=false。本次编译不算新的CAD执行；前述参数变化真实CAD仍由独立候选流程完成，正常发布入口执行待后续串行验证。
- 失败历史保留：首次“沿纵向增加10毫米”被现有NL层识别为standalone distance而非安装，拒绝模板；第二次使用相同chainId碰到上下文已存在保护。第三次使用新chainId和明确新增指令，绝对位置放在已确认参数字段。不得宣称本次实现任意相对移动自然语言编辑。
- 新增7项参数变体选择测试，杯口/规则/入口联合112 passed（3.65秒），tests-v6；完整tests-v5运行中，其启动早于此次变体代码修改，不能作为最终新增功能全量证明。

### 2026-10-28 06:11 新参数配方独立发布

- 将+10mm候选的原始validation-package完整复制到其CAD证据目录，保留原图和端点路径摘要；实际执行来源是V1四组件检查点，未改写为包内初始单基座准备路径。现有pair/relation发布器重新核验真实CAD与参数，生成relation-station-gn00-aa00-plus10mm-20261028-v1。发布只证明指定Demo定位，不提升实际机械兼容性。
- 该新发布尚未绑定工位registry自动选取。目前每条规则仅有一个validation入口，且验收计划限定candidate起点；需以可验证的多参数配方登记接入，避免替换原配方导致默认位置失去授权，也不得绕过旧计划摘要。普通compile对旧registry的+10mm阻断仍正确保留。
- 变序链传输包86.378秒CAD成功，继续独立工位复核。tests-v5完整后端回归已启动，结果待收集，不沿用上次统计。

### 2026-10-28 06:08 杯口测量跨上下文复用

- 杯口报告新增可选nativeObservedStatePath：来源和目标原生杯可分别在不同保存实体中测量，逐组验证只读状态、实体SHA及捕获位姿，再复用既有局部功能点转换。不要求为了测量而把两个杯模组装入同一个新实体。
- 增加原生图模块文件与杯目录身份一致检查。新增独立世界平移5m仍得到相同工位参数的正例，以及摘要、位姿、源装配体、只读标志、原生身份错误拒绝测试。杯口+规则78 passed（3.18秒）；新能力只是离线证据处理，不计第二基座真实CAD通过。
- 第二基座来源P000现有实验证据已定位至validation-queue-20261026-v72-native-projection-4/validation-p000-jj00-v1；可对其有界采集来源杯并独立重开，对Project01 GN00/FJ00原生双杯分别采集，再用分离捕获配置补JJ00工位。当前变序CAD仍串行运行，未并发启动扫描。

### 2026-10-28 06:06 参数变化闭环与变序启动

- GN00+10mm候选：CAD81.566秒、独立重开46.294秒、总128.036秒；统一verify-station重算服务区通过，工艺仍null。与V1原清洁包对比平移[0.01,0,-4.996e-16]m、旋转矩阵差0，目标浮动且constrainedStatus=3；旧四组件及配合保全，重开警告位1。记录见gn00-plus10mm-cad-v1/README-CN.md。新候选尚需正常Demo发布，不沿用旧授权。
- 串行启动full-chain-reordered-v1，顺序为校准→传输→清洁→排胶杯→扫描，扫描仍在传输之后。当前仅启动，未声明整链成功。第二基座仍需杯口数据与新配方验证。

### 2026-10-28 06:05 换型完整链通过，开始+10mm新CAD

- V2末包完成：CAD调度160.580秒，独立重开及杯口工位检查通过；attempt-003完整success=true、targetStationValidated=true。恢复段637.579秒不冒充全链总时长；详见V2 README。现有两条新完整链都在AA00基座，尚未满足第二基座要求。
- 位置变化测试已串行启动：使用V1校准后四组件检查点，GN00纵向改为366.3090645mm，横向231mm、支承0不变，输出gn00-plus10mm-cad-v1。目标不固定，无根/叶锚点；待实际CAD与新工位后检，不预报通过。
- 修复报告层混淆：ruleDriven预检通过取readyForCadCompilation且无阻断，CAD后targetStationValidated仍单独取实际后检。旧JSON不改写；新增5个报告语义测试，联合58 passed（1.64秒）。这是状态解释修正，不放宽执行或几何验收。

### 2026-10-28 06:02 当前证据修正与下一步数据缺口

- V2换型链前四包已完成实际保存重开与工位后检；第五包P000任务`project-global-job-79cb29aa19cb`仍在执行。这里只记录运行中，不提前计第二条全链成功。
- GN00纵向+10mm新候选的普通compile负例已执行，1.333秒，以`STATION_PARAMETERS_REQUIRE_NEW_CAD_RELEASE`在CAD前拒绝；证明旧授权不适用于新参数，不证明新参数不可行。下一步需新CAD和当前状态几何验证。
- 修正本文验收表及产物README中滞后的“入口未接通/V1待执行”描述，保留早期scope为历史快照。
- 第二基座杯口规则发现一个具体复用限制：`cup_function_point.build_report`当前要求来源杯与原生杯目录全部绑定同一个已保存装配体及状态。不能直接拼接AA00上下文中的P000杯目录与Project01原型GN00杯目录冒充同一测量。后续应复用局部功能点坐标与各自可追溯坐标变换，或取得真实共同测量上下文；不得改写证据来源来绕过检查。该限制属于杯口数据接入，不需要新增装配执行器。

### 阶段1启动

- 已核对当前工作区和既有普通累计入口；入口仍未接入完整运行后工位验证，不能宣称该项已完成。
- 并行推进当前范围清单、清洁规则参数化、扫描关联参数化；主执行者负责规则登记及累计入口集成。
- 本阶段尚未启动新的SolidWorks装配。无须用户新增确认；按Goal允许的有依据Demo估计推进。

意义：将主线从不断增加单独案例，转为可重复使用的工位规则与同一执行入口，同时保持全部验收要求不变。

### 阶段1/2：规则配置、参数准备与运行后检查接口

- 冻结范围在`data/assembly_stations/scope-v1.json`；只读审计结果在`demo/unified_six_role_goal_20261028/scope-v2/`。当前缺少可认证精确权威的5项为GN00→JJ00、AG00→AA00、N000→A600、N000→A000、A300→A600；不等于机械上已证明无法安装。
- 登记入口为`data/assembly_stations/station-rules-v1.json`。清洁规则复用目标原生服务区，杯口规则复用目标原生杯口投影，扫描规则绑定确切传输与基座；传输/校准复用当前已发布的目标机械端口。
- 配置与真实CAD验收分开：7项配置全部可解析，当前registry仍标记candidate，不因为旧CAD成功自动记为本Goal通过。
- `.gitignore`仅放开`data/assembly_stations/*.json`，其余data生成物继续忽略，确保规则能够随源码交接。
- 普通入口新增`plan-stations`：使用与compile/run/resume相同的已确认清单，可推导参数并生成标准validation-package/effective-mate-graph/selected-face-endpoint-catalog，复用现有候选编译器。
- 新增`verify-station`：按当前CAD结果、独立重开状态、原上下文保全和同一规则重算几何。更名后的配合仍需匹配真实端点、距离及方向，不能借名称相似冒充验证。
- 新规则触发后，compile目前明确阻断，等待自动发布绑定与运行后检查点贯通；历史未指定规则的流程保持原能力，不宣称工位验收。此处是待完成集成项，不是把Goal缩减为离线规划。

真实目录离线准备：`station-preparation-v2`以同一六类清单完成5/5追加步骤准备，0.4821秒；GN00推导356.3091/231/0 mm，P000推导533.5976/906/0 mm并生成新候选。`station-preparation-v1`保留最初传输/校准规则缺失记录，不覆盖失败历史。`v3`只推导不生成候选，0.3596秒。

`historical-postcheck-v2`用新接口重算此前GN00/P000保存实体，CAD证据与代理几何通过、完整工艺未知；**这是离线历史证据复核，不计为新CAD构建或V1/V2/V3**。

#### 当前可用命令

在仓库根目录执行，输出目录必须是新的：

```powershell
python scripts/run_natural_language_staged_chain.py plan-stations `
  data/assembly_stations/chain-aa00-six-role-v1.json `
  demo/my-station-plan --prepare-candidates
```

该命令不启动SolidWorks。请求中的`allowPrototypeEstimate`允许有来源的Demo估计；每个参数化步骤仍需`allowDatumFallback=true`。改位置使用完整的`positionParametersMeters`（longitudinal/lateral/supportGap，单位米），生成新候选，不修改旧发布。

```powershell
python scripts/run_natural_language_staged_chain.py verify-station `
  demo/my-station-plan/s04-cleaning/station-plan.json `
  --cad-result <本次CAD结果JSON> --state <本次独立重开JSON> `
  --report demo/my-new-postcheck.json
```

该命令也不启动CAD；输入必须来自实际执行且源、输出、图和状态摘要一致。它不能把旧参数或其他新增目标的CAD结果当成当前步骤。

下一步不变：完成新候选验证/发布绑定 → 贯通普通累计运行及逐包后检查点 → 三组新的六类链 → 变序/改参/恢复与负例。尚无任何一条新全链被记为完成。

### 2026-10-28：原生工位配合比较接入只读复核

05:56实际目录负例：`negative-ambiguous-transport-request.json`声明两个独立传输实例但未指明扫描依赖，统一plan-stations在0.880秒给出`DEPENDENCY_AMBIGUOUS:Transport`，2/3步骤可规划但整链不完整，CAD未启动。证据为`negative-ambiguous-transport-v1/station-planning.json`。V2扫描包恢复后的独立复核及closure已于05:55:47提交，受控启动前失败后的继续执行在真实扫描包上走通；剩余AH00/GN00/P000继续执行。

完整后端回归已结束：2286 passed、3 subtests passed，432.46秒；JUnit在`demo/unified_six_role_goal_20261028/tests-v3/backend-junit.xml`。此结果为代码回归，不替代V2/V3现场链路或新参数CAD证据。

05:53参数变化准备：`candidate-aa00-gn00-plus10mm-v1.json`仅将纵向距离增加10 mm，横向231 mm与支承0保持。统一plan-stations在1.510秒生成`gn00-plus10mm-candidate-v1`标准配合候选；requiresFreshCadValidation=true、reusableExecutionAuthority=null。该准备不证明新位置服务区域通过，需实际CAD与当前状态复核后再发布，不沿用原356.309 mm配方授权。

05:52真实暂停/受控失败：V2在首包全部复核后正常停于`s01-transport`，attempt-001记录pausedAfterStage，总153.693秒。再次resume并注入`s02-scanner`启动前失败，attempt-002用7.118秒返回，首包明确reused_committed_checkpoint，最后提交仍为首包；第二包未被记为通过。随后已去掉注入参数恢复同一任务，待第二包真实成功后确认失败继续闭环。暂停报告success=false表示整链尚未完成，不是首包失败。

05:51交付核对：V1逐包实测组件/配合为2/3、3/6、4/9、5/12、6/15，各包仅1个固定基座；已增加`full-chain-v1/README-CN.md`说明最终实体、依赖、警告与耗时边界。变序清单`chain-aa00-six-role-reordered-v1.json`按校准→传输→清洁→杯→扫描，统一入口编译5.502秒通过，未执行CAD。V2首包CAD95.812秒成功，等待独立检查后按要求暂停；不能把阶段调度成功当作暂停测试已完成。

05:49:27 V1完成：`full-chain-v1/run-attempts/attempt-001.json`的success与targetStationValidated均true，5次追加均有stage-closure及station-postcheck。最终为AA00/SS00/AI00/BD00/GN00/P000六类链。恢复段499.459秒，不含此前首次执行与编号误拒排查，不应作为全程耗时；完整耗时需汇总各原始CAD/检查尝试。V2已通过同一run入口启动并指定`--pause-after-stage s01-transport`，真实验证阶段间暂停/恢复；尚未完成。总Goal仍缺V2/V3、变序/参数变化等验收，不标记完成。

05:49 V1末包P000阶段CAD178.354秒成功，正在独立重开与杯口验证，不能提前宣称整链通过。JJ00的目标废胶杯已从Project01完整占用树定位为GN00/FJ00下的`FL00002-00549-1`和`FL00002-00549-2`；仅叶身份已知，杯口中心/开口方向尚未采集，不以包围盒中心代替真实功能点。当前CAD链结束后使用既有有界叶面采集工具读取两叶，不新增机构研究或全量扫描。完整后端回归仍在运行，尚无最终统计。

05:47第二基座完整清单准备：`chain-jj00-six-role-v1.json`声明JJ00+SS00+SM00+BD00+AG00+P000，来源Project01/03/05；同一plan-stations在1.414秒完成4/5步骤推导，仅杯口步骤因`TARGET_STATION_RULE_MISSING`停止。证据在`jj00-six-role-preparation-v1/`。没有把现有P000→JJ00配合可执行历史当作目标杯口位置已验证；需有界采集/复用JJ00原生废胶杯功能点后补数据。V1末包P000继续运行，完整后端回归已启动，结果待收集。

05:45 V1第四包：GN00的阶段CAD80.312秒，独立重开及当前服务区域复核通过，`s04-cleaning/station-check-attempts/attempt-001/postcheck.json`的cadPassed/proxyGeometryPassed/targetStationValidated均true，functionalPassed仍null。第二基座AG00→JJ00通过同一plan-stations生成标准候选包（0.991秒），在`jj00-ag00-candidate-v1/`，未启动CAD。后检查异常增加机器可读`postcheck-error.json`，保留失败消息、输入位置和未提交检查点状态；53项专项通过、1.47秒。

05:44第二基座数据推进：通过既有通用清洁规则增加AG00→JJ00配置，目标区域取JJ00原生GN00服务区域，来源为Project03 AG00完整占用与安装基准。离线推导纵向537.690935 mm、横向261 mm、支承间隙0，serviceRegionDemoPassed=true（命令0.515秒）；登记在registry-v5，状态candidate，未宣称CAD通过或发布可复用。不是复制AA00参数。V1前三包已提交，第四包GN00任务`project-global-job-972d33229b04`正在运行；第二基座仍需杯口功能点和新候选CAD闭环。

后续现场与第二基座准备：扫描attempt-002重开复核已提交，第三包BD00的CAD阶段61.651秒成功，尚待该包独立复核。发布端点检查同步支持经源文件核实的完整token，AH00真实历史发布图离线比较通过，专项53 passed（1.38秒）。新增JJ00的SS00传输与BD00校准工位配置、registry-v4（10项配置），仅补已核实原生端口数据，不复制AA00参数；第二基座清洁/杯口仍需目标服务区域与功能点依据，尚未形成V3全链。现有V1/V2继续引用不可变旧registry，不受新增配置影响。

05:41扫描包问题与恢复：AI00的CAD阶段131.037秒成功，独立重开成功，但执行器返回完整token `FL9A24D063AI00`而计划使用`AI00`，造成身份比较误拒。修复为先核对目录源文件，再允许短编号或该确切文件编号，不允许任意同后缀冒认；53项专项通过（1.25秒）。`s02-scanner/identity-fix-postcheck.json`对同一实际实体重算得到cadPassed/proxyGeometryPassed=true、functionalPassed=null。旧失败证据未覆盖，已执行原链resume；成功CAD包跳过插入，只重试独立检查，第二次阶段CAD调度0.131秒不是新的实体生成耗时。

05:39换型准备：新增`calibration-ah00-aa00-v1.json`与不覆盖旧版的`station-rules-v3.json`，复用已发布AH00→AA00机械端口。`chain-aa00-six-role-ah00-v1.json`只将BD00换为AH00，保持SS00/AI00/GN00/P000与AA00，仍覆盖Project01/03/05。同一compile入口生成`full-chain-v2-ah00`，4.342秒，ready_not_started；这是V2准备，不是CAD完成。A500→AA00检查显示无直接安装权威，未静默启用旧参数化配方来凑换型案例。当前V1仍由同一进程串行执行，不并发开启第二CAD链。

05:38现场更新：统一入口`full-chain-v1`首包SS00→AA00通过CAD（阶段80.080秒）、独立重开（47.474秒）及注册工位配合比较，2组件3配合，重开警告位32保留，不声称零警告。`s01-transport/station-postcheck.json`与`stage-closure.json`已提交，第二包AI00任务`project03-job-3a22d8f23bba`正在运行。新全链尚未完成。入口增加`--pause-after-stage`，可在包提交后停止，下次resume复用已有包；52项专项测试通过、1.35秒（暂停恢复此时仅为模拟测试）。新进程的最终报告按实际逐包工位复核计算，不再使用未实现占位文案；当前已启动进程加载的是旧报告代码，后续须经resume重验生成准确汇总，不修改旧尝试记录。

后续增量：普通执行循环加入`verify_stage_checkpoint`，在阶段closure写入前调用既有独立重开检查脚本及同一工位规则。检查失败保留已成功CAD包与独立尝试目录；恢复时若job已成功，不再调用插入执行器，只重试复核。已提交复核重新检查计划/CAD/状态摘要并重算规则。专项50 passed、1.41秒，包括首次检查失败、第二次通过、重复恢复不重复重开及状态被修改拒绝的模拟测试。本轮无真实CAD执行；新registry的compile阻断仍保留，待规则授权与编译预检查连接完成后放行。该钩子测试不计入三条新完整链验收。

- `station_rule_planner.verify_station_stage`补齐传输/校准的`released_mate_parameters`分支：重验不可变发布，读取其摘要绑定的实际CAD执行图，再比较本次图的局部端点、配合类型、方向和参数；允许生成名称变化，不用来源世界位姿作为定位依据。
- 错误目标、距离改变、端点改变、证据图被改动不能通过；结果仅证明注册目标基准配合一致，不声称运输工艺或实际紧固已验证。
- 专项测试30 passed，2.06秒；真实SS00→AA00和BD00→AA00发布图离线复核均通过（命令0.335秒）。这是历史图适配检查，本轮未启动CAD，不能计作新累计链或保存重开测试。
- 仍待完成：普通累计入口自动执行后的独立重开、工位复核与检查点连接；之后执行三条新六类链。当前compile的明确阻断尚未解除。

### 2026-10-28 05:16—05:26：配置生成的新配方完成真实CAD验证

从`station-preparation-v2`通用准备结果直接使用既有CAD执行器，没有为GN00或P000编写新专用装配脚本。两次均从单基座缓存检查点开始；是两个新配对验证，**不是六类累计链，不计V1/V2/V3**。

| 配对 | CAD保存重开 | 独立重开检查包装耗时 | 结果 |
|---|---:|---:|---|
| GN00→AA00 | 77.592秒 | 44.744秒 | 2组件、3激活配合、完全约束、仅AA00固定、无根/叶锚点；服务区代理通过；警告位1 |
| P000→AA00 | 108.093秒 | 61.836秒 | 2组件、3激活配合、完全约束、仅AA00固定、无根/叶锚点；双杯二维投影通过；警告位0 |

两配对的上述CAD和独立检查合计约292.265秒；不包含编程、测试、等待或历史全链耗时。GN仍保留整包络超出等工程未知；P杯口高度差仍单列，实际排胶未验证。均未执行碰撞/B-rep或紧固验证。MCP文档基线前后均保留原有两个铰链零件，未结束SolidWorks进程。

新实体及证据：

- `demo/unified_six_role_goal_20261028/station-preparation-v2/s04-cleaning/assembly.SLDASM`
- `demo/unified_six_role_goal_20261028/station-preparation-v2/s05-cup/assembly.SLDASM`
- 同目录各含`cad-result.json`、`reopened-state.json`、`station-postcheck.json`、`pair-release.json`和原始参数/执行图。
- 发布：`demo/global_assembly_catalog/releases/relation-station-gn00-aa00-20261028-v1/`及`relation-station-p000-aa00-20261028-v1/`；保持`datum_placement_demo`，不提升直接机械兼容性。

登记版本`data/assembly_stations/station-rules-v2.json`绑定原始候选计划、CAD、重开状态和精确配对发布，并在读取时重算同一规则。`chain-aa00-six-role-v2.json`不需手填两项发布路径；`station-preparation-v5`真实准备5/5通过（1.703秒），GN/P自动选择新配方。修改定位参数则产生待重新验证候选，不沿用当前发布。

测试与边界：

- 完整后端回归：2276 passed、3 subtests passed，402.71秒；JUnit见`tests-v1/backend-junit.xml`。
- 随后绑定防篡改/发布匹配补强后的联合专项：198 passed，9.57秒；JUnit见`tests-v2/targeted-junit.xml`。Python编译通过。不要把后续补强说成已重新跑过完整回归。
- 新增负例包括规则改动自签摘要、伪造发布字段、错误精确配对、参数变化仍复用旧发布、借其他目标的CAD成功及更名配合的错端点/错距离。
- 真实累计入口自动运行后复核尚未贯通：指定新registry的`compile`仍明确停止，不允许用旧位置的legacy执行假冒已接入。下一步优先完成这处连接，然后开始V1完整新六类链；不要再次扩展无关架构。
