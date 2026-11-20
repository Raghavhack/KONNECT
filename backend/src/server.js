const express = require("express");
const cors = require("cors");
const path = require("path");
process.on("beforeExit", (code) => {
  console.log("[Debug] Node beforeExit:", code);
  console.log("[Debug] Active resources:", process.getActiveResourcesInfo());
});

process.on("exit", (code) => {
  console.log("[Debug] Node exit:", code);
});

process.on("uncaughtExceptionMonitor", (err) => {
  console.error("[Debug] Uncaught exception:", err);
});
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
});

const healthRoutes = require("./routes/healthRoutes");
const queryRoutes = require("./routes/queryRoutes");
const streamRoutes = require("./routes/streamRoutes");
const onedriveAuthRoutes = require("./routes/onedriveAuthRoutes");
const onedriveWebhookRoutes = require("./routes/onedriveWebhookRoutes");
const googleAuthRoutes = require("./routes/googleAuthRoutes");
const gdriveRoutes = require("./routes/gdriveRoutes");
const billingRoutes = require("./routes/billingRoutes");
const ingestionRoutes = require("./routes/ingestionRoutes");

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.text({ type: "text/*" }));


app.get("/", (req, res) => {
  res.json({
    message: "KONNECT Backend is running!",
    architecture: "Node.js Orchestration Layer + gRPC Transport + Python Intelligence Service",
    endpoints: {
      health: "/api/health",
      query: "POST /api/query",
      stream: "GET /api/stream",
      cacheInvalidate: "POST /api/cache/invalidate",
      simulateEdit: "POST /api/simulate-edit",
      onedriveAuth: "/api/auth/onedrive/connect",
      onedriveStatus: "/api/auth/onedrive/status",
      onedriveWebhook: "POST /api/webhooks/onedrive",
      gdriveAuth: "/api/auth/gdrive/connect",
      gdriveStatus: "/api/auth/gdrive/status",
      gdriveWebhook: "POST /api/webhooks/gdrive",
      billingPlans: "GET /api/billing/plans",
      billingCheckout: "POST /api/billing/checkout",
    },
  });
});

app.use("/api/health", healthRoutes);
app.use("/api", queryRoutes);
app.use("/api", streamRoutes);
app.use("/api/auth/onedrive", onedriveAuthRoutes);
app.use("/api/webhooks/onedrive", onedriveWebhookRoutes);
app.use("/api/auth/gdrive", gdriveRoutes);
app.use("/api/auth/google", gdriveRoutes);
app.use("/api/webhooks/gdrive", gdriveRoutes);
app.use("/api/webhooks/google", gdriveRoutes);
app.use("/api/billing", billingRoutes);
app.use("/api/ingest", ingestionRoutes);

// app.listen(PORT, () => {
//   console.log(`Server running on port ${PORT}`);
// });
const PORT = process.env.PORT || 5000;

const server = app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log("[Debug] Server listening:", server.listening);
  server.ref();
});

server.on("close", () => {
  console.log("[Debug] HTTP server was closed!");
});

server.on("error", (err) => {
  console.error("[Debug] HTTP server error:", err);
});
