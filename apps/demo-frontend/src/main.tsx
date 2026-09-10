import React, { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AlertTriangle, Boxes, CheckCircle2, Crosshair, Eye, FileJson, Layers, Loader2, MapPinned, Move3D, Play, RefreshCw, RotateCcw, Save, Upload, XCircle } from "lucide-react";
import {
  applyCapturedLayout,
  approveProjectCasePreview,
  arrange,
  captureCommonBaseLayout,
  captureProjectLayout,
  confirmProjectCaseModules,
  ConstraintRole,
  DemoComponent,
  DemoState,
  discoverComponents,
  DiscoveredComponent,
  DiscoveryResult,
  finalizeCommonBase,
  generateConstraintLayout,
  getMcpHealth,
  getProjectCasePreview,
  getProject02DependencyAblation,
  getProjectMigrationReadiness,
  getProjectCaseVerificationPlan,
  getState,
  initializeCommonBase,
  LayoutComponentSummary,
  LayoutJsonInfo,
  LayoutVerificationPlan,
  McpHealthResult,
  ModuleSemanticInput,
  listLayoutJsonFiles,
  OperationResult,
  OrientationCheck,
  OrientationCorrection,
  parseArrangePayload,
  ProvisionalComponentInput,
  ProjectCasePreview,
  Project02DependencyAblationBundle,
  ProjectMigrationReadiness,
  ProjectModuleConfirmationResult,
  ProjectModuleRecommendationResult,
  PreviewModule,
  resetState,
  recommendProjectCaseModules,
  saveState,
  selectLayoutJson,
  solveProjectCasePreview,
  syncDiscoveredComponents,
  uploadLayoutJson,
  verifyFaceMappings
} from "./api";
import "./styles.css";
import { FaceEndpointWorkbench } from "./FaceEndpointWorkbench";

type Axis = "x" | "y" | "z";

type WorldBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
};

type BlockSpec = {
  width: number;
  height: number;
  color: string;
};

const DEFAULT_WORLD_BOUNDS: WorldBounds = {
  minX: -0.1,
  maxX: 0.8,
  minY: -0.3,
  maxY: 0.3
};

const BLOCK_SPECS: Record<string, BlockSpec> = {
  a: { width: 0.14, height: 0.1, color: "#2f80ed" },
  b: { width: 0.16, height: 0.12, color: "#10a37f" },
  c: { width: 0.13, height: 0.11, color: "#d97706" }
};

const BLOCK_COLORS = ["#2f80ed", "#10a37f", "#d97706", "#7c3aed", "#dc2626", "#0891b2", "#4d7c0f", "#be185d"];

function blockSpec(component: DemoComponent): BlockSpec {
  const fallbackIndex = Math.abs(hashText(component.id || component.componentName)) % BLOCK_COLORS.length;
  return BLOCK_SPECS[component.id] ?? { width: 0.14, height: 0.1, color: BLOCK_COLORS[fallbackIndex] };
}

