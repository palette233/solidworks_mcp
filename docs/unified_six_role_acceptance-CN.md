# 六类累计装配统一入口：阶段验收报告

日期：2026-10-28。证据根目录为 `demo/unified_six_role_goal_20261028/`，以下相对路径均位于该目录，配置位于仓库的`data/assembly_stations/`。

## 验收口径

本报告核对目标指定的统一流程、至少三条有区别的六类真实累计链、变更与异常测试及交付物；不把代表链通过解释为所有68项工位已完成。范围清单同时包含Project01/02/03/05，真实代表链覆盖Project01/03/05、AA00和JJ00两基座。Project02列在目录及缺口中，不冒称本轮完成其六类整链。

## 逐项证据

| 要求 | 核对结果与证据 |
|---|---|
| 固定目录、区分执行接口/工位/实验/缺口 | scope-v8/scope.json及coverage.json：4基座17移动模组、68精确配对（跨项目51）；63当前接口、12工位配置、11工位验证。coverage-gaps-CN.md逐项列出其余57项；7项工位证据层级为experimental，不能混算为新机械发布 |
| 参数和规则可配置，而非每案例脚本 | station-rules-v11.json及各evaluator配置登记安装基准、清洁服务区、杯口投影、扫描目标和发布配合参数；所有四条链使用run_natural_language_staged_chain.py，组合由JSON改变 |
| 普通入口贯通 | compile/run/resume；每包依次接口授权、工位参数、配合图、真实CAD、独立重开、当前状态后检、检查点。delivery-jj00-compile-v1为最新示例编译，9.950798秒，未运行CAD |
| 无原型目标位姿锚点 | current-chain-audit-v1.json所有20包nonPrototypeInsertionAudited=true；检查实际执行诊断、TargetCaseAnchored=false、根/叶锚点空、独立插入。桥接代码确实调用确定性非来源初始变换再建配合。未导出数值初始矩阵，证据等级如实标注 |
| 真实配合和外部自由度 | 20包allMatesCreated、mateSolveClean、targetFullyConstrained、parametersReopened均通过；保存状态中新增目标isFixed=false且constrainedStatus=3，只固定基座 |
| 保存关闭重开、上下文保全 | 20包savedClosedReopened、sourceUnchanged、priorContextPreserved通过；比较原组件源文件/名称/位姿/配置/固定与求解状态、原配合类型/方向/参数/激活状态。全链另检查连续输入输出 |
| 当前实际输出上的工位 | 每包station-postcheck指向独立保存状态；清洁区域、杯口投影、扫描关联或登记的安装参数按当前输出重算，不继承历史成功标签 |
| 当前六类链、同基座换型、第二基座 | full-chain-v1、full-chain-v2-ah00、full-chain-jj00-v2各5包，均6组件15顶层配合，覆盖六角色/两基座/三个项目来源 |
| 变序 | full-chain-reordered-v1按校准→传输→清洁→排胶→扫描完成；order-comparison.json十项通过，与基准最终位姿和配合参数等价 |
| 位置参数变化 | gn00-plus10mm-cad-v1/parameter-comparison.json十一项通过：GN00纵向+10mm、旋转不变、原四组件不变；CAD追加及重开约128.036秒 |
| 新配方普通复用 | GN00/P000在AA00、AG00/P000在JJ00的新Demo发布进入普通选择；BD00/JJ00补精确直接接口发布。+10mm参数配方经gn00-plus10mm-released-compile-v3再次真实执行，506.412秒，注意后者是两组件复用实验 |
| 换基座/型号重选，关联失效重算 | JJ00换基座与SM00换扫描真实链通过；AH00换校准真实链通过。scanner_target_rule测试覆盖换传输定义不得沿用旧条码区、换基座/实例失效、位置改变重算。新几何依据缺失时拒绝，不假称自动创造条码工位 |
| 多候选/实例消歧 | station_rule_registry测试验证重复工位要显式选择、角色多实例要明确dependencySelections；累计扫描后检通过前置检查点摘要绑定选定逻辑实例的实际组件名。四条真实链复算通过；重复型号多实例完整CAD插入未实测，不做扩大声明 |
| 暂停、失败后继续 | full-chain-v2-ah00/run-attempts：首包后真实暂停，第二包前受控注入失败，resume复用同一首包jobId并完成剩余四包。分别153.693、7.118、637.579秒，不含人工等待，不模拟断电/强杀CAD |
| 缺少工位负例 | negative-missing-station-v2：A800→AA00在当前v11明确TARGET_STATION_RULE_MISSING，3.052秒，无CAD；不静默使用旧接口位置 |
| 关联不明确负例 | negative-ambiguous-transport-v1：两个传输实例未选择，DEPENDENCY_AMBIGUOUS:Transport，无CAD |
| 新尺寸不可偷用旧发布 | negative-unreleased-parameter-v1：STATION_PARAMETERS_REQUIRE_NEW_CAD_RELEASE，1.333秒；之后明确验证发布变体才可正常执行 |
| 证据失效负例 | test_station_rule_registry：规则/源文件/计划摘要、参数发布、实例保存状态及实体变化均拒绝；test_scanner_target_rule：旧关联摘要与配置/源零件变化拒绝。此部分是离线测试，不伪称真实破坏CAD文件 |
| 统一交付与耗时 | docs/unified_six_role_operation-CN.md给出命令、结果索引、恢复流程和边界；每包JSON记录UTC与耗时；本报告、专项进展、开发规则及log.md同步记录 |

