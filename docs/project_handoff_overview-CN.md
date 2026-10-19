# SolidWorks MCP 项目技术交接总览

> 更新时间：2026-10-12
> 面向对象：后续继续开发本项目的工程师
> 当前主线：**自然语言驱动的模组级灵活组合装配**
> 当前验收边界：**装配 Demo 可生成、配合可验证、结果可保存重开；碰撞/B-rep 与生产放行暂不作为主线硬门禁**

---

## 1. 一句话说明项目目标

用户用受控自然语言描述“先安装基座，再安装传输、扫描、校准等模组”，系统从跨项目模组目录中选择具体子装配体及其语义端口，编译为可解释的配合关系图和 CAD 事务，最终在 SolidWorks 中累计生成、保存并重新打开一版独立装配体，同时保留完整机器可读证据。

目标不是简单复制某个原型顶层位姿，也不是让任意两个不兼容模组强行组合；目标是：

1. 在机械上有意义的模组角色和槽位之间实现跨项目替换；
2. 用稳定的面、边、轴等端点恢复真实 SolidWorks 配合；
3. 对每一步给出来源、端口、模板、自由度、执行状态和耗时；
4. 将不确定项显式标为代理、估计或待验证，不静默包装成生产可用结果。

---

## 2. 当前主技术路线

```text
受控自然语言需求
        ↓
模组身份、角色与别名解析
        ↓
全局模组目录检索
        ↓
语义端口与槽位兼容匹配
        ↓
配合关系模板 / 配合图
        ↓
不可变关系发布版本授权
        ↓
CAD 事务清单与分步工作包
        ↓
SolidWorks 增量插入、配合、求解
        ↓
保存 → 关闭 → 重开 → 参数复测
        ↓
检查点、耗时、哈希与闭环证据
```

### 2.1 为什么需要“语义端口”

模组角色只能说明“它是什么”，不能说明“应该用哪个面、孔、轴或基准与谁连接”。语义端口把机械意图和真实 CAD 几何连接起来，典型内容包括：

- 端口用途：外部安装、工艺观察、距离验证等；
- 端点角色：安装面、定位孔轴、侧向基准、光轴、条码目标区；
- 稳定几何定位信息：组件路径、实体/面索引、几何签名、方向等；
- 所属模组、接口类别、可连接槽位；
- 证据来源与置信度。

### 2.2 为什么需要“关系模板”

一个机械连接通常不是单一配合，而是一束配合，例如：

```text
安装面重合 + 定位孔同心 + 侧面平行
```

关系模板记录双方端口、配合束、方向、尺寸、预期剩余自由度，以及该模板是否已取得 CAD 证据。自然语言编译器只允许使用当前发布版本授权的模板。

### 2.3 为什么采用增量累计装配

每增加一个模组都产生一个新检查点，而不是一次性生成整机。这样可以：

- 清楚定位失败发生在哪一步；
- 暂停、恢复或从最后成功检查点继续；
- 避免长链失败后从零开始；
- 将每个模组的配合、耗时和验证结果单独保存。

---

## 3. 系统架构与代码入口

### 3.1 数据与证据层

| 内容 | 主要位置 | 作用 |
|---|---|---|
| 项目配置 | `apps/demo-backend/src/demo_backend/project_profiles/*.json` | 项目原型、模组编号、CAD 路径和基础参数 |
| 项目参数包 | `demo/project*_parameter_package.json` | 原型测量、估计参数及其来源 |
| 面端点目录 | `demo/semantic_ports/**/face_endpoint_catalog.json` | 稳定恢复具体面、轴、边等 CAD 端点 |
| 语义端口证据 | `demo/semantic_ports/**` | 模组端口定义、捕获和验证结果 |
| 全局目录发布 | `demo/global_assembly_catalog/releases/**` | 模组、端口、关系模板及发布证据 |
| 任务与运行证据 | `demo/global_assembly_contexts/**` | 上下文、清单任务、CAD 工作包、检查点和结果 |

### 3.2 后端核心模块

