"use client";

import React, { useState } from "react";
import {
  X,
  FileText,
  FileSpreadsheet,
  FileCode,
  Download,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sparkles,
  Layers,
  BarChart3,
  TrendingUp,
  Share2,
  Store,
  Brain,
  Database,
} from "lucide-react";
import { api } from "@/lib/api";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  datasetName?: string;
  projectId?: string;
}

type ExportFormat = "pdf" | "xlsx" | "docx" | "json";

const FORMAT_OPTIONS: {
  id: ExportFormat;
  title: string;
  extension: string;
  desc: string;
  icon: any;
  color: string;
  badge: string;
}[] = [
  {
    id: "pdf",
    title: "PDF Report",
    extension: ".pdf",
    desc: "Executive document with Page X of Y numbering, styled tables, and embedded high-resolution charts.",
    icon: FileText,
    color: "from-rose-500/20 to-red-500/20 text-rose-400 border-rose-500/30",
    badge: "Publication Grade",
  },
  {
    id: "xlsx",
    title: "Excel Workbook",
    extension: ".xlsx",
    desc: "Multi-tab spreadsheet with styled headers, auto-fit columns, financial number formats, and native charts.",
    icon: FileSpreadsheet,
    color: "from-emerald-500/20 to-teal-500/20 text-emerald-400 border-emerald-500/30",
    badge: "Data Analyst",
  },
  {
    id: "docx",
    title: "Word Document",
    extension: ".docx",
    desc: "Structured Microsoft Word document with editable sections, metadata cards, and embedded chart figures.",
    icon: FileText,
    color: "from-blue-500/20 to-indigo-500/20 text-blue-400 border-blue-500/30",
    badge: "Enterprise",
  },
  {
    id: "json",
    title: "Structured JSON",
    extension: ".json",
    desc: "High-fidelity machine-readable JSON containing full dataset telemetry, model benchmarks, and correlations.",
    icon: FileCode,
    color: "from-amber-500/20 to-orange-500/20 text-amber-400 border-amber-500/30",
    badge: "API & Pipeline",
  },
];

const SCOPE_OPTIONS = [
  {
    id: "complete",
    label: "Complete Intelligence Report",
    desc: "All modules, regression models, valuation tiers, social vectors, and live telemetry",
    icon: Layers,
  },
  {
    id: "price_trends",
    label: "Price Trends & ML Regression",
    desc: "Time series, 7-day moving averages, ML regressor comparisons, and PCA diagnostics",
    icon: TrendingUp,
  },
  {
    id: "market_activity",
    label: "Market Activity & Valuation Tiers",
    desc: "High-level market KPIs, tier distributions, and 3-tier classification models",
    icon: BarChart3,
  },
  {
    id: "social_engagement",
    label: "Social Sentiment & Signal Vectors",
    desc: "Pearson/Spearman correlation matrices and top predictive social indicators",
    icon: Share2,
  },
  {
    id: "marketplace_hub",
    label: "Marketplace Hub Telemetry",
    desc: "Verified collections floor prices, 24h volumes, and ETH/USD conversion rates",
    icon: Store,
  },
  {
    id: "ml_results",
    label: "Machine Learning Benchmarks",
    desc: "Consolidated ML regressors (RMSE, MAE, R²) and valuation tier classifiers",
    icon: Brain,
  },
  {
    id: "dataset_summary",
    label: "Dataset Schema & Data Quality",
    desc: "Column data types, non-null counts, missing value audits, and descriptive statistics",
    icon: Database,
  },
];

