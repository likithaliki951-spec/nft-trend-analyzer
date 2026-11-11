"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  ShieldAlert,
  Users,
  CheckCircle2,
  Activity,
  LogOut,
  Shield,
  Layers,
  ArrowRight,
  LayoutDashboard,
} from "lucide-react";

export function AdminSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const navItems = [
    {
      title: "Overview",
      href: "/admin/dashboard",
      icon: LayoutDashboard,
      badge: "Stats",
    },
    {
      title: "User Management",
      href: "/admin/users",
      icon: Users,
      badge: "Directory",
    },
    {
      title: "Admin Approvals",
      href: "/admin/approvals",
      icon: CheckCircle2,
      badge: "Pending",
    },
    {
      title: "Activity Monitoring",
      href: "/admin/activity",
      icon: Activity,
      badge: "Audit Logs",
    },
  ];

  return (
    <aside className="w-64 bg-[#0a0f1d] border-r border-amber-500/20 flex flex-col justify-between shrink-0">
      <div>
        {/* Admin Brand Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center space-x-3 bg-gradient-to-b from-amber-500/10 to-transparent">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-slate-950 font-bold shadow-lg shadow-amber-500/20">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <h1 className="font-bold text-sm tracking-tight text-white">Admin Console</h1>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono font-semibold border border-amber-500/30">
                PRO
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">RBAC Governance</p>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="p-3">
          <div className="px-3 py-2 text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider">
            Administration
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/admin/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm"
                      : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon className={`h-4 w-4 ${isActive ? "text-amber-400" : "text-slate-400"}`} />
                    <span>{item.title}</span>
                  </div>
                  {item.badge && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border ${
                      isActive
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                        : "bg-slate-800 text-slate-400 border-slate-700"
                    }`}>
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Quick Switch to User Analytics */}
          <div className="px-3 pt-6 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Cross Navigation
          </div>
          <nav className="space-y-1">
            <Link
              href="/user/dashboard"
              className="flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-violet-300 hover:bg-violet-500/10 border border-transparent hover:border-violet-500/20 transition-all"
            >
              <div className="flex items-center space-x-2">
                <Layers className="h-3.5 w-3.5 text-violet-400" />
                <span>View User Analytics</span>
              </div>
              <ArrowRight className="h-3 w-3 text-slate-500" />
            </Link>
          </nav>
        </div>
      </div>

      {/* Admin User Footer Card */}
      <div className="p-4 border-t border-slate-800/80 bg-[#080c16]">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="h-8 w-8 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <ShieldAlert className="h-4 w-4" />
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-white truncate">{user?.name || "Administrator"}</div>
              <div className="text-[10px] text-amber-400/90 truncate capitalize flex items-center gap-1 font-mono">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse"></span>
                Master Admin
              </div>
            </div>
          </div>
          <button
            onClick={() => logout("admin")}
            title="Sign Out of Admin Portal"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
