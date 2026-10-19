# 跨项目全局模组与语义端口开发记录

> 开发与验收分层以`docs/development_execution_rules-CN.md`为准。本文件记录本专项的实现和实证，不单独改变Demo检查点、工程发布门禁或碰撞调度规则。

## 1. 目标

将原来按项目01、02、03、05分别维护的“模组编号、语义端口和装配模板”提升为全局能力，使用户不需要先声明某个项目，也可以：

1. 用自然语言或编号检索CAD模组；
2. 明确选择一个具体CAD定义，而不是只选择“扫描模组”这一抽象类别；
3. 在版本化装配上下文中逐个加入模组；
4. 根据语义端口兼容关系生成可审计的装配图补丁；
5. 保留端口来源、面注册表证据、模板和人工确认记录，为后续SolidWorks执行提供输入。

本阶段按用户要求暂不把“有无干涉”视为关键问题，也不把碰撞门禁作为自然语言装配功能的同步验收项。开发资源优先投入自然语言解析、语义端口、真实配合、累计装配及恢复机制。Demo结果明确标记为“碰撞未评估”；只有后续另行完成AABB/条件B-rep及基线复核，才可升级为工程静态验证结果。

## 2. 本轮已实现

### 2.1 全局模组定义与安全去重

- 新增 `global-module-catalog/v1`。
- 项目编号和A600、A800、SM00等编号只作为历史别名及来源信息，不再作为全局主键。
- 只有组件文件名集合相同的记录才自动合并；显示名称、功能类别相同不会触发合并，避免把尺寸不同的“扫描模组”误认为同一CAD文件。
- 当前已汇总项目01、02、03、05；项目06因缺少版本化项目配置而显式阻塞。

### 2.2 全局语义端口注册表

- 汇总已有 `semantic_port_catalog.json`、`face_endpoint_catalog.json` 和连接模板。
- 每个全局端口记录：所属CAD定义、类别、接口类型、能力、旧端口编号、来源目录、面端点角色、局部几何指纹、持久引用是否存在及可迁移性。
- 端口整体可迁移性与“某个连接模板实际使用的端点角色是否可迁移”分开判断。例如A180安装端口包含只读槽口证据，但安装模板只使用支承面和纵向基准，因此已验证模板仍可进入图补丁。

### 2.3 兼容矩阵与连接模板

- 将项目内模板转换为全局模板编号。
- 从模板两侧接口类型生成可审计的端口兼容关系。
- 当前目录统计：34个CAD模组定义、74个语义端口、39个连接模板、61条端口兼容关系；72个端口具备完整的模组局部恢复证据。

### 2.4 版本化装配上下文

- 新增 `global-assembly-context/v1`，保存模组实例、语义连接、修订号、命令历史、目录摘要和上下文摘要。
- 所有写入必须先生成预览，再以匹配的 `previewDigest` 和 `confirmed=true` 提交；预览后上下文若变化则拒绝旧预览。
- 支持三种预览状态：`ready`、`needs_confirmation`、`blocked`。
- 通用名称跨项目存在多个候选时不会自动猜选；用户可显式选择 `moduleDefinitionId`。

### 2.5 自然语言增量装配预览

- 支持从自然语言中识别项目历史编号、组件名和功能别名。
- CAD组件名和项目模组编号的匹配优先级高于通用功能别名；“A800传输模组”可唯一定位，“扫描模组”在跨项目目录中会要求确认。
- 自动查找待加入模组与当前上下文之间的兼容端口和模板。
- 当前只写入装配图上下文，不修改SolidWorks。
- 支持目录声明的同源多实例：项目02的T401允许两套实例，第三套会以`MODULE_INSTANCE_CAPACITY_REACHED`拒绝。
- 当命令同时提到待添加模组和已有目标模组（例如“将第二套T401安装到A200”）时，会用目标模组提示过滤兼容端口，而不是任意选择A600或A200。

### 2.6 API与展示页

新增API：

- `GET /api/demo/global-module-catalog`
- `GET /api/demo/global-module-catalog/search?q=...`
- `POST /api/demo/global-assembly-contexts`
- `GET /api/demo/global-assembly-contexts/{contextId}`
- `POST /api/demo/global-assembly-contexts/{contextId}/commands/preview`
- `POST /api/demo/global-assembly-contexts/{contextId}/commands/apply`
- `GET /api/demo/global-assembly-contexts/{contextId}/execution-manifest`
- `GET /api/demo/global-assembly-contexts/{contextId}/project-adapter-plan`
- `POST /api/demo/global-assembly-contexts/{contextId}/project-adapter-jobs`（只排队，不启动CAD）

展示页新增“跨项目模组库·静态自由组合MVP”：可查看目录统计、建立上下文、检索模组、输入自然语言命令、查看歧义/阻塞/端口候选并确认写入图补丁。页面持续显示“碰撞未评估”。

### 2.7 到既有CAD执行器的编译清单

- 新增 `global-assembly-execution-manifest/v1`。
- 将全局端口和模板反向解析为来源目录中的旧端口编号、旧模板编号、面目录及 `base*_graph.json` 候选。
- `A600→A800→A180`上下文已编译为2个 `semantic-connection-request/v1`，两步均为 `ready_for_project_adapter`。
- 清单不会直接启动SolidWorks；下一层仍需选择每一步的累计源装配体并调用已有增量插入执行器。

### 2.8 项目02 A200与双T401端口闭环

- A200已登记`重合26 + 槽口1 + 槽口2`三条真实安装关系；槽口配合保留有序面端点及`SlotConstraint`，不再降级为只读备注。
- 第一套T401通过`重合14 + 距离10`连接A600；第二套T401通过`距离28`连接A200。
- 三组端口均来自项目02原型配合图中的持久引用、叶零件相对路径、体/面索引和局部几何指纹。
- 槽口曲面没有单一平面法向量，因此可迁移性规则改为：平面必须具备局部法向；一般曲面使用局部中心、叶路径、体/面索引和持久引用恢复。
- 已形成`A600→A200→T401-1→T401-2`四实例、三连接、四修订的全局图证据链；三步执行清单均为`ready_for_project_adapter`。

### 2.9 项目05九对象端口迁移

- 将D000、K000、F000、M000、G000、N000、P000、B000共8个待装对象的安装面迁移到全局端口，A000同时获得8个对应承载端口。
- 25条原型关系中，21条具备完整创建参数并作为驱动关系；`宽度17`及`槽口1/4/6`只有端点面而缺少高级约束参数，按失败关闭原则登记为`evidence_only`，不猜测`WidthConstraintType`或`SlotConstraint`。
- 每个待装对象仍保留项目05已验证静态位姿的案例锚点；这保证与既有静态CAD长链一致，但不等于获得厂商通用安装基准。
- B000端口位于B000/Z000复合运动组的B000外部安装成员上；Z000继续作为组内成员，不伪装成第二个独立龙门实例。
- 已形成`A000→D000→K000→F000→M000→G000→N000→P000→B000`九实例、八连接、九修订的全局图证据链；8/8执行步骤均为`ready_for_project_adapter`。

### 2.10 累计检查点与项目CAD runner绑定

- 新增`global-project-adapter-plan/v1`，把全局图清单继续编译为“项目、机械顺序、已验证基座、累计步骤、runner”五类执行信息，但不会自动启动SolidWorks。
- 项目05完整九对象图被识别为已验证的完整顺序；绑定A000现有保存重开证据，生成D000至B000共8步持久任务计划。第一步只允许从A000外部已验证检查点开始，后续步骤只允许从上一已提交检查点继续。
- 项目02局部链`A600→A200→T401-1→T401-2`虽具备3/3面级连接证据，但不符合完整机械顺序。计划在启动CAD前失败关闭，并明确报告缺少A800、A180、A700、A300、A500、A100。
- 随后补建项目02完整链`A600→A800→A180→A700→A300→A500→A100→A200→T401-1→T401-2`：10实例、9连接全部可编译，顺序判定为`exact`，项目适配计划为`ready_for_durable_job`。
- 项目02现有runner把两套T401作为一个累计步骤中的两次CAD动作；绑定层读取完整闭包中的`instanceTokens`，将两个语义实例合并成一个T401任务步骤，避免两套供胶被重复插入。最终计划为A800至T401共8步。
- 新增API `GET /api/demo/global-assembly-contexts/{contextId}/project-adapter-plan`；展示页“检查CAD执行就绪性”同时显示图编译结果、项目顺序、基座检查点、累计步骤和阻塞原因。
- 新增`create_seeded_durable_job`，只有`safeToCreateDurableJob=true`的计划才能建立任务并播种基座；阻塞计划无法绕过前置检查进入任务队列。
- 为避免保存上下文与工作台目录摘要不一致，项目02/05证据链现统一使用跨项目主目录，而不再生成一次性项目子目录摘要。

### 2.11 显式排队、恢复与失败回滚

- 新增`POST /api/demo/global-assembly-contexts/{contextId}/project-adapter-jobs`。请求必须显式提交`confirmed=true`；接口只建立`queued`任务并播种已验证基座，返回`executionStarted=false`和`solidWorksStarted=false`，不注册后台CAD任务。
- 创建前重新编译项目适配计划并检查统一发布契约；顺序不完整、runner未登记、基座缺失或现场CAD未放行时均拒绝创建。
- 展示页增加人工确认复选框及“创建排队任务（不执行CAD）”按钮；查看计划不会产生任务，未勾选也不能创建。
- 使用上下文摘要作为幂等键时，重复点击复用同一任务，不会产生重复装配作业。
- 模拟runner闭环证明：首步输入为A000已验证基座；D000提交后可暂停，恢复时从D000继续且不重跑；K000失败时未提交产物进入隔离区并回滚到D000，恢复后只重试K000及其尾部。
- 上述模拟用于验证任务状态机，不代表运行了SolidWorks或证明实体安全。
- 本阶段闭环测试：排队与恢复专项5/5、全量后端632项及3个subtests、前端生产构建、Python语法和定向差异检查全部通过。

### 2.12 二次确认启动与短前缀执行范围

- 排队请求新增`stepLimit`，可从完整8步计划中建立1至8步的已验证连续前缀。默认在界面选择1步，便于先验证A800或D000，而不是直接运行长链。
- 新增`POST /api/demo/global-assembly-contexts/{contextId}/project-adapter-jobs/{jobId}/start`；必须同时提交`confirmed=true`、当前`contextDigest`和预期步骤数。
- 启动前重新加载上下文、重新编译计划并核对任务来源、项目、步骤前缀、统一发布契约和执行模式；任何一项变化都拒绝调度。
- `request_start`以`startRequestedAt`实现幂等，同一任务重复点击只会调度一次。
- 启动接口只登记后台任务，本次HTTP请求本身仍返回`solidWorksStartedInRequest=false`；真正CAD工作由后台runner接管。
- 若runner在进入首步执行器之前初始化失败，任务会失败关闭、保留A600/A000基座回滚点并生成证据清单，不再永久停留在`queued`。
- 展示页将“创建排队任务”和“明确启动CAD任务”拆为两个确认区，并显示本次步骤数。测试没有实际调用后台任务，因此本轮仍未启动SolidWorks。

### 2.13 任务监控与受控恢复

- 全局装配工作台会每秒读取已经明确启动的排队或运行任务，展示每一步的状态、尝试次数、检查点路径和错误信息。
- 界面显示最后有效检查点与回滚策略，并提供请求暂停、请求取消和从检查点恢复；暂停/取消由持久任务状态机处理，不直接杀死或覆盖已提交装配体。
- 全局任务恢复不再调用旧的通用恢复接口。恢复前必须再次提交当前`contextDigest`和步骤数，并重新检查任务来源、步骤前缀、项目runner及统一发布许可。
- `prepare_resume`会清除旧启动时间和启动请求标记，但保留已成功步骤及最后检查点；随后重新登记一次幂等后台执行请求。因此失败步骤和其后步骤可重试，已经提交的前序步骤不会重跑。
- runner初始化失败的专项测试已证明：任务进入`failed`、回滚点保持A000、证据清单落盘；经专用恢复接口后任务回到`queued`，失败步骤恢复为`pending`且只登记一个后台任务。
- 本阶段仅验证调度对象和任务状态，没有执行BackgroundTasks，因此未启动SolidWorks。

### 2.14 项目02 A600→A800真实单步实证

- 用户明确选择项目02后，建立独立任务`project02-job-e6ffd79bb6e6`，执行范围固定为`stepLimit=1`；唯一目标步骤为A800，未调度A180及后续模组。
- 任务从已验证A600基座`step00_A600_base_V3.SLDASM`开始，经正式二次确认接口进入现场CAD runner。
- A800从独立模组文件插入；`重合35`与`宽度9`两项驱动配合均创建成功，端点均通过源装配体持久引用恢复。
- 保存、关闭、重新打开复核通过；配合类型、对齐和高级宽度参数均匹配，A800被SolidWorks判定为完全约束。
- CAD动作耗时98.165秒，持久任务总耗时100.207秒；主要阶段为打开上下文30.476秒、插入31.505秒、重建配合16.165秒、保存10.002秒、重开验证7.615秒。
- 既有对象对门禁随runner执行：A600/A800复用了版本化B-rep缓存，1.673秒通过`noNewInterferenceOverAcceptedBaseline`，没有重新运行精确B-rep。该结论是“相对已接受原型基线无新增干涉”，不是绝对零干涉。
- 最终检查点：`demo/semantic_ports/project02_ordered_jobs/project02-job-e6ffd79bb6e6/cad-working/step-01-a800-attempt1-action1.SLDASM`。
- 当前布局仍使用项目02案例位姿锚点闭合源配合未消除的自由度；本次证明真实增量装配链可用，但尚未证明厂商安装基准独立性。

### 2.15 成功检查点续跑与A180真实实证

- 排队请求新增`seedJobId`：只能引用同项目、同上下文摘要、状态为`succeeded`且检查点文件完整的任务。
- 系统从检查点的`stepId/moduleToken`反查完整机械顺序，只生成其后的连续步骤；启动和恢复时会再次核对来源任务状态、检查点路径以及当前计划切片。
- 展示页增加“以上一检查点准备下一步（不启动CAD）”；新任务仍需单独二次确认，成功按钮本身不会启动SolidWorks。
- 使用A800成功任务`project02-job-e6ffd79bb6e6`建立续跑任务`project02-job-b96f2dade86b`。其输入装配体明确为A800检查点，唯一步骤为A180；A800没有重跑。
- A180成功创建`重合34`与`距离24`，保存关闭、重开复核、完全约束和干净求解均通过。
- CAD动作36.882秒，持久任务总耗时38.923秒。相比从A600重新构建前两步，续跑直接复用31.65 MB的A800检查点。
- A180/A600与A180/A800两对均通过版本化B-rep缓存的`zeroInterference`证据；门禁共1.733秒，没有精确B-rep重算。
- 最新累计装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-b96f2dade86b/cad-working/step-02-a180-attempt1-action1.SLDASM`。

### 2.16 A700→A300真实步骤边界暂停与恢复

- 从A180检查点建立两步续跑任务`project02-job-2b64c336a17e`，步骤严格为`A700→A300`。
- A700进入`running`后登记暂停请求；执行器没有中断SolidWorks，而是在A700保存、重开、门禁通过并提交检查点后，于A300开始前进入`paused`。
- 暂停证据：A700为`succeeded/attemptCount=1`，A300为`pending/attemptCount=0`，最后检查点为A700。
- 通过上下文专用恢复接口重新校验计划和检查点后，A700保持成功且未重跑；A300从A700装配体执行一次，任务最终成功。
- A700 CAD动作44.355秒、对象对门禁1.967秒；A300 CAD动作40.773秒、对象对门禁2.425秒。任务跨两次运行累计执行时间90.337秒。
- A300成功创建`距离19`、`距离20`、`重合39`，保存重开后完全约束、求解干净。
- A700/A180由严格AABB分离通过，A300/A180同样由AABB通过；其余对象对复用了版本化B-rep缓存，没有精确B-rep重算。含`noNewInterferenceOverAcceptedBaseline`的对象对仍不能解释为绝对零干涉。
- 发现A700可迁移性局限：其顶层`RequestedMateCount=0`，实际用案例位姿锚点和2个叶级位姿锚点定位。它能够复现项目02案例，但尚未形成独立于原型位姿的通用机械安装端口。
- 最新累计装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-2b64c336a17e/cad-working/step-04-a300-attempt1-action1.SLDASM`。

### 2.17 A500校准模组真实单步

