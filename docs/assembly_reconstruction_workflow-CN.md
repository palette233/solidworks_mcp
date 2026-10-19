# 从零开始：基于 Common Base 与 Layout2D 的装配体复原操作手册

## 1. 目标与适用范围

本手册用于完成以下任务：

> 已知一个参考装配体 X，其中包含若干子装配体；记录这些组件的真实底面和
> Transform2 布局，在新的空白 Assembly 中重新导入相同组件，先完成 Common Base，
> 再根据 Layout2D 恢复组件的平面位置与旋转。

完整链路：

```text
准备环境
→ 启动 SolidWorks / MCP / 后端 / 前端
→ 打开参考装配体 X
→ 发现并选择参与复原的组件
→ 逐个记录并验证真实底面
→ 读取 Transform2，生成 Layout2D JSON
→ Reset 并加载 Layout JSON
→ Initialize 新目标装配体
→ Verify Faces
→ Common Base
→ Replay Layout
→ 检查 XY / Theta 误差
```

重要说明：

- “记录 Transform2”在本项目中对应 `Capture Project Layout` 或
  `capture_common_base_layout.py`。
- Transform2 不直接原样复制到目标组件，而是被转换为相对共同底平面的
  `x / y / thetaDegrees`。
- Layout2D 依赖底面中心和法向，因此正确顺序是**先记录底面，再捕获 Transform2/Layout2D**。
- 当前流程恢复的是共同底平面内的位置和旋转，不等价于恢复所有机械配合关系。

## 2. 两类装配体

| 对象 | 作用 |
| --- | --- |
| 参考装配体 X | 已经具有目标布局，用于记录底面和捕获 Layout2D |
| 目标装配体 | 新建的 Assembly，用于重新导入组件并执行 Common Base、Replay Layout |

参考装配体和目标装配体中的组件实例名应保持一致。例如参考布局记录的是 `A-1`，
目标 Assembly 中也应存在 `A-1`。

## 3. 第一次使用：获取代码和安装环境

### 3.1 获取当前项目版本

```cmd
cd /d D:\your-workspace
git clone --branch merge-to-upstream --single-branch https://github.com/palette233/solidworks_mcp.git
cd solidworks_mcp
```

以下命令统一假设项目路径为：

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
```

如果实际位置不同，请替换为自己的路径。

### 3.2 检查基础环境

```cmd
dotnet --version
python --version
node --version
npm --version
```

需要：

- Windows；
- SolidWorks；
- .NET 8 SDK；
- Python 3；
- Node.js 和 npm。

安装后端 Python 依赖：

```cmd
python -m pip install fastapi uvicorn pydantic
```

### 3.3 构建 MCP 和命令行工具

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp

dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet build apps\demo-backend\tools\McpToolRunner\McpToolRunner.csproj -c Release
```

预期结果：

```text
0 个警告
0 个错误
```

### 3.4 安装前端依赖

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
```

`npm install` 一般只需首次运行或依赖变化后执行。

## 4. 每次测试前：定义路径

在 CMD 中根据本次测试修改：

```cmd
set "PROJECT_ROOT=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp"
set "SOURCE_ASSEMBLY=D:\path\X_reference.SLDASM"
set "TARGET_ASSEMBLY=D:\path\X_replay_test.SLDASM"
set "LAYOUT_JSON=%PROJECT_ROOT%\demo\project_layout2d.json"
set "PROJECT_CONFIG=%PROJECT_ROOT%\demo\project_config.json"
```

要求：

- `SOURCE_ASSEMBLY` 指向参考装配体；
- `TARGET_ASSEMBLY` 指向准备生成的新目标装配体；
- 目标文件不要与参考文件相同；
- 如果目标文件已存在，先在 SolidWorks 中关闭，再备份、改名或删除。

## 5. 启动 SolidWorks、MCP、后端和前端

建议使用四个独立窗口：

```text
窗口 1：SolidWorks
窗口 2：MCP Hub
窗口 3：后端
窗口 4：前端
```

### 5.1 启动 SolidWorks

手工启动 SolidWorks。

检查：

- 没有未处理的错误或保存对话框；
- 没有正在进行的重建；
- 没有打开旧的目标装配体；
- 准备记录参考布局时，打开 `SOURCE_ASSEMBLY`。

### 5.2 启动 MCP Hub

打开 CMD：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
scripts\start_mcp_hub.cmd
```

