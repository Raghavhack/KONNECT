const express = require("express");
const router = express.Router();
const multer = require("multer");
const documentParser = require("../services/documentParser");
const grpcClient = require("../services/grpcClient");
const gdriveService = require("../services/gdriveService");
const onedriveService = require("../services/onedriveService");

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024 }, // 25MB max
});

/**
 * POST /api/ingest/upload
 * Directly uploads a PDF, DOCX, TXT, or MD file and ingests it into the knowledge graph
 */
router.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ success: false, error: "No file provided" });
    }

    const { originalname, mimetype, buffer } = req.file;
    console.log(`[Ingestion] Received file upload: ${originalname} (${mimetype}, ${buffer.length} bytes)`);

    const textContent = await documentParser.parseBuffer(buffer, originalname, mimetype);
    if (!textContent || !textContent.trim()) {
      return res.status(400).json({ success: false, error: "Extracted document content is empty" });
    }

    const documentId = `doc_${Date.now()}_${originalname.replace(/[^a-zA-Z0-9_\-\.]/g, "_")}`;
    const fastMode = req.body.fast_mode !== undefined ? (req.body.fast_mode === "true" || req.body.fast_mode === true) : true;

    // Pass to Python Intelligence Service via gRPC
    const result = await grpcClient.updateKnowledgeGraph({
      documentId,
      title: originalname,
      content: textContent,
      kHops: 2,
      triggerLeiden: true,
      invalidateCache: true,
      fastMode,
    });

    console.log(`[Ingestion] Graph updated for [${originalname}]:`, result);

    res.json({
      success: true,
      documentId,
      fileName: originalname,
      contentLength: textContent.length,
      graphUpdate: {
        nodesUpdated: result.affected_nodes_count || result.new_entities_count || 0,
        newEntities: result.new_entities_count || 0,
        edgesUpdated: result.new_relationships_count || 0,
        updatedEmbeddings: result.updated_embeddings_count || 0,
        totalTimeMs: result.total_time_ms,
        message: result.message,
      },
    });
  } catch (err) {
    console.error("[Ingestion] Error uploading document:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * POST /api/ingest/text
 * Ingests raw text directly into the knowledge graph
 */
router.post("/text", async (req, res) => {
  try {
    const { title, content } = req.body;
    if (!content || !content.trim()) {
      return res.status(400).json({ success: false, error: "Document content cannot be empty" });
    }

    const documentTitle = title || `Document_${new Date().toISOString()}`;
    const documentId = `doc_text_${Date.now()}`;
    const fastMode = req.body.fast_mode !== undefined ? (req.body.fast_mode === true || req.body.fast_mode === "true") : true;

    const result = await grpcClient.updateKnowledgeGraph({
      documentId,
      title: documentTitle,
      content: content,
      kHops: 2,
      triggerLeiden: true,
      invalidateCache: true,
      fastMode,
    });

    res.json({
      success: true,
      documentId,
      title: documentTitle,
      graphUpdate: {
        nodesUpdated: result.affected_nodes_count || result.new_entities_count || 0,
        newEntities: result.new_entities_count || 0,
        edgesUpdated: result.new_relationships_count || 0,
        updatedEmbeddings: result.updated_embeddings_count || 0,
        totalTimeMs: result.total_time_ms,
        message: result.message,
      },
    });
  } catch (err) {
    console.error("[Ingestion] Error ingesting text:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * POST /api/ingest/sync-gdrive
 * Scans connected Google Drive 'KONNECT' folder and ingests documents
 * using the same fast ingestion pipeline as direct document uploads.
 */
router.post("/sync-gdrive", async (req, res) => {
  try {
    const status = gdriveService.getStatus();
    if (!status.connected) {
      return res.status(400).json({
        success: false,
        error: "Google Drive is not connected. Please authorize via /api/auth/google/connect first.",
      });
    }

    const files = await gdriveService.listFiles();
    console.log(`[Google Drive Sync] Found ${files.length} documents in private KONNECT folder`);

    let ingestedCount = 0;
    const results = [];

    for (const file of files) {
      try {
        const content = await gdriveService.fetchFileContent(file.id, file.name, file.mimeType);
        if (content && content.trim()) {
          const documentId = `doc_${Date.now()}_${file.name.replace(/[^a-zA-Z0-9_\-\.]/g, "_")}`;
          const result = await grpcClient.updateKnowledgeGraph({
            documentId,
            title: file.name,
            content,
            kHops: 2,
            triggerLeiden: true,
            invalidateCache: true,
            fastMode: true,
          });
          ingestedCount++;
          results.push({
            documentId,
            fileName: file.name,
            nodesUpdated: result.affected_nodes_count || result.new_entities_count || 0,
            newEntities: result.new_entities_count || 0,
            edgesUpdated: result.new_relationships_count || 0,
            totalTimeMs: result.total_time_ms,
            message: result.message,
          });
        }
      } catch (fileErr) {
        console.warn(`[Google Drive Sync] Error ingesting ${file.name}:`, fileErr.message);
      }
    }

    res.json({
      success: true,
      folderScoped: true,
      folderName: "KONNECT",
      message: `Scanned private 'KONNECT' folder. Synchronized ${ingestedCount} documents with fast ingestion.`,
      ingestedCount,
      documents: results,
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * POST /api/ingest/sync-onedrive
 * Scans connected OneDrive 'KONNECT' folder and ingests documents
 * using the same fast ingestion pipeline as direct document uploads.
 */
router.post("/sync-onedrive", async (req, res) => {
  try {
    const files = await onedriveService.listFiles();
    console.log(`[OneDrive Sync] Found ${files.length} documents in private KONNECT folder`);

    let ingestedCount = 0;
    const results = [];

    for (const file of files) {
      try {
        const content = await onedriveService.fetchFileContent(file.id, file.name, file.file?.mimeType);
        if (content && content.trim()) {
          const documentId = `doc_${Date.now()}_${file.name.replace(/[^a-zA-Z0-9_\-\.]/g, "_")}`;
          const result = await grpcClient.updateKnowledgeGraph({
            documentId,
            title: file.name,
            content,
            kHops: 2,
            triggerLeiden: true,
            invalidateCache: true,
            fastMode: true,
          });
          ingestedCount++;
          results.push({
            documentId,
            fileName: file.name,
            nodesUpdated: result.affected_nodes_count || result.new_entities_count || 0,
            newEntities: result.new_entities_count || 0,
            edgesUpdated: result.new_relationships_count || 0,
            totalTimeMs: result.total_time_ms,
            message: result.message,
          });
        }
      } catch (fileErr) {
        console.warn(`[OneDrive Sync] Error ingesting ${file.name}:`, fileErr.message);
      }
    }

    res.json({
      success: true,
      folderScoped: true,
      folderName: "KONNECT",
      message: `Scanned private 'KONNECT' folder. Synchronized ${ingestedCount} documents with fast ingestion.`,
      ingestedCount,
      documents: results,
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

module.exports = router;
