import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clausewise · Cross-Department Document Processing and Q&A Assistant",
  description: "An intelligent processing and Q&A system for official policy documents across school departments",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
