import React, { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, CheckCircle2, FileJson, Layers, Loader2, MapPinned, Move3D, Play, RefreshCw, RotateCcw, Save, Upload, XCircle } from "lucide-react";
import {
  applyCapturedLayout,
  arrange,
  captureCommonBaseLayout,
  captureProjectLayout,
  DemoComponent,
  DemoState,
  discoverComponents,
  DiscoveredComponent,
  DiscoveryResult,
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
  syncDiscoveredComponents,
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

function App() {
  const [state, setState] = useState<DemoState | null>(null);
  const [layoutFiles, setLayoutFiles] = useState<LayoutJsonInfo[]>([]);
  const [result, setResult] = useState<OperationResult | null>(null);
  const [mcpHealth, setMcpHealth] = useState<McpHealthResult | null>(null);
  const [sourceAssemblyPath, setSourceAssemblyPath] = useState("");
  const [projectLayoutOutputPath, setProjectLayoutOutputPath] = useState("demo/project_layout2d.json");
  const [projectConfigOutputPath, setProjectConfigOutputPath] = useState("demo/project_config.json");
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

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
