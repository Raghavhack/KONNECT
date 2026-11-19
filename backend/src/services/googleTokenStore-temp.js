const fs = require("fs");
const path = require("path");

const TOKEN_FILE_PATH = path.join(
    __dirname,
    "../../.google_tokens.json"
);

class GoogleTokenStore {
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
            console.warn(
                "Failed to read Google token file:",
                err.message
            );
        }

        return null;
    }

    saveToDisk(tokens) {
        try {
            fs.writeFileSync(
                TOKEN_FILE_PATH,
                JSON.stringify(tokens, null, 2),
                "utf-8"
            );
        } catch (err) {
            console.error(
                "Failed to save Google tokens:",
                err.message
            );
            throw err;
        }
    }

    setTokens(newTokens) {
        const previousTokens = this.getTokens() || {};

        this.tokens = {
            ...previousTokens,
            ...newTokens,
            refresh_token:
                newTokens.refresh_token ||
                previousTokens.refresh_token ||
                null,
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
        const tokens = this.getTokens();

        if (!tokens || !tokens.expiry_date) {
            return true;
        }

        return Date.now() > tokens.expiry_date - 120000;
    }

    clear() {
        this.tokens = null;

        try {
            if (fs.existsSync(TOKEN_FILE_PATH)) {
                fs.unlinkSync(TOKEN_FILE_PATH);
            }
        } catch (err) {
            console.warn(
                "Failed to delete Google token file:",
                err.message
            );
        }
    }
}

module.exports = new GoogleTokenStore();