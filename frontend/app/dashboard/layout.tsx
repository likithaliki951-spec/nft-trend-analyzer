"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading) {
      if (!user) {
        router.replace("/user/login");
      } else if (user.role === "admin") {
        router.replace("/admin/dashboard");
      } else {
        // Seamlessly route to the dedicated User Portal
        const target = pathname.startsWith("/dashboard")
          ? pathname.replace(/^\/dashboard/, "/user/dashboard")
          : "/user/dashboard";
        router.replace(target);
      }
    }
  }, [user, isLoading, pathname, router]);

  return (
    <div className="min-h-screen bg-[#070b14] flex items-center justify-center">
      <div className="flex flex-col items-center space-y-3">
        <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin"></div>
        <span className="text-xs text-slate-400">Redirecting to User Workspace...</span>
      </div>
    </div>
  );
}
