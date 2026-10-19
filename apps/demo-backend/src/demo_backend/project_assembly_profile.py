from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PROFILE_SCHEMA = "project-assembly-profile/v1"
SUPPORTED_CONFIDENCE_LEVELS = {
    "vendor-confirmed",
    "engineer-confirmed",
    "measured-from-cad",
    "inferred-from-prototype",
    "temporary-estimate",
}


class ProjectAssemblyProfileError(ValueError):
    pass


def project_assembly_profile_path(project_id: str) -> Path:
    normalized = str(project_id or "").strip().lower()
    if not normalized or not normalized.replace("-", "").replace("_", "").isalnum():
        raise ProjectAssemblyProfileError(f"非法项目编号：{project_id!r}")
    return Path(__file__).resolve().parent / "project_profiles" / f"{normalized}.json"


def validate_project_assembly_profile(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schemaVersion") != PROFILE_SCHEMA:
        raise ProjectAssemblyProfileError("不支持的项目装配配置版本。")

    project_id = str(payload.get("projectId") or "").strip().lower()
    if not project_id:
        raise ProjectAssemblyProfileError("项目装配配置缺少projectId。")
    if not str(payload.get("profileVersion") or "").strip():
        raise ProjectAssemblyProfileError("项目装配配置缺少profileVersion。")

    modules = payload.get("modules")
    if not isinstance(modules, dict) or not modules:
        raise ProjectAssemblyProfileError("项目装配配置必须包含非空modules。")
    normalized_modules = {str(token).upper(): row for token, row in modules.items()}
    if len(normalized_modules) != len(modules):
        raise ProjectAssemblyProfileError("模组编号忽略大小写后重复。")

    base_module = str(payload.get("baseModule") or "").upper()
    if base_module not in normalized_modules:
        raise ProjectAssemblyProfileError("baseModule未登记在modules中。")

    validated_sequence = [str(value).upper() for value in payload.get("validatedSequence") or []]
    if not validated_sequence or validated_sequence[0] != base_module:
        raise ProjectAssemblyProfileError("validatedSequence必须以baseModule开始。")
    unknown_sequence = [value for value in validated_sequence if value not in normalized_modules]
    if unknown_sequence:
        raise ProjectAssemblyProfileError(
            "validatedSequence包含未登记模组：" + "、".join(unknown_sequence)
        )
    if len(validated_sequence) != len(set(validated_sequence)):
        raise ProjectAssemblyProfileError("validatedSequence中存在重复模组。")

    aliases: dict[str, str] = {}
    for token, row in normalized_modules.items():
        if not isinstance(row, dict):
            raise ProjectAssemblyProfileError(f"模组{token}配置必须为对象。")
        if not str(row.get("label") or "").strip():
            raise ProjectAssemblyProfileError(f"模组{token}缺少label。")
        instance_count = row.get("instanceCount", 1)
        if not isinstance(instance_count, int) or instance_count < 1:
            raise ProjectAssemblyProfileError(f"模组{token}的instanceCount必须为正整数。")
        confidence = str(row.get("sourceConfidence") or "")
        if confidence not in SUPPORTED_CONFIDENCE_LEVELS:
            raise ProjectAssemblyProfileError(
                f"模组{token}的sourceConfidence不受支持：{confidence or 'missing'}"
            )
        raw_aliases = [token, *(row.get("aliases") or [])]
        for alias_value in raw_aliases:
            alias = str(alias_value).strip()
            if not alias:
                raise ProjectAssemblyProfileError(f"模组{token}包含空别名。")
            existing = aliases.get(alias.casefold())
            if existing is not None and existing != token:
                raise ProjectAssemblyProfileError(
                    f"别名{alias!r}同时指向{existing}和{token}。"
                )
            aliases[alias.casefold()] = token

        policy = row.get("assemblyPolicy")
        if token == base_module:
            continue
        if not isinstance(policy, dict):
            raise ProjectAssemblyProfileError(f"增量模组{token}缺少assemblyPolicy。")
        required = [str(value).upper() for value in policy.get("requires") or []]
        unknown_required = [value for value in required if value not in normalized_modules]
        if unknown_required:
            raise ProjectAssemblyProfileError(
                f"模组{token}依赖未登记模组：" + "、".join(unknown_required)
            )
        if token in required:
            raise ProjectAssemblyProfileError(f"模组{token}不能依赖自身。")
        for required_key in (
            "placementKind",
            "ruleSummary",
            "acceptanceChecks",
            "implementationStatus",
        ):
            if required_key not in policy:
                raise ProjectAssemblyProfileError(
                    f"模组{token}的assemblyPolicy缺少{required_key}。"
                )

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ProjectAssemblyProfileError("项目装配配置缺少artifacts。")
    for key in ("orderedClosure", "fullMachineClosure"):
        if not str(artifacts.get(key) or "").strip():
            raise ProjectAssemblyProfileError(f"artifacts缺少{key}。")

    release_boundary = payload.get("releaseBoundary")
    if release_boundary is not None:
        if not isinstance(release_boundary, dict):
            raise ProjectAssemblyProfileError("releaseBoundary必须为对象。")
        requirements = release_boundary.get("productionDynamicRequires") or []
        if not isinstance(requirements, list) or any(
            not str(value).strip() for value in requirements
        ):
            raise ProjectAssemblyProfileError(
                "productionDynamicRequires必须为非空字符串数组。"
            )
        dynamic_evidence = release_boundary.get("dynamicEvidence")
        if dynamic_evidence is not None:
            if not isinstance(dynamic_evidence, dict):
                raise ProjectAssemblyProfileError("dynamicEvidence必须为对象。")
            for key in ("artifact", "schemaVersion"):
                if not str(dynamic_evidence.get(key) or "").strip():
                    raise ProjectAssemblyProfileError(f"dynamicEvidence缺少{key}。")

    result = deepcopy(payload)
    result["projectId"] = project_id
    result["baseModule"] = base_module
    result["validatedSequence"] = validated_sequence
    result["modules"] = normalized_modules
    return result


def assembly_profile_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_project_assembly_profile(
    project_id: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    profile_path = (path or project_assembly_profile_path(project_id)).resolve()
    if not profile_path.is_file():
        raise ProjectAssemblyProfileError(f"项目装配配置不存在：{profile_path}")
    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectAssemblyProfileError(f"项目装配配置JSON无效：{profile_path}") from exc
    if not isinstance(raw, dict):
        raise ProjectAssemblyProfileError("项目装配配置根节点必须为对象。")
    profile = validate_project_assembly_profile(raw)
    if profile["projectId"] != str(project_id).strip().lower():
        raise ProjectAssemblyProfileError(
            f"配置projectId={profile['projectId']}与请求{project_id}不一致。"
        )
    profile["profilePath"] = str(profile_path)
    profile["profileDigest"] = assembly_profile_digest(raw)
    return profile


def module_alias_map(profile: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for token, row in profile["modules"].items():
        result[token] = token
        for alias in row.get("aliases") or []:
            result[str(alias)] = token
    return result


def module_policy_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base_module = str(profile["baseModule"])
    return {
        token: deepcopy(row["assemblyPolicy"])
        for token, row in profile["modules"].items()
        if token != base_module
    }
