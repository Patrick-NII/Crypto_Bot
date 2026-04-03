import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "out");
const port = parseInt(process.argv[2] || "3000", 10);

const mimeTypes = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".txt": "text/plain",
};

createServer((req, res) => {
  let url = req.url.split("?")[0];
  let filePath = join(root, url);

  const isFile = existsSync(filePath) && statSync(filePath).isFile();
  if (!isFile) {
    const htmlPath = join(root, url === "/" ? "index.html" : url + ".html");
    if (existsSync(htmlPath) && statSync(htmlPath).isFile()) filePath = htmlPath;
    else filePath = join(root, "404.html");
  }

  try {
    const data = readFileSync(filePath);
    const ext = extname(filePath);
    res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
}).listen(port, () => console.log(`Serving on http://localhost:${port}`));
