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
const onedriveAuthRoutes = require("./routes/onedriveAuthRoutes");
const onedriveWebhookRoutes = require("./routes/onedriveWebhookRoutes");
const googleAuthRoutes = require("./routes/googleAuthRoutes");

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.text({ type: "text/*" }));


app.get("/", (req, res) => {
  res.json({
    message: "KONNECT Backend is running!",
    endpoints: {
      health: "/api/health",
      onedriveAuth: "/api/auth/onedrive/connect",
      onedriveStatus: "/api/auth/onedrive/status",
      googleAuth: "/api/auth/google/connect",
      googleStatus: "/api/auth/google/status",
      onedriveWebhook: "/api/webhooks/onedrive",
    },
  });
});

app.use("/api/health", healthRoutes);
app.use("/api/auth/onedrive", onedriveAuthRoutes);
app.use("/api/webhooks/onedrive", onedriveWebhookRoutes);
app.use("/api/auth/google", googleAuthRoutes);

// const PORT = process.env.PORT || 5000;

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