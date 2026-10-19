# 项目02可编辑配合图：删除、修改、新增与重建闭环

> 日期：2026-09-07
> 当前状态：A500–A700基础面配合编辑Demo已完成真实SolidWorks闭环
> 验收结论：`PASS_BASIC_EDITABLE_MATE_GRAPH_DEMO`

## 1. 本阶段目标

在不修改原始导出文件、不重新读取原型配合树的前提下，实现：

```text
只读原型配合图 + 可审计Patch
              ↓ 离线编译与冲突门禁
         Effective Mate Graph
              ↓ MCP按JSON重建
        新SLDASM → 保存 → 关闭 → 重开
              ↓
      回读配合数量、类型、方向和数值
```

这一阶段解决的是“导出的配合能否作为可编辑中间态并真正控制新装配体”，不是项目02全量原型恢复，也不包含实体干涉放行。

## 2. 实现内容

### 2.1 不可变源图与Patch分离

- 原始图保持只读，当前自包含版本为`project02_module_mate_graph_v3.json`；
- Patch支持`removeMate`、`updateMate`、`addMate`；
- `addMate`可复用已导出配合的两个面端点，避免人工重写长面标识；
- 编译结果保存源图SHA-256、Patch SHA-256、逐操作before/after审计记录；
- 每条配合生成稳定`MateId`，同时保留人可读`MateName`。

### 2.2 编译前硬门禁

- 校验Patch版本、模组和配合选择器；
- 校验基准模组仍在有效图中；
- 仅允许当前已实现的基础配合类型；
- 每条基础配合必须恰好引用两个不同模组的面；
- 距离不得为负，距离/角度配合必须有数值；
- 配合名称和ID必须唯一；
- 同一对面上的两个不同距离被判定为冲突并拒绝输出。

### 2.3 JSON驱动的SolidWorks重建

新增MCP接口`RebuildAssemblyFromMateGraph`：

1. 读取Effective Graph，不重新导出原型配合；
2. 插入图中列出的真实子装配体；
3. 应用指定初始放置策略并固定唯一基准模组；
4. 根据端点恢复目标叶零件和面，创建基础配合；
5. 保存新装配体，按文档标题关闭并重新打开；
6. 从新装配体回读配合，核验数量、类型、Alignment、Distance和Angle。

### 2.4 修复的隐藏依赖

初次真实测试发现，旧图未记录子装配体引用配置，直接插入时可能打开错误配置，导致实体/面索引和几何指纹均不能匹配。现已：

- 将`ReferencedConfiguration`加入模组节点，源图升级到v1.3；
- 重建时显式设置引用配置、预加载模组源文档并解析轻量化子树；
- 修正保存后按完整路径关闭失败的问题，改为按SolidWorks文档标题关闭。

其意义是：重建不再依赖“原型此前恰好被打开并激活了正确配置”。

## 3. A500–A700真实闭环结果

测试关系为原型中的`距离8`，原始值50 mm。四组目标装配体均已保存、关闭、重开并回读：

| 场景 | 请求配合 | 创建 | 重开回读 | 参数结果 | 结论 |
|---|---:|---:|---:|---|---|
| 基线50 mm | 1 | 1 | 1 | 50 mm | 通过 |
| 删除`距离8` | 0 | 0 | 0 | 无配合 | 通过 |
| 修改`距离8` | 1 | 1 | 1 | 60 mm | 通过 |
| 新增60 mm并删除旧关系 | 1 | 1 | 1 | 新名称、60 mm | 通过 |
| 冲突输入：同面50/60 mm并存 | — | — | — | 编译阶段拒绝 | 通过 |

关键机器证据：

- `demo/mate_graph_edit/v4/project02_A500_A700_baseline_rebuilt_final.result.json`；
- `demo/mate_graph_edit/v4/project02_A500_A700_delete_rebuilt_final.result.json`；
- `demo/mate_graph_edit/v4/project02_A500_A700_distance60_rebuilt_final.result.json`；
- `demo/mate_graph_edit/v4/project02_A500_A700_replace_distance_rebuilt_final.result.json`；
- 汇总：`demo/mate_graph_edit/v4/project02_A500_A700_editable_closure_final.summary.json`。

