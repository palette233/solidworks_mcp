# 已有组件配合编辑与多轮自然语言装配进展

更新日期：2026-10-10

## 1. 本轮目标与优先级

本轮按以下顺序推进，不把实体干涉或完整 B-rep 作为主线阻塞项：

1. 已有组件直接新增、修改或删除配合；
2. 多配合与自由度闭合分析；
3. 刚性/柔性子装配体的通用执行策略；
4. 多轮自然语言有序装配；
5. 跨项目语义端口覆盖审计。

当前 Demo 验收仍要求：输入与图补丁可追溯、面端点可恢复、配合求解可解释、源文件不被覆盖、结果保存重开可复核。碰撞状态单独记录为“未评估”。

## 2. 阶段一：已有组件直接编辑配合

### 功能修改

- `PatchAudit`成为执行依据：
  - `addMate`只创建新增配合；
  - `updateMate`只抑制旧配合并创建修改后的配合；
  - `removeMate`只抑制被删除的配合。
- 目标组件不再默认删除、重插或主动移到实验位置。
- 未携带`PatchAudit`的历史有效图继续走旧的重配实验路径，保持兼容。
- 新增独立运行脚本`run_context_direct_mate_edit.py`，在执行前后验证源装配体SHA-256，并明确检查目标没有重插和主动位移。

### 真实 CAD 闭环

以 Project02 A700—A600 已选面重合配合为例：

- 执行模式：`direct_existing_component_mate_edit`；
- 新增配合：`NL_A700_A600_934b24255e`；
- 目标组件重插：否；
- 目标组件主动位移：否；
- 保存重开参数一致：是；
- A700最终完全约束：是；
- 源装配体SHA-256不变：是；
- v1耗时：95.056秒。

实体：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a700-a600-direct-mate-edit-v1.SLDASM`

意义：系统从“为了增加一条关系而重建整个模组”推进为“直接编辑现有装配语义”，减少柔性状态丢失和无关位姿扰动。

## 3. 阶段二：多配合与自由度闭合

- 新增六列刚体约束雅可比分析：`tx, ty, tz, rx, ry, rz`。
- 当前已线性化平面重合、距离、平行和垂直关系；未知几何或未支持的关系不乐观计入约束秩。
- 结果明确区分“案例位姿当前保持”和“配合本身独立闭合六自由度”。

测试结果：

- 单一重合面：约束秩3，剩余3自由度；
- 两个非平行重合面：约束秩5，剩余1自由度；
- 三个正交重合面：约束秩6，理论闭合；
- 缺少法向等几何证据：保持6自由度并报告不支持原因。

意义：后续选面向导可以告诉使用者为什么还需要第二基准面、孔轴或第三基准，而不是只看当前模型是否暂时停在某个位置。

边界：该分析是解释性刚体秩估计，SolidWorks保存重开后的真实求解状态仍为最终依据；圆柱轴、槽口、宽度等高级关系还需继续补充线性化模型。

## 4. 阶段三：刚性/柔性通用策略

- 直接编辑已存在的柔性组件：保留父装配上下文，不要求为了新增配合而重插；保存重开前后必须比较柔性根节点和所有语义端点叶节点指纹。
- 重新插入柔性目标：必须提供内部叶位姿锚点或权威命名状态，否则失败关闭。
- 刚性目标：无需内部柔性状态锚点，但仍须验证求解状态和保存重开。

Project02 A700现场v2复核：

- 根节点及端点叶节点指纹：2/2稳定；
- 最大变换矩阵误差：0；
- 保存重开、配合参数与源文件哈希：通过；
- 总耗时：89.985秒，其中重建配合42.789秒、保存关闭28.309秒、重开验证9.754秒。

实体：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a700-a600-direct-mate-edit-v2-flex-audit.SLDASM`

意义：A700专用锚点经验被提升为按执行模式选择的通用刚柔性策略。

## 5. 阶段四：多轮自然语言有序装配

- 新增`apply-sequence`接口：一组自然语言命令逐条以最新内存上下文解析。
- 任一轮存在模组歧义、端口歧义或缺少兼容关系时，整批上下文零写入。
- 全部轮次就绪后原子写入最终上下文，并把每个中间修订写入`assembly-conversation/v1`会话台账。
- 保留单轮接口，因此既支持“逐轮确认后继续”，也支持“提交一组已经明确的有序命令”。
- CAD执行仍为独立显式动作，不因写入语义图自动启动。

测试已覆盖：A600→A800两轮提交、会话恢复，以及第二轮未知模组导致整批零写入。

意义：自然语言不再只是一次性生成完整固定序列，而可以持续追加并从最近检查点继续。

## 6. 阶段五：跨项目端口覆盖

生成证据：`demo/global_assembly_catalog/v1/cross_project_port_readiness.json`

- Project01：8/8模组具有语义图端口覆盖；
- Project02：9/9；
- Project03：8/8；
- Project05：9/9；
- Project06：缺少版本化项目配置，明确阻塞，未生成虚构端口。

当前全局目录累计34个模组定义、74个语义端口、61条兼容关系。

意义：已经具备跨项目自然语言检索和语义连接的统一中间层，同时把“图层可连接”与“现场CAD端点已跨项目实证”分开表述。

## 7. 当前剩余工作

1. 为圆柱面/孔轴、槽口、切线等高级配合补充自由度模型；宽度居中已增加保守的一维中心面约束模型。
2. 建立Project06版本化配置、模组身份和首批语义端口。
3. 在项目01、03、05各选一组真实多配合执行案例，验证通用事务与检查点机制不依赖项目02。
4. 按用户当前范围，实体干涉/B-rep仍为可选工程验证，不作为上述功能完成的门槛。

### 延期待办：前端与鼠标点选

- 将自由度分析接入前端配合确认区，展示约束秩、剩余自由度、矛盾关系和推荐下一基准；
- 支持在同一事务中用鼠标连续选择第二、第三组面、轴、边或点；
- 增加选中端点高亮、所属模组、几何类型、法向/轴向和稳定端点编号展示；
- 增加事务预览、人工确认、失败原因和检查点切换界面。

延期原因：这些内容属于输入与展示产品化，不影响后端继续验证已有面目录、配合图、自由度预检、CAD直接编辑、原子发布和检查点续装。重新启动前端工作前，后端接口和证据格式必须保持版本化，避免届时重复改界面。

## 8. 回归测试结论

- 后端全量回归：684项通过，另有3个subtests通过；
- 本轮C#定向测试：21/21通过；
- C#全量测试：354项通过，2项既有可视化集成测试失败，原因分别是测试客户端明确不暴露`ResolveComponentTarget`和`ListComponents`，与本轮配合编辑代码无关；
- MCP Release构建：通过，0错误；
- 前端TypeScript/Vite生产构建：通过；
- Python编译检查：通过。

## 9. 真实多配合事务与会话检查点闭环（2026-10-10）

### 真实数据选择

- A700—A600当前只登记了一对真实选面，因此没有虚构第二、第三基准来制造“六自由度闭合”。
- 改用原型配合图中已有的A500—A600三关系：Y向重合、Z向宽度居中、X向距离。
- 三条关系均携带真实叶零件路径、实体/面索引、世界法向和面中心。

### 新增能力

- 新增`direct-mate-transaction-preflight/v1`：要求`PatchAudit`、操作序号连续、目标局部图不混入无关配合，并可配置“必须多操作”和“必须六自由度闭合”。
- 同一端点上的“重合+非零距离”或“平行/重合/距离+垂直”等确定性矛盾会在编译阶段直接拒绝，不启动SolidWorks。
- 自由度模型增加宽度配合的保守线性化：只把宽度中心面偏移计为一个独立约束，不夸大其旋转约束能力。
- `run_context_direct_mate_edit.py`改为临时文件执行；只有CAD重建、保存、关闭、重开和参数复核通过后，才原子发布正式文件。失败临时件不进入正式输出路径。
- 新增直接配合执行绑定：复核源/输出哈希、执行模式、保存重开和组件语义后，把结果登记为会话当前修订的最新实体检查点。
- 新增后端接口`POST /api/demo/global-assembly-contexts/{context_id}/direct-mate-executions/bind`，必须显式确认。

### 真实CAD结果

- 预检：约束秩6，剩余自由度0，不支持关系0；
- 批量操作：3条`updateMate`一次提交；
- SolidWorks创建/替换：3/3；
- A500最终状态：完全约束；
- 保存重开参数：一致；
- 目标删除或重插：否；
- 主动位移目标：否；
- 源装配体SHA-256：执行前后均为`4e686e861b08360d2b8fec2663019c01a7a3680cdc88c453f8a69b6812519f17`；
- 发布实体SHA-256：`afc0706d8b7b554440a15f4cad12c6c0562f2295ab6df56c7aa676b64110a50c`；
- 总耗时：94.719秒，其中CAD重建45.084秒、保存关闭28.584秒、重开复核7.197秒。

正式实体：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a500-a600-three-mate-direct-edit-v1.SLDASM`

执行证据：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a500-a600-three-mate-direct-edit-v1.direct-mate-edit.result.json`

会话台账已将其登记为修订10的最新实体检查点`direct-mate-6f509850028c5ff3`；下一次检查点配合图导出已验证会指向该新实体，而不是旧尾链装配体。

本次修改的意义：多配合不再是逐条试写，而是在CAD启动前整体判断数据完整性和自由度闭合；CAD失败不会发布半成品，成功结果可以继续进入下一轮自然语言/选面编辑。

## 10. 任意直接编辑实体检查点续装（2026-10-10）

- `GlobalProjectAdapterJobCreateRequest`新增`seedEditId`，并与历史`seedJobId`互斥。
- 会话台账可按编号唯一恢复直接配合实体检查点，且只接受状态成功的检查点。
- 续装计划复核来源任务编号、实体SHA-256和执行证据SHA-256，再把编辑后实体替换为下一段任务的`seedCheckpoint`。
- 新执行范围标记为`validated_direct_edit_continuation`，保留`seedJobId`、`seedEditId`和原工艺步骤位置。
- 单元闭环以Project05两步前缀验证：D000完成后生成直接编辑实体，再创建K000续装任务；K000的初始检查点明确指向编辑后实体，而不是D000原始输出。
- Project02当前十对象实例已经位于既有计划末端，没有剩余原计划步骤可续跑；后续新增模组或中间步骤编辑可使用该能力。

本次修改的意义：直接配合编辑不再形成“只能查看、不能续装”的旁路产物，而成为持久装配任务可验证的正式输入。

## 11. 高级配合自由度与跨项目事务推进（2026-10-10）

### 圆柱同轴配合

- 配合图端点新增向后兼容的解析圆柱字段：曲面类型、圆柱轴线原点、局部/世界轴向和半径。
- 刚体自由度分析对具有完整圆柱证据的同轴配合计入四个独立约束：两个横向平移和两个轴向旋转；轴向平移与绕轴旋转仍保留。
- 缺少圆柱轴线或两轴不平行时失败关闭，不再把“圆柱面索引存在”误当作同轴语义已经充分。
- 槽口等仍缺少方向几何的高级关系继续明确阻断，等待真实几何字段后再建模。

意义：自由度预检开始覆盖真实机械常用的孔轴关系，同时坚持“有几何证据才计秩”，避免在CAD执行前虚假宣称完全约束。

### Project06身份层接入

- 新增Project06版本化配置，登记9类模组、13个实例的身份、别名、来源装配体和功能分类。
- 当前状态严格标为`identity_only_cad_unvalidated`：可以检索和解析模组，但没有虚构语义端口、兼容关系或CAD适配器。
- 跨项目就绪审计现能区分“可搜索”与“可装配”：Project06为9/9可搜索、0/9具备语义端口，发布门禁保持关闭。

意义：五个项目已经进入同一个全局身份目录；Project06的缺口可被机器审计，而不是以缺少配置的形式隐藏。

### 通用真实模组对事务生成器

- 新增`scripts/build_pair_multi_mate_transaction.py`，可从任意真实配合图抽取指定模组对的全部关系，生成源子图、补丁、有效图、自由度预检和清单。
- 生成器要求至少两条关系、端点持久引用完整、所有活动关系严格属于指定模组对，并要求自由度秩达到6；不满足即不进入CAD。
- Project05重新导出的真实配合图包含13个模组、31条跨模组配合和10个配合束；D000—A000的重合、距离和宽度关系通过事务预检，秩6、残余自由度0。

