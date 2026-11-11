"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Lock, Mail, User as UserIcon, ArrowRight, Shield, AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";

export default function UserRegisterPage() {
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Password Policy Indicators
  const hasMinLength = password.length >= 12;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Password confirmation does not match.");
      return;
    }

    if (!hasMinLength || !hasUppercase || !hasLowercase || !hasDigit || !hasSpecial) {
      setError("Password does not meet all enterprise security requirements.");
      return;
    }

    setLoading(true);
    try {
      await register(email, name, password, confirmPassword);
    } catch (err: any) {
      setError(err.message || "Failed to create account. Please check the provided information.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
      {/* Header */}
      <header className="flex items-center justify-between max-w-6xl mx-auto w-full py-2">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-violet-600 to-sky-500 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-violet-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-sm text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
              User Registration
            </span>
          </div>
        </Link>

        <Link
          href="/admin/register"
          className="flex items-center space-x-1.5 text-xs text-amber-400/90 hover:text-amber-300 px-3 py-1.5 rounded-lg border border-amber-500/20 hover:border-amber-500/40 bg-amber-500/5 transition-all"
        >
          <Shield className="h-3.5 w-3.5" />
          <span>Apply for Admin Account</span>
          <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      {/* Main Registration Card */}
      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-lg bg-[#0d1322] border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-sky-500 to-indigo-500"></div>

          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-white tracking-tight">Create User Account</h1>
            <p className="text-xs text-slate-400 mt-1">
              Join the NFT Trend Analyzer analytics platform as a regular analyst
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name</label>
              <div className="relative">
                <UserIcon className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Elena Rostova"
                  required
                  className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                />
              </div>
            </div>

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
                  placeholder="elena@nfttrends.io"
                  required
                  className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 12 characters"
                    required
                    className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm password"
                    required
                    className="w-full bg-[#080c16] border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
                  />
                </div>
              </div>
            </div>

            {/* Password Policy Criteria Checklist */}
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] space-y-1.5">
              <span className="text-slate-400 font-semibold block mb-1">
                Enterprise Password Policy:
              </span>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                <span className={`flex items-center gap-1.5 ${hasMinLength ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> 12+ characters
                </span>
                <span className={`flex items-center gap-1.5 ${hasUppercase ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> Uppercase (A-Z)
                </span>
                <span className={`flex items-center gap-1.5 ${hasLowercase ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> Lowercase (a-z)
                </span>
                <span className={`flex items-center gap-1.5 ${hasDigit ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> Number (0-9)
                </span>
                <span className={`flex items-center gap-1.5 ${hasSpecial ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> Special (!@#$%...)
                </span>
                <span className={`flex items-center gap-1.5 ${passwordsMatch ? "text-emerald-400" : "text-slate-500"}`}>
                  <CheckCircle2 className="h-3 w-3" /> Passwords match
                </span>
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
                  <span>Create Regular User Account</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-800 text-center space-y-2">
            <p className="text-xs text-slate-400">
              Already have an account?{" "}
              <Link
                href="/user/login"
                className="text-violet-400 hover:text-violet-300 font-semibold transition-colors"
              >
                Sign In to User Portal
              </Link>
            </p>
            <p className="text-[11px] text-slate-500">
              Applying for administrator credentials?{" "}
              <Link
                href="/admin/register"
                className="text-amber-400/90 hover:text-amber-300 font-medium transition-colors"
              >
                Admin Registration Request →
              </Link>
            </p>
          </div>
        </div>
      </main>

      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Secure User Portal
      </footer>
    </div>
  );
}
