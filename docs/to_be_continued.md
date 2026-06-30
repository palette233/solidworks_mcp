# To Be Continued

## Automatic Common Base Orientation Correction Still Pending

### Date

- 2026-06-25

### Latest validation result

- After deleting the old `ABC_arrange_demo.SLDASM`, `Initialize -> Common Base` was run again.
- A/B/C were inserted successfully.
- B/C Coincident mates were created successfully with `bottomMateResult.errorName=swAddMateError_NoError`.
- `FinalizeCommonBaseAssembly` still returned `bottom face orientation mismatch`.
- The remaining failure comes from `orientationChecks`: B/C have `matchesBase=false`.

### Current conclusion

- The duplicate-mate regression has been narrowed down.
- The remaining core problem is automatic correction of B/C bottom-face orientation so their recorded bottom-face normals match A.

### Proposed implementation

- Read A/B/C recorded bottom-face `worldNormal`.
- Use A's `worldNormal` as the target direction.
- For B/C, compute the rotation axis and angle from the current normal to the target normal.
- Apply an explicit component rotation, then create or refresh the Coincident mate.
- Probe the bottom-face normal again and require the dot product to meet the threshold.

## Latest status for Common Base orientation fix

### Date

- 2026-06-25

### Current status

- The earlier "try multiple Coincident mate alignments + Undo(1)" approach showed a real regression risk: duplicate Coincident mates may be left behind.
- The current implementation has been restored to the stable strategy: create one Coincident mate per target component, then run orientation checks/reporting.
- `FinalizeCommonBaseAssembly` still returns `orientationChecks` so B/C bottom-face normals can be compared with A.
- If orientation does not match, the tool reports orientation mismatch, but it no longer attempts automatic correction by repeatedly adding/undoing mates.

### Pending validation

- A real SolidWorks validation pass is still required with a clean assembly.
- Validation should confirm:
  - each target component gets only one required Coincident mate;
  - duplicate Coincident mates are no longer created;
  - all three bottom faces are coplanar;
  - if B/C bottom normals still do not match A, the frontend reports a clear orientation mismatch.

### Future direction

- If automatic B/C bottom-face orientation correction is required, the next step should explicitly compute and apply corrective component rotation from the normal vectors before or after mating.
- The implementation should not probe SolidWorks behavior by repeatedly adding and undoing mate alignments.

## Components inserted by Initialize may be hidden

### Date

- 2026-06-25

### Symptom

- After `Initialize`, the user initially saw only C in the SolidWorks UI.
- State/log inspection showed A/B/C were inserted.
- The user later confirmed A/B were present but hidden in the component tree and became visible after manually setting them to show.

### Impact

- This is not an insertion failure, but it can make the demo look broken and may cause users to misread `InitializeCommonBaseAssembly` as incomplete.

### Future improvement

- Explicitly show/unhide inserted components after `InitializeCommonBaseAssembly`.
- Return component visibility state in the tool result and warn if a component is hidden.
- Optionally run `ZoomToFit` or refresh the active view after insertion.

## Small-Face Bottom Normal Fallback

### Background

During Common Base validation, a small selected face on `A-1` could be recorded and re-selected by the existing face-mapping logic, but its `localNormal` and `worldNormal` were recorded as `null`.

After selecting a larger planar face on the same component, normal recording succeeded. This shows the current normal-recording path is active and working for standard planar faces, but some small or ambiguous faces are not reliable normal sources.

### Current Behavior

The current implementation reads a face normal through:

- `IFace2.GetSurface()`
- `ISurface.IsPlane()`
- `ISurface.PlaneParams`
- `IFace2.FaceInSurfaceSense()`

If this path cannot produce a valid non-zero normal, the mapping stores:

```json
"localNormal": null,
"worldNormal": null
```

This is intentional after the zero-normal guard fix. It prevents invalid normals such as `[0,0,0]` from being used as Common Base orientation baselines.

### Problem

Some small faces may still be useful for selection tests, but they are not currently suitable as Common Base bottom-face references because orientation validation requires a valid planar normal.

Possible causes:

- The face is not recognized by SolidWorks as a simple planar surface.
- The face is a small split, transition, thin, chamfer, or ambiguous topology face.
- Mouse/ray selection may select a nearby narrow face rather than the visually intended bottom face.
- Nested assembly transforms may expose weak or missing surface metadata.

### Proposed Future Work

If small-face support becomes necessary, add a fallback normal extraction path:

1. Try the current `PlaneParams` path first.
2. If `PlaneParams` fails, collect face geometry samples using one or more SolidWorks APIs:
   - face tessellation / triangulation data,
   - face boundary / loop vertices,
   - edge curve endpoints where available.
3. Fit a plane from sampled points.
4. Compute a normal from the fitted plane.
5. Validate the fitted normal:
   - enough non-collinear points,
   - low point-to-plane residual,
   - normal length above tolerance.
6. Store normal metadata with a source flag, for example:

```json
"normalSource": "planeParams"
```

or:

```json
"normalSource": "fittedFromFaceSamples"
```

### Acceptance Criteria

