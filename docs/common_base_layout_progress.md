# Common Base Layout Reconstruction Progress

## 2026-06-25 - Clean Assembly Validation Result

Validation flow:

- After deleting the old `demo/ABC_arrange_demo.SLDASM`, the backend workflow was run again:
  - `Reset`
  - `Initialize`
  - `Common Base`
  - `Capture Layout`
  - `Replay Layout`

Result:

- `InitializeCommonBaseAssembly` passed. A/B/C were inserted and a new `demo/ABC_arrange_demo.SLDASM` was created.
- `FinalizeCommonBaseAssembly` still returned `bottom face orientation mismatch`.
- However, B/C now report `bottomMateResult.errorName=swAddMateError_NoError`, meaning the Coincident mates were created successfully.
- The remaining failure comes from `orientationChecks`:
  - A is the base and passed with `matchesBase=true`.
  - B/C returned `matchesBase=false`.
- This means the latest fix narrowed the issue from "duplicate mate regression" to the intended remaining problem: automatic bottom-face orientation correction is not implemented yet.
- `CaptureCommonBaseLayoutFromAssembly` passed and wrote `demo/captured_common_base_layout.json`.
- `ApplyCapturedCommonBaseLayout` passed and wrote `demo/apply_captured_layout_result.png`; A/B/C all moved successfully from captured layout2d targets.

Current conclusion:

- The `Initialize -> Capture Layout -> Replay Layout` path is usable.
- Common Base mate creation succeeds, but bottom-face orientation consistency is still pending.
- The next implementation should explicitly rotate B/C from normal vectors so their bottom-face direction matches A, rather than returning to repeated mate/undo retries.

## 2026-06-25 - Common Base duplicate-mate regression fixed

Goal:

- Restore the previously stable Common Base behavior.
- Avoid repeatedly creating and undoing Coincident mates during a single `FinalizeCommonBaseAssembly` call.

Code changes:

- Updated `vendor/solidworks-mcp/app/SolidWorksMcpApp/Tools/DemoTools.cs`.
- Removed the risky alignment retry flow that created a mate, rebuilt, probed orientation, then called `Undo(1)`.
- Restored `MateBottomFacesToFirstComponent()` so each target component creates only one bottom-face Coincident mate.
- Kept post-mate `orientationChecks` so the tool can still report whether B/C bottom-face normals match A.
- If orientation mismatches, the tool reports a clear orientation mismatch without leaving extra mates from retry attempts.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

Result:

- MCP app build passed with 0 warnings and 0 errors.
- Backend Python compilation passed.
- Frontend TypeScript/Vite build passed.
- Published the fixed MCP to the default `artifacts/solidworks-mcp` directory.
- Restarted the default MCP and backend. `/api/health` confirms:
  - `mcpCwd=artifacts/solidworks-mcp`
  - `faceMappingPath=artifacts/solidworks-mcp/face_mappings.json`

Current status:

- Code-level fix and basic build checks are complete.
- Real SolidWorks validation has not been run directly yet because the current `demo/ABC_arrange_demo.SLDASM` may already contain duplicate mates left by the previous retry implementation.
- Recommended next validation: close and delete the old `ABC_arrange_demo.SLDASM`, or manually remove the duplicate Coincident mates, then run `Initialize -> Common Base` on a clean assembly.

## Goal

Support this workflow:

1. Open a source assembly `X` that contains first-level subassemblies such as `A`, `B`, and `C`.
2. Record or resolve each subassembly's bottom face.
3. Capture the original layout relationship on the common bottom plane.
4. Create a new blank assembly, insert the subassemblies, finalize common-base mating, and move the subassemblies in the base plane to approximately reconstruct the source layout.

## Recommended Architecture

The workflow is split into explicit phases:

1. `CaptureCommonBaseLayoutFromAssembly`
   - Reads first-level component `Transform2`.
   - Selects recorded bottom faces.
   - Probes bottom-face world center and normal.
   - Builds a `CommonBaseFrame`.
   - Projects each bottom center into 2D layout coordinates.
   - Optionally writes a layout JSON file.

2. `InitializeCommonBaseAssembly`
   - Creates or opens the target assembly.
   - Inserts components.
   - Saves `assemblyPath`.
   - Does not mate or move components.

3. `FinalizeCommonBaseAssembly`
   - Creates bottom-face coincident mates once.
   - Sets `commonBaseReady=true` through the backend state.
   - Future improvement: verify normal orientation after mate.

4. `MoveComponentsOnCommonBase`
   - Runs only after `commonBaseReady=true`.
   - Moves components by bottom-face center.
   - Future improvement: consume captured `baseFrame` instead of a fixed SolidWorks reference plane.

## Changes Completed In This Iteration

### Face Mapping

Updated:

- `SelectionService.FaceMappingProbeResult`
- `SelectionService.GetSelectedFaceMappingProbe`
- `SelectionService.RecordFaceMapping`
- `SelectionService.SelectFaceByName`

Added fields:

- `WorldNormal`
- `LocalNormal`

Behavior:

- When the selected face is planar, the service records/probes a normalized face normal.
- `face_mappings.json` entries now store `localNormal` and `worldNormal`.
- `SelectFaceByName` still supports old mappings without normals.
- When `localNormal` exists, selection uses it as a small tie-breaker in addition to local center and area.

### Component Transform Capture

Updated:

- `AssemblyService`
- `IAssemblyService`
- `AssemblyTools`
- `SolidWorksMcpHubTestClient`

Added:

- `ComponentPoseInfo`
- `IAssemblyService.ListComponentPoses(bool topLevelOnly = true)`
- MCP tool `list_component_poses`

Returned data includes:

- component name
- source file path
- hierarchy path
- depth
- raw `Transform2`
- translation
- X/Y/Z axes

### Common Base Layout Math

Added:

- `CommonBaseLayoutMath`
- `CommonBaseFrame`
- `CommonBaseLayout2d`

Responsibilities:

- Build a stable base frame from bottom-center origin, bottom normal, and preferred component X axis.
- Project world points into 2D layout coordinates.
- Convert 2D layout coordinates back to world points on the base plane.
- Compare normal directions with a dot-product threshold through `NormalsMatchDirection`.

### Finalize Orientation Validation

Updated:

- `DemoTools.FinalizeCommonBaseAssembly`
- `DemoTools.FinalizeCommonBaseCore`

Added:

- `DemoBottomOrientationCheck`
- `DemoCommonBaseResult.OrientationChecks`

Behavior:

- After bottom-face mating and rebuild, the tool reselects/probes every component bottom face.
- The first component is used as the base orientation.
- Later components must have `dot(worldNormal, baseWorldNormal) >= normalDotThreshold`.
- The default threshold is `0.95`.
- If a component normal points the opposite way, `Success=false` and the message includes `bottom face orientation mismatch`.
- This version only detects orientation errors. It does not automatically rotate or flip components.

### Capture MCP Tool

Updated:

- `DemoTools`

Added MCP tool:

- `capture_common_base_layout_from_assembly`

C# method:

- `CaptureCommonBaseLayoutFromAssembly`

Internal method:

- `CaptureCommonBaseLayoutCore`

Output record:

- `DemoCapturedLayoutDocument`

The tool currently:

- Opens a source assembly path if supplied, otherwise uses the active assembly.
- Captures all top-level components by default, or a supplied component list.
- Requires existing bottom-face mappings.
- Uses the first valid captured component, or `baseComponentName`, as the layout origin.
- Returns each component's source `Transform2`, bottom center, bottom normal, and projected 2D layout.
- Optionally writes the captured document to a JSON file.

### CLI Test Script

Added:

- `scripts/capture_common_base_layout.py`

Purpose:

- Calls `capture_common_base_layout_from_assembly` through `McpToolRunner`.
- Prints the captured layout JSON.
- Optionally writes a layout JSON file.

Example:

```cmd
python scripts\capture_common_base_layout.py ^
  --source D:\path\to\X.SLDASM ^
  --component A-1:底面 ^
  --component B-1:底面 ^
  --component C-1:底面 ^
  --base-component A-1 ^
  --output demo\captured_common_base_layout.json
```

