const fs = require("fs");
const path = require("path");

const TOKEN_FILE_PATH = path.join(__dirname, "../../.onedrive_tokens.json");

/**
 * Token store for OneDrive OAuth credentials.
 * Keeps tokens in memory with persistent file fallback.
 * Can be replaced by Prisma/PostgreSQL later.
 */
class TokenStore {
  constructor() {
    this.tokens = this.loadFromDisk();
  }

  loadFromDisk() {
    try {
      if (fs.existsSync(TOKEN_FILE_PATH)) {
        const raw = fs.readFileSync(TOKEN_FILE_PATH, "utf-8");
        return JSON.parse(raw);
      }
    } catch (err) {
      console.warn("Failed to read token file from disk:", err.message);
    }
    return null;
  }

  saveToDisk(tokens) {
    try {
      fs.writeFileSync(TOKEN_FILE_PATH, JSON.stringify(tokens, null, 2), "utf-8");
    } catch (err) {
      console.warn("Failed to persist token file to disk:", err.message);
    }
  }

  setTokens({ accessToken, refreshToken, expiresIn, accountInfo }) {
    const expiresAt = Date.now() + (expiresIn ? expiresIn * 1000 : 3600 * 1000);
    this.tokens = {
      accessToken,
      refreshToken,
      expiresAt,
      accountInfo: accountInfo || this.tokens?.accountInfo || null,
      updatedAt: new Date().toISOString(),
    };
    this.saveToDisk(this.tokens);
    return this.tokens;
  }

  getTokens() {
    if (!this.tokens) {
      this.tokens = this.loadFromDisk();
    }
    return this.tokens;
  }

  isExpired() {
    if (!this.tokens || !this.tokens.expiresAt) return true;
    // Mark expired if less than 2 minutes remain
    return Date.now() > this.tokens.expiresAt - 120 * 1000;
  }

  clear() {
    this.tokens = null;
    try {
      if (fs.existsSync(TOKEN_FILE_PATH)) {
        fs.unlinkSync(TOKEN_FILE_PATH);
      }
    } catch (err) {
      console.warn("Failed to delete token file:", err.message);
    }
  }

  saveDeltaToken(deltaLinkOrToken) {
    if (!this.tokens) this.tokens = {};
    this.tokens.deltaToken = deltaLinkOrToken;
    this.saveToDisk(this.tokens);
  }

  getDeltaToken() {
    return this.tokens?.deltaToken || null;
  }
}

module.exports = new TokenStore();