事务证据：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/multi-mate-d000-a000-v1/manifest.json`

意义：多配合事务已从Project02专用脚本提升为跨项目可复用能力。

### Project05现场CAD验证闭环

- 前六轮复制后重开实验暴露了轻量化深层叶组件不可访问的问题；全部失败副本进入`_failed_transactions`，正式输出路径未被污染，源文件SHA-256始终不变。
- 已修复原型迁移后的顶层定位：优先使用装配层级身份，绝对磁盘路径仅作辅助，因为Project05仍携带供应商旧路径引用。
- 新增“保持已解析源会话”执行模式：先在活动原型会话中导出并验证全部配合端点，再将该内存装配`Save As`为临时工作副本，随后执行配合事务；不再复制后以轻量状态重新打开，也不递归解析整个A000。
- D000—A000三条真实配合在该模式下全部创建/替换成功；保存、关闭、重开、配合参数、完全约束状态和组件语义均通过，正式输出已原子发布。
- 总耗时109.181秒：已解析会话另存11.285秒、三配合重建15.839秒、保存关闭19.023秒、重开复核54.392秒。
- 源装配体SHA-256前后均为`15427a62932ed4d3d34872cadc41b8f73e89ab9ddfa08491c89d4bc067a0167c`；输出SHA-256为`132090130f81f0d02082492cfa56d8d83a89c668b80e479d2729a020b021a380`。

正式实体：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-three-mate-resolved-session-v7.SLDASM`

执行证据：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-three-mate-resolved-session-v7.direct-mate-edit.result.json`

审计证据：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-direct-edit-audit.json`

后续迁移原则：大型轻量化原型优先使用“同一SolidWorks会话内导出—端点验证—另存—执行”；只有无法保持会话时才考虑版本化端点缓存/定向叶组件解析器，禁止为解决一个端点而同步解析整个大型根模组。

### 单命令编排器

新增`scripts/run_resolved_session_pair_transaction.py`，将以下步骤收敛为一次命令：

1. 在读取原型前记录源SHA-256；
2. 在同一SolidWorks会话导出指定模组对配合图并保持端点已解析；
3. 生成源子图、补丁、有效图、自由度预检和事务清单；
4. 在活动源会话中验证全部端点并另存临时装配体；
5. 批量编辑配合，保存、关闭、重开并复核；
6. 成功后原子发布，失败后归档临时件；
7. 输出各阶段耗时、文件摘要和完整CAD证据。

Project05真实单命令结果：

- 总耗时171.311秒；
- 图导出与端点解析63.954秒；
- 事务编译与预检0.019秒；
- 同会话CAD执行107.240秒；
- 3/3配合成功，秩6、残余自由度0；
- 保存重开、配合参数、完全约束状态、组件语义与源文件不变均通过。

最新正式实体：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-single-command-v8.SLDASM`

最新执行证据：`demo/global_assembly_contexts/checkpoint-graphs/project05-prototype-v1/executions/project05-d000-a000-single-command-v8.resolved-session.result.json`

示例命令：

```powershell
python scripts/run_resolved_session_pair_transaction.py `
  --source <原型.SLDASM> `
  --target D000 --context A000 `
  --output <新装配体.SLDASM> `
  --work-dir <本次事务目录> `
  --direct-stdio
```

## 12. 本轮测试闭环（2026-10-10）

- 后端全量回归：693项通过，另有3个subtests通过；包含单命令成功发布、CAD异常归档、底层同会话成功与失败路径；
- C#配合图与装配服务定向测试：51/51通过；
- MCP Release构建：通过，0错误；
- Python编译检查：通过；
- Project02、Project05派生上下文已重新绑定加入Project06后的新全局目录摘要，旧摘要不会被静默接受。

本轮没有执行实体干涉/B-rep；这符合当前开发范围，碰撞状态不得由配合事务成功推断。

## 13. 项目01与项目03跨项目实证（2026-10-10）

### Project01：BD00—JJ00

- 真实关系：同轴12、同轴13、重合7；
- 新圆柱模型分别贡献4、1个独立约束，平面重合再贡献1个，总秩6、残余自由度0；
- 3/3配合成功，BD00完全约束；保存重开、参数、组件语义和源摘要全部通过；
- 总耗时178.344秒，其中图导出67.963秒、编译预检0.023秒、CAD执行110.256秒。

正式实体：`demo/global_assembly_contexts/checkpoint-graphs/project01-prototype-v1/executions/project01-bd00-jj00-single-command-v1.SLDASM`

### Project03：AB00—AA00

- 真实关系：重合25、宽度1、距离5；
- 保守自由度模型分别贡献3、1、2个独立约束，总秩6、残余自由度0；
- 新导出器恢复了宽度面/凸耳面索引与宽度约束类型，旧图缺字段的问题没有通过默认值绕过；
- 3/3配合成功，AB00完全约束；保存重开、参数、组件语义和源摘要全部通过；
- 总耗时211.535秒，其中图导出71.907秒、编译预检0.024秒、CAD执行139.501秒。

正式实体：`demo/global_assembly_contexts/checkpoint-graphs/project03-prototype-v1/executions/project03-ab00-aa00-single-command-v1.SLDASM`

跨项目统一审计：`demo/global_assembly_contexts/cross-project-pair-transaction-closure-v1.json`

阶段结论：同一事务内核已在项目01、02、03、05四个原型上完成真实CAD闭环，覆盖“两同轴+一重合”和“重合+宽度+距离”两类典型安装关系；Project06仍保持身份层可检索、CAD未验证的诚实边界。

## 14. 语义连接到持久真实CAD任务闭环（2026-10-10）

### 新增后端能力

- 新增版本化来源注册表`resolved_pair_transaction_sources.json`。项目01、02、03、05绑定真实原型路径；Project06明确禁用并记录阻塞原因。
- 新增`resolved_pair_transaction_jobs.py`，把已提交的全局语义连接唯一解析为项目、目标模组、基座模组、源装配体SHA-256和单步真实事务计划。
- 任务创建只写持久状态，不启动SolidWorks；任务启动必须二次提交`contextDigest`和`planDigest`，任一连接、模组映射、目录或源文件变化都会失败关闭。
- 默认幂等键来自稳定`planDigest`，因此仅`compiledAt`变化不会重复创建任务。
- 任务按尝试保存独立输出、事务目录、stdout/stderr和结果证据；失败可恢复重试，旧尝试不会被覆盖。
- 后端增加计划、创建、启动、恢复和查询接口；真实CAD执行通过全局互斥锁串行进入SolidWorks。

接口路径：

- `GET /api/demo/global-assembly-contexts/{contextId}/connections/{connectionId}/resolved-pair-plan`
- `POST /api/demo/global-assembly-contexts/{contextId}/connections/{connectionId}/resolved-pair-jobs`
- `POST .../resolved-pair-jobs/{jobId}/start`
- `POST .../resolved-pair-jobs/{jobId}/resume`
- `GET /api/demo/resolved-pair-jobs/{jobId}`

### Project05真实持久任务

- 上下文：`project05-full-static-graph-v1`；连接：`connection-001`；编译为D000相对A000的三配合事务。
- 任务：`project05-job-2fd5dca2ddd7`；状态`succeeded`；装配状态`assembled`；碰撞状态`not_evaluated`。
- 自由度预检：秩6、残余自由度0；SolidWorks创建/替换3/3配合；保存重开参数一致；D000完全约束；组件语义一致。
- 源装配体SHA-256执行前后均为`15427a62932ed4d3d34872cadc41b8f73e89ab9ddfa08491c89d4bc067a0167c`。
- 正式实体SHA-256：`eb4ea21dede7e9603d308c19a4204423f6a0cbd7ee8ee63d4800d91929e340e1`。
- 持久任务总耗时184.452秒；内部事务183.981秒，其中图导出与端点解析74.333秒、编译预检0.023秒、同会话CAD执行109.532秒。

正式实体：`demo/semantic_ports/project05_resolved_pair_jobs/project05-job-2fd5dca2ddd7/attempt-01/project05-job-2fd5dca2ddd7-d000-a000.SLDASM`

任务台账：`demo/semantic_ports/project05_resolved_pair_jobs/project05-job-2fd5dca2ddd7/job.json`

完整证据：`demo/semantic_ports/project05_resolved_pair_jobs/project05-job-2fd5dca2ddd7/evidence-manifest.json`

本次修改的意义：此前的单命令能力已经升级为可由语义连接触发、可双重确认、可查询、可失败恢复且有持久证据的后端作业；自然语言图层不再需要直接管理SolidWorks进程和临时文件。

### 测试闭环

- 新任务模块测试：6项通过，覆盖真实计划编译、默认幂等、成功提交、失败关闭、API双确认和摘要变化拒绝。
- 后端全量回归：699项通过，另有3个subtests通过。
- 本轮未执行实体干涉/B-rep；配合与保存重开成功不得表述为碰撞通过。

## 15. Project02独立累计插入闭环（2026-10-10）

### 从“编辑原型”切换到“独立逐步装配”

- Project02的语义连接`connection-001`不再以完整原型为执行源，而是从仅含A600的独立基座装配体插入全新的A800。
- `connection-002`必须显式指定前一步成功任务的`seedJobId`，从其A600+A800实体检查点继续插入全新的A180；缺少种子、种子项目不符、状态不是成功、末步不是A800、实体或证据摘要变化均失败关闭。
- 后端计划、创建和启动接口均传递并复核种子绑定；计划摘要同时绑定上下文、源实体、上一步证据和当前有效配合图。
- 独立插入脚本在保存重开复核后主动关闭输出文档，使其能够被下一阶段可靠读取、校验摘要并作为累计输入。

### 端点恢复修复

- A800首次独立插入暴露出同一支撑面的面积在不同装配上下文中约有2.75%差异，而包围盒、中心和法向保持一致。
- 面指纹匹配保持面积严格优先；只有面积漂移不超过5%，且包围盒与中心均在`1e-4 m`内严格吻合时才接受降级恢复，法向仍严格校验。
- 该规则不是一般模糊猜面：缺少包围盒/中心证据或面积、位置明显漂移时仍拒绝。

### 真实CAD结果

1. A600→A800：任务`project02-job-fe64d9d23a25`成功；2/2配合，A800完全约束，保存重开参数一致，组件语义一致，源不变，输出关闭；耗时50.466秒。
2. A600+A800→A180：任务`project02-job-0baa5e819a88`成功；2/2配合，A180完全约束，保存重开参数一致，组件语义一致，上一步实体不变，输出关闭；耗时44.002秒。

三模组累计实体：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-0baa5e819a88/attempt-01/project02-job-0baa5e819a88-a180-a600.SLDASM`

A800任务证据：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-fe64d9d23a25/evidence-manifest.json`

A180任务证据：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-0baa5e819a88/evidence-manifest.json`

回归闭环：独立累计任务定向测试11/11通过；后端全量704项及3个subtests通过；C#端点/配合定向测试25/25与MCP Release零错误构建保持有效；修改文件通过`git diff --check`。

本次修改的意义：全局语义连接第一次驱动了Project02真实的独立累计建模链；结果不依赖完整原型中预先存在的A800/A180，也不以原型初始顶层组件充当装配结果。碰撞仍为`not_evaluated`，本结论只覆盖配合、位姿约束、保存重开、语义和来源完整性。

## 16. Project02服务模组累计装配与下游工艺关系闭环（2026-10-10）

### 约束策略细化

- 独立安装档案新增`constraintRequirement`：普通刚性模组必须`fully_constrained`；A700等柔性机构允许`accepted_flexible_or_fully_constrained`，但仍必须由SolidWorks确认约束状态可接受且求解干净。
- A700、A300、A500均改为显式消费上一阶段成功任务；最近检查点分别必须是A180、A700、A300，禁止跳步或使用未签认文件。
- A500除了自身3条安装配合外，还保留A500—A700的50 mm工艺间距作为重开后的验证关系；局部配合成功但工艺间距失败时，整个任务必须拒绝。

### 发现并修正A700残余位姿问题

第一版A700任务`project02-job-1bc5ee399a0d`建立6/6真实配合并通过柔性求解门禁，但这些配合允许A700根部存在合法残余位姿。沿该分支安装A500时，任务`project02-job-6bcc438ea13c`虽然完成3/3配合、完全约束、保存重开和语义复核，A500—A700间距却从目标50 mm偏离为约1.128 m，因此被事务门禁拒绝，输出进入隔离区，累计检查点没有推进。

新增`static_installation_effective.json`，同时保留：

1. A700相对A600的6条真实安装配合；
2. 项目02原型标定的根位姿分支锚点，明确不是厂商基准；
3. A730与A721两个内部静态状态锚点，明确不代表动态工艺已验证。

修正版A700任务`project02-job-2fdc4c694816`通过：6/6配合、根位姿吻合、2/2内部锚点应用、保存重开后最大变换元素误差约`8.88e-14`，目标完全约束，耗时55.937秒。

### 最新累计链结果

- A300任务`project02-job-9ecc914162c2`：3/3配合，完全约束，保存重开、参数、语义、输出关闭和源不变均通过；耗时50.667秒。
- A500任务`project02-job-7d59620b9434`：3/3配合，完全约束，保存重开与全部门禁通过；A500—A700目标距离0.05 m，实测`0.049999999999941425 m`，绝对误差约`5.86e-14 m`；耗时50.720秒。

最新六模组累计实体：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-7d59620b9434/attempt-01/project02-job-7d59620b9434-a500-a600.SLDASM`