## 实体与耗时

最终实体完整路径位于current-chain-audit-v1.json每条链最后一个stages条目的assemblyPath；报告同时给出文件SHA。可按操作指南查找，不使用首包的中间产物。

- 第二基座完整链：1087.336秒，约18分7秒。
- 变序完整链：1007.506秒，约16分48秒。
- AH00换型链：三个运行片段，暂停及失败恢复证据分别保留；不能将637.579秒恢复时间当作总运行时间。
- 当前证据复算：4条链20包，12.238秒，不是新CAD执行时间。
- 打开警告位1/32保留；配合错误码0不等于所有打开检查零警告。

## 自动化测试快照

- tests-v8-junit.xml：2319 passed，3 subtests passed，643.00秒；这是实例绑定修改前的完整后端快照。
- instance-binding-tests-v1.xml：最新相关模块101 passed，3.18秒。
- evidence-audit-tests-v1.xml：审计缺检查点/链摘要变化拒绝，2 passed，0.31秒。
- 最新4条真实链20包current-chain-audit-v1.json通过。不能把不同代码快照测试简单相加作为一次完整回归结果。

## 保留的能力边界与下一轮缺口

1. 未覆盖57项工位规则/证据逐项列明；不是全部型号任意配对已验证。新增型号/基座仍需提供同角色工位、参考方向、功能区域与精确端点数据。
2. 同型号重复实例的后检已有明确选择机制，但当前插入器仍可能在重复源文件场景拒绝身份歧义；未证明任意多实例CAD累计链。
3. 改型/改基座通过新清单重新推导与构建；不是任意既有装配体的一键原地替换功能。相对自然语言位置编辑也不是本次自动识别覆盖保证。
4. 安装参数采用目标原生工位或声明的Demo几何估计，不代表厂家签认值。杯口二维投影通过不保证等高或真实排胶；清洁服务区是代理区域。
5. 碰撞/B-rep、实际紧固、真实工艺与生产放行均未验证且不作为本轮完成条件；functionalPassed保持null。
6. 历史AH00运行报告targetStationPreflightPassed=false为当时报告字段口径错误，保留原文件。后来已修正字段计算并以当前20包复核证明实际CAD/工位闭环，不篡改历史报告。

结论：本阶段所要求的统一流程与代表性闭环已有证据；仍应按上述边界使用，不得对外宣称全目录68项目标工位和所有自由组合已完成。
