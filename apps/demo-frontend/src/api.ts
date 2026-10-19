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
    combinedServiceModule?: {
      cadId?: string;
      functionCount: number;
      reachTargetCount: number;
      functions: string[];
    };
    calibrationModule?: {
      cadId?: string;
      reachTargetCount: number;
    };
    moduleSummary?: Record<string, unknown>;
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
    vendorConfirmed?: boolean;
    allRequiredTargetsInsideCommonReach?: boolean;
    requiredTargetCount?: number;
    minimumTargetBoundaryMarginMeters?: number;
    commonReachInstallationFrameMeters?: {
      minU: number;
      maxU: number;
      minV: number;
      maxV: number;
      widthU: number;
      widthV: number;
    };
    commonPlanarReachInstallationMeters?: {
      minU: number;
      maxU: number;
      minV: number;
      maxV: number;
    };
    valvePair?: {
      spacingMeters: number;
      spacingAlongFlowMeters: number;
      spacingAlongTransverseMeters: number;
    };
    dualValvePitch?: {
      meters: number;
      method?: string;
      engineeringConfirmed?: boolean;
    };
    targetCount?: number;
    allTargetsInsideCommonPlanarReach?: boolean;
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

export type SemanticPortEndpointBinding = {
  role: string;
  endpointId: string;
  geometryClass?: string | null;
  leafHierarchyPath?: string | null;
  faceIndex?: number | null;
  faceAreaSquareMeters?: number | null;
  faceCenterLocal?: number[] | null;
  faceNormalLocal?: number[] | null;
  recoveryConfidence?: string | null;
};

export type SemanticPortView = {
  portId: string;
  displayName: string;
  description?: string | null;
  moduleToken: string;
  moduleHierarchyPath: string;
  category: "mechanical" | "functional" | "spatial";
  interfaceType: string;
  status: string;
  evidence?: string | null;
  endpointBindings: SemanticPortEndpointBinding[];
};

export type SemanticConnectionRequest = {
  schemaVersion: string;
  connectionId?: string;
  intent?: string;
  portAId?: string;
  portBId?: string;
  templateId?: string;
  planId?: string;
  connections?: Array<{
    connectionId: string;
    portAId: string;
    portBId: string;
    templateId: string;
    parameters?: Record<string, unknown>;
  }>;
  baseModuleToken?: string;
  initialPlacementMode?: string;
  componentToAdd?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
};

export type SemanticPortCatalogView = {
  success: boolean;
  projectId: string;
  semanticCatalogPath: string;
  endpointCatalogPath: string;
  sourceGraphPath: string;
  demoRequestPath: string;
  ports: SemanticPortView[];
  connectionTemplates: Array<Record<string, unknown>>;
  demoRequest: SemanticConnectionRequest;
  defaultNaturalLanguageRequirement: string;
  latestClosurePath?: string | null;
  latestClosure?: {
    success: boolean;
    status: string;
    cacheReused: boolean;
    instancesByModuleToken: Record<string, string>;
    timing?: { durationSeconds?: number };
    releaseGate?: {
      releaseAllowed: boolean;
      status: string;
      interferenceSummary?: {
        completedExactPairCount?: number;
        newInterferenceCount?: number;
      };
    };
  } | null;
  validation: { success: boolean; portCount: number; templateCount: number; warnings: string[] };
  message: string;
};

export type SemanticAssemblyIntent = {
  schemaVersion: "semantic-assembly-intent/v1";
  projectId: string;
  operation: "add_module";
  sourceRequirement: string;
  moduleToAdd: string;
  mentionedModules: string[];
  fixedContextModules: string[];
  componentSolvingStates: Record<string, "rigid" | "flexible">;
  relationships: Array<{
    relationshipId: string;
    sourceModule: string;
    targetModule: string;
    purpose: "installation" | "spacing";
    applicationMode: "driving" | "validate_only";
    parameters?: { distanceMillimeters?: number };
    evidence?: string;
  }>;
  outputPolicy: { modifyPrototype: boolean; createIndependentAssembly: boolean };
  parser: { mode: string; geometricEntitiesGenerated: boolean; warnings: string[] };
};

export type SemanticIntentResolution = {
  success: boolean;
  assemblyPlan: SemanticConnectionRequest;
  selectionAudit: Array<{
    relationshipId: string;
    purpose: string;
    selected: {
      portAId: string;
      portBId: string;
      templateId: string;
      score: number;
      reason: string;
    };
    candidates: Array<Record<string, unknown>>;
  }>;
  solvingStateChecks: Array<{
    moduleToken: string;
    requested: string;
    catalogState?: string | null;
    matched: boolean;
  }>;
  blockingIssues: string[];
  requiresHumanConfirmation: boolean;
  message: string;
};

export type SemanticConnectionPreview = {
  success: boolean;
  message: string;
  semanticCatalogPath: string;
  endpointCatalogPath: string;
  sourceGraphPath: string;
  connectionRequest: SemanticConnectionRequest;
  selectedPorts: SemanticPortView[];
  patch: Record<string, unknown>;
  effectiveSummary: {
    connectionId?: string;
    portAId?: string;
    portBId?: string;
    planId?: string;
    connectionCount?: number;
    addedComponent?: string | null;
    generatedMateCount: number;
    generatedMateNames?: string[];
    validationRelationCount?: number;
    cadVerifiedFullyConstrained?: boolean;
    effectiveModuleCount: number;
    effectiveMateCount: number;
    executionMode: string;
    constraintEffect?: {
      estimatedRemovedScalarDof?: number;
      fullyLocatesAddedComponent?: boolean;
      assessment?: string;
    };
  };
  previewDigest: string;
  suggestedOutputAssemblyPath: string;
  executionBoundary: {
    mode: string;
    modifiesPrototype: boolean;
    preservesExistingParentContext?: boolean;
    fullyLocatesAddedComponent: boolean;
    validationRelationCount?: number;
  };
  requirement?: string;
  parsedIntent?: SemanticAssemblyIntent;
  intentResolution?: SemanticIntentResolution;
};

