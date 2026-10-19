import json
from pathlib import Path
from types import SimpleNamespace

from demo_backend.semantic_assembly_cad_runner import (
    build_live_cad_step_specs,
    live_cad_step_runner,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


def fixtures(tmp_path: Path):
    base = tmp_path / "A600.SLDASM"
    base.write_bytes(b"base")
    graph = tmp_path / "a800.json"
    graph.write_text("{}", encoding="utf-8")
    evidence = tmp_path / "a800.result.json"
    evidence.write_text(
        json.dumps(
            {
                "effectiveGraphPath": str(graph),
                "targetModuleToken": "A800",
            }
        ),
        encoding="utf-8",
    )
    closure = {
        "steps": [
            {"moduleToken": "A600", "assemblyPath": str(base)},
            {"moduleToken": "A800", "evidencePath": str(evidence)},
        ]
    }
    return base, closure


def plan():
    return {"steps": [{"stepId": "step-01-a800", "moduleToken": "A800"}]}


def test_builds_specs_from_durable_cad_evidence(tmp_path: Path):
    base, closure = fixtures(tmp_path)
    resolved_base, specs = build_live_cad_step_specs(closure)
    assert resolved_base == base.resolve()
    assert specs["A800"][0]["targetModuleToken"] == "A800"


def test_requested_subsequence_does_not_validate_unrelated_broken_step(tmp_path: Path):
    base, closure = fixtures(tmp_path)
    broken = tmp_path / "broken.result.json"
    broken.write_text("{}", encoding="utf-8")
    closure["steps"].append({"moduleToken": "A100", "evidencePath": str(broken)})
    resolved_base, specs = build_live_cad_step_specs(
        closure,
        required_tokens={"A800"},
    )
    assert resolved_base == base.resolve()
    assert set(specs) == {"A800"}


def test_a100_compiles_to_insert_then_rigid_replacement(tmp_path: Path):
    base, closure = fixtures(tmp_path)
    directory = tmp_path / "a100"
    directory.mkdir()
    graph = directory / "a100-effective.json"
    graph.write_text("{}", encoding="utf-8")
    insertion = directory / "step06_A600_A800_A180_A700_A300_A500_A100_V1.context-insert.result.json"
    insertion.write_text(
        json.dumps(
            {"effectiveGraphPath": str(graph), "targetModuleToken": "A100"}
        ),
        encoding="utf-8",
    )
    replacement = directory / "A100_WITH_A150_SLOT0_RIGID_V5_CLEAN.SLDASM"
    replacement.write_bytes(b"replacement")
    replacement.with_suffix(".replacement-result.json").write_text(
        json.dumps(
            {
                "success": True,
                "finalOpenNeedsRegen": False,
                "finalRebuildState": {"NeedsRebuild": False},
            }
        ),
        encoding="utf-8",
    )
    (directory / "FL9A24D062A100.001.prototype-health-diagnostics.json").write_text(
        json.dumps(
            {
                "health": {
                    "ReadyForVerificationGate": True,
                    "HasBlockingIssues": False,
                    "ActionableDiagnostics": {"CurrentIssues": []},
                }
            }
        ),
        encoding="utf-8",
    )
    final = directory / "final.SLDASM"
    final.write_bytes(b"final")
    final_evidence = directory / "final.json"
    final_evidence.write_text("{}", encoding="utf-8")
    closure["steps"].append(
        {
            "moduleToken": "A100",
            "assemblyPath": str(final),
            "evidencePath": str(final_evidence),
        }
    )
    _, specs = build_live_cad_step_specs(closure, required_tokens={"A100"})
    assert [action["actionKind"] for action in specs["A100"]] == [
        "context_incremental",
        "replace_top_level_and_set_rigid",
    ]
    assert specs["A100"][1]["replacementFilePath"] == str(replacement.resolve())


def test_a100_rejects_replacement_that_still_needs_regen(tmp_path: Path):
    _, closure = fixtures(tmp_path)
    directory = tmp_path / "a100"
    directory.mkdir()
    graph = directory / "a100-effective.json"
    graph.write_text("{}", encoding="utf-8")
    insertion = directory / "step06_A600_A800_A180_A700_A300_A500_A100_V1.context-insert.result.json"
    insertion.write_text(
        json.dumps({"effectiveGraphPath": str(graph), "targetModuleToken": "A100"}),
        encoding="utf-8",
    )
    replacement = directory / "A100_WITH_A150_SLOT0_RIGID_V5_CLEAN.SLDASM"
    replacement.write_bytes(b"replacement")
    replacement.with_suffix(".replacement-result.json").write_text(
        json.dumps(
            {
                "success": False,
                "finalOpenNeedsRegen": True,
                "finalRebuildState": {"NeedsRebuild": True},
            }
        ),
        encoding="utf-8",
    )
    (directory / "FL9A24D062A100.001.prototype-health-diagnostics.json").write_text(
        json.dumps(
            {
                "health": {
                    "ReadyForVerificationGate": True,
                    "HasBlockingIssues": False,
                    "ActionableDiagnostics": {"CurrentIssues": []},
                }
            }
        ),
        encoding="utf-8",
    )
    final = directory / "final.SLDASM"
    final.write_bytes(b"final")
    closure["steps"].append(
        {"moduleToken": "A100", "assemblyPath": str(final), "evidencePath": "unused"}
    )

    try:
        build_live_cad_step_specs(closure, required_tokens={"A100"})
    except Exception as exc:
        assert "NeedsRegen" in str(exc)
    else:
        raise AssertionError("A dirty A100 replacement must be rejected before CAD execution")


def test_live_runner_commits_only_after_explicit_hard_gate(tmp_path: Path):
    _, closure = fixtures(tmp_path)
    workspace = tmp_path / "workspace"
    script = workspace / "scripts/run_context_incremental_insert.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake", encoding="utf-8")
    executable = tmp_path / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    store = DurableAssemblyJobStore(tmp_path / "jobs")

    def command_runner(command, timeout):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    gate_file = tmp_path / "gate.json"
    gate_file.write_text("{}", encoding="utf-8")
    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=workspace,
        executable=executable,
        hard_gate=lambda job, step, output, previous: {
            "accepted": True,
            "evidencePath": str(gate_file),
        },
        command_runner=command_runner,
    )
    job = store.create(plan(), execution_mode="live_cad")
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    assert result["status"] == "succeeded"
    assert Path(result["lastCommittedCheckpoint"]["assemblyPath"]).is_file()


