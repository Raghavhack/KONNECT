// const { google, makeClient, googleConfig } = require("../config/google");
// const tokenStore = require("./googleTokenStore-temp");

// class GoogleDriveService {
//     constructor() {
//         this.oauth2Client = null;
//     }

//     getOAuthClient() {
//         if (!googleConfig.clientId || !googleConfig.clientSecret) {
//             throw new Error(
//                 "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing. Check backend/.env"
//             );
//         }

//         if (!this.oauth2Client) {
//             this.oauth2Client = makeClient();

//             this.oauth2Client.on("tokens", (tokens) => {
//                 try {
//                     const existingTokens = tokenStore.getTokens() || {};

//                     tokenStore.setTokens({
//                         ...existingTokens,
//                         ...tokens,
//                         refresh_token:
//                             tokens.refresh_token ||
//                             existingTokens.refresh_token,
//                     });
//                 } catch (err) {
//                     console.error(
//                         "[Google Drive] Failed to save refreshed tokens:",
//                         err.message
//                     );
//                 }
//             });
//         }

//         return this.oauth2Client;
//     }

//     getAuthUrl(state = "konnect-google-auth") {
//         const client = this.getOAuthClient();

//         return client.generateAuthUrl({
//             access_type: "offline",
//             prompt: "consent",
//             scope: googleConfig.scopes,
//             state,
//             include_granted_scopes: true,
//         });
//     }

//     async exchangeCodeForTokens(code) {
//         const client = this.getOAuthClient();

//         const { tokens } = await client.getToken(code);

//         if (!tokens.access_token) {
//             throw new Error("Google did not return an access token.");
//         }

//         const existingTokens = tokenStore.getTokens() || {};

//         const savedTokens = {
//             ...existingTokens,
//             ...tokens,
//             refresh_token:
//                 tokens.refresh_token || existingTokens.refresh_token,
//         };

//         client.setCredentials(savedTokens);
//         tokenStore.setTokens(savedTokens);

//         return savedTokens;
//     }

//     async getAuthenticatedClient() {
//         const tokens = tokenStore.getTokens();

//         if (!tokens || !tokens.refresh_token) {
//             throw new Error(
//                 "Google Drive is not connected. Please reconnect your Google account."
//             );
//         }

//         const client = this.getOAuthClient();

//         client.setCredentials(tokens);

//         const accessToken = await client.getAccessToken();

//         if (!accessToken || !accessToken.token) {
//             throw new Error("Unable to refresh Google access token.");
//         }

//         return client;
//     }

//     async getValidAccessToken() {
//         const client = await this.getAuthenticatedClient();

//         const token = client.credentials.access_token;

//         if (!token) {
//             throw new Error("Google access token is unavailable.");
//         }

//         return token;
//     }

//     async listFiles(pageSize = 20, pageToken = undefined) {
//         const auth = await this.getAuthenticatedClient();

//         const drive = google.drive({
//             version: "v3",
//             auth,
//         });

//         const response = await drive.files.list({
//             pageSize,
//             pageToken,
//             fields: "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,size)",
//             orderBy: "modifiedTime desc",
//         });

//         return {
//             files: response.data.files || [],
//             nextPageToken: response.data.nextPageToken || null,
//         };
//     }

//     async getFile(fileId) {
//         const auth = await this.getAuthenticatedClient();

//         const drive = google.drive({
//             version: "v3",
//             auth,
//         });

//         const response = await drive.files.get({
//             fileId,
//             fields: "id,name,mimeType,size,modifiedTime,webViewLink",
//         });

//         return response.data;
//     }

//     async downloadFile(fileId) {
//         const auth = await this.getAuthenticatedClient();

//         const drive = google.drive({
//             version: "v3",
//             auth,
//         });

//         const response = await drive.files.get(
//             {
//                 fileId,
//                 alt: "media",
//             },
//             {
//                 responseType: "stream",
//             }
//         );

//         return response.data;
//     }

//     getStatus() {
//     const tokens = tokenStore.getTokens();

//     if (!tokens || !tokens.refresh_token) {
//         return {
//             connected: false,
//             message: "Google Drive is not connected.",
//         };
//     }

//     return {
//         connected: true,
//         isExpired: tokenStore.isExpired(),
//         expiresAt: tokens.expiry_date
//             ? new Date(tokens.expiry_date).toISOString()
//             : null,
//     };
//   }

//     disconnect() {
//         tokenStore.clear();

//         if (this.oauth2Client) {
//             this.oauth2Client.setCredentials({});
//             this.oauth2Client = null;
//         }
//     }
// }

// module.exports = new GoogleDriveService();
const { google, makeClient, googleConfig } = require("../config/google");
const tokenStore = require("./googleTokenStore-temp");
const mammoth = require("mammoth");
const { PDFParse } = require("pdf-parse");
const googleSyncStore = require("./googleSyncStore");
class GoogleDriveService {
    constructor() {
        this.oauth2Client = null;
    }

