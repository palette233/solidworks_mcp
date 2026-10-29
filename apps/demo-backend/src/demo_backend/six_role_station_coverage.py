"""Read-only coverage: frozen members, current interface authority, station rules.

The 17 x 4 matrix is a denominator, never evidence that 68 stations are ready.
Existing immutable release verification and runtime revocations remain the
authority. This reporting layer neither creates a new release nor starts CAD.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .global_module_catalog import validate_global_module_catalog
from .global_relation_catalog_release import load_relation_catalog_release
from .mechanical_interface_contracts import validate_contract_catalog
from .relation_driving_safety import BLOCKED_STATUS, validate_relation_driving_safety_registry


SCOPE_PATH = "data/assembly_stations/scope-v1.json"
GLOBAL_PATH = "demo/global_assembly_catalog/v1/global_module_catalog.json"
DRIVING_SAFETY_PATH = "demo/global_assembly_catalog/relation-driving-safety-v1.json"
DATUM_SAFETY_PATH = "demo/cross_project_substitution/parameterized-datum-placement-v1/release-safety-registry.json"
CONTRACT_FOLDERS = (
    "transport", "contextual-transport", "scanner", "contextual-scanner",
    "calibration", "cleaning-weighing", "wastecup", "native-wastecup",
)


class SourceReader:
    """One-run source cache with content digests; never a historical-pass cache."""
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.sources, self.cache = {}, {}

    def path(self, path):
        path = Path(path)
        return path.resolve() if path.is_absolute() else (self.workspace/path).resolve()

    def bind(self, path):
        path = self.path(path)
        if path not in self.sources:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            self.sources[path] = {"path": str(path), "sha256": digest, "sizeBytes": path.stat().st_size}
        return self.sources[path]

    def read(self, path):
        path = self.path(path)
        if path not in self.cache:
            raw = path.read_bytes()
            self.sources[path] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "sizeBytes": len(raw)}
            self.cache[path] = json.loads(raw.decode("utf-8-sig"))
        return self.cache[path]


def validate_scope(scope, catalog):
    if scope.get("schemaVersion") != "six-role-station-scope/v1":
        raise ValueError("Unsupported six-role scope")
    validate_global_module_catalog(catalog)
    all_rows = scope.get("bases", [])+scope.get("movingModules", [])
    ids = [r.get("moduleDefinitionId") for r in all_rows]
    canonical = [r.get("cadModuleDefinitionId") for r in all_rows]
    if not all(ids) or not all(canonical) or len(ids) != len(set(ids)) or len(canonical) != len(set(canonical)):
        raise ValueError("Duplicate/empty frozen module identity")
    index = {}
    for definition in catalog.get("moduleDefinitions", []):
        for alias in definition.get("projectAliases", []):
            key = f'{alias["projectId"]}::{alias["moduleToken"]}'
            index.setdefault(key, []).append(definition)
    for row in all_rows:
        matches = index.get(row["moduleDefinitionId"], [])
        if len(matches) != 1 or matches[0]["moduleDefinitionId"] != row["cadModuleDefinitionId"]:
            raise ValueError(f'Frozen module is absent/ambiguous/drifted: {row["moduleDefinitionId"]}')
        if row["moduleDefinitionId"].split("::")[0] not in scope["projects"]:
            raise ValueError("Frozen module project is out of scope")
        if row.get("role") not in scope["roles"]:
            raise ValueError("Unknown frozen role")
    if any(r["role"] != "Base" for r in scope["bases"]) or any(r["role"] == "Base" for r in scope["movingModules"]):
        raise ValueError("Base/moving roles are mixed")
    counts = {"baseCount": len(scope["bases"]), "movingModuleCount": len(scope["movingModules"]),
              "exactPairCount": len(scope["bases"])*len(scope["movingModules"])}
    if counts != scope["expectedCounts"]:
        raise ValueError("Frozen scope counts disagree with actual members")
    return {row["moduleDefinitionId"]: index[row["moduleDefinitionId"]][0] for row in all_rows}


def _release_sources(reader, manifest):
    """Bind all files read by the existing immutable-release validator."""
    reader.read(manifest["releasedCatalogRelativePath"])
    topology = manifest.get("relationTopologyAttestation") or {}
    if topology.get("path"):
        reader.read(topology["path"])
    for row in manifest.get("validationEvidence", []):
        reader.read(row["path"])
    for key in ("parameterizedDatumPairBinding", "directInterfacePairBinding"):
        pair = (manifest.get("releaseMetadata") or {}).get(key) or {}
        for field in ("effectiveGraphPath", "cadResultPath", "outputAssemblyPath"):
            if pair.get(field):
                reader.bind(pair[field])


def load_current_interface_authorities(workspace, scope, *, reader=None):
    """Enumerate exact authenticated releases once, then apply current revocations.

