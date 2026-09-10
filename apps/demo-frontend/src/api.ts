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
    toolResults?: Array<Record<string, unknown>>;
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
  discovery?: DiscoveryResult | null;
  constraintLayout?: ConstraintLayoutPlan | null;
};

export type ConstraintRole = "fixed" | "gantry" | "transport" | "glue" | "functional";

export type SemanticModuleType =
  | "frame"
  | "gantry"
  | "dispenser"
  | "transport"
  | "return_transport"
  | "glue_supply"
  | "scanner"
  | "ccd"
  | "calibration"
  | "cleaning"
  | "weighing"
  | "carrier"
  | "functional";

export type ModuleSemanticInput = {
  moduleType: SemanticModuleType;
  points?: Record<string, { u: number; v: number }>;
  regions?: Record<string, { minU: number; minV: number; maxU: number; maxV: number }>;
  preferredSide?: "auto" | "low" | "high";
  allowedRotationDegrees?: number[];
  parameters?: Record<string, unknown>;
};

export type ProvisionalComponentInput = {
  componentName: string;
  widthMeters: number;
  depthMeters: number;
  heightMeters: number;
  anchorU?: number;
  anchorV?: number;
  filePath?: string | null;
  bottomFaceName?: string;
  reason?: string;
  replayable?: boolean;
};

export type ConstraintLayoutPlan = {
  roles?: Record<string, ConstraintRole>;
  roleReasons?: Record<string, string>;
  gantryComponentName?: string;
  longAxis?: string;
  usedMarginRatio?: number;
  minimumClearanceMeters?: number;
  glueDistanceMeters?: number;
  attempts?: Array<{ marginRatio: number; success: boolean; message: string }>;
  portalConstraints?: Array<{
    portalComponentName: string;
    passThroughComponentNames: string[];
    estimatedOpeningWidth?: number;
    estimatedOpeningHeight?: number;
    minimumClearanceMeters?: number;
    requiresCadInterferenceValidation?: boolean;
  }>;
  moduleSemantics?: Record<string, ModuleSemanticInput>;
  processConstraints?: Array<Record<string, unknown>>;
  processValidation?: {
    success?: boolean;
    hardFeasible?: boolean;
    constraintCount?: number;
    passedCount?: number;
    hardFailureCount?: number;
    softFailureCount?: number;
    diagnostics?: Array<{
      id: string;
      type: string;
      hard: boolean;
      success: boolean;
      message: string;
      measured?: Record<string, unknown>;
    }>;
  };
  provisionalPlaceholderCount?: number;
  assumptionWarnings?: string[];
  validation?: {
    success?: boolean;
    overlapPairs?: string[][];
    allowedAabbOverlapPairs?: string[][];
    requiresCadInterferenceValidation?: boolean;
    componentCount?: number;
    containmentRelaxedComponents?: string[];
    processHardFeasible?: boolean;
    productionReady?: boolean;
  };
};

export type PreviewBounds = {
  minU: number;
  minV: number;
  maxU: number;
  maxV: number;
};

export type PreviewModule = {
  componentName: string;
  code: string;
  label: string;
  moduleType: string;
  role: ConstraintRole;
  color: string;
  center: number[];
  bounds: number[];
  thetaDegrees: number;
  rotationQuarters: number;
  points: Array<{ name: string; position: number[] }>;
  regions: Array<{ name: string; bounds: number[] }>;
  protectedSpaces: Array<{
    id: string;
    bounds: number[];
    heightRangeMeters: number[];
    purpose: string;
    minimumClearanceMeters: number;
    hardClearanceWith: string[];
    enforcement?: string;
    confirmed?: boolean | null;
    evidenceStatus?: string | null;
  }>;
  interactionEnvelope?: {
    bounds: number[];
    heightRangeMeters: number[];
    source: string;
  } | null;
  hardBodyEnvelope?: {
    bounds: number[];
    heightRangeMeters: number[];
    source: string;
  } | null;
  transportSweepEnvelope?: {
    bounds: number[];
    heightRangeMeters: number[];
    source: string;
  } | null;
  transportStaticKeepoutEnvelope?: {
    bounds: number[];
    heightRangeMeters: number[];
    source: string;
  } | null;
  provisional: boolean;
};

export type PreviewReviewItem = {
  severity: "pass" | "warning" | "fail" | "info";
  title: string;
  message: string;
};

export type AssemblySequenceStage = {
  id: string;
  title: string;
  moduleCodes: string[];
  status: "ready" | "provisional" | "blocked";
  evidence: Array<{
    label: string;
    available: boolean;
    source: string;
    details?: Record<string, unknown>;
  }>;
  blockedBy: string[];
  measured: Record<string, unknown>;
};

