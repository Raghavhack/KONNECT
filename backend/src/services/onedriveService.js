const axios = require("axios");
const msal = require("@azure/msal-node");
const config = require("../config/onedrive");
const tokenStore = require("./tokenStore");
const documentParser = require("./documentParser");
const { withExponentialBackoff } = require("../utils/retry");

class OneDriveService {
  constructor() {
    this._msalClient = null;
    this.konnectFolderId = null;
  }

  getMsalClient() {
    if (!config.clientId || !config.clientSecret) {
      throw new Error(
        "MICROSOFT_CLIENT_ID or MICROSOFT_CLIENT_SECRET is missing. Check backend/.env"
      );
    }

    return new msal.ConfidentialClientApplication({
      auth: {
        clientId: config.clientId,
        authority: `https://login.microsoftonline.com/${config.tenantId}`,
        clientSecret: config.clientSecret,
      },
    });
  }

  /**
   * Generates the Microsoft Entra OAuth 2.0 authorization URL using MSAL Node
   */
  async getAuthUrl(state = "konnect-auth") {
    const cca = this.getMsalClient();
    const authCodeUrlParams = {
      scopes: config.scopes,
      redirectUri: config.redirectUri,
      prompt: "login",
      state: state,
    };

    return await cca.getAuthCodeUrl(authCodeUrlParams);
  }

  /**
   * Exchanges authorization code for tokens using MSAL Node
   */
  async exchangeCodeForTokens(code) {
    const cca = this.getMsalClient();
    const tokenRequest = {
      code: code,
      scopes: config.scopes,
      redirectUri: config.redirectUri,
    };

    const response = await withExponentialBackoff(
      () => cca.acquireTokenByCode(tokenRequest),
      { operationName: "AcquireTokenByCode" }
    );

    const tokens = tokenStore.setTokens({
      accessToken: response.accessToken,
      refreshToken: "", // MSAL handles refresh internally or via account cache
      expiresIn: Math.floor(
        (response.expiresOn.getTime() - Date.now()) / 1000
      ),
      accountInfo: response.account,
    });

    return tokens;
  }

  /**
   * Returns a valid access token, refreshing if necessary
   */
  async getValidAccessToken() {
    const stored = tokenStore.getTokens();
    if (!stored || !stored.accessToken) {
      throw new Error("OneDrive is not connected. Please authenticate first.");
    }

    // If token is still fresh, return it
    if (!tokenStore.isExpired()) {
      return stored.accessToken;
    }

    // Try silent acquisition via MSAL if account exists
    if (stored.accountInfo) {
      try {
        const cca = this.getMsalClient();
        const silentRequest = {
          account: stored.accountInfo,
          scopes: config.scopes,
        };
        const silentResponse = await cca.acquireTokenSilent(silentRequest);
        tokenStore.setTokens({
          accessToken: silentResponse.accessToken,
          refreshToken: "",
          expiresIn: Math.floor(
            (silentResponse.expiresOn.getTime() - Date.now()) / 1000
          ),
          accountInfo: silentResponse.account,
        });
        return silentResponse.accessToken;
      } catch (silentErr) {
        console.warn("Silent token acquisition failed:", silentErr.message);
      }
    }

    return stored.accessToken;
  }

