# Project01 跨项目只读关系验证闭环

日期：2026-10-11

## 目标

验证 Project02、Project03 已形成的“自然语言关系 → 独立关系模板 → 事务清单 → 持久作业 → 真实 CAD 证据”流程，是否能在 Project01 上复用，而不依赖项目编号专用执行逻辑。

本轮选择 Project01 的既有关系：`GN00` 防转平面与 `SS00` 基准面保持平行。源关系原本是驱动安装配合；本轮不重复创建它，只把同一稳定端点登记成独立的只读观察模板。

## 功能修改

1. 新增版本化关系派生注册表 `relation_template_derivations.v1.json`，把“从复合模板提取只读关系”和“观察既有驱动配合”区分为两种显式模式。
2. 新增可重复目录构建脚本 `scripts/build_registered_relation_catalog.py`，生成候选目录及逐条派生证据；源目录和源模板保持不变。
3. 独立关系语义支持单步骤 `validate_only` 平行关系，不再错误要求只读关系必须驱动位姿。
4. SolidWorks 适配器增加平面法向无向夹角测量；同向和反向法向均按同一平面方向处理，默认平行目标为 `0 rad`。
5. 新增 Project01 准备脚本、既有大装配体子集种子签认和最终证据汇总脚本。

本次修改的意义：只读关系验证从“只能测量距离”扩展到“可测量平行角度”，且关系模板派生成为版本化、可重建的目录流程，不再依赖一次性手工 JSON。

## 真实 CAD 闭环

- 持久作业：`project01-job-8a21b33ff155`
- 执行包：`packet-003 / VERIFY_RELATION`
- 输入：Project01 十对象已保存装配体；清单所需 JJ00、SS00、GN00 为精确子集，其余 6 个顶层对象显式留痕。
- 端点恢复：GN00 使用 `GeometricFingerprint+ModulePoseDelta`；SS00 使用 `BodyFaceIndex+ModulePoseDelta`。
- 期望夹角：`0 rad`
- 实测夹角：`0 rad`
- 绝对误差：`0 rad`
- 容差：`1e-6 rad`
- 配合请求/创建：`0 / 0`
- 源装配体：SHA-256 前后一致。
- 结果：另存、关闭、重开和参数复核均通过。
- 碰撞/B-rep：按当前主线未执行，不属于本轮验收。

最终装配体：

`demo/global_assembly_contexts/manifest_jobs/project01-job-8a21b33ff155/packet-runs/packet-003-attempt-01/project01-gn00-ss00-parallel-validation-v1-packet-003.SLDASM`

最终机器可读报告：

`demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json`

## 时间分析

- 持久作业总耗时：约 `151.40 s`
- CAD 调用：约 `149.74 s`
- 打开并解析图根：约 `55.29 s`
- 保存并关闭：约 `35.55 s`
- 重开并复核：约 `49.82 s`
- 真正的关系计算本身不是主要耗时；大装配体打开、保存和重开约占绝大部分。

## 测试结果

- Python 后端：`807 passed, 3 subtests passed`
- C# 非可视化集成回归：`363 passed`
- C# 全量运行：`366 passed, 2 failed`。两项失败来自既有 `HelloWorldVisualIntegrationTests` 调用测试客户端明确不暴露的 `ResolveComponentTarget` 和 `ListComponents`，与本轮改动无关；本轮新增夹角算法的 29 项定向测试全部通过。

## 当前边界与下一步

当前已经在 Project02、Project03、Project01 三个项目族上证明同一只读关系事务链可复用，但这不代表任意驱动型关系都可安全新增。下一步建议：

1. 把 Project01/03 的派生关系目录纳入统一版本发布与上下文迁移报告；
2. 扩充只读关系到同轴、重合和角度，但仍要求真实端点证据；
3. 为驱动型跨项目关系单独建立自由度与过约束预检，不从只读验证结果外推；
4. 优化大装配体只读验证的打开/保存策略，减少重复重开时间。

## 后续落实：重合关系与正式发布目录

上述第1、2项已继续推进：

