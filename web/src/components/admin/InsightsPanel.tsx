"use client";
import { useCallback, useEffect, useState } from "react";
import { systemInsights, type SystemInsights, type User } from "@/lib/api";
import Icon, { type IconName } from "../Icon";
import styles from "./admin.module.css";

const PLANE_ICON: Record<string, IconName> = { working: "activity", episodic: "clock", user: "agent", organization: "building", learning: "loop" };
const SIGNAL_LABEL: Record<string,string> = { up:"Adopted",down:"Thumbs-down",correction:"Correction",copy:"Copied",follow_up:"Follow-up",abandon:"Abandoned",verifier_pass:"Verification passed",verifier_fail:"Verification failed" };
export default function InsightsPanel({ user }: { user: User }) {
  const [data,setData]=useState<SystemInsights|null>(null); const [error,setError]=useState("");
  const load=useCallback(()=>systemInsights().then(setData).catch(e=>setError(String(e))),[]);
  useEffect(()=>{load()},[load]);
  if(error) return <div className={styles.errorBanner}>{error}</div>;
  if(!data) return <div className={styles.loading}><span/><b>Building the memory topology</b></div>;
  const f=data.fact_plane,e=data.evolution;
  return <div className={styles.panelStack}>
    <section className={styles.heroPanel}><div><span className={styles.eyebrow}>MEMORY GOVERNANCE</span><h2>Five memory planes, one independent fact plane</h2><p>Memory handles context understanding and continuous learning; policy facts always go back to active documents and full chunks, guarding the trust boundary with sources and versions.</p></div><div className={styles.heroBadge}><Icon name="brain" size={28}/><span><b>{data.memory_planes.reduce((n,p)=>n+p.count,0)}</b><small>Governable memory units</small></span></div></section>
    <div className={styles.memoryMap}>
      <div className={styles.planeRail}>{data.memory_planes.map((p,i)=><div className={styles.memoryPlane} key={p.key}><span className={styles.planeIndex}>0{i+1}</span><span className={styles.planeIcon}><Icon name={PLANE_ICON[p.key]} size={19}/></span><div><b>{p.name}</b><small>{p.detail}</small><code>{p.store}</code></div><strong>{p.count}</strong></div>)}</div>
      <div className={styles.factCore}><div className={styles.orbit}/><span className={styles.factIcon}><Icon name="database" size={28}/></span><small>INDEPENDENT SOURCE OF TRUTH</small><h3>Policy fact plane</h3><p>Full MongoDB documents and chunks</p><div className={styles.factStats}><span><b>{f.active_documents}</b>Active documents</span><span><b>{f.chunks}</b>Fact chunks</span><span><b>{f.relations}</b>Knowledge relations</span><span><b>{f.conflicts}</b>Conflicts</span></div></div>
    </div>
    <div className={styles.grid3}>
      <div className={styles.card}><div className={styles.cardTitle}><span><Icon name="shield" size={17}/>Memory governance</span><em>GUARDRAIL</em></div><div className={styles.statRows}><span>Usage records<b>{data.governance.usage_records}</b></span><span>Stale organizational memory<b>{data.governance.stale_org_memory}</b></span><span>Pending candidates<b>{data.governance.pending_candidates}</b></span><span>Privacy view<b>{user.dept_id ? "Department isolated" : "Global audit"}</b></span></div></div>
      <div className={styles.card}><div className={styles.cardTitle}><span><Icon name="layers" size={17}/>Policy evolution</span><em>VERSIONED</em></div><div className={styles.statRows}><span>Policy version snapshots<b>{e.strategy_versions}</b></span><span>Policy execution records<b>{e.executions}</b></span><span>Running experiments<b>{e.experiments.filter(x=>x.status==="running").length}</b></span><span>Lifecycle proposals<b>{e.proposals.length}</b></span></div></div>
      <div className={styles.card}><div className={styles.cardTitle}><span><Icon name="activity" size={17}/>Canary traffic</span><em>A/B BUCKET</em></div><div className={styles.bucket}><div style={{flex:e.treatment||1}}>Treatment <b>{e.treatment}</b></div><div style={{flex:e.control||1}}>Control <b>{e.control}</b></div></div><p className={styles.cardHint}>Stable hash bucketing · Policy versions and hit records retained · Automatic rollback supported</p></div>
    </div>
    <div className={styles.grid2}>
      <div className={styles.card}><div className={styles.cardTitle}><span><Icon name="activity" size={17}/>Feedback signal radar</span><em>OBSERVE</em></div><div className={styles.signalGrid}>{Object.entries(data.signals).map(([k,v])=><div key={k}><span>{SIGNAL_LABEL[k]||k}</span><b>{v}</b><i style={{width:`${Math.min(100,v*8)}%`}}/></div>)}</div></div>
      <div className={styles.card}><div className={styles.cardTitle}><span><Icon name="clock" size={17}/>Recent execution traces</span><em>TRACEABLE</em></div><div className={styles.traceList}>{data.recent_traces.length===0?<div className={styles.empty}>No execution records yet</div>:data.recent_traces.slice(0,7).map(t=><div key={t.id}><span className={t.success?styles.traceOk:styles.traceFail}/><span><b>{t.query||"System review task"}</b><small>{t.intent||"review"} · {t.latency_ms}ms</small></span><time>{t.created_at.slice(5,16).replace("T"," ")}</time></div>)}</div></div>
    </div>
  </div>;
}