- A small planar face that fails `PlaneParams` can still produce a valid `localNormal/worldNormal` through fitting.
- Non-planar or noisy faces are rejected with a clear message instead of producing misleading normals.
- `face_mapping_record_probe.py` prints the normal source.
- `face_mapping_verify_select.py` compares fitted normals consistently.
- `FinalizeCommonBaseAssembly` can use fitted normals only when validation quality is high enough.

### Current Recommendation

Do not block the current demo on this enhancement. For the first complete validation, use larger, clearly planar bottom faces for A/B/C, then verify the full workflow:

1. Initialize assembly.
2. Record valid bottom faces with normals.
3. Finalize Common Base.
4. Move components from frontend coordinates.

## Automatic Bottom-Face Orientation Correction

### Background

`FinalizeCommonBaseAssembly` can currently detect bottom-face orientation mismatches after creating coincident mates. In the latest validation, A/B/C became coplanar, C's bottom-face orientation matched A, but B's bottom face was flipped relative to A.

The frontend correctly showed:

```text
FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.
error / base pending
```

and disabled Arrange because `commonBaseReady=false`.

### Current Behavior

- A/B/C bottom faces can be selected.
- Coincident mates for B and C can be created successfully.
- Orientation validation compares each component's bottom-face `worldNormal` against A's baseline normal.
- If any component normal does not match A within the configured threshold, the tool fails Common Base readiness.

This behavior is correct for safety, but it only detects the problem. It does not fix component orientation.

### Problem

For the full assembly-recovery workflow, common base should mean:

- bottom faces are coplanar,
- bottom-face normals point consistently,
- subsequent 2D movement does not break the established base relationship.

If B is coplanar but upside down, the current workflow blocks movement. This protects the model, but it prevents a complete automated demo unless the user manually fixes B.

### Proposed Future Work

Add automatic orientation correction to the MCP high-level common-base workflow:

1. Read A's bottom-face normal as the baseline.
2. Read each other component's bottom-face normal.
3. If a component's normal is opposite to A:
   - try an alternate mate alignment first, or
   - rotate/flip the component around a suitable in-plane axis, then reapply/verify mate.
4. Re-probe bottom-face normals after correction.
5. Only set `commonBaseReady=true` when:
   - mate creation succeeds,
   - faces are coplanar,
   - bottom-face normals match the baseline.

### Acceptance Criteria

- A/B/C can be finalized into a common base without manual flipping when one component starts upside down.
- Orientation correction does not move components off the common plane.
- `orientationChecks` clearly report before/after normals and correction actions.
- Frontend can show whether Common Base was completed directly or after automatic correction.

### Current Recommendation

Keep this as a follow-up enhancement. For the current validation round, focus on verifying the newly introduced Transform2 capture/layout functionality and use the current orientation mismatch result as proof that the validation guard works.

## Why This Workflow Is More Valuable Than a Pure Transform2 Plugin

### Question

Compared with a pure Transform2 plugin, what advantages does the current frontend + backend + MCP + Transform2-based reconstruction workflow provide?

### Answer

A pure Transform2 plugin is usually good at a direct matrix-level workflow:

```text
read component Transform2
save transform matrix
apply transform matrix in another assembly
```

That is useful for exact pose copying, but the current project is aiming at a more explainable and interactive assembly-reconstruction workflow.

### Main Advantages

1. Closer to the target business workflow.

   The current project does not only restore raw component poses. It introduces common-base semantics:

   ```text
   import subassemblies
   align bottom faces
   project bottom centers into a common 2D plane
   move components in that 2D layout
   ```

   This matches the intended demo better than blindly restoring a full Transform2 matrix.

2. Interactive frontend control.

   The frontend allows users to inspect state, drag 2D rectangles, edit coordinates, and execute staged operations. This makes the demo visible and controllable:

   ```text
   frontend 2D layout change
   -> backend sends target data
   -> MCP calls SolidWorks tools
   -> SolidWorks components move
   ```

3. Step-by-step verification.

   The workflow is split into clear phases:

   ```text
   Initialize
   Record / Verify Face Mapping
   Common Base
   Capture Layout
   Arrange
   ```

   Each phase can be tested independently, which is important for debugging CAD automation.

4. Bottom-face semantics, not just matrices.

   Transform2 alone does not know which face is the bottom face. The current workflow adds:

   - `RecordFaceMapping`
   - `SelectFaceByName`
   - `bottomFaceName`
   - `bottomCenterWorld`
   - `bottomNormalWorld`
   - `orientationChecks`

   This gives the system semantic knowledge of the assembly base plane.

5. Better fit for high-level MCP tools and LLM orchestration.

   Complex SolidWorks actions are wrapped into stable high-level MCP tools:

   - `InitializeCommonBaseAssembly`
   - `FinalizeCommonBaseAssembly`
   - `MoveComponentsOnCommonBase`
   - `CaptureCommonBaseLayoutFromAssembly`

   This allows an LLM or external app to call meaningful operations instead of composing many low-level APIs manually.

6. Easier path toward a semi-automatic reconstruction workbench.

   The current architecture can grow into a system that supports:

   - automatic bottom-face detection,
   - bottom-face orientation correction,
   - Transform2/layout capture,
   - frontend manual adjustment,
   - backend state persistence,
   - iterative assembly reconstruction.

