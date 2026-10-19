import { useEffect, useState } from "react";
import { CheckCircle2, FileJson, Link2, Loader2, Network, RefreshCw, Save, ShieldAlert } from "lucide-react";

import {
  SemanticConnectionApplyResult,
  SemanticConnectionPreview,
  SemanticPortCatalogView,
  applySemanticConnection,
  getSemanticPortCatalog,
  previewSemanticAssemblyIntent
} from "./api";


function shortPath(value?: string | null): string {
  if (!value) return "—";
  return value.split(/[\\/]/).at(-1) ?? value;
}

export function SemanticPortWorkbench() {
  const [catalog, setCatalog] = useState<SemanticPortCatalogView | null>(null);
  const [preview, setPreview] = useState<SemanticConnectionPreview | null>(null);
  const [applyResult, setApplyResult] = useState<SemanticConnectionApplyResult | null>(null);
  const [outputPath, setOutputPath] = useState("");
  const [requirement, setRequirement] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadCatalog() {
    setLoading(true);
    setError(null);
    try {
      const result = await getSemanticPortCatalog();
      setCatalog(result);
      setRequirement(result.defaultNaturalLanguageRequirement);
      setPreview(null);
      setApplyResult(null);
      setConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCatalog();
  }, []);

  async function handlePreview() {
    if (!catalog) return;
    setPreviewing(true);
    setError(null);
    setApplyResult(null);
    setConfirmed(false);
    try {
      const result = await previewSemanticAssemblyIntent({
        requirement,
        semanticCatalogPath: catalog.semanticCatalogPath,
        endpointCatalogPath: catalog.endpointCatalogPath,
        sourceGraphPath: catalog.sourceGraphPath,
        planTemplatePath: catalog.demoRequestPath
      });
      setPreview(result);
      setOutputPath(result.suggestedOutputAssemblyPath);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleApply() {
    if (!catalog || !preview || !confirmed) return;
    setApplying(true);
    setError(null);
    try {
      const result = await applySemanticConnection({
        semanticCatalogPath: catalog.semanticCatalogPath,
        endpointCatalogPath: catalog.endpointCatalogPath,
        sourceGraphPath: catalog.sourceGraphPath,
        connectionRequest: preview.connectionRequest,
        previewDigest: preview.previewDigest,
        outputAssemblyPath: outputPath,
        confirmed: true,
        executionMode: "context_incremental"
      });
      setApplyResult(result);
      if (!result.success) setError(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setApplying(false);
    }
  }

  return (
    <section className="panel semantic-port-workbench" id="semantic-port-workbench">
      <div className="semantic-port-heading">
        <div>
          <span className="eyebrow">Project 02 · Complete semantic installation</span>
          <h2>多端口安装计划与增量配合图</h2>
          <p>将工程端口绑定到稳定面端点；驱动配合负责定位，验证关系保留工艺尺寸但不制造过约束。</p>
        </div>
        <button type="button" onClick={() => void loadCatalog()} disabled={loading}>
          {loading ? <Loader2 className="spin" /> : <RefreshCw />}重新加载
        </button>
      </div>

      {error ? <div className="semantic-port-error"><ShieldAlert />{error}</div> : null}

      {catalog ? (
        <>
          {catalog.latestClosure ? (
            <div className={catalog.latestClosure.success ? "semantic-success" : "semantic-port-error"}>
              {catalog.latestClosure.success ? <CheckCircle2 /> : <ShieldAlert />}
              <div>
                <strong>最新实体发布闭环：{catalog.latestClosure.status}</strong>
                <small>
                  实例映射：{Object.entries(catalog.latestClosure.instancesByModuleToken ?? {})
                    .map(([token, instance]) => `${token}=${instance}`)
                    .join("；") || "—"}
                </small>
                <small>
                  精确检查 {catalog.latestClosure.releaseGate?.interferenceSummary?.completedExactPairCount ?? 0} 对；
                  新增干涉 {catalog.latestClosure.releaseGate?.interferenceSummary?.newInterferenceCount ?? 0}；
                  证据{catalog.latestClosure.cacheReused ? "已安全复用" : "本轮新生成"}；
                  编排耗时 {(catalog.latestClosure.timing?.durationSeconds ?? 0).toFixed(3)} s
                </small>
                <small>{catalog.latestClosurePath}</small>
              </div>
            </div>
          ) : null}

          <div className="semantic-flow-strip" aria-label="semantic port compilation flow">
            <span>工程意图</span><strong>→</strong><span>语义端口</span><strong>→</strong><span>面端点</span><strong>→</strong><span>配合图 Patch</span><strong>→</strong><span>上下文增量装配</span>
          </div>

          <div className="semantic-port-grid">
            {catalog.ports.map((port) => (
              <article className="semantic-port-card" key={port.portId}>
                <div className="semantic-port-card-title">
                  <Network />
                  <div><strong>{port.displayName}</strong><small>{port.portId}</small></div>
                </div>
                <dl>
                  <dt>模组</dt><dd>{port.moduleToken}</dd>
                  <dt>接口</dt><dd>{port.interfaceType}</dd>
                  <dt>证据</dt><dd>{port.evidence ?? "—"}</dd>
                  <dt>状态</dt><dd>{port.status}</dd>
                </dl>
                {port.endpointBindings.map((binding) => (
                  <div className="semantic-endpoint-binding" key={binding.endpointId}>
                    <Link2 />
                    <div>
                      <strong>{binding.role} → {binding.endpointId}</strong>
                      <small>{shortPath(binding.leafHierarchyPath)} / Face {binding.faceIndex ?? "—"} / {binding.geometryClass ?? "—"}</small>
                    </div>
                  </div>
                ))}
              </article>
            ))}
          </div>

          <div className="semantic-action-grid">
            <article className="semantic-intent-card">
              <span>自然语言工程需求</span>
              <textarea
                value={requirement}
                rows={7}
                onChange={(event) => {
                  setRequirement(event.target.value);
                  setPreview(null);
                  setApplyResult(null);
                  setConfirmed(false);
                }}
              />
              <small>受控解析器只生成工程意图，不生成Face；端口必须来自已验证目录，歧义或刚柔性冲突会阻断执行。</small>
              <button className="primary-button" type="button" onClick={() => void handlePreview()} disabled={previewing || !requirement.trim()}>
                {previewing ? <Loader2 className="spin" /> : <FileJson />}解析需求、选择端口并预览
              </button>
            </article>

            {preview ? (
              <article className="semantic-preview-card">
                <div className="semantic-preview-title"><CheckCircle2 /><strong>图级预检通过</strong></div>
                {preview.parsedIntent ? (
                  <div className="semantic-intent-summary">
                    <strong>结构化意图</strong>
                    <span>新增：{preview.parsedIntent.moduleToAdd}</span>
                    <span>固定上下文：{preview.parsedIntent.fixedContextModules.join("、")}</span>
                    <span>刚柔性：{Object.entries(preview.parsedIntent.componentSolvingStates).map(([token, state]) => `${token}=${state}`).join("、") || "继承目录"}</span>
                    <span>关系：{preview.parsedIntent.relationships.map((item) => `${item.sourceModule}→${item.targetModule} ${item.purpose}/${item.applicationMode}`).join("；")}</span>
                  </div>
                ) : null}
                {preview.intentResolution ? (
                  <div className="semantic-selection-list">
                    <strong>语义端口选择</strong>
                    {preview.intentResolution.selectionAudit.map((item) => (
                      <div key={item.relationshipId}>
                        <span>{item.selected.portAId} ↔ {item.selected.portBId}</span>
                        <small>{item.selected.templateId} · 得分 {item.selected.score} · {item.selected.reason}</small>
                      </div>
                    ))}
                    {preview.intentResolution.solvingStateChecks.map((item) => (
                      <div key={item.moduleToken}>
                        <span>{item.moduleToken}：要求 {item.requested} / 目录 {item.catalogState ?? "unknown"}</span>
                        <small>{item.matched ? "刚柔性门禁通过" : "刚柔性冲突"}</small>
                      </div>
                    ))}
                  </div>
                ) : null}
                <dl>
                  <dt>新增节点</dt><dd>{preview.effectiveSummary.addedComponent ?? "无"}</dd>
                  <dt>有效图</dt><dd>{preview.effectiveSummary.effectiveModuleCount} 模组 / {preview.effectiveSummary.effectiveMateCount} 配合</dd>
                  <dt>连接计划</dt><dd>{preview.effectiveSummary.connectionCount ?? 1} 组语义连接</dd>
                  <dt>驱动配合</dt><dd>{preview.effectiveSummary.generatedMateCount} 条（{preview.effectiveSummary.generatedMateNames?.join("、") ?? "见Patch"}）</dd>
                  <dt>验证关系</dt><dd>{preview.effectiveSummary.validationRelationCount ?? 0} 条（只核验，不重复驱动）</dd>
                  <dt>原型修改</dt><dd>{preview.executionBoundary.modifiesPrototype ? "是" : "否"}</dd>
                  <dt>执行模式</dt><dd>{preview.executionBoundary.mode === "context_incremental" ? "复制上下文后真实插入" : "空白装配体重建"}</dd>
                  <dt>父级上下文</dt><dd>{preview.executionBoundary.preservesExistingParentContext ? "保留" : "不保留"}</dd>
                  <dt>完全定位</dt><dd>{preview.executionBoundary.fullyLocatesAddedComponent ? "是，CAD阶段已验证" : "尚待CAD验证"}</dd>
                </dl>
                <div className="semantic-warning">
                  “重合13＋宽度4＋距离27”作为驱动配合定位 A500；“距离8=50 mm”已识别为冗余工艺关系，降级为验证项，避免过约束。
                </div>
                <label>独立新装配体路径
                  <input value={outputPath} onChange={(event) => { setOutputPath(event.target.value); setConfirmed(false); }} />
                </label>
                <label className="semantic-confirm">
                  <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                  我已核对端口、Patch 与输出路径，确认复制原装配上下文、移除原A500并从独立文件重新插入；原型文件不修改。
                </label>
                <button className="primary-button" type="button" disabled={!confirmed || applying || !outputPath.trim()} onClick={() => void handleApply()}>
                  {applying ? <Loader2 className="spin" /> : <Save />}重建、另存并重开复核
                </button>
              </article>
            ) : null}
          </div>

          {applyResult?.success ? (
            <div className="semantic-success">
              <CheckCircle2 />
              <div>
                <strong>SolidWorks 上下文增量插入与尺寸复核通过</strong>
                <small>{applyResult.artifacts.outputAssemblyPath}</small>
                {applyResult.validationSummary ? (
                  <small>
                    validate_only：{applyResult.validationSummary.passedCount}/{applyResult.validationSummary.relationCount}通过；
                    {applyResult.validationSummary.results.map((item) => (
                      `${item.RelationName ?? "关系"} 实测${((item.MeasuredDistanceMeters ?? 0) * 1000).toFixed(3)} mm`
                    )).join("；")}
                  </small>
                ) : null}
                {applyResult.releaseGate && !applyResult.releaseGate.releaseAllowed ? (
                  <small>发布状态：待实体干涉门禁。{applyResult.releaseGate.message}</small>
                ) : null}
              </div>
            </div>
          ) : null}
        </>
      ) : loading ? <div className="semantic-loading"><Loader2 className="spin" />正在加载语义端口目录…</div> : null}
    </section>
  );
}
