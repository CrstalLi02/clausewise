"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createDepartment,
  getUploadJob,
  listDocuments,
  updateDocumentStatus,
  uploadDocument,
  type Dashboard,
  type Document,
  type User,
} from "@/lib/api";
import styles from "./admin.module.css";

const PIPELINE_ORDER = ["upload", "parse", "clean", "chunk", "metadata", "vectorize", "index", "relations"];

export default function DeptPanel({ data, refresh, user }: { data: Dashboard; refresh: () => void; user: User }) {
  const [deptId, setDeptId] = useState("");
  const [docs, setDocs] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // New department form
  const [nid, setNid] = useState("");
  const [nname, setNname] = useState("");
  const [ncat, setNcat] = useState("general");

  const loadDocs = useCallback(async () => {
    try {
      setDocs(await listDocuments(deptId || undefined));
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    }
  }, [deptId]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !deptId) {
      setErr("Please select a department and a file first");
      return;
    }
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const res = await uploadDocument(file, deptId);
      setMsg(`"${res.file_name}" has been added to the async ingestion queue, job ID ${res.job_id}.`);
      for (let i = 0; i < 60; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const job = await getUploadJob(res.job_id);
        if (job.status === "completed") {
          setMsg(`Document ingestion complete: ${job.result?.relations ?? 0} cross-department relations detected, and a review order has been generated.`);
          break;
        }
        if (job.status === "failed") {
          throw new Error(job.result?.error || "Async ingestion failed");
        }
      }
      e.target.value = "";
      await loadDocs();
      refresh();
    } catch (ex) {
      setErr(String(ex instanceof Error ? ex.message : ex));
    } finally {
      setBusy(false);
    }
  }

  async function onCreateDept() {
    if (!nid || !nname) return;
    setErr("");
    try {
      await createDepartment({ id: nid, name: nname, category: ncat });
      setNid("");
      setNname("");
      await refresh();
    } catch (ex) {
      setErr(String(ex instanceof Error ? ex.message : ex));
    }
  }

  async function toggleStatus(doc: Document, status: string) {
    try {
      await updateDocumentStatus(doc._id, status);
      await loadDocs();
      refresh();
    } catch (ex) {
      setErr(String(ex instanceof Error ? ex.message : ex));
    }
  }

  const depts = data.departments || [];
  const isSuper = !user.dept_id;

  return (
    <div>
      <div className={styles.sectionHead}><div><span className={styles.eyebrow}>KNOWLEDGE ASSETS</span><h2>Department and Policy Fact Governance</h2><p>{isSuper ? "Create departments, import policies, and watch the full chain from parsing to relation discovery." : "This workspace only shows and operates on your department's assets; cross-department data is strictly isolated by the backend."}</p></div></div>
      <div className={styles.grid}>
        {isSuper && <div className={styles.card}>
          <h3>New Department</h3>
          <div className={styles.row} style={{ marginBottom: 8 }}>
            <input className={styles.input} placeholder="ID (e.g. dept_xxx)" value={nid} onChange={(e) => setNid(e.target.value)} />
            <input className={styles.input} placeholder="Name (e.g. International Exchange Office)" value={nname} onChange={(e) => setNname(e.target.value)} />
          </div>
          <div className={styles.row}>
            <select className={styles.select} value={ncat} onChange={(e) => setNcat(e.target.value)}>
              <option value="general">General</option>
              <option value="academic">Academic</option>
              <option value="student">Student</option>
              <option value="finance">Finance</option>
              <option value="admin">Administration</option>
              <option value="logistics">Logistics</option>
            </select>
            <button className={styles.btn} onClick={onCreateDept} disabled={!nid || !nname}>
              Create
            </button>
          </div>
        </div>}

        <div className={styles.card}>
          <h3>Upload a New Document (automatic parsing and ingestion)</h3>
          <div className={styles.row} style={{ marginBottom: 8 }}>
            <select className={styles.select} value={deptId} onChange={(e) => setDeptId(e.target.value)}>
              <option value="">Select department</option>
              {depts.map((d) => (
                <option key={d._id} value={d._id}>
                  {d.name} ({d._id})
                </option>
              ))}
            </select>
          </div>
          <label className={styles.filePicker}><input type="file" accept=".pdf,.docx,.md,.txt,.html" onChange={onUpload} disabled={busy || !deptId} /><span>Choose policy file</span></label>
          <div className={styles.muted} style={{ marginTop: 8 }}>
            Supports PDF / Word / Markdown / TXT. After upload, the document automatically goes through the 3.2 data processing Pipeline, and questions are generated automatically to start a review order.
          </div>
          {busy && <div className={styles.muted} style={{ marginTop: 8 }}>Parsing and ingesting…</div>}
        </div>
      </div>

      {msg && <div style={{ marginTop: 12, color: "#15803d", fontSize: 13 }}>{msg}</div>}
      {err && <div className={styles.error} style={{ marginTop: 12 }}>{err}</div>}

      <h2 className={styles.title} style={{ marginTop: 24 }}>
        Documents ({deptId ? depts.find((d) => d._id === deptId)?.name || deptId : "All"})
      </h2>
      {docs.length === 0 ? (
        <div className={styles.empty}>No documents yet. Select a department and upload one.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {docs.map((doc) => (
            <div key={doc._id} className={styles.card}>
              <div className={styles.rowBetween}>
                <h3>{doc.title}</h3>
                <div className={styles.row}>
                  <span className={styles.badge + " " + (doc.status === "active" ? styles.badgeGreen : styles.badgeGray)}>
                    {doc.status}
                  </span>
                  <span className={styles.badge + " " + styles.badgeBlue}>{doc.doc_type || "other"}</span>
                </div>
              </div>
              <div className={styles.muted} style={{ marginBottom: 10 }}>
                {doc.source?.file_name || doc._id} · Version {doc.version || "1.0"} · {doc.chunk_count ?? 0} chunks · Vectors{" "}
                {doc.vector_status === "ready" ? "ready" : doc.vector_status}
              </div>

              <PipelineStages doc={doc} />

              <div className={styles.row} style={{ marginTop: 10 }}>
                {doc.status !== "archived" && (
                  <button className={styles.btnGhost + " " + styles.btnSm} onClick={() => toggleStatus(doc, "archived")}>
                    Archive
                  </button>
                )}
                {doc.status !== "active" && (
                  <button className={styles.btnGhost + " " + styles.btnSm} onClick={() => toggleStatus(doc, "active")}>
                    Restore to active
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineStages({ doc }: { doc: Document }) {
  const stages = doc.pipeline_stages || [];
  // Production documents persist the final ingestion facts rather than every
  // transient stage. A ready vector plus stored chunks means the synchronous
  // pipeline and relation scan completed successfully.
  const completedFromFacts = doc.vector_status === "ready" && (doc.chunk_count ?? 0) > 0;
  const ordered = PIPELINE_ORDER.map((key) => {
    const s = stages.find((x) => x.key === key);
    return s || { key, name: key, done: completedFromFacts };
  });
  return (
    <div className={styles.row} style={{ gap: 6 }}>
      {ordered.map((s, i) => (
        <span key={s.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span className={styles.badge + " " + (s.done ? styles.badgeGreen : styles.badgeGray)}>
            {s.name}
            {s.detail ? ` (${s.detail})` : ""}
          </span>
          {i < ordered.length - 1 && <span className={styles.muted}>→</span>}
        </span>
      ))}
    </div>
  );
}