### Tradeoff

A pure Transform2 plugin is still more direct if the only goal is exact pose restoration. It may be simpler and more precise for:

```text
copy original transform
paste original transform
```

The current project is stronger when the goal is:

```text
explainable
interactive
stage-verifiable
bottom-face-aware
LLM/MCP-callable
2D layout reconstruction with human adjustment
```

### Summary

The pure Transform2 plugin is best viewed as a matrix-level pose copy tool. The current project is better viewed as an assembly-layout reconstruction workflow with frontend interaction, backend state, semantic bottom-face mapping, MCP tool orchestration, and Transform2-based layout capture.

## MCP Publish/Runtime Directory Consistency

### Background

While implementing the first layout2d replay workflow, the MCP app was rebuilt successfully. Publishing to `artifacts/solidworks-mcp` could not overwrite the running executable because the old MCP process was still active, so the publish script wrote a new artifact directory:

```text
artifacts/solidworks-mcp-20260624-112354
```

Running `apply_captured_common_base_layout.py` against the new directory failed before tool execution:

```text
System.IO.IOException: The server shut down unexpectedly.
```

The new artifact log showed:

```text
Tray startup skipped because another hub instance is already running.
```

### Problem

The new MCP tool exists in the newly published executable, but the active hub is still the older `artifacts/solidworks-mcp` instance. This prevents validating newly added tools until the old MCP process is stopped and the new MCP build is launched.

### Resolution for Next Test

Before testing newly published MCP tools:

1. Stop the old `SolidWorksMcpApp.exe` processes.
2. Start the newly published MCP executable, or republish after the old process is stopped so `artifacts/solidworks-mcp` can be overwritten.
3. Copy or recreate `face_mappings.json` in the active MCP artifact directory.
4. Run the command-line tool again.

### Current Recommendation

For the next validation, either:

- restart MCP from `artifacts/solidworks-mcp-20260624-112354`, or
- stop MCP, republish to `artifacts/solidworks-mcp`, and use the default script paths.

## PowerShell npm Execution Policy Blocks Frontend Build Command

### Background

After exposing `Replay Layout` in the frontend, the frontend build needed to be verified.

### Symptom

Running this directly in PowerShell:

```cmd
npm run build
```

fails because the system blocks `npm.ps1`.

### Current Workaround

Use the CMD entry point instead:

```cmd
cmd /c npm.cmd run build
```

### Recommendation

- This is not a frontend code issue. It is a Windows PowerShell Execution Policy environment issue.
- Future Windows demo/test instructions should prefer `cmd /c npm.cmd ...` to avoid being blocked by PowerShell policy.

## Frontend Replay Layout Still Needs Real UI-Level Validation

### Current Status

- `ApplyCapturedCommonBaseLayout` has passed real SolidWorks validation through the command-line script.
- The frontend now has a `Replay Layout` button.
- The backend now exposes `/api/demo/apply-captured-layout`.
- The frontend build passes.

### Pending Validation

The next real-environment validation should:

1. Start the new MCP build.
2. Start the backend.
3. Start the frontend.
4. Confirm `ABC_arrange_demo.SLDASM` is initialized or open.
5. Click `Replay Layout` in the frontend.
6. Confirm SolidWorks replays component positions from captured `layout2d`.
7. Confirm the frontend Result and Screenshot sections update.

## Multiple SolidWorks Instances Can Make MCP Miss the User-Selected Face

### Time

- 2026-06-24

### Symptom

- The user selected the bottom face of `A-1` in SolidWorks.
- MCP returned this when calling `record_face_mapping`:

```text
No active document. Open or create a document first.
```

### Analysis

- Multiple `SLDWORKS.exe` processes are currently running.
- MCP connected to a SolidWorks instance with no active document.
- The SolidWorks UI where the user selected the bottom face is likely a different instance.

### Impact

- Manual face recording requires the user-operated SolidWorks instance and the MCP-connected SolidWorks instance to be the same one.
- If they differ, MCP cannot read the user's current selection even when the correct face is selected visually.

### Temporary Workaround

1. Save any SolidWorks documents that should be kept.
2. Close extra SolidWorks windows/processes and keep only one SolidWorks instance.
3. Reopen:

```text
demo/X_reference.SLDASM
```

4. Select the real bottom face of `A-1` in that single instance.
5. Run face recording again.

### Follow-Up Improvement

- Add an MCP health tool that returns the connected SolidWorks process, active document title, and active document path.
- Before face recording, check that the active document is the expected `X_reference.SLDASM`.
- If multiple SolidWorks processes are detected, return a clear warning.

## Validate Common Base Orientation-Aware Mate Retry in Real SolidWorks

### Time

- 2026-06-25

### Current Status

- `FinalizeCommonBaseAssembly` now tries multiple coincident mate alignments.
- After each successful mate it probes the target bottom-face normal.
- If the normal does not match the base component, the tool undoes that mate and tries the next alignment.
- The code builds successfully.

### Pending Validation

This still needs a real SolidWorks run with the new MCP build:

1. Publish the updated MCP.
2. Stop old `SolidWorksMcpApp.exe` instances.
3. Start the newly published MCP.
4. Initialize an assembly with A/B/C.
5. Record/verify bottom faces if needed.
6. Run `FinalizeCommonBaseAssembly`.
7. Confirm:
   - bottom faces are coplanar;
   - B/C bottom-face normals match A;
   - frontend no longer reports `bottom face orientation mismatch`.

### Remaining Risk

If SolidWorks resolves all tried coincident mate alignments to the same physical orientation for a specific face pair, the retry mechanism will still fail with `BottomFaceOrientationMismatch`. In that case the next improvement should rotate the component explicitly before or after mating, using the normal vectors to compute a correction transform.

## Validate Small-Face Normal Fallback and Frontend Capture Layout

### Time

- 2026-06-25

### Current Status

- Small-face normal fallback has been implemented:
  - primary path: `PlaneParams`;
  - fallback path: tessellated normals;
  - fallback path: fitted normal from tessellated triangle points.
- Unit tests cover the tessellation fitting helper.
- Frontend now exposes `Capture Layout`.
- Backend now exposes `/api/demo/capture-common-base-layout`.
- Latest published MCP build: `artifacts/solidworks-mcp-20260625-163843`.

### Pending Real Validation

1. Restart MCP from `artifacts/solidworks-mcp-20260625-163843`.
2. Open or initialize an assembly with known A/B/C bottom-face mappings.
3. Select and record a previously problematic small bottom face.
4. Verify that `face_mappings.json` now contains `localNormal` and `worldNormal` instead of `null`.
5. Run frontend `Capture Layout`.
6. Confirm `demo/captured_common_base_layout.json` updates.
7. Run frontend `Replay Layout`.
8. Confirm component positions replay from the newly captured layout.

### Remaining Risk

- SolidWorks tessellation APIs can vary by face type and document state. If both tessellated normals and tessellated triangle points are unavailable, small faces may still return `normal=null`.
- If triangle point ordering is inconsistent for some topology, the fitted normal direction may need an additional orientation check against surrounding geometry or component transform.

## Common Base Orientation Auto-Correction Still Needs a Second-Phase Design

### Time

- 2026-06-25

### Current Progress

- A first explicit-rotation correction path has been implemented:
  - computes a rotation axis and angle from the base bottom-face normal and target bottom-face normal;
  - tries both positive and negative angle directions;
  - rolls the component back when the correction cannot be confirmed;
  - returns `orientationCorrections` for diagnostics.
- Build and unit-level validation passed.

### Real Validation Problems

- For B, after rotation the selected recorded face returned `normal=null`, so the tool could not confirm whether the orientation was fixed.
- For C, the face normal matched A before the coincident mate, but mismatched after mating. This suggests the mate solver itself can still change component orientation.
- Therefore the first pre-mate explicit-rotation strategy is not enough to solve bottom-face orientation consistently.

### Recommended Follow-Up

1. Split correction into two phases:
   - optional pre-mate correction;
   - mandatory post-mate orientation check and second explicit correction.
2. Preserve the established common-base relation during the second correction:
   - rotate in a controlled way around the common-base frame or bottom-center anchor;
   - move the bottom center back after rotation to prevent layout2d drift.
3. Improve face re-identification after rotation:
   - keep matching by normal, area, local center, and leaf full name;
   - add candidate-face scanning when `SelectFaceByName` succeeds but the selected face probe returns `normal=null`.
4. Add diagnostic tools:
   - list current mates;
   - detect duplicate coincident mates;
   - report each component bottom normal, bottom center, and Transform2.
5. Validate with a minimal real SolidWorks sample first:
   - start with A/B only;
   - verify common-base plus orientation correction;
   - then scale back to A/B/C and larger assemblies.

### Not Recommended

- Do not return to repeated add/undo mate-alignment guessing. That path has already shown duplicate-mate regression risk.

### 2026-06-26 Update

- A first `PostMate` second-phase correction path has been integrated:
  - create the coincident mate once;
  - rebuild;
  - explicitly rotate by bottom-face normals;
  - run the final orientation check.
- `orientationCorrections` now includes a `Stage` field. The expected value for this path is `PostMate`.

Still pending:

1. Publish the updated MCP and validate in real SolidWorks.
2. If B still returns `normal=null` after rotation, implement candidate-face scanning fallback.
3. If post-mate explicit rotation is constrained by mates, consider:
   - temporarily suppressing the relevant mate during correction;
   - or setting orientation through Transform2 before mating and using mate only as a final verification;
   - or adding a dedicated Transform2 setter to remove uncertainty from `RotateComponent` multiplication order.
4. Add a mate diagnostic tool that lists mates in the active assembly and flags duplicate coincident mates.

### 2026-06-26 Update: PostMate Rotation Disabled by Default

- A real run produced a `Common Base` timeout.
- The likely cause is `RotateComponent` running after Coincident mates were already created, forcing SolidWorks into a long constraint solve.
- `enablePostMateOrientationCorrection` now defaults to `false`.
- Future automatic orientation correction should prefer:
  1. mate diagnostics and mate suppression;
  2. suppressing related mates before rotation, then restoring them;
  3. or setting initial orientation through Transform2 before mating;
  4. avoiding direct component rotation while the component is strongly constrained by mates.

