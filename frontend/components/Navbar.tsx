"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Sparkles, UploadCloud, CheckCircle2, AlertCircle, RefreshCw, Database } from "lucide-react";

export function Navbar({ onDatasetChanged }: { onDatasetChanged?: () => void }) {
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [activeMeta, setActiveMeta] = useState<any>(null);

  const fetchActiveMeta = async () => {
    try {
      const res = await api.getActiveDataset();
      if (res && res.dataset_name) {
        setActiveMeta(res);
      }
    } catch {
      // Ignore if offline
    }
  };

  useEffect(() => {
    fetchActiveMeta();
  }, []);

  const handleLoadDemo = async () => {
    try {
      setLoadingDemo(true);
      const res = await api.loadDemoDataset();
      setStatusMsg(`Demo dataset active (${res.rows} records)`);
      await fetchActiveMeta();
      if (onDatasetChanged) onDatasetChanged();
      setTimeout(() => setStatusMsg(null), 4000);
    } catch (err: any) {
      setStatusMsg("Failed to load demo data");
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-[#0d1322]/80 backdrop-blur-md px-6 flex items-center justify-between z-10">
      <div className="flex items-center space-x-3">
        {activeMeta ? (
          <div className="flex items-center space-x-2 text-xs px-3 py-1.5 rounded-xl bg-violet-500/10 text-violet-300 border border-violet-500/20 font-medium">
            <Database className="h-3.5 w-3.5 text-violet-400" />
            <span className="font-semibold text-white truncate max-w-[200px] md:max-w-[320px]">
              {activeMeta.dataset_name}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              ({activeMeta.rows_count?.toLocaleString()} rows)
            </span>
          </div>
        ) : (
          <span className="text-xs px-2.5 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 font-medium">
            Workspace Session Active
          </span>
        )}

        {statusMsg && (
          <span className="text-xs text-emerald-400 flex items-center gap-1.5 animate-fade-in font-medium">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {statusMsg}
          </span>
        )}
      </div>

      <div className="flex items-center space-x-3">
        <button
          onClick={handleLoadDemo}
          disabled={loadingDemo}
          className="flex items-center space-x-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition-colors disabled:opacity-50"
        >
          {loadingDemo ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin text-sky-400" />
          ) : (
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />
          )}
          <span>{loadingDemo ? "Loading Demo..." : "Load Demo Dataset"}</span>
        </button>

        <Link
          href="/dashboard/workspace"
          className="flex items-center space-x-1.5 text-xs bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white px-3.5 py-1.5 rounded-lg font-medium shadow-sm transition-all"
        >
          <UploadCloud className="h-3.5 w-3.5" />
          <span>Upload Dataset</span>
        </Link>
      </div>
    </header>
  );
}
