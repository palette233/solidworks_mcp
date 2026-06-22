# SOLIDWORKS API RAG and MCP Workspace

This workspace starts with a crawler for SOLIDWORKS 2025 API Web Help pages.

It now also contains a SolidWorks MCP server base from [just1step/solidworks-mcp](https://github.com/just1step/solidworks-mcp), with a local RAG-backed knowledge tool added on top.

## Crawl

```powershell
python scripts/crawl_solidworks_api.py --max-pages 100 --delay 0.5
```

Outputs are written to `data/solidworks_api_2025/`:

- `pages.jsonl`: one metadata record per crawled page, including URL, title, paths, and discovered links.
- `html/`: extracted `helpContentData.helpText` HTML for each page.
- `text/`: plain text extracted from the help HTML, suitable for later RAG chunking.
- `crawl_state.json`: summary for the latest run.

The crawler is scoped to `https://help.solidworks.com/2025/english/api/` and resumes by skipping URLs already present in `pages.jsonl`.

## Build RAG Index

The default RAG index is local and requires no API key:

```powershell
python scripts/build_rag_index.py --backend tfidf
```

This reads the current `pages.jsonl`, loads each page's text file, creates overlapping chunks, and writes an index to `data/solidworks_api_2025/rag_index/`.

You can rebuild while the crawler is still running. The builder ignores incomplete JSONL lines and uses only text files that already exist.

To use SentenceTransformers embeddings instead:

```powershell
python scripts/build_rag_index.py --backend sbert --sbert-model sentence-transformers/all-MiniLM-L6-v2
```

## Query

```powershell
python scripts/query_rag.py "IAssemblyDoc AddComponent4 insert part into assembly" --top-k 6
```

Print concatenated context for a downstream LLM or MCP tool:

```powershell
python scripts/query_rag.py "How do I open a SOLIDWORKS document with ISldWorks?" --context --top-k 8
```

## MCP Integration

The upstream MCP app lives in [vendor/solidworks-mcp](</C:/Users/uenx/Documents/New project 3/vendor/solidworks-mcp/README.md>).

Added integration:

- `SearchSolidWorksApiKnowledge`: an MCP tool exposed from `SolidWorksMcpApp` that calls the local Python RAG query script.
- It reads from `data/solidworks_api_2025/rag_index/`, so rebuild the index whenever the crawler has added enough new pages.
- `ListGlobalVariables`: inspect global variables defined in the active document.
- `GetSelectedDimensionInfo`: inspect the currently selected display dimension before binding it.
- `UpsertGlobalVariable`: create or update a SolidWorks global variable in the active document.
- `BindSelectedDimensionToGlobalVariable`: bind the currently selected SolidWorks display dimension to an existing global variable.
- `ListFeatureDimensions`: inspect bindable dimensions on a named feature.
- `UpsertGlobalVariableAndBindFeatureDimensionByDescription`: create/update a variable and bind the best-matching feature dimension by description, without manual dimension selection.
- `CaptureActiveAssemblyEntityAnnotationSet`: traverse the active assembly, highlight each component/feature/body target, export front/top/right PNGs, and write a stable `manifest.json`.
- `AnnotateAssemblyEntityCaptureSetWithQwen`: call an OpenAI-compatible Qwen vision endpoint to classify each captured target as directly related to overall X/Y/Z assembly size.
- `ImportAssemblyEntityDimensionAnnotations`: import externally generated target annotations into a normalized `dimension-annotations.json` index.
- `QueryAssemblyEntityDimensionAnnotations`: query the annotation index before changing overall assembly width/depth/height.
- `HighlightAssemblyEntityAnnotationTarget`: reselect a captured target in the active assembly by stable `targetId`.

## Assembly Entity Dimension Annotation Workflow

The entity annotation tools are designed for the workflow where the model first builds an evidence index, then later uses that index to plan size changes.

1. Capture a manifest and front/top/right images for the active assembly:

```text
CaptureActiveAssemblyEntityAnnotationSet(
  outputDirectory="C:\\temp\\sw-entity-annotations",
  width=1280,
  height=720,
  includeComponents=true,
  includeFeatures=true,
  includeBodies=true,
  maxTargets=50,
  startIndex=0,
  skipExistingTargets=true,
  writeManifestAfterEachTarget=true,
  maxDurationSeconds=45,
  useCleanDisplayMode=false,
  capturePaddingFactor=1.35
)
```

This writes `manifest.json` and one `entities/<targetId>/front.png`, `top.png`, and `right.png` set per target. Each manifest target contains the owning component path, hierarchy path, document path, feature/body metadata, selection status, and stable `targetId`.

The capture skips FeatureManager management nodes such as `Favorites`, `Sensors`, `DocsFolder`, mate folders, reference folders, lights/cameras, and other non-geometric folders. Child part and subassembly contents are collected by recursively traversing assembly components instead of treating `DocsFolder` itself as a target. When a child feature or body cannot be directly selected in assembly context, the capture falls back to highlighting the owning component and records that as `selection.method = "owning-component"`.

For large assemblies, run capture in batches to avoid MCP request timeouts:

```text
CaptureActiveAssemblyEntityAnnotationSet(
  outputDirectory="C:\\temp\\sw-entity-annotations",
  width=800,
  height=600,
  includeComponents=true,
  includeFeatures=true,
  includeBodies=false,
  maxTargets=25,
  startIndex=0,
  skipExistingTargets=true,
  maxDurationSeconds=45,
  useCleanDisplayMode=false,
  capturePaddingFactor=1.35
)

CaptureActiveAssemblyEntityAnnotationSet(
  outputDirectory="C:\\temp\\sw-entity-annotations",
  width=800,
  height=600,
  includeComponents=true,
  includeFeatures=true,
  includeBodies=false,
  maxTargets=25,
  startIndex=25,
  skipExistingTargets=true,
  maxDurationSeconds=45,
  useCleanDisplayMode=false,
  capturePaddingFactor=1.35
)
```

`writeManifestAfterEachTarget=true` is the default, so completed targets are persisted after every capture. `maxDurationSeconds` is also enabled by default; it makes the tool return a partial manifest before common MCP client request timeouts cut the call off. The result includes `totalTargetCount`, `processedThisRun`, `skippedExistingCount`, `nextStartIndex`, and `stoppedReason`. Re-run with the same `outputDirectory`, `skipExistingTargets=true`, and `startIndex` set to the returned `nextStartIndex` until `stoppedReason` is `completed`.

By default, `useCleanDisplayMode=false` preserves the normal SolidWorks shaded display and selection highlight. The capture switches to each standard view, zooms to fit, zooms out with `capturePaddingFactor`, selects the target, refreshes highlighted items, and exports the PNG. The default `capturePaddingFactor=1.35` prioritizes fitting the whole model in view; if the model appears too small you can lower it, for example `1.2`. Set `useCleanDisplayMode=true` only when you explicitly want hidden-lines-removed images and do not need the normal shaded highlight appearance.

For very large assemblies, prefer the Python batch runner instead of asking an LLM client to hold one long MCP request open:

```powershell
python .\scripts\capture_assembly_entity_annotations.py `
  --output-dir C:\temp\sw-entity-annotations `
  --width 800 `
  --height 600 `
  --batch-size 5 `
  --tool-time-budget 20 `
  --request-timeout 90 `
  --padding 1.35 `
  --no-include-bodies
```

The runner starts `SolidWorksMcpApp.exe --proxy`, calls `CaptureActiveAssemblyEntityAnnotationSet` repeatedly, and resumes from `manifest.json` if a batch times out after writing partial progress. It automatically uses the latest `artifacts\solidworks-mcp*\SolidWorksMcpApp.exe`, or you can pass `--exe C:\path\to\SolidWorksMcpApp.exe`.

To verify the Python runner can talk to the local MCP hub before capturing, run:

```powershell
python .\scripts\capture_assembly_entity_annotations.py `
  --output-dir C:\temp\sw-entity-annotations `
  --probe-only
```

2. Annotate with Qwen vision from inside the MCP app:

```text
AnnotateAssemblyEntityCaptureSetWithQwen(
  manifestPath="C:\\temp\\sw-entity-annotations\\manifest.json",
  model="qwen3.6-flash",
  maxTargets=0
)
```

Set `DASHSCOPE_API_KEY` or `QWEN_API_KEY` in the environment before starting `SolidWorksMcpApp.exe`. Optional overrides are `SOLIDWORKS_ENTITY_ANNOTATION_QWEN_MODEL`, `QWEN_VISION_MODEL`, `DASHSCOPE_BASE_URL`, and `QWEN_BASE_URL`. The default base URL is DashScope OpenAI-compatible mode, and the default model is `qwen3.6-flash`.

3. Or import annotations produced by an external vision pipeline:

```json
[
  {
    "targetId": "ae_0123456789abcdef",
    "x": { "related": true, "description": "Controls the left/right outside envelope.", "identifiers": ["outer side face"] },
    "y": { "related": false },
    "z": { "related": true, "description": "Sets the top boundary.", "identifiers": ["top plate"] },
    "overallReason": "The target is on the assembly envelope.",
    "confidence": 0.82
  }
]
```

Call `ImportAssemblyEntityDimensionAnnotations(manifestPath, annotationJsonOrFilePath)` to normalize this into `dimension-annotations.json`.

4. Before changing an overall assembly dimension, query the index:

```text
QueryAssemblyEntityDimensionAnnotations(
  annotationPath="C:\\temp\\sw-entity-annotations\\dimension-annotations.json",
  axis="z",
  query="height",
  onlyRelated=true
)
```

5. Highlight a returned target before editing:

```text
HighlightAssemblyEntityAnnotationTarget(
  manifestOrAnnotationPath="C:\\temp\\sw-entity-annotations\\dimension-annotations.json",
  targetId="ae_0123456789abcdef"
)
```

The intended downstream edit flow is: query related targets for the requested X/Y/Z size change, inspect returned `componentPath`, `hierarchyPath`, `featureName`, and descriptions, then use the existing component-open and feature-dimension binding tools to adjust the confirmed controlling geometry.

Build prerequisites on the Windows machine where you publish the app:

- SolidWorks installed locally
- .NET 8 SDK available in `PATH`
- Python available in `PATH`

Optional environment variables when the published exe is not launched from this workspace:

- `SOLIDWORKS_MCP_WORKSPACE`: root folder containing `scripts/query_rag.py`
- `SOLIDWORKS_API_RAG_QUERY_SCRIPT`: explicit path to `query_rag.py`
- `SOLIDWORKS_API_RAG_INDEX_DIR`: explicit path to the built RAG index

Publish command:

```powershell
.\scripts\publish_solidworks_mcp.ps1
```

The app will still use the upstream tray hub + `--proxy` stdio client flow. The only added behavior is the local API knowledge-search tool.

After publishing, start the tray app:

```powershell
.\artifacts\solidworks-mcp\SolidWorksMcpApp.exe
```

The exported Claude Desktop and VS Code MCP configs now include the RAG environment variables automatically:

- `SOLIDWORKS_MCP_WORKSPACE`
- `SOLIDWORKS_API_RAG_QUERY_SCRIPT`
- `SOLIDWORKS_API_RAG_INDEX_DIR`

That allows `SearchSolidWorksApiKnowledge` to work even when the exe is launched from `artifacts\solidworks-mcp\`.

For `BindSelectedDimensionToGlobalVariable`, exactly one SolidWorks display dimension must already be selected.
