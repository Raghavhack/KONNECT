const express = require("express");
const router = express.Router();
const gdriveService = require("../services/gdriveService");
const queueService = require("../services/queueService");

/**
 * GET /api/auth/gdrive/connect
 * Redirects user to Google OAuth 2.0 consent screen
 */
router.get("/connect", (req, res) => {
  const url = gdriveService.getAuthUrl();
  res.redirect(url);
});

/**
 * GET /api/auth/gdrive/callback
 * Handles OAuth callback
 */
router.get("/callback", async (req, res) => {
  const code = req.query.code;
  if (!code) {
    return res.status(400).send("No authorization code provided");
  }

  try {
    await gdriveService.handleCallback(code);
    const frontendUrl = process.env.FRONTEND_URL || "http://localhost:5173";
    res.redirect(`${frontendUrl}/live-demo?gdrive=connected`);
  } catch (err) {
    res.status(500).send(`Authentication failed: ${err.message}`);
  }
});

/**
 * GET /api/auth/gdrive/status
 */
router.get("/status", (req, res) => {
  res.json(gdriveService.getStatus());
});

/**
 * POST /api/webhooks/gdrive
 * Google Drive push notifications webhook endpoint.
 * Enqueues job with debouncing and idempotency.
 */
router.post("/webhook", (req, res) => {
  const channelId = req.headers["x-goog-channel-id"] || "gdrive-channel";
  const resourceId = req.headers["x-goog-resource-id"] || `res-${Date.now()}`;
  const resourceState = req.headers["x-goog-resource-state"] || "change";
  const messageNumber = req.headers["x-goog-message-number"] || Date.now().toString();

  // Acknowledge push notification immediately (200 OK)
  res.status(200).send("OK");

  if (resourceState === "sync") {
    console.log(`[Google Drive Webhook] Received sync verification for channel ${channelId}`);
    return;
  }

  const idempotencyKey = `gdrive-${channelId}-${resourceId}-${messageNumber}`;
  queueService.enqueueDebounced(
    resourceId,
    { source: "Google Drive", resourceId, channelId },
    idempotencyKey
  );
});

module.exports = router;

