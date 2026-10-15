# Shared Protocol Buffers (`shared/proto`)

This folder contains the authoritative interface definition contracts (`.proto`) between the **JavaScript API/Orchestration service** (`backend`) and the **Python Intelligence service** (`ai_service`).

## Contract Overview: `intelligence.proto`

- **Package**: `konnect.intelligence.v1`
- **Service**: `IntelligenceService`
  - `ParseDocument`: Preprocesses text with spaCy, produces chunks, and extracts candidate entities & relations.
  - `UpdateKnowledgeGraph`: Performs incremental updates, $k$-hop bounded neighborhood re-embedding via ROLAND GRU, Leiden community detection, and Redis cache invalidation.
  - `StreamGraphUpdates`: Server-streaming RPC delivering real-time graph deltas (`ADDED_NODE`, `UPDATED_NODE`, `ADDED_EDGE`, etc.) to the JS orchestration layer for live frontend rendering.
  - `Query`: Executes PCST (Prize-Collecting Steiner Tree) semantic subgraph retrieval, synthesizes answers using frozen LLMs (OpenAI / Anthropic), and produces grounded citations.
  - `InvalidateCache`: Explicitly evicts semantic cache entries referencing modified graph entities or documents.
  - `BenchmarkLatency`: Benchmarks $k$-hop bounded-neighborhood update latency against full-graph recomputation.
  - `CheckHealth`: Probes system health and connected subsystems (Neo4j, Redis, PyTorch, spaCy, Embeddings).

## Compilation

### For Python (`ai_service`):
```bash
python -m grpc_tools.protoc -Ishared/proto --python_out=ai_service/app/grpc/generated --grpc_python_out=ai_service/app/grpc/generated shared/proto/intelligence.proto
```
Or run the automated helper:
```bash
python ai_service/scripts/generate_protos.py
```

### For JavaScript / TypeScript (`backend`):
```bash
npx proto-loader-gen-types --longs=String --enums=String --defaults --oneofs --grpcLib=@grpc/grpc-js --outDir=backend/src/proto/ shared/proto/intelligence.proto
```
