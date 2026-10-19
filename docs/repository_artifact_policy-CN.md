# 仓库源码、实验与生成物管理规则

更新日期：2026-10-19

## 1. 目的

本仓库同时包含应用源码、SolidWorks桥接代码、实验脚本和大量CAD运行证据。若全部提交，会导致仓库体积快速增长、审查困难，并使依赖和临时文件进入历史。本规则明确哪些内容进入Git，哪些保留为外部成果。

## 2. 三类内容

### 2.1 正式源码与测试：进入Git

- `apps/demo-backend/src/`
- `apps/demo-backend/tests/`
- `apps/demo-frontend/src/`
- `vendor/solidworks-mcp/`中的源码与测试
- `solidworks_rag/`
- 项目配置、锁文件及启动脚本
- `docs/`中的架构、规则、操作和交接文档

要求：能够被代码审查，具有稳定入口或测试覆盖，不依赖某次本地会话才能理解。

### 2.2 实验与复现工具：选择性进入Git

`scripts/`中的Python或PowerShell脚本按用途管理：

- `run_*`：执行已有工作流；
- `compile_*`：把语义数据编译为中间产物；
- `build_*`：生成端口、图或候选数据；
- `capture_*`：从CAD采集证据；
- `validate_*`、`verify_*`：验证产物；
- `finalize_*`、`summarize_*`：固化和汇总实验；
- `diagnose_*`、`analyze_*`：专项诊断。

仍能复现实验、生成正式目录或被测试调用的脚本进入Git。完全重复、已经失效且无复现价值的脚本不进入主线；历史实现由Git标签或历史提交保存，不复制为`old/`目录。

### 2.3 运行与展示生成物：不进入普通Git历史

- `.runtime/`、`tmp/`和工具临时目录；
- `node_modules/`、`bin/`、`obj/`、前端`dist/`；
- `demo/`下生成的日志、JSONL、截图、CAD文件和摘要；
- `outputs/`、`deliverables/`；
- `review_packages/`中的ZIP、SLDASM和大体积评审材料；
- PPT渲染中间文件；
- Office/SolidWorks锁文件。

它们保留在本地或发布为GitHub Release附件。必须版本化的大型CAD二进制应使用Git LFS，并优先使用SolidWorks Pack and Go保证依赖完整。

## 3. 证据进入Git的方式

普通提交只保存：

- 生成证据的代码；
- 输入配置或最小脱敏样例；
- JSON Schema或数据契约；
- 体积较小的人工结论摘要；
- 外部评审包的文件名、摘要、生成时间和下载位置。

不提交成百上千个运行日志、截图或会话检查点。

## 4. 版本封存

- 稳定里程碑使用Git标签；
- 主线合并使用功能明确的小提交；
- 大型评审包使用Release版本号；
- 删除被替代代码前确认测试覆盖和迁移文档；
- 不使用`backup/`、`v1_old/`等目录复制整个旧版本。

## 5. 提交前检查

```powershell
git status --short
git diff --check
python -m pytest apps/demo-backend/tests
npm.cmd --prefix apps/demo-frontend run build
dotnet test vendor/solidworks-mcp/bridge/SolidWorksBridge.sln -c Release
```

真实SolidWorks验证按功能风险单独执行，不要求每个纯文档或解析器提交都启动CAD。

