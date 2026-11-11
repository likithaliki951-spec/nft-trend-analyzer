"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  Users,
  Shield,
  Clock,
  ShieldAlert,
  Activity,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  TrendingUp,
  UserCheck,
  UserX,
} from "lucide-react";

export default function AdminOverviewDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAdminDashboardStats();
      setStats(res);
    } catch (err: any) {
      setError(err.message || "Failed to load administrator statistics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center space-x-2 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-1.5 font-mono">
            <span>Privileged Governance</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Platform Overview</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time authoritative telemetry, user registrations, and RBAC governance metrics
          </p>
        </div>

        <button
          onClick={fetchStats}
          disabled={loading}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl border border-slate-700 transition-colors disabled:opacity-50 self-start md:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-amber-400" : ""}`} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2.5">
          <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 6 Key Telemetry Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Total Users */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Total Users
            </span>
            <Users className="h-4 w-4 text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : (stats?.total_registered_users ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">All registered accounts</div>
        </div>

        {/* Active Regular Users */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Active Users
            </span>
            <UserCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {loading ? "..." : (stats?.active_users ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Authorized regular users</div>
        </div>

        {/* Pending Users */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Pending Users
            </span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">
            {loading ? "..." : (stats?.pending_users ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Awaiting verification</div>
        </div>

        {/* Suspended Users */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Suspended
            </span>
            <UserX className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">
            {loading ? "..." : (stats?.suspended_users ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Access revoked</div>
        </div>

        {/* Approved Admins */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">
              Approved Admins
            </span>
            <Shield className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-300">
            {loading ? "..." : (stats?.approved_administrators ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Active administrators</div>
        </div>

        {/* Pending Admin Requests */}
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Admin Requests
            </span>
            <ShieldAlert className="h-4 w-4 text-orange-400" />
          </div>
          <div className="text-2xl font-bold text-orange-400">
            {loading ? "..." : (stats?.pending_admin_requests ?? 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Pending approval</div>
        </div>
      </div>

      {/* Quick Action Navigation Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/admin/approvals"
          className="p-5 rounded-xl border border-slate-800 bg-[#0d1322] hover:border-amber-500/40 hover:bg-amber-500/5 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="h-9 w-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              {stats?.pending_admin_requests > 0 && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
                  {stats.pending_admin_requests} Awaiting
                </span>
              )}
            </div>
            <h3 className="text-sm font-bold text-white group-hover:text-amber-300 transition-colors">
              Review Admin Requests
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Review, approve, or reject Gmail administrator registration requests.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-amber-400/90 font-medium">
            <span>Manage Approvals</span>
            <ArrowRight className="h-3.5 w-3.5 transform group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/admin/users"
          className="p-5 rounded-xl border border-slate-800 bg-[#0d1322] hover:border-sky-500/40 hover:bg-sky-500/5 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="h-9 w-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                <Users className="h-4 w-4" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Directory
              </span>
            </div>
            <h3 className="text-sm font-bold text-white group-hover:text-sky-300 transition-colors">
              User Directory &amp; RBAC
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Search accounts, filter statuses, and activate or suspend platform members.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-sky-400/90 font-medium">
            <span>Manage Users</span>
            <ArrowRight className="h-3.5 w-3.5 transform group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/admin/activity"
          className="p-5 rounded-xl border border-slate-800 bg-[#0d1322] hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <Activity className="h-4 w-4" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Audit Trail
              </span>
            </div>
            <h3 className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors">
              Activity Monitoring
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Inspect immutable audit records of logins, registrations, dataset uploads, and approvals.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-emerald-400/90 font-medium">
            <span>View Audit Logs</span>
            <ArrowRight className="h-3.5 w-3.5 transform group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>
      </div>

      {/* Recent User Registrations Feed */}
      <div className="rounded-xl border border-slate-800 bg-[#0d1322] overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Users className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-bold text-white">Recent Account Registrations</h2>
          </div>
          <Link
            href="/admin/users"
            className="text-xs text-amber-400/90 hover:text-amber-300 transition-colors"
          >
            View all accounts &rarr;
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d18] text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3 font-semibold">User</th>
                <th className="px-5 py-3 font-semibold">Role</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Email Verified</th>
                <th className="px-5 py-3 font-semibold">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-slate-400">
                    <RefreshCw className="h-4 w-4 animate-spin text-amber-400 mx-auto mb-2" />
                    <span>Loading recent accounts...</span>
                  </td>
                </tr>
              ) : stats?.recent_registrations?.length > 0 ? (
                stats.recent_registrations.map((u: any) => (
                  <tr key={u.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-white">{u.name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{u.email}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                        u.role === "admin"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-slate-800 text-slate-300 border border-slate-700"
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        u.account_status === "active"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : u.account_status === "pending"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      }`}>
                        {u.account_status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      {u.email_verified ? (
                        <span className="text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                        </span>
                      ) : (
                        <span className="text-slate-500">Unverified</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 font-mono text-[11px]">
                      {u.created_at ? new Date(u.created_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-slate-500">
                    No registered accounts found.
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
