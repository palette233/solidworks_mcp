import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const workspace = process.cwd();
const catalogPath = path.join(workspace, "demo", "global_assembly_catalog", "v1", "global_module_catalog.json");
const coveragePath = path.join(workspace, "demo", "global_assembly_catalog", "v1", "global_module_port_coverage_matrix.json");
const outputDir = path.join(workspace, "outputs", "module_role_port_review_20261011");
const outputPath = path.join(outputDir, "全目录模组角色与语义端口人工审阅表_v1.xlsx");
const previewDir = path.join(outputDir, "previews");

if (process.argv.includes("--accept-all-suggested-roles")) {
  const acceptedOutputPath = path.join(outputDir, "全目录模组角色与语义端口人工审阅表_v1_已接受建议角色.xlsx");
  const input = await FileBlob.load(outputPath);
  const reviewWorkbook = await SpreadsheetFile.importXlsx(input);
  const reviewSheet = reviewWorkbook.worksheets.getItem("人工审阅");
  const summarySheet = reviewWorkbook.worksheets.getItem("概览");
  const verificationPath = path.join(outputDir, "verification.json");
  const verification = JSON.parse(await fs.readFile(verificationPath, "utf8"));
  const reviewCount = Number(verification.reviewRowCount);
  const firstRow = 5;
  const lastRow = firstRow + reviewCount - 1;
  const suggestedRoles = reviewSheet.getRange(`F${firstRow}:F${lastRow}`).values;
  reviewSheet.getRange(`L${firstRow}:L${lastRow}`).values = suggestedRoles;
  reviewSheet.getRange(`N${firstRow}:N${lastRow}`).values = Array.from(
    { length: reviewCount },
    () => ["角色已确认，其他待审"],
  );
  reviewSheet.getRange(`Q${firstRow}:Q${lastRow}`).values = Array.from(
    { length: reviewCount },
    () => ["2026-10-12：用户暂时接受建议角色；独立装配判断与端口集合仍待后续审阅。"],
  );
  reviewSheet.getRange(`N${firstRow}:N${lastRow}`).dataValidation = {
    rule: {
      type: "list",
      values: ["待确认", "角色已确认，其他待审", "确认", "需要修改", "需要SolidWorks查看"],
    },
  };
  reviewSheet.getRange(`N${firstRow}:N${lastRow}`).conditionalFormats.add("containsText", {
    text: "角色已确认",
    format: { fill: "#DBEAFE", font: { bold: true, color: "#1D4ED8" } },
  });

  summarySheet.getRange("D8:E8").values = [["建议角色已接受", null]];
  summarySheet.getRange("E8").formulas = [[`=COUNTA('人工审阅'!L${firstRow}:L${lastRow})`]];
  summarySheet.getRange("D9:E9").copyFrom(summarySheet.getRange("D8:E8"), "all");
  summarySheet.getRange("D9:E9").values = [["其他项目仍待审", null]];
  summarySheet.getRange("E9").formulas = [[`=COUNTIF('人工审阅'!N${firstRow}:N${lastRow},"角色已确认，其他待审")`]];
  summarySheet.getRange("D5:E9").format.borders = { preset: "outside", style: "thin", color: "#B7C9D6" };

  await reviewWorkbook.recalculate();
  const reviewInspect = await reviewWorkbook.inspect({
    kind: "table",
    sheetId: "人工审阅",
    range: `A1:Q${Math.min(lastRow, 12)}`,
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 17,
    maxChars: 12000,
  });
  const summaryInspect = await reviewWorkbook.inspect({
    kind: "table",
    sheetId: "概览",
    range: "A1:H12",
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 8,
    maxChars: 6000,
  });
  const errorInspect = await reviewWorkbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
    maxChars: 8000,
  });
  await fs.mkdir(previewDir, { recursive: true });
  const preview = await reviewWorkbook.render({
    sheetName: "人工审阅",
    range: `A1:Q${Math.min(lastRow, 19)}`,
    scale: 1,
    format: "png",
  });
  const previewPath = path.join(previewDir, "review_roles_accepted.png");
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  const output = await SpreadsheetFile.exportXlsx(reviewWorkbook);
  await output.save(acceptedOutputPath);

  verification.roleReviewUpdate = {
    updatedAt: "2026-10-12",
    acceptedSuggestedRoleCount: reviewCount,
    remainingOtherReviewCount: reviewCount,
    independentAssemblyDecisionChanged: false,
    portRecommendationChanged: false,
    reviewInspect: reviewInspect.ndjson,
    summaryInspect: summaryInspect.ndjson,
    errorInspect: errorInspect.ndjson,
    preview: previewPath,
  };
  await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2), "utf8");
  console.log(JSON.stringify({ outputPath: acceptedOutputPath, acceptedSuggestedRoleCount: reviewCount, remainingOtherReviewCount: reviewCount, previewPath }, null, 2));
  process.exit(0);
}

