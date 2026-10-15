const express = require("express");
const router = express.Router();
const config = require("../config/onedrive");
const queueService = require("../services/queueService");
const onedriveService = require("../services/onedriveService");

/**
 * POST & GET /api/webhooks/onedrive
 *
 * Microsoft Graph Webhook Specification:
 * 1. Subscription Handshake:
 *    Microsoft sends a POST or GET request with a query string `validationToken`.
 *    The server MUST return HTTP 200 with the exact validation token in plain text within 10 seconds!
 *
 * 2. Change Notifications:
 *    Microsoft sends a POST request with body:
 *    {
 *      "value": [
 *        {
 *          "subscriptionId": "...",
 *          "clientState": "...",
 *          "changeType": "updated",
 *          "resource": "me/drive/root",
 *          "resourceData": { "@odata.type": "#Microsoft.Graph.DriveItem", "id": "..." }
 *        }
 *      ]
 *    }
 *    The server MUST acknowledge fast (HTTP 202 Accepted) and process asynchronously.
 */
router.all("/", async (req, res) => {
  // 1. Validation Handshake
  const validationToken = req.query.validationToken;
  if (validationToken) {
    console.log("[Webhook] Received Microsoft Graph validationToken handshake.");
    res.set("Content-Type", "text/plain");
    return res.status(200).send(validationToken);
  }

  // 2. Notification Delivery
  const notifications = req.body?.value || [];
  if (!notifications.length) {
    return res.status(200).json({ received: 0 });
  }

  console.log(
    `[Webhook] Received ${notifications.length} change notification(s) from Microsoft Graph.`
  );

  const results = [];

  for (const notif of notifications) {
    // Security check: verify clientState matches our secret
    if (notif.clientState && notif.clientState !== config.clientStateSecret) {
      console.warn(
        `[Webhook] Rejected notification with invalid clientState: ${notif.clientState}`
      );
      continue;
    }

    const docId = notif.resourceData?.id || "delta-sync";
    const changeType = notif.changeType || "updated";

    // Idempotency key per architecture: derived from event/resource + changeType
    const idempotencyKey = `${notif.subscriptionId || "sub"}_${docId}_${changeType}_${Math.floor(
      Date.now() / 2000
    )}`;

    // Debounce rapid edits per document and enqueue
    const enqueueResult = queueService.enqueueDebounced(
      docId,
      {
        subscriptionId: notif.subscriptionId,
        changeType: changeType,
        resource: notif.resource,
        resourceData: notif.resourceData,
        receivedAt: new Date().toISOString(),
      },
      idempotencyKey
    );

    results.push({ docId, changeType, ...enqueueResult });
  }

  // Ack fast with HTTP 202 Accepted per spec
  return res.status(202).json({
    accepted: true,
    processed: results.length,
    events: results,
  });
});

/**
 * POST /api/webhooks/onedrive/subscribe
 * Manually trigger subscription registration with Microsoft Graph
 */
router.post("/subscribe", async (req, res) => {
  try {
    const { notificationUrl } = req.body || {};
    const subscription = await onedriveService.createWebhookSubscription(
      notificationUrl
    );
    res.json({ success: true, subscription });
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message,
      hint: "Ensure OneDrive is connected and notificationUrl is a publicly reachable HTTPS endpoint (e.g. via ngrok).",
    });
  }
});

module.exports = router;
