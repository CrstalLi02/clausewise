"use client";

import { useState } from "react";
import { login, setToken, type User } from "@/lib/api";
import Icon from "./Icon";
import styles from "./Login.module.css";

const DEMOS = [
  { type: "Student", user: "student", pass: "student123", desc: "Policy Q&A, trusted citations, and personal memory", icon: "chat" as const },
  { type: "Department Admin", user: "jwc_admin", pass: "admin123", desc: "Department documents, reviews, and local evolution", icon: "building" as const },
  { type: "Super Admin", user: "admin", pass: "admin123", desc: "Global governance, Loop, and policy experiments", icon: "shield" as const },
];

export default function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(""); setBusy(true);
    try {
      const res = await login(username.trim(), password);
      setToken(res.token); onLogin(res.user);
    } catch (err) { setError(String(err instanceof Error ? err.message : err)); }
    finally { setBusy(false); }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.ambientOne} /><div className={styles.ambientTwo} />
      <section className={styles.story}>
        <div className={styles.wordmark}><span className={styles.seal}>C</span><span>CLAUSEWISE</span></div>
        <div className={styles.eyebrow}><span /> TRUSTED KNOWLEDGE ORCHESTRATION</div>
        <h1>Policy knowledge that is<br />grounded and keeps evolving.</h1>
        <p className={styles.lead}>Connect cross-department facts, memory, and feedback so every answer is traceable and every correction changes behavior in the next round.</p>
        <div className={styles.arch}>
          {[
            ["database", "Fact plane", "Versioned policies and citations"],
            ["brain", "Five memory layers", "Episodic, user, organizational, learning"],
            ["loop", "Evolution loop", "Observe → Reflect → Adapt"],
          ].map(([icon, title, text]) => <div key={title} className={styles.archItem}>
            <span className={styles.archIcon}><Icon name={icon as "database"} size={19} /></span>
            <div><b>{title}</b><small>{text}</small></div>
          </div>)}
        </div>
        <div className={styles.trust}><Icon name="shield" size={16} /> Python control plane · pi Agent execution engine · end-to-end auditing</div>
      </section>

      <section className={styles.loginSide}>
        <form className={styles.card} onSubmit={submit}>
          <div className={styles.mobileBrand}><span className={styles.seal}>C</span> Clausewise</div>
          <div className={styles.cardHead}>
            <span className={styles.kicker}>WELCOME BACK</span>
            <h2>Enter the knowledge hub</h2>
            <p>You will be taken to the workspace that matches your account permissions</p>
          </div>
          <label className={styles.field}><span>Username</span><div className={styles.inputWrap}><Icon name="agent" size={17}/><input value={username} onChange={e => setUsername(e.target.value)} placeholder="Enter your username" autoFocus /></div></label>
          <label className={styles.field}><span>Password</span><div className={styles.inputWrap}><Icon name="shield" size={17}/><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" /></div></label>
          {error && <div className={styles.error}>{error}</div>}
          <button className={styles.submit} type="submit" disabled={busy}>{busy ? <><span className={styles.spinner}/>Verifying</> : <>Secure sign-in <Icon name="arrow" size={17}/></>}</button>
          <div className={styles.divider}><span>Quick sign-in with a demo identity</span></div>
          <div className={styles.demoList}>{DEMOS.map(d => <button key={d.user} type="button" className={styles.demo} onClick={() => { setUsername(d.user); setPassword(d.pass); setError(""); }}>
            <span className={styles.demoIcon}><Icon name={d.icon} size={17}/></span><span><b>{d.type}</b><small>{d.desc}</small></span><code>{d.user}</code>
          </button>)}</div>
          <div className={styles.security}><Icon name="shield" size={14}/> Local demo environment · Tokens expire · Actions isolated by role</div>
        </form>
      </section>
    </div>
  );
}
