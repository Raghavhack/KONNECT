const express = require("express");
const crypto = require("crypto");
const router = express.Router();

const googleDriveService = require("../services/googleDriveService");
const queueService = require("../services/queueService");

const pendingStates = new Map();
const STATE_TTL = 10 * 60 * 1000;

// GET /connect
router.get("/connect", (req, res) => {
    try {
        const state = crypto.randomBytes(32).toString("hex");

        pendingStates.set(state, Date.now() + STATE_TTL);

        for (const [key, expiry] of pendingStates.entries()) {
            if (Date.now() > expiry) {
                pendingStates.delete(key);
            }
        }

        const authUrl = googleDriveService.getAuthUrl(state);

        if (req.query.json === "true") {
            return res.json({
                success: true,
                authUrl,
            });
        }

        res.redirect(authUrl);

    } catch (err) {
        console.error("[Google Connect Error]:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});

// GET /callback
router.get("/callback", async (req, res) => {
    const { code, state, error, error_description } = req.query;

    if (!state || !pendingStates.has(state)) {
        return res.status(403).json({
            success: false,
            error: "Invalid or expired OAuth state.",
        });
    }

    pendingStates.delete(state);

    if (error) {
        return res.status(400).json({
            success: false,
            error,
            description: error_description || "Google authentication failed.",
        });
    }

    if (!code) {
        return res.status(400).json({
            success: false,
            error: "Authorization code missing.",
        });
    }

    try {
        await googleDriveService.exchangeCodeForTokens(code);

        const frontendUrl =
            process.env.FRONTEND_URL ||
            "http://localhost:5173/app/sources";

        const separator = frontendUrl.includes("?") ? "&" : "?";

        res.redirect(`${frontendUrl}${separator}google=connected`);

    } catch (err) {
        console.error("[Google Callback Error]:", err.message);

        res.status(500).json({
            success: false,
            error: "Google authentication failed.",
            details: err.message,
        });
    }
});

// GET /status
router.get("/status", (req, res) => {
    try {
        res.json(googleDriveService.getStatus());
    } catch (err) {
        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});

// POST /disconnect
router.post("/disconnect", (req, res) => {
    try {
        googleDriveService.disconnect();

        res.json({
            success: true,
            message: "Google Drive disconnected successfully.",
        });

    } catch (err) {
        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});

// GET /files - Fetch Google Drive files
router.get("/files", async (req, res) => {
    try {
        const result = await googleDriveService.listFiles(20);

        res.json({
            success: true,
            files: result.files,
            nextPageToken: result.nextPageToken,
        });
    } catch (err) {
        console.error("[Google Drive] File listing error:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
router.get("/files/:fileId", async (req, res) => {
    try {
        const file = await googleDriveService.getFile(req.params.fileId);

        res.json({
            success: true,
            file,
        });
    } catch (err) {
        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
router.get("/files/:fileId/download", async (req, res) => {
    try {
        const stream = await googleDriveService.downloadFile(req.params.fileId);

        stream.on("error", (err) => {
            console.error("[Google Drive Download Error]:", err.message);
            if (!res.headersSent) {
                res.status(500).json({ success: false, error: err.message });
            }
        });

        stream.pipe(res);
    } catch (err) {
        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
router.get("/files/:fileId/read", async (req, res) => {
    try {
        const result = await googleDriveService.readFile(req.params.fileId);

        res.json({
            success: true,
            file: result.file,
            contentType: result.contentType,
            content: Buffer.isBuffer(result.content)
                ? result.content.toString("base64")
                : result.content,
            encoding: Buffer.isBuffer(result.content)
                ? "base64"
                : "utf-8",
        });
    } catch (err) {
        console.error("[Google Drive Read Error]:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
// GET /files/:fileId/sheets
router.get("/files/:fileId/sheets", async (req, res) => {
    try {
        const result = await googleDriveService.readSpreadsheet(
            req.params.fileId
        );

        res.json({
            success: true,
            spreadsheet: result,
        });
    } catch (err) {
        console.error("[Google Sheets Error]:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
// POST /initialize-sync
router.post("/initialize-sync", async (req, res) => {
    try {
        const pageToken =
            await googleDriveService.initializeChangeTracking();

        res.json({
            success: true,
            message: "Google Drive change tracking initialized.",
            pageToken,
        });
    } catch (err) {
        console.error("[Google Sync Init Error]:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});

// GET /changes - Fetch Google Drive changes and enqueue them
router.get("/changes", async (req, res) => {
    try {
        const changes = await googleDriveService.pullChanges();

        const queueResults = [];

        for (const change of changes) {
            const fileId = change.fileId;

            if (!fileId) continue;

            const result = queueService.enqueueDebounced(
                fileId,
                {
                    provider: "google",
                    removed: change.removed || false,
                    file: change.file || null,
                },
                `google:${fileId}:${change.removed ? "removed" : change.file?.modifiedTime || Date.now()}`
            );

            queueResults.push({
                fileId,
                status: result.status,
            });
        }

        res.json({
            success: true,
            totalChanges: changes.length,
            queuedChanges: queueResults.length,
            queueResults,
            changes,
        });

    } catch (err) {
        console.error("[Google Changes Error]:", err.message);

        res.status(500).json({
            success: false,
            error: err.message,
        });
    }
});
module.exports = router;