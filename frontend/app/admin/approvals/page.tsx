"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Shield,
  Clock,
  Mail,
  UserCheck,
  UserX,
  HelpCircle,
} from "lucide-react";

export default function AdminApprovalsPage() {
  const [requests, setRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAdminApprovals();
      setRequests(res || []);
    } catch (err: any) {
      setError(err.message || "Failed to load pending administrator approvals.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (reqId: string, emailVerified: boolean) => {
    if (!emailVerified) {
      setError("Cannot approve administrator request: applicant's email address has not been verified.");
      return;
    }

    try {
      setActionLoading(reqId);
      setError(null);
      setFeedback(null);
      const res = await api.approveAdminRequest(reqId);
      setFeedback(res.message || "Administrator application approved successfully.");
      await fetchApprovals();
      setTimeout(() => setFeedback(null), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to approve administrator request.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (reqId: string) => {
    try {
      setActionLoading(reqId);
      setError(null);
      setFeedback(null);
      const res = await api.rejectAdminRequest(reqId);
      setFeedback(res.message || "Administrator application rejected.");
      await fetchApprovals();
      setTimeout(() => setFeedback(null), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to reject administrator request.");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center space-x-2 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-1.5 font-mono">
            <span>Privileged Authorization Workflow</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Administrator Approvals</h1>
          <p className="text-xs text-slate-400 mt-1">
            Review subsequent administrator requests submitted via verified Gmail addresses
          </p>
        </div>

        <button
          onClick={fetchApprovals}
          disabled={loading}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl border border-slate-700 transition-colors disabled:opacity-50 self-start md:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-amber-400" : ""}`} />
          <span>Refresh Queue</span>
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

      {/* Security Guidance Alert */}
      <div className="p-4 rounded-xl bg-[#0a0f1d] border border-amber-500/20 text-xs space-y-1.5">
        <div className="flex items-center space-x-2 text-amber-400 font-semibold">
          <Shield className="h-4 w-4" />
          <span>RBAC Approval Policy (Option B)</span>
        </div>
        <p className="text-slate-400 text-[11px] leading-relaxed">
          Subsequent administrators submit requests with a valid Gmail address. They receive status:{" "}
          <span className="font-mono text-amber-400 font-semibold">PENDING</span> and cannot access admin APIs or the admin dashboard. Requests can only be approved after email verification is confirmed.
        </p>
      </div>

      {/* Approvals Table */}
      <div className="rounded-xl border border-slate-800 bg-[#0d1322] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d18] text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-5 py-3.5 font-semibold">Applicant</th>
                <th className="px-5 py-3.5 font-semibold">Gmail Address</th>
                <th className="px-5 py-3.5 font-semibold">Email Verification</th>
                <th className="px-5 py-3.5 font-semibold">Requested Date</th>
                <th className="px-5 py-3.5 font-semibold text-right">Decisions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin text-amber-400 mx-auto mb-2" />
                    <span>Loading pending administrator requests...</span>
                  </td>
                </tr>
              ) : requests.length > 0 ? (
                requests.map((r) => {
                  const isCurrentAction = actionLoading === r.id;
                  const isVerified = Boolean(r.email_verified);

                  return (
                    <tr key={r.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-5 py-4 font-semibold text-white">
                        {r.name || "Administrator Applicant"}
                      </td>
                      <td className="px-5 py-4 font-mono text-[11px] text-amber-300">
                        {r.email}
                      </td>
                      <td className="px-5 py-4">
                        {isVerified ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 inline-flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3" /> Verified
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" /> Pending Verification
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-slate-400 font-mono text-[11px]">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handleApprove(r.id, isVerified)}
                            disabled={isCurrentAction || !isVerified}
                            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-[11px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center space-x-1 shadow-sm"
                            title={
                              isVerified
                                ? "Approve this administrator account"
                                : "Unverified applicant cannot be approved"
                            }
                          >
                            <UserCheck className="h-3.5 w-3.5" />
                            <span>{isCurrentAction ? "..." : "Approve"}</span>
                          </button>
                          <button
                            onClick={() => handleReject(r.id)}
                            disabled={isCurrentAction}
                            className="px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/30 font-medium text-[11px] transition-colors disabled:opacity-50 flex items-center space-x-1"
                            title="Reject this administrator application"
                          >
                            <UserX className="h-3.5 w-3.5" />
                            <span>Reject</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-slate-500">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500 mx-auto mb-2" />
                    <span>No pending administrator requests in queue.</span>
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