| 模块 | 作用 |
|---|---|
| `global_module_catalog.py` | 跨项目模组身份、角色、别名和端口目录 |
| `global_relation_semantics.py` | 端口兼容、关系语义和配合模板 |
| `global_assembly_workbench.py` | 自然语言上下文、预览、应用与修订 |
| `global_natural_language_manifest.py` | 将受控自然语言编译为装配清单 |
| `global_assembly_compiler.py` | 将实例图和关系图编译为可执行计划 |
| `global_cad_transaction_packets.py` | 生成逐步 CAD 工作包 |
| `global_relation_catalog_release.py` | 不可变关系发布与授权 |
| `global_cad_manifest_orchestrator.py` | 持久任务、检查点、暂停和恢复 |
| `global_cad_packet_executor.py` | 执行单个 SolidWorks 工作包并记录证据 |
| `face_endpoint_catalog.py` | 面端点登记、查询与恢复 |
| `mate_graph_edit.py` | 配合图新增、修改、删除等研究功能 |

### 3.3 SolidWorks 执行层

主要代码位于：

- `vendor/solidworks-mcp/app/SolidWorksMcpApp`
- `vendor/solidworks-mcp/bridge/SolidWorksBridge`

该层负责真实 SolidWorks 操作：打开文档、插入子装配体、恢复端点、创建配合、重建求解、保存、关闭、重开和读取验证参数。

### 3.4 前端与 API

前端：`apps/demo-frontend`
后端：`apps/demo-backend`

常用 API 包括：

- `/api/demo/global-module-catalog`
- `/api/demo/global-module-catalog/search`
- `/api/demo/global-module-port-coverage`
- `/api/demo/global-relation-capabilities`
- `/api/demo/global-relation-intents/preview`
- `/api/demo/global-assembly-contexts`
- `/api/demo/global-cad-manifest-jobs`
- `/api/demo/global-cad-manifest-jobs/compile-natural-language`

前端目前是辅助展示层，不是主线开发重点；鼠标点选面、自动猜面和完整任务状态 UI 均可后续产品化。

---

## 4. 当前已经完成的能力

### 4.1 自然语言到真实 CAD 的主链已走通

已经完成第一条包含四种角色、跨两个项目的自然语言累计装配链：

```text
Project03 AA00 基座
  → Project01 SS00 传输模组
  → Project03 AI00 扫描模组
  → Project01 BD00 校准模组
```

对应自然语言要求：

1. `Add Project03 AA00 as the base module.`
2. `Install Project01 SS00 transport module onto the Project03 AA00 transport slot.`
3. `Install Project03 AI00 scanner module onto the Project03 AA00 scanner slot.`
4. `Install Project01 BD00 calibration module onto the Project03 AA00 calibration slot.`

结果：

- 自然语言编译耗时：`0.194021 s`；
- 生成 3 个 CAD 工作包；
- 3 个工作包全部成功；
- 每包均创建 `3/3` 个驱动配合；
- 新增模组均达到完全约束；
- 每步均完成保存、关闭、重开和参数复测；
- CAD 累计执行耗时：`529.505085 s`。

发布版本：

```text
relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012
```

任务 ID：

```text
project-global-job-163f19364c24
```

