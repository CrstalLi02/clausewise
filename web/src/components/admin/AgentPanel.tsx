"use client";

import { useEffect, useState } from "react";
import { agents as fetchAgents, type AgentInfo } from "@/lib/api";
import styles from "./admin.module.css";
import { phaseBadgeClass, phaseLabel } from "./labels";

export default function AgentPanel({ data }: { data: import("@/lib/api").Dashboard }) {
  const [rows, setRows] = useState<AgentInfo[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchAgents().then(setRows).catch((e) => setErr(String(e instanceof Error ? e.message : e)));
  }, []);

  return (
    <div>
      <h2 className={styles.title}>
        Department Sub-Agent Visualization
        <span className={styles.muted}> (each department has its own agent stack: Intent + Retrieval + Answer + Verifier)</span>
      </h2>
      <div className={styles.muted} style={{ marginBottom: 16 }}>
        K8s deploys an independent Deployment + HPA per department: low-traffic departments run 1 replica, while high-traffic departments (Academic Affairs / Student Affairs) scale up to 20 replicas at peak.
      </div>
      {err && <div className={styles.error} style={{ marginBottom: 12 }}>{err}</div>}

      <div className={styles.grid2}>
        {rows.map((a) => {
          const acc = Math.round((a.review_stats?.accuracy ?? 0) * 100);
          return (
            <div key={a._id} className={styles.card}>
              <div className={styles.rowBetween}>
                <h3>{a.name}</h3>
                <span className={styles.badge + " " + phaseBadgeClass(a.loop_phase)}>{phaseLabel(a.loop_phase)}</span>
              </div>
              <div className={styles.muted} style={{ marginBottom: 10 }}>
                {a.name_en} · {a._id}
              </div>

              <div className={styles.row} style={{ marginBottom: 10, gap: 5 }}>
                {["Orchestrator", "Intent", "Retrieval", "Answer", "Verifier"].map((name) => (
                  <span key={name} className={styles.badge + " " + styles.badgeBlue} style={{ fontSize: 10 }}>
                    {name}
                  </span>
                ))}
              </div>

              <table className={styles.table}>
                <tbody>
                  <tr>
                    <th>Model</th>
                    <td className={styles.mono}>{a.model}</td>
                  </tr>
                  <tr>
                    <th>Temperature</th>
                    <td>{a.temperature}</td>
                  </tr>
                  <tr>
                    <th>Replicas</th>
                    <td>{a.replicas} (elastic 1–20)</td>
                  </tr>
                  <tr>
                    <th>Ingested documents</th>
                    <td>{a.doc_count}</td>
                  </tr>
                  <tr>
                    <th>Department Skills</th>
                    <td>{a.skill_count}</td>
                  </tr>
                  <tr>
                    <th>Hook</th>
                    <td>{a.hook_count}</td>
                  </tr>
                  <tr>
                    <th>Review accuracy</th>
                    <td>{acc}% ({a.review_stats?.total ?? 0} samples)</td>
                  </tr>
                </tbody>
              </table>

              {a.hot_queries?.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div className={styles.muted} style={{ marginBottom: 4 }}>
                    Hot frequent questions (department memory)
                  </div>
                  {a.hot_queries.map((h, i) => (
                    <span key={i} className={styles.badge + " " + styles.badgeGray} style={{ margin: "0 4px 4px 0" }}>
                      {h.q} ×{h.n}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
