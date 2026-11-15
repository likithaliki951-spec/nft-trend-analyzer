"use client";

import React, { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Mail, ArrowLeft, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

export default function UserForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await api.forgotPassword(email);
      setMessage(res.message || "If this email address is registered, instructions have been prepared.");
      setSubmitted(true);
    } catch {
      setMessage("If this email address is registered, instructions have been prepared.");
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
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
      </header>

      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-md bg-[#0d1322] border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-sky-500 to-indigo-500"></div>

          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-white tracking-tight">Reset Password</h1>
            <p className="text-xs text-slate-400 mt-1">
              Enter your work email address to receive password reset instructions
            </p>
          </div>

          {submitted ? (
            <div className="space-y-6 text-center">
              <div className="h-12 w-12 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{message}</p>
              <Link
                href="/user/login"
                className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Return to User Sign In</span>
              </Link>
            </div>
          ) : (
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

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-violet-500/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 mt-6"
              >
                {loading ? (
                  <RefreshCw className="h-4 w-4 animate-spin text-white" />
                ) : (
                  <span>Send Reset Link</span>
                )}
              </button>

              <div className="text-center pt-4 space-y-2">
                <div>
                  <Link
                    href="/reset-password"
                    className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
                  >
                    Already have a reset token? Enter it here &rarr;
                  </Link>
                </div>
                <div>
                  <Link
                    href="/user/login"
                    className="inline-flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    <ArrowLeft className="h-3 w-3" />
                    <span>Back to User Sign In</span>
                  </Link>
                </div>
              </div>
            </form>
          )}
        </div>
      </main>

      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Secure User Portal
      </footer>
    </div>
  );
}