export type SemanticConnectionApplyResult = {
  status: "ok" | "error";
  success: boolean;
  message: string;
  executionMode: string;
  artifacts: {
    outputAssemblyPath: string;
    requestPath: string;
    patchPath: string;
    effectiveGraphPath: string;
    resultPath: string;
  };
  solidWorksResult: Record<string, unknown>;
  validationSummary?: {
    relationCount: number;
    passedCount: number;
    allPassed: boolean;
    results: Array<{
      RelationName?: string;
      MeasuredDistanceMeters?: number;
      ExpectedDistanceMeters?: number;
      ToleranceMeters?: number;
      Passed?: boolean;
    }>;
  };
  releaseGate?: {
    status: string;
    releaseAllowed: boolean;
    message: string;
  };
};

export type GlobalModuleDefinition = {
  moduleDefinitionId: string;
  displayName: string;
  category: string;
  componentNames: string[];
  aliases: string[];
  projectAliases: Array<{
    projectId: string;
    moduleToken: string;
    instanceCount: number;
    isBaseModule: boolean;
  }>;
  portIds: string[];
  portCoverage: "none" | "partial" | "portable_complete";
};

export type GlobalModuleCatalog = {
  schemaVersion: "global-module-catalog/v1";
  catalogDigest: string;
  summary: {
    loadedProjectCount: number;
    missingProjectCount: number;
    moduleDefinitionCount: number;
    semanticPortCount: number;
    portablePortCount: number;
    connectionTemplateCount: number;
    compatibilityCount: number;
    blockerCount: number;
  };
  collisionPolicy: { enabled: false; status: string; statement: string };
  moduleDefinitions: GlobalModuleDefinition[];
  blockers: Array<Record<string, unknown>>;
};

export type GlobalModuleSearchResult = {
  score: number;
  matchedTerms: string[];
  moduleDefinitionId: string;
  displayName: string;
  category: string;
  componentNames: string[];
  projectAliases: GlobalModuleDefinition["projectAliases"];
  portCoverage: string;
  portablePortCount: number;
};

export type GlobalAssemblyContext = {
  schemaVersion: "global-assembly-context/v1";
  contextId: string;
  displayName: string;
  catalogDigest: string;
  revision: number;
  relationReleaseBinding?: {
    releaseId: string;
    releaseManifestPath?: string;
    authorizedDrivingTemplateIds?: string[];
  } | null;
  instances: Array<{
    instanceId: string;
    moduleDefinitionId: string;
    displayName: string;
    placementStatus: string;
  }>;
  connections: Array<Record<string, unknown>>;
  history?: Array<{
    revision: number;
    requirement?: string | null;
    operation?: string | null;
    timestamp?: string | null;
    portableReleaseTransition?: {
      transitionKind?: "first_bind" | "expand" | null;
      sourceReleaseId?: string | null;
      releaseId?: string | null;
      replacementCount?: number;
    } | null;
  }>;
  collisionAssessment: { status: string; reason: string };
  contextDigest: string;
};

export type GlobalAssemblyConversation = {
  success: boolean;
  schemaVersion: "assembly-conversation/v1";
  contextId: string;
  currentContextRevision: number;
  currentContextDigest: string;
  turnCount: number;
  continuationReady: boolean;
  ledgerPath: string;
  latestSuccessfulDemo?: {
    jobId: string;
    projectId: string;
    validationProfile?: "demo" | "generic-cad-transaction-manifest-v1";
    assemblyStatus?: string;
    collisionStatus?: "not_evaluated" | "passed" | "rejected";
    contextRevision: number;
    contextDigest: string;
    assemblyPath: string;
    committedAt?: string | null;
  } | null;
  turns: Array<{
    turnId: string;
    contextRevision: number;
    requirement: string;
    previewDigest: string;
    contextDigest: string;
    operation?: string | null;
    moduleDefinitionId?: string | null;
    instanceId?: string | null;
    connectionId?: string | null;
    graphStatus: "committed";
    recordedAt: string;
    jobs: Array<{
      jobId: string;
      projectId: string;
      validationProfile: "demo" | "engineering" | "generic-cad-transaction-manifest-v1";
      status: string;
      assemblyStatus: string;
      collisionStatus: string;
      sourceJobId?: string | null;
      bindingRevisionSource?: "explicit_plan" | "exact_context_digest_backfill";
      demoCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
      lookupError?: string;
    }>;
    cadEdits?: Array<Record<string, unknown>>;
  }>;
};

export type TemporarySemanticPort = {
  portId: string;
  displayName: string;
  aliases: string[];
  moduleInstanceId: string;
  moduleDefinitionId: string;
  moduleToken: string;
  moduleHierarchyPath?: string | null;
  interfaceType: string;
  status: "user_selected_provisional";
  endpointBindings: Array<{ role: string; endpointId: string }>;
};

export type TemporaryConnectionPreview = {
  schemaVersion: "temporary-connection-preview/v1";
  contextId: string;
  contextRevision: number;
  requirement: string;
  status: "ready" | "blocked";
  selectedPorts: TemporarySemanticPort[];
  endpointIds: string[];
  mateDraft: {
    mateType: number | null;
    mateLabel: string | null;
    distanceMeters?: number | null;
    angleDegrees?: number | null;
    alignment: number;
  };
  blockers: Array<{ code: string; detail: string }>;
  endpointCatalogPath: string;
  previewDigest: string;
  executionBoundary: {
    solidWorksModified: false;
    readyForCurrentCheckpointGraphAdapter: boolean;
    statement: string;
  };
};

export type CheckpointMateGraphBinding = {
  schemaVersion: "checkpoint-mate-graph-binding/v1";
  contextId: string;
  contextRevision: number;
  contextDigest: string;
  demoJobId: string;
  projectId: string;
  checkpointAssembly: { path: string; sha256: string; sizeBytes: number };
  mateGraph: {
    path: string;
    sha256: string;
    schemaVersion: string;
    moduleCount: number;
    mateCount: number;
  };
  bindingDigest: string;
};

export type CheckpointMateGraphExport = {
  success: boolean;
  status: "confirmation_required" | "cached_bound_graph" | "bound";
  executionStarted: boolean;
  solidWorksAssemblyModified: false;
  spec: {
    demoJobId: string;
    projectId: string;
    moduleTokens: string[];
    outputGraphPath: string;
    bindingPath: string;
    checkpointAssembly: { path: string; sha256: string };
  };
  binding?: CheckpointMateGraphBinding;
  bindingPath?: string;
};

