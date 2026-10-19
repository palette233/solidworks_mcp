from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any


BASE_CONTEXT_CACHE_SCHEMA = "global-cad-base-context-cache-entry/v1"
BASE_CONTEXT_WRAPPER_ADAPTER_VERSION = "create-global-cad-base-wrapper/v1"


class GlobalCadBaseContextCacheError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _wrapper_evidence_accepted(
    evidence: dict[str, Any],
    inputs: dict[str, Any],
    assembly_sha256: str,
) -> bool:
    try:
        transform = [float(value) for value in evidence["baseContextTransform"]]
        pose_error = float(evidence["poseMaximumElementError"])
        component_count = int(evidence["topLevelComponentCount"])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(
        evidence.get("schemaVersion") == "global-cad-base-wrapper-run/v1"
        and evidence.get("success") is True
        and evidence.get("sourceModuleUnchanged") is True
        and evidence.get("outputClosedAfterVerification") is True
        and evidence.get("sourceModuleSha256Before")
        == inputs.get("sourceAssemblySha256")
        and evidence.get("sourceModuleSha256After")
        == inputs.get("sourceAssemblySha256")
        and str(evidence.get("baseContextModuleToken") or "").upper()
        == inputs.get("baseContextModuleToken")
        and transform == inputs.get("baseContextTransform")
        and evidence.get("outputAssemblySha256") == assembly_sha256
        and component_count == 1
        and pose_error <= 1e-9
    )


def build_base_context_cache_descriptor(
    *,
    source_assembly_path: Path,
    source_assembly_sha256: str,
    base_context_module_token: str,
    base_context_transform: list[Any],
    adapter_version: str = BASE_CONTEXT_WRAPPER_ADAPTER_VERSION,
) -> dict[str, Any]:
    source = source_assembly_path.resolve()
    transform = [float(value) for value in base_context_transform]
    if len(transform) != 16:
        raise GlobalCadBaseContextCacheError("基座变换必须包含16个数值。")
    inputs = {
        "sourceAssemblySha256": str(source_assembly_sha256),
        "baseContextModuleToken": str(base_context_module_token).upper(),
        "baseContextTransform": transform,
        "adapterVersion": str(adapter_version),
    }
    return {
        "schemaVersion": "global-cad-base-context-cache-descriptor/v1",
        "cacheKey": _digest(inputs),
        "inputs": inputs,
        "sourceAssemblyPath": str(source),
    }


def lookup_base_context_cache(
    cache_root: Path,
    descriptor: dict[str, Any],
) -> dict[str, Any]:
    cache_root = cache_root.resolve()
    cache_key = str(descriptor.get("cacheKey") or "")
    entry_root = cache_root / cache_key
    metadata_path = entry_root / "cache-entry.json"
    if not metadata_path.is_file():
        return {
            "status": "miss",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": "cache_entry_missing",
        }
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": f"cache_metadata_unreadable:{exc}",
        }
    core = {key: value for key, value in metadata.items() if key != "entryDigest"}
    if (
        metadata.get("schemaVersion") != BASE_CONTEXT_CACHE_SCHEMA
        or metadata.get("entryDigest") != _digest(core)
        or metadata.get("cacheKey") != cache_key
        or metadata.get("inputs") != descriptor.get("inputs")
    ):
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": "cache_metadata_binding_mismatch",
        }
    assembly_path = entry_root / str(metadata.get("assemblyFile") or "")
    evidence_path = entry_root / str(metadata.get("evidenceFile") or "")
    if not assembly_path.is_file() or not evidence_path.is_file():
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": "cache_artifact_missing",
        }
    if (
        _file_sha256(assembly_path) != metadata.get("assemblySha256")
        or _file_sha256(evidence_path) != metadata.get("evidenceSha256")
    ):
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": "cache_artifact_digest_mismatch",
        }
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": f"cache_evidence_unreadable:{exc}",
        }
    inputs = descriptor["inputs"]
    valid_evidence = _wrapper_evidence_accepted(
        evidence,
        inputs,
        str(metadata.get("assemblySha256") or ""),
    )
    if not valid_evidence:
        return {
            "status": "invalid",
            "cacheKey": cache_key,
            "entryRoot": str(entry_root),
            "reason": "cache_wrapper_evidence_not_accepted",
        }
    return {
        "status": "hit",
        "cacheKey": cache_key,
        "entryRoot": str(entry_root),
        "metadataPath": str(metadata_path),
        "assemblyPath": str(assembly_path),
        "assemblySha256": metadata["assemblySha256"],
        "evidencePath": str(evidence_path),
        "evidenceSha256": metadata["evidenceSha256"],
        "adapterVersion": inputs["adapterVersion"],
        "cachedPreparationDurationSeconds": (
            float(evidence["durationSeconds"])
            if isinstance(evidence.get("durationSeconds"), (int, float))
            else None
        ),
    }


def publish_base_context_cache(
    cache_root: Path,
    descriptor: dict[str, Any],
    *,
    assembly_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    cache_root = cache_root.resolve()
    assembly_path = assembly_path.resolve()
    evidence_path = evidence_path.resolve()
    if not assembly_path.is_file() or not evidence_path.is_file():
        raise GlobalCadBaseContextCacheError("基座缓存发布缺少装配体或证据文件。")
    cache_key = str(descriptor.get("cacheKey") or "")
    if not cache_key:
        raise GlobalCadBaseContextCacheError("基座缓存描述缺少cacheKey。")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    inputs = descriptor.get("inputs") or {}
    assembly_sha256 = _file_sha256(assembly_path)
    if not _wrapper_evidence_accepted(evidence, inputs, assembly_sha256):
        raise GlobalCadBaseContextCacheError("基座包装证据不满足缓存发布条件。")

    existing = lookup_base_context_cache(cache_root, descriptor)
    if existing.get("status") == "hit":
        return {**existing, "published": False, "reusedExisting": True}

    cache_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{cache_key[:12]}-", dir=cache_root))
    target = cache_root / cache_key
    try:
        cached_assembly = temporary / "base-context-wrapper.SLDASM"
        cached_evidence = temporary / "base-context-wrapper.result.json"
        shutil.copy2(assembly_path, cached_assembly)
        shutil.copy2(evidence_path, cached_evidence)
        core = {
            "schemaVersion": BASE_CONTEXT_CACHE_SCHEMA,
            "cacheKey": cache_key,
            "inputs": descriptor["inputs"],
            "sourceAssemblyPathAtPublish": descriptor.get("sourceAssemblyPath"),
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "assemblyFile": cached_assembly.name,
            "assemblySha256": _file_sha256(cached_assembly),
            "assemblySizeBytes": cached_assembly.stat().st_size,
            "evidenceFile": cached_evidence.name,
            "evidenceSha256": _file_sha256(cached_evidence),
            "collisionStatus": "not_evaluated",
        }
        metadata = {**core, "entryDigest": _digest(core)}
        (temporary / "cache-entry.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            os.replace(temporary, target)
        except OSError:
            concurrent = lookup_base_context_cache(cache_root, descriptor)
            if concurrent.get("status") == "hit":
                shutil.rmtree(temporary, ignore_errors=True)
                return {**concurrent, "published": False, "reusedExisting": True}
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    result = lookup_base_context_cache(cache_root, descriptor)
    if result.get("status") != "hit":
        raise GlobalCadBaseContextCacheError("基座缓存发布后复核失败。")
    return {**result, "published": True, "reusedExisting": False}
