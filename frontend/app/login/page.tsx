"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Eye, EyeOff, Lock, Mail, User, ShieldCheck, AlertCircle, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState<"signin" | "register">("signin");

  // Form States
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Real-time password strength validation
  const getPasswordStrength = (pwd: string) => {
    let score = 0;
    if (pwd.length >= 12) score += 1;
    if (pwd.length >= 16) score += 1;
    if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;

    const levels = [
      { label: "Too Weak", color: "bg-rose-500", width: "15%" },
      { label: "Weak", color: "bg-orange-500", width: "35%" },
      { label: "Moderate", color: "bg-amber-500", width: "60%" },
      { label: "Strong", color: "bg-sky-500", width: "85%" },
      { label: "Very Strong", color: "bg-emerald-500", width: "100%" },
    ];
    return levels[Math.min(4, score)];
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to sign in. Check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);
    try {
      await register(email, name, password, passwordConfirm);
    } catch (err: any) {
      setErrorMsg(err.message || "Registration failed. Check password requirements.");
    } finally {
      setIsLoading(false);
    }
  };

  const strength = getPasswordStrength(password);

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-center items-center px-4 py-12">
      {/* Brand Header */}
      <div className="text-center mb-8">
        <Link href="/" className="inline-flex items-center space-x-2.5 mb-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-violet-600 to-sky-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-violet-500/20">
            NT
          </div>
          <span className="font-bold text-xl text-white tracking-tight">NFT Trend Analyzer</span>
        </Link>
        <p className="text-xs text-slate-400">Machine Learning &amp; Market Research Terminal</p>
      </div>

      {/* Main Auth Container Card */}
      <div className="w-full max-w-md bg-[#0d1322] border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        {/* Top Glow Accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-600 via-sky-500 to-emerald-500"></div>

        {/* Tabs */}
        <div className="grid grid-cols-2 bg-slate-900/80 p-1 rounded-xl border border-slate-800 mb-6">
          <button
            onClick={() => {
              setActiveTab("signin");
              setErrorMsg(null);
            }}
            className={`py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "signin"
                ? "bg-violet-600 text-white shadow-md shadow-violet-600/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            🔑 Sign In
          </button>
          <button
            onClick={() => {
              setActiveTab("register");
              setErrorMsg(null);
            }}
            className={`py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "register"
                ? "bg-violet-600 text-white shadow-md shadow-violet-600/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            📝 Create Account
          </button>
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Sign In Form */}
        {activeTab === "signin" && (
          <form onSubmit={handleSignIn} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Work Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-xs font-medium text-slate-300">Password</label>
                <Link href="/reset-password" className="text-[11px] text-violet-400 hover:text-violet-300">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full pl-9 pr-10 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-violet-500/25 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <span>{isLoading ? "Authenticating..." : "Sign In to Terminal"}</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>
        )}

        {/* Register Form */}
        {activeTab === "register" && (
          <form onSubmit={handleRegister} className="space-y-3.5">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Morgan"
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Work Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Create Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 12 characters"
                  className="w-full pl-9 pr-10 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* Password Strength Indicator */}
              {password && (
                <div className="mt-2">
                  <div className="flex justify-between items-center text-[10px] text-slate-400 mb-1">
                    <span>Strength:</span>
                    <span className="font-semibold text-slate-200">{strength.label}</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${strength.color} transition-all duration-300`}
                      style={{ width: strength.width }}
                    ></div>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  placeholder="Re-enter password"
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>

            {/* Checklist Box */}
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl text-[10px] text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300 mb-1">Password Requirements:</div>
              <div className="flex items-center gap-1.5">
                <span className={password.length >= 12 ? "text-emerald-400" : "text-slate-400"}>●</span>
                <span>Minimum 12 characters long</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={/[A-Z]/.test(password) && /[a-z]/.test(password) ? "text-emerald-400" : "text-slate-400"}>●</span>
                <span>Uppercase and lowercase letters</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={/[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password) ? "text-emerald-400" : "text-slate-400"}>●</span>
                <span>Number and special character (!@#$%^&*)</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-violet-500/25 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <span>{isLoading ? "Creating Account..." : "Create Analyst Account"}</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>
        )}
      </div>

      <p className="mt-8 text-center text-xs text-slate-400">
        Demo Administrator account available: <span className="font-mono text-slate-300">admin@nfttrends.io</span>
      </p>
    </div>
  );
}
