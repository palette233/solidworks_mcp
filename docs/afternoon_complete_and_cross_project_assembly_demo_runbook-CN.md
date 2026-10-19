# 下午演示手册：完整累计装配与跨项目累计装配

> 更新时间：2026-10-14
> 适用页面：`http://127.0.0.1:5173/#global-assembly-workbench`
> 推荐演示时长：12～18分钟
> 推荐方式：前端展示语义过程，SolidWorks打开既有实体检查点，PowerShell展示机器可读证据。

> 彩排状态：2026-10-14已按本文流程完成一轮实机彩排。完整链在前端恢复为`8个模组 / 7个事务包 / 7/7 succeeded`，跨项目链恢复为`4个模组 / 3个事务包 / 3/3 succeeded`；两个最终装配体文件均存在。彩排中发现并修复了“通用清单任务成功后未自动回写装配会话”的问题。

---

## 1. 本次演示要证明什么

本次建议演示两条已经完成真实CAD闭环的链路。

### 1.1 完整累计装配链

```text
Project05 A000固定环境
  → D000产品传输
  → F000条码扫描
  → M000产品定位CCD
  → G000校准/称重
  → N000针头清洁
  → P000双杯排胶
  → B000龙门及双阀运动组
```

证明：

- 自然语言需求可以逐轮形成8模组装配上下文；
- 7个新增模组按7个CAD事务包累计加入同一装配体；
- 每包从非原型初始位姿开始，不复制原型顶层位姿；
- 每包创建真实SolidWorks配合，并执行保存、关闭、重开和复核；
- 后一包严格以前一包的实体检查点为输入。

### 1.2 较短跨项目累计装配链

```text
Project03 AA00固定环境
  → Project01 BD00校准模组
  → Project01 SS00传输模组
  → Project03 AI00扫描模组
```

证明：

- 系统不是只能复刻一个项目原型；
- 不同项目的子装配体可以通过已发布语义端口和配合模板进入同一装配体；
- 三个新增模组按独立检查点累计执行；
- 模组来源、接口、配合模板和结果装配体均可追溯。

### 1.3 本轮不宣称的内容

演示时应主动说明：

- 碰撞、全量B-rep和动态工艺不属于本轮累计装配验收；
- 完整链的扫描光轴、条码目标区和实际工作距离仍待专项验证；
- 当前证明的是“机械累计装配闭环”，不是生产放行；
- 不是所有模组都可以任意两两连接，只能使用已经登记且兼容的语义端口。

---

## 2. 推荐演示节奏

| 时间 | 内容 | 主要界面 |
|---:|---|---|
| 1分钟 | 说明技术路线和演示边界 | PPT或口头说明 |
| 4～6分钟 | 完整8模组累计装配 | 前端＋PowerShell＋SolidWorks |
| 4～5分钟 | 跨项目4模组累计装配 | 前端＋PowerShell＋SolidWorks |
| 2分钟 | 展示检查点、配合与审计证据 | SolidWorks＋JSON报告 |
| 1分钟 | 总结当前能力和后续工作 | PPT或口头说明 |

会议现场不建议重新执行完整CAD长链：完整链历史实测约`874.467 s`，跨项目短链约`335.831 s`。已有结果与证据足以完成演示。

---

## 3. 演示前准备

### 3.1 SolidWorks

- [ ] 关闭无关零件和大型原型装配体；
- [ ] 保留一个干净的SolidWorks 2024会话；
- [ ] 确认没有许可证、`.NET Framework`或CAM数据库提示；
- [ ] 不在会议前启动干涉检查或大型强制重建；
- [ ] 将本手册第6、7节中的两个最终装配体路径复制到记事本备用。

### 3.2 启动后端

第一个PowerShell窗口：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
.\scripts\start_demo_backend.cmd
```

浏览器检查：

```text
http://127.0.0.1:8000/api/health
```

预期返回`status = ok`。

### 3.3 启动前端

第二个PowerShell窗口：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm.cmd run dev -- --host 127.0.0.1
```

注意使用`npm.cmd`，不要使用可能被PowerShell执行策略拦截的`npm.ps1`。