脚本会打开一个名为 `SolidWorks MCP Hub` 的新窗口。测试期间保持该窗口打开。

检查 MCP：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
scripts\check_mcp_hub.cmd
```

期望：

```text
DLL status: found
MCP process status: ...
Pipe status: connectable
```

说明：

- 独立的面记录/验证脚本默认使用 Hub/proxy；
- 后端几何操作默认使用 `--stdio-direct`；
- 因此后端不依赖 Hub，但完整新人流程仍建议启动 Hub，便于使用面记录脚本。

需要停止 Hub 时：

```cmd
scripts\stop_mcp_hub.cmd
```

### 5.3 启动后端

在新的 CMD 中执行：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
set "DEMO_TARGET_ASSEMBLY_PATH=D:\path\X_replay_test.SLDASM"
scripts\start_demo_backend.cmd
```

注意：必须在启动后端之前设置 `DEMO_TARGET_ASSEMBLY_PATH`。

期望：

```text
Uvicorn running on http://127.0.0.1:8000
```

检查基础健康状态：

```cmd
curl.exe http://127.0.0.1:8000/api/health
```

重点确认：

```text
status = ok
mcpMode = bridge
mcpCommand = dotnet
faceMappingPath = ...\artifacts\solidworks-mcp\face_mappings.json
DEMO_TARGET_ASSEMBLY_PATH = 本次目标装配体
```

检查 MCP 与 SolidWorks：

```cmd
curl.exe http://127.0.0.1:8000/api/demo/mcp-health
```

### 5.4 启动前端

在新的 CMD 中执行：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm run dev
```

期望：

```text
http://127.0.0.1:5173
```

在浏览器或 VS Code Simple Browser 中打开：

```text
http://127.0.0.1:5173
```

## 6. 阶段一：在参考装配体中发现组件

在 SolidWorks 中打开参考装配体 X，并确保它是当前活动文档。

### 6.1 前端 Project Config 区域

如果前端还保留上一次测试的目标装配体状态，先点击 `Reset`。Reset 不会修改当前打开的参考装配体。

填写：

| 前端框 | 建议值 |
| --- | --- |
| Source assembly | 参考装配体 X 的完整路径；留空表示使用当前活动装配体 |
| Output layout | `demo/project_layout2d.json` |
| Project config | `demo/project_config.json` |
| Discovery scope | 一般选择 `Top-level components` |
| Include parts | 只恢复子装配体时不勾选 |

执行：

```text
Discover
→ 检查组件列表
→ 勾选参与复原的组件
→ Sync Selected
```

如果组件很多：

- 使用 `Filter` 按组件名、文件路径或层级路径筛选；
- `Select Visible` 选中筛选后的可见项；
- `Clear` 清空当前选择。

完成 `Sync Selected` 后，Coordinates 和 Face Mapping 区域应显示选中的组件。

## 7. 阶段二：逐个记录真实底面

对每个参与复原的组件执行一次。

### 7.1 在 SolidWorks 中选面

1. 在组件树中找到组件实例。
2. 展开子装配体，必要时隐藏遮挡组件。
3. 用鼠标选中该组件的真实底面。
4. 保持选中状态，不要点击空白区域。

### 7.2 记录选中的面

在项目根目录的 CMD 中执行：

```cmd
python scripts\face_mapping_record_probe.py --component "A-1" --face 底面
```

将 `A-1` 替换成真实组件实例名。

成功结果应包含：

- `Success: true`；
- 正确的 `LeafComponentName` 和 `LeafComponentFullName`；
- `LocalCenter`；
- `LocalNormal` 和 `WorldNormal`；
- `Area`；
- `MappingPath` 指向
  `artifacts\solidworks-mcp\face_mappings.json`。

### 7.3 验证能否重新选回同一面

```cmd
python scripts\face_mapping_verify_select.py --component "A-1" --face 底面
```

预期：

```text
RESULT: PASS
```

验证内容：

- 叶子零件是否一致；
- 局部中心误差是否在阈值内；
- 面积误差是否在阈值内；
- 局部法向是否一致；
- `SelectFaceByName` 是否成功。

如果是 `FAIL`：

1. 不要执行 Common Base。
2. 确认当前活动文档是参考装配体。
3. 确认组件实例名完全一致。
4. 重新选择真实平面。
5. 重新记录，再次验证。

### 7.4 批量记录建议

对于 10 个以上组件：

```text
每记录 3～5 个组件
→ 点击前端 Verify Faces
→ 尽早发现错误
→ 再继续下一批
```

## 8. 阶段三：记录 Transform2 并生成 Layout2D

前置条件：

- 参考装配体是当前活动文档；
- 所有参与组件的底面实际共面；
- 底面方向符合预期；
- 所有底面记录均验证为 PASS；
- 组件处于希望未来恢复到的最终布局。

### 8.1 推荐方式：前端 Generate Config

确认前端已经执行：

```text
Discover
→ 选择参与组件
→ Sync Selected
→ Verify Faces
```

然后填写：

```text
Source assembly = 参考装配体路径
Output layout = demo/project_layout2d.json
Project config = demo/project_config.json
```

点击：

```text
Generate Config
```

该按钮完成：

1. 读取参考装配体中的组件 Transform2；
2. 读取已记录底面的中心和法向；
3. 以第一个组件作为默认基准组件；
4. 计算每个组件的 `x / y / thetaDegrees / thetaAxis`；
5. 生成 Layout JSON；
6. 生成项目配置 JSON。

当前前端默认使用同步后组件列表中的第一个组件作为基准组件。若必须指定其他基准组件，
使用下方命令行方式的 `--base-component` 参数。

### 8.2 命令行方式

三个组件示例：

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp

python scripts\capture_common_base_layout.py ^
  --source "D:\path\X_reference.SLDASM" ^
  --component "A-1:底面" ^
  --component "B-1:底面" ^
  --component "C-1:底面" ^
  --base-component "A-1" ^
  --output "demo\project_layout2d.json"
```

