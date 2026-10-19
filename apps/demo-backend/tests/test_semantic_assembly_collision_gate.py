import json
from pathlib import Path
from types import SimpleNamespace

from demo_backend.brep_evidence_cache import build_cache_entry, build_pair_fingerprint
from demo_backend.semantic_assembly_collision_gate import (
    canonical_pair,
    evaluate_pair_local_collision_gate,
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


def component(name: str, path: Path, x: float, box):
    return {
        "Name": name,
        "Path": str(path),
        "Translation": [x, 0, 0],
        "XAxis": [1, 0, 0],
        "YAxis": [0, 1, 0],
        "ZAxis": [0, 0, 1],
        "BoundingBoxWorld": box,
        "ReferencedConfiguration": "Default",
    }


def test_strict_pairs_skip_brep_and_overlaps_require_exact(tmp_path: Path):
    a = tmp_path / "A200.SLDASM"
    b = tmp_path / "A600.SLDASM"
    c = tmp_path / "A800.SLDASM"
    for path in (a, b, c):
        path.write_bytes(path.stem.encode())
    payload = {
        "components": [
            component("FL9A24D062A200.001-1", a, 0, [0, 0, 0, 1, 1, 1]),
            component("FL9A24D062A600.001-1", b, 0.5, [0.5, 0, 0, 2, 1, 1]),
            component("FL9A24D062A800.001-1", c, 3, [3, 0, 0, 4, 1, 1]),
        ]
    }
    result = evaluate_pair_local_collision_gate(payload, "A200")
    assert result["strictAabbAcceptedCount"] == 1
    assert result["unresolvedExactPairCount"] == 1
    assert result["accepted"] is False


def test_matching_pair_cache_closes_overlapping_pair(tmp_path: Path):
    a = tmp_path / "A200.SLDASM"
    b = tmp_path / "A600.SLDASM"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    first = component("FL9A24D062A200.001-1", a, 0, [0, 0, 0, 1, 1, 1])
    second = component("FL9A24D062A600.001-1", b, 0.5, [0.5, 0, 0, 2, 1, 1])
    evidence = {
        "ExactCheckComplete": True,
        "FailedBodyPairCount": 0,
        "HasInterference": False,
    }
    evidence_path = tmp_path / "exact.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    fingerprint = build_pair_fingerprint(first, second, policy="zeroInterference")
    entry = build_cache_entry(fingerprint, evidence_path, evidence)
    result = evaluate_pair_local_collision_gate(
        {"components": [first, second]},
        "A200",
        cache_manifest={"entries": [entry]},
    )
    assert result["cacheAcceptedCount"] == 1
    assert result["accepted"] is True


def test_token_baseline_and_cache_survive_runtime_instance_suffix_change(tmp_path: Path):
    first_file = tmp_path / "D000.SLDASM"
    second_file = tmp_path / "K000.SLDASM"
    baseline = tmp_path / "prototype-baseline.json"
    evidence_path = tmp_path / "exact.json"
    first_file.write_bytes(b"d000")
    second_file.write_bytes(b"k000")
    baseline.write_text("{}", encoding="utf-8")
    evidence = {
        "ExactCheckComplete": True,
        "FailedBodyPairCount": 0,
        "HasInterference": True,
        "Acceptance": {"Accepted": True},
    }
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    original_first = component(
        "FL9C254098D000.001-1", first_file, 0, [0, 0, 0, 1, 1, 1]
    )
    original_second = component(
        "FL9C254098K000.001-1", second_file, 0.5, [0.5, 0, 0, 2, 1, 1]
    )
    fingerprint = build_pair_fingerprint(
        original_first,
        original_second,
        policy="noNewInterferenceOverAcceptedBaseline",
        baseline_path=baseline,
    )
    entry = build_cache_entry(fingerprint, evidence_path, evidence)
    renamed_first = {**original_first, "Name": "FL9C254098D000.001-7"}
    renamed_second = {**original_second, "Name": "FL9C254098K000.001-4"}

    result = evaluate_pair_local_collision_gate(
        {"components": [renamed_first, renamed_second]},
        "D000",
        cache_manifest={"entries": [entry]},
        accepted_baselines={canonical_pair("D000", "K000"): baseline},
    )

    assert result["accepted"] is True
    assert result["cacheAcceptedCount"] == 1
    assert result["pairs"][0]["policy"] == "noNewInterferenceOverAcceptedBaseline"


def test_multi_instance_insert_checks_pair_between_inserted_instances(tmp_path: Path):
    first_file = tmp_path / "T401-1.SLDASM"
    second_file = tmp_path / "T401-2.SLDASM"
    first_file.write_bytes(b"first")
    second_file.write_bytes(b"second")
    first = component("T401AA-07388-0-1", first_file, 0, [0, 0, 0, 1, 1, 1])
    second = component("T401AA-07388-0-2", second_file, 3, [3, 0, 0, 4, 1, 1])
    result = evaluate_pair_local_collision_gate(
        {"components": [first, second]},
        "T401",
    )
    assert result["pairCount"] == 1
    assert result["strictAabbAcceptedCount"] == 1
    assert result["accepted"] is True


def test_project05_multi_member_b000_stage_includes_z000(tmp_path: Path):
    files = {token: tmp_path / f"{token}.SLDASM" for token in ("B000", "Z000", "D000")}
    for token, path in files.items():
        path.write_bytes(token.encode())
    payload = {
        "components": [
            component("FL9C254098B000.001-1", files["B000"], 0, [0, 0, 0, 1, 1, 1]),
            component("FL9C254098Z000.001-1", files["Z000"], 3, [3, 0, 0, 4, 1, 1]),
            component("FL9C254098D000.001-1", files["D000"], 6, [6, 0, 0, 7, 1, 1]),
        ]
    }
    result = evaluate_pair_local_collision_gate(
        payload,
        "B000",
        inserted_module_tokens={"B000", "Z000"},
    )
    assert result["insertedModuleTokens"] == ["B000", "Z000"]
    assert result["pairCount"] == 3
    assert result["strictAabbAcceptedCount"] == 3
    assert result["accepted"] is True


def test_declared_installation_contact_is_explicitly_accepted(tmp_path: Path):
    frame = tmp_path / "A000.SLDASM"
    transport = tmp_path / "D000.SLDASM"
    frame.write_bytes(b"frame")
    transport.write_bytes(b"transport")
    result = evaluate_pair_local_collision_gate(
        {
            "components": [
                component("FL9C254098A000.001-1", frame, 0, [0, 0, 0, 2, 2, 1]),
                component("FL9C254098D000.001-1", transport, 0, [1, 0, 0, 3, 2, 1]),
            ]
        },
        "D000",
        accepted_contact_token_pairs={("A000", "D000")},
    )
    assert result["accepted"] is True
    assert result["installationContactAcceptedCount"] == 1
    assert result["pairs"][0]["method"] == "declared-installation-contact"


def test_live_gate_runs_exact_only_for_cache_miss_then_persists_cache(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    first_file = tmp_path / "A200.SLDASM"
    second_file = tmp_path / "A600.SLDASM"
    first_file.write_bytes(b"a200")
    second_file.write_bytes(b"a600")
    first = component("FL9A24D062A200.001-1", first_file, 0, [0, 0, 0, 1, 1, 1])
    second = component("FL9A24D062A600.001-1", second_file, 0.5, [0.5, 0, 0, 2, 1, 1])
    calls = []

    def command_runner(command, timeout):
        calls.append(command)
        if "capture_top_level_component_poses.py" in command[1]:
            output = Path(command[command.index("--output") + 1])
            output.write_text(json.dumps({"components": [first, second]}), encoding="utf-8")
        else:
            output_dir = Path(command[command.index("--output-dir") + 1])
            output_dir.mkdir(parents=True)
            detail = output_dir / "detail.json"
            detail.write_text(
                json.dumps(
                    {
                        "ExactCheckComplete": True,
                        "FailedBodyPairCount": 0,
                        "HasInterference": False,
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "result_leaf_details_batch.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "pair": [first["Name"], second["Name"]],
                                "outputPath": str(detail),
                                "exactCheckComplete": True,
                                "failedBodyPairCount": 0,
                                "acceptance": {"accepted": True, "policy": "zeroInterference"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=0, stderr="")

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    cache_path = tmp_path / "cache/manifest.json"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=workspace,
        executable=tmp_path / "fake.exe",
        cache_manifest_path=cache_path,
        command_runner=command_runner,
    )
    job = {"jobId": "job-1"}
    step = {"stepId": "step-a200", "moduleToken": "A200", "attemptCount": 1}
    assembly = tmp_path / "candidate.SLDASM"
    assembly.write_bytes(b"assembly")
    first_result = gate(job, step, assembly, None)
    assert first_result["accepted"] is True
    assert len(calls) == 2
    assert json.loads(cache_path.read_text(encoding="utf-8"))["entryCount"] == 1

    step["attemptCount"] = 2
    second_result = gate(job, step, assembly, None)
    assert second_result["accepted"] is True
    # Second pass captures fresh poses but does not rerun exact B-rep.
    assert len(calls) == 3


def test_pose_capture_failure_returns_rejection_for_runner_rollback(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)

    def command_runner(command, timeout):
        return SimpleNamespace(returncode=2, stderr="pose failure")

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=workspace,
        executable=tmp_path / "fake.exe",
        cache_manifest_path=tmp_path / "cache.json",
        command_runner=command_runner,
    )
    result = gate(
        {"jobId": "job-1"},
        {"stepId": "step-a800", "moduleToken": "A800", "attemptCount": 1},
        tmp_path / "candidate.SLDASM",
        None,
    )
    assert result["accepted"] is False
    assert "位姿/AABB捕获失败" in result["message"]


def test_live_gate_keeps_complete_negative_batch_when_exact_command_returns_nonzero(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    first_file = tmp_path / "A300.SLDASM"
    second_file = tmp_path / "A700.SLDASM"
    first_file.write_bytes(b"a300")
    second_file.write_bytes(b"a700")
    first = component("FL9A24D062A300.001-1", first_file, 0, [0, 0, 0, 1, 1, 1])
    second = component("FL9A24D062A700.001-1", second_file, 0.5, [0.5, 0, 0, 2, 1, 1])

    def command_runner(command, timeout):
        if "capture_top_level_component_poses.py" in command[1]:
            output = Path(command[command.index("--output") + 1])
            output.write_text(json.dumps({"components": [first, second]}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        output_dir = Path(command[command.index("--output-dir") + 1])
        output_dir.mkdir(parents=True)
        detail = output_dir / "detail.json"
        detail.write_text(
            json.dumps(
                {
                    "ExactCheckComplete": True,
                    "FailedBodyPairCount": 0,
                    "HasInterference": True,
                }
            ),
            encoding="utf-8",
        )
        (output_dir / "result_leaf_details_batch.json").write_text(
            json.dumps(
                {
                    "pairs": [
                        {
                            "pair": [first["Name"], second["Name"]],
                            "outputPath": str(detail),
                            "exactCheckComplete": True,
                            "failedBodyPairCount": 0,
                            "acceptance": {"accepted": False, "policy": "zeroInterference"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        # capture_leaf_interference_details.py uses a non-zero code for a
        # completed exact check that found a disallowed interference.
        return SimpleNamespace(returncode=2, stderr="hard interference")

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=workspace,
        executable=tmp_path / "fake.exe",
        cache_manifest_path=tmp_path / "cache.json",
        command_runner=command_runner,
    )
    result = gate(
        {"jobId": "job-1"},
        {"stepId": "step-a300", "moduleToken": "A300", "attemptCount": 1},
        tmp_path / "candidate.SLDASM",
        None,
    )

    assert result["accepted"] is False
    assert result["message"] == "仍有未接受的精确干涉对象对。"
    evidence = json.loads(Path(result["evidencePath"]).read_text(encoding="utf-8"))
    assert evidence["exactCommandReturnCode"] == 2
    assert evidence["exactBatchEvidencePath"].endswith("result_leaf_details_batch.json")