### Verification Script

Updated:

- `scripts/face_mapping_verify_select.py`

New behavior:

- If a stored mapping contains `localNormal`, verification compares selected-face normal via `1 - abs(dot)`.
- Old mappings without normals still verify using leaf, local center, and area.

## Tests Completed

Commands run:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m py_compile scripts\capture_common_base_layout.py scripts\face_mapping_record_probe.py scripts\face_mapping_verify_select.py
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter CommonBaseLayoutMathTests
```

Result:

- MCP app build passed.
- Python scripts compile passed.
- `CommonBaseLayoutMathTests` passed: 5 tests.

## Current Phase Status

### Phase 1: Stable Demo Flow

Status: mostly complete before this iteration.

Existing tools:

- `InitializeCommonBaseAssembly`
- `FinalizeCommonBaseAssembly`
- `MoveComponentsOnCommonBase`

### Phase 2: Bottom-Face Orientation Control

Status: validation implemented, automatic correction not implemented.

Completed:

- Record/probe local and world normals for planar faces.
- Validate bottom-face world-normal orientation after `FinalizeCommonBaseAssembly`.
- Return explicit `bottom face orientation mismatch` when a later component normal does not match the base component normal.

Remaining:

- Use normals to choose mate alignment deliberately before or during mate creation.
- Optionally rotate or flip components to correct orientation.

### Phase 3: More Reliable Face Mapping

Status: partially improved.

Completed:

- Local normal is stored and used as a selection tie-breaker.

Remaining:

- Persistent reference support.
- Geometry fallback using center + area + normal + topology hints.
- Post-finalize automatic re-probe and drift detection.

### Phase 4: Frontend Workflow

Status: not changed in this iteration.

Existing:

- Initialize/Common Base/Arrange separated.
- 2D dragging exists.

Remaining:

- Add capture-layout UI.
- Add explicit verify-bottom-faces UI.
- Display captured `layout2d` and status per component.
- Use captured layout as the initial frontend board state.

## Next Recommended Implementation Step

Publish the updated MCP build and run a real SolidWorks validation:

1. Record bottom faces again so mappings include `localNormal/worldNormal`.
2. Run `InitializeCommonBaseAssembly`.
3. Run `FinalizeCommonBaseAssembly`.
4. Check `orientationChecks` in the returned JSON.
5. If all checks pass, run `MoveComponentsOnCommonBase`.

After real validation is stable, implement optional automatic correction for orientation mismatch.

## Issue Log

### 2026-06-22 16:53:57 CST - Common Base failed after orientation validation

Observed result:

- `InitializeCommonBaseAssembly` completed successfully at `2026-06-22 16:52:30 CST` and saved `demo/ABC_arrange_demo.SLDASM`.
- `FinalizeCommonBaseAssembly` ran at `2026-06-22 16:53:57 CST` with `normalDotThreshold=0.95`.
- B and C bottom face mate calls returned `swAddMateError_NoError`, so the mate step itself did not fail.
- The tool returned `Success=false` with message `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`

Root-cause analysis:

- The latest `face_mappings.json` proves the updated normal-recording code is active because mappings now include `localNormal` and `worldNormal`.
- However, A's recorded bottom face has `localNormal: [0,0,0]` and `worldNormal: [0,0,0]`.
- `FinalizeCommonBaseAssembly` uses A as the reference bottom-face normal. A zero reference normal makes dot-product orientation checks unreliable and causes B/C to be reported as orientation mismatches.
- This failure is therefore not primarily a move failure or a mate failure. It is an invalid reference-normal problem in the face-mapping/orientation-validation path.

Follow-up items:

- Reject missing or near-zero normals during face recording and validation instead of storing or using `[0,0,0]`.
- Return a clearer error such as `A-1 bottom face normal unavailable; please re-record a planar bottom face`.
- Re-record A's bottom face after the validation fix, ensuring the selected face is a true planar bottom face.
- Preserve `orientationChecks` in backend `lastRun` and frontend output so future failures can be diagnosed without relying on truncated MCP logs.

### 2026-06-22 17:20 CST - Zero-normal guard implemented

Changes:

- Added `CommonBaseLayoutMath.IsValidNormal(...)`.
- Updated `CommonBaseLayoutMath.NormalsMatchDirection(...)` so zero or near-zero normals never pass direction matching.
- Updated `SelectionService.TryGetPlanarFaceNormal(...)` and local-to-world vector conversion so invalid planar normals return `null` instead of `[0,0,0]`.
- Updated face selection matching so saved zero normals are ignored as tie-breakers.
- Updated `FinalizeCommonBaseAssembly` orientation probing to report a clear bottom-face normal probe error when a selected bottom face has no valid planar world normal.
- Added a unit test covering zero-normal rejection.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter CommonBaseLayoutMathTests
```

Result:

- MCP app Release build passed with 0 warnings and 0 errors.
- `CommonBaseLayoutMathTests` passed: 6 tests.

Next validation step:

- Publish/restart the MCP build.
- Re-record A-1's bottom face. The new mapping should not contain `[0,0,0]` normal values.
- Run `FinalizeCommonBaseAssembly` again and inspect `orientationChecks`.

### 2026-06-22 17:35 CST - Backend face mapping path pointed to old MCP artifact

Observed result:

- Backend `/api/health` returned `mcpCwd` as `artifacts/solidworks-mcp`, which was correct for the new MCP build.
- The same response still returned `faceMappingPath` as `artifacts/solidworks-mcp-20260615-demo-mate/face_mappings.json`.
- This meant the backend would call the new MCP tool directory while still checking face mappings from an old artifact directory.

Root cause:

- `DEMO_MCP_CWD` controls where the backend launches the MCP command.
- `DEMO_FACE_MAPPING_PATH` separately controls which `face_mappings.json` the backend uses for preflight checks.
- Updating only `DEMO_MCP_CWD` is not enough; the backend default in `config.py` still points to the older demo-mate artifact unless `DEMO_FACE_MAPPING_PATH` is explicitly set.

Resolution:

Start the backend with both the MCP working directory and face mapping path set to the same current artifact:

```cmd
set DEMO_MCP_MODE=bridge
set DEMO_LLM_MODE=dry-run
set DEMO_MCP_CWD=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp
set DEMO_MCP_COMMAND=SolidWorksMcpApp.exe
set DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

Validation:

- After restarting the backend, `/api/health` should show both `mcpCwd` and `faceMappingPath` under `artifacts/solidworks-mcp`.
- The user confirmed the health response is now as expected.

### 2026-06-22 18:32:47 CST - Common Base mate succeeded but B orientation mismatch blocked Arrange

Observed result:

- A/B/C bottom-face mappings were valid enough for selection.
- `FinalizeCommonBaseAssembly` selected the bottom faces and created coincident mates for B and C.
- B and C mate results returned `swAddMateError_NoError`.
- SolidWorks UI showed the three bottom faces coplanar.
- B's bottom-face orientation was opposite to A, while C matched A.
- Frontend displayed `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`
- Frontend stayed at `error / base pending`, and `Arrange` was disabled.

Analysis:

- The Common Base mate step succeeded geometrically.
- The orientation guard correctly prevented `commonBaseReady=true` because B was coplanar but flipped relative to A.
- This is the expected behavior for the current implementation: orientation is detected but not automatically corrected.

Follow-up:

- Automatic bottom-face orientation correction has been added to `docs/to_be_continued.md` as a long-term enhancement.
- The current validation round should continue with the Transform2 capture/layout workflow.

### 2026-06-22 18:40 CST - Clean-state Transform2/layout2d capture validated

Observed result:

- The user re-ran `capture_common_base_layout.py` in a clean initialized assembly state, before running Common Base.
- `CaptureCommonBaseLayoutFromAssembly` returned `success=true`.
- `missingFaceMappings=[]`.
- A/B/C all returned:
  - `sourceTransform`,
  - `componentTranslation`,
  - `componentXAxis`,
  - `bottomCenterWorld`,
  - `bottomNormalWorld`,
  - `layout2d`,
  - successful face selection and face probe.
- A's `layout2d` was `{ x: 0, y: 0 }` as the base component.
- B's `layout2d` was approximately `{ x: 0.218, y: 0 }`.
- C's `layout2d` was approximately `{ x: -0.0195, y: 0.012 }`.
- Face probe areas matched the current `face_mappings.json` values, so the capture did not select the wrong faces in this clean-state run.

Analysis:

- Transform2 capture and common-base 2D projection are working in the clean-state workflow.
- This JSON can serve as a 2D layout blueprint for reconstructing component positions in a new assembly after common-base alignment.
- B's bottom-face normal still differs from A/C, so automatic orientation correction remains a separate follow-up requirement.

Status:

- Transform2/layout capture: validated.
- Automatic orientation correction: pending.
- Applying captured `layout2d` back into a new assembly: pending.

### 2026-06-24 11:24 CST - First layout2d replay tool implemented

Implemented:

- Added MCP tool `ApplyCapturedCommonBaseLayout`.
- Added command-line script `scripts/apply_captured_common_base_layout.py`.
- The new tool reads a JSON file produced by `CaptureCommonBaseLayoutFromAssembly`.
- For each component, it:
  - reads captured `layout2d`,
  - converts it back to a target world-space bottom-center point using `baseFrame`,
  - selects the component's recorded bottom face,
  - reads the current bottom-face center,
  - calls `MoveComponent` with the computed delta.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m py_compile scripts\apply_captured_common_base_layout.py scripts\capture_common_base_layout.py
```