更多组件时重复增加：

```cmd
--component "组件实例名:底面"
```

### 8.3 检查 Layout JSON

```cmd
type demo\project_layout2d.json
```

每个组件应包含：

```json
{
  "componentName": "B-1",
  "filePath": "D:\\path\\B.SLDASM",
  "bottomFaceName": "底面",
  "layout2d": {
    "x": 0.2,
    "y": 0.1,
    "thetaDegrees": 30.0,
    "thetaAxis": "..."
  }
}
```

检查：

- 组件数量正确；
- 组件实例名正确；
- `filePath` 可访问；
- `x/y` 不是异常大数；
- `thetaDegrees` 存在；
- 基准组件符合预期。

## 9. 阶段四：准备新的目标装配体

### 9.1 关闭参考装配体

保存参考装配体，然后关闭它。

如果需要同时保留参考装配体作对照，可以保持打开，但必须保证后续 MCP 操作时目标装配体是
SolidWorks 当前活动文档。为了降低误操作风险，首次测试建议关闭参考装配体。

### 9.2 处理旧目标文件

前端 `Reset`：

- 会重置 `demo/demo_state.json`；
- 不会关闭 SolidWorks 文档；
- 不会删除目标 `.SLDASM`；
- 不会删除已有配合。

因此，全新测试前应确认：

- 旧目标装配体已经关闭；
- 旧目标文件已备份、改名或删除；
- 后端启动时配置的是新的目标路径。

如果修改了目标路径，需要停止并重启后端：

```cmd
set "DEMO_TARGET_ASSEMBLY_PATH=D:\path\X_replay_test.SLDASM"
scripts\start_demo_backend.cmd
```

## 10. 阶段五：前端完成装配体复原

### 10.1 推荐操作顺序

```text
1. Reset
2. 选择 Layout JSON 或 Upload JSON
3. 检查组件列表和 Face Mapping 状态
4. Initialize
5. Health
6. Verify Faces
7. Common Base
8. Replay Layout
9. 检查 Replay Check 和 SolidWorks UI
```

### 10.2 Reset

点击顶部圆形箭头按钮 `Reset`。

作用：

- 清除后端上一次 Assembly 路径；
- 将 `commonBaseReady` 设回 `false`；
- 恢复到可 Initialize 状态。

不要把 Reset 当成“删除 SolidWorks 装配体”。

### 10.3 载入 Layout JSON

在 `Layout JSON` 下拉框选择刚生成的：

```text
demo/project_layout2d.json
```

或者点击 `Upload JSON` 上传。