- 从A300检查点建立A500-only续跑任务`project02-job-9e45097d2c39`；A600/A800/A180/A700/A300均直接来自累计检查点，没有重跑。
- A500成功创建`重合13`、`宽度4`、`距离27`三项顶层驱动配合；没有案例位姿锚点，也没有叶级位姿锚点。
- 保存关闭、重开参数复核、完全约束和干净求解均通过。该结果比A700更接近可迁移的语义安装端口。
- CAD动作40.136秒，持久任务总耗时42.368秒；5组对象对门禁耗时1.994秒。
- A500/A180与A500/A300由严格AABB分离直接通过；A500/A600、A500/A800、A500/A700使用版本化缓存通过，没有精确B-rep重算。
- A500/A800采用`noNewInterferenceOverAcceptedBaseline`，因此仍是“相对原型基线无新增干涉”，不是绝对零干涉；其余两个缓存对象对为`zeroInterference`。
- 最新累计装配体：`demo/semantic_ports/project02_ordered_jobs/project02-job-9e45097d2c39/cad-working/step-05-a500-attempt1-action1.SLDASM`。

## 3. 实际闭环结果

运行：

```powershell
python scripts/build_global_module_catalog.py
python scripts/run_global_natural_language_assembly_demo.py --context-id global-nl-demo-v1 --reset
```

三步命令：

1. `请先安装A600箱体模组`
2. `然后安装A800传输模组`
3. `最后安装A180扫描模组`

结果：三步均唯一解析并写入上下文，形成3个实例、2条语义连接和3条修订历史；没有启动SolidWorks，没有执行碰撞门禁。

新增项目02 CCD/供胶证据链：

```powershell
python scripts/build_project02_a200_t401_semantic_installations.py
python scripts/build_global_module_catalog.py
python scripts/run_project02_a200_t401_global_chain.py
```

结果：A600、A200和两套T401形成4个实例、3条连接、4条修订；自然语言中的A600/A200目标提示均缩小为唯一连接，第三套T401被实例上限拒绝；执行清单3/3可交给既有项目适配器。此测试复用了既有CAD闭环证据，但本轮没有重新启动SolidWorks。

项目05证据链：

```powershell
python scripts/build_project05_global_semantic_ports.py
python scripts/build_global_module_catalog.py
python scripts/run_project05_global_semantic_chain.py
```

结果：项目05的9个功能对象形成9个实例、8条连接和9条修订；8/8步骤可编译为项目适配器请求。旧图中缺少高级参数的宽度/槽口关系不会进入驱动配合。本轮没有重新启动SolidWorks，CAD真实性引用此前已经完成的项目05现场长链闭包。

累计执行绑定：

```powershell
python scripts/compile_global_project_adapter_plan.py project05-full-static-graph-v1
python scripts/compile_global_project_adapter_plan.py project02-a200-t401-evidence-v1
python scripts/run_project02_full_global_semantic_chain.py
```

结果：项目05输出`ready_for_durable_job`和8步计划；项目02局部链输出`blocked`和6个缺失前序模组；项目02完整链输出`ready_for_durable_job`和8个累计任务步骤。目标测试分别完成A000/A600基座播种，并确认项目02 runner动作规格中A100为2个动作、T401为2个动作；没有执行任何CAD动作。

本轮闭环测试：项目适配与相关全局图目标测试13/13通过；全量后端630项及3个subtests通过；API函数级烟雾测试通过；前端TypeScript与Vite生产构建、Python语法检查和定向差异检查均通过。

证据：

- 全局目录：`demo/global_assembly_catalog/v1/global_module_catalog.json`
- 迁移报告：`demo/global_assembly_catalog/v1/migration_report.json`
- 演示上下文：`demo/global_assembly_contexts/global-nl-demo-v1.json`
- 演示报告：`demo/global_assembly_contexts/global-nl-demo-v1.run.json`
- CAD适配器编译清单：`demo/global_assembly_contexts/global-nl-demo-v1.execution-manifest.json`
- A200/T401端口证据：`demo/semantic_ports/project02_a200_t401_installations_v1/`
- A200/T401全局上下文：`demo/global_assembly_contexts/project02-a200-t401-evidence-v1.json`
- A200/T401命令审计：`demo/global_assembly_contexts/project02-a200-t401-evidence-v1.run.json`
- A200/T401执行清单：`demo/global_assembly_contexts/project02-a200-t401-evidence-v1.execution-manifest.json`
- 项目05端口迁移：`demo/semantic_ports/project05_global_installation_ports_v1/`
- 项目05全局上下文：`demo/global_assembly_contexts/project05-full-static-graph-v1.json`
- 项目05命令审计：`demo/global_assembly_contexts/project05-full-static-graph-v1.run.json`
- 项目05执行清单：`demo/global_assembly_contexts/project05-full-static-graph-v1.execution-manifest.json`
- 项目05项目适配计划：`demo/global_assembly_contexts/project05-full-static-graph-v1.project-adapter-plan.json`
- 项目02失败关闭计划：`demo/global_assembly_contexts/project02-a200-t401-evidence-v1.project-adapter-plan.json`
- 项目02完整上下文：`demo/global_assembly_contexts/project02-full-static-graph-v1.json`
- 项目02完整项目适配计划：`demo/global_assembly_contexts/project02-full-static-graph-v1.project-adapter-plan.json`

测试：

- A200/T401、项目05迁移与全局上下文目标测试10/10通过；
- 全量后端回归627项及3个subtests通过；
- Python核心模块语法检查通过；
- 前端TypeScript与Vite生产构建通过；
- API函数级烟雾测试完成目录读取、A800检索、上下文创建、A600预览和确认写入。

## 4. 当前未完成与阻塞

1. 项目06缺少版本化项目配置，尚不能进入全局目录；这是当前唯一目录级硬阻塞。
2. A200/T401及项目05端口虽已具备可恢复面证据，但仍沿用各自项目的源位姿案例锚点；这些不是厂商安装基准。
3. 项目05旧图中的宽度/槽口关系缺少高级参数，当前只作来源证据；若要由配合本身完全定位，需重新导出完整图或现场选面确认参数。
4. 项目02/05均已能选择基座、累计检查点并绑定既有runner，但本轮只验证到持久任务创建和runner动作规格，没有执行现场CAD。
5. 当前一次命令新增一个模组；多轮上下文已能保存，但“多个兼容端口时在界面逐项选端口后重新预览”的交互仍需增强。
6. 碰撞门禁按本轮范围暂缓，不作为本阶段验收项。

## 5. 后续建议顺序

1. 项目02 A800与A180两步累计链已经分别实证，且A180续跑没有重跑A800。
2. `A700→A300`真实边界暂停和恢复已经通过，已证明恢复不会重跑A700。
3. A500真实单步已经通过，并证明其三项顶层配合可独立恢复。
4. 下一阶段从A500检查点执行A100龙门两动作，重点验证同一步内两个CAD动作均以正确累计输入串联、只在两个动作全部通过后提交一个A100检查点。
5. A100通过后再进入A200/T401，完整剩余链仍不自动执行。
3. 在展示页增加同源多实例序号、端口候选明细、目标实例选择和人工选面回退。
4. 重新导出项目05高级配合参数，或允许工程师选择面后确认宽度/槽口选项，用权威参数替换4条只读关系。
5. 最后补项目06档案与端口。碰撞门禁在需求重新开启时再作为独立阶段接入，不与端口建模混杂开发。

## 6. 本轮修改的意义

系统已从“只能在某个项目的固定顺序中识别模组”推进为“具有跨项目CAD身份、语义端口、兼容关系和可持续多轮写入的装配图上下文”。当前最重要的收益不是自动生成最终实体，而是可以准确指出：自然语言选中了哪个CAD定义、使用哪两个端口、为什么可连接、还缺什么证据，并在证据不足时停止。

补齐A200和双T401后，项目02中此前“目录没有端口”的最后两类模组已进入全局图层。系统也第一次验证了“同一CAD源文件按目录声明重复使用两次，并分别连接不同已有模组”的语义装配能力，为后续跨项目自由组合提供了真实案例。

项目05迁移后，所有已加载项目的模组定义都至少拥有一个语义端口；系统可以对两个不同机械架构生成完整静态语义图链。剩余主问题已从“没有端口”转为“如何把图步骤可靠绑定到累计CAD检查点并执行”。

累计绑定完成后，系统不再把“面级连接可编译”误当成“整条机械装配顺序可执行”。项目05证明完整图可以进入持久任务层；项目02反例证明缺少传输、扫描和服务模组时会在SolidWorks启动前停止。这一层把高成本CAD操作前移为低成本、可解释的失败关闭检查。

## 7. A700—A600人工选面配合真实闭环（2026-10-09）

- 在当前十对象Demo检查点中，人工分别选择A700安装面和A600安装面。两个稳定端点均记录持久引用、叶零件层级、面索引、面积、局部指纹和装配体世界法向。
- 两面世界法向点积为`-1.0`，平面间距约`5.63e-16 m`。编译器不再固定写入“同向”，而是根据已选面世界法向自动生成`swMateAlignANTI_ALIGNED`。
- 首次v1实证保留为失败证据：错误的同向设置使A700翻转并漂移约`0.480256 m`；同时，执行器误把本轮新增配合当成源装配体中必须抑制的旧配合。
- 修正后，配合图新增`sourceMateNamesToSuppress`，只要求抑制不可变源图中实际存在的旧配合；本轮新建配合不再触发伪失败。
- A700为柔性子装配体，最终v3同时恢复并复核A730与A720/A721两个项目02检查点内部状态锚点。保存重开后，2/2内部锚点稳定，最大矩阵元素误差约`4.04e-14`。
- v3真实执行通过：新建配合1/1、求解错误为零、保存重开参数一致、A700顶层完全约束、案例位姿误差约`7.89e-15 m`、源装配体SHA-256保持不变。
- 对A700整棵子树独立复测：233/233层级对象位姿稳定，最大平移差约`3.14e-14 m`。柔性根节点聚合包围盒存在差异，但所有子对象位姿均一致，因此不将根聚合包围盒单值误判为实体漂移。
- CAD执行耗时`70.771 s`；主要阶段为打开和解析上下文`20.562 s`、重建配合及内部状态`13.703 s`、保存关闭`25.922 s`、重开验证`7.675 s`。

最终实体：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/executions/project02-job-635438e6d96f-a700-selected-face-coincident-v3.SLDASM`。

主要证据：

- 执行结果：同目录`project02-job-635438e6d96f-a700-selected-face-coincident-v3.context-insert.result.json`；
- 子树复测：同目录`project02-job-635438e6d96f-a700-selected-face-coincident-v3.subtree-comparison.json`；
- 有效配合图：`demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/compiled-v3/project02-job-635438e6d96f-a700-934b24255e.effective-graph.json`；
- 截图：`demo/screenshots/project02_selected_face_trial/a700-a600-coincident-v3-isometric.png`。

本次修改的意义：人工选面已经从“临时端口和文字草案”推进到“稳定面恢复—法向驱动的配合语义—独立另存—重开参数复核—柔性内部状态复核”的真实CAD闭环。

边界：该案例所选两面原先已经共面，未由一条平面重合配合独立求出全部六自由度；剩余自由度和柔性内部状态仍由当前项目02检查点锚点闭合。因此它证明的是“在当前累计装配体中安全增加并重建一条人工选面配合”，不是跨项目厂商基准独立定位。碰撞/干涉未在本轮评估。

## 8. 主线切换：项目无关事务DAG第一阶段（2026-10-10）

### 8.1 新增能力

- 新增`global-assembly-command-ir/v1`：每次自然语言预览同步产生规范化`ADD`和`CONNECT`操作，不再只保留Project02式文字命令。
- 新增`global-assembly-transaction-dag/v1`：直接从全局上下文的实例与连接生成累计插入事务，不读取项目档案中的固定机械顺序。
- DAG会验证实例、端口归属、模板、兼容矩阵、端口可迁移性、驱动配合步骤、CAD源和基座可达性。
- DAG按语义连接自动确定目标、上下文依赖和确定性步骤顺序；孤立实例在启动CAD前以`INSTANCE_NOT_REACHABLE_FROM_BASE`失败关闭。
- 新增模板约束语义诊断：区分目录已闭合、CAD已验证、需权威CAD复核和明确欠约束。明确欠约束时返回`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`。
- 新增只读API `GET /api/demo/global-assembly-contexts/{contextId}/transaction-dag`及命令行`scripts/compile_global_transaction_dag.py`。

### 8.2 闭环结果

- Project05完整九对象上下文在不读取项目固定顺序的情况下形成8步事务，状态`ready_for_generic_cad_executor`，阻塞0。
- Project02完整十对象上下文形成9步事务；A800和A180模板在目录中明确标记未完全定位，因此新规划器返回2项欠约束阻塞。A700/A300/A500/A100列为需CAD复核，A200及两个T401具备既有CAD闭合声明。
- 新建三模组自然语言上下文`global-free-composition-mvp-v1`，命令`A600→A800→A180`成功转为3个实例、2条连接和2步事务；同样在事务层提前指出A800/A180定位语义不足。
- 旧`global-nl-demo-v1`因目录摘要过期被拒绝，没有静默套用新目录。
- 第一阶段定向回归31项通过；加入CAD事务数据包后，后端全量721项及3个subtests通过；Python模块语法检查通过。实体干涉/B-rep保持`not_evaluated`，本轮没有启动SolidWorks。

证据文件：

- `demo/global_assembly_contexts/project02-full-static-graph-v1.transaction-dag.json`；
- `demo/global_assembly_contexts/project05-full-static-graph-v1.transaction-dag.json`；
- `demo/global_assembly_contexts/global-free-composition-mvp-v1.json`；
- `demo/global_assembly_contexts/global-free-composition-mvp-v1.transaction-dag.json`。

### 8.3 当前边界和下一步

当前已经完成“任意已登记语义子图→通用事务DAG”，但DAG尚未由一个完全项目无关的累计SolidWorks执行器消费。下一步应把每个`INSERT_AND_CONNECT`事务编译为目标CAD源、端点恢复和配合创建数据包，复用既有保存重开、失败归档和检查点机制；Project02专用runner只作为回归适配层。A800、A180的阻塞应通过补纵向/平面内安装基准解决，不应通过放宽门禁或复制顶层Transform绕过。

本次修改的意义：自由组合首次拥有独立于项目固定顺序的可执行中间层，并能在高成本CAD前准确指出Project02当前仍缺的机械定位语义。

### 8.4 通用CAD事务数据包

- 新增`global-cad-transaction-packet/v1`及汇总`global-cad-transaction-manifest/v1`。
- 每个数据包明确目标CAD源、语义依赖、累计输入检查点、连接模板、配合类型/参数、两端角色及面注册表候选、权威CAD复核要求和事务摘要。
- 数据包串联采用`base_module_source→previous_transaction_checkpoint`，不读取项目runner中的固定顺序。
- 新增API `GET /api/demo/global-assembly-contexts/{contextId}/cad-transaction-manifest`和命令行`scripts/compile_global_cad_transaction_manifest.py`。
- Project05生成8/8端点完整数据包、阻塞0；Project02生成9个数据包，但2个明确欠约束步骤和4个只声明“需CAD复核”的步骤保持不可直接执行。此结果没有借用Project02既有成功作业来静默提升目录证据等级。

新增证据：

- `demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json`；
- `demo/global_assembly_contexts/project02-full-static-graph-v1.cad-transaction-manifest.json`；
- `demo/global_assembly_contexts/global-free-composition-mvp-v1.cad-transaction-manifest.json`；
- `demo/global_assembly_contexts/global-free-composition-planner-closure-v1.json`。

下一步从Project05的8个就绪数据包中选择短前缀接入现有事务执行内核，验证不调用Project05固定顺序规划器也能累计保存重开。通过后再将既有CAD验证结果以版本化方式回写Project02的A300/A500/A100/A200模板证据，并单独补A800/A180真实机械基准。

本次修改的意义：通用DAG已被进一步落成可由CAD执行器消费的端点级合同；剩余瓶颈从“自然语言和排序”收敛为“通用数据包执行与少数端口证据补齐”。

### 8.5 通用CAD数据包短链实证（2026-10-10）

- 新增通用数据包执行计划与单包执行器：只读取CAD事务清单、指定数据包和上一检查点，不读取项目固定装配顺序。
- 首包若以独立根模组文件作为输入，执行器会先创建一个只含该模组的父装配体，并按有效配合图的`SourceTransform`恢复其权威上下文位姿；保存、关闭、重开且姿态复核通过后，才允许插入目标模组。
- 第一次现场试验暴露两类真实问题：直接把A000根文件当作父装配体时无法解析同名上下文子组件；旧项目05语义端口迁移丢失了`距离1.DistanceFlipDimension=true`，导致D000落到距离面的反侧，偏差为`0.624 m = 2 × 0.312 m`。两类结果均被门禁拒绝，没有提升为累计检查点。
- 修正方式不是移动结果或放宽门禁：根模组改为通用包装基座；项目05端口迁移改用含完整高级配合参数的`project05_module_mate_graph_v2_axes.json`，随后重新生成全局目录、上下文、DAG和CAD事务清单。
- Project05数据包1真实通过：A000包装位姿最大元素误差为0；D000创建2/2配合；保存重开后类型、对齐、距离和翻转方向全部一致；案例锚点平移误差约`5.55e-17 m`；约束状态与求解状态通过；源A000不变。
- Project05数据包2真实通过：明确以上一包A000+D000装配体为输入，不再创建基座；K000创建3/3配合，保存重开参数一致，平移误差0，目标完全约束；上一检查点哈希不变。
- 数据源更新后的全量后端回归为725项及3个subtests全部通过；旧Project02局部上下文因目录摘要变化曾被拒绝，重新生成并复核后恢复预期的失败关闭行为。
- 碰撞与B-rep仍按当前范围保持`not_evaluated`；本轮结论只覆盖通用累计输入、面恢复、配合重建、约束状态、保存重开和来源完整性。

正式证据：

- 数据包1：`demo/global_assembly_contexts/generic_packet_runs/project05-full-static-graph-v1-packet-001-20261010T120344Z/execution-envelope.json`；
- 数据包2：`demo/global_assembly_contexts/generic_packet_runs/project05-full-static-graph-v1-packet-002-20261010T120903Z/execution-envelope.json`；
- 两包累计实体：`demo/global_assembly_contexts/generic_packet_runs/project05-full-static-graph-v1-packet-002-20261010T120903Z/project05-full-static-graph-v1-packet-002.SLDASM`；
- 汇总：`demo/global_assembly_contexts/global-free-composition-planner-closure-v1.json`。

本次修改的意义：通用链已经从“项目无关规划与端点合同”推进到“连续两个真实CAD事务”。第二包消费第一包检查点，证明结果不是逐步复刻完整原型，也不是调用Project05固定顺序runner；剩余工作是增加清单级持久编排、暂停恢复和失败回滚，再扩展更长前缀与跨项目实证。

### 8.6 清单级持久编排、长链和跨项目族实证（2026-10-10）

已新增`global-cad-manifest-job-plan/v1`和清单级持久编排器。它把CAD事务清单中的每个数据包映射为一个可提交步骤，并在每步启动前重新校验清单文件SHA-256、`manifestDigest`和`packetDigest`。每步只有在实体存在、执行返回成功、源文件不变、保存/关闭/重开验证通过后才成为新的累计检查点。

新增命令行`scripts/run_global_cad_manifest_job.py`，支持：

- `create`：从完整清单或连续清单切片创建幂等持久任务；非首包切片必须提供经过包编号、包摘要、文件摘要验证的种子装配体和证据；
- `run`：从当前检查点自动连续执行后续所有包；
- `pause`：登记暂停请求，当前正在运行的CAD动作不会被强杀，任务在下一个已提交包边界暂停；
- `resume`：清除暂停/失败状态，只重试失败步骤及其后续尾部；
- `status`：读取持久`job.json`、逐次尝试、检查点和回滚状态。

失败回滚采用“提交指针回退”而不是反向修改SolidWorks：未通过验证的输出不会成为累计输入；如失败步骤已经生成文件，则移入任务的`rejected`目录；任务始终保留最后成功检查点。另增加清单级步骤计时和证据索引，每次尝试均记录输入检查点、输出、执行包证据、开始/结束时间和耗时。

真实项目05实验从已验证的`packet-002`检查点开始：

1. 执行`packet-003/F000`后主动请求暂停，任务在F000检查点暂停，耗时约`161.436 s`；
2. 恢复时在`packet-004/M000`执行前注入诊断故障，未调用CAD，回滚指针仍为F000；
3. 再次恢复，仅重试M000并继续执行G000，没有重跑F000；M000约`166.808 s`，G000约`168.786 s`；
4. 最终形成`A000+D000+K000+F000+M000+G000`六模组累计实体，任务状态`succeeded/assembled`，碰撞状态仍为`not_evaluated`。

跨项目族实验最初暴露两个通用性缺口，并均以失败关闭方式发现：

- 项目01/03首包基座不是单一箱体，而是两个固定模组组成的组合上下文；旧通用包装器错误假设基座唯一；
- 项目03清单中的项目别名`AE00`与有效图中的真实令牌`FL9A24D063AE00`不同。

执行器现已支持：读取有效图声明的多模组基座集合，只接受唯一且具有成功保存/关闭/重开证据的`step00`组合上下文；同时显式解析“项目别名→有效图令牌”，不再假设字符串完全相同。随后在同一个失败任务上恢复执行，项目03的`AA00+AF00→AE00`真实CAD成功，第三次尝试耗时约`206.048 s`，源组合基座保持不变。

测试结果：新增编排器聚焦测试10/10通过；相关聚焦回归26/26通过；后端全量`732 passed, 3 subtests passed`；Python语法编译通过。

正式证据：

- 项目05持久任务：`demo/global_assembly_contexts/manifest_jobs/project05-job-642ab847f1cf/`；
- 项目05最终实体：`demo/global_assembly_contexts/manifest_jobs/project05-job-642ab847f1cf/packet-runs/packet-005-attempt-01/project05-full-static-graph-v1-packet-005.SLDASM`；
- 项目03持久任务：`demo/global_assembly_contexts/manifest_jobs/project03-job-4c038b2c1c11/`；
- 项目03跨族实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-4c038b2c1c11/packet-runs/packet-001-attempt-03/project03-cross-family-smoke-v1-packet-001.SLDASM`；
- 汇总闭包：`demo/global_assembly_contexts/global-cad-manifest-orchestrator-closure-v1.json`。

