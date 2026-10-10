const axios = require("axios");
const msal = require("@azure/msal-node");
const config = require("../config/onedrive");
const tokenStore = require("./tokenStore");
const { withExponentialBackoff } = require("../utils/retry");

class OneDriveService {
  constructor() {
    this._msalClient = null;
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
   * Registers a Microsoft Graph Webhook Subscription for changes on user's drive root.
   */
  async createWebhookSubscription(customNotificationUrl = null) {
    const token = await this.getValidAccessToken();
    const notificationUrl =
      customNotificationUrl || config.webhookNotificationUrl;

    const expirationDate = new Date(Date.now() + 4200 * 60 * 1000).toISOString();

    const payload = {
      changeType: "updated,created,deleted",
      notificationUrl: notificationUrl,
      resource: "/me/drive/root",
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

    console.log(`[OneDrive] Webhook subscription created. ID: ${res.data.id}`);
    return res.data;
  }

  /**
   * Queries OneDrive Delta to get all newly created, updated, or deleted files
   */
  async fetchDeltaChanges() {
    const token = await this.getValidAccessToken();
    const existingDeltaToken = tokenStore.getDeltaToken();

    let queryUrl = existingDeltaToken
      ? existingDeltaToken
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
   * Downloads the raw text or stream of a specific OneDrive file item
   */
  async fetchFileContent(driveItemId) {
    const token = await this.getValidAccessToken();
    const res = await withExponentialBackoff(
      () =>
        axios.get(
          `${config.graphEndpoint}/me/drive/items/${driveItemId}/content`,
          {
            headers: { Authorization: `Bearer ${token}` },
            responseType: "text",
          }
        ),
      { operationName: `FetchFileContent-${driveItemId}` }
    );

    return res.data;
  }
}

module.exports = new OneDriveService();
