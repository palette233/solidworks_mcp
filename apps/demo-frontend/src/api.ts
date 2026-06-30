export type Coordinate = {
  x: number;
  y: number;
  z: number;
};

export type Layout2d = {
  x: number;
  y: number;
  thetaDegrees?: number | null;
  thetaAxis?: string | null;
};

export type LayoutComponentSummary = {
  componentName: string;
  filePath?: string | null;
  bottomFaceName: string;
  layout2d?: Layout2d | null;
  faceMappingFound?: boolean | null;
};

export type LayoutJsonInfo = {
  path: string;
  success?: boolean | null;
  message?: string | null;
  baseComponentName?: string | null;
  componentCount: number;
  components: LayoutComponentSummary[];
};

export type DemoComponent = {
  id: string;
  displayName: string;
  componentName: string;
  filePath: string;
  bottomFaceName: string;
  current: Coordinate;
  target: Coordinate;
};

export type DemoState = {
  assemblyPath: string | null;
  commonBaseReady: boolean;
  layoutJsonPath?: string | null;
  layoutInfo?: LayoutJsonInfo | null;
  components: DemoComponent[];
  lastRun?: {
    status?: string;
    message?: string;
    toolSuccess?: boolean;
    toolMessage?: string;
    screenshotPath?: string | null;
    components?: ArrangeComponentResult[];
    orientationCorrections?: OrientationCorrection[];
    orientationChecks?: OrientationCheck[];
    missingFaceMappings?: string[];
    replayValidation?: ReplayValidation;
  } | null;
  updatedAt: string;
};

export type ToolCallPlan = {
  tool: string;
  arguments: Record<string, unknown>;
};

export type OperationResult = {
  status: "ok" | "dry-run" | "blocked" | "error";
  message: string;
  plan: ToolCallPlan[];
  toolResults: Array<Record<string, unknown>>;
  state: DemoState | null;
  missingFaceMappings: Array<Record<string, string>>;
  layoutInfo?: LayoutJsonInfo | null;
};

export type McpHealthResult = {
  status: "ok" | "dry-run" | "blocked" | "error";
  message: string;
  activeDocument?: Record<string, unknown> | null;
  expectedAssemblyPath?: string | null;
  activeAssemblyMatchesState?: boolean | null;
  faceMappingPath?: string | null;
  mcpFaceMappingPath?: string | null;
  faceMappingPathsMatch?: boolean | null;
  mcpFaceMappingInfo?: Record<string, unknown> | null;
  toolResults: Array<Record<string, unknown>>;
};

export type ArrangeComponentResult = {
  componentName: string;
  layout2d?: Layout2d | null;
  faceSelection?: { success?: boolean; message?: string } | null;
  bottomMateResult?: { mateType?: string; errorName?: string; errorDescription?: string } | null;
  bottomFaceCenter?: { success?: boolean; center?: number[]; message?: string } | null;
  rotationResult?: { success?: boolean; message?: string } | null;
  currentThetaDegrees?: number | null;
  targetThetaDegrees?: number | null;
  deltaThetaDegrees?: number | null;
  moveResult?: { success?: boolean; message?: string } | null;
};

export type FaceProbe = {
  worldNormal?: number[] | null;
  localNormal?: number[] | null;
  worldCenter?: number[] | null;
  localCenter?: number[] | null;
  area?: number | null;
  message?: string;
};

export type OrientationCorrection = {
  stage?: string;
  componentName: string;
  bottomFaceName?: string;
  success?: boolean;
  applied?: boolean;
  rotationAxis?: number[] | null;
  angleDegrees?: number;
  beforeProbe?: FaceProbe | null;
  afterRotationProbe?: FaceProbe | null;
  afterRestoreProbe?: FaceProbe | null;
  message?: string;
};

export type OrientationCheck = {
  componentName: string;
  bottomFaceName?: string;
  success?: boolean;
  matchesBase?: boolean;
  dotWithBase?: number | null;
  normalDotThreshold?: number;
  worldNormal?: number[] | null;
  faceProbe?: FaceProbe | null;
  message?: string;
};

export type ArrangeToolPayload = {
  success: boolean;
  message: string;
  screenshot?: { outputPath?: string | null } | null;
  components?: ArrangeComponentResult[];
  orientationCorrections?: OrientationCorrection[];
  orientationChecks?: OrientationCheck[];
  missingFaceMappings?: string[];
};

export type ReplayValidationComponent = {
  componentName: string;
  success?: boolean;
  xyError?: number | null;
  thetaErrorDegrees?: number | null;
  message?: string;
};

export type ReplayValidation = {
  success?: boolean;
  message?: string;
  maxXyError?: number | null;
  maxThetaErrorDegrees?: number | null;
  captureStatus?: string;
  captureMessage?: string;
  captureOutputPath?: string;
  components?: ReplayValidationComponent[];
};

const jsonHeaders = {
  "Content-Type": "application/json"
};

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function getState(): Promise<DemoState> {
  return request<DemoState>("/api/demo/state");
}

export async function getMcpHealth(): Promise<McpHealthResult> {
  return request<McpHealthResult>("/api/demo/mcp-health");
}

export async function saveState(state: DemoState): Promise<DemoState> {
  return request<DemoState>("/api/demo/state", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(state)
  });
}

export async function resetState(): Promise<DemoState> {
  return request<DemoState>("/api/demo/reset", {
    method: "POST"
  });
}

export async function arrange(state: DemoState): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/arrange", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      alignBottom: true,
      useLlm: false,
      components: state.components.map((component) => ({
        id: component.id,
        componentName: component.componentName,
        x: component.target.x,
        y: component.target.y,
        z: component.target.z
      }))
    })
  });
}

export async function initializeCommonBase(state: DemoState): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/initialize-common-base", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      alignBottom: false,
      useLlm: false,
      components: state.components.map((component) => ({
        id: component.id,
        componentName: component.componentName,
        x: component.target.x,
        y: component.target.y,
        z: component.target.z
      }))
    })
  });
}

export async function finalizeCommonBase(): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/finalize-common-base", {
    method: "POST"
  });
}

export async function captureCommonBaseLayout(): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/capture-common-base-layout", {
    method: "POST"
  });
}

export async function listLayoutJsonFiles(): Promise<LayoutJsonInfo[]> {
  return request<LayoutJsonInfo[]>("/api/demo/layout-json-files");
}

export async function selectLayoutJson(layoutJsonPath: string, syncComponents = true): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/select-layout-json", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ layoutJsonPath, syncComponents })
  });
}

export async function uploadLayoutJson(fileName: string, content: string, syncComponents = true): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/upload-layout-json", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ fileName, content, syncComponents })
  });
}

export async function verifyFaceMappings(): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/verify-face-mappings", {
    method: "POST"
  });
}

export async function applyCapturedLayout(): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/apply-captured-layout", {
    method: "POST"
  });
}

export function parseArrangePayload(result: OperationResult | null): ArrangeToolPayload | null {
  const last = result?.toolResults?.at(-1);
  const texts = last?.text;
  if (!Array.isArray(texts) || typeof texts.at(-1) !== "string") {
    return null;
  }

  try {
    return JSON.parse(texts.at(-1) as string) as ArrangeToolPayload;
  } catch {
    return null;
  }
}