export function ExportModal({ isOpen, onClose, datasetName, projectId }: ExportModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("pdf");
  const [selectedScope, setSelectedScope] = useState<string>("complete");
  const [customTitle, setCustomTitle] = useState<string>("");
  const [includeCharts, setIncludeCharts] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  if (!isOpen) return null;

  const handleExport = async () => {
    try {
      setIsExporting(true);
      setStatusMessage(null);

      const result = await api.exportReport({
        format: selectedFormat,
        scope: selectedScope,
        project_id: projectId,
        custom_title: customTitle.trim() || undefined,
        include_charts: includeCharts,
      });

      api.downloadBlob(result.blob, result.filename);

      setStatusMessage({
        type: "success",
        text: `Successfully generated and downloaded ${result.filename}`,
      });

      setTimeout(() => {
        setIsExporting(false);
      }, 1000);
    } catch (err: any) {
      setIsExporting(false);
      setStatusMessage({
        type: "error",
        text: err?.message || "Failed to generate report export. Please check server logs.",
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-[#0d1322] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-[#070b14]/50">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Download className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Export Analytical Report</h2>
              <p className="text-xs text-slate-400">
                {datasetName ? `Active Dataset: ${datasetName}` : "Download publication-ready reports in multiple formats"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isExporting}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 custom-scrollbar">
          {/* Format Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
              1. Choose Export Format
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {FORMAT_OPTIONS.map((fmt) => {
                const Icon = fmt.icon;
                const isSelected = selectedFormat === fmt.id;
                return (
                  <button
                    key={fmt.id}
                    type="button"
                    onClick={() => setSelectedFormat(fmt.id)}
                    className={`relative p-3.5 rounded-xl border text-left transition-all flex flex-col justify-between ${
                      isSelected
                        ? "bg-violet-950/30 border-violet-500 shadow-sm shadow-violet-500/10"
                        : "bg-[#070b14]/40 border-slate-800/80 hover:border-slate-700 hover:bg-[#070b14]/70"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2.5">
                        <div className={`p-2 rounded-lg border bg-gradient-to-br ${fmt.color}`}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white flex items-center gap-1.5">
                            {fmt.title}
                            <span className="text-[10px] font-mono text-slate-400">{fmt.extension}</span>
                          </div>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 font-medium">
                            {fmt.badge}
                          </span>
                        </div>
                      </div>
                      <div
                        className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${
                          isSelected ? "border-violet-500 bg-violet-600" : "border-slate-700 bg-transparent"
                        }`}
                      >
                        {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{fmt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Scope Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
              2. Select Content Scope
            </label>
            <div className="relative">
              <select
                value={selectedScope}
                onChange={(e) => setSelectedScope(e.target.value)}
                className="w-full bg-[#070b14] border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors cursor-pointer"
              >
                {SCOPE_OPTIONS.map((sc) => (
                  <option key={sc.id} value={sc.id}>
                    {sc.label}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-[11px] text-slate-400 mt-1.5 ml-1">
              {SCOPE_OPTIONS.find((s) => s.id === selectedScope)?.desc}
            </p>
          </div>

          {/* Advanced Configurations */}
          <div className="space-y-3 pt-1 border-t border-slate-800/60">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Custom Document Title (Optional)
              </label>
              <input
                type="text"
                placeholder={datasetName ? `NFT Market Intelligence Report — ${datasetName}` : "Enter custom report title..."}
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                className="w-full bg-[#070b14] border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            {selectedFormat !== "json" && (
              <label className="flex items-center space-x-2.5 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-700 bg-[#070b14] text-violet-600 focus:ring-violet-500 focus:ring-offset-0 cursor-pointer"
                />
                <span className="text-xs text-slate-300 select-none">
                  Include high-resolution graphical plots and trend visualizers
                </span>
              </label>
            )}
          </div>

          {/* Status Banners */}
          {statusMessage && (
            <div
              className={`p-3.5 rounded-xl border text-xs flex items-center space-x-2.5 animate-fade-in ${
                statusMessage.type === "success"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-300"
              }`}
            >
              {statusMessage.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              )}
              <span className="leading-snug">{statusMessage.text}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800/80 bg-[#070b14]/50">
          <button
            type="button"
            onClick={onClose}
            disabled={isExporting}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-violet-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isExporting ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin text-sky-300" />
                <span>Generating {selectedFormat.toUpperCase()}...</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4 text-violet-200" />
                <span>Generate & Download {selectedFormat.toUpperCase()}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