    getOAuthClient() {
        if (!googleConfig.clientId || !googleConfig.clientSecret) {
            throw new Error(
                "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing. Check backend/.env"
            );
        }

        if (!this.oauth2Client) {
            this.oauth2Client = makeClient();

            this.oauth2Client.on("tokens", (tokens) => {
                try {
                    const existingTokens = tokenStore.getTokens() || {};

                    tokenStore.setTokens({
                        ...existingTokens,
                        ...tokens,
                        refresh_token:
                            tokens.refresh_token ||
                            existingTokens.refresh_token,
                    });
                } catch (err) {
                    console.error(
                        "[Google Drive] Failed to save refreshed tokens:",
                        err.message
                    );
                }
            });
        }

        return this.oauth2Client;
    }

    getAuthUrl(state = "konnect-google-auth") {
        const client = this.getOAuthClient();

        return client.generateAuthUrl({
            access_type: "offline",
            prompt: "consent",
            scope: googleConfig.scopes,
            state,
            include_granted_scopes: true,
        });
    }

    async exchangeCodeForTokens(code) {
        const client = this.getOAuthClient();
        const { tokens } = await client.getToken(code);

        if (!tokens.access_token) {
            throw new Error("Google did not return an access token.");
        }

        const existingTokens = tokenStore.getTokens() || {};

        const savedTokens = {
            ...existingTokens,
            ...tokens,
            refresh_token:
                tokens.refresh_token || existingTokens.refresh_token,
        };

        client.setCredentials(savedTokens);
        tokenStore.setTokens(savedTokens);

        return savedTokens;
    }

    async getAuthenticatedClient() {
        const tokens = tokenStore.getTokens();

        if (!tokens || !tokens.refresh_token) {
            throw new Error(
                "Google Drive is not connected. Please reconnect your Google account."
            );
        }

        const client = this.getOAuthClient();
        client.setCredentials(tokens);

        const accessToken = await client.getAccessToken();

        if (!accessToken || !accessToken.token) {
            throw new Error("Unable to refresh Google access token.");
        }

        return client;
    }

    async getValidAccessToken() {
        const client = await this.getAuthenticatedClient();
        const token = client.credentials.access_token;

        if (!token) {
            throw new Error("Google access token is unavailable.");
        }

        return token;
    }

    getDriveClient(auth) {
        return google.drive({
            version: "v3",
            auth,
        });
    }

    async listFiles(pageSize = 20, pageToken = undefined) {
        const auth = await this.getAuthenticatedClient();
        const drive = this.getDriveClient(auth);

        const response = await drive.files.list({
            q: "trashed = false",
            pageSize,
            pageToken,
            includeItemsFromAllDrives: true,
            supportsAllDrives: true,
            fields:
                "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,size,parents)",
            orderBy: "modifiedTime desc",
        });

        return {
            files: response.data.files || [],
            nextPageToken: response.data.nextPageToken || null,
        };
    }

    async getFile(fileId) {
        const auth = await this.getAuthenticatedClient();
        const drive = this.getDriveClient(auth);

        const response = await drive.files.get({
            fileId,
            supportsAllDrives: true,
            fields:
                "id,name,mimeType,size,modifiedTime,webViewLink,parents,trashed",
        });

        return response.data;
    }

    async downloadFile(fileId) {
        const auth = await this.getAuthenticatedClient();
        const drive = this.getDriveClient(auth);

        const response = await drive.files.get(
            {
                fileId,
                alt: "media",
                supportsAllDrives: true,
            },
            {
                responseType: "stream",
            }
        );

        return response.data;
    }

    async readFile(fileId) {
        const auth = await this.getAuthenticatedClient();
        const drive = this.getDriveClient(auth);

        const metadataResponse = await drive.files.get({
            fileId,
            supportsAllDrives: true,
            fields: "id,name,mimeType,size,modifiedTime,webViewLink,trashed",
        });

        const file = metadataResponse.data;

        if (file.trashed) {
            throw new Error("Cannot read a file that has been moved to trash.");
        }

        if (file.mimeType === "application/vnd.google-apps.folder") {
            throw new Error("Cannot read a folder as a file.");
        }

        let content;

        if (file.mimeType === "application/vnd.google-apps.document") {
            const response = await drive.files.export(
                {
                    fileId,
                    mimeType: "text/plain",
                },
                {
                    responseType: "text",
                }
            );

            content = response.data;
        } else if (
            file.mimeType === "application/vnd.google-apps.spreadsheet"
        ) {
            const response = await drive.files.export(
                {
                    fileId,
                    mimeType: "text/csv",
                },
                {
                    responseType: "text",
                }
            );

            content = response.data;
                } else if (
            file.mimeType === "application/vnd.google-apps.presentation"
        ) {
            const response = await drive.files.export(
                {
                    fileId,
                    mimeType: "text/plain",
                },
                {
                    responseType: "text",
                }
            );

            content = response.data;
        } else if (
            file.mimeType ===
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) {
            const response = await drive.files.get(
                {
                    fileId,
                    alt: "media",
                    supportsAllDrives: true,
                },
                {
                    responseType: "arraybuffer",
                }
            );

            const buffer = Buffer.from(response.data);
            const result = await mammoth.extractRawText({ buffer });

            content = result.value;
                } else if (file.mimeType === "application/pdf") {
            const response = await drive.files.get(
                {
                    fileId,
                    alt: "media",
                    supportsAllDrives: true,
                },
                {
                    responseType: "arraybuffer",
                }
            );

            const buffer = Buffer.from(response.data);
            const parser = new PDFParse({ data: buffer });

            try {
                const result = await parser.getText();
                content = result.text;
            } finally {
                await parser.destroy();
            }
        } 
        else {
            const response = await drive.files.get(
                {
                    fileId,
                    alt: "media",
                    supportsAllDrives: true,
                },
                {
                    responseType: "arraybuffer",
                }
            );

            content = Buffer.from(response.data);
        }

        return {
            file,
            content,
            contentType:
                file.mimeType.startsWith("application/vnd.google-apps.") ||
                file.mimeType ===
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
                file.mimeType === "application/pdf"
                    ? "text/plain"
                    : file.mimeType,
        };
    }

