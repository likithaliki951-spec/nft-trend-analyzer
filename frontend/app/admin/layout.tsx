"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AdminSidebar } from "@/components/AdminSidebar";
import { ShieldAlert, Clock, LogOut, Lock, ArrowLeft } from "lucide-react";
import Link from "next/link";

const AUTH_PAGES = ["/admin/login", "/admin/register", "/admin/setup"];

export default function AdminPortalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  const isAuthPage = AUTH_PAGES.some((p) => pathname === p || pathname.startsWith(p + "/"));

  useEffect(() => {
    if (!isLoading && !isAuthPage) {
      if (!user) {
        router.push("/admin/login");
      }
    }
  }, [user, isLoading, isAuthPage, router]);

  // If on login/register/setup page, render full-bleed without admin sidebar
  if (isAuthPage) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <div className="h-8 w-8 rounded-full border-2 border-amber-500 border-t-transparent animate-spin"></div>
          <span className="text-xs text-slate-400">Verifying administrator credentials...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // RBAC Access Control: Regular users cannot access administrator pages
  if (user.role !== "admin") {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center p-6 text-center">
        <div className="max-w-md bg-[#0d1322] border border-amber-500/30 rounded-2xl p-8 shadow-2xl space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto">
            <Lock className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Access Denied</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Administrator privileges are required to access this portal. Your account is currently authenticated with role:{" "}
            <span className="font-mono text-amber-400 uppercase font-semibold">{user.role}</span>.
          </p>
          <div className="pt-2 flex justify-center gap-3">
            <Link
              href="/user/dashboard"
              className="inline-flex items-center space-x-2 text-xs bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-xl transition-colors shadow-md shadow-violet-500/20"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Go to User Dashboard</span>
            </Link>
            <button
              onClick={() => logout("admin")}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl border border-slate-700 transition-colors"
            >
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Account Suspended Screen
  if (user.account_status === "suspended") {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center p-6 text-center">
        <div className="max-w-md bg-[#0d1322] border border-rose-500/30 rounded-2xl p-8 shadow-2xl space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center mx-auto">
            <ShieldAlert className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Administrator Account Suspended</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Your administrator privileges have been suspended. Access to management consoles, approvals, and telemetry is disabled.
          </p>
          <div className="pt-2">
            <button
              onClick={() => logout("admin")}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Account Pending Screen
  if (user.account_status === "pending") {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center p-6 text-center">
        <div className="max-w-md bg-[#0d1322] border border-amber-500/30 rounded-2xl p-8 shadow-2xl space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto">
            <Clock className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Administrator Approval Pending</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Your administrator application is currently pending review by an active platform administrator. Administrative capabilities are disabled until formal approval is granted.
          </p>
          <div className="pt-2">
            <button
              onClick={() => logout("admin")}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#070b14] overflow-hidden">
      <AdminSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Admin Portal Header */}
        <header className="h-16 border-b border-slate-800 bg-[#0a0f1d]/90 backdrop-blur-md px-8 flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse"></span>
              <span>Administrator Command Center</span>
            </div>
            <span className="text-xs text-slate-400 hidden sm:inline">
              Authoritative RBAC &amp; Platform Monitoring
            </span>
          </div>

          <div className="flex items-center space-x-3">
            <Link
              href="/user/dashboard"
              className="text-xs text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 transition-colors"
            >
              Open User View
            </Link>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