新装配体位于同一目录。失败的早期v1/v2/v3文件保留为调试证据，不作为验收结果。

## 4. 代码入口

- 离线编辑器：`apps/demo-backend/src/demo_backend/mate_graph_edit.py`；
- 编译命令：`scripts/compile_mate_graph_patch.py`；
- SolidWorks实现：`vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/AssemblyEditableMateGraph.cs`；
- MCP工具：`vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/AssemblyTools.cs`；
- 真实闭环脚本：`scripts/test_project02_editable_mate_graph.py`；
- Python测试：`apps/demo-backend/tests/test_mate_graph_edit.py`；
- 面目录与离线选择器：`apps/demo-backend/src/demo_backend/face_endpoint_catalog.py`；
- 面目录构建/查询/选面增量脚本：`scripts/build_project02_face_endpoint_catalog.py`、`scripts/query_face_endpoint_catalog.py`、`scripts/capture_selected_face_endpoint.py`；
- SolidWorks面目录实现：`vendor/solidworks-mcp/bridge/SolidWorksBridge/SolidWorks/AssemblyFaceEndpointCatalog.cs`；
- .NET测试：`vendor/solidworks-mcp/bridge/SolidWorksBridge.Tests/SolidWorks/AssemblyEditableMateGraphTests.cs`。

## 5. 回归结果

- Python面目录、选择器、离线编辑与冲突门禁：14/14通过；
- .NET有效图加载、端点ID、类型门禁与参数复核：8/8定向测试通过；
- SolidWorks A500–A700真实重建：4/4场景通过；
- Release构建：0错误、0警告。

## 6. 当前局限

- 当前Demo只开放基础两面配合；Width、Slot等高级配合尚未进入可编辑导入协议；
- 已提供SolidWorks当前选面捕获、指定叶扫描、目录增量合并和按EndpointId自动高亮；尚未接入浏览器候选面列表界面；
- 人工新选面及扫描新增面均已完成真实重建验收；当前交互仍以命令行和SolidWorks视图为主；
- 本轮使用`source_pose`作为A500/A700初始收敛位姿，只证明编辑关系可落入新装配体，不证明纯配合可唯一定位；
- 尚未把全部27条项目02配合通过Effective Graph重建；T401三条面恢复失败和A500/A700过约束审计仍存在；
- 配合成功不等于实体无干涉，AABB/B-rep仍是后续独立验收。

## 7. 后续规划

1. 在展示层增加模组、叶零件、面积、法向和几何类型筛选，并调用现有SolidWorks候选面高亮接口；
2. 为平面候选增加方向分组、相对位置排序和配合类型适配提示，减少人工逐面试选；
3. 将A500–A700 Demo扩展为“小集合编辑”，逐条禁用配合并输出首次过约束点；
4. 为圆柱面、同心、Width和Slot补充专用端点及参数Schema；
5. 在非原型初始位姿下验证基础配合编辑，再处理T401和全量27条恢复。

功能修改意义：把只读配合导出升级为“可审计、可拒绝冲突、可控制真实CAD重建”的中间态，为后续通过增删配合研究欠约束、冗余和装配方案变更提供了可重复实验基础。

## 8. 2026-09-07 面端点目录与选择器第一阶段

已完成以下闭环：

- 新增`solidworks-face-endpoint-catalog/v1`，端点记录模组/叶零件路径、引用配置、Body/Face索引、面积、局部/世界中心、法向、持久引用和恢复置信度；
- `EndpointId`由模组实例、模组配置、叶路径、叶配置、Body/Face索引和几何指纹确定；
- A500/A700种子目录包含2个端点，重复生成后两个ID及持久引用完全一致；
- 离线选择器支持按ID精确选择、按模组/面积/叶路径过滤、两个模组端点兼容性检查和原配合端点匹配；
- Patch新增`endpointIds`语法，编译时从目录展开完整面端点，并记录目录SHA-256；
- 新增`CaptureSelectedFaceEndpoint`，可把SolidWorks当前选中的任意模组面转成目录条目；`capture_selected_face_endpoint.py`以另存新目录方式追加，禁止覆盖原目录。