当前边界与阻塞：

1. 碰撞/B-rep按当前开发范围没有执行，所有新任务明确保留`collisionStatus=not_evaluated`；
2. 暂停只在事务包边界生效，不中断正在运行的SolidWorks动作，这是为了避免留下半保存文件；
3. 多模组基座必须已有唯一、可验证的`step00`上下文；缺失或存在多个候选时失败关闭；
4. 项目02通用清单仍因A800/A180的机械定位语义不足而阻塞，不能用本编排器绕过；
5. 项目01组合基座问题已具备通用解析能力，但本轮真实跨族验收使用项目03，项目01仍应另行执行一次现场回归。

本次修改的意义：项目无关路线已从“手工逐包调用”升级为可持久、可自动连续运行、可在安全边界暂停、可从失败检查点恢复的清单执行系统；同一执行器已经在项目05长链和项目03另一机械族上产生真实CAD证据。

### 8.7 项目01组合基座回归、任务API与自然语言清单任务（2026-10-10）

本轮按“先证明通用执行，再开放后端接口，最后扩大自然语言输入”的顺序完成：

1. 项目01真实SS00首包回归通过。通用执行器从有效图和成功证据中自动选择`JJ00+HL00`组合上下文，采用与项目03相同的`use_verified_composite_base_context`规则；SS00插入、保存、关闭、重开和源文件完整性均通过。作业`project01-job-90be4101aaf4`耗时`115.885 s`，输出大小`42,673,226 bytes`，碰撞状态为`not_evaluated`。
2. 新增清单任务后端API：创建、列表、状态、启动、暂停和恢复。状态响应直接给出完成步数、失败步骤与原因、回滚信息、最后成功检查点、逐步耗时和事件流。
3. 新增自然语言清单编译器及命令行。2至20条命令可以原子形成全局上下文、通用CAD事务清单和未启动的持久任务；歧义、端口不足或清单阻塞均在任务创建前停止。
4. 修正项目号消歧和目标提示解析：`项目05`可与Project06同名`A000`区分；“在A000上安装M000”会把已有A000作为连接目标、M000作为新增模组。
5. 三步`A000→G000→F000`形成2包，五步`A000→M000→F000→P000→G000`形成4包；顺序来自输入语义图，而非Project05固定序列。
6. Project02 `A600→A800→A180`在任务创建前因两个`TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE`阻断，未启动CAD。

后端API包括：

- `POST /api/demo/global-cad-manifest-jobs`；
- `GET /api/demo/global-cad-manifest-jobs`和`GET /api/demo/global-cad-manifest-jobs/{jobId}`；
- `POST /api/demo/global-cad-manifest-jobs/{jobId}/start|pause|resume`；
- `POST /api/demo/global-cad-manifest-jobs/compile-natural-language`。

主要证据：

- 项目01实体：`demo/global_assembly_contexts/manifest_jobs/project01-job-90be4101aaf4/packet-runs/packet-001-attempt-01/project01-cross-family-smoke-v1-packet-001.SLDASM`；
- 三步/五步编译：`demo/global_assembly_contexts/project05-nl-three-step-nonfixed-v1.natural-language-compilation.json`、`project05-nl-five-step-nonfixed-v1.natural-language-compilation.json`；
- Project02阻断：`demo/global_assembly_contexts/project02-a800-a180-readiness-v1.natural-language-compilation.json`。

自动化回归：本阶段定向测试16项通过；全量后端`741 passed, 3 subtests passed`；Python编译通过。前端未修改，碰撞/B-rep保持独立可选后验验证。

补充真实CAD闭环：三步非固定顺序案例已由排队任务继续执行成功。系统从独立A000基座先插入G000，再以上一检查点插入F000；两包均通过保存/关闭/重开、源检查点不变和实体提交。作业`project05-job-09b1a2005ef9`总耗时`378.139 s`，其中G000约`300.967 s`、F000约`76.998 s`。最终实体为`demo/global_assembly_contexts/manifest_jobs/project05-job-09b1a2005ef9/packet-runs/packet-002-attempt-01/project05-nl-three-step-nonfixed-v1-packet-002.SLDASM`。这证明非固定顺序不仅能编译，也能被同一通用执行器真实消费。

本次修改的意义：持久通用执行器现在具有稳定后端调用合同；受控自然语言可以直接生成可恢复任务，同时Project02机械基准不足仍保持失败关闭。

### 8.8 全局模组—端口—模板覆盖矩阵（2026-10-11）

新增`global-module-port-coverage-matrix/v1`，把签名目录中的模组身份、别名、项目来源、语义端口、兼容模板、CAD端点证据和缺口优先级合并为单一只读视图。当前结果为：43个模组全部可检索，34个具备语义图及CAD端点，61个兼容连接对中59个可进入CAD端点选择。

选择评估器支持定义ID、`项目:模组`和唯一模组号；重名模组必须消歧。只有全部模组具有CAD端点且所选模组能由CAD就绪关系连接成一个子图时，状态才为`ready`。Project02 `A600+A800+A180`已通过；Project06的A000、B000、D000、F000、G000、K000、M000、N000、P000因无语义端口保持阻断。

后端接口：

- `GET /api/demo/global-module-port-coverage`：读取或生成覆盖矩阵；
- `POST /api/demo/global-module-port-coverage/selection-readiness`：判断一组模组是否具备进入后续关系编译和CAD事务规划的最低条件。

目录文件保持签名只读，覆盖矩阵不能反向改写目录。碰撞/B-rep不属于本矩阵的判定内容，继续标记为`not_evaluated`。

功能修改意义：语义端口不再只是分散文件中的能力声明，而成为自然语言选模组、关系编译和CAD任务创建之前的统一能力门禁。

### 8.9 关系模板语义与自由度门禁（2026-10-11）

全局关系层新增两级判断：第一层解析用户所说的是安装、重合、同轴、平行、垂直、距离、角度、居中还是方位；第二层判断候选模板是否为该关系的精确模板、是否含驱动步骤、端点是否便携以及是否闭合新增模组自由度。

当前目录39个模板中有35个复合安装束。复合安装束包含同轴或平行配合，只能说明完整安装过程需要这些配合，不能证明系统支持单独创建同轴或平行关系。A500/A700的`距离8`还同时存在“只读验证”和“驱动但旧签名目录未绑定共享面目录”两种证据；两者均不能在当前签名目录中直接完成新模组定位。

目录构建器现已支持读取语义目录声明的共享`endpointCatalogPath`。迁移预览显示端点恢复后可形成便携驱动距离关系，但其自由度解释仍为`declared_underconstrained`，因此关系可创建不等于模组完整定位。

功能修改意义：端口、关系和定位充分性被拆成可独立审计的层级，为后续自由组合与人工选面兜底共用同一套关系解释奠定基础。

### 8.10 目录版本迁移与关系编辑端口复用（2026-10-11）

全局端口目录升级采用“旧目录＋候选目录＋上下文引用集合”的三方审计。只有上下文使用的模组身份、端口几何语义、模板配合步骤和兼容边在候选目录中保持一致，才允许把上下文复制为新版本并更新目录摘要。端点证据由非便携升级为便携属于可接受的单调增强；删除端口、改变模板语义或降低便携性会失败关闭。

A500/A700共享面目录已通过该机制进入候选目录，而不是覆盖当前签名目录。迁移后的端口可以用于两种不同流程：

1. 新增模组定位：单一50 mm距离仍欠约束，不能单独决定完整位姿；
2. 既有模组关系编辑：可新增、替换或删除距离关系，并编译为独立`ADD_RELATION`事务，由CAD检查与已有安装配合是否过约束。

功能修改意义：同一组稳定面端点既能服务新模组插入，也能服务已安装模组的关系修改，但两类事务使用不同的自由度判定规则，不再互相混淆。

## 8.11 独立基础关系与组合闭合端口（2026-10-11）

Project01新增4个复用真实端点的语义端口：GN00主安装面/孔、JJ00对应安装位、GN00防转面和SS00防转基准。由此形成3个独立关系模板：重合、同心和平行。

端口与模板的关键边界：

- 独立重合预计剩3个自由度；独立同心预计剩2个自由度；独立平行预计剩4个自由度，三者单独均不得声明完整定位。
- `GN00_SS00_standalone_parallel`额外声明与`GN00_to_JJ00_primary`构成已知互补组合，组合后剩余自由度为0。
- 互补声明限定为同一目标插入阶段；编排器不得把不相关实例间的平行关系拿来关闭GN00自由度。
- 端点均具有持久引用加几何指纹证据，可进入通用CAD事务包；目录升级仍通过摘要迁移，不覆盖签名目录。

候选目录统计：43个模组、74个端口、42个模板、67条兼容边。Project06的9个缺端口模组状态不变。

功能修改意义：语义端口目录不仅描述“两个端点可以建立什么配合”，还开始描述“哪几条配合可以共同完成一个具体模组的定位”。

## 8.12 多端口组合关系的现场执行边界（2026-10-11）

- 同一目标模组允许在一个`INSERT_AND_CONNECT`事务中使用多个语义端口。例如GN00同时使用JJ00主定位端口和SS00防转端口。
- 端口组合只有在目录明确声明互补、组合自由度闭合且所有端点便携时才可进入CAD事务。
- 权威有效图可能覆盖更多原型模组；执行时生成事务局部投影，只保留本次端口连接涉及的模组和配合，避免把无关原型上下文变成隐式依赖。
- 投影不能改变配合语义。请求与图中目标配合必须精确相等，缺少或额外配合均拒绝执行。
- Project01 GN00已以`JJ00重合＋同心`和`SS00平行防转`完成3/3真实配合重建、完全约束及重开验证。

功能修改意义：语义端口不再只是单连接选择器；多个端口可以在一个受审计事务内共同决定目标位姿，同时仍保持失败关闭和原型依赖可见。

## 8.13 既有实例关系的驱动/验证分流（2026-10-11）

- 通用CAD事务包现在为`INSERT_AND_CONNECT`、`ADD_RELATION`和`VERIFY_RELATION`分别选择插入、既有组件配合编辑、只读关系验证三种执行策略。
- `ADD_RELATION`只保留请求关系和两个既有模组，并移除旧隔离重建图中的历史`addModule`动作；`VERIFY_RELATION`生成0条驱动配合、1条验证关系和0条图补丁。
- A500/A700的50 mm距离作为新增驱动配合时，端点恢复和配合创建均成功，但SolidWorks判定装配过约束；事务未发布且源装配体未改变。
- 同一距离按只读语义执行后，两个端点分别以`BodyFaceIndex+ModulePoseDelta`和`GeometricFingerprint+ModulePoseDelta`恢复；重开测量为`0.0499999999999968 m`，容差`0.0001 m`，验证通过。
- 成功验证没有新增、删除或替换任何配合，目标组件未重插、未显式位移；输出副本保存并重开成功，源检查点SHA-256保持不变。
- CAD阶段约`89.713 s`：打开与解析约`27.653 s`、执行只读关系路径约`13.408 s`、保存关闭约`21.403 s`、重开复核约`26.595 s`。碰撞/B-rep保持`not_evaluated`。

证据目录：`demo/global_assembly_contexts/generic_packet_runs/project02-a500-a700-spacing-verify-real-v2-20261011/`。全量后端回归为`797 passed, 3 subtests passed`。

功能修改意义：语义端口目录不仅能回答“用哪两个面”，现在还能决定“该关系应驱动CAD，还是只应验证现状”，从而避免将验证性工艺关系错误写成过约束配合。