export type CheckpointTemporaryMatePreview = {
  schemaVersion: "checkpoint-temporary-mate-preview/v1";
  status:
    | "ready_for_explicit_direct_mate_edit_confirmation"
    | "ready_for_explicit_remate_confirmation"
    | "ready_for_explicit_context_insert_confirmation";
  demoJobId: string;
  checkpointAssemblyPath: string;
  targetModuleToken: string;
  preservedExistingMateNames: string[];
  newMateName: string;
  constraintSafety: {
    sourceDrivingMateCount: number;
    usesCheckpointPoseAnchor: boolean;
    executionStrategy: "target_reinsert_with_checkpoint_pose_anchor" | "target_remate_with_preserved_source_mates";
    claimBoundary: string;
  };
  compiledPreviewDigest: string;
  artifacts?: {
    patchPath: string;
    effectiveGraphPath: string;
    compiledPreviewPath: string;
  };
  executionBoundary: {
    solidWorksModified: false;
    nextTool: string;
    requiresExplicitConfirmation: true;
  };
};

export type HistoricalCheckpointAssessment = {
  schemaVersion: "historical-demo-checkpoint-import/v1";
  status: "ready_for_import" | "blocked";
  contextId: string;
  contextRevision: number;
  contextDigest: string;
  jobId: string;
  projectId: string;
  checkpointAssemblyIdentity: { path: string; sizeBytes: number; sha256: string };
  componentInventoryIdentity: { path: string; sizeBytes: number; sha256: string };
  expectedModuleTokenCounts: Record<string, number>;
  observedModuleTokenCounts: Record<string, number>;
  expectedInstanceCount: number;
  observedComponentCount: number;
  blockers: Array<{ code: string; detail?: unknown }>;
  warnings: Array<{ code: string; detail?: unknown }>;
  assessmentDigest: string;
  executionBoundary: {
    solidWorksStarted: false;
    solidWorksAssemblyModified: false;
    jobFileModified: false;
    effectAfterConfirmation: string;
  };
};

export type HistoricalCheckpointImportResult = {
  success: boolean;
  status: "imported";
  jobId: string;
  contextId: string;
  contextRevision: number;
  assessmentDigest: string;
  attestationPath: string;
  checkpointAssemblyIdentity: { path: string; sizeBytes: number; sha256: string };
  solidWorksStarted: false;
  solidWorksAssemblyModified: false;
  jobFileModified: false;
  conversation: GlobalAssemblyConversation;
};

export type GlobalAssemblyCommandPreview = {
  schemaVersion: "global-assembly-command-preview/v1";
  status: "ready" | "needs_confirmation" | "blocked";
  requirement: string;
  resolution: string;
  previewDigest: string;
  selectedModuleDefinitionId?: string | null;
  moduleAlternatives: Array<{
    moduleDefinitionId: string;
    displayName: string;
    matchedTerm: string;
  }>;
  connectionCandidates: Array<{
    newSide: "A" | "B";
    newPortId: string;
    existingPortId: string;
    existingInstanceId: string;
    globalTemplateId: string;
    purpose: string;
    portable: boolean;
  }>;
  proposedPatch?: Record<string, unknown> | null;
  portableReleaseTransition?: {
    transitionKind: "first_bind" | "expand";
    discoveryMode?:
      | "active_catalog_rebinding"
      | "immutable_release_port_discovery"
      | "bound_release_expansion";
    sourceCatalogDigest: string;
    sourceReleaseId?: string | null;
    sourceRelationReleaseBinding?: {
      releaseId: string;
      releaseManifestPath: string;
      authorizedDrivingTemplateIds: string[];
    } | null;
    releaseId: string;
    catalogDigest: string;
    relationReleaseBinding: {
      releaseId: string;
      releaseManifestPath: string;
      authorizedDrivingTemplateIds: string[];
    };
    replacements: Array<{
      connectionId: string;
      sourceTemplateId: string | null;
      portableTemplateId: string;
      orientation: "same" | "swapped";
      mateStepCount: number;
    }>;
    upgradedConnections?: Array<Record<string, unknown>>;
    selectionPolicy: string;
    solidWorksExecuted: false;
    requiresExplicitConfirmation: true;
  } | null;
  engineeringFallbacks?: Array<{
    kind: "physical_adapter_required" | "mechanical_interface_review_required";
    sourceModule: string;
    sourceModuleDefinitionId: string;
    nativeSlotModule: string;
    nativeSlotModuleDefinitionId: string;
    directCombinationAllowed: false;
    cadLaunchDecision: "fail_closed_before_cad";
    engineeringDisposition: {
      classification: string;
      recommendedEngineeringAction: string;
      explanation: string;
      knownLocatingDifferences: Array<{
        roles: string[];
        sourceDistanceMeters: number;
        targetDistanceMeters: number;
        absoluteDifferenceMeters: number;
      }>;
      requiredNextEvidence: string[];
    };
    userFailureExplanation?: {
      summary?: string;
      explanation?: string;
      suggestedActions?: string[];
    } | null;
  }>;
  fallbackPolicy?: {
    automaticFallbackExecutionAllowed: false;
    requiresEngineerSelection: true;
    solidWorksExecuted: false;
    statement: string;
  };
  blockers: Array<{ code: string; detail: string }>;
  collisionAssessment: { status: "not_evaluated"; reason: string };
  cadExecution: { status: "not_executed"; statement: string };
};

export type GlobalAssemblyExecutionManifest = {
  schemaVersion: "global-assembly-execution-manifest/v1";
  contextId: string;
  status: "ready_for_project_adapter" | "blocked";
  stepCount: number;
  steps: Array<{
    order: number;
    connectionId: string;
    status: string;
    targetInstanceId?: string | null;
    semanticCatalogPath?: string | null;
    sourceGraphCandidates: string[];
    semanticConnectionRequest: {
      portAId?: string | null;
      portBId?: string | null;
      templateId?: string | null;
    };
    blockers: Array<{ code: string; detail: string }>;
  }>;
  blockers: Array<{ connectionId: string; code: string; detail: string }>;
  executionBoundary: {
    solidWorksExecuted: false;
    collisionGateExecuted: false;
    statement: string;
  };
};

