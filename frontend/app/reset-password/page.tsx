"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Mail, Lock, KeyRound, CheckCircle2, AlertCircle, ArrowLeft, RefreshCw, ArrowRight, ShieldCheck } from "lucide-react";

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const urlToken = searchParams.get("token") || "";
  const urlEmail = searchParams.get("email") || "";

  const [step, setStep] = useState<"request" | "confirm">(urlToken ? "confirm" : "request");
  const [email, setEmail] = useState(urlEmail);
  const [token, setToken] = useState(urlToken);
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState(false);

  useEffect(() => {
    if (urlToken) {
      setToken(urlToken);
      setStep("confirm");
    }
    if (urlEmail) {
      setEmail(urlEmail);
    }
  }, [urlToken, urlEmail]);

  // Password policy validations
  const hasMinLength = newPassword.length >= 12;
  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasLowercase = /[a-z]/.test(newPassword);
  const hasDigit = /[0-9]/.test(newPassword);
  const hasSpecial = /[^A-Za-z0-9]/.test(newPassword);
  const passwordsMatch = newPassword.length > 0 && newPassword === newPasswordConfirm;

  const handleRequestToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    setIsLoading(true);
    try {
      const res = await api.forgotPassword(email);
      setSuccessMsg(res.message || "If this email address is registered, password reset instructions have been prepared.");
      setStep("confirm");
    } catch (err: any) {
      // Keep user-facing message safe and generic
      setSuccessMsg("If this email address is registered, password reset instructions have been prepared.");
      setStep("confirm");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    if (newPassword !== newPasswordConfirm) {
      setErrorMsg("New password and confirmation do not match.");
      return;
    }

    if (!hasMinLength || !hasUppercase || !hasLowercase || !hasDigit || !hasSpecial) {
      setErrorMsg("Password does not meet enterprise policy (12+ characters with uppercase, lowercase, digit, and special character).");
      return;
    }

    setIsLoading(true);
    try {
      const res = await api.resetPassword({
        token: token.trim(),
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });
      setSuccessMsg(res.message || "Password updated successfully. You can now log in with your new credentials.");
      setIsCompleted(true);
    } catch (err: any) {
      setErrorMsg(err.message || "Password reset failed. Please ensure your token is valid and unexpired.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-[#0d1322] border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl relative">
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-sky-500 to-indigo-500"></div>

      <Link
        href="/user/login"
        className="inline-flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        <span>Back to User Sign In</span>
      </Link>

      <h1 className="text-xl font-bold text-white mb-2">Password Recovery</h1>
      <p className="text-xs text-slate-400 mb-6">
        {isCompleted
          ? "Your credentials have been securely updated."
          : step === "request"
          ? "Enter your registered work email to receive password reset instructions."
          : "Set a new secure password conforming to enterprise policy."}
      </p>

      {errorMsg && (
        <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && !isCompleted && (
        <div className="mb-5 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start space-x-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
          <span>{successMsg}</span>
        </div>
      )}

      {isCompleted ? (
        <div className="space-y-6 text-center py-4">
          <div className="h-14 w-14 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto">
            <ShieldCheck className="h-7 w-7 text-emerald-400" />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-white">Password Reset Successful</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Your password has been securely updated. You can now authenticate using your new password.
            </p>
          </div>
          <Link
            href="/user/login"
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-violet-500/20 transition-all flex items-center justify-center space-x-2"
          >
            <span>Sign In to User Portal</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : step === "request" ? (
        <form onSubmit={handleRequestToken} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Registered Work Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@nfttrends.io"
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition-all disabled:opacity-50 flex items-center justify-center space-x-2 shadow-lg shadow-violet-500/20"
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Preparing Instructions...</span>
              </>
            ) : (
              <span>Request Reset Authorization</span>
            )}
          </button>

          <div className="pt-2 text-center">
            <button
              type="button"
              onClick={() => setStep("confirm")}
              className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
            >
              Already have an authorization token? Enter it here &rarr;
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleConfirmReset} className="space-y-4">
          {email && (
            <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
              <span>Account: <strong className="text-slate-200">{email}</strong></span>
              <button
                type="button"
                onClick={() => setStep("request")}
                className="text-violet-400 hover:text-violet-300 text-[11px]"
              >
                Change
              </button>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Authorization Token</label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste authorization token from email"
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">New Password (12+ characters)</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Uppercase, lowercase, digit, special character"
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Confirm New Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="password"
                required
                value={newPasswordConfirm}
                onChange={(e) => setNewPasswordConfirm(e.target.value)}
                placeholder="Re-enter new password"
                className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
              />
            </div>
          </div>

          {/* Password Policy Indicators */}
          <div className="bg-[#080c16] border border-slate-800 rounded-xl p-3 space-y-1.5">
            <span className="text-[11px] font-medium text-slate-400 block">Password Requirements:</span>
            <div className="grid grid-cols-2 gap-1 text-[10px]">
              <div className={`flex items-center space-x-1.5 ${hasMinLength ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{hasMinLength ? "✓" : "○"}</span>
                <span>12+ characters</span>
              </div>
              <div className={`flex items-center space-x-1.5 ${hasUppercase ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{hasUppercase ? "✓" : "○"}</span>
                <span>Uppercase letter</span>
              </div>
              <div className={`flex items-center space-x-1.5 ${hasLowercase ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{hasLowercase ? "✓" : "○"}</span>
                <span>Lowercase letter</span>
              </div>
              <div className={`flex items-center space-x-1.5 ${hasDigit ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{hasDigit ? "✓" : "○"}</span>
                <span>Number</span>
              </div>
              <div className={`flex items-center space-x-1.5 ${hasSpecial ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{hasSpecial ? "✓" : "○"}</span>
                <span>Special character</span>
              </div>
              <div className={`flex items-center space-x-1.5 ${passwordsMatch ? "text-emerald-400" : "text-slate-500"}`}>
                <span>{passwordsMatch ? "✓" : "○"}</span>
                <span>Passwords match</span>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition-all disabled:opacity-50 flex items-center justify-center space-x-2 shadow-lg shadow-violet-500/20"
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Updating Password...</span>
              </>
            ) : (
              <span>Update Password & Return</span>
            )}
          </button>

          <div className="pt-2 text-center">
            <button
              type="button"
              onClick={() => {
                setStep("request");
                setErrorMsg(null);
                setSuccessMsg(null);
              }}
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              Need a new token? Request another link &rarr;
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col justify-center items-center px-4 py-12">
      <Suspense
        fallback={
          <div className="w-full max-w-md bg-[#0d1322] border border-slate-800 rounded-2xl p-8 shadow-2xl flex flex-col items-center space-y-3">
            <RefreshCw className="h-6 w-6 text-violet-400 animate-spin" />
            <span className="text-xs text-slate-400">Loading password recovery...</span>
          </div>
        }
      >
        <ResetPasswordContent />
      </Suspense>
    </div>
  );
}
