"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  TrendingUp,
  BarChart3,
  MessageSquare,
  Store,
  FolderArchive,
  ShieldAlert,
  LogOut,
  User as UserIcon,
  Layers,
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const navItems = [
    {
      title: "1. Price Trends & Prediction",
      href: "/dashboard/price-trends",
      icon: TrendingUp,
      badge: "PCA + Models",
    },
    {
      title: "2. Market Activity",
      href: "/dashboard/market-activity",
      icon: BarChart3,
      badge: "Overview & Tiers",
    },
    {
      title: "3. Social Engagement",
      href: "/dashboard/social-engagement",
      icon: MessageSquare,
      badge: "Signals",
    },
    {
      title: "4. Marketplace Hub",
      href: "/dashboard/marketplace-hub",
      icon: Store,
      badge: "Live API",
    },
  ];

  return (
    <aside className="w-64 bg-[#0d1322] border-r border-slate-800 flex flex-col justify-between shrink-0">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-violet-600 to-sky-500 flex items-center justify-center text-white shadow-lg shadow-violet-500/20">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-tight text-white">NFT Trend Analyzer</h1>
            <p className="text-[11px] text-slate-400 font-mono">Analytics Platform</p>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="p-3">
          <div className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Consolidated Sections
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-violet-600/15 text-violet-300 border border-violet-500/30 shadow-sm"
                      : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon className={`h-4 w-4 ${isActive ? "text-violet-400" : "text-slate-400"}`} />
                    <span>{item.title}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Workspace Management */}
          <div className="px-3 pt-6 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Workspace
          </div>
          <nav className="space-y-1">
            <Link
              href="/dashboard/workspace"
              className={`flex items-center space-x-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                pathname === "/dashboard/workspace"
                  ? "bg-sky-500/15 text-sky-300 border border-sky-500/30"
                  : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
              }`}
            >
              <FolderArchive className="h-4 w-4 text-sky-400" />
              <span>Saved Projects & Datasets</span>
            </Link>

            {user?.role === "admin" && (
              <Link
                href="/dashboard/admin"
                className={`flex items-center space-x-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  pathname === "/dashboard/admin"
                    ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                    : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                }`}
              >
                <ShieldAlert className="h-4 w-4 text-amber-400" />
                <span>Admin Command Console</span>
              </Link>
            )}
          </nav>
        </div>
      </div>

      {/* User Footer Card */}
      <div className="p-4 border-t border-slate-800 bg-[#090d18]">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
              <UserIcon className="h-4 w-4 text-violet-400" />
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-white truncate">{user?.name || "Analyst"}</div>
              <div className="text-[10px] text-slate-400 truncate capitalize flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                {user?.role || "analyst"}
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            title="Sign Out"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
