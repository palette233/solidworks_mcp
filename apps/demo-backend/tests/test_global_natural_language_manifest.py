import json
from pathlib import Path
import shutil

import pytest

from demo_backend.global_natural_language_manifest import (
    compile_natural_language_manifest_job,
)
from demo_backend.assembly_conversation import load_conversation
from demo_backend.global_assembly_workbench import context_path, load_context
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "context_id,requirements,expected_packets",
    [
        (
            "nl-manifest-three-step",
            [
                "先安装项目05 A000机架基座",
                "然后在A000上安装项目05 G000校准与称重组合模组",
                "最后在A000上安装项目05 F000双读头条码扫描模组",
            ],
            2,
        ),
        (
            "nl-manifest-five-step",
            [
                "先安装项目05 A000机架基座",
                "然后安装项目05 M000产品定位CCD模组",
                "再安装项目05 F000双读头条码扫描模组",
                "随后安装项目05 P000双杯排胶模组",
                "最后安装项目05 G000校准与称重组合模组",
            ],
            4,
        ),
        (
            "nl-manifest-five-step-reordered",
            [
                "先安装项目05 A000机架基座",
                "然后安装项目05 G000校准与称重组合模组",
                "再安装项目05 P000双杯排胶模组",
                "随后安装项目05 F000双读头条码扫描模组",
                "最后安装项目05 M000产品定位CCD模组",
            ],
            4,
        ),
    ],
)
def test_nonfixed_natural_language_order_compiles_directly_to_job(
    tmp_path, monkeypatch, context_id, requirements, expected_packets
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-{context_id}"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": context_id,
            "requirements": requirements,
            "overwrite": True,
            "idempotencyKey": context_id,
        },
        store=store,
    )
    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["packetCount"] == expected_packets
    assert result["job"]["status"] == "queued"
    assert result["job"]["progress"]["totalSteps"] == expected_packets
    assert result["cadStarted"] is False
    assert result["collisionStatus"] == "not_evaluated"
    assert result["timingSeconds"]["totalSeconds"] >= 0
    assert result["timingSeconds"]["phasesSeconds"]["compileTransactionDag"] >= 0
    job = store.load(result["jobId"])
    assert [step["moduleToken"] for step in job["steps"]] == [
        requirement.split("项目05 ", 1)[1].split(" ", 1)[0][:4]
        if "项目05 " in requirement
        else ""
        for requirement in requirements[1:]
    ]
    assert job["plan"]["commandAudit"]["status"] == "complete"
    assert (store._dir(result["jobId"]) / "command-audit.json").is_file()
    assert (store._dir(result["jobId"]) / "timing-report.json").is_file()
    assert (WORKSPACE / context_dir / f"{context_id}.transaction-dag.json").is_file()
    saved_context = load_context(WORKSPACE, context_id)
    conversation = load_conversation(
        context_path(WORKSPACE, context_id), saved_context
    )
    latest_turn = conversation["turns"][-1]
    assert latest_turn["contextRevision"] == saved_context["revision"]
    assert [binding["jobId"] for binding in latest_turn["jobs"]] == [
        result["jobId"]
    ]
    shutil.rmtree(WORKSPACE / context_dir)


def test_project02_portable_release_compiles_without_pose_positioning_standard(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project02-readiness"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project02-readiness",
            "requirements": [
                "先安装项目02 A600箱体",
                "然后安装项目02 A800传输模组",
                "最后安装项目02 A180扫描模组",
            ],
            "overwrite": True,
        },
        store=store,
    )
    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["packetCount"] == 2
    assert result["positioningStandardId"] is None
    assert result["cadStarted"] is False
    assert result["job"]["status"] == "queued"
    context = json.loads(
        (WORKSPACE / context_dir / "nl-project02-readiness.json").read_text(
            encoding="utf-8"
        )
    )
    assert context["relationReleaseBinding"]["releaseId"] == (
        "relation-v30-project02-a800-a180-portable-driving-20261011"
    )
    shutil.rmtree(WORKSPACE / context_dir)


