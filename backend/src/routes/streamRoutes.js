const express = require("express");
const router = express.Router();
const grpcClient = require("../services/grpcClient");

const activeClients = new Set();

// Forward gRPC events to all connected SSE clients
if (grpcClient.isReady) {
  grpcClient.subscribeGraphStream(
    (event) => {
      const payload = JSON.stringify(event);
      for (const client of activeClients) {
        client.write(`event: graph-delta\ndata: ${payload}\n\n`);
      }
    },
    (err) => {
      console.warn("[Stream Route] gRPC stream error:", err.message);
    }
  );
}

/**
 * GET /api/stream
 * Server-Sent Events (SSE) endpoint for real-time graph delta streaming to frontend.
 */
router.get("/stream", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  // Send initial connected event
  res.write(
    `event: connected\ndata: ${JSON.stringify({
      message: "Connected to KONNECT Graph Delta Stream",
      timestamp: new Date().toISOString(),
    })}\n\n`
  );

  activeClients.add(res);

  // Keep connection alive with periodic heartbeats
  const heartbeatInterval = setInterval(() => {
    res.write(
      `event: heartbeat\ndata: ${JSON.stringify({
        tag: "CONNECTED",
        text: "Heartbeat — gRPC stream healthy",
        time: new Date().toLocaleTimeString(),
      })}\n\n`
    );
  }, 15000);

  req.on("close", () => {
    clearInterval(heartbeatInterval);
    activeClients.delete(res);
  });
});

module.exports = router;

