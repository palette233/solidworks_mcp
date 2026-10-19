import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Boxes,
  CheckCircle2,
  CircleDot,
  Info,
  Link2,
  Loader2,
  Network,
  Plus,
  RefreshCw,
  Route,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Undo2,
  X
} from "lucide-react";

import {
  GlobalAssemblyCommandPreview,
  GlobalAssemblyConversation,
  TemporarySemanticPort,
  TemporaryConnectionPreview,
  CheckpointMateGraphExport,
  CheckpointTemporaryMatePreview,
  HistoricalCheckpointAssessment,
  GlobalAssemblyContext,
  GlobalAssemblyExecutionManifest,
  GlobalCadTransactionManifest,
  GlobalPortableReleaseRecommendation,
  GlobalProjectAdapterPlan,
  EngineeringValidationJob,
  OrderedAssemblyJob,
  GlobalModuleCatalog,
  GlobalModuleSearchResult,
  applyGlobalAssemblyCommand,
  cancelOrderedSemanticAssemblyJob,
  createGlobalAssemblyContext,
  createEngineeringValidationJob,
  getGlobalModuleCatalog,
  getGlobalAssemblyContext,
  getGlobalAssemblyConversation,
  getTemporarySemanticPorts,
  captureTemporarySemanticPort,
  previewTemporarySemanticConnection,
  exportCheckpointMateGraph,
  compileCheckpointTemporaryConnection,
  previewHistoricalCheckpointImport,
  importHistoricalCheckpoint,
  getGlobalAssemblyExecutionManifest,
  getGlobalCadTransactionManifest,
  getGlobalPortableReleaseRecommendation,
  getGlobalProjectAdapterPlan,
  loadOrderedSemanticAssemblyJob,
  loadGlobalCadManifestJob,
  loadEngineeringValidationJob,
  pauseOrderedSemanticAssemblyJob,
  pauseGlobalCadManifestJob,
  prepareGlobalIndependentCadJob,
  commitGlobalPortableReleaseUpgrade,
  prepareGlobalProjectAdapterJob,
  resumeGlobalProjectAdapterJob,
  resumeGlobalCadManifestJob,
  startGlobalCadManifestJob,
  startGlobalProjectAdapterJob,
  undoLatestGlobalAssemblyCommand,
  previewGlobalAssemblyCommand,
  searchGlobalModuleCatalog
} from "./api";

const ENGINEERING_EXAMPLES = [
  "在当前设备的操作侧增加一个喷嘴校准模组，现有清洁称重模组保持不动；完成后另存为新装配体。",
  "在传输线入口附近增加一个条码扫描模组，优先选择已有完整安装接口的型号。",
  "先安装传输模组，再安装能够读取载具条码的扫描模组，并把不能自动确定的型号列出来让我选择。"
];

const VERIFIED_CAD_CONTEXTS = [
  {
    contextId: "cross-project-a600-ah00-portable-v1",
    label: "跨项目校准模组",
    description: "Project02固定环境＋Project03校准模组，1包真实配合"
  },
  {
    contextId: "project01-jj00-project03-ae00-transport-v1",
    label: "跨项目传输模组",
    description: "Project01固定环境＋Project03传输模组，1包真实配合"
  },
  {
    contextId: "cross-project-aa00-bd00-ss00-ai00-portable-v1",
    label: "跨项目三步累计链",
    description: "Project03固定环境＋Project01校准/传输＋Project03扫描，3包累计装配"
  }
];

const ACTIVE_CONTEXT_STORAGE_KEY = "solidworks-demo.active-global-assembly-context";

function storedContextId() {
  if (typeof window === "undefined") return "global-demo";
  try {
    return window.localStorage.getItem(ACTIVE_CONTEXT_STORAGE_KEY)?.trim() || "global-demo";
  } catch {
    return "global-demo";
  }
}

function rememberContextId(value: string) {
  try {
    window.localStorage.setItem(ACTIVE_CONTEXT_STORAGE_KEY, value);
  } catch {
    // The backend conversation remains durable even when browser storage is unavailable.
  }
}

function latestConversationJobId(conversation: GlobalAssemblyConversation) {
  for (let turnIndex = conversation.turns.length - 1; turnIndex >= 0; turnIndex -= 1) {
    const jobs = conversation.turns[turnIndex].jobs;
    for (let jobIndex = jobs.length - 1; jobIndex >= 0; jobIndex -= 1) {
      if (jobs[jobIndex].jobId) return jobs[jobIndex].jobId;
    }
  }
  return null;
}

function coverageLabel(coverage?: string) {
  if (coverage === "portable_complete") return "安装接口完整";
  if (coverage === "partial") return "部分接口可用";
  if (coverage === "none") return "尚未登记安装接口";
  return "接口状态待确认";
}

function previewStatusLabel(status: GlobalAssemblyCommandPreview["status"]) {
  if (status === "ready") return "方案可以确认";
  if (status === "needs_confirmation") return "需要选择具体模组";
  return "当前方案暂不能执行";
}

function blockerExplanation(code: string, detail: string) {
  const normalized = code.toLowerCase();
  if (normalized.includes("ambiguous") || normalized.includes("confirmation")) {
    return "需求对应多个可选模组，请先选择具体型号。";
  }
  if (normalized.includes("port")) {
    return "所选模组缺少可用于当前连接的语义安装接口。";
  }
  if (normalized.includes("template") || normalized.includes("compat")) {
    return "当前两个模组之间尚未登记可复用的装配关系。";
  }
  if (normalized.includes("context") || normalized.includes("instance")) {
    return "当前装配上下文中缺少可连接的已有模组。";
  }
  return detail;
}


