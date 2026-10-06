"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listReviewOrders,
  submitReview,
  type Dashboard,
  type ReviewOrder,
} from "@/lib/api";
import styles from "./admin.module.css";
import { phaseBadgeClass, phaseLabel } from "./labels";

type VerdictMap = Record<number, { correct: boolean; correction: string }>;

export default function ReviewPanel({ data, refresh }: { data: Dashboard; refresh: () => void }) {
  const [deptId, setDeptId] = useState("");
  const [status, setStatus] = useState("");
  const [orders, setOrders] = useState<ReviewOrder[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [verdicts, setVerdicts] = useState<Record<string, VerdictMap>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setOrders(await listReviewOrders(deptId || undefined, status || undefined));
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    }
  }, [deptId, status]);

  useEffect(() => {
    load();
  }, [load]);

  const depts = data.departments || [];

  function setVerdict(orderId: string, index: number, correct: boolean) {
    setVerdicts((prev) => {
      const cur = prev[orderId] || {};
      return { ...prev, [orderId]: { ...cur, [index]: { correct, correction: cur[index]?.correction || "" } } };
    });
  }
  function setCorrection(orderId: string, index: number, correction: string) {
    setVerdicts((prev) => {
      const cur = prev[orderId] || {};
      return { ...prev, [orderId]: { ...cur, [index]: { correct: cur[index]?.correct ?? false, correction } } };
    });
  }

  async function onSubmit(order: ReviewOrder) {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const vmap = verdicts[order._id] || {};
      if (Object.keys(vmap).length !== order.qa_pairs.length) {
        setErr(`Please mark every question "Correct" or "Incorrect" (reviewed ${Object.keys(vmap).length}/${order.qa_pairs.length})`);
        return;
      }
      const list = order.qa_pairs.map((_, i) => ({
        index: i,
        correct: vmap[i].correct,
        correction: vmap[i]?.correction || "",
      }));
      const res = await submitReview(order._id, list);
      setMsg(
        `Review complete: ${res.correct}/${res.total} correct (accuracy ${Math.round((res.accuracy ?? 0) * 100)}%). The department Loop phase has been advanced automatically based on accuracy.`
      );
      setExpanded(null);
      await load();
      refresh();
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  const pendingCount = orders.filter((o) => o.status === "pending").length;

  return (
    <div>
      <h2 className={styles.title}>
        Review Center <span className={styles.muted}>(new documents auto-generate questions → system answers → human review → feedback accumulates)</span>
      </h2>

      <div className={styles.row} style={{ marginBottom: 16 }}>
        <select className={styles.select} value={deptId} onChange={(e) => setDeptId(e.target.value)}>
          <option value="">All departments</option>
          {depts.map((d) => (
            <option key={d._id} value={d._id}>
              {d.name}
            </option>
          ))}
        </select>
        <select className={styles.select} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="reviewed">Reviewed</option>
          <option value="auto_approved">Auto-approved (out of the loop)</option>
        </select>
        <span className={styles.muted}>{pendingCount} pending</span>
      </div>

      {msg && <div style={{ marginBottom: 12, color: "#15803d", fontSize: 13 }}>{msg}</div>}
      {err && <div className={styles.error} style={{ marginBottom: 12 }}>{err}</div>}

      {orders.length === 0 ? (
        <div className={styles.empty}>No review orders yet. The system generates one automatically after a new document is uploaded.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {orders.map((order) => {
            const open = expanded === order._id;
            return (
              <div key={order._id} className={styles.card}>
                <div className={styles.rowBetween}>
                  <div>
                    <h3 style={{ marginBottom: 4 }}>{order.doc_title}</h3>
                    <div className={styles.muted}>
                      {order._id} · {order.dept_id} · {order.created_at?.slice(0, 19).replace("T", " ")}
                    </div>
                  </div>
                  <div className={styles.row}>
                    {order.accuracy != null && (
                      <span className={styles.badge + " " + styles.badgeBlue}>
                        Accuracy {Math.round(order.accuracy * 100)}%
                      </span>
                    )}
                    <span
                      className={
                        styles.badge +
                        " " +
                        (order.status === "pending"
                          ? styles.badgeAmber
                          : order.status === "auto_approved"
                          ? styles.badgeGreen
                          : styles.badgeBlue)
                      }
                    >
                      {order.status === "pending"
                        ? "Pending"
                        : order.status === "reviewed"
                        ? "Reviewed"
                        : "Auto-approved"}
                    </span>
                    <button className={styles.btnGhost + " " + styles.btnSm} onClick={() => setExpanded(open ? null : order._id)}>
                      {open ? "Collapse" : "View details"}
                    </button>
                  </div>
                </div>

                {open && (
                  <div style={{ marginTop: 12 }}>
                    {order.qa_pairs.map((qa, i) => {
                      const v = (verdicts[order._id] || {})[i];
                      const correct = v?.correct;
                      const isReviewed = order.status !== "pending";
                      return (
                        <div key={i} className={styles.qablock}>
                          <div className={styles.qaQuestion}>
                            {i + 1}. {qa.question}
                          </div>
                          {qa.expected && (
                            <div className={styles.muted} style={{ marginBottom: 6 }}>
                              Key points of the reference answer: {qa.expected}
                            </div>
                          )}
                          <div className={styles.qaAnswer}>System answer: {qa.answer}</div>
                          {qa.citations?.length > 0 && (
                            <div className={styles.qaMeta}>
                              <b>Citations: </b>
                              {qa.citations.map((c, j) => (
                                <span key={j} className={styles.citation}>
                                  [{c.chunk_index != null ? c.chunk_index + 1 : "?"}] {c.doc_title || c.doc_id}
                                  {c.section_path?.length ? " · " + c.section_path.join(" > ") : ""}
                                </span>
                              ))}
                            </div>
                          )}

                          {!isReviewed ? (
                            <>
                              <div className={styles.verdictRow}>
                                <button
                                  className={`${styles.verdictBtn} ${correct === true ? styles.correctSel : ""}`}
                                  onClick={() => setVerdict(order._id, i, true)}
                                >
                                  ✓ Correct
                                </button>
                                <button
                                  className={`${styles.verdictBtn} ${correct === false ? styles.incorrectSel : ""}`}
                                  onClick={() => setVerdict(order._id, i, false)}
                                >
                                  ✗ Incorrect
                                </button>
                                {correct === false && (
                                  <input
                                    className={styles.input}
                                    style={{ flex: 1 }}
                                    placeholder="Enter a correction (it will be saved as feedback)"
                                    value={v?.correction || ""}
                                    onChange={(e) => setCorrection(order._id, i, e.target.value)}
                                  />
                                )}
                              </div>
                            </>
                          ) : (
                            <div className={styles.qaMeta}>
                              Review result: {qa.verdict === "rejected" ? "✗ Incorrect" : "✓ Correct"}
                              {qa.correction ? ` · Correction: ${qa.correction}` : ""}
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {order.status === "pending" && (
                      <div className={styles.row}>
                        <button className={styles.btn} disabled={busy} onClick={() => onSubmit(order)}>
                          {busy ? "Submitting…" : "Submit review"}
                        </button>
                        <span className={styles.muted}>After submission, results are written to the question bank and added to the cumulative accuracy; once the threshold is exceeded, human review is disabled for this department.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <h2 className={styles.title} style={{ marginTop: 24 }}>
        Review Statistics and Phases by Department
      </h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Department</th>
            <th>Phase</th>
            <th>Reviewed samples</th>
            <th>Correct</th>
            <th>Accuracy</th>
            <th>Progress</th>
          </tr>
        </thead>
        <tbody>
          {depts.map((d) => {
            const s = d.review_stats || { total: 0, correct: 0, accuracy: 0 };
            const pct = Math.round((s.accuracy ?? 0) * 100);
            return (
              <tr key={d._id}>
                <td>{d.name}</td>
                <td>
                  <span className={styles.badge + " " + phaseBadgeClass(d.loop_phase)}>{phaseLabel(d.loop_phase)}</span>
                </td>
                <td>{s.total}</td>
                <td>{s.correct}</td>
                <td>{pct}%</td>
                <td>
                  <div className={styles.row}>
                    <div className={styles.progress}>
                      <div
                        className={`${styles.progressFill} ${pct >= 80 ? styles.progressFillGreen : styles.progressFillAmber}`}
                        style={{ width: Math.min(100, pct) + "%" }}
                      />
                    </div>
                    <span className={styles.muted}>80%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
