import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Crosshair, Eye, FileJson, Loader2, RefreshCw, Save, ScanSearch, ShieldCheck } from "lucide-react";

import {
  FaceEndpointCatalogView,
  FaceEndpointView,
  FaceMatePatchApplyResult,
  FaceMatePatchPreview,
  applyFaceMatePatch,
  getFaceEndpointCatalog,
  highlightFaceEndpoint,
  previewFaceMatePatch
} from "./api";


const MATE_TYPES = [
  { value: 0, label: "重合" },
  { value: 2, label: "垂直" },
  { value: 3, label: "平行" },
  { value: 5, label: "距离" },
  { value: 6, label: "角度" }
];

function dominantNormal(values?: number[] | null): string {
  if (!values || values.length < 3) return "未知";
  const axes = ["X", "Y", "Z"];
  let index = 0;
  for (let cursor = 1; cursor < 3; cursor += 1) {
    if (Math.abs(values[cursor]) > Math.abs(values[index])) index = cursor;
  }
  return `${values[index] >= 0 ? "+" : "−"}${axes[index]}`;
}

function shortLeaf(value: string): string {
  return value.split("/").at(-1) ?? value;
}

function compactId(value?: string): string {
  if (!value) return "未选择";
  const parts = value.split(":");
  return parts.length >= 3 ? `${parts[1].toUpperCase()} · ${parts[2]}` : value;
}

function endpointLabel(endpoint: FaceEndpointView | null): string {
  return endpoint ? `${endpoint.moduleToken} / ${shortLeaf(endpoint.relativeLeafHierarchyPath)} / Face ${endpoint.faceIndex}` : "未选择";
}

function toolPayloadMessage(result: Awaited<ReturnType<typeof highlightFaceEndpoint>>): string {
  const text = result.toolResults?.at(-1)?.text;
  if (Array.isArray(text) && typeof text.at(-1) === "string") {
    try {
      const payload = JSON.parse(text.at(-1) as string) as { Message?: string; message?: string; Zoomed?: boolean };
      return `${payload.Message ?? payload.message ?? result.message}${payload.Zoomed === false ? "（已选中，未缩放）" : ""}`;
    } catch {
      return result.message;
    }
  }
  return result.message;
}