载入后检查：

- 组件数量；
- Layout Summary 中每个组件的 x、y、theta；
- Coordinates 中的组件实例名和文件路径来源；
- Face Mapping 不应显示 Missing。

### 10.4 Initialize

点击：

```text
Initialize
```

作用：

- 新建或打开目标 Assembly；
- 按 Layout JSON 中的 `filePath` 导入组件；
- 保存目标 Assembly；
- 不执行 Common Base；
- 不执行 Layout2D 移动。

等待按钮恢复可用，不要重复点击。

成功判据：

- Result 显示 `ok / base pending`；
- `assemblyPath` 指向目标文件；
- SolidWorks 中可以看到所有组件；
- 目标 `.SLDASM` 已生成。

如果组件已导入但看不见，在 SolidWorks 组件树中检查 Hidden/Suppressed 状态，不要立即重复 Initialize。

### 10.5 Health

点击：

```text
Health
```

检查 MCP Health：

- `Assembly = Yes`；
- `Mapping = Yes`；
- `Active` 与 `Expected` 指向同一个目标 Assembly；
- `Backend map` 与 `MCP map` 指向同一个 `face_mappings.json`。

Health 不通过时不要继续 Common Base。

### 10.6 Verify Faces

点击：

```text
Verify Faces
```

作用：

- 在目标装配体中按组件名查找组件；
- 通过面映射重新选择底面；
- 读取底面中心、面积和法向；
- 确认映射在新目标 Assembly 中仍有效。

成功判据：

- Result 为 `ok`；
- Face Mapping 中所有组件为 `Verified`；
- 没有 Missing；
- 组件 Face 结果为 OK。

### 10.7 Common Base

点击：

```text
Common Base
```

作用：

- 选择各组件记录的底面；
- 以基准组件底面为参考；
- 建立底面共面关系；
- 检查各底面法向；
- 成功后设置 `commonBaseReady = true`。

成功判据：

- Result 为 `ok / base ready`；
- Mate 没有错误；
- Orientation Checks 中 `Match = Yes`；
- SolidWorks UI 中各真实底面共面；
- 没有重复 Coincident mate。

如果出现：

```text
bottom face orientation mismatch
orientation probe errors
```

不要继续 Replay。先检查对应组件的底面映射和法向。

### 10.8 Replay Layout

点击：

```text
Replay Layout
```

作用：

- 读取 Layout JSON；
- 读取目标装配体中各底面当前中心；
- 计算目标 `x/y` 与当前位置的差值；
- 根据 `thetaDegrees` 计算平面内旋转差；
- 移动和旋转组件；
- 再次采集实际布局并计算误差。

成功判据：

- Result 为 `ok / base ready`；
- Replay Check 为 `matched`；
- 每个组件 `XY error` 小于 XY tol；
- 每个组件 `Theta error` 小于 Theta tol；
- SolidWorks UI 与参考装配体布局一致。

## 11. 前端顶部按钮说明

| 按钮 | 作用 | 是否属于标准复原流程 |
| --- | --- | --- |
| Refresh | 从后端重新读取 state 和 Layout 文件列表 | 排障时使用 |
| Save | 保存当前前端坐标状态到后端 | 手工 Arrange 时使用 |
| Reset | 重置后端流程状态，不处理 SolidWorks 文件 | 是 |
| Initialize | 新建/打开目标 Assembly 并导入组件 | 是 |
| Common Base | 根据底面映射完成共底面 | 是 |
| Capture Layout | 捕获当前已初始化 Assembly 的布局快照 | 可选，不是参考装配体主采集入口 |
| Verify Faces | 批量验证底面映射 | 是 |
| Health | 检查活动 Assembly 和映射路径 | 是 |
| Replay Layout | 根据选中的 Layout JSON 恢复 x/y/theta | 是 |
| Arrange | 按 Coordinates 中手工设置的目标坐标移动组件 | 可选，与 Replay 不同 |

`Generate Config` 才是从任意参考装配体读取 Transform2 并生成项目 Layout 的推荐入口。

## 12. 前端各区域和输入框说明

### 12.1 2D layout

- 每个矩形代表一个参与布局的组件；
- 矩形中心对应目标底面中心；
- 向右是 Layout +X；
- 向上是 Layout +Y；
- 拖动矩形只修改前端 `target.x/y`；
- 拖动后需要点击 `Arrange` 才会操作 SolidWorks；
- Replay Layout 使用 JSON，不依赖手工拖动结果。