const catalog = JSON.parse(await fs.readFile(catalogPath, "utf8"));
const coverage = JSON.parse(await fs.readFile(coveragePath, "utf8"));

const roleDefinitions = {
  MachineBase: {
    cn: "设备机架/安装基座",
    required: "基座坐标系；上表面安装区；操作面方向；可用安装位",
    relation: "作为装配根节点，向其他模组提供安装端口",
  },
  Transport: {
    cn: "产品传输模组",
    required: "基座安装端口；输送方向；扫码工位；工作位1/2；条码目标区",
    relation: "连接基座，向扫描、CCD和工艺工作位提供功能端口",
  },
  BarcodeScanner: {
    cn: "条码扫描模组",
    required: "机械安装端口；扫描出光轴；扫描方向；工作距离",
    relation: "安装到基座或传输支架，光轴指向条码目标区",
  },
  CCDAlignment: {
    cn: "CCD视觉定位模组",
    required: "机械安装端口；相机光轴；视场；工作距离；工作位覆盖",
    relation: "安装到基座，功能端口覆盖传输工作位",
  },
  CalibrationStation: {
    cn: "针头标定模组",
    required: "机械安装端口；标定服务点；进针方向",
    relation: "安装到基座，标定点进入点胶头可达范围",
  },
  CalibrationWeighing: {
    cn: "标定与称重组合模组",
    required: "机械安装端口；标定服务点；称重点；维护方向",
    relation: "安装到基座，标定和称重服务点进入点胶头可达范围",
  },
  CleaningWeighing: {
    cn: "清洁/称重组合模组",
    required: "机械安装端口；清洁服务点；称重点；维护方向",
    relation: "安装到基座，服务点进入点胶头可达范围",
  },
  NozzleCleaning: {
    cn: "针头清洁模组",
    required: "机械安装端口；清洁服务点；进针方向；耗材维护方向",
    relation: "安装到基座，清洁点进入点胶头可达范围",
  },
  WasteCollection: {
    cn: "排胶/废胶收集模组",
    required: "机械安装端口；排胶服务点；进针方向；维护方向",
    relation: "安装到基座，排胶点进入点胶头可达范围",
  },
  CleaningInspection: {
    cn: "清洁与胶体检测组合模组",
    required: "机械安装端口；清洁点；废胶点；硬度测试点；维护方向",
    relation: "安装到基座，多个服务点进入点胶头可达范围",
  },
  CarrierPositioning: {
    cn: "载具顶升/旋转定位模组",
    required: "基座安装端口；载具定位基准；运动方向；工作状态",
    relation: "安装到基座或传输模组，向工艺工作位提供载具定位",
  },
  DispensingGantry: {
    cn: "XYZ龙门点胶模组",
    required: "基座安装端口；工具中心；点胶头方向；可达工作空间",
    relation: "安装到基座，工作空间覆盖传输工作位和服务点",
  },
  GlueSupply: {
    cn: "供胶系统",
    required: "机械安装端口；供胶输出接口；维护方向",
    relation: "安装到基座并向点胶阀提供供胶连接",
  },
};

function projectLabel(projectId) {
  return ({ project01: "项目01", project02: "项目02", project03: "项目03", project04: "项目04", project05: "项目05", project06: "项目06" })[projectId] ?? projectId;
}

function inferRole(module) {
  const name = module.displayName ?? "";
  const category = module.category ?? "";
  if (category === "frame") return ["MachineBase", "高"];
  if (category === "transport") return ["Transport", "高"];
  if (category === "scanner") return ["BarcodeScanner", "高"];
  if (category === "ccd") return ["CCDAlignment", "高"];
  if (category === "gantry") return ["DispensingGantry", "高"];
  if (category === "glue_supply") return ["GlueSupply", "高"];
  if (category === "positioning") return ["CarrierPositioning", "高"];
  if (category === "calibration") {
    if (name.includes("称重")) return ["CalibrationWeighing", "高"];
    return ["CalibrationStation", "高"];
  }
  if (category === "cleaning_weighing") {
    if (name.includes("针头清洁") || name.includes("自动针头清洁")) return ["NozzleCleaning", "高"];
    if (name.includes("废胶") && (name.includes("收集") || name.includes("排胶")) && !name.includes("清洁")) return ["WasteCollection", "高"];
    if (name.includes("硬度") || name.includes("测试")) return ["CleaningInspection", "中"];
    if (name.includes("清洁") && name.includes("称重")) return ["CleaningWeighing", "高"];
    return ["CleaningWeighing", "中"];
  }
  return ["Unclassified", "低"];
}

