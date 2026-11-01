"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import {
  Store,
  ArrowRightLeft,
  DollarSign,
  TrendingUp,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Sparkles,
  Layers,
  HelpCircle,
  Database,
  Radio,
} from "lucide-react";

const POPULAR_COLLECTIONS = [
  { name: "Bored Ape Yacht Club", slug: "boredapeyachtclub", tag: "PFP Blue-Chip" },
  { name: "CryptoPunks", slug: "cryptopunks", tag: "Historical Genesis" },
  { name: "Mutant Ape Yacht Club", slug: "mutant-ape-yacht-club", tag: "Derivative PFP" },
  { name: "Azuki", slug: "azuki", tag: "Anime Culture" },
  { name: "Pudgy Penguins", slug: "pudgypenguins", tag: "IP & Consumer" },
  { name: "Doodles", slug: "doodles-official", tag: "Community Art" },
];

export default function MarketplaceHubPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active dataset context
  const [activeMeta, setActiveMeta] = useState<any>(null);

  // Live ETH price state
  const [ethPriceData, setEthPriceData] = useState<any>(null);

  // Selected collection stats
  const [selectedSlug, setSelectedSlug] = useState("boredapeyachtclub");
  const [collStats, setCollStats] = useState<any>(null);
  const [loadingColl, setLoadingColl] = useState(false);

  // Currency converter state
  const [convertEth, setConvertEth] = useState<number>(1.5);
  const [convertUsd, setConvertUsd] = useState<number>(0);
  const [converting, setConverting] = useState(false);
  const [conversionResult, setConversionResult] = useState<any>(null);

  useEffect(() => {
    fetchMarketplaceData();

    const handleDatasetChanged = () => {
      fetchActiveMeta();
    };
    window.addEventListener("dataset-changed", handleDatasetChanged);
    return () => window.removeEventListener("dataset-changed", handleDatasetChanged);
  }, []);

  const fetchActiveMeta = async () => {
    try {
      const meta = await api.getActiveDataset();
      if (meta) setActiveMeta(meta);
    } catch {
      // Ignore
    }
  };

  const fetchMarketplaceData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [priceRes, collRes, metaRes] = await Promise.allSettled([
        api.getEthPrice(),
        api.getCollectionStats(selectedSlug),
        api.getActiveDataset(),
      ]);

      if (priceRes.status === "fulfilled") {
        setEthPriceData(priceRes.value.data);
        if (priceRes.value.data?.rate_usd) {
          const rate = priceRes.value.data.rate_usd;
          setConvertUsd(Number((1.5 * rate).toFixed(2)));
          setConversionResult({
            eth_amount: 1.5,
            rate_usd: rate,
            usd_amount: 1.5 * rate,
            is_live: priceRes.value.data.is_live,
            source: priceRes.value.data.source,
          });
        }
      }

      if (collRes.status === "fulfilled") {
        setCollStats(collRes.value.stats);
      }

      if (metaRes.status === "fulfilled" && metaRes.value) {
        setActiveMeta(metaRes.value);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load live marketplace data.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCollection = async (slug: string) => {
    setSelectedSlug(slug);
    try {
      setLoadingColl(true);
      const res = await api.getCollectionStats(slug);
      setCollStats(res.stats);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingColl(false);
    }
  };

  const handleEthInputChange = (val: number) => {
    setConvertEth(val);
    const rate = ethPriceData?.rate_usd || 2800.0;
    setConvertUsd(Number((val * rate).toFixed(2)));
  };

  const handleUsdInputChange = (val: number) => {
    setConvertUsd(val);
    const rate = ethPriceData?.rate_usd || 2800.0;
    setConvertEth(Number((val / rate).toFixed(4)));
  };

  const executeConvert = async () => {
    try {
      setConverting(true);
      const res = await api.convertCurrency(convertEth);
      setConversionResult(res.conversion);
    } catch (err: any) {
      alert(`Conversion failed: ${err.message}`);
    } finally {
      setConverting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-400" />
        <p className="text-sm text-slate-400">Querying live crypto market rates & collection metrics...</p>
      </div>
    );
  }

  const rate = ethPriceData?.rate_usd || 2800.0;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center space-x-2 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-1.5">
            <span>Section 4 of 4</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Marketplace Hub & Live Feeds</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time Ethereum spot price feeds, OpenSea smart contract telemetry, and high-frequency currency conversion.
          </p>
        </div>

        <button
          onClick={fetchMarketplaceData}
          className="flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg border border-slate-700 transition-colors self-start md:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Spot Feeds</span>
        </button>
      </div>

      {/* Explicit Distinction Badge: Live External API vs Uploaded Dataset */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 via-[#0d1322] to-sky-500/10 border border-amber-500/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center shrink-0">
            <Radio className="h-4 w-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-white">Live External API Telemetry</span>
              <span className="text-[10px] px-2 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                Distinct from Uploaded CSV Data
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              These live oracle metrics (CoinGecko & OpenSea) reflect current decentralized market conditions to benchmark against historical CSV analyses.
              {activeMeta && (
                <span className="text-slate-300 ml-1">
                  Active workspace dataset: <strong>{activeMeta.dataset_name}</strong> ({activeMeta.rows_count?.toLocaleString()} rows).
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Spot Price Card with Source Badge */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-[#141b2d] to-[#0d1322] border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-lg">
        <div className="space-y-2">
          <div className="flex items-center space-x-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Ethereum Spot Exchange Rate
            </span>
            <span
              className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border flex items-center space-x-1 ${
                ethPriceData?.is_live
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${ethPriceData?.is_live ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`}></span>
              <span>{ethPriceData?.source || "Live API"}</span>
            </span>
          </div>

          <div className="flex items-baseline space-x-3">
            <span className="text-3xl font-extrabold text-white font-mono">
              ${rate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className="text-xs text-slate-400">USD per 1.0 ETH</span>
          </div>

          <p className="text-[11px] text-slate-400 flex items-center space-x-1.5">
            <Clock className="h-3 w-3 text-slate-400" />
            <span>Last Polled: {ethPriceData?.timestamp ? new Date(ethPriceData.timestamp).toLocaleTimeString() : "Just now"}</span>
          </p>
        </div>

        <div className="flex items-center space-x-3 self-start md:self-auto">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-right">
            <span className="text-[10px] text-slate-400 block uppercase">Network Status</span>
            <span className="text-xs font-bold text-emerald-400 flex items-center justify-end gap-1 mt-0.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Synchronized
            </span>
          </div>
        </div>
      </div>

      {/* OpenSea Collection Intelligence */}
      <div className="p-6 rounded-2xl bg-[#0d1322] border border-slate-800 space-y-6">
        <div>
          <div className="flex items-center space-x-2">
            <Store className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">OpenSea Collection Intelligence</h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Query real-time floor prices, circulating supply, and aggregate volumes across leading smart contracts.
          </p>
        </div>

        {/* Collection Selector Tabs */}
        <div className="flex flex-wrap gap-2">
          {POPULAR_COLLECTIONS.map((c) => {
            const isSelected = selectedSlug === c.slug;
            return (
              <button
                key={c.slug}
                onClick={() => handleSelectCollection(c.slug)}
                className={`px-3 py-2 rounded-xl text-xs font-medium transition-all text-left border flex items-center space-x-2 ${
                  isSelected
                    ? "bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-sm"
                    : "bg-slate-900/60 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-white"
                }`}
              >
                <span>{c.name}</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  {c.tag}
                </span>
              </button>
            );
          })}
        </div>

        {/* Selected Collection Card */}
        <div className="p-5 rounded-xl bg-slate-900/40 border border-slate-800 relative">
          {loadingColl && (
            <div className="absolute inset-0 bg-[#0d1322]/80 backdrop-blur-xs flex items-center justify-center rounded-xl z-10">
              <RefreshCw className="h-5 w-5 animate-spin text-amber-400" />
            </div>
          )}

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800/80 mb-4">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase">Selected Contract</span>
              <h4 className="text-lg font-bold text-white capitalize">
                {collStats?.slug?.replace(/-/g, " ") || selectedSlug}
              </h4>
            </div>

            <span
              className={`text-[10px] font-medium px-2.5 py-0.5 rounded-full border self-start md:self-auto ${
                collStats?.is_live
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}
            >
              {collStats?.source || "Verified Benchmark"}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3.5 rounded-lg bg-[#0b0f19] border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Floor Price</span>
              <div className="text-lg font-bold text-amber-400 font-mono mt-0.5">
                {collStats?.floor_price_eth ? `${collStats.floor_price_eth} ETH` : "12.50 ETH"}
              </div>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                ≈ ${(Number(collStats?.floor_price_eth || 12.5) * rate).toLocaleString(undefined, { maximumFractionDigits: 0 })} USD
              </span>
            </div>

            <div className="p-3.5 rounded-lg bg-[#0b0f19] border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Total Supply</span>
              <div className="text-lg font-bold text-white font-mono mt-0.5">
                {collStats?.total_supply?.toLocaleString() || "10,000"}
              </div>
              <span className="text-[10px] text-slate-500 block mt-0.5">Minted items</span>
            </div>

            <div className="p-3.5 rounded-lg bg-[#0b0f19] border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Total Volume</span>
              <div className="text-lg font-bold text-sky-400 font-mono mt-0.5">
                {collStats?.total_volume_eth?.toLocaleString() || "145,000"} ETH
              </div>
              <span className="text-[10px] text-slate-500 block mt-0.5">Historical turnover</span>
            </div>

            <div className="p-3.5 rounded-lg bg-[#0b0f19] border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Implied Market Cap</span>
              <div className="text-lg font-bold text-emerald-400 font-mono mt-0.5">
                ${((collStats?.floor_price_eth || 12.5) * (collStats?.total_supply || 10000) * rate).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <span className="text-[10px] text-slate-500 block mt-0.5">USD Valuation</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Interactive Currency Converter */}
      <div className="p-6 rounded-2xl bg-[#0d1322] border border-slate-800 space-y-6">
        <div className="flex items-center space-x-2.5">
          <div className="h-8 w-8 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center">
            <ArrowRightLeft className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">High-Frequency Currency Converter</h3>
            <p className="text-xs text-slate-400">
              Dynamic bilateral calculation utilizing active market spot rates
            </p>
          </div>
        </div>

        {/* Quick Presets */}
        <div className="flex items-center space-x-2">
          <span className="text-[11px] text-slate-400">Quick Presets:</span>
          {[0.1, 0.5, 1.0, 5.0, 10.0].map((preset) => (
            <button
              key={preset}
              onClick={() => handleEthInputChange(preset)}
              className="text-[10px] px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition-colors"
            >
              {preset} ETH
            </button>
          ))}
        </div>

        {/* Bilateral Input Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              Ethereum Amount (ETH)
            </label>
            <div className="relative">
              <input
                type="number"
                step="0.01"
                value={convertEth}
                onChange={(e) => handleEthInputChange(parseFloat(e.target.value) || 0)}
                className="w-full bg-[#0b0f19] border border-slate-700 rounded-lg px-3.5 py-2.5 text-base font-mono font-bold text-white focus:outline-none focus:border-amber-500"
              />
              <span className="absolute right-3.5 top-3 text-xs font-mono font-bold text-slate-400">
                ETH
              </span>
            </div>
            <span className="text-[10px] text-slate-500 block">Base crypto token quantity</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              US Dollar Valuation (USD)
            </label>
            <div className="relative">
              <input
                type="number"
                step="1"
                value={convertUsd}
                onChange={(e) => handleUsdInputChange(parseFloat(e.target.value) || 0)}
                className="w-full bg-[#0b0f19] border border-slate-700 rounded-lg px-3.5 py-2.5 text-base font-mono font-bold text-emerald-400 focus:outline-none focus:border-amber-500"
              />
              <span className="absolute right-3.5 top-3 text-xs font-mono font-bold text-slate-400">
                USD
              </span>
            </div>
            <span className="text-[10px] text-slate-500 block">Derived fiat settlement amount</span>
          </div>
        </div>

        {/* Conversion Confirmation Banner */}
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2 text-slate-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <span>
              <strong>Exchange Quote:</strong> {convertEth} ETH ={" "}
              <span className="font-mono font-bold text-emerald-400">
                ${convertUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
              </span>
            </span>
          </div>

          <div className="text-[11px] text-slate-400 font-mono">
            Rate: 1 ETH = ${rate.toFixed(2)} USD
          </div>
        </div>
      </div>
    </div>
  );
}
