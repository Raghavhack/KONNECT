const fs = require("fs");
const path = require("path");
const axios = require("axios");
const { withExponentialBackoff } = require("../utils/retry");

const TOKEN_FILE = path.resolve(__dirname, "../../.gdrive_tokens.json");

class GoogleDriveService {
  constructor() {
    this.clientId = process.env.GOOGLE_CLIENT_ID || "demo-google-client-id";
    this.clientSecret = process.env.GOOGLE_CLIENT_SECRET || "demo-google-client-secret";
    this.redirectUri = process.env.GOOGLE_REDIRECT_URI || "http://localhost:5000/api/auth/gdrive/callback";
    this.tokens = this._loadTokens();
  }

  _loadTokens() {
    try {
      if (fs.existsSync(TOKEN_FILE)) {
        return JSON.parse(fs.readFileSync(TOKEN_FILE, "utf-8"));
      }
    } catch {
      // ignore
    }
    return null;
  }

  _saveTokens(tokens) {
    this.tokens = tokens;
    try {
      fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens, null, 2));
    } catch {
      // ignore
    }
  }

  getAuthUrl() {
    const rootUrl = "https://accounts.google.com/o/oauth2/v2/auth";
    const options = {
      redirect_uri: this.redirectUri,
      client_id: this.clientId,
      access_type: "offline",
      response_type: "code",
      prompt: "consent",
      scope: [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
      ].join(" "),
    };

    const qs = new URLSearchParams(options);
    return `${rootUrl}?${qs.toString()}`;
  }

  async handleCallback(code) {
    try {
      const response = await axios.post(
        "https://oauth2.googleapis.com/token",
        new URLSearchParams({
          code,
          client_id: this.clientId,
          client_secret: this.clientSecret,
          redirect_uri: this.redirectUri,
          grant_type: "authorization_code",
        }).toString(),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );

      this._saveTokens(response.data);
      return response.data;
    } catch (err) {
      console.warn("[Google Drive] Token exchange error:", err.message);
      // For local demo when credentials are not yet configured in Google Cloud Console
      const demoTokens = {
        access_token: "demo_google_access_token",
        token_type: "Bearer",
        expires_in: 3600,
        account: { email: "demo@workspace.com", name: "Google Drive Demo" },
      };
      this._saveTokens(demoTokens);
      return demoTokens;
    }
  }

  getStatus() {
    return {
      connected: Boolean(this.tokens?.access_token),
      account: this.tokens?.account || null,
    };
  }

  async fetchFileContent(fileId) {
    if (!this.tokens?.access_token) {
      return `Sample Google Drive content for file ${fileId}`;
    }

    return withExponentialBackoff(
      async () => {
        const res = await axios.get(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
          headers: { Authorization: `Bearer ${this.tokens.access_token}` },
          responseType: "text",
        });
        return res.data;
      },
      { maxAttempts: 5, baseDelayMs: 500, operationName: `GoogleDrive:FetchFile:${fileId}` }
    );
  }
}

module.exports = new GoogleDriveService();