const pptEvidence = {
  project01: {
    overview: "01-PPT.pptx，第8页（整机模组总览）",
    BarcodeScanner: "01-PPT.pptx，第17页（扫描模组）",
    CalibrationStation: "01-PPT.pptx，第18–20页（针头标定）",
    CleaningWeighing: "01-PPT.pptx，第24–28页（清洁、称重、排胶）",
    CleaningInspection: "01-PPT.pptx，第24–28页（清洁、称重、硬度测试）",
    WasteCollection: "01-PPT.pptx，第24–28页（排胶/称重）",
    DispensingGantry: "01-PPT.pptx，第14页（点胶执行与微调轴）",
    Transport: "01-PPT.pptx，第15–16页（传输、顶升、旋转）",
    CarrierPositioning: "01-PPT.pptx，第15–16页（传输、顶升、旋转）",
  },
  project02: {
    overview: "02-PPT.pptx，第8页（整机模组总览）",
    BarcodeScanner: "02-PPT.pptx，第16页（SR-700扫描模组）",
    CalibrationStation: "02-PPT.pptx，第17–19页（针头标定）",
    CleaningWeighing: "02-PPT.pptx，第23–25页（称重、清洁）",
    WasteCollection: "02-PPT.pptx，第23–25页（排胶、称重、清洁）",
    DispensingGantry: "02-PPT.pptx，第14页（双阀与微调平台）",
    Transport: "02-PPT.pptx，第15页（双工作位传输）",
    CCDAlignment: "02-PPT.pptx，第28页（CCD X/Y模组）",
    GlueSupply: "02-PPT.pptx，第8页（供胶系统）",
  },
  project03: {
    overview: "03-PPT.pptx，第8页（整机模组总览）",
    BarcodeScanner: "03-PPT.pptx，第16页（SR-X100扫描模组）",
    CalibrationStation: "03-PPT.pptx，第17–22页（针头标定）",
    CleaningInspection: "03-PPT.pptx，第23–27页（清洁、称重、硬度测试）",
    CleaningWeighing: "03-PPT.pptx，第23–27页（清洁、称重）",
    DispensingGantry: "03-PPT.pptx，第12–13页（XYZ点胶执行）",
    Transport: "03-PPT.pptx，第14–15页（传输、顶升、旋转）",
    CarrierPositioning: "03-PPT.pptx，第14–15页（顶升与旋转定位）",
    GlueSupply: "03-PPT.pptx，第28–29页（双路自动供胶）",
  },
  project05: {
    overview: "05.pptx，第8页（整机模组总览）",
    BarcodeScanner: "05.pptx，第14页（双读头扫描）",
    CCDAlignment: "05.pptx，第15页（CCD X/Y模组）",
    CalibrationStation: "05.pptx，第16–18页（针头标定）",
    CalibrationWeighing: "05.pptx，第16–20页（标定与称重）",
    NozzleCleaning: "05.pptx，第21页（针头清洁）",
    WasteCollection: "05.pptx，第19–21页（称重、清洁、排胶）",
    DispensingGantry: "05.pptx，第11–12页（点胶行程与双阀）",
    Transport: "05.pptx，第13页（双工作位传输）",
  },
  project06: {
    overview: "06.pptx，第8页（整机模组总览）",
    BarcodeScanner: "06.pptx，第14页（双读头扫描）",
    CCDAlignment: "06.pptx，第15页（CCD X/Y模组）",
    CalibrationStation: "06.pptx，第16–18页（针头标定）",
    CalibrationWeighing: "06.pptx，第16–20页（标定与称重）",
    NozzleCleaning: "06.pptx，第21页（针头清洁）",
    WasteCollection: "06.pptx，第19–21页（称重、清洁、排胶）",
    DispensingGantry: "06.pptx，第11–12页（点胶行程与双阀）",
    Transport: "06.pptx，第13页（双工作位传输）",
  },
};

const moduleById = new Map(catalog.moduleDefinitions.map((m) => [m.moduleDefinitionId, m]));
const portById = new Map(catalog.semanticPorts.map((p) => [p.globalPortId, p]));
const coverageById = new Map(coverage.modules.map((m) => [m.moduleDefinitionId, m]));
const templateById = new Map(catalog.connectionTemplates.map((t) => [t.globalTemplateId, t]));

function aliasFor(module) {
  return module.projectAliases?.[0] ?? { projectId: "", moduleToken: "" };
}

function evidenceFor(projectId, role) {
  const entry = pptEvidence[projectId];
  if (!entry) return "现有全局目录与原型配合图";
  return entry[role] ?? entry.overview;
}

function recommendedReview(module, cov, role, confidence) {
  const alias = aliasFor(module);
  const reasons = [];
  let priority = "P2";
  if ((cov?.portCount ?? 0) === 0) {
    priority = "P0";
    reasons.push("当前无语义端口，需要从同项目原型配合或同构项目端口迁移");
  }
  if (module.portCoverage === "partial") {
    if (priority !== "P0") priority = "P1";
    reasons.push("现有端口覆盖为partial，需要确认安装端口与功能端口是否齐全");
  }
  if (["CleaningWeighing", "CleaningInspection", "CalibrationWeighing"].includes(role)) {
    if (priority === "P2") priority = "P1";
    reasons.push("组合功能模组，需要确认是否作为整体安装，及清洁/称重/检测端口是否拆分");
  }
  if (alias.projectId === "project02" && alias.moduleToken === "A700") {
    if (priority === "P2") priority = "P1";
    reasons.push("已知可移植性专项已暂停；保留Project02显式标定回退，当前不阻塞全目录覆盖");
  }
  if (confidence === "低") {
    priority = "P0";
    reasons.push("角色推断置信度低");
  }
  if (reasons.length === 0) reasons.push("角色与安装端口已有较完整目录证据，仅需快速确认");
  return [priority, reasons.join("；")];
}

