/**
 * pi-side self-check: verifies that the pi framework + DeepSeek provider can chat normally through the pi agent loop.
 *
 * Notes:
 * - DeepSeek is the primary chat model (critical path; determines the exit code).
 * - The relay service (yunwu) is used for Embedding / bge reranking via direct HTTP calls from the Python backend
 *   (see backend/scripts/doctor.py, verified separately). Here it is only an informational probe.
 *
 * Usage: npm run doctor
 */
import { loadConfig } from "./config.js";
import { buildModels, getMainModel } from "./providers.js";
import { buildTools } from "./tools.js";
import { runAgent, type AgentRuntime } from "./agents.js";
import type { Model } from "@earendil-works/pi-ai";

interface DoctorResult {
  name: string;
  ok: boolean;
  critical: boolean;
  sample?: string;
  error?: string;
}

async function checkModel(
  name: string,
  model: Model<"openai-completions">,
  runtime: AgentRuntime,
  critical: boolean,
): Promise<DoctorResult> {
  try {
    const out = await runAgent({ ...runtime, model }, "You are an assistant. Reply with exactly one word: OK", "Hello");
    return { name, ok: out.length > 0, critical, sample: out.slice(0, 80) };
  } catch (err) {
    return { name, ok: false, critical, error: String(err) };
  }
}

async function main(): Promise<void> {
  const config = loadConfig();
  const models = buildModels(config);
  const tools = buildTools(config);
  const runtime: AgentRuntime = {
    model: getMainModel(models, config),
    streamFn: models.streamSimple.bind(models),
    tools,
  };

  const results: DoctorResult[] = [];
  results.push(await checkModel("pi + DeepSeek Agent", getMainModel(models, config), runtime, true));

  const relay = models.getModel("relay", config.relayModel) as Model<"openai-completions"> | undefined;
  if (relay) {
    results.push(await checkModel("pi + relay Agent (informational)", relay, runtime, false));
  }

  console.log("=".repeat(60));
  console.log("pi-agent self-check");
  console.log("=".repeat(60));
  for (const r of results) {
    const mark = r.ok ? "PASS" : r.critical ? "FAIL" : "WARN";
    console.log(`[${mark}] ${r.name}`);
    if (r.ok) console.log(`       sample: ${r.sample}`);
    else console.log(`       ${r.error ? "error : " + r.error : "no output received"}`);
  }
  if (!relay) {
    console.log("[INFO] The relay service is used for Embedding/bge reranking in this system and is verified via direct Python calls (backend/scripts/doctor.py)");
  }
  console.log("=".repeat(60));

  const criticalOk = results.filter((r) => r.critical).every((r) => r.ok);
  process.exit(criticalOk ? 0 : 1);
}

main();
