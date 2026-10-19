import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.global_cad_base_context_cache import (
    GlobalCadBaseContextCacheError,
    build_base_context_cache_descriptor,
    lookup_base_context_cache,
    publish_base_context_cache,
)


IDENTITY = [
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _accepted_artifacts(tmp_path: Path):
    source = tmp_path / "source.SLDASM"
    source.write_bytes(b"source-module")
    assembly = tmp_path / "wrapper.SLDASM"
    assembly.write_bytes(b"verified-wrapper")
    descriptor = build_base_context_cache_descriptor(
        source_assembly_path=source,
        source_assembly_sha256=_sha(source),
        base_context_module_token="A000",
        base_context_transform=IDENTITY,
    )
    evidence = {
        "schemaVersion": "global-cad-base-wrapper-run/v1",
        "success": True,
        "baseContextModuleToken": "A000",
        "baseContextTransform": IDENTITY,
        "sourceModuleSha256Before": _sha(source),
        "sourceModuleSha256After": _sha(source),
        "sourceModuleUnchanged": True,
        "outputAssemblySha256": _sha(assembly),
        "topLevelComponentCount": 1,
        "poseMaximumElementError": 0.0,
        "outputClosedAfterVerification": True,
        "durationSeconds": 123.5,
    }
    evidence_path = tmp_path / "wrapper.result.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return source, assembly, evidence_path, descriptor


def test_publish_and_reuse_verified_content_addressed_wrapper(tmp_path):
    source, assembly, evidence, descriptor = _accepted_artifacts(tmp_path)
    cache_root = tmp_path / "cache"

    published = publish_base_context_cache(
        cache_root,
        descriptor,
        assembly_path=assembly,
        evidence_path=evidence,
    )
    hit = lookup_base_context_cache(cache_root, descriptor)

    assert published["published"] is True
    assert hit["status"] == "hit"
    assert Path(hit["assemblyPath"]).read_bytes() == b"verified-wrapper"
    assert hit["cachedPreparationDurationSeconds"] == 123.5
    assert build_base_context_cache_descriptor(
        source_assembly_path=tmp_path / "moved" / source.name,
        source_assembly_sha256=_sha(source),
        base_context_module_token="A000",
        base_context_transform=IDENTITY,
    )["cacheKey"] == descriptor["cacheKey"]


def test_transform_and_adapter_version_invalidate_cache_key(tmp_path):
    source, assembly, evidence, descriptor = _accepted_artifacts(tmp_path)
    cache_root = tmp_path / "cache"
    publish_base_context_cache(
        cache_root,
        descriptor,
        assembly_path=assembly,
        evidence_path=evidence,
    )
    translated = [*IDENTITY]
    translated[9] = 0.125
    other_transform = build_base_context_cache_descriptor(
        source_assembly_path=source,
        source_assembly_sha256=_sha(source),
        base_context_module_token="A000",
        base_context_transform=translated,
    )
    other_adapter = build_base_context_cache_descriptor(
        source_assembly_path=source,
        source_assembly_sha256=_sha(source),
        base_context_module_token="A000",
        base_context_transform=IDENTITY,
        adapter_version="create-global-cad-base-wrapper/v2",
    )

    assert lookup_base_context_cache(cache_root, other_transform)["status"] == "miss"
    assert lookup_base_context_cache(cache_root, other_adapter)["status"] == "miss"


def test_corrupt_cached_assembly_is_rejected(tmp_path):
    _, assembly, evidence, descriptor = _accepted_artifacts(tmp_path)
    cache_root = tmp_path / "cache"
    published = publish_base_context_cache(
        cache_root,
        descriptor,
        assembly_path=assembly,
        evidence_path=evidence,
    )
    Path(published["assemblyPath"]).write_bytes(b"corrupt")

    result = lookup_base_context_cache(cache_root, descriptor)

    assert result["status"] == "invalid"
    assert result["reason"] == "cache_artifact_digest_mismatch"


def test_publish_rejects_incomplete_wrapper_evidence(tmp_path):
    _, assembly, evidence_path, descriptor = _accepted_artifacts(tmp_path)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence.pop("poseMaximumElementError")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(GlobalCadBaseContextCacheError, match="不满足缓存发布条件"):
        publish_base_context_cache(
            tmp_path / "cache",
            descriptor,
            assembly_path=assembly,
            evidence_path=evidence_path,
        )