### 8.14 关系验证进入持久作业合同（2026-10-11）

关系包新增`relationModuleTokens`，Project02验证包明确登记`[A500, A700]`。持久编排器现可从清单第10包建立单步后缀计划，并记录`expectedSeed=packet-009`；故障注入后回滚到外部检查点，恢复时仅重试验证包。选中后缀必须全部就绪，不能借“后缀执行”绕过本包阻塞。

该轮为编排模拟闭环，未重复启动SolidWorks；真实几何验证沿用8.13节证据。全量后端回归为`799 passed, 3 subtests passed`。

当前阻塞：需要新增受控转换器，把已签认的历史十对象检查点转换为`global-cad-packet-execution/v1`可接受的种子证据，之后才能用正式持久作业重跑真实`VERIFY_RELATION`。

### 8.15 历史检查点种子转换与真实持久关系验证（2026-10-11）

上述阻塞已解除。新增外部种子证据格式与转换脚本；它明确声明“检查点与迁移上下文一致，但当前清单前缀未被重新执行”，避免伪造执行历史。转换器复核十个实例、A100/A180/A200/A300/A500/A600/A700/A800各1套及T401两套、源上下文迁移谱系、装配体SHA-256和packet-009摘要。

正式持久任务`project02-job-da6d6a5ec4ed`从外部种子启动并成功提交packet-010。输出：`demo/global_assembly_contexts/manifest_jobs/project02-job-da6d6a5ec4ed/packet-runs/packet-010-attempt-01/project02-full-static-graph-spacing-validation-v2-packet-010.SLDASM`。验证仍为50 mm、误差约`3.2e-15 m`、0项配合修改、源检查点不变。

第二项目族评估：Project03已有`距离5`、`距离1`和`距离2`只读端点证据，但目前仅嵌在AB00/AI00复合安装模板中，还没有可被关系编辑器独立选择的`validate_only`模板。因此下一步应从既有稳定端点派生独立只读模板，而不是拆用复合安装束。

全量后端回归为`802 passed, 3 subtests passed`。
# Project03关系模板跨项目复用（2026-10-11）

Project03 `AB00_to_AA00_partial_anchored_installation` 同时包含驱动重合与只读距离验证。为避免验证40 mm距离时误放整套安装配合，系统新增受控派生：仅把源模板中已标记 `validate_only` 的 `距离5` 复制为独立 `spacing` 模板，并继承原端口、面端点与来源摘要。真实CAD已在AA00、AB00既有实例上完成40 mm测量，证明语义端口和面恢复链可跨Project02/Project03复用。

## 8.16 注册式关系派生与 Project01 平行验证（2026-10-11）

关系模板派生现由`demo/global_assembly_catalog/v1/relation_template_derivations.v1.json`登记，并通过`scripts/build_registered_relation_catalog.py`重复构建。Project03距离关系采用`extract_validate_only`；Project01 GN00—SS00平行关系采用`existing_mate_observation`。两者含义不同，不能互换。

Project01派生模板仍复用原GN00/SS00稳定面端口，但`applicationMode=validate_only`，因此事务包为`VERIFY_RELATION`，不会参与GN00位姿求解。真实CAD重开后两面无向法向夹角为0，容差`1e-6 rad`，0项配合修改。

功能修改意义：语义端口目录现在可表达“用这些面驱动装配”与“用这些面只读验证既有关系”的差别，并能通过统一目录构建流程跨项目发布。

## 8.17 平面重合端口与发布目录（2026-10-11）

GN00/JJ00主安装端口中的`support_plane`现被复用于只读重合验证。SolidWorks端同时测量平面法向夹角和法向距离；本次实测距离约`2.60e-16 m`、夹角0，均通过容差。该验证不创建配合，也不参与位姿求解。

注册式目录已发布到`demo/global_assembly_catalog/releases/relation-v4-20261011/`。发布清单绑定Project03距离、Project01平行、Project01重合三条真实验证证据，并明确只读范围。

功能修改意义：相同语义端口可以用于驱动安装或只读验证，但运行方式由模板语义决定；发布目录只暴露已经完成对应CAD证据闭环的用法。

## 8.18 发布目录选择器与圆柱轴线恢复（2026-10-11）

关系语义入口现默认绑定 `relation-v4-20261011`，并提供独立发布信息接口。自然语言“验证两个安装面重合”“验证两个基准面平行”“验证两个安装面保持40 mm距离”均返回唯一已发布模板和下一步端点选择要求；“验证两个孔同轴”因同轴模板尚未取得本轮真实CAD发布证据而失败关闭。

端点恢复层已能在找回圆柱面后读取解析圆柱参数，得到轴线原点与方向；同轴测量使用径向轴距和无向轴角共同判断。这使端口目录后续可把`locating_hole`从“可找回一个面”提升为“可验证一条机械轴线”。当前旧端点证据中可能没有预存轴线字段，执行器会优先从重开后的真实圆柱面读取，失败时才使用已导出的解析轴线。

功能修改意义：面注册表不需要预先把所有几何量都固化为JSON，稳定面身份与现场解析几何可以协同工作；但只有完成真实CAD验证后，相应同轴模板才会进入发布目录。

## 8.19 同轴端口真实复核与 v5 目录（2026-10-11）

GN00 `locating_hole` 与 JJ00 `mounting_hole` 已完成真实 CAD 只读同轴验证。面注册表先恢复圆柱面，执行器再从运行时曲面提取轴线；重开后径向轴距为 `8.755986498829282e-17 m`、轴角为 `0 rad`。这条关系未创建或修改任何配合。

同轴模板现已与距离、平行、重合模板一起发布到 `demo/global_assembly_catalog/releases/relation-v5-20261011/`。自然语言“验证两个孔同轴”可以选择唯一模板；驱动装配仍不在发布范围内。

功能修改意义：语义端口不再只描述“这是一个孔面”，而是能够通过稳定面身份恢复真实圆柱轴线，并把机械同轴语义落实为可复核的几何量。

## 8.20 语义端口与驱动自由度预检协同（2026-10-11）

语义端口负责说明“用户要连接什么”，有效配合图负责说明“这些面、孔轴和关系会约束哪些自由度”。新预检将两者联合：端口或模板只有只读发布证据时，关系只能验证；拟新增关系没有贡献独立约束行时，判为冗余并禁止驱动；几何不足以建立保守雅可比时直接阻断。

Project05 A000—D000的重合、距离、宽度三配合束形成6阶独立约束，能够完整定位D000。它现被标记为限定驱动模板候选，而不是三个可任意拆用的单关系模板。

功能修改意义：端口目录开始承载“可用于观察”与“可用于定位”两种不同权限，减少自然语言关系被错误执行为实体位姿修改的风险。

## Project05 A000—D000 限定驱动候选（2026-10-11）

- preview包：`demo/global_assembly_catalog/v1/driving-v1-preview/project05_D000_A000_scoped_driving_v2/`；
- 连接模板：`D000_to_A000_scoped_driving_v2`；
- 完整配合束：`重合3＋距离1＋宽度17`；
- 面端点：完整复用原Project05端点目录的8个身份，其中宽度配合使用2个A000宽度面和2个D000标签面；
- 宽度高级语义：保留宽度端点索引、标签端点索引、居中类型与翻转标记；
- 约束声明：`fullyLocatesAddedComponent=true`、`expectedResidualDof=0`、`exactMateBundleRequired=true`；
- 授权状态：`candidate_only_not_released`，不得用于其他模组对或单独宽度配合；
- 默认目录隔离：preview候选只通过`additional_semantic_catalog_paths`加载，不参与正式语义目录扫描。

当前真实CAD冷会话重跑因深层叶组件未解析而失败关闭，不能发布驱动权限。历史同会话实证仍证明同一三配合束可以成功创建、完全约束并重开复核；后续需用当前版本在缓存或小上下文中复验。

补充闭环结果：已从历史通过副本裁剪只含A000、D000的静态上下文，并以当前执行器的同会话预解析模式完成3/3配合重建。结果装配体SHA-256为`08f10d06157730b1b23b69de2dba174cbe15624248c18ad48ed51bb61a807a7a`。该模板现进入专用v6发布，但没有加入默认v5发布。

### 8.21 端口“可恢复”不等于配合“可独立定位”（2026-10-11）

v6后续非原型位姿实验发现，8个面端点都能稳定恢复、3条配合也能原位重建，但固定的D000实例会让“完全约束”产生假阳性。真实扰动或解除固定后，原位编辑不能把D000恢复到目标位姿。

最终采用更严格的独立插入验证：删除旧D000，从其独立子装配体文件以非case-anchor位姿插入，再使用相同8个面端点和完整三配合束定位。该实验3/3配合成功、求解干净、完全约束并保存重开通过。

因此端口与模板发布新增分层：

- 面端点身份通过：证明能稳定找到面；
- 原位关系重建通过：证明能重建关系参数；
- 非原型独立插入通过：才证明该模板能够驱动新模组位姿。

专用v7发布只依据第三层证据授权驱动；v6会被新门禁拒绝。该区分避免把面注册表的稳定性错误外推为装配定位的充分性。

## 8.22 v7语义端口进入通用持久执行器（2026-10-11）

- A000—D000发布模板不再由专用实验脚本旁路执行；v7自然语言CAD事务包已由通用持久执行器直接消费。
- 执行边界对发布绑定和逐模板授权进行现场复核，未授权模板即使拥有自洽的新摘要也会被拒绝。
- `宽度17`的四个真实面端点及宽度/标签分组进入事务执行投影，和`重合3`、`距离1`共同构成6自由度闭合定位束。
- 真实结果为3/3配合创建、D000完全约束、保存重开参数一致、源文件不变；失败注入后的恢复只重试失败包。
- 证据总表：`demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/durable-executor-closure.json`；Python全量回归`834 passed, 3 subtests passed`。

本次修改的意义：语义端口、面目录和关系模板第一次共同驱动“自然语言到持久CAD检查点”的生产形态执行链，而不仅是选择预览或独立试验。

## 8.23 Project01组合端口进入发布绑定累计装配（2026-10-11）

- SS00与JJ00的三基准安装端口已作为完整3配合闭合束发布。
- GN00先通过JJ00主安装端口建立重合＋同心关系，再通过GN00/SS00防转端口增加独立平行关系，组合后声明剩余自由度为0。
- 关系编辑只允许使用独立关系模板`template/project01/gn00-ss00-standalone-parallel/5df3a32e59`；原安装模板中的防转条目不能冒充独立关系模板。
- `relation-v9-project01-driving-independent-20261011`只授权上述三条模板；自然语言安装和关系新增均从同一发布绑定读取权限。
- 真实累计执行两包各创建3/3配合，独立插入、完全约束、保存关闭重开均通过。闭环报告：`demo/global_assembly_contexts/project01-jj00-ss00-gn00-v8-driving-v1/durable-executor-closure.json`。

本次修改的意义：端口目录不再只支持“一对模组的一次安装”，而能表达新增模组同时依赖基座主定位和已有模组防转关系的多边约束。

## 8.24 Project01一等模板组合与通用目录复核（2026-10-11）

- Project01语义端口源新增`templateCombinations`，把GN00的JJ00主定位与SS00防转平行关系登记为同一精确组合。
- 新全局目录包含43个模组定义、74个语义端口、42个连接模板、1个模板组合和67条兼容关系；目录校验通过。
- 组合全局ID为`combination/project01/gn00-primary-plus-ss00-anti-rotation/18004cfdec`，成员正好是`GN00_to_JJ00_primary`和`GN00_SS00_standalone_parallel`，不接受缺项或额外模板冒充闭合组合。
- 使用新目录重新编译Project01事务图，结果为2个事务、`ready_for_generic_cad_executor`；GN00步骤由目录证据判定`closed_by_declared_template_combination`、预计剩余自由度0。
- 证据：`demo/global_assembly_catalog/v1/combination-v1-preview/project01-declared-combination-closure.json`。该文件是目录/事务语义闭环，不替代既有v9真实CAD证据。

功能修改意义：目录本身现在能够回答“哪几条关系必须一起使用才能完整定位模组”，后续Project03等项目族可以按相同结构登记组合，而不需要复制Project01专用判断代码。

## 8.25 v10组合发布与Project03闭合语义审计（2026-10-11）

- 新不可变发布：`relation-v10-project01-combination-driving-20261011`。它沿用已通过的SS00、GN00独立插入CAD证据，同时显式授权组合`combination/project01/gn00-primary-plus-ss00-anti-rotation/18004cfdec`。
- 新自然语言上下文：`project01-jj00-ss00-gn00-v10-combination-v1`。4条命令编译为2个累计CAD包，GN00主定位和防转关系属于同一packet；删除任一成员的负例会被组合授权门禁拒绝。
- Project03共审计11条安装模板：6条是无锚点声明的原子闭合候选，5条需要继续补语义。
- AE00三基准模板作为正例，在不绑定项目基准位姿的情况下编译为1个ready事务；AG00诊断模板仍余1自由度且没有补充组合，明确失败关闭。
- AB00两条模板以及部分AG00模板包含`prototype/anchor/calibrated`来源或约束声明矛盾，不能仅因JSON写有零自由度就认定为可移植闭合。
- 审计证据：`demo/global_assembly_catalog/v1/combination-v1-preview/project03-template-combination-readiness.json`。

功能修改意义：相同目录结构已经跨Project01/Project03工作，同时保留了对不充分机械语义的失败关闭，不再把“原型锚点能摆对位置”误当成“配合关系能独立定位”。

## 8.26 Project03 AE00端口的发布级真实CAD闭环（2026-10-11）

- 新增驱动证据审计器，对Project03全部安装模板同时核对目录闭合声明和真实CAD结果；AC00锚点模板不再被误计为可移植原子闭合。
- AE00端口使用`support_plane + locating_hole_1 + locating_hole_2`三类角色，对应重合28、同心39、同心40三条驱动配合，声明剩余自由度为0。
- 发布级复验从独立`FL9A24D063AE00.001.SLDASM`以非原型位姿插入，未使用case anchor或叶位姿anchor；3/3配合创建并在重开后逐项匹配。
- `relation-v11-project03-ae00-driving-20261011`只授权该端口模板。自然语言“先安装AA00环境，再把AE00传输模组安装到AA00传输安装位”已编译为1个通用CAD包并真实执行通过。
- 实体输出：`demo/global_assembly_contexts/project03-aa00-ae00-v11-driving-v1/cad-run-packet-001/project03-aa00-ae00-v11-driving-v1-packet-001.SLDASM`；闭环报告：同级`closure-report.json`。
- CAD适配器耗时约`72.01 s`；碰撞/B-rep为`not_evaluated`。

功能修改意义：语义端口能力已从Project01/05迁移到Project03，并证明同一自然语言编译、逐模板授权和项目无关CAD执行链可复用，而不是复刻原型顶层位姿。

## 8.27 Project03 AE00—AD00累计端口链（2026-10-11）