完整任务证据：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-7d59620b9434/evidence-manifest.json`

回归闭环：服务模组与持久任务联合定向测试19/19通过；后端全量707项及3个subtests通过；碰撞/B-rep仍为`not_evaluated`。

本次修改的意义：累计装配不再以“每个新模组局部装上”为充分条件，而开始验证新步骤对既有模组间工艺关系的影响；错误分支被自动拒绝，修正后的约束重新求解，而不是人工移动失败实体。

## 17. Project02十对象独立累计装配闭环（2026-10-10）

### 后续静态模组闭环

- A100任务`project02-job-0e2436fad5c6`：从A500成功检查点插入龙门，3/3顶层安装配合、完全约束、保存重开、参数与语义均通过，耗时63.219秒。该结论只覆盖龙门顶层安装，不覆盖内部运动状态、权威行程或工艺点扫掠。
- A200任务`project02-job-76a3eba2bb07`：从A100检查点插入CCD，1条重合和2条槽口配合均重建成功；案例锚点、完全约束、保存重开及语义均通过，耗时83.074秒。CCD工作距离、视场及光路通道仍未验证。
- T401第一实例任务`project02-job-dd84e4c4dd81`：相对A600建立重合与距离关系，2/2配合、完全约束和重开门禁通过，耗时69.496秒。
- T401第二实例任务`project02-job-0ff50cfd2992`：相对A200建立距离关系，1/1配合、完全约束和重开门禁通过，耗时69.112秒；插入名称为`T401AA-07388-0-2`，第一实例未被误删或替换。

### 非基座上下文与重复实例

- 独立安装编译器不再一律要求连接的一端必须是A600；若版本化注册表明确声明唯一的目标/上下文安装档案，可执行T401→A200这类非基座上下文连接。
- 未登记的非基座连接仍失败关闭，不允许仅凭自然语言或令牌顺序猜测目标端。
- 同一CAD定义的重复实例由有效图中的层级路径区分；第二个T401插入时必须保留第一个实例。

### 终态链审计

新增`resolved_pair_transaction_chain.py`与命令行审计器，从终态任务反向核验每一级`seedJobId`、输入/输出实体SHA-256、证据SHA-256、源文件不变、输出关闭及模组顺序。真实终态审计结果：

- 插入顺序：A800→A180→A700→A300→A500→A100→A200→T401→T401；
- 9个持久作业、A600加9次插入，共10个顶层对象；
- 注册顺序与实际链完全一致，全部输入均为前一步签认输出；
- 各步执行耗时合计约536.979秒；
- 静态累计装配与保存重开证据闭环；碰撞状态仍为`not_evaluated`，生产放行仍为`false`。

最终实体：`demo/semantic_ports/project02_resolved_pair_jobs/project02-job-0ff50cfd2992/attempt-01/project02-job-0ff50cfd2992-t401-a200.SLDASM`

链审计：`demo/semantic_ports/project02_resolved_pair_jobs/project02-full-static-chain-audit-v1.json`

本次修改的意义：Project02已从“若干可用的单步实验”升级为可追溯、不可跳步、支持非基座上下文和重复实例的完整静态累计装配链；同时继续诚实地区分静态装配证据与碰撞、动态、光学及维护验证。

## 18. 原型依赖审计与非原型初始位姿实验（2026-10-10）

### 审计结论

- 当前9个插入步骤全部使用从项目02原型提取的真实配合面和配合参数；因此“去顶层位姿依赖”不等于“完全不使用原型知识”。
- 7步含顶层案例位姿锚点；A500与A100原本已经采用确定性非原型初始位姿。
- A700另含A730、A721两个原型内部静态状态锚点；本轮只移除顶层案例锚点，保留这两个内部状态，以隔离实验变量。
- A600独立基座及其单位坐标基准仍来自项目02案例，本轮没有替换机器安装基准。

### 实验方法

对7个含案例锚点的步骤生成独立消融图：

1. 清空`caseAnchoredModuleTokens`；
2. 将初始放置模式改为确定性非原型位姿；
3. 保留真实配合、面端点和高级配合参数；
4. 每一步分别使用其已签认的上游检查点，插入全新目标实例；
5. 复核配合创建、约束状态、保存重开、参数、组件语义和源文件不变；
6. 失败输出只作为诊断证据，不进入正式累计链。

7次新CAD实验累计测量耗时约401.895秒；A500、A100直接复用其已经无案例锚点的正式持久任务证据。

### 结果

| 模组关系 | 配合创建 | 完全约束 | 非原型初始位姿门禁 | 结论 |
| --- | ---: | ---: | ---: | --- |
| A800→A600 | 2/2 | 否 | 失败 | 缺少纵向安装基准/厂商XYZ偏置或定位挡块 |
| A180→A600 | 2/2 | 否 | 失败 | 缺少扫描支架平面内定位和方向基准 |
| A700→A600 | 6/6 | 否 | 失败 | 顶层仍欠约束，且内部仍依赖2个静态状态锚点 |
| A300→A600 | 3/3 | 是 | 通过 | 顶层案例锚点可删除 |
| A500→A600 | 3/3 | 是 | 通过 | 原正式任务已无案例锚点 |
| A100→A600 | 3/3 | 是 | 通过 | 原正式任务已无案例锚点；内部动态行程仍未验证 |
| A200→A600 | 3/3 | 是 | 通过 | 顶层案例锚点可删除；光学参数仍未验证 |
| T401-1→A600 | 2/2 | 否 | 失败 | 需补安装位置与软管/维护方向基准 |
| T401-2→A200 | 1/1 | 否 | 失败 | 单一距离不能确定刚体位姿，需补面、轴或孔系基准 |

审计报告：`demo/semantic_ports/project02_nonprototype_initial_pose_v1/prototype_dependency_audit.json`

CAD实验汇总：`demo/semantic_ports/project02_nonprototype_initial_pose_v1/nonprototype_initial_pose_cad_test.json`

阶段结论：4/9步骤已经证明顶层位姿不依赖原型案例锚点；A300、A200的锚点可在下一轮从正式图中删除。A800、A180、A700及两个T401仍需要新的机械/工艺定位语义，不能简单删除锚点并继续累计装配。

本次修改的意义：把“看起来在复刻原型”转化为逐步、可执行、可量化的依赖结论；系统现在能指出哪些案例锚点确属冗余，哪些实际上在补偿配合关系缺失的自由度。

## 19. 自然语言自由组合主线第一阶段（2026-10-10）

- 自然语言预览新增项目无关命令IR，明确记录`ADD`和`CONNECT`，不再把项目编号或固定顺序作为命令语义的一部分。
- 全局上下文新增事务DAG编译器，按基座可达性和连接依赖自动排序，可接受合法子集和不同的实例顺序。
- Project05完整图已在通用DAG层8/8步骤就绪；Project02完整图9步均成功排序，但A800/A180因目录声明欠约束被阻塞，证明新主线不会用案例位姿掩盖缺失自由度。
- 当前只完成低成本规划闭环，没有执行新的SolidWorks装配；下一步是用通用事务数据包替换“必须命中某项目固定runner顺序”的执行入口。

功能修改意义：Project02从核心算法退回为黄金回归案例，自然语言自由组合开始拥有项目无关的中间表达、依赖排序和失败解释。

## 20. 通用CAD事务合同（2026-10-10）

- 通用DAG节点现可继续编译为端点级CAD事务数据包，包含目标CAD源、累计输入、配合参数、端点角色候选、复核条件和稳定摘要。
- Project05完整上下文生成8个可执行器接入的数据包且无阻塞，证明数据包层不依赖Project05固定顺序档案。
- Project02保持诚实边界：A800/A180欠约束，A700/A300/A500/A100仍需把既有CAD验证结果正式回写为版本化模板证据；这些步骤不会因为历史作业成功而被通用编译器自动放行。
- 本轮仍未启动SolidWorks；下一步是让现有原子插入、保存重开、失败归档和检查点机制直接消费该数据包。

功能修改意义：自然语言装配链的通用上半段已经贯通到CAD端点合同，专用项目runner不再是唯一可执行表达。

## 21. 通用事务执行器与两步累计CAD闭环（2026-10-10）

- 新增`global-cad-packet-execution-plan/v1`：复核清单/数据包摘要，绑定累计输入、有效配合图和目标模组；后续包必须显式提供上一已提交检查点。
- 新增`scripts/create_global_cad_base_wrapper.py`：把独立根模组包装为父装配体中的唯一顶层组件，应用配合图中的16值`SourceTransform`，保存重开并以`1e-9`姿态阈值复核。
- 新增`scripts/run_global_cad_transaction_packet.py`真实执行路径：根包自动准备基座，后续包直接消费上一输出；所有运行写入独立目录，拒绝覆盖，并记录计划、stdout/stderr、CAD结果和执行信封。
- 修复项目05端口迁移数据源：由缺少高级选项的早期图切换到`project05_module_mate_graph_v2_axes.json`，从源配合保留距离翻转方向。新增回归测试要求D000事务中的`DistanceFlipDimension`必须为`true`。

失败关闭证据：

1. 未包装根模组时，执行器无法在A000根文件中解析顶层A000上下文组件；源文件未变，输出未提交。
2. 包装后但距离翻转字段缺失时，2/2配合虽创建成功，D000仍偏离`0.624 m`，保存重开参数和案例锚点门禁拒绝该结果。

成功闭环：

1. `packet-001`：A000包装后插入D000，2/2配合、翻转方向、案例锚点、约束状态、保存重开、源完整性全部通过；基座准备约`211.506 s`，CAD插入约`84.559 s`。
2. `packet-002`：以第一包实体为不可变输入插入K000，3/3配合、完全约束、保存重开和检查点完整性全部通过；CAD事务约`157.828 s`。

回归闭环：聚焦测试10/10通过；全量后端725项及3个subtests通过；Python语法检查通过。

最新累计实体：`demo/global_assembly_contexts/generic_packet_runs/project05-full-static-graph-v1-packet-002-20261010T120903Z/project05-full-static-graph-v1-packet-002.SLDASM`。

当前边界：已有单包真实执行和两包人工串联，但尚未形成清单级持久作业编排器；暂停恢复、失败回滚和从第三包继续的自动调度仍待开发。碰撞/B-rep不属于当前验收项，保持`not_evaluated`。

功能修改意义：自然语言提交的全局语义图首次由项目无关数据包直接产生连续真实CAD结果，且失败原因能追溯到根上下文与配合高级参数，而不是依赖人工移动结果纠错。

## 22. 既有实例关系的真实CAD编辑与只读验证（2026-10-11）

通用事务执行器新增两条非插入路径：`ADD_RELATION`直接编辑检查点中已经存在的两个组件；`VERIFY_RELATION`只恢复端点并验证距离/角度。两条路径均使用关系局部执行图，不再执行历史`addModule`动作。

A500/A700 50 mm驱动新增实验安全失败：面恢复和配合创建完成后，SolidWorks判定过约束，输出不发布。随后把该关系按目录中的`validate_only`语义编译为`VERIFY_RELATION`，测得距离`0.0499999999999968 m`，容差`0.0001 m`，且配合创建/抑制/替换数均为0；源装配体摘要不变，输出副本保存重开成功。

真实验证总耗时约`91.933 s`；全量后端`797 passed, 3 subtests passed`。碰撞/B-rep未评估。

功能修改意义：已有模组之间的自然语言关系不再只能“硬写一条新配合”，而可以安全表达为“验证当前几何是否满足要求”。

## 23. 默认去原型位姿门禁与显式兜底模式（2026-10-13）

本轮把汇报中确定的技术路线落实到实际任务入口：

- 全局项目适配计划新增`assemblyMode`；默认值为`mate_driven_port_assembly`。
- 编译器逐条读取全局关系模板中的`fullyLocatesAddedComponent`、`remainingDof`与`residualDofPolicy`，生成`poseDependencyAudit`。
- 默认模式中，欠约束、原型位姿锚点、案例锚点和端口完整性未验证都会在CAD前阻断。
- 旧的项目粗复原链保留为`prototype_pose_dependency`，但必须显式选择，结果标记`prototypePoseDependency=true`、`portable=false`。
- 前端增加模式选择、端口完整性统计、逐连接剩余自由度显示和原型模式二次确认。
- 任务恢复前会使用任务原始模式重新编译，避免状态变化后绕过检查；前端幂等键也已加入模式字段。

Project02回归结果：

- 默认模式：正确阻断，A800/A180明确报告依赖原型/案例位姿；其余未形成完整定位证明的端口报告为待补齐。
- 显式原型位姿模式：旧的8步Project02适配计划仍可生成，兼容已有粗复原与调试流程。
- 后端聚焦回归：`8 passed`；全量后端回归：`1034 passed, 3 subtests passed`。
- 前端：TypeScript检查与Vite生产构建通过。

本次修改的意义：真实CAD执行入口终于与主线目标一致——默认证明“语义端口＋配合图能够定位”，而不是默认复用原型位置后再创建灰色配合。

进一步核对历史发布后确认：A800纵向定位基准与A180平面内定位/方向基准已经在`relation-v36-project02-nine-addon-portable-driving-20261011`中完成非原型初始位姿CAD验证，两个模板均已声明`fullyLocatesAddedComponent=true`。当前灰色固定配合来自旧上下文仍引用`source-installation`模板，而不是端口证据从未建立。后续重点改为：让默认工作台绑定v36无锚点发布或等价的最新受控发布，并让`mate_driven_port_assembly`走项目无关CAD事务清单；旧项目适配runner仅保留给显式原型位姿兜底。

## 24. 项目无关独立CAD任务入口（2026-10-13）

本轮把默认独立模式从“只做门禁判断”继续接入到真正的通用事务执行链：

- 新增`POST /api/demo/global-assembly-contexts/{context_id}/independent-cad-jobs`，从受控上下文即时编译项目无关CAD事务清单，并创建持久排队任务；该接口不会启动SolidWorks。
- 前端默认模式改为读取`cad-transaction-manifest`，不再同时生成旧的项目执行清单和项目专用适配计划。
- 默认模式的准备、启动、轮询、暂停、恢复均分流到`generic_cad_manifest`执行器；显式原型位姿模式才继续调用旧项目runner。
- 通用任务状态新增`startRequestedAt`，解决“任务已经提交、后台尚未真正开始”的短窗口内刷新后停止轮询问题。
- 会话恢复逻辑可同时读取旧项目作业仓库和全局事务作业仓库，页面刷新后不会丢失项目无关任务。
- 前端显示关系发布ID、事务包、操作类型、执行策略和失败关闭原因；通用任务不显示旧runner专属的续跑、取消和工程验证操作。

无SolidWorks回归结果：

- `project02-release-a800-a180-v2`：`ready_for_generic_executor_implementation`，2个`INSERT_AND_CONNECT`事务包，0个阻塞，绑定`relation-v30-project02-a800-a180-portable-driving-20261011`。
- 历史`global-demo`：`blocked`，以`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`和`DAG_STEP_NOT_EXECUTION_READY`失败关闭；未使用原型位姿补足。
- 后端定向回归：`16 passed`。
- 前端TypeScript与Vite生产构建通过。

真实本地API闭环另外创建了未启动任务`project02-job-4b20abad45c6`：状态`queued`，`startRequestedAt=null`，`solidWorksStarted=false`，绑定上下文修订3和2个事务包；重新读取会话后，最新绑定任务仍为该任务。该回归同时发现并修复了通用清单缺少`contextRevision`导致任务无法绑定自然语言轮次的问题。

最终回归：后端`1036 passed, 3 subtests passed`；前端生产构建通过。前后端展示服务已恢复，SolidWorks未被启动。

## 25. 便携关系发布自动推荐与显式迁移（2026-10-13）

为解决普通自然语言会话仍引用旧`source-installation`模板的问题，本轮增加了基于语义端口的发布推荐层：

- 遍历已验证的不可变关系发布，但只接受与当前连接端口对完全一致、用途一致、声明完整定位且在发布授权集合内的模板。
- 候选必须用一个发布覆盖当前全部连接，禁止把多个发布权限在运行时拼接。
- 按“授权范围最小、同范围版本最新”选择推荐项，同时保留其他候选供审计。
- 推荐阶段只读；确认后创建新上下文并生成迁移证据，源上下文不覆盖。
- 前端在默认独立模式被阻断时显示推荐发布、逐连接模板替换、新上下文编号和确认按钮；迁移完成后自动重新编译项目无关事务包。

Project02真实无CAD闭环：

1. 源上下文：`global-demo`，两条连接仍引用A800/A180欠约束模板。
2. 自动推荐：`relation-v30-project02-a800-a180-portable-driving-20261011`；替换2条连接，另有7个覆盖范围更大的候选保留为备选。
3. 新上下文：`global-demo-portable-auto-v2`，修订4；源上下文发布绑定仍为`null`，源文件SHA-256为`afbd323faa68d4eff42f8bbab24ddf0bc849fd9db03099f54894e66cd9327c17`且迁移后复核未变化。
4. 新连接：A800、A180均切换到`nonanchor-driving-v1`模板。
5. 项目无关清单：`ready_for_generic_executor_implementation`，2个事务包，0阻塞。
6. `solidWorksExecuted=false`；本轮只证明发布选择、图迁移和执行清单闭环。

迁移证据：`demo/global_assembly_contexts/global-demo-portable-auto-v2.portable-release-binding.json`。

最终回归：后端`1039 passed, 3 subtests passed`；前端TypeScript与Vite生产构建通过；展示服务已加载新接口。

本次修改的意义：用户不再需要知道v30或具体模板ID；系统能够从历史会话已有的语义端口出发，推荐已验证完整配合束，并以新上下文形式安全接入默认独立装配链。

本次修改的意义：默认技术路线已经贯通到“受控发布 → 项目无关事务包 → 持久排队任务 → 通用CAD执行器”，不再只是界面上的模式名称。当前没有启动实体CAD长任务；下一步应让自然语言累计会话在提交时自动选择兼容的最新便携发布，减少人工恢复特定发布上下文的步骤。

## 26. 自然语言首次连接自动绑定便携发布（2026-10-13）

本轮将第25节的发布推荐从“历史图事后迁移”前移到新会话的命令预览与确认阶段：

- 仅添加基座时保持未绑定状态，因为此时尚无需要驱动的连接。
- 第一次添加与基座有真实安装关系的模组时，系统先在内存中形成假设图，再按稳定端口对寻找可完整定位的新模板。
- 若单一不可变发布可覆盖该连接，预览直接把欠约束源模板替换为便携模板，并向工程师显示发布编号、模板替换和配合步数。
- 工程师点击原有“提交并加入当前装配”后，新增模组、连接和发布绑定在同一个修订中写入；没有中间欠约束修订。
- 提交端重新读取发布清单，并核验绑定、授权模板、端口对、替换证据和`fullyLocatesAddedComponent=true`，防止客户端篡改。
- 后续模组预览自动读取已绑定目录，只能选择同一发布已授权的关系模板。

Project02无CAD闭环：

1. 修订1：加入A600基座，发布绑定为空。
2. 修订2：加入A800传输模组；同一修订自动绑定`relation-v30-project02-a800-a180-portable-driving-20261011`，连接直接采用`nonanchor-driving`模板。
3. 修订3：加入A180扫描模组；沿用同一发布并选择A180的`nonanchor-driving`模板，不再发生第二次发布切换。
4. 项目无关CAD事务清单为`ready_for_generic_executor_implementation`，2个事务包、0阻塞。
5. 全过程没有启动SolidWorks，碰撞/B-rep保持`not_evaluated`。

定向后端回归：新增闭环测试与相关上下文/事务测试均通过；全量后端回归为`1040 passed, 3 subtests passed`；前端TypeScript检查与Vite生产构建通过。前端确认区现在会在首次连接时提示“本次将同时绑定便携发布”，工程师不需要输入发布或模板编号。

本地API另外建立了`portable-first-bind-api-v1`证据上下文，实测修订序列为`A600:1 → A800:2 → A180:3`；A800提交时首次绑定v30，A180提交时没有再次切换发布。最终清单仍为2包、0阻塞，后端和前端服务均返回HTTP 200。

本次修改的意义：新会话不再经历“先写入旧模板—默认模式阻断—再创建派生上下文”的绕路，真正把便携配合选择纳入自然语言累计装配的正常提交过程。

当前边界：若后续添加的模组不在当前发布授权范围内，仍会失败关闭；下一步应实现受控的发布扩展预览，使已有连接与新连接由一个更大但仍单一的发布共同覆盖。

## 27. 累计装配中的受控发布扩展（2026-10-13）

本轮解决了“首次绑定v30后无法继续加入A500”的范围问题：

- 当当前发布返回`NO_COMPATIBLE_PORT_PAIR`时，预览层会枚举能覆盖全部既有连接的更大不可变发布。
- 对每个候选先在内存中按稳定语义端口重映射旧连接，再使用候选发布授权集合编译本次自然语言命令。
- 只有旧连接和新连接可以由同一个发布完整覆盖时，才产生`transitionKind=expand`的确认预览。
- 提交端复核发布摘要、授权模板、旧连接一一替换、端口方向和完整定位声明；发布编号篡改即使重新计算预览摘要也会被拒绝。
- 确认后仅增加一个上下文修订，不产生“迁移修订＋新增修订”两个中间状态。

Project02真实API无CAD闭环：

1. 输入上下文：`portable-first-bind-api-v1`修订3，A600+A800+A180，绑定v30。
2. 命令：`在设备箱体上安装喷嘴校准模组`。
3. 预览：`expand`，从v30扩展到`relation-v31-project02-a800-a180-a500-portable-driving-20261011`；重映射2条既有连接，并为A500选择完整定位模板。
4. 提交：上下文修订4，4个实例、3条连接；全部连接属于v31单一授权集合。
5. 项目无关CAD事务清单：`ready_for_generic_executor_implementation`，3个事务包、0阻塞。
6. SolidWorks未启动，碰撞/B-rep未执行。

负例：`在设备操作侧增加喷嘴校准模组`仍然阻断，因为现有A500模板没有声明操作侧方位语义。发布扩展不会删除自然语言限定词来换取可执行结果。

本次修改的意义：累计自然语言装配链可以随模组增加受控扩大关系目录，同时继续坚持单一发布、完整定位和人工确认三项边界。

继续验证结果：

- v31上下文增加A700时，自动扩展到`relation-v32-project02-a800-a180-a500-a700-portable-driving-20261011`。
- 系统重映射3条既有连接并增加A700连接；提交后为修订5、5个模组、4条连接。
- 项目无关事务清单为4包、0阻塞，没有针对A700编写专用扩展分支。
- 多条命令原子接口也已改为逐轮读取内存中的最新发布：一次提交A600、A800、A180、A500、A700五条命令，最终同样绑定v32并得到4个事务包。
- 原子序列的任一轮失败仍不会写入上下文。
- 原先“Project02无定位标准必须阻断”的旧回归已更新：A800/A180现在由v30无锚点完整配合束定位，不再需要原型推断定位标准；显式定位标准路径仍保留为独立兼容测试。

最终回归：后端`1041 passed, 3 subtests passed`；前端TypeScript与Vite生产构建通过；前后端展示服务均返回HTTP 200。

下一步：继续验证v32之后的常见功能模组扩展，并把发布切换历史以更直观的方式加入会话记录；实体CAD执行仍应等用户确认语义图结果后再启动。

## 28. v33至v36覆盖验证与发布历史展示（2026-10-13）

本轮继续使用`portable-first-bind-api-v1`逐轮加入Project02模组：

| 新增对象 | 发布变化 | 图结果 |
| --- | --- | --- |
| A300排胶回收 | v32→v33 | 6个实例、5条连接 |
| A200 CCD | v33→v34 | 7个实例、6条连接 |
| A100龙门双阀 | v34→v35 | 8个实例、7条连接 |
| 第一套T401供胶 | v35→v36 | 9个实例、8条连接 |
| 第二套T401供胶→A200 | 保持v36 | 10个实例、9条连接 |

第二套T401验证了两项能力：同一CAD定义可作为不同实例重复插入；新模组不必全部连接A600，也可以连接此前加入的A200，形成非星形关系图。

最终含A700的图可以完整生成，但CAD事务清单被运行时安全目录以`DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED`阻断。检查发现A700同一配合束在v32、v34等发布中使用不同模板摘要，旧安全目录只覆盖部分ID；现已把全部已知版本加入撤销目录，防止通过切换发布版本绕过A700外部位姿问题。

为验证其余关系，另建`portable-release-growth-no-a700-v1`：

- 一次原子提交9条自然语言命令；
- 9个实例、8条非星形连接；
- 最终绑定v36；
- 项目无关事务清单为`ready_for_generic_executor_implementation`；
- 8个事务包、0阻塞；
- 未启动SolidWorks，碰撞/B-rep未执行。

前端当前装配会话新增：

- 当前完整配合发布；
- 首次绑定/扩展类型；
- 源发布→目标发布；
- 每次扩展重映射的既有连接数量。

本次修改的意义：发布扩展已经覆盖Project02除已知A700问题外的完整九对象语义链，并证明同一模组多实例及模组间非星形连接；同时前端能够解释目录为何以及何时发生变化。

最终回归：后端`1046 passed, 3 subtests passed`；前端TypeScript与Vite生产构建通过。新增参数化回归逐一锁定v32、v33、v34、v35/v36中的4个A700模板摘要，确保全部被运行时撤销。

基于不含A700的可执行上下文，已创建但未启动持久任务`project02-job-aae6c22b71c0`：

- 状态`queued`；
- `startRequestedAt=null`；
- 8个事务步骤，完成0步；
- `executionStarted=false`、`solidWorksStarted=false`；
- 重新读取任务仓库后状态和步数一致；
- 会话第9轮能够恢复该任务绑定。

该证据只验证“清单→持久任务→刷新恢复”，没有请求SolidWorks执行；系统中原本存在的SolidWorks进程未被本轮任务使用或修改。

下一步：在不启动CAD的前提下，把“含A700被阻断”和“不含A700可执行”两种结果作为前端可见对照；随后选择不含A700链建立未启动的持久CAD任务，验证任务创建与页面刷新恢复，但仍不执行SolidWorks长链。

## 29. 跨项目首次端口发现与多角色累计链（2026-10-13）

本轮转向验证主线目标中的“不同原型、同类角色可以组合”，发现并修复了一个流程顺序缺口：跨项目关系虽然已经存在于不可变发布中，但首次连接过去只查询活动目录；活动目录没有该端口对时，系统会在有机会选择跨项目发布之前提前阻断。

修复后的流程为：

```text
活动目录首次连接失败
  → 保留工程师原始自然语言与已确认模组
  → 枚举不可变驱动发布
  → 检查双方模组、端口对、语义限定和完整定位声明
  → 选择最小范围/最高版本发布
  → 在同一修订写入模组、连接与发布绑定
