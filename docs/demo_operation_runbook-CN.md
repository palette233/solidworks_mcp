# 自然语言模组装配演示操作手册

> 更新时间：2026-10-12
> 用途：会议演示时逐步对照操作
> 推荐时长：8～12分钟
> 当前主线：自然语言 → 模组检索 → 语义端口 → 配合模板 → CAD事务 → SolidWorks累计装配 → 保存重开证据

---

## 1. 演示边界与推荐策略

今晚推荐采用：

```text
现场运行快速逻辑链
    ＋
展示已经完成的真实CAD长链证据
```

不推荐会议现场重新跑完整约9分钟的SolidWorks长链，原因包括：

- SolidWorks许可证和加载状态具有不确定性；
- 完整CAD执行会占用大部分演示时间；
- 当前已经有同一发布版本的真实执行、保存、关闭、重开和复测证据；
- 现场重点应放在系统如何理解需求、选择端口以及产生可执行事务，而不是等待CAD进度条。

### 1.1 四类操作的含义

| 操作类型 | 是否修改数据 | 是否启动SolidWorks | 演示用途 |
|---|---:|---:|---|
| 目录检索、查看报告 | 否 | 否 | 展示知识库和现有证据 |
| 生成预览 | 否 | 否 | 展示自然语言解析和候选端口 |
| 确认写入上下文 | 是，仅修改装配图JSON | 否 | 展示多轮累计装配语义 |
| 编译排队任务 | 是，生成清单和任务 | 否 | 展示CAD执行前门禁 |
| 启动CAD任务 | 是，生成新装配体 | 是 | 真实机械执行，可选 |

### 1.2 汇报时应使用的准确表述

可以说：

> 系统已经形成受控自然语言到真实SolidWorks累计装配的闭环，并验证了跨项目模组组合。

不要说：

- 所有模组都可以任意两两连接；
- 当前结果已经保证无实体干涉；
- 当前结果已经达到生产放行标准；
- 当前使用完全开放、无约束的自然语言。

---

## 2. 演示前准备

### 2.1 SolidWorks准备

- [ ] 关闭其他大型装配体；
- [ ] 保留一个干净SolidWorks 2024会话；
- [ ] 不打开项目原型；
- [ ] 确认许可证没有弹出错误；
- [ ] 不在演示前启动全量干涉检查。

### 2.2 启动后端

打开第一个PowerShell：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
.\scripts\start_demo_backend.cmd
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

期望：

```text
status = ok
mcpMode = bridge
```

API文档：

```text
http://127.0.0.1:8000/docs
```

### 2.3 启动前端

