"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { UserSidebar } from "@/components/UserSidebar";
import { Navbar } from "@/components/Navbar";
import { ShieldAlert, Clock, LogOut } from "lucide-react";

export default function UserDashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (!user) {
        router.push("/user/login");
      } else if (user.role === "admin") {
        // SEC Requirement: Administrators attempting /user/dashboard must be redirected to their admin portal
        router.push("/admin/dashboard");
      }
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin"></div>
          <span className="text-xs text-slate-400">Loading user research environment...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Account Suspended Screen
  if (user.account_status === "suspended") {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center p-6 text-center">
        <div className="max-w-md bg-[#0d1322] border border-rose-500/30 rounded-2xl p-8 shadow-2xl space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center mx-auto">
            <ShieldAlert className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Account Suspended</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Your regular user account has been suspended by a platform administrator. Access to research modules, datasets, and exports is restricted.
          </p>
          <div className="pt-2">
            <button
              onClick={() => logout("user")}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Account Pending Screen
  if (user.account_status === "pending") {
    return (
      <div className="min-h-screen bg-[#070b14] flex items-center justify-center p-6 text-center">
        <div className="max-w-md bg-[#0d1322] border border-amber-500/30 rounded-2xl p-8 shadow-2xl space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center mx-auto">
            <Clock className="h-7 w-7" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">Account Approval Pending</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Your account is currently awaiting verification and activation. You will be able to access the research workspace once approved.
          </p>
          <div className="pt-2">
            <button
              onClick={() => logout("user")}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl border border-slate-700 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#070b14] overflow-hidden">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