def test_live_runner_quarantines_cad_output_when_gate_rejects(tmp_path: Path):
    _, closure = fixtures(tmp_path)
    workspace = tmp_path / "workspace"
    script = workspace / "scripts/run_context_incremental_insert.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake", encoding="utf-8")
    executable = tmp_path / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    store = DurableAssemblyJobStore(tmp_path / "jobs")

    def command_runner(command, timeout):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"unsafe")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *args: {"accepted": False, "message": "collision"},
        command_runner=command_runner,
    )
    job = store.create(plan(), execution_mode="live_cad")
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    assert result["status"] == "failed"
    assert Path(result["rollback"]["quarantinedArtifactPath"]).is_file()


def test_demo_profile_commits_without_invoking_collision_gate(tmp_path: Path):
    _, closure = fixtures(tmp_path)
    workspace = tmp_path / "workspace"
    script = workspace / "scripts/run_context_incremental_insert.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake", encoding="utf-8")
    executable = tmp_path / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    store = DurableAssemblyJobStore(tmp_path / "jobs")

    def command_runner(command, timeout):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    def forbidden_gate(*args):
        raise AssertionError("demo profile must not invoke B-rep collision gate")

    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=workspace,
        executable=executable,
        hard_gate=forbidden_gate,
        command_runner=command_runner,
    )
    job = store.create(
        {**plan(), "validationProfile": "demo"}, execution_mode="live_cad"
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])

    assert result["status"] == "succeeded"
    assert result["assemblyStatus"] == "assembled"
    assert result["collisionStatus"] == "not_evaluated"
    assert result["demoCheckpoint"]["moduleToken"] == "A800"
    assert result["engineeringCheckpoint"] is None
    assert result["lastCommittedCheckpoint"]["validationEvidenceKind"] == "cad_save_reopen"


def test_engineering_profile_records_collision_checkpoint(tmp_path: Path):
    _, closure = fixtures(tmp_path)
    workspace = tmp_path / "workspace"
    script = workspace / "scripts/run_context_incremental_insert.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fake", encoding="utf-8")
    executable = tmp_path / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    evidence = tmp_path / "brep.json"
    evidence.write_text("{}", encoding="utf-8")
    store = DurableAssemblyJobStore(tmp_path / "jobs")

    def command_runner(command, timeout):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *args: {"accepted": True, "evidencePath": str(evidence)},
        command_runner=command_runner,
    )
    job = store.create(
        {**plan(), "validationProfile": "engineering"}, execution_mode="live_cad"
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])

    assert result["collisionStatus"] == "passed"
    assert result["engineeringCheckpoint"]["moduleToken"] == "A800"
    assert result["engineeringCheckpoint"]["validationEvidenceKind"] == "collision_hard_gate"
