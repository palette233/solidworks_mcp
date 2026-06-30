import React, { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, CheckCircle2, FileJson, Layers, Loader2, MapPinned, Move3D, Play, RefreshCw, RotateCcw, Save, Upload, XCircle } from "lucide-react";
import {
  applyCapturedLayout,
  arrange,
  captureCommonBaseLayout,
  DemoComponent,
  DemoState,
  finalizeCommonBase,
  getMcpHealth,
  getState,
  initializeCommonBase,
  LayoutComponentSummary,
  LayoutJsonInfo,
  McpHealthResult,
  listLayoutJsonFiles,
  OperationResult,
  OrientationCheck,
  OrientationCorrection,
  parseArrangePayload,
  resetState,
  saveState,
  selectLayoutJson,
  uploadLayoutJson,
  verifyFaceMappings
} from "./api";
import "./styles.css";

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

const WORLD_BOUNDS: WorldBounds = {
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
  disabled,
  onMove
}: {
  state: DemoState;
  disabled: boolean;
  onMove: (id: string, x: number, y: number) => void;
}) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const worldWidth = WORLD_BOUNDS.maxX - WORLD_BOUNDS.minX;
  const worldHeight = WORLD_BOUNDS.maxY - WORLD_BOUNDS.minY;

  function toScreenX(worldX: number): number {
    return ((worldX - WORLD_BOUNDS.minX) / worldWidth) * 100;
  }

  function toScreenY(worldY: number): number {
    return ((WORLD_BOUNDS.maxY - worldY) / worldHeight) * 100;
  }

  function pointerToWorld(event: PointerEvent<HTMLDivElement>) {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) {
      return null;
    }

    const localX = clamp(event.clientX - rect.left, 0, rect.width);
    const localY = clamp(event.clientY - rect.top, 0, rect.height);
    const worldX = WORLD_BOUNDS.minX + (localX / rect.width) * worldWidth;
    const worldY = WORLD_BOUNDS.maxY - (localY / rect.height) * worldHeight;
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
          X {WORLD_BOUNDS.minX}..{WORLD_BOUNDS.maxX} m, Y {WORLD_BOUNDS.minY}..{WORLD_BOUNDS.maxY} m
        </span>
      </div>
      <div
        ref={canvasRef}
        className="layout-canvas"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div className="axis x-axis" />
        <div className="axis y-axis" />
        {state.components.map((component) => {
          const spec = blockSpec(component);
          const widthPercent = (spec.width / worldWidth) * 100;
          const heightPercent = (spec.height / worldHeight) * 100;
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

function App() {
  const [state, setState] = useState<DemoState | null>(null);
  const [layoutFiles, setLayoutFiles] = useState<LayoutJsonInfo[]>([]);
  const [result, setResult] = useState<OperationResult | null>(null);
  const [mcpHealth, setMcpHealth] = useState<McpHealthResult | null>(null);
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

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const [nextState, nextLayoutFiles] = await Promise.all([getState(), listLayoutJsonFiles()]);
      setState(nextState);
      setLayoutFiles(nextLayoutFiles);
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
      const nextResult = await applyCapturedLayout();
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

      <section className="layout-grid">
        <div className="main-column">
          {state ? (
            <LayoutCanvas
              state={state}
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
                <dd>{formatNumber(replayValidation.maxXyError, 8)} m</dd>
                <dt>Max Theta</dt>
                <dd>{formatNumber(replayValidation.maxThetaErrorDegrees, 6)} deg</dd>
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
                        <dd>{formatNumber(component.xyError, 8)} m</dd>
                        <dt>Theta error</dt>
                        <dd>{formatNumber(component.thetaErrorDegrees, 6)} deg</dd>
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

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
