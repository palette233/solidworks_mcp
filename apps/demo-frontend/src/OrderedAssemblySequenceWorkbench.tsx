import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  GitBranch,
  Loader2,
  ShieldCheck,
  Workflow
} from "lucide-react";

import {
  OrderedAssemblyPreview,
  OrderedAssemblyClosure,
  OrderedAssemblyValidatedRun,
  OrderedAssemblyJob,
  OrderedAssemblyPipelineAudit,
  OrderedAssemblyDependencyAudit,
  OrderedAssemblyReleaseContract,
  OrderedAssemblyStep,
  pauseOrderedSemanticAssemblyJob,
  createOrderedSemanticAssemblyJob,
  loadOrderedSemanticAssemblyClosure,
  loadOrderedSemanticAssemblyPipelineAudit,
  loadOrderedSemanticAssemblyDependencyAudit,
  loadOrderedSemanticAssemblyReleaseContract,
  loadOrderedSemanticAssemblyJob,
  previewOrderedSemanticAssembly,
  resumeOrderedSemanticAssemblyJob,
  runOrderedSemanticAssemblyValidatedDemo
} from "./api";


type SupportedJobProject = "project01" | "project02" | "project03" | "project05";

const DEFAULT_REQUIREMENTS: Record<SupportedJobProject, string> = {
  project01:
    "项目01：以JJ00为基座，先添加SS00，再添加FF00，然后添加SM00，接着添加GN00，再添加BD00，然后添加GJ00，最后添加LM00。",
  project02:
    "项目02：以A600为基座，先添加A800，再添加A180，然后添加A700，接着添加A300，再添加A500，然后添加A100，再添加A200，最后添加T401。",
  project03:
    "项目03：以AA00为基座，先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，再添加AH00，然后添加AJ00，最后添加AB00。",
  project05:
    "项目05：以A000为基座，先添加D000，再添加K000，然后添加F000，接着添加M000，再添加G000，然后添加N000，接着添加P000，最后添加B000。"
};

function statusMeta(step: OrderedAssemblyStep) {
  if (step.status === "blocked_by_order") {
    return {
      className: "blocked",
      label: "顺序阻断",
      icon: <AlertTriangle aria-hidden="true" />
    };
  }
  if (step.status === "cad_validated_single_step") {
    return {
      className: "validated",
      label: "单步 CAD 已验证",
      icon: <CheckCircle2 aria-hidden="true" />
    };
  }
  if (step.implementationStatus === "top_level_cad_validated_release_blocked") {
    return {
      className: "blocked",
      label: "顶层已装配，发布被拒绝",
      icon: <AlertTriangle aria-hidden="true" />
    };
  }
  return {
    className: "planned",
    label: "规划完成，待补 CAD 模板",
    icon: <CircleDashed aria-hidden="true" />
  };
}

function tokenList(values: string[]) {
  return values.length ? values.join("、") : "无";
}

