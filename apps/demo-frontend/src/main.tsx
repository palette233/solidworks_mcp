import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, Loader2, Play, RefreshCw, RotateCcw, Save, XCircle } from "lucide-react";
import {
  arrange,
  DemoComponent,
  DemoState,
  getState,
  OperationResult,
  parseArrangePayload,
  resetState,
  saveState
} from "./api";
import "./styles.css";

function cloneWithTarget(state: DemoState, id: string, axis: "x" | "y" | "z", value: number): DemoState {
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

function numberValue(value: number): string {
  return Number.isFinite(value) ? String(value) : "0";
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
  axis: "x" | "y" | "z";
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

function App() {
  const [state, setState] = useState<DemoState | null>(null);
  const [result, setResult] = useState<OperationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const arrangePayload = useMemo(() => parseArrangePayload(result), [result]);
  const effectiveComponents = arrangePayload?.components ?? state?.lastRun?.components ?? [];
  const effectiveMessage = arrangePayload?.message ?? state?.lastRun?.toolMessage ?? result?.message ?? "等待执行";
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
          <p>A/B/C 子装配体底面中心坐标排布控制台</p>
        </div>
        <div className="toolbar" aria-label="Actions">
          <button className="icon-button" type="button" onClick={load} disabled={busy} title="刷新状态">
            <RefreshCw aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={handleSave} disabled={busy || !state} title="保存坐标">
            <Save aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={handleReset} disabled={busy} title="重置状态">
            <RotateCcw aria-hidden="true" />
          </button>
          <button className="primary-button" type="button" onClick={handleArrange} disabled={busy || !state}>
            {busy ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
            执行排布
          </button>
        </div>
      </header>

      {error ? <div className="banner error">{error}</div> : null}

      <section className="layout-grid">
        <div className="panel table-panel">
          <div className="panel-heading">
            <h2>坐标</h2>
            <span>{state?.updatedAt ? new Date(state.updatedAt).toLocaleString() : "未加载"}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>组件</th>
                  <th>当前 X</th>
                  <th>当前 Y</th>
                  <th>当前 Z</th>
                  <th>底面中心 X</th>
                  <th>底面中心 Y</th>
                  <th>底面中心 Z</th>
                  <th>底面</th>
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

        <aside className="side-column">
          <div className="panel">
            <div className="panel-heading">
              <h2>结果</h2>
              <span className={`pill ${effectiveStatus}`}>{effectiveStatus}</span>
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
                    <dt>选面</dt>
                    <dd>{component.faceSelection?.success ? "成功" : component.faceSelection?.message ?? "未执行"}</dd>
                    <dt>配合</dt>
                    <dd>{component.bottomMateResult?.errorName ?? "锚点/未执行"}</dd>
                    <dt>中心</dt>
                    <dd>
                      {component.bottomFaceCenter?.center
                        ? component.bottomFaceCenter.center.map((value) => value.toFixed(4)).join(", ")
                        : "未读取"}
                    </dd>
                    <dt>移动</dt>
                    <dd>{component.moveResult?.message ?? "未执行"}</dd>
                  </dl>
                </div>
              ))}
            </div>
          </div>

          <div className="panel screenshot-panel">
            <div className="panel-heading">
              <h2>截图</h2>
              <span>{screenshotUrl ? "已生成" : "未生成"}</span>
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