Result:

- Build passed with 0 warnings and 0 errors.
- Python script syntax checks passed.

Live test status:

- Publishing to `artifacts/solidworks-mcp` was blocked because the old MCP executable was still running.
- Publish script created `artifacts/solidworks-mcp-20260624-112354`.
- Running the new script against that directory failed before tool execution because another hub instance was already running.
- This runtime-directory issue has been recorded in `docs/to_be_continued.md`.

Current status:

- Code implementation is complete for first layout2d replay.
- Real SolidWorks validation is pending a clean MCP restart with the newly published build.

### 2026-06-24 11:34 CST - First layout2d replay real validation passed

Executed:

```cmd
taskkill /IM SolidWorksMcpApp.exe /F
python scripts\apply_captured_common_base_layout.py --layout demo\captured_common_base_layout.json --assembly demo\ABC_arrange_demo.SLDASM --mcp-cwd artifacts\solidworks-mcp-20260624-112354 --screenshot demo\apply_captured_layout_result.png
```

Issue found and fixed:

- The first run passed relative paths to MCP.
- MCP resolved those paths relative to the published artifact directory and could not find `demo/captured_common_base_layout.json`.
- `scripts/apply_captured_common_base_layout.py` was fixed to pass absolute paths for layout JSON, assembly path, and screenshot path.

Result:

- `ApplyCapturedCommonBaseLayout` completed successfully.
- A/B/C all returned `moveResult.success=true`.
- B moved by approximately `deltaY=-0.01000000000000002m`, matching the captured layout target.
- Screenshot was exported to `demo/apply_captured_layout_result.png`.

Status:

- First end-to-end layout2d replay is validated.
- Remaining follow-up: expose this workflow in the frontend and handle Chinese face-name display/encoding more cleanly.

### 2026-06-24 - layout2d replay exposed in the frontend

Implemented:

- Added backend endpoint `POST /api/demo/apply-captured-layout`.
- Added `DemoService.apply_captured_layout()`, which calls the MCP tool `apply_captured_common_base_layout`.
- Updated `GET /api/demo/screenshot` to prefer the latest `lastRun.screenshotPath`, so replay screenshots can be displayed in the frontend.
- Added frontend API function `applyCapturedLayout()`.
- Added a `Replay Layout` button to the frontend toolbar.
- The button replays `demo/captured_common_base_layout.json` into the current assembly from `assemblyPath`.

Verification:

```cmd
python -m compileall apps\demo-backend\src scripts\apply_captured_common_base_layout.py
cmd /c npm.cmd run build
```

Result:

- Backend Python compilation passed.
- Frontend TypeScript/Vite build passed.

Current status:

- layout2d replay now has both script validation and frontend entry-point integration.
- Next useful validation is a real UI-level run by clicking `Replay Layout` while SolidWorks and the backend are running.

### 2026-06-25 - Common Base orientation-aware mate retry implemented

Goal:

- Fix the core remaining Common Base issue where coincident mates made the bottom faces coplanar but could leave a target component's bottom-face normal opposite from the base component.

Implemented:

- Updated `DemoTools.FinalizeCommonBaseCore()` to call an orientation-aware bottom-face mating flow.
- `MateBottomFacesToFirstComponent()` now accepts an optional normal dot threshold.
- For `FinalizeCommonBaseAssembly`, the first component's bottom-face world normal is probed before mating.
- For each later component, the tool now tries coincident mate alignments in order:
  - `Closest`
  - `AntiAligned`
  - `None`
- After each successful mate creation, the tool rebuilds and probes the target bottom-face normal.
- If the target normal does not match the base normal, the tool calls `Undo(1)` and tries the next mate alignment.
- If none of the alignments produces a matching normal, the component returns `BottomFaceOrientationMismatch` instead of silently accepting a wrong orientation.
- The older arrange path still uses the previous simpler mate flow by passing `normalDotThreshold: null`, so this change is scoped to the explicit `FinalizeCommonBaseAssembly` stage.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

Result:

- Build passed with 0 warnings and 0 errors.

Current status:

- Code-level implementation is complete.
- A new MCP build was published to `artifacts/solidworks-mcp-20260625-161303`, and `face_mappings.json` was copied into that directory.
- Real SolidWorks validation is still required after restarting the active MCP build from the new directory.
- If SolidWorks treats all tried mate alignments as the same physical orientation for a specific face pair, the tool will now fail clearly instead of reporting a false ready state.

### 2026-06-25 - Small-face normal fallback and Capture Layout productization

Goal:

- Improve face-mapping robustness when small planar faces return `normal=null`.
- Productize the Transform2/Layout2D workflow so capture and replay are both available through backend/frontend actions.

Implemented:

- Updated `SelectionService.TryGetPlanarFaceNormal()`:
  - keeps `ISurface.PlaneParams` as the primary path;
  - falls back to tessellated normals when available;
  - falls back to fitting a normal from tessellated triangle points when `PlaneParams` fails;
  - keeps face-sense correction when SolidWorks exposes it.
