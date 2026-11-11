"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Users,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  UserCheck,
  UserX,
  Shield,
  Clock,
} from "lucide-react";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAdminUsers({
        status: statusFilter || undefined,
        role: roleFilter || undefined,
        search: search || undefined,
      });
      setUsers(res || []);
    } catch (err: any) {
      setError(err.message || "Failed to load user directory.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [statusFilter, roleFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchUsers();
  };

  const handleStatusChange = async (userId: string, newStatus: "active" | "suspended") => {
    try {
      setActionLoading(userId);
      setFeedback(null);
      const res = await api.updateUserStatus(userId, newStatus);
      setFeedback(res.message || `Account status updated to ${newStatus}.`);
      await fetchUsers();
      setTimeout(() => setFeedback(null), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to update account status.");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">User Directory &amp; RBAC</h1>
          <p className="text-xs text-slate-400 mt-1">
            Search registered accounts, filter governance status, and activate or suspend platform members
          </p>
        </div>

        <button
          onClick={fetchUsers}
          disabled={loading}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl border border-slate-700 transition-colors disabled:opacity-50 self-start md:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-amber-400" : ""}`} />
          <span>Refresh Directory</span>
        </button>
      </div>

      {feedback && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center space-x-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Search and Filters Toolbar */}
      <div className="p-4 rounded-xl bg-[#0d1322] border border-slate-800 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-1 relative">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search accounts by name or email address..."
            className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-colors"
          />
        </form>

        <div className="flex items-center gap-3">
          <div className="flex items-center space-x-1.5 text-xs text-slate-400">
            <Filter className="h-3.5 w-3.5" />
            <span>Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#080c16] border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition-colors"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="suspended">Suspended</option>
            <option value="rejected">Rejected</option>
          </select>

          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="bg-[#080c16] border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition-colors"
          >
            <option value="">All Roles</option>
            <option value="user">Regular User</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="rounded-xl border border-slate-800 bg-[#0d1322] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d18] text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3.5 font-semibold">User</th>
                <th className="px-5 py-3.5 font-semibold">Role</th>
                <th className="px-5 py-3.5 font-semibold">Account Status</th>
                <th className="px-5 py-3.5 font-semibold">Verification</th>
                <th className="px-5 py-3.5 font-semibold">Registered</th>
                <th className="px-5 py-3.5 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin text-amber-400 mx-auto mb-2" />
                    <span>Loading directory accounts...</span>
                  </td>
                </tr>
              ) : users.length > 0 ? (
                users.map((u) => {
                  const isCurrentAction = actionLoading === u.id;
                  const isActive = u.account_status === "active";
                  const isSuspended = u.account_status === "suspended";

                  return (
                    <tr key={u.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-white">{u.name}</div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">{u.email}</div>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                          u.role === "admin"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-slate-800 text-slate-300 border border-slate-700"
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                          u.account_status === "active"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : u.account_status === "pending"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : u.account_status === "suspended"
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-slate-800 text-slate-400 border border-slate-700"
                        }`}>
                          {u.account_status}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        {u.email_verified ? (
                          <span className="text-emerald-400 flex items-center gap-1 font-medium">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                          </span>
                        ) : (
                          <span className="text-slate-500 flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" /> Unverified
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-slate-400 font-mono text-[11px]">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          {isActive ? (
                            <button
                              onClick={() => handleStatusChange(u.id, "suspended")}
                              disabled={isCurrentAction}
                              className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[11px] font-medium transition-colors disabled:opacity-50"
                              title="Suspend this user account"
                            >
                              {isCurrentAction ? "..." : "Suspend"}
                            </button>
                          ) : isSuspended ? (
                            <button
                              onClick={() => handleStatusChange(u.id, "active")}
                              disabled={isCurrentAction}
                              className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[11px] font-medium transition-colors disabled:opacity-50"
                              title="Re-activate this user account"
                            >
                              {isCurrentAction ? "..." : "Activate"}
                            </button>
                          ) : (
                            <span className="text-[11px] text-slate-500">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-slate-500">
                    No matching accounts found.
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