export function FaceEndpointWorkbench() {
  const [catalog, setCatalog] = useState<FaceEndpointCatalogView | null>(null);
  const [loading, setLoading] = useState(false);
  const [moduleFilter, setModuleFilter] = useState("ALL");
  const [leafFilter, setLeafFilter] = useState("ALL");
  const [normalFilter, setNormalFilter] = useState("ALL");
  const [minimumAreaMm2, setMinimumAreaMm2] = useState(100);
  const [faceA, setFaceA] = useState<FaceEndpointView | null>(null);
  const [faceB, setFaceB] = useState<FaceEndpointView | null>(null);
  const [mateType, setMateType] = useState(2);
  const [mateName, setMateName] = useState("界面新增垂直1");
  const [distanceMm, setDistanceMm] = useState(10);
  const [angleDegrees, setAngleDegrees] = useState(90);
  const [alignment, setAlignment] = useState(0);
  const [highlightingId, setHighlightingId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [patchPreview, setPatchPreview] = useState<FaceMatePatchPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [outputAssemblyPath, setOutputAssemblyPath] = useState("");
  const [applyConfirmed, setApplyConfirmed] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<FaceMatePatchApplyResult | null>(null);

  async function loadCatalog() {
    setLoading(true);
    setError(null);
    try {
      setCatalog(await getFaceEndpointCatalog());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCatalog();
  }, []);

  const availableLeaves = useMemo(() => {
    const endpoints = catalog?.endpoints ?? [];
    return Array.from(new Set(
      endpoints
        .filter((item) => moduleFilter === "ALL" || item.moduleToken === moduleFilter)
        .map((item) => item.relativeLeafHierarchyPath)
    )).sort();
  }, [catalog, moduleFilter]);

  const filtered = useMemo(() => {
    return (catalog?.endpoints ?? [])
      .filter((item) => moduleFilter === "ALL" || item.moduleToken === moduleFilter)
      .filter((item) => leafFilter === "ALL" || item.relativeLeafHierarchyPath === leafFilter)
      .filter((item) => normalFilter === "ALL" || dominantNormal(item.faceNormalWorld) === normalFilter)
      .filter((item) => item.faceAreaSquareMeters * 1_000_000 >= minimumAreaMm2)
      .sort((left, right) => right.faceAreaSquareMeters - left.faceAreaSquareMeters);
  }, [catalog, leafFilter, minimumAreaMm2, moduleFilter, normalFilter]);

  const compatibility = useMemo(() => {
    if (!faceA || !faceB) return { ok: false, text: "请选择来自两个模组的面A和面B。" };
    if (faceA.endpointId === faceB.endpointId) return { ok: false, text: "面A和面B不能是同一个端点。" };
    if (faceA.moduleHierarchyPath === faceB.moduleHierarchyPath) return { ok: false, text: "当前基础配合要求连接两个不同模组。" };
    if (faceA.geometryClass !== "Plane" || faceB.geometryClass !== "Plane") return { ok: false, text: "当前MVP仅验证两个平面端点。" };
    return { ok: true, text: `可生成${MATE_TYPES.find((item) => item.value === mateType)?.label ?? "基础"}配合Patch预览。` };
  }, [faceA, faceB, mateType]);

  async function handleHighlight(endpoint: FaceEndpointView) {
    if (!catalog) return;
    setHighlightingId(endpoint.endpointId);
    setError(null);
    setStatus(null);
    try {
      const result = await highlightFaceEndpoint(endpoint.endpointId, catalog.catalogPath, true);
      if (result.status !== "ok") throw new Error(result.message);
      setStatus(toolPayloadMessage(result));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setHighlightingId(null);
    }
  }

  async function handlePreview() {
    if (!catalog || !faceA || !faceB || !compatibility.ok) return;
    setPreviewing(true);
    setError(null);
    setPatchPreview(null);
    try {
      const preview = await previewFaceMatePatch({
        catalogPath: catalog.catalogPath,
        faceAEndpointId: faceA.endpointId,
        faceBEndpointId: faceB.endpointId,
        mateType,
        mateName,
        alignment,
        distanceMeters: mateType === 5 ? distanceMm / 1000 : null,
        angleDegrees: mateType === 6 ? angleDegrees : null
      });
      setPatchPreview(preview);
      setOutputAssemblyPath(preview.suggestedOutputAssemblyPath);
      setApplyConfirmed(false);
      setApplyResult(null);
      setStatus(preview.message);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleApply() {
    if (!catalog || !faceA || !faceB || !patchPreview || !applyConfirmed || !outputAssemblyPath.trim()) return;
    setApplying(true);
    setError(null);
    setApplyResult(null);
    try {
      const result = await applyFaceMatePatch({
        catalogPath: catalog.catalogPath,
        sourceGraphPath: patchPreview.sourceGraphPath,
        faceAEndpointId: faceA.endpointId,
        faceBEndpointId: faceB.endpointId,
        mateType,
        mateName,
        alignment,
        distanceMeters: mateType === 5 ? distanceMm / 1000 : null,
        angleDegrees: mateType === 6 ? angleDegrees : null,
        previewDigest: patchPreview.previewDigest,
        outputAssemblyPath: outputAssemblyPath.trim(),
        confirmed: true
      });
      setApplyResult(result);
      if (!result.success) throw new Error(result.message);
      setStatus(result.message);
      setApplyConfirmed(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setApplying(false);
    }
  }

  return (
    <section className="face-workbench panel" aria-labelledby="face-workbench-title">
      <div className="face-workbench-heading">
        <div>
          <span className="eyebrow">项目02 · 可编辑配合图</span>
          <h2 id="face-workbench-title">面端点目录与选择器</h2>
          <p>浏览已完成的单叶扫描结果，目测高亮候选面，并生成只读Patch预览。</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void loadCatalog()} disabled={loading}>
          {loading ? <Loader2 className="spin" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
          刷新目录
        </button>
      </div>

      {error ? <div className="banner error">{error}</div> : null}
      {status ? <div className="face-workbench-status"><CheckCircle2 aria-hidden="true" />{status}</div> : null}

      <div className="face-catalog-summary">
        <div><span>目录端点</span><strong>{catalog?.endpointCount ?? "—"}</strong></div>
        <div><span>已扫描叶</span><strong>{catalog?.mergedLeafSelectors?.length ?? 0}</strong></div>
        <div><span>当前候选</span><strong>{filtered.length}</strong></div>
        <div><span>模式</span><strong>{catalog?.catalogMode ?? "载入中"}</strong></div>
      </div>

      <div className="face-workbench-grid">
        <div className="face-browser">
          <div className="face-filter-grid">
            <label>模组
              <select value={moduleFilter} onChange={(event) => { setModuleFilter(event.target.value); setLeafFilter("ALL"); }}>
                <option value="ALL">全部</option>
                {(catalog?.modules ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label>叶零件
              <select value={leafFilter} onChange={(event) => setLeafFilter(event.target.value)}>
                <option value="ALL">全部</option>
                {availableLeaves.map((value) => <option key={value} value={value}>{shortLeaf(value)}</option>)}
              </select>
            </label>
            <label>世界法向
              <select value={normalFilter} onChange={(event) => setNormalFilter(event.target.value)}>
                {['ALL', '+X', '−X', '+Y', '−Y', '+Z', '−Z'].map((value) => <option key={value} value={value}>{value === 'ALL' ? '全部' : value}</option>)}
              </select>
            </label>
            <label>最小面积 mm²
              <input type="number" min="0" step="10" value={minimumAreaMm2} onChange={(event) => setMinimumAreaMm2(Number(event.target.value) || 0)} />
            </label>
          </div>

          <div className="face-table-wrap">
            <table className="face-table">
              <thead><tr><th>端点</th><th>叶零件 / 面</th><th>面积</th><th>法向</th><th>操作</th></tr></thead>
              <tbody>
                {filtered.slice(0, 60).map((endpoint) => (
                  <tr key={endpoint.endpointId} className={faceA?.endpointId === endpoint.endpointId || faceB?.endpointId === endpoint.endpointId ? "selected" : ""}>
                    <td><strong>{compactId(endpoint.endpointId)}</strong><small>{endpoint.moduleToken}</small></td>
                    <td><span>{shortLeaf(endpoint.relativeLeafHierarchyPath)}</span><small>Body {endpoint.bodyIndex} / Face {endpoint.faceIndex}</small></td>
                    <td>{(endpoint.faceAreaSquareMeters * 1_000_000).toFixed(1)} mm²</td>
                    <td><span className="normal-chip">{dominantNormal(endpoint.faceNormalWorld)}</span></td>
                    <td><div className="face-row-actions">
                      <button type="button" title="在SolidWorks中高亮" onClick={() => void handleHighlight(endpoint)} disabled={Boolean(highlightingId)}>
                        {highlightingId === endpoint.endpointId ? <Loader2 className="spin" /> : <Eye />}
                      </button>
                      <button type="button" onClick={() => { setFaceA(endpoint); setPatchPreview(null); setApplyResult(null); setApplyConfirmed(false); }}>设为A</button>
                      <button type="button" onClick={() => { setFaceB(endpoint); setPatchPreview(null); setApplyResult(null); setApplyConfirmed(false); }}>设为B</button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filtered.length && !loading ? <div className="face-empty"><ScanSearch />当前筛选条件下没有候选面。</div> : null}
          </div>
        </div>

        <div className="mate-builder">
          <div className="selected-face-card"><span>面 A</span><strong>{endpointLabel(faceA)}</strong><small>{compactId(faceA?.endpointId)}</small></div>
          <div className="selected-face-card"><span>面 B</span><strong>{endpointLabel(faceB)}</strong><small>{compactId(faceB?.endpointId)}</small></div>

          <div className={`compatibility-note ${compatibility.ok ? "good" : "warn"}`}>
            {compatibility.ok ? <CheckCircle2 /> : <Crosshair />}{compatibility.text}
          </div>

          <label>配合类型
            <select value={mateType} onChange={(event) => { const value = Number(event.target.value); setMateType(value); setMateName(`界面新增${MATE_TYPES.find((item) => item.value === value)?.label ?? "基础"}1`); setPatchPreview(null); }}>
              {MATE_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label>配合名称<input value={mateName} onChange={(event) => setMateName(event.target.value)} /></label>
          <label>方向
            <select value={alignment} onChange={(event) => setAlignment(Number(event.target.value))}>
              <option value={0}>Aligned</option><option value={1}>Anti-aligned</option>
            </select>
          </label>
          {mateType === 5 ? <label>距离 mm<input type="number" min="0" step="1" value={distanceMm} onChange={(event) => setDistanceMm(Number(event.target.value) || 0)} /></label> : null}
          {mateType === 6 ? <label>角度 °<input type="number" step="1" value={angleDegrees} onChange={(event) => setAngleDegrees(Number(event.target.value) || 0)} /></label> : null}

          <button className="primary-button mate-preview-button" type="button" disabled={!compatibility.ok || previewing} onClick={() => void handlePreview()}>
            {previewing ? <Loader2 className="spin" /> : <FileJson />}
            检查并生成Patch预览
          </button>
          <small className="safety-note">安全边界：此页面不会创建、覆盖或保存SolidWorks装配体。</small>

          {patchPreview ? (
            <div className="patch-preview">
              <div><strong>预检通过</strong><span>{patchPreview.effectiveSummary.moduleCount} 模组 / {patchPreview.effectiveSummary.mateCount} 条有效配合</span></div>
              <pre>{JSON.stringify(patchPreview.patch, null, 2)}</pre>
              <div className="mate-apply-panel">
                <div className="mate-apply-heading"><ShieldCheck /><strong>第二步：确认后另存新装配体</strong></div>
                <label>新装配体路径
                  <input
                    value={outputAssemblyPath}
                    onChange={(event) => { setOutputAssemblyPath(event.target.value); setApplyConfirmed(false); setApplyResult(null); }}
                  />
                </label>
                <small>只允许保存到工作区的 demo/mate_graph_edit/ui_runs；任何同名SLDASM或审计JSON均拒绝覆盖。</small>
                <label className="mate-apply-confirm">
                  <input type="checkbox" checked={applyConfirmed} onChange={(event) => setApplyConfirmed(event.target.checked)} />
                  我已核对面A、面B、配合类型和输出路径，并确认创建一个新的装配体。
                </label>
                <button
                  className="primary-button"
                  type="button"
                  disabled={!applyConfirmed || applying || !outputAssemblyPath.trim()}
                  onClick={() => void handleApply()}
                >
                  {applying ? <Loader2 className="spin" /> : <Save />}
                  应用Patch、另存并重开复核
                </button>
                {applyResult?.success ? (
                  <div className="mate-apply-result">
                    <CheckCircle2 />
                    <div>
                      <strong>SolidWorks闭环通过</strong>
                      <span>
                        请求 {applyResult.rebuildSummary.requestedMateCount ?? "—"} / 创建 {applyResult.rebuildSummary.createdMateCount ?? "—"} / 重开 {applyResult.rebuildSummary.reopenedMateCount ?? "—"}
                      </span>
                      <span>
                        创建错误 {applyResult.rebuildSummary.mateCreationErrorsClear === true ? "已清零" : applyResult.rebuildSummary.mateCreationErrorsClear === false ? "未清零" : "—"} / 组件过约束 {applyResult.rebuildSummary.componentsNotOverConstrained === true ? "无" : applyResult.rebuildSummary.componentsNotOverConstrained === false ? "存在" : "—"} / 刚柔性 {applyResult.rebuildSummary.componentSemanticsMatch === true ? "一致" : applyResult.rebuildSummary.componentSemanticsMatch === false ? "不一致" : "—"}
                      </span>
                      <small>{applyResult.artifacts.outputAssemblyPath}</small>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