关键真实测试没有使用`copyEndpointsFromMate`：Patch仅指定
`face:a500:7d587bfd92815e6f`和`face:a700:22da287d7186a8d3`，成功删除原50 mm关系并新增“目录新增距离60”。新装配体保存重开后回读1条配合，名称正确，距离为0.06 m，参数复核通过。

正式证据：

- 目录：`demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_faces_v5.json`；
- 重复稳定性目录：`demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_faces_v6_repeat.json`；
- Patch：`demo/mate_graph_edit/project02_A500_A700_endpoint_ids_distance60.patch.json`；
- Effective Graph：`demo/mate_graph_edit/v5_endpoint_ids/project02_A500_A700_endpoint_ids_distance60.effective.json`；
- 装配体：`demo/mate_graph_edit/v5_endpoint_ids/project02_A500_A700_endpoint_ids_distance60_rebuilt_final.SLDASM`；
- 总结：`demo/mate_graph_edit/v5_endpoint_ids/face_endpoint_catalog_closure_v1.json`。

开发中两次尝试全量遍历A500/A700所有叶面，分别在低面积阈值下出现长时间COM等待，已主动终止且未生成目录。由此将产品策略调整为“原配合端点快速生成种子目录＋指定叶零件/当前选面按需扩展”；目录构建是低频步骤，日常查询和Patch编译不重复扫描CAD。

功能修改意义：新增配合已经从“复制一条旧配合的端点”升级为“用两个稳定EndpointId明确指定两个面”；同时以按需扩展代替无边界全树扫描，降低SolidWorks阻塞风险和日常交互成本。

## 9. 2026-09-07 人工新选面在线闭环

用户在项目02原型中人工选择了一张未参与`距离8`的平面。在线捕获先排除A500归属，随后确认其属于A700：

- EndpointId：`face:a700:a93b6607c982bd3f`；
- 叶零件：`FL5A24D062A720009.01-1`；
- Body/Face索引：`0/0`；
- 面积：约`0.05052885 m²`；
- 世界法向：约`(0,-1,0)`；
- 恢复证据：持久引用＋配置/层级/索引＋几何指纹。

该端点已以不可覆盖方式追加到
`demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_plus_selected_v1.json`，目录由2个端点扩展为3个端点。

为验证它不是“只记录、不可使用”，新增Patch删除原`距离8`，并用A500已知端点与该人工新端点建立`目录新增垂直1`。有效图编译为2个模组、1条配合、0项警告。第一次真实重建已完成配合创建和重开回读，但暴露复核器错误地比较垂直配合Alignment；垂直几何没有aligned/anti-aligned语义，SolidWorks保存重开时会规范化该字段。修正复核规则并增加单元测试后，同一输入重跑结果为：请求1、创建1、重开回读1、参数匹配通过。

正式证据：

- Patch：`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular.patch.json`；
- Effective Graph：`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular.effective.json`；
- 重建装配体：`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular_rebuilt_v2.SLDASM`；
- 结果：`demo/mate_graph_edit/project02_A500_A700_selected_face_perpendicular_rebuilt_v2.result.json`。

回归结果：`.NET`定向测试7/7通过，MCP Release构建0错误0警告；真实SolidWorks保存—关闭—重开闭环通过。本阶段未执行实体干涉检查。

功能修改意义：证明“人工选择一个从未出现在导出配合中的面”能够被独立编号、写入中间数据、在新装配体中恢复并真正参与新配合；同时使参数复核按不同配合类型的实际语义执行，避免把SolidWorks字段规范化误报为重建失败。

## 10. 2026-09-07 指定叶零件扫描与自动高亮闭环

选择A700叶零件`FL5A24D062A720009.01-1`进行受控扫描，原因是该零件已有人工选面真值，且单叶规模可控。新增`BuildLeafFaceEndpointCatalog`后，扫描仅执行以下范围：

```text
A700唯一顶层实例
  → 唯一叶选择器 FL5A24D062A720009.01-1
  → 该叶的1个实体、99个面
  → 平面及面积阈值过滤
  → 34个可复用端点
```

