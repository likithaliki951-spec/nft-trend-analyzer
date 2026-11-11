"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LegacyLoginPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/user/login");
  }, [router]);

  return (
    <div className="min-h-screen bg-[#070b14] flex items-center justify-center">
      <div className="flex flex-col items-center space-y-3">
        <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin"></div>
        <span className="text-xs text-slate-400">Redirecting to User Portal...</span>
      </div>
    </div>
  );
}