### 2026-06-26 Update: Strategy 3 Selected and Implemented

- Pre-mate Transform2 orientation correction has been integrated.
- `enablePreMateOrientationCorrection` defaults to `true`.
- The default flow now corrects component orientation before creating mates.
- PostMate rotation remains available as an experimental switch, but it stays disabled by default.

Still pending:

1. Publish the updated MCP and validate in real SolidWorks.
2. If B/C still cannot reliably probe normals after correction, implement candidate-face scanning fallback.
3. If Transform2 rotation direction remains unstable, add a more explicit Transform2 setter instead of relying on the current `RotateComponent` matrix multiplication behavior.

### 2026-06-26 Update: New MCP Startup Blocked by Device Guard

- The newly published single-file executable is blocked by Windows Device Guard:

```text
artifacts\solidworks-mcp\SolidWorksMcpApp.exe
```

- The viable fallback is the build output DLL:

```text
dotnet vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\SolidWorksMcpApp.dll
```

- That DLL still needs a stable foreground/tray session to keep the Hub running.
- The backend temporary launcher has been changed to use:

```text
DEMO_MCP_COMMAND=dotnet
DEMO_MCP_ARGS=<SolidWorksMcpApp.dll> --proxy --client DemoBackendArrange
```

- Follow-up: resolve executable trust/signing/allow-listing, or formalize the DLL startup path in a stable script.

### 2026-06-26 Update: Add MCP Direct Stdio Mode

Background:

- `SolidWorksMcpHub` named-pipe/tray mode has repeatedly caused integration friction:
  - permission isolation;
  - Hub lifecycle ambiguity;
  - Device Guard blocking the published executable;
  - proxy processes failing before they reach the Hub.
- These issues distract from validating the frontend/backend/MCP demo workflow.

Recommended Solution:

- Add a direct stdio mode to the MCP app, for example:

```cmd
dotnet SolidWorksMcpApp.dll --stdio
```

- In this mode, the MCP app should not start the tray Hub and should not connect to `SolidWorksMcpHub`.
- The backend launches MCP as a direct child process and communicates through stdin/stdout.

Suggested Implementation:

1. Add a `--stdio` branch in `SolidWorksMcpApp`.
2. Build the MCP session host directly against the current process stdin/stdout.
3. Configure the backend with:

```cmd
DEMO_MCP_MODE=stdio
DEMO_MCP_COMMAND=dotnet
DEMO_MCP_ARGS=<SolidWorksMcpApp.dll> --stdio
DEMO_MCP_CWD=<directory containing SolidWorksMcpApp.dll>
```

4. Keep the existing `--proxy` / Hub mode for tray use cases.
5. Use direct stdio as the default for demo integration tests.

Expected Benefit:

- Shorter startup chain.
- No dependency on a long-lived Hub process.
- Better fit for automated testing and frontend/backend integration.
- Errors can be captured directly from stderr/stdout.

### 2026-06-26 Addendum: Common Base timeout recap

- The latest `Common Base` run returned `MCP execution failed: TimeoutError:` in the frontend.
- The MCP Hub log shows that `FinalizeCommonBaseAssembly` actually completed:
  - Started at 16:42:48
  - Completed at 16:46:02
  - Total duration: about 194.6 seconds
- The backend default `DEMO_MCP_TIMEOUT_SECONDS` is 180 seconds, so the backend timed out about 14.6 seconds before MCP returned.
- This run was not a Hub/proxy connection failure. SolidWorks completed the tool call, but slower than the backend timeout.
- The real MCP result was still `FinalizeCommonBaseAssembly completed with bottom face orientation mismatch.`, so `commonBaseReady=false` is expected.

Next plan:

1. For short-term validation, raise `DEMO_MCP_TIMEOUT_SECONDS` to 420 seconds so the backend can capture the full MCP result.
2. Add phase timing logs in `FinalizeCommonBaseAssembly` for probe, PreMate correction, mate, rebuild, save, and screenshot.
3. Make screenshot export optional for Common Base validation to reduce extra runtime.
4. Continue the direct stdio MCP plan to reduce Hub/proxy startup uncertainty.

### 2026-06-26 Addendum: Orientation diagnostics are now visible

- MCP `orientationCorrections` and `orientationChecks` are now persisted into `demo_state.json`.
- The frontend now has an `Orientation` diagnostics panel for:
  - whether correction was triggered;
  - before/after world normals;
  - rotation axis and angle;
  - final dot value against A;
  - which component mismatched.
- After the next real `Common Base` run, use the diagnostics to decide:
  1. If PreMate correction did not trigger, inspect face-mapping normals and correction predicate logic.
  2. If PreMate correction succeeded but mate later failed, prioritize an explicit Transform2 initial-pose setter or a controlled post-mate correction path.
  3. If any component normal cannot be read, continue with candidate-face scanning fallback.

### 2026-06-26 Addendum: SelectFaceByName needs rotation/mate robustness

