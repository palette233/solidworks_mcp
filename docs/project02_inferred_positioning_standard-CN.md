# Project02 A800/A180推定定位标准

## 1. 目标

需求方没有提供完整的厂商安装端面、销孔、孔系和扫码光学参数。本标准将需求文件、真实CAD配合、几何推定和原型测量统一为一份版本化、可校验、可替换的Project02定位基线。

它解决两个问题：

1. A800和A180的定位规则不再分散在脚本、说明文字和历史原型位姿中；
2. 系统能够明确区分“足以进行Project02粗布局”和“足以生产放行”。

当前标准只适用于Project02，不得把其中的原型测量常数直接迁移到其他项目。

## 2. 权威等级

定位参数按以下优先级覆盖：

1. 厂商确认；
2. 机械工程师确认；
3. CAD真实配合测量；
4. CAD实体几何推定；
5. Project02原型标定；
6. 需求文件派生；
7. 临时估计。

只有前两级可以形成生产参数决定。其余等级可以用于粗布局和Demo，但必须保留来源、范围和替换条件。

## 3. A800定位准则

- 基座：A600；
- 支承：`重合35`，确定支承高度和支承面姿态；
- 横向居中：`宽度9`，确定横向位置和剩余姿态；
- 纵向位置：上述配合不约束沿输送长轴X的平移，当前由Project02安装坐标中的原型标定锚点封闭；
- 需求复核：上层输送面高度`0.92～0.96 m`、内框宽度`0.334 m`、操作侧护栏距离`0.412 m`；
- 替换条件：获得厂商端面、定位销或安装孔系基准后，必须替换纵向案例锚点并重新执行受影响装配链。

## 4. A180定位准则

机械层：

- 基座：A600，而不是A800；
- 支承：`重合34`；
- 纵向位置：`距离24=0.272 m`；
- `槽口3`当前只作为真实原型证据，尚未作为通用驱动配合；
- 剩余自由度暂由Project02案例锚点封闭。

功能层：

- 源端口：`A180.scan_optical`；
- 目标端口：`A800.barcode_target`；
- 粗工作距离：`0.100～0.160 m`，优选约`0.127085 m`；
- 必须满足光路无遮挡、朝向条码侧、扫码工位位于点胶工位之前；
- 光轴方向符号、PLC量产停靠公差仍未由厂商或工程师确认。

## 5. 代码与产物

- 标准JSON：`apps/demo-backend/src/demo_backend/project_profiles/project02_positioning_standard.json`；
- 校验与审计：`apps/demo-backend/src/demo_backend/project02_positioning_standard.py`；
- 命令行审计：`scripts/audit_project02_positioning_standard.py`；
- 审计产物：`demo/positioning_standards/project02_positioning_standard_v1.audit.json`；
- A800构建器和A180构建器均写入`positioningStandardBinding`，绑定标准版本、摘要和模组规则编号。

## 6. 当前闭环结果

- 标准结构校验通过；
- 所有登记证据文件存在；
- A800和A180语义端口构建器成功消费同一定位标准；
- A180工作距离由定位标准提供，不再由构建器单独硬编码；
- 自动结论：`PROJECT02_INFERRED_POSITIONING_STANDARD_READY_FOR_COARSE_LAYOUT`；
- `coarseLayoutReady=true`；
- `productionReady=false`。

测试命令：

```powershell
python -m pytest apps/demo-backend/tests/test_project02_positioning_standard.py apps/demo-backend/tests/test_project02_semantic_installation_builders.py -q
python scripts/audit_project02_positioning_standard.py
```

本轮结果为`6 passed`，并成功重新生成A800/A180集成测试目录。

## 7. 尚未完成与下一步

1. 将通用事务DAG的欠约束判定读取本标准的“Project02粗布局准入”结论，使A800/A180在明确选择Project02推定基线时可以由`blocked`转为`ready-with-project-baseline`；
2. 默认通用模式继续失败关闭，不得静默采用案例锚点；
3. 对准入后的A600→A800→A180清单只做编译和非CAD回归，确认事务包记录标准摘要；
4. 经人工明确确认后，再运行一次真实累计CAD短链；
5. 将厂商或工程师确认数据写入参数权威注册表时，自动替换低等级基线并使生产审计重新计算。

## 8. 结果表述边界

允许表述：

> 已建立Project02 A800/A180推定定位标准，现有证据足以进行Project02粗布局与Demo装配。

禁止表述：

> 已获得厂商安装尺寸；已形成可跨项目复用的生产定位标准；扫码光学已经量产验收。

## 9. 通用事务编排接入（2026-10-11）

通用DAG、CAD事务清单和自然语言清单入口均新增显式参数：

```text
positioningStandardId = project02-inferred-v1
```

行为规则：

- 未选择标准：A800/A180继续以`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`失败关闭；
- 显式选择标准：仅A800和A180的已登记剩余自由度按项目基线封闭，状态为`ready-with-project-baseline`；
- 每个事务包携带标准版本、SHA-256摘要、模组规则编号和参数权威要求；
- 项目固定顺序没有重新进入通用编译器；
- 碰撞状态保持`not_evaluated`。

自然语言入口烟测：

```powershell
python scripts/compile_global_natural_language_manifest_job.py `
  project02-positioning-standard-v1-smoke `
  "先安装项目02 A600箱体" `
  "然后安装项目02 A800传输模组" `
  "最后安装项目02 A180扫描模组" `
  --positioning-standard-id project02-inferred-v1 `
  --overwrite
```

结果：2个事务包、0个阻塞项，任务`project02-job-6e3c1b72de5d`已创建并完成。完整后端回归为`748 passed, 3 subtests passed`。

## 10. 真实累计CAD短链（2026-10-11）

用户清理SolidWorks现场后，已通过通用持久清单执行器完成：

```text
A600基座 → A800传输模组 → A180扫描模组
```

闭环结果：

- 作业：`project02-job-6e3c1b72de5d`；
- 状态：`succeeded / assembled`；
- A800事务：`182.943 s`，2/2配合建立成功，保存关闭重开后参数一致；
- A180事务：`32.787 s`，2/2配合建立成功，`距离24=0.272 m`重开后保持一致；
- 作业总耗时：`215.913 s`；
- 最终独立装配体：`demo/global_assembly_contexts/manifest_jobs/project02-job-6e3c1b72de5d/packet-runs/packet-002-attempt-01/project02-positioning-standard-v1-smoke-packet-002.SLDASM`；
- 最终SHA-256：`88fd1f0ed67bf500b4ec97c3059778334dcb2debec4b16a0bc6bd8b233857334`；
- 独立复核：3个顶层对象，重建状态健康，文件哈希稳定，耗时`5.433 s`；
- 截图：`demo/global_assembly_contexts/manifest_jobs/project02-job-6e3c1b72de5d/final-assembly.png`；
- 复核证据：`demo/global_assembly_contexts/manifest_jobs/project02-job-6e3c1b72de5d/final-reopen-verification.json`。

约束与证据结论：

- A800案例锚点平移误差约`1.24e-16 m`、旋转误差为`0`；
- A180案例锚点平移误差为`0`、旋转误差约`2.22e-16`；
- 两步均从独立模组文件插入，不是复制原型顶层组件；
- 上一步输出作为下一步不可变检查点，且源装配体哈希保持不变；
- 定位标准版本与摘要已进入事务清单；
- 碰撞/B-rep状态保持`not_evaluated`，本轮不作为装配编排验收项；
- 该结果仍属于Project02粗布局/Demo实证，`productionReady=false`不变。
