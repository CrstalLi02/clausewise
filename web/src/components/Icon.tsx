import type { SVGProps } from "react";

export type IconName =
  | "spark" | "chat" | "grid" | "building" | "review" | "loop" | "brain"
  | "agent" | "logout" | "plus" | "menu" | "send" | "copy" | "trash"
  | "check" | "shield" | "file" | "database" | "activity" | "memory"
  | "refresh" | "arrow" | "search" | "upload" | "clock" | "layers";

const paths: Record<IconName, React.ReactNode> = {
  spark: <><path d="M12 3l1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z"/><path d="m18 14 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14Z"/></>,
  chat: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z"/><path d="M8 9h8M8 13h5"/></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  building: <><path d="M3 21h18M6 21V8l6-4 6 4v13"/><path d="M9 12h1M14 12h1M9 16h1M14 16h1"/></>,
  review: <><path d="M9 11l2 2 4-4"/><path d="M18 6V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v2M6 18v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2"/><rect x="3" y="6" width="18" height="12" rx="2"/></>,
  loop: <><path d="M20 7h-9a5 5 0 0 0-5 5v1"/><path d="m17 4 3 3-3 3M4 17h9a5 5 0 0 0 5-5v-1"/><path d="m7 20-3-3 3-3"/></>,
  brain: <><path d="M9.5 4A3.5 3.5 0 0 0 6 7.5v.3A3.5 3.5 0 0 0 4 11v1a3.5 3.5 0 0 0 2 3.2v.3A3.5 3.5 0 0 0 9.5 19H12V4H9.5Z"/><path d="M14.5 4A3.5 3.5 0 0 1 18 7.5v.3a3.5 3.5 0 0 1 2 3.2v1a3.5 3.5 0 0 1-2 3.2v.3a3.5 3.5 0 0 1-3.5 3.5H12V4h2.5ZM8 9h4M12 14h4"/></>,
  agent: <><rect x="4" y="7" width="16" height="13" rx="3"/><path d="M9 12h.01M15 12h.01M9 16h6M12 7V3M9 3h6"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-5"/></>,
  plus: <path d="M12 5v14M5 12h14"/>, menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>,
  trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v5M14 11v5"/></>,
  check: <path d="m5 12 4 4L19 6"/>, shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
  file: <><path d="M6 2h8l4 4v16H6Z"/><path d="M14 2v5h5M9 13h6M9 17h6"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  activity: <path d="M3 12h4l2-7 4 14 2-7h6"/>, memory: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9 7 7M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></>, arrow: <path d="m9 18 6-6-6-6"/>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>, upload: <><path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 20h14"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>, layers: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></>,
};

export default function Icon({ name, size = 18, ...props }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