实现增加了100面显式安全上限（接口默认500，可由调用者收紧）、唯一叶选择器门禁、非覆盖输出、源装配体一致性校验和增量目录合并。两个独立真实扫描结果均为34个端点，34/34 `EndpointId`一致。人工选面`face:a700:a93b6607c982bd3f`被局部扫描自动找回；合并时不重复写入，而是记录“人工捕获＋叶扫描”两种恢复证据。种子及人工目录原有3个端点，合并后为36个端点，即新增33个、去重1个。

新增`SelectFaceEndpointFromCatalog`和命令行脚本，可按ID打开/激活源装配体、恢复叶零件及面、在SolidWorks中选中并缩放。人工真值面和纯扫描新增面`face:a700:ac51c9ef4bbe0f43`均以`BodyFaceIndex＋几何指纹门禁`成功高亮。

最终测试没有复用人工选面：使用纯扫描新增面`face:a700:ac51c9ef4bbe0f43`与A500端点建立`叶扫描新增垂直1`，删除原`距离8`。新装配体请求1条、创建1条、保存关闭重开后回读1条，参数匹配通过。

关键证据：

- 首次叶目录：`demo/mate_graph_edit/face_catalog/project02_A700_A720009_leaf_planar_v1.json`；
- 重复稳定性目录：`demo/mate_graph_edit/face_catalog/project02_A700_A720009_leaf_planar_v2_repeat.json`；
- 合并目录：`demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_plus_A720009_leaf_v1.json`；
- Patch：`demo/mate_graph_edit/project02_A500_A700_leaf_scanned_perpendicular.patch.json`；
- Effective Graph：`demo/mate_graph_edit/project02_A500_A700_leaf_scanned_perpendicular.effective.json`；
- 验收装配体：`demo/mate_graph_edit/project02_A500_A700_leaf_scanned_perpendicular_rebuilt_v1.SLDASM`；
- 验收结果：`demo/mate_graph_edit/project02_A500_A700_leaf_scanned_perpendicular_rebuilt_v1.result.json`。

性能与回归：稳定扫描约35.62秒，远低于此前无法完成的全A500/A700叶面枚举；Python面目录与Patch定向测试16/16通过，.NET定向7/7通过，MCP Release构建0错误0警告。本轮只验证面寻址和配合重建，未执行AABB/B-rep。

功能修改意义：面目录从“原配合种子＋逐个手选”升级为“按工程师指定的叶零件批量发现候选面”，同时具备ID高亮和扫描端点驱动重建能力；这为后续浏览器候选列表、T401失败面定位和多配合编辑提供了有边界、可复测的底层路径。

## 11. 2026-09-07 面端点展示层MVP

已把面端点目录接入本地展示页：

- 展示36个A500/A700端点，并按模组、叶零件、世界法向和最小面积筛选；
- 在候选表中分别指定面A、面B，实时检查“不同模组＋平面端点”的基础兼容性；
- 支持重合、垂直、平行、距离、角度五类基础配合输入；
- 生成只读`mate-graph-patch/v1`预览，并调用Effective Graph编译器完成冲突预检；
- 可由浏览器按钮调用MCP，按`EndpointId`在SolidWorks源装配体中恢复、选中并缩放对应面；
- HTTP响应不向浏览器暴露持久引用，仅在服务端目录和SolidWorks恢复链中使用。

实际界面验收选择：

- 面A：`face:a500:7d587bfd92815e6f`；
- 面B：`face:a700:ac51c9ef4bbe0f43`；
- 类型：垂直；
- 结果：Patch预检通过，2个模组、2条Effective Graph有效配合、0项警告；
- SolidWorks高亮：成功，使用`GeometricFingerprint`恢复并缩放A700候选面。

联调中发现两项问题并完成修正：

1. 项目05迁移就绪数据缺少部分可选数值时，旧面板直接调用`toFixed()`造成整页白屏；现改为安全数值格式化，缺值显示`n/a`；
2. `McpToolRunner`按已发布的snake_case名称调用工具，展示层最初使用C#方法名导致`Unknown tool`；现统一调用`select_face_endpoint_from_catalog`。

