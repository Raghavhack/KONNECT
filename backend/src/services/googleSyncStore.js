const fs = require("fs");
const path = require("path");

const STATE_FILE_PATH = path.join(
    __dirname,
    "../../.google_sync_state.json"
);

class GoogleSyncStore {
    constructor() {
        this.state = this.loadFromDisk();
    }

    loadFromDisk() {
        try {
            if (fs.existsSync(STATE_FILE_PATH)) {
                return JSON.parse(
                    fs.readFileSync(STATE_FILE_PATH, "utf-8")
                );
            }
        } catch (err) {
            console.warn(
                "[Google Sync] Failed to load state:",
                err.message
            );
        }

        return {
            pageToken: null,
            updatedAt: null,
        };
    }

    saveToDisk() {
        try {
            fs.writeFileSync(
                STATE_FILE_PATH,
                JSON.stringify(this.state, null, 2),
                "utf-8"
            );
        } catch (err) {
            console.error(
                "[Google Sync] Failed to save state:",
                err.message
            );
            throw err;
        }
    }

    getPageToken() {
        return this.state.pageToken || null;
    }

    setPageToken(pageToken) {
        this.state.pageToken = pageToken;
        this.state.updatedAt = new Date().toISOString();

        this.saveToDisk();

        return this.state;
    }

    clear() {
        this.state = {
            pageToken: null,
            updatedAt: null,
        };

        try {
            if (fs.existsSync(STATE_FILE_PATH)) {
                fs.unlinkSync(STATE_FILE_PATH);
            }
        } catch (err) {
            console.warn(
                "[Google Sync] Failed to clear state:",
                err.message
            );
        }
    }
}

module.exports = new GoogleSyncStore();