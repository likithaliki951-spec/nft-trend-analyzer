"use client";

import React, { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  Shield,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  Clock,
  Layers,
} from "lucide-react";

export default function AdminRegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [verifyStatus, setVerifyStatus] = useState<string | null>(null);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlToken = params.get("token");
      const urlEmail = params.get("email");
      if (urlToken) {
        setVerificationToken(urlToken);
        setSubmitted(true);
      }
      if (urlEmail) {
        setEmail(urlEmail);
      }
    }
  }, []);

  // Password Policy
  const hasMinLength = password.length >= 12;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;

  // Gmail Validation
  const isGmail = /@gmail\.com$/i.test(email.trim()) || /@googlemail\.com$/i.test(email.trim());

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isGmail) {
      setError("Administrator registration is strictly restricted to valid Gmail addresses (@gmail.com).");
      return;
    }

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
      const res = await api.adminRegister({
        email: email.trim().toLowerCase(),
        name: name.trim(),
        password,
        password_confirm: confirmPassword,
      });

      setRequestId(res.request_id || "");
      if (res.verification_token) {
        setVerificationToken(res.verification_token);
      }
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || "Failed to submit administrator registration request.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEmail = async () => {
    if (!verificationToken) return;
    try {
      setLoading(true);
      const res = await api.adminVerifyEmail({
        email: email.trim().toLowerCase(),
        token: verificationToken,
      });
      setVerifyStatus(res.message || "Email address verified successfully!");
    } catch (err: any) {
      setError(err.message || "Failed to verify email address.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
      {/* Header */}
      <header className="flex items-center justify-between max-w-6xl mx-auto w-full py-2">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-slate-950 font-bold text-sm shadow-lg shadow-amber-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-sm text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
              Admin Application
            </span>
          </div>
        </Link>

        <Link
          href="/user/login"
          className="flex items-center space-x-1.5 text-xs text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 transition-all"
        >
          <Layers className="h-3.5 w-3.5 text-violet-400" />
          <span>Switch to User Portal</span>
        </Link>
      </header>

      {/* Main Form */}
      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-lg bg-[#0a0f1d] border border-amber-500/30 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600"></div>

          {submitted ? (
            <div className="space-y-6 text-center">
              <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto">
                <Clock className="h-7 w-7" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Application Submitted &bull; PENDING
                </h2>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                  Your administrator registration request for{" "}
                  <span className="font-mono text-amber-300">{email}</span> has been logged with status:{" "}
                  <span className="font-mono text-amber-400 font-bold uppercase">PENDING</span>.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-left space-y-2 text-xs">
                <div className="text-slate-300 font-semibold flex items-center gap-2">
                  <Shield className="h-4 w-4 text-amber-400" />
                  <span>Security &amp; Approval Process</span>
                </div>
                <ul className="text-slate-400 text-[11px] space-y-1 list-disc list-inside">
                  <li>Pending administrators cannot access admin APIs or the admin dashboard.</li>
                  <li>Email ownership verification must be confirmed.</li>
                  <li>An existing active administrator must review and approve your request.</li>
                </ul>
              </div>

              {/* Email Ownership Verification */}
              {!verifyStatus && (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-left space-y-3">
                  <div className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Email Ownership Verification</span>
                  </div>
                  <p className="text-[11px] text-slate-300">
                    Verify email ownership to make this application eligible for administrator review and approval:
                  </p>
                  <input
                    type="text"
                    value={verificationToken}
                    onChange={(e) => setVerificationToken(e.target.value.trim())}
                    placeholder="Enter or paste email verification token..."
                    className="w-full bg-[#050811] border border-amber-500/30 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-400 font-mono"
                  />
                  <button
                    onClick={handleVerifyEmail}
                    disabled={loading || !verificationToken.trim()}
                    className="w-full py-2 px-3 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs transition-colors"
                  >
                    Confirm Email Verification
                  </button>
                </div>
              )}

              {verifyStatus && (
                <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center space-x-2">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{verifyStatus}</span>
                </div>
              )}

              <div className="pt-2">
                <Link
                  href="/admin/login"
                  className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
                >
                  <span>Return to Admin Login</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div className="text-center mb-6">
                <div className="inline-flex items-center space-x-2 text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-2">
                  <span>Option B: Administrator Approval Required</span>
                </div>
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Request Administrator Access
                </h1>
                <p className="text-xs text-slate-400 mt-1">
                  Requires a verified Gmail address and approval by an active platform administrator
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
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Full Name</label>
                  <div className="relative">
                    <UserIcon className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Alexandre Miller"
                      required
                      className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-medium text-slate-300">Applicant Gmail Address</label>
                    <span className="text-[10px] text-amber-400 font-mono">@gmail.com required</span>
                  </div>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="alexandre@gmail.com"
                      required
                      className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                    />
                  </div>
                  {email.length > 0 && !isGmail && (
                    <p className="text-[10px] text-amber-400 mt-1">
                      Must end with @gmail.com or @googlemail.com
                    </p>
                  )}
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
                        className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
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
                        className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                      />
                    </div>
                  </div>
                </div>

                {/* Password Policy */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-[11px] space-y-1.5">
                  <span className="text-slate-400 font-semibold block mb-1">
                    Password Requirements:
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
                      <CheckCircle2 className="h-3 w-3" /> Special (!@#$...)
                    </span>
                    <span className={`flex items-center gap-1.5 ${passwordsMatch ? "text-emerald-400" : "text-slate-500"}`}>
                      <CheckCircle2 className="h-3 w-3" /> Passwords match
                    </span>
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
                      <span>Submit Administrator Application</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-6 pt-5 border-t border-slate-800 text-center space-y-2">
                <p className="text-xs text-slate-400">
                  Already an approved administrator?{" "}
                  <Link
                    href="/admin/login"
                    className="text-amber-400 hover:text-amber-300 font-semibold transition-colors"
                  >
                    Sign In to Admin Portal
                  </Link>
                </p>
                <p className="text-[11px] text-slate-500">
                  Regular analyst?{" "}
                  <Link
                    href="/user/register"
                    className="text-violet-400 hover:text-violet-300 font-medium transition-colors"
                  >
                    User Public Registration →
                  </Link>
                </p>
              </div>
            </>
          )}
        </div>
      </main>

      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Restricted Administrator Portal &bull; All Access Logged
      </footer>
    </div>
  );
}