- AD00使用AA00功能安装端口，通过`support_plane + locating_hole_1 + locating_hole_2`三基准关系完成定位。
- AD00当前checkpoint直接以AE00通用执行结果为输入；独立AD00从非原型位姿插入，3/3配合、零锚点、完全约束、保存重开通过。
- 新发布`relation-v12-project03-ae00-ad00-driving-20261011`只授权AE00、AD00两条模板。
- 三条自然语言命令编译为两个累计包；持久作业`project03-job-cea5e3c2ac90`两包一次通过，第二包输入严格等于第一包输出。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project03-job-cea5e3c2ac90/packet-runs/packet-002-attempt-01/project03-aa00-ae00-ad00-v12-driving-v1-packet-002.SLDASM`。
- 总执行约`161.36 s`，其中AE00包约`74.21 s`、AD00包约`86.88 s`。

功能修改意义：端口目录已经支持在同一Project03检查点上连续追加两个独立模组；这比复用两个彼此无关的单步实验更接近自然语言有序装配的目标形态。

## 8.28 Project03 AI00驱动端口与只读距离验证（2026-10-11）

- AI00安装端口包含`support_plane + locating_hole_1 + locating_hole_2`三条驱动关系，以及`longitudinal_offset + lateral_offset`两条只读距离关系。
- 三条驱动关系负责将独立AI00从确定性的非原型初始位姿完全定位；两条距离关系只验证`0.29 m`和`0.01 m`结果，不重复驱动位置。
- AI00发布级checkpoint直接消费v12的AE00+AD00累计实体，3/3驱动配合、2/2距离验证、完全约束、求解干净、保存关闭重开及源文件不变均通过。
- 新发布`relation-v13-project03-ae00-ad00-ai00-driving-20261011`只授权AE00、AD00、AI00三条已取得当前checkpoint证据的模板。
- 持久作业`project03-job-d7ecc82db4f1`形成三包累计链；第三包输入严格等于第二包输出，最终实体位于`packet-003-attempt-02`。

功能修改意义：语义端口目录现在能够在同一安装模板中明确区分“决定模组位置的关系”和“安装后只检查结果的关系”，避免把验证尺寸错误地叠加成过约束。

## 8.29 Project03 AH00标定端口与四包累计链（2026-10-11）

- AH00标定模组通过`support_plane + locating_hole_1 + locating_hole_2`三基准端口直接安装到AA00，声明并实测剩余自由度为0。
- checkpoint工具新增目标上下文投影：AH00执行图只保留AH00、AA00及三条直接配合，不再要求解析与本次安装无关且尚未装入的AG00。
- AH00发布级实证为3/3配合、完全约束、无case/叶位姿锚点、求解干净、保存关闭重开一致和源文件不变。
- `relation-v14-project03-ae00-ad00-ai00-ah00-driving-20261011`只授权AE00、AD00、AI00、AH00四条已有当前证据的模板。
- 通用自然语言累计事务形成4个包；最终AH00包严格消费AI00包提交的实体，任务`project03-job-884766b7b8c5`一次完成。

功能修改意义：标定端口首次进入发布级自然语言累计链；执行图投影消除了旧原型图的无关模块依赖，但没有改变任何端点或配合语义。

## 8.30 Project03 AJ00供胶端口与五包累计链（2026-10-11）

- AJ00供胶模组通过`support_plane + locating_hole_1 + locating_hole_2`三基准端口直接安装到AA00，声明并实测剩余自由度为0。
- 目标上下文投影后，AJ00执行图只包含AJ00、AA00和3条直接驱动配合，不继承旧原型中与本次安装无关的模组依赖。
- AJ00发布级实证为3/3配合、完全约束、无case/叶位姿锚点、求解干净、保存关闭重开一致和源文件不变。
- `relation-v15-project03-five-module-driving-20261011`授权AE00、AD00、AI00、AH00、AJ00五条已有当前证据的模板。
- 通用自然语言事务按调用方指定token顺序形成5个累计包；最终AJ00包严格消费AH00包提交的实体，任务`project03-job-ab65b73736c8`一次完成。

功能修改意义：Project03全部5条无锚点原子闭合端口已进入同一发布目录和累计实体链，证明端口目录不仅能逐个恢复面，还能支持多个独立子装配体连续组合。

## 8.31 发布绑定自然语言与已有实例关系端口（2026-10-11）

- 通用自然语言清单可绑定指定不可变关系发布，后续每个安装端口和关系端口均只能从该发布授权集合中选择。
- 对接口类型相同、每条配合两端角色相同的安装模板，A/B方向只是目录迁移产生的等价表示；系统归一为单一候选。距离、平行等普通关系不自动归一，仍保留人工确认语义。
- 当命令同时指向两个已存在实例并明确平行、重合、距离等关系时，系统转入已有实例关系编辑，不再尝试增加第三个实例。
- Project01中SS00通过三基准端口安装到JJ00；GN00先通过主安装端口连接JJ00，再通过防转平行端口连接SS00，两条关系在同一个GN00事务包内形成零剩余自由度组合。

功能修改意义：语义端口目录开始同时服务“新增模组定位”和“已有模组补充关系”，更接近自然语言自由组合，而不是只能沿星形基座逐个添加。

## 8.32 数据驱动关系发布与Project05顺序验证（2026-10-11）

- 驱动发布现由声明式规格列出模板、证据、预期配合数、项目作用域和模板组合；发布器从目录读取端口/模板语义，不再在Python脚本中逐次追加模组ID。
- Project03 v16用同一规格一次授权AE00、AD00、AI00、AH00、AJ00五条端口模板，并复用各自真实checkpoint证据。
- Project05发布绑定用例仅授权D000—A000三基准端口；自然语言换一种表达仍能唯一选中相同模板并生成D000事务包。
- M000、F000、P000、G000可按两种顺序编译，说明全局端口图不依赖Project05固定步骤；但这些端口仍来自未发布目录，不能用于发布级驱动执行。

功能修改意义：端口语义、真实CAD证据和发布权限形成了可重复的数据链；“解析得到关系”与“关系已获准驱动CAD”被明确分开。

## 8.33 Project05 F000非锚点端口与双模板顺序互换（2026-10-11）

- F000双读头条码扫描模组通过A000/F000三基准端口定位；执行图删除案例锚点和目标叶位姿锚点，只保留目标、基座及3条真实驱动配合。
- F000从确定性非原型初始位姿开始，实测3/3配合、完全约束、求解干净、保存关闭重开和源文件不变均通过。
- 候选提升器只在上述checkpoint完整通过时把F000模板升级为`fullyLocatesAddedComponent=true / expectedResidualDof=0 / caseAnchorAllowed=false`；有效图必须使用可移植的工作区相对路径。
- v20不可变发布同时授权D000和F000。自然语言清单按`D000→F000`和`F000→D000`两种顺序分别生成2个包，并完成真实累计CAD执行。
- 四个包均由各自语义端口和配合求解定位，没有读取原型顶层Transform；闭环报告为`demo/global_assembly_contexts/project05-release-permutation-v2/closure-report.json`。

功能修改意义：Project05端口目录首次证明两个独立模组不仅能被解析，还能在同一发布权限下按不同顺序真实追加到同一基座；顺序不再由项目专用固定流程决定。

## 8.34 Project05 M000 CCD端口与三模组顺序闭环（2026-10-11）

- M000 CCD模组的A000安装端口包含3条真实驱动配合；移除原型案例锚点后，从确定性非原型初始位姿仍能完全定位。
- M000真实checkpoint为3/3配合、完全约束、无case/叶位姿锚点、求解干净、保存关闭重开一致，证明其闭合性来自端口配合而非原型Transform。
- 多目标候选目录同时登记F000和M000端口，D000继续使用已发布的独立三基准模板；v21发布授权三个模板。
- `D000→F000→M000`和`M000→F000→D000`均由同一全局目录及发布白名单选择端口，分别完成3包真实CAD累计装配。
- 每个包只使用当前目标与A000的安装端口；已有附加模组不会改变下一个模组的端口选择，因此顺序可交换。

功能修改意义：语义端口目录已支持三个独立附加模组的发布级顺序互换，进一步证明“端口选择＋配合求解”可以替代按项目写死的装配顺序。

## 8.35 Project05 G000柔性端口与四模组顺序闭环（2026-10-11）

- G000安装端口由平行、同心和重合三条真实驱动配合组成；删除案例/叶位姿锚点后仍能从非原型初始位姿确定整模组外部安装位置。
- G000子装配体声明为柔性，安装完成后允许内部执行机构继续运动。因此端口闭合判断使用“外部约束状态被接受＋组件柔性语义匹配”，而不是把内部自由度错误地当成整模组漂移。
- v23发布在同一目录摘要下授权D000、F000、M000、G000；正序和逆序累计装配都只从相应A000安装端口选择配合。
- G000分别作为第一和最后一个附加模组通过真实CAD保存重开，证明其端口选择不依赖已有附加模组或固定顺序。

功能修改意义：语义端口目录不仅能够处理刚性模组，还能够表达“外部定位固定、内部机构可动”的柔性模组，避免用强制刚化换取表面上的完全约束。

## 8.36 Project05 P000自由槽端口与四关系闭合（2026-10-11）

- P000双杯排胶模组的原型安装关系为`重合43＋平行14＋槽口6`；槽口高级选项为Free，因此该组合保留沿槽方向平移，不是完整定位端口。
- 槽口两端由P000同一安装叶零件上的同半径圆柱面识别，槽长约50 mm；A000销轴位于槽内约59.75%位置。这些数据用于解释原型，不把Free槽口擅自改为Centered/Distance/Percent。
- 新端口在保留原型Free槽口的同时，增加`P000_LOCATING_DISTANCE_X=345.122535 mm`。距离端点来自P000与A000各自已登记的稳定侧平面，参数权限为`prototype_estimate`。
- P000端口共登记8个面端点和4个驱动步骤；有效图路径为工作区相对路径，可随不可变目录一起解析。
- 非原型初始位姿checkpoint证实四关系使P000外部刚体自由度归零；端口不使用case锚点或目标叶位姿锚点。
- v25发布允许自然语言命令“将P000双杯排胶模组安装到A000”唯一选择该端口；P000与F000交换添加顺序时，两条累计CAD链均通过。
- v25下进一步执行`P000→G000→M000→F000→D000`五附加模组链；五个端口分别连接A000，每包只重建当前目标关系并消费前一实体检查点，整链约208.59秒完成。

功能修改意义：高级槽口关系不再被简化成普通两面配合，也不再由源位姿暗中补足自由度；端口目录能够同时表达“允许滑动的原始关系”和“用于Demo闭合的显式工程尺寸”。

## 8.37 Project05 N000自由槽端口与六模板发布（2026-10-11）

- N000原型安装关系为`重合42＋平行13＋槽口4`，其中槽口为Free；其约束秩为5/6，剩余沿槽X方向平移。
- N000槽口端点不是圆柱销，而是安装叶零件上的平面槽壁；A000端点是圆柱定位销。端口图通过`AnalysisGeometry.SlotAxisWorld`和槽参考点保留真实槽语义。
- 槽两端圆弧中心约为`[0.700, 0.656, 0.4315]`与`[0.750, 0.656, 0.4315]`米，槽长约50 mm；A000销位于第一端附近。
- 为封闭唯一剩余自由度，增加`N000_LOCATING_DISTANCE_X=465 mm`。端点来自N000与A000已登记的稳定侧平面；该尺寸仅是原型测量值，不是厂商基准。
- 四关系端口从非原型初始位姿完成4/4配合并达到6/6刚体秩；保存、关闭、重开后约束状态和参数均保持一致。
- N000端口包位于`demo/global_assembly_catalog/v1/combination-v1-preview/project05-nonanchor-driving-v7/N000`，全局模板ID为`template/project05/n000-to-a000-nonanchor-driving-v2/a5c9d7e56f`。
- v26不可变发布同时授权D000/F000/M000/G000/P000/N000六个Project05附加模组；`N000→P000`和`P000→N000`均通过真实CAD累计装配。

功能修改意义：面目录、配合图和自由度分析现在能表达“目标侧槽壁、基座侧定位销、Free槽口及补充定位尺寸”的完整机械语义，为继续审计K000、B000提供了可复用模板。

## 8.38 Project05 K000三基准端口（2026-10-11）

- K000双工位顶升定位模组通过`重合4＋平行2＋同心5`连接A000，6个端点均已有持久引用、叶路径、体/面索引和局部几何信息。
- 三关系对外部刚体形成6阶独立约束，预计剩余自由度为0；旧目录中的`project05_source_pose_case_anchor`已由真实非锚点checkpoint取代。
- 新模板`K000_to_A000_nonanchor_driving_v1`只允许A000/K000精确三配合束，不允许case锚点或目标叶位姿锚点。
- v27发布授权七个附加模组；K000与N000交换插入顺序时均通过真实CAD累计装配。

功能修改意义：K000证明完整的平面、方向面和定位孔组合无需额外估计尺寸即可从任意初始位姿恢复，避免把原型Transform误当成机械基准。

## 8.39 Project05 B000柔性运动组端口与8/8发布（2026-10-11）

- B000通过`重合37＋同心1＋平行1`连接A000；三关系对B000整组的外部安装刚体形成6/6约束。
- B000源组件求解状态为`swComponentFlexibleSolving`。候选模板保持`internalFlexibilityPreserved=true`，真实checkpoint同时满足外部完全约束和`ComponentSemanticsMatch=true`。
- Z000仍作为B000/Z000运动组的内部成员，不注册为第二个独立龙门安装对象；自然语言添加B000时插入独立B000子装配体并保留其内部结构。
- 新模板`B000_to_A000_nonanchor_driving_v1`进入v28发布。v28共授权D000、K000、F000、M000、G000、N000、P000、B000八个待装对象。
- B000与K000正反顺序累计实体均通过，证明柔性运动组可以位于累计链首或链尾，且不会要求固定项目顺序。

功能修改意义：Project05端口目录从局部试验集扩展为当前机械范围8/8完整发布；系统能够在不刚化内部机构的前提下，用面级配合确定整个柔性子装配体的安装位置。

# 2026-10-11 Project02 A800/A180无锚点语义端口与累计装配闭环

- A800安装束升级为`重合35＋宽度9＋A800_LOCATING_DISTANCE_X`。纵向距离`49.5 mm`来自原型稳定侧平面测量，明确标记为`prototype_estimate / productionReady=false`；不再依赖原型顶层Transform或case锚点。
- A180安装束升级为`重合34＋距离24＋槽口3`。`槽口3`的Free参数和两端稳定面已补齐；真实CAD证明原三配合已完全定位。曾尝试增加额外X距离，但SolidWorks报告过约束，故已撤销并保留失败记录。
- 两个严格checkpoint均从确定性非原型初始位姿执行：各3/3配合创建、完全约束、求解干净、无case/叶位姿锚点、源文件未改，并通过保存、关闭、重开与摘要复核；耗时约`56.68 s`和`54.84 s`。
- 新增候选构建器`scripts/build_project02_a800_a180_driving_candidates.py`，把稳定面端点、有效图、严格checkpoint和全局模板一次性打包；两条模板均在全局兼容矩阵中标记为可移植。
- 首版v29发布的有效图路径仅写文件名，通用执行器在CAD启动前失败关闭；修正为工作区相对路径后，以新ID发布`relation-v30-project02-a800-a180-portable-driving-20261011`。
- 三句自然语言命令“A600基础环境→安装A800→安装A180”编译为两包作业`project02-job-d13cf4819eaa`，真实累计执行一次通过，总耗时约`73.09 s`；A800约`37.40 s`、A180约`35.57 s`。
- 最终实体：`demo/global_assembly_contexts/manifest_jobs/project02-job-d13cf4819eaa/packet-runs/packet-002-attempt-01/project02-release-a800-a180-v2-packet-002.SLDASM`。
- 机器可核验闭环：`demo/global_assembly_contexts/project02-release-a800-a180-v2/closure-report.json`；最终SHA-256为`c1628850b7bea5166c1103c9b84b2246f269e0c80ade184c22173bd414cd8d09`。
- 实体干涉/B-rep按当前主线保持`not_evaluated`，不影响本次自然语言模组级配合驱动闭环结论。

功能修改意义：Project02最关键的“基座→传输→扫描”机械顺序已从带原型位姿补位的Demo升级为可发布、可自然语言编排、可从独立模组累计生成实体的通用链，为继续接入A700/A300/A500等功能模组建立了稳定基线。

## 8.40 Project02 A500/A700端口与四包累计链（2026-10-11）

- A500通过`重合13＋宽度4＋距离27`连接A600；从确定性非原型初始位姿执行时，3/3配合创建并达到完全约束。
- A500与A700的50 mm关系属于两端均存在后才可执行的只读工艺验证，不属于A500安装配合；当前安装图将其登记为延迟验证。
- A700通过`平行1＋平行2＋距离6＋重合38＋宽度10＋距离29`连接A600。旧案例锚点和两个内部叶姿态锚点均已删除。
- A700外部安装配合束在真实CAD中被接受，内部子机构继续保持柔性；因此用`TargetConstraintStateAccepted＋ComponentSemanticsMatch`验收，不把合法内部运动误判为安装失败。
- v32发布同时授权A800、A180、A500、A700四条无锚点端口；四条模板均有独立checkpoint、面端点目录和工作区可解析执行图。
- 自然语言顺序A800→A180→A500→A700编译成4个累计事务包，作业`project02-job-1f558d80f971`一次通过，总耗时约153.83秒。
- 各包耗时约37.23、35.97、37.30、42.95秒；最终实体为`demo/global_assembly_contexts/manifest_jobs/project02-job-1f558d80f971/packet-runs/packet-004-attempt-01/project02-release-a800-a180-a500-a700-v4-packet-004.SLDASM`。
- 闭环报告为`demo/global_assembly_contexts/project02-release-a800-a180-a500-a700-v4/closure-report.json`，最终SHA-256为`ef2ebade3c46b0d84375fb416b5c56b2cd03d1e3535d3337c3377d4b316a3153`；碰撞/B-rep未执行。

功能修改意义：Project02已从两模组关键链扩展为“传输、扫描、校准、柔性服务”四模组真实累计装配，且每个位置均由可审计配合而非原型顶层位姿或隐藏锚点决定。

## 8.41 Project02 A300端口与五包累计链（2026-10-11）

- A300排胶杯通过`距离19（80 mm）＋距离20（390 mm）＋重合39`安装到A600，静态刚体约束秩为6/6。
- 旧执行图使用A300原型case锚点避免距离配合的镜像分支；新图删除该锚点，并保留已由CAD验证的`距离20`归一化创建方向。
- A300从确定性非原型初始位姿执行严格checkpoint，3/3配合、完全约束、参数重开一致、求解干净、源文件不变及会话清洁均通过，约43.11秒。
- v33发布同时授权A800、A180、A500、A700、A300五条端口；自然语言作业`project02-job-68696a91e2bc`按五模组顺序累计执行成功，总耗时约196.87秒。
- 五包耗时约38.26、36.73、37.91、43.68、39.79秒；最终实体为`demo/global_assembly_contexts/manifest_jobs/project02-job-68696a91e2bc/packet-runs/packet-005-attempt-01/project02-release-five-addon-v5-packet-005.SLDASM`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-five-addon-v5/closure-report.json`；最终SHA-256为`7d1ea91213844fb4e55e6f3224c138424cc85bd8fb9975b57c81f6a6d12ade32`。