def test_project02_explicit_inferred_standard_compiles_to_queued_job(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project02-standard"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project02-with-positioning-standard",
            "requirements": [
                "先安装项目02 A600箱体",
                "然后安装项目02 A800传输模组",
                "最后安装项目02 A180扫描模组",
            ],
            "positioningStandardId": "project02-inferred-v1",
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["positioningStandardId"] == "project02-inferred-v1"
    assert result["positioningStandard"]["explicitlySelected"] is True
    assert result["packetCount"] == 2
    assert result["cadStarted"] is False
    assert result["job"]["status"] == "queued"
    shutil.rmtree(WORKSPACE / context_dir)


def test_project02_release_bound_spacing_is_blocked_before_cad_by_revoked_a700_driver(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project02-spacing-verify"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v36-project02-nine-addon-portable-driving-20261011/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project02-release-bound-spacing-verify",
            "requirements": [
                "创建项目02的A600箱体基座",
                "在A600箱体上安装A800传输模组",
                "在A600箱体上安装A500标定模组",
                "在A600箱体上安装A700清洁称重模组",
                "验证项目02 A500与A700之间的50毫米距离",
            ],
            "releaseManifestPath": release,
            "positioningStandardId": "project02-inferred-v1",
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is False
    assert result["status"] == "blocked_before_job_creation"
    assert result["cadStarted"] is False
    assert result["jobCreated"] is False
    assert any(
        blocker["code"]
        == "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
        and blocker["moduleToken"] == "A700"
        for blocker in result["blockers"]
    )
    shutil.rmtree(WORKSPACE / context_dir)


def test_project02_explicit_calibrated_a700_fallback_creates_auditable_job(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project02-a700-fallback"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    template_id = (
        "template/project02/a700-to-a600-nonanchor-driving-v1/32804d30f3"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project02-explicit-a700-fallback",
            "requirements": [
                "创建项目02的A600箱体基座",
                "在A600箱体上安装A800传输模组",
                "在A600箱体上安装A180扫描模组",
                "在A600箱体上安装A500标定模组",
                "在A600箱体上安装A700清洁称重模组",
            ],
            "releaseManifestPath": (
                "demo/global_assembly_catalog/releases/"
                "relation-v33-project02-five-addon-portable-driving-20261011/"
                "release-manifest.json"
            ),
            "positioningStandardId": "project02-inferred-v1",
            "drivingStrategySelections": [
                {
                    "globalTemplateId": template_id,
                    "strategyId": (
                        "project02/a700/prototype-calibrated-static-snapshot-v1"
                    ),
                    "confirmed": True,
                }
            ],
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    fallback_step = next(
        step for step in job["plan"]["steps"] if step["moduleToken"] == "A700"
    )
    assert fallback_step["executionStrategy"] == (
        "calibrated_static_snapshot_insert"
    )
    manifest = json.loads(
        Path(result["manifestPath"]).read_text(encoding="utf-8-sig")
    )
    packet = manifest["packets"][3]
    assert packet["drivingExecutionOverride"]["portable"] is False
    assert packet["drivingExecutionOverride"]["scope"] == "project02-only"
    shutil.rmtree(WORKSPACE / context_dir)


def test_project01_release_bound_nonstar_graph_compiles_to_queued_job(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project01-release"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v10-project01-combination-driving-20261011/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project01-release-bound-nonstar",
            "requirements": [
                "先安装项目01 JJ00机架基座",
                "在JJ00上安装项目01 SS00输送模组",
                "在JJ00上安装项目01 GN00模组",
                "让项目01 GN00防转面与SS00基准面保持平行",
            ],
            "releaseManifestPath": release,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["releaseManifestPath"] == release
    assert result["packetCount"] == 2
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    assert job["plan"]["commandAudit"]["status"] == "complete"
    assert [step["moduleToken"] for step in job["steps"]] == ["SS00", "GN00"]
    assert job["plan"]["steps"][1]["connectionCount"] == 2
    shutil.rmtree(WORKSPACE / context_dir)


def test_project05_release_bound_alternative_wording_compiles_to_queued_job(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project05-release"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v7-project05-driving-independent-20261011/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project05-release-bound-wording",
            "requirements": [
                "请先建立项目05 A000机架基础环境",
                "随后把项目05 D000上层输送模组安装到A000",
            ],
            "releaseManifestPath": release,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["releaseManifestPath"] == release
    assert result["packetCount"] == 1
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    assert job["plan"]["commandAudit"]["status"] == "complete"
    assert [step["moduleToken"] for step in job["steps"]] == ["D000"]
    shutil.rmtree(WORKSPACE / context_dir)


def test_project01_base_cross_project_complete_chain_compiles_without_cad(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project01-cross-project-chain"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project01-cross-project-complete-chain",
            "requirements": [
                "请先建立项目01 JJ00设备箱体与固定安装环境。",
                "随后把项目03 AE00产品传输模组安装到当前固定环境。",
                "在传输线入口附近增加项目01 SM00条码扫描模组。",
                "在当前设备操作区域增加项目03 AH00喷嘴校准模组。",
            ],
            "releaseManifestPath": release,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["releaseManifestPath"] == release
    assert result["packetCount"] == 3
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    assert job["plan"]["commandAudit"]["status"] == "complete"
    assert [step["moduleToken"] for step in job["steps"]] == [
        "AE00",
        "SM00",
        "AH00",
    ]
    assert all(step["connectionCount"] == 1 for step in job["plan"]["steps"])
    shutil.rmtree(WORKSPACE / context_dir)


def test_project05_engineering_language_roles_compile_without_internal_tokens(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project05-role-language"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v28-project05-all-eight-addon-portable-driving-20261011/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project05-role-language-chain",
            "requirements": [
                "请先建立项目05的设备机架和固定安装环境。",
                "在当前机架上安装项目05的产品传输模组。",
                "在传输线入口附近增加项目05的双读头条码扫描模组。",
                "在当前设备上增加项目05的喷嘴校准模组。",
                "在当前机架上增加项目05的产品定位CCD模组。",
            ],
            "releaseManifestPath": release,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["packetCount"] == 4
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert [step["moduleToken"] for step in job["steps"]] == [
        "D000",
        "F000",
        "G000",
        "M000",
    ]
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    assert job["plan"]["commandAudit"]["status"] == "complete"
    shutil.rmtree(WORKSPACE / context_dir)


def test_project03_expanded_cross_project_eight_module_chain_compiles(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project03-expanded-chain"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v62-project03-expanded-cross-project-chain-driving-20261014/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project03-expanded-cross-project-chain",
            "requirements": [
                "请先建立项目03 AA00设备箱体与固定安装环境。",
                "随后把项目01 SS00产品传输模组安装到当前基座。",
                "在传输线入口附近增加项目03 AI00条码扫描模组。",
                "在设备操作区域增加项目01 BD00喷嘴校准模组。",
                "在当前基座上增加项目03 AD00定位模组。",
                "在当前基座上增加项目03 AJ00供胶系统。",
                "在当前基座上增加项目03 AG00清洁称重模组。",
                "最后在当前基座上安装项目03 AB00龙门点胶模组。",
            ],
            "releaseManifestPath": release,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["status"] == "job_created_not_started"
    assert result["packetCount"] == 7
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert [step["moduleToken"] for step in job["steps"]] == [
        "SS00",
        "AI00",
        "BD00",
        "AD00",
        "AJ00",
        "AG00",
        "AB00",
    ]
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    assert job["plan"]["commandAudit"]["status"] == "complete"
    assert all(step["connectionCount"] == 1 for step in job["plan"]["steps"])
    shutil.rmtree(WORKSPACE / context_dir)


def test_project03_shuffled_eight_module_requirements_auto_order_to_validated_chain(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"{tmp_path.name}-project03-auto-order-chain"
    monkeypatch.setattr(
        "demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    release = (
        "demo/global_assembly_catalog/releases/"
        "relation-v62-project03-expanded-cross-project-chain-driving-20261014/"
        "release-manifest.json"
    )
    result = compile_natural_language_manifest_job(
        WORKSPACE,
        {
            "contextId": "nl-project03-expanded-cross-project-auto-order",
            "requirements": [
                "最后增加项目03 AB00龙门点胶模组。",
                "增加项目03 AG00清洁称重模组。",
                "安装项目01 SS00产品传输模组。",
                "建立项目03 AA00设备箱体与固定安装环境。",
                "增加项目03 AJ00供胶系统。",
                "增加项目01 BD00喷嘴校准模组。",
                "增加项目03 AI00条码扫描模组。",
                "增加项目03 AD00定位模组。",
            ],
            "releaseManifestPath": release,
            "autoOrderByReleasedDependencies": True,
            "overwrite": True,
        },
        store=store,
    )

    assert result["success"] is True
    assert result["dependencyOrdering"]["status"] == "ready"
    assert result["dependencyOrdering"]["reordered"] is True
    assert result["cadStarted"] is False
    job = store.load(result["jobId"])
    assert [step["moduleToken"] for step in job["steps"]] == [
        "SS00",
        "AI00",
        "BD00",
        "AD00",
        "AJ00",
        "AG00",
        "AB00",
    ]
    assert job["plan"]["releaseAuthority"]["status"] == "verified"
    shutil.rmtree(WORKSPACE / context_dir)
