"use client";

import { useCallback, useEffect, useState } from "react";
import { dashboard, type Dashboard, type User } from "@/lib/api";
import Icon, { type IconName } from "./Icon";
import styles from "./admin/admin.module.css";
import OverviewPanel from "./admin/OverviewPanel";
import DeptPanel from "./admin/DeptPanel";
import ReviewPanel from "./admin/ReviewPanel";
import LoopPanel from "./admin/LoopPanel";
import AgentPanel from "./admin/AgentPanel";
import InsightsPanel from "./admin/InsightsPanel";

type Tab = "overview" | "dept" | "review" | "loop" | "insights" | "agent";
const TABS: { key: Tab; label: string; sub: string; icon: IconName }[] = [
  { key: "overview", label: "Overview", sub: "Global operations and review phases", icon: "grid" },
  { key: "dept", label: "Knowledge Assets", sub: "Department and document fact governance", icon: "building" },
  { key: "review", label: "Trusted Review", sub: "Human verification and progressive exit", icon: "review" },
  { key: "loop", label: "Evolution Loop", sub: "Feedback, reflection, and policy deployment", icon: "loop" },
  { key: "insights", label: "Memory & Experiments", sub: "Five memory layers and canary observation", icon: "brain" },
  { key: "agent", label: "Agent Network", sub: "Department execution units and elasticity", icon: "agent" },
];

export default function AdminDashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sideOpen, setSideOpen] = useState(false);
  const isSuper = !user.dept_id;

  const refresh = useCallback(async () => {
    try { setData(await dashboard()); setError(""); }
    catch (e) { setError(String(e instanceof Error ? e.message : e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const current = TABS.find(t => t.key === tab)!;

  return <div className={styles.wrap}>
    <aside className={`${styles.sidebar} ${sideOpen ? styles.sidebarMobileOpen : ""}`}>
      <div className={styles.brand}><span className={styles.brandSeal}>C</span><span><b>Clausewise</b><small>CLAUSEWISE CONTROL</small></span></div>
      <div className={styles.scopeCard}><span className={styles.scopeIcon}><Icon name={isSuper ? "shield" : "building"} size={17}/></span><span><b>{isSuper ? "Super Admin Workspace" : "Department Governance Workspace"}</b><small>{isSuper ? "Global policy and fact control plane" : `${user.dept_id} · Data strictly isolated`}</small></span></div>
      <nav className={styles.nav}>{TABS.map(t => <button key={t.key} className={`${styles.navItem} ${tab === t.key ? styles.navActive : ""}`} onClick={() => {setTab(t.key);setSideOpen(false)}}>
        <span className={styles.navIcon}><Icon name={t.icon} size={18}/></span><span><b>{t.label}</b><small>{t.sub}</small></span>
        {t.key === "review" && (data?.pending_review_count || 0) > 0 && <em>{data!.pending_review_count}</em>}
      </button>)}</nav>
      <div className={styles.sidebarFoot}><div className={styles.live}><span/> CONTROL PLANE ONLINE</div><button onClick={onLogout}><Icon name="logout" size={16}/>Sign out</button></div>
    </aside>
    {sideOpen && <button className={styles.backdrop} onClick={() => setSideOpen(false)} aria-label="Close menu"/>}
    <section className={styles.workspace}>
      <header className={styles.header}>
        <button className={styles.mobileMenu} onClick={() => setSideOpen(true)}><Icon name="menu"/></button>
        <div><div className={styles.breadcrumb}>Console / {isSuper ? "Global" : user.dept_id}</div><h1>{current.label}</h1><p>{current.sub}</p></div>
        <div className={styles.headerRight}><button className={styles.refreshBtn} onClick={refresh}><Icon name="refresh" size={16}/>Refresh</button><div className={styles.avatar}>{user.name.slice(0,1)}</div><div className={styles.userInfo}><b>{user.name}</b><small>{isSuper ? "Super Admin" : "Department Admin"}</small></div></div>
      </header>
      <main className={styles.body}>
        {error && <div className={styles.errorBanner}><Icon name="shield" size={17}/>{error}</div>}
        {loading || !data ? <div className={styles.loading}><span/><b>Syncing the control plane</b><small>Reading facts, memory, and policy state</small></div> : <>
          {tab === "overview" && <OverviewPanel data={data} refresh={refresh}/>}
          {tab === "dept" && <DeptPanel data={data} refresh={refresh} user={user}/>}
          {tab === "review" && <ReviewPanel data={data} refresh={refresh}/>}
          {tab === "loop" && <LoopPanel data={data} refresh={refresh} user={user}/>}
          {tab === "insights" && <InsightsPanel user={user}/>}
          {tab === "agent" && <AgentPanel data={data}/>}
        </>}
      </main>
    </section>
  </div>;
}