功能修改意义：Project02已形成包含刚性、柔性、高级槽口和有符号距离分支的五模组累计实体链，进一步证明通用编排器可以消费不同机械语义，而非复制固定项目流程。

## 8.42 Project02 A200 CCD端口与六包累计链（2026-10-11）

- A200 CCD模组通过`重合26＋槽口1＋槽口2`连接A600；两个槽口均为Distance模式并保留完整高级参数。
- 旧静态图缺少槽轴分析几何，因此解析自由度只识别重合面的3个约束；新流程将该局限明确记录，并交由真实SolidWorks求解器裁决，而不是猜测新增配合。
- A200去除原型case锚点后，从确定性非原型初始位姿执行严格checkpoint：3/3配合、完全约束、组件语义匹配、求解干净、保存关闭重开和源文件保护全部通过，约51.27秒。
- v34不可变发布授权A800、A180、A500、A700、A300、A200六条无锚点端口；自然语言作业`project02-job-0761271ce4f9`完成6包真实累计装配，总耗时约244.12秒。
- 六包耗时约37.67、36.38、38.14、45.07、40.67、45.47秒；最终实体为`demo/global_assembly_contexts/manifest_jobs/project02-job-0761271ce4f9/packet-runs/packet-006-attempt-01/project02-release-six-addon-v6-packet-006.SLDASM`。
- 闭环报告：`demo/global_assembly_contexts/project02-release-six-addon-v6/closure-report.json`；最终SHA-256为`639bfbd5215090cdb299aff166b8969f954b99b47204eebbc30633947db1fa8d`。

功能修改意义：Project02 CCD安装从“原型位姿＋案例锚点”升级为完整高级槽口配合驱动；自然语言累计链现已覆盖六个附加模组，并对静态模型与权威CAD的职责边界形成可复用做法。

## 8.43 Project02 A100外部安装与七包累计闭环（2026-10-11）

- A100仅使用顶层`重合8＋重合9＋距离9`安装束连接A600；静态刚体分析为秩6/6、剩余自由度0。
- 执行图不包含整模组case锚点，也不包含原型中的36个内部叶位姿锚点；A100从确定性非原型初始位姿插入。
- 严格CAD checkpoint约78.79秒通过：3/3配合、完全约束、组件语义一致、求解干净、保存关闭重开一致、源装配体未改。
- A100继续保持柔性求解；该证据只授权顶层安装位置，不授权内部阀头/滑台工艺姿态。
- 七目标候选目录发布为`relation-v35-project02-seven-addon-portable-driving-20261011`，一次授权A800、A180、A500、A700、A300、A200、A100七条端口。
- 八句自然语言命令编译为七包持久CAD作业`project02-job-3a22a673ec04`，按A800→A180→A500→A700→A300→A200→A100执行，总耗时约308.40秒。
- 七包全部通过配合创建、约束状态接受、求解、保存关闭重开、源保护、无case/叶位姿锚点和输出摘要检查。
- 闭环报告：`demo/global_assembly_contexts/project02-release-seven-addon-v7/closure-report.json`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：Project02已从六个静态/服务模组扩展到包含柔性龙门的七模组累计装配；系统能够在不复刻原型内部姿态的前提下，由自然语言、发布语义端口和真实CAD配合逐步形成完整主设备结构。

## 8.44 Project02双T401非星形端口与九包闭环（2026-10-11）

- T401-1源关系`重合14＋距离10`仍剩1个刚体自由度；增加基于已登记稳定平面的Z向距离后达到6/6，真实CAD以3/3配合完成无锚点安装。
- T401-2不直接连接A600，而通过A200的端口安装。源`距离28`仍剩3个自由度；增加X、Y两个独立平面距离后达到6/6，真实CAD以3/3配合完成无锚点安装。
- 两个新增尺寸均来自Project02原型测量，权限为`prototype_estimate`，不是厂商安装基准；本阶段用于粗装Demo。
- 全局目录保留同一T401 CAD定义的两个实例容量，并发布两个不同模板：`T401_1_to_A600_nonanchor_driving_v1`与`T401_2_to_A200_nonanchor_driving_v1`。
- 自然语言解析新增“唯一剩余实例容量”规则：当命令同时提到已存在的A200与T401时，A200已满而T401尚有第二个实例容量，因此自动把T401识别为新增对象。
- v36不可变发布共授权9条安装模板；10句自然语言命令编译为9包作业`project02-job-28dac4c3a894`，全部一次成功，总耗时约409.16秒。
- 最终累计实体包含A600、A800、A180、A500、A700、A300、A200、A100以及两套T401；第二套供胶真实连接A200，证明装配图已从星形扩展到非星形结构。
- 闭环报告：`demo/global_assembly_contexts/project02-release-nine-addon-v8/closure-report.json`；碰撞/B-rep保持`not_evaluated`。

功能修改意义：系统首次在同一自然语言长链中处理“重复CAD定义＋不同端口＋不同上下文模组”，证明累计装配可以表达更一般的模组关系图，而不是只把所有对象安装到基座。

### 8.45 双T401包边界暂停恢复与通用柔性摘要（2026-10-11）

- 从完整九包清单的第7包A100检查点建立两包后续作业`project02-job-4885035c7bc0`，种子通过包摘要、装配体摘要和路径一致性验签。
- 第8包T401-1提交后主动暂停，状态为`paused`，第9包仍为`pending`；恢复后只执行第9包T401-2，第8包尝试次数保持1。
- 暂停与恢复两个阶段合计约103.32秒，最终作业状态为`succeeded`，两套T401均有独立实体检查点。
- 通用编排闭环报告现读取每包执行图与CAD结果，输出外部安装状态、目标完全约束观察、求解状态、组件语义匹配及内部柔性保持状态。
- Project02九包报告中A700、A200、A100均显示外部安装约束接受且内部柔性保持；其余刚性模组显示外部安装通过、内部求解模式为刚性。
- 汇总证据：`demo/global_assembly_contexts/project02-release-nine-addon-v8/orchestrator-closure.json`。

功能修改意义：重复实例长链不仅能连续执行，也能从已验签检查点恢复；柔性模组的机械含义不再依靠项目专用文字解释，而进入通用机器可读证据。

## 8.46 主线调整：全目录语义端口覆盖优先（2026-10-11）

- 当前主线不再优先深挖Project02 A700内部结构，而是优先完成全局目录中各子模组的真实机械语义端口覆盖。
- A700保留为已知专项：无锚点模板已证伪，强制刚性不足以修复；显式Project02标定回退已闭环，但`portable=false`。后续只有在全目录覆盖需要验证通用柔性端口机制时才重新进入该专项。
- 端口来源采用“双证据路线”：首先导出原型中同层级子装配体之间的配合关系，恢复两端真实几何和完整配合参数；随后用机械知识、几何结构和功能资料判断这些几何是对外安装基准、工艺验证点，还是模组内部运动关系。
- 每个模组的端口数量不预设。底座类模组可能暴露多个安装位，扫描器可能同时具有安装端口、出光/视场端口和条码目标兼容语义；普通支架也可能只需要一个由多个几何约束组成的复合安装端口。
- 覆盖统计必须区分“至少有一个端口”和“可用于完整装配”。后者要求端点可恢复、存在兼容模板、配合束能够确定外部位姿，并最终取得非原型初始位姿的CAD证据。
- 不采用所有模组两两穷举。先抽象端口类型与兼容规则，例如`mounting_surface`、`locating_hole`、`anti_rotation_plane`、`scanner_optical_axis`、`barcode_target_region`，再由少量关系模板覆盖多种具体模组组合。
- 下一步应生成按模组、项目、端口类型、兼容关系、配合束完整性和证据等级统计的全目录缺口清单，优先处理“已有原型配合但尚未迁移为稳定端口”的高收益项。

功能修改意义：端口建设从项目专用长链转为全局机械接口知识库建设，为跨项目、非固定顺序的自然语言模组组合提供真正可扩展的基础。

## 8.47 全目录角色/端口轻量覆盖与首个跨项目替换MVP（2026-10-12）

- 新增`cross_project_module_substitution.py`，在现有全局目录之上生成独立角色覆盖，不改写权威CAD目录。
- 43个模组全部获得已接受的`primaryRole / displayRole / capabilities`；独立可装配性没有被角色确认自动代替，非基座项仍保持待审。
- 74个既有语义端口全部附加规范接口元数据，原始接口类型、面端点证据和模板来源保持不变。
- 新增跨项目替换兼容判定：主角色、规范接口类、驱动配合拓扑、定位特征几何不变量、端口可移植性和零剩余自由度缺一不可。
- Project03 AH00与Project01 BD00均识别为`Calibration`，安装接口为`calibration_base_mount`，驱动拓扑均为`COINCIDENT + CONCENTRIC + CONCENTRIC`，双定位孔中心距均为50 mm，因此生成一条新的跨项目模板。
- 自然语言“在项目01基座中使用项目03 AH00针头校准模组替换BD00”已编译为2个实例、1条连接、1个CAD事务包和3条驱动配合；CAD尚未启动，碰撞状态保持`not_evaluated`。
- 后端新增`POST /api/demo/global-module-catalog/cross-project-substitutions/preview`，可直接获得兼容报告、装配上下文、事务DAG和CAD事务清单。
- 构建脚本：`scripts/build_cross_project_substitution_mvp.py`；输出目录：`demo/cross_project_substitution/mvp-v1/`。
- 首次实体作业在0.13秒内被执行器拒绝，原因是跨项目模板只有端点事务包、没有唯一有效配合图；未启动SolidWorks，也未产生待回滚输出。
- 新增跨项目有效图组合：保留Project03 AH00端点、Project01 JJ00槽位端点和三条驱动配合，只包含JJ00与AH00两个模组，不含原型顶层或叶级位姿锚点。
- 修正后的计划通过硬验证：目标`FL9A24D063AH00`、基座`JJ00`、请求3条配合、有效图3条配合，覆盖状态为`exact`。
- 持久CAD作业`project03-job-d75711e079d8`执行成功：3/3配合创建、保存关闭重开、参数复核、完全约束、求解干净和源文件保护均通过。
- 输出装配体：`demo/cross_project_substitution/mvp-v1/jobs/project03-job-d75711e079d8/packet-runs/packet-001-attempt-01/cross-project-198b22e272c5-packet-001.SLDASM`，SHA-256为`86433a77155ed2714fcdc3dae6bfde082da1d41d986e4db47685c5fb3b1e4d84`。
- 作业总耗时约185.60秒，实际CAD适配器32.43秒；首次JJ00基座包装缓存未命中，其余时间主要用于独立包装准备和进程编排。
- 有效图及关联执行回归44项通过；核心构建资产重复生成SHA-256一致。
- 实体执行后已无保存关闭JJ00原型及其2个残留叶零件，原型源文件SHA-256保持不变，SolidWorks恢复为0个打开文档。
- 基座包装器已增加“运行前文档基线→仅关闭本次新增文档→复核会话恢复”的自动清理门禁；新增2项清理测试后，全量后端回归为`947 passed, 3 subtests passed`，耗时46.86秒。

功能修改意义：系统已经能把“来自不同原型但机械槽位兼容的同角色模组”组合成新的有效配合图，并从确定性非源初始位姿生成真实SolidWorks装配体，而不是复制任一原型顶层位姿或只做文本推荐。

## 8.48 全目录候选矩阵、端口方向消歧与第二类跨项目传输接口闭环（2026-10-12）

- 新增全目录候选矩阵构建器：汇总43个模组定义，并对118个有向跨项目同角色组合进行统一判定。
- 初版矩阵中的6项“待消歧”经端口方向复核后已全部消除。最终结果为：4项可直接组合有效图、0项需要模板消歧、58项缺少端口或模板、56项存在已知不兼容；0项仅停留在机械几何复核。
- 4项可组合关系覆盖两类接口族：校准模组`AH00↔BD00`，传输模组`AE00↔SS00`。最终矩阵摘要为`3a6ea08b71ebc3f5a2bd09822720f056af8531eb2e95cb1936c6472cced802ac`。
- 端口规范新增`portDirection / portPurpose / installationProfileId / ownerRole`：A200自身连接A600的端口为`required / external_installation`，A200供T401安装的端口为`provided / child_module_slot`，不再把两者误认为A200的两个自身安装方案。
- T401保留两个真实安装配置；候选选择器会根据目标槽位提供方角色自动选择。与GJ00/AJ00比较时唯一选择面向基础箱体的`T401-1`配置，而非连接CCD的`T401-2`配置。
- 原6项随后因为配合拓扑不同且缺少可比较定位几何，被准确改判为`incompatible`；系统在启动CAD前拒绝，不能通过人工选择模板绕过机械硬冲突。
- 为避免把Project01 `GN00—SS00`单条防转平行关系误识别为独立安装端口，原子安装束现在要求至少两项驱动配合；这使传输模组唯一完整安装束能够自动消歧。
- 第二个MVP使用Project03 `AE00`传输模组替换Project01 `SS00`槽位；两端接口均为“支承面＋双定位孔”，定位孔中心距均为58 mm，离线编译耗时约0.101秒。
- 真实作业`project03-job-e64acfa17a55`成功：从确定性非源初始位姿插入AE00，3/3配合创建，完全约束、求解干净、组件语义一致、保存关闭重开及参数复核全部通过。
- 作业总执行约76.23秒，其中CAD适配器约72.36秒；基座包装缓存命中，避免重复准备约152.35秒。
- 输出装配体：`demo/cross_project_substitution/transport-v1/jobs/project03-job-e64acfa17a55/packet-runs/packet-001-attempt-01/cross-project-3fd5ce476712-packet-001.SLDASM`，SHA-256为`d6746c57b475c219b9d40ba32fc3fde11b42fe0f23905a4d6758ef632b66ffbb`。
- 事务包级会话清理已生效：运行前0个文档，结束时自动关闭2个基座叶零件，恢复为0个文档且无错误。消歧逻辑完成后的完整后端回归为`953 passed, 3 subtests passed`。
- 碰撞/B-rep未执行，状态保持`not_evaluated`；本轮结论限于角色、接口、配合定位和CAD保存重开闭环。

功能修改意义：跨项目组合不再依赖人工逐对挑选；系统已有全目录优先级地图，并用第二类机械接口证明“角色→接口→完整配合束→真实CAD”的方法能够跨项目复用。

## 8.49 GN00组合端口与Project03 AB00完整安装束补齐（2026-10-12）

- Project01 GN00不再被误判为“缺少完整端口”：其安装能力来自已发布的精确组合，JJ00提供主安装束，SS00提供防转关系；组合共同声明零剩余自由度。
- SS00防转端口依据不可变发布证据规范为`provided / child_module_slot`，但单独仍不构成原子安装接口。
- Project03 AB00旧端口只包含重合和只读距离，并依赖原型位姿锚点；复查原型配合图后确认还存在四面宽度配合，原始八个面端点均具有持久引用。
- 新增AB00完整端口：`重合＋宽度居中＋40 mm距离`。离线生成8个端点、2个端口和1个零自由度模板，不使用case位姿锚点。
- 真实SolidWorks验证成功：独立AB00插入、3/3配合创建、完全约束、求解干净、保存关闭重开、配合类型/方向/距离/高级参数复核全部通过。
- CAD总耗时约123.23秒；主要阶段为打开与解析42.77秒、独立插入12.37秒、创建配合2.44秒、保存关闭35.39秒、重开复核28.35秒。
- AB00模板已发布为不可变关系目录`relation-v39-project03-ab00-complete-driving-20261012`，授权范围仅为该完整三关系安装束。
- 重建后的118项有向同角色矩阵：4项可直接组合、0项待几何复核、0项待消歧、48项缺端口/模板、66项已确认不兼容。
- 其中48项缺口全部属于已延期Project06；排除Project06后的活动范围为：4项可组合、0项缺端口/模板、66项不兼容。
- `incompatible`不是未完成项：它表示现有证据已经发现接口、配合拓扑或定位几何硬冲突，不能直接跨项目替换。
- 定向回归34项通过；完整后端回归`958 passed, 3 subtests passed`，耗时47.93秒。
- 碰撞/B-rep未执行，保持`not_evaluated`，不纳入本轮语义端口覆盖结论。

