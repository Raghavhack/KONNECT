const express = require("express");
const router = express.Router();
const onedriveService = require("../services/onedriveService");
const tokenStore = require("../services/tokenStore");
const config = require("../config/onedrive");

/**
 * GET /api/auth/onedrive/connect
 * Starts Microsoft Entra OAuth 2.0 flow
 */
router.get("/connect", async (req, res) => {
  try {
    const authUrl = await onedriveService.getAuthUrl();
    // If request asks for JSON redirect URL
    if (req.query.json === "true") {
      return res.json({ success: true, authUrl });
    }
    // Otherwise redirect browser directly
    res.redirect(authUrl);
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message,
      hint: "Make sure MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET are configured in backend/.env",
    });
  }
});

/**
 * GET /api/auth/onedrive/callback
 * Microsoft Entra redirects here with authorization `code`
 */
router.get("/callback", async (req, res) => {
  console.log("[OneDrive Callback Query]:", JSON.stringify(req.query, null, 2));
  const { code, error, error_description } = req.query;

  if (error) {
    console.error(`[OneDrive Callback] Error from Microsoft: ${error} - ${error_description}`);
    return res.status(400).json({
      success: false,
      error: error,
      description: error_description || "No description provided by Microsoft",
      fullQuery: req.query,
    });
  }

  if (!code) {
    return res.status(400).json({
      success: false,
      error: "Authorization code missing from callback",
    });
  }

  try {
    const tokens = await onedriveService.exchangeCodeForTokens(code);

    // Optionally auto-register webhook subscription if a public URL is configured
    let subscription = null;
    if (
      config.webhookNotificationUrl &&
      !config.webhookNotificationUrl.includes("localhost")
    ) {
      try {
        subscription = await onedriveService.createWebhookSubscription();
      } catch (subErr) {
        console.warn(
          "[OneDrive Callback] Could not automatically create webhook subscription:",
          subErr.message
        );
      }
    }

    // Redirect to frontend with success query param or return JSON
    const frontendRedirect =
      process.env.FRONTEND_URL || "http://localhost:5173/live-demo?onedrive=connected";

    if (req.headers.accept && req.headers.accept.includes("text/html")) {
      return res.redirect(frontendRedirect);
    }

    res.json({
      success: true,
      message: "OneDrive successfully connected!",
      account: tokens.accountInfo,
      subscription: subscription ? { id: subscription.id } : "pending_public_url",
    });
  } catch (err) {
    console.error("[OneDrive Callback Error]:", err.message);
    res.status(500).json({
      success: false,
      error: err.message,
    });
  }
});

/**
 * GET /api/auth/onedrive/status
 * Returns connection state and account details
 */
router.get("/status", async (req, res) => {
  const tokens = tokenStore.getTokens();

  if (!tokens || !tokens.accessToken) {
    let authUrl = null;
    try {
      if (config.clientId) authUrl = await onedriveService.getAuthUrl();
    } catch (_) {}

    return res.json({
      connected: false,
      message: "OneDrive is not connected.",
      authUrl: authUrl,
    });
  }

  const isExpired = tokenStore.isExpired();

  res.json({
    connected: true,
    account: tokens.accountInfo || null,
    isExpired: isExpired,
    expiresAt: new Date(tokens.expiresAt).toISOString(),
    deltaTokenStored: !!tokens.deltaToken,
  });
});

/**
 * POST /api/auth/onedrive/disconnect
 * Disconnects OneDrive and wipes tokens
 */
router.post("/disconnect", (req, res) => {
  tokenStore.clear();
  res.json({
    success: true,
    message: "OneDrive disconnected and local tokens cleared.",
  });
});

/**
 * GET /api/auth/onedrive/delta
 * Manually trigger delta synchronization of changed files
 */
router.get("/delta", async (req, res) => {
  try {
    const changes = await onedriveService.fetchDeltaChanges();
    res.json({
      success: true,
      count: changes.length,
      changes: changes.map((item) => ({
        id: item.id,
        name: item.name,
        size: item.size,
        lastModifiedDateTime: item.lastModifiedDateTime,
        deleted: !!item.deleted,
        file: item.file ? true : false,
        folder: item.folder ? true : false,
      })),
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

module.exports = router;
