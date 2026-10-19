import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.global_manifest_seed_import import (
    GlobalManifestSeedImportError,
    build_existing_assembly_subset_seed_evidence,
    build_external_manifest_seed_evidence,
    validate_external_manifest_seed_evidence,
)


def _fixture(tmp_path: Path):
    assembly = tmp_path / "checkpoint.SLDASM"
    assembly.write_bytes(b"historical-checkpoint")
    context = {
        "contextId": "target-context",
        "contextDigest": "context-digest",
        "catalogDigest": "catalog-digest",
        "instances": [
            {"instanceId": "instance-a", "moduleDefinitionId": "definition-a"},
            {"instanceId": "instance-b", "moduleDefinitionId": "definition-b"},
        ],
        "history": [
            {
                "operation": "catalog_binding_migration",
                "sourceContextId": "source-context",
            }
        ],
    }
    catalog = {
        "catalogDigest": "catalog-digest",
        "moduleDefinitions": [
            {
                "moduleDefinitionId": "definition-a",
                "projectAliases": [{"projectId": "project02", "moduleToken": "A500"}],
            },
            {
                "moduleDefinitionId": "definition-b",
                "projectAliases": [{"projectId": "project02", "moduleToken": "A700"}],
            },
        ],
    }
    historical = {
        "schemaVersion": "historical-demo-checkpoint-import/v1",
        "status": "ready_for_import",
        "contextId": "source-context",
        "contextRevision": 2,
        "projectId": "project02",
        "checkpointAssemblyIdentity": {
            "path": str(assembly),
            "sizeBytes": assembly.stat().st_size,
            "sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
        },
        "expectedModuleTokenCounts": {"A500": 1, "A700": 1},
        "observedModuleTokenCounts": {"A500": 1, "A700": 1},
        "instanceTokenBindings": [
            {"instanceId": "instance-a", "moduleToken": "A500"},
            {"instanceId": "instance-b", "moduleToken": "A700"},
        ],
        "blockers": [],
        "assessmentDigest": "assessment-digest",
        "importedAt": "2026-10-11T00:00:00Z",
    }
    import_path = tmp_path / "historical-import.json"
    import_path.write_text(json.dumps(historical), encoding="utf-8")
    plan = {
        "requiresSeedCheckpoint": True,
        "expectedSeed": {
            "packetId": "packet-009",
            "packetDigest": "packet-digest",
            "moduleToken": "T401",
        },
        "manifestPath": str(tmp_path / "manifest.json"),
        "manifestDigest": "manifest-digest",
        "planDigest": "plan-digest",
        "contextId": "target-context",
        "contextDigest": "context-digest",
    }
    return plan, context, catalog, historical, import_path, assembly


def test_signed_historical_checkpoint_converts_to_external_seed(tmp_path: Path):
    plan, context, catalog, historical, import_path, assembly = _fixture(tmp_path)

    evidence = build_external_manifest_seed_evidence(
        plan=plan,
        context=context,
        catalog=catalog,
        historical_import=historical,
        historical_import_path=import_path,
    )

    assert evidence["packetId"] == "packet-009"
    assert evidence["outputAssemblyPath"] == str(assembly.resolve())
    assert [row["moduleToken"] for row in evidence["instanceTokenBindings"]] == [
        "A500",
        "A700",
    ]
    validate_external_manifest_seed_evidence(evidence, plan=plan)


def test_instance_identity_mismatch_is_rejected(tmp_path: Path):
    plan, context, catalog, historical, import_path, _ = _fixture(tmp_path)
    historical["instanceTokenBindings"][0]["moduleToken"] = "A300"

    with pytest.raises(GlobalManifestSeedImportError, match="实例集合"):
        build_external_manifest_seed_evidence(
            plan=plan,
            context=context,
            catalog=catalog,
            historical_import=historical,
            historical_import_path=import_path,
        )


def test_external_seed_digest_prevents_post_conversion_edits(tmp_path: Path):
    plan, context, catalog, historical, import_path, _ = _fixture(tmp_path)
    evidence = build_external_manifest_seed_evidence(
        plan=plan,
        context=context,
        catalog=catalog,
        historical_import=historical,
        historical_import_path=import_path,
    )
    evidence["packetDigest"] = "changed"

    with pytest.raises(GlobalManifestSeedImportError, match="证据摘要"):
        validate_external_manifest_seed_evidence(evidence, plan=plan)


def test_existing_assembly_can_attest_a_relation_context_subset(tmp_path: Path):
    assembly = tmp_path / "full.SLDASM"
    assembly.write_bytes(b"full-project03-assembly")
    inventory = tmp_path / "poses.json"
    inventory.write_text(
        json.dumps(
            {
                "schemaVersion": "assembly-top-level-component-poses/v1",
                "assemblyPath": str(assembly.resolve()),
                "componentCount": 3,
                "components": [
                    {"Name": "FL9A24D063AA00.001-1", "Path": "AA00.SLDASM"},
                    {"Name": "FL9A24D063AB00.001-1", "Path": "AB00.SLDASM"},
                    {"Name": "EXTRA-1", "Path": "extra.SLDASM"},
                ],
            }
        ),
        encoding="utf-8",
    )
    context = {
        "contextId": "p03-relation",
        "contextDigest": "context-digest",
        "catalogDigest": "catalog-digest",
        "instances": [
            {"instanceId": "aa", "moduleDefinitionId": "definition-aa"},
            {"instanceId": "ab", "moduleDefinitionId": "definition-ab"},
        ],
    }
    catalog = {
        "catalogDigest": "catalog-digest",
        "moduleDefinitions": [
            {
                "moduleDefinitionId": "definition-aa",
                "projectAliases": [{"projectId": "project03", "moduleToken": "AA00"}],
            },
            {
                "moduleDefinitionId": "definition-ab",
                "projectAliases": [{"projectId": "project03", "moduleToken": "AB00"}],
            },
        ],
    }
    plan = {
        "requiresSeedCheckpoint": True,
        "expectedSeed": {
            "packetId": "packet-001",
            "packetDigest": "packet-digest",
            "moduleToken": "AB00",
        },
        "manifestPath": str(tmp_path / "manifest.json"),
        "manifestDigest": "manifest-digest",
        "planDigest": "plan-digest",
        "contextId": "p03-relation",
        "contextDigest": "context-digest",
    }

    evidence = build_existing_assembly_subset_seed_evidence(
        plan=plan,
        context=context,
        catalog=catalog,
        project_id="project03",
        assembly_path=assembly,
        component_inventory_path=inventory,
    )

    assert evidence["moduleTokenCounts"] == {"AA00": 1, "AB00": 1}
    assert len(
        evidence["sourceExistingAssembly"]["unmatchedTopLevelComponents"]
    ) == 1
    validate_external_manifest_seed_evidence(evidence, plan=plan)
