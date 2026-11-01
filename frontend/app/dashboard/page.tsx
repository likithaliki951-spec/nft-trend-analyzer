"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import {
  TrendingUp,
  BarChart3,
  MessageSquare,
  Store,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  Sparkles,
  Download,
} from "lucide-react";
import { ExportModal } from "@/components/ExportModal";

export default function DashboardOverviewPage() {
  const { user } = useAuth();
  const [marketStats, setMarketStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExportOpen, setIsExportOpen] = useState(false);

  useEffect(() => {
    api
      .getMarketOverview()
      .then((res) => {
        setMarketStats(res.kpis);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const sections = [
    {
      num: "Section 1",
      title: "Price Trends & Prediction",
      desc: "Chronological time-series, PCA decomposition (60 components), regression benchmarking (RF, Gradient Boosting, Ridge, Linear).",
      href: "/dashboard/price-trends",
      icon: TrendingUp,
      tag: "Time-Series + ML + PCA",
      color: "border-violet-500/30 bg-violet-500/5 hover:border-violet-500/60",
    },
    {
      num: "Section 2",
      title: "Market Activity",
      desc: "Macro volume KPIs, unique asset distribution, and valuation categorization (Logistic Regression, Random Forest, SVM).",
      href: "/dashboard/market-activity",
      icon: BarChart3,
      tag: "KPIs + Classification",
      color: "border-sky-500/30 bg-sky-500/5 hover:border-sky-500/60",
    },
    {
      num: "Section 3",
      title: "Social Engagement",
      desc: "Discord and Twitter/X sentiment signals, volume correlations, and cross-metric correlation matrix heatmap.",
      href: "/dashboard/social-engagement",
      icon: MessageSquare,
      tag: "Correlations + Heatmap",
      color: "border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/60",
    },
    {
      num: "Section 4",
      title: "Marketplace Hub",
      desc: "Live CoinGecko Ethereum spot rates, OpenSea verified floor statistics, and real-time ETH-to-USD currency calculator.",
      href: "/dashboard/marketplace-hub",
      icon: Store,
      tag: "Live APIs + Converter",
      color: "border-amber-500/30 bg-amber-500/5 hover:border-amber-500/60",
    },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Welcome Banner */}
      <div className="p-6 md:p-8 rounded-2xl bg-gradient-to-r from-[#11192e] via-[#0d1322] to-[#121829] border border-slate-800 shadow-xl relative overflow-hidden">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 mb-2">
              <span>Terminal Ready</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Welcome back, {user?.name || "Analyst"}
            </h1>
            <p className="text-xs text-slate-400 max-w-xl mt-1">
              Select one of the four consolidated dashboard sections below or access your persistent workspace to continue research.
            </p>
          </div>
          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={() => setIsExportOpen(true)}
              className="text-xs bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white px-4 py-2.5 rounded-xl font-medium flex items-center space-x-1.5 shadow-md shadow-violet-500/20 transition-all"
            >
              <Download className="h-4 w-4" />
              <span>Export Report</span>
            </button>
            <Link
              href="/dashboard/workspace"
              className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2.5 rounded-xl border border-slate-700 transition-colors font-medium flex items-center space-x-1.5"
            >
              <Database className="h-4 w-4 text-sky-400" />
              <span>Saved Projects</span>
            </Link>
          </div>
        </div>
      </div>

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
      />

      {/* KPI Cards Preview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">Total Sales</div>
          <div className="text-xl font-bold text-white">
            {isLoading ? "..." : (marketStats?.total_sales?.toLocaleString() || "120")}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Observed transactions</div>
        </div>
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">Total Volume (ETH)</div>
          <div className="text-xl font-bold text-sky-400">
            {isLoading ? "..." : `${marketStats?.total_volume_eth?.toFixed(2) || "3,587.15"} ETH`}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Aggregate traded volume</div>
        </div>
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">Average Price</div>
          <div className="text-xl font-bold text-violet-400">
            {isLoading ? "..." : `${marketStats?.average_price_eth?.toFixed(3) || "1.355"} ETH`}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Mean floor transaction</div>
        </div>
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">Collections</div>
          <div className="text-xl font-bold text-emerald-400">
            {isLoading ? "..." : (marketStats?.unique_collections || "2")}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Indexed smart contracts</div>
        </div>
      </div>

      {/* 4 Main Sections Hub */}
      <div>
        <h2 className="text-sm font-semibold text-white tracking-tight mb-4 flex items-center space-x-2">
          <Layers className="h-4 w-4 text-violet-400" />
          <span>Core Analytical Sections</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sections.map((sec) => {
            const Icon = sec.icon;
            return (
              <Link
                key={sec.href}
                href={sec.href}
                className={`p-5 rounded-xl border bg-[#0d1322] transition-all flex flex-col justify-between group ${sec.color}`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="h-9 w-9 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-white">
                      <Icon className="h-4 w-4 text-violet-400" />
                    </div>
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      {sec.tag}
                    </span>
                  </div>
                  <div className="text-[10px] font-semibold text-violet-400 uppercase tracking-wider mb-0.5">
                    {sec.num}
                  </div>
                  <h3 className="text-base font-bold text-white group-hover:text-violet-300 transition-colors">
                    {sec.title}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{sec.desc}</p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-300 font-medium">
                  <span>Open Section</span>
                  <ArrowRight className="h-3.5 w-3.5 transform group-hover:translate-x-1 transition-transform text-violet-400" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
