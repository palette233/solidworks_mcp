# 自然语言模组装配架构

更新日期：2026-10-19

## 1. 主线目标

系统面向机械工程师，把工程语言描述转换为可解释、可审核、可恢复的模组级装配事务：

```text
自然语言需求
→ 模组角色识别与候选消歧
→ 全局模组目录
→ 语义端口与关系模板匹配
→ 面、边、点稳定恢复
→ 可编辑配合图
→ CAD事务清单
→ SolidWorks真实配合
→ 保存、关闭、重开与证据复核
```

目标不是复制某个原型的顶层位姿，而是在已经登记、发布且证据等级允许的接口范围内，从非原型初始位姿累计安装不同模组。

## 2. 分层职责

### 2.1 自然语言与交互层

- 识别功能角色、数量、顺序、连接意图和工程限定词；
- 当描述对应多个CAD模组时返回候选，由工程师确认；
- 在缺少安装目标、关系歧义或接口不受支持时失败关闭；
- 保存会话修订、用户确认和回滚点。

核心入口：

- `global_assembly_workbench.py`
- `global_assembly_context.py`
- `global_assembly_transactions.py`
- `global_relation_semantics.py`

### 2.2 全局目录与语义端口层

- 全局模组目录为每个独立CAD定义建立稳定ID、项目来源、角色和别名；
- 语义端口描述模组对外可用的安装或工艺接口；
- 面端点目录记录端口所引用的具体面、边、点及恢复策略；
- 关系模板描述两端口之间需要建立的配合束及预期剩余自由度。

核心入口：

- `global_module_catalog.py`
- `semantic_port_catalog.py`
- `face_endpoint_catalog.py`
- `global_relation_template_derivation.py`

### 2.3 配合图与发布层

- 配合图记录模组实例、关系边、端口、具体端点、配合类型和参数；
- 配合图支持新增、修改和删除，但进入CAD执行前必须重新校验；
- 不可变关系发布绑定允许执行的模板、目录摘要和证据等级；
- 默认执行模式为`direct_installation`；`datum_placement_demo`必须显式选择。

核心入口：

- `global_relation_catalog_release.py`
- `global_relation_edits.py`
- `relation_execution_policy.py`
- `driving_relation_release_publisher.py`

### 2.4 编译与持久编排层

- 把确认后的实例图编译为事务DAG和逐包CAD清单；
- 每次只添加一个目标模组，并以上一成功检查点作为下一包输入；
- 支持暂停、恢复、失败保留和从最后成功检查点继续；
- 清单和每包证据均绑定输入摘要、模板发布和执行结果。

核心入口：

- `global_assembly_compiler.py`
- `global_cad_transaction_packets.py`
- `global_cad_manifest_orchestrator.py`
- `semantic_assembly_jobs.py`

### 2.5 SolidWorks执行层

- 从独立子装配体文件插入目标模组；
- 默认采用确定性的非原型初始位姿；
- 通过端点目录恢复几何实体并建立真实配合；
- 保存、关闭、重开后复核配合参数和组件约束状态；
- 不允许用原型顶层位姿、案例锚点或叶级位姿锚点静默补足自由度。

核心实现位于：

- `vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/`
- `scripts/run_context_incremental_insert.py`
- `global_cad_packet_executor.py`

## 3. 主要数据契约

| 对象 | 作用 | 关键边界 |
|---|---|---|
| 全局模组目录 | 标识CAD模组、角色和来源 | 同角色不代表可互换 |
| 语义端口 | 描述接口用途和端点角色 | 不自动证明工艺合理性 |
| 面端点目录 | 恢复具体面、边、点 | CAD拓扑变化后必须复验 |
| 关系模板 | 定义配合束和自由度目标 | 必须绑定证据等级 |
| 装配上下文 | 保存实例与连接关系 | 是可编辑中间态，不是CAD结果 |
| CAD事务清单 | 规定执行顺序和逐包输入 | 编译通过不等于CAD通过 |
| 执行证据 | 保存配合、重开和摘要结果 | 不自动包含碰撞和工艺验证 |

## 4. 成功状态

### Demo装配完成

表示自然语言、端口、配合图和真实CAD累计执行已经闭环。最低要求：

- 模组与关系唯一或已经人工确认；
- 配合全部创建且求解状态被接受；
- 非原型初始位姿规则满足；
- 保存、关闭、重开成功；
- 产物和证据可追溯。

推荐状态名：`DEMO_ASSEMBLED_COLLISION_NOT_EVALUATED`。

### 工程验证完成

在Demo候选上另行完成必要的空间、碰撞和工程复核后，才能升级为`ENGINEERING_STATIC_VALIDATED`。该状态仍不自动代表动态行程、管线、维护空间或生产节拍通过。

## 5. 当前主线与暂缓项

当前主线：

1. 补齐模组角色、机械安装端口和完整定位证据；
2. 建立可连接/不兼容矩阵；
3. 通过非原型初始位姿验证真实配合；
4. 扩展自然语言累计装配链和跨项目组合；
5. 让失败原因、检查点和恢复过程可审计。

独立后验项：

- AABB、B-rep与碰撞；
- 动态全行程；
- 扫码、CCD、点胶可达性等工艺验证；
- 维护空间、线缆与气路；
- 生产参数签认。

## 6. 开发约束

- 新功能应尽量进入现有数据契约，不新增平行的“另一套目录/端口/任务格式”；
- 原型可以提供端点和尺寸知识，但原型顶层位姿只能作为显式标定或只读见证；
- 任何自动跨项目推荐都必须说明证据等级和未验证项；
- 运行证据不得与源码一起大量提交，保存策略见`repository_artifact_policy-CN.md`；
- 修改主线规则时，同步更新`development_execution_rules-CN.md`和进展文档。