验证结果：前端TypeScript/Vite生产构建通过；Python面目录、工作台和服务路径定向测试15/15通过；MCP Release构建0错误0警告；本地页面真实完成“筛选—A/B选面—Patch预检—SolidWorks高亮”。

当前边界：页面不创建、覆盖或保存装配体；新叶扫描仍通过脚本执行；只支持平面和五类基础配合，尚未提供圆柱/同心、Width、Slot端点编辑。下一步应增加“应用Patch并另存新装配体”的显式二次确认入口，然后开展A500/A700逐条删边的过约束定位实验。

功能修改意义：把命令行面目录升级为机械工程师可目测、可筛选、可回到SolidWorks核对的交互入口；在真正修改CAD前先生成可审计Patch和Effective Graph，可显著降低选错面和反复重建的成本。

## 12. 2026-09-07 展示层安全应用与A500/A700过约束初诊

展示层已经从“只生成Patch预览”扩展为“人工确认后真实另存并重开复核”。新增流程为：重新计算预览摘要、校验摘要未过期、限制输出到工作区`demo/mate_graph_edit/ui_runs`、拒绝覆盖任何已有文件、写出Patch与Effective Graph，再调用SolidWorks重建、保存、关闭和重开，最后保存结果审计文件。界面只有在用户勾选明确确认后才允许执行。

真实验收使用A500端点`face:a500:7d587bfd92815e6f`与A700扫描端点`face:a700:ac51c9ef4bbe0f43`建立垂直配合。结果为请求2条、创建2条、重开回读2条，参数复核通过：

- 装配体：`demo/mate_graph_edit/ui_runs/project02_A500_A700_ui_20260907T103357Z.SLDASM`；
- Patch：同目录同名前缀`.patch.json`；
- Effective Graph：同目录同名前缀`.effective.json`；
- 结果审计：同目录同名前缀`.result.json`。

同时新增A500/A700过约束证据审计。对既有方案A（原型初始位姿＋配合）、B（纯配合）、C（配合＋残差锚点）的重建结果做交叉分析，三种模式共同出现：首个过定义配合为A600–A700的`宽度10`，随后为A600–A700的`距离29`。没有A500直接参与的配合报告首次过定义；A500通过A500–A700的`距离8`接入已过约束子图，因此A500显示过约束更可能是传播结果。

机器报告：`demo/mate_graph_edit/diagnostics/project02_A500_A700_overconstraint_stage1_v1.json`。报告将`宽度10`列为第一根因候选、`距离29`列为次级候选，结论置信度为跨A/B/C模式重复的高置信证据，但尚未用删边重建证明因果。

下一步只做一个最小隔离实验：保留A600与A700相关关系，仅删除`宽度10`后重建并检查A700是否仍过约束；若消失，再逐步加回`距离8`观察A500状态。当前可编辑图重建器尚不支持Width/Slot的完整编辑语义，需先补齐Width执行或复用全量重建执行器，避免一次运行多组耗时SolidWorks实验。

功能修改意义：展示层已经具备“选面—预检—明确确认—真实另存—重开复核—审计留痕”的完整安全闭环；过约束排查也从反复目测转为基于三组结果的最小因果实验，后续只需验证最可能的单条根因边。

## 13. 2026-09-07 A600/A700过约束最小隔离实验

围绕A/B/C三种恢复均首先报告的`宽度10`，进行了两次严格限定为A600+A700的真实重建。两次均从不可变原型配合图编译独立Effective Graph，以A600为固定基准并使用源位姿作为收敛初值，不修改原型文件。

实验一仅删除`宽度10`，保留`平行1、平行2、距离6、重合38、距离29`。SolidWorks请求5条、创建5条、保存重开回读5条且参数一致，耗时248.10秒；但`距离29`仍返回`swAddMateError_OverDefinedAssembly`，说明`宽度10`不是唯一触发项。

实验二同时删除`宽度10`与`距离29`，保留其余4条。SolidWorks请求4条、创建4条、保存重开回读4条且参数一致，耗时214.98秒；4条配合创建均返回`swAddMateError_NoError`。对应装配体：

- `demo/mate_graph_edit/diagnostics/project02_A600_A700_without_width10_stage2_v1.SLDASM`；
- `demo/mate_graph_edit/diagnostics/project02_A600_A700_without_width10_distance29_stage2_v1.SLDASM`。