Multiple releases remain visible; this report does not select execution mode
or replace the preferred-interface resolver. A caller still needs explicit
datum opt-in and normal planning/instance-context checks before execution.
    """
    reader = reader or SourceReader(workspace)
    catalog = reader.read(GLOBAL_PATH)
    identities = validate_scope(scope, catalog)
    alias_by_cad = {v["moduleDefinitionId"]: k for k, v in identities.items()}
    bases = {r["moduleDefinitionId"] for r in scope["bases"]}
    moving = {r["moduleDefinitionId"] for r in scope["movingModules"]}
    driving = reader.read(DRIVING_SAFETY_PATH)
    validate_relation_driving_safety_registry(driving)
    blocked_templates = {r["globalTemplateId"]: r for r in driving["templates"] if r["status"] == BLOCKED_STATUS}
    safety = reader.read(DATUM_SAFETY_PATH)
    if safety.get("schemaVersion") != "parameterized-datum-release-safety-registry/v1":
        raise ValueError("Unsupported runtime datum revocation registry")
    revoked_ids = {str(value) for r in safety.get("revokedReleases", [])
                   for value in [r.get("releaseId"), *r.get("globalRelationReleaseIds", [])] if value}
    blocked_pairs = {(r["moduleDefinitionId"], r["slotDefinitionId"]): r
                     for r in safety.get("revokedReleases", []) if r.get("blockCandidateReuse") is True}
    contracts = []
    for name in CONTRACT_FOLDERS:
        report = reader.read(f"demo/cross_project_substitution/{name}-interface-contract-v1/interface-contract-catalog.json")
        validate_contract_catalog(report)
        contracts.extend(report.get("compatibilityMatrix", []))
    rows, errors = defaultdict(list), []
    release_root = reader.workspace/"demo/global_assembly_catalog/releases"
    for path in sorted(release_root.glob("*/release-manifest.json")):
        manifest = reader.read(path)
        if manifest.get("status") != "released_for_demo_relation_execution":
            continue
        candidates, exact_pairs = set(), set()
        metadata = manifest.get("releaseMetadata") or {}
        binding_ids = {manifest.get("releaseId"), manifest.get("releaseDigest")}
        for key in ("directInterfacePairBinding", "parameterizedDatumPairBinding"):
            binding = metadata.get(key) or {}
            binding_ids.update((binding.get("releaseId"), binding.get("releaseDigest")))
            if binding.get("moduleDefinitionId") in moving and binding.get("slotDefinitionId") in bases:
                exact_pairs.add((binding["moduleDefinitionId"], binding["slotDefinitionId"]))
        binding_ids.discard(None)
        for contract in contracts:
            evidence = contract.get("pairReleaseEvidence") or {}
            if (contract.get("moduleDefinitionId") in moving and contract.get("slotDefinitionId") in bases
                    and contract.get("compatible") is True
                    and contract.get("existingPairReleaseReusable") is True
                    and binding_ids & {evidence.get("releaseId"), evidence.get("releaseDigest")}):
                exact_pairs.add((contract["moduleDefinitionId"], contract["slotDefinitionId"]))
        candidates.update(exact_pairs)
        released_catalog = None
        relative = manifest.get("releasedCatalogRelativePath")
        if relative:
            try:
                released_catalog = reader.read(relative)
            except (OSError, ValueError) as exc:
                errors.append({"manifestPath": str(path), "reason": str(exc)})
        if released_catalog:
            ports = {p["globalPortId"]: p for p in released_catalog.get("semanticPorts", [])}
            for template in released_catalog.get("connectionTemplates", []):
                if template.get("globalTemplateId") not in (manifest.get("scope") or {}).get("authorizedDrivingTemplateIds", []):
                    continue
                aliases = {alias_by_cad.get(ports.get(pid, {}).get("moduleDefinitionId"))
                           for field in ("candidatePortIdsA", "candidatePortIdsB") for pid in template.get(field, [])}
                base_ids, moving_ids = aliases & bases, aliases & moving
                if len(base_ids) == len(moving_ids) == 1:
                    candidates.add((next(iter(moving_ids)), next(iter(base_ids))))
        if not candidates:
            continue
        blocked_release = bool(binding_ids & revoked_ids)
        blocked_template_ids = sorted(set((manifest.get("scope") or {}).get("authorizedDrivingTemplateIds", [])) & set(blocked_templates))
        valid, error = False, None
        try:
            _release_sources(reader, manifest)
            load_relation_catalog_release(path, workspace_root=reader.workspace)
            valid = True
        except (OSError, ValueError) as exc:
            error = str(exc)
        for pair in sorted(candidates):
            blocked_pair = pair in blocked_pairs
            blocked = blocked_release or bool(blocked_template_ids) or blocked_pair
            row = {"releaseId": manifest.get("releaseId"), "releaseManifestPath": str(path.resolve()),
                   "releaseManifestSha256": reader.bind(path)["sha256"], "authenticated": valid,
                   "runtimeRevoked": blocked,
                   "exactPairAuthorityBound": pair in exact_pairs,
                   "currentAuthorityAvailable": valid and not blocked and pair in exact_pairs,
                   "blockedTemplateIds": blocked_template_ids,
                   "runtimeReason": blocked_pairs[pair].get("reasonCode") if blocked_pair else None,
                   "error": error, "requiresNormalPlannerAndContextChecks": True}
            rows[pair].append(row)
    return dict(rows), {"discoveryErrors": errors, "runtimeCandidateBlockedPairs": [list(p) for p in sorted(blocked_pairs)]}


def build_six_role_station_coverage(workspace, *, scope_path=None, station_rules=(),
                                   station_rule_validator=None, interface_authorities=None):
    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    reader = SourceReader(workspace)
    scope = reader.read(scope_path or SCOPE_PATH)
    identities = validate_scope(scope, reader.read(GLOBAL_PATH))
    interface_clock = perf_counter()
    if interface_authorities is None:
        authorities, authority_audit = load_current_interface_authorities(workspace, scope, reader=reader)
    else:
        authorities, authority_audit = interface_authorities, {"injectedForTesting": True}
    interface_seconds = perf_counter()-interface_clock
    alias_by_cad = {r["cadModuleDefinitionId"]: r["moduleDefinitionId"] for r in scope["bases"]+scope["movingModules"]}
    moving = {r["moduleDefinitionId"]: r for r in scope["movingModules"]}
    base_ids = {r["moduleDefinitionId"] for r in scope["bases"]}
    rules, seen = defaultdict(list), set()
    for rule in station_rules:
        rid = rule.get("ruleId")
        if not rid or rid in seen:
            raise ValueError("Empty/duplicate station rule ID")
        seen.add(rid)
        source = alias_by_cad.get(rule.get("sourceModuleDefinitionId"), rule.get("sourceModuleDefinitionId"))
        target = alias_by_cad.get(rule.get("targetBaseDefinitionId"), rule.get("targetBaseDefinitionId"))
        if source not in moving or target not in base_ids or rule.get("role") != moving[source]["role"]:
            raise ValueError("Station rule pair/role is outside frozen scope")
        required = {"placement", "evidence", "validation"}
        configured = (required.issubset(rule) and isinstance(rule["placement"], dict) and bool(rule["placement"])
                      and isinstance(rule["evidence"], list) and isinstance(rule["validation"], dict)
                      and rule["validation"].get("status") in {"candidate", "experimental_cad_verified", "released_demo"})
        assessment = {"configuredStationRule": configured, "validatedStationRule": False,
                      "experimentalEvidenceOnly": False,
                      "blockingReasonCodes": ["STATION_VALIDATOR_NOT_APPLIED"] if configured else ["STATION_RULE_INCOMPLETE"],
                      "evidence": [], "ruleDigest": hashlib.sha256(json.dumps(rule, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}
        if station_rule_validator is not None:
            assessment = station_rule_validator(reader.workspace, rule, scope)
        for evidence in assessment.get("evidence", []):
            path = evidence.get("path")
            if path and reader.bind(path)["sha256"] != evidence.get("sha256"):
                raise ValueError("Station validator evidence changed during coverage")
        rules[(source, target)].append({"ruleId": rid, "status": rule.get("validation", {}).get("status"), **assessment})
    pairs = []
    for module in scope["movingModules"]:
        for base in scope["bases"]:
            pair = (module["moduleDefinitionId"], base["moduleDefinitionId"])
            releases, assessments = authorities.get(pair, []), rules.get(pair, [])
            available = any(r.get("currentAuthorityAvailable") is True and r.get("authenticated") is True
                            and r.get("runtimeRevoked") is False for r in releases)
            configured = any(r.get("configuredStationRule") is True for r in assessments)
            validated = any(r.get("configuredStationRule") is True and r.get("validatedStationRule") is True for r in assessments)
            experimental = any(r.get("experimentalEvidenceOnly") is True for r in assessments)
            gaps = []
            if not available: gaps.append("CURRENT_INTERFACE_AUTHORITY_UNAVAILABLE")
            if not configured: gaps.append("TARGET_STATION_RULE_MISSING")
            elif not validated: gaps.append("TARGET_STATION_VALIDATION_PENDING")
            pairs.append({"sourceModuleDefinitionId": pair[0], "targetBaseDefinitionId": pair[1],
                "role": module["role"], "crossProject": pair[0].split("::")[0] != pair[1].split("::")[0],
                "executableCurrentAuthority": available, "configuredStationRule": configured,
                "validatedStationRule": validated, "experimentalEvidenceOnly": experimental,
                "interfaceReleases": releases, "stationRules": assessments, "missingData": gaps,
                "cadLaunchAllowed": False})
    return {"schemaVersion": "six-role-station-coverage/v1", "scopeId": scope["scopeId"],
        "summary": {**scope["expectedCounts"], "roleCounts": dict(Counter(r["role"] for r in scope["movingModules"])),
                    **{key+"PairCount": sum(r[key] for r in pairs) for key in (
                        "executableCurrentAuthority", "configuredStationRule", "validatedStationRule", "experimentalEvidenceOnly")},
                    "crossProjectPairCount": sum(r["crossProject"] for r in pairs),
                    "missingDataPairCount": sum(bool(r["missingData"]) for r in pairs)},
        "scope": scope, "moduleSources": {k: v.get("cadSources", []) for k, v in identities.items()},
        "pairs": pairs, "authorityAudit": authority_audit,
        "sources": sorted(reader.sources.values(), key=lambda r: r["path"]),
        "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter()-clock, "interfaceReadSeconds": interface_seconds,
        "cadExecuted": False, "cadLaunchAllowed": False,
        "boundary": "Current interface releases, configured station rules and validated station evidence are independent. 68 pairs do not mean 68 ready stations. Datum opt-in, precise rule binding and normal planner/context checks remain required; collision/B-rep and fastening are not evaluated."}


def render_station_coverage_markdown(report):
    s = report["summary"]
    lines = ["# 六类跨项目目标工位覆盖与缺口", "",
        f"范围：{s['movingModuleCount']}个移动模组 × {s['baseCount']}个基座 = {s['exactPairCount']}个精确配对；其中跨项目{s['crossProjectPairCount']}项。",
        "", "接口发布、工位配置和工位验证是三个独立层次；本报告不授权CAD，不把68项接口历史记录当作68个工位已完成。", "",
        f"- 当前已认证且未撤销的接口配对：{s['executableCurrentAuthorityPairCount']}",
        f"- 已配置工位规则：{s['configuredStationRulePairCount']}",
        f"- 工位证据已验证：{s['validatedStationRulePairCount']}",
        f"- 仅有实验性证据：{s['experimentalEvidenceOnlyPairCount']}", "",
        "| 移动模组 | 目标基座 | 功能角色 | 当前接口 | 工位配置 | 工位验证 | 缺口 |",
        "| --- | --- | --- | --- | --- | --- | --- |"]
    for p in report["pairs"]:
        labels = ["是" if p[k] else "否" for k in ("executableCurrentAuthority", "configuredStationRule", "validatedStationRule")]
        lines.append(f"| {p['sourceModuleDefinitionId']} | {p['targetBaseDefinitionId']} | {p['role']} | {' | '.join(labels)} | {', '.join(p['missingData']) or '仍需任务上下文校验'} |")
    lines += ["", "## 范围与边界", "",
              "- Project06、CCD、龙门、供胶和A700内部柔性结构不在本轮覆盖范围。",
              "- G000按校准主角色计数；GN00/AG00属于复合服务模组，功能重复不重复计算型号。",
              "- 仅配置规则不证明可执行；仅有CAD实验也不证明普通入口已经具备当前发布权威。",
              "- 碰撞/B-rep、实际紧固、动态工艺和生产签认没有在本报告中验证。",
              f"- 只读接口核验耗时 {report['interfaceReadSeconds']:.3f} 秒；报告总耗时 {report['durationSeconds']:.3f} 秒。",
              "- 全部读取文件及SHA-256见同目录coverage.json的sources字段。", ""]
    return "\n".join(lines)