export type AssemblySequencePlan = {
  schemaVersion: string;
  enabled: boolean;
  mode: string;
  currentLayoutSolverMode: string;
  sequentialSolverReady: boolean;
  baseModuleCode: string;
  operationSide: string;
  installationFrameResolved?: boolean;
  installationGeometryResolved?: boolean;
  installationGeometry?: {
    status?: string | null;
    installationPlatform?: {
      boundary?: Record<string, number>;
      safeBoundary?: Record<string, number>;
      edgeMarginMeters?: number;
    } | null;
    transportSupportRegion?: Record<string, number> | null;
    hardKeepoutRegionCount: number;
    hardKeepoutRegions?: Array<{
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
      source?: string;
    }>;
    conditionalStructuralBodyCount: number;
    captureCoverage?: {
      capturedBodyCount?: number;
      failedBodyCount?: number;
      coverageRatio?: number;
      coverageComplete?: boolean;
    } | null;
    authoritativeForFinalCollision?: boolean;
  } | null;
  prototypeTransportInterfaceResolved?: boolean;
  mateDerivedTransportInterfaceResolved?: boolean;
  mateDerivedTransportInterface?: {
    status?: string | null;
    datumFrameMeters?: number[] | null;
    constraintInterpretation?: {
      fixedTranslationAxes?: string[];
      freeTranslationAxes?: string[];
      orientationFullyConstrained?: boolean;
      remainingDegreeOfFreedom?: string;
    } | null;
    axisConfidence?: Record<string, string> | null;
    confirmedAsVendorInterface?: boolean;
    remainingRequiredConfirmation?: string | null;
  } | null;
  scanStationInferenceResolved?: boolean;
  scanStationInferencePath?: string | null;
  scanStationInference?: {
    status?: string | null;
    selectedCarrierInstance?: string | null;
    candidateCount?: number | null;
    nearestDistanceMarginMeters?: number | null;
    selectedDistanceMeters?: number | null;
    dynamicScanStopConfirmed?: boolean | null;
    usableForCoarseLayout?: boolean | null;
  } | null;
  dynamicScanWindowResolved?: boolean;
  dynamicScanInputAuthority?: string;
  dynamicScanPrototypeDerived?: boolean;
  dynamicScanWindowPath?: string | null;
  dynamicScanWindow?: {
    status?: string | null;
    estimatedStopToleranceMeters?: number | null;
    windowAxis?: string | null;
    engineeringConfirmed?: boolean | null;
    plcTriggerConfirmed?: boolean | null;
    usableForCoarseLayout?: boolean | null;
  } | null;
  selectedServiceSide: string;
  operationSideCapacityEstimated?: boolean;
  operationSideCapacityEvidencePath?: string | null;
  operationSideCapacity?: {
    status?: string | null;
    operationSideGrossBand?: {
      grossDepthMeters?: number;
      grossWidthMeters?: number;
      grossAreaSquareMeters?: number;
      remainingAreaBeforeAnchoredModuleOccupancySquareMeters?: number;
    } | null;
    prototypeServiceCluster?: {
      requiredDepthFromSafeFrontMeters?: number;
      requiredLateralSpanMeters?: number;
    } | null;
    capacityDecision?: {
      simpleRectangularBandFits?: boolean;
      prototypeDemonstratesNonConvexFit?: boolean;
      estimatedSelectedSide?: string;
      confidence?: string;
    } | null;
    maintenanceEstimate?: {
      staticModuleClearanceMeters?: number;
      a500ProtectedAccessStripDepthMeters?: number;
      authoritativeForFinalMaintenance?: boolean;
    } | null;
    authoritativeForFinalMaintenance?: boolean;
  } | null;
  serviceAccessEstimated?: boolean;
  serviceAccessInputAuthority?: string;
  serviceAccessPrototypeDerived?: boolean;
  serviceAccessEvidencePath?: string | null;
  serviceAccess?: {
    status?: string | null;
    protectedSpaceConstraintCount?: number | null;
    engineeringConfirmed?: boolean | null;
    authoritativeForFinalMaintenance?: boolean | null;
  } | null;
  serviceFunctionalSplitResolved?: boolean;
  serviceFunctionalSplitEvidencePath?: string | null;
  serviceFunctionalSplit?: {
    status?: string | null;
    rigidPlacementUnit?: string | null;
    totalServiceAccessConstraintCount?: number | null;
    functions?: {
      cleaning?: {
        sourceSubassemblies?: string[];
        derivedServicePointLocalMeters?: { u?: number; v?: number };
      };
      weighing?: {
        sourceSubassemblies?: string[];
        derivedServicePointLocalMeters?: { u?: number; v?: number };
      };
    };
  } | null;
  dualValveReachEstimated?: boolean;
  dualValveReachInputAuthority?: string;
  dualValveReachPrototypeDerived?: boolean;
  dualValveReachEvidencePath?: string | null;
  dualValveReach?: {
    status?: string | null;
    commonIntersectionMatches?: boolean | null;
    estimatedValveHeadSpacingMeters?: number | null;
    engineeringConfirmed?: boolean | null;
    authoritativeForFinalMotion?: boolean | null;
  } | null;
  dualValveAxisEvidencePath?: string | null;
  dualValveAxisEvidence?: {
    status?: string | null;
    evidence?: {
      topLevelModuleCount?: number | null;
      capturedLeafBodyCount?: number | null;
      namedLimitDistanceMate?: {
        found?: boolean | null;
        solidWorksMateType?: string | null;
        currentDistanceMeters?: number | null;
      } | null;
    } | null;
    solverSensitivity?: Array<{
      id?: string | null;
      commonWidthUMeters?: number | null;
      commonWidthVMeters?: number | null;
      feasible?: boolean | null;
      replayRequiredIfApplied?: boolean | null;
      jointCandidateLimit?: number | null;
      layoutComparison?: { maxXyErrorMeters?: number | null } | null;
    }> | null;
    diagnosis?: {
      blockingModule?: string | null;
      blockingClass?: string | null;
      balancedExpandedSearchFeasible?: boolean | null;
    } | null;
  } | null;
  dualValveConstraintAblationPath?: string | null;
  dualValveConstraintAblation?: {
    status?: string | null;
    formalRequestModified?: boolean | null;
    scenarios?: Array<{
      id?: string | null;
      feasible?: boolean | null;
      elapsedSeconds?: number | null;
      rank1PlacementSignature?: Record<string, [number, number, number, number]> | null;
      processConstraintFailureCounts?: Record<string, Record<string, number>> | null;
    }> | null;
    diagnosis?: {
      baselineFeasible?: boolean | null;
      relativeWindowRemovalRecoversFeasibility?: boolean | null;
      relativeWindowWideningRecoversFeasibility?: boolean | null;
      softRelativePreferenceRecoversFeasibility?: boolean | null;
      drainReachRemovalRecoversFeasibility?: boolean | null;
      allA300ProcessDomainRemovalRecoversFeasibility?: boolean | null;
      interpretation?: string | null;
    } | null;
  } | null;
  parameterRobustnessAudited?: boolean;
  parameterRobustnessEvidencePath?: string | null;
  parameterRobustness?: {
    status?: string | null;
    scenarioCount?: number | null;
    summary?: {
      dynamicScan?: {
        maximumTestedFeasibleValue?: number | null;
        maximumTestedLayoutPreservingValue?: number | null;
        firstTestedFailureValue?: number | null;
      };
      serviceAccess?: {
        maximumTestedFeasibleValue?: number | null;
        maximumTestedLayoutPreservingValue?: number | null;
        firstTestedFailureValue?: number | null;
      };
      dualValveReach?: {
        maximumTestedFeasibleValue?: number | null;
        maximumTestedLayoutPreservingValue?: number | null;
        firstTestedFailureValue?: number | null;
      };
    };
  } | null;
  moduleMateGraphPath: string;
  sourceAssemblyPath?: string | null;
  stages: AssemblySequenceStage[];
  summary: {
    stageCount: number;
    readyCount: number;
    provisionalCount: number;
    blockedCount: number;
    mateEvidenceBundleCount: number;
  };
  nextRequiredInputs: string[];
  message: string;
};

