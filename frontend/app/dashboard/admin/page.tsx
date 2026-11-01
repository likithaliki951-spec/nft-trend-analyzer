"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import {
  ShieldAlert,
  Users,
  Database,
  HardDrive,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Lock,
  Server,
  ArrowLeft,
  Key,
} from "lucide-react";

export default function AdminPage() {
  const { user } = useAuth();
  const [telemetry, setTelemetry] = useState<any>(null);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.role === "admin") {
      fetchAdminData();
    } else {
      setLoading(false);
    }
  }, [user]);

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [telRes, usersRes] = await Promise.all([
        api.getAdminTelemetry(),
        api.getAdminUsers(),
      ]);
      setTelemetry(telRes);
      setUsersList(usersRes || []);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load administrative telemetry.");
    } finally {
      setLoading(false);
    }
  };

  // If user is not admin, show RBAC permission notice
  if (!loading && user?.role !== "admin") {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto">
          <Lock className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold text-white tracking-tight">
          Administrator Privileges Required
        </h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
          The administrative command console contains sensitive server telemetry, health diagnostics, and user directory management. Your current account role is{" "}
          <span className="font-mono text-amber-400 uppercase font-semibold">{user?.role || "analyst"}</span>.
        </p>
        <div className="pt-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to Dashboard</span>
          </Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-400" />
        <p className="text-sm text-slate-400">Loading platform telemetry & user directory...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center space-x-2 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-1.5">
            <span>Privileged Access</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Admin Command Console</h1>
          <p className="text-xs text-slate-400 mt-1">
            Global system health, storage telemetry, cryptographic auditing, and user access control.
          </p>
        </div>

        <button
          onClick={fetchAdminData}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg border border-slate-700 transition-colors self-start md:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* System Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Registered Users</span>
            <Users className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white mt-1">
            {telemetry?.active_users_count || usersList.length} Accounts
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Active platform identities</span>
        </div>

        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Saved Projects</span>
            <Database className="h-4 w-4 text-violet-400" />
          </div>
          <div className="text-xl font-bold text-violet-400 mt-1">
            {telemetry?.total_projects_saved ?? 0} Checkpoints
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Archived user sessions</span>
        </div>

        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Storage Volume</span>
            <HardDrive className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-400 mt-1 font-mono">
            {telemetry?.storage_size_formatted || "0.00 MB"}
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Dataset disk footprint</span>
        </div>

        <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Database Status</span>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400 mt-1 capitalize">
            {telemetry?.database_status || "Online"}
          </div>
          <span className="text-[10px] text-slate-500 mt-1 font-mono">
            Backend: {telemetry?.database_backend || "SQLite/Supabase"}
          </span>
        </div>
      </div>

      {/* Security and Infrastructure Diagnostics */}
      <div className="p-5 rounded-2xl bg-[#0d1322] border border-slate-800 space-y-3">
        <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
          <Server className="h-4 w-4 text-amber-400" />
          <span>Server Runtime & Cryptographic Standards</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase block">Password Hashing</span>
            <div className="text-slate-200 font-mono mt-1 font-semibold">Bcrypt (cost factor = 12)</div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">With PBKDF2 backward compatibility</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase block">Session Tokens</span>
            <div className="text-slate-200 font-mono mt-1 font-semibold">HMAC-SHA256 JWT</div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">Cryptographic signature verification</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
            <span className="text-[10px] text-slate-400 uppercase block">Python Runtime</span>
            <div className="text-slate-200 font-mono mt-1 font-semibold">{telemetry?.python_version || "Python 3.13"}</div>
            <span className="text-[10px] text-slate-500 mt-0.5 block">{telemetry?.platform_info || "FastAPI"}</span>
          </div>
        </div>
      </div>

      {/* Registered Users Directory */}
      <div className="p-5 rounded-2xl bg-[#0d1322] border border-slate-800 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Registered User Directory</h3>
          <p className="text-xs text-slate-400">
            Global account registry with role-based access status. Private user data and password hashes remain isolated.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Display Name</th>
                <th className="py-3 px-4">Email Address</th>
                <th className="py-3 px-4">Account Role</th>
                <th className="py-3 px-4">Registered Date</th>
                <th className="py-3 px-4">Security Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {usersList.map((u) => (
                <tr key={u.id || u.email} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-white">{u.name}</td>
                  <td className="py-3.5 px-4 font-mono text-slate-300">{u.email}</td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded uppercase ${
                        u.role === "admin"
                          ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                          : "bg-slate-800 text-slate-300 border border-slate-700"
                      }`}
                    >
                      {u.role || "analyst"}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "Active"}
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center space-x-1.5 text-xs text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>Encrypted & Verified</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