export type GlobalProjectAdapterPlan = {
  schemaVersion: "global-project-adapter-plan/v1";
  contextId: string;
  contextRevision: number;
  projectId?: string | null;
  assemblyMode: "mate_driven_port_assembly" | "prototype_pose_dependency";
  prototypePoseDependency: boolean;
  portable: boolean;
  poseDependencyAudit?: {
    assemblyMode: string;
    connectionCount: number;
    mateDrivenReadyCount: number;
    prototypePoseRequiredCount: number;
    portable: boolean;
    statement: string;
    connections: Array<{
      connectionId: string;
      globalTemplateId: string;
      status: "mate_driven_ready" | "prototype_pose_required" | "port_completeness_unverified" | "template_missing";
      fullyLocatesAddedComponent?: boolean | string | null;
      remainingDof?: string | null;
      residualDofPolicy?: string | null;
      prototypePoseRequired: boolean;
    }>;
  } | null;
  status: "ready_for_durable_job" | "blocked";
  safeToCreateDurableJob: boolean;
  stepCount: number;
  sequenceAssessment?: {
    status: "accepted" | "blocked";
    kind: "exact" | "validated_prefix" | "sequence_mismatch";
    actual: string[];
    expected: string[];
    nextExpectedTokens: string[];
    missingPredecessors: string[];
  } | null;
  runnerBinding?: { runnerId?: string | null; solidWorksStarted: false } | null;
  seedCheckpoint?: {
    moduleToken: string;
    assemblyPath: string;
    evidencePath: string;
  } | null;
  steps: Array<{
    stepId: string;
    moduleToken: string;
    sourceCheckpointPolicy: string;
    runnerId?: string | null;
  }>;
  blockers: Array<{
    code: string;
    detail: string;
    missingPredecessors?: string[];
  }>;
  executionBoundary: {
    solidWorksExecuted: false;
    collisionGateExecuted: false;
    collisionPolicy: string;
    statement?: string;
  };
};

export type GlobalCadTransactionManifest = {
  schemaVersion: "global-cad-transaction-manifest/v1";
  contextId: string;
  contextRevision?: number | null;
  status: "ready_for_generic_executor_implementation" | "blocked";
  planningMode: "project_independent_semantic_graph";
  projectSequenceRequired: false;
  packetCount: number;
  manifestDigest: string;
  relationReleaseBinding?: { releaseId?: string | null } | null;
  packets: Array<{
    packetId: string;
    order: number;
    status: string;
    operation: string;
    executionStrategy: string;
    targetInstanceId?: string | null;
    blockers: Array<{ code: string; detail?: string }>;
  }>;
  blockers: Array<{ packetId?: string; code: string; detail?: string }>;
};

export type GlobalPortableReleaseRecommendation = {
  schemaVersion: "portable-relation-release-recommendation/v1";
  status: "ready" | "blocked";
  sourceContextId: string;
  sourceContextRevision: number;
  sourceContextDigest: string;
  recommendation: null | {
    releaseId: string;
    releaseVersion: number;
    releaseManifestPath: string;
    authorizedTemplateCount: number;
    replacements: Array<{
      connectionId: string;
      sourceTemplateId: string;
      portableTemplateId: string;
      orientation: "same" | "swapped";
      mateStepCount: number;
    }>;
  };
  alternatives: Array<{
    releaseId: string;
    releaseVersion: number;
    releaseManifestPath: string;
    authorizedTemplateCount: number;
    replacements: Array<{
      connectionId: string;
      sourceTemplateId: string;
      portableTemplateId: string;
      orientation: "same" | "swapped";
      mateStepCount: number;
    }>;
  }>;
  blockers: Array<{ code: string; detail?: string }>;
  selectionPolicy: string;
  previewDigest: string;
};

type GlobalCadManifestJobStatus = {
  jobId: string;
  projectId: string;
  status: OrderedAssemblyJob["status"];
  assemblyStatus?: string;
  collisionStatus?: "not_evaluated" | "passed" | "rejected";
  progress: {
    completedSteps: number;
    totalSteps: number;
    currentStepId?: string | null;
    nextStepId?: string | null;
  };
  pauseRequested: boolean;
  steps: OrderedAssemblyJobStep[];
  lastCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
  failure?: {
    reason?: string | null;
    rollback?: OrderedAssemblyJob["rollback"];
  } | null;
  createdAt: string;
  updatedAt: string;
  startRequestedAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  executionDurationSeconds?: number;
  commandAudit?: OrderedAssemblyJob["commandAudit"];
  timingReport?: OrderedAssemblyJob["timingReport"];
  userSummary?: OrderedAssemblyJob["userSummary"];
};

function normalizeGlobalCadManifestJob(
  value: GlobalCadManifestJobStatus,
  markStartRequested = false
): OrderedAssemblyJob {
  return {
    jobId: value.jobId,
    projectId: value.projectId,
    executionMode: "generic_cad_manifest",
    validationProfile: "demo",
    assemblyStatus: value.assemblyStatus,
    collisionStatus: value.collisionStatus,
    status: value.status,
    cancelRequested: false,
    pauseRequested: value.pauseRequested,
    createdAt: value.createdAt,
    updatedAt: value.updatedAt,
    startedAt: value.startedAt,
    startRequestedAt:
      markStartRequested || value.startRequestedAt || value.startedAt
        ? (value.startRequestedAt ?? value.startedAt ?? new Date().toISOString())
        : null,
    completedAt: value.completedAt,
    executionDurationSeconds: value.executionDurationSeconds,
    commandAudit: value.commandAudit,
    timingReport: value.timingReport,
    userSummary: value.userSummary,
    steps: value.steps,
    lastCommittedCheckpoint: value.lastCheckpoint,
    demoCheckpoint: value.lastCheckpoint,
    rollback: value.failure?.rollback ?? null,
    error: value.failure?.reason ?? null
  };
}

export type OrderedAssemblyStep = {
  stepId: string;
  order: number;
  moduleToken: string;
  moduleLabel: string;
  sourceText: string;
  availableBefore: string[];
  requiredModules: string[];
  missingRequiredModules: string[];
  dependenciesSatisfied: boolean;
  placementKind: string;
  ruleSummary: string;
  acceptanceChecks: string[];
  implementationStatus:
    | "single_module_cad_validated"
    | "top_level_cad_validated_release_blocked"
    | "preview_only";
  missingImplementation?: string | null;
  engineeringLimitations?: string[];
  cadExecutableNow: boolean;
  status: "blocked_by_order" | "cad_validated_single_step" | "preview_ready_implementation_missing";
};