export type ProjectCasePreview = {
  caseId: string;
  title: string;
  generatedAt: string;
  sourceIndependent: boolean;
  relativeConstraintsSourceIndependent?: boolean;
  prototypePoseUsedForSolving: boolean;
  sourceCapturePoseUsedForAnchoring?: boolean;
  caseAnchor?: {
    componentName: string;
    targetKind: string;
    scope: string;
    targetAnchor: number[];
    appliedTranslation: number[];
    achievedAnchor: number[];
    exactSourcePoseReuse: boolean;
    sourceCapturePoseReadForAnchor?: boolean;
    prototypeDerivedParameter?: boolean;
    targetSource?: string | null;
    relativeConstraintsRemainSourceIndependent: boolean;
  } | null;
  inverseGantryCoverage?: {
    method: string;
    gantryComponentName: string;
    constraintCount: number;
    targetPointCount: number;
    feasibleAnchorRegion: number[] | null;
    selectedAnchor: number[];
    nonEmpty: boolean;
    selectedInside: boolean;
  } | null;
  fixedEnvironment?: {
    componentName: string;
    componentCode: string;
    role: "fixed";
    degreesOfFreedom: number;
    worldTransformPreserved: boolean;
    searchVariable: boolean;
    installationFrameName: string;
    geometryAuthoritativeForFinalCollision: boolean;
    candidateValidationCount: number;
  } | null;
  fixedEnvironmentValidation?: {
    hardFeasible: boolean;
    constraintCount: number;
    passedCount: number;
    hardFailureCount: number;
  } | null;
  solverMode: string;
  solutionPath: string;
  previewPath: string;
  viewBounds: PreviewBounds;
  longAxis: string;
  modules: PreviewModule[];
  solutions?: Array<{
    rank: number;
    score: number;
    candidateRanks: number[];
    predictedConditionalBrepPairCount: number;
    predictedConditionalLeafAabbHitCount: number;
    conditionalLeafAabbRisks: ConditionalLeafAabbRisk[];
    modules: PreviewModule[];
  }>;
  jointSearchSummary?: {
    success?: boolean;
    solutionCount: number;
    exploredNodeCount: number;
    maximumSearchNodes: number;
    candidateCounts: Record<string, number>;
    acceptedCandidateCounts: Record<string, number>;
    rejectionCounts?: Record<string, Record<string, number>>;
    processConstraintFailureCounts: Record<string, Record<string, number>>;
    collisionMatrix: Record<string, number>;
    moduleStageDiagnostics?: Record<string, {
      candidateCount: number;
      acceptedCandidateCount: number;
      candidateGenerationCalls: number;
      candidateCacheHitCount: number;
      candidatePipelineSeconds: number;
      rejectionCounts: Record<string, number>;
      processConstraintFailureCounts: Record<string, number>;
    }>;
    elapsedSeconds?: number | null;
    timeLimitSeconds?: number | null;
  };
  assemblySequencePlan?: AssemblySequencePlan | null;
  diagnostics: Array<{
    id: string;
    type: string;
    group: string;
    hard: boolean;
    success: boolean;
    message: string;
    measured?: Record<string, unknown>;
  }>;
  metrics: {
    componentCount: number;
    processPassed: number;
    processTotal: number;
    spatialPassed: number;
    spatialTotal: number;
    interactionPassed: number;
    interactionTotal: number;
    interactionHardPassed?: number;
    interactionHardTotal?: number;
    interactionAdvisoryWarningCount?: number;
    fixedEnvironmentPassed?: number;
    fixedEnvironmentTotal?: number;
    reachContained: boolean;
    hardFeasible: boolean;
    transportCenterOffsetMeters?: number | null;
    portalGantryOverlapRatio?: number | null;
    portalCenterOffsetMeters?: number | null;
    portalMaximumCenterOffsetMeters?: number | null;
    portalMaximumOverhangMeters?: number | null;
    portalAllowedOverhangMeters?: number | null;
    serviceClusterDeltaUMeters?: number | null;
    serviceClusterDeltaVMeters?: number | null;
    unallowedOverlapCount: number;
    allowedOverlapReviewCount: number;
    strictAabbPairCount: number;
    conditionalBrepPairCount: number;
    installationContactPairCount?: number;
    predictedConditionalLeafAabbHitCount: number;
    solverBrepCallCount: number;
    productionReady: boolean;
  };
  staticCollisionPolicy?: {
    pairCount: number;
    strictAabbPairCount: number;
    brepOnAabbOverlapPairCount: number;
    installationContactPairCount?: number;
    solverInvokesBrep: boolean;
  };
  allowedOverlapPairs: string[][];
  conditionalLeafAabbRisks: ConditionalLeafAabbRisk[];
  reviewItems: PreviewReviewItem[];
  assumptionWarnings: string[];
};