- Face mapping is no longer the early world-center-only implementation. It already stores leaf-local center, area, and normal, so it has some robustness for ordinary component movement.
- The latest Common Base diagnostics show:
  - B/C final probed face areas differ greatly from the recorded bottom face areas;
  - after rotation or mate solving, the current candidate score can select adjacent small/side faces.
- Next improvements:
  1. Treat area/normal as strong constraints instead of weak penalties.
  2. Verify the selected face probe against the recorded mapping after selection.
  3. Return candidate scoring diagnostics.
  4. If no reliable candidate exists, return a clear failure instead of continuing to mate.
  5. Unify the `face_mappings.json` path used by backend validation and MCP selection.

### 2026-06-26 Addendum: SelectFaceByName strong validation completed, real validation pending

- Area/normal/center strong constraints and top-candidate diagnostics are implemented.
- Expected behavior:
  - If B/C's true bottom face can be recovered reliably, `SelectFaceByName` returns `Success=true`;
  - If only an adjacent small/side face can be found, `SelectFaceByName` returns `Success=false` and reports whether center, area, or normal failed.
- Remaining work:
  1. Stop the old MCP, then publish/start the updated MCP;
  2. Run `Common Base` again in real SolidWorks;
  3. Use `faceSelection.diagnostics` to decide whether thresholds should be tuned or Persistent Reference is needed;
  4. Unify the `face_mappings.json` path.

### 2026-06-26 Addendum: New conclusion after strong-validation real test

- The updated MCP was built and validated with a real `Common Base` run.
- Strong validation is working:
  - B-1 final orientation check was rejected because `center distance 0.407875m > 0.002000m`;
  - C-1 final orientation check was rejected because `center distance 0.280773m > 0.002000m`.
- The problem is no longer "a wrong small face was selected and still returned success". It is now clearly:

```text
After rotation/mate, the old face mapping's saved leaf-local center is no longer valid as a later strong constraint.
```

Priority:

1. Unify the `face_mappings.json` path.
2. Investigate and implement SolidWorks Persistent Reference to recover the same IFace2.
3. Before persistent reference is available, consider writing a post-common-base face mapping snapshot after PreMate correction/mating.
4. In Common Base, if strong validation fails, return a clear "mapping invalidated by pose change; re-record or refresh mapping" message instead of continuing automatic correction.

### 2026-06-26 Addendum: Persistent Reference is wired, clean re-record validation pending

Completed:

- The backend and MCP default `face_mappings.json` path now resolves to:

```text
artifacts\solidworks-mcp\face_mappings.json
```

- `RecordFaceMapping` now attempts to store a SolidWorks Persistent Reference:

```json
"persistentReferenceBase64": "..."
```

- `SelectFaceByName` now:
  1. tries `GetObjectByPersistReference3` with `persistentReferenceBase64` first;
  2. falls back to the current leaf-local center / area / normal strong candidate validation if the persistent reference is missing or fails.
- `InitializeCommonBaseAssembly` now reuses an existing target assembly file so reset + initialize does not fail when `ABC_arrange_demo.SLDASM` is already open in SolidWorks.

Current limitation:

- The existing A/B/C mappings are old entries and do not contain `persistentReferenceBase64`.
- The current `ABC_arrange_demo.SLDASM` has already gone through Common Base / mate / rotation attempts. In this state, B/C cannot be selected by the old geometry mapping strongly enough to auto-refresh the mapping.
- Therefore Persistent Reference support is implemented, but the real workflow validation still needs a clean bottom-face re-record.

Recommended next validation:

1. Return to a clean initialized state:
   - close or delete the old `ABC_arrange_demo.SLDASM`;
   - `Reset`;
   - `Initialize`;
   - do not run `Common Base` first.
2. In SolidWorks UI, select the real bottom faces for A/B/C and run the record script or frontend record action.
3. Check `artifacts\solidworks-mcp\face_mappings.json` and confirm A/B/C contain:

```json
"persistentReferenceBase64": "..."
```

4. Run `Common Base` again and inspect:
   - whether `SelectFaceByName` succeeds through Persistent Reference;
   - whether B/C still show large center-distance drift;
   - whether `orientationChecks` still fail.

If it still fails:

- Implement a post-common-base face mapping snapshot:
  - preserve the pre-common-base mapping;
  - after PreMate / mate, write a `postCommonBaseMapping` from the currently selected/known bottom faces;
  - let later orientation checks and Replay Layout prefer that snapshot.
- Continue evaluating whether SolidWorks Persistent Reference remains stable after save/reopen, subassembly rotation, and mate solving.
### 2026-06-29 Addendum: MCP Hub/Proxy chain needs stabilization

Observed behavior:

- While attempting to automatically create `demo\X_reference.SLDASM`, both the official backend endpoint and a temporary direct MCP plan failed during MCP connection setup:

```text
System.IO.IOException: The server shut down unexpectedly.
```

- After restarting the MCP Hub, the log only showed:

```text
Hub pipe server starting on 'SolidWorksMcpHub'
Tray service started
```

but the process later exited and direct pipe mode reported:

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

Follow-up work:

1. Script and standardize MCP Hub startup so manual, hidden-window, and visible-window launches behave consistently.
2. Add a startup health check:
   - verify the `dotnet`/`SolidWorksMcpApp` process is alive;
   - verify `\\.\pipe\SolidWorksMcpHub` is connectable;
   - run one lightweight tool such as `Ping` or `ListComponents`.
3. If `dotnet SolidWorksMcpApp.dll` remains unstable as a tray/Hub session, prioritize direct stdio MCP mode to remove the Hub/proxy layer.
4. The backend should check MCP health before frontend operations, instead of exposing `server shut down unexpectedly` only after a button click.

Impact:

- The automatic `X_reference` creation workflow is currently blocked.
- The CAD operation plan itself remains reusable once the Hub/Proxy chain is restored.

### 2026-06-29 Addendum: Root cause of operation-chain instability and current fix

Current conclusion:

- The main instability was not `MoveComponent` / `RotateComponent` itself. The larger failure point was MCP Hub/proxy startup and connection handling.
- In DLL launch mode, `dotnet SolidWorksMcpApp.dll --proxy` makes `Environment.ProcessPath` point to `dotnet.exe`.
- The old proxy auto-start logic could therefore start bare `dotnet.exe`, which made the proxy fail with:

```text
System.IO.IOException: The server shut down unexpectedly.
```

- Manual or scripted tray Hub startup can also leave the named pipe unavailable:

```text
FileNotFoundError: \\.\pipe\SolidWorksMcpHub
```

Mitigations completed:

1. Added `SolidWorksMcpApp --stdio-direct`, allowing backend automation to use direct MCP stdio without Hub/proxy.
2. Added `SolidWorksMcpApp --headless-hub`, allowing a non-tray Hub session when a named pipe is still needed.
3. Fixed DLL-mode proxy Hub auto-start so it no longer launches bare `dotnet`.
4. Changed backend defaults to prefer direct stdio.
5. Made `McpToolRunner` tolerate stdin BOM/whitespace so PowerShell debug commands are less fragile.

Remaining work:

1. Document direct stdio startup and health-check commands.
2. Extend backend `/api/health` with a lightweight MCP tool probe instead of only echoing configuration.
3. Surface MCP health in the frontend before running long CAD actions.
4. Keep Hub/proxy as an optional mode, but prefer direct stdio for demos and automation.

### 2026-06-29 Addendum: Why rotation can still be unstable

Even after stabilizing MCP transport, rotation still has CAD-level risk:

- `RotateComponent` modifies component `Transform2`.
- If the component is fixed, already mated, or affected by internal subassembly constraints, SolidWorks may trigger expensive constraint solving.
- Rotation after common-base mates, especially around arbitrary axes, can be slow, cancelled by constraints, or change which face the fallback mapping selects.

Current safer approach:

- For `X_reference` creation, rotate only around the common bottom-face normal after Common Base is already established.
- For automatic orientation correction, prefer pre-mate orientation setup instead of rotating after strong mates exist.
- For real assembly restoration, prefer recording/restoring explicit `Transform2` or target orientation data over relying only on incremental rotations.

### 2026-06-29 Addendum: bottom-face world/local center semantics need continued validation

During `X_reference_spread` creation:

- B/C `sourceTransform` changed after `MoveComponent`.
- The old `CaptureCommonBaseLayoutFromAssembly` result still produced unchanged `layout2d`.
- Root cause: `GetSelectedFaceMappingProbe` treated the center of `IFace2.GetBox()` as a world-space point.
- In nested subassembly / leaf-component cases, that center behaves more like a leaf/local-space point and must be transformed through `IComponent2.GetTotalTransform(true)` to get an assembly world center.

Fix completed:

- `GetSelectedFaceMappingProbe` now uses:
  - `localCenter = BoxCenter(face.GetBox())`
  - `worldCenter = GetTotalTransform(true) * localCenter`
- `RecordFaceMapping` now stores the clearer leaf-local center as well.
- Recapturing `X_reference_spread` layout2d now succeeds.

Remaining considerations:

1. Older face mappings may contain `localCenter` values recorded with the previous semantics. A/B/C currently rely on Persistent Reference, so this does not block the current workflow.
2. If a future workflow lacks Persistent Reference and falls back to geometry matching, the fallback may need to support both legacy and corrected local-center semantics.
3. The next Replay Layout test should verify that the corrected world-center probe also drives restored component movement correctly.

### 2026-06-29 Addendum: Replay Layout loop passed, orientation replay still pending

Loop verification result:

- Fresh assembly creation, A/B/C insertion, Common Base, and replay of `x_reference_layout2d.json` passed.
- The recaptured layout2d after replay matched the target layout2d with approximately `2.78e-17` error.

Fix completed:

- `ApplyCapturedCommonBaseLayout` used to call `GetSelectedFaceCenter()` for the current bottom-face center.
- That path did not use `GetTotalTransform(true)` and caused replay offsets for nested components.
- It now uses `GetSelectedFaceMappingProbe().WorldCenter`.

Remaining work:

1. Current replay restores only 2D bottom-center positions. It does not restore each component's own rotation/orientation.
2. `X_reference_spread` already contains rotated B/C `sourceTransform` data, so a future Transform2 orientation replay can:
   - align bottom-face normals;
   - restore in-plane rotation around the common-base normal;
   - then restore layout2d position.