export function GlobalAssemblyWorkbench() {
  const [catalog, setCatalog] = useState<GlobalModuleCatalog | null>(null);
  const [context, setContext] = useState<GlobalAssemblyContext | null>(null);
  const [conversation, setConversation] = useState<GlobalAssemblyConversation | null>(null);
  const [temporaryPorts, setTemporaryPorts] = useState<TemporarySemanticPort[]>([]);
  const [temporaryInstanceId, setTemporaryInstanceId] = useState("");
  const [temporaryModuleToken, setTemporaryModuleToken] = useState("");
  const [temporaryPortName, setTemporaryPortName] = useState("用户选定安装面");
  const [temporaryInterfaceType, setTemporaryInterfaceType] = useState("temporary_planar_mount");
  const [temporaryRequirement, setTemporaryRequirement] = useState("");
  const [temporaryPreview, setTemporaryPreview] = useState<TemporaryConnectionPreview | null>(null);
  const [checkpointGraph, setCheckpointGraph] = useState<CheckpointMateGraphExport | null>(null);
  const [checkpointGraphConfirmed, setCheckpointGraphConfirmed] = useState(false);
  const [targetRemateToken, setTargetRemateToken] = useState("");
  const [compiledTemporaryMate, setCompiledTemporaryMate] = useState<CheckpointTemporaryMatePreview | null>(null);
  const [historicalJobId, setHistoricalJobId] = useState("project02-job-635438e6d96f");
  const [historicalInventoryPath, setHistoricalInventoryPath] = useState("");
  const [historicalAssessment, setHistoricalAssessment] = useState<HistoricalCheckpointAssessment | null>(null);
  const [historicalImportConfirmed, setHistoricalImportConfirmed] = useState(false);
  const [contextId, setContextId] = useState(storedContextId);
  const [query, setQuery] = useState("扫描模组");
  const [results, setResults] = useState<GlobalModuleSearchResult[]>([]);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState("");
  const [requirement, setRequirement] = useState(ENGINEERING_EXAMPLES[0]);
  const [preview, setPreview] = useState<GlobalAssemblyCommandPreview | null>(null);
  const [candidateDefinitionIds, setCandidateDefinitionIds] = useState<string[]>([]);
  const [intentConfirmed, setIntentConfirmed] = useState(false);
  const [undoArmed, setUndoArmed] = useState(false);
  const [manifest, setManifest] = useState<GlobalAssemblyExecutionManifest | null>(null);
  const [independentManifest, setIndependentManifest] = useState<GlobalCadTransactionManifest | null>(null);
  const [portableReleasePreview, setPortableReleasePreview] = useState<GlobalPortableReleaseRecommendation | null>(null);
  const [portableReleaseConfirmed, setPortableReleaseConfirmed] = useState(false);
  const [portableTargetContextId, setPortableTargetContextId] = useState("");
  const [adapterPlan, setAdapterPlan] = useState<GlobalProjectAdapterPlan | null>(null);
  const [assemblyMode, setAssemblyMode] = useState<"mate_driven_port_assembly" | "prototype_pose_dependency">("mate_driven_port_assembly");
  const [prototypeFallbackConfirmed, setPrototypeFallbackConfirmed] = useState(false);
  const [prepareConfirmed, setPrepareConfirmed] = useState(false);
  const [stepLimit, setStepLimit] = useState(1);
  const [preparedJob, setPreparedJob] = useState<OrderedAssemblyJob | null>(null);
  const [continuationSeedJobId, setContinuationSeedJobId] = useState<string | null>(null);
  const [engineeringValidation, setEngineeringValidation] = useState<EngineeringValidationJob | null>(null);
  const [engineeringConfirmed, setEngineeringConfirmed] = useState(false);
  const [startConfirmed, setStartConfirmed] = useState(false);
  const [startMessage, setStartMessage] = useState<string | null>(null);
  const [resumeConfirmed, setResumeConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [commitMessage, setCommitMessage] = useState<string | null>(null);
  const requirementRef = useRef<HTMLTextAreaElement | null>(null);

  async function loadCatalog() {
    setBusy(true);
    setError(null);
    try {
      setCatalog(await getGlobalModuleCatalog());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadCatalog();
    void restoreContext(contextId, { silentWhenMissing: true });
  }, []);

  useEffect(() => {
    if (!preparedJob || !preparedJob.startRequestedAt || !["queued", "running"].includes(preparedJob.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      const loadJob = preparedJob.executionMode === "generic_cad_manifest"
        ? loadGlobalCadManifestJob
        : loadOrderedSemanticAssemblyJob;
      void loadJob(preparedJob.jobId)
        .then((result) => {
          setPreparedJob(result);
          if (!['queued', 'running'].includes(result.status) && context) {
            void getGlobalAssemblyConversation(context.contextId).then((snapshot) => {
              setConversation(snapshot);
              setContinuationSeedJobId(snapshot.latestSuccessfulDemo?.jobId ?? null);
            });
          }
        })
        .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [preparedJob?.jobId, preparedJob?.status, preparedJob?.startRequestedAt, context?.contextId]);

  useEffect(() => {
    if (!engineeringValidation || !["queued", "running"].includes(engineeringValidation.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadEngineeringValidationJob(engineeringValidation.validationJobId)
        .then((result) => {
          setEngineeringValidation(result);
          if (!["queued", "running"].includes(result.status) && preparedJob) {
            void loadOrderedSemanticAssemblyJob(preparedJob.jobId).then(setPreparedJob);
          }
        })
        .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [engineeringValidation?.validationJobId, engineeringValidation?.status, preparedJob?.jobId]);

  async function handleSearch() {
    setBusy(true);
    setError(null);
    try {
      const response = await searchGlobalModuleCatalog(query);
      setResults(response.results);
      setSelectedDefinitionId(response.results.length === 1 ? response.results[0].moduleDefinitionId : "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateContext() {
    setBusy(true);
    setError(null);
    try {
      const response = await createGlobalAssemblyContext({
        contextId,
        displayName: "全局语义装配演示",
        overwrite: true
      });
      setContext(response.context);
      setConversation(await getGlobalAssemblyConversation(response.context.contextId));
      rememberContextId(response.context.contextId);
      setTemporaryPorts([]);
      setTemporaryInstanceId("");
      setTemporaryPreview(null);
      setCheckpointGraph(null);
      setCheckpointGraphConfirmed(false);
      setTargetRemateToken("");
      setCompiledTemporaryMate(null);
      setHistoricalAssessment(null);
      setHistoricalImportConfirmed(false);
      setPreview(null);
      setManifest(null);
      setIndependentManifest(null);
      setPortableReleasePreview(null);
      setPortableReleaseConfirmed(false);
      setPortableTargetContextId("");
      setAdapterPlan(null);
      setPrepareConfirmed(false);
      setPreparedJob(null);
      setContinuationSeedJobId(null);
      setEngineeringValidation(null);
      setEngineeringConfirmed(false);
      setStartConfirmed(false);
      setStartMessage(null);
      setCommitMessage(null);
      setResumeConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function restoreContext(
    requestedContextId: string,
    options: { silentWhenMissing?: boolean } = {}
  ) {
    const normalizedContextId = requestedContextId.trim();
    if (!normalizedContextId) return;
    setBusy(true);
    setError(null);
    try {
      const [loadedContext, loadedConversation] = await Promise.all([
        getGlobalAssemblyContext(normalizedContextId),
        getGlobalAssemblyConversation(normalizedContextId)
      ]);
      const latestJobId = latestConversationJobId(loadedConversation);
      const [localPorts, compiledExecution, restoredJob] = await Promise.all([
        getTemporarySemanticPorts(normalizedContextId),
        loadedContext.connections.length
          ? assemblyMode === "mate_driven_port_assembly"
            ? getGlobalCadTransactionManifest(normalizedContextId).then(async (independent) => ({
                independent,
                portableRelease:
                  independent.status === "blocked"
                    ? await getGlobalPortableReleaseRecommendation(normalizedContextId)
                    : null
              }))
            : Promise.all([
                getGlobalAssemblyExecutionManifest(normalizedContextId),
                getGlobalProjectAdapterPlan(normalizedContextId, assemblyMode)
              ]).then(([legacyManifest, legacyPlan]) => ({ legacyManifest, legacyPlan }))
          : Promise.resolve(null),
        latestJobId
          ? loadOrderedSemanticAssemblyJob(latestJobId)
              .catch(() => loadGlobalCadManifestJob(latestJobId))
              .catch(() => null)
          : Promise.resolve(null)
      ]);
      setContextId(normalizedContextId);
      setContext(loadedContext);
      setConversation(loadedConversation);
      setTemporaryPorts(localPorts.ports);
      setTemporaryInstanceId(loadedContext.instances[0]?.instanceId ?? "");
      setTemporaryPreview(null);
      setCheckpointGraph(null);
      setCheckpointGraphConfirmed(false);
      setTargetRemateToken("");
      setCompiledTemporaryMate(null);
      setHistoricalAssessment(null);
      setHistoricalImportConfirmed(false);
      setContinuationSeedJobId(loadedConversation.latestSuccessfulDemo?.jobId ?? null);
      setPreview(null);
      setManifest(compiledExecution && "legacyManifest" in compiledExecution ? compiledExecution.legacyManifest : null);
      setAdapterPlan(compiledExecution && "legacyPlan" in compiledExecution ? compiledExecution.legacyPlan : null);
      setIndependentManifest(compiledExecution && "independent" in compiledExecution ? compiledExecution.independent : null);
      setPortableReleasePreview(
        compiledExecution && "portableRelease" in compiledExecution && compiledExecution.independent.status === "blocked"
          ? compiledExecution.portableRelease
          : null
      );
      setPortableReleaseConfirmed(false);
      setPortableTargetContextId(`${normalizedContextId}-portable`);
      setPreparedJob(restoredJob);
      setStepLimit(
        restoredJob?.steps.length
          ?? (compiledExecution && "legacyPlan" in compiledExecution ? compiledExecution.legacyPlan.stepCount : undefined)
          ?? (compiledExecution && "independent" in compiledExecution ? compiledExecution.independent.packetCount : undefined)
          ?? 1
      );
      // Recover evidence and task state, but never recover a user's explicit confirmation.
      setPrepareConfirmed(false);
      setEngineeringValidation(null);
      setEngineeringConfirmed(false);
      setStartConfirmed(false);
      setResumeConfirmed(false);
      setStartMessage(
        restoredJob
          ? `已恢复装配会话和最近CAD任务：${restoredJob.jobId}（${restoredJob.status}）。`
          : loadedConversation.latestSuccessfulDemo
            ? `已恢复CAD续装检查点：${loadedConversation.latestSuccessfulDemo.jobId}`
          : "已恢复装配图；当前没有可续装的CAD检查点。"
      );
      setCommitMessage(null);
      rememberContextId(normalizedContextId);
    } catch (reason) {
      if (!options.silentWhenMissing) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadContext() {
    await restoreContext(contextId);
  }

  async function handleCaptureTemporaryPort() {
    if (!context || !temporaryInstanceId || !temporaryModuleToken.trim() || !temporaryPortName.trim()) return;
    setBusy(true);
    setError(null);
    setCommitMessage(null);
    try {
      await captureTemporarySemanticPort(context.contextId, {
        instanceId: temporaryInstanceId,
        moduleToken: temporaryModuleToken.trim(),
        displayName: temporaryPortName.trim(),
        interfaceType: temporaryInterfaceType.trim(),
        role: "primary"
      });
      const result = await getTemporarySemanticPorts(context.contextId);
      setTemporaryPorts(result.ports);
      setTemporaryPreview(null);
      setCompiledTemporaryMate(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleTemporaryConnectionPreview() {
    if (!context || !temporaryRequirement.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await previewTemporarySemanticConnection(context.contextId, temporaryRequirement);
      setTemporaryPreview(result);
      setTargetRemateToken(result.selectedPorts[0]?.moduleToken ?? "");
      setCompiledTemporaryMate(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleCheckpointGraphExport() {
    if (!context || !conversation?.latestSuccessfulDemo) return;
    setBusy(true);
    setError(null);
    try {
      const result = await exportCheckpointMateGraph(context.contextId, {
        confirmed: checkpointGraphConfirmed,
        expectedDemoJobId: conversation.latestSuccessfulDemo.jobId
      });
      setCheckpointGraph(result);
      setCompiledTemporaryMate(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleCompileTemporaryMate() {
    if (!context || !temporaryPreview || !checkpointGraph?.binding || !targetRemateToken) return;
    setBusy(true);
    setError(null);
    try {
      setCompiledTemporaryMate(
        await compileCheckpointTemporaryConnection(context.contextId, {
          temporaryPreview,
          targetModuleToken: targetRemateToken,
          expectedBindingDigest: checkpointGraph.binding.bindingDigest
        })
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleHistoricalCheckpointPreview() {
    if (!context || !historicalJobId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setHistoricalAssessment(
        await previewHistoricalCheckpointImport(context.contextId, {
          jobId: historicalJobId.trim(),
          componentInventoryPath: historicalInventoryPath.trim() || undefined
        })
      );
      setHistoricalImportConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleHistoricalCheckpointImport() {
    if (!context || !historicalAssessment || historicalAssessment.status !== "ready_for_import") return;
    setBusy(true);
    setError(null);
    try {
      const result = await importHistoricalCheckpoint(context.contextId, {
        jobId: historicalJobId.trim(),
        componentInventoryPath: historicalInventoryPath.trim() || undefined,
        expectedContextDigest: context.contextDigest,
        assessmentDigest: historicalAssessment.assessmentDigest,
        confirmed: historicalImportConfirmed
      });
      setConversation(result.conversation);
      setContinuationSeedJobId(result.jobId);
      setStartMessage(`历史Demo检查点已受控导入：${result.jobId}`);
      setHistoricalImportConfirmed(false);
      setCheckpointGraph(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview(moduleDefinitionId = selectedDefinitionId) {
    if (!context) return;
    setBusy(true);
    setError(null);
    setCommitMessage(null);
    setIntentConfirmed(false);
    try {
      const result = await previewGlobalAssemblyCommand(context.contextId, {
        requirement,
        moduleDefinitionId: moduleDefinitionId || undefined
      });
      setSelectedDefinitionId(result.selectedModuleDefinitionId ?? moduleDefinitionId ?? "");
      if (result.moduleAlternatives.length) {
        setCandidateDefinitionIds(result.moduleAlternatives.map((item) => item.moduleDefinitionId));
      }
      setPreview(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    if (!context || !preview || preview.status !== "ready" || !intentConfirmed) return;
    setBusy(true);
    setError(null);
    try {
      const preservedSeed = preparedJob?.status === "succeeded"
        ? preparedJob.jobId
        : continuationSeedJobId;
      const result = await applyGlobalAssemblyCommand(context.contextId, preview);
      setContext(result.context);
      setConversation(await getGlobalAssemblyConversation(context.contextId));
      setPreview(null);
      setIntentConfirmed(false);
      setCheckpointGraph(null);
      setCheckpointGraphConfirmed(false);
      setCompiledTemporaryMate(null);
      setSelectedDefinitionId("");
      setCandidateDefinitionIds([]);
      setManifest(null);
      setIndependentManifest(null);
      setPortableReleasePreview(null);
      setPortableReleaseConfirmed(false);
      setAdapterPlan(null);
      setPrepareConfirmed(false);
      setPreparedJob(null);
      setContinuationSeedJobId(preservedSeed);
      setEngineeringValidation(null);
      setEngineeringConfirmed(false);
      setStartConfirmed(false);
      setStartMessage(null);
      setCommitMessage(
        `已写入装配会话：修订 ${result.context.revision}，当前包含 ${result.context.instances.length} 个模组。`
      );
      setResumeConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  function focusRequirement() {
    window.setTimeout(() => requirementRef.current?.focus(), 0);
  }

  function handleReturnToRequirement() {
    setPreview(null);
    setIntentConfirmed(false);
    focusRequirement();
  }

  function handleAbandonCurrentOperation() {
    setPreview(null);
    setSelectedDefinitionId("");
    setCandidateDefinitionIds([]);
    setIntentConfirmed(false);
    setRequirement("");
    focusRequirement();
  }

  function handleAddPrerequisiteBase() {
    setPreview(null);
    setSelectedDefinitionId("");
    setCandidateDefinitionIds([]);
    setIntentConfirmed(false);
    setRequirement("请先建立设备箱体与安装基座，作为后续功能模组的固定安装环境。");
    focusRequirement();
  }

  async function handleUndoLatestTurn() {
    if (!context || !undoArmed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await undoLatestGlobalAssemblyCommand(context.contextId, context);
      setContext(result.context);
      setConversation(await getGlobalAssemblyConversation(context.contextId));
      setPreview(null);
      setSelectedDefinitionId("");
      setCandidateDefinitionIds([]);
      setIntentConfirmed(false);
      setUndoArmed(false);
      setManifest(null);
      setIndependentManifest(null);
      setPortableReleasePreview(null);
      setPortableReleaseConfirmed(false);
      setAdapterPlan(null);
      setPreparedJob(null);
      setEngineeringValidation(null);
      setStartMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleCompileManifest() {
    if (!context) return;
    setBusy(true);
    setError(null);
    try {
      if (assemblyMode === "mate_driven_port_assembly") {
        const compiledIndependentManifest = await getGlobalCadTransactionManifest(context.contextId);
        const releasePreview = compiledIndependentManifest.status === "blocked"
          ? await getGlobalPortableReleaseRecommendation(context.contextId)
          : null;
        setIndependentManifest(compiledIndependentManifest);
        setPortableReleasePreview(
          compiledIndependentManifest.status === "blocked" ? releasePreview : null
        );
        setPortableReleaseConfirmed(false);
        setPortableTargetContextId(`${context.contextId}-portable`);
        setManifest(null);
        setAdapterPlan(null);
      } else {
        const [compiledManifest, compiledAdapterPlan] = await Promise.all([
          getGlobalAssemblyExecutionManifest(context.contextId),
          getGlobalProjectAdapterPlan(context.contextId, assemblyMode)
        ]);
        setManifest(compiledManifest);
        setAdapterPlan(compiledAdapterPlan);
        setIndependentManifest(null);
        setPortableReleasePreview(null);
      }
      setStepLimit(1);
      setPreparedJob(null);
      setStartConfirmed(false);
      setStartMessage(null);
      setResumeConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handlePortableReleaseUpgrade() {
    if (
      !context ||
      !portableReleaseConfirmed ||
      portableReleasePreview?.status !== "ready" ||
      !portableReleasePreview.recommendation ||
      !portableTargetContextId.trim()
    ) return;
    setBusy(true);
    setError(null);
    try {
      const result = await commitGlobalPortableReleaseUpgrade(
        context.contextId,
        portableReleasePreview.previewDigest,
        portableReleasePreview.recommendation.releaseId,
        portableTargetContextId.trim()
      );
      const upgraded = result.context;
      const [upgradedConversation, upgradedManifest] = await Promise.all([
        getGlobalAssemblyConversation(upgraded.contextId),
        getGlobalCadTransactionManifest(upgraded.contextId)
      ]);
      setContextId(upgraded.contextId);
      setContext(upgraded);
      setConversation(upgradedConversation);
      rememberContextId(upgraded.contextId);
      setIndependentManifest(upgradedManifest);
      setManifest(null);
      setAdapterPlan(null);
      setPortableReleasePreview(null);
      setPortableReleaseConfirmed(false);
      setPreparedJob(null);
      setPrepareConfirmed(false);
      setStartConfirmed(false);
      setStepLimit(Math.max(1, upgradedManifest.packetCount));
      setStartMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handlePrepareJob() {
    const independentReady = independentManifest?.status === "ready_for_generic_executor_implementation";
    const fallbackReady = adapterPlan?.safeToCreateDurableJob === true;
    if (
      !context ||
      !(assemblyMode === "mate_driven_port_assembly" ? independentReady : fallbackReady) ||
      !prepareConfirmed ||
      (assemblyMode === "prototype_pose_dependency" && !prototypeFallbackConfirmed)
    ) return;
    setBusy(true);
    setError(null);
    try {
      const idempotencyKey = `global-context-${context.contextDigest}-${assemblyMode}-steps-${stepLimit}-demo`;
      const result = assemblyMode === "mate_driven_port_assembly"
        ? await prepareGlobalIndependentCadJob(context.contextId, idempotencyKey, stepLimit)
        : await prepareGlobalProjectAdapterJob(
            context.contextId,
            continuationSeedJobId
              ? `global-conversation-${context.contextDigest}-${assemblyMode}-from-${continuationSeedJobId}-steps-${stepLimit}`
              : idempotencyKey,
            stepLimit,
            continuationSeedJobId ?? undefined,
            "demo",
            assemblyMode
          );
      setPreparedJob(result.job);
      setContinuationSeedJobId(null);
      setConversation(await getGlobalAssemblyConversation(context.contextId));
      setStartConfirmed(false);
      setStartMessage(
        "message" in result
          ? result.message
          : "已创建项目无关CAD事务任务；当前尚未启动SolidWorks。"
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handlePrepareContinuation() {
    if (!context || !preparedJob || preparedJob.status !== "succeeded") return;
    setBusy(true);
    setError(null);
    try {
      const result = await prepareGlobalProjectAdapterJob(
        context.contextId,
        `global-continuation-${preparedJob.jobId}-${assemblyMode}-next-1-demo`,
        1,
        preparedJob.jobId,
        "demo",
        assemblyMode
      );
      setPreparedJob(result.job);
      setContinuationSeedJobId(null);
      setConversation(await getGlobalAssemblyConversation(context.contextId));
      setPrepareConfirmed(false);
      setStartConfirmed(false);
      setStartMessage(result.message);
      setResumeConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleStartJob() {
    if (!context || !preparedJob || !startConfirmed) return;
    setBusy(true);
    setError(null);
    try {
      if (preparedJob.executionMode === "generic_cad_manifest") {
        setPreparedJob(await startGlobalCadManifestJob(preparedJob.jobId));
        setStartMessage("项目无关CAD事务已提交后台执行。");
      } else {
        const result = await startGlobalProjectAdapterJob(
          context.contextId,
          preparedJob.jobId,
          context.contextDigest,
          preparedJob.steps.length
        );
        setPreparedJob(result.job);
        setStartMessage(result.message);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handlePauseJob() {
    if (!preparedJob) return;
    setBusy(true);
    setError(null);
    try {
      setPreparedJob(
        preparedJob.executionMode === "generic_cad_manifest"
          ? await pauseGlobalCadManifestJob(preparedJob.jobId)
          : await pauseOrderedSemanticAssemblyJob(preparedJob.jobId)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelJob() {
    if (!preparedJob) return;
    setBusy(true);
    setError(null);
    try {
      setPreparedJob(await cancelOrderedSemanticAssemblyJob(preparedJob.jobId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleResumeJob() {
    if (!context || !preparedJob || !resumeConfirmed) return;
    setBusy(true);
    setError(null);
    try {
      if (preparedJob.executionMode === "generic_cad_manifest") {
        setPreparedJob(await resumeGlobalCadManifestJob(preparedJob.jobId));
        setStartMessage("项目无关CAD事务已从持久检查点恢复。");
      } else {
        const result = await resumeGlobalProjectAdapterJob(
          context.contextId,
          preparedJob.jobId,
          context.contextDigest,
          preparedJob.steps.length
        );
        setPreparedJob(result.job);
        setStartMessage(result.message);
      }
      setResumeConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleEngineeringValidation() {
    if (!preparedJob || !engineeringConfirmed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createEngineeringValidationJob(
        preparedJob.jobId,
        `engineering-${preparedJob.jobId}-${preparedJob.demoCheckpoint?.committedAt ?? "latest"}`
      );
      setEngineeringValidation(result.validationJob);
      setEngineeringConfirmed(false);
      setStartMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  const selectedDefinition = catalog?.moduleDefinitions.find(
    (item) => item.moduleDefinitionId === (preview?.selectedModuleDefinitionId ?? selectedDefinitionId)
  );
  const candidateIds = candidateDefinitionIds.length
    ? candidateDefinitionIds
    : (preview?.moduleAlternatives ?? []).map((candidate) => candidate.moduleDefinitionId);
  const candidateDefinitions = candidateIds
    .map((candidateId) => catalog?.moduleDefinitions.find((item) => item.moduleDefinitionId === candidateId))
    .filter((candidate): candidate is NonNullable<typeof candidate> => Boolean(candidate));
  const latestTurn = conversation?.turns.length
    ? conversation.turns[conversation.turns.length - 1]
    : null;
  const latestTurnHasCadEvidence = Boolean(latestTurn?.jobs.length || latestTurn?.cadEdits?.length);
  const activeStep = !context ? 1 : !preview ? 2 : preview.status === "needs_confirmation" ? 3 : preview.status === "ready" ? 4 : 3;
  const independentMode = assemblyMode === "mate_driven_port_assembly";
  const executionReady = independentMode
    ? independentManifest?.status === "ready_for_generic_executor_implementation"
    : adapterPlan?.safeToCreateDurableJob === true;
  const executionStepCount = independentMode
    ? independentManifest?.packetCount ?? 0
    : adapterPlan?.stepCount ?? 0;

  return (
    <section className="panel global-assembly-workbench" id="global-assembly-workbench">
      <div className="semantic-port-heading">
        <div>
          <span className="eyebrow">跨项目模组库 · 静态自由组合 MVP</span>
          <h2>自然语言增量装配上下文</h2>
          <p>项目编号只作为历史别名；系统按CAD定义、语义端口和兼容模板生成可审计的装配图补丁。</p>
        </div>
        <button type="button" onClick={() => void loadCatalog()} disabled={busy}>
          {busy ? <Loader2 className="spin" /> : <RefreshCw />}刷新目录
        </button>
      </div>

      {error ? <div className="semantic-port-error"><ShieldAlert />{error}</div> : null}

      {catalog ? (
        <div className="global-summary-grid">
          <div><strong>{catalog.summary.moduleDefinitionCount}</strong><span>CAD模组定义</span></div>
          <div><strong>{catalog.summary.semanticPortCount}</strong><span>语义端口</span></div>
          <div><strong>{catalog.summary.compatibilityCount}</strong><span>兼容关系</span></div>
          <div><strong>{catalog.summary.blockerCount}</strong><span>待补证据</span></div>
        </div>
      ) : null}

      <div className="assembly-journey" aria-label="装配流程">
        {["选择当前装配", "描述工程意图", "确认具体模组", "检查并确认", "写入装配会话"].map((label, index) => {
          const order = index + 1;
          const state = order < activeStep ? "done" : order === activeStep ? "active" : "pending";
          return (
            <div className={`assembly-journey-step ${state}`} key={label}>
              <span>{state === "done" ? <CheckCircle2 /> : order}</span>
              <small>{label}</small>
              {order < 5 ? <ArrowRight /> : null}
            </div>
          );
        })}
      </div>

      <div className="engineer-assembly-grid">
        <div className="engineer-context-card">
          <div className="engineer-card-heading">
            <Boxes />
            <div>
              <strong>当前装配会话</strong>
              <small>{context ? `正在编辑：${context.contextId}` : "先选择要继续修改的装配上下文"}</small>
            </div>
          </div>
          <label>会话名称<input value={contextId} onChange={(event) => setContextId(event.target.value)} /></label>
          <div className="engineer-button-row">
            <button type="button" onClick={() => void handleCreateContext()} disabled={busy || !catalog}>
              <Plus />新建空白会话
            </button>
            <button className="secondary-action" type="button" onClick={() => void handleLoadContext()} disabled={busy || !contextId.trim()}>
              <RefreshCw />继续已有会话
            </button>
          </div>
          <div className={`context-readiness ${context ? "ready" : "waiting"}`}>
            {context ? <CheckCircle2 /> : <Info />}
            <span>
              {context
                ? `已加载：修订 ${context.revision}，包含 ${context.instances.length} 个模组`
                : busy
                  ? "正在恢复最近使用的装配会话…"
                  : "尚未选择装配会话"}
            </span>
          </div>
          {commitMessage ? <div className="context-commit-message"><CheckCircle2 />{commitMessage}</div> : null}
          {context?.instances.length ? (
            <div className="context-instance-chips" aria-label="当前模组">
              {context.instances.map((instance) => (
                <span key={instance.instanceId} title={instance.instanceId}>
                  {instance.displayName}<small>{instance.placementStatus}</small>
                </span>
              ))}
            </div>
          ) : null}
          {context?.relationReleaseBinding ? (
            <div className="context-release-history">
              <strong>当前完整配合发布</strong>
              <code>{context.relationReleaseBinding.releaseId}</code>
              {(context.history ?? []).some((item) => item.portableReleaseTransition) ? (
                <details>
                  <summary>查看发布绑定与扩展历史</summary>
                  {(context.history ?? [])
                    .filter((item) => item.portableReleaseTransition)
                    .map((item) => {
                      const transition = item.portableReleaseTransition!;
                      return (
                        <p key={`${item.revision}-${transition.releaseId}`}>
                          修订{item.revision} · {transition.transitionKind === "expand"
                            ? "扩展"
                            : transition.transitionKind === "first_bind"
                              ? "首次绑定"
                              : "绑定/扩展"}
                          {transition.sourceReleaseId ? `：${transition.sourceReleaseId} → ` : "："}
                          {transition.releaseId}
                          {typeof transition.replacementCount === "number"
                            ? ` · 重映射${transition.replacementCount}条连接`
                            : ""}
                        </p>
                      );
                    })}
                </details>
              ) : null}
            </div>
          ) : null}
          {context && context.revision > 0 ? (
            <div className="context-undo-zone">
              {!undoArmed ? (
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => setUndoArmed(true)}
                  disabled={busy || latestTurnHasCadEvidence}
                  title={latestTurnHasCadEvidence ? "最新一轮已有CAD证据，不能只撤销语义图" : undefined}
                >
                  <Undo2 />撤销上一轮
                </button>
              ) : (
                <div className="undo-confirmation">
                  <strong>确认撤销第 {context.revision} 轮？</strong>
                  <small>{latestTurn?.requirement || "将恢复到上一版装配图。"}</small>
                  <div className="engineer-button-row">
                    <button type="button" onClick={() => void handleUndoLatestTurn()} disabled={busy}>
                      <Undo2 />确认撤销
                    </button>
                    <button className="secondary-action" type="button" onClick={() => setUndoArmed(false)} disabled={busy}>
                      取消
                    </button>
                  </div>
                </div>
              )}
              {latestTurnHasCadEvidence ? <small>最新一轮已绑定CAD任务或实体修改，需先处理实体结果。</small> : null}
            </div>
          ) : null}
        </div>

        <div className="engineer-intent-card">
          <div className="engineer-card-heading">
            <Sparkles />
            <div><strong>描述你希望如何修改设备</strong><small>可以使用模组名称、用途、位置和先后关系，无需输入内部编号</small></div>
          </div>
          <textarea
            ref={requirementRef}
            rows={5}
            value={requirement}
            onChange={(event) => {
              setRequirement(event.target.value);
              setSelectedDefinitionId("");
              setPreview(null);
              setCandidateDefinitionIds([]);
              setIntentConfirmed(false);
            }}
            placeholder="例如：在当前设备操作侧增加一个喷嘴校准模组，已有清洁称重模组保持不动。"
          />
          <div className="engineering-example-list">
            <span>快速示例</span>
            {ENGINEERING_EXAMPLES.map((example, index) => (
              <button
                className="example-chip"
                key={example}
                type="button"
                onClick={() => {
                  setRequirement(example);
                  setSelectedDefinitionId("");
                  setPreview(null);
                  setCandidateDefinitionIds([]);
                  setIntentConfirmed(false);
                }}
              >示例 {index + 1}</button>
            ))}
          </div>
          <div className="engineering-example-list">
            <span>真实CAD验证案例</span>
            {VERIFIED_CAD_CONTEXTS.map((example) => (
              <button
                className="example-chip"
                key={example.contextId}
                type="button"
                title={example.description}
                onClick={() => void restoreContext(example.contextId)}
                disabled={busy}
              >{example.label}</button>
            ))}
          </div>
          <button className="primary-analysis-action" type="button" onClick={() => void handlePreview()} disabled={busy || !context || !requirement.trim()}>
            {busy ? <Loader2 className="spin" /> : <Sparkles />}分析需求并推荐模组
          </button>
          {!context ? <p className="inline-guidance">请先在左侧新建或加载一个装配会话。</p> : null}
        </div>
      </div>

      <details className="expert-toolbox">
        <summary><SlidersHorizontal />专家工具：按编号或类别直接检索</summary>
        <div className="expert-search-row">
          <label>模组名称、编号或类别<input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <button type="button" onClick={() => void handleSearch()} disabled={busy}><Search />检索</button>
        </div>
        {results.length ? (
          <div className="expert-search-results">
            {results.map((item) => (
              <button
                type="button"
                className={selectedDefinitionId === item.moduleDefinitionId ? "selected" : ""}
                key={item.moduleDefinitionId}
                onClick={() => {
                  setSelectedDefinitionId(item.moduleDefinitionId);
                  setPreview(null);
                  setIntentConfirmed(false);
                }}
              >
                <strong>{item.displayName}</strong>
                <small>{item.projectAliases.map((alias) => `${alias.projectId}:${alias.moduleToken}`).join(" / ")}</small>
              </button>
            ))}
          </div>
        ) : <p className="muted-copy">工程师模式会优先通过自然语言自动检索；这里只用于直接指定或排查。</p>}
      </details>

      {preview ? (
        <div className={`engineer-analysis-panel ${preview.status}`}>
          <div className="analysis-status-heading">
            {preview.status === "ready" ? <CheckCircle2 /> : <ShieldAlert />}
            <div>
              <span>系统分析结果</span>
              <h3>{previewStatusLabel(preview.status)}</h3>
            </div>
          </div>

          {preview.status === "needs_confirmation" && candidateDefinitions.length ? (
            <div className="candidate-selection-block">
              <div className="section-caption"><CircleDot />请选择工程师实际希望使用的模组</div>
              <div className="module-candidate-grid">
                {candidateDefinitions.map((candidate) => (
                  <article className={selectedDefinitionId === candidate.moduleDefinitionId ? "selected" : ""} key={candidate.moduleDefinitionId}>
                    <div><strong>{candidate.displayName}</strong><span>{candidate.category}</span></div>
                    <p>{candidate.projectAliases.map((alias) => `${alias.projectId} · ${alias.moduleToken}`).join(" / ")}</p>
                    <small>{coverageLabel(candidate.portCoverage)} · {candidate.portIds.length} 个语义端口</small>
                    <button type="button" onClick={() => void handlePreview(candidate.moduleDefinitionId)} disabled={busy}>
                      选择此模组并重新检查
                    </button>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {selectedDefinition ? (
            <div className="selected-module-summary">
              <span>已识别模组</span>
              <strong>{selectedDefinition.displayName}</strong>
              <small>
                {selectedDefinition.projectAliases.map((alias) => `${alias.projectId} · ${alias.moduleToken}`).join(" / ")}
                {` · ${coverageLabel(selectedDefinition.portCoverage)}`}
              </small>
            </div>
          ) : null}

          {preview.connectionCandidates.length ? (
            <div className="connection-plan-list">
              <div className="section-caption"><Link2 />建议的装配关系</div>
              {preview.connectionCandidates.map((candidate, index) => {
                const target = context?.instances.find((item) => item.instanceId === candidate.existingInstanceId);
                return (
                  <div className="connection-plan-item" key={`${candidate.globalTemplateId}-${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>将{selectedDefinition?.displayName ?? "所选模组"}连接到{target?.displayName ?? "当前装配体"}</strong>
                      <small>{candidate.purpose === "installation" ? "用于确定安装位置" : `关系用途：${candidate.purpose}`} · {candidate.portable ? "可跨项目复用" : "仅适用于当前已登记场景"}</small>
                    </div>
                    <details><summary>技术追溯</summary><code>{candidate.newPortId} → {candidate.existingPortId}<br />{candidate.globalTemplateId}</code></details>
                  </div>
                );
              })}
            </div>
          ) : null}

          {preview.portableReleaseTransition ? (
            <div className="context-readiness ready">
              <CheckCircle2 />
              <span>
                {preview.portableReleaseTransition.transitionKind === "expand"
                  ? `本次确认将把关系发布从 ${preview.portableReleaseTransition.sourceReleaseId ?? "当前版本"} 受控扩展为 ${preview.portableReleaseTransition.releaseId}，并用同一发布重新绑定全部既有连接。`
                  : preview.portableReleaseTransition.discoveryMode === "immutable_release_port_discovery"
                    ? `活动目录尚未登记这组跨项目接口；系统已从不可变发布中找到可完整定位的语义端口与配合束，并将绑定 ${preview.portableReleaseTransition.releaseId}。`
                  : `本次确认将同时采用已验证的完整定位配合束，并绑定便携关系发布 ${preview.portableReleaseTransition.releaseId}。`}
                后续模组将继续受该单一发布约束。
                当前仅更新装配语义图，不启动SolidWorks。
              </span>
              <details>
                <summary>技术追溯</summary>
                <code>
                  {preview.portableReleaseTransition.replacements.map((item) => (
                    <span key={item.connectionId}>
                      {item.sourceTemplateId ?? "活动目录未登记模板"} → {item.portableTemplateId}（{item.mateStepCount}步配合）<br />
                    </span>
                  ))}
                  选择规则：{preview.portableReleaseTransition.selectionPolicy}
                </code>
              </details>
            </div>
          ) : null}

          {preview.engineeringFallbacks?.length ? (
            <div className="engineering-fallback-list">
              <div className="section-caption"><Route />可选工程回退路线</div>
              {preview.engineeringFallbacks.map((fallback, index) => (
                <article key={`${fallback.sourceModule}-${fallback.nativeSlotModule}-${index}`}>
                  <div>
                    <strong>
                      {fallback.kind === "physical_adapter_required"
                        ? "当前型号需要实体转接接口"
                        : "当前型号需要机械接口复核"}
                    </strong>
                    <span>{fallback.sourceModule} → {fallback.nativeSlotModule}原生槽位</span>
                  </div>
                  <p>{fallback.engineeringDisposition.explanation}</p>
                  {fallback.engineeringDisposition.knownLocatingDifferences.map((difference) => (
                    <small key={difference.roles.join("-")}>
                      定位特征间距：当前模组 {(difference.sourceDistanceMeters * 1000).toFixed(1)} mm；
                      原生槽位 {(difference.targetDistanceMeters * 1000).toFixed(1)} mm；
                      差值 {(difference.absoluteDifferenceMeters * 1000).toFixed(1)} mm。
                    </small>
                  ))}
                  <div className="fallback-actions">
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void handlePreview(fallback.nativeSlotModuleDefinitionId)}
                      disabled={busy}
                    >改用原生兼容模组并重新检查</button>
                  </div>
                  <details>
                    <summary>转接方案进入可执行目录前还需什么</summary>
                    <ul>
                      {fallback.engineeringDisposition.requiredNextEvidence.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <code>{fallback.cadLaunchDecision} · 当前未启动SolidWorks</code>
                  </details>
                </article>
              ))}
              <p>{preview.fallbackPolicy?.statement}</p>
            </div>
          ) : null}

          {preview.blockers.length ? (
            <div className="human-blocker-list">
              <div className="section-caption"><ShieldAlert />需要处理的问题</div>
              {preview.blockers.map((blocker, index) => {
                const explanation = blockerExplanation(blocker.code, blocker.detail);
                return (
                  <div key={`${blocker.code}-${index}`}>
                    <strong>{explanation}</strong>
                    {explanation !== blocker.detail ? <small>{blocker.detail}</small> : null}
                    <code>{blocker.code}</code>
                  </div>
                );
              })}
            </div>
          ) : null}

          {preview.status !== "ready" ? (
            <div className="preview-recovery-actions">
              <button type="button" onClick={handleReturnToRequirement} disabled={busy}>
                返回修改需求
              </button>
              {candidateDefinitions.length ? (
                <button className="secondary-action" type="button" onClick={() => void handlePreview("")} disabled={busy}>
                  重新选择模组
                </button>
              ) : null}
              {preview.blockers.some((blocker) => blocker.code === "RELATION_TARGET_REQUIRED") ? (
                <button className="secondary-action" type="button" onClick={handleAddPrerequisiteBase} disabled={busy}>
                  先补充安装基座
                </button>
              ) : null}
              <button className="ghost-danger-action" type="button" onClick={handleAbandonCurrentOperation} disabled={busy}>
                <X />放弃本次操作
              </button>
            </div>
          ) : null}

          <div className="analysis-scope-note">
            <Info />
            <span>本阶段检查模组身份、语义端口和已登记装配关系；实体干涉与B-rep仍作为可选的后验工程验证。</span>
          </div>

          {preview.status === "ready" ? (
            <div className="engineer-confirmation-zone">
              <label>
                <input type="checkbox" checked={intentConfirmed} onChange={(event) => setIntentConfirmed(event.target.checked)} />
                我已确认所选模组和上述装配关系符合本次工程意图
              </label>
              <small>勾选仅表示确认工程意图；还需点击下方按钮才会真正增加当前模组。</small>
              <button type="button" onClick={() => void handleApply()} disabled={busy || !intentConfirmed}>
                <CheckCircle2 />提交并加入当前装配
              </button>
            </div>
          ) : (
            <p className="inline-guidance">系统不会在存在歧义或接口不兼容时创建CAD任务。</p>
          )}
        </div>
      ) : null}

      {conversation?.turns.length ? (
        <div className="global-preview ready">
          <div><Network /><strong>可恢复会话：{conversation.turnCount}轮自然语言命令</strong></div>
          {conversation.turns.map((turn) => (
            <p key={turn.turnId}>
              第{turn.contextRevision}轮 · {turn.requirement} · 图已提交
              {turn.jobs.length
                ? ` · CAD ${turn.jobs.map((job) => `${job.jobId}:${job.status}`).join("、")}`
                : " · CAD尚未执行"}
            </p>
          ))}
          {conversation.latestSuccessfulDemo ? (
            <>
              <p>最近可续装CAD检查点：{conversation.latestSuccessfulDemo.assemblyPath}</p>
              <p>
                装配状态：{conversation.latestSuccessfulDemo.assemblyStatus === "assembled" ? "已完成" : conversation.latestSuccessfulDemo.assemblyStatus ?? "未知"}
                {` · 碰撞/B-rep：${conversation.latestSuccessfulDemo.collisionStatus === "passed" ? "已通过" : conversation.latestSuccessfulDemo.collisionStatus === "rejected" ? "已否决" : "未执行"}`}
              </p>
            </>
          ) : (
            <p className="muted-copy">当前没有已成功的CAD检查点。</p>
          )}
        </div>
      ) : null}

      {context ? (
        <div className="global-preview">
          <div><RefreshCw /><strong>历史CAD检查点受控导入</strong></div>
          <p>
            仅用于导入会话台账建立前已经成功的CAD任务。系统会核对当前上下文、组件多重集、
            装配体SHA-256和组件清单证据；不会打开或修改SolidWorks。
          </p>
          <label>
            历史任务编号
            <input
              value={historicalJobId}
              onChange={(event) => {
                setHistoricalJobId(event.target.value);
                setHistoricalAssessment(null);
                setHistoricalImportConfirmed(false);
              }}
            />
          </label>
          <label>
            顶层组件清单（可留空自动推断）
            <input
              value={historicalInventoryPath}
              onChange={(event) => {
                setHistoricalInventoryPath(event.target.value);
                setHistoricalAssessment(null);
                setHistoricalImportConfirmed(false);
              }}
              placeholder="例如工程验证产生的 attempt1-poses.json"
            />
          </label>
          <button type="button" disabled={busy || !historicalJobId.trim()} onClick={() => void handleHistoricalCheckpointPreview()}>
            <ShieldAlert />生成导入评估
          </button>
          {historicalAssessment ? (
            <div className={historicalAssessment.status === "ready_for_import" ? "semantic-success" : "semantic-port-error"}>
              <strong>{historicalAssessment.status === "ready_for_import" ? "历史检查点证据一致" : "历史检查点不可导入"}</strong>
              <span>
                期望{historicalAssessment.expectedInstanceCount}个实例，证据中有
                {historicalAssessment.observedComponentCount}个顶层对象。
              </span>
              <small>
                期望：{JSON.stringify(historicalAssessment.expectedModuleTokenCounts)}；
                观测：{JSON.stringify(historicalAssessment.observedModuleTokenCounts)}
              </small>
              {historicalAssessment.blockers.map((blocker, index) => (
                <small key={`${blocker.code}-${index}`}>{blocker.code}</small>
              ))}
              {historicalAssessment.status === "ready_for_import" ? (
                <>
                  <label className="global-confirmation">
                    <input
                      type="checkbox"
                      checked={historicalImportConfirmed}
                      onChange={(event) => setHistoricalImportConfirmed(event.target.checked)}
                    />
                    我确认只把该不可变检查点绑定到当前会话台账
                  </label>
                  <button type="button" disabled={busy || !historicalImportConfirmed} onClick={() => void handleHistoricalCheckpointImport()}>
                    <CheckCircle2 />确认导入检查点
                  </button>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {context ? (
        <div className="global-preview">
          <div><Link2 /><strong>人工选面兜底（上下文局部端口）</strong></div>
          <p>在SolidWorks中先选中一个平面，再登记为当前上下文的临时端口；此操作不创建配合、不移动模组。</p>
          <label>
            所属实例
            <select value={temporaryInstanceId} onChange={(event) => setTemporaryInstanceId(event.target.value)}>
              <option value="">请选择</option>
              {context.instances.map((instance) => (
                <option key={instance.instanceId} value={instance.instanceId}>
                  {instance.displayName} · {instance.instanceId}
                </option>
              ))}
            </select>
          </label>
          <label>模组编号<input value={temporaryModuleToken} onChange={(event) => setTemporaryModuleToken(event.target.value)} placeholder="例如 A180" /></label>
          <label>端口名称<input value={temporaryPortName} onChange={(event) => setTemporaryPortName(event.target.value)} /></label>
          <label>接口类型<input value={temporaryInterfaceType} onChange={(event) => setTemporaryInterfaceType(event.target.value)} /></label>
          <button
            type="button"
            disabled={busy || !temporaryInstanceId || !temporaryModuleToken.trim() || !temporaryPortName.trim()}
            onClick={() => void handleCaptureTemporaryPort()}
          >
            <Link2 />捕获当前选中面并登记端口
          </button>
          {temporaryPorts.map((port) => (
            <p key={port.portId}>{port.displayName} · {port.moduleToken} · {port.endpointBindings[0]?.endpointId}</p>
          ))}
          {temporaryPorts.length >= 2 ? (
            <>
              <label>
                临时配合命令
                <textarea
                  rows={2}
                  value={temporaryRequirement}
                  onChange={(event) => {
                    setTemporaryRequirement(event.target.value);
                    setTemporaryPreview(null);
                  }}
                  placeholder="例如：将扫描安装面与箱体承载面建立重合配合"
                />
              </label>
              <button type="button" disabled={busy || !temporaryRequirement.trim()} onClick={() => void handleTemporaryConnectionPreview()}>
                <Network />解析为基础配合草案
              </button>
            </>
          ) : null}
          {temporaryPreview ? (
            <div className={temporaryPreview.status === "ready" ? "semantic-success" : "semantic-port-error"}>
              <strong>{temporaryPreview.status === "ready" ? "临时配合草案已就绪" : "临时配合草案被阻断"}</strong>
              <span>
                {temporaryPreview.selectedPorts.map((port) => port.displayName).join(" ↔ ")} · {temporaryPreview.mateDraft.mateLabel ?? "未识别"}
              </span>
              {temporaryPreview.blockers.map((blocker) => <small key={blocker.code}>{blocker.code}：{blocker.detail}</small>)}
              <small>{temporaryPreview.executionBoundary.statement}</small>
            </div>
          ) : null}
          {temporaryPreview?.status === "ready" && conversation?.latestSuccessfulDemo ? (
            <div className="global-preview">
              <div><Network /><strong>绑定当前CAD检查点的配合图</strong></div>
              <p>
                检查点：{conversation.latestSuccessfulDemo.jobId}。先只读导出当前累计装配体的配合图，
                再把上述两个人工选面编译为目标模组的局部重配图。
              </p>
              <label className="global-confirmation">
                <input
                  type="checkbox"
                  checked={checkpointGraphConfirmed}
                  onChange={(event) => setCheckpointGraphConfirmed(event.target.checked)}
                />
                我确认允许启动SolidWorks执行只读配合图导出（不会修改装配体）
              </label>
              <button type="button" disabled={busy} onClick={() => void handleCheckpointGraphExport()}>
                <Network />
                {checkpointGraphConfirmed ? "导出并绑定检查点配合图" : "检查配合图导出计划"}
              </button>
              {checkpointGraph ? (
                <div className={checkpointGraph.binding ? "semantic-success" : "semantic-port-error"}>
                  <strong>{checkpointGraph.binding ? "检查点配合图已绑定" : "等待明确确认"}</strong>
                  <span>{checkpointGraph.spec.outputGraphPath}</span>
                  {checkpointGraph.binding ? (
                    <small>
                      {checkpointGraph.binding.mateGraph.moduleCount}个模组，
                      {checkpointGraph.binding.mateGraph.mateCount}条配合；装配体未修改。
                    </small>
                  ) : null}
                </div>
              ) : null}
              {checkpointGraph?.binding ? (
                <>
                  <label>
                    要重新建立配合的目标模组
                    <select value={targetRemateToken} onChange={(event) => setTargetRemateToken(event.target.value)}>
                      {temporaryPreview.selectedPorts.map((port) => (
                        <option key={port.portId} value={port.moduleToken}>{port.moduleToken} · {port.displayName}</option>
                      ))}
                    </select>
                  </label>
                  <button type="button" disabled={busy || !targetRemateToken} onClick={() => void handleCompileTemporaryMate()}>
                    <Link2 />编译为目标局部配合图（不执行CAD）
                  </button>
                </>
              ) : null}
              {compiledTemporaryMate ? (
                <div className="semantic-success">
                  <strong>配合补丁已编译，尚未执行</strong>
                  <span>
                    目标{compiledTemporaryMate.targetModuleToken}；保留
                    {compiledTemporaryMate.preservedExistingMateNames.length}条原有配合；新增
                    {compiledTemporaryMate.newMateName}
                  </span>
                  <small>{compiledTemporaryMate.constraintSafety.claimBoundary}</small>
                  <small>下一步仍需单独确认真实重配、另存和重开复核。</small>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {context?.instances.length ? (
        <>
          <div className="global-instance-list">
            {context.instances.map((instance, index) => (
              <div key={instance.instanceId}><strong>{index + 1}. {instance.displayName}</strong><span>{instance.placementStatus}</span></div>
            ))}
          </div>
          <label>
            装配定位模式
            <select
              value={assemblyMode}
              onChange={(event) => {
                setAssemblyMode(event.target.value as "mate_driven_port_assembly" | "prototype_pose_dependency");
                setPrototypeFallbackConfirmed(false);
                setManifest(null);
                setIndependentManifest(null);
                setPortableReleasePreview(null);
                setPortableReleaseConfirmed(false);
                setAdapterPlan(null);
                setPreparedJob(null);
                setPrepareConfirmed(false);
                setStartConfirmed(false);
              }}
            >
              <option value="mate_driven_port_assembly">语义端口＋配合图独立装配（默认）</option>
              <option value="prototype_pose_dependency">原型位姿依赖模式（显式兜底）</option>
            </select>
          </label>
          <p className="muted-copy">
            {assemblyMode === "mate_driven_port_assembly"
              ? "仅固定设备基座；若配合束不能封闭必要自由度，系统将在启动CAD前阻断。"
              : "允许使用原型顶层位姿或案例锚点，只用于粗复原、调试和端口标定，不证明模组可自由组合。"}
          </p>
          <button type="button" onClick={() => void handleCompileManifest()} disabled={busy || context.connections.length === 0}>
            <Network />检查CAD执行就绪性
          </button>
        </>
      ) : null}

      {manifest ? (
        <div className={`global-preview ${manifest.status === "ready_for_project_adapter" ? "ready" : "blocked"}`}>
          <div><Network /><strong>执行清单：{manifest.status}</strong></div>
          <p>{manifest.stepCount}个连接步骤；SolidWorks未执行；碰撞未评估。</p>
          {manifest.steps.map((step) => (
            <p key={step.connectionId}>
              {step.order}. {step.semanticConnectionRequest.portAId} ↔ {step.semanticConnectionRequest.portBId} · {step.semanticConnectionRequest.templateId}
            </p>
          ))}
          <p className="muted-copy">{manifest.executionBoundary.statement}</p>
        </div>
      ) : null}

      {adapterPlan || independentManifest ? (
        <div className={`global-preview ${executionReady ? "ready" : "blocked"}`}>
          <div>
            {executionReady ? <CheckCircle2 /> : <ShieldAlert />}
            <strong>
              {independentMode
                ? `项目无关CAD事务清单：${independentManifest?.status ?? "未生成"}`
                : `原型位姿兜底执行计划：${adapterPlan?.status ?? "未生成"}`}
            </strong>
          </div>
          {independentMode ? (
            <>
              <p>
                规划方式：项目无关语义配合图；事务包：{independentManifest?.packetCount ?? 0}；
                发布绑定：{independentManifest?.relationReleaseBinding?.releaseId ?? "缺失"}。
              </p>
              <p>定位模式：仅由语义端口和真实配合驱动；不读取原型顶层位姿。</p>
              {independentManifest?.packets.map((packet) => (
                <p key={packet.packetId}>
                  {packet.order}. {packet.packetId} · {packet.operation} · {packet.executionStrategy}
                </p>
              ))}
              {independentManifest?.blockers.map((blocker, index) => (
                <p key={`${blocker.code}-${index}`}>{blocker.code}：{blocker.detail ?? "事务包未满足独立执行要求"}</p>
              ))}
              {portableReleasePreview?.status === "ready" && portableReleasePreview.recommendation ? (
                <div className="global-preview ready">
                  <div><Sparkles /><strong>发现可复用的便携关系发布</strong></div>
                  <p>
                    推荐：{portableReleasePreview.recommendation.releaseId}；将替换
                    {portableReleasePreview.recommendation.replacements.length}条欠约束模板。
                  </p>
                  {portableReleasePreview.recommendation.replacements.map((replacement) => (
                    <p key={replacement.connectionId}>
                      {replacement.connectionId}：{replacement.sourceTemplateId} → {replacement.portableTemplateId}
                    </p>
                  ))}
                  <p className="muted-copy">{portableReleasePreview.selectionPolicy}</p>
                  <label>
                    新装配会话编号（源会话不会被覆盖）
                    <input
                      value={portableTargetContextId}
                      onChange={(event) => setPortableTargetContextId(event.target.value)}
                    />
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={portableReleaseConfirmed}
                      onChange={(event) => setPortableReleaseConfirmed(event.target.checked)}
                    />
                    我确认创建新的便携发布上下文，并使用已验证配合束替代当前欠约束模板
                  </label>
                  <button
                    type="button"
                    onClick={() => void handlePortableReleaseUpgrade()}
                    disabled={busy || !portableReleaseConfirmed || !portableTargetContextId.trim()}
                  >
                    <CheckCircle2 />创建独立装配上下文（不执行CAD）
                  </button>
                </div>
              ) : portableReleasePreview?.status === "blocked" ? (
                <p className="collision-deferred">
                  当前没有单一便携发布覆盖全部连接；需要补发布或拆分装配链，系统不会自动拼接多个发布权限。
                </p>
              ) : null}
            </>
          ) : (
            <>
              <p>
                项目：{adapterPlan?.projectId ?? "无法唯一确定"}；累计步骤：{adapterPlan?.stepCount ?? 0}；
                顺序：{adapterPlan?.sequenceAssessment?.kind ?? "未判定"}。
              </p>
              <p>定位模式：原型位姿依赖兜底；可移植：否。</p>
            </>
          )}
          {adapterPlan?.poseDependencyAudit ? (
            <>
              <p>
                端口完整性：{adapterPlan.poseDependencyAudit.mateDrivenReadyCount}/
                {adapterPlan.poseDependencyAudit.connectionCount}条连接已证明可由配合独立定位；
                {adapterPlan.poseDependencyAudit.prototypePoseRequiredCount}条仍需要原型/案例位姿。
              </p>
              <p className="muted-copy">{adapterPlan.poseDependencyAudit.statement}</p>
              {adapterPlan.poseDependencyAudit.connections.map((row) => (
                <p key={`pose-${row.connectionId}`}>
                  {row.connectionId} · {row.status}
                  {row.remainingDof ? ` · 剩余自由度：${row.remainingDof}` : ""}
                </p>
              ))}
            </>
          ) : null}
          {adapterPlan?.seedCheckpoint ? (
            <p>已验证基座：{adapterPlan.seedCheckpoint.moduleToken}；后续仅从已提交检查点继续。</p>
          ) : null}
          {adapterPlan?.steps.map((step) => (
            <p key={step.stepId}>{step.stepId} · {step.moduleToken} · {step.sourceCheckpointPolicy}</p>
          ))}
          {adapterPlan?.blockers.map((blocker, index) => (
            <p key={`${blocker.code}-${index}`}>
              {blocker.code}：{blocker.detail}
              {blocker.missingPredecessors?.length ? `；缺少 ${blocker.missingPredecessors.join("、")}` : ""}
            </p>
          ))}
          {executionReady ? (
            <>
              <label>
                本次任务步骤数（建议先验证1步）
                <input
                  type="number"
                  min={1}
                  max={executionStepCount}
                  value={stepLimit}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setStepLimit(Math.max(1, Math.min(executionStepCount, value || 1)));
                    setPreparedJob(null);
                    setStartConfirmed(false);
                  }}
                />
              </label>
              <p className="collision-deferred">装配任务固定使用演示档位；工程碰撞验证在装配完成后独立启动。</p>
              {assemblyMode === "prototype_pose_dependency" ? (
                <label>
                  <input
                    type="checkbox"
                    checked={prototypeFallbackConfirmed}
                    onChange={(event) => setPrototypeFallbackConfirmed(event.target.checked)}
                  />
                  我确认本次显式使用原型位姿依赖模式；结果不可作为自由组合能力证明
                </label>
              ) : null}
              <label>
                <input
                  type="checkbox"
                  checked={prepareConfirmed}
                  onChange={(event) => setPrepareConfirmed(event.target.checked)}
                />
                我确认只创建排队任务和基座检查点；本操作不启动SolidWorks
              </label>
              <button
                type="button"
                onClick={() => void handlePrepareJob()}
                disabled={busy || !prepareConfirmed || (assemblyMode === "prototype_pose_dependency" && !prototypeFallbackConfirmed)}
              >
                <CheckCircle2 />创建排队任务（不执行CAD）
              </button>
              {preparedJob ? (
                <div>
                  <p>
                    已创建/复用任务：{preparedJob.jobId}；{preparedJob.steps.length}步；
                    {preparedJob.startRequestedAt ? "已提交后台执行请求。" : "当前仍未启动。"}
                  </p>
                  <label>
                    <input
                      type="checkbox"
                      checked={startConfirmed}
                      onChange={(event) => setStartConfirmed(event.target.checked)}
                    />
                    我确认下一操作将启动SolidWorks后台CAD任务，并从已验证基座执行上述步骤
                  </label>
                  <button type="button" onClick={() => void handleStartJob()} disabled={busy || !startConfirmed || Boolean(preparedJob.startRequestedAt)}>
                    <ShieldAlert />明确启动CAD任务
                  </button>
                  <p>
                    状态：{preparedJob.status}；已提交检查点：
                    {preparedJob.steps.filter((step) => step.status === "succeeded").length}/{preparedJob.steps.length}
                    {preparedJob.pauseRequested ? "；已请求暂停" : ""}
                    {preparedJob.cancelRequested ? "；已请求取消" : ""}
                  </p>
                  <p>
                    装配状态：{preparedJob.assemblyStatus ?? "未知"}；碰撞状态：
                    {preparedJob.collisionStatus === "passed"
                      ? "已通过工程验证"
                      : preparedJob.collisionStatus === "rejected"
                        ? "工程验证拒绝"
                        : "未评估"}
                  </p>
                  {preparedJob.steps.map((step) => (
                    <p key={step.stepId}>
                      {step.moduleToken} · {step.status} · 尝试{step.attemptCount}次
                      {step.checkpoint?.assemblyPath ? ` · ${step.checkpoint.assemblyPath}` : ""}
                      {step.error ? ` · ${step.error}` : ""}
                    </p>
                  ))}
                  {preparedJob.lastCommittedCheckpoint?.assemblyPath ? (
                    <p>最后有效检查点：{preparedJob.lastCommittedCheckpoint.assemblyPath}</p>
                  ) : null}
                  {preparedJob.commandAudit ? (
                    <p>
                      自然语言到CAD审计：{preparedJob.commandAudit.status}
                      {preparedJob.commandAudit.path ? ` · ${preparedJob.commandAudit.path}` : ""}
                    </p>
                  ) : null}
                  {preparedJob.executionDurationSeconds != null ? (
                    <p>累计执行耗时：{preparedJob.executionDurationSeconds.toFixed(3)}秒</p>
                  ) : null}
                  {preparedJob.userSummary?.markdownPath ? (
                    <p>可读结果摘要：{preparedJob.userSummary.markdownPath}</p>
                  ) : null}
                  {preparedJob.timingReport?.path ? (
                    <p>分阶段计时报告：{preparedJob.timingReport.path}</p>
                  ) : null}
                  {preparedJob.engineeringCheckpoint?.assemblyPath ? (
                    <p>工程验证检查点：{preparedJob.engineeringCheckpoint.assemblyPath}</p>
                  ) : (
                    <p className="collision-deferred">当前装配体尚无工程碰撞验证检查点。</p>
                  )}
                  {preparedJob.executionMode !== "generic_cad_manifest" && preparedJob.status === "succeeded" && preparedJob.demoCheckpoint?.assemblyPath ? (
                    <>
                      <label>
                        <input
                          type="checkbox"
                          checked={engineeringConfirmed}
                          onChange={(event) => setEngineeringConfirmed(event.target.checked)}
                        />
                        我确认对当前不可变Demo检查点单独执行工程碰撞验证
                      </label>
                      <button
                        type="button"
                        onClick={() => void handleEngineeringValidation()}
                        disabled={busy || !engineeringConfirmed || Boolean(
                          engineeringValidation && ["queued", "running"].includes(engineeringValidation.status)
                        )}
                      >
                        <ShieldAlert />启动独立工程验证
                      </button>
                    </>
                  ) : null}
                  {engineeringValidation ? (
                    <div>
                      <p>
                        工程验证：{engineeringValidation.status}；碰撞状态：
                        {engineeringValidation.collisionStatus}
                        {engineeringValidation.durationSeconds != null
                          ? `；耗时${engineeringValidation.durationSeconds.toFixed(3)}秒`
                          : ""}
                      </p>
                      <p>绑定SHA-256：{engineeringValidation.sourceAssemblyIdentity.sha256}</p>
                      {engineeringValidation.evidencePath ? <p>验证证据：{engineeringValidation.evidencePath}</p> : null}
                      {engineeringValidation.error ? <p>{engineeringValidation.error}</p> : null}
                    </div>
                  ) : null}
                  {preparedJob.rollback ? <p>失败回滚策略：{preparedJob.rollback.mode}</p> : null}
                  {preparedJob.executionMode !== "generic_cad_manifest" && preparedJob.status === "succeeded" ? (
                    <button type="button" onClick={() => void handlePrepareContinuation()} disabled={busy}>
                      <Plus />以上一检查点准备下一步（不启动CAD）
                    </button>
                  ) : null}
                  {["queued", "running"].includes(preparedJob.status) && preparedJob.startRequestedAt ? (
                    <>
                      <button type="button" onClick={() => void handlePauseJob()} disabled={busy}>请求暂停</button>
                      {preparedJob.executionMode !== "generic_cad_manifest" ? (
                        <button type="button" onClick={() => void handleCancelJob()} disabled={busy}>请求取消</button>
                      ) : null}
                    </>
                  ) : null}
                  {["paused", "failed", "cancelled"].includes(preparedJob.status) ? (
                    <>
                      <label>
                        <input
                          type="checkbox"
                          checked={resumeConfirmed}
                          onChange={(event) => setResumeConfirmed(event.target.checked)}
                        />
                        我确认从最后有效检查点恢复CAD任务
                      </label>
                      <button type="button" onClick={() => void handleResumeJob()} disabled={busy || !resumeConfirmed}>
                        从检查点恢复
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
              {startMessage ? <p>{startMessage}</p> : null}
            </>
          ) : null}
          <p className="collision-deferred">装配任务不内嵌碰撞门禁；Demo成功后可对不可变检查点独立验证。</p>
        </div>
      ) : null}

    </section>
  );
}