打开：

```text
http://127.0.0.1:5173/#global-assembly-workbench
```

### 3.4 建议提前打开的材料

1. 本演示手册；
2. 前端“自然语言增量装配上下文”页面；
3. 一个PowerShell证据查询窗口；
4. 完整累计链最终装配体；
5. 跨项目链最终装配体。

---

## 4. 开场说明话术

建议用以下文字开始：

> 当前系统把自然语言需求转换为模组实例、语义端口和配合图，再编译为可恢复的CAD事务。每次新增模组都会产生独立实体检查点，下一步从上一检查点继续。今天不现场等待十几分钟重新跑完整长链，而是展示已经完成的自然语言上下文、逐包SolidWorks结果和机器可读证据。

技术路线可以简化为：

```text
自然语言需求
  → 候选模组与人工确认
  → 语义端口匹配
  → 配合图和自由度检查
  → CAD事务包
  → SolidWorks真实配合
  → 保存、关闭、重开
  → 下一模组继续累计
```

---

## 5. Case A：在前端展示完整累计装配上下文

### 5.1 加载已验证上下文

在“当前装配会话”的“会话名称”输入：

```text
project05-complete-seven-addon-v2
```

点击：

```text
继续已有会话
```

预期看到：

- 修订号为8；
- 上下文包含8个模组；
- 8轮自然语言要求；
- A000为固定安装环境；
- D000、F000、M000、G000、N000、P000、B000依次进入语义装配图。

### 5.2 展示重点

指出页面中的以下内容：

1. 工程需求不是直接变成一个坐标，而是先解析为模组和关系；
2. 每个连接都绑定双方语义端口；
3. 默认定位模式是“语义端口＋配合图独立装配”；
4. 原型位姿依赖是显式兜底模式，不是默认模式；
5. 碰撞状态保持“未评估”，不会被错误表述为已经无干涉。

### 5.3 可展示的8轮需求

已保存上下文中的需求依次为：

```text
请建立项目05的设备机架，作为后续模组的固定安装环境。
在当前机架上安装项目05的产品传输模组。
继续安装项目05的双读头条码扫描模组。
继续安装项目05的产品定位CCD模组。
继续安装项目05的喷嘴校准与称重组合模组。
继续安装项目05的自动针头清洁模组。
继续安装项目05的双杯排胶模组。
最后安装项目05的龙门与双阀Z轴运动组。
```

说明：这些是本轮用于唯一消歧和复现实验的受控命令。面向最终使用者时，项目号和内部编号应主要由候选推荐与人工确认承担，而不是要求工程师记忆。

---

## 6. Case B：展示完整累计装配的真实CAD结果

### 6.1 先展示CAD前预检

在仓库根目录执行：

```powershell
python .\scripts\audit_project05_complete_cumulative_chain.py
```

重点解释以下结果：

```text
status = passed
packetCount = 7
actualModuleOrder = D000, F000, M000, G000, N000, P000, B000
casePoseAnchorCount = 0
targetLeafPoseAnchorCount = 0
collisionStatus = not_evaluated
```

这一步证明：昂贵CAD执行前，系统已经检查7个包均未使用原型顶层位姿、案例位姿锚点或叶级位姿锚点。

预检报告：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\project05-complete-seven-addon-v2.preflight-audit.json
```

### 6.2 查询已完成任务

PowerShell执行：

```powershell
$j = Get-Content `
  ".\demo\global_assembly_contexts\manifest_jobs\project05-job-72463661a6a2\job.json" `
  -Raw | ConvertFrom-Json

$j | Select-Object jobId,status,executionDurationSeconds,assemblyStatus,collisionStatus

$j.steps | Select-Object `
  stepId,moduleToken,status,attemptCount,
  @{Name="durationSeconds";Expression={$_.attempts[0].durationSeconds}},
  @{Name="assemblyPath";Expression={$_.checkpoint.assemblyPath}}
```

预期：

```text
status = succeeded
7/7步骤成功
D000 → F000 → M000 → G000 → N000 → P000 → B000
executionDurationSeconds ≈ 874.467
collisionStatus = not_evaluated
```