function hashText(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function cloneWithTarget(state: DemoState, id: string, axis: Axis, value: number): DemoState {
  return {
    ...state,
    components: state.components.map((component) =>
      component.id === id
        ? {
            ...component,
            target: {
              ...component.target,
              [axis]: value
            }
          }
        : component
    )
  };
}

function cloneWithXYTarget(state: DemoState, id: string, x: number, y: number): DemoState {
  return {
    ...state,
    components: state.components.map((component) =>
      component.id === id
        ? {
            ...component,
            target: {
              ...component.target,
              x,
              y
            }
          }
        : component
    )
  };
}

function numberValue(value: number): string {
  return Number.isFinite(value) ? String(value) : "0";
}

function roundMeters(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function expandBounds(bounds: WorldBounds, minimumSize = 0.4, paddingRatio = 0.18): WorldBounds {
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const width = Math.max(bounds.maxX - bounds.minX, minimumSize);
  const height = Math.max(bounds.maxY - bounds.minY, minimumSize);
  const paddedWidth = width * (1 + paddingRatio * 2);
  const paddedHeight = height * (1 + paddingRatio * 2);
  return {
    minX: centerX - paddedWidth / 2,
    maxX: centerX + paddedWidth / 2,
    minY: centerY - paddedHeight / 2,
    maxY: centerY + paddedHeight / 2
  };
}

function computeWorldBounds(state: DemoState | null): WorldBounds {
  if (!state) return DEFAULT_WORLD_BOUNDS;

  const points: Array<{ x: number; y: number }> = [];
  for (const component of state.components) {
    points.push({ x: component.target.x, y: component.target.y });
    const layout = layoutFor(component, state.layoutInfo);
    if (layout?.layout2d) {
      points.push({ x: layout.layout2d.x, y: layout.layout2d.y });
    }
  }

  const valid = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (!valid.length) return DEFAULT_WORLD_BOUNDS;

  return expandBounds({
    minX: Math.min(...valid.map((point) => point.x)),
    maxX: Math.max(...valid.map((point) => point.x)),
    minY: Math.min(...valid.map((point) => point.y)),
    maxY: Math.max(...valid.map((point) => point.y))
  });
}

function formatVector(values?: number[] | null): string {
  if (!values?.length) {
    return "n/a";
  }
  return values.map((value) => value.toFixed(4)).join(", ");
}

function formatNumber(value?: number | null, digits = 4): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

function formatHealthBool(value?: boolean | null): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "n/a";
}

function shortPath(value?: string | null): string {
  if (!value) return "No layout";
  const normalized = value.replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.slice(-2).join("/");
}

function discoveryKey(component: DiscoveredComponent): string {
  return `${component.hierarchyPath || component.componentName}::${component.componentName}`;
}

function layoutFor(component: DemoComponent, layoutInfo?: LayoutJsonInfo | null): LayoutComponentSummary | null {
  return layoutInfo?.components.find((item) => item.componentName === component.componentName) ?? null;
}

function StatusIcon({ ok }: { ok?: boolean }) {
  if (ok) {
    return <CheckCircle2 className="status-icon ok" aria-hidden="true" />;
  }
  return <XCircle className="status-icon bad" aria-hidden="true" />;
}

function CoordinateInput({
  component,
  axis,
  onChange
}: {
  component: DemoComponent;
  axis: Axis;
  onChange: (value: number) => void;
}) {
  return (
    <input
      aria-label={`${component.componentName} target ${axis}`}
      className="coord-input"
      inputMode="decimal"
      type="number"
      step="0.01"
      value={numberValue(component.target[axis])}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );
}

function LayoutCanvas({
  state,
  worldBounds,
  disabled,
  onMove
}: {
  state: DemoState;
  worldBounds: WorldBounds;
  disabled: boolean;
  onMove: (id: string, x: number, y: number) => void;
}) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const worldWidth = worldBounds.maxX - worldBounds.minX;
  const worldHeight = worldBounds.maxY - worldBounds.minY;

  function toScreenX(worldX: number): number {
    return ((worldX - worldBounds.minX) / worldWidth) * 100;
  }

  function toScreenY(worldY: number): number {
    return ((worldBounds.maxY - worldY) / worldHeight) * 100;
  }

  function pointerToWorld(event: PointerEvent<HTMLDivElement>) {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) {
      return null;
    }

    const localX = clamp(event.clientX - rect.left, 0, rect.width);
    const localY = clamp(event.clientY - rect.top, 0, rect.height);
    const worldX = worldBounds.minX + (localX / rect.width) * worldWidth;
    const worldY = worldBounds.maxY - (localY / rect.height) * worldHeight;
    return {
      x: roundMeters(worldX),
      y: roundMeters(worldY)
    };
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!draggingId || disabled) {
      return;
    }
    const point = pointerToWorld(event);
    if (!point) {
      return;
    }
    onMove(draggingId, point.x, point.y);
  }

  function handlePointerUp(event: PointerEvent<HTMLDivElement>) {
    if (draggingId) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDraggingId(null);
  }

  return (
    <div className="panel canvas-panel">
      <div className="panel-heading">
        <h2>2D layout</h2>
        <span>
          X {formatNumber(worldBounds.minX, 3)}..{formatNumber(worldBounds.maxX, 3)} m, Y {formatNumber(worldBounds.minY, 3)}..
          {formatNumber(worldBounds.maxY, 3)} m
        </span>
      </div>
      <div
        ref={canvasRef}
        className="layout-canvas"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div className="axis x-axis" style={{ top: `${clamp(toScreenY(0), 0, 100)}%` }} />
        <div className="axis y-axis" style={{ left: `${clamp(toScreenX(0), 0, 100)}%` }} />
        {state.components.map((component) => {
          const spec = blockSpec(component);
          const widthPercent = clamp((spec.width / worldWidth) * 100, 4, 24);
          const heightPercent = clamp((spec.height / worldHeight) * 100, 4, 24);
          return (
            <button
              key={component.id}
              className={`layout-block ${draggingId === component.id ? "dragging" : ""}`}
              type="button"
              disabled={disabled}
              style={{
                left: `${toScreenX(component.target.x)}%`,
                top: `${toScreenY(component.target.y)}%`,
                width: `${widthPercent}%`,
                height: `${heightPercent}%`,
                backgroundColor: spec.color
              }}
              onPointerDown={(event) => {
                if (disabled) {
                  return;
                }
                event.currentTarget.setPointerCapture(event.pointerId);
                setDraggingId(component.id);
              }}
            >
              <strong>{component.componentName}</strong>
              <span>
                {component.target.x.toFixed(3)}, {component.target.y.toFixed(3)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Project02RequirementPanel({
  requirement,
  recommendation,
  selectedModuleCodes,
  confirmation,
  busy,
  onRequirementChange,
  onRecommend,
  onToggleModule,
  onConfirm
}: {
  requirement: string;
  recommendation: ProjectModuleRecommendationResult | null;
  selectedModuleCodes: string[];
  confirmation: ProjectModuleConfirmationResult | null;
  busy: boolean;
  onRequirementChange: (value: string) => void;
  onRecommend: () => void;
  onToggleModule: (code: string) => void;
  onConfirm: () => void;
}) {
  const selected = new Set(selectedModuleCodes);
  return (
    <section className="panel requirement-recommendation-panel">
      <div className="requirement-header">
        <div>
          <span className="eyebrow">需求 → 模组</span>
          <h2>项目02 · 需求驱动模组推荐</h2>
          <p>规则引擎提取能力、补齐依赖，并区分必选与可选模组；确认完整八模组基线后进入现有布局求解。</p>
        </div>
        <button className="primary-button" type="button" onClick={onRecommend} disabled={busy || !requirement.trim()}>
          {busy ? <Loader2 className="spin" aria-hidden="true" /> : <Boxes aria-hidden="true" />}
          解析需求并推荐
        </button>
      </div>
      <div className="requirement-input-row">
        <textarea
          value={requirement}
          disabled={busy}
          rows={3}
          onChange={(event) => onRequirementChange(event.target.value)}
          placeholder="例如：每个载具4个产品，需要双阀环氧胶点胶、扫码追溯、CCD视觉定位、喷嘴校准、清洁、称重和排胶。"
        />
      </div>

      {recommendation ? (
        <>
          <div className="requirement-summary-row">
            <div>
              <span>能力覆盖</span>
              <strong>{recommendation.coverage.coveredCapabilityCount}/{recommendation.coverage.requiredCapabilityCount}</strong>
            </div>
            <div>
              <span>必选模组</span>
              <strong>{recommendation.requiredModuleCodes.length}</strong>
            </div>
            <div>
              <span>可选模组</span>
              <strong>{recommendation.optionalModuleCodes.length}</strong>
            </div>
            <div className={recommendation.layoutCompatibility.compatible ? "good" : "warn"}>
              <span>当前求解器</span>
              <strong>{recommendation.layoutCompatibility.compatible ? "可衔接" : "子集待支持"}</strong>
            </div>
          </div>
          <div className="capability-strip">
            {recommendation.capabilities.map((capability) => (
              <span className={capability.source} key={capability.id} title={capability.evidence.join("、") || `由 ${capability.requiredBy} 依赖补齐`}>
                {capability.label}<small>{capability.source === "explicit" ? "需求" : "依赖"}</small>
              </span>
            ))}
          </div>
          <div className="recommended-module-grid">
            {recommendation.modules.map((module) => {
              const checked = selected.has(module.code);
              return (
                <label className={`recommended-module ${module.status} ${checked ? "selected" : ""}`} key={module.code}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={busy || module.required}
                    onChange={() => onToggleModule(module.code)}
                  />
                  <span className="module-code">{module.code}</span>
                  <span className="module-copy">
                    <strong>{module.label}</strong>
                    <small>{module.reasons.join("；") || "当前需求未选择"}</small>
                  </span>
                  <span className={`module-status ${module.status}`}>
                    {module.status === "required" ? "必选" : module.status === "optional" ? "可选" : "未选择"}
                  </span>
                </label>
              );
            })}
          </div>
          {recommendation.missingInformation.length ? (
            <div className="requirement-warnings">
              {recommendation.missingInformation.map((message) => <span key={message}>{message}</span>)}
            </div>
          ) : null}
          <div className="requirement-confirm-row">
            <div>
              <strong>{recommendation.layoutCompatibility.message}</strong>
              <span>当前选择：{selectedModuleCodes.join("、") || "无"}</span>
            </div>
            <button className="primary-button" type="button" disabled={busy || selectedModuleCodes.length === 0} onClick={onConfirm}>
              {busy ? <Loader2 className="spin" aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
              确认模组并进入求解
            </button>
          </div>
          {confirmation ? (
            <div className={`module-confirmation ${confirmation.layoutSolverReady ? "good" : confirmation.accepted ? "warn" : "bad"}`}>
              <strong>{confirmation.message}</strong>
              {confirmation.missingForCurrentSolver.length ? <span>当前八模组求解还缺：{confirmation.missingForCurrentSolver.join("、")}</span> : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function ProjectMigrationReadinessPanel({ readiness, projectLabel }: { readiness: ProjectMigrationReadiness | null; projectLabel: string }) {
  if (!readiness) return null;
  const firstStageCaptured = readiness.status === "PROJECT03_FIRST_STAGE_GEOMETRY_READY_FURTHER_EXTRACTION_REQUIRED";
  const groupLabels: Record<string, string> = {
    "frame-context": "固定环境：机架＋回流",
    "transport-process-group": "输送主模组",
    "flip-positioning-module": "翻转定位模组",
    "gantry-motion-group": "点胶运动组：龙门＋双阀头",
    "combined-service-module": "组合功能模组",
    "calibration-module": "标定模组",
    "scanner-module": "扫码模组",
    "glue-supply-module": "供胶模组"
  };
  const extractionLabels: Record<string, string> = {
    "JJ00 operation face and top installation surface": "JJ00操作面与顶部安装面",
    "JJ00-SS00 transport installation frame plus SS00/FF00 work stations": "JJ00-SS00安装基准及SS00/FF00工位",
    "SM00 optical origin/axis and carrier barcode face": "SM00光学原点/轴线与载具条码面",
    "GN00 four function ports and BD00 calibration point": "GN00四功能端口与BD00标定点",
    "LM00/ZZ00 dual-valve reach": "LM00/ZZ00双阀公共行程",
    "exact JJ00 operation-face confirmation": "确认JJ00精确操作面",
    "module/subtree occupancy and collision-pair classification": "模组/子树占用体与碰撞对分类",
    "AA00 operation face and AA00-AE00 transport installation frame": "AA00操作面与AA00-AE00输送安装基准",
    "AE00/AD00 work positions": "AE00/AD00输送与旋转工位",
    "AI00 optical axis and barcode side": "AI00扫码光轴与条码侧",
    "resolve AI00 carrier barcode/RFID evidence": "核清AI00载具条码/RFID证据",
    "AG00 function ports and AH00 calibration point": "AG00功能端口与AH00标定点",
    "AB00/AC00 dual-valve common reach": "AB00/AC00双阀公共行程",
    "exact AA00 operation-face and capacity confirmation": "确认AA00精确操作面与维护容量"
  };
  const missingLabels: Record<string, string> = {
    baseOperationFace: "机架操作面",
    baseTopInstallationSurface: "顶部安装面",
    transportInstallationFrame: "输送安装基准",
    transportWorkPositions: "输送/翻转工位",
    barcodeFaceAndSide: "条码面与所在侧",
    scannerWorkingDistanceAndAxis: "扫码光轴与工作距离",
    dualValveReach: "双阀公共行程",
    calibrationServicePoint: "标定服务点",
    combinedServiceFunctionPoints: "组合功能模组四服务点",
    operationSideCapacity: "操作侧可用空间",
    moduleOccupancy: "模组多包围盒占用体",
    staticCollisionPolicy: "静态碰撞对分类"
  };
  return (
    <section className="panel migration-readiness-panel">
      <div className="requirement-header">
        <div>
          <span className="eyebrow">跨案例迁移门禁</span>
          <h2>{projectLabel} · 参数包与通用约束就绪度</h2>
          <p>只使用{projectLabel}原型的数值证据，按通用工艺顺序和分级碰撞策略决定是否允许生成Top-3。</p>
        </div>
        <span className={`migration-gate ${readiness.top3SolveReady ? "ready" : "blocked"}`}>
          {readiness.top3SolveReady ? "Top-3可求解" : firstStageCaptured ? "首阶段几何已恢复" : "待几何采集"}
        </span>
      </div>
      <div className="requirement-summary-row">
        <div><span>模组CAD解析</span><strong>{readiness.resolvedModuleCadCount}/{readiness.moduleCount}</strong></div>
        <div><span>顶层求解对象</span><strong>{readiness.proposedTopLevelSolveObjects.length}</strong></div>
        <div><span>缺失硬证据</span><strong>{readiness.missingRequiredEvidence.length}</strong></div>
        <div><span>部分证据</span><strong>{readiness.partialEvidence.length}</strong></div>
        <div className={readiness.project02NumericParametersInherited ? "warn" : "good"}>
          <span>项目02数值复用</span><strong>{readiness.project02NumericParametersInherited ? "存在" : "已隔离"}</strong>
        </div>
      </div>
      {readiness.firstStageGeometry ? (
        <div className="migration-evidence">
          <strong>已恢复项目03安装与拓扑基线</strong>
          <div>
            <span>AA00–AE00定位孔距 {formatNumber(readiness.firstStageGeometry.transportInstallationInterface.locatingHoleSpacingMeters * 1000, 0)} mm</span>
            <span>{readiness.firstStageGeometry.mateGraphSummary.interModuleMateCount} 条跨模组配合 / {readiness.firstStageGeometry.mateGraphSummary.mateBundleCount} 组连接</span>
            <span>{readiness.firstStageGeometry.topLevelOccupancy.majorModuleCount} 个主要模组 + {readiness.firstStageGeometry.topLevelOccupancy.looseAuxiliaryInstanceCount} 个辅助散件</span>
            <span>操作面候选 {readiness.firstStageGeometry.operationSideInference.candidate}（{readiness.firstStageGeometry.operationSideInference.confidence}置信度）</span>
          </div>
        </div>
      ) : null}
      {readiness.workPositions ? (
        <div className="migration-evidence">
          <strong>已恢复项目03双工作位</strong>
          <div>
            <span>AD10工作站 × {readiness.workPositions.workPositionCount}</span>
            <span>中心间距 {formatNumber(readiness.workPositions.centerSeparationMeters * 1000, 0)} mm</span>
            <span>
              U = {readiness.workPositions.workPositions.map((item) => (item.installationFramePointMeters.u * 1000).toFixed(0)).join(" / ")} mm
            </span>
            {readiness.workPositions.geometricConsistency ? (
              <span>AE90夹持中点最大偏差 {formatNumber(readiness.workPositions.geometricConsistency.maximumGuardMidpointDeltaMeters * 1000, 1)} mm</span>
            ) : null}
            {readiness.workPositions.pptProcessEvidence ? (
              <span>PPT工艺：举升＋{formatNumber(readiness.workPositions.pptProcessEvidence.rotationAngleDegrees, 0)}°旋转</span>
            ) : null}
          </div>
          <small>按低U/高U稳定命名；实际A/B编号仍待输送入口方向或PLC站号确认。</small>
        </div>
      ) : null}
      <div className="migration-group-grid">
        {readiness.layoutObjectGroups.map((group) => (
          <div className="migration-group" key={group.id}>
            <strong>{groupLabels[group.id] ?? group.id}</strong>
            <span>{group.memberCadIds.join(" + ")}</span>
            <small>{group.placementMode}</small>
          </div>
        ))}
      </div>
      {readiness.scannerGeometry ? (
        <div className="migration-evidence">
          <strong>已恢复扫描工艺基线</strong>
          <div>
            <span>{readiness.scannerGeometry.scannerModel} × {readiness.scannerGeometry.scannerCount}</span>
            <span>{readiness.scannerGeometry.processSummary ?? "载具侧扫 + 产品上扫"}</span>
            <span>
              原型CAD光束 {formatNumber(readiness.scannerGeometry.scanners[0]?.modeledWorkingDistanceMeters != null
                ? readiness.scannerGeometry.scanners[0].modeledWorkingDistanceMeters * 1000
                : null, 0)} mm
            </span>
            {readiness.scannerGeometry.barcodeInterfaces?.carrierBarcode ? (
              <span>载具条码证据：{readiness.scannerGeometry.barcodeInterfaces.carrierBarcode.status}</span>
            ) : null}
          </div>
          {readiness.scannerGeometry.barcodeInterfaces?.carrierBarcode?.reason ? (
            <small>{readiness.scannerGeometry.barcodeInterfaces.carrierBarcode.reason}</small>
          ) : null}
        </div>
      ) : null}
      {readiness.servicePoints ? (
        <div className="migration-evidence">
          <strong>已恢复功能服务端口</strong>
          <div>
            <span>{readiness.servicePoints.combinedServiceModule.cadId?.match(/A[A-Z]00/)?.[0] ?? "GN00"} {readiness.servicePoints.combinedServiceModule.functionCount} 类功能 / {readiness.servicePoints.combinedServiceModule.reachTargetCount} 个阀头目标</span>
            <span>{readiness.servicePoints.calibrationModule.cadId?.match(/A[A-Z]00/)?.[0] ?? "BD00"} 标定目标 × {readiness.servicePoints.calibrationModule.reachTargetCount}</span>
            <span>共 {readiness.servicePoints.servicePorts.length} 个粗布局可达点</span>
          </div>
        </div>
      ) : null}
      {readiness.dualValveReach ? (
        <div className="migration-evidence">
          <strong>已建立双阀原型行程基线</strong>
          <div>
            <span>公共范围 {formatNumber(readiness.dualValveReach.commonReachInstallationFrameMeters.widthU * 1000, 0)} × {formatNumber(readiness.dualValveReach.commonReachInstallationFrameMeters.widthV * 1000, 0)} mm</span>
            <span>阀间距 {formatNumber(readiness.dualValveReach.valvePair.spacingAlongFlowMeters * 1000, 0)} mm</span>
            <span>{readiness.dualValveReach.requiredTargetCount} 个目标全部可达</span>
          </div>
        </div>
      ) : null}
      {readiness.moduleOccupancy ? (
        <div className="migration-evidence">
          <strong>已建立分级静态碰撞门禁</strong>
          <div>
            <span>{readiness.moduleOccupancy.coverage.layoutObjectCount} 个布局对象 / {readiness.moduleOccupancy.staticCollisionPolicy.pairCount} 组对象对全覆盖</span>
            {readiness.moduleOccupancy.coverage.capturedLeafBodyCount !== undefined ? <span>{readiness.moduleOccupancy.coverage.capturedLeafBodyCount} 个叶实体包围盒</span> : null}
            <span>{readiness.moduleOccupancy.staticCollisionPolicy.strictMultiAabbPairs.length} 组严格多包围盒</span>
            <span>{readiness.moduleOccupancy.staticCollisionPolicy.conditionalBrepPairs.length} 组条件 B-rep</span>
            <span>{readiness.moduleOccupancy.staticCollisionPolicy.installationContactPairs.length} 组安装接触</span>
            <span>求解阶段 B-rep：{readiness.moduleOccupancy.staticCollisionPolicy.solverInvokesBrep ? "启用" : "不启用"}</span>
          </div>
        </div>
      ) : null}
      {readiness.missingRequiredEvidence.length || readiness.partialEvidence.length ? (
        <div className="migration-evidence">
          <strong>进入首轮求解前仍需补齐或确认</strong>
          <div>
            {readiness.missingRequiredEvidence.map((item) => <span key={item}>{missingLabels[item] ?? item}</span>)}
            {readiness.partialEvidence.map((item) => <span key={`partial-${item}`}>{missingLabels[item] ?? item}（部分证据）</span>)}
          </div>
        </div>
      ) : (
        <div className="migration-evidence">
          <strong>粗布局输入已闭环</strong>
          <div><span>下一步：快速生成Top-3 → 展示层目测 → 仅对选中方案Replay与条件B-rep</span></div>
        </div>
      )}
      {readiness.nextExtractionOrder.length ? <p className="migration-next">优先顺序：{readiness.nextExtractionOrder.map((item) => extractionLabels[item] ?? item).join(" → ")}</p> : null}
    </section>
  );
}

type A600InstallationGeometryView = NonNullable<
  NonNullable<ProjectCasePreview["assemblySequencePlan"]>["installationGeometry"]
>;

function A600InstallationMap({ geometry }: { geometry: A600InstallationGeometryView }) {
  const boundary = geometry.installationPlatform?.safeBoundary;
  if (!boundary || boundary.minX === undefined || boundary.minY === undefined || boundary.maxX === undefined || boundary.maxY === undefined) {
    return null;
  }
  const width = Math.max(1e-6, boundary.maxX - boundary.minX);
  const height = Math.max(1e-6, boundary.maxY - boundary.minY);
  const px = (value: number) => 18 + ((value - boundary.minX) / width) * 284;
  const py = (value: number) => 148 - ((value - boundary.minY) / height) * 128;
  const support = geometry.transportSupportRegion;
  return (
    <div className="a600-installation-map">
      <svg viewBox="0 0 320 168" role="img" aria-label="A600上部安装区与结构禁入区">
        <rect x="18" y="20" width="284" height="128" className="a600-safe-boundary" />
        {support && support.minX !== undefined && support.minY !== undefined && support.maxX !== undefined && support.maxY !== undefined ? (
          <rect
            x={px(support.minX)}
            y={py(support.maxY)}
            width={Math.max(1, px(support.maxX) - px(support.minX))}
            height={Math.max(1, py(support.minY) - py(support.maxY))}
            className="a600-transport-support"
          />
        ) : null}
        {(geometry.hardKeepoutRegions ?? []).map((item, index) => (
          <rect
            key={`${item.minX}-${item.minY}-${index}`}
            x={px(item.minX)}
            y={py(item.maxY)}
            width={Math.max(1, px(item.maxX) - px(item.minX))}
            height={Math.max(1, py(item.minY) - py(item.maxY))}
            className="a600-hard-keepout"
          />
        ))}
        <line x1="18" y1="20" x2="18" y2="148" className="a600-operation-face" />
        <text x="22" y="16">操作面 / front</text>
        <text x="184" y="163">A600工程坐标 X → 机内</text>
      </svg>
      <div><span className="safe">安全安装边界</span><span className="support">A800支承区</span><span className="keepout">结构禁入区</span></div>
    </div>
  );
}

function ProjectCasePreviewPanel({
  caseId,
  preview,
  solving,
  approving,
  approval,
  onSolve,
  onApprove,
  approvalEnabled = true,
  solveButtonLabel
}: {
  caseId: "project01" | "project02" | "project03";
  preview: ProjectCasePreview | null;
  solving: boolean;
  approving: boolean;
  approval: LayoutVerificationPlan | null;
  onSolve: () => void;
  onApprove: (solutionRank: number) => void;
  approvalEnabled?: boolean;
  solveButtonLabel?: string;
}) {
  const isProject01 = caseId === "project01";
  const isProject03 = caseId === "project03";
  const isProject02 = caseId === "project02";
  const caseLabel = isProject01 ? "项目01" : isProject03 ? "项目03" : "项目02";
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedSolutionRank, setSelectedSolutionRank] = useState(1);
  const [visualReviewChecked, setVisualReviewChecked] = useState(false);
  useEffect(() => {
    setSelectedSolutionRank(1);
    setSelectedName(null);
    setVisualReviewChecked(false);
  }, [preview?.generatedAt]);
  const activeSolution = preview?.solutions?.find((item) => item.rank === selectedSolutionRank);
  const activeModules = activeSolution?.modules ?? preview?.modules ?? [];
  const activeLeafRisks = activeSolution?.conditionalLeafAabbRisks ?? preview?.conditionalLeafAabbRisks ?? [];
  const activeLeafHitCount = activeSolution?.predictedConditionalLeafAabbHitCount
    ?? preview?.metrics.predictedConditionalLeafAabbHitCount
    ?? 0;
  const visibleReviewItems = (preview?.reviewItems ?? []).filter((item) =>
    (!isProject01 && !isProject03) || !["传输模组中心性", "2.5D交互复核"].includes(item.title)
  );
  const selected = activeModules.find((item) => item.componentName === selectedName) ?? null;
  const width = 1000;
  const height = 560;
  const padding = 44;
  const bounds = preview?.viewBounds;
  const worldWidth = Math.max((bounds?.maxU ?? 1) - (bounds?.minU ?? -1), 0.001);
  const worldHeight = Math.max((bounds?.maxV ?? 1) - (bounds?.minV ?? -1), 0.001);
  const scale = Math.min((width - padding * 2) / worldWidth, (height - padding * 2) / worldHeight);
  const drawingWidth = worldWidth * scale;
  const drawingHeight = worldHeight * scale;
  const offsetX = (width - drawingWidth) / 2;
  const offsetY = (height - drawingHeight) / 2;

  function toX(value: number): number {
    return offsetX + (value - (bounds?.minU ?? -1)) * scale;
  }

  function toY(value: number): number {
    return offsetY + ((bounds?.maxV ?? 1) - value) * scale;
  }

  function moduleRect(module: PreviewModule) {
    const [minU, minV, maxU, maxV] = module.bounds;
    return {
      x: toX(minU),
      y: toY(maxV),
      width: Math.max((maxU - minU) * scale, 2),
      height: Math.max((maxV - minV) * scale, 2)
    };
  }

  const orderedModules = useMemo(
    () => [...activeModules].sort((first, second) => {
      const order = (item: PreviewModule) => item.moduleType === "frame" ? -1 : item.moduleType === "gantry" ? 0 : item.moduleType === "ccd" ? 1 : 2;
      return order(first) - order(second);
    }),
    [activeModules]
  );
  const gantry = activeModules.find((item) => item.moduleType === "gantry");
  const overlapReviewLabels = (preview?.allowedOverlapPairs ?? []).map((pair) =>
    pair.map((componentName) =>
      activeModules.find((item) => item.componentName === componentName)?.code ?? componentName
    ).join(" ↔ ")
  );
  const gantryShortCenter = gantry
    ? preview?.longAxis === "u"
      ? (gantry.bounds[1] + gantry.bounds[3]) / 2
      : (gantry.bounds[0] + gantry.bounds[2]) / 2
    : null;

  return (
    <section className="panel project-preview-panel">
      <div className="project-preview-header">
        <div>
          <span className="eyebrow">快速迭代闭环</span>
          <h2>{caseLabel} · 顺序约束求解方案展示</h2>
          <p>{isProject01 ? "SS00/FF00按项目01安装基准固定，服务模组先排布，最后反求LM00+ZZ00覆盖。" : isProject03 ? "AE00按AA00安装基准固定，AD00/AI00与服务模组先排布，最后反求AB00+AC00覆盖。" : "A800由A600工程安装坐标中的显式基准点定位；其余模组由几何、工艺点与通用约束求解。"}</p>
        </div>
        <button className="primary-button preview-solve-button" type="button" onClick={onSolve} disabled={solving}>
          {solving ? <Loader2 className="spin" aria-hidden="true" /> : <Crosshair aria-hidden="true" />}
          {solveButtonLabel ?? (preview ? "重新求解并刷新" : `求解${caseLabel}`)}
        </button>
      </div>

      {!preview ? (
        <div className="preview-empty">
          <Eye aria-hidden="true" />
          <strong>尚未生成预览</strong>
          <span>点击“求解{caseLabel}”，无需启动SolidWorks即可查看预计布局。</span>
        </div>
      ) : (
        <>
          <div className="preview-metrics" aria-label="求解指标">
            <div className={preview.metrics.hardFeasible ? "metric good" : "metric bad"}>
              <span>硬约束</span>
              <strong>{preview.metrics.hardFeasible ? "通过" : "失败"}</strong>
            </div>
            <div className="metric">
              <span>工艺约束</span>
              <strong>{preview.metrics.processPassed}/{preview.metrics.processTotal}</strong>
            </div>
            <div className="metric">
              <span>空间约束</span>
              <strong>{preview.metrics.spatialPassed}/{preview.metrics.spatialTotal}</strong>
            </div>
            <div className={preview.metrics.interactionPassed === preview.metrics.interactionTotal ? "metric good" : "metric bad"}>
              <span>2.5D交互</span>
              <strong>{preview.metrics.interactionPassed}/{preview.metrics.interactionTotal}</strong>
            </div>
            {isProject02 ? <div className={(preview.metrics.fixedEnvironmentPassed ?? 0) === (preview.metrics.fixedEnvironmentTotal ?? -1) ? "metric good" : "metric bad"}>
              <span>A600固定环境</span>
              <strong>{preview.metrics.fixedEnvironmentPassed ?? 0}/{preview.metrics.fixedEnvironmentTotal ?? 0}</strong>
            </div> : null}
            {isProject02 ? <div className={(preview.metrics.transportCenterOffsetMeters ?? 0) <= 0.05 ? "metric good" : "metric warn"}>
              <span>传输中心偏差</span>
              <strong>{((preview.metrics.transportCenterOffsetMeters ?? 0) * 1000).toFixed(1)} mm</strong>
            </div> : null}
            {isProject02 ? <div className={(preview.metrics.portalGantryOverlapRatio ?? 0) >= 0.85 ? "metric good" : "metric bad"}>
              <span>CCD/龙门轴向覆盖</span>
              <strong>{((preview.metrics.portalGantryOverlapRatio ?? 0) * 100).toFixed(1)}%</strong>
            </div> : null}
            {isProject02 ? <div className={(preview.metrics.portalCenterOffsetMeters ?? Number.POSITIVE_INFINITY) <= (preview.metrics.portalMaximumCenterOffsetMeters ?? 0.03) ? "metric good" : "metric bad"}>
              <span>CCD结构中心偏置</span>
              <strong>{((preview.metrics.portalCenterOffsetMeters ?? 0) * 1000).toFixed(1)} mm</strong>
            </div> : null}
            {isProject02 ? <div className={(preview.metrics.portalMaximumOverhangMeters ?? Number.POSITIVE_INFINITY) <= (preview.metrics.portalAllowedOverhangMeters ?? 0.16) ? "metric good" : "metric bad"}>
              <span>CCD最大单侧越界</span>
              <strong>{((preview.metrics.portalMaximumOverhangMeters ?? 0) * 1000).toFixed(1)} mm</strong>
            </div> : null}
            {isProject02 ? <div className="metric good">
              <span>A300/A700锚点差</span>
              <strong>
                U {((preview.metrics.serviceClusterDeltaUMeters ?? 0) * 1000).toFixed(1)} / V {((preview.metrics.serviceClusterDeltaVMeters ?? 0) * 1000).toFixed(1)} mm
              </strong>
            </div> : null}
            <div className="metric warn">
              <span>重叠复核</span>
              <strong>{preview.metrics.allowedOverlapReviewCount} 对</strong>
            </div>
            <div className="metric good">
              <span>包围盒直接判定</span>
              <strong>{preview.metrics.strictAabbPairCount} 对</strong>
            </div>
            <div className="metric warn">
              <span>B-rep候选上限</span>
              <strong>{activeSolution?.predictedConditionalBrepPairCount ?? preview.metrics.conditionalBrepPairCount} / {preview.staticCollisionPolicy?.pairCount ?? 28} 对</strong>
            </div>
            {isProject02 ? <div className="metric warn">
              <span>A600安装接触</span>
              <strong>{preview.metrics.installationContactPairCount ?? 0} 对</strong>
            </div> : null}
            <div className={activeLeafHitCount === 0 ? "metric good" : "metric warn"}>
              <span>叶盒宽相预命中</span>
              <strong>{activeLeafHitCount} 处 / {activeLeafRisks.length} 对</strong>
            </div>
            <div className="metric good">
              <span>求解阶段B-rep</span>
              <strong>{preview.metrics.solverBrepCallCount} 次</strong>
            </div>
          </div>

          {(preview.solutions?.length ?? 0) > 1 ? (
            <div className="preview-solution-picker" aria-label="求解方案选择">
              <strong>候选布局</strong>
              {preview.solutions!.map((solution) => (
                <button
                  className={solution.rank === selectedSolutionRank ? "active" : ""}
                  type="button"
                  key={solution.rank}
                  onClick={() => {
                    setSelectedSolutionRank(solution.rank);
                    setSelectedName(null);
                  }}
                >
                  方案 {solution.rank}
                  <span>评分 {solution.score.toFixed(3)}</span>
                  <span>B-rep候选 {solution.predictedConditionalBrepPairCount} 对</span>
                  <span>叶盒预命中 {solution.predictedConditionalLeafAabbHitCount} 处</span>
                </button>
              ))}
              <span>已探索 {preview.jointSearchSummary?.exploredNodeCount ?? 0} 个联合节点</span>
            </div>
          ) : null}

          <div className="preview-workspace">
            <div className="preview-canvas-wrap">
              <svg className="preview-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${caseLabel}求解布局预览`}>
                <defs>
                  <pattern id="preview-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#dbe4ed" strokeWidth="1" />
                  </pattern>
                  <marker id="direction-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L7,3 z" fill="#25364a" />
                  </marker>
                </defs>
                <rect x="0" y="0" width={width} height={height} fill="url(#preview-grid)" />
                {gantryShortCenter !== null && preview.longAxis === "u" ? (
                  <line className="gantry-centerline" x1={toX(gantry?.bounds[0] ?? 0)} x2={toX(gantry?.bounds[2] ?? 0)} y1={toY(gantryShortCenter)} y2={toY(gantryShortCenter)} />
                ) : null}
                {gantryShortCenter !== null && preview.longAxis !== "u" ? (
                  <line className="gantry-centerline" y1={toY(gantry?.bounds[1] ?? 0)} y2={toY(gantry?.bounds[3] ?? 0)} x1={toX(gantryShortCenter)} x2={toX(gantryShortCenter)} />
                ) : null}
                {orderedModules.flatMap((module) => module.regions.map((region) => {
                  const [minU, minV, maxU, maxV] = region.bounds;
                  return (
                    <g key={`${module.componentName}-${region.name}`}>
                      <rect className="preview-region" x={toX(minU)} y={toY(maxV)} width={(maxU - minU) * scale} height={(maxV - minV) * scale} />
                      <text className="preview-region-label" x={toX(minU) + 7} y={toY(maxV) + 17}>{region.name}</text>
                    </g>
                  );
                }))}
                {orderedModules.flatMap((module) => module.protectedSpaces.map((space) => {
                  const [minU, minV, maxU, maxV] = space.bounds;
                  return (
                    <g key={`${module.componentName}-${space.id}`}>
                      <rect
                        className={`protected-space ${space.id.includes("maintenance") ? "maintenance" : "process"}`}
                        x={toX(minU)}
                        y={toY(maxV)}
                        width={(maxU - minU) * scale}
                        height={(maxV - minV) * scale}
                      />
                      <text className="protected-space-label" x={toX(minU) + 5} y={toY(maxV) + 14}>
                        {space.id}
                      </text>
                    </g>
                  );
                }))}
                {orderedModules.filter((module) => module.transportSweepEnvelope).map((module) => {
                  const envelope = module.transportSweepEnvelope!;
                  return (
                    <g key={`${module.componentName}-transport-sweep`}>
                      <rect
                        className="transport-sweep-envelope"
                        x={toX(envelope.bounds[0])}
                        y={toY(envelope.bounds[3])}
                        width={(envelope.bounds[2] - envelope.bounds[0]) * scale}
                        height={(envelope.bounds[3] - envelope.bounds[1]) * scale}
                      />
                      <text className="transport-sweep-label" x={toX(envelope.bounds[0]) + 7} y={toY(envelope.bounds[3]) + 17}>
                        carrier sweep
                      </text>
                    </g>
                  );
                })}
                {orderedModules.filter((module) => module.transportStaticKeepoutEnvelope).map((module) => {
                  const envelope = module.transportStaticKeepoutEnvelope!;
                  return (
                    <g key={`${module.componentName}-transport-static-keepout`}>
                      <rect
                        className="transport-static-keepout-envelope"
                        x={toX(envelope.bounds[0])}
                        y={toY(envelope.bounds[3])}
                        width={(envelope.bounds[2] - envelope.bounds[0]) * scale}
                        height={(envelope.bounds[3] - envelope.bounds[1]) * scale}
                      />
                      <text className="transport-static-keepout-label" x={toX(envelope.bounds[0]) + 7} y={toY(envelope.bounds[1]) - 7}>
                        fixed rail keepout
                      </text>
                    </g>
                  );
                })}
                {activeLeafRisks.map((risk) => (
                  <g className="leaf-risk-link" key={`${risk.firstComponentName}-${risk.secondComponentName}`}>
                    <line
                      x1={toX(risk.firstCenter[0])}
                      y1={toY(risk.firstCenter[1])}
                      x2={toX(risk.secondCenter[0])}
                      y2={toY(risk.secondCenter[1])}
                    />
                    <text
                      x={toX((risk.firstCenter[0] + risk.secondCenter[0]) / 2)}
                      y={toY((risk.firstCenter[1] + risk.secondCenter[1]) / 2) - 6}
                    >
                      {risk.hitCount}
                    </text>
                  </g>
                ))}
                {orderedModules.map((module) => {
                  const rect = moduleRect(module);
                  const selectedClass = selectedName === module.componentName ? " selected" : "";
                  const radians = module.thetaDegrees * Math.PI / 180;
                  const arrowLength = Math.min(Math.max(Math.min(rect.width, rect.height) * 0.45, 18), 44);
                  const centerX = toX(module.center[0]);
                  const centerY = toY(module.center[1]);
                  return (
                    <g
                      className={`preview-module${selectedClass}`}
                      key={module.componentName}
                      onClick={() => setSelectedName(module.componentName)}
                      tabIndex={0}
                      role="button"
                      aria-label={`${module.code} ${module.label}`}
                    >
                      <rect
                        x={rect.x}
                        y={rect.y}
                        width={rect.width}
                        height={rect.height}
                        rx="5"
                        fill={module.color}
                        fillOpacity={module.moduleType === "frame" ? 0.04 : module.moduleType === "gantry" ? 0.10 : 0.30}
                        stroke={module.color}
                        strokeWidth={module.moduleType === "frame" || module.moduleType === "gantry" ? 3 : 2}
                        strokeDasharray={module.moduleType === "frame" ? "10 6" : undefined}
                      />
                      {module.interactionEnvelope?.source !== "fullAabb" ? (
                        <rect
                          className="interaction-envelope"
                          x={toX(module.interactionEnvelope?.bounds[0] ?? 0)}
                          y={toY(module.interactionEnvelope?.bounds[3] ?? 0)}
                          width={((module.interactionEnvelope?.bounds[2] ?? 0) - (module.interactionEnvelope?.bounds[0] ?? 0)) * scale}
                          height={((module.interactionEnvelope?.bounds[3] ?? 0) - (module.interactionEnvelope?.bounds[1] ?? 0)) * scale}
                        />
                      ) : null}
                      {module.moduleType !== "frame" ? <line
                          className="module-direction"
                          x1={centerX}
                          y1={centerY}
                          x2={centerX + Math.cos(radians) * arrowLength}
                          y2={centerY - Math.sin(radians) * arrowLength}
                          markerEnd="url(#direction-arrow)"
                        /> : null}
                      <text
                        className="preview-module-code"
                        x={rect.x + 7}
                        y={module.moduleType === "gantry" || module.moduleType === "frame" ? rect.y + rect.height - 7 : rect.y + 17}
                      >
                        {module.code}
                      </text>
                      {module.points.map((point) => (
                        <g key={`${module.componentName}-${point.name}`}>
                          <title>{`${module.code}.${point.name}`}</title>
                          <circle className="service-point" cx={toX(point.position[0])} cy={toY(point.position[1])} r="4" />
                          {selectedName === module.componentName ? (
                            <text className="service-point-label" x={toX(point.position[0]) + 6} y={toY(point.position[1]) - 6}>{point.name}</text>
                          ) : null}
                        </g>
                      ))}
                    </g>
                  );
                })}
              </svg>
              <div className="preview-caption">
                <span>{isProject01 || isProject03 ? "虚线框：双阀公共行程" : "虚线框：胶阀行程/CCD覆盖"}</span>
                <span>黑色箭头：模组方向</span>
                <span>圆点：工艺服务点（点击模组查看名称）</span>
                <span>点划线框：简化主体交互包络</span>
                <span>红色虚线区：载具/产品运动扫掠区</span>
                <span>橙/紫色框：阀头接近与维护保护空间</span>
                <span>橙色连线数字：叶盒宽相预命中（非实体干涉结论）</span>
              </div>
            </div>

            <aside className="preview-inspector">
              <h3>{selected ? `${selected.code} · ${selected.label}` : "模组与观察项"}</h3>
              {selected ? (
                <div className="selected-module-detail">
                  <button type="button" className="text-button" onClick={() => setSelectedName(null)}>返回观察项</button>
                  <dl>
                    <dt>中心</dt><dd>{selected.center.map((value) => value.toFixed(3)).join(", ")} m</dd>
                    <dt>方向</dt><dd>{selected.thetaDegrees.toFixed(1)}°</dd>
                    <dt>类型</dt><dd>{selected.moduleType}</dd>
                    <dt>点位</dt><dd>{selected.points.map((point) => point.name).join("、") || "无"}</dd>
                    <dt>交互高度</dt><dd>{selected.interactionEnvelope?.heightRangeMeters.map((value) => value.toFixed(3)).join(" ~ ") ?? "使用完整AABB"} m</dd>
                    <dt>交互包络</dt><dd>{selected.interactionEnvelope?.source === "fullAabb" ? "完整AABB" : "简化主体包络（临时）"}</dd>
                    <dt>载具扫掠区</dt><dd>{selected.transportSweepEnvelope ? selected.transportSweepEnvelope.heightRangeMeters.map((value) => value.toFixed(3)).join(" ~ ") + " m" : "无"}</dd>
                    <dt>保护空间</dt><dd>{selected.protectedSpaces.length ? `${selected.protectedSpaces.length} 个` : "无"}</dd>
                    <dt>状态</dt><dd>{selected.provisional ? "含临时估算" : "已定义"}</dd>
                  </dl>
                </div>
              ) : (
                <div className="review-list">
                  {preview.assemblySequencePlan ? (
                    <div className="assembly-sequence-gate">
                      <div className="assembly-sequence-heading">
                        <div>
                          <strong>A600锚定装配顺序</strong>
                          <span>{preview.assemblySequencePlan.message}</span>
                        </div>
                        <b className={preview.assemblySequencePlan.sequentialSolverReady ? "ready" : "blocked"}>
                          {preview.assemblySequencePlan.summary.readyCount}/{preview.assemblySequencePlan.summary.stageCount} 正式就绪
                        </b>
                      </div>
                      <ol>
                        {preview.assemblySequencePlan.stages.map((stage) => (
                          <li className={stage.status} key={stage.id}>
                            <span>{stage.id.slice(0, 2)}</span>
                            <div>
                              <strong>{stage.title}</strong>
                              <small>{stage.moduleCodes.join(" → ")}</small>
                              {stage.blockedBy.length ? <em>待补：{stage.blockedBy.join("；")}</em> : null}
                            </div>
                          </li>
                        ))}
                      </ol>
                      {preview.assemblySequencePlan.installationGeometryResolved && preview.assemblySequencePlan.installationGeometry ? (
                        <>
                          <A600InstallationMap geometry={preview.assemblySequencePlan.installationGeometry} />
                          <p>
                            A600粗安装面：{preview.assemblySequencePlan.installationGeometry.hardKeepoutRegionCount}个硬禁入区、
                            {preview.assemblySequencePlan.installationGeometry.conditionalStructuralBodyCount}个条件结构；
                            叶体覆盖率 {((preview.assemblySequencePlan.installationGeometry.captureCoverage?.coverageRatio ?? 0) * 100).toFixed(2)}%。
                            当前仅用于粗布局，最终实体碰撞仍需条件复核。
                          </p>
                        </>
                      ) : null}
                      {preview.assemblySequencePlan.mateDerivedTransportInterfaceResolved && preview.assemblySequencePlan.mateDerivedTransportInterface ? (
                        <p>
                          A800配合面基准：
                          Y/Z及姿态已由“重合35＋宽度9”恢复；
                          配合特征粗定位 XYZ = {(preview.assemblySequencePlan.mateDerivedTransportInterface.datumFrameMeters ?? [])
                            .map((value) => `${(value * 1000).toFixed(1)} mm`)
                            .join(" / ")}。
                          X仅为原型特征位置，尚未被配合约束，需确认厂商端面或销孔基准。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.scanStationInferenceResolved && preview.assemblySequencePlan.scanStationInference ? (
                        <p>
                          扫码站位粗推断：A800 的 5 个二维码载具中，
                          {preview.assemblySequencePlan.scanStationInference.selectedCarrierInstance?.endsWith("-8") ? "载具8" : preview.assemblySequencePlan.scanStationInference.selectedCarrierInstance}
                          距 A180 光学中心约 {((preview.assemblySequencePlan.scanStationInference.selectedDistanceMeters ?? 0) * 1000).toFixed(1)} mm，
                          比第二近候选近 {((preview.assemblySequencePlan.scanStationInference.nearestDistanceMarginMeters ?? 0) * 1000).toFixed(1)} mm，
                          可作为缓存/入口扫码位用于粗布局；PLC触发点与动态停靠位置仍待确认。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.dynamicScanWindowResolved && preview.assemblySequencePlan.dynamicScanWindow ? (
                        <p>
                          动态扫码粗窗口（{preview.assemblySequencePlan.dynamicScanInputAuthority === "prototypeBaselineAcceptedForCoarseLayout" ? "项目02原型基线" : "暂估"}）：
                          载具8沿传输长轴按 ±{((preview.assemblySequencePlan.dynamicScanWindow.estimatedStopToleranceMeters ?? 0) * 1000).toFixed(1)} mm
                          验证窗口两端的工作距离、无遮挡视线和有向光轴。该容差来自二维码几何半宽，PLC触发位置与量产停靠精度仍待替换确认。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.operationSideCapacityEstimated && preview.assemblySequencePlan.operationSideCapacity ? (
                        <p>
                          功能模组侧别：暂选操作面侧（{preview.assemblySequencePlan.selectedServiceSide}）。
                          操作侧规则矩形净深约 {((preview.assemblySequencePlan.operationSideCapacity.operationSideGrossBand?.grossDepthMeters ?? 0) * 1000).toFixed(0)} mm，
                          原型服务模组簇需求深度约 {((preview.assemblySequencePlan.operationSideCapacity.prototypeServiceCluster?.requiredDepthFromSafeFrontMeters ?? 0) * 1000).toFixed(0)} mm；
                          因原型利用传输/CCD周围非凸通道，当前按中等置信度估计保留在操作面侧，维护空间仍待确认。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.serviceAccessEstimated && preview.assemblySequencePlan.serviceAccess ? (
                        <p>
                          服务空间粗审计（{preview.assemblySequencePlan.serviceAccessInputAuthority === "prototypeBaselineAcceptedForCoarseLayout" ? "项目02原型基线" : "暂估"}）：A500/A700/A300共
                          {preview.assemblySequencePlan.serviceAccess.protectedSpaceConstraintCount ?? 0}条保护空间净空关系通过；
                          真实工具与人工维护包络尚未工程确认。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.serviceFunctionalSplitResolved && preview.assemblySequencePlan.serviceFunctionalSplit ? (
                        <p>
                          A700内部功能拆分：A710/A720清洁服务点约为局部
                          U={((preview.assemblySequencePlan.serviceFunctionalSplit.functions?.cleaning?.derivedServicePointLocalMeters?.u ?? 0) * 1000).toFixed(1)} mm、
                          V={((preview.assemblySequencePlan.serviceFunctionalSplit.functions?.cleaning?.derivedServicePointLocalMeters?.v ?? 0) * 1000).toFixed(1)} mm；
                          A730称重点约为局部
                          U={((preview.assemblySequencePlan.serviceFunctionalSplit.functions?.weighing?.derivedServicePointLocalMeters?.u ?? 0) * 1000).toFixed(1)} mm、
                          V={((preview.assemblySequencePlan.serviceFunctionalSplit.functions?.weighing?.derivedServicePointLocalMeters?.v ?? 0) * 1000).toFixed(1)} mm。
                          A700仍作为一个刚体模组求解，两个点分别执行可达和维护空间门禁。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.dualValveReachEstimated && preview.assemblySequencePlan.dualValveReach ? (
                        <p>
                          双阀粗行程审计（{preview.assemblySequencePlan.dualValveReachInputAuthority === "prototypeBaselineAcceptedForCoarseLayout" ? "项目02原型基线" : "暂估"}）：左右阀公共交集
                          {preview.assemblySequencePlan.dualValveReach.commonIntersectionMatches ? "一致" : "不一致"}，
                          暂估阀头间距 {((preview.assemblySequencePlan.dualValveReach.estimatedValveHeadSpacingMeters ?? 0) * 1000).toFixed(0)} mm；
                          真实轴限位仍待测量。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.dualValveAxisEvidence ? (() => {
                        const axisEvidence = preview.assemblySequencePlan.dualValveAxisEvidence;
                        const optimistic = axisEvidence.solverSensitivity?.find((item) => item.id === "geometry-optimistic");
                        const balanced = axisEvidence.solverSensitivity?.find((item) => item.id === "geometry-balanced-expanded-search");
                        const namedMate = axisEvidence.evidence?.namedLimitDistanceMate;
                        return (
                          <p>
                            A100轴证据：已读取{axisEvidence.evidence?.topLevelModuleCount ?? 0}个顶层子装配体、
                            {axisEvidence.evidence?.capturedLeafBodyCount ?? 0}个叶体；
                            “LimitDistance1”实际为{namedMate?.solidWorksMateType ?? "未知类型"}、当前距离
                            {((namedMate?.currentDistanceMeters ?? 0) * 1000).toFixed(1)} mm，不能作为机械限位。
                            几何乐观公共行程约{((optimistic?.commonWidthUMeters ?? 0) * 1000).toFixed(0)}×
                            {((optimistic?.commonWidthVMeters ?? 0) * 1000).toFixed(0)} mm时
                            {optimistic?.feasible ? "可解" : "无解"}
                            {optimistic?.replayRequiredIfApplied
                              ? `，位姿最大变化${((optimistic.layoutComparison?.maxXyErrorMeters ?? 0) * 1000).toFixed(1)} mm，采用后需Replay`
                              : ""}；
                            平衡档扩大至{balanced?.jointCandidateLimit ?? 0}个候选后仍
                            {balanced?.feasible ? "可解" : "无解"}，瓶颈为A300工艺域。
                          </p>
                        );
                      })() : null}
                      {preview.assemblySequencePlan.dualValveConstraintAblation ? (() => {
                        const ablation = preview.assemblySequencePlan.dualValveConstraintAblation;
                        const baseline = ablation.scenarios?.find((item) => item.id === "balanced-baseline");
                        const widened = ablation.scenarios?.find((item) => item.id === "widened-a300-a700-relative-window");
                        const soft = ablation.scenarios?.find((item) => item.id === "soft-a300-a700-relative-preference");
                        const widenedA300 = widened?.rank1PlacementSignature?.["FL9A24D062A300.001-1"];
                        const widenedA700 = widened?.rank1PlacementSignature?.["FL9A24D062A700.001-1"];
                        const deltaU = widenedA300 && widenedA700 ? widenedA300[0] - widenedA700[0] : null;
                        const deltaV = widenedA300 && widenedA700 ? widenedA300[1] - widenedA700[1] : null;
                        return (
                          <p>
                            A300–A700约束消融：1000×820 mm平衡行程保留全部约束时
                            {baseline?.feasible ? "可解" : "无解"}；仅适度放宽两模组相对窗口后
                            {widened?.feasible ? "恢复可解" : "仍无解"}
                            {deltaU !== null && deltaV !== null
                              ? `（相对位移约U=${(deltaU * 1000).toFixed(1)} mm、V=${(deltaV * 1000).toFixed(1)} mm）`
                              : ""}。
                            原窄窗口改作软偏好时{soft?.feasible ? "也可解，但服务簇可能漂移" : "仍无解"}；
                            本测试未修改正式约束，需在真实轴限位或工艺间距确认后再选型。
                          </p>
                        );
                      })() : null}
                      {preview.assemblySequencePlan.parameterRobustnessAudited && preview.assemblySequencePlan.parameterRobustness?.summary ? (
                        <p>
                          参数压力测试：{preview.assemblySequencePlan.parameterRobustness.scenarioCount ?? 0}个离散场景；
                          扫码停靠±{((preview.assemblySequencePlan.parameterRobustness.summary.dynamicScan?.maximumTestedLayoutPreservingValue ?? 0) * 1000).toFixed(0)} mm内保持当前位姿，
                          维护保护空间放大至{(preview.assemblySequencePlan.parameterRobustness.summary.serviceAccess?.maximumTestedLayoutPreservingValue ?? 0).toFixed(2)}倍仍保持当前位姿；
                          阀行程每侧缩小{((preview.assemblySequencePlan.parameterRobustness.summary.dualValveReach?.maximumTestedFeasibleValue ?? 0) * 1000).toFixed(0)} mm仍可求解，但会触发布局变化与新Replay。
                        </p>
                      ) : null}
                      {preview.assemblySequencePlan.nextRequiredInputs.length ? (
                        <p>下一批输入：{preview.assemblySequencePlan.nextRequiredInputs.join("；")}</p>
                      ) : null}
                    </div>
                  ) : null}
                  {visibleReviewItems.map((item) => (
                    <article className={`review-item ${item.severity}`} key={`${item.title}-${item.message}`}>
                      {item.severity === "pass" ? <CheckCircle2 aria-hidden="true" /> : item.severity === "warning" || item.severity === "fail" ? <AlertTriangle aria-hidden="true" /> : <Activity aria-hidden="true" />}
                      <div><strong>{item.title}</strong><span>{item.message}</span></div>
                    </article>
                  ))}
                  {overlapReviewLabels.length > 0 ? (
                    <div className="overlap-review-list">
                      <strong>三维复核组合</strong>
                      <span>{overlapReviewLabels.join("；")}</span>
                    </div>
                  ) : null}
                  <div className="leaf-risk-list">
                    <strong>条件 B-rep 优先复核</strong>
                    {activeLeafRisks.length ? activeLeafRisks.map((risk) => (
                      <button
                        type="button"
                        key={`${risk.firstComponentName}-${risk.secondComponentName}`}
                        onClick={() => setSelectedName(risk.firstComponentName)}
                      >
                        <span>{risk.firstCode} ↔ {risk.secondCode}</span>
                        <b>{risk.hitCount} 个叶盒预命中</b>
                      </button>
                    )) : <span className="leaf-risk-empty">无叶盒宽相预命中</span>}
                    <small>预命中仅用于安排 CAD 精检顺序，不等同于实体干涉。</small>
                  </div>
                </div>
              )}
              <div className="module-legend">
                {activeModules.map((module) => (
                  <button type="button" key={module.componentName} onClick={() => setSelectedName(module.componentName)}>
                    <i style={{ backgroundColor: module.color }} />
                    <span><strong>{module.code}</strong>{module.label}</span>
                  </button>
                ))}
              </div>
            </aside>
          </div>

          <div className="preview-footer">
            <span>求解器：有限候选联合回溯（Top-{preview.solutions?.length ?? 1}）</span>
            <span>当前展示：方案 {selectedSolutionRank}</span>
            <span>相对约束去原型：{preview.relativeConstraintsSourceIndependent ? "是" : "否"}</span>
            <span>
              案例锚点：{isProject01
                ? "SS00项目01配合安装基准"
                : isProject03
                  ? "AE00项目03配合安装基准"
                : preview.caseAnchor?.componentName.includes("A800")
                  ? preview.caseAnchor.targetKind === "installationFramePoint"
                    ? "A800安装基准（当前X参数由原型估计）"
                    : "A800复用项目02原型"
                  : "无"}
            </span>
            <span>结果：{preview.solutionPath.replaceAll("\\", "/").split("/").slice(-2).join("/")}</span>
          </div>
          {approvalEnabled ? <div className="preview-approval-gate">
            <div>
              <strong>人工目测门禁</strong>
              <span>先检查朝向、越界、明显穿透和工艺可维护性；确认后才生成该方案的 Replay 文件。</span>
            </div>
            <label>
              <input
                type="checkbox"
                checked={visualReviewChecked}
                onChange={(event) => setVisualReviewChecked(event.target.checked)}
              />
              已完成当前方案目测
            </label>
            <button
              className="primary-button"
              type="button"
              disabled={!visualReviewChecked || approving}
              onClick={() => onApprove(selectedSolutionRank)}
            >
              {approving ? <Loader2 className="spin" aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
              确认方案 {selectedSolutionRank}，进入三维复核
            </button>
            {approval?.status === "visual_review_approved" ? (
              <div className="approval-status good">
                <CheckCircle2 aria-hidden="true" />
                <span>
                  已物化方案 {approval.selectedSolutionRank}；下一步为 SolidWorks Replay 和 AABB 粗筛，B-rep 当前仍被门禁阻止。
                </span>
              </div>
            ) : null}
            {approval?.status === "cad_closure_reused" && approval.cadClosureReuse?.success ? (
              <div className="approval-status good">
                <CheckCircle2 aria-hidden="true" />
                <span>
                  当前方案与已关闭的 v52 CAD 布局完全等价；Replay、AABB与条件B-rep证据已复用，无需重复启动SolidWorks。
                </span>
              </div>
            ) : null}
            {isProject01 && approval?.collisionClosure ? (
              <div className="collision-closure-card">
                <div>
                  <strong>三维实体闭环</strong>
                  <span>{approval.collisionClosure.message}</span>
                </div>
                <div className="collision-closure-metrics">
                  <span className="closure-clear">
                    无非法干涉
                    <b>{approval.collisionClosure.strictAabbClearPairCount}组AABB＋{approval.collisionClosure.exactClearTopLevelPairCount}组精检</b>
                  </span>
                  <span className="closure-provisional">
                    暂定允许接触
                    <b>{approval.collisionClosure.provisionalAllowedBodyContactCount}个实体对</b>
                  </span>
                  <span className={approval.collisionClosure.illegalInterferenceCount === 0 ? "closure-clear" : "closure-illegal"}>
                    非法干涉
                    <b>{approval.collisionClosure.illegalInterferenceCount}个</b>
                  </span>
                </div>
                <small>暂定白名单仅适用于项目01方案1的静态工艺位Demo，不等同于生产批准。</small>
              </div>
            ) : null}
          </div> : (
            <div className="preview-approval-gate">
              <div>
                <strong>只读目测候选</strong>
                <span>当前候选不会覆盖项目02标准预览，也不能直接触发CAD；先比较方向、边界与明显接触。</span>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Project02DependencyAblationPanel({
  bundle,
  loading,
  onReload
}: {
  bundle: Project02DependencyAblationBundle | null;
  loading: boolean;
  onReload: () => void;
}) {
  const feedbackReady = Boolean(bundle?.collisionFeedback?.report.success);
  const recommended: "B" | "C" | "F" = feedbackReady
    ? "F"
    : (bundle?.report.recommendedVariantForVisualReview ?? "C");
  const [variant, setVariant] = useState<"B" | "C" | "F">(recommended);
  useEffect(() => setVariant(recommended), [bundle?.report.generatedAt, feedbackReady, recommended]);
  const preview = variant === "F"
    ? (bundle?.collisionFeedback?.preview ?? null)
    : (bundle?.variants[variant] ?? null);
  const experiment = variant === "F"
    ? undefined
    : bundle?.report.experiments.find((item) => item.variant === variant);
  const feedbackReport = bundle?.collisionFeedback?.report;
  const gate = bundle?.report.referenceV22UnderGeometryOnlyValidation;

  return (
    <div className="dependency-ablation-display">
      <section className="panel">
        <div className="project-preview-header">
          <div>
            <span className="eyebrow">去 v42 依赖实验 · 碰撞反馈闭环 · 只读</span>
            <h2>项目02 · 独立候选与反馈加固方案</h2>
            <p>B/C为原始消融候选；F把C方案的精确碰撞证据回灌为求解期硬约束。所有候选仍需先目测，再决定是否Replay。</p>
          </div>
          <button className="secondary-button" type="button" onClick={onReload} disabled={loading}>
            {loading ? <Loader2 className="spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
            刷新实验结果
          </button>
        </div>
        {!bundle ? <div className="preview-empty"><Eye aria-hidden="true" /><strong>尚未加载消融结果</strong></div> : <>
          <div className="preview-solution-picker">
            <strong>依赖档位</strong>
            {(["B", "C", ...(bundle.collisionFeedback ? ["F" as const] : [])] as const).map((item) => {
              const row = item === "F"
                ? undefined
                : bundle.report.experiments.find((value) => value.variant === item);
              const duration = item === "F" ? feedbackReport?.timing.solveSeconds : row?.durationSeconds;
              const solutionCount = item === "F" ? feedbackReport?.solutionCount : row?.solutionCount;
              return <button key={item} type="button" className={variant === item ? "active" : ""} onClick={() => setVariant(item)}>
                {item === "F" ? "反馈加固 F" : `方案组 ${item}`}{recommended === item ? "（推荐目测）" : ""}
                <span>{duration?.toFixed(2) ?? "n/a"} s · {solutionCount ?? 0} 解</span>
                <span>{item === "F"
                  ? `${feedbackReport?.feedbackMetadata.confirmedHardOccupancyPairs.length ?? 0}组碰撞硬化 · 门禁${feedbackReport?.compatibilityGate.passed ? "通过" : "失败"}`
                  : `相对v22最大位移 ${(((row?.rank1DifferenceFromV22?.maximumCenterDistanceMeters ?? 0) * 1000)).toFixed(1)} mm`}</span>
              </button>;
            })}
          </div>
          <div className="preview-metrics">
            <div className={gate?.hardFeasible ? "metric good" : "metric bad"}><span>v22兼容硬门禁</span><strong>{gate?.hardFailureCount ?? 0} 失败</strong></div>
            <div className="metric warn"><span>维护空间告警</span><strong>{gate?.advisoryWarningCount ?? 0} 项</strong></div>
            <div className="metric warn"><span>条件CAD风险</span><strong>{gate?.conditionalBrepRiskCount ?? 0} 项</strong></div>
            <div className={variant === "F" && feedbackReport?.compatibilityGate.passed ? "metric good" : "metric"}>
              <span>{variant === "F" ? "反馈兼容门禁" : `${variant} rank-1评分`}</span>
              <strong>{variant === "F"
                ? (feedbackReport?.compatibilityGate.passed ? "Top-3通过" : "未通过")
                : (experiment?.rank1Score?.toFixed(3) ?? "n/a")}</strong>
            </div>
          </div>
        </>}
      </section>
      {preview ? <div id="project02-ablation-preview">
        <ProjectCasePreviewPanel
          key={`${variant}-${preview.generatedAt}`}
          caseId="project02"
          preview={preview}
          solving={loading}
          approving={false}
          approval={null}
          onSolve={onReload}
          onApprove={() => undefined}
          approvalEnabled={false}
          solveButtonLabel="刷新只读候选"
        />
      </div> : null}
    </div>
  );
}

function App() {
  const [state, setState] = useState<DemoState | null>(null);
  const [projectRequirement, setProjectRequirement] = useState("每个载具4个产品，需要双阀环氧胶点胶、扫码追溯、CCD视觉定位、喷嘴校准、清洁、称重和排胶。");
  const [moduleRecommendation, setModuleRecommendation] = useState<ProjectModuleRecommendationResult | null>(null);
  const [selectedModuleCodes, setSelectedModuleCodes] = useState<string[]>([]);
  const [moduleConfirmation, setModuleConfirmation] = useState<ProjectModuleConfirmationResult | null>(null);
  const [requirementBusy, setRequirementBusy] = useState(false);
  const [projectPreview, setProjectPreview] = useState<ProjectCasePreview | null>(null);
  const [dependencyAblation, setDependencyAblation] = useState<Project02DependencyAblationBundle | null>(null);
  const [dependencyAblationBusy, setDependencyAblationBusy] = useState(false);
  const [project01Readiness, setProject01Readiness] = useState<ProjectMigrationReadiness | null>(null);
  const [project03Readiness, setProject03Readiness] = useState<ProjectMigrationReadiness | null>(null);
  const [project05Readiness, setProject05Readiness] = useState<ProjectMigrationReadiness | null>(null);
  const [project01Preview, setProject01Preview] = useState<ProjectCasePreview | null>(null);
  const [project01PreviewBusy, setProject01PreviewBusy] = useState(false);
  const [project01PreviewApproval, setProject01PreviewApproval] = useState<LayoutVerificationPlan | null>(null);
  const [project01PreviewApprovalBusy, setProject01PreviewApprovalBusy] = useState(false);
  const [project03Preview, setProject03Preview] = useState<ProjectCasePreview | null>(null);
  const [project03PreviewBusy, setProject03PreviewBusy] = useState(false);
  const [project03PreviewApproval, setProject03PreviewApproval] = useState<LayoutVerificationPlan | null>(null);
  const [project03PreviewApprovalBusy, setProject03PreviewApprovalBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewApproval, setPreviewApproval] = useState<LayoutVerificationPlan | null>(null);
  const [previewApprovalBusy, setPreviewApprovalBusy] = useState(false);
  const [layoutFiles, setLayoutFiles] = useState<LayoutJsonInfo[]>([]);
  const [result, setResult] = useState<OperationResult | null>(null);
  const [mcpHealth, setMcpHealth] = useState<McpHealthResult | null>(null);
  const [sourceAssemblyPath, setSourceAssemblyPath] = useState("");
  const [projectLayoutOutputPath, setProjectLayoutOutputPath] = useState("demo/project_layout2d.json");
  const [projectConfigOutputPath, setProjectConfigOutputPath] = useState("demo/project_config.json");
  const [constraintLayoutOutputPath, setConstraintLayoutOutputPath] = useState("demo/constraint_layout2d.json");
  const [constraintRoleOverrides, setConstraintRoleOverrides] = useState<Record<string, ConstraintRole>>({});
  const [constraintClearanceMeters, setConstraintClearanceMeters] = useState(0.01);
  const [constraintGlueDistanceMeters, setConstraintGlueDistanceMeters] = useState(0.05);
  const [constraintAllowRotation, setConstraintAllowRotation] = useState(false);
  const [constraintPortalPassThrough, setConstraintPortalPassThrough] = useState<Record<string, string>>({});
  const [constraintPortalWidthRatio, setConstraintPortalWidthRatio] = useState(0.8);
  const [constraintPortalHeightRatio, setConstraintPortalHeightRatio] = useState(0.75);
  const [constraintModuleSemanticsJson, setConstraintModuleSemanticsJson] = useState("{}");
  const [constraintProcessConstraintsJson, setConstraintProcessConstraintsJson] = useState("[]");
  const [constraintProvisionalComponentsJson, setConstraintProvisionalComponentsJson] = useState("[]");
  const [constraintAutoProcessConstraints, setConstraintAutoProcessConstraints] = useState(true);
  const [discoveryScope, setDiscoveryScope] = useState("topLevelOnly");
  const [discoveryIncludeParts, setDiscoveryIncludeParts] = useState(false);
  const [discoveryFilter, setDiscoveryFilter] = useState("");
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [selectedDiscoveryKeys, setSelectedDiscoveryKeys] = useState<Set<string>>(new Set());
  const [xyToleranceMeters, setXyToleranceMeters] = useState(0.000001);
  const [thetaToleranceDegrees, setThetaToleranceDegrees] = useState(0.0001);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const arrangePayload = useMemo(() => parseArrangePayload(result), [result]);
  const effectiveComponents = arrangePayload?.components ?? state?.lastRun?.components ?? [];
  const orientationCorrections = arrangePayload?.orientationCorrections ?? state?.lastRun?.orientationCorrections ?? [];
  const orientationChecks = arrangePayload?.orientationChecks ?? state?.lastRun?.orientationChecks ?? [];
  const replayValidation = state?.lastRun?.replayValidation;
  const effectiveMessage = arrangePayload?.message ?? state?.lastRun?.toolMessage ?? result?.message ?? "Waiting";
  const effectiveStatus = result?.status ?? state?.lastRun?.status ?? "idle";
  const hasScreenshot = Boolean(arrangePayload?.screenshot?.outputPath || state?.lastRun?.screenshotPath);
  const screenshotUrl = hasScreenshot
    ? `/api/demo/screenshot?t=${encodeURIComponent(state?.updatedAt ?? String(Date.now()))}`
    : null;
  const worldBounds = useMemo(() => computeWorldBounds(state), [state]);
  const missingMappingNames = useMemo(() => {
    const rows = result?.missingFaceMappings ?? [];
    return new Set(
      rows
        .map((row) => row.componentName)
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    );
  }, [result]);
  const mappingRows = useMemo(() => {
    const toolResults = state?.lastRun && Array.isArray((state.lastRun as Record<string, unknown>).toolResults)
      ? ((state.lastRun as Record<string, unknown>).toolResults as Array<Record<string, unknown>>)
      : [];
    const verified = result?.status === "ok" && result.plan.some((item) => item.tool === "select_face_by_name");
    return (state?.components ?? []).map((component) => ({
      component,
      status: missingMappingNames.has(component.componentName) ? "missing" : verified ? "verified" : "ready",
      toolCount: toolResults.filter((item) => item.arguments && (item.arguments as Record<string, unknown>).componentName === component.componentName).length,
    }));
  }, [missingMappingNames, result, state]);
  const filteredDiscoveryComponents = useMemo(() => {
    const query = discoveryFilter.trim().toLowerCase();
    const components = discovery?.components ?? [];
    if (!query) {
      return components;
    }
    return components.filter((component) =>
      [component.componentName, component.hierarchyPath, component.filePath]
        .some((value) => value.toLowerCase().includes(query))
    );
  }, [discovery, discoveryFilter]);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const [nextState, nextLayoutFiles, persistedPreview, verificationPlan, migrationReadiness, project03MigrationReadiness, project05MigrationReadiness, persistedProject01Preview, project01VerificationPlan, persistedProject03Preview, project03VerificationPlan, persistedDependencyAblation] = await Promise.all([
        getState(),
        listLayoutJsonFiles(),
        getProjectCasePreview("project02").catch(() => null),
        getProjectCaseVerificationPlan("project02").catch(() => null),
        getProjectMigrationReadiness("project01").catch(() => null),
        getProjectMigrationReadiness("project03").catch(() => null),
        getProjectMigrationReadiness("project05").catch(() => null),
        getProjectCasePreview("project01").catch(() => null),
        getProjectCaseVerificationPlan("project01").catch(() => null),
        getProjectCasePreview("project03").catch(() => null),
        getProjectCaseVerificationPlan("project03").catch(() => null),
        getProject02DependencyAblation().catch(() => null)
      ]);
      setState(nextState);
      setLayoutFiles(nextLayoutFiles);
      if (persistedPreview) setProjectPreview(persistedPreview);
      if (verificationPlan) setPreviewApproval(verificationPlan);
      if (migrationReadiness) setProject01Readiness(migrationReadiness);
      if (project03MigrationReadiness) setProject03Readiness(project03MigrationReadiness);
      if (project05MigrationReadiness) setProject05Readiness(project05MigrationReadiness);
      if (persistedProject01Preview) setProject01Preview(persistedProject01Preview);
      if (project01VerificationPlan) setProject01PreviewApproval(project01VerificationPlan);
      if (persistedProject03Preview) setProject03Preview(persistedProject03Preview);
      if (project03VerificationPlan) setProject03PreviewApproval(project03VerificationPlan);
      if (persistedDependencyAblation) setDependencyAblation(persistedDependencyAblation);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function refreshLayouts() {
    setLayoutFiles(await listLayoutJsonFiles());
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSave() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      setState(await saveState(state));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleArrange() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      const nextResult = await arrange(state);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleInitializeCommonBase() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      const nextResult = await initializeCommonBase(state);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalizeCommonBase() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await finalizeCommonBase();
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleApplyCapturedLayout() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await applyCapturedLayout(xyToleranceMeters, thetaToleranceDegrees);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateConstraintLayout() {
    if (!state?.components.length) return;
    setBusy(true);
    setError(null);
    try {
      const moduleSemantics = JSON.parse(constraintModuleSemanticsJson) as Record<string, ModuleSemanticInput>;
      const processConstraints = JSON.parse(constraintProcessConstraintsJson) as Array<Record<string, unknown>>;
      const provisionalComponents = JSON.parse(constraintProvisionalComponentsJson) as ProvisionalComponentInput[];
      if (!moduleSemantics || Array.isArray(moduleSemantics) || typeof moduleSemantics !== "object") {
        throw new Error("Module semantics must be a JSON object keyed by component name.");
      }
      if (!Array.isArray(processConstraints)) {
        throw new Error("Process constraints must be a JSON array.");
      }
      if (!Array.isArray(provisionalComponents)) {
        throw new Error("Provisional components must be a JSON array.");
      }
      const nextResult = await generateConstraintLayout({
        sourceAssemblyPath,
        baseComponentName: state.components[0]?.componentName ?? null,
        outputPath: constraintLayoutOutputPath,
        roleOverrides: constraintRoleOverrides,
        marginRatios: [0.05, 0.03, 0.01, 0],
        minimumClearanceMeters: constraintClearanceMeters,
        glueDistanceMeters: constraintGlueDistanceMeters,
        allowRotation: constraintAllowRotation,
        portalPassThrough: Object.fromEntries(
          Object.entries(constraintPortalPassThrough)
            .filter(([, passThrough]) => Boolean(passThrough))
            .map(([portal, passThrough]) => [portal, [passThrough]])
        ),
        portalOpeningWidthRatio: constraintPortalWidthRatio,
        portalOpeningHeightRatio: constraintPortalHeightRatio,
        moduleSemantics,
        processConstraints,
        autoGenerateProcessConstraints: constraintAutoProcessConstraints,
        provisionalComponents,
        syncLayout: provisionalComponents.every((item) => item.replayable === true && Boolean(item.filePath))
      });
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      await refreshLayouts();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleCaptureCommonBaseLayout() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await captureCommonBaseLayout();
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      await refreshLayouts();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleDiscoverComponents() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await discoverComponents(
        sourceAssemblyPath,
        discoveryScope,
        discoveryIncludeParts,
        false,
        "底面"
      );
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      const nextDiscovery = nextResult.discovery ?? null;
      setDiscovery(nextDiscovery);
      setSelectedDiscoveryKeys(new Set(nextDiscovery?.components.map(discoveryKey) ?? []));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleSyncDiscoveredComponents() {
    if (!discovery) return;
    const selected = discovery.components.filter((component) => selectedDiscoveryKeys.has(discoveryKey(component)));
    setBusy(true);
    setError(null);
    try {
      const nextResult = await syncDiscoveredComponents(selected);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleCaptureProjectLayout() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await captureProjectLayout(
        sourceAssemblyPath,
        state?.components?.[0]?.componentName ?? null,
        projectLayoutOutputPath,
        projectConfigOutputPath
      );
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      await refreshLayouts();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  function handleToggleDiscovered(component: DiscoveredComponent) {
    setSelectedDiscoveryKeys((current) => {
      const next = new Set(current);
      const key = discoveryKey(component);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function handleSelectVisibleDiscovered() {
    setSelectedDiscoveryKeys(new Set(filteredDiscoveryComponents.map(discoveryKey)));
  }

  function handleClearDiscoveredSelection() {
    setSelectedDiscoveryKeys(new Set());
  }

  async function handleSelectLayout(path: string) {
    if (!path) return;
    setBusy(true);
    setError(null);
    try {
      const nextResult = await selectLayoutJson(path, true);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      await refreshLayouts();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadLayout(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const content = await file.text();
      const nextResult = await uploadLayoutJson(file.name, content, true);
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
      await refreshLayouts();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyFaceMappings() {
    setBusy(true);
    setError(null);
    try {
      const nextResult = await verifyFaceMappings();
      setResult(nextResult);
      if (nextResult.state) {
        setState(nextResult.state);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleMcpHealth() {
    setBusy(true);
    setError(null);
    try {
      setMcpHealth(await getMcpHealth());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleRecommendProject02Modules() {
    setRequirementBusy(true);
    setError(null);
    try {
      const recommendation = await recommendProjectCaseModules(projectRequirement, "project02");
      setModuleRecommendation(recommendation);
      setSelectedModuleCodes(recommendation.defaultSelectedModuleCodes);
      setModuleConfirmation(null);
      setProjectPreview(null);
      setPreviewApproval(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setRequirementBusy(false);
    }
  }

  function handleToggleRecommendedModule(code: string) {
    if (moduleRecommendation?.requiredModuleCodes.includes(code)) return;
    setSelectedModuleCodes((current) => current.includes(code)
      ? current.filter((item) => item !== code)
      : [...current, code]);
    setModuleConfirmation(null);
  }

  async function handleConfirmProject02Modules() {
    setRequirementBusy(true);
    setError(null);
    try {
      const confirmation = await confirmProjectCaseModules(projectRequirement, selectedModuleCodes, "project02");
      setModuleConfirmation(confirmation);
      if (confirmation.layoutSolverReady) {
        await handleSolveProject02Preview();
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setRequirementBusy(false);
    }
  }

  async function handleSolveProject02Preview() {
    setPreviewBusy(true);
    setError(null);
    try {
      setProjectPreview(await solveProjectCasePreview("project02"));
      setPreviewApproval(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function handleReloadDependencyAblation() {
    setDependencyAblationBusy(true);
    setError(null);
    try {
      setDependencyAblation(await getProject02DependencyAblation());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setDependencyAblationBusy(false);
    }
  }

  async function handleSolveProject01Preview() {
    setProject01PreviewBusy(true);
    setError(null);
    try {
      setProject01Preview(await solveProjectCasePreview("project01"));
      setProject01PreviewApproval(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setProject01PreviewBusy(false);
    }
  }

  async function handleApproveProject01Preview(solutionRank: number) {
    setProject01PreviewApprovalBusy(true);
    setError(null);
    try {
      setProject01PreviewApproval(
        await approveProjectCasePreview(
          "project01",
          solutionRank,
          "用户已在项目01方案展示层完成目测确认"
        )
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setProject01PreviewApprovalBusy(false);
    }
  }

  async function handleSolveProject03Preview() {
    setProject03PreviewBusy(true);
    setError(null);
    try {
      setProject03Preview(await solveProjectCasePreview("project03"));
      setProject03PreviewApproval(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setProject03PreviewBusy(false);
    }
  }

  async function handleApproveProject03Preview(solutionRank: number) {
    setProject03PreviewApprovalBusy(true);
    setError(null);
    try {
      setProject03PreviewApproval(
        await approveProjectCasePreview(
          "project03",
          solutionRank,
          "Codex依据硬约束、最小总位移与原型工艺一致性自主选定"
        )
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setProject03PreviewApprovalBusy(false);
    }
  }

  async function handleApproveProject02Preview(solutionRank: number) {
    setPreviewApprovalBusy(true);
    setError(null);
    try {
      setPreviewApproval(
        await approveProjectCasePreview(
          "project02",
          solutionRank,
          "用户已在方案展示层完成目测确认"
        )
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPreviewApprovalBusy(false);
    }
  }

  async function handleReset() {
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      setState(await resetState());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>SolidWorks Assembly Demo</h1>
          <p>Drag 2D blocks to set bottom-center coordinates for A/B/C.</p>
        </div>
        <div className="toolbar" aria-label="Actions">
          <button className="icon-button" type="button" onClick={load} disabled={busy} title="Refresh">
            <RefreshCw aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={handleSave} disabled={busy || !state} title="Save">
            <Save aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={handleReset} disabled={busy} title="Reset">
            <RotateCcw aria-hidden="true" />
          </button>
          <button className="secondary-button" type="button" onClick={handleInitializeCommonBase} disabled={busy || !state || Boolean(state?.assemblyPath)}>
            <Layers aria-hidden="true" />
            Initialize
          </button>
          <button className="secondary-button" type="button" onClick={handleFinalizeCommonBase} disabled={busy || !state?.assemblyPath || Boolean(state?.commonBaseReady)}>
            <Move3D aria-hidden="true" />
            Common Base
          </button>
          <button className="secondary-button" type="button" onClick={handleCaptureCommonBaseLayout} disabled={busy || !state?.assemblyPath}>
            <Save aria-hidden="true" />
            Capture Layout
          </button>
          <button className="secondary-button" type="button" onClick={handleVerifyFaceMappings} disabled={busy || !state}>
            <CheckCircle2 aria-hidden="true" />
            Verify Faces
          </button>
          <button className="secondary-button" type="button" onClick={handleMcpHealth} disabled={busy}>
            <Activity aria-hidden="true" />
            Health
          </button>
          <button className="secondary-button" type="button" onClick={handleApplyCapturedLayout} disabled={busy || !state?.assemblyPath}>
            <MapPinned aria-hidden="true" />
            Replay Layout
          </button>
          <button className="primary-button" type="button" onClick={handleArrange} disabled={busy || !state?.commonBaseReady}>
            {busy ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
            Arrange
          </button>
        </div>
      </header>

      {error ? <div className="banner error">{error}</div> : null}

      <Project02RequirementPanel
        requirement={projectRequirement}
        recommendation={moduleRecommendation}
        selectedModuleCodes={selectedModuleCodes}
        confirmation={moduleConfirmation}
        busy={requirementBusy}
        onRequirementChange={(value) => {
          setProjectRequirement(value);
          setModuleConfirmation(null);
        }}
        onRecommend={() => void handleRecommendProject02Modules()}
        onToggleModule={handleToggleRecommendedModule}
        onConfirm={() => void handleConfirmProject02Modules()}
      />

      <ProjectMigrationReadinessPanel readiness={project01Readiness} projectLabel="项目01" />

      <ProjectMigrationReadinessPanel readiness={project03Readiness} projectLabel="项目03" />

      <ProjectMigrationReadinessPanel readiness={project05Readiness} projectLabel="项目05" />

      <ProjectCasePreviewPanel
        caseId="project01"
        preview={project01Preview}
        solving={project01PreviewBusy}
        approving={project01PreviewApprovalBusy}
        approval={project01PreviewApproval}
        onSolve={() => void handleSolveProject01Preview()}
        onApprove={(solutionRank) => void handleApproveProject01Preview(solutionRank)}
      />

      <ProjectCasePreviewPanel
        caseId="project03"
        preview={project03Preview}
        solving={project03PreviewBusy}
        approving={project03PreviewApprovalBusy}
        approval={project03PreviewApproval}
        onSolve={() => void handleSolveProject03Preview()}
        onApprove={(solutionRank) => void handleApproveProject03Preview(solutionRank)}
      />

      <ProjectCasePreviewPanel
        caseId="project02"
        preview={projectPreview}
        solving={previewBusy}
        approving={previewApprovalBusy}
        approval={previewApproval}
        onSolve={() => void handleSolveProject02Preview()}
        onApprove={(solutionRank) => void handleApproveProject02Preview(solutionRank)}
      />

      <Project02DependencyAblationPanel
        bundle={dependencyAblation}
        loading={dependencyAblationBusy}
        onReload={() => void handleReloadDependencyAblation()}
      />

      <FaceEndpointWorkbench />

      <section className="layout-grid">
        <div className="main-column">
          {state ? (
            <LayoutCanvas
              state={state}
              worldBounds={worldBounds}
              disabled={busy}
              onMove={(id, x, y) => setState((current) => current && cloneWithXYTarget(current, id, x, y))}
            />
          ) : null}

          <div className="panel layout-json-panel">
            <div className="panel-heading">
              <h2>Layout JSON</h2>
              <span>{state?.layoutInfo?.componentCount ?? 0} components</span>
            </div>
            <div className="layout-json-controls">
              <label className="select-label">
                <FileJson aria-hidden="true" />
                <select
                  value={state?.layoutJsonPath ?? ""}
                  disabled={busy}
                  onChange={(event) => void handleSelectLayout(event.target.value)}
                  aria-label="Select layout JSON"
                >
                  <option value="">Select layout JSON</option>
                  {layoutFiles.map((item) => (
                    <option key={item.path} value={item.path}>
                      {shortPath(item.path)} ({item.componentCount})
                    </option>
                  ))}
                </select>
              </label>
              <label className="upload-button">
                <Upload aria-hidden="true" />
                Upload JSON
                <input type="file" accept="application/json,.json" disabled={busy} onChange={handleUploadLayout} />
              </label>
              <span className="layout-path">{shortPath(state?.layoutJsonPath)}</span>
            </div>
            <div className="project-config-panel">
              <div className="project-config-row">
                <label>
                  Source assembly
                  <input
                    type="text"
                    value={sourceAssemblyPath}
                    disabled={busy}
                    placeholder="Use active SolidWorks assembly when empty"
                    onChange={(event) => setSourceAssemblyPath(event.target.value)}
                  />
                </label>
                <label>
                  Output layout
                  <input
                    type="text"
                    value={projectLayoutOutputPath}
                    disabled={busy}
                    onChange={(event) => setProjectLayoutOutputPath(event.target.value)}
                  />
                </label>
                <label>
                  Project config
                  <input
                    type="text"
                    value={projectConfigOutputPath}
                    disabled={busy}
                    onChange={(event) => setProjectConfigOutputPath(event.target.value)}
                  />
                </label>
              </div>
              <div className="project-config-row compact">
                <label>
                  Discovery scope
                  <select value={discoveryScope} disabled={busy} onChange={(event) => setDiscoveryScope(event.target.value)}>
                    <option value="topLevelOnly">Top-level components</option>
                    <option value="recursive">Recursive components</option>
                  </select>
                </label>
                <label>
                  Filter
                  <input
                    type="search"
                    value={discoveryFilter}
                    disabled={busy}
                    placeholder="Component, path, hierarchy"
                    onChange={(event) => setDiscoveryFilter(event.target.value)}
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={discoveryIncludeParts}
                    disabled={busy}
                    onChange={(event) => setDiscoveryIncludeParts(event.target.checked)}
                  />
                  Include parts
                </label>
              </div>
              <div className="project-config-actions">
                <button className="secondary-button" type="button" onClick={handleDiscoverComponents} disabled={busy}>
                  Discover
                </button>
                <button className="secondary-button" type="button" onClick={handleSelectVisibleDiscovered} disabled={busy || filteredDiscoveryComponents.length === 0}>
                  Select Visible
                </button>
                <button className="secondary-button" type="button" onClick={handleClearDiscoveredSelection} disabled={busy || selectedDiscoveryKeys.size === 0}>
                  Clear
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={handleSyncDiscoveredComponents}
                  disabled={busy || !discovery || selectedDiscoveryKeys.size === 0}
                >
                  Sync Selected
                </button>
                <button className="secondary-button" type="button" onClick={handleCaptureProjectLayout} disabled={busy || !state?.components.length}>
                  Generate Config
                </button>
              </div>
              {discovery ? (
                <div className="discovery-summary">
                  <div className="discovery-message">
                    <strong>{discovery.componentCount}</strong> components · {filteredDiscoveryComponents.length} visible · {discovery.message}
                  </div>
                  <div className="discovery-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Use</th>
                          <th>Component</th>
                          <th>Type</th>
                          <th>Path</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredDiscoveryComponents.map((component) => (
                          <tr key={`${component.hierarchyPath}-${component.componentName}`}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selectedDiscoveryKeys.has(discoveryKey(component))}
                                disabled={busy}
                                onChange={() => handleToggleDiscovered(component)}
                                aria-label={`Use ${component.componentName}`}
                              />
                            </td>
                            <td>
                              <strong>{component.componentName}</strong>
                              <span>{component.hierarchyPath}</span>
                            </td>
                            <td>{component.isAssembly ? "ASM" : component.isPart ? "PRT" : "Other"}</td>
                            <td>{shortPath(component.filePath)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
              <div className="constraint-layout-section">
                <div className="constraint-layout-heading">
                  <div>
                    <strong>Constraint Layout</strong>
                    <span>Generate a rule-based XZ layout, then review and Replay Layout.</span>
                  </div>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={handleGenerateConstraintLayout}
                    disabled={busy || !state?.components.length}
                  >
                    <Boxes aria-hidden="true" />
                    Generate
                  </button>
                </div>
                <div className="constraint-settings">
                  <label>
                    Output layout
                    <input
                      type="text"
                      value={constraintLayoutOutputPath}
                      disabled={busy}
                      onChange={(event) => setConstraintLayoutOutputPath(event.target.value)}
                    />
                  </label>
                  <label>
                    Clearance (m)
                    <input
                      type="number"
                      min="0"
                      step="0.005"
                      value={numberValue(constraintClearanceMeters)}
                      disabled={busy}
                      onChange={(event) => setConstraintClearanceMeters(Math.max(0, Number(event.target.value)))}
                    />
                  </label>
                  <label>
                    Glue distance (m)
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={numberValue(constraintGlueDistanceMeters)}
                      disabled={busy}
                      onChange={(event) => setConstraintGlueDistanceMeters(Math.max(0, Number(event.target.value)))}
                    />
                  </label>
                  <label className="checkbox-label constraint-checkbox">
                    <input
                      type="checkbox"
                      checked={constraintAllowRotation}
                      disabled={busy}
                      onChange={(event) => setConstraintAllowRotation(event.target.checked)}
                    />
                    Allow 90° rotation
                  </label>
                </div>
                <div className="constraint-portal-settings">
                  <label>
                    Portal width ratio
                    <input
                      type="number"
                      min="0.01"
                      max="1"
                      step="0.05"
                      value={numberValue(constraintPortalWidthRatio)}
                      disabled={busy}
                      onChange={(event) => setConstraintPortalWidthRatio(
                        Math.min(1, Math.max(0.01, Number(event.target.value)))
                      )}
                    />
                  </label>
                  <label>
                    Portal height ratio
                    <input
                      type="number"
                      min="0.01"
                      max="1"
                      step="0.05"
                      value={numberValue(constraintPortalHeightRatio)}
                      disabled={busy}
                      onChange={(event) => setConstraintPortalHeightRatio(
                        Math.min(1, Math.max(0.01, Number(event.target.value)))
                      )}
                    />
                  </label>
                </div>
                <div className="constraint-semantic-settings">
                  <label className="checkbox-label constraint-checkbox">
                    <input
                      type="checkbox"
                      checked={constraintAutoProcessConstraints}
                      disabled={busy}
                      onChange={(event) => setConstraintAutoProcessConstraints(event.target.checked)}
                    />
                    Auto-generate scanner / CCD / service constraints
                  </label>
                  <label>
                    Module semantics JSON
                    <textarea
                      rows={8}
                      spellCheck={false}
                      value={constraintModuleSemanticsJson}
                      disabled={busy}
                      onChange={(event) => setConstraintModuleSemanticsJson(event.target.value)}
                      placeholder='{"scanner-1":{"moduleType":"scanner","points":{"scanOrigin":{"u":0,"v":0}},"parameters":{"maxWorkingDistanceMeters":0.3,"barcodeSide":"low"}}}'
                    />
                  </label>
                  <label>
                    Provisional components JSON
                    <textarea
                      rows={6}
                      spellCheck={false}
                      value={constraintProvisionalComponentsJson}
                      disabled={busy}
                      onChange={(event) => setConstraintProvisionalComponentsJson(event.target.value)}
                      placeholder='[{"componentName":"PROVISIONAL_WEIGHING_PLACEHOLDER-1","widthMeters":0.22,"depthMeters":0.22,"heightMeters":0.2,"reason":"No verified WKC204C CAD","replayable":false}]'
                    />
                  </label>
                  <label>
                    Additional process constraints JSON
                    <textarea
                      rows={6}
                      spellCheck={false}
                      value={constraintProcessConstraintsJson}
                      disabled={busy}
                      onChange={(event) => setConstraintProcessConstraintsJson(event.target.value)}
                      placeholder='[{"id":"custom-clearance","type":"moduleClearance","firstComponent":"cleaning-1","secondComponent":"ccd-1","minDistanceMeters":0.1,"hard":true}]'
                    />
                  </label>
                </div>
                <div className="constraint-role-grid">
                  {(state?.components ?? []).map((component) => {
                    const role = constraintRoleOverrides[component.componentName] ?? "auto";
                    return (
                      <div className="constraint-component-config" key={component.id}>
                        <label>
                          <span>{component.componentName}</span>
                          <select
                            value={role}
                            disabled={busy}
                            onChange={(event) => {
                              const value = event.target.value;
                              setConstraintRoleOverrides((current) => {
                                const next = { ...current };
                                if (value === "auto") {
                                  delete next[component.componentName];
                                } else {
                                  next[component.componentName] = value as ConstraintRole;
                                }
                                return next;
                              });
                              if (value !== "functional") {
                                setConstraintPortalPassThrough((current) => {
                                  const next = { ...current };
                                  delete next[component.componentName];
                                  return next;
                                });
                              }
                            }}
                          >
                            <option value="auto">Auto</option>
                            <option value="gantry">Gantry</option>
                            <option value="transport">Transport</option>
                            <option value="functional">Functional</option>
                            <option value="glue">Glue</option>
                          </select>
                        </label>
                        {role === "functional" ? (
                          <label>
                            Pass-through
                            <select
                              value={constraintPortalPassThrough[component.componentName] ?? ""}
                              disabled={busy}
                              onChange={(event) => {
                                const value = event.target.value;
                                setConstraintPortalPassThrough((current) => {
                                  const next = { ...current };
                                  if (value) {
                                    next[component.componentName] = value;
                                  } else {
                                    delete next[component.componentName];
                                  }
                                  return next;
                                });
                              }}
                            >
                              <option value="">None</option>
                              {(state?.components ?? [])
                                .filter((candidate) => candidate.componentName !== component.componentName)
                                .map((candidate) => (
                                  <option value={candidate.componentName} key={candidate.id}>
                                    {candidate.componentName}
                                  </option>
                                ))}
                            </select>
                          </label>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                {result?.constraintLayout ? (
                  <div className="constraint-result">
                    <strong>{result.constraintLayout.gantryComponentName ?? "No gantry"}</strong>
                    {result.constraintLayout.portalConstraints?.length ? (
                      <span>
                        {result.constraintLayout.portalConstraints.length} portal constraint(s) · CAD interference check required after Replay
                      </span>
                    ) : null}
                    <span>
                      margin {((result.constraintLayout.usedMarginRatio ?? 0) * 100).toFixed(0)}% · {result.constraintLayout.longAxis ?? "?"} axis · {result.constraintLayout.validation?.success ? "validated" : "review required"}
                    </span>
                    {result.constraintLayout.processValidation ? (
                      <span>
                        process {result.constraintLayout.processValidation.passedCount ?? 0}/{result.constraintLayout.processValidation.constraintCount ?? 0} · {result.constraintLayout.processValidation.hardFeasible ? "hard-feasible" : "hard constraint failed"}
                      </span>
                    ) : null}
                    {result.constraintLayout.assumptionWarnings?.map((warning) => (
                      <span key={warning}>PROVISIONAL · {warning}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
            <div className="replay-settings">
              <label>
                XY tol
                <input
                  type="number"
                  min="0"
                  step="0.000001"
                  value={numberValue(xyToleranceMeters)}
                  onChange={(event) => setXyToleranceMeters(Math.max(0, Number(event.target.value)))}
                />
                m
              </label>
              <label>
                Theta tol
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={numberValue(thetaToleranceDegrees)}
                  onChange={(event) => setThetaToleranceDegrees(Math.max(0, Number(event.target.value)))}
                />
                deg
              </label>
            </div>
            {state?.layoutInfo?.components?.length ? (
              <div className="layout-summary">
                {state.layoutInfo.components.map((component) => (
                  <div className="layout-summary-row" key={component.componentName}>
                    <strong>{component.componentName}</strong>
                    <span>x {formatNumber(component.layout2d?.x, 4)}</span>
                    <span>y {formatNumber(component.layout2d?.y, 4)}</span>
                    <span>
                      theta {formatNumber(component.layout2d?.thetaDegrees, 2)} {component.layout2d?.thetaAxis ?? ""}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="panel table-panel">
            <div className="panel-heading">
              <h2>Coordinates</h2>
              <span>{state?.updatedAt ? new Date(state.updatedAt).toLocaleString() : "Not loaded"}</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>Current X</th>
                    <th>Current Y</th>
                    <th>Current Z</th>
                    <th>Bottom X</th>
                    <th>Bottom Y</th>
                    <th>Bottom Z</th>
                    <th>Layout X</th>
                    <th>Layout Y</th>
                    <th>Theta</th>
                    <th>Face</th>
                  </tr>
                </thead>
                <tbody>
                  {state?.components.map((component) => {
                    const layout = layoutFor(component, state.layoutInfo);
                    return (
                      <tr key={component.id}>
                        <td>
                          <strong>{component.componentName}</strong>
                          <span>{component.displayName}</span>
                        </td>
                        <td>{component.current.x.toFixed(3)}</td>
                        <td>{component.current.y.toFixed(3)}</td>
                        <td>{component.current.z.toFixed(3)}</td>
                        <td>
                          <CoordinateInput
                            component={component}
                            axis="x"
                            onChange={(value) => setState((current) => current && cloneWithTarget(current, component.id, "x", value))}
                          />
                        </td>
                        <td>
                          <CoordinateInput
                            component={component}
                            axis="y"
                            onChange={(value) => setState((current) => current && cloneWithTarget(current, component.id, "y", value))}
                          />
                        </td>
                        <td>
                          <CoordinateInput
                            component={component}
                            axis="z"
                            onChange={(value) => setState((current) => current && cloneWithTarget(current, component.id, "z", value))}
                          />
                        </td>
                        <td>{formatNumber(layout?.layout2d?.x, 4)}</td>
                        <td>{formatNumber(layout?.layout2d?.y, 4)}</td>
                        <td>
                          {formatNumber(layout?.layout2d?.thetaDegrees, 2)}
                          {layout?.layout2d?.thetaAxis ? ` ${layout.layout2d.thetaAxis}` : ""}
                        </td>
                        <td>{component.bottomFaceName}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <aside className="side-column">
          {mcpHealth ? (
            <div className="panel health-panel">
              <div className="panel-heading">
                <h2>MCP Health</h2>
                <span className={`pill ${mcpHealth.status}`}>{mcpHealth.status}</span>
              </div>
              <p className="result-message">{mcpHealth.message}</p>
              <dl className="validation-summary">
                <dt>Assembly</dt>
                <dd>{formatHealthBool(mcpHealth.activeAssemblyMatchesState)}</dd>
                <dt>Mapping</dt>
                <dd>{formatHealthBool(mcpHealth.faceMappingPathsMatch)}</dd>
                <dt>Active</dt>
                <dd>{shortPath(String(mcpHealth.activeDocument?.path ?? mcpHealth.activeDocument?.documentPath ?? ""))}</dd>
                <dt>Expected</dt>
                <dd>{shortPath(mcpHealth.expectedAssemblyPath)}</dd>
                <dt>Backend map</dt>
                <dd>{shortPath(mcpHealth.faceMappingPath)}</dd>
                <dt>MCP map</dt>
                <dd>{shortPath(mcpHealth.mcpFaceMappingPath)}</dd>
              </dl>
            </div>
          ) : null}

          {mappingRows.length > 0 ? (
            <div className="panel mapping-panel">
              <div className="panel-heading">
                <h2>Face Mapping</h2>
                <span>{mappingRows.filter((row) => row.status === "missing").length} missing</span>
              </div>
              <div className="mapping-list">
                {mappingRows.map(({ component, status, toolCount }) => (
                  <div className="mapping-row" key={component.id}>
                    <div>
                      <strong>{component.componentName}</strong>
                      <span>{component.bottomFaceName}</span>
                    </div>
                    <span className={`mapping-status ${status}`}>
                      {status === "missing" ? "Missing" : status === "verified" ? "Verified" : "Ready"}
                    </span>
                    <span className="mapping-count">{toolCount ? `${toolCount} calls` : "not run"}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="panel">
            <div className="panel-heading">
              <h2>Result</h2>
              <span className={`pill ${effectiveStatus}`}>
                {effectiveStatus} / {state?.commonBaseReady ? "base ready" : "base pending"}
              </span>
            </div>
            <p className="result-message">{effectiveMessage}</p>
            <div className="component-results">
              {effectiveComponents.map((component) => (
                <div className="component-card" key={component.componentName}>
                  <div className="component-title">
                    <strong>{component.componentName}</strong>
                    <StatusIcon ok={component.moveResult?.success !== false && component.faceSelection?.success !== false} />
                  </div>
                  <dl>
                    <dt>Face</dt>
                    <dd>{component.faceSelection?.success ? "OK" : component.faceSelection?.message ?? "Not run"}</dd>
                    <dt>Mate</dt>
                    <dd>{component.bottomMateResult?.errorName ?? "Anchor / not run"}</dd>
                    <dt>Center</dt>
                    <dd>
                      {component.bottomFaceCenter?.center
                        ? component.bottomFaceCenter.center.map((value) => value.toFixed(4)).join(", ")
                        : "Not read"}
                    </dd>
                    <dt>Theta</dt>
                    <dd>
                      target {formatNumber(component.targetThetaDegrees, 2)} / current {formatNumber(component.currentThetaDegrees, 2)} / delta{" "}
                      {formatNumber(component.deltaThetaDegrees, 2)}
                    </dd>
                    <dt>Move</dt>
                    <dd>{component.moveResult?.message ?? "Not run"}</dd>
                    <dt>Rotate</dt>
                    <dd>{component.rotationResult?.message ?? "Not run"}</dd>
                  </dl>
                </div>
              ))}
            </div>
          </div>

          {(orientationCorrections.length > 0 || orientationChecks.length > 0) ? (
            <div className="panel diagnostics-panel">
              <div className="panel-heading">
                <h2>Orientation</h2>
                <span>{orientationChecks.length} checks</span>
              </div>
              {orientationCorrections.length > 0 ? (
                <div className="diagnostics-block">
                  <h3>Corrections</h3>
                  {orientationCorrections.map((item: OrientationCorrection, index: number) => (
                    <div className="diagnostic-card" key={`${item.stage}-${item.componentName}-${index}`}>
                      <div className="component-title">
                        <strong>{item.componentName}</strong>
                        <StatusIcon ok={item.success} />
                      </div>
                      <dl>
                        <dt>Stage</dt>
                        <dd>{item.stage ?? "n/a"}</dd>
                        <dt>Applied</dt>
                        <dd>{item.applied ? "Yes" : "No"}</dd>
                        <dt>Angle</dt>
                        <dd>{formatNumber(item.angleDegrees, 3)} deg</dd>
                        <dt>Axis</dt>
                        <dd>{formatVector(item.rotationAxis)}</dd>
                        <dt>Before</dt>
                        <dd>{formatVector(item.beforeProbe?.worldNormal)}</dd>
                        <dt>After</dt>
                        <dd>{formatVector(item.afterRotationProbe?.worldNormal)}</dd>
                        <dt>Message</dt>
                        <dd>{item.message ?? "n/a"}</dd>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}
              {orientationChecks.length > 0 ? (
                <div className="diagnostics-block">
                  <h3>Checks</h3>
                  {orientationChecks.map((item: OrientationCheck, index: number) => (
                    <div className="diagnostic-card" key={`${item.componentName}-${index}`}>
                      <div className="component-title">
                        <strong>{item.componentName}</strong>
                        <StatusIcon ok={item.success && item.matchesBase} />
                      </div>
                      <dl>
                        <dt>Match</dt>
                        <dd>{item.matchesBase ? "Yes" : "No"}</dd>
                        <dt>Dot</dt>
                        <dd>
                          {formatNumber(item.dotWithBase, 5)} / {formatNumber(item.normalDotThreshold, 2)}
                        </dd>
                        <dt>Normal</dt>
                        <dd>{formatVector(item.worldNormal ?? item.faceProbe?.worldNormal)}</dd>
                        <dt>Message</dt>
                        <dd>{item.message ?? "n/a"}</dd>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {replayValidation ? (
            <div className="panel validation-panel">
              <div className="panel-heading">
                <h2>Replay Check</h2>
                <span className={`pill ${replayValidation.success ? "ok" : "error"}`}>
                  {replayValidation.success ? "matched" : "review"}
                </span>
              </div>
              <p className="result-message">{replayValidation.message ?? "Replay validation completed."}</p>
              <dl className="validation-summary">
                <dt>Max XY</dt>
                <dd>
                  {formatNumber(replayValidation.maxXyError, 8)} / {formatNumber(replayValidation.xyToleranceMeters, 8)} m
                </dd>
                <dt>Max Theta</dt>
                <dd>
                  {formatNumber(replayValidation.maxThetaErrorDegrees, 6)} / {formatNumber(replayValidation.thetaToleranceDegrees, 6)} deg
                </dd>
                <dt>Capture</dt>
                <dd>{replayValidation.captureStatus ?? "n/a"}</dd>
              </dl>
              {replayValidation.components?.length ? (
                <div className="component-results compact">
                  {replayValidation.components.map((component) => (
                    <div className="component-card" key={component.componentName}>
                      <div className="component-title">
                        <strong>{component.componentName}</strong>
                        <StatusIcon ok={component.success} />
                      </div>
                      <dl>
                        <dt>XY error</dt>
                        <dd>
                          {formatNumber(component.xyError, 8)} / {formatNumber(component.xyToleranceMeters, 8)} m
                        </dd>
                        <dt>Theta error</dt>
                        <dd>
                          {formatNumber(component.thetaErrorDegrees, 6)} / {formatNumber(component.thetaToleranceDegrees, 6)} deg
                        </dd>
                        <dt>Message</dt>
                        <dd>{component.message ?? "n/a"}</dd>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="panel screenshot-panel">
            <div className="panel-heading">
              <h2>Screenshot</h2>
              <span>{screenshotUrl ? "Ready" : "Empty"}</span>
            </div>
            {screenshotUrl ? (
              <img src={screenshotUrl} alt="SolidWorks current view" />
            ) : (
              <div className="empty-shot">No image</div>
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}

const rootElement = document.getElementById("root") as HTMLElement & {
  __solidworksDemoRoot?: ReturnType<typeof createRoot>;
};
const applicationRoot = rootElement.__solidworksDemoRoot ?? createRoot(rootElement);
rootElement.__solidworksDemoRoot = applicationRoot;

applicationRoot.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