打开第二个PowerShell：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm.cmd run dev -- --host 127.0.0.1
```

打开：

```text
http://127.0.0.1:5173/#global-assembly-workbench
```

注意：使用`npm.cmd`，不要使用可能被PowerShell执行策略拦截的`npm.ps1`。

### 2.4 提前准备的窗口

建议提前打开并最小化：

1. 前端自然语言增量装配页；
2. PowerShell编译窗口；
3. 最终跨项目装配体；
4. 完整闭环报告；
5. 扫描工艺验证报告。

---

## 3. Case A：全局模组目录与角色检索

### 3.1 场景意义

回答以下问题：

> 系统是否只认识Project02编号，还是能够把不同项目的同类子装配体放入统一目录？

这个Case只读，不修改上下文，不启动SolidWorks。

### 3.2 操作步骤

进入：

```text
http://127.0.0.1:5173/#global-assembly-workbench
```

找到：

```text
跨项目模组库 · 静态自由组合MVP
自然语言增量装配上下文
```

操作：

1. 点击“刷新目录”；
2. 查看CAD模组定义、语义端口、兼容关系、待补证据；
3. 在“全局检索”中依次检索：

```text
传输模组
```

```text
扫描模组
```

```text
校准模组
```

```text
CCD模组
```

### 3.3 应重点讲解

- 项目编号是历史来源和别名，不是唯一身份；
- 同一角色可以有多个项目候选；
- 系统最终依据CAD定义、语义端口和关系模板判断是否能连接；
- 搜索到某个模组不等于它已经可以安装到所有基座。

### 3.4 当前页面统计说明

当前前端默认目录通常显示：

```text
43个CAD模组定义
74个语义端口
61条兼容关系
9项待补证据
```

显式绑定的v48不可变发布包含更晚的跨项目关系，因此报告数字可能为`76`个端口和`71`条兼容关系。展示时不要把两个版本的统计混为同一快照；真实四角色CAD链应以v48发布为准。

---

## 4. Case B：Project02中文三模组装配图预览

> 2026-10-12实测说明：推荐使用下方“无内部编号”的工程描述。当前结构图中，A800、A180和A500均通过各自已登记的安装端口连接到A600；A180与A800的扫码关系目前属于工艺意图/只读验证，不应在页面上表述为两者已有直接安装连接。A500命令暂不加入“操作侧”，因为现有A500—A600模板尚未声明操作侧基准。

### 4.1 场景意义

快速展示中文自然语言、多轮上下文和机械装配顺序：

```text
A600箱体 → A800传输 → A180扫描
```

该Case主要证明图级编排，不启动SolidWorks、不验证碰撞。

### 4.2 建立新上下文

在“建立装配上下文”中输入：

```text
meeting-project02-preview-v1
```

点击：

```text
新建/重置上下文
```

期望：

```text
当前修订：0
实例：0
```

### 4.3 添加A600基座

输入：

```text
请先添加项目02的A600箱体模组作为基座
```

依次点击：

1. “生成预览”；
2. 检查“预览状态：ready”；
3. “确认写入装配上下文”。

含义：定义整个累计装配的固定环境，但尚未修改SolidWorks。

### 4.4 添加A800传输模组

输入：

```text
然后将项目02的A800传输模组安装到A600传输槽位
```

重复：

1. 生成预览；
2. 查看候选端口；
3. 确认写入上下文。

含义：系统需要选择A800安装端口、A600承载端口和对应关系模板。

### 4.5 添加A180扫描模组

输入：

```text
最后将项目02的A180扫描模组安装到A600扫描槽位
```

重复预览和确认。

含义：机械安装端口负责确定位置，扫描光轴和条码目标区属于后续工艺验证语义，不应混成安装配合。

### 4.6 展示结果

指出：

- 三轮自然语言命令历史；
- A600、A800、A180三个实例；
- 两条连接关系；
- 当前只提交装配图，CAD尚未执行；
- 碰撞状态明确为“未评估”。

### 4.7 命令行快速替代

若前端操作时间不足，可执行：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
python .\scripts\run_global_natural_language_assembly_demo.py `
  --context-id meeting-project02-preview-v1 `
  --reset
```

边界：该脚本只生成可审计装配图草案，不启动SolidWorks。

### 4.8 推荐的工程师语言四模组累计案例（已实测）

依次输入并在每轮选择Project02候选、勾选工程意图、点击“提交并加入当前装配”：

```text
请先建立一套设备箱体与安装基座，作为后续模组的固定安装环境。
```

```text
在当前设备箱体上安装一套产品传输模组，用于承载产品并依次经过两个点胶工作区。
```

```text
在传输线入口附近增加一个条码扫描模组，用于读取载具和产品条码。
```

```text
增加一个喷嘴校准模组，方便点胶头定期进行位置校准。
```

实测结果：修订4、4个模组、3条结构安装连接。页面中的结构连接分别是A800→A600、A180→A600、A500→A600。扫码器与传输线的光轴、目标区和工作距离属于另一个只读工艺验证层，不等同于直接安装配合。

如果第四句改为“在设备操作侧增加……”，当前会安全阻断，因为模板没有操作侧语义。这个阻断可以作为边界展示，但不能再把它列为预期成功步骤。

---

## 5. Case C：跨项目四角色完整主线Demo

### 5.1 场景意义

这是今晚最重要的Case：

```text
Project03 AA00 基座
  → Project01 SS00 传输
  → Project03 AI00 扫描
  → Project01 BD00 校准
```

它证明：

- 不是复刻单一原型；
- 模组来自两个项目；
- 自然语言决定对象和顺序；
- 端口和配合模板驱动真实CAD定位；
- 每一步产生不可变检查点。

### 5.2 前端图级预览

建立上下文：

```text
meeting-cross-project-preview-v1
```

逐条输入以下命令，每条都执行“生成预览 → 确认写入装配上下文”。