矩形尺寸只是操作视图，不等于真实 CAD 外形和比例。

### 12.2 Layout JSON

| 控件 | 含义 |
| --- | --- |
| Select layout JSON | 从项目已知 JSON 中选择布局 |
| Upload JSON | 从本机上传布局 JSON |
| Layout path | 当前选中布局文件 |
| components | JSON 中的组件数量 |

选择或上传时默认会把 JSON 中的组件同步到后端状态。

### 12.3 Project Config

| 控件 | 含义 |
| --- | --- |
| Source assembly | 参考装配体路径；留空使用 SolidWorks 当前活动装配体 |
| Output layout | 生成的 Layout2D JSON 路径 |
| Project config | 生成的项目配置路径 |
| Discovery scope | 顶层组件或递归组件 |
| Filter | 按组件名、层级或路径过滤发现结果 |
| Include parts | 是否把零件也作为布局单元 |
| Discover | 读取源装配体组件树 |
| Select Visible | 选择过滤后可见的组件 |
| Clear | 清空选择 |
| Sync Selected | 把选择的组件写入前端/后端状态 |
| Generate Config | 捕获 Transform2，生成 Layout JSON 和项目配置 |

通常优先选择 `Top-level components`。只有明确需要嵌套组件作为独立布局单元时才使用 Recursive。

### 12.4 XY tol / Theta tol

| 输入框 | 含义 | 默认值 |
| --- | --- | --- |
| XY tol | Replay 后允许的最大平面位置误差，单位 m | `0.000001` |
| Theta tol | Replay 后允许的最大角度误差，单位 deg | `0.0001` |

阈值只影响 Replay 成功判定，不直接改变移动结果。

### 12.5 Layout Summary

显示 Layout JSON 中每个组件的：

- `x`；
- `y`；
- `thetaDegrees`；
- `thetaAxis`。

这是参考目标值，不是当前 SolidWorks 实际测量值。

### 12.6 Coordinates

| 列 | 含义 |
| --- | --- |
| Component | 组件实例名与显示名 |
| Current X/Y/Z | 后端记忆的当前坐标，不保证每次都实时读取 Transform2 |
| Bottom X/Y/Z | 可编辑目标底面中心，用于 Arrange |
| Layout X/Y | 选中 Layout JSON 的参考目标值 |
| Theta | Layout JSON 的平面内目标旋转 |
| Face | 使用的面映射名称，通常为“底面” |

使用 Replay 时通常不需要手工修改 Bottom X/Y/Z。

### 12.7 MCP Health

| 字段 | 含义 |
| --- | --- |
| Assembly | 当前活动 Assembly 是否与后端期望路径一致 |
| Mapping | 后端和 MCP 是否使用同一个面映射文件 |
| Active | SolidWorks 当前活动文档 |
| Expected | 后端 state 中的目标 Assembly |
| Backend map | 后端读取的映射路径 |
| MCP map | MCP 读取的映射路径 |

### 12.8 Face Mapping

状态含义：

| 状态 | 含义 |
| --- | --- |
| Missing | 没有该组件的底面映射 |
| Ready | 映射存在，但本轮尚未验证 |
| Verified | 已通过 SelectFaceByName 和 probe 验证 |

### 12.9 Result

顶部状态：

```text
ok / base ready
ok / base pending
error / base pending
blocked / base pending
```

组件结果：

| 字段 | 含义 |
| --- | --- |
| Face | 是否成功选回底面 |
| Mate | Common Base 配合结果 |
| Center | 当前读取的底面中心 |
| Theta | 目标、当前和差值角度 |
| Move | 平移结果 |
| Rotate | 旋转结果 |

### 12.10 Orientation

Corrections 显示是否尝试调整法向；Checks 显示最终法向检查：

- `Match = Yes` 表示与基准底面法向一致；
- `Dot` 越接近 1 越一致；
- `Normal` 是当前世界法向；
- mismatch 时不要继续 Replay。

### 12.11 Replay Check