export type Project02DependencyAblationBundle = {
  schemaVersion: string;
  readOnly: boolean;
  reportPath: string;
  report: {
    generatedAt: string;
    recommendedVariantForVisualReview?: "B" | "C" | null;
    recommendedVariantForCadValidation?: "B" | "C" | null;
    cadValidationBlockedPendingVisualApproval?: boolean;
    referenceV22UnderGeometryOnlyValidation?: {
      hardFeasible: boolean;
      hardFailureCount: number;
      advisoryWarningCount: number;
      conditionalBrepRiskCount: number;
    };
    experiments: Array<{
      variant: "A" | "B" | "C";
      success: boolean;
      durationSeconds?: number;
      solutionCount?: number;
      rank1Score?: number;
      rank1PredictedConditionalBrepPairCount?: number;
      rank1PredictedConditionalLeafAabbHitCount?: number;
      rank1DifferenceFromV22?: {
        maximumCenterDistanceMeters?: number;
      };
    }>;
  };
  variants: Partial<Record<"B" | "C", ProjectCasePreview>>;
  collisionFeedback?: {
    reportPath: string;
    previewPath: string;
    report: {
      success: boolean;
      solutionCount: number;
      sourceVariant: string;
      compatibilityGate: {
        passed: boolean;
        solutionCount: number;
        solutions: Array<{
          rank: number;
          passed: boolean;
          orientationViolations: unknown[];
          confirmedPairRisks: string[][];
          repeatsRejectedCandidate: boolean;
        }>;
      };
      feedbackMetadata: {
        confirmedHardOccupancyPairs: string[][];
        orientationRestrictions: Array<{
          componentCode: string;
          retainedRotationDegrees: number[];
        }>;
      };
      timing: {
        solveSeconds: number;
        totalSeconds: number;
      };
      nextGate: string;
    };
    preview: ProjectCasePreview;
  } | null;
};

