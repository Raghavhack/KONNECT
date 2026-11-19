const dotenv = require("dotenv");
const { google } = require("googleapis");

const path = require("path");

function reloadEnv() {
    dotenv.config({
        path: path.resolve(__dirname, "../../../.env"),
    });
}

reloadEnv();

const googleConfig = {
  get clientId() {
    reloadEnv();
    return process.env.GOOGLE_CLIENT_ID || "";
  },

  get clientSecret() {
    reloadEnv();
    return process.env.GOOGLE_CLIENT_SECRET || "";
  },

  get redirectUri() {
    reloadEnv();
    return (
      process.env.GOOGLE_REDIRECT_URI ||
      "http://localhost:5000/api/auth/google/callback"
    );
  },

  get scopes() {
    reloadEnv();
    if (process.env.GOOGLE_SCOPES) {
      return process.env.GOOGLE_SCOPES.split(" ").filter(Boolean);
    }

    return ["https://www.googleapis.com/auth/drive.readonly"];
  },
};

const makeClient = () =>
  new google.auth.OAuth2(
    googleConfig.clientId,
    googleConfig.clientSecret,
    googleConfig.redirectUri
  );

module.exports = { google, googleConfig, makeClient };