export type OrderedAssemblyPreview = {
  success: boolean;
  message: string;
  audit: {
    runId: string;
    startedAt: string;
    completedAt: string;
    timingSeconds: { parseCommand: number; buildPlan: number; total: number };
  };
  intent: {
    schemaVersion: string;
    projectId: string;
    projectProfile?: {
      schemaVersion: string;
      profileVersion: string;
      profileDigest: string;
      profilePath: string;
    };
    intentDigest?: string;
    sourceRequirement: string;
    initialContextModules: string[];
    steps: Array<Pick<OrderedAssemblyStep, "order" | "moduleToken" | "moduleLabel" | "sourceText">>;
    parser: { mode: string; geometricEntitiesGenerated: boolean; warnings: string[] };
  };
  plan: {
    schemaVersion: string;
    intentDigest?: string;
    planDigest?: string;
    steps: OrderedAssemblyStep[];
    summary: {
      stepCount: number;
      orderValid: boolean;
      previewReady: boolean;
      cadExecutableStepCount: number;
      allStepsCadExecutableNow: boolean;
      dynamicProcessRequestAccepted?: boolean;
      finalPlannedModuleTokens: string[];
      orderBlockerCount: number;
      missingImplementationCount: number;
    };
    orderBlockers: string[];
    missingImplementations: Array<{ moduleToken: string; reason: string }>;
    dynamicProcessGate?: {
      requested: boolean;
      accepted: boolean;
      status: string;
      scope: string;
      message: string;
      requestedAngleDegrees?: number;
      startAngleDegrees?: number | null;
      targetAngleDegrees?: number;
      continuousPathVerified?: boolean;
      firstObservedCollisionBracketDegrees?: number[];
      knownPairFirstObservedCollisionBracketDegrees?: number[];
      rejectedSampledAnglesDegrees?: number[];
      newLeafSourcePairs?: Array<{
        leafSourcePair: string[];
        count: number;
      }>;
      evidencePath?: string;
    } | null;
    executionBoundary: {
      mode: string;
      modifiesPrototype: boolean;
      safeToStartCad: boolean;
      reason: string;
    };
  };
  contracts?: {
    intent: { schemaVersion: string; intentDigest: string };
    plan: { schemaVersion: string; intentDigest: string; planDigest: string };
  };
};

export type OrderedAssemblyClosure = {
  available: boolean;
  status: string;
  allCadStepsPassed?: boolean;
  finalAssemblyPath?: string;
  sequence?: string[];
  interferenceGate?: {
    expectedTopLevelPairCount?: number;
    checkedPairCount?: number;
    pairCoverageComplete?: boolean;
    acceptedPairCount?: number;
    rejectedPairCount?: number;
  };
  blockingIssues?: Array<{
    id: string;
    scope: string[];
    description: string;
    requiredNextStep: string;
  }>;
  knownLimitations?: Array<{
    id: string;
    scope: string[];
    description: string;
    requiredNextStep: string;
  }>;
  releaseDecision?: {
    topLevelStaticAssemblyBuilt?: boolean;
    zeroNewInterferenceForCompletedChecks?: boolean;
    staticSevenModuleDemoReleaseAllowed?: boolean;
    staticTenObjectDemoReleaseAllowed?: boolean;
    productionReleaseAllowed?: boolean;
    reason?: string;
  };
  timingSeconds?: { cadStagesTotal?: number; conditionalBrepTotal?: number };
  evidencePath: string;
};

export type OrderedAssemblyValidatedRun = {
  success: boolean;
  executionMode: "validated_artifact_replay";
  cadExecutedThisRequest: false;
  validatedCadArtifactReused: true;
  message: string;
  requestedSequence: string[];
  finalAssemblyPath: string;
  interferenceGate: {
    checkedPairCount?: number;
    acceptedPairCount?: number;
  };
  releaseDecision: {
    staticSevenModuleDemoReleaseAllowed?: boolean;
    productionReleaseAllowed?: boolean;
    reason?: string;
  };
  audit: {
    runId: string;
    durationSeconds: number;
    runEvidencePath: string;
  };
};

export type OrderedAssemblyPipelineAudit = {
  schemaVersion: string;
  generatedAt: string;
  projectId: string;
  projectProfile: { profileVersion: string; profileDigest: string; profilePath: string };
  checks: Array<{ id: string; passed: boolean; evidence: unknown; message: string }>;
  blockingIssues: string[];
  warnings: string[];
  readyForValidatedArtifactReplay: boolean;
  readyForLiveCadExecution: boolean;
  finalAssemblyPath: string;
  closureEvidencePath: string;
  timingSeconds: { total: number };
};

export type OrderedAssemblyDependencyAudit = {
  schemaVersion: string;
  generatedAt: string;
  projectId: string;
  prototypeDependentModuleCount: number;
  productionAuthorityAcceptedModuleCount: number;
  staticDemoProfileAccepted: boolean;
  productionProfileAccepted: boolean;
  productionBlockers: Array<{
    moduleToken: string;
    sourceConfidence: string;
    requiredReplacement: string;
    pendingParameterAuthorityRequirementIds?: string[];
  }>;
  parameterAuthorityAudit?: {
    registry: { registryVersion: string; registryDigest: string; registryPath: string };
    requirementCount: number;
    productionAcceptedRequirementCount: number;
    staticDemoParameterEvidenceAccepted: boolean;
    productionParameterAuthorityAccepted: boolean;
    productionBlockers: Array<{
      requirementId: string;
      ownerModules: string[];
      nextAction: string;
    }>;
  } | null;
  productionDynamicRequirements: string[];
};

export type OrderedAssemblyReleaseContract = {
  schemaVersion: string;
  generatedAt: string;
  projectId: string;
  profile: { version: string; digest: string; path: string };
  static: {
    allowed: boolean;
    closureExists: boolean;
    closureSuccess: boolean;
    evidencePath: string;
  };
  liveCad: { allowed: boolean; explicitlyReleasedByProfile: boolean };
  dynamic: {
    configured: boolean;
    evidenceExists: boolean;
    schemaMatches: boolean;
    productionReady: boolean;
    commandGateEnabled: boolean;
    status: string;
    continuousPathVerified: boolean;
    verifiedSafeSampledAnglesDegrees: number[];
    rejectedSampledAnglesDegrees: number[];
    firstObservedCollisionBracketDegrees?: number[] | null;
    knownPairFirstContactRefinement?: {
      firstObservedCollisionBracketDegrees?: number[];
      doesNotProveWholeMachineContinuousSafety?: boolean;
    } | null;
    evidencePath?: string | null;
  };
  parameterAuthority: {
    confidenceCounts: Record<string, number>;
    prototypeOrTemporaryModuleCount: number;
    productionAuthorityClosed: boolean;
  };
  release: {
    staticDemoAllowed: boolean;
    liveCadAllowed: boolean;
    productionAllowed: boolean;
    productionBlockers: string[];
  };
};