### 6.3 在SolidWorks查看逐步累计效果

为了在会议中快速体现“逐个加入”，建议依次打开三个代表性检查点，而不是现场重新执行：

#### 检查点1：基座＋传输

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project05-job-72463661a6a2\packet-runs\packet-001-attempt-01\project05-complete-seven-addon-v2-packet-001.SLDASM
```

#### 检查点3：再加入扫描和CCD

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project05-job-72463661a6a2\packet-runs\packet-003-attempt-01\project05-complete-seven-addon-v2-packet-003.SLDASM
```

#### 检查点7：完整8模组

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project05-job-72463661a6a2\packet-runs\packet-007-attempt-01\project05-complete-seven-addon-v2-packet-007.SLDASM
```

在每个装配体中：

1. 等待完全加载；
2. 按`F`缩放至窗口；
3. 切换等轴测；
4. 展开FeatureManager设计树，指出新增的顶层子装配体；
5. 展开“配合”文件夹，指出当前包建立的真实配合；
6. 强调这三个文件是同一累计链的不可变检查点，不是三次独立拼装。

### 6.4 完整链的验证结果

| 新增模组 | 实际配合结果 | 初始位姿 |
|---|---:|---|
| D000传输 | 3/3 | 非原型确定性位置 |
| F000扫描 | 3/3 | 非原型确定性位置 |
| M000 CCD | 3/3 | 非原型确定性位置 |
| G000校准/称重 | 4/4 | 非原型确定性位置 |
| N000清洁 | 4/4 | 非原型确定性位置 |
| P000排胶杯 | 4/4 | 非原型确定性位置 |
| B000龙门 | 3/3 | 非原型确定性位置 |

机械闭合报告：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\project05-complete-seven-addon-v2\complete-demo-chain-closure.json
```

准确结论：

> 完整累计机械装配链已通过；原型顶层位姿未被用于新增模组定位。机械接口、配合端点和部分尺寸仍来源于原型标定，因此属于“去原型位姿、未去原型机械标定”。

---

## 7. Case C：前端展示跨项目短链

### 7.1 一键加载真实CAD案例

在前端“真实CAD验证案例”区域点击：

```text
跨项目三步累计链
```

如果按钮不可见，也可以在“会话名称”输入：

```text
cross-project-aa00-bd00-ss00-ai00-portable-v1
```

然后点击“继续已有会话”。

预期看到：

- 修订4；
- 4轮自然语言命令；
- 4个顶层模组；
- 最近CAD任务为`project-global-job-f0aa2d732403`；
- 三个事务步骤均已成功。

### 7.2 解释跨项目来源

| 角色 | 模组 | 来源 |
|---|---|---|
| 固定环境 | AA00 | Project03 |
| 校准模组 | BD00 | Project01 |
| 产品传输 | SS00 | Project01 |
| 条码扫描 | AI00 | Project03 |

其中：

- BD00通过跨项目校准端口安装到Project03基座；
- SS00通过跨项目传输端口安装到Project03基座；
- AI00使用Project03已发布扫描端口；
- 最终结果不属于Project01或Project03任一完整原型的直接复制。

### 7.3 展示当前任务状态

```powershell
$j = Get-Content `
  ".\demo\global_assembly_contexts\manifest_jobs\project-global-job-f0aa2d732403\job.json" `
  -Raw | ConvertFrom-Json

$j | Select-Object jobId,status,executionDurationSeconds,assemblyStatus,collisionStatus

$j.steps | Select-Object `
  stepId,moduleToken,status,attemptCount,
  @{Name="durationSeconds";Expression={$_.attempts[0].durationSeconds}},
  @{Name="assemblyPath";Expression={$_.checkpoint.assemblyPath}}
```

预期：

```text
status = succeeded
BD00 → SS00 → AI00
3/3步骤成功
executionDurationSeconds ≈ 335.831
collisionStatus = not_evaluated
```

---

## 8. Case D：在SolidWorks查看跨项目累计结果

### 8.1 逐步检查点

#### 检查点1：Project03基座＋Project01校准

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-f0aa2d732403\packet-runs\packet-001-attempt-01\cross-project-aa00-bd00-ss00-ai00-portable-v1-packet-001.SLDASM
```