- Added internal tessellation normal fitting helpers and unit tests in `SelectionServiceFaceNormalTests`.
- Added backend MCP tool constant `CAPTURE_COMMON_BASE_LAYOUT_TOOL`.
- Added backend endpoint `POST /api/demo/capture-common-base-layout`.
- Added `DemoService.capture_common_base_layout()`, which writes the captured data to `demo/captured_common_base_layout.json`.
- Added frontend API `captureCommonBaseLayout()`.
- Added a `Capture Layout` button to the frontend toolbar, next to `Replay Layout`.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --filter FullyQualifiedName~SelectionServiceFaceNormalTests
python -m compileall apps\demo-backend\src scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
cmd /c npm.cmd run build
```

Result:

- MCP app build passed with 0 warnings and 0 errors.
- New normal fallback unit tests passed: 3/3.
- Backend Python compilation passed.
- Frontend TypeScript/Vite build passed.
- Test project still emits pre-existing nullable warnings outside the new test file.

Published build:

- Published to `artifacts/solidworks-mcp-20260625-163843`.
- Copied `face_mappings.json` into that directory.

Current status:

- Code-level implementation and local tests are complete.
- Real SolidWorks validation is still required for:
  - small-face fallback on an actual small face;
  - frontend `Capture Layout`;
  - frontend `Replay Layout`;
  - Common Base orientation-aware mate retry from the latest published build.

### 2026-06-25 - Common Base orientation retry regression found

Symptom:

- After `Initialize`, A/B/C were inserted successfully, but A/B were hidden in SolidWorks and had to be shown from the component tree.
- `Common Base` failed with:

```text
FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.
```

- The user observed what looked like duplicate Coincident mates between A-B and A-C.

Analysis:

- The new orientation-aware retry flow was:

```text
AddMate -> ForceRebuild -> ProbeNormal -> mismatch -> Undo(1)
```

- The risky part is that `Undo(1)` may undo the rebuild rather than the newly created mate.
- That can leave a Coincident mate behind for each attempted alignment, producing duplicate or over-defined mates.
- This is a regression against the previously working basic common-base workflow.

Resolution direction:

- Restore basic stability first: do not repeatedly create/undo mates in one Common Base call.
- Short-term fix: create one Coincident mate per target component, then run orientation probe/report.
- If orientation still mismatches, return a clear orientation mismatch without creating duplicate mates.
- Future automatic orientation correction should explicitly rotate the component using normal vectors instead of guessing SolidWorks mate alignment behavior through repeated mate attempts.

### 2026-06-25 - First Explicit-Rotation Attempt for Common Base Orientation

Goal:

- Fix bottom-face orientation by computing an explicit component rotation from normal vectors, without repeatedly creating and undoing coincident mates.

Implemented:

- Added `CommonBaseLayoutMath.CalculateNormalAlignmentRotation()` to compute a rotation axis and angle from source and target normals.
- Added `DemoBottomOrientationCorrection` so `FinalizeCommonBaseAssembly` can report correction attempts per component.
- Updated `FinalizeCommonBaseAssembly`:
  - uses the first component bottom-face `worldNormal` as the reference;
  - attempts an explicit rotation for each following component before mating;
  - probes the recorded bottom face after rotation;
  - tries the opposite angle if the first rotation attempt fails;
  - rolls the component back if both attempts fail;
  - then runs the single coincident-mate common-base step;
  - returns both `orientationCorrections` and `orientationChecks`.
- Added `NormalizeComponentLayout()` to tolerate direct MCP-runner tests where Chinese `底面` was passed as `??`.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

Result:

- Build passed.
- Normal math and small-face fallback unit tests passed: 9/9.
- Backend compilation passed.
- Frontend build passed.

Real SolidWorks validation:

- `InitializeCommonBaseAssembly` succeeded and inserted A/B/C.
- `FinalizeCommonBaseAssembly` still failed with `bottom face orientation mismatch`.
- B triggered the correction path, but after rotation the selected bottom face returned `worldNormal=null` / `localNormal=null`, so the correction could not be confirmed and was rolled back.
- C matched the base normal before mating, but mismatched after the coincident mate, which suggests the mate solve can still change component orientation.
- The previous duplicate-mate retry regression was not reproduced in this run.

Current status:

- The first explicit-rotation correction path is implemented and rollback-safe.
- Real validation shows the orientation problem is not fully solved yet.
- Recommended next step: run a post-mate correction pass, then strengthen face re-identification and normal probing after component rotation.

### 2026-06-26 - PostMate Second-Phase Orientation Correction Integrated

Goal:

- Avoid the previous failure mode where a component looked corrected before mating but changed orientation after the coincident mate solve.
- Make `FinalizeCommonBaseAssembly` run common-base mating first, then correct orientation, then run the final orientation check.

Implemented:

- Updated `FinalizeCommonBaseAssembly` ordering:
  - run `MateBottomFacesToFirstComponent()` once;
  - `ForceRebuild`;
  - run `CorrectBottomFaceOrientations(..., stage: "PostMate")`;
  - `ForceRebuild` again;
  - run `ProbeBottomFaceOrientations()` for final checks.
- Added `Stage` to `DemoBottomOrientationCorrection`.
- Orientation correction now reports `PostMate`, making real-run logs easier to interpret.
- Kept rollback behavior so failed correction attempts do not leave the component in the attempted pose.

Verification:

```cmd
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
dotnet test vendor\solidworks-mcp\bridge\SolidWorksBridge.Tests\SolidWorksBridge.Tests.csproj -c Release --no-build --filter "FullyQualifiedName~CommonBaseLayoutMathTests|FullyQualifiedName~SelectionServiceFaceNormalTests"
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

Result:

- MCP app build passed with 0 warnings and 0 errors.
- Normal/math and small-face fallback tests passed: 9/9.
- Backend compilation passed.
- Frontend build passed.

Current status:

- The PostMate second-phase correction is implemented.
- It still needs to be published and validated in real SolidWorks.
- Real validation should check final B/C `orientationChecks`, duplicate-mate behavior, and whether components remain visible after Initialize/Common Base.

### 2026-06-26 - Common Base Timeout and Safe Fallback

Symptom:

- Clicking `Common Base` returned `MCP execution failed: TimeoutError:` in the frontend.
- MCP logs showed `FinalizeCommonBaseAssembly started` without a matching completed entry.
- The backend returned an error after the default 180-second MCP timeout.

Likely Cause:

- The new PostMate correction attempted `RotateComponent` after Coincident mates had already been created.
- Rotating an already mated component can make SolidWorks spend a long time solving constraints or waiting, so the MCP tool did not return.

Change:

- Added an experimental `enablePostMateOrientationCorrection` flag to `FinalizeCommonBaseAssembly`.
- It defaults to `false`.
- The default Common Base flow now:
  - creates bottom-face coincident mates;
  - rebuilds;
  - probes orientation;
  - returns quickly.
- If orientation mismatches, the tool reports `bottom face orientation mismatch` instead of rotating mated components by default.

Verification:

- MCP app build passed.
- Backend compilation passed.
- Frontend build passed.
- MCP and backend were republished/restarted.

Current status:

- The safe default flow is restored.
- The next `Common Base` run is expected to return instead of timing out.
- Automatic PostMate correction remains available as an experimental opt-in path.

### 2026-06-26 - Strategy 3 Integrated: PreMate Transform2 Orientation Correction

Goal:

- Automatically correct bottom-face orientation without rotating components after coincident mates already constrain them.
- Use the safer order: correct orientation with Transform2 first, then create coincident mates.

Change:

- Added `enablePreMateOrientationCorrection` to `FinalizeCommonBaseAssembly`; default is `true`.
- Kept `enablePostMateOrientationCorrection` defaulting to `false`.
- Default flow now:
  - probe recorded bottom-face normals;
  - use the first component's bottom normal as the baseline;
  - rotate B/C with Transform2 before mating;
  - re-probe bottom normals after rotation;
  - roll back a component if the correction cannot be confirmed;
  - create bottom-face coincident mates;
  - run final `orientationChecks`.
- `orientationCorrections[*].stage` should be `PreMateTransform2`.

Verification:

- MCP app build passed with 0 warnings and 0 errors.
- Normal/math and small-face fallback tests passed: 9/9.
- Backend compilation passed.
- Frontend build passed.

Current status:

- Code-level implementation is complete.
- The updated MCP still needs to be published and validated in real SolidWorks.
- If real validation still returns `normal=null` after rotation, the next step is candidate-face scanning fallback.

### 2026-06-26 - Integration Infrastructure Plan: Direct Stdio MCP

Background:

- The current blocker for real `Common Base` validation has shifted from geometry logic to MCP startup/connectivity.
- Hub/proxy mode has repeatedly been affected by Device Guard, named-pipe permissions, and Windows session boundaries.

Plan:

- Add a direct stdio mode so the backend can launch MCP as a child process.
- Use this mode as the recommended path for frontend/backend demo integration.
- Keep Hub/tray mode for long-running desktop usage.

Current Impact:

- PreMate Transform2 orientation correction is implemented.
- Real validation can still be attempted through manually started Hub/backend, but the current path is not stable enough for repeated testing.

### 2026-06-26 - Common Base Timeout Root Cause Confirmed

Observed:

