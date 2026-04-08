import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "out");
const port = parseInt(process.env.PORT || process.argv[2] || "3000", 10);

const mimeTypes = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".txt": "text/plain",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".map": "application/json",
};

function tryFile(filePath) {
  try {
    if (existsSync(filePath) && statSync(filePath).isFile()) return filePath;
  } catch {}
  return null;
}

createServer((req, res) => {
  let url = req.url.split("?")[0];

  // Decode URI components for encoded paths
  url = decodeURIComponent(url);

  let filePath = join(root, url);

  // 1. Try exact file match (for static assets like .js, .css, .txt, .woff2, etc.)
  let resolved = tryFile(filePath);

  // 2. If it's a directory, look for index.html inside it
  if (!resolved) {
    resolved = tryFile(join(filePath, "index.html"));
  }

  // 3. Try appending .html (for clean URLs like /dashboard -> dashboard.html)
  if (!resolved) {
    resolved = tryFile(filePath + ".html");
  }

  // 4. Fallback to 404.html or generic 404
  if (!resolved) {
    resolved = tryFile(join(root, "404.html"));
  }

  if (!resolved) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  try {
    const data = readFileSync(resolved);
    const ext = extname(resolved);
    const contentType = mimeTypes[ext] || "application/octet-stream";

    res.writeHead(200, {
      "Content-Type": contentType,
      "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=31536000, immutable",
    });
    res.end(data);
  } catch {
    res.writeHead(500);
    res.end("Internal server error");
  }
}).listen(port, () => console.log(`Serving on http://localhost:${port}`));