功能修改意义：轻量覆盖阶段已完成当前活动项目的“端口/模板空白清零”，并用高级宽度配合的真实CAD闭环证明可以从原配合图恢复被旧实现遗漏的完整安装语义，而不是增加原型位姿依赖。

## 8.50 不兼容关系分层与首个转接接口需求包（2026-10-12）

- 将活动范围内66项有向不兼容记录合并为33组无向机械接口问题，避免双向重复统计。
- 分层结果：28组为安装拓扑不同，3组为已量化定位孔距不一致，2组为安装上下文架构不同。
- 所有33组均保持`directCombinationAllowed=false`，没有通过修改标签或放宽配合规则伪造兼容关系。
- 选择扫描模组作为首个转接需求样例：Project03 AI00模组侧双定位孔间距为200 mm，Project01 SM00原槽位为22 mm，绝对差178 mm。
- 已生成双接口转接需求，明确要求模组侧200 mm接口、基座侧22 mm接口；当前没有转接件CAD和端点目录，因此状态为`engineering_geometry_required`。
- 后端自然语言替换预览已接入工程处置：输入“用项目03 AI00扫描模组替换项目01 SM00”时，返回孔距差、转接件需求和所需证据，并在CAD前失败关闭。
- 输出目录：`demo/cross_project_substitution/incompatibility-triage-v1/`，包含完整分层JSON、Markdown报告和AI00→SM00转接需求JSON。
- 定向回归18项通过；完整后端回归`964 passed, 3 subtests passed`，耗时48.39秒。
- 碰撞/B-rep未执行；当前阻塞发生在机械接口层，启动实体检查没有工程意义。

功能修改意义：跨项目自由组合能力开始具备“可组合则编译、不兼容则解释、可转接则生成需求”的完整决策边界，不再把所有失败都留给人工阅读原始配合数据。

## 8.51 已登记备用槽位扫描与A600定向采集任务（2026-10-12）

- 新增备用槽位发现器，对28组安装拓扑不一致关系的56个有向替换方向逐一检查目标基座现有`provided`端口。
- 扫描结果为：0个可直接使用、0个仅需几何复核、0个已登记但仍不兼容、56个没有已登记备用槽位；该结论不表示基座实体不存在其他孔系，只表示当前端口目录没有相关证据。
- 发现器只消费已发布语义端口，不猜测未登记CAD几何，不授权CAD执行，也不触发碰撞/B-rep。
- 将首个高价值采集目标收敛为“Project03 AH00校准模组安装到Project02 A600”。AH00已登记接口为支承面加两个定位孔，孔距50 mm。
- A600原生A500槽位的端点为支承面、两宽度侧面和偏置面，配合拓扑与AH00双孔定位不同，不能直接复用或改名。
- 现有A600几何捕获包含158个叶组件和708个实体包围盒，安装面文件包含平台与keepout，安装坐标系包含操作面、支承面与中心面；这些资产都不足以证明50 mm孔系。
- 新增机器可读采集请求：只优先扫描A500原生槽位所在静止叶零件`24D062-FL5B24D062A600001.01-1-1`及实体索引12，筛选“支承面＋两平行定位轴＋50±0.5 mm中心距”。
- 若定向自动筛选无结果，回退为人工选择两个定位面和一个支承面；端点目录发布前维持`geometry_capture_required / cadExecutionAllowed=false`。
- 产物位于`demo/cross_project_substitution/alternate-slot-discovery-v1/`，其中A600专项子目录包含JSON采集合同、Markdown说明和构建摘要。
- 新增采集结果筛选器：读取叶级面目录后，自动比较圆柱轴平行度、轴间垂距、支承面法向和50 mm目标孔距；筛选命中仍只进入人工复核，不会自动发布端口。
- 使用现有A500有界端点目录进行负例闭环：目标叶中只有4个平面端点、0个圆柱端点，正确返回`no_matching_geometry_in_supplied_catalog`和0个候选，没有误报备用槽位。
- 首次按默认500面上限采集时安全失败，未产生不完整目录；显式提高到2000面后，只扫描同一目标叶零件并成功得到1521个面端点，未遍历A600其余叶组件。
- 实测目录包含850个平面和587个圆柱面。按同实体、同半径、轴平行、50±0.5 mm孔距以及共同支承面筛选后，收敛为Body 72上的两个50 mm定位孔列；孔半径均为2.10 mm。
- 两个孔列在A600安装坐标系中的`xIntoMachine`分别为0.1613 m和0.1863 m；依据“优先靠近操作面”的已声明工艺顺序选择前者，同时保留后者为备用候选，没有以原型模组位姿替代选择。
- 已将选中支承面和两个定位孔封装为未发布候选端口，并在SolidWorks中逐个按EndpointId恢复；3/3恢复成功，总耗时7.22秒，当前恢复策略为`BodyFaceIndex`。
- 恢复成功只授权下一步候选跨项目CAD验证，端口仍为`portable=false / semanticPortPublished=false`；必须完成AH00非原型初始位姿插入、3个配合、完全约束及保存重开后才能发布。
- 定向回归7项通过；完整后端回归`973 passed, 3 subtests passed`，耗时79.57秒。碰撞/B-rep未执行，继续保持独立可选后验验证。

功能修改意义：目录覆盖从“只知道没有备用端口”推进到“定向找到真实候选孔系、稳定恢复具体面并形成未发布候选端口”，后续可直接进入小范围跨项目装配验证，无需再次解析整机或盲扫全部实体。

## 8.52 A600校准备用槽位真实CAD闭环与跨项目发布（2026-10-12）

- 候选端口的两个50 mm定位孔不再按EndpointId或遍历顺序分配角色，而按A600局部坐标中的横向位置稳定映射为`locating_hole_1/2`；选择规则和坐标同时进入证据。
- 新增候选CAD验证编译器，将A600基座、Project03 AH00独立模组、一个支承面和两个定位孔编译为`重合＋同心＋同心`三关系有效图。
- AH00从确定性非原型初始位姿插入，不使用整模组case锚点、原型顶层位姿或叶零件位姿锚点。
- 真实SolidWorks执行一次通过：3/3配合创建，全部端点由装配体持久引用恢复，目标完全约束、求解干净、组件语义一致，保存关闭重开后全部参数匹配。
- CAD总耗时约51.00秒；打开和解析14.65秒、独立插入4.32秒、创建配合3.75秒、保存关闭24.19秒、重开复核3.67秒。
- A600与AH00源文件在执行前后SHA-256一致；输出装配体SHA-256为`f200d28f604d62f111cf08cbb12fd6f345c526a5544f36ab09809c4499514829`。
- 发布包只保留实际使用的6个端点，形成A600操作面侧校准槽位和AH00安装端口；模板为`AH00_to_A600_cross_project_three_datum_installation`。
- 全局目录增加“端口级项目归属”薄层，使同一模板包可以同时引用Project02 A600与Project03 AH00，CAD身份仍由各自项目Profile验证，不能由模板虚构。
- 首次v40发布误从通用重建目录起步，导致其作为Project02最新发布时遮蔽v36九模组授权。该发布保留为审计证据，但不作为活动基线。
- 新增发布谱系合并器，从Project02 v36九模组发布增量加入1个端口、1个模板和2条兼容边，得到v41；原Project02 51个模板全部保留。
- 活动发布为`relation-v41-project02-a600-project03-ah00-driving-20261012`，目录摘要`fcb252fc498f57294582dcd6cfc7a9bf298e6652a842a7044e356bab0cef4962`，仅授权新的A600/AH00模板。
- 更新后的备用槽位扫描中，Project03 AH00→Project02 A500替换方向能够发现A600新槽位并返回`registered_alternate_slot_ready`；未从未登记几何猜测其他槽位。
- 完整后端回归`985 passed, 3 subtests passed`。碰撞/B-rep、运动行程、维护空间和生产参数均未验证，不属于本发布结论。

功能修改意义：首个“目录无槽位→定向几何采集→稳定端点→非原型真实CAD验证→跨项目不可变发布→候选矩阵可发现”的完整闭环已经打通；新增能力是可复用的端口登记流程，不是对原型顶层位姿的复刻。

## 8.53 A600操作面侧槽位的自然语言发布绑定与真实累计装配（2026-10-12）

- v41中的端点、有效图和三配合均已可执行，但模板没有声明自然语言方位`operator_side`，因此“安装到操作面侧校准槽位”会在CAD前被语义门禁拒绝。
- 新增有界语义升级：只给既有A600/AH00模板补充`sideSemantics=[operator_side]`；模板编号、两个端口、6个端点和`重合＋双同心`配合束全部不变。
- 新不可变发布为`relation-v42-project02-a600-ah00-operation-side-language-20261012`，目录摘要`2a06dc78b251681ffcba56768ae709815776139fa9ebee3ffed8d8fc64edd8ef`；它复用v41的非原型初始位姿CAD证据，不重新宣称碰撞或生产放行。
- 两条自然语言命令已形成真实闭环：先添加Project02 A600箱体作为基座，再把Project03 AH00校准模组安装到A600操作面侧校准槽位。
- 离线编译约`0.180 s`，唯一选中模板`template/project02/ah00-to-a600-cross-project-three-datum-installat/a133494fd1`，生成1个包、3条驱动配合并绑定v42发布。
- 发现并修复两处跨项目编排缺陷：模板证据属于槽位所有方Project02时，不能据此删除目标模组Project03 AH00的唯一别名；该规则同时进入作业编排器和单包执行器。
- 第一次作业尝试在`0.12 s`内于CAD启动前失败关闭，没有修改CAD；修复后从失败检查点重试成功。
- 持久作业`project-global-job-cd04eec0deb6`第二次尝试耗时`87.88 s`，其中CAD适配器`70.02 s`；A600基座包装缓存命中，估算避免`128.50 s`重复准备。
- 真实CAD结果：3/3配合创建、AH00完全约束、求解干净、保存关闭重开、全部参数复核、源装配保护和会话恢复均通过。
- 输出装配体：`demo/global_assembly_contexts/manifest_jobs/project-global-job-cd04eec0deb6/packet-runs/packet-001-attempt-02/project02-a600-ah00-operation-side-v1-packet-001.SLDASM`；SHA-256为`3b012f542ef6862041b9e188059b717188eec6581bd655d6b0a0b8222d0c5017`。
- 使用v42重建全目录矩阵与备用槽位报告：活动范围仍为2项可组合、2项待配置消歧、0项端口/模板空白、66项已确认不兼容；A600备用槽位发现结果保持2项就绪，没有能力回退。
- 完整后端回归为`991 passed, 3 subtests passed`，耗时49.16秒；碰撞/B-rep保持`not_evaluated`。

功能修改意义：已发布端口不再只能被候选矩阵“发现”，而能由带明确方位的中文命令唯一选择、编译、持久执行并生成可继续装配的真实SolidWorks检查点；这是一条跨项目直接安装链，不再借用“替换A500”的错误语义。

## 8.54 Project01 JJ00与Project03 AE00传输槽位的发布绑定和第二类自然语言实证（2026-10-12）

- 将跨项目目录合并从A600/AH00专用实现抽取为薄层通用函数：只增量接纳指定模板、两个已登记可移植端口和已有兼容记录，不重建全局目录，也不推断新几何。
- 复用此前Project03 AE00替换Project01 SS00时形成的真实接口证据：AE00与JJ00均为“支承面＋双定位孔”，定位孔中心距均为58 mm；旧CAD证据已经证明独立非锚定插入、3/3配合、完全约束和保存重开。
- 新不可变发布为`relation-v43-project01-jj00-project03-ae00-transport-driving-20261012`，目录摘要`0b5dce4cbb98a5f0d90688d9fad3943c7657459ba36a2ea6ff616a6aa2446291`；授权模板为`template/cross-project/ae00-to-project01-ss00-slot/97aed2cb02`。
- 两条中文命令可以直接工作：先添加Project01 JJ00箱体作为基座，再把Project03 AE00传输模组安装到Project01 JJ00传输安装位。命令不再表述为“替换SS00”，实际上下文只包含JJ00和新插入的AE00。
- 离线编译耗时约`0.128 s`，生成1个事务包、3条驱动配合和持久任务`project03-job-f18e29248c09`，且发布授权、命令审计和配合来源完整绑定。
- 新一轮真实SolidWorks执行成功：AE00独立插入，3/3配合创建，目标完全约束、求解干净、保存关闭重开及参数复核通过。
- 本次作业总耗时约`122.23 s`，CAD适配器约`101.34 s`；JJ00基座包装缓存命中，估算避免约`152.35 s`重复准备。
- 输出装配体：`demo/global_assembly_contexts/manifest_jobs/project03-job-f18e29248c09/packet-runs/packet-001-attempt-01/project01-jj00-project03-ae00-transport-v1-packet-001.SLDASM`；SHA-256为`6ee13d82b634ae0c853d454893cba125ff788a40ff3e830feea799768d4982d8`。
- 重建后的候选矩阵已读取v43、v42、v39和v28。4个活动有向候选现在均显示“模板上下文待消歧”，原因是对应接口同时具有原生安装模板与已经发布的跨项目直接模板；这不是端口缺失或CAD能力回退，下一轮需把“已发布可直接执行”从“尚待选择原生安装配置”中单独展示。
- 定向回归`39 passed`；完整后端回归`994 passed, 3 subtests passed`，耗时48.92秒。碰撞/B-rep仍保持`not_evaluated`。

功能修改意义：同一条“中文命令→语义端口→不可变发布→持久任务→真实CAD”流程已经跨越校准和传输两种角色、A600和JJ00两种基座，证明实现依赖全局目录与模板证据，而不是针对A600/AH00写死的单案例逻辑。

## 8.55 已发布直接执行关系分层与用户可读任务摘要（2026-10-12）

- 修正全目录候选报告的状态模型：已经进入不可变发布、且端口所有方跨项目的执行模板不再重复参与“原生安装配置发现”，避免把同一能力误报为模板歧义。
- 候选矩阵新增`released_direct_execution`状态，并单独记录发布ID、模板ID、两个项目和模板用途；已发布直接执行仍必须通过发布授权校验。
- 重建后，活动项目范围为：1项`released_direct_execution`、3项`ready_for_effective_graph_composition`、0项几何复核、0项模板消歧、0项端口/模板缺失、66项已知不兼容；Project06延期范围仍有48项端口/模板缺失。
- 全局候选矩阵新增按角色和项目方向聚合视图，摘要更新为`92a203dfcc98d2bb43953ba10e8b0935d56ceb4d81475d199e935d45abd5b474`。两条已发布跨项目直接执行关系分别为Project03 AH00→Project02 A600与Project03 AE00→Project01 JJ00。
- 聚合结果表明当前直接可组合能力集中在Calibration与Transport；CCD、Scanner、Gantry、GlueSupply等活动关系均已有硬不兼容证据，不应被误列为“还差少量代码”的待办。Project06缺口单独显示为延期端口建设。
- 备用槽位报告同步去除跨项目执行模板对原生profile的污染；真实结果为2项可用、0项待复核、1项不兼容、53项无备用槽位，摘要为`2fc40c507f38ed1b62eb4bea496549023981dfdd403f192a65322468d503d23d`。
- 新增通用用户摘要构建器与命令行入口。摘要从持久作业读取自然语言命令、模组实例、双方语义端口、模板与发布绑定、每包配合数量、完全约束、保存重开、输出文件和阶段耗时；现已自动挂接到通用持久作业产物刷新流程。
- 摘要门禁不会包装失败：作业必须成功、请求配合数必须全部创建、约束状态接受、求解干净、保存重开及参数复核通过，才标记`passed`；缺少任一项均为`not_passed`。
- 已为两个真实跨项目任务生成摘要：`project03-job-f18e29248c09/user-summary.md`和`project-global-job-cd04eec0deb6/user-summary.md`。两者都明确写出碰撞/B-rep为`not_evaluated`。
- 状态接口新增用户摘要JSON、Markdown路径和摘要状态；成功、失败、暂停或证据不足均会刷新摘要，且不会改变原任务结果。
- 定向回归16项通过；完整后端回归为`998 passed, 3 subtests passed`。

功能修改意义：目录报告现在能区分“已经发布并可直接执行”和“还需组合有效图的候选”，使用者也可以从一页摘要核对自然语言到真实CAD证据的完整链路，而无需阅读庞大的作业JSON。

## 8.56 活动目录直接兼容关系发布完结与发布绑定复验（2026-10-12）