#### 检查点2：再加入Project01传输

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-f0aa2d732403\packet-runs\packet-002-attempt-01\cross-project-aa00-bd00-ss00-ai00-portable-v1-packet-002.SLDASM
```

#### 检查点3：再加入Project03扫描

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-f0aa2d732403\packet-runs\packet-003-attempt-01\cross-project-aa00-bd00-ss00-ai00-portable-v1-packet-003.SLDASM
```

### 8.2 SolidWorks观察点

1. FeatureManager中有AA00、BD00、SS00和AI00四个顶层对象；
2. BD00、SS00来自Project01，AA00、AI00来自Project03；
3. 三步均建立真实驱动配合；
4. 后一检查点保留前一步组件和配合；
5. 装配体已完成保存、关闭和重开复核。

建议话术：

> 这条短链主要证明跨项目接口复用。系统没有复制任何一个完整原型，而是以Project03固定环境为上下文，分别选择Project01校准、Project01传输和Project03扫描的已发布端口，逐包形成新的累计装配体。

---

## 9. 可选：现场展示一次快速阻断

如果时间允许，可以新建空白会话，直接输入：

```text
增加一个喷嘴校准模组。
```

在空白上下文中，系统应提示缺少可连接的固定环境或安装目标，并阻止创建CAD任务。

这个Case用来证明：

> 系统不是识别到模组名称就强行插入，而是先检查当前上下文、语义端口和兼容模板。

不要在会议现场临时尝试未登记的新模组组合，以免把“目录尚未覆盖”误解为系统运行故障。

---

## 10. 常见问题与准确回答

### 10.1 这是在复刻原型吗？

完整链不是复制原型顶层位姿。7个新增模组均从非原型初始位姿插入并由配合求解。但是配合面、机械接口和部分尺寸仍以原型提取或标定信息为依据。

跨项目短链更不是单一原型复刻，因为其顶层模组来自Project01和Project03两个项目。

### 10.2 为什么不现场重新跑完整链？

完整链实测约14.6分钟，跨项目短链约5.6分钟。会议时间不适合等待SolidWorks加载、保存和重开。展示既有不可变检查点和机器证据能覆盖完全相同的验证内容。

### 10.3 为什么有的配合包含距离或宽度？

单个重合或同心关系通常不能封闭刚体的全部自由度。系统使用完整配合束共同限定支承面、方向和二维位置。

### 10.4 是否已经无干涉？

没有作此声明。当前任务的`collisionStatus`是`not_evaluated`。碰撞和B-rep是独立后验工程验证，不影响本轮证明自然语言、语义端口、配合重建和累计保存链路。

### 10.5 为什么完整链仍使用Project05字样？

本轮使用项目范围进行唯一消歧和复现实验。最终交互目标是让工程师描述功能，由系统推荐具体型号并要求人工确认，而不是要求工程师记忆内部项目号和模组编号。

### 10.6 能否更换累计顺序？

架构支持依赖允许范围内的非固定顺序，Project05过去已完成多种正逆序短链验证。本次完整7包只运行了一条代表性顺序，没有穷举全部排列。

---

## 11. 故障回退方案

### 11.1 前端页面为空或灰色

1. 检查`http://127.0.0.1:8000/api/health`；
2. 检查前端PowerShell是否仍显示Vite运行中；
3. 使用`Ctrl+F5`强制刷新；
4. 重新打开`http://127.0.0.1:5173/#global-assembly-workbench`；
5. 再次输入上下文编号并点击“继续已有会话”。

### 11.2 PowerShell提示禁止运行npm.ps1

使用：

```powershell
npm.cmd run dev -- --host 127.0.0.1
```

不要临时修改整机执行策略。

### 11.3 SolidWorks加载缓慢

- 不要重复点击打开；
- 等待状态栏停止变化；
- 先只展示前端和PowerShell证据；
- 必要时放弃现场切换三个检查点，只打开最终装配体。

