"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approveSkill, getLoopJob, listLoopJobs, listTraces, pendingFeedback, runLoop, setLoopPhase,
  type Dashboard, type Hook, type LoopCycleReport, type LoopJob, type Rule, type Skill, type User,
} from "@/lib/api";
import Icon from "../Icon";
import styles from "./admin.module.css";
import { LOOP_STAGES, PHASE_DESC, PHASE_LABEL, phaseBadgeClass, phaseLabel } from "./labels";

const STAGE_INDEX: Record<string, number> = { queued: -1, observe: 1, reflect: 2, adapt: 3, deploy: 4, complete: 5 };
const ARTIFACT_LABEL: Record<string, string> = { skills: "Total Skills", active_skills: "Active Skills", pending_skills: "Pending Skills", hooks: "Hooks", rules: "Rules", experiments: "Experiments", strategy_versions: "Policy versions" };
const ROOT_CAUSE_LABEL: Record<string, string> = { retrieval: "Retrieval recall", intent: "Intent routing", generation: "Answer generation", knowledge_gap: "Knowledge gap" };

export default function LoopPanel({ data, refresh, user }: { data: Dashboard; refresh: () => void; user: User }) {
  const [currentJob, setCurrentJob] = useState<LoopJob | null>(null);
  const [history, setHistory] = useState<LoopJob[]>([]);
  const [feedback, setFeedback] = useState<Record<string, unknown>[] | null>(null);
  const [traces, setTraces] = useState<Record<string, unknown>[] | null>(null);
  const [error, setError] = useState("");
  const isSuper = !user.dept_id;

  const loadHistory = useCallback(async () => {
    if (!isSuper) return;
    try {
      const jobs = await listLoopJobs(8); setHistory(jobs);
      if (!currentJob && jobs[0]) setCurrentJob(jobs[0]);
    } catch { /* history does not block the panel */ }
  }, [isSuper, currentJob]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  useEffect(() => {
    if (!currentJob || !["queued", "running"].includes(currentJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getLoopJob(currentJob._id); setCurrentJob(next);
        if (["completed", "failed"].includes(next.status)) {
          window.clearInterval(timer); await refresh(); await loadHistory();
        }
      } catch (e) { setError(e instanceof Error ? e.message : String(e)); window.clearInterval(timer); }
    }, 900);
    return () => window.clearInterval(timer);
  }, [currentJob?._id, currentJob?.status, refresh, loadHistory]);

  async function onRunLoop() {
    setError("");
    try {
      const queued = await runLoop();
      setCurrentJob({
        _id: queued.job_id, type: "run_loop", status: "queued",
        progress: { stage: "queued", detail: queued.message }, result: undefined,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function onLoadFeedback() { setFeedback(await pendingFeedback()); }
  async function onLoadTraces() { setTraces(await listTraces(20)); }
  async function onSetPhase(phase: string) { await setLoopPhase(phase); refresh(); }
  async function onApproveSkill(id: string) { await approveSkill(id); refresh(); }

  const report = currentJob?.status === "completed" ? currentJob.result as LoopCycleReport : null;
  const currentStage = currentJob?.status === "completed" ? "complete" : currentJob?.progress?.stage || currentJob?.status || "idle";
  const currentIndex = STAGE_INDEX[currentStage] ?? -1;
  const skills = data.skills || [], hooks = data.hooks || [], rules = data.rules || [];

  return <div className={styles.panelStack}>
    <div className={styles.sectionHead}><div><span className={styles.eyebrow}>EVOLUTION LOOP</span><h2>How feedback changes the next round</h2><p>After submission, the real execution stages of the Worker are tracked continuously; on completion, signals, root causes, policy changes, and deployment results are shown.</p></div></div>

    <section className={styles.loopConsole}>
      <div className={styles.loopConsoleHead}>
        <div><span className={styles.liveDot}/><b>{currentJob ? `LOOP JOB · ${currentJob._id.slice(-10)}` : "LOOP CONTROL CENTER"}</b><small>{currentJob ? jobStatusText(currentJob) : "Waiting for an admin to trigger a governed evolution cycle"}</small></div>
        <div className={styles.row}>
          <span className={styles.badge + " " + styles.badgeBlue}>Global phase: {phaseLabel(data.loop_phase_global)}</span>
          {isSuper && <button className={styles.btn} onClick={onRunLoop} disabled={!!currentJob && ["queued", "running"].includes(currentJob.status)}>{currentJob && ["queued", "running"].includes(currentJob.status) ? "Running…" : "▶ Trigger a new Loop"}</button>}
        </div>
      </div>
      <div className={styles.loopTimeline}>{LOOP_STAGES.map((stage, index) => {
        const state = currentJob ? index < currentIndex ? "done" : index === currentIndex ? "running" : "waiting" : "waiting";
        return <div key={stage.key} className={`${styles.timelineStep} ${styles[`timeline_${state}`]}`}>
          <div className={styles.timelineIndex}>{state === "done" ? <Icon name="check" size={14}/> : index + 1}</div>
          <div><b>{stage.name}</b><small>{stage.desc}</small>{state === "running" && <em>{currentJob?.progress?.detail || "Processing"}</em>}</div>
          {index < LOOP_STAGES.length - 1 && <span className={styles.timelineLine}/>}
        </div>;
      })}</div>
      {currentJob?.status === "failed" && <div className={styles.loopError}>Execution failed: {String((currentJob.result as {error?:string})?.error || "Unknown error")}</div>}
      {!currentJob && <div className={styles.loopHint}><Icon name="activity" size={17}/><span><b>After triggering, the page does not stop at the job_id</b><small>The system polls the job automatically, lights up Observe, Reflect, Adapt, and Deploy in turn, and shows the final changes.</small></span></div>}
    </section>

    {error && <div className={styles.errorBanner}>{error}</div>}
    {report && <LoopReport report={report}/>}

    {isSuper && history.length > 0 && <section className={styles.card}>
      <div className={styles.cardTitle}><span><Icon name="clock" size={17}/>Recent Loop runs</span><em>ASYNC JOB HISTORY</em></div>
      <div className={styles.loopHistory}>{history.map(job => <button key={job._id} className={currentJob?._id === job._id ? styles.historyActive : ""} onClick={() => setCurrentJob(job)}><span className={statusClass(job.status)}/><span><b>{job._id.slice(-12)}</b><small>{new Date(job.created_at).toLocaleString("en-US")} · {job.progress?.stage || job.status}</small></span><em>{job.status}</em></button>)}</div>
    </section>}

    <div className={styles.phaseRow}>{(["human_in_loop", "human_on_loop", "human_out_of_loop"] as const).map((phase, i) => <div key={phase} className={`${styles.phaseCard} ${data.loop_phase_global === phase ? styles.active : ""}`} onClick={() => isSuper && onSetPhase(phase)} style={{cursor:isSuper?"pointer":"default"}}><div className={styles.phaseTitle}>Phase {i+1} · {PHASE_LABEL[phase]} {data.loop_phase_global===phase&&"✓"}</div><div className={styles.phaseDesc}>{PHASE_DESC[phase]}</div></div>)}</div>

    <div className={styles.row}><button className={styles.btnGhost} onClick={onLoadFeedback}>Load pending feedback (Observe)</button><button className={styles.btnGhost} onClick={onLoadTraces}>Load recent traces (Execute)</button></div>
    {feedback && <FeedbackTable rows={feedback}/>}
    {traces && <TraceTable rows={traces}/>}

    <div className={styles.sectionHead} style={{marginTop:10}}><div><span className={styles.eyebrow}>EXECUTABLE POLICY MEMORY</span><h2>Skill Self-Evolution (Skill Miner)</h2><p>Baseline Skills provide real, demonstrable workflows; automatic Skills still come from clustering frequent questions, trace replay, and canary experiments.</p></div><div className={styles.skillSummary}><span><b>{skills.length}</b>Total</span><span><b>{skills.filter(s=>s.status==="active").length}</b>Active</span><span><b>{skills.reduce((n,s)=>n+(s.metrics?.trigger_count||0),0)}</b>Hits</span></div></div>
    <div className={styles.skillGrid}>{skills.map(skill => <SkillCard key={skill._id} skill={skill} canApprove={!user.dept_id || skill.dept_id === user.dept_id} onApprove={onApproveSkill}/>)}</div>

    <div className={styles.sectionHead} style={{marginTop:10}}><div><span className={styles.eyebrow}>POLICY GUARDRAILS</span><h2>Hooks and Rules</h2></div></div>
    <div className={styles.grid2}><ArtifactList title={`Hooks · ${hooks.length}`} rows={hooks}/><ArtifactList title={`Rules · ${rules.length}`} rows={rules}/></div>
  </div>;
}

function LoopReport({report}:{report:LoopCycleReport}) {
  const causes = report.reflect?.root_causes || {};
  const changes = Object.entries(report.changes || {}).filter(([,value])=>value!==0);
  return <section className={styles.reportPanel}>
    <div className={styles.reportHero}><span className={styles.reportCheck}><Icon name="check" size={22}/></span><div><span>LOOP CYCLE COMPLETE</span><h3>{report.summary}</h3><p>{report.next_action}</p></div><div className={styles.reportDuration}><b>{(report.duration_ms/1000).toFixed(1)}s</b><small>Duration</small></div></div>
    <div className={styles.reportMetrics}><div><span>Observe</span><b>{report.observed}</b><small>Pending feedback</small></div><div><span>Bad Cases</span><b>{report.bad_cases}</b><small>Sent to root-cause analysis</small></div><div><span>Adapt</span><b>{report.adaptations?.length||0}</b><small>Policy candidates</small></div><div><span>Deploy</span><b>{(report.deployed?.skills||0)+(report.deployed?.hooks||0)+(report.deployed?.rules||0)}</b><small>Released this round</small></div></div>
    <div className={styles.reportGrid}>
      <div className={styles.reportCard}><h4>Observed feedback signals</h4>{Object.keys(report.signals||{}).length===0?<p>No new signals this round</p>:<div className={styles.signalPills}>{Object.entries(report.signals).map(([k,v])=><span key={k}>{signalLabel(k)} <b>{v}</b></span>)}</div>}</div>
      <div className={styles.reportCard}><h4>Reflect root-cause distribution</h4>{Object.keys(causes).length===0?<p>No bad cases, so no attribution needed</p>:<div className={styles.causeBars}>{Object.entries(causes).map(([k,v])=><div key={k}><span>{ROOT_CAUSE_LABEL[k]||k}</span><i><em style={{width:`${Math.min(100,Number(v)*20)}%`}}/></i><b>{v}</b></div>)}</div>}</div>
      <div className={styles.reportCard}><h4>Policy asset changes</h4>{changes.length===0?<p>Only health checks ran this round; no policies were added or released.</p>:<div className={styles.changeList}>{changes.map(([k,v])=><span key={k}>{ARTIFACT_LABEL[k]||k}<b className={Number(v)>0?styles.deltaUp:styles.deltaDown}>{Number(v)>0?"+":""}{v}</b></span>)}</div>}</div>
    </div>
    {report.adaptations?.length>0&&<div className={styles.adaptationList}><h4>Candidates generated this round</h4>{report.adaptations.map((a,i)=><span key={a.id||i}><em>{a.type}</em><b>{a.name||a.id}</b><small>{a.auto_activated?"Auto-applied":"Awaiting review/canary"}</small></span>)}</div>}
  </section>;
}

function SkillCard({skill,canApprove,onApprove}:{skill:Skill;canApprove:boolean;onApprove:(id:string)=>void}) {
  const metrics=skill.metrics||{}, steps=(skill.action?.steps as Array<Record<string,unknown>>|undefined)||[];
  return <article className={styles.skillCard}><header><span className={styles.skillIcon}><Icon name="spark" size={18}/></span><div><span>{skill.origin==="builtin_baseline"?"BUILT-IN BASELINE":skill.auto_generated?"LOOP MINED":"MANAGED SKILL"}</span><h3>{skill.name}</h3></div><em className={skill.status==="active"?styles.skillActive:styles.skillPending}>{skill.status==="active"?"Active":"Pending"}</em></header><p>{skill.description||"An executable policy distilled from recurring question patterns."}</p><div className={styles.skillMeta}><span>v{skill.version||1}</span><span>{skill.scope==="global"?"Global":skill.dept_id}</span><span>Canary {Math.round((skill.gray_percent??1)*100)}%</span></div><div className={styles.skillTriggers}>{(skill.trigger?.intent_patterns||[]).map(p=><span key={p}>{p}</span>)}</div><div className={styles.workflow}><b>Execution workflow</b>{steps.map((step,i)=><div key={i}><span>{i+1}</span><strong>{actionLabel(String(step.action||""))}</strong><small>{stepDetail(step)}</small>{i<steps.length-1&&<i/>}</div>)}</div><div className={styles.skillMetrics}><span><b>{metrics.trigger_count||0}</b>Triggers</span><span><b>{Math.round((metrics.success_rate||0)*100)}%</b>Success rate</span><span><b>{skill.replay?.delta!=null?`${Math.round(skill.replay.delta*100)}%`:"—"}</b>Replay uplift</span></div>{skill.rubric_rules?.length?<details className={styles.skillRules}><summary>View reflection and constraint rules</summary><ul>{[...(skill.unique_rules||[]),...(skill.rubric_rules||[])].map((r,i)=><li key={i}>{r}</li>)}</ul></details>:null}{skill.status==="pending"&&canApprove&&<button className={styles.btn} onClick={()=>onApprove(skill._id)}>Approve and activate</button>}</article>;
}

function FeedbackTable({rows}:{rows:Record<string,unknown>[]}) { return <section className={styles.card}><div className={styles.cardTitle}><span>Pending feedback · {rows.length}</span><em>OBSERVE QUEUE</em></div>{rows.length===0?<div className={styles.empty}>No pending feedback</div>:<table className={styles.table}><thead><tr><th>Signal</th><th>Question</th><th>Answer summary</th></tr></thead><tbody>{rows.slice(0,10).map((f,i)=><tr key={i}><td><span className={styles.badge+" "+(f.signal==="down"||f.signal==="correction"?styles.badgeRed:styles.badgeGray)}>{String(f.signal)}</span></td><td>{String(f.query||"")}</td><td>{String(f.answer||"").slice(0,120)}</td></tr>)}</tbody></table>}</section> }
function TraceTable({rows}:{rows:Record<string,unknown>[]}) { return <section className={styles.card}><div className={styles.cardTitle}><span>Recent traces · {rows.length}</span><em>EXECUTE HISTORY</em></div><table className={styles.table}><thead><tr><th>Time</th><th>Question</th><th>Intent</th><th>Latency</th><th>Verification</th></tr></thead><tbody>{rows.map((t,i)=><tr key={i}><td className={styles.mono}>{String(t.created_at||"").slice(0,19).replace("T"," ")}</td><td>{String(t.query||"")}</td><td>{String((t.intent as Record<string,unknown>)?.type||"")}</td><td>{String(t.latency_ms||0)}ms</td><td><span className={styles.badge+" "+(t.success?styles.badgeGreen:styles.badgeRed)}>{t.success?"Passed":"Failed"}</span></td></tr>)}</tbody></table></section> }
function ArtifactList({title,rows}:{title:string;rows:Array<Hook|Rule>}) { return <section className={styles.card}><div className={styles.cardTitle}><span>{title}</span><em>ACTIVE POLICY</em></div>{rows.map((row,i)=>{const detail="content" in row?row.content:JSON.stringify((row as Hook).trigger||{});return <div className={styles.artifactRow} key={row._id||i}><div><b>{row.name||row._id}</b><small>{detail}</small></div><span className={styles.badge+" "+(row.status==="active"?styles.badgeGreen:styles.badgeAmber)}>{row.status}</span></div>})}</section> }
function jobStatusText(job:LoopJob){if(job.status==="completed")return "Completed; you can review this round's impact";if(job.status==="failed")return "Failed; please check the error message";return job.progress?.detail||"Waiting for a Worker to pick up the job"}
function statusClass(status:string){return status==="completed"?styles.statusDone:status==="failed"?styles.statusFailed:styles.statusRunning}
function signalLabel(key:string){return ({up:"Adopted",down:"Thumbs-down",correction:"Correction",copy:"Copied",follow_up:"Follow-up",abandon:"Abandoned",verifier_pass:"Verification passed",verifier_fail:"Verification failed"} as Record<string,string>)[key]||key}
function actionLabel(action:string){return ({extract_entity:"Extract key entities",retrieve:"Expand fact recall",generate:"Structured generation",call_tool:"Call governance tool"} as Record<string,string>)[action]||action}
function stepDetail(step:Record<string,unknown>){const p=(step.params||{}) as Record<string,unknown>;return String(p.query||p.template||p.tool||p.entity||"Execute policy step")}
