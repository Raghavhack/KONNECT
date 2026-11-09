const path = require("path");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");
const axios = require("axios");
const { withExponentialBackoff } = require("../utils/retry");

const PROTO_PATH = path.resolve(__dirname, "../../../shared/proto/intelligence.proto");
const PYTHON_GRPC_HOST = process.env.PYTHON_GRPC_HOST || "localhost:50051";
const PYTHON_REST_URL = process.env.PYTHON_REST_URL || "http://localhost:8000/api/v1";

class GrpcIntelligenceClient {
  constructor() {
    this.client = null;
    this.isReady = false;
    this.activeStreams = new Set();
    this.init();
  }

  init() {
    try {
      const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true,
      });

      const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
      const intelligenceProto = protoDescriptor.konnect.intelligence.v1;

      this.client = new intelligenceProto.IntelligenceService(
        PYTHON_GRPC_HOST,
        grpc.credentials.createInsecure()
      );

      console.log(`[gRPC Client] Initialized IntelligenceService client targeting ${PYTHON_GRPC_HOST}`);
      this.isReady = true;
    } catch (err) {
      console.warn(`[gRPC Client] Failed to load proto from ${PROTO_PATH}:`, err.message);
      this.isReady = false;
    }
  }

  /**
   * Health Check
   */
  async checkHealth() {
    if (!this.isReady || !this.client) {
      return this._fallbackHealth();
    }

    return withExponentialBackoff(
      () =>
        new Promise((resolve, reject) => {
          this.client.CheckHealth({ client_id: "node-orchestration" }, (err, response) => {
            if (err) return reject(err);
            resolve(response);
          });
        }),
      { maxAttempts: 3, baseDelayMs: 300, operationName: "gRPC:CheckHealth" }
    ).catch(() => this._fallbackHealth());
  }

  async _fallbackHealth() {
    try {
      const res = await axios.get(`${PYTHON_REST_URL}/health`, { timeout: 3000 });
      return { status: res.data.status, subsystems: res.data.subsystems, fallback: true };
    } catch {
      return { status: "OFFLINE", subsystems: {}, fallback: true };
    }
  }

  /**
   * Incremental Knowledge Graph Update
   */
  async updateKnowledgeGraph({ documentId, title, content, kHops = 2, triggerLeiden = true, invalidateCache = true, metadata = {} }) {
    const requestPayload = {
      document_id: documentId,
      title: title || documentId,
      content: content || "",
      k_hops: kHops,
      trigger_leiden: triggerLeiden,
      invalidate_cache: invalidateCache,
      metadata,
    };

    if (this.isReady && this.client) {
      try {
        return await withExponentialBackoff(
          () =>
            new Promise((resolve, reject) => {
              this.client.UpdateKnowledgeGraph(requestPayload, (err, response) => {
                if (err) return reject(err);
                resolve(response);
              });
            }),
          { maxAttempts: 5, baseDelayMs: 500, operationName: "gRPC:UpdateKnowledgeGraph" }
        );
      } catch (err) {
        console.warn(`[gRPC Client] UpdateKnowledgeGraph RPC failed (${err.message}). Trying REST fallback...`);
      }
    }

    // REST fallback to FastAPI
    return withExponentialBackoff(
      async () => {
        const res = await axios.post(`${PYTHON_REST_URL}/documents/update`, {
          document_id: documentId,
          title,
          content,
          k_hops: kHops,
          trigger_leiden: triggerLeiden,
          invalidate_cache: invalidateCache,
        });
        return res.data;
      },
      { maxAttempts: 5, baseDelayMs: 500, operationName: "REST:UpdateKnowledgeGraph" }
    );
  }

  /**
   * PCST-driven semantic query answering with citations and subgraph context
   */
  async query({ query, queryId, bypassCache = false, kHops = 2, pcstCostWeight = 0.5, similarityThreshold = 0.6, useGnn = true }) {
    const requestPayload = {
      query,
      query_id: queryId || `q-${Date.now()}`,
      bypass_cache: bypassCache,
      k_hops: kHops,
      pcst_cost_weight: pcstCostWeight,
      similarity_threshold: similarityThreshold,
      use_gnn: useGnn,
    };

    if (this.isReady && this.client) {
      try {
        return await withExponentialBackoff(
          () =>
            new Promise((resolve, reject) => {
              this.client.Query(requestPayload, (err, response) => {
                if (err) return reject(err);
                resolve(response);
              });
            }),
          { maxAttempts: 3, baseDelayMs: 400, operationName: "gRPC:Query" }
        );
      } catch (err) {
        console.warn(`[gRPC Client] Query RPC failed (${err.message}). Trying REST fallback...`);
      }
    }

    // REST fallback to FastAPI
    return withExponentialBackoff(
      async () => {
        const res = await axios.post(`${PYTHON_REST_URL}/query`, {
          query,
          query_id: queryId,
          bypass_cache: bypassCache,
          pcst_cost_weight: pcstCostWeight,
          similarity_threshold: similarityThreshold,
          use_gnn: useGnn,
        });
        return res.data;
      },
      { maxAttempts: 3, baseDelayMs: 400, operationName: "REST:Query" }
    );
  }

  /**
   * Explicit Cache Invalidation
   */
  async invalidateCache(entityNames = [], documentIds = []) {
    if (this.isReady && this.client) {
      try {
        return await new Promise((resolve, reject) => {
          this.client.InvalidateCache(
            { entity_names: entityNames, document_ids: documentIds },
            (err, response) => {
              if (err) return reject(err);
              resolve(response);
            }
          );
        });
      } catch (err) {
        console.warn(`[gRPC Client] InvalidateCache RPC failed (${err.message}). Trying REST...`);
      }
    }

    const res = await axios.post(`${PYTHON_REST_URL}/cache/invalidate`, {
      entity_names: entityNames,
    });
    return res.data;
  }

  /**
   * Subscribe to real-time graph updates stream from Python service
   */
  subscribeGraphStream(onData, onError) {
    if (!this.isReady || !this.client) {
      return null;
    }

    try {
      const stream = this.client.StreamGraphUpdates({
        client_id: `node-stream-${Date.now()}`,
        include_heartbeats: true,
      });

      stream.on("data", (event) => {
        if (typeof onData === "function") onData(event);
      });

      stream.on("error", (err) => {
        console.warn("[gRPC Client] StreamGraphUpdates error:", err.message);
        if (typeof onError === "function") onError(err);
      });

      stream.on("end", () => {
        console.log("[gRPC Client] StreamGraphUpdates ended.");
      });

      return stream;
    } catch (err) {
      console.warn("[gRPC Client] Failed to subscribe to stream:", err.message);
      return null;
    }
  }
}

module.exports = new GrpcIntelligenceClient();

