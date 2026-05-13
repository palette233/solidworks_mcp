# SOLIDWORKS API RAG Workspace

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
