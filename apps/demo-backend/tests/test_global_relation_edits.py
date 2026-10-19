import json
import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.global_assembly_transactions import (
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_assembly_context import context_digest
from demo_backend.global_relation_edits import (
    GlobalRelationEditError,
    apply_global_relation_edit,
    preview_global_relation_edit,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "global_relation"
CATALOG = json.loads(
    (
        FIXTURES / "global_module_catalog.refresh-preview.json"
    ).read_text(encoding="utf-8")
)
CONTEXT = json.loads(
    (
        FIXTURES / "project02-full-static-graph-catalog-refresh-v1.json"
    ).read_text(encoding="utf-8")
)
RELATION_V2_CATALOG = json.loads(
    (
        FIXTURES / "global_module_catalog.relation-v2-preview.json"
    ).read_text(encoding="utf-8")
)
RELATION_V2_CONTEXT = json.loads(
    (
        FIXTURES / "project02-full-static-graph-relation-v2-v1.json"
    ).read_text(encoding="utf-8")
)


def instance(token):
    folded = token.casefold()
    return next(
        row["instanceId"]
        for row in CONTEXT["instances"]
        if folded in str(row["moduleDefinitionId"]).casefold()
    )


def test_existing_instances_can_add_exact_standalone_distance_relation():
    preview = preview_global_relation_edit(
        CATALOG,
        CONTEXT,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
        },
    )

    assert preview["status"] == "ready"
    assert len(preview["connectionCandidates"]) == 1
    assert preview["proposedPatch"]["operation"] == "add_relation"
    assert preview["proposedPatch"]["after"]["relationIntent"][
        "primaryRelation"
    ] == "spacing"


def test_relation_edit_compiles_as_post_insert_cad_checked_transaction():
    preview = preview_global_relation_edit(
        CATALOG,
        CONTEXT,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
        },
    )
    updated = apply_global_relation_edit(
        CONTEXT,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )
    dag = compile_global_assembly_transaction_dag(CATALOG, updated)
    relation_step = next(step for step in dag["steps"] if step["operation"] == "ADD_RELATION")

    assert len(updated["connections"]) == len(CONTEXT["connections"]) + 1
    assert relation_step["status"] == "compiled_requires_cad_verification"
    assert relation_step["constraintAssessment"]["requiresFullPlacementClosure"] is False
    assert relation_step["constraintAssessment"]["overconstraintMustBeCheckedByCad"] is True
    assert "POST_INSERT_CONNECTION_NOT_SCHEDULED" not in {
        blocker["code"] for blocker in dag["blockers"]
    }


def test_unregistered_60mm_relation_fails_closed():
    preview = preview_global_relation_edit(
        CATALOG,
        CONTEXT,
        {
            "operation": "add",
            "requirement": "让A500与A700保持60mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
        },
    )
    reason_codes = {
        reason["code"]
        for row in preview["relationCandidateAssessments"]
        for reason in (row.get("relationAssessment") or {}).get("reasons") or []
    }
    assert preview["status"] == "blocked"
    assert "REQUESTED_DISTANCE_NOT_SUPPORTED_BY_TEMPLATE" in reason_codes


def test_relation_delete_round_trip_and_confirmation_gate():
    add = preview_global_relation_edit(
        CATALOG,
        CONTEXT,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
        },
    )
    with pytest.raises(GlobalRelationEditError, match="confirmed=true"):
        apply_global_relation_edit(
            CONTEXT,
            add,
            preview_digest=add["previewDigest"],
            confirmed=False,
        )
    updated = apply_global_relation_edit(
        CONTEXT, add, preview_digest=add["previewDigest"], confirmed=True
    )
    connection_id = add["proposedPatch"]["connectionId"]
    delete = preview_global_relation_edit(
        CATALOG,
        updated,
        {"operation": "delete", "connectionId": connection_id},
    )
    restored = apply_global_relation_edit(
        updated,
        delete,
        preview_digest=delete["previewDigest"],
        confirmed=True,
    )

    assert delete["status"] == "ready"
    assert len(restored["connections"]) == len(CONTEXT["connections"])
    assert restored["history"][-1]["operation"] == "delete_relation"