第一条：

```text
Add Project03 AA00 as the base module.
```

第二条：

```text
Install Project01 SS00 transport module onto the Project03 AA00 transport slot.
```

第三条：

```text
Install Project03 AI00 scanner module onto the Project03 AA00 scanner slot.
```

第四条：

```text
Install Project01 BD00 calibration module onto the Project03 AA00 calibration slot.
```

英文命令是当前v48真实长链已经验证过的受控表达。中文同义表达可以作为后续鲁棒性展示，但今晚关键主链建议使用上述原命令。

### 5.3 绑定不可变v48发布并正式编译

打开PowerShell：

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
```

执行：

```powershell
python .\scripts\compile_global_natural_language_manifest_job.py `
  meeting-cross-project-v1 `
  "Add Project03 AA00 as the base module." `
  "Install Project01 SS00 transport module onto the Project03 AA00 transport slot." `
  "Install Project03 AI00 scanner module onto the Project03 AA00 scanner slot." `
  "Install Project01 BD00 calibration module onto the Project03 AA00 calibration slot." `
  --display-name "会议跨项目四角色装配演示" `
  --release-manifest "demo\global_assembly_catalog\releases\relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012\release-manifest.json" `
  --overwrite
```

该命令会创建排队任务，但不会启动SolidWorks。

### 5.4 查看精简结果

```powershell
$c = Get-Content `
  ".\demo\global_assembly_contexts\meeting-cross-project-v1.natural-language-compilation.json" `
  -Raw | ConvertFrom-Json

$c | Select-Object `
  success,status,contextId,turnCount,packetCount,jobId,cadStarted,collisionStatus

$c.timingSeconds
```

期望看到：

```text
success        = true
status         = job_created_not_started
turnCount      = 4
packetCount    = 3
cadStarted     = false
collisionStatus = not_evaluated
```

含义：所有CAD变更之前，系统已经完成模组识别、端口选择、关系模板授权、顺序和事务包编译。

### 5.5 查看CAD事务清单

打开：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\meeting-cross-project-v1.cad-transaction-manifest.json
```

搜索：

```text
packet-001
packet-002
packet-003
portAId
portBId
templateId
requestedMateCount
```

对应含义：

| 工作包 | 新增模组 | 输入来源 |
|---|---|---|
| packet-001 | SS00传输 | AA00基座 |
| packet-002 | AI00扫描 | packet-001检查点 |
| packet-003 | BD00校准 | packet-002检查点 |

---

## 6. Case D：真实SolidWorks结果复核

### 6.1 场景意义

证明Case C不仅停留在JSON和图结构，而是已经真实执行过SolidWorks。

### 6.2 查看已完成任务状态

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp

$j = Get-Content `
  ".\demo\global_assembly_contexts\manifest_jobs\project-global-job-163f19364c24\job.json" `
  -Raw | ConvertFrom-Json

$j | Select-Object `
  jobId,status,assemblyStatus,collisionStatus,startedAt,completedAt,executionDurationSeconds

$j.steps | Select-Object `
  stepId,moduleToken,status,attemptCount,
  @{Name="assemblyPath";Expression={$_.checkpoint.assemblyPath}}
```

期望：

```text
packet-001  SS00  succeeded  1
packet-002  AI00  succeeded  1
packet-003  BD00  succeeded  1
```

### 6.3 在SolidWorks中打开结果

SolidWorks中选择：

```text
文件 → 打开
```

文件：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-163f19364c24\packet-runs\packet-003-attempt-01\cross-project-p03-ss00-ai00-bd00-v1-packet-003.SLDASM
```

操作：

1. 等待完全加载；
2. 按`F`缩放至窗口；
3. 切换等轴测；
4. 展开FeatureManager设计树；
5. 指出AA00、SS00、AI00、BD00；
6. 展开“配合”文件夹；
7. 说明每个新增模组均创建`3/3`个驱动配合；
8. 说明模组完全约束、保存成功、关闭重开成功。

现场不要执行：

- 删除或编辑配合；
- 打开多个原型进行对比；
- 全量干涉检查；
- 大型强制重建。

### 6.4 结果解释

该装配体不是Project01或Project03顶层原型的完整复制。它使用Project03 AA00作为基座，分别通过发布的端口与配合模板插入Project01 SS00、Project03 AI00和Project01 BD00。

---

## 7. Case E：机器可读证据与工艺代理验证

### 7.1 完整闭环证据

打开：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\cross_project_substitution\cumulative-project03-v2\complete-demo-chain-closure.json
```

