"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Lock, Mail, ArrowRight, Shield, AlertCircle, RefreshCw, Layers } from "lucide-react";

export default function UserLoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
      {/* Top Header */}
      <header className="flex items-center justify-between max-w-6xl mx-auto w-full py-2">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-violet-600 to-sky-500 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-violet-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-sm text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
              User Portal
            </span>
          </div>
        </Link>

        {/* Clear Navigation to Admin Portal */}
        <Link
          href="/admin/login"
          className="flex items-center space-x-1.5 text-xs text-amber-400/90 hover:text-amber-300 px-3 py-1.5 rounded-lg border border-amber-500/20 hover:border-amber-500/40 bg-amber-500/5 transition-all"
        >
          <Shield className="h-3.5 w-3.5" />
          <span>Switch to Admin Portal</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      {/* Main Login Card */}
      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-md bg-[#0d1322] border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          {/* Subtle Accent Glow */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-sky-500 to-indigo-500"></div>

          <div className="text-center mb-8">
            <div className="h-12 w-12 rounded-2xl bg-violet-600/10 text-violet-400 border border-violet-500/20 flex items-center justify-center mx-auto mb-3">
              <Layers className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">User Sign In</h1>
            <p className="text-xs text-slate-400 mt-1">
              Access the NFT Trend Analyzer research and analytics terminal
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
                Work Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@nfttrends.io"
                  required
                  className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-300">Password</label>
                <Link
                  href="/user/forgot-password"
                  className="text-[11px] text-violet-400 hover:text-violet-300 transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-violet-500/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 mt-6"
            >
              {loading ? (
                <RefreshCw className="h-4 w-4 animate-spin text-white" />
              ) : (
                <>
                  <span>Sign In to User Dashboard</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-slate-800 text-center space-y-2">
            <p className="text-xs text-slate-400">
              Don&apos;t have an account yet?{" "}
              <Link
                href="/user/register"
                className="text-violet-400 hover:text-violet-300 font-semibold transition-colors"
              >
                Register as a Regular User
              </Link>
            </p>
            <p className="text-[11px] text-slate-500">
              Platform administrator?{" "}
              <Link
                href="/admin/login"
                className="text-amber-400/90 hover:text-amber-300 font-medium transition-colors"
              >
                Sign In to Administrator Console →
              </Link>
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Secure User Portal
      </footer>
    </div>
  );
}
