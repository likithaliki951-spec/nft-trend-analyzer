"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  RefreshCw,
  Clock,
  User,
  Shield,
  Database,
  Download,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

export default function AdminActivityPage() {
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchActivity = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAdminActivity(100);
      setActivities(res || []);
    } catch (err: any) {
      setError(err.message || "Failed to load audit activity history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivity();
  }, []);

  const getActionBadge = (action: string) => {
    if (action.includes("admin_approved")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Admin Approved
        </span>
      );
    }
    if (action.includes("admin_rejected")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
          Admin Rejected
        </span>
      );
    }
    if (action.includes("admin_registered")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          Admin Request
        </span>
      );
    }
    if (action.includes("user_registered")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-500/10 text-violet-400 border border-violet-500/20">
          User Registered
        </span>
      );
    }
    if (action.includes("login")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
          Authentication
        </span>
      );
    }
    if (action.includes("dataset")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/20">
          Dataset Ingested
        </span>
      );
    }
    if (action.includes("report")) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
          Report Export
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
        {action}
      </span>
    );
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Activity Monitoring</h1>
          <p className="text-xs text-slate-400 mt-1">
            Immutable audit logging of platform events, registrations, logins, datasets, and approvals
          </p>
        </div>

        <button
          onClick={fetchActivity}
          disabled={loading}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl border border-slate-700 transition-colors disabled:opacity-50 self-start md:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-amber-400" : ""}`} />
          <span>Refresh Audit Logs</span>
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Activity Log Table */}
      <div className="rounded-xl border border-slate-800 bg-[#0d1322] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d18] text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3.5 font-semibold">Timestamp</th>
                <th className="px-5 py-3.5 font-semibold">Event Type</th>
                <th className="px-5 py-3.5 font-semibold">User Identity</th>
                <th className="px-5 py-3.5 font-semibold">Details &amp; Metadata</th>
                <th className="px-5 py-3.5 font-semibold">Client IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin text-amber-400 mx-auto mb-2" />
                    <span>Loading audit activity history...</span>
                  </td>
                </tr>
              ) : activities.length > 0 ? (
                activities.map((act) => (
                  <tr key={act.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                      {act.created_at ? new Date(act.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">{getActionBadge(act.action)}</td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-slate-200 text-[11px]">
                        {act.user_email || "System"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-300">
                      {act.details && Object.keys(act.details).length > 0 ? (
                        <span className="font-mono text-[11px] text-slate-400 bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
                          {JSON.stringify(act.details)}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 font-mono text-[11px]">
                      {act.ip_address || "127.0.0.1"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-slate-500">
                    No platform audit activity recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
