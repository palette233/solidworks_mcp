# 六类全型号、跨多基座广泛组合阶段验收（2026-10-26）

## 结论

本阶段目标已完成。当前登记范围包含17种移动模组、4种基座，共68个精确“模组—基座”组合；68项均已具备不可变执行发布，待CAD验证、待工程选择、待语义实现和待替代策略数量均为0。

该结论表示“当前Demo范围内具备可审计、可调用的技术执行覆盖”，不表示68项均已获得机械唯一工位、目标包络、实际紧固、碰撞/B-rep、工艺合理性或生产放行验证。

## 组合矩阵

权威报告：

`demo/global_assembly_catalog/broad-combination-coverage-20261026-v74-native-projection-complete/coverage.json`

|指标|结果|
|---|---:|
|移动模组|17|
|基座|4|
|精确组合|68|
|原生关系发布|35|
|参数化关系发布|33|
|待CAD验证|0|
|待工程选择|0|
|待语义实现|0|

零待办复核位于`demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v75-zero-pending/engineering-review.json`；位置、单轴、双轴对和柔性槽决策数量均为0。

## 最终五项闭环

最后5项使用显式授权的“同一精确模组原型语义工位坐标 → 目标基座语义坐标框架”Demo投影。系统只复制纵向、横向和支承间隙，不复制原型顶层变换、组件固定状态或叶级位姿锚点；该能力默认关闭，必须显式启用。

5项均完成：

- 从确定性非原型初始位姿插入；
- 创建3/3真实驱动配合；
- 完全约束且配合求解干净；
- 保存、关闭、重新打开；
- 重开后配合参数一致；
- 源装配体摘要不变；
- 生成精确配对和全局关系不可变发布。

总CAD耗时`755.803 s`，平均`151.161 s/项`。完整索引位于`demo/cross_project_substitution/parameterized-datum-placement-v1/confirmed-position-decisions-20261026-v68-native-projection-demo/batch-execution-summary.json`。

## 六模组自然语言累计装配证据

本阶段不是只验证单对接口；还保留了多基座、跨型号和不同顺序的真实六模组累计装配闭环。

|基座|追加顺序|结果|总耗时|
|---|---|---|---:|
|Project03 AA00|SS00 → AI00 → BD00 → AG00 → P000|标准顺序通过|约581.182 s墙钟|
|Project03 AA00|AG00 → BD00 → SS00 → AI00 → P000|变序通过|约884.433 s墙钟，含一次失败替代|
|Project02 A600|BD00 → A800 → N000 → P000 → AI00|5/5阶段通过|798.397 s|
|Project05 A000|P000 → A180 → D000 → G000 → AG00|5/5阶段通过|669.707 s|

这些链均以基座加5个移动模组形成六模组装配体。真实阶段证据覆盖自然语言映射、发布授权、独立组件插入、真实配合、约束与求解状态、保存重开、参数复核、检查点连续性和源文件不变。G000保留内部柔性，但其外部安装根位姿通过双非原型初始位姿重复性见证。

主要证据：

- `demo/cross_project_substitution/six-role-project03-base-v1/`
- `demo/cross_project_substitution/multi-base-six-role-preflight-20261026-v1/`
- `demo/c6/a6/`
- `demo/c6/a0/`
- `demo/cross_project_substitution/six-role-gn00-datum-20261024-v1/`

## 软件验证

- 新增与聚焦回归：`107 passed`；
- 最终完整后端回归：`1893 passed, 3 subtests passed in 368.44s`；
- `python -m compileall -q apps/demo-backend/src scripts`通过；
- 新增证据目录共121份JSON完成解析；
- `git diff --check`通过。

## 能力边界

本阶段明确不包含：碰撞/B-rep、实际紧固、承载与维护空间、运动行程、工艺合理性、供应商尺寸签认、生产放行、前端产品化和A700内部结构。

后续若继续，应从“扩大技术覆盖”转向机械评审：优先抽查采用Demo语义工位投影的组合，确认工位、包络和实际固定方式；无需继续扩建新的端口、配合图或执行器架构。
