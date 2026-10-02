const path = require("node:path");
const { getDefaultConfig } = require("expo/metro-config");

const projectRoot = __dirname;
const repositoryRoot = path.resolve(projectRoot, "../..");
const config = getDefaultConfig(projectRoot);

config.watchFolders = [repositoryRoot];

module.exports = config;