export type ProjectMigrationReadiness = {
  schemaVersion: string;
  projectId: string;
  family: string;
  status: string;
  sourceAssemblyPath: string;
  sourceAssemblyExists: boolean;
  pptPath?: string | null;
  pptExists: boolean;
  moduleCount: number;
  resolvedModuleCadCount: number;
  allModuleCadPathsResolved: boolean;
  proposedTopLevelSolveObjects: string[];
  capabilityCoverage: string[];
  missingRequiredEvidence: string[];
  partialEvidence: string[];
  firstStageGeometry?: {
    status: string;
    transportInstallationInterface: {
      locatingHoleSpacingMeters: number;
      flowAxisWorld: number[];
      transverseAxisWorld: number[];
      upAxisWorld: number[];
    };
    operationSideInference: {
      candidate: string;
      confidence: string;
      exactFaceCaptured: boolean;
    };
    topLevelOccupancy: {
      capturedInstanceCount: number;
      majorModuleCount: number;
      looseAuxiliaryInstanceCount: number;
    };
    mateGraphSummary: {
      interModuleMateCount: number;
      mateBundleCount: number;
    };
  } | null;
  workPositions?: {
    status: string;
    coarseLayoutUsable: boolean;
    engineeringConfirmed: boolean;
    workPositionCount: number;
    centerSeparationMeters: number;
    workPositions: Array<{
      stableId: string;
      sourceInstance: string;
      installationFramePointMeters: {
        u: number;
        v: number;
        normal: number;
      };
    }>;
    geometricConsistency?: {
      guardCount: number;
      maximumGuardMidpointDeltaMeters: number;
      passesThirtyMillimeterTolerance: boolean;
    };
    pptProcessEvidence?: {
      rotationAngleDegrees: number;
    };
  } | null;
  scannerGeometry?: {
    status: string;
    scannerModel: string;
    scannerCount: number;
    engineeringConfirmed: boolean;
    processSummary?: string;
    scanners: Array<{
      role: "carrierBarcodeScanner" | "productBarcodeScanner" | string;
      opticalDirectionWorld: number[];
      modeledWorkingDistanceMeters: number;
    }>;
    barcodeInterfaces?: {
      productBarcode?: { status: string; side?: string };
      carrierBarcode?: { status: string; reason?: string };
    };
    carrierIdentityDevice?: {
      role: string;
      confidence: string;
    };
  } | null;
  servicePoints?: {
    status: string;
    engineeringConfirmed: boolean;
    combinedServiceModule: {
      cadId?: string;
      functionCount: number;
      reachTargetCount: number;
      functions: string[];
    };
    calibrationModule: {
      cadId?: string;
      reachTargetCount: number;
    };
    servicePorts: Array<{
      id: string;
      capability: string;
      worldMeters: number[];
      confidence: string;
      proxyMethod: string;
    }>;
  } | null;
  dualValveReach?: {
    status: string;
    engineeringConfirmed: boolean;
    vendorConfirmed: boolean;
    allRequiredTargetsInsideCommonReach: boolean;
    requiredTargetCount: number;
    minimumTargetBoundaryMarginMeters: number;
    commonReachInstallationFrameMeters: {
      minU: number;
      maxU: number;
      minV: number;
      maxV: number;
      widthU: number;
      widthV: number;
    };
    valvePair: {
      spacingMeters: number;
      spacingAlongFlowMeters: number;
      spacingAlongTransverseMeters: number;
    };
  } | null;
  moduleOccupancy?: {
    status: string;
    engineeringConfirmed: boolean;
    prototypeBaselineAcceptedForCoarseLayout: boolean;
    coverage: {
      layoutObjectCount: number;
      leafCapturedStructuralModuleCount: number;
      requiredLeafCapturedStructuralModuleCount: number;
      capturedLeafBodyCount?: number;
      singleBoxOrdinaryModules: string[];
      fixedContextTopLevelBoxes: string[];
    };
    staticCollisionPolicy: {
      pairCount: number;
      coveredPairCount: number;
      aabbInflationPerSideMeters: number;
      strictMultiAabbPairs: string[][];
      conditionalBrepPairs: Array<{ pair: string[]; reason: string }>;
      installationContactPairs: Array<{ pair: string[]; reason: string }>;
      solverInvokesBrep: boolean;
      postReplayBrepOnly: boolean;
    };
  } | null;
  top3SolveReady: boolean;
  project01NumericParametersInherited?: boolean;
  project02NumericParametersInherited: boolean;
  layoutObjectGroups: Array<{
    id: string;
    placementMode: string;
    primaryCadId: string;
    memberCadIds: string[];
    membersResolved: boolean;
    reason: string;
  }>;
  requiredEvidence: Array<{
    id: string;
    status: "available" | "partial" | "missing";
    acquisition: string;
  }>;
  forbiddenInheritedProject02Constants?: string[];
  forbiddenInheritedCaseConstants?: string[];
  portableRulesSelected: string[];
  nextExtractionOrder: string[];
};