最终装配体：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-163f19364c24\packet-runs\packet-003-attempt-01\cross-project-p03-ss00-ai00-bd00-v1-packet-003.SLDASM
```

SHA256：

```text
85560701FF1180BC4AD3705FE2B7F9C31EA57D71CDD9C93A3BE0C5918A9C7FF7
```

闭环证据：

- `demo/cross_project_substitution/cumulative-project03-v2/complete-demo-chain-closure.json`
- `demo/cross_project_substitution/cumulative-project03-v2/complete-demo-chain-closure.md`

### 4.2 扫描工艺静态代理验证已接入

AI00 扫描模组与 SS00 传输模组已进行只读工艺验证：

- 扫描站位于 SS00 保守输送包络内；
- 横向误差约 `0.402 mm`；
- 所需工作距离约 `79.5 mm`；
- KEYENCE SR-X100 官方读取距离为 `70–1000 mm`，静态 Demo 范围内通过。

状态：

```text
static_demo_passed_barcode_surface_proxy
```

边界：条码位置目前仍采用原型光束端点代理，真实条码面、码尺寸、视野和现场触发尚未验证，因此 `productionReady=false`。

证据：

- `demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.json`
- `demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.md`

### 4.3 全局模组目录与端口覆盖

当前 v48 全局目录：

- 已载入项目：Project01、02、03、05、06；
- 模组定义：`43`；
- 自然语言可检索：`43`；
- 语义端口：`76`；
- 可移植端口：`76`；
- 关系模板：`45`；
- 兼容关系：`71`。

覆盖矩阵：

- 语义图就绪模组：`34`；
- CAD 端点就绪模组：`34`；
- 阻塞模组：`9`；
- 连接对：`61`；
- CAD 端点就绪连接对：`59`。

九个模组级缺口全部来自已明确暂缓的 Project06。换言之，当前活跃范围 Project01/02/03/05 在“模组至少有一个可用端口”层面为 `34/34`，但这不代表任意两模组可以两两连接。

覆盖证据：

- `demo/global_assembly_catalog/releases/relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012/global_module_catalog.json`
- `demo/global_assembly_catalog/v1/global_module_port_coverage_matrix.json`

### 4.4 持久任务和证据体系

已具备：

- 分包自动连续执行；
- 检查点持久化；
- 暂停和恢复；
- 失败原因与最后成功步骤保留；
- 运行时长记录；
- 结果文件哈希；
- 配合数量、求解状态、重开状态和参数复测证据。

### 4.5 多项目基础验证

| 项目 | 当前能力摘要 |
|---|---|
| Project01 | 已识别主要模组、工作位与端口；验证过 GN00–SS00 非星形关系；SS00、BD00 已用于跨项目链 |
| Project02 | 当前最完整的原生长链；覆盖 A600、A800、A180、A700、A300、A500、A100、A200、T401 等；已有非原型初始位姿试验 |
| Project03 | AA00 基座及 AE00/AD00/AI00/AH00/AG00/AJ00/AB00 等端口已建立；AA00、AI00 已用于当前跨项目 Demo |
| Project05 | 八类主要模组与可移植端口已建立；完成多顺序与跨项目证据积累 |
| Project06 | 仅完成身份和角色登记，九个模组尚无语义端口；按当前范围暂缓 |

### 4.6 回归状态

最近一次后端完整回归：

```text
1031 passed, 3 subtests passed in 81.22s
```

与完整 Demo 链相关的定向回归：`12 passed`。

---

## 5. 尚未完成和能力边界

### 5.1 当前自然语言是“受控自然语言”

系统已能识别项目、模组、角色、顺序和目标槽位，但不是任意开放对话。未登记别名、表达歧义或缺少兼容模板时应明确拒绝，而不是猜测执行。

### 5.2 不是所有模组可以自由两两组合

可执行连接至少需要：

1. 双方模组已登记；
2. 双方存在对应语义端口；
3. 端口接口类别兼容；
4. 有明确配合模板；
5. 模板在当前不可变发布版本中获授权；
6. 相关 CAD 文件可访问。

当前方向是覆盖机械上常见的“同角色跨项目替换”，而不是建立无意义的全连接图。

### 5.3 碰撞和 B-rep 暂未作为主线硬门禁

当前完整 Demo 闭环的碰撞状态为：

```text
not_evaluated
```

这意味着装配关系和静态工艺代理已通过，但不能宣称装配体无实体干涉。碰撞、AABB 和条件 B-rep 保留为独立的后验工程验证能力，除非需求重新排序，否则不要让它阻塞当前自然语言装配主线。

### 5.4 生产放行尚未完成

尚缺：

- 厂商权威安装基准和公差；
- 真实条码面、码尺寸、视场及触发验证；
- 动态全行程验证；
- 维护空间、线缆/气管空间和可达性；
- 完整碰撞和工艺节拍验证。

因此当前成果应描述为“可解释、具有真实 CAD 证据的装配 Demo”，不应称为生产方案。

### 5.5 拓扑变化会影响端点恢复

面端点目录使用组件路径、实体/面索引和几何签名恢复目标端点。若源零件发生分割、合并、倒角或重建顺序变化，面索引可能改变，必须重新捕获或用更强几何签名匹配。

### 5.6 外部 CAD 路径依赖

大量源 CAD 位于：

```text
D:\zengshuang\workspace\cuhksz\cad_data\...
```

新机器若没有相同文件和路径，需要复制 CAD 数据并增加路径重映射；仅克隆 Git 仓库不能保证真实 CAD 执行成功。

---

## 6. 相关但非当前主线的技术分支

### 6.1 约束求解布局生成

目标是根据空间、工艺和包络约束求解模组位姿，并通过预览和 Replay 生成方案。Project01/02/03/05 已积累原型测量、求解、预览和 Replay 能力，但仍有较强的原型标定参数依赖。

权威文档：`docs/layout_constraints_and_solver_principles-CN.md`

该分支与当前“通过端口和配合自由组合”不同，不要混为同一求解器。

### 6.2 可编辑配合图与原型重建

已研究：

- 导出模组层级配合关系；
- 稳定登记配合面端点；
- 新增、修改、删除配合；
- 在小装配中重建；
- 分析剩余自由度、过约束和柔性子装配影响。

整机纯配合重建仍受残余自由度、原型初始位姿、柔性子装配和历史异常组件影响，尚未成为当前主线执行器。

### 6.3 需求到模组检索和前端

该分支适合由另一位同学独立继续，范围和接口已写在：

`docs/requirement_module_retrieval_frontend_handoff-CN.md`

该分支应消费全局模组目录和搜索 API，不应直接修改底层布局或 CAD 配合执行逻辑。

---

## 7. 推荐的后续开发顺序

### P0：先完成安全交接

1. 对当前工作区创建完整快照；
2. 审核并提交代码、测试、小型 JSON/Markdown 证据；
3. 大型 `.SLDASM/.SLDPRT` 和生成缓存决定单独归档或提供共享路径；
4. 记录 CAD 数据根目录和 SolidWorks 环境；
5. 在另一目录执行一次从克隆到测试的复现。

原因：当前 Git 工作区有大量未提交、未跟踪文件。现有分支和提交不能代表最新能力，不能直接把一个旧提交链接当作完整交付物。

### P1：扩展自然语言完整演示链

优先增加：

- 同一四角色链的中文命令；
- 不同输入顺序下的依赖排序；
- 重复添加、容量超限、槽位歧义和缺少模板的明确错误；
- 编译预览与实际执行结果的一致性验证。

若发布版本、几何和模板未变化，应优先复用已有 CAD 证据，不要无意义重复跑长时间 SolidWorks。

### P2：继续补机械上有意义的跨项目替换

按角色逐个验证，而不是全量两两组合：

1. Transport；
2. Scanner；
3. Calibration；
4. Cleaning/Weighing；
5. CCD；
6. Gantry / Glue Supply。

每新增一对关系，应完成：端口定义、模板、自由度预检、非原型初始位姿试验、真实 CAD 保存重开和发布证据。

### P3：完善真实工艺端口

首先把 SS00 的真实条码面、条码尺寸、视场和触发位置登记为正式工艺端口，替换当前光束端点代理。

### P4：按需求重新启用工程精检

只有需求明确要求时，再将以下项目升级为硬门禁：

- AABB 快检；
- 条件 B-rep；
- 动态全行程；
- 维护空间；
- Project06 端口覆盖；
- 生产参数签认。

---

## 8. 运行和复现入口

### 8.1 启动后端

```powershell
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