- The frontend showed `error / base pending` and `MCP execution failed: TimeoutError:`.
- The backend state file recorded an error and `commonBaseReady=false`.
- The MCP Hub log shows `FinalizeCommonBaseAssembly` ran from 16:42:48 to 16:46:02 and completed after about 194.6 seconds.

Conclusion:

- The backend default timeout is 180 seconds, shorter than the actual SolidWorks execution time in this run.
- The frontend error was caused by the backend timing out before MCP returned, not by the MCP tool never returning.
- The real MCP result was `bottom face orientation mismatch`, so Common Base orientation consistency still failed the final check.

Next:

- Restart the backend with `DEMO_MCP_TIMEOUT_SECONDS=420`.
- Run `Common Base` again so the backend can capture the full orientation correction/check result.
- Use the returned `orientationChecks` to determine whether PreMate Transform2 did not take effect or whether mate solving changed the component orientation afterward.

### 2026-06-26 - Orientation Diagnostics Persisted and Displayed

Goal:

- Avoid losing detail when `Common Base` fails with only `bottom face orientation mismatch`.
- Make the next run show whether B/C attempted correction, what the normals were before/after correction, and which final check failed against A.

Completed:

- Backend `DemoService._last_run_from_payload()` now persists:
  - `orientationCorrections`
  - `orientationChecks`
  - `missingFaceMappings`
- Frontend `api.ts` now includes `OrientationCorrection`, `OrientationCheck`, and `FaceProbe` types.
- The frontend result area now includes an `Orientation` diagnostics panel:
  - `Corrections` shows stage, applied flag, angle, axis, before/after world normal, and message.
  - `Checks` shows component match status, dot value, threshold, final world normal, and message.

Validation:

```cmd
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

Result:

- Backend compile check passed.
- Frontend TypeScript/Vite build passed.

Next:

- Restart backend and frontend.
- Run `Common Base` again.
- Inspect the frontend `Orientation` panel or `demo/demo_state.json` for `orientationCorrections` / `orientationChecks` to identify the exact mismatch source.

### 2026-06-26 - Face Mapping Move Robustness Status and New Issue

Current state:

- A first version of "face mappings survive component movement" already exists.
- `RecordFaceMapping` currently records:
  - leaf component short/full name;
  - leaf-local center;
  - local/world normal;
  - area.
- `SelectFaceByName` currently:
  - resolves the real leaf component by full name;
  - scans only that leaf component's bodies/faces;
  - uses leaf-local center distance as the dominant score;
  - uses area mismatch as a small penalty;
  - uses local normal dot as a small penalty.

New issue observed in real Common Base runs:

- After `Common Base`, B/C final `orientationChecks` selected faces whose areas are much smaller than the recorded bottom faces:
  - B recorded area about `0.009411`, final probe area about `0.000960`;
  - C recorded area about `0.006229`, final probe area about `0.001248`.
- This means the current fallback works for simple movement, but can still select adjacent small/side faces after rotation and mate solving.
- The current score gives area and normal too little weight, while local-center proximity can become ambiguous after rotation/mating.

Next recommendation:

1. Strengthen `SelectFaceByName` candidate scoring:
   - turn area error from a weak penalty into a strong filter or strong penalty;
   - turn localNormal dot from a weak penalty into a strong filter;
   - require leaf full name match;
   - fail selection when the best candidate exceeds area/normal/center thresholds instead of returning `Success=true`.
2. Return candidate scoring diagnostics from `FaceMappingResult` or a new diagnostic result.
3. In `Common Base`, after `SelectFaceByName`, probe and verify that area/normal match the recorded mapping; otherwise stop with a clear remap/fallback message.
4. Unify the `face_mappings.json` path so backend validation and MCP selection use the same mapping file.

### 2026-06-26 - SelectFaceByName Strong Validation and Candidate Diagnostics Implemented

Goal:

- Prevent `SelectFaceByName` from selecting an adjacent small/side face after rotation/mate and still returning `Success=true`.
- Surface errors during face selection instead of continuing into mate and orientation checks with the wrong face.

Completed:

- Extended `FaceMappingResult` with optional `Diagnostics`.
- Added:
  - `FaceMappingSelectionDiagnostics`
  - `FaceMappingCandidateDiagnostic`
- `SelectFaceByName` now returns top candidate diagnostics, including:
  - rank;
  - score;
  - center distance;
  - area;
  - area relative error;
  - normal dot;
  - local center;
  - local normal;
  - reject reason.
- Strong candidate thresholds:
  - local center distance `<= 0.002m`;
  - area relative error `<= 0.05`;
  - local normal dot `>= 0.95`.
- If the best candidate does not satisfy the thresholds, `SelectFaceByName` now fails and reports the reason in `Diagnostics.FailureReason`.

Validation:

```cmd
dotnet build vendor\solidworks-mcp\bridge\SolidWorksBridge\SolidWorksBridge.csproj -c Release
python -m compileall apps\demo-backend\src
cmd /c npm.cmd run build
```

Result:

- `SolidWorksBridge` build passed.
- Backend compile check passed.
- Frontend build passed.
- Full MCP App build is currently blocked by the running `.NET Host (124880)` locking the output DLL; stop the old MCP before publishing/validating.

Next:

- Stop the old MCP Hub.
- Rebuild/restart the updated MCP.
- Run `Common Base` again.
- If B/C are still mismapped, `faceSelection.diagnostics` should show exactly why the best candidate was rejected.

### 2026-06-26 - SelectFaceByName Strong Validation Real Test Result

Test actions:

- Stopped the old MCP Hub.
- Built the updated MCP App.
- Started the updated MCP Hub in the background.
- Called backend endpoints:
  - `POST /api/demo/reset`
  - `POST /api/demo/initialize-common-base`
  - `POST /api/demo/finalize-common-base`

Result:

- `InitializeCommonBaseAssembly` successfully regenerated `demo/ABC_arrange_demo.SLDASM`.
- `FinalizeCommonBaseAssembly` returned:

```text
FinalizeCommonBaseAssembly completed with bottom face orientation probe errors.
```

- Initial selection and mate:
  - A-1 face selection succeeded;
  - B-1 face selection succeeded, `swAddMateError_NoError`;
  - C-1 face selection succeeded, `swAddMateError_NoError`.
- PreMate correction:
  - B-1 attempted rotation correction, but validation failed and the component was rolled back;
  - C-1 was not rotated because its pre-mate normal already matched A.
- Final orientation check:
  - A-1 succeeded, `matchesBase=true`;
  - B-1 was rejected by strong validation, `faceSelection.success=false`, reason:

```text
center distance 0.407875m > 0.002000m
```

  - C-1 was rejected by strong validation, `faceSelection.success=false`, reason:

```text
center distance 0.280773m > 0.002000m
```

Conclusion:

- Strong validation is working: it no longer treats a clearly displaced candidate as the mapped bottom face.
- The failure moved from "wrong small face selected and later orientation mismatch" to "face selection fails clearly with diagnostics".
- The deeper issue is that after rotation/mate, the saved leaf-local center no longer matches the recovered candidate, so the current local-center-based mapping does not cover this pose-change scenario.

Next:

1. Unify the `face_mappings.json` path first to avoid mapping-file drift.
2. Evaluate SolidWorks face persistent reference as the more stable long-term solution.
3. Alternatively, update the mapping localCenter after Transform2 rotation/mating before later probes.
4. As a short-term Common Base path, save pre/post-common-base mapping snapshots so post-rotation checks do not rely on stale localCenter values.

### 2026-06-26 - Unified face_mappings path and first Persistent Reference pass

Goal:

- Make the backend and MCP use the same `face_mappings.json` file.
- Record SolidWorks Persistent Reference data when a face is mapped, then prefer that reference when selecting the same `IFace2` later.
- Validate that the new code does not break the current Initialize / Common Base workflow.

Completed:

- The backend default `DEMO_FACE_MAPPING_PATH` now points to:

```text
artifacts\solidworks-mcp\face_mappings.json
```

- `SelectionService` now:
  - resolves the mapping path from `DEMO_FACE_MAPPING_PATH`;
  - creates the mapping directory before writing;
  - stores `persistentReferenceBase64` in `RecordFaceMapping`;
  - tries SolidWorks `GetObjectByPersistReference3` first in `SelectFaceByName`;
  - falls back to the existing strong geometry candidate validation if the persistent reference is missing or fails.
- `DemoTools.HasFaceMapping` now reads the same environment-variable-driven mapping path.
- `InitializeCommonBaseAssembly` now reuses an existing target assembly:
  - if `demo\ABC_arrange_demo.SLDASM` already exists, it opens/reuses it;
  - it no longer always creates a new assembly and overwrites the same path, avoiding SolidWorks `SaveAs3` failures when the target file is already open.

Validation:

```cmd
python -m compileall apps\demo-backend\src
dotnet build vendor\solidworks-mcp\bridge\SolidWorksBridge\SolidWorksBridge.csproj -c Release
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