export type ConditionalLeafAabbRisk = {
  firstComponentName: string;
  secondComponentName: string;
  firstCode: string;
  secondCode: string;
  firstCenter: number[];
  secondCenter: number[];
  hitCount: number;
  broadPhaseOnly: boolean;
};

export type ProjectCapabilityRecommendation = {
  id: string;
  label: string;
  source: "explicit" | "dependency";
  evidence: string[];
  requiredBy?: string | null;
};

export type ProjectModuleRecommendation = {
  code: string;
  label: string;
  componentName: string;
  status: "required" | "optional" | "not_selected";
  required: boolean;
  selectedByDefault: boolean;
  capabilities: string[];
  optionalCapability?: string | null;
  reasons: string[];
};

export type ProjectModuleRecommendationResult = {
  projectId: string;
  generatedAt: string;
  requirement: string;
  normalizedRequirement: string;
  productCountPerCarrier?: number | null;
  capabilities: ProjectCapabilityRecommendation[];
  excludedCapabilities: Array<{ id: string; label: string }>;
  dependencyAdditions: Array<{ capability: string; requiredBy: string }>;
  modules: ProjectModuleRecommendation[];
  requiredModuleCodes: string[];
  defaultSelectedModuleCodes: string[];
  optionalModuleCodes: string[];
  coverage: {
    requiredCapabilityCount: number;
    coveredCapabilityCount: number;
    complete: boolean;
  };
  missingInformation: string[];
  assumptions: string[];
  layoutCompatibility: {
    caseId: string;
    compatible: boolean;
    requiredBaselineModuleCodes: string[];
    missingForCurrentSolver: string[];
    message: string;
  };
  savedPath?: string | null;
};

export type ProjectModuleConfirmationResult = {
  projectId: string;
  confirmedAt: string;
  accepted: boolean;
  selectedModuleCodes: string[];
  missingRequiredModuleCodes: string[];
  unknownModuleCodes: string[];
  layoutSolverReady: boolean;
  missingForCurrentSolver: string[];
  message: string;
  savedPath?: string | null;
};