重点字段：

```text
status = complete_demo_chain_passed
mechanicalDemoChainPassed = true
completeFunctionalDemoPassed = true
collisionStatus = not_evaluated
executionDurationSeconds = 529.505085
productionReady = false
```

含义：

- 自然语言、机械配合和保存重开已闭环；
- 静态扫描工艺代理已通过；
- 碰撞没有被本轮评估；
- 不能表述为生产放行。

### 7.2 扫描工艺验证

打开：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\cross_project_substitution\cumulative-project03-v2\scanner-transport-process-validation.md
```

可以汇报：

- 扫描站位于SS00保守输送包络内；
- 横向误差约`0.402 mm`；
- 估算工作距离约`79.5 mm`；
- 位于SR-X100官方读取距离范围内。

必须同步说明：

> 条码位置仍采用原型光束端点代理，真实条码面、码尺寸、视野和触发时序仍待工程确认。

---

## 8. Case F：失败关闭与可解释阻塞

### 8.1 场景意义

证明系统并非“无论什么命令都强行装配”，而是在证据不足或接口不兼容时停止在CAD之前。

### 8.2 推荐展示方式

这个Case建议展示已有失败摘要，不建议会议现场临时修改关系目录。

可使用的解释示例：

```text
用项目03 AI00扫描模组替换项目01 SM00
```

已知工程处置中，该替换存在安装孔距/定位图案差异，需要：

- 转接接口；或
- 目标基座存在兼容槽位；或
- 新增经过验证的直接安装关系。

讲解词：

> 系统会区分“同角色”和“机械接口兼容”。两个模组都是扫描器，并不意味着安装孔系相同；缺少兼容证据时应在SolidWorks启动前拒绝。

### 8.3 应展示的信息

- 用户输入；
- 候选模组；
- 双方端口；
- 阻塞码；
- 孔距或定位图案差异；
- 建议补充转接件或新槽位。

这个Case的价值在于展示系统具有工程边界，而不是只会生成结果。

---

## 9. Case G：持久任务、暂停恢复与检查点

### 9.1 场景意义

回答：

> 长时间SolidWorks任务中途失败，是否必须从头再来？

### 9.2 推荐展示方式

不必现场制造失败。打开：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\demo\global_assembly_contexts\manifest_jobs\project-global-job-163f19364c24\job.json
```

展示：

- `steps`；
- `lastCommittedCheckpoint`；
- `demoCheckpoint`；
- `rollback`；
- `events.jsonl`；
- 每个packet独立的`cad-result.json`。

讲解：

> 每完成一个CAD包才提交检查点；下一包严格消费上一包结果。若后续失败，系统保留最后有效装配体和证据，可以暂停或恢复，而不是重新执行所有步骤。

---

## 10. 可选Case H：人工选面兜底

### 10.1 场景意义

当语义端口目录没有覆盖某个特殊连接，而需求方可以接受人工选面时，可以：

1. 在SolidWorks选中面；
2. 在前端登记为上下文临时端口；
3. 选择第二个面并登记；
4. 用自然语言描述两者需要的基础配合；
5. 生成配合草案和局部配合图。

### 10.2 前端入口

在建立上下文并拥有模组实例后，找到：

```text
人工选面兜底（上下文局部端口）
```

操作字段包括：

- 所属实例；
- 模组编号；
- 端口名称；
- 接口类型；
- “捕获当前选中面并登记端口”；
- 临时配合命令；
- “解析为基础配合草案”。

该功能目前适合作为补充探索，不建议列为今晚主线必演项。

---

## 11. 可选：现场重新执行真实CAD

只在满足以下条件时执行：

- 会议至少预留15分钟；
- SolidWorks许可证稳定；
- 当前只有一个干净SolidWorks会话；
- 新编译任务已经通过预检；
- 现场允许等待。

从Case C编译输出复制新`jobId`：

```powershell
python .\scripts\run_global_cad_manifest_job.py run <jobId> --timeout-seconds 2400
```