重要边界：A/B/C结果保存的原型源特征状态表明，`宽度10`与`距离29`在原型中`SourceFeatureErrorCode=0`且不是Warning。因此本实验只能证明“当前重建语义下两条关系依次触发过定义”，不能证明原型配合设计错误，也不应立即把删除两条关系变成通用规则。可能差异包括A700刚/柔性状态、Width高级参数、配合创建顺序以及重开后求解器规范化。

新增通用单图重建脚本`scripts/run_effective_mate_graph_rebuild.py`，记录输入SHA-256、开始/结束时间、耗时、CAD结果并禁止覆盖。机器对照报告：`demo/mate_graph_edit/diagnostics/project02_A600_A700_overconstraint_stage2_v1.json`；定向回归13/13通过。

下一步应增强可编辑图闭环结果：记录重开后每个顶层模组的`GetConstrainedStatus()`，并把源`SolvingState`和Width高级参数纳入中间数据；随后用完整语义重建一次包含全部6条关系的A600+A700基线。只有在完整语义仍过约束时，才讨论冗余关系删减。本阶段未执行AABB或B-rep。

功能修改意义：通过两个最小可复现实验区分了“源设计错误”和“重建语义不完整”；避免把暂时能消除错误码的删边方案误当成正确工程规则，同时为后续刚柔性和高级配合复原提供了明确验收标准。

## 14. 2026-09-07 完整配合语义基线闭环

在不删除任何原型关系的前提下，已完成A600+A700全部6条配合的真实重建。中间图升级为`solidworks-module-mate-graph/v1.4`，新增两类此前缺失的工程语义：顶层组件`SolvingState`（刚性/柔性）以及Width高级参数（宽度面组、舌片面组、约束类型、百分比/距离和翻转状态）。重建时先恢复A600刚性、A700柔性，再按源顺序创建全部配合；保存、关闭、重新打开后同时复核配合数量、参数、创建错误、组件过约束状态和刚柔性状态。

真实结果为：请求6条、创建6条、重开回读6条，全部创建返回`swAddMateError_NoError`；Width10高级选项一致；A600为刚性且完全约束，A700为柔性且欠约束，但两者均不过约束，组件刚柔性与源图一致。A700的“欠约束”是柔性子装配体保留内部自由度的正常表现，不是失败。

关键产物：

- 完整语义源图：`demo/layout_previews/project02_A600_A700_module_mate_graph_semantics_v1.json`；
- Patch：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_baseline_v1.patch.json`；
- Effective Graph：同目录同名前缀`.effective.json`；
- 新装配体：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_baseline_v1.SLDASM`；
- 重建审计：同目录同名前缀`.result.json`；
- 根因报告：`demo/mate_graph_edit/diagnostics/project02_A600_A700_full_semantics_audit_v1.json`。

根因结论已由“可能是Width10/Distance29冗余”修正为：原有重建图遗漏A700的柔性求解状态，导致同一组健康配合在刚性重建环境中依次报告过定义。Width高级参数也必须持久化，但旧方案A曾在运行期传入该参数，因此本次消除过约束的决定性变化是恢复A700柔性。删除Width10或Distance29不再作为推荐方案。

展示层严格验收结果已增加三项字段：创建错误是否清零、组件是否不过约束、组件刚柔性是否一致。前端生产构建、Python定向测试24/24、.NET定向测试29/29均通过；后端健康检查和浏览器展示页复核通过。本阶段仍未执行AABB/B-rep，因此只证明“配合语义与求解状态闭环”，不能据此宣称实体零干涉。

下一步：将v1.4语义扩展到项目02完整顶层模组图，先做离线图完整性审计，再进行一次完整项目02重建；只有配合语义验收通过后，才进入分层AABB与条件B-rep检查，避免把几何干涉诊断与配合语义缺失混在一起。

功能修改意义：证明原型的全部A600+A700关系可以在不删边的情况下恢复，并把“成功”从配合数量相等提升为配合参数、创建错误、组件约束状态和刚柔性状态共同通过；由此消除了一个会误导后续图编辑与原型复原的关键语义缺口。
