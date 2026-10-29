"""Explicit engineer choices survive descriptive text and reach CAD compilation."""

import json
from pathlib import Path
import shutil

import pytest

from demo_backend import global_natural_language_manifest as compiler
from demo_backend.models import GlobalNaturalLanguageManifestJobRequest
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


ROOT = Path(__file__).resolve().parents[3]
RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v62-project03-expanded-cross-project-chain-driving-20261014/"
    "release-manifest.json"
)


def _selections():
    catalog, _ = compiler.load_released_relation_catalog(ROOT, RELEASE)
    return [
        {"moduleDefinitionId": next(
            row["moduleDefinitionId"] for row in catalog["moduleDefinitions"]
            if any(alias.get("projectId") == project and alias.get("moduleToken") == token
                   for alias in row.get("projectAliases", []))
        ), "confirmed": True}
        for project, token in [("project03", "AA00"), ("project01", "SS00")]
    ]


def test_confirmed_candidates_override_ambiguous_description_and_are_recorded(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"confirmed-selection-{tmp_path.name}"
    monkeypatch.setattr("demo_backend.global_assembly_workbench.DEFAULT_CONTEXT_DIR", context_dir)
    selections = _selections()
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    result = compiler.compile_natural_language_manifest_job(
        ROOT,
        {
            "contextId": "confirmed-base-transport",
            "requirements": [
                "先建立项目03 AA00设备箱体与固定安装基座。",
                "在当前设备上安装产品传输模组。",
            ],
            "confirmedModuleSelections": selections,
            "releaseManifestPath": RELEASE,
            "enforceMechanicalInterfaceContracts": True,
        },
        store=store,
    )
    assert result["success"] is True
    assert result["cadStarted"] is False
    assert result["packetCount"] == 1
    assert [item["moduleDefinitionId"] for item in result["confirmedModuleSelections"]] == [
        item["moduleDefinitionId"] for item in selections
    ]
    report = json.loads(Path(result["reportPath"]).read_text(encoding="utf-8"))
    assert report["confirmedModuleSelections"] == result["confirmedModuleSelections"]
    preflight = json.loads((store._dir(result["jobId"]) / "preflight.json").read_text(encoding="utf-8"))
    assert preflight["naturalLanguageCompilation"]["confirmedModuleSelections"] == result["confirmedModuleSelections"]
    assert store.load(result["jobId"])["steps"][0]["moduleToken"] == "SS00"
    shutil.rmtree(ROOT / context_dir)


@pytest.mark.parametrize(
    "selections,match",
    [
        ([], "长度相同"),
        ([{"moduleDefinitionId": "x", "confirmed": True}], "长度相同"),
        ([{"moduleDefinitionId": "x"}, {"moduleDefinitionId": "y", "confirmed": True}], "confirmed=true"),
        ([{"moduleDefinitionId": "x", "confirmed": "true"}, {"moduleDefinitionId": "y", "confirmed": True}], "confirmed=true"),
        ([{"moduleDefinitionId": "x", "confirmed": False}, {"moduleDefinitionId": "y", "confirmed": True}], "confirmed=true"),
        ([{"moduleDefinitionId": "x", "confirmed": True}, {"moduleDefinitionId": "y", "confirmed": True}], "不存在"),
    ],
)
def test_invalid_selection_is_rejected_before_creating_context(monkeypatch, selections, match):
    def forbidden(*args):
        pytest.fail("invalid confirmation must not create a context")

    monkeypatch.setattr(compiler, "create_context", forbidden)
    with pytest.raises(compiler.GlobalNaturalLanguageManifestError, match=match):
        compiler.compile_natural_language_manifest_job(
            ROOT,
            {"contextId": "bad-confirmation", "requirements": ["先建立基座", "添加传输"],
             "releaseManifestPath": RELEASE, "confirmedModuleSelections": selections},
        )


def test_api_model_keeps_confirmed_selections_and_explicit_execution_mode():
    request = GlobalNaturalLanguageManifestJobRequest(
        contextId="confirmed-api", requirements=["建立基座", "增加模组"],
        confirmedModuleSelections=_selections(), relationExecutionMode="datum_placement_demo",
    )
    dumped = request.model_dump(by_alias=True, exclude_none=True)
    assert dumped["confirmedModuleSelections"] == _selections()
    assert dumped["relationExecutionMode"] == "datum_placement_demo"
    with pytest.raises(ValueError):
        GlobalNaturalLanguageManifestJobRequest(
            contextId="unconfirmed-api", requirements=["建立基座", "增加模组"],
            confirmedModuleSelections=[{"moduleDefinitionId": "cad/example", "confirmed": "true"}],
        )
