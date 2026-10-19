# 工艺语义约束布局

## 目标

在现有 `Gantry / Transport / Glue / Functional` 几何布局之上，增加扫描、CCD、校准、清洁和称重等工艺语义。只有二维几何约束和工艺硬约束均通过，才生成 Replay 兼容的 Layout2D。

该版本采用配置驱动的 2.5D 模型：组件已完成 Common Base；点位和区域使用组件底面中心为原点的局部 `U/V` 偏移，并随组件的 90° 离散旋转同步变换。

## 支持的模组类型

- `gantry`、`dispenser`
- `transport`、`return_transport`
- `glue_supply`
- `scanner`、`ccd`
- `calibration`、`cleaning`、`weighing`
- `carrier`、`functional`

模组类型会自动映射到现有几何角色；若 `roleOverrides` 与 `moduleType` 冲突，布局生成会被阻止。

粗复原还支持 `provisionalComponents`。占位组件使用公共底面坐标和长宽高生成临时包围盒，输出始终包含假设告警，并令 `validation.productionReady=false`。没有真实 `filePath` 的占位体只能参与求解，不能同步到 SolidWorks Replay。

## 语义配置示例

```json
{
  "moduleSemantics": {
    "gantry-1": {
      "moduleType": "gantry",
      "regions": {
        "dualValveReach": {"minU": -0.5, "minV": -0.3, "maxU": 0.5, "maxV": 0.3}
      },
      "allowedRotationDegrees": [0]
    },
    "transport-1": {
      "moduleType": "transport",
      "points": {
        "barcode": {"u": -0.4, "v": -0.05},
        "workPosition1": {"u": -0.15, "v": 0.0},
        "workPosition2": {"u": 0.15, "v": 0.0}
      },
      "allowedRotationDegrees": [0]
    },
    "scanner-1": {
      "moduleType": "scanner",
      "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
      "parameters": {"maxWorkingDistanceMeters": 0.3, "barcodeSide": "low"}
    },
    "ccd-1": {
      "moduleType": "ccd",
      "points": {"cameraOrigin": {"u": 0.0, "v": 0.0}},
      "regions": {
        "fieldOfView": {"minU": -0.2, "minV": -0.15, "maxU": 0.2, "maxV": 0.15}
      },
      "parameters": {"minWorkingDistanceMeters": 0.1, "maxWorkingDistanceMeters": 0.4}
    },
    "calibration-1": {
      "moduleType": "calibration",
      "points": {"servicePoint": {"u": 0.0, "v": 0.0}}
    },
    "cleaning-1": {
      "moduleType": "cleaning",
      "points": {"servicePoint": {"u": 0.0, "v": 0.0}},
      "parameters": {"isolationClearanceMeters": 0.1}
    },
    "weighing-1": {
      "moduleType": "weighing",
      "points": {"servicePoint": {"u": 0.0, "v": 0.0}}
    }
  },
  "provisionalComponents": [
    {
      "componentName": "weighing-1",
      "widthMeters": 0.22,
      "depthMeters": 0.22,
      "heightMeters": 0.20,
      "reason": "No verified weighing CAD",
      "replayable": false
    }
  ],
  "autoGenerateProcessConstraints": true,
  "processConstraints": []
}
```

## 约定点位与区域

| 模组 | 必需配置 |
|---|---|
| Scanner | `scanOrigin`、传输 `barcode`、`maxWorkingDistanceMeters`、`barcodeSide` |
| CCD | `cameraOrigin`、传输上的 `workPosition*` 或 `fiducial*`；并配置 `fieldOfView` 或最大工作距离 |
| Gantry | `dualValveReach`，或同时配置 `leftValveReach` 和 `rightValveReach` |
| Calibration/Cleaning/Weighing | `servicePoint` |

扫描条码、CCD工作点和服务点可由人工测量、PPT标注或后续CAD参考点采集获得。程序不会猜测真实设备工作距离。

## 自动生成的硬约束

1. 传输 `workPosition*`/`fiducial*` 位于双阀公共范围，或同时位于左右阀范围。
2. Scanner 与条码点满足最大距离、条码侧和二维视线无遮挡。
3. CCD 覆盖所有工作点，满足配置的工作距离、二维视场和视线无遮挡。
4. 校准、清洁和称重的 `servicePoint` 位于阀头可达区域。
5. 清洁模组与 CCD、称重模组满足隔离间距。

移动式 CCD 可配置 `parameters.movingAxisCoverage=true`。此时 `fieldOfView` 表达运动轴覆盖区，程序不会生成错误的固定相机二维视线约束；19 × 14.25 mm 等单次曝光光学视场应作为设备参数另外保存。