- 新增通用跨项目直接安装发布器`scripts/release_cross_project_direct_installation.py`及通用证据构建函数，不再为每个模组对复制专用发布脚本。
- 对Project03 AH00→Project01 JJ00校准槽位、Project01 BD00→Project03 AA00校准槽位、Project01 SS00→Project03 AA00传输槽位完成不可变发布，分别形成v44、v45、v46目录。
- 发布证据硬检查两个可移植端口、跨项目所有权、零剩余自由度、独立非锚定插入、3/3配合、完全约束、求解干净、保存关闭重开、参数复核、源文件及会话保护和输出摘要。
- 候选矩阵改为“最新项目目录用于候选推理、全部不可变发布用于授权审计”，避免较新单关系发布遮蔽历史仍有效的跨项目授权；同一模板的多个历史发布按最新记录去重。
- 当前活动范围70个有向同角色组合已基本闭合：4个为`released_direct_execution`，66个为明确`incompatible`；待发布候选、待几何复核、待模板消歧、端口/模板缺口均为0。
- Project06的48个方向仍显式延期，不计入活动闭合；跨项目不可变直接执行模板共5条，其中A600/AH00关系不属于同角色替换矩阵，因此矩阵行显示4条。
- 新增`activeCoverageClosure`，当前状态为`basic_active_coverage_closed`，未决方向数为0；矩阵摘要为`998cbc66d153c8d55b620d23d7d9e36fa39f090cc1e2b9149fbb920729080817`。
- v45发布绑定自然语言任务`project01-job-86a04eaa623c`执行成功：3/3配合、完全约束及保存重开通过，作业约109.61秒，CAD约91.92秒；输出SHA-256为`43f78f40071ad681c4c834aa11ac05a006ae72dce7b4c502fb3d443d816251ec`。
- v46发布绑定自然语言任务`project01-job-b601e1a0748d`执行成功：3/3配合、完全约束及保存重开通过，作业约104.12秒，CAD约86.26秒；输出SHA-256为`2501a2e2d1cd8a94e42977e2139735fa96b0b4f0d7c8d505ee3ad8dd0aeebbf0`。
- v44发布绑定自然语言任务`project03-job-d18e11cad8d2`随后补齐并执行成功：3/3配合、完全约束及保存重开通过，作业约122.83秒，CAD约96.81秒；输出SHA-256为`bdc7f6f5d7f87017108bbcc7d83011184b7238ef44d92306cf55c105c7321851`。
- 复验发现英文`transport slot`曾被误识别为SolidWorks槽配合；现已区分“安装槽位名称”和“显式槽配合请求”，前者按目录端口选择，`pin in slot / slot mate`仍保留几何关系语义。
- 定向回归52项通过；完整后端回归为`1002 passed, 3 subtests passed in 73.19s`。碰撞/B-rep仍为`not_evaluated`。

功能修改意义：当前活动目录中所有已有直接兼容证据的端口/槽位均已从候选升级为自然语言可调用、发布可审计、发布绑定真实CAD可重放的关系；剩余66项不是软件漏建端口，而是现有机械证据明确不能直接替换，后续只能新增真实槽位或转接接口。

## 8.57 Project03双槽位累计装配与顺序兼容闭环（2026-10-12）

- 新增累计不可变发布`relation-v47-project03-aa00-project01-calibration-transport-driving-20261012`，同时授权Project01 `SS00`传输模组安装到Project03传输槽位、Project01 `BD00`校准模组安装到Project03校准槽位；发布复用v45、v46各自已经通过的真实CAD证据，不扩大碰撞结论。
- 两条三轮自然语言链均由同一通用编译器生成：`AA00→SS00→BD00`与`AA00→BD00→SS00`；两条链各生成2个累计CAD事务包，每包3条驱动配合。
- 真实任务`project01-job-a6148a40bdc8`按`SS00→BD00`执行成功，总耗时`222.362096 s`；真实任务`project01-job-38931a61c370`按`BD00→SS00`执行成功，总耗时`233.361233 s`。
- 两条链的第二包均以上一包保存的SLDASM为输入。四个事务包全部满足3/3配合创建、约束状态接受、求解干净、组件语义一致、源文件不变、保存关闭重开及参数复核，无case锚点和叶位姿锚点。
- 新增通用顺序兼容闭环器，检查发布摘要、授权/使用模板集合、累计输入输出链、最终文件摘要和碰撞边界；同时增加“第二包输入被篡改时必须失败关闭”的回归。
- 两种顺序的最终语义签名均为`AA00 + BD00 + SS00`，因此判定`semanticResultEquivalent=true`。两个SLDASM的SHA-256不同属于插入历史和文档序列化差异，二进制相同不是顺序兼容验收项。
- 报告：`demo/cross_project_substitution/cumulative-project03-v1/order-closure.json`和`order-closure.md`。
- 矩阵已改用Project03 v47作为最新推理目录，活动范围仍为4项已发布直接执行、66项明确不兼容、0项未决；新摘要为`e642a0d18eb42a90bee3c3f630239bf3aed843a79cac10440267346cad6cca84`。
- 定向回归11项通过；完整后端回归为`1005 passed, 3 subtests passed in 83.26s`。
- 碰撞/B-rep保持`not_evaluated`，本闭环只证明自然语言顺序、发布授权、配合定位、累计检查点和CAD生命周期。

功能修改意义：第一轮端口覆盖不再只证明“每个模组可单独安装”，而是证明两个独立跨项目槽位可以在同一新装配体中按相反顺序累计执行，并得到等价的语义装配结果。

## 8.58 自然语言装配失败原因归一化与用户级建议（2026-10-12）

- 新增`assembly_user_failure.py`薄层解释器。它不重新判断机械兼容性，只把候选矩阵、关系发布、清单编译和CAD任务已经产生的底层阻塞码归一为稳定的用户级原因。
- 首批核心原因码包括：`INSTALLATION_TOPOLOGY_INCOMPATIBLE`、`LOCATING_PATTERN_MISMATCH`、`TARGET_SLOT_NOT_REGISTERED`、`SOURCE_INSTALLATION_PORT_MISSING`、`DRIVING_RELATION_NOT_AUTHORIZED`、`DRIVING_RELATION_NOT_PUBLISHED`、`INSTALLATION_CONFIGURATION_AMBIGUOUS`和`CAD_EXECUTION_FAILED`。
- 每个解释同时返回简短说明、机械或发布原因、建议动作、修复后可重试条件、原始阻塞码和`cadLaunchDecision`；前置问题统一在CAD前失败关闭，CAD运行期问题标为`stopped_after_failure`。
- 候选矩阵的非直接执行行现在都携带`userFailureExplanation`。当前118个方向中，56项为安装拓扑不兼容、6项为定位图案尺寸不一致、4项为安装上下文不兼容；Project06延期缺口分别为24项缺自身安装端口、24项目标槽位未登记。
- 跨项目自然语言替换预览已同时返回原工程处置和新的用户解释；例如AI00→SM00仍保留178 mm孔距差证据，但可直接显示“定位图案不一致，需转接件或兼容槽位”。
- 发布关系自然语言预览会把`RELEASE_SCOPE_FORBIDS_DRIVING_RELATION`等底层门禁翻译为“关系未获驱动授权”，并给出“完成非原型CAD验证→发布→重新绑定任务”的建议。
- 全局执行清单在编译失败时返回统一解释；持久任务状态和`user-summary.md`在CAD失败时显示原因码、说明和建议，不再要求用户从异常字符串推断问题。
- 新增四类实际证据示例报告：`demo/cross_project_substitution/failure-explanations-v1/failure-explanation-demo.json`和`.md`；四个样例均在CAD前完成判定，没有启动SolidWorks。
- 最新候选矩阵摘要为`c5fd405bcc676ed9a125246651fb73b5ad9288f38e7f7ea6ac5547c1a14a3702`；状态数量保持4项已发布、66项明确不兼容、48项Project06延期缺口，解释元数据没有改变机械结论。
- 定向回归51项通过；完整后端回归为`1010 passed, 3 subtests passed in 76.02s`。
- 碰撞/B-rep继续为`not_evaluated`；前置接口或授权失败不需要先运行实体碰撞检查。

功能修改意义：系统从“能阻止错误装配”进一步提升为“能用面向使用者的语言说明为什么阻止、需要补什么以及何时可以重试”，同时保持原有机械硬门禁不被解释层放宽。

## 8.59 扫描模组第三角色有界槽位发现（2026-10-12）

本轮继续遵守“Project06 暂缓”的范围约束，仅处理 Project01、Project03 的扫描模组与其静态安装支承件。目的不是放宽既有不兼容结论，而是检查目标基座上是否存在尚未登记、但真实可用的备用安装孔系。

- Project01 `SM00` 的原生定位孔距为 `22 mm`；Project03 `AI00` 的原生定位孔距为 `200 mm`，两者原生槽位不能直接互换。
- 在 Project03 `AA00` 的扫描支承叶零件上建立了 242 个面端点。最接近 `22 mm` 的孔距为 `22.360679775 mm`，偏差 `0.360679775 mm`；该结果只属于近似几何，未通过与候选矩阵一致的 `1e-6 m` 直接兼容阈值，因此保持不兼容。
- 在 Project01 `JJ00` 的扫描支承叶零件上建立了 232 个面端点，发现 6 组精确 `200 mm` 的孔对。按“与原生扫描工位中心距离最小”排序后，选出一个由 1 个支承平面和 2 个圆柱定位面组成的候选槽位。
- 候选面端点为：
  - 支承面 `face:jj00:4d272809c45d46b4`；
  - 定位面 `face:jj00:c2da3af915900469`；
  - 定位面 `face:jj00:ec5c90215b8a0fa3`。
- 三个端点已在 SolidWorks 中完成只读恢复，`3/3` 成功，均使用 `BodyFaceIndex`，总耗时 `6.090315 s`。
- 候选槽位中心与 Project01 原生 `SM00` 扫描工位中心相距约 `349.716 mm`。因此“孔距完全匹配”只证明机械定位候选存在，不能证明扫描光轴、工作距离和条码目标区满足工艺要求。
- 当前没有创建配合、没有另存装配体、没有发布语义端口，也没有执行碰撞/B-rep。候选状态为“端点已恢复，等待非原型初始位姿三配合验证与光学工艺复核”。
- Project06 未参与扫描、推理或报告统计。

主要证据：

- `demo/cross_project_substitution/scanner-slot-discovery-v1/build_summary.json`；
- `demo/cross_project_substitution/scanner-slot-discovery-v1/project03_AA00_project01_SM00/scanner_slot_discovery.json`；
- `demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/scanner_slot_discovery.json`；
- `demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/endpoint_recovery_evidence.json`。

本次修改的意义：证明硬不兼容的原生槽位之外，可以通过有界、只读的静态支承件扫描发现备用槽位，而且发现容差不会被错误地当作直接安装容差；同时将“机械孔系匹配”和“扫描功能可用”明确分成两个门槛。

## 8.60 扫描候选工艺预检与CAD前失败关闭（2026-10-12）

在备用孔系端点恢复后，新增`cross-project-scanner-process-preflight/v1`。预检消费槽位发现报告、端点恢复证据和全局目录，分别检查：

- 严格机械孔距是否命中；
- 选定的支承面及定位面是否稳定恢复；
- 来源扫描模组是否登记扫描原点和有方向的光轴；
- 是否登记权威最小/最大工作距离；
- 目标项目的传输模组是否登记条码目标点；
- 后续是否已经求出候选安装位姿、光轴—目标交点及实际距离。

本轮Project03 `AI00`安装到Project01备用孔系的结果为`blocked_before_cad_missing_functional_semantics`：机械候选和`3/3`端点恢复已通过，但目录中尚无`AI00`扫描光轴、工作距离范围和Project01 `SS00`条码目标点。因此预检明确返回`cadInsertionAllowed=false`、`semanticPortPublished=false`，没有启动SolidWorks配合重建。

证据位于：

- `demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/scanner_process_preflight.json`；
- `demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/scanner_process_preflight.md`。

定向预检测试4项通过；连同槽位发现相关测试共20项通过。完整后端回归为`1019 passed, 3 subtests passed`。

本次修改的意义：系统不会为了生成可见装配体而跳过扫码功能证据；即使安装孔完全匹配，也会在光轴、工作距离或条码目标缺失时于CAD前停止，并给出下一步应采集的确切数据。

## 8.61 基座—传输—扫描—功能模组自然语言累计装配链（2026-10-12）

为避免等待跨项目Scanner备用槽位的光学语义补齐，首条完整机械演示链采用Project03原生扫描安装端口，并保留跨项目传输与校准：

```text
Project03 AA00基座
→ Project01 SS00传输模组
→ Project03 AI00扫描模组
→ Project01 BD00校准模组
```

完成内容：

- 新发布`relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012`，在同一不可变授权集合中包含SS00跨项目传输安装、AI00原生扫描安装和BD00跨项目校准安装；
- 四条自然语言在`0.194021 s`内编译为三包持久CAD任务，执行顺序为`SS00→AI00→BD00`；
- AI00原型五关系语义被正确区分：支承面＋两定位孔形成3条驱动配合，两个距离关系保持只读验证，避免过约束；
- 真实CAD任务`project-global-job-163f19364c24`一次完成三包，第二、第三包严格消费上一包检查点；
- 每包均为3/3驱动配合创建成功、目标完全约束、求解干净、保存关闭重开和参数复核通过；
- 单包耗时分别为`144.483388 s`、`241.382240 s`、`143.332913 s`，累计执行耗时`529.505085 s`；首包命中基座包装缓存，估计避免重复准备`526.578993 s`；
- 最终装配体为`demo/global_assembly_contexts/manifest_jobs/project-global-job-163f19364c24/packet-runs/packet-003-attempt-01/cross-project-p03-ss00-ai00-bd00-v1-packet-003.SLDASM`；
- 新增机械演示链闭合报告，机械累计装配判定通过，但`AI00→SS00`跨项目扫码光轴/目标/工作距离仍标记为待验证，未宣称完整功能工艺通过；
- Project06未引入，碰撞/B-rep保持`not_evaluated`。
- 定向回归20项通过；完整后端回归`1024 passed, 3 subtests passed`。

主要证据：

- `demo/cross_project_substitution/cumulative-project03-v2/release-spec.json`；
- `demo/global_assembly_catalog/releases/relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012/release-manifest.json`；
- `demo/global_assembly_contexts/cross-project-p03-ss00-ai00-bd00-v1.natural-language-compilation.json`；
- `demo/global_assembly_contexts/manifest_jobs/project-global-job-163f19364c24/job.json`；
- `demo/cross_project_substitution/cumulative-project03-v2/complete-demo-chain-closure.json`。

本次修改的意义：主线首次形成由自然语言驱动的“基座＋传输＋扫描＋功能模组”真实累计SolidWorks装配链；剩余缺口已经从机械装配执行缩小为扫描器与跨项目传输目标之间的功能语义验证。

## 8.62 AI00—SS00动态条码通道只读验证（2026-10-12）

在不重复运行四模组CAD长链的前提下，新增`cross_project_scanner_transport_process_validation.py`，复用Project03 `AI00`原型中的100 mm CAD光束和Project01产品扫描器留下的条码通道代理，统一换算到已生成装配体的SS00安装坐标系。

验证不把载具条码误当成固定世界点，而是按机械工艺拆成：

- `U`：载具可沿传输方向运动，使用AI00当前扫描站坐标；
- `V`：条码通道横向坐标，来自Project01产品扫码原型；
- `normal`：条码通道高度，来自Project01产品扫码原型；
- 扫描站还必须落在SS00整模组AABB给出的保守纵向包络内。

实测结果：

- AI00扫描站在SS00保守纵向区间`[-67.190, 1337.190] mm`内；
- 光轴到动态条码通道的横向误差为`0.402 mm`，低于当前粗布局容差`5 mm`；
- 从AI00出光代理到条码通道所需距离为`79.500 mm`；
- AI00现有CAD名义光束为`100.000 mm`，其端点与条码通道相差`20.504 mm`；
- KEYENCE官方SR-X100规格给出的读取距离为`70–1000 mm`，79.500 mm落在该范围内；
- 状态升级为`static_demo_passed_barcode_surface_proxy`，四角色闭合报告为`complete_demo_chain_passed`，静态功能Demo通过；
- 条码仍为原型扫描光束端点代理，码尺寸、视野、真实面和现场触发未验证，因此`productionReady=false`；
- Project06未引入，碰撞/B-rep未执行。
- 定向回归12项通过；完整后端回归`1031 passed, 3 subtests passed in 81.22s`。

证据：

- `demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.json`；
- `demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.md`；
- `demo/cross_project_substitution/cumulative-project03-v2/complete-demo-chain-closure.json`。

本次修改的意义：扫码功能已在静态Demo层闭合，证明当前机械组合在方向、横向通道、传输纵向范围和型号读取距离上没有明显冲突；剩余工作明确限定为真实条码面、码尺寸、视野和现场触发等工程确认，不再阻塞自然语言完整演示链。
