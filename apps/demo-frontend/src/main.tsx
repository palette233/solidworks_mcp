import React, { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, Layers, Loader2, Move3D, Play, RefreshCw, RotateCcw, Save, XCircle } from "lucide-react";
import {
  arrange,
  DemoComponent,
  DemoState,
  finalizeCommonBase,
  getState,
  initializeCommonBase,
  OperationResult,
  parseArrangePayload,
  resetState,
  saveState
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

function blockSpec(component: DemoComponent): BlockSpec {
  return BLOCK_SPECS[component.id] ?? { width: 0.14, height: 0.1, color: "#66727f" };
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
  const [result, setResult] = useState<OperationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const arrangePayload = useMemo(() => parseArrangePayload(result), [result]);
  const effectiveComponents = arrangePayload?.components ?? state?.lastRun?.components ?? [];
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
      setState(await getState());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
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
                    <th>Face</th>
                  </tr>
                </thead>
                <tbody>
                  {state?.components.map((component) => (
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
                      <td>{component.bottomFaceName}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <aside className="side-column">
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
                    <dt>Move</dt>
                    <dd>{component.moveResult?.message ?? "Not run"}</dd>
                  </dl>
                </div>
              ))}
            </div>
          </div>

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