export type OrderedAssemblyJobStep = {
  index: number;
  stepId: string;
  moduleToken: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  attemptCount: number;
  attempts?: Array<{
    attempt: number;
    startedAt: string;
    completedAt?: string | null;
    durationSeconds?: number | null;
  }>;
  checkpoint?: {
    assemblyPath: string;
    evidencePath?: string | null;
    committedAt: string;
    validationProfile?: "demo" | "engineering" | "generic-cad-transaction-manifest-v1";
    assemblyStatus?: string;
    collisionStatus?: "not_evaluated" | "passed" | "rejected";
    validationEvidenceKind?: string | null;
  } | null;
  error?: string | null;
  executionDurationSeconds?: number;
};

export type OrderedAssemblyJob = {
  jobId: string;
  projectId: string;
  executionMode: "validated_artifact_replay" | "live_cad" | "generic_cad_manifest";
  validationProfile?: "demo" | "engineering" | "generic-cad-transaction-manifest-v1";
  assemblyStatus?: string;
  collisionStatus?: "not_evaluated" | "passed" | "rejected";
  status: "queued" | "running" | "paused" | "succeeded" | "failed" | "cancelled";
  cancelRequested: boolean;
  pauseRequested: boolean;
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  startRequestedAt?: string | null;
  completedAt?: string | null;
  executionDurationSeconds?: number;
  commandAudit?: {
    status: "complete" | "incomplete" | "unavailable";
    path?: string | null;
    digest?: string | null;
  };
  timingReport?: {
    status: "available" | "pending";
    path?: string | null;
  };
  userSummary?: {
    status: string;
    path?: string | null;
    markdownPath?: string | null;
  };
  steps: OrderedAssemblyJobStep[];
  lastCommittedCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
  demoCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
  engineeringCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
  rollback?: { mode: string; checkpoint?: OrderedAssemblyJobStep["checkpoint"] } | null;
  error?: string | null;
};

export type EngineeringValidationJob = {
  schemaVersion: string;
  validationJobId: string;
  projectId: string;
  sourceJobId: string;
  status: "queued" | "running" | "succeeded" | "rejected" | "failed";
  collisionStatus: "not_evaluated" | "passed" | "rejected";
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  durationSeconds?: number | null;
  sourceAssemblyIdentity: { path: string; sizeBytes: number; sha256: string };
  engineeringCheckpoint?: OrderedAssemblyJobStep["checkpoint"];
  evidencePath?: string | null;
  error?: string | null;
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

export async function getSemanticPortCatalog(): Promise<SemanticPortCatalogView> {
  return request<SemanticPortCatalogView>("/api/demo/semantic-port-catalog");
}

export async function getGlobalModuleCatalog(): Promise<GlobalModuleCatalog> {
  return request<GlobalModuleCatalog>("/api/demo/global-module-catalog");
}

export async function searchGlobalModuleCatalog(
  query: string,
  limit = 20
): Promise<{ success: boolean; resultCount: number; results: GlobalModuleSearchResult[] }> {
  return request(`/api/demo/global-module-catalog/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function createGlobalAssemblyContext(options: {
  contextId: string;
  displayName?: string;
  overwrite?: boolean;
}): Promise<{ success: boolean; contextPath: string; context: GlobalAssemblyContext }> {
  return request("/api/demo/global-assembly-contexts", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function getGlobalAssemblyContext(contextId: string): Promise<GlobalAssemblyContext> {
  return request(`/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}`);
}

export async function getGlobalAssemblyConversation(
  contextId: string
): Promise<GlobalAssemblyConversation> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/conversation`
  );
}

export async function getTemporarySemanticPorts(
  contextId: string
): Promise<{
  success: boolean;
  contextId: string;
  ports: TemporarySemanticPort[];
  registryPath: string;
  endpointCatalogPath: string;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/temporary-ports`
  );
}

export async function captureTemporarySemanticPort(
  contextId: string,
  options: {
    instanceId: string;
    moduleToken: string;
    displayName: string;
    interfaceType: string;
    role?: string;
    aliases?: string[];
  }
): Promise<{
  success: boolean;
  contextId: string;
  port: TemporarySemanticPort;
  registryPath: string;
  endpointCatalogPath: string;
  cadModified: false;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/temporary-ports/capture-selected-face`,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(options) }
  );
}

export async function previewTemporarySemanticConnection(
  contextId: string,
  requirement: string,
  portIds: string[] = []
): Promise<TemporaryConnectionPreview> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/temporary-connections/preview`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ requirement, portIds })
    }
  );
}

export async function exportCheckpointMateGraph(
  contextId: string,
  options: { confirmed: boolean; expectedDemoJobId?: string }
): Promise<CheckpointMateGraphExport> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/checkpoint-mate-graph/export`,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(options) }
  );
}

export async function compileCheckpointTemporaryConnection(
  contextId: string,
  options: {
    temporaryPreview: TemporaryConnectionPreview;
    targetModuleToken: string;
    expectedBindingDigest: string;
  }
): Promise<CheckpointTemporaryMatePreview> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/checkpoint-mate-graph/compile-temporary-connection`,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(options) }
  );
}

export async function previewHistoricalCheckpointImport(
  contextId: string,
  options: { jobId: string; componentInventoryPath?: string }
): Promise<HistoricalCheckpointAssessment> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/historical-checkpoints/preview`,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(options) }
  );
}

