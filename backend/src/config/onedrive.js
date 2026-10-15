const dotenv = require("dotenv");

function reloadEnv() {
  dotenv.config();
}

reloadEnv();

const onedriveConfig = {
  get clientId() {
    reloadEnv();
    return process.env.MICROSOFT_CLIENT_ID || "";
  },
  get clientSecret() {
    reloadEnv();
    return process.env.MICROSOFT_CLIENT_SECRET || "";
  },
  get tenantId() {
    reloadEnv();
    return process.env.MICROSOFT_TENANT_ID || "common";
  },
  get redirectUri() {
    reloadEnv();
    return (
      process.env.MICROSOFT_REDIRECT_URI ||
      "http://localhost:5000/api/auth/onedrive/callback"
    );
  },
  get scopes() {
    reloadEnv();
    if (process.env.MICROSOFT_SCOPES) {
      return process.env.MICROSOFT_SCOPES.split(" ").filter(Boolean);
    }
    // Standard OIDC + Microsoft Graph scopes
    // In Microsoft identity v2.0, offline_access requires openid
    return ["openid", "profile", "offline_access", "User.Read", "Files.Read"];
  },
  authEndpoint: "https://login.microsoftonline.com",
  graphEndpoint: "https://graph.microsoft.com/v1.0",
  get webhookNotificationUrl() {
    reloadEnv();
    return (
      process.env.ONEDRIVE_WEBHOOK_URL ||
      "http://localhost:5000/api/webhooks/onedrive"
    );
  },
  get clientStateSecret() {
    reloadEnv();
    return (
      process.env.ONEDRIVE_CLIENT_STATE || "konnect-onedrive-client-state-secret"
    );
  },
  get debounceQuietWindowMs() {
    reloadEnv();
    return parseInt(process.env.DEBOUNCE_QUIET_WINDOW_MS || "3000", 10);
  },
  get redisUrl() {
    reloadEnv();
    return process.env.REDIS_URL || "redis://localhost:6379";
  },
};

module.exports = onedriveConfig;