Result:

- Backend compile check passed.
- `SolidWorksBridge` build passed.
- `SolidWorksMcpApp` build passed.
- The updated MCP Hub was started with:

```text
DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

- `/api/health` reports the unified mapping path.
- Backend endpoint validation:
  - `POST /api/demo/reset` passed;
  - `POST /api/demo/initialize-common-base` passed and reused the existing `ABC_arrange_demo.SLDASM`;
  - `POST /api/demo/finalize-common-base` still failed at face-mapping/orientation probe validation.

Key finding:

- Path unification is active. The latest probe reports:

```text
D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
```

- The current A/B/C mappings are old entries and do not yet include `persistentReferenceBase64`, so this validation still used the geometry fallback.
- B/C still fail strong validation after pose changes:
  - B-1 best candidate rejected: `center distance 0.407875m > 0.002000m`
  - C-1 best candidate rejected: `center distance 0.280773m > 0.002000m`
- Persistent Reference support is implemented, but a clean re-record of the bottom faces is required before it can be validated in the real Common Base workflow.

Next:

1. Re-record A/B/C bottom faces from a clean initialized assembly so `persistentReferenceBase64` is written.
2. Run Common Base again and verify that `SelectFaceByName` recovers faces through Persistent Reference before falling back to geometry.
3. If Persistent Reference is not stable after save/reopen or mate operations, implement a post-common-base face mapping snapshot as the workflow-level fallback.

### 2026-06-29 - Persistent Reference + Common Base real validation passed

Test actions:

- Manually selected the real bottom faces for A/B/C in `ABC_arrange_demo.SLDASM`.
- Recorded them through the backend `POST /api/demo/record-selected-face` debug endpoint.
- Confirmed `artifacts\solidworks-mcp\face_mappings.json` contains `persistentReferenceBase64` for:
  - A-1 `底面`;
  - B-1 `底面`;
  - C-1 `底面`.
- Ran:

```text
POST /api/demo/finalize-common-base
```

Result:

- Backend returned:

```text
status=ok
commonBaseReady=true
```

- `orientationChecks`:
  - A-1: `matchesBase=true`, selected via Persistent Reference;
  - B-1: `matchesBase=true`, selected via Persistent Reference;
  - C-1: `matchesBase=true`, selected via Persistent Reference.
- `orientationCorrections`:
  - B-1: `PreMateTransform2` did not rotate because the bottom-face normal already matched;
  - C-1: `PreMateTransform2` did not rotate because the bottom-face normal already matched.

Conclusion:

- Persistent Reference resolved the previous Common Base failure where B/C geometry fallback was rejected by `center distance ... > 0.002m`.
- With refreshed A/B/C bottom-face mappings, the current workflow can finalize Common Base successfully.
- Next validation should focus on `Replay Layout` after Common Base is ready.
### 2026-06-29 - Replay Layout backend real validation passed

Test actions:

- Checked `demo/captured_common_base_layout.json` after `Common Base` had already completed and `commonBaseReady=true`.
- Confirmed the captured layout is valid:
  - `success=true`
  - `baseComponentName=A-1`
  - three components: A-1, B-1, C-1
  - `layout2d` contains A at the origin and relative 2D coordinates for B/C.
- Ran the backend endpoint:

```text
POST /api/demo/apply-captured-layout
```

Result:

- Backend returned:

```text
status=ok
lastRunStatus=ok
commonBaseReady=true
```

- MCP returned:

```text
ApplyCapturedCommonBaseLayout completed.
```

- A/B/C all recovered their bottom faces through Persistent Reference.
- A/B/C component moves all succeeded.
- Result screenshot was generated:

```text
demo\apply_captured_layout_result.png
```

Conclusion:

- The backend core workflow for "after Common Base, replay captured layout2d to restore component positions" is now validated.
- Persistent Reference remained effective during Replay Layout, so the previous B/C geometry-mapping drift did not reappear in this run.
- Next recommended check is a visual inspection in SolidWorks and one frontend end-to-end run through the `Replay Layout` button.
### 2026-06-29 - X_reference creation attempt blocked by MCP Hub/Proxy

Goal:

- Start from the current common-base `ABC_arrange_demo.SLDASM`.
- Move B-1/C-1 in the common-base plane and rotate them around the bottom-face normal without intentionally breaking the common-base relationship.
- Save the result as:

```text
demo\X_reference.SLDASM
```

- Capture a new layout2d from `X_reference.SLDASM`:

```text
demo\x_reference_layout2d.json
```

Attempted MCP plan:

1. `OpenDocument(ABC_arrange_demo.SLDASM)`
2. `MoveComponent(B-1, dx=0.04, dy=0, dz=0.03)`
3. `RotateComponent(B-1, axis=(0,-1,0), angle=20deg)`
4. `MoveComponent(C-1, dx=-0.03, dy=0, dz=0.04)`
5. `RotateComponent(C-1, axis=(0,-1,0), angle=-15deg)`
6. `SaveDocumentAs(demo\X_reference.SLDASM, saveAsCopy=true)`
7. `CaptureCommonBaseLayoutFromAssembly(..., output=demo\x_reference_layout2d.json)`

Observed result:

- Both the official backend endpoint and the temporary direct MCP plan failed during MCP connection setup:

```text
MCP execution failed: McpProtocolError: Unhandled exception.
System.IO.IOException: The server shut down unexpectedly.
```

- After restarting the MCP Hub, the startup log appeared briefly, but the named pipe was unavailable:

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

- The following files were not generated:

```text
demo\X_reference.SLDASM
demo\x_reference_layout2d.json
demo\x_reference_result.png
```

Conclusion:

- The current blocker is not the CAD operation plan itself; it is the MCP Hub/Proxy connection chain.
- Automatic SolidWorks edits cannot continue until the `SolidWorksMcpHub` pipe is reliably available again.
- Once the Hub is restored, the MCP plan above can be rerun to create `X_reference`.

### 2026-06-29 - Direct MCP stdio stabilized and X_reference verified

Goal:

- Reduce dependency on the long-lived `SolidWorksMcpHub` named pipe and tray session.
- Fix DLL-mode proxy startup instability when running `dotnet SolidWorksMcpApp.dll --proxy`.
- Complete the previously blocked `X_reference` creation, rotation, save, and layout2d capture flow.

Code changes completed:

- Added `--stdio-direct` mode to `SolidWorksMcpApp`, allowing backend automation to call MCP tools through direct stdio without Hub/proxy.
- Added `--headless-hub` mode for cases where a named-pipe Hub is still needed without a tray UI.
- Fixed DLL-mode proxy Hub startup: `Environment.ProcessPath` points to `dotnet.exe` in DLL mode, so the old logic could launch bare `dotnet` and cause `server shut down unexpectedly`.
- Updated backend default MCP args: when `DEMO_MCP_COMMAND=dotnet` and `DEMO_MCP_CWD` contains `SolidWorksMcpApp.dll`, the backend now defaults to `SolidWorksMcpApp.dll --stdio-direct`.
- Made `McpToolRunner` tolerate leading stdin BOM/whitespace so PowerShell ad-hoc debug calls do not fail JSON parsing.

Verification:

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` passed.
- `dotnet build apps\demo-backend\tools\McpToolRunner\McpToolRunner.csproj -c Release` passed.
- `python -m compileall apps\demo-backend\src` passed.
- Through direct stdio MCP, executed:
  1. open `demo\ABC_arrange_demo.SLDASM`;
  2. move B-1 / C-1 in the common-base plane;
  3. rotate B-1 / C-1 around the common bottom-face normal;
  4. save as `demo\X_reference.SLDASM`;
  5. capture layout2d from `X_reference.SLDASM` to `demo\x_reference_layout2d.json`;
  6. open `X_reference.SLDASM` and export `demo\x_reference_result.png`.