export async function importHistoricalCheckpoint(
  contextId: string,
  options: {
    jobId: string;
    componentInventoryPath?: string;
    expectedContextDigest: string;
    assessmentDigest: string;
    confirmed: boolean;
  }
): Promise<HistoricalCheckpointImportResult> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/historical-checkpoints/import`,
    { method: "POST", headers: jsonHeaders, body: JSON.stringify(options) }
  );
}

export async function previewGlobalAssemblyCommand(
  contextId: string,
  options: {
    requirement: string;
    moduleDefinitionId?: string;
    instanceId?: string;
    newPortId?: string;
    existingPortId?: string;
    existingInstanceId?: string;
    globalTemplateId?: string;
  }
): Promise<GlobalAssemblyCommandPreview> {
  return request(`/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/commands/preview`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function applyGlobalAssemblyCommand(
  contextId: string,
  preview: GlobalAssemblyCommandPreview
): Promise<{ success: boolean; contextPath: string; context: GlobalAssemblyContext; message: string }> {
  return request(`/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/commands/apply`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ preview, previewDigest: preview.previewDigest, confirmed: true })
  });
}

export async function undoLatestGlobalAssemblyCommand(
  contextId: string,
  context: GlobalAssemblyContext
): Promise<{
  success: boolean;
  status: "rolled_back";
  contextPath: string;
  snapshotPath: string;
  context: GlobalAssemblyContext;
  rolledBackTurn: GlobalAssemblyConversation["turns"][number];
  message: string;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/commands/undo-latest`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        expectedRevision: context.revision,
        expectedContextDigest: context.contextDigest,
        confirmed: true
      })
    }
  );
}

export async function applyGlobalAssemblyCommandSequence(
  contextId: string,
  commands: Array<{
    requirement: string;
    moduleDefinitionId?: string;
    instanceId?: string;
    newPortId?: string;
    existingPortId?: string;
    existingInstanceId?: string;
    globalTemplateId?: string;
  }>
): Promise<{
  success: boolean;
  status: "committed" | "needs_confirmation" | "blocked";
  contextModified: boolean;
  failedAtOrder?: number;
  turnCount?: number;
  turns: Array<Record<string, unknown>>;
  context?: GlobalAssemblyContext;
  message: string;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/commands/apply-sequence`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ commands, confirmed: true })
    }
  );
}

export async function getGlobalAssemblyExecutionManifest(
  contextId: string
): Promise<GlobalAssemblyExecutionManifest> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/execution-manifest`
  );
}

export async function getGlobalProjectAdapterPlan(
  contextId: string,
  assemblyMode: "mate_driven_port_assembly" | "prototype_pose_dependency" = "mate_driven_port_assembly"
): Promise<GlobalProjectAdapterPlan> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/project-adapter-plan?assemblyMode=${encodeURIComponent(assemblyMode)}`
  );
}

export async function getGlobalCadTransactionManifest(
  contextId: string
): Promise<GlobalCadTransactionManifest> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/cad-transaction-manifest`
  );
}

export async function getGlobalPortableReleaseRecommendation(
  contextId: string
): Promise<GlobalPortableReleaseRecommendation> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/portable-release-recommendation`
  );
}

export async function commitGlobalPortableReleaseUpgrade(
  contextId: string,
  previewDigest: string,
  releaseId: string,
  targetContextId: string
): Promise<{
  success: true;
  sourcePreserved: true;
  solidWorksExecuted: false;
  context: GlobalAssemblyContext;
  evidencePath: string;
  message: string;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/portable-release-upgrades`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        previewDigest,
        releaseId,
        targetContextId,
        confirmed: true
      })
    }
  );
}

export async function prepareGlobalIndependentCadJob(
  contextId: string,
  idempotencyKey?: string,
  packetLimit?: number
): Promise<{
  success: boolean;
  preparedOnly: true;
  executionStarted: false;
  solidWorksStarted: false;
  assemblyMode: "mate_driven_port_assembly";
  portable: true;
  manifestPath: string;
  transactionDagPath: string;
  manifest: GlobalCadTransactionManifest;
  job: OrderedAssemblyJob;
}> {
  const result = await request<{
    success: boolean;
    preparedOnly: true;
    executionStarted: false;
    solidWorksStarted: false;
    assemblyMode: "mate_driven_port_assembly";
    portable: true;
    manifestPath: string;
    transactionDagPath: string;
    manifest: GlobalCadTransactionManifest;
    job: GlobalCadManifestJobStatus;
  }>(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/independent-cad-jobs`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ confirmed: true, idempotencyKey, packetLimit })
    }
  );
  return { ...result, job: normalizeGlobalCadManifestJob(result.job) };
}

export async function startGlobalCadManifestJob(jobId: string): Promise<OrderedAssemblyJob> {
  const result = await request<GlobalCadManifestJobStatus>(
    `/api/demo/global-cad-manifest-jobs/${encodeURIComponent(jobId)}/start`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ timeoutSeconds: 2400 })
    }
  );
  return normalizeGlobalCadManifestJob(result, true);
}

export async function loadGlobalCadManifestJob(jobId: string): Promise<OrderedAssemblyJob> {
  const result = await request<GlobalCadManifestJobStatus>(
    `/api/demo/global-cad-manifest-jobs/${encodeURIComponent(jobId)}`
  );
  return normalizeGlobalCadManifestJob(result);
}

export async function pauseGlobalCadManifestJob(jobId: string): Promise<OrderedAssemblyJob> {
  const result = await request<GlobalCadManifestJobStatus>(
    `/api/demo/global-cad-manifest-jobs/${encodeURIComponent(jobId)}/pause`,
    { method: "POST" }
  );
  return normalizeGlobalCadManifestJob(result, true);
}

export async function resumeGlobalCadManifestJob(jobId: string): Promise<OrderedAssemblyJob> {
  const result = await request<GlobalCadManifestJobStatus>(
    `/api/demo/global-cad-manifest-jobs/${encodeURIComponent(jobId)}/resume`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ timeoutSeconds: 2400 })
    }
  );
  return normalizeGlobalCadManifestJob(result, true);
}

export async function prepareGlobalProjectAdapterJob(
  contextId: string,
  idempotencyKey?: string,
  stepLimit?: number,
  seedJobId?: string,
  validationProfile: "demo" | "engineering" = "demo",
  assemblyMode: "mate_driven_port_assembly" | "prototype_pose_dependency" = "mate_driven_port_assembly"
): Promise<{
  success: boolean;
  preparedOnly: true;
  executionStarted: false;
  solidWorksStarted: false;
  message: string;
  executionScope: {
    kind: "validated_prefix" | "full_chain" | "validated_continuation";
    requestedStepCount: number;
    fullStepCount: number;
    startStepIndex?: number;
    moduleTokens: string[];
    seedJobId?: string;
    seedStepId?: string;
  };
  job: OrderedAssemblyJob;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/project-adapter-jobs`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        confirmed: true,
        idempotencyKey,
        stepLimit,
        seedJobId,
        validationProfile,
        assemblyMode
      })
    }
  );
}

