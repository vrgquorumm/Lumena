import { createReadStream } from "node:fs";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { fileURLToPath } from "node:url";
import http from "node:http";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "dist/public");
const port = Number(process.env.PORT || 8080);
const apiOrigin = (process.env.API_ORIGIN || "").replace(/\/+$/, "");

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function isApiRequest(requestUrl) {
  return requestUrl.pathname === "/api" || requestUrl.pathname.startsWith("/api/");
}

async function proxyApi(request, response, requestUrl) {
  if (!apiOrigin) {
    response.writeHead(503, { "content-type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ message: "API_ORIGIN is not configured." }));
    return;
  }

  const headers = new Headers();
  for (const [key, value] of Object.entries(request.headers)) {
    if (key !== "host" && key !== "content-length" && typeof value === "string") {
      headers.set(key, value);
    }
  }

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await new Promise((resolve, reject) => {
          const chunks = [];
          request.on("data", (chunk) => chunks.push(chunk));
          request.on("end", () => resolve(Buffer.concat(chunks)));
          request.on("error", reject);
        });

  const upstream = await fetch(`${apiOrigin}${requestUrl.pathname}${requestUrl.search}`, {
    method: request.method,
    headers,
    body,
  });

  const responseHeaders = {
    "content-type": upstream.headers.get("content-type") || "application/octet-stream",
    "cache-control": upstream.headers.get("cache-control") || "no-cache",
    connection: upstream.headers.get("connection") || "keep-alive",
    "x-accel-buffering": upstream.headers.get("x-accel-buffering") || "no",
  };
  response.writeHead(upstream.status, responseHeaders);

  if (upstream.body) {
    Readable.fromWeb(upstream.body).pipe(response);
  } else {
    response.end();
  }
}

async function serveStatic(response, requestUrl) {
  const requestedPath = requestUrl.pathname === "/" ? "/index.html" : requestUrl.pathname;
  const relativePath = decodeURIComponent(requestedPath).replace(/^\/+/, "");
  const candidate = path.resolve(root, relativePath);
  const insideRoot = candidate === root || candidate.startsWith(`${root}${path.sep}`);
  let filePath = insideRoot ? candidate : path.join(root, "index.html");

  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) throw new Error("Not a file");
  } catch {
    filePath = path.join(root, "index.html");
  }

  const extension = path.extname(filePath).toLowerCase();
  response.writeHead(200, {
    "content-type": contentTypes[extension] || "application/octet-stream",
    "cache-control": extension === ".html" ? "no-cache" : "public, max-age=31536000, immutable",
  });
  createReadStream(filePath).pipe(response);
}

const server = http.createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
    if (isApiRequest(requestUrl)) {
      await proxyApi(request, response, requestUrl);
      return;
    }
    await serveStatic(response, requestUrl);
  } catch (error) {
    console.error(error);
    if (!response.headersSent) response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    response.end("Bad gateway");
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Lumena web listening on ${port}`);
});