Generated outputs:

```text
demo\X_reference.SLDASM
demo\x_reference_layout2d.json
demo\x_reference_result.png
```

Key observations:

- `x_reference_layout2d.json` reports `success=true`.
- A/B/C bottom faces were recovered through Persistent Reference.
- B/C `sourceTransform` values include rotation matrices, confirming rotation was captured into the layout data.
- A/B/C bottom-face world normals remain close to `[0, -1, 0]`, so this rotation path preserved the common-base relationship.

Conclusion:

- The main instability was the MCP Hub/proxy startup chain, not the CAD operation plan itself.
- The currently preferred backend automation path is now `McpToolRunner -> dotnet SolidWorksMcpApp.dll --stdio-direct -> SolidWorks COM`.
- Rotation remains a CAD-constraint risk in general, but the tested “common-base, rotate around bottom-face normal” workflow passed for A/B/C.

### 2026-06-29 - X_reference_spread reference and layout2d recapture

Goal:

- Starting from `X_reference.SLDASM`, move B-1 / C-1 farther while preserving the common-base relationship.
- Recapture layout2d for the next “new assembly replay” test.

Actions:

- The current common-base normal is close to global `Y`, so this run only moved components along global `X/Z` and avoided global `Y`.
- B-1 move:

```text
deltaX=0.12, deltaY=0, deltaZ=0
```

- C-1 move:

```text
deltaX=-0.10, deltaY=0, deltaZ=0.06
```

- Direct save to `X_reference.SLDASM` failed with a read-only/sharing save error because the file was already open, so the result was saved as:

```text
demo\X_reference_spread.SLDASM
```

Issue found and fixed:

- Initially, B/C `sourceTransform` changed, but captured `layout2d` did not.
- Root cause: `GetSelectedFaceMappingProbe` treated the center of `IFace2.GetBox()` as a world-space center. In nested subassembly cases, that center behaves like a leaf/local-space center, so top-level component movement was not reflected in the captured bottom-face world center.
- Fixed probe logic:
  - `localCenter = BoxCenter(face.GetBox())`
  - `worldCenter = leafComponent.GetTotalTransform(true) * localCenter`
  - world normals also prefer the total transform.

Verification:

- `SolidWorksMcpApp` rebuild passed.
- Recaptured `demo\x_reference_layout2d.json` with `success=true`.
- Exported screenshot:

```text
demo\x_reference_spread_result.png
```

Captured layout2d:

```text
A-1: x=0, y=0
B-1: x=0.552681, y=0.180535
C-1: x=0.258654, y=0.144401
```

Common-base check:

- A/B/C `bottomCenterWorld.Y` are all approximately `-0.499264`.
- A/B/C `bottomNormalWorld` are all close to `[0, -1, 0]`.

Conclusion:

- A stronger reference assembly is now available:

```text
demo\X_reference_spread.SLDASM
```

- The corresponding target layout is available at:

```text
demo\x_reference_layout2d.json
```

- Next step: create a fresh assembly, import A/B/C, run Common Base, then replay this layout2d and compare against `X_reference_spread`.

### 2026-06-29 - Fresh-assembly Replay Layout loop passed

Test goal:

- Create a fresh assembly.
- Insert A/B/C.
- Run Common Base.
- Replay `demo\x_reference_layout2d.json`.
- Capture layout2d again from the replayed assembly and compare it with the `X_reference_spread` target layout.

Generated files:

```text
demo\ABC_replay_from_x_reference.SLDASM
demo\abc_replay_initialize.png
demo\abc_replay_common_base.png
demo\abc_replay_from_x_reference_result.png
demo\abc_replay_from_x_reference_layout2d.json
```

Execution result:

- `InitializeCommonBaseAssembly` succeeded.
- `FinalizeCommonBaseAssembly` succeeded.
- B-1 triggered `PreMateTransform2` orientation correction during Common Base and passed final orientation checks.
- A/B/C bottom faces were recovered through Persistent Reference.
- `ApplyCapturedCommonBaseLayout` succeeded.

Issue found and fixed during the test:

- The first replay result did not match the target layout2d.
- Root cause: `ApplyCapturedCommonBaseLayout` still used the old `GetSelectedFaceCenter()` path, whose center was not transformed through `GetTotalTransform(true)`.
- Fixed by using `GetSelectedFaceMappingProbe().WorldCenter` as the current bottom-face center during replay.

Final numeric comparison:

```text
A-1 expected=(0, 0), actual=(0, 0), error=0
B-1 expected=(0.5526811272380519, 0.1805345745326763),
    actual=(0.5526811272380519, 0.18053457453267627),
    error=2.78e-17
C-1 expected=(0.25865398947636403, 0.14440055932749202),
    actual=(0.25865398947636403, 0.144400559327492),
    error=2.78e-17
```

Conclusion:

- The core loop now works: capture layout2d from a reference assembly, create a fresh assembly, insert components, run Common Base, replay layout2d, and recover the 2D bottom-center positions.
- This validates 2D position restoration. Full component orientation restoration remains a future Transform2 replay enhancement.

### 2026-06-29 - Layout2D In-Plane Theta Replay Passed

Goal:

- Extend `layout2d.x/y` replay with `layout2d.thetaDegrees/thetaAxis`.
- Capture the source assembly's in-plane component rotation around the common-base normal.
- After Common Base in a fresh assembly, restore both bottom-center position and in-plane component rotation.

Implementation notes:

- `CommonBaseLayout2d` now includes:
  - `ThetaDegrees`
  - `ThetaAxis`
- Layout capture now stores component `Transform2` `XAxis/YAxis/ZAxis`.
- A fixed X axis is not reliable because some component X axes can be nearly parallel to the common-base normal.
- Added `ProjectPointWithRotation()`, which chooses the Transform2 axis with the strongest projection onto the common-base plane.
- Layout replay now:
  1. reads the current Transform2 axis named by `thetaAxis`;
  2. calculates the delta between current theta and target theta;
  3. rotates around `baseFrame.Normal`;
  4. probes the bottom face center again;
  5. moves the component so the bottom center reaches target `layout2d.x/y`.

Issue found and fixed:

- The first real loop restored x/y exactly but inverted theta:
  - B-1 target `-20deg`, actual `+20deg`.
  - C-1 target `+15deg`, actual `-15deg`.
- Root cause: `RotateComponent` angle sign is opposite to the layout projection convention.
- To avoid changing other rotation flows, only theta replay in `ApplyCapturedCommonBaseLayout` negates the rotation angle.

Verification:

- `dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release` passed.
- Added `CommonBaseLayoutMathTests`, but `dotnet test` was blocked by Windows application control policy while loading the test DLL. This was an environment block, not an assertion failure.
- Real SolidWorks loop passed:

```text
Reference layout: demo\x_reference_layout2d_theta.json
Replay assembly: demo\ABC_replay_from_x_reference_theta_signfix.SLDASM
Recaptured replay layout: demo\abc_replay_from_x_reference_theta_signfix_layout2d.json
```

Final comparison:

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

Conclusion:

- The loop now works for reference layout2d position + theta capture, fresh assembly creation, Common Base, and replay of both 2D position and in-plane rotation.
- Theta is the projected angle of a selected component Transform2 axis on the common-base plane. It is not a full 3D pose restore, but it satisfies the current stage goal of restoring planar layout and heading on the common base.