Portal 或支架式组件使用整体包围盒时，可能与传输产生正常的二维投影重叠。经方案确认后可为对应语义模块设置 `parameters.allowTransportProjectionOverlap=true`；这只允许二维候选继续求解，输出仍会要求 SolidWorks 三维干涉复核。

清洁隔离默认使用模块包围盒。若 CCD 是跨线 Portal、包围盒包含大量空区，可设置 `parameters.isolationMode="servicePoints"`，改为检查清洁服务点与相机/称重服务点之间的距离。

## 显式约束类型

- `pointDistance`：两点最小/最大距离。
- `pointInRegion`：组件点位必须进入另一组件的局部区域。
- `sameSide`：组件位于参考组件长轴或短轴的指定一侧。
- `moduleClearance`：两个二维包围盒之间的最小距离。
- `lineOfSight`：两点之间的二维线段不得穿过阻挡组件包围盒。

每条约束可设置 `hard`。硬约束失败时求解返回 `blocked`；软约束失败只进入诊断。

## 输出与验收

生成结果新增：

- `constraintPlan.moduleSemantics`
- `constraintPlan.processConstraints`
- `constraintPlan.processValidation`
- `constraintPlan.provisionalPlaceholderCount`
- `constraintPlan.assumptionWarnings`
- `constraintPlan.validation.processHardFeasible`
- `constraintPlan.validation.productionReady`

`validation.success=true` 现在表示几何非重叠与工艺硬约束均通过。前端显示 `process passed/total` 和 `hard-feasible` 状态。

## 真实项目初步映射（2026-08-05）

- A100：双阀点胶 XYZ 龙门，建议 `gantry`。
- A200：CCD 产品定位运动模组，建议 `ccd`，同时保留 A800 穿越其 Portal 的几何关系。
- A300：双接废胶杯，不是称重模组；当前暂用 `functional` 和显式服务点可达约束。
- A500：针头校准模组，建议 `calibration`。
- A700：自动针头清洁模组，建议 `cleaning`。
- A800：传输、载具定位及工作位总成，建议 `transport`。

完整证据和待确认项见 `docs/module_identification-CN.md`。

## 当前边界

- 视场、视线和距离均为 Common Base 平面上的 2.5D近似，尚未替代三维光锥和实体最小距离检查。
- 现有放置器会使用语义侧面偏好和允许旋转，但仍是规则式放置，不是完整 CP-SAT 全局搜索。
- 已完成七组件中 Gantry/CCD/Calibration/Cleaning/Transport/排胶杯的初步映射；Scanner 和 Weighing 尚未确认是独立顶层组件还是父装配内部机构。
- 真实项目仍缺设备工作距离、阀头行程和局部点位数据。

## 真实粗求解闭环（2026-08-05）

运行：

```powershell
python scripts\generate_coarse_process_layout.py
```

当前输出为 `demo/FL9A24D062A000_coarse_process_layout2d.json`：8 个对象、11/11 工艺硬约束通过、非允许碰撞为 0。称重占位体不可 Replay，Scanner/A600 仍未纳入，因此结果只属于 `provisional/coarse`。

## A180 Scanner 与 A700 组合模组闭环（2026-08-05）

真实项目映射已更新为：`A180=scanner`；`A700=cleaning + weighing`，其中 A730 为称重子模组。新请求不再注入称重占位体。A700 暂以 `moduleType=cleaning` 保存单一实体语义，并用 `parameters.combinedFunctions=["cleaning","weighing"]` 标记组合功能；显式硬约束复用其共享粗服务点检查称重可达性。

新增两项通用能力：

- 任何模组设置 `parameters.provisional=true` 时，输出会列入 `assumptionWarnings`，并自动令 `productionReady=false`，避免“真实 CAD 已齐全”被误报为生产级参数已验证。
- Portal 框架或具有明确高度分层的组件可设置 `lineOfSightTransparent=true`，仅跳过 2.5D AABB 的假遮挡；Scanner 的视线硬约束仍保留，后续必须以三维光锥复核。

当前真实粗闭环输出为 `demo/FL9A24D062A000_real_process_layout2d.json`：8 个真实 CAD 对象、13/13 工艺硬约束通过、非法重叠为 0、允许投影重叠为 3、无占位体。Replay 输出及验收脚本分别为 `demo/FL9A24D062A000_8components_real_process_replay.SLDASM` 和 `scripts/validate_real_process_closure.py`。