export function OrderedAssemblySequenceWorkbench() {
  const [projectId, setProjectId] = useState<SupportedJobProject>("project02");
  const [requirement, setRequirement] = useState(DEFAULT_REQUIREMENTS.project02);
  const [preview, setPreview] = useState<OrderedAssemblyPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [closure, setClosure] = useState<OrderedAssemblyClosure | null>(null);
  const [pipelineAudit, setPipelineAudit] = useState<OrderedAssemblyPipelineAudit | null>(null);
  const [dependencyAudit, setDependencyAudit] = useState<OrderedAssemblyDependencyAudit | null>(null);
  const [releaseContract, setReleaseContract] = useState<OrderedAssemblyReleaseContract | null>(null);
  const [validatedRun, setValidatedRun] = useState<OrderedAssemblyValidatedRun | null>(null);
  const [runningValidatedDemo, setRunningValidatedDemo] = useState(false);
  const [job, setJob] = useState<OrderedAssemblyJob | null>(null);
  const [jobBusy, setJobBusy] = useState(false);
  const [executionMode, setExecutionMode] = useState<"validated_artifact_replay" | "live_cad">(
    "validated_artifact_replay"
  );

  useEffect(() => {
    setReleaseContract(null);
    void loadOrderedSemanticAssemblyReleaseContract(projectId)
      .then(setReleaseContract)
      .catch(() => setReleaseContract(null));
    if (projectId !== "project02") {
      setClosure(null);
      setPipelineAudit(null);
      setDependencyAudit(null);
      return;
    }
    void loadOrderedSemanticAssemblyClosure()
      .then(setClosure)
      .catch(() => setClosure(null));
    void loadOrderedSemanticAssemblyPipelineAudit()
      .then(setPipelineAudit)
      .catch(() => setPipelineAudit(null));
    void loadOrderedSemanticAssemblyDependencyAudit()
      .then(setDependencyAudit)
      .catch(() => setDependencyAudit(null));
  }, [projectId]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadOrderedSemanticAssemblyJob(job.jobId)
        .then(setJob)
        .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.jobId, job?.status]);

  async function handlePreview() {
    setLoading(true);
    setError(null);
    try {
      setPreview(await previewOrderedSemanticAssembly(requirement, projectId));
    } catch (reason) {
      setPreview(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  async function handleValidatedDemo() {
    setRunningValidatedDemo(true);
    setError(null);
    try {
      setValidatedRun(await runOrderedSemanticAssemblyValidatedDemo(requirement));
    } catch (reason) {
      setValidatedRun(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunningValidatedDemo(false);
    }
  }

  async function handleCreateJob() {
    setJobBusy(true);
    setError(null);
    try {
      setJob(await createOrderedSemanticAssemblyJob(requirement, executionMode, projectId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setJobBusy(false);
    }
  }

  async function handlePauseJob() {
    if (!job) return;
    setJobBusy(true);
    try {
      setJob(await pauseOrderedSemanticAssemblyJob(job.jobId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setJobBusy(false);
    }
  }

  async function handleResumeJob() {
    if (!job) return;
    setJobBusy(true);
    try {
      setJob(await resumeOrderedSemanticAssemblyJob(job.jobId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setJobBusy(false);
    }
  }

  const summary = preview?.plan.summary;
  const boundary = preview?.plan.executionBoundary;
  const staticClosureReady =
    closure?.releaseDecision?.staticTenObjectDemoReleaseAllowed === true ||
    closure?.releaseDecision?.staticSevenModuleDemoReleaseAllowed === true;
  const project03ReleasedPrefix = ["AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"];
  const project03RequestedTokens =
    projectId === "project03"
      ? (preview?.plan.steps ?? []).map((step) => step.moduleToken)
      : [];
  const project03LivePrefixReady =
    projectId === "project03" &&
    project03RequestedTokens.length > 0 &&
    project03RequestedTokens.length <= project03ReleasedPrefix.length &&
    project03RequestedTokens.every(
      (token, index) => token === project03ReleasedPrefix[index]
    );
  const selectedModeReady =
    executionMode === "live_cad"
      ? projectId === "project05"
        ? boundary?.safeToStartCad === true
        : projectId === "project03"
          ? project03LivePrefixReady && boundary?.safeToStartCad === true
          : projectId === "project02" && pipelineAudit?.readyForLiveCadExecution === true
      : projectId !== "project02"
        ? boundary?.safeToStartCad === true
        : staticClosureReady;

  return (
    <section className="ordered-assembly-workbench">
      <div className="ordered-assembly-heading">
        <div>
          <p className="ordered-assembly-eyebrow">{projectId.toUpperCase()} · CONTROLLED DEMO</p>
          <h2>自然语言有序装配编排</h2>
          <p>
            将“先添加、再添加、最后添加”的要求转换成可审核步骤。生成步骤只做安全预演；
            只有明确创建现场作业时才会启动 SolidWorks，且不会覆盖原型。
          </p>
        </div>
        <Workflow aria-hidden="true" />
      </div>

      <div className="ordered-assembly-command">
        <label htmlFor="ordered-assembly-project">项目证据链</label>
        <select
          id="ordered-assembly-project"
          value={projectId}
          onChange={(event) => {
            const next = event.target.value as SupportedJobProject;
            setProjectId(next);
            setRequirement(DEFAULT_REQUIREMENTS[next]);
            setPreview(null);
            setValidatedRun(null);
            setJob(null);
            setError(null);
            if (next !== "project02") setExecutionMode("validated_artifact_replay");
          }}
        >
          <option value="project01">项目01（真实工件证据回放）</option>
          <option value="project02">项目02（回放 + 现场CAD）</option>
            <option value="project03">项目03（回放 + 七步现场整链）</option>
          <option value="project05">项目05（真实工件证据回放）</option>
        </select>
        <label htmlFor="ordered-assembly-requirement">装配要求</label>
        <textarea
          id="ordered-assembly-requirement"
          value={requirement}
          onChange={(event) => setRequirement(event.target.value)}
          rows={3}
        />
        <button type="button" onClick={() => void handlePreview()} disabled={loading || !requirement.trim()}>
          {loading ? <Loader2 className="spin" aria-hidden="true" /> : <GitBranch aria-hidden="true" />}
          {loading ? "正在生成…" : "生成装配步骤"}
        </button>
        <button
          type="button"
          onClick={() => void handleValidatedDemo()}
          disabled={projectId !== "project02" || runningValidatedDemo || !preview?.plan.executionBoundary.safeToStartCad || !staticClosureReady}
        >
          {runningValidatedDemo ? <Loader2 className="spin" aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
          {runningValidatedDemo ? "正在载入…" : "载入已验证实体闭环"}
        </button>
        <div className="ordered-assembly-mode">
          <label htmlFor="ordered-assembly-mode">作业模式</label>
          <select
            id="ordered-assembly-mode"
            value={executionMode}
            onChange={(event) => setExecutionMode(event.target.value as "validated_artifact_replay" | "live_cad")}
          >
            <option value="validated_artifact_replay">已验证产物回放（不启动SolidWorks）</option>
            <option value="live_cad">
              现场CAD逐步执行（仅开放各项目已发布的连续步骤前缀）
            </option>
          </select>
          <span>
            {executionMode === "live_cad"
              ? "逐步生成独立装配体；每步保存重开并通过碰撞硬门禁后才提交。"
              : "快速复用已验收实体与门禁证据，用于演示和结果复核。"}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void handleCreateJob()}
          disabled={jobBusy || !preview?.plan.executionBoundary.safeToStartCad || !selectedModeReady}
        >
          {jobBusy ? <Loader2 className="spin" aria-hidden="true" /> : <Workflow aria-hidden="true" />}
          {jobBusy
            ? "正在提交…"
            : executionMode === "live_cad"
              ? "创建现场CAD作业"
              : "创建证据回放作业"}
        </button>
      </div>

      {job ? (
        <div className={`ordered-assembly-boundary ${job.status === "succeeded" ? "ready" : "review"}`}>
          {job.status === "succeeded" ? <CheckCircle2 aria-hidden="true" /> : <CircleDashed aria-hidden="true" />}
          <div>
            <strong>{job.projectId} 异步作业 {job.jobId}：{job.status}</strong>
            <p>
              {job.steps.filter((step) => step.status === "succeeded").length}/{job.steps.length} 个检查点已提交；
              失败或取消时回到最后一个已提交装配体。
            </p>
            {job.steps.map((step) => (
              <p key={step.stepId}>
                {step.moduleToken} · {step.status} · 尝试 {step.attemptCount} 次
                {step.checkpoint ? ` · ${step.checkpoint.assemblyPath}` : ""}
              </p>
            ))}
            {["queued", "running"].includes(job.status) ? (
              <button type="button" onClick={() => void handlePauseJob()} disabled={jobBusy}>请求暂停</button>
            ) : null}
            {["failed", "cancelled", "paused"].includes(job.status) ? (
              <button type="button" onClick={() => void handleResumeJob()} disabled={jobBusy}>从检查点恢复</button>
            ) : null}
          </div>
        </div>
      ) : null}

      {closure?.available ? (
        <div className={`ordered-assembly-boundary ${staticClosureReady ? "ready" : "review"}`}>
          {staticClosureReady ? <CheckCircle2 aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
          <div>
            <strong>
              最新实体闭环：{closure.allCadStepsPassed ? `${closure.sequence?.length ?? 0}个语义阶段通过` : "CAD阶段未通过"}，
              {closure.interferenceGate?.acceptedPairCount ?? 0}/
              {closure.interferenceGate?.checkedPairCount ?? 0} 模组对已接受
            </strong>
            <p>{closure.releaseDecision?.reason ?? closure.status}</p>
            <p>最终装配体：{closure.finalAssemblyPath}</p>
            {(closure.blockingIssues ?? []).map((item) => (
              <p className="ordered-step-warning" key={item.id}>
                {item.scope.join("/")}：{item.description}
              </p>
            ))}
            {(closure.knownLimitations ?? []).map((item) => (
              <p className="ordered-step-warning" key={item.id}>
                已知边界 · {item.scope.join("/")}：{item.description}
              </p>
            ))}
          </div>
        </div>
      ) : null}

      {pipelineAudit ? (
        <div className={`ordered-assembly-boundary ${pipelineAudit.readyForLiveCadExecution ? "ready" : "review"}`}>
          {pipelineAudit.readyForLiveCadExecution ? <CheckCircle2 aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
          <div>
            <strong>
              全链预检：{pipelineAudit.checks.filter((item) => item.passed).length}/{pipelineAudit.checks.length}项通过
            </strong>
            <p>
              已验证产物回放：{pipelineAudit.readyForValidatedArtifactReplay ? "可执行" : "阻断"}；
              现场CAD长链：{pipelineAudit.readyForLiveCadExecution ? "可执行" : "阻断"}。
            </p>
            {pipelineAudit.warnings.map((warning) => <p className="ordered-step-warning" key={warning}>{warning}</p>)}
          </div>
        </div>
      ) : null}

      {releaseContract ? (
        <div className={`ordered-assembly-boundary ${releaseContract.release.productionAllowed ? "ready" : "review"}`}>
          {releaseContract.release.productionAllowed ? <CheckCircle2 aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
          <div>
            <strong>
              统一发布契约：静态演示{releaseContract.release.staticDemoAllowed ? "可用" : "阻断"}；
              现场CAD{releaseContract.release.liveCadAllowed ? "可用" : "阻断"}；
              生产发布{releaseContract.release.productionAllowed ? "可用" : "阻断"}
            </strong>
            <p>
              动态证据：{releaseContract.dynamic.configured ? releaseContract.dynamic.status : "未登记"}；
              连续路径：{releaseContract.dynamic.continuousPathVerified ? "已证明" : "未证明"}；
              原型推断/临时参数模组：{releaseContract.parameterAuthority.prototypeOrTemporaryModuleCount}个。
            </p>
            {releaseContract.dynamic.firstObservedCollisionBracketDegrees ? (
              <p>
                整机采样首个碰撞区间：
                ({releaseContract.dynamic.firstObservedCollisionBracketDegrees.join("°, ")}°]
              </p>
            ) : null}
            {releaseContract.release.productionBlockers.map((blocker) => (
              <p className="ordered-step-warning" key={blocker}>生产阻塞 · {blocker}</p>
            ))}
          </div>
        </div>
      ) : null}

      {dependencyAudit ? (
        <div className={`ordered-assembly-boundary ${dependencyAudit.productionProfileAccepted ? "ready" : "review"}`}>
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>
              参数来源边界：{dependencyAudit.prototypeDependentModuleCount}个模组仍含原型推断
            </strong>
            <p>
              静态Demo参数：{dependencyAudit.staticDemoProfileAccepted ? "允许" : "拒绝"}；
              生产参数：{dependencyAudit.productionProfileAccepted ? "允许" : "拒绝"}。
            </p>
            {dependencyAudit.parameterAuthorityAudit ? (
              <p>
                权威参数签认：
                {dependencyAudit.parameterAuthorityAudit.productionAcceptedRequirementCount}/
                {dependencyAudit.parameterAuthorityAudit.requirementCount}项；注册表版本
                {dependencyAudit.parameterAuthorityAudit.registry.registryVersion}。
              </p>
            ) : null}
            <p>生产放行还需：{tokenList(dependencyAudit.productionDynamicRequirements)}</p>
          </div>
        </div>
      ) : null}

      {error ? <div className="ordered-assembly-error">{error}</div> : null}

      {validatedRun ? (
        <div className="ordered-assembly-boundary ready">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <strong>
              命令已绑定实体闭环：{validatedRun.interferenceGate.acceptedPairCount ?? 0}/
              {validatedRun.interferenceGate.checkedPairCount ?? 0} 模组对通过
            </strong>
            <p>{validatedRun.message}</p>
            <p>最终装配体：{validatedRun.finalAssemblyPath}</p>
            <p>
              运行记录：{validatedRun.audit.runEvidencePath} · 本次复用验证证据，未重新启动 SolidWorks
            </p>
          </div>
        </div>
      ) : null}

      {preview && summary && boundary ? (
        <>
          <div className="ordered-assembly-summary">
            <div>
              <span>识别步骤</span>
              <strong>{summary.stepCount}</strong>
            </div>
            <div>
              <span>顺序检查</span>
              <strong className={summary.orderValid ? "good" : "bad"}>
                {summary.orderValid ? "通过" : "未通过"}
              </strong>
            </div>
            <div>
              <span>已验证 CAD 步骤</span>
              <strong>
                {summary.cadExecutableStepCount}/{summary.stepCount}
              </strong>
            </div>
            <div>
              <span>可启动整链 CAD</span>
              <strong className={boundary.safeToStartCad ? "good" : "pending"}>
                {boundary.safeToStartCad ? "是" : "否"}
              </strong>
            </div>
          </div>

          <div className={`ordered-assembly-boundary ${boundary.safeToStartCad ? "ready" : "review"}`}>
            <ShieldCheck aria-hidden="true" />
            <div>
              <strong>{boundary.safeToStartCad ? "已满足执行门禁" : "当前停在预演门禁"}</strong>
              <p>{boundary.reason}</p>
            </div>
          </div>

          {preview.plan.dynamicProcessGate ? (
            <div
              className={`ordered-assembly-boundary ${
                preview.plan.dynamicProcessGate.accepted ? "ready" : "review"
              }`}
            >
              <ShieldCheck aria-hidden="true" />
              <div>
                <strong>
                  动态工艺门禁：
                  {preview.plan.dynamicProcessGate.requested
                    ? preview.plan.dynamicProcessGate.accepted
                      ? "通过"
                      : "拒绝"
                    : "未请求，仅静态装配"}
                </strong>
                <p>{preview.plan.dynamicProcessGate.message}</p>
                {preview.plan.dynamicProcessGate.firstObservedCollisionBracketDegrees ? (
                  <p>
                    首次观测碰撞区间：
                    ({preview.plan.dynamicProcessGate.firstObservedCollisionBracketDegrees.join("°, ")}°]
                  </p>
                ) : null}
                {preview.plan.dynamicProcessGate.knownPairFirstObservedCollisionBracketDegrees ? (
                  <p>
                    已知碰撞叶对局部首碰区间：
                    ({preview.plan.dynamicProcessGate.knownPairFirstObservedCollisionBracketDegrees.join("°, ")}°]；
                    该结果不代表整机连续安全
                  </p>
                ) : null}
                {preview.plan.dynamicProcessGate.evidencePath ? (
                  <p>证据：{preview.plan.dynamicProcessGate.evidencePath}</p>
                ) : null}
              </div>
            </div>
          ) : null}

          <p className="ordered-assembly-audit">
            预演编号：{preview.audit.runId} · 解析与规划耗时：
            {(preview.audit.timingSeconds.total * 1000).toFixed(3)} ms
          </p>
          <p className="ordered-assembly-audit">
            项目配置：{preview.intent.projectProfile?.profileVersion ?? "未登记"} · 配置指纹：
            {(preview.intent.projectProfile?.profileDigest ?? "").slice(0, 12) || "未登记"} · 意图指纹：
            {(preview.intent.intentDigest ?? preview.contracts?.intent.intentDigest ?? "").slice(0, 12) || "未登记"} · 计划指纹：
            {(preview.plan.planDigest ?? preview.contracts?.plan.planDigest ?? "").slice(0, 12) || "未登记"}
          </p>

          <div className="ordered-assembly-timeline">
            {preview.plan.steps.map((step) => {
              const meta = statusMeta(step);
              return (
                <article className={`ordered-assembly-step ${meta.className}`} key={step.stepId}>
                  <div className="ordered-step-index">{step.order}</div>
                  <div className="ordered-step-body">
                    <div className="ordered-step-title">
                      <div>
                        <strong>{step.moduleToken}</strong>
                        <span>{step.moduleLabel}</span>
                      </div>
                      <span className={`ordered-step-status ${meta.className}`}>
                        {meta.icon}
                        {meta.label}
                      </span>
                    </div>
                    <p className="ordered-step-rule">{step.ruleSummary}</p>
                    <dl>
                      <dt>前置模组</dt>
                      <dd>{tokenList(step.requiredModules)}</dd>
                      <dt>当前已有</dt>
                      <dd>{tokenList(step.availableBefore)}</dd>
                      <dt>验收检查</dt>
                      <dd>{step.acceptanceChecks.join(" · ")}</dd>
                    </dl>
                    {step.missingRequiredModules.length ? (
                      <p className="ordered-step-warning">
                        缺少前置模组：{tokenList(step.missingRequiredModules)}
                      </p>
                    ) : null}
                    {step.missingImplementation ? (
                      <p className="ordered-step-warning">阻塞：{step.missingImplementation}</p>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>

          {preview.plan.missingImplementations.length ? (
            <div className="ordered-assembly-gaps">
              <h3>尚未打通的 CAD 执行能力</h3>
              <ul>
                {preview.plan.missingImplementations.map((item) => (
                  <li key={item.moduleToken}>
                    <strong>{item.moduleToken}</strong>：{item.reason}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : (
        <div className="ordered-assembly-empty">
          选择项目并输入装配顺序，即可在执行或回放 CAD 证据前检查依赖、工程规则和实现状态。
        </div>
      )}
    </section>
  );
}
