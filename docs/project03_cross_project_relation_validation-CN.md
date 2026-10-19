# Project03 跨项目关系验证

## 目标

验证 Project02 已走通的“语义端口 → 可编辑关系图 → CAD 事务包 → 持久执行器 → 保存重开复核”能力，是否能在不编写 Project03 专用 CAD 执行器的情况下复用。

首个案例选择 Project03 `AA00—AB00` 的 `距离5=40 mm`。该关系在原始语义包中属于复合安装模板的只读验证步骤，适合验证跨项目关系语义、稳定面恢复和真实 CAD 测量，同时不会改变原装配配合。

## 本轮实现

1. 新增通用模板拆分器：只允许从复合模板中提取已声明为 `validate_only` 的步骤，生成独立只读关系模板；拒绝把驱动配合伪装成独立验证关系。
2. 新增既有装配体子集签认：关系上下文只包含 AA00、AB00 时，允许种子装配体包含额外顶层组件；要求上下文实例数量精确匹配，并显式记录8个额外对象。
3. 关系清单仍保留 AB00 安装包作为前缀，但本次只执行第二包 `VERIFY_RELATION`；已有全装检查点通过文件 SHA-256、组件清单和上下文摘要绑定为外部种子，不宣称安装前缀被重新执行。
4. 修复跨项目审计差异：历史 `ValidationRelations` 不一定保存 `alignment`。只读距离/角度验证改为按关系名称、类型和目标标量匹配，不虚构对齐值；实际方向由恢复后的几何端点测量确定。

## 真实 CAD 结果

- 持久任务：`project03-job-ac77c693ae78`
- 状态：`succeeded`
- 请求值：`0.04 m`
- 重开后实测：`0.04000000000000188 m`
- 绝对误差：`1.880440247958859E-15 m`
- 容差：`1E-06 m`
- 配合变更：创建0、更新0、删除0
- 端点恢复：AB00 使用 `BodyFaceIndex+ModulePoseDelta`；AA00 使用 `GeometricFingerprint+ModulePoseDelta`
- 源装配体：SHA-256 复核未变化
- CAD阶段耗时：约152.59秒；持久步骤耗时约156.49秒
- 碰撞/B-rep：按当前主线未执行

首轮在进入 SolidWorks 前失败，原因是旧执行器固定假定验证关系的 `alignment=1`，而 Project03 模板记录为0、审计记录未保存该字段。失败未接受任何输出并回滚到已签认种子；修复后通过同一任务的恢复机制成功完成。

## 功能修改的意义

本轮证明当前通用关系执行链并非只适用于 Project02。Project03 使用不同的模组编号、有效图和端点恢复策略，但仍可复用相同的模板选择、事务清单、断点执行、只读 CAD 验证和证据封装机制。后续扩展到 Project01/05/06 时，应优先登记可独立执行的关系语义；复合安装模板中的验证项必须经受控拆分，不能直接重放整套安装配合。

## 证据入口

- 候选目录：`demo/global_assembly_contexts/project03-relation-validation-v1/global_module_catalog.project03-validation-v1.json`
- 上下文：`demo/global_assembly_contexts/project03-relation-validation-v1/project03-aa00-ab00-distance5-validation-v1.json`
- 事务清单：`demo/global_assembly_contexts/project03-relation-validation-v1/project03-aa00-ab00-distance5-validation-v1.cad-transaction-manifest.json`
- 外部种子：`demo/global_assembly_contexts/project03-relation-validation-v1/project03-aa00-ab00-distance5-validation-v1.external-seed.json`
- 最终装配体：`demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/project03-aa00-ab00-distance5-validation-v1-packet-002.SLDASM`
- CAD结果：`demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/cad-result.json`
- 持久任务结果：`demo/global_assembly_contexts/project03-relation-validation-v1/job-resume-result.json`

## 后续

1. 将独立只读模板派生能力接入目录构建流程，而不是只生成 Project03 候选目录。
2. 再选择一个 Project03 驱动型关系做 `ADD_RELATION` 预检，但只有在 CAD 判定不过约束时才允许提交。
3. 以相同方法选择 Project05 或 Project01 的只读尺寸关系，验证第三个项目族。
4. 碰撞和 B-rep继续作为可选后验工程验证，不纳入当前自然语言模组装配主线验收。
