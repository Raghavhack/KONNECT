const express = require("express");
const cors = require("cors");
require("dotenv").config();

const healthRoutes = require("./routes/healthRoutes");
const onedriveAuthRoutes = require("./routes/onedriveAuthRoutes");
const onedriveWebhookRoutes = require("./routes/onedriveWebhookRoutes");

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
      onedriveWebhook: "/api/webhooks/onedrive",
    },
  });
});

app.use("/api/health", healthRoutes);
app.use("/api/auth/onedrive", onedriveAuthRoutes);
app.use("/api/webhooks/onedrive", onedriveWebhookRoutes);

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});