export async function startGlobalProjectAdapterJob(
  contextId: string,
  jobId: string,
  expectedContextDigest: string,
  expectedStepCount: number
): Promise<{
  success: boolean;
  executionScheduled: boolean;
  solidWorksStartedInRequest: false;
  message: string;
  job: OrderedAssemblyJob;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/project-adapter-jobs/${encodeURIComponent(jobId)}/start`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        confirmed: true,
        expectedContextDigest,
        expectedStepCount
      })
    }
  );
}

export async function resumeGlobalProjectAdapterJob(
  contextId: string,
  jobId: string,
  expectedContextDigest: string,
  expectedStepCount: number
): Promise<{
  success: boolean;
  executionScheduled: boolean;
  solidWorksStartedInRequest: false;
  message: string;
  job: OrderedAssemblyJob;
}> {
  return request(
    `/api/demo/global-assembly-contexts/${encodeURIComponent(contextId)}/project-adapter-jobs/${encodeURIComponent(jobId)}/resume`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        confirmed: true,
        expectedContextDigest,
        expectedStepCount
      })
    }
  );
}

export async function createEngineeringValidationJob(
  jobId: string,
  idempotencyKey?: string
): Promise<{
  success: boolean;
  executionScheduled: boolean;
  sourceDemoPreserved: true;
  message: string;
  validationJob: EngineeringValidationJob;
}> {
  return request(
    `/api/demo/semantic-assembly-sequence/jobs/${encodeURIComponent(jobId)}/engineering-validation`,
    {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ confirmed: true, idempotencyKey })
    }
  );
}

export async function loadEngineeringValidationJob(
  validationJobId: string
): Promise<EngineeringValidationJob> {
  return request(
    `/api/demo/engineering-validation-jobs/${encodeURIComponent(validationJobId)}`
  );
}

export async function previewSemanticConnection(options: {
  semanticCatalogPath?: string;
  endpointCatalogPath?: string;
  sourceGraphPath?: string;
  connectionRequest: SemanticConnectionRequest;
}): Promise<SemanticConnectionPreview> {
  return request<SemanticConnectionPreview>("/api/demo/semantic-port-catalog/connection-preview", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function previewSemanticAssemblyIntent(options: {
  requirement: string;
  semanticCatalogPath?: string;
  endpointCatalogPath?: string;
  sourceGraphPath?: string;
  planTemplatePath?: string;
}): Promise<SemanticConnectionPreview> {
  return request<SemanticConnectionPreview>("/api/demo/semantic-port-catalog/intent-preview", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(options)
  });
}

export async function previewOrderedSemanticAssembly(
  requirement: string,
  projectId = "project02"
): Promise<OrderedAssemblyPreview> {
  return request<OrderedAssemblyPreview>("/api/demo/semantic-assembly-sequence/preview", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ requirement, projectId })
  });
}

export async function loadOrderedSemanticAssemblyClosure(): Promise<OrderedAssemblyClosure> {
  return request<OrderedAssemblyClosure>("/api/demo/semantic-assembly-sequence/closure");
}

export async function loadOrderedSemanticAssemblyPipelineAudit(): Promise<OrderedAssemblyPipelineAudit> {
  return request<OrderedAssemblyPipelineAudit>("/api/demo/semantic-assembly-sequence/pipeline-audit");
}

export async function loadOrderedSemanticAssemblyDependencyAudit(): Promise<OrderedAssemblyDependencyAudit> {
  return request<OrderedAssemblyDependencyAudit>("/api/demo/semantic-assembly-sequence/dependency-audit");
}

export async function loadOrderedSemanticAssemblyReleaseContract(
  projectId: string
): Promise<OrderedAssemblyReleaseContract> {
  return request<OrderedAssemblyReleaseContract>(
    `/api/demo/semantic-assembly-sequence/release-contract?projectId=${encodeURIComponent(projectId)}`
  );
}

export async function runOrderedSemanticAssemblyValidatedDemo(
  requirement: string
): Promise<OrderedAssemblyValidatedRun> {
  return request<OrderedAssemblyValidatedRun>("/api/demo/semantic-assembly-sequence/run-validated-demo", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ requirement })
  });
}

export async function createOrderedSemanticAssemblyJob(
  requirement: string,
  executionMode: "validated_artifact_replay" | "live_cad" = "validated_artifact_replay",
  projectId = "project02"
): Promise<OrderedAssemblyJob> {
  return request<OrderedAssemblyJob>("/api/demo/semantic-assembly-sequence/jobs", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ requirement, executionMode, projectId })
  });
}

export async function loadOrderedSemanticAssemblyJob(jobId: string): Promise<OrderedAssemblyJob> {
  return request<OrderedAssemblyJob>(
    `/api/demo/semantic-assembly-sequence/jobs/${encodeURIComponent(jobId)}`
  );
}

export async function cancelOrderedSemanticAssemblyJob(jobId: string): Promise<OrderedAssemblyJob> {
  return request<OrderedAssemblyJob>(
    `/api/demo/semantic-assembly-sequence/jobs/${encodeURIComponent(jobId)}/cancel`,
    { method: "POST" }
  );
}

export async function pauseOrderedSemanticAssemblyJob(jobId: string): Promise<OrderedAssemblyJob> {
  return request<OrderedAssemblyJob>(
    `/api/demo/semantic-assembly-sequence/jobs/${encodeURIComponent(jobId)}/pause`,
    { method: "POST" }
  );
}

export async function resumeOrderedSemanticAssemblyJob(jobId: string): Promise<OrderedAssemblyJob> {
  return request<OrderedAssemblyJob>(
    `/api/demo/semantic-assembly-sequence/jobs/${encodeURIComponent(jobId)}/resume`,
    { method: "POST" }
  );
}

export async function applySemanticConnection(options: {
  semanticCatalogPath?: string;
  endpointCatalogPath?: string;
  sourceGraphPath?: string;
  connectionRequest: SemanticConnectionRequest;
  previewDigest: string;
  outputAssemblyPath: string;
  confirmed: boolean;
  executionMode?: "blank_rebuild" | "context_incremental";
}): Promise<SemanticConnectionApplyResult> {
  return request<SemanticConnectionApplyResult>("/api/demo/semantic-port-catalog/apply", {
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
