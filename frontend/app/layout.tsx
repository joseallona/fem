import type { Metadata } from "next";
import Link from "next/link";
import { Settings } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "FEM — Forecasting Engine Monitor",
  description: "Strategic foresight intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <div className="flex min-h-screen flex-col">
          <header className="border-b bg-white px-6 py-3 flex items-center gap-4">
            <span className="font-bold text-primary text-lg tracking-tight">FEM</span>
            <span className="text-muted-foreground text-sm">Forecasting Engine Monitor</span>
            <div className="ml-auto">
              <Link href="/settings" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <Settings className="h-4 w-4" /> Settings
              </Link>
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
