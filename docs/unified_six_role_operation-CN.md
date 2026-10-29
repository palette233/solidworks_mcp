# 六类跨项目累计装配：统一入口操作与结果索引

日期：2026-10-28。用于已确认选型后的脚本运行，不代表任意自然语言、任意模组组合已验证。

## 当前能力与范围

使用同一入口完成模组/基座确认、接口和工位选择、参数推导、真实配合定位、保存重开、当前代理几何复核与检查点提交。只固定基座，不用目标根或叶位姿锚点补约束。

目录范围为Project01/02/03/05；当前覆盖清单为4个基座、17个移动模组、68个精确配对。63项有当前执行接口依据，但只有11项工位规则绑定本阶段实体验证，另1项为配置候选。其余57项未达到当前工位验证口径，不能说全目录自由组合已完成。

完整缺口逐项见 `demo/unified_six_role_goal_20261028/scope-v8/coverage-gaps-CN.md`；机器清单为同目录coverage.json及scope.json。

## 操作示例

在仓库根目录打开PowerShell。Python须具备现有后端依赖；CAD执行需正常的SolidWorks会话及项目零件路径。不要并行启动多个CAD作业。

输入例子：`data/assembly_stations/chain-jj00-six-role-v4.json`。

其中每步含工程描述requirement、已确认moduleSelection；基准定位Demo另需显式allowDatumFallback=true。allowPrototypeEstimate=true表示接受有来源的原型测量Demo参数，不授权复制目标世界位姿。采用target_role_station，不静默降级历史配方。

```powershell
# 仅推导工位，不启动CAD。输出目录必须不存在。
python scripts/run_natural_language_staged_chain.py plan-stations data/assembly_stations/chain-jj00-six-role-v4.json demo/my-six-role-plan-01

# 编译执行清单，不启动CAD。
python scripts/run_natural_language_staged_chain.py compile data/assembly_stations/chain-jj00-six-role-v4.json demo/my-six-role-run-01

# 明确启动真实CAD；逐包保存重开并复核。
python scripts/run_natural_language_staged_chain.py run demo/my-six-role-run-01

# 仅在任务暂停或失败后继续；从已有检查点恢复，不重新插入已完成包。
python scripts/run_natural_language_staged_chain.py resume demo/my-six-role-run-01
```

独立新实验请复制输入JSON、修改chainId并使用新的输出目录，避免与既有任务身份冲突。不要修改已编译目录的输入或历史成功证据。

可在首次run时增加`--pause-after-stage s01-transport`，在该包完整验证后暂停；之后使用resume。`--inject-failure-before-stage`只供受控恢复测试，不用于正式演示。

## 如何判断完成

- cad_job_finished只表示CAD作业结束，不代表工位后检通过。
- stage_checkpoint_committed表示本包后检及检查点已提交。
- run-attempts最新报告需success=true、targetStationValidated=true。
- 每包stage-closure.json给出确切实体路径和SHA；station-postcheck.json指向保存重开证据。
- 最终文件取chain.json中最后一包的stage-closure，不取首包或中间包。
- functionalPassed=null表示真实工艺未验证，不是工艺通过。

## 代表性结果

以下目录均相对于仓库根目录 `D:/zengshuang/workspace/cuhksz/cad/solidworks_mcp`。

| 案例目录（位于demo/unified_six_role_goal_20261028） | 组合及作用 |
|---|---|
| full-chain-v1 | AA00＋SS00＋AI00＋BD00＋GN00＋P000，基准六类链 |
| full-chain-v2-ah00 | 同一AA00基座，AH00替换BD00；另完成暂停/失败后恢复 |
| full-chain-jj00-v2 | JJ00＋SS00＋SM00＋BD00＋AG00＋P000，另一基座、扫描与清洁型号 |
| full-chain-reordered-v1 | 基准链变序：先校准，后传输、清洁、排胶、扫描 |

四条链均为6组件，最终15条顶层配合。第二基座链执行1087.336秒，约18分7秒；变序链1007.506秒，约16分48秒。其他运行存在暂停/恢复，须合看run-attempts，不用单次恢复时间冒充端到端耗时。

本次重新逐包审计结果：`demo/unified_six_role_goal_20261028/current-chain-audit-v1.json`，4条链20包，通过当前CAD闭环及工位验证，耗时12.238秒。此为读取已有真实证据的复算，不是新CAD构建。报告每包含完整实体地址、SHA、工位参数与打开警告；警告位1/32保留，不能宣称全程零警告。

## 位置变化与新组合

已验证GN00纵向356.309→366.309 mm，实际位移10 mm，其余四组件不变；见gn00-plus10mm-cad-v1。该变体发布后通过普通入口再次执行，见gn00-plus10mm-released-compile-v3，总506.412秒。后一次为基座加GN00两组件，不算新增六类链。

新参数先用plan-stations的`--prepare-candidates`形成候选。旧发布不自动授权新参数；需要候选CAD和当前工位复核，登记精确参数配方后才能普通复用。自由文本“移动10mm”不能视为所有相对位置语言均已自动贯通。

多个关联实例必须显式选择；扫描后检沿已提交检查点绑定实际传输组件。任意重复型号多实例的完整CAD插入尚未验证，歧义或身份不足会拒绝，不猜选第一个。

## 后验工程边界

参数化支承定位不证明孔位兼容、实际固定可靠或无需转接件。碰撞/B-rep、真实扫码/排胶、动态工艺及生产放行未验证且非本轮硬条件。新基座或新型号缺少目标工位、功能点/区域或精确接口依据时，应补数据，不能静默复制来源原型位置。
