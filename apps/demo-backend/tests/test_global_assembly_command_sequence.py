import json
from pathlib import Path
import shutil

from demo_backend.global_assembly_workbench import (
    apply_command,
    apply_command_sequence,
    context_path,
    create_context,
    load_global_catalog,
    preview_command,
    undo_latest_command,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def definition(catalog, token):
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(alias["moduleToken"] == token for alias in row["projectAliases"])
    )


def test_ordered_sequence_commits_every_turn_and_is_resumable(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-ready"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    create_context(
        WORKSPACE,
        {"contextId": "sequence-ready", "displayName": "sequence", "overwrite": True},
    )
    a600 = definition(catalog, "A600")
    a800 = definition(catalog, "A800")
    result = apply_command_sequence(
        WORKSPACE,
        "sequence-ready",
        {
            "confirmed": True,
            "commands": [
                {"requirement": "请先安装项目02 A600箱体", "moduleDefinitionId": a600["moduleDefinitionId"]},
                {"requirement": "然后安装项目02 A800传输模组", "moduleDefinitionId": a800["moduleDefinitionId"]},
            ],
        },
    )
    assert result["success"] is True
    assert result["turnCount"] == 2
    assert result["finalContextRevision"] == 2
    saved = json.loads(context_path(WORKSPACE, "sequence-ready").read_text(encoding="utf-8"))
    assert len(saved["instances"]) == 2
    ledger = json.loads(
        context_path(WORKSPACE, "sequence-ready")
        .with_suffix(".conversation.json")
        .read_text(encoding="utf-8")
    )
    assert [turn["contextRevision"] for turn in ledger["turns"]] == [1, 2]
    shutil.rmtree(WORKSPACE / context_dir)


def test_ambiguous_sequence_is_atomic_and_writes_nothing(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-ambiguous"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    create_context(
        WORKSPACE,
        {"contextId": "sequence-ambiguous", "overwrite": True},
    )
    a600 = definition(catalog, "A600")
    before = context_path(WORKSPACE, "sequence-ambiguous").read_bytes()
    result = apply_command_sequence(
        WORKSPACE,
        "sequence-ambiguous",
        {
            "confirmed": True,
            "commands": [
                {"requirement": "安装A600", "moduleDefinitionId": a600["moduleDefinitionId"]},
                {"requirement": "再安装一个完全未知的神秘模组"},
            ],
        },
    )
    assert result["success"] is False
    assert result["contextModified"] is False
    assert result["failedAtOrder"] == 2
    assert context_path(WORKSPACE, "sequence-ambiguous").read_bytes() == before
    shutil.rmtree(WORKSPACE / context_dir)


def test_zero_padded_chinese_project_number_disambiguates_same_module_token(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-project05"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    create_context(
        WORKSPACE,
        {"contextId": "sequence-project05", "overwrite": True},
    )
    result = apply_command_sequence(
        WORKSPACE,
        "sequence-project05",
        {
            "confirmed": True,
            "commands": [{"requirement": "先安装项目05 A000机架基座"}],
        },
    )
    assert result["success"] is True
    instance = result["context"]["instances"][0]
    assert instance["moduleDefinitionId"].startswith("cad/fl9c254098a000-001/")
    shutil.rmtree(WORKSPACE / context_dir)


