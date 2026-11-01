"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  X,
  FileText,
  FileSpreadsheet,
  FileCode,
  Download,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Layers,
  BarChart3,
  TrendingUp,
  Share2,
  Store,
  Brain,
  Database,
  UploadCloud,
} from "lucide-react";
import { api } from "@/lib/api";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  datasetName?: string;
  projectId?: string;
  hasActiveDataset?: boolean;
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

export function ExportModal({ isOpen, onClose, datasetName, projectId, hasActiveDataset }: ExportModalProps) {
  const [mounted, setMounted] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("pdf");
  const [selectedScope, setSelectedScope] = useState<string>("complete");
  const [customTitle, setCustomTitle] = useState<string>("");
  const [includeCharts, setIncludeCharts] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [activeDatasetInfo, setActiveDatasetInfo] = useState<{
    has_active_dataset: boolean;
    dataset_name?: string;
    project_id?: string;
    rows_count?: number;
    is_demo?: boolean;
  } | null>(null);
  const [isLoadingDataset, setIsLoadingDataset] = useState(false);

  // Client-side mount check for createPortal SSR safety
  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch or refresh active dataset on open
  useEffect(() => {
    if (!isOpen) {
      setStatusMessage(null);
      return;
    }

    if (projectId) {
      setActiveDatasetInfo({
        has_active_dataset: true,
        dataset_name: datasetName || "Saved Project",
        project_id: projectId,
      });
      return;
    }

    let isMounted = true;
    setIsLoadingDataset(true);
    api
      .getActiveDataset()
      .then((res) => {
        if (!isMounted) return;
        if (res && res.has_active_dataset && res.dataset_name) {
          setActiveDatasetInfo(res);
        } else if (datasetName) {
          setActiveDatasetInfo({
            has_active_dataset: hasActiveDataset !== false,
            dataset_name: datasetName,
            project_id: projectId,
          });
        } else {
          setActiveDatasetInfo(null);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        if (datasetName) {
          setActiveDatasetInfo({
            has_active_dataset: hasActiveDataset !== false,
            dataset_name: datasetName,
            project_id: projectId,
          });
        } else {
          setActiveDatasetInfo(null);
        }
      })
      .finally(() => {
        if (isMounted) setIsLoadingDataset(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, projectId, datasetName, hasActiveDataset]);

  // Prevent background dashboard scrolling when modal is open
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  // Handle Escape key to close modal
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isExporting) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isExporting, onClose]);

  if (!mounted || !isOpen) return null;

  const currentDatasetName = activeDatasetInfo?.dataset_name || datasetName;
  const currentProjectId = activeDatasetInfo?.project_id || projectId;
  const hasActiveData = Boolean(
    (activeDatasetInfo && activeDatasetInfo.has_active_dataset && currentDatasetName) ||
    projectId ||
    (datasetName && hasActiveDataset !== false)
  );

  const handleExport = async () => {
    try {
      setIsExporting(true);
      setStatusMessage(null);

      const result = await api.exportReport({
        format: selectedFormat,
        scope: selectedScope,
        project_id: currentProjectId || undefined,
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

  const modalContent = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/80 backdrop-blur-sm transition-opacity animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isExporting) {
          onClose();
        }
      }}
    >
      <div
        className="relative w-full max-w-2xl bg-[#0d1322] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-auto my-auto"
        style={{ maxHeight: "90dvh" }}
      >
        {/* 1. Fixed Modal Header */}
        <div className="shrink-0 flex items-center justify-between px-4 sm:px-6 py-3.5 sm:py-4 border-b border-slate-800/80 bg-[#070b14]/90 z-10">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 shrink-0">
              <Download className="h-4 sm:h-5 w-4 sm:w-5" />
            </div>
            <div className="min-w-0">
              <h2 id="export-modal-title" className="text-sm sm:text-base font-semibold text-white truncate">
                Export Analytical Report
              </h2>
              <p className="text-[11px] sm:text-xs text-slate-400 truncate max-w-[220px] sm:max-w-md">
                {isLoadingDataset ? (
                  "Checking active dataset..."
                ) : currentDatasetName ? (
                  `Active Dataset: ${currentDatasetName}${activeDatasetInfo?.rows_count ? ` (${activeDatasetInfo.rows_count.toLocaleString()} rows)` : ""}`
                ) : (
                  "No analyzed dataset currently active"
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isExporting}
            aria-label="Close export dialog"
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors disabled:opacity-50 shrink-0 ml-2"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 2. Scrollable Modal Content */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6 overscroll-contain custom-scrollbar">
          {/* Active Dataset Alert if none available */}
          {!isLoadingDataset && !hasActiveData && (
            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 animate-fade-in">
              <div className="flex items-start space-x-3">
                <AlertCircle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs leading-relaxed space-y-1.5 flex-1">
                  <p className="font-semibold text-white">No Analyzed Dataset Available for Export</p>
                  <p className="text-slate-300">
                    You have not uploaded or analyzed an NFT dataset yet. Reports require real analysis results to generate. Please upload your dataset in the Workspace or load demo data to enable report downloads.
                  </p>
                  <div className="pt-2 flex items-center space-x-3">
                    <Link
                      href="/dashboard/workspace"
                      onClick={onClose}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-xs transition-colors shadow-sm"
                    >
                      <UploadCloud className="h-3.5 w-3.5" />
                      <span>Go to Workspace & Upload</span>
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}
          {/* Format Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 sm:mb-2.5">
              1. Choose Export Format
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3">
              {FORMAT_OPTIONS.map((fmt) => {
                const Icon = fmt.icon;
                const isSelected = selectedFormat === fmt.id;
                return (
                  <button
                    key={fmt.id}
                    type="button"
                    onClick={() => setSelectedFormat(fmt.id)}
                    className={`relative p-3 sm:p-3.5 rounded-xl border text-left transition-all flex flex-col justify-between ${
                      isSelected
                        ? "bg-violet-950/30 border-violet-500 shadow-sm shadow-violet-500/10"
                        : "bg-[#070b14]/40 border-slate-800/80 hover:border-slate-700 hover:bg-[#070b14]/70"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <div className={`p-2 rounded-lg border bg-gradient-to-br ${fmt.color} shrink-0`}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs sm:text-sm font-semibold text-white flex items-center gap-1.5 truncate">
                            {fmt.title}
                            <span className="text-[10px] font-mono text-slate-400">{fmt.extension}</span>
                          </div>
                          <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 font-medium">
                            {fmt.badge}
                          </span>
                        </div>
                      </div>
                      <div
                        className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ml-2 transition-colors ${
                          isSelected ? "border-violet-500 bg-violet-600" : "border-slate-700 bg-transparent"
                        }`}
                      >
                        {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                    </div>
                    <p className="text-[11px] sm:text-xs text-slate-400 leading-relaxed">{fmt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Scope Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 sm:mb-2.5">
              2. Select Content Scope
            </label>
            <div className="relative">
              <select
                value={selectedScope}
                onChange={(e) => setSelectedScope(e.target.value)}
                className="w-full bg-[#070b14] border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors cursor-pointer"
              >
                {SCOPE_OPTIONS.map((sc) => (
                  <option key={sc.id} value={sc.id}>
                    {sc.label}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-[11px] text-slate-400 mt-1.5 ml-0.5">
              {SCOPE_OPTIONS.find((s) => s.id === selectedScope)?.desc}
            </p>
          </div>

          {/* Advanced Configurations */}
          <div className="space-y-3 pt-2 border-t border-slate-800/60">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Custom Document Title (Optional)
              </label>
              <input
                type="text"
                placeholder={currentDatasetName ? `NFT Market Intelligence Report — ${currentDatasetName}` : "Enter custom report title..."}
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                className="w-full bg-[#070b14] border border-slate-800 rounded-xl px-3.5 py-2 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            {selectedFormat !== "json" && (
              <label className="flex items-center space-x-2.5 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-700 bg-[#070b14] text-violet-600 focus:ring-violet-500 focus:ring-offset-0 cursor-pointer shrink-0"
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

        {/* 3. Fixed Modal Footer */}
        <div className="shrink-0 flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-t border-slate-800/80 bg-[#070b14]/90 z-10">
          <button
            type="button"
            onClick={onClose}
            disabled={isExporting}
            className="px-3.5 sm:px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting || isLoadingDataset || !hasActiveData}
            className="flex items-center space-x-2 px-4 sm:px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-violet-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isExporting ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin text-sky-300" />
                <span>Generating {selectedFormat.toUpperCase()}...</span>
              </>
            ) : !hasActiveData ? (
              <>
                <AlertCircle className="h-4 w-4 text-amber-300" />
                <span>Upload Dataset to Export</span>
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

  return createPortal(modalContent, document.body);
}
