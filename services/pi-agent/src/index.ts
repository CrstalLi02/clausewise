/**
 * pi-agent service entry point.
 */
import { loadConfig } from "./config.js";
import { buildRuntime } from "./runtime.js";
import { buildApp } from "./server.js";

async function main(): Promise<void> {
  const config = loadConfig();
  const runtime = buildRuntime(config);
  const app = buildApp(config, runtime);

  await app.listen({ port: config.port, host: config.host });
  console.log(`[pi-agent] listening on http://${config.host}:${config.port}`);
  console.log(`[pi-agent] backend -> ${config.backendUrl}`);
}

main().catch((err) => {
  console.error("[pi-agent] Startup failed:", err);
  process.exit(1);
});
