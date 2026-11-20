const fs = require("fs");
const path = require("path");
const axios = require("axios");
const dotenv = require("dotenv");
const { withExponentialBackoff } = require("../utils/retry");
const documentParser = require("./documentParser");

const TOKEN_FILE = path.resolve(__dirname, "../../.gdrive_tokens.json");

function reloadEnv() {
  dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  dotenv.config({ path: path.resolve(__dirname, "../../../.env") });
}

reloadEnv();

class GoogleDriveService {
  constructor() {
    this.tokens = this._loadTokens();
    this.konnectFolderId = this.tokens?.konnectFolderId || null;
  }

  get clientId() {
    reloadEnv();
    return process.env.GOOGLE_CLIENT_ID || "demo-google-client-id";
  }

  get clientSecret() {
    reloadEnv();
    return process.env.GOOGLE_CLIENT_SECRET || "demo-google-client-secret";
  }

  get redirectUri() {
    reloadEnv();
    return (
      process.env.GOOGLE_REDIRECT_URI ||
      "http://localhost:5000/api/auth/google/callback"
    );
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
    if (tokens.konnectFolderId) {
      this.konnectFolderId = tokens.konnectFolderId;
    }
    try {
      fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens, null, 2));
    } catch {
      // ignore
    }
  }

  getAuthUrl(customRedirectUri = null) {
    const finalRedirectUri = customRedirectUri || this.redirectUri;
    const rootUrl = "https://accounts.google.com/o/oauth2/v2/auth";
    const options = {
      redirect_uri: finalRedirectUri,
      client_id: this.clientId,
      access_type: "offline",
      response_type: "code",
      prompt: "consent",
      // Privacy-first scopes:
      // drive.file grants access ONLY to files/folders created or opened by KONNECT.
      // It does NOT grant access to the user's personal drive files outside the KONNECT folder.
      scope: [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
      ].join(" "),
    };

    const qs = new URLSearchParams(options);
    return `${rootUrl}?${qs.toString()}`;
  }

  async handleCallback(code, customRedirectUri = null) {
    const finalRedirectUri = customRedirectUri || this.redirectUri;
    try {
      const response = await axios.post(
        "https://oauth2.googleapis.com/token",
        new URLSearchParams({
          code,
          client_id: this.clientId,
          client_secret: this.clientSecret,
          redirect_uri: finalRedirectUri,
          grant_type: "authorization_code",
        }).toString(),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );

      const tokenData = response.data;

      // Get user profile
      try {
        const userRes = await axios.get("https://www.googleapis.com/oauth2/v2/userinfo", {
          headers: { Authorization: `Bearer ${tokenData.access_token}` },
        });
        tokenData.account = {
          email: userRes.data.email,
          name: userRes.data.name || userRes.data.email,
        };
      } catch {
        tokenData.account = { email: "user@workspace.com", name: "Google Drive User" };
      }

      this._saveTokens(tokenData);

      // Automatically create or link the dedicated private "KONNECT" folder
      await this.getOrCreateKonnectFolder();

      return this.tokens;
    } catch (err) {
      console.warn("[Google Drive] Token exchange error:", err.message);
      // Demo / simulated tokens for testing without Google Cloud credentials
      const demoTokens = {
        access_token: "demo_google_access_token",
        token_type: "Bearer",
        expires_in: 3600,
        account: { email: "demo@workspace.com", name: "Demo User" },
        konnectFolderId: "gdrive-folder-konnect-demo",
      };
      this._saveTokens(demoTokens);
      return demoTokens;
    }
  }

  /**
   * Ensures a dedicated 'KONNECT' folder exists in Google Drive.
   * Scopes all future discovery, parsing, and webhooks to this folder only.
   */
  async getOrCreateKonnectFolder() {
    if (!this.tokens?.access_token || this.tokens.access_token === "demo_google_access_token") {
      this.konnectFolderId = "gdrive-folder-konnect-demo";
      return this.konnectFolderId;
    }

    try {
      // 1. Search for existing 'KONNECT' folder
      const searchRes = await axios.get("https://www.googleapis.com/drive/v3/files", {
        headers: { Authorization: `Bearer ${this.tokens.access_token}` },
        params: {
          q: "name = 'KONNECT' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
          fields: "files(id, name)",
          spaces: "drive",
        },
      });

      if (searchRes.data.files && searchRes.data.files.length > 0) {
        this.konnectFolderId = searchRes.data.files[0].id;
        console.log(`[Google Drive] Found existing private folder 'KONNECT' (ID: ${this.konnectFolderId})`);
      } else {
        // 2. Create the 'KONNECT' folder
        const createRes = await axios.post(
          "https://www.googleapis.com/drive/v3/files",
          {
            name: "KONNECT",
            mimeType: "application/vnd.google-apps.folder",
            description: "Dedicated workspace folder for KONNECT AI. Only documents inside this folder are processed.",
          },
          {
            headers: {
              Authorization: `Bearer ${this.tokens.access_token}`,
              "Content-Type": "application/json",
            },
          }
        );
        this.konnectFolderId = createRes.data.id;
        console.log(`[Google Drive] Created private folder 'KONNECT' (ID: ${this.konnectFolderId})`);
      }

      this.tokens.konnectFolderId = this.konnectFolderId;
      this._saveTokens(this.tokens);
      return this.konnectFolderId;
    } catch (err) {
      console.warn(`[Google Drive] Could not verify/create KONNECT folder: ${err.message}`);
      return null;
    }
  }

  getStatus() {
    const isRealToken = Boolean(
      this.tokens?.access_token &&
      this.tokens.access_token !== "demo_google_access_token" &&
      !this.tokens.access_token.startsWith("demo_")
    );
    return {
      connected: isRealToken,
      account: isRealToken ? this.tokens?.account : null,
      folderScoped: true,
      folderName: "KONNECT",
      folderId: this.konnectFolderId,
    };
  }

  /**
   * Lists files strictly inside the 'KONNECT' folder.
   */
  async listFiles() {
    if (!this.tokens?.access_token || this.tokens.access_token === "demo_google_access_token") {
      return [
        {
          id: "gdrive-doc-1",
          name: "Project_Roadmap_Q3.docx",
          mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          size: 14200,
        },
        {
          id: "gdrive-doc-2",
          name: "Backend_Architecture.pdf",
          mimeType: "application/pdf",
          size: 87905,
        },
      ];
    }

    if (!this.konnectFolderId) {
      await this.getOrCreateKonnectFolder();
    }

    const query = `'${this.konnectFolderId}' in parents and trashed = false`;
    const res = await axios.get("https://www.googleapis.com/drive/v3/files", {
      headers: { Authorization: `Bearer ${this.tokens.access_token}` },
      params: {
        q: query,
        fields: "files(id, name, mimeType, size, modifiedTime)",
      },
    });

    return res.data.files || [];
  }

  /**
   * Fetches and parses document content for a file in the KONNECT folder.
   */
  async fetchFileContent(fileId, fileName = "", mimeType = "") {
    if (!this.tokens?.access_token || this.tokens.access_token === "demo_google_access_token") {
      return `Sample content for file ${fileName || fileId} inside KONNECT folder.`;
    }

    return withExponentialBackoff(
      async () => {
        // Google Docs export as text
        if (mimeType === "application/vnd.google-apps.document") {
          const exportRes = await axios.get(
            `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=text/plain`,
            {
              headers: { Authorization: `Bearer ${this.tokens.access_token}` },
              responseType: "text",
            }
          );
          return exportRes.data;
        }

        // Binary files (PDF, DOCX, TXT)
        const res = await axios.get(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
          headers: { Authorization: `Bearer ${this.tokens.access_token}` },
          responseType: "arraybuffer",
        });

        const buffer = Buffer.from(res.data);
        return await documentParser.parseBuffer(buffer, fileName, mimeType);
      },
      { maxAttempts: 5, baseDelayMs: 500, operationName: `GoogleDrive:FetchFile:${fileId}` }
    );
  }
}

module.exports = new GoogleDriveService();
