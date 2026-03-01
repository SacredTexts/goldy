#!/usr/bin/env node
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const https = require("https");
const os = require("os");

const REPO = "SacredTexts/goldy";
const BIN_NAME = "goldy";
const BIN_DIR = path.join(__dirname, "bin");

function getPlatform() {
  const platform = os.platform();
  const arch = os.arch();

  const platformMap = {
    darwin: "darwin",
    linux: "linux",
    win32: "windows",
  };

  const archMap = {
    x64: "amd64",
    arm64: "arm64",
  };

  const goos = platformMap[platform];
  const goarch = archMap[arch];

  if (!goos || !goarch) {
    console.error(`Unsupported platform: ${platform}/${arch}`);
    process.exit(1);
  }

  return { goos, goarch, isWindows: platform === "win32" };
}

function getVersion() {
  const pkg = require("./package.json");
  return pkg.version;
}

function downloadFile(url) {
  return new Promise((resolve, reject) => {
    const follow = (url, redirects = 0) => {
      if (redirects > 5) return reject(new Error("Too many redirects"));

      https
        .get(url, { headers: { "User-Agent": "goldy-npm" } }, (res) => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            return follow(res.headers.location, redirects + 1);
          }
          if (res.statusCode !== 200) {
            return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          }
          const chunks = [];
          res.on("data", (chunk) => chunks.push(chunk));
          res.on("end", () => resolve(Buffer.concat(chunks)));
          res.on("error", reject);
        })
        .on("error", reject);
    };
    follow(url);
  });
}

async function extractTarGz(buffer, destDir) {
  const tmpFile = path.join(os.tmpdir(), `goldy-${Date.now()}.tar.gz`);
  fs.writeFileSync(tmpFile, buffer);
  fs.mkdirSync(destDir, { recursive: true });
  execSync(`tar -xzf "${tmpFile}" -C "${destDir}"`, { stdio: "pipe" });
  fs.unlinkSync(tmpFile);
}

async function extractZip(buffer, destDir) {
  const tmpFile = path.join(os.tmpdir(), `goldy-${Date.now()}.zip`);
  fs.writeFileSync(tmpFile, buffer);
  fs.mkdirSync(destDir, { recursive: true });
  execSync(`unzip -o "${tmpFile}" -d "${destDir}"`, { stdio: "pipe" });
  fs.unlinkSync(tmpFile);
}

async function main() {
  const { goos, goarch, isWindows } = getPlatform();
  const version = getVersion();
  const ext = isWindows ? "zip" : "tar.gz";
  const binSuffix = isWindows ? ".exe" : "";

  const archiveName = `${BIN_NAME}_${goos}_${goarch}.${ext}`;
  const url = `https://github.com/${REPO}/releases/download/v${version}/${archiveName}`;

  console.log(`Downloading goldy v${version} for ${goos}/${goarch}...`);

  try {
    const buffer = await downloadFile(url);
    const tmpDir = path.join(os.tmpdir(), `goldy-extract-${Date.now()}`);

    if (isWindows) {
      await extractZip(buffer, tmpDir);
    } else {
      await extractTarGz(buffer, tmpDir);
    }

    fs.mkdirSync(BIN_DIR, { recursive: true });

    const srcBin = path.join(tmpDir, `${BIN_NAME}${binSuffix}`);
    const destBin = path.join(BIN_DIR, `${BIN_NAME}${binSuffix}`);

    fs.copyFileSync(srcBin, destBin);
    if (!isWindows) {
      fs.chmodSync(destBin, 0o755);
    }

    fs.rmSync(tmpDir, { recursive: true, force: true });

    console.log(`Installed goldy to ${destBin}`);
  } catch (err) {
    console.error(`Failed to download goldy: ${err.message}`);
    console.error(`URL: ${url}`);
    console.error("");
    console.error("You can install manually:");
    console.error("  cd ~/.goldy/cmd/goldy-install && go install .");
    process.exit(1);
  }
}

main();