    async readSpreadsheet(fileId) {
    const auth = await this.getAuthenticatedClient();

    const sheetsApi = google.sheets({
        version: "v4",
        auth,
    });

    // Get spreadsheet metadata and worksheet names
    const metadata = await sheetsApi.spreadsheets.get({
        spreadsheetId: fileId,
        fields: "spreadsheetId,properties(title),sheets(properties(sheetId,title,index,gridProperties))",
    });

    const sheets = metadata.data.sheets || [];

    if (sheets.length === 0) {
        return {
            spreadsheetId: fileId,
            title: metadata.data.properties?.title,
            sheets: [],
        };
    }

    // Read data from every worksheet
    const ranges = sheets.map((sheet) => {
        const title = sheet.properties.title.replace(/'/g, "''");
        return `'${title}'`;
    });

    const valuesResponse = await sheetsApi.spreadsheets.values.batchGet({
        spreadsheetId: fileId,
        ranges,
        valueRenderOption: "FORMATTED_VALUE",
    });

    const valueRanges = valuesResponse.data.valueRanges || [];

    return {
        spreadsheetId: fileId,
        title: metadata.data.properties?.title,
        sheets: sheets.map((sheet, index) => ({
            sheetId: sheet.properties.sheetId,
            title: sheet.properties.title,
            index: sheet.properties.index,
            rowCount: sheet.properties.gridProperties?.rowCount,
            columnCount: sheet.properties.gridProperties?.columnCount,
            rows: valueRanges[index]?.values || [],
        })),
    };
    }

async getStartPageToken() {
    const auth = await this.getAuthenticatedClient();
    const drive = this.getDriveClient(auth);

    const response = await drive.changes.getStartPageToken({
        supportsAllDrives: true,
    });

    const pageToken = response.data.startPageToken;

    googleSyncStore.setPageToken(pageToken);

    console.log("[Google Sync] Initial page token saved.");

    return pageToken;
}

async initializeChangeTracking() {
    const existingToken = googleSyncStore.getPageToken();

    if (existingToken) {
        console.log("[Google Sync] Existing page token found.");
        return existingToken;
    }

    return await this.getStartPageToken();
}

async pullChanges() {
    const auth = await this.getAuthenticatedClient();
    const drive = this.getDriveClient(auth);

    let pageToken = googleSyncStore.getPageToken();

    if (!pageToken) {
        throw new Error(
            "Google change tracking is not initialized. Initialize it first."
        );
    }

    const changes = [];

    while (pageToken) {
        const response = await drive.changes.list({
            pageToken,
            pageSize: 100,
            includeRemoved: true,
            supportsAllDrives: true,
            includeItemsFromAllDrives: true,
            fields: [
                "nextPageToken",
                "newStartPageToken",
                "changes(fileId,removed,file(id,name,mimeType,trashed,modifiedTime,webViewLink))",
            ].join(","),
        });

        changes.push(...(response.data.changes || []));

        if (response.data.nextPageToken) {
            pageToken = response.data.nextPageToken;
        } else {
            if (response.data.newStartPageToken) {
                googleSyncStore.setPageToken(
                    response.data.newStartPageToken
                );
            }

            break;
        }
    }

    console.log(
        `[Google Sync] Retrieved ${changes.length} changes.`
    );

    return changes;
}
    getStatus() {
        const tokens = tokenStore.getTokens();

        if (!tokens || !tokens.refresh_token) {
            return {
                connected: false,
                message: "Google Drive is not connected.",
            };
        }

        return {
            connected: true,
            isExpired: tokenStore.isExpired(),
            expiresAt: tokens.expiry_date
                ? new Date(tokens.expiry_date).toISOString()
                : null,
        };
    }

    disconnect() {
        tokenStore.clear();

        if (this.oauth2Client) {
            this.oauth2Client.setCredentials({});
            this.oauth2Client = null;
        }
    }
}

module.exports = new GoogleDriveService();