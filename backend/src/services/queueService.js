const { Queue, Worker } = require("bullmq");
const IORedis = require("ioredis");
const config = require("../config/onedrive");
const onedriveService = require("./onedriveService");

class QueueService {
  constructor() {
    this.redisAvailable = false;
    this.queue = null;
    this.worker = null;
    this.processedIdempotencyKeys = new Set();
    this.debounceTimers = new Map(); // documentId -> { timeout, eventData }

    this.init();
  }

  async init() {
    try {
      this.redisClient = new IORedis(config.redisUrl, {
        maxRetriesPerRequest: null,
        lazyConnect: true,
        connectTimeout: 3000,
        retryStrategy: () => null, // Don't crash if Redis is unavailable locally
      });

      await this.redisClient.connect();
      this.redisAvailable = true;
      console.log("[Queue] Connected to Redis. Initializing BullMQ...");

      this.queue = new Queue("onedrive-sync-queue", {
        connection: this.redisClient,
        defaultJobOptions: {
          attempts: 5,
          backoff: {
            type: "exponential",
            delay: 1000,
          },
          removeOnComplete: 100,
          removeOnFail: 200,
        },
      });

      this.worker = new Worker(
        "onedrive-sync-queue",
        async (job) => {
          return await this.processSyncJob(job.data);
        },
        {
          connection: this.redisClient,
          concurrency: 3,
        }
      );

      this.worker.on("completed", (job) => {
        console.log(`[Queue] Job #${job.id} completed successfully.`);
      });

      this.worker.on("failed", (job, err) => {
        console.error(`[Queue] Job #${job?.id} failed:`, err.message);
      });
    } catch (err) {
      this.redisAvailable = false;
      console.warn(
        `[Queue] Redis not reachable (${err.message}). Using built-in In-Memory Queue with debouncing & idempotency fallback.`
      );
    }
  }

  /**
   * Idempotency check: ensures retried webhook deliveries don't double-process.
   */
  isDuplicate(idempotencyKey) {
    if (!idempotencyKey) return false;
    if (this.processedIdempotencyKeys.has(idempotencyKey)) {
      return true;
    }
    this.processedIdempotencyKeys.add(idempotencyKey);

    // Keep set bounded to last 5,000 keys to avoid memory bloat
    if (this.processedIdempotencyKeys.size > 5000) {
      const oldestKey = this.processedIdempotencyKeys.values().next().value;
      this.processedIdempotencyKeys.delete(oldestKey);
    }
    return false;
  }

  /**
   * Debouncing per document: rapid successive edits to the same file collapse into one job,
   * processed after a quiet window (e.g., 3000ms).
   */
  enqueueDebounced(documentId, eventPayload, idempotencyKey) {
    // 1. Check idempotency
    if (this.isDuplicate(idempotencyKey)) {
      console.log(
        `[Debounce] Skipped duplicate event with idempotency key: ${idempotencyKey}`
      );
      return { status: "duplicate_skipped" };
    }

    // 2. Clear existing debounce timer for this document if rapid edit occurred
    if (this.debounceTimers.has(documentId)) {
      clearTimeout(this.debounceTimers.get(documentId).timer);
      console.log(
        `[Debounce] Collapsing rapid edit for document [${documentId}]. Resetting quiet window timer.`
      );
    }

    // 3. Schedule the collapsed job after the quiet window
    const timer = setTimeout(async () => {
      this.debounceTimers.delete(documentId);
      await this.dispatchJob({
        documentId,
        ...eventPayload,
        dispatchedAt: new Date().toISOString(),
      });
    }, config.debounceQuietWindowMs);

    this.debounceTimers.set(documentId, {
      timer,
      eventPayload,
      receivedAt: Date.now(),
    });

    return {
      status: "debounced",
      quietWindowMs: config.debounceQuietWindowMs,
      documentId,
    };
  }

  /**
   * Dispatches the job to BullMQ on Redis if available, or processes via in-memory worker
   */
  async dispatchJob(jobData) {
    if (this.redisAvailable && this.queue) {
      const job = await this.queue.add("process-onedrive-document", jobData, {
        jobId: `doc-${jobData.documentId}-${Date.now()}`,
      });
      console.log(`[Queue] Enqueued job #${job.id} for document ${jobData.documentId}`);
      return job;
    } else {
      console.log(
        `[In-Memory Queue] Processing document [${jobData.documentId}]...`
      );
      return await this.processSyncJob(jobData);
    }
  }

  /**
   * Worker job execution:
   * 1. Fetches document delta or file contents from Microsoft Graph
   * 2. (In Phase 2) Streams file to Python Intelligence Service via gRPC
   */
  async processSyncJob(jobData) {
    try {
      console.log(
        `[Sync Worker] Beginning processing for document ${jobData.documentId}`
      );

      let content = null;
      if (jobData.documentId && jobData.documentId !== "delta-sync") {
        try {
          content = await onedriveService.fetchFileContent(jobData.documentId);
          console.log(
            `[Sync Worker] Fetched content for document ${jobData.documentId} (length: ${
              typeof content === "string" ? content.length : "binary"
            })`
          );
        } catch (fetchErr) {
          console.warn(
            `[Sync Worker] Could not fetch raw content for ${jobData.documentId}: ${fetchErr.message}`
          );
        }
      }

      // Next step in KONNECT architecture:
      // gRPC call to Python service to parse AST, run spaCy NER, Cypher MERGE in Neo4j,
      // and ROLAND GRU 2-hop re-embedding.
      return {
        success: true,
        documentId: jobData.documentId,
        contentLength: content ? content.length : 0,
        processedAt: new Date().toISOString(),
      };
    } catch (err) {
      console.error(`[Sync Worker] Error processing document:`, err.message);
      throw err;
    }
  }
}

module.exports = new QueueService();