| 字段 | 含义 |
| --- | --- |
| Max XY | 所有组件中的最大位置误差 / 阈值 |
| Max Theta | 所有组件中的最大角度误差 / 阈值 |
| Capture | Replay 后重新采集实际布局是否成功 |
| XY error | 单个组件的位置误差 |
| Theta error | 单个组件的角度误差 |

### 12.12 Screenshot

显示最近一次 MCP 操作保存的 SolidWorks 截图，用于快速确认结果。最终仍应回到 SolidWorks UI
检查真实几何和配合关系。

## 13. 完整前端操作清单

### 13.1 参考装配体采集

```text
[ ] 在 SolidWorks 打开参考装配体
[ ] 前端 Reset，清除上一次目标装配体状态
[ ] Health，确认 Active 指向参考装配体
[ ] Source assembly 填参考装配体路径
[ ] Discovery scope 选择 Top-level components
[ ] Discover
[ ] 勾选参与复原的组件
[ ] Sync Selected
[ ] 逐个手工选底面并运行记录脚本
[ ] 逐个运行验证脚本，全部 PASS
[ ] 前端 Verify Faces
[ ] 设置 Output layout 和 Project config
[ ] Generate Config
[ ] 检查 Layout Summary 的 x/y/theta
[ ] 保存并关闭参考装配体
```

### 13.2 目标装配体复原

```text
[ ] 确认目标文件路径正确，旧目标文件已关闭
[ ] Reset
[ ] 选择或 Upload 新生成的 Layout JSON
[ ] 检查组件数量和文件路径
[ ] Initialize
[ ] Health：Assembly = Yes，Mapping = Yes
[ ] Verify Faces：全部 Verified
[ ] Common Base：ok / base ready
[ ] 检查 Orientation：全部 Match = Yes
[ ] Replay Layout
[ ] Replay Check：matched
[ ] 检查每个组件 XY error / Theta error
[ ] 在 SolidWorks UI 中与参考装配体对照
[ ] 保存目标装配体
```

## 14. 常用排障命令

### 14.1 检查端口

```cmd
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

终止确认后的单个进程：

```cmd
taskkill /PID 12345 /F
```

不要写成：

```cmd
taskkill /PID 12345 /F:
```

### 14.2 检查 MCP Hub

```cmd
scripts\check_mcp_hub.cmd
```

### 14.3 检查后端

```cmd
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:8000/api/demo/mcp-health
```

### 14.4 查看当前状态

```cmd
type demo\demo_state.json
```

### 14.5 查看面映射

```cmd
type artifacts\solidworks-mcp\face_mappings.json
```

### 14.6 查看 Layout JSON

```cmd
type demo\project_layout2d.json
```

## 15. 常见问题

### WinError 10048

8000 端口已有后端。不要重复启动，先访问 `/api/health`；确需重启时只终止占用 8000 的 PID。

### MCP server shut down unexpectedly

检查：

- SolidWorks 是否打开；
- Hub 是否存在；
- 是否有 SolidWorks 模态对话框；
- MCP DLL 是否完成 Release 构建；
- 面脚本和后端是否同时操作 SolidWorks；
- `DEMO_MCP_CWD` 是否正确。

### Initialize 按钮不可点击

常见原因是 `demo_state.json` 已有 `assemblyPath`。点击 Reset 前，先确认不会丢失需要保留的运行状态。

### Common Base 按钮不可点击

可能原因：

- 尚未 Initialize；
- 已经是 `base ready`；
- 当前仍处于 Busy。

### Replay 后位置正确但旋转错误

检查：

- JSON 是否包含 `thetaDegrees`；
- `thetaAxis` 是否存在；
- Result 中 `current/target/delta theta`；
- Replay Check 中 `thetaErrorDegrees`。

### 前端显示成功但 SolidWorks 看起来不正确

以以下四项联合判断：

1. MCP 返回状态；
2. Replay Check 数值；
3. Screenshot；
4. SolidWorks UI 中的真实底面、组件方向和配合。

## 16. 最短演示流程

如果底面映射和 Layout JSON 已经准备好，只需：

```text
启动 SolidWorks
→ 启动 MCP Hub
→ 启动后端
→ 启动前端
→ Reset
→ 选择 Layout JSON
→ Initialize
→ Health
→ Verify Faces
→ Common Base
→ Replay Layout
→ 检查 Replay Check
```

如果是第一次处理新的参考装配体，则必须先完成组件发现、底面记录/验证和 Generate Config。
