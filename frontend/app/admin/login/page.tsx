"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Lock, Mail, ArrowRight, Shield, AlertCircle, RefreshCw, Key, Layers } from "lucide-react";

export default function AdminLoginPage() {
  const { adminLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await adminLogin(email, password);
    } catch (err: any) {
      setError(err.message || "Invalid administrator credentials or access denied.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
      {/* Top Header */}
      <header className="flex items-center justify-between max-w-6xl mx-auto w-full py-2">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-slate-950 font-bold text-sm shadow-lg shadow-amber-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-sm text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
              Admin Portal
            </span>
          </div>
        </Link>

        {/* Clear Switch to User Portal */}
        <Link
          href="/user/login"
          className="flex items-center space-x-1.5 text-xs text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 transition-all"
        >
          <Layers className="h-3.5 w-3.5 text-violet-400" />
          <span>Switch to User Portal</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      {/* Main Admin Login Card */}
      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-md bg-[#0a0f1d] border border-amber-500/30 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          {/* Amber Accent Glow */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600"></div>

          <div className="text-center mb-8">
            <div className="h-12 w-12 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto mb-3">
              <Shield className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Administrator Console</h1>
            <p className="text-xs text-slate-400 mt-1">
              Privileged access for platform governance, RBAC approvals, and telemetry
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start space-x-2.5 animate-shake">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Administrator Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@gmail.com"
                  required
                  className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-300">Administrator Password</label>
              </div>
              <div className="relative">
                <Lock className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-slate-950 font-bold text-xs shadow-lg shadow-amber-500/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 mt-6"
            >
              {loading ? (
                <RefreshCw className="h-4 w-4 animate-spin text-slate-950" />
              ) : (
                <>
                  <Shield className="h-3.5 w-3.5" />
                  <span>Authenticate as Administrator</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-slate-800 text-center space-y-2">
            <p className="text-xs text-slate-400">
              Need administrator access?{" "}
              <Link
                href="/admin/register"
                className="text-amber-400 hover:text-amber-300 font-semibold transition-colors"
              >
                Submit Admin Registration Request
              </Link>
            </p>
            <p className="text-[11px] text-slate-500">
              First-time setup?{" "}
              <Link
                href="/admin/setup"
                className="text-slate-400 hover:text-amber-300 transition-colors inline-flex items-center gap-1"
              >
                <Key className="h-3 w-3" />
                <span>Initialize Master Administrator</span>
              </Link>
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Restricted Administrator Portal &bull; All Access Logged
      </footer>
    </div>
  );
}