### 11.4 SolidWorks出现许可证或.NET提示

- 不要在会议中反复重启或修改系统配置；
- 切换为前端＋机器证据演示；
- 使用本手册中的检查点路径和任务报告说明实体闭环结果。

### 11.5 前端没有恢复完整链的CAD状态

当前版本已修复通用清单任务与装配会话的自动绑定。正常情况下，重新加载
`project05-complete-seven-addon-v2`后应直接看到：

```text
project05-job-72463661a6a2 · succeeded
7/7
assemblyStatus = assembled
```

如果仍未出现：

1. 使用`Ctrl+F5`或新建浏览器标签页加载最新前端；
2. 重新输入会话编号并点击“继续已有会话”；
3. 不要重新启动CAD长链；先使用第6.2节查询任务JSON；
4. 确认后端已加载包含会话绑定修复的新版本。

---

## 12. 结束总结话术

> 当前已经完成两类真实闭环。第一类是在同一项目机械环境中，从固定基座开始累计加入传输、扫描、CCD、校准称重、清洁、排胶和龙门，形成8模组实体装配体；第二类是在Project03基座上累计加入Project01和Project03的不同模组，证明语义端口可以支持跨项目组合。两条链都建立了真实SolidWorks配合、实体检查点和保存重开证据。下一阶段重点是扩大兼容端口覆盖，并补充独立的扫描工艺、碰撞和动态行程验证。

---

## 13. 演示前最终检查表

- [ ] 后端健康检查通过；
- [ ] 前端页面可访问；
- [ ] `project05-complete-seven-addon-v2`能够加载；
- [ ] “跨项目三步累计链”按钮能够加载；
- [ ] 完整链任务JSON可以查询；
- [ ] 跨项目任务JSON可以查询；
- [ ] 两个最终装配体路径可访问；
- [ ] SolidWorks只保留必要窗口；
- [ ] 已明确说明碰撞/B-rep未评估；
- [ ] 已明确说明完整链“去原型位姿、未去原型机械标定”；
- [ ] 不在会议现场重新运行完整长链。

---

## 14. 2026-10-14实机彩排记录

### 14.1 运行环境

- 后端健康检查：`status = ok`；
- 前端：`http://127.0.0.1:5173/#global-assembly-workbench`可访问；
- SolidWorks：进程正常响应；
- 当前打开的完整链结果：`project05-complete-seven-addon-v2-packet-007.SLDASM`；
- 碰撞/B-rep：两条链均保持`not_evaluated`，未被误报为已通过。

### 14.2 完整链彩排结果

```text
上下文：project05-complete-seven-addon-v2
修订：8
模组：8
任务：project05-job-72463661a6a2
状态：succeeded
检查点：7/7
累计耗时：874.467秒
定位模式：语义端口＋配合图独立装配
原型顶层位姿：未读取
```

前端已正确展示D000、F000、M000、G000、N000、P000、B000七步结果及每一步装配体路径。

### 14.3 跨项目链彩排结果

```text
上下文：cross-project-aa00-bd00-ss00-ai00-portable-v1
修订：4
模组：4
任务：project-global-job-f0aa2d732403
状态：succeeded
检查点：3/3
累计耗时：335.831秒
模组来源：Project03 AA00/AI00＋Project01 BD00/SS00
```

前端已正确展示发布绑定、三个项目无关CAD事务包、每步装配体路径和最终可续装检查点。

### 14.4 彩排中发现并修复的问题

问题：通用自然语言清单编译器创建持久CAD任务后，没有调用已有的会话绑定逻辑。因此后台和SolidWorks已经成功，但刷新页面后会显示“CAD尚未执行”。

修复：任务创建后立即按`contextId + contextRevision + contextDigest`绑定到对应自然语言轮次；以后新任务会自动回写，既有完整链任务也已补绑。相关回归测试为`11 passed`。

现场注意：旧标签页可能保留热更新前的页面代码。若页面中看不到“装配定位模式”或仍显示旧状态，请新建标签页打开演示地址，不要据此重新执行CAD。