### 2026-06-30 - Demo Version Pre-Commit Stabilization

Goal:

- After the demo version was completed, stabilize the engineering workflow before creating a local commit.
- Reduce `git status` noise and avoid accidentally committing temporary CAD files, screenshots, logs, or IDE caches.
- Add reproducibility notes for later regression tests or PR preparation.

Completed:

- Updated `.gitignore`:
  - ignored `demo/**/*.SLDASM`, `demo/*.png`, and intermediate `demo/*.json` files;
  - allowed only the final layout samples:
    - `demo/x_reference_layout2d_theta.json`
    - `demo/abc_replay_from_x_reference_theta_signfix_layout2d.json`;
  - ignored `logs/`, `apps/demo-frontend/tsconfig.tsbuildinfo`, and root scratch files.
- Updated `apps/demo-backend/README.md`:
  - documented the current stable direct MCP stdio path;
  - updated backend startup, health check, and endpoint list.
- Updated `apps/demo-frontend/README.md`:
  - documented the current demo workflow;
  - recommended this order: `Reset -> Initialize -> Common Base -> Capture Layout -> Replay Layout`.
- Added pre-commit checklists:
  - `docs/demo_stabilization_checklist-CN.md`
  - `docs/demo_stabilization_checklist.md`

Verification:

```text
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py apps\demo-backend\src
```

Result:

- build passed with 0 errors.
- Python compileall passed.

Current commit strategy:

- Commit locally first, without pushing.
- Commit source, scripts, tests, docs, `.gitignore`, and the two final layout JSON samples.
- Do not commit CAD binaries, screenshots, logs, runtime state, or cache files.

### 2026-06-30 - First Productization Pass

Goal:

- Support n subassemblies instead of hard-coding A/B/C into the frontend/backend workflow.
- Let the frontend choose or upload layout JSON.
- Display layout2d `x/y/theta` per component.
- Add batch face-mapping verification to catch a bad component mapping before Common Base or Replay.

Completed:

- Backend state now includes:
  - `layoutJsonPath`
  - `layoutInfo`
- Added layout JSON management APIs:
  - `GET /api/demo/layout-json-files`
  - `POST /api/demo/select-layout-json`
  - `POST /api/demo/upload-layout-json`
- Selecting or uploading a layout JSON parses its `components` array and can sync any number of components into the current demo state.
- `ApplyCapturedCommonBaseLayout` now prefers the selected `layoutJsonPath` from state.
- Added:
  - `POST /api/demo/verify-face-mappings`
- Batch verification behavior:
  1. first checks whether each component bottom-face mapping exists in `face_mappings.json`;
  2. returns `blocked` immediately when mappings are missing;
  3. otherwise generates `select_face_by_name` + `get_selected_face_mapping_probe` calls for each component.
- Frontend now includes:
  - layout JSON selector;
  - layout JSON upload button;
  - layout2d summary;
  - Layout X / Layout Y / Theta columns in the component table;
  - `Verify Faces` button;
  - theta target/current/delta in replay results.
- Component color fallback now hashes component id/name, so the UI can display more than A/B/C.

Verification:

```text
python -m compileall apps\demo-backend\src
cmd /c npm run build
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
```

Result:

- Backend Python compilation passed.
- Frontend TypeScript/Vite build passed.
- MCP App build passed.

Non-CAD backend loop:

- `list_layout_json_files()` finds captured layout JSON files.
- `select_layout_json(demo/x_reference_layout2d_theta.json)` succeeds and syncs A/B/C target x/y from layout2d.
- `upload_layout_json(uploaded_theta_test.json)` saves under `demo/uploaded_layouts/` and syncs components.
- `verify_face_mappings()` generated 6 planned calls under the current dry-run config: 3 components × select/probe.

Note:

- Real batch face-mapping verification depends on the active SolidWorks assembly containing the corresponding component instances.
- For a real n-component validation, first open or initialize the target assembly containing those components.
### 2026-06-30 - Frontend Uploaded Layout JSON Real Loop Passed

Goal:
- Verify that the first n-component productization pass did not break the stable A/B/C demo workflow.
- Verify that the frontend can upload `x_reference_layout2d_theta.json`, then run `Initialize -> Verify Faces -> Common Base -> Replay Layout`.
- Verify that the replayed SolidWorks geometry matches the uploaded layout `x/y/theta`.

Actual test sequence:

```text
Reset
Upload demo\x_reference_layout2d_theta.json
Initialize
Verify Faces
Common Base
Replay Layout
```

Backend log result:
- `/api/demo/reset` returned 200.
- `/api/demo/upload-layout-json` returned 200.
- `/api/demo/initialize-common-base` returned 200.
- `/api/demo/verify-face-mappings` returned 200.
- `/api/demo/finalize-common-base` returned 200.
- `/api/demo/apply-captured-layout` returned 200.

Replay state:
- `lastRun.status=ok`
- `lastRun.toolSuccess=true`
- `lastRun.toolMessage=ApplyCapturedCommonBaseLayout completed.`
- `commonBaseReady=true`
- Current `layoutJsonPath` points to `demo\uploaded_layouts\x_reference_layout2d_theta.json`.

MCP geometry recheck:
- Captured the current replayed `ABC_arrange_demo.SLDASM` layout again and compared it with the uploaded layout.
- A-1: `xy_error=0.0m`, `theta_error=0.0deg`
- B-1: `xy_error=1.72e-15m`, `theta_error=0.0deg`
- C-1: `xy_error=1.78e-15m`, `theta_error=0.0deg`

Conclusion:
- The frontend JSON upload, component sync, batch face verification, Common Base, and Replay Layout loop passed in real SolidWorks.
- The current version can drive A/B/C `x/y/theta` restoration from an uploaded layout JSON.
- Some terminal/log output may still show mojibake for Chinese `底面` or degree symbols, but it did not affect this run.
### 2026-06-30 - Engineering Stabilization Round 2: Health Check and Replay Error Report

Goal:
- Reduce the risk of operating on the wrong SolidWorks/MCP instance or active document.
- Automatically produce a geometry recheck after Replay Layout, instead of relying only on a manual second capture.
- Keep the change low-risk by enhancing backend orchestration rather than changing the underlying SolidWorks tools.

Completed:
- Added `GET /api/demo/mcp-health`:
  - calls MCP `get_active_document`;
  - returns the current SolidWorks active document;
  - when `demo_state.json` has an `assemblyPath`, reports whether the active document matches it.
- Added an active assembly consistency check before `Verify Faces`:
  - when `assemblyPath` exists and MCP is not in dry-run mode, the backend checks the active document first;
  - if the active assembly differs from `demo_state.json.assemblyPath`, the operation returns `blocked`.
- Added automatic post-Replay validation:
  - after successful replay, the backend calls `capture_common_base_layout_from_assembly`;
  - writes `demo/replay_validation_layout2d.json`;
  - compares captured `layout2d.x/y/theta` with the selected target layout JSON;
  - stores per-component `xyError/thetaErrorDegrees` and max errors in `state.lastRun.replayValidation`.
- Added frontend `Replay Check` display:
  - max XY error;
  - max theta error;
  - per-component error and pass/fail status.

Verification:

```text
python -m compileall apps\demo-backend\src
cmd /c npm run build
```

Result:
- Backend compilation passed.
- Frontend TypeScript/Vite build passed.

Service-level dry-run validation:
- `mcp_health()` returns `dry-run`.
- `list_layout_json_files()` lists layout JSON files.
- `select_layout_json(demo/x_reference_layout2d_theta.json)` succeeds with 3 components.
- `verify_face_mappings()` generates 6 planned calls in dry-run.
- `_compare_layout_payloads(target, target)` returns `success=true` with zero max XY/theta error.

Note:
- This round does not change the C# MCP tool behavior, so it has low impact on the already validated Common Base / Replay core loop.
- Real SolidWorks validation of `Replay Check` requires restarting the backend and running Replay Layout once from the frontend.