或：

```powershell
scripts\start_demo_backend.cmd
```

API 文档：`http://127.0.0.1:8000/docs`

### 8.2 启动前端

```powershell
cd apps\demo-frontend
npm.cmd run dev
```

前端地址：`http://127.0.0.1:5173/`

注意：本机 PowerShell 执行策略可能阻止 `npm.ps1`，应使用 `npm.cmd`。

### 8.3 运行测试

```powershell
$env:PYTHONPATH='apps/demo-backend/src'
python -m pytest apps/demo-backend/tests -q
```

前端构建：

```powershell
npm.cmd --prefix apps/demo-frontend run build
```

C# 构建：

```powershell
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

### 8.4 快速演示脚本

```powershell
python scripts\run_global_natural_language_assembly_demo.py
```

该脚本默认演示 Project02 的 A600 → A800 → A180 图级流程，支持 `--context-id`、`--commands`、`--reset`。它默认不启动 SolidWorks，也不执行碰撞检查，不能等同于真实 CAD 闭环。

最新四角色真实 CAD 链已经完成，闭环结果应直接读取：

```text
demo/cross_project_substitution/cumulative-project03-v2/complete-demo-chain-closure.json
```

以下两个脚本只基于已有证据生成闭环摘要，不会重跑 CAD：

- `scripts/build_cross_project_scanner_transport_process_validation.py`
- `scripts/build_natural_language_complete_demo_chain_closure.py`

---

## 9. SolidWorks 环境注意事项

1. 推荐保持一个干净 SolidWorks 会话，不要并行打开多个大型装配体；
2. 网络许可证、`.NET Framework`、SOLIDWORKS CAM/SQLite 插件曾造成启动异常；
3. 长装配和保存重开可能持续数分钟，不要因界面短暂卡顿立刻强杀；
4. 若确需结束进程，先保存证据并确认没有用户未保存文件；
5. 不应自动重启 Windows；
6. SolidWorks 2024 和对应 MCP Bridge 版本应一起记录；
7. 真实 CAD 长链执行前，先跑 Python 回归和事务预检。

---

## 10. Git 与交接风险

当前检查结果：

```text
branch: codex/requirement-module-retrieval-handoff
HEAD:   041f281 Add requirement-to-module demo and developer handoff
origin: https://github.com/palette233/solidworks_mcp.git
```

但是当前工作树包含大量未提交和未跟踪的后续开发文件，尤其是全局目录、自然语言编译、持久编排、跨项目端口和 CAD 证据相关代码。因此：

- **不要执行 `git reset --hard` 或 `git clean`；**
- **不要假设 `041f281` 就是当前版本；**
- 交接前必须建立新检查点提交或完整工作区归档；
- 检查 `.gitignore`，确认关键 JSON/Markdown 证据是否会被遗漏；
- 大型 CAD 文件若不进入 Git，需另附共享位置和哈希清单。

---

## 11. 新同学第一天建议阅读顺序

1. `docs/development_execution_rules-CN.md` —— 当前执行规则和验收边界，优先级最高；
2. 本文 `docs/project_handoff_overview-CN.md` —— 全局交接入口；
3. `docs/global_module_semantic_ports-CN.md` —— 全局模组、端口、模板和累计装配主线；
4. `docs/to_be_continued-CN.md` —— 最近恢复点；
5. `docs/log.md` —— 按时间查看功能变更；
6. `docs/natural_language_cad_assembly_pipeline-CN.md` —— 历史完整路线，但若与执行规则冲突，以执行规则为准；
7. 按负责分支阅读专项交接文档。

---

## 12. 交接验收清单

### 代码和环境

- [ ] 新同学能拉取包含最新代码的提交或快照；
- [ ] CAD 数据路径可访问或已完成重映射；
- [ ] Python 后端测试通过；
- [ ] 前端可构建；
- [ ] C# Bridge 可构建；
- [ ] SolidWorks 与许可证可稳定启动。

### 数据和证据

- [ ] 能读取 v48 全局目录；
- [ ] 能读取覆盖矩阵；
- [ ] 能读取最新完整 Demo 闭环 JSON；
- [ ] 能找到最终四角色装配体；
- [ ] 理解 `static_demo_proxy`、`productionReady=false` 和 `collisionStatus=not_evaluated` 的含义。

### 功能理解

- [ ] 能用自然语言编译一个装配上下文；
- [ ] 能解释模组角色、语义端口、关系模板和发布版本之间的关系；
- [ ] 能区分图级预览与真实 CAD 执行；
- [ ] 能从最后检查点恢复任务；
- [ ] 知道何时拒绝执行缺少端口或模板的组合。

---

## 13. 当前最准确的项目结论

项目已经越过“只能识别模组或复刻单一原型”的阶段，形成了从受控自然语言、跨项目模组检索、语义端口匹配、关系图编译，到真实 SolidWorks 累计装配和证据闭环的完整骨架，并完成一条跨项目四角色真实 CAD 链。

当前主要差距不是再造底层架构，而是：

1. 扩充机械上有意义的端口和跨项目关系覆盖；
2. 提高中文自然语言及异常输入的鲁棒性；
3. 将工艺代理端口逐步替换为真实工程端口；
4. 做好版本、数据路径和未提交工作区的正式交付；
5. 在需求重新要求时，再将碰撞、动态和生产参数升级为硬门禁。