const moduleRows = [];
for (const module of catalog.moduleDefinitions) {
  const alias = aliasFor(module);
  const cov = coverageById.get(module.moduleDefinitionId) ?? {};
  const [role, confidence] = inferRole(module);
  const roleDef = roleDefinitions[role] ?? { cn: "待分类", required: "待确认", relation: "待确认" };
  const ports = (module.portIds ?? []).map((id) => portById.get(id)).filter(Boolean);
  const compatibleNames = (cov.compatibleModuleDefinitionIds ?? [])
    .map((id) => moduleById.get(id)?.displayName ?? id)
    .filter((v, i, a) => a.indexOf(v) === i);
  const [priority, reviewReason] = recommendedReview(module, cov, role, confidence);
  const source = `${evidenceFor(alias.projectId, role)}；全局目录及面端点/配合模板`;
  moduleRows.push({
    projectId: alias.projectId,
    project: projectLabel(alias.projectId),
    token: alias.moduleToken,
    displayName: module.displayName,
    category: module.category,
    role,
    roleCn: roleDef.cn,
    confidence,
    independent: alias.isBaseModule ? "是（装配根基座）" : "是（顶层功能模组）",
    nature: alias.isBaseModule ? "基座" : (role.includes("Weighing") || role === "CleaningInspection" ? "复合功能模组" : "独立功能模组"),
    portCount: cov.portCount ?? 0,
    mechanicalPortCount: cov.mechanicalPortCount ?? 0,
    functionalPortCount: cov.functionalPortCount ?? 0,
    portNames: ports.map((p) => p.displayName).join("\n"),
    interfaceTypes: ports.map((p) => p.interfaceType).join("\n"),
    capabilities: [...new Set(ports.flatMap((p) => p.capabilities ?? []))].join("、"),
    recommendedPorts: roleDef.required,
    compatibleNames: compatibleNames.join("\n"),
    templateCount: (cov.templateIds ?? []).length,
    endpointReady: cov.cadEndpointReady ? "是" : "否",
    graphReady: cov.semanticGraphReady ? "是" : "否",
    coverageStatus: module.portCoverage ?? "none",
    source,
    priority,
    reviewReason,
    moduleDefinitionId: module.moduleDefinitionId,
    cadPath: module.cadSources?.[0]?.path ?? "",
  });
}

moduleRows.sort((a, b) => `${a.projectId}:${a.token}`.localeCompare(`${b.projectId}:${b.token}`, "zh-CN"));

const portRows = catalog.semanticPorts.map((p) => {
  const module = moduleById.get(p.moduleDefinitionId);
  const alias = module ? aliasFor(module) : { projectId: "", moduleToken: "" };
  const [role] = module ? inferRole(module) : ["Unclassified"];
  const compat = catalog.compatibility.filter((c) => c.portAId === p.globalPortId || c.portBId === p.globalPortId);
  const partners = compat.map((c) => {
    const otherId = c.portAId === p.globalPortId ? c.portBId : c.portAId;
    const other = portById.get(otherId);
    const otherModule = other ? moduleById.get(other.moduleDefinitionId) : null;
    const otherAlias = otherModule ? aliasFor(otherModule) : null;
    return otherAlias ? `${projectLabel(otherAlias.projectId)}/${otherAlias.moduleToken}` : otherId;
  });
  return [
    projectLabel(alias.projectId), alias.moduleToken, module?.displayName ?? "", role,
    p.displayName, p.category, p.interfaceType, (p.capabilities ?? []).join("、"),
    p.portable ? "是" : "否", (p.endpointEvidence ?? []).length,
    [...new Set(partners)].join("、"), compat.length,
    (p.provenance ?? []).map((x) => x.status).join("、"), p.globalPortId,
  ];
});

const roleCounts = new Map();
for (const r of moduleRows) roleCounts.set(r.roleCn, (roleCounts.get(r.roleCn) ?? 0) + 1);
const reviewRows = moduleRows.filter((r) => r.priority !== "P2");

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("概览");
const moduleSheet = workbook.worksheets.add("模组角色简表");
const reviewSheet = workbook.worksheets.add("人工审阅");
const portSheet = workbook.worksheets.add("端口明细");
const ruleSheet = workbook.worksheets.add("依据与规则");

for (const sheet of [summarySheet, moduleSheet, reviewSheet, portSheet, ruleSheet]) {
  sheet.showGridLines = false;
}