- 新增GN00安装面—JJ00基准面的独立只读重合模板；重合不只检查“法向平行”，还同时要求平面距离接近0。
- 持久作业`project01-job-14a100663758`真实CAD通过：实测距离`2.5985104778551083e-16 m`、距离容差`1e-4 m`、实测夹角`0 rad`、角度容差`1e-6 rad`。
- 两端面均通过`BodyFaceIndex+ModulePoseDelta`恢复；请求/创建配合均为0，源文件未变化，另存重开通过。
- 已发布不可变Demo目录`relation-v4-20261011`，目录摘要`c54fb4ac283e52fc9f097460240adc07c3fec68140775de07daff0fd0265bba2`；发布清单绑定3条派生模板与3份真实CAD通过证据。
- 发布范围只包含自然语言关系选择和只读CAD验证；驱动关系、碰撞/B-rep和生产放行均明确为false。

新增装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-14a100663758/packet-runs/packet-003-attempt-01/project01-gn00-jj00-coincident-validation-v1-packet-003.SLDASM`。

本次修改的意义：目录消费者可以引用固定发布摘要，不再依赖会变化的preview文件；同时“重合”已被落实为距离与方向两个条件的联合验证，而不是仅凭配合名称判断。

## 运行时发布目录接入与同轴能力准备

默认自然语言关系入口现已显式加载并校验 `relation-v4-20261011`：运行时会核对发布清单摘要、仓库相对路径、发布目录文件 SHA-256、目录语义摘要和三条已发布模板。`GET /api/demo/global-relation-release` 可直接查看当前发布ID、摘要、范围和证据数量；`POST /api/demo/global-relation-intents/preview` 会把自然语言要求匹配到已发布模板，而不再只返回“识别出重合/平行/距离”。

本轮已验证：重合、平行和 40 mm 距离分别命中唯一模板；未发布的同轴请求明确阻断；API 已正式接受 `operation=verify`。若调用者要求 `executionMode=drive`，当前发布清单因 `drivingRelationRelease=false` 在启动CAD前拒绝请求。

SolidWorks只读验证器同时补充了圆柱面轴线恢复和同轴偏差计算：从恢复的真实圆柱面读取轴线，计算两轴无向夹角与径向距离。纯几何测试已覆盖反向轴线、轴向错位、径向错位和角度误差；尚未登记并执行同轴真实CAD关系，因此同轴仍未加入发布目录。

本次修改的意义：自然语言入口、发布范围和执行模式形成一致的失败关闭边界；同时同轴验证已具备几何执行基础，下一阶段只需选择稳定端点并完成真实CAD证据，而不是重新设计测量器。

## Project01 同轴真实 CAD 闭环与 v5 发布（2026-10-11）

上述同轴闭环已经完成。系统从 GN00 定位孔和 JJ00 安装孔恢复两个真实圆柱面，并在保存、关闭、重新打开后重新读取轴线。持久作业 `project01-job-6028bd3d279b` 的径向轴距为 `8.755986498829282e-17 m`，无向轴角为 `0 rad`，分别通过 `1e-4 m` 和 `1e-6 rad` 容差；两端均采用 `BodyFaceIndex+RuntimeCylinderSurface` 恢复，请求和创建配合均为 0，源装配体摘要未变化。

结果装配体：`demo/global_assembly_contexts/manifest_jobs/project01-job-6028bd3d279b/packet-runs/packet-003-attempt-01/project01-gn00-jj00-concentric-validation-v1-packet-003.SLDASM`。CAD 阶段约 `137.99 s`，其中打开并解析根组件 `45.74 s`、保存关闭 `48.21 s`、重开复核 `34.37 s`；本轮未执行碰撞/B-rep。

同轴模板和证据已发布为不可变目录 `relation-v5-20261011`，目录摘要为 `387575b777e857b5cbd6694d625258c866d0b9fcb9fe84e6f34902386d7afa60`。默认关系入口已切换到 v5；“验证两个孔同轴”现在会命中唯一已发布模板，而“驱动两个孔同轴”仍因发布范围不含驱动关系而失败关闭。

最终回归：Python `812 passed, 3 subtests passed`；C# 非可视化 `367 passed`。

本次修改的意义：同轴能力已经从“算法可用”升级为“真实端点恢复、真实 CAD 测量、持久作业、重开复核、不可变发布”完整证据链。下一阶段应进入驱动关系的自由度/过约束预检，而不是把只读通过直接等同于可安全创建配合。