状态查询：

```powershell
python .\scripts\run_global_cad_manifest_job.py status <jobId>
```

推荐表述：

> 为控制会议时间，现场只运行亚秒级自然语言编译；随后展示同一v48发布已完成的真实CAD执行结果。

---

## 12. 推荐的会议演示组合

### 12.1 五分钟精简版

```text
Case A 目录检索
  → Case C 正式编译
  → Case D 打开最终装配体
  → Case E 展示闭环结果
```

### 12.2 十分钟标准版

```text
Case A 目录检索
  → Case B 中文三模组图预览
  → Case C 跨项目四角色正式编译
  → Case D SolidWorks结果
  → Case E 工艺代理验证
  → Case F 失败关闭
```

### 12.3 技术讨论版

```text
Case A
  → Case C
  → CAD事务清单
  → Case D
  → Case F
  → Case G检查点
  → 讨论端口扩充、转接接口与工程验证
```

---

## 13. 常见问题与现场回答

### 13.1 这是复制原型吗？

不是完整复制某个原型。当前跨项目案例使用Project03基座，并分别插入Project01传输、Project03扫描和Project01校准模组。位姿由发布的语义端口和SolidWorks配合关系求解。

### 13.2 为什么要使用不可变发布版本？

防止尚未验证或后续变化的模板静默进入CAD。任务明确绑定某一版本的端口、模板和摘要，便于复现与审计。

### 13.3 为什么有语义端口还需要配合模板？

端口说明用哪些几何对象连接；模板说明这些对象之间建立重合、同心、平行、距离等哪些配合，以及预期封闭多少自由度。

### 13.4 是否保证无干涉？

当前主线没有执行碰撞硬门禁，因此答案是否定的。当前只证明配合、完全约束、保存重开和静态工艺代理；碰撞/B-rep属于可独立启动的后验工程验证。

### 13.5 是否可以任意自由组合？

编排架构支持自由组合，但真实执行要求双方端口兼容且存在已发布关系模板。当前目标是覆盖机械上有意义的常见角色替换，不是无条件全连接。

### 13.6 为什么现场不重新跑完整CAD？

完整长链约需9分钟，且受SolidWorks和许可证状态影响。现场运行逻辑编译并展示同版本真实CAD闭环证据，更稳定，也更能突出系统设计。

### 13.7 刷新页面后如何确认任务没有丢失？

页面会记住最近使用的装配会话，并从后台台账恢复会话修订、自然语言轮次、执行清单和最近CAD任务。刷新后应重新看到“已加载：修订N，包含N个模组”、最近任务编号、任务状态及最后有效检查点。该恢复过程只读取后台状态，不会再次启动SolidWorks或重复创建任务；若浏览器存储被清理，可输入原会话名称并点击“继续已有会话”。

---

## 14. 故障备用方案

### 前端不可访问

1. 使用Case C命令行正式编译；
2. 展示生成的自然语言编译JSON；
3. 展示已有任务状态；
4. 打开最终装配体。

### SolidWorks无法启动

1. 不反复强制重启；
2. 展示最终装配体缩略图或预先截图；
3. 展示`user-summary.md`和闭环JSON；
4. 说明装配体此前已经保存、关闭和重开验证。

### 自然语言预览被阻断

1. 不临时修改目录；
2. 展示阻塞原因和候选端口；
3. 切换到v48正式编译命令；
4. 将其解释为CAD前失败关闭能力。

### 页面再次局部报错

当前迁移就绪面板已经增加局部错误边界。若某个历史面板出现告警，自然语言装配主区域应仍可继续使用；不要刷新或重启SolidWorks。

---

## 15. 演示完成检查

- [ ] 展示过全局模组目录；
- [ ] 展示过至少一次模组搜索；
- [ ] 展示过自然语言预览；
- [ ] 解释过确认写入上下文不等于启动CAD；
- [ ] 展示过v48发布绑定；
- [ ] 展示过三个CAD事务包；
- [ ] 打开过最终四角色装配体；
- [ ] 展示过保存重开与完全约束证据；
- [ ] 明确碰撞未评估；
- [ ] 明确当前不是生产放行结果；
- [ ] 说明后续重点是扩充机械上有意义的跨项目端口与模板。
