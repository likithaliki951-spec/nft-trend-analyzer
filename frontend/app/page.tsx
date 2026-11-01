import Link from "next/link";
import { TrendingUp, BarChart3, MessageSquare, Store, Shield, Cpu, Database, ArrowRight } from "lucide-react";

export default function Home() {
  const sections = [
    {
      title: "Section 1: Price Trends & Prediction",
      desc: "Chronological time-series modeling, 60-component PCA dimensionality reduction, and Random Forest & Gradient Boosting regression.",
      icon: TrendingUp,
      badge: "PCA + ML Models",
      color: "from-violet-500/20 to-indigo-500/20 border-violet-500/30",
    },
    {
      title: "Section 2: Market Activity",
      desc: "Macro transaction volume KPIs, collection distributions, and valuation tier classification (Logistic Regression, RF, SVM).",
      icon: BarChart3,
      badge: "Overview & Tiers",
      color: "from-sky-500/20 to-blue-500/20 border-sky-500/30",
    },
    {
      title: "Section 3: Social Engagement",
      desc: "Social signal matrices, Discord/Twitter engagement dynamics, and cross-metric correlation coefficient benchmarking.",
      icon: MessageSquare,
      badge: "Signal Analysis",
      color: "from-emerald-500/20 to-teal-500/20 border-emerald-500/30",
    },
    {
      title: "Section 4: Marketplace Hub",
      desc: "Real-time CoinGecko ETH/USD rates, OpenSea verified collection floor stats, and interactive currency conversion.",
      icon: Store,
      badge: "Live External APIs",
      color: "from-amber-500/20 to-orange-500/20 border-amber-500/30",
    },
  ];

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Banner */}
      <nav className="h-20 border-b border-slate-800/80 px-8 flex items-center justify-between max-w-7xl mx-auto w-full">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-violet-600 to-sky-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-violet-500/20">
            NT
          </div>
          <div>
            <span className="font-bold text-base text-white tracking-tight">NFT Trend Analyzer</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
              v3.0 Web Terminal
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <Link
            href="/login"
            className="text-xs text-slate-300 hover:text-white transition-colors font-medium px-3 py-2"
          >
            Sign In
          </Link>
          <Link
            href="/dashboard"
            className="text-xs bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-medium px-4 py-2 rounded-lg shadow-md shadow-violet-500/20 transition-all flex items-center space-x-1.5"
          >
            <span>Launch Dashboard</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex-1 max-w-7xl mx-auto px-8 py-16 flex flex-col items-center text-center">
        <div className="inline-flex items-center space-x-2 text-xs font-semibold px-3 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 mb-6">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>FastAPI + Next.js + Supabase Architecture</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-white max-w-4xl mb-6">
          Analytics &amp; Machine Learning for Trending NFTs
        </h1>
        <p className="text-base md:text-lg text-slate-400 max-w-2xl mb-10 leading-relaxed">
          Analyze NFT market trends, predict prices, explore social engagement, and discover market intelligence using data analytics and machine learning.
        </p>

        <div className="flex flex-wrap gap-4 justify-center mb-16">
          <Link
            href="/dashboard"
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-sm shadow-xl shadow-violet-500/25 transition-all flex items-center space-x-2"
          >
            <span>Open Research Workspace</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/login"
            className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 font-semibold text-sm border border-slate-800 transition-colors"
          >
            Sign In / Register
          </Link>
        </div>

        {/* 4 Consolidated Sections Grid */}
        <div className="w-full text-left mb-16">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-6 text-center">
            Consolidated 4-Section Architecture
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {sections.map((sec, i) => {
              const Icon = sec.icon;
              return (
                <div
                  key={i}
                  className={`p-6 rounded-2xl bg-gradient-to-br ${sec.color} border bg-[#0d1322] backdrop-blur-sm transition-all hover:scale-[1.01]`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="h-10 w-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-white">
                      <Icon className="h-5 w-5 text-violet-400" />
                    </div>
                    <span className="text-[10px] px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-medium border border-slate-700">
                      {sec.badge}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{sec.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{sec.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Technical Architecture Highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full text-left">
          <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center space-x-2 text-violet-400 mb-2">
              <Cpu className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-wider">FastAPI ML Engine</span>
            </div>
            <p className="text-xs text-slate-400">
              Random Forest, Gradient Boosting, SVM, and balanced Logistic Regression executed server-side.
            </p>
          </div>
          <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center space-x-2 text-sky-400 mb-2">
              <Database className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-wider">Supabase Persistence</span>
            </div>
            <p className="text-xs text-slate-400">
              Row Level Security ensures strict account isolation for datasets, sessions, and predictions.
            </p>
          </div>
          <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center space-x-2 text-emerald-400 mb-2">
              <Shield className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-wider">Enterprise Security</span>
            </div>
            <p className="text-xs text-slate-400">
              Salted bcrypt hashing, brute-force rate-limiting, and 12+ character complexity enforcement.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-400">
        NFT Trend Analyzer &bull; Version 3.0.0 &bull; Independently Hosted Web Application
      </footer>
    </div>
  );
}
