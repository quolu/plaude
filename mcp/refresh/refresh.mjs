#!/usr/bin/env node
// Plaud Web のログイン済みプロファイルで web.plaud.ai を開き、
// api-apne1 へ飛ぶ Authorization (Bearer JWT) を横取りして token ファイルへ保存する。
// 初回だけ --login で headed 起動して Google ログインを済ませる。以後は headless で毎日回せる。
import puppeteer from "puppeteer-core";
import { mkdirSync, writeFileSync, chmodSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const CHROME = process.env.PLAUD_CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const DIR = process.env.PLAUD_REFRESH_DIR || join(homedir(), ".config", "plaud-templates");
const PROFILE = join(DIR, "browser-profile");
const TOKEN = join(DIR, "token");
const LOGIN = process.argv.includes("--login");
const TIMEOUT_MS = LOGIN ? 300_000 : 45_000;

mkdirSync(PROFILE, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: !LOGIN,
  userDataDir: PROFILE,
  args: ["--no-first-run", "--no-default-browser-check"],
});

try {
  const page = (await browser.pages())[0] || (await browser.newPage());
  const got = new Promise((resolve) => {
    page.on("request", (req) => {
      const auth = req.headers()["authorization"];
      if (auth && auth.startsWith("Bearer ") && req.url().includes("plaud.ai")) resolve(auth);
    });
  });
  await page.goto("https://web.plaud.ai/home", { waitUntil: "domcontentloaded", timeout: 60_000 });
  const auth = await Promise.race([
    got,
    new Promise((_, rej) => setTimeout(() => rej(new Error(
      LOGIN
        ? "ログインが完了しなかった（5分でタイムアウト）"
        : "Authorization を捕捉できなかった。セッション切れの可能性。`node refresh.mjs --login` で再ログインする"
    )), TIMEOUT_MS)),
  ]);
  const payload = JSON.parse(Buffer.from(auth.split(".")[1], "base64").toString());
  writeFileSync(TOKEN, auth + "\n");
  chmodSync(TOKEN, 0o600);
  console.log(`token 保存: ${TOKEN} (exp: ${new Date(payload.exp * 1000).toLocaleString("ja-JP")})`);
} finally {
  await browser.close();
}
