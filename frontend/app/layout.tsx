import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "NFT Trend Analyzer — Analytics & Machine Learning Platform",
  description:
    "Analytics and machine learning platform for NFT market trends, price prediction, social engagement, and market intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-[#070b14] text-slate-100 min-h-screen antialiased selection:bg-violet-500/30 selection:text-violet-200">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