export type LayoutVerificationPlan = {
  caseId: string;
  status: "awaiting_visual_review" | "visual_review_approved" | string;
  sourcePreviewGeneratedAt: string;
  selectedSolutionRank?: number | null;
  selectedSolutionPath?: string | null;
  approvedAt?: string | null;
  reviewerNote: string;
  stages: Array<{
    id: string;
    status: "pending" | "blocked" | "completed" | "deferred" | string;
    blockedBy?: string[];
    checks?: string[];
    scope?: string;
    requiredWhen?: string;
    maximumPairCount?: number;
    allPairBaselineCount?: number;
    minimumAvoidedPairCount?: number;
  }>;
  policy: {
    manualModuleMoveAfterFailure: boolean;
    failureAction: string;
    stopOnFirstHardInterference: boolean;
    reusePassingPairResultsWhenPosesUnchanged: boolean;
    solverInvokesBrep?: boolean;
  };
  cadClosureReuse?: {
    success: boolean;
    status: string;
    replayRequired: boolean;
    conditionalBrepRequired: boolean;
    staticCollisionReady: boolean;
    priorCadClosure?: {
      assemblyPath?: string | null;
      status?: string | null;
    };
  };
  collisionClosure?: {
    status: string;
    demoConditionallyPassed: boolean;
    strictAabbClearPairCount: number;
    exactClearTopLevelPairCount: number;
    provisionalAllowedBodyContactCount: number;
    illegalInterferenceCount: number;
    incompleteCheckCount: number;
    productionReady: boolean;
    message: string;
    evidencePath?: string;
  };
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

export type FaceEndpointView = {
  endpointId: string;
  moduleToken: string;
  moduleHierarchyPath: string;
  leafHierarchyPath: string;
  relativeLeafHierarchyPath: string;
  leafComponentName: string;
  geometryClass: string;
  bodyIndex: number;
  faceIndex: number;
  faceAreaSquareMeters: number;
  faceCenterLocal?: number[] | null;
  faceCenterWorld?: number[] | null;
  faceNormalLocal?: number[] | null;
  faceNormalWorld?: number[] | null;
  recoveryConfidence?: string | null;
};

export type FaceEndpointCatalogView = {
  success: boolean;
  catalogPath: string;
  catalogMode?: string | null;
  sourceAssemblyPath?: string | null;
  endpointCount: number;
  modules: string[];
  leaves: string[];
  mergedLeafSelectors: string[];
  endpoints: FaceEndpointView[];
  message: string;
};

export type FaceMatePatchPreview = {
  success: boolean;
  compatible: boolean;
  message: string;
  catalogPath: string;
  sourceGraphPath: string;
  selectedEndpoints: FaceEndpointView[];
  patch: Record<string, unknown>;
  previewDigest: string;
  suggestedOutputAssemblyPath: string;
  effectiveSummary: {
    moduleCount: number;
    mateCount: number;
    operationCount: number;
    warnings: string[];
  };
};

export type FaceMatePatchApplyResult = {
  status: "ok" | "error";
  success: boolean;
  message: string;
  previewDigest: string;
  artifacts: {
    outputAssemblyPath: string;
    patchPath: string;
    effectiveGraphPath: string;
    resultPath: string;
  };
  rebuildSummary: {
    requestedMateCount?: number | null;
    createdMateCount?: number | null;
    reopenedMateCount?: number | null;
    parametersMatch?: boolean | null;
    mateCreationErrorsClear?: boolean | null;
    componentsNotOverConstrained?: boolean | null;
    componentSemanticsMatch?: boolean | null;
  };
  solidWorksResult: Record<string, unknown>;
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
  xyToleranceMeters?: number | null;
  thetaToleranceDegrees?: number | null;
  message?: string;
};

export type ReplayValidation = {
  success?: boolean;
  message?: string;
  maxXyError?: number | null;
  maxThetaErrorDegrees?: number | null;
  xyToleranceMeters?: number | null;
  thetaToleranceDegrees?: number | null;
  captureStatus?: string;
  captureMessage?: string;
  captureOutputPath?: string;
  components?: ReplayValidationComponent[];
};

export type DiscoveredComponent = {
  componentName: string;
  displayName: string;
  filePath: string;
  hierarchyPath: string;
  depth: number;
  isAssembly: boolean;
  isPart: boolean;
  isSuppressed: boolean;
  isHidden: boolean;
  transform?: number[] | null;
  translation?: number[] | null;
  xAxis?: number[] | null;
  yAxis?: number[] | null;
  zAxis?: number[] | null;
  defaultBottomFaceName: string;
};

export type DiscoveryResult = {
  success: boolean;
  message: string;
  sourceAssemblyPath?: string | null;
  scope: string;
  includeParts: boolean;
  includeSuppressed: boolean;
  componentCount: number;
  components: DiscoveredComponent[];
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

export async function getFaceEndpointCatalog(catalogPath?: string): Promise<FaceEndpointCatalogView> {
  const suffix = catalogPath ? `?catalogPath=${encodeURIComponent(catalogPath)}` : "";
  return request<FaceEndpointCatalogView>(`/api/demo/mate-face-catalog${suffix}`);
}

export async function highlightFaceEndpoint(
  endpointId: string,
  catalogPath?: string,
  zoomToSelection = true
): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/mate-face-catalog/highlight", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ endpointId, catalogPath: catalogPath || null, zoomToSelection })
  });
}

