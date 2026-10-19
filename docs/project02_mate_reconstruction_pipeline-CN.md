# 项目02：配合关系原型重建七阶段监控

- 总体状态：`PASSED`
- 当前阶段：`independent_interference_validation`
- 最近更新：`2026-09-14T12:29:12.842719Z`

| 阶段 | 状态 | 证据/问题 | 下一动作 |
|---|---|---|---|
| 1. 完整图语义升级 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\layout_previews\project02_module_mate_graph_v6_all_bodies.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_v6_all_bodies_semantics_audit.json | 对T401两个实例的三张配合面执行目标叶/零件级在线恢复，并写入稳定EndpointId。 |
| 2. T401小装配面恢复 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_T401_source_mate_face_catalog_v1.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_T401_small_recovery_v1.result.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_T401_small_recovery_v1.SLDASM | 编译包含10个顶层实例、27条配合的完整Effective Graph，并执行保存重开复核。 |
| 3. 27/27配合重建 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_full27_source_pose_v1.SLDASM；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_full27_source_pose_v1.result.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_full27_source_pose_v1.reopened_graph.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_full27_source_pose_v1.closure-audit.json | 分析完整健康配合图的剩余刚体自由度，区分柔性子装配体内部自由度与顶层位姿欠约束。 |
| 4. 自由度分析 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_full27_top_level_dof_v1.json | 从5个残余标量自由度提取3个最小模组锚点，并保留标量化接口。 |
| 5. 最少锚点提取 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\project02_minimal_residual_anchors_v1.json | 仅A600基准及A800、T401-1、T401-2使用锚点；其余模组从确定性非原型网格起始，执行全装重建。 |
| 6. 非原型初始位姿全装重建 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix.SLDASM；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix.result.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\project02_mate_reconstruction_ABC_summary.json | 对最终v20非原型初始位姿重建结果执行全模组分层干涉验证，并与原型基线比较。 |
| 7. 独立实体干涉验证 | `PASSED` | 证据：D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix.result.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\targeted_interference\project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix_leaf_details_batch.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\A600_A800_failed_leaf_fallback.json；D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\mate_reconstruction_pipeline\non_source_minimal_anchor_v3_flex_reopen_fix\project02_mate_reconstruction_v20_interference_closure.json | 七阶段闭环完成；后续可将柔性内部状态与原型固有干涉基线缓存推广到其他项目。 |

## 阶段门原则

只有前一阶段形成机器可读证据并通过验收，后一阶段才进入执行；实体干涉验证最后独立进行，避免把配合语义错误误判为几何碰撞问题。

## 本轮闭环结论（2026-09-14）

- 七阶段均已通过；最终重建装配体包含 10 个顶层模组，27 条配合全部创建成功。保存后重新打开仍识别到 10 个模组和 27 条配合，10/10 顶层位姿复核通过。
- 干涉验证覆盖全部 45 组顶层模组对：17 组由严格分离的 AABB 直接证明，28 组进入精确验证；相对项目02原型，新增干涉模组对为 0。
- 项目02原型自身存在 8 组已知实体相交/设计接触，因此通过标准是“无新增干涉”，不能表述为“绝对零接触”。

## 本轮功能修改及意义

- 完整图导出改为枚举全部实体类型，并支持同一 T401 零件实例的重复面选择器，解决小装配配合面缺失。
- 增加 Slot 配合及求解状态、配置、Width/Slot/Distance 等语义的完整保留，使 27 条配合不再因语义降级而丢失。
- 将柔性子装配体求解状态恢复推迟到全部顶层配合创建之后，避免 A100、A200、A700 在父级约束尚未完备时形成错误内部位姿。
- 为实验输出增加唯一标签和运行计时，并按已保存文档标题关闭文件，解决同名装配体残留导致的保存后重开失败。
- 建立“AABB 初筛—候选模组对叶级 B-rep—失败叶对官方接口回退—与原型基线比较”的分层验证流程，减少不必要的全量 B-rep 调用，同时使 45/45 模组对均有证据。

## 时间记录

- v20 非原型初始位姿全装重建、保存和重开复核：约 1148.1 秒（19.1 分钟）。
- 首次 45 组模组对完整干涉筛查：约 3279.6 秒（54.7 分钟）。
- 原型干涉基线补采：约 1483.7 秒（24.7 分钟）。
- v20 柔性相关 19 组候选精检：约 1636.7 秒（27.3 分钟）。
- A600/A800 三个 B-rep 内核失败叶对的回退验证：约 131.5 秒。

## 已知边界与后续方向

- 当前“最少锚点”是 3 个模组级 4×4 位姿锚点（A800、T401-1、T401-2）；自由度分析已识别为 5 个标量自由度，但执行器尚未把锚点进一步缩减成 5 个标量约束。
- A100/A600 的原型相交叶对由 7 个减少为 6 个；没有新增干涉，但若目标升级为柔性内部几何逐叶等价，仍需补充内部状态约束。
- A600/A800 的三个叶对会触发 SolidWorks B-rep 内核错误 547，目前通过对精确叶组件调用官方干涉接口完成判定；后续可将回退策略固化为通用验证器能力。
- 原型固有接触基线仍是项目相关数据。迁移到项目01、03、05、06前，应分别建立其完整配合语义、柔性状态和原型干涉基线。