def test_existing_module_mention_is_used_as_target_hint_not_new_module(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-target-hint"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    a000 = definition(catalog, "A000")
    # Select the Project05 definitions explicitly for the base because A000 is
    # intentionally reused by several project families.
    a000 = next(
        row
        for row in catalog["moduleDefinitions"]
        if row["moduleDefinitionId"].startswith("cad/fl9c254098a000-001/")
    )
    create_context(WORKSPACE, {"contextId": "sequence-target-hint", "overwrite": True})
    result = apply_command_sequence(
        WORKSPACE,
        "sequence-target-hint",
        {
            "confirmed": True,
            "commands": [
                {"requirement": "安装项目05 A000", "moduleDefinitionId": a000["moduleDefinitionId"]},
                {"requirement": "在A000上安装项目05 M000产品定位CCD模组"},
            ],
        },
    )
    assert result["success"] is True
    assert result["turns"][1]["resolution"] == "unique_new_module_with_existing_target_hint"
    assert result["context"]["instances"][1]["moduleDefinitionId"].startswith(
        "cad/fl9c254098m000-001/"
    )
    shutil.rmtree(WORKSPACE / context_dir)


def test_incompatible_cross_project_scanner_exposes_adapter_fallback(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-adapter-fallback"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    jj00 = definition(catalog, "JJ00")
    ai00 = definition(catalog, "AI00")
    create_context(
        WORKSPACE,
        {"contextId": "sequence-adapter-fallback", "overwrite": True},
    )
    base_preview = preview_command(
        WORKSPACE,
        "sequence-adapter-fallback",
        {
            "requirement": "请先建立项目01的设备机架和固定安装环境。",
            "moduleDefinitionId": jj00["moduleDefinitionId"],
        },
    )
    apply_command(
        WORKSPACE,
        "sequence-adapter-fallback",
        {
            "preview": base_preview,
            "previewDigest": base_preview["previewDigest"],
            "confirmed": True,
        },
    )

    preview = preview_command(
        WORKSPACE,
        "sequence-adapter-fallback",
        {
            "requirement": "在当前机架上安装项目03的条码扫描模组。",
            "moduleDefinitionId": ai00["moduleDefinitionId"],
        },
    )

    assert preview["status"] == "blocked"
    assert preview["proposedPatch"] is None
    assert preview["cadExecution"]["status"] == "not_executed"
    assert preview["fallbackPolicy"] == {
        "automaticFallbackExecutionAllowed": False,
        "requiresEngineerSelection": True,
        "solidWorksExecuted": False,
        "statement": (
            "直接接口不兼容；系统仅给出可审计的转接或接口评审路线，"
            "不得以原型位姿或近似孔位强行装配。"
        ),
    }
    fallback = preview["engineeringFallbacks"][0]
    assert fallback["kind"] == "physical_adapter_required"
    assert fallback["sourceModule"] == "project03:AI00"
    assert fallback["sourceModuleDefinitionId"] == ai00["moduleDefinitionId"]
    assert fallback["nativeSlotModule"] == "project01:SM00"
    assert fallback["nativeSlotModuleDefinitionId"] == definition(
        catalog, "SM00"
    )["moduleDefinitionId"]
    assert fallback["directCombinationAllowed"] is False
    assert fallback["cadLaunchDecision"] == "fail_closed_before_cad"
    difference = fallback["engineeringDisposition"]["knownLocatingDifferences"][0]
    assert difference["sourceDistanceMeters"] == 0.2
    assert difference["targetDistanceMeters"] == 0.021999999999999992
    assert difference["absoluteDifferenceMeters"] == 0.17800000000000002
    shutil.rmtree(WORKSPACE / context_dir)


def test_latest_unexecuted_turn_can_be_restored_from_revision_snapshot(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-undo"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    frame = definition(catalog, "A600")
    created = create_context(
        WORKSPACE, {"contextId": "sequence-undo", "overwrite": True}
    )["context"]
    preview = preview_command(
        WORKSPACE,
        "sequence-undo",
        {
            "requirement": "请先安装项目02 A600箱体",
            "moduleDefinitionId": frame["moduleDefinitionId"],
        },
    )
    applied = apply_command(
        WORKSPACE,
        "sequence-undo",
        {
            "preview": preview,
            "previewDigest": preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]

    result = undo_latest_command(
        WORKSPACE,
        "sequence-undo",
        {
            "expectedRevision": applied["revision"],
            "expectedContextDigest": applied["contextDigest"],
            "confirmed": True,
        },
    )

    assert result["status"] == "rolled_back"
    assert result["context"] == created
    assert result["rolledBackTurn"]["instanceId"] == applied["instances"][0]["instanceId"]
    ledger = json.loads(
        context_path(WORKSPACE, "sequence-undo")
        .with_suffix(".conversation.json")
        .read_text(encoding="utf-8")
    )
    assert ledger["turns"] == []
    assert len(ledger["rolledBackTurns"]) == 1
    shutil.rmtree(WORKSPACE / context_dir)


def test_rollback_branch_can_reuse_revision_without_snapshot_collision(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-branch-reuse"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    frame = definition(catalog, "A600")
    transport = definition(catalog, "A800")
    create_context(WORKSPACE, {"contextId": "branch-reuse", "overwrite": True})

    first_preview = preview_command(
        WORKSPACE,
        "branch-reuse",
        {
            "requirement": "请先安装项目02 A600箱体",
            "moduleDefinitionId": frame["moduleDefinitionId"],
        },
    )
    first = apply_command(
        WORKSPACE,
        "branch-reuse",
        {
            "preview": first_preview,
            "previewDigest": first_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    undo_latest_command(
        WORKSPACE,
        "branch-reuse",
        {
            "expectedRevision": first["revision"],
            "expectedContextDigest": first["contextDigest"],
            "confirmed": True,
        },
    )

    second_preview = preview_command(
        WORKSPACE,
        "branch-reuse",
        {
            "requirement": "建立设备箱体与安装基座",
            "moduleDefinitionId": frame["moduleDefinitionId"],
        },
    )
    second = apply_command(
        WORKSPACE,
        "branch-reuse",
        {
            "preview": second_preview,
            "previewDigest": second_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert second["revision"] == 1
    assert second["contextDigest"] != first["contextDigest"]

    transport_preview = preview_command(
        WORKSPACE,
        "branch-reuse",
        {
            "requirement": "在当前设备箱体上安装产品传输模组",
            "moduleDefinitionId": transport["moduleDefinitionId"],
        },
    )
    committed = apply_command(
        WORKSPACE,
        "branch-reuse",
        {
            "preview": transport_preview,
            "previewDigest": transport_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]

    assert committed["revision"] == 2
    assert len(committed["instances"]) == 2
    assert len(committed["connections"]) == 1
    assert committed["history"][-1]["sourceContextDigest"] == second["contextDigest"]
    revision_dir = context_path(WORKSPACE, "branch-reuse").parent / "branch-reuse.revisions"
    revision_one = list(revision_dir.glob("revision-000001*.json"))
    assert len(revision_one) == 2
    shutil.rmtree(WORKSPACE / context_dir)


def test_undo_rejects_latest_turn_with_bound_cad_job(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"sequence-{tmp_path.name}-undo-job"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    catalog = load_global_catalog(WORKSPACE)
    frame = definition(catalog, "A600")
    create_context(WORKSPACE, {"contextId": "sequence-undo-job", "overwrite": True})
    preview = preview_command(
        WORKSPACE,
        "sequence-undo-job",
        {
            "requirement": "安装项目02 A600箱体",
            "moduleDefinitionId": frame["moduleDefinitionId"],
        },
    )
    applied = apply_command(
        WORKSPACE,
        "sequence-undo-job",
        {
            "preview": preview,
            "previewDigest": preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    ledger_path = context_path(WORKSPACE, "sequence-undo-job").with_suffix(
        ".conversation.json"
    )
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["turns"][-1]["jobs"] = [{"jobId": "cad-job-1"}]
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="已经绑定CAD任务"):
        undo_latest_command(
            WORKSPACE,
            "sequence-undo-job",
            {
                "expectedRevision": applied["revision"],
                "expectedContextDigest": applied["contextDigest"],
                "confirmed": True,
            },
        )
    assert json.loads(
        context_path(WORKSPACE, "sequence-undo-job").read_text(encoding="utf-8")
    )["revision"] == 1
    shutil.rmtree(WORKSPACE / context_dir)