  /**
   * Fetches the authenticated user profile from Microsoft Graph
   */
  async getUserProfile(tokenOverride = null) {
    const token = tokenOverride || (await this.getValidAccessToken());
    const res = await withExponentialBackoff(
      () =>
        axios.get(`${config.graphEndpoint}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      { operationName: "GetUserProfile" }
    );
    return res.data;
  }

  /**
   * Automatically discovers or creates the dedicated private 'KONNECT' folder in OneDrive.
   * Scopes all indexing, delta syncing, and file reading exclusively to this folder.
   */
  async getOrCreateKonnectFolder() {
    const token = await this.getValidAccessToken();
    const stored = tokenStore.getTokens();
    if (stored?.konnectFolderId) {
      this.konnectFolderId = stored.konnectFolderId;
      return this.konnectFolderId;
    }

    try {
      // 1. Check if folder already exists at root:/KONNECT
      const res = await withExponentialBackoff(
        () =>
          axios.get(`${config.graphEndpoint}/me/drive/root:/KONNECT`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        { operationName: "GetKonnectFolder" }
      );
      if (res.data?.id) {
        this.konnectFolderId = res.data.id;
        tokenStore.setTokens({ ...stored, konnectFolderId: res.data.id });
        console.log(`[OneDrive] Found existing private folder 'KONNECT' (ID: ${this.konnectFolderId})`);
        return this.konnectFolderId;
      }
    } catch (err) {
      if (err.response?.status === 404) {
        // 2. Create the folder if not present
        const createRes = await withExponentialBackoff(
          () =>
            axios.post(
              `${config.graphEndpoint}/me/drive/root/children`,
              {
                name: "KONNECT",
                folder: {},
                description: "Dedicated workspace folder for KONNECT AI. Only documents inside this folder are processed.",
              },
              {
                headers: {
                  Authorization: `Bearer ${token}`,
                  "Content-Type": "application/json",
                },
              }
            ),
          { operationName: "CreateKonnectFolder" }
        );
        this.konnectFolderId = createRes.data.id;
        tokenStore.setTokens({ ...stored, konnectFolderId: this.konnectFolderId });
        console.log(`[OneDrive] Created private folder 'KONNECT' (ID: ${this.konnectFolderId})`);
        return this.konnectFolderId;
      }
      console.warn(`[OneDrive] Error locating/creating KONNECT folder:`, err.message);
    }
    return null;
  }

  /**
   * Lists files strictly inside the 'KONNECT' folder.
   */
  async listFiles() {
    const token = await this.getValidAccessToken();
    const folderId = await this.getOrCreateKonnectFolder();

    if (!folderId) {
      return [];
    }

    const res = await withExponentialBackoff(
      () =>
        axios.get(`${config.graphEndpoint}/me/drive/items/${folderId}/children`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      { operationName: "ListKonnectFolderFiles" }
    );

    return res.data.value || [];
  }

  /**
   * Registers a Microsoft Graph Webhook Subscription strictly scoped to the KONNECT folder.
   */
  async createWebhookSubscription(customNotificationUrl = null) {
    const token = await this.getValidAccessToken();
    const folderId = await this.getOrCreateKonnectFolder();
    const notificationUrl =
      customNotificationUrl || config.webhookNotificationUrl;

    const expirationDate = new Date(Date.now() + 4200 * 60 * 1000).toISOString();

    const payload = {
      changeType: "updated,created,deleted",
      notificationUrl: notificationUrl,
      resource: folderId ? `/me/drive/items/${folderId}` : "/me/drive/root",
      expirationDateTime: expirationDate,
      clientState: config.clientStateSecret,
    };

    const res = await withExponentialBackoff(
      () =>
        axios.post(`${config.graphEndpoint}/subscriptions`, payload, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }),
      { operationName: "CreateWebhookSubscription" }
    );

    console.log(`[OneDrive] Webhook subscription created for KONNECT folder. ID: ${res.data.id}`);
    return res.data;
  }

  /**
   * Queries OneDrive Delta strictly for files inside the KONNECT folder.
   */
  async fetchDeltaChanges() {
    const token = await this.getValidAccessToken();
    const folderId = await this.getOrCreateKonnectFolder();
    const existingDeltaToken = tokenStore.getDeltaToken();

    let queryUrl = existingDeltaToken
      ? existingDeltaToken
      : folderId
      ? `${config.graphEndpoint}/me/drive/items/${folderId}/delta`
      : `${config.graphEndpoint}/me/drive/root/delta`;

    let allChanges = [];
    let nextLink = queryUrl;

    while (nextLink) {
      const res = await withExponentialBackoff(
        () =>
          axios.get(nextLink, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        { operationName: "FetchDeltaChanges" }
      );

      const items = res.data.value || [];
      allChanges.push(...items);

      if (res.data["@odata.nextLink"]) {
        nextLink = res.data["@odata.nextLink"];
      } else if (res.data["@odata.deltaLink"]) {
        tokenStore.saveDeltaToken(res.data["@odata.deltaLink"]);
        nextLink = null;
      } else {
        nextLink = null;
      }
    }

    return allChanges;
  }

  /**
   * Downloads and parses a specific OneDrive file item (PDF, DOCX, TXT).
   */
  async fetchFileContent(driveItemId, fileName = "", mimeType = "") {
    const token = await this.getValidAccessToken();
    const res = await withExponentialBackoff(
      () =>
        axios.get(
          `${config.graphEndpoint}/me/drive/items/${driveItemId}/content`,
          {
            headers: { Authorization: `Bearer ${token}` },
            responseType: "arraybuffer",
          }
        ),
      { operationName: `FetchFileContent-${driveItemId}` }
    );

    const buffer = Buffer.from(res.data);
    return await documentParser.parseBuffer(buffer, fileName, mimeType);
  }
}

module.exports = new OneDriveService();
