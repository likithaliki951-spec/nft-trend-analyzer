"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Key, Lock, Mail, User as UserIcon, ArrowRight, Shield, AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";

export default function AdminSetupPage() {
  const { setSession } = useAuth();
  const router = useRouter();
  const [setupToken, setSetupToken] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Password confirmation does not match.");
      return;
    }

    if (password.length < 12) {
      setError("Password must be at least 12 characters long.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.adminSetupInit({
        setup_token: setupToken.trim(),
        email: email.trim().toLowerCase(),
        name: name.trim(),
        password,
        password_confirm: confirmPassword,
      });

      if (res.access_token && res.user) {
        setSession(res.access_token, res.user, "/admin/dashboard");
      } else {
        router.push("/admin/login");
      }
    } catch (err: any) {
      setError(err.message || "Failed to initialize administrator. Please check your setup token.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-between p-6">
      <header className="flex items-center justify-between max-w-6xl mx-auto w-full py-2">
        <Link href="/" className="flex items-center space-x-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center text-slate-950 font-bold text-sm shadow-lg shadow-amber-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-sm text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
              Setup Provisioning
            </span>
          </div>
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center my-8">
        <div className="w-full max-w-lg bg-[#0a0f1d] border border-amber-500/30 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600"></div>

          <div className="text-center mb-6">
            <div className="h-12 w-12 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto mb-3">
              <Key className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">First Administrator Setup</h1>
            <p className="text-xs text-slate-400 mt-1">
              One-time initial bootstrap process. Permanently disables once completed.
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
              <label className="block text-xs font-medium text-amber-300 mb-1.5">
                Secret Setup Token (ADMIN_SETUP_TOKEN)
              </label>
              <div className="relative">
                <Key className="absolute left-3.5 top-3 h-4 w-4 text-amber-500/80" />
                <input
                  type="password"
                  value={setupToken}
                  onChange={(e) => setSetupToken(e.target.value)}
                  placeholder="Enter secret setup token configured on server"
                  required
                  className="w-full bg-[#070b14] border border-amber-500/40 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400 font-mono transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Master Admin Name
              </label>
              <div className="relative">
                <UserIcon className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="System Administrator"
                  required
                  className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Master Admin Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@nfttrends.io"
                  required
                  className="w-full bg-[#070b14] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition-colors"
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
                  <span>Provision Master Administrator</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-800 text-center">
            <Link
              href="/admin/login"
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              Return to Admin Sign In
            </Link>
          </div>
        </div>
      </main>

      <footer className="text-center text-[11px] text-slate-500 py-2">
        NFT Trend Analyzer v3.0 &bull; Master Setup Tool
      </footer>
    </div>
  );
}