const fontFamily = "Microsoft YaHei";
const titleStyle = { font: { name: fontFamily, size: 15, bold: true, color: "#1F2937" } };
const headerStyle = {
  fill: "#1F4E78",
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
const bodyFont = { name: fontFamily, size: 10, color: "#1F2937" };
const inputFill = "#FFF2CC";
const lightBlue = "#D9EAF7";
const lightGray = "#F3F4F6";

// 概览
summarySheet.getRange("A2:H2").merge();
summarySheet.getRange("A2").values = [["全目录模组角色与语义端口审阅"]];
summarySheet.getRange("A2:H2").format = titleStyle;
summarySheet.getRange("A3:H3").merge();
summarySheet.getRange("A3").values = [["基于全局目录、原型配合与项目PPT/需求表的半自动初标。人工优先审阅P0/P1项。"]];
summarySheet.getRange("A3:H3").format = { font: { name: fontFamily, size: 10, italic: true, color: "#4B5563" } };

const pendingFormula = reviewRows.length > 0 ? `=COUNTIF('人工审阅'!N5:N${reviewRows.length + 4},"待确认")` : "=0";
summarySheet.getRange("A5:B10").values = [
  ["指标", "数量"],
  ["当前目录模组", coverage.summary.moduleCount],
  ["已有CAD端点模组", coverage.summary.cadEndpointReadyModuleCount],
  ["当前无端口模组", coverage.summary.blockedModuleCount],
  ["语义端口", catalog.summary.semanticPortCount],
  ["兼容连接", catalog.summary.compatibilityCount],
];
summarySheet.getRange("D5:E8").values = [
  ["审阅状态", "数量"],
  ["重点审阅行", reviewRows.length],
  ["P0行", reviewRows.filter((r) => r.priority === "P0").length],
  ["仍待人工确认", null],
];
summarySheet.getRange("E8").formulas = [[pendingFormula]];
summarySheet.getRange("A5:B5").format = headerStyle;
summarySheet.getRange("D5:E5").format = headerStyle;
summarySheet.getRange("A6:B10").format.font = bodyFont;
summarySheet.getRange("D6:E8").format.font = bodyFont;
summarySheet.getRange("A5:B10").format.borders = { preset: "outside", style: "thin", color: "#B7C9D6" };
summarySheet.getRange("D5:E8").format.borders = { preset: "outside", style: "thin", color: "#B7C9D6" };

summarySheet.getRange("A12:B12").values = [["建议标准角色", "模组数"]];
summarySheet.getRange("A12:B12").format = headerStyle;
let roleRow = 13;
for (const [roleCn, count] of [...roleCounts.entries()].sort((a, b) => b[1] - a[1])) {
  summarySheet.getRange(`A${roleRow}:B${roleRow}`).values = [[roleCn, count]];
  roleRow += 1;
}
summarySheet.getRange(`A13:B${roleRow - 1}`).format.font = bodyFont;
summarySheet.getRange("D12:H12").merge();
summarySheet.getRange("D12").values = [["人工审阅方法"]];
summarySheet.getRange("D12:H12").format = headerStyle;
summarySheet.getRange("D13:H18").merge();
summarySheet.getRange("D13").values = [[
  "1. 先打开“人工审阅”，优先处理P0，再处理P1。\n" +
  "2. 确认建议角色、是否独立装配、原型配合用途。\n" +
  "3. 不需要手工录入Face编号；端点与配合证据已保留在“端口明细”。\n" +
  "4. Project06当前9个模组无端口，适合优先从Project05同构原型迁移。\n" +
  "5. A700可移植性保留为专项，不阻塞本轮全目录覆盖。"
]];
summarySheet.getRange("D13:H18").format = { font: bodyFont, wrapText: true, verticalAlignment: "top", fill: "#F8FAFC", borders: { preset: "outside", style: "thin", color: "#D1D5DB" } };
summarySheet.freezePanes.freezeRows(4);

// 模组角色简表
moduleSheet.getRange("A2:Y2").merge();
moduleSheet.getRange("A2").values = [["现有模组角色和端口简表"]];
moduleSheet.getRange("A2:Y2").format = titleStyle;
const moduleHeaders = [
  "序号", "项目", "模组编号", "模组名称", "现有类别", "建议标准角色", "角色代码", "置信度",
  "独立装配判断", "模组性质", "端口数", "机械端口", "功能端口", "现有端口名称", "已有接口类型",
  "现有能力", "建议端口集合", "兼容模组", "模板数", "端点就绪", "语义图就绪", "覆盖状态", "人工优先级", "审阅原因", "主要依据",
];
moduleSheet.getRange("A4:Y4").values = [moduleHeaders];
moduleSheet.getRange("A4:Y4").format = headerStyle;
const moduleValues = moduleRows.map((r, i) => [
  i + 1, r.project, r.token, r.displayName, r.category, r.roleCn, r.role, r.confidence,
  r.independent, r.nature, r.portCount, r.mechanicalPortCount, r.functionalPortCount,
  r.portNames, r.interfaceTypes, r.capabilities, r.recommendedPorts, r.compatibleNames,
  r.templateCount, r.endpointReady, r.graphReady, r.coverageStatus, r.priority, r.reviewReason, r.source,
]);
moduleSheet.getRange(`A5:Y${moduleRows.length + 4}`).values = moduleValues;
moduleSheet.getRange(`A5:Y${moduleRows.length + 4}`).format = { font: bodyFont, verticalAlignment: "top" };
moduleSheet.getRange(`D5:Y${moduleRows.length + 4}`).format.wrapText = true;
moduleSheet.getRange(`K5:M${moduleRows.length + 4}`).format.numberFormat = "0";
moduleSheet.getRange(`A4:Y${moduleRows.length + 4}`).format.borders = { insideHorizontal: { style: "thin", color: "#E5E7EB" }, bottom: { style: "thin", color: "#9CA3AF" } };
moduleSheet.tables.add(`A4:Y${moduleRows.length + 4}`, true, "ModuleRoleTable");
moduleSheet.freezePanes.freezeRows(4);
moduleSheet.freezePanes.freezeColumns(4);
moduleSheet.getRange(`W5:W${moduleRows.length + 4}`).conditionalFormats.add("containsText", { text: "P0", format: { fill: "#FECACA", font: { bold: true, color: "#991B1B" } } });
moduleSheet.getRange(`W5:W${moduleRows.length + 4}`).conditionalFormats.add("containsText", { text: "P1", format: { fill: "#FEF3C7", font: { bold: true, color: "#92400E" } } });

// 人工审阅
reviewSheet.getRange("A2:Q2").merge();
reviewSheet.getRange("A2").values = [["人工审阅清单"]];
reviewSheet.getRange("A2:Q2").format = titleStyle;
reviewSheet.getRange("A3:Q3").merge();
reviewSheet.getRange("A3").values = [["黄色列为人工输入。建议先处理P0，再处理P1。若系统建议正确，可直接选择“确认”。"]];
reviewSheet.getRange("A3:Q3").format = { font: { name: fontFamily, size: 10, italic: true, color: "#4B5563" } };
const reviewHeaders = [
  "审阅ID", "优先级", "项目", "模组编号", "模组名称", "建议角色", "置信度", "现有端口",
  "建议端口集合", "需要确认的原因", "来源依据", "人工确认角色", "独立装配确认", "审阅结论", "最终角色", "最终独立装配", "人工备注",
];
reviewSheet.getRange("A4:Q4").values = [reviewHeaders];
reviewSheet.getRange("A4:Q4").format = headerStyle;
const reviewValues = reviewRows.map((r, i) => [
  `R${String(i + 1).padStart(3, "0")}`, r.priority, r.project, r.token, r.displayName, r.roleCn, r.confidence,
  r.portNames || "无", r.recommendedPorts, r.reviewReason, r.source,
  "", "", "待确认", "", "", "",
]);
if (reviewRows.length > 0) {
  reviewSheet.getRange(`A5:Q${reviewRows.length + 4}`).values = reviewValues;
  for (let i = 0; i < reviewRows.length; i += 1) {
    const row = i + 5;
    reviewSheet.getRange(`O${row}`).formulas = [[`=IF(L${row}<>"",L${row},F${row})`]];
    reviewSheet.getRange(`P${row}`).formulas = [[`=IF(M${row}<>"",M${row},"待确认")`]];
  }
  const roleOptions = Object.values(roleDefinitions).map((x) => x.cn);
  reviewSheet.getRange(`L5:L${reviewRows.length + 4}`).dataValidation = { rule: { type: "list", values: roleOptions } };
  reviewSheet.getRange(`M5:M${reviewRows.length + 4}`).dataValidation = { rule: { type: "list", values: ["是", "否", "复合模组内部成员", "待进一步查看"] } };
  reviewSheet.getRange(`N5:N${reviewRows.length + 4}`).dataValidation = { rule: { type: "list", values: ["待确认", "确认", "需要修改", "需要SolidWorks查看"] } };
  reviewSheet.getRange(`L5:N${reviewRows.length + 4}`).format.fill = inputFill;
  reviewSheet.getRange(`Q5:Q${reviewRows.length + 4}`).format.fill = inputFill;
  reviewSheet.getRange(`N5:N${reviewRows.length + 4}`).conditionalFormats.add("containsText", { text: "待确认", format: { fill: "#FEF3C7", font: { bold: true, color: "#92400E" } } });
  reviewSheet.getRange(`N5:N${reviewRows.length + 4}`).conditionalFormats.add("containsText", { text: "确认", format: { fill: "#DCFCE7", font: { bold: true, color: "#166534" } } });
  reviewSheet.getRange(`N5:N${reviewRows.length + 4}`).conditionalFormats.add("containsText", { text: "需要修改", format: { fill: "#FECACA", font: { bold: true, color: "#991B1B" } } });
  reviewSheet.getRange(`A5:Q${reviewRows.length + 4}`).format = { font: bodyFont, verticalAlignment: "top" };
  reviewSheet.getRange(`E5:Q${reviewRows.length + 4}`).format.wrapText = true;
  reviewSheet.tables.add(`A4:Q${reviewRows.length + 4}`, true, "ManualReviewTable");
}
reviewSheet.freezePanes.freezeRows(4);
reviewSheet.freezePanes.freezeColumns(5);

// 端口明细
portSheet.getRange("A2:N2").merge();
portSheet.getRange("A2").values = [["现有语义端口明细"]];
portSheet.getRange("A2:N2").format = titleStyle;
const portHeaders = ["项目", "模组编号", "模组名称", "建议角色代码", "端口名称", "类别", "接口类型", "能力", "可移植", "端点数", "兼容模组", "兼容边数", "来源状态", "全局端口ID"];
portSheet.getRange("A4:N4").values = [portHeaders];
portSheet.getRange("A4:N4").format = headerStyle;
portSheet.getRange(`A5:N${portRows.length + 4}`).values = portRows;
portSheet.getRange(`A5:N${portRows.length + 4}`).format = { font: bodyFont, verticalAlignment: "top" };
portSheet.getRange(`C5:N${portRows.length + 4}`).format.wrapText = true;
portSheet.tables.add(`A4:N${portRows.length + 4}`, true, "SemanticPortTable");
portSheet.freezePanes.freezeRows(4);
portSheet.freezePanes.freezeColumns(4);

// 依据与规则
ruleSheet.getRange("A2:F2").merge();
ruleSheet.getRange("A2").values = [["角色与端口规则、资料来源"]];
ruleSheet.getRange("A2:F2").format = titleStyle;
ruleSheet.getRange("A4:D4").values = [["角色代码", "中文角色", "建议端口集合", "典型关系"]];
ruleSheet.getRange("A4:D4").format = headerStyle;
let rr = 5;
for (const [code, def] of Object.entries(roleDefinitions)) {
  ruleSheet.getRange(`A${rr}:D${rr}`).values = [[code, def.cn, def.required, def.relation]];
  rr += 1;
}
ruleSheet.getRange(`A5:D${rr - 1}`).format = { font: bodyFont, verticalAlignment: "top", wrapText: true };
ruleSheet.tables.add(`A4:D${rr - 1}`, true, "RoleRuleTable");

const sourceStart = rr + 2;
ruleSheet.getRange(`A${sourceStart}:F${sourceStart}`).values = [["来源", "适用项目", "页/范围", "用于判断", "证据等级", "备注"]];
ruleSheet.getRange(`A${sourceStart}:F${sourceStart}`).format = headerStyle;
const sources = [
  ["全局模组目录", "01/02/03/05/06", "43模组、74端口、39模板、61兼容关系", "CAD身份、现有端口、模板、兼容关系", "直接目录证据", "目录摘要以当前global_module_catalog.json为准"],
  ["全局端口覆盖矩阵", "01/02/03/05/06", "43模组", "端点就绪、语义图就绪、缺口优先级", "直接目录证据", "当前34个模组端点就绪，9个模组无端口"],
  ["01-PPT.pptx", "项目01", "第8页及相关详细设计页", "机架、传输、扫描、标定、清洁称重、龙门、供胶角色", "工艺资料", "模组编号映射仍以CAD目录为准"],
  ["02-PPT.pptx", "项目02", "第8、10、14–28页", "扫描、CCD、标定、清洁、称重、传输和龙门工艺语义", "工艺资料", "A700可移植问题独立保留"],
  ["03-PPT.pptx", "项目03", "第8、9、12–29页", "扫描、标定、清洁称重、定位、龙门和供胶语义", "工艺资料", "含旋转载具与双路供胶"],
  ["04.pptx", "项目04", "第8、9、12–28页", "通用角色补充：上料龙门、旋转点胶、扫描、清洁称重", "工艺参考", "当前全局CAD目录没有Project04模组定义"],
  ["05.pptx", "项目05", "第8、9、11–23页", "传输、扫描、CCD、标定称重、清洁和龙门语义", "工艺资料", "与Project06结构高度相似"],
  ["06.pptx", "项目06", "第8、9、11–23页", "Project06模组角色与工艺功能", "工艺资料", "当前9个模组均缺语义端口，可优先对照Project05迁移"],
  ["双阀点胶方案需求描述文件_20260908.xlsx", "通用/项目02参考", "Sheet1，第2–11行", "核心模组集合、工作位、龙门覆盖、CCD覆盖和操作面维护要求", "需求资料", "明确清洁、排胶和称重模组尽量靠近OP操作侧"],
];
ruleSheet.getRange(`A${sourceStart + 1}:F${sourceStart + sources.length}`).values = sources;
ruleSheet.getRange(`A${sourceStart + 1}:F${sourceStart + sources.length}`).format = { font: bodyFont, verticalAlignment: "top", wrapText: true };
ruleSheet.tables.add(`A${sourceStart}:F${sourceStart + sources.length}`, true, "SourceEvidenceTable");
ruleSheet.freezePanes.freezeRows(4);

// 通用列宽与行高
summarySheet.getRange("A:H").format.font = bodyFont;
summarySheet.getRange("A:A").format.columnWidth = 27;
summarySheet.getRange("B:B").format.columnWidth = 12;
summarySheet.getRange("C:C").format.columnWidth = 3;
summarySheet.getRange("D:H").format.columnWidth = 18;

const moduleWidths = [7, 10, 11, 26, 16, 22, 20, 10, 18, 16, 9, 10, 10, 28, 26, 20, 36, 28, 9, 10, 11, 14, 11, 42, 34];
moduleWidths.forEach((w, i) => moduleSheet.getRangeByIndexes(0, i, moduleRows.length + 6, 1).format.columnWidth = w);
moduleSheet.getRange(`A5:Y${moduleRows.length + 4}`).format.rowHeight = 44;

const reviewWidths = [10, 9, 10, 11, 26, 23, 10, 28, 36, 42, 32, 24, 18, 18, 24, 18, 32];
reviewWidths.forEach((w, i) => reviewSheet.getRangeByIndexes(0, i, reviewRows.length + 6, 1).format.columnWidth = w);
if (reviewRows.length > 0) reviewSheet.getRange(`A5:Q${reviewRows.length + 4}`).format.rowHeight = 58;

const portWidths = [10, 11, 26, 20, 30, 12, 32, 22, 10, 9, 25, 10, 24, 46];
portWidths.forEach((w, i) => portSheet.getRangeByIndexes(0, i, portRows.length + 6, 1).format.columnWidth = w);
portSheet.getRange(`A5:N${portRows.length + 4}`).format.rowHeight = 42;

ruleSheet.getRange("A:A").format.columnWidth = 25;
ruleSheet.getRange("B:B").format.columnWidth = 24;
ruleSheet.getRange("C:C").format.columnWidth = 46;
ruleSheet.getRange("D:D").format.columnWidth = 44;
ruleSheet.getRange("E:E").format.columnWidth = 18;
ruleSheet.getRange("F:F").format.columnWidth = 38;

// 统一标题和表头高度
for (const sheet of [summarySheet, moduleSheet, reviewSheet, portSheet, ruleSheet]) {
  sheet.getRange("1:1").format.rowHeight = 10;
  sheet.getRange("2:2").format.rowHeight = 25;
}
moduleSheet.getRange("4:4").format.rowHeight = 34;
reviewSheet.getRange("4:4").format.rowHeight = 34;
portSheet.getRange("4:4").format.rowHeight = 34;
ruleSheet.getRange("4:4").format.rowHeight = 34;

await workbook.recalculate();

await fs.mkdir(previewDir, { recursive: true });
const previews = [
  ["概览", "A1:H26", "summary.png"],
  ["模组角色简表", "A1:Y18", "modules.png"],
  ["人工审阅", `A1:Q${Math.min(reviewRows.length + 4, 18)}`, "review.png"],
  ["端口明细", "A1:N18", "ports.png"],
  ["依据与规则", `A1:F${sourceStart + sources.length}`, "rules.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const blob = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await blob.arrayBuffer()));
}

const summaryInspect = await workbook.inspect({
  kind: "table",
  sheetId: "概览",
  range: "A1:H20",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
  maxChars: 8000,
});
const reviewInspect = await workbook.inspect({
  kind: "table",
  sheetId: "人工审阅",
  range: `A1:Q${Math.min(reviewRows.length + 4, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 17,
  maxChars: 10000,
});
const errorInspect = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 8000,
});

await fs.mkdir(outputDir, { recursive: true });
const out = await SpreadsheetFile.exportXlsx(workbook);
await out.save(outputPath);

const verification = {
  outputPath,
  sourceCatalogDigest: catalog.catalogDigest,
  sourceCoverageDigest: coverage.matrixDigest,
  moduleCount: moduleRows.length,
  portCount: portRows.length,
  reviewRowCount: reviewRows.length,
  p0ReviewCount: reviewRows.filter((r) => r.priority === "P0").length,
  p1ReviewCount: reviewRows.filter((r) => r.priority === "P1").length,
  summaryInspect: summaryInspect.ndjson,
  reviewInspect: reviewInspect.ndjson,
  errorInspect: errorInspect.ndjson,
  previews: previews.map((x) => path.join(previewDir, x[2])),
};
await fs.writeFile(path.join(outputDir, "verification.json"), JSON.stringify(verification, null, 2), "utf8");
console.log(JSON.stringify({ outputPath, moduleCount: moduleRows.length, portCount: portRows.length, reviewRowCount: reviewRows.length, p0: verification.p0ReviewCount, p1: verification.p1ReviewCount, previewDir }, null, 2));
