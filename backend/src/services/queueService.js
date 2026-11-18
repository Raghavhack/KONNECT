const { Queue, Worker } = require("bullmq");
const IORedis = require("ioredis");
const config = require("../config/onedrive");
const onedriveService = require("./onedriveService");
const googleDriveService = require("./googleDriveService");

class QueueService {
  constructor() {
    this.redisAvailable = false;
    this.queue = null;
    this.worker = null;
    this.processedIdempotencyKeys = new Set();
    this.debounceTimers = new Map();

    this.init();
  }

  async init() {
    try {
      this.redisClient = new IORedis(config.redisUrl, {
        maxRetriesPerRequest: null,
        lazyConnect: true,
        connectTimeout: 3000,
        retryStrategy: () => null,
      });

      this.redisClient.on("error", (err) => {
        console.warn("[Redis] Connection error:", err.message);
      });

      await this.redisClient.connect();
      this.redisAvailable = true;

      console.log("[Queue] Connected to Redis. Initializing BullMQ...");

      // Keep the existing queue name to preserve compatibility.
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
        `[Queue] Redis not reachable (${err.message}). Using in-memory processing.`
      );
    }
  }

  isDuplicate(idempotencyKey) {
    if (!idempotencyKey) return false;

    if (this.processedIdempotencyKeys.has(idempotencyKey)) {
      return true;
    }

    this.processedIdempotencyKeys.add(idempotencyKey);

    if (this.processedIdempotencyKeys.size > 5000) {
      const oldestKey =
        this.processedIdempotencyKeys.values().next().value;

      this.processedIdempotencyKeys.delete(oldestKey);
    }

    return false;
  }

  enqueueDebounced(
    documentId,
    eventPayload = {},
    idempotencyKey,
    provider = "onedrive"
  ) {
    provider = eventPayload.provider || provider;

    if (!["onedrive", "google"].includes(provider)) {
      throw new Error(`Unsupported provider: ${provider}`);
    }

    if (this.isDuplicate(idempotencyKey)) {
      console.log(
        `[Debounce] Skipped duplicate ${provider} event: ${idempotencyKey}`
      );

      return { status: "duplicate_skipped" };
    }

    // Prevent Google and OneDrive files with the same ID
    // from sharing a debounce timer.
    const debounceKey = `${provider}:${documentId}`;

    if (this.debounceTimers.has(debounceKey)) {
      clearTimeout(this.debounceTimers.get(debounceKey).timer);

      console.log(
        `[Debounce] Collapsing rapid edit for ${debounceKey}`
      );
    }

    const timer = setTimeout(async () => {
      this.debounceTimers.delete(debounceKey);

      try {
        await this.dispatchJob({
          ...eventPayload,
          provider,
          documentId,
          dispatchedAt: new Date().toISOString(),
        });
      } catch (err) {
        console.error(
          `[Queue] Failed to dispatch ${debounceKey}:`,
          err.message
        );
      }
    }, config.debounceQuietWindowMs);

    this.debounceTimers.set(debounceKey, {
      timer,
      eventPayload,
      receivedAt: Date.now(),
    });

    return {
      status: "debounced",
      provider,
      documentId,
      quietWindowMs: config.debounceQuietWindowMs,
    };
  }

  async dispatchJob(jobData) {
    const provider = jobData.provider || "onedrive";

    if (this.redisAvailable && this.queue) {
      const job = await this.queue.add(
        "process-document",
        jobData,
        {
          jobId: `doc-${provider}-${jobData.documentId}-${Date.now()}`,
        }
      );

      console.log(
        `[Queue] Enqueued ${provider} job #${job.id} for ${jobData.documentId}`
      );

      return job;
    }

    console.log(
      `[In-Memory Queue] Processing ${provider} document ${jobData.documentId}`
    );

    return await this.processSyncJob(jobData);
  }

  async processSyncJob(jobData) {
    const provider = jobData.provider || "onedrive";
    const documentId = jobData.documentId;

    try {
      console.log(
        `[Sync Worker] Processing ${provider} document ${documentId}`
      );

      // Handle deleted or removed Google Drive files.
      if (provider === "google" && (
        jobData.removed === true ||
        jobData.file?.trashed === true
      )) {
        console.log(
          `[Google Drive] File ${documentId} was removed or trashed.`
        );

        // TODO: Remove this document's contributions
        // from the KONNECT knowledge graph.

        return {
          success: true,
          provider,
          documentId,
          removed: true,
          processedAt: new Date().toISOString(),
        };
      }

      let content = null;

      if (documentId && documentId !== "delta-sync") {
        if (provider === "google") {
          const result = await googleDriveService.readFile(documentId);
          content = result.content;

          console.log(
              `[Google Drive] Fetched ${result.file.name} (${content.length} characters/bytes)`
        );
        } else if (provider === "onedrive") {
          content = await onedriveService.fetchFileContent(documentId);

          console.log(
            `[OneDrive] Fetched content for ${documentId}`
          );
        } else {
          throw new Error(`Unsupported provider: ${provider}`);
        }
      }

      // TODO: Send content to the KONNECT intelligence layer.
      // This is where the gRPC integration will be connected.

      return {
        success: true,
        provider,
        documentId,
        contentLength: content ? content.length : 0,
        processedAt: new Date().toISOString(),
      };
    } catch (err) {
      console.error(
        `[Sync Worker] ${provider} document ${documentId} failed:`,
        err.message
      );

      throw err;
    }
  }
}

module.exports = new QueueService();

console.log("[Debug] Queue service initialized");