export async function previewFaceMatePatch(options: {
  faceAEndpointId: string;
  faceBEndpointId: string;
  mateType: number;
  mateName: string;
  alignment: number;
  distanceMeters?: number | null;
  angleDegrees?: number | null;
  catalogPath?: string;
}): Promise<FaceMatePatchPreview> {
  return request<FaceMatePatchPreview>("/api/demo/mate-face-catalog/patch-preview", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function applyFaceMatePatch(options: {
  faceAEndpointId: string;
  faceBEndpointId: string;
  mateType: number;
  mateName: string;
  alignment: number;
  distanceMeters?: number | null;
  angleDegrees?: number | null;
  catalogPath?: string;
  sourceGraphPath?: string;
  previewDigest: string;
  outputAssemblyPath: string;
  confirmed: boolean;
}): Promise<FaceMatePatchApplyResult> {
  return request<FaceMatePatchApplyResult>("/api/demo/mate-face-catalog/apply", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function solveProjectCasePreview(caseId = "project02"): Promise<ProjectCasePreview> {
  return request<ProjectCasePreview>(`/api/demo/cases/${encodeURIComponent(caseId)}/solve-preview`, {
    method: "POST"
  });
}

export async function getProjectCasePreview(caseId = "project02"): Promise<ProjectCasePreview> {
  return request<ProjectCasePreview>(`/api/demo/cases/${encodeURIComponent(caseId)}/preview`);
}

export async function getProject02DependencyAblation(): Promise<Project02DependencyAblationBundle> {
  return request<Project02DependencyAblationBundle>("/api/demo/cases/project02/dependency-ablation");
}

export async function recommendProjectCaseModules(
  requirement: string,
  caseId = "project02"
): Promise<ProjectModuleRecommendationResult> {
  return request<ProjectModuleRecommendationResult>(`/api/demo/cases/${encodeURIComponent(caseId)}/recommend-modules`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ requirement })
  });
}

export async function confirmProjectCaseModules(
  requirement: string,
  selectedModuleCodes: string[],
  caseId = "project02"
): Promise<ProjectModuleConfirmationResult> {
  return request<ProjectModuleConfirmationResult>(`/api/demo/cases/${encodeURIComponent(caseId)}/confirm-modules`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ requirement, selectedModuleCodes })
  });
}

export async function approveProjectCasePreview(
  caseId: string,
  solutionRank: number,
  reviewerNote = ""
): Promise<LayoutVerificationPlan> {
  return request<LayoutVerificationPlan>(`/api/demo/cases/${encodeURIComponent(caseId)}/approve-preview`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ solutionRank, reviewerNote })
  });
}

export async function getProjectCaseVerificationPlan(
  caseId = "project02"
): Promise<LayoutVerificationPlan> {
  return request<LayoutVerificationPlan>(`/api/demo/cases/${encodeURIComponent(caseId)}/verification-plan`);
}

export async function getProjectMigrationReadiness(
  caseId = "project01"
): Promise<ProjectMigrationReadiness> {
  return request<ProjectMigrationReadiness>(`/api/demo/cases/${encodeURIComponent(caseId)}/migration-readiness`);
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

export async function discoverComponents(
  sourceAssemblyPath: string,
  scope = "topLevelOnly",
  includeParts = false,
  includeSuppressed = false,
  defaultBottomFaceName = "底面"
): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/discover-components", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      sourceAssemblyPath: sourceAssemblyPath || null,
      scope,
      includeParts,
      includeSuppressed,
      defaultBottomFaceName
    })
  });
}

export async function syncDiscoveredComponents(components: DiscoveredComponent[]): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/sync-discovered-components", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ components })
  });
}

export async function captureProjectLayout(
  sourceAssemblyPath: string,
  baseComponentName: string | null,
  outputPath: string,
  projectConfigPath: string
): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/capture-project-layout", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      sourceAssemblyPath: sourceAssemblyPath || null,
      baseComponentName,
      outputPath: outputPath || null,
      projectConfigPath: projectConfigPath || null
    })
  });
}

export async function generateConstraintLayout(options: {
  sourceAssemblyPath: string;
  baseComponentName: string | null;
  outputPath: string;
  roleOverrides: Record<string, ConstraintRole>;
  marginRatios: number[];
  minimumClearanceMeters: number;
  glueDistanceMeters: number;
  allowRotation: boolean;
  portalPassThrough: Record<string, string[]>;
  portalOpeningWidthRatio: number;
  portalOpeningHeightRatio: number;
  moduleSemantics: Record<string, ModuleSemanticInput>;
  processConstraints: Array<Record<string, unknown>>;
  autoGenerateProcessConstraints: boolean;
  provisionalComponents: ProvisionalComponentInput[];
  syncLayout: boolean;
}): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/generate-constraint-layout", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
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

export async function applyCapturedLayout(xyToleranceMeters?: number, thetaToleranceDegrees?: number): Promise<OperationResult> {
  return request<OperationResult>("/api/demo/apply-captured-layout", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ xyToleranceMeters, thetaToleranceDegrees })
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