def test_existing_instances_can_register_validation_only_spacing_relation():
    def relation_v2_instance(token):
        folded = token.casefold()
        return next(
            row["instanceId"]
            for row in RELATION_V2_CONTEXT["instances"]
            if folded in str(row["moduleDefinitionId"]).casefold()
        )

    template = next(
        row
        for row in RELATION_V2_CATALOG["connectionTemplates"]
        if row.get("legacyTemplateId") == "A500_to_A700_source_spacing"
    )
    ports = {
        row["interfaceType"]: row["globalPortId"]
        for row in RELATION_V2_CATALOG["semanticPorts"]
        if row["globalPortId"] in set(template["candidatePortIdsA"] + template["candidatePortIdsB"])
    }
    preview = preview_global_relation_edit(
        RELATION_V2_CATALOG,
        RELATION_V2_CONTEXT,
        {
            "operation": "verify",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": relation_v2_instance("a500"),
            "instanceBId": relation_v2_instance("a700"),
            "globalTemplateId": template["globalTemplateId"],
            "portAId": next(
                value for value in template["candidatePortIdsA"] if "a500-a700" in value
            ),
            "portBId": next(
                value for value in template["candidatePortIdsB"] if "a700-a500" in value
            ),
        },
    )
    assert preview["status"] == "ready"
    assert preview["proposedPatch"]["operation"] == "verify_relation"
    updated = apply_global_relation_edit(
        RELATION_V2_CONTEXT,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )
    dag = compile_global_assembly_transaction_dag(RELATION_V2_CATALOG, updated)
    relation_step = next(
        step for step in dag["steps"] if step["operation"] == "VERIFY_RELATION"
    )
    assert relation_step["status"] == "ready_for_relation_verification"
    assert relation_step["constraintAssessment"]["overconstraintMustBeCheckedByCad"] is False


def test_release_bound_relation_edit_only_accepts_authorized_template():
    bound_context = deepcopy(CONTEXT)
    bound_context["relationReleaseBinding"] = {
        "releaseId": "test-release",
        "releaseDigest": "0" * 64,
        "releaseManifestPath": "demo/test-release/release.json",
        "catalogDigest": CATALOG["catalogDigest"],
        "authorizedDrivingTemplateIds": ["template/not-the-spacing-template"],
    }
    bound_context["contextDigest"] = context_digest(bound_context)

    preview = preview_global_relation_edit(
        CATALOG,
        bound_context,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
            "allowedTemplateIds": bound_context["relationReleaseBinding"][
                "authorizedDrivingTemplateIds"
            ],
        },
    )

    assert preview["status"] == "blocked"
    assert preview["relationReleaseBinding"] == bound_context["relationReleaseBinding"]
    assert "RELATION_TEMPLATE_NOT_AUTHORIZED_BY_RELEASE" in {
        row["code"] for row in preview["blockers"]
    }


def test_release_binding_change_between_preview_and_apply_is_rejected():
    unrestricted = preview_global_relation_edit(
        CATALOG,
        CONTEXT,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
        },
    )
    bound_context = deepcopy(CONTEXT)
    bound_context["relationReleaseBinding"] = {
        "releaseId": "test-release",
        "releaseDigest": "0" * 64,
        "releaseManifestPath": "demo/test-release/release.json",
        "catalogDigest": CATALOG["catalogDigest"],
        "authorizedDrivingTemplateIds": [
            unrestricted["connectionCandidates"][0]["globalTemplateId"]
        ],
    }
    bound_context["contextDigest"] = context_digest(bound_context)
    preview = preview_global_relation_edit(
        CATALOG,
        bound_context,
        {
            "operation": "add",
            "requirement": "让A500与A700保持50mm间距",
            "instanceAId": instance("a500"),
            "instanceBId": instance("a700"),
            "allowedTemplateIds": bound_context["relationReleaseBinding"][
                "authorizedDrivingTemplateIds"
            ],
        },
    )
    tampered = deepcopy(preview)
    tampered["relationReleaseBinding"]["releaseId"] = "another-release"
    tampered["previewDigest"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in tampered.items() if key != "previewDigest"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(GlobalRelationEditError, match="发布绑定不一致"):
        apply_global_relation_edit(
            bound_context,
            tampered,
            preview_digest=tampered["previewDigest"],
            confirmed=True,
        )
