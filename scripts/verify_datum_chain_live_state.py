"""Bounded read-only CAD inspection using the existing top-level verifier."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "apps/demo-backend/src"))
from demo_backend.datum_chain_verification import compare_cad_states


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad-result",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--count",type=int,required=True)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--base",default="AA00")
    parser.add_argument(
        "--reference-search-folder",
        type=Path,
        action="append",
        default=[],
        help=(
            "Existing exact parent folder used transiently for referenced-document "
            "resolution. The verifier restores the original SolidWorks settings."
        ),
    )
    args=parser.parse_args()
    result=read(args.cad_result)
    tool=result["toolResult"]
    names=[r["ObservedMateName"] for r in tool["MateVerifications"]]
    command=["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",
             str(ROOT / "scripts/verify_p000_support_demo_state.ps1"),
             "-AssemblyPath",result["outputAssemblyPath"],"-ReportPath",str(args.report.resolve()),
             "-BaseToken",args.base,"-TargetToken",tool["TargetModuleToken"],
             "-ExpectedTopLevelComponentCount",str(args.count),"-ExpectedMateNamesJson",json.dumps(names)]
    if args.source:
        command += ["-SourceCheckpoint",str(args.source.resolve())]
    if args.reference_search_folder:
        folders = []
        for folder in args.reference_search_folder:
            resolved = folder.resolve()
            if not resolved.is_dir():
                parser.error(f"reference search folder does not exist: {resolved}")
            value = str(resolved)
            if value.casefold() not in {item.casefold() for item in folders}:
                folders.append(value)
        command += ["-ReferenceSearchFoldersJson", json.dumps(folders, ensure_ascii=False)]
    clock=perf_counter()
    completed=subprocess.run(command,capture_output=True,timeout=300)
    if completed.returncode:
        print(completed.stderr.decode("utf-8",errors="replace"))
        return completed.returncode
    observed=read(args.report)
    if args.source and len((observed.get("sourceObserved") or {}).get("components") or [])>1:
        source={"success":observed["sourceCheckpointSha256Before"]==observed["sourceCheckpointSha256After"],
                "observed":observed["sourceObserved"]}
        comparison=compare_cad_states(source,observed,base_token=args.base,added_token=tool["TargetModuleToken"])
        comparison["startedFromCheckpointPath"]=str(args.source.resolve())
        with args.report.with_suffix(".preservation.json").open("x",encoding="utf-8") as stream:
            json.dump(comparison,stream,ensure_ascii=False,indent=2)
        if not comparison["success"]:
            print(json.dumps(comparison,ensure_ascii=False))
            return 2
    print(json.dumps({"success":observed["success"],"report":str(args.report.resolve()),
                      "durationSeconds":perf_counter()-clock,"openWarnings":observed["observed"]["openWarnings"],
                      "components":len(observed["observed"]["components"]),"mates":len(observed["observed"]["allTopLevelMates"])},ensure_ascii=False))
    return 0 if observed["success"] else 2


if __name__=="__main__":
    raise SystemExit(main())