3. `GetSelectedFaceCenter()` may still be used by older flows and should either be replaced with probe world center or fixed internally.

### 2026-06-29 Addendum: layout2d in-plane theta replay completed, full 3D pose restore still pending

Completed:

- `layout2d` now includes `thetaDegrees/thetaAxis`.
- Capture chooses the Transform2 X/Y/Z axis with the strongest projection onto the common-base plane as the theta reference axis.
- Replay restores theta first, then probes the bottom center again and restores x/y.
- Real SolidWorks loop passed:

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

Issue found:

- `RotateComponent` angle direction is opposite to the layout projection convention.
- The current fix negates the angle only inside `ApplyCapturedCommonBaseLayout` theta replay, leaving the lower-level `RotateComponent` behavior unchanged.

Remaining work:

1. This restores planar heading on the common base, not arbitrary full 3D `Transform2` pose.
2. If full 3D pose restoration is needed later, add a dedicated `SetComponentTransform2` or complete Transform2 save/restore tool.
3. `dotnet test` is currently blocked by Windows application control policy while loading the test DLL. The test environment or runner still needs to be stabilized.

### 2026-06-30 Addendum: n-component productization follow-ups

First pass completed:

- State and frontend are no longer tied to fixed A/B/C. Components can be synced from a layout JSON `components` array.
- The frontend can choose or upload layout JSON and display each component's `x/y/theta`.
- Batch face-mapping verification has been added.

Remaining work:

1. Upload currently handles layout JSON content only, not CAD files.
   - In real projects, child assembly file paths in the layout JSON must still be accessible on the local machine.
   - CAD upload would need separate file storage, path mapping, and safety rules.
2. Real batch face-mapping verification depends on the active SolidWorks assembly.
   - If the wrong assembly is active, `select_face_by_name` may fail even when mappings exist.
   - Add an active document / assemblyPath consistency check before verification.
3. The frontend canvas still uses fixed world bounds.
   - For n components or larger layouts, auto-fit based on layout bounds should be added.
4. Current n-component sync is driven by captured layout JSON.
   - A future tool can discover top-level components from the source assembly and generate the demo configuration automatically.
### 2026-06-30 Addendum: Follow-ups After Real Frontend Loop

The frontend upload of `x_reference_layout2d_theta.json` followed by `Initialize -> Verify Faces -> Common Base -> Replay Layout` has passed real SolidWorks validation. A second capture confirmed the replayed `x/y/theta` errors are effectively zero.

Recommended follow-ups:

1. Stabilize MCP/backend health checks
   - `/api/health` currently mainly reports backend configuration.
   - Add lightweight MCP Hub connectivity, tool-list, and SolidWorks active-document checks.
2. Check active assembly consistency
   - Before `Verify Faces`, `Common Base`, and `Replay Layout`, verify that the active SolidWorks assembly matches `demo_state.json.assemblyPath`.
   - This prevents operations from running against the wrong assembly after SolidWorks restarts or window switches.
3. Auto-fit the frontend canvas
   - The current layout view still uses a fairly fixed world range.
   - For n components or larger layouts, fit the viewport from layout bounds.
4. Discover n components from a source assembly
   - Current n-component sync is driven by the layout JSON `components` array.
   - Add a source-assembly discovery tool that lists top-level child assemblies and produces a record/verify checklist.
5. Clean up encoding display
   - PowerShell/log output can still show mojibake for `底面` and degree symbols.
   - Functionality is unaffected, but CLI/log encoding should be made consistent.
6. Add automatic post-replay error reporting
   - The current geometry recheck can be run manually by capturing the replayed assembly and comparing it with the target layout.
   - Later, `Replay Layout` should optionally capture and return per-component `xy_error/theta_error`.
### 2026-06-30 Addendum: Follow-ups After Health Check and Replay Error Report

Completed:
- Backend now exposes `/api/demo/mcp-health`.
- `Verify Faces` now checks active assembly consistency before selecting faces.
- `Replay Layout` now automatically captures the current layout and stores `state.lastRun.replayValidation`.
- Frontend now displays `Replay Check`.

Still pending:

1. Add an explicit frontend MCP Health button or status light
   - The endpoint exists, but the frontend does not have a dedicated entry yet.
   - Later, add a toolbar `Health` button that shows whether the active document matches the state assembly.
2. Add softer consistency warnings before `Common Base` and `Replay Layout`
   - These tools open the target file via `assemblyPath`, so they should not always block.
   - A warning is enough to tell users that the visible SolidWorks window may differ from the target assembly.
3. Make replay validation thresholds configurable
   - Current defaults: `xyError <= 1e-6m`, `thetaError <= 1e-4deg`.
   - Larger real assemblies may need project-specific thresholds.
4. Keep `demo/replay_validation_layout2d.json` ignored
   - It is a runtime validation artifact and should not be committed.
5. Run one more real SolidWorks validation
   - Restart backend;
   - run `Replay Layout` from the frontend;
   - confirm `Replay Check` shows `matched` with near-zero errors.