```

无CAD闭环一：`cross-project-a600-ah00-portable-v1`

- 基座：Project02 A600；
- 新增模组：Project03 AH00喷嘴校准模组；
- 自然语言保留“设备操作侧”限定；
- 自动首次绑定`relation-v42-project02-a600-ah00-operation-side-language-20261012`；
- 2个实例、1条跨项目连接；
- 项目无关事务清单：1包、0阻塞、`ready_for_generic_executor_implementation`。

无CAD闭环二：`cross-project-aa00-bd00-ss00-ai00-portable-v1`

- 固定环境：Project03 AA00；
- 校准：Project01 BD00；
- 传输：Project01 SS00；
- 扫描：Project03 AI00；
- 发布增长：v45首次绑定 → v47扩展 → v48扩展；
- 4个实例、3条连接；
- 项目无关事务清单：3包、0阻塞、`ready_for_generic_executor_implementation`。

第二条链证明：装配上下文不要求所有模组来自同一项目，也不依赖Project02编号；编译器依据具体模组、语义端口、自然语言关系和不可变发布选择连接。两个清单已经保存，但未创建或启动SolidWorks任务，碰撞/B-rep仍为独立后验项。

测试闭环：新增两项跨项目回归，并与发布增长、原子序列和运行时安全测试共同通过`23 passed`；全量后端回归为`1048 passed, 3 subtests passed`。

展示层同步增加“发布内端口发现”说明：当活动目录没有跨项目模板时，确认区会明确显示系统是从不可变发布中找到语义端口与完整配合束，并在技术追溯中列出端口、模板、配合步数和发布选择规则。前端TypeScript检查与Vite生产构建通过。

本次修改的意义：技术路线从“Project02内部累计装配”前进到“跨项目角色替换与累计装配”，并消除了跨项目模板只能被人工指定、不能作为首次连接自动进入会话的问题。

下一步：在工作台实际演示两条跨项目上下文，并优先继续补齐尚未进入任何完整定位发布的角色/模组；实体CAD执行仍应由用户在审阅语义图后显式启动。

## 30. 当前范围覆盖闭合与跨项目CAD任务准备（2026-10-13）

重新生成全目录跨项目候选矩阵后，当前范围得到：

- Project01/02/03/05活动组合共70项；
- 4项已经取得不可变发布直接执行授权；
- 66项已经根据接口类型、配合拓扑或定位几何明确判定不兼容；
- 活动范围内`needs_endpoint_or_template=0`、模板待消歧=0、机械几何待复核=0；
- 其余48项缺口均属于已明确延期的Project06；
- 活动范围闭合状态为`basic_active_coverage_closed`。

这意味着下一阶段不应继续无差别补端口，而应验证已经发布的跨项目关系能否经通用执行器形成真实CAD结果。

选择最短链`Project02 A600 → Project03 AH00`作为首个实体候选。检查执行环境时发现当前SolidWorks仍打开带未保存标记的`step-02-a180-attempt1-action1 *`，因此本轮没有关闭、保存、复用或修改该会话，只完成任务准备。

准备过程同时发现旧API只固化CAD事务清单，没有固化事务DAG，导致命令审计为`AUDIT_SOURCE_MISSING:transactionDAG`。现已修改独立任务入口，使一次确认同时生成：

1. 版本化装配上下文；
2. 事务DAG；
3. CAD事务清单；
4. 命令审计；
5. 未启动的持久排队任务。

新任务`project-global-job-5d97534ddeb2`结果：

- `status=queued`；
- `startRequestedAt=null`；
- 1个`INSERT_AND_CONNECT`包、3条驱动配合；
- 绑定v42跨项目发布；
- 命令审计`complete`，2/2条自然语言命令完成映射；
- `executionStarted=false`、`solidWorksStarted=false`；
- 碰撞/B-rep仍为`not_evaluated`。

相关文件：

- `demo/global_assembly_contexts/cross-project-a600-ah00-portable-v1.transaction-dag.json`；
- `demo/global_assembly_contexts/cross-project-a600-ah00-portable-v1.cad-transaction-manifest.json`；
- `demo/global_assembly_contexts/manifest_jobs/project-global-job-5d97534ddeb2/command-audit.json`。

测试闭环：独立任务与发布推荐定向测试通过；前端TypeScript与Vite生产构建通过；全量后端回归仍为`1048 passed, 3 subtests passed`。

本次修改的意义：当前主线已经从“跨项目关系可编译”推进到“跨项目任务可审计、可排队、可刷新恢复”；实体CAD验证只剩执行环境清理和显式启动，不再缺少上游语义或证据文件。

下一步：用户确认当前未保存SolidWorks文档是否需要保留并清理会话；会话干净后启动上述一包任务，检查三条真实配合是否激活、是否从非原型初始位姿完成定位，以及保存关闭重开后是否保持一致。

## 31. Project02箱体与Project03校准模组真实跨项目闭环（2026-10-13）

用户清理SolidWorks会话后，正式启动`project-global-job-5d97534ddeb2`。该任务消费v42不可变发布，将Project03 AH00从独立子装配体文件插入Project02 A600箱体上下文。

结果：

- 作业状态`succeeded`，装配状态`assembled`；
- 1/1事务包一次成功，无重试；
- AH00从确定性的非原型位姿插入；
- 未固定目标组件，`TargetCaseAnchored=false`；
- 未请求或应用任何叶级位姿锚点；
- 创建3/3条驱动配合：1条重合、2条同心；
- `TargetFullyConstrained=true`；
- `MateSolveClean=true`；
- `ComponentSemanticsMatch=true`；
- 保存关闭重开成功，3/3条配合的类型、方向、距离、角度和高级选项复核通过；
- 基座源装配体SHA-256执行前后相同；
- 输出装配体关闭后提交，源AH00会话也已清理。

耗时：

- 作业总耗时约`91.464 s`；
- CAD适配器约`82.372 s`；
- 基座包装缓存命中，估计避免重复准备`128.503 s`；
- 打开与解析约`35.140 s`；
- 插入目标约`6.401 s`；
- 重建三条配合约`7.156 s`；
- 保存关闭约`12.693 s`；
- 重开复核约`16.909 s`。

输出装配体：

`demo/global_assembly_contexts/manifest_jobs/project-global-job-5d97534ddeb2/packet-runs/packet-001-attempt-01/cross-project-a600-ah00-portable-v1-packet-001.SLDASM`

输出SHA-256：`c8b0383027cf88a8f57fb16ee250d238d42bd4a04a49e5876db894291feb0bf7`。

自然语言审计保持2/2完整映射：

1. `建立设备箱体与安装基座`；
2. `在设备操作侧安装喷嘴校准模组`。

用户摘要、命令审计、计时报告、有效配合图、CAD结果和证据清单均已保存。碰撞/B-rep状态仍为`not_evaluated`，本轮不宣称实体无干涉。

本次修改的意义：主线首次完成“自然语言 → 跨项目模组选择 → 语义端口 → 配合图 → 非原型初始位姿真实CAD配合 → 保存重开”的完整实体证据闭环，证明语义端口与配合图能够独立驱动跨项目模组装配。

下一步：在同一机制下选择第二种角色做实体复验，优先使用Project03 AA00基座＋Project01 SS00传输模组的一包关系；通过后再尝试v48的校准＋传输＋扫描三包累计链，验证跨项目长链检查点传递。

## 32. 跨项目传输单包与三包累计实体闭环（2026-10-13）

在第31节校准模组闭环通过后，继续完成两组真实CAD实验。

### 32.1 Project03基座＋Project01传输模组

上下文`cross-project-aa00-ss00-portable-v1`自动首次绑定v46发布，将Project01 SS00传输模组安装到Project03 AA00固定环境。

- 作业：`project01-job-377c018fa2ed`；
- 1包一次成功；
- 3/3条驱动配合创建成功；
- 完全约束、求解干净、组件语义匹配；
- 从非原型位姿插入，未固定、未使用位姿锚点；
- 保存关闭重开及配合参数复核通过；
- 总耗时约`87.506 s`，CAD适配器约`84.702 s`；
- 输出SHA-256：`c182fe44cfed8893299c0af8a1ec8a8fd6a81ee975120dc7239c6d7c5e013343`。

输出：

`demo/global_assembly_contexts/manifest_jobs/project01-job-377c018fa2ed/packet-runs/packet-001-attempt-01/cross-project-aa00-ss00-portable-v1-packet-001.SLDASM`

### 32.2 Project03基座＋Project01校准/传输＋Project03扫描三包链

上下文`cross-project-aa00-bd00-ss00-ai00-portable-v1`绑定v48单一发布。作业`project-global-job-f0aa2d732403`按检查点顺序执行：

|包|模组|结果|驱动配合|只读工艺验证|耗时|
|---|---|---|---:|---:|---:|
|packet-001|Project01 BD00校准|成功|3/3|0|92.372 s|
|packet-002|Project01 SS00传输|成功|3/3|0|84.634 s|
|packet-003|Project03 AI00扫描|成功|3/3|2/2|158.351 s|

累计闭环结果：

- 3/3包均一次成功，总耗时约`335.831 s`；
- 每一包都完全约束、求解干净、保存关闭重开和配合参数复核通过；
- 每个目标均从非原型位姿独立插入，`TargetCaseAnchored=false`，位姿锚点应用数为0；
- packet-002的输入严格等于packet-001输出；packet-003的输入严格等于packet-002输出；
- AI00除3条驱动配合外，重开后还测量2条只读距离：`0.29 m`和`0.01 m`，绝对误差分别约`9.55e-15 m`和`1.90e-14 m`，均在`1e-6 m`容差内；
- 最终装配体SHA-256：`a60a78c48bb5a1d2915c0cc2500dadccca771588d4a96e9a08bd9b127341d6b8`；
- 碰撞/B-rep仍未执行。

最终输出：

`demo/global_assembly_contexts/manifest_jobs/project-global-job-f0aa2d732403/packet-runs/packet-003-attempt-01/cross-project-aa00-bd00-ss00-ai00-portable-v1-packet-003.SLDASM`

本次修改的意义：系统已不只是支持单一跨项目模组替换，而是能够把来自Project01和Project03的不同角色按自然语言语义图连续装入同一新装配体，并用上一包真实实体作为下一包输入。校准、传输、扫描三类接口均由真实配合独立定位。

前端任务区同步补充成功证据入口：页面刷新恢复任务后，可直接看到自然语言到CAD审计状态及文件、累计执行耗时、可读结果摘要、分阶段计时报告和最终有效检查点，不再要求工程师手工打开任务JSON判断是否完成。前端TypeScript检查与Vite生产构建通过。

下一步：把这些真实成功证据加入前端上下文摘要和演示案例；随后补齐尚未实体复验的两个反向替换关系（Project03 AE00/AH00安装到Project01 JJ00），或在扩展Project06前由需求方确认是否继续保持延期。

## 33. 通用任务刷新恢复与续装状态闭环（2026-10-13）

三包跨项目任务成功后发现一个展示层状态缺口：任务台账已经记录`succeeded/assembled`和最终实体路径，但会话快照的`latestSuccessfulDemo`仍为空。原因不是CAD执行失败，而是旧恢复逻辑只接受`validationProfile=demo`，没有接受默认主线的`generic-cad-transaction-manifest-v1`。

现已完成：

- 将通用配合图任务纳入会话可续装检查点判定；
- 判定同时要求任务成功、装配完成、最终实体路径存在，且没有被碰撞验证明确否决；
- 保留`collisionStatus=not_evaluated`，不把未执行的碰撞/B-rep误写为通过；
- 直接配合编辑的检查点来源同步接受通用配合图实体结果；
- 前端类型和恢复提示同步更新，刷新后可恢复任务、结果路径和“CAD续装检查点”；
- 后端服务重启后，用真实作业`project-global-job-f0aa2d732403`调用会话接口复核：`continuationReady=true`，最终路径指向packet-003实体，验证档位为通用清单，碰撞状态仍为`not_evaluated`。

测试闭环：

- 新增“通用任务可续装”和“碰撞明确否决后不可续装”两项单元测试；
- 定向回归`10 passed`；
- 全量后端回归`1051 passed, 3 subtests passed`；
- 前端TypeScript检查和Vite生产构建通过；
- 实际后端接口返回当前四修订会话、四轮自然语言历史和最终真实CAD检查点。

继续执行只读配合图导出预览时又发现：旧适配器把任务级`project-global`误当成每个模组的来源项目，因而无法解析Project03基座。现已改为按装配上下文逐实例恢复来源：

- `AA00 → Project03`；
- `BD00 → Project01`；
- `SS00 → Project01`；
- `AI00 → Project03`。

真实接口复核返回`confirmation_required`、`executionStarted=false`、`solidWorksStarted=false`，并生成包含上述4个模组及来源映射的只读导出规格；本轮没有实际调用SolidWorks导出配合图。

本次修改的意义：默认语义端口＋配合图执行结果不再成为“任务成功但会话断链”的孤立文件；工程师刷新页面后仍能看到已完成实体证据，并基于同一语义上下文继续添加模组或进入面选取/直接配合编辑流程。

下一步：优先把本轮三包链作为前端内置演示案例和结果摘要；随后对v43/v44两条反向跨项目关系做真实CAD复验。Project06继续按用户要求暂缓，碰撞/B-rep继续保持可选后验验证。

## 34. v43/v44反向跨项目关系证据复核与展示入口（2026-10-13）

准备执行Project03 AE00/AH00安装到Project01 JJ00的反向实体复验时，发现两条发布在2026-10-11已经产生完整真实CAD证据，因此没有重复启动SolidWorks，而是按当前规则重新审计旧证据。

### v43：Project03 AE00传输模组 → Project01 JJ00

- 作业：`project03-job-f18e29248c09`；
- 输出：`demo/global_assembly_contexts/manifest_jobs/project03-job-f18e29248c09/packet-runs/packet-001-attempt-01/project01-jj00-project03-ae00-transport-v1-packet-001.SLDASM`；
- 目标从确定性非原型位姿插入；
- 0个叶级位姿锚点，目标未固定；
- 3/3条驱动配合成功；
- 完全约束、求解干净、组件语义匹配；
- 源装配体摘要未变化；
- 保存关闭重开和3条配合参数复核通过。

### v44：Project03 AH00校准模组 → Project01 JJ00

- 作业：`project03-job-d18e11cad8d2`；
- 输出：`demo/global_assembly_contexts/manifest_jobs/project03-job-d18e11cad8d2/packet-runs/packet-001-attempt-01/cross-project-p01-ah00-release-v1-packet-001.SLDASM`；
- 同样满足非原型初始位姿、0锚点、3/3配合、完全约束、求解干净、源文件不变及保存重开复核。

两个旧作业均与当前上下文ID和上下文摘要严格一致。旧任务计划形成时尚未写`contextRevision`字段，因此本轮没有篡改历史任务文件，而是在摘要匹配后把其成功检查点幂等绑定到对应会话修订。后端实际接口验证两个会话均返回`continuationReady=true`，装配状态为`assembled`，碰撞状态仍为`not_evaluated`。

旧任务修订回填现已固化为通用薄层规则：只有`contextId + contextDigest`完全匹配才允许推断修订，并在绑定中记录`bindingRevisionSource=exact_context_digest_backfill`；摘要不一致的旧任务会被阻断。新增定向测试后，全量后端回归为`1052 passed, 3 subtests passed`，前端生产构建通过。

前端新增三组真实CAD案例入口：

1. Project02固定环境＋Project03校准；
2. Project01固定环境＋Project03传输；
3. Project03固定环境＋Project01校准/传输＋Project03扫描三包链。

会话摘要现在同时显示“装配已完成”和“碰撞/B-rep未执行”，避免把配合实体证据误解为无干涉证据。

本次修改的意义：v42、v43、v44、v46、v48覆盖的双向跨项目组合均已有真实CAD证据，不再需要把已通过案例当作待执行任务；演示者可以直接加载受控上下文查看自然语言轮次、配合任务和最终实体路径。

下一步：不引入已暂缓的Project06；优先完善跨项目案例的可读摘要与自然语言新建流程的一致性，并继续审计活动范围内尚未形成长链组合的已发布端口。

## 35. 工程话术驱动的跨项目四模组实体闭环（2026-10-13）

本轮由系统代替人工完成“自然语言输入—候选消歧—累计写入—事务编译—真实CAD装配—保存重开复核”的完整测试。新建会话`nl-cross-project-engineering-full-v1`，工程输入不要求用户记忆项目号或模组编号；型号编号只在候选确认阶段使用。

累计会话最终包含：

1. Project03 AA00箱体与回流固定环境；
2. Project01 SS00上层产品传输模组；
3. Project03 AI00条码扫描模组；
4. Project01 BD00喷嘴校准模组。

自然语言候选消歧测试发现：句子“在当前固定环境上安装一套产品传输模组……”同时包含安装目标和新增对象，旧逻辑会把“固定环境”误列为待添加候选。现已增加动作宾语聚焦：

- `在Y上安装X`、`增加X`：以动作后的X选择新增模组；
- `将/把X安装到Y`：以前置宾语X选择新增模组；
- 完整原句仍用于识别已有目标Y和关系语义；
- 继续保留“已有目标提示”和“同型号剩余实例容量”的原有可解释标签。

因此，传输轮只返回5个传输型号，扫描轮只返回4个扫描型号，校准轮只返回2个校准型号，不再混入已有基座或其他环境模组。

安全关闭测试也实际执行：输入“在设备操作侧增加一个喷嘴校准模组”时，系统识别到`operator_side`，但当前模板未声明操作侧基准，因此以`REQUESTED_RELATION_TEMPLATE_NOT_AVAILABLE`阻断，没有静默忽略限定词。改为“在当前设备上增加一个喷嘴校准模组……”后，使用已经发布的安装端口正常写入。

最终会话状态：修订4、4个模组、3条连接，绑定发布`relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012`。CAD事务清单包含3个顺序数据包且无阻塞。

真实作业`project-global-job-0d1f74570540`结果：

|包|新增模组|驱动配合|只读关系|CAD动作耗时|结果|
|---|---|---:|---:|---:|---|
|packet-001|Project01 SS00传输|3/3|0|93.277 s|成功|
|packet-002|Project03 AI00扫描|3/3|2/2|139.164 s|成功|
|packet-003|Project01 BD00校准|3/3|0|65.196 s|成功|

全链总耗时`307.398 s`，其中CAD动作`297.637 s`；主要时间为重开复核`119.420 s`、打开并恢复图根`67.782 s`和保存关闭`64.354 s`。第1包命中基座包装缓存，估算避免约`526.579 s`重复准备时间。

三包共同满足：

- 目标从确定性非原型初始位姿插入；
- `TargetCaseAnchored=false`，请求及应用位姿锚点均为0；
- 请求配合数等于创建数，目标完全约束、求解干净；
- 源文件SHA-256前后不变；
- 输出按精确路径保存、关闭、重开；
- 配合类型、方向和参数逐条复核通过；
- AI00两条只读距离`0.29 m`和`0.01 m`复测通过；
- 碰撞/B-rep未执行，状态明确保持`not_evaluated`。

最终实体：

`demo/global_assembly_contexts/manifest_jobs/project-global-job-0d1f74570540/packet-runs/packet-003-attempt-01/nl-cross-project-engineering-full-v1-packet-003.SLDASM`

计时报告：

`demo/global_assembly_contexts/manifest_jobs/project-global-job-0d1f74570540/timing-report.json`

测试闭环：新增动作宾语聚焦回归测试；兼容`把/将X安装到Y`、已有目标提示和重复实例容量；定向测试`9 passed`；全量后端回归`1053 passed, 3 subtests passed`。

本次修改的意义：首次用面向机械工程师的普通工程话术，从候选确认开始，真实形成Project03→Project01→Project03→Project01的跨项目累计装配体；结果不是原型位姿复刻，也不是只生成JSON，而是由语义端口和配合图从非原型位姿建立激活的真实SolidWorks配合。

## 36. Project01基座的第二条跨项目自然语言长链（2026-10-14）

为避免成功案例只覆盖Project03基座，本轮建立了第二条来源顺序不同的累计链：

`Project01 JJ00基座 → Project03 AE00传输 → Project01 SM00扫描 → Project03 AH00校准`

首先发现Project01 SM00原有CAD结果属于旧证据格式：3/3配合、完全约束和保存重开均成功，但没有记录源装配体不变、输出关闭和目标源文档会话清洁，因此发布器按规则拒绝。没有把旧结果直接升级，而是重新执行一次检查点安全重放：

- 耗时`127.312 s`；
- 3/3配合创建并复核通过；
- 从确定性非原型位姿插入；
- `TargetCaseAnchored=false`，叶级锚点请求数和应用数均为0；
- 完全约束、求解干净；
- 源文件SHA-256前后不变；
- 输出保存关闭重开、目标源文档关闭通过。

基于三份独立真实CAD证据，发布不可变关系目录：

`relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014`

该发布只授权以下三条模板：AE00传输到JJ00传输槽、SM00扫描到JJ00扫描槽、AH00校准到JJ00校准槽；碰撞/B-rep状态保持`not_evaluated`。

同时修复自然语言清单API缺少`releaseManifestPath`字段的问题。此前编译器内部已经支持不可变发布绑定，但API模型会丢弃该字段，导致上下文建立后回落默认目录并出现目录摘要不一致。修复后，发布清单路径能从请求一直传递到上下文、事务DAG、CAD清单和持久任务。

真实作业`project-global-job-71ff70d731eb`结果：

|包|新增模组|驱动配合|CAD动作耗时|结果|
|---|---|---:|---:|---|
|packet-001|Project03 AE00传输|3/3|97.875 s|成功|
|packet-002|Project01 SM00扫描|3/3|88.656 s|成功|
|packet-003|Project03 AH00校准|3/3|86.309 s|成功|

全链总耗时`283.493 s`。三包均满足非原型初始位姿、0锚点、完全约束、求解干净、源文件不变、保存关闭重开和配合参数复核；累计输入输出检查点连续。最终装配体：

`demo/global_assembly_contexts/manifest_jobs/project-global-job-71ff70d731eb/packet-runs/packet-003-attempt-01/nl-cross-project-jj00-complete-v1-packet-003.SLDASM`

SHA-256：`AF24654420B84F29E30D7EE207F1B174480A24698CAF7C56E23C5A902F8DEA00`。

完整链闭合脚本已改为通用参数化工具，可指定作业、发布、基座和模组顺序；闭合门禁新增“不得使用案例/叶级位姿锚点、源文件不变、输出已关闭、目标源会话清洁”。机械累计装配闭合通过；SM00对AE00条码目标的光轴和工作距离仍属于待单独验证的工艺关系，不影响本轮机械装配结论。

测试闭环：发布、自然语言编译、API发布绑定和完整链闭合定向测试`30 passed`。本次修改的意义：同一套语义端口、配合图和持久执行器已在两种不同基座及相反跨项目来源顺序上形成真实累计装配，进一步排除了“只对单一Project03案例硬编码”的可能。

## 37. Project05工程语言选择与第三项目族严格闭环（2026-10-14）

本轮继续扩大主线证据范围，没有引入Project06，也没有把碰撞/B-rep加入验收。首先修复自然语言候选选择对项目限定词和功能角色理解不足的问题：命令“增加项目05的喷嘴校准模组”现在会同时使用“项目05”限定和`calibration`角色语义，唯一选择Project05 G000，不再被Project01/Project03的同类校准模组别名抢占。角色别名覆盖机架、传输、扫描、校准、CCD、清洁称重、龙门、定位和供胶等常用类别。

随后执行Project05四数据包链：

`A000基座 → D000传输 → F000扫描 → G000校准 → M000 CCD`

真实作业`project05-job-ec7c2f11febb`在CAD执行层完成4/4包，四个模组均创建3/3配合，源文件不变并完成保存关闭重开。但严格闭环没有把作业级`succeeded`直接视为可移植装配通过：G000显示`TargetFullyConstrained=false`，且当前证据没有`ExternalPlacementEquivalencePassed=true`，因此无法证明其外部安装位姿已由配合独立封闭。闭环报告正确给出`mechanical_demo_chain_failed`，失败点为packet-003；其余D000、F000、M000通过。负样例保留在：

`demo/global_assembly_contexts/project05-functional-chain-v1/complete-demo-chain-closure.json`

为避免G000证据歧义掩盖Project05其余通用能力，随后从同一不可变发布编译并执行刚性三步链：

`A000基座 → D000传输 → F000扫描 → M000 CCD`

自然语言编译耗时`0.239 s`，真实作业`project05-job-28ea1f5e9384`结果：

|包|新增模组|驱动配合|CAD动作耗时|外部位姿|结果|
|---|---|---:|---:|---|---|
|packet-001|D000传输|3/3|133.001 s|完全约束、0锚点|成功|
|packet-002|F000扫描|3/3|93.078 s|完全约束、0锚点|成功|
|packet-003|M000 CCD|3/3|100.064 s|完全约束、0锚点|成功|

全链总耗时`326.619 s`。三包均满足确定性非原型初始位姿、`TargetCaseAnchored=false`、叶级位姿锚点为0、求解干净、源装配体不变、输出关闭、保存重开和配合参数复核；累计检查点连续。最终实体：

`demo/global_assembly_contexts/manifest_jobs/project05-job-28ea1f5e9384/packet-runs/packet-003-attempt-01/nl-project05-rigid-functional-chain-v1-packet-003.SLDASM`

SHA-256：`025255B456DD444ED4C428B37534B8C799BF5AA9427AAF29C61DDA110C3BB7E1`。严格闭环报告：

`demo/global_assembly_contexts/project05-rigid-functional-chain-v1/complete-demo-chain-closure.json`

机械累计装配结论为通过；F000对D000条码目标的光轴、条码面和工作距离仍待只读工艺验证，因此没有宣称完整扫码功能通过。碰撞/B-rep状态继续明确为`not_evaluated`。

闭环器同步升级：刚性模组可用`TargetFullyConstrained=true`证明外部位姿；柔性模组只有在明确提供`ExternalPlacementEquivalencePassed=true`时才可通过。新增正反测试分别证明“内部柔性但外部位姿等价”可以通过、“仅配合创建成功而无外部位姿证据”必须阻断。定向回归`41 passed`，全量后端回归`1062 passed, 3 subtests passed`。

本次修改的意义：主线已在Project01、Project03和Project05三种基座/项目族形成真实CAD累计装配证据；同时把柔性内部状态与整个模组外部安装真实性分离，避免为了追求长链数量而接受位置仍不确定的模组。

## 38. 第三类跨项目角色的机械不兼容回退闭环（2026-10-14）

在传输和校准两类模组已经具备双向跨项目真实CAD证据后，本轮优先审计扫描模组能否成为第三类直接替换角色。全局候选矩阵表明，Project01 SM00、Project02 A180、Project03 AI00和Project05 F000之间当前没有可直接互换的接口。该结论不是端口数据缺失造成的误判：活动范围内12个方向均有原子安装端口，但均存在配合拓扑或定位特征尺寸硬冲突。

最接近可转接的组合为：

`Project03 AI00扫描模组 → Project01 SM00原生槽位`

两者均采用“支承面＋两个定位孔”的三基准拓扑，且各自原型端口都声明能够封闭外部自由度；但AI00定位孔间距为`200.0 mm`，SM00/JJ00原生槽位孔距为`22.0 mm`，差值`178.0 mm`。因此不能通过改名端口、近似同心或原型位姿强行装配，必须改用原生SM00或增加具有双侧定位图案的实体转接件。

此前上述机械结论只存在于独立跨项目替换API和离线处置报告中，自然语言累计装配工作台只能显示`NO_COMPATIBLE_PORT_PAIR`。现已完成薄层整合：

- 当自然语言新增模组找不到直接端口关系时，先保持原请求失败关闭；
- 从当前基座已经发布的完整安装模板中识别该槽位的原生同角色模组；
- 复用现有跨项目替换评估器比较待装模组与原生模组；
- 若是已量化定位图案不一致，返回`physical_adapter_required`；
- 若只是配合拓扑不同且几何尚不可比，返回`mechanical_interface_review_required`；
- 回退结果包含双方模组、孔距差、原因、所需证据和明确的`fail_closed_before_cad`决策；
- 不自动设计转接件，不把回退写入装配图，也不启动SolidWorks。

前端新增“可选工程回退路线”区域：显示具体机械差异，并提供“改用原生兼容模组并重新检查”操作；如果工程师坚持跨项目型号，则界面列出实体转接件、两侧稳定端点目录和两侧完整配合束等后续材料。

真实API演示上下文：`engineering-fallback-project01-ai00-v1`。当前修订1只包含Project01 JJ00基座；命令“在当前机架上安装项目03的条码扫描模组”得到：

- 预览状态：`blocked`；
- 直接阻塞：`NO_COMPATIBLE_PORT_PAIR`；
- 回退类型：`physical_adapter_required`；
- 识别关系：`project03:AI00 → project01:SM00`原生槽位；
- 孔距：`200.0 mm → 22.0 mm`；
- CAD状态：`not_executed`。

测试闭环：回退、替换、发布扩展与自然语言序列定向回归`35 passed`；全量后端回归`1063 passed, 3 subtests passed`；前端TypeScript与Vite生产构建通过。

本次修改的意义：全局自由组合不再只有“可以直接装”与“不能装”两种结果。对于机械上确实不能直连的同类模组，系统能够说明为什么、指出安全替代型号，并把实体转接设计需要补齐的证据定义清楚；同时不牺牲语义端口＋配合图主线的真实性。

## 39. 全目录证据级缺口清单与刚性模组队列收敛（2026-10-14）

本轮按新主线停止扩展工艺验证、实体转接件、A700内部结构和碰撞/B-rep，先建立Project01、Project02、Project03、Project05共34个顶层模组的证据级缺口清单。

新增只读构建器：

- `apps/demo-backend/src/demo_backend/global_module_gap_report.py`；
- `scripts/build_global_module_gap_report.py`；
- 输出`demo/global_assembly_catalog/coverage-v2/global_module_gap_report.json`；
- 可读报告`demo/global_assembly_catalog/coverage-v2/global_module_gap_report.md`。

与旧覆盖矩阵不同，新报告不再把“目录中存在portable端点”直接等同于已完成，而是联合读取：

1. 基线全局模组目录；
2. 全部不可变关系发布；
3. 每个发布的授权模板和模板组合；
4. 非原型CAD评估、完全约束和保存重开证据；
5. 运行时安全撤销目录。

历史目录的模板A/B侧并不统一表示新增目标或上下文，因此新增目标判定改为优先读取CAD评估中的`targetModuleToken`，再结合项目别名恢复定义。GN00等多关系定位模组则读取`authorizedTemplateCombinationIds`，不能把已验证的“主安装＋防转关系”误报为缺少完整模板。

最终结果：

- 当前范围模组：34；
- 已验证可移植新增模组：21；
- 已验证固定环境/槽位提供方：4；
- A700按用户当前决策明确暂缓：1；
- 真正待补齐：8。

原计划优先处理的CCD和刚性服务模组中，Project02 A200、Project05 M000、Project02 A300、Project05 N000/P000以及Project01 GN00均已存在符合当前口径的非原型CAD证据，因此不再重复启动SolidWorks。当前真实缺口收敛为：

1. Project01 FF00、GJ00：端点、完整三基准模板和正反兼容边均已存在，但尚未形成当前受控发布；
2. Project03 AG00、Project01 LM00：完整模板存在但尚未形成当前受控发布；
3. Project03 AB00：已有授权但缺当前口径CAD证据；
4. Project03 AD00、AJ00和Project05 G000：已有执行证据，但外部位姿未被完整封闭。

测试闭环：新增5项单元测试，覆盖Project05刚性正例、G000外部位姿反例、运行时撤销优先级、Project01 GN00组合模板、FF00/GJ00双向兼容边以及A700显式暂缓；后端全量回归`1068 passed, 3 subtests passed`。

本次修改的意义：开发队列第一次由机器可读证据自动生成，避免对已经完成的A200、A300、M000、N000、P000重复开发，也避免把历史组合模板或已撤销模板误判为可执行能力。初步审计曾把FF00/GJ00误报为缺完整模板，进一步检查确认原因是历史目录同一模板存在正反两条兼容边，按模板ID覆盖会丢失一条；报告现按`模板＋两侧端口`保留全部边并正确归类为`release_pending`。下一步依次审计AG00、FF00、LM00和GJ00的已有CAD证据，符合当前门禁的直接形成候选发布；只有仍缺当前证据的代表项才启动非原型SolidWorks闭环。

## 40. 待发布刚性模组证据刷新与隐式锚点阻断（2026-10-14）

本轮继续执行第39节生成的第一批队列，新增通用只读审计器：

- `apps/demo-backend/src/demo_backend/release_pending_evidence_audit.py`；
- `scripts/audit_release_pending_rigid_modules.py`；
- 输出`demo/global_assembly_catalog/coverage-v2/release_pending_rigid_module_evidence_audit.json`及同名Markdown报告。

审计器区分四种历史证据：可直接用于发布、新版checkpoint重放即可、依赖案例/叶级位姿锚点、无锚点但外部位姿仍未闭合。初始审计确认：

- FF00、GJ00、LM00的旧版结果均为3/3配合、无案例锚点、完全约束和保存重开通过，但缺当前证据封装要求的源文件不变、输出哈希和关闭后复核字段；
- AG00的无锚点两配合结果仍欠约束，只有增加案例位姿锚点后才能完全约束，因此不能直接发布。

随后依次执行三次新版checkpoint实体重放：

1. FF00：124.60秒，3/3配合，无案例/叶级锚点，完全约束，源装配未改，保存关闭重开通过；发布`relation-v51-project01-ff00-driving-20261014`。
2. GJ00：145.89秒，3/3配合，同样通过全部门禁；发布`relation-v52-project01-gj00-driving-20261014`。
3. LM00第一次：207.32秒，虽然3/3配合和重开复核通过，但执行图包含2个后来加入的目标叶级位姿锚点，工具总状态失败并阻止发布。

为解决第三项，新增`nonprototype_execution_graph.py`及脚本`prepare_nonprototype_execution_graph.py`。该工具复制执行图，只移除目标模组的案例锚点、叶级位姿锚点和目标固定状态，不修改机械配合、端点、源变换或历史文件，并写入来源摘要。LM00使用净化图再次执行：195.46秒，3/3配合、零位姿锚点、完全约束、保存关闭重开通过；发布`relation-v53-project01-lm00-driving-20261014`。第一次失败结果保留为负证据。

全目录报告进一步接入实证审计。静态目录即使声明模板完整，只要无锚点CAD已经证明仍有外部自由度，就必须由实证状态覆盖静态声明。因此AG00现在被归类为`installation_bundle_repair_required`，下一动作是补独立定位基准，而不是直接发布。

刷新后的全目录结果：34个活动模组中，24个已验证可移植、4个已验证槽位提供方、1个明确暂缓、5个待补项。剩余队列为AG00、AB00、AD00、AJ00和G000。碰撞/B-rep、动态运动和工艺合理性仍未参与本轮结论。

本次修改的意义：第一批“待发布”不再停留在目录标签层，而是完成了历史证据审计、非原型实体重放、不可变发布和全目录状态回写的完整闭环；同时证明执行图中的隐式叶级锚点能够在CAD启动前被显式清除和审计，避免把原型内部状态误当成语义端口独立定位能力。

## 41. Project03 AG00三基准端口补齐与零锚点发布（2026-10-14）

本轮按全目录缺口清单处理Project03 AG00，不研究A700内部结构，也不把碰撞、B-rep或工艺合理性纳入结论。旧AG00模板只有“支承面＋一个定位孔”两条驱动配合，真实无锚点CAD已经证明仍保留绕孔轴旋转的外部自由度，因此不能依靠原型顶层或叶级位姿继续发布。

新增了保守的第二安装基准发现器：

- `apps/demo-backend/src/demo_backend/installation_datum_discovery.py`；
- `scripts/discover_secondary_installation_datum.py`；
- `apps/demo-backend/src/demo_backend/project03_ag00_three_datum_port.py`；
- `scripts/build_project03_ag00_three_datum_candidate.py`。

发现过程只扫描AG00两个静止安装叶零件和AA00基座叶零件的有界持久面目录。原型世界坐标只用于筛选已经登记的圆柱面轴线是否共线、是否与主定位孔独立；它不进入执行图，也不生成顶层或叶级位姿锚点。结果唯一找到第二组独立定位孔：两轴共线、轴向间隔`20 mm`，且相对主定位孔横向独立`170 mm`。由此形成经典的“支承面＋两个独立定位孔”三基准配合束。

生成候选包：

`demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/`

候选端点目录只保留六个必需持久面端点；模板`AG00_to_AA00_three_datum_installation_v1`包含3条驱动配合，预期剩余外部自由度为0。真实CAD完成两级验证：

1. 普通非原型插入：`71.713 s`，独立组件插入，3/3配合，完全约束，保存重开参数一致，案例和叶级位姿锚点均为0；
2. 严格checkpoint：`94.453 s`，同时证明源装配体未修改、输出文件已关闭、目标源会话清洁、配合求解无错误。

严格结果实体：

`demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/project03_AG00_three_datum_checkpoint_v2.SLDASM`

结果证据：

`demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/project03_AG00_three_datum_checkpoint_v2.result.json`

随后形成不可变发布：

`demo/global_assembly_catalog/releases/relation-v54-project03-ag00-three-datum-driving-20261014/`

发布只授权新的三基准模板，旧两配合结果保留为历史负证据。全目录报告重新生成后：34个活动模组中，25个已验证可移植、4个已验证固定环境、1个明确暂缓、4个待补项；剩余队列为Project03 AB00、AD00、AJ00和Project05 G000。

本次修改的意义：AG00首次通过稳定面端点和三基准配合图，从非原型初始位姿独立求出最终安装位姿；证明“补齐语义端口机械基准”能够真正替代原型位姿捷径，并把全目录主线从静态标签推进到可复现的真实CAD发布证据。

## 42. Project03 AB00当前检查点证据刷新（2026-10-14）

AG00回灌后，全目录的下一项为Project03 AB00。该模组并不缺语义端口：既有`AB00_to_AA00_complete_three_relation_installation`已经包含支承重合、宽度居中和40 mm距离三条驱动配合，旧版非原型CAD也曾完成3/3配合和完全约束。缺口只来自旧结果未记录当前严格门禁所需的源文件不变、输出关闭和目标源会话清洁等字段。

本轮未重新找面、未更改端口或配合参数，直接使用既有完整配合图进行新版checkpoint重放。第一次命令因PowerShell提供大写SHA-256、脚本执行精确小写比较而在CAD启动前失败关闭；确认文件没有变化后，以规范化小写摘要重新执行。

正式结果：

- 耗时`139.662 s`；
- 独立组件从确定性非原型位姿插入；
- 3/3真实配合创建成功；
- `TargetCaseAnchored=false`，叶级位姿锚点数为0；
- 完全约束、配合求解干净；
- 源装配体未修改，输出保存后关闭并重新打开；
- 三条配合的类型、方向、距离和宽度高级参数在重开后保持一致。

输出实体：

`demo/global_assembly_catalog/coverage-v2/ab00-checkpoint-refresh-v1/project03_AB00_complete_checkpoint_v1.SLDASM`

严格结果：

`demo/global_assembly_catalog/coverage-v2/ab00-checkpoint-refresh-v1/project03_AB00_complete_checkpoint_v1.result.json`

已生成不可变发布：

`demo/global_assembly_catalog/releases/relation-v55-project03-ab00-checkpoint-driving-20261014/`

全目录报告再次回写后：34个活动模组中，26个已验证可移植、4个已验证固定环境、1个明确暂缓、3个待补项。剩余缺口只包括Project03 AD00、AJ00和Project05 G000，三者均不是“缺CAD证据”，而是现有证据已经表明外部安装位姿尚未闭合。

本次修改的意义：证明全目录缺口能够区分“机械端口需要重新设计”和“完整端口只需证据升级”两类问题；对后者可低成本复用既有稳定面与配合图完成当前发布，而不重复进行机械标注。

## 43. Project03证据回灌与Project05 G000双初始位姿闭环（2026-10-14）

本轮继续按全目录缺口推进，没有转向A700内部结构，也没有把碰撞、B-rep、工艺可达性或动态全行程纳入当前安装端口结论。

首先复核Project03 AD00和AJ00。两者既有严格checkpoint原始结果已经满足当前零锚点、配合创建、保存重开、源文件不变与外部位姿闭合要求，缺口仅来自旧发布评估摘要没有当前`constraintStateObservation`字段。因此未重复运行SolidWorks，直接用当前评估器重新形成不可变证据发布：

- `relation-v56-project03-ad00-evidence-refresh-driving-20261014`；
- `relation-v57-project03-aj00-evidence-refresh-driving-20261014`。

Project05 G000是剩余唯一非暂缓缺口。原型中G000与A000存在重合、平行、自由槽和被抑制的482 mm距离关系；历史迁移只重建前三条普通关系，因G000保持柔性而无法证明外部根位姿闭合。本轮生成静态四关系候选：

`demo/global_assembly_catalog/coverage-v2/g000-four-relation-candidate-v1/`

候选显式恢复源自由槽，并只在“静态Demo配置”中启用原型里被抑制的距离关系，用于封闭槽向位置；该模板明确`productionReady=false`，不宣称动态工位或运动范围已验证。

第一次真实CAD运行完成4/4配合、零案例/叶级位姿锚点、保存关闭重开和源文件不变，但最终根位姿相对原型保存位置平移约60 mm。该结果证明“新静态配置不等于原型姿态”，不能继续用原型位姿等价作为唯一判据。

为此新增通用双初始位姿见证机制：

- C#执行结果记录重开后的目标根变换；
- `EditPolicy.initialPlacementVariant`只改变配合前的确定性非原型位姿；
- 第一次零锚点CAD求解结果作为新静态配置的只读见证；
- 第二次从另一非原型初始位姿执行相同配合束；
- 见证只在重开后比较，不参与配合、固定或位姿赋值。

对应实现：

- `external_placement_repeatability.py`；
- `build_external_placement_repeatability_graph.py`；
- 发布器支持`repeatabilityBaselineEvidencePath`并同时封存两次CAD证据。

第二次真实CAD结果：

- 4/4配合创建并在重开后保持参数一致；
- 箱体位姿锚点和叶级位姿锚点均为0；
- G000继续保持源柔性求解状态；
- 与第一次静态配置的平移误差约`1.71e-15 m`；
- 旋转残差约`2.22e-16`；
- 源装配体未修改，结果文件关闭，目标源会话清洁。

由此证明四关系束唯一决定G000的外部安装位姿，而SolidWorks中的“未完全约束”来自其内部柔性结构。形成不可变发布：

`demo/global_assembly_catalog/releases/relation-v58-project05-g000-static-four-relation-driving-20261014/`

同时修复全目录报告对外部位姿见证字段新旧名称的兼容读取。最终报告：34个活动模组中，29个已验证可移植、4个已验证固定环境/槽位提供方、1个按当前决策暂缓（Project02 A700），非暂缓缺口为0。

本次修改的意义：全目录主线首次完成当前范围内所有非暂缓模组的端口与非原型CAD证据闭环；同时建立了适用于柔性复合模组的“外部根位姿重复收敛”判据，避免把内部可动误判为外部安装失败，也避免用原型保存位姿补足欠约束。

## 44. Project05完整累计装配链闭环（2026-10-14）

本轮从空白A000固定环境出发，使用自然语言依次加入D000传输、F000扫描、M000 CCD、G000校准/称重、N000清洁、P000排胶杯和B000龙门。K000不在用户指定的七类附加模组中，因此作为可选模组明确排除；碰撞、B-rep和动态工艺继续保持独立后验项。

首先形成v59统一发布和第一版清单。CAD启动前人工预检发现D000仍使用`source_pose`，因此没有执行这条昂贵长链。随后只刷新D000的初始位姿策略，不改变三条配合、面端点和配合参数；D000从两种确定性非原型初始位姿执行后，平移收敛误差约`7.85e-17 m`、旋转误差约`8.33e-17`，形成v60独立发布。最终七个模板合并到单一不可变发布：

`demo/global_assembly_catalog/releases/relation-v61-project05-complete-seven-addon-driving-20261014/`

正式自然语言上下文为`project05-complete-seven-addon-v2`，持久任务为`project05-job-72463661a6a2`。七个数据包均首次执行成功，逐包完成真实配合创建、源文件不变、保存、关闭、重开和配合参数复核；后一包输入严格等于前一包输出。各包配合数依次为`3/3、3/3、3/3、4/4、4/4、4/4、3/3`，案例锚点和叶级位姿锚点始终为0。

最终独立装配体：

`demo/global_assembly_contexts/manifest_jobs/project05-job-72463661a6a2/packet-runs/packet-007-attempt-01/project05-complete-seven-addon-v2-packet-007.SLDASM`

累计执行总时间为`874.467 s`。其中CAD动作约`821.339 s`；主要成本为打开/解析约`238.300 s`、保存/关闭约`202.293 s`、重开/复核约`202.326 s`、确定性插入约`85.390 s`、建立配合约`62.823 s`。时间报告位于：

`demo/global_assembly_contexts/manifest_jobs/project05-job-72463661a6a2/timing-report.json`

严格闭合器最初把G000误判为失败：当前累计包保留内部柔性，所以`TargetFullyConstrained=false`；而其双初始位姿重复收敛证据已经封存在v58/v61发布中。现已修复为只在发布编号、发布摘要、目录摘要和全局模板编号完全匹配，且当前包仍零锚点、约束状态被接受、求解干净时，才引用该发布级见证。修复后七包机械闭合全部通过，G000证据来源明确为`immutable_release_two_pose_repeatability`。

同时新增自动预检：

`scripts/audit_project05_complete_cumulative_chain.py`

历史v59会因D000的`source_pose`被拒绝；正式v61七包全部通过。预检报告为：

`demo/global_assembly_contexts/project05-complete-seven-addon-v2.preflight-audit.json`

机械闭合报告为：

`demo/global_assembly_contexts/project05-complete-seven-addon-v2/complete-demo-chain-closure.json`

当前结论：完整累计机械装配链已经通过；扫描光轴/条码目标、碰撞/B-rep和动态工艺均仍为`pending/not_evaluated`，没有被本轮机械结果越权声明为通过。

本次修改的意义：主线从“四模组演示链”推进到“基座＋七类附加模组”的完整累计实体链，并且每一包都能追溯到非原型位姿、真实配合和保存重开证据；昂贵CAD运行前也具备自动拒绝原型位姿捷径的能力。

回归阶段另发现多个不可变发布携带同一机械接口时，备用槽位证据收集会按机械键覆盖旧模板身份。现已调整为：证据汇总保留每个不可变模板ID，实际备用槽位评估再按机械端口和配合拓扑去重。该修复不改变v61累计链，但避免新发布破坏历史跨项目候选恢复。最终全后端回归为`1096 passed, 3 subtests passed`。
