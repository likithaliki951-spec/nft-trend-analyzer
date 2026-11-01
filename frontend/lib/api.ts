/**
 * API client for communicating with the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("nft_auth_token");
}

export function setAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("nft_auth_token", token);
  }
}

export function clearAuthToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("nft_auth_token");
    localStorage.removeItem("nft_user");
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new Error(
      "Unable to connect to the server. Please verify that the backend service is running and accessible."
    );
  }

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // Use fallback error string
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  // Auth
  register: (body: any) => request<any>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: any) => request<any>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  getMe: () => request<any>("/auth/me"),
  forgotPassword: (email: string) => request<any>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (body: any) => request<any>("/auth/reset-password", { method: "POST", body: JSON.stringify(body) }),

  // Datasets & Automated Pipeline
  loadDemoDataset: () => request<any>("/analysis/dataset/demo"),
  uploadDataset: (formData: FormData) => request<any>("/analysis/dataset/upload", { method: "POST", body: formData }),
  joinDatasets: (formData: FormData) => request<any>("/analysis/dataset/join-upload", { method: "POST", body: formData }),
  pipelineUploadAndAnalyze: (formData: FormData) => request<any>("/analysis/pipeline/upload-and-analyze", { method: "POST", body: formData }),
  getActiveDataset: () => request<any>("/analysis/active-dataset"),
  getActiveModuleResults: (module: string) => request<any>(`/analysis/active-results/${encodeURIComponent(module)}`),

  // Section 1: Price Trends & Prediction
  getTimeSeries: (params: any = {}) => request<any>("/analysis/price-trends/time-series", { method: "POST", body: JSON.stringify(params) }),
  trainPredictionModels: (params: any = {}) => request<any>("/ml/predict-train", { method: "POST", body: JSON.stringify(params) }),

  // Section 2: Market Activity
  getMarketOverview: (params: any = {}) => request<any>("/analysis/market-activity/overview", { method: "POST", body: JSON.stringify(params) }),
  getValuationCategories: (params: any = {}) => request<any>("/ml/valuation-categories", { method: "POST", body: JSON.stringify(params) }),
  estimateSingleNFT: (params: any) => request<any>("/ml/valuation-estimate-single", { method: "POST", body: JSON.stringify(params) }),

  // Section 3: Social Engagement
  getSocialEngagement: (params: any = {}) => request<any>("/analysis/social-engagement", { method: "POST", body: JSON.stringify(params) }),

  // Section 4: Marketplace Hub
  getEthPrice: () => request<any>("/marketplace/eth-usd"),
  getCollectionStats: (slug: string) => request<any>(`/marketplace/collection-stats?slug=${encodeURIComponent(slug)}`),
  convertCurrency: (ethAmount: number) => request<any>("/marketplace/convert", { method: "POST", body: JSON.stringify({ eth_amount: ethAmount }) }),

  // Workspace
  listProjects: () => request<any[]>("/workspace/projects"),
  saveProject: (data: any) => request<any>("/workspace/projects", { method: "POST", body: JSON.stringify(data) }),
  reopenProject: (id: string) => request<any>(`/workspace/projects/${id}`),
  selectActiveProject: (id: string) => request<any>(`/workspace/select-active/${encodeURIComponent(id)}`, { method: "POST" }),
  deleteProject: (id: string) => request<any>(`/workspace/projects/${id}`, { method: "DELETE" }),

  // Admin
  getAdminTelemetry: () => request<any>("/admin/telemetry"),
  getAdminUsers: () => request<any[]>("/admin/users"),

  // Export Reports
  exportReport: (params: {
    format: "pdf" | "json" | "docx" | "xlsx";
    scope?: string;
    project_id?: string;
    custom_title?: string;
    include_charts?: boolean;
  }) => downloadReportFile(params),
  downloadBlob: (blob: Blob, filename: string) => triggerBrowserDownload(blob, filename),
};

export async function downloadReportFile(params: {
  format: "pdf" | "json" | "docx" | "xlsx";
  scope?: string;
  project_id?: string;
  custom_title?: string;
  include_charts?: boolean;
}): Promise<{ blob: Blob; filename: string }> {
  const token = getAuthToken();
  const headers = new Headers({
    "Content-Type": "application/json",
  });
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/analysis/export`, {
      method: "POST",
      headers,
      body: JSON.stringify(params),
    });
  } catch (err: any) {
    throw new Error(
      "Unable to connect to the export service. Please verify that the backend service is running."
    );
  }

  if (!res.ok) {
    let errorDetail = `Export failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // Use fallback
    }
    throw new Error(errorDetail);
  }

  const disposition = res.headers.get("Content-Disposition");
  let filename = `NFT_Trend_Analysis_Report.${params.format}`;
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename="?([^";]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  return { blob, filename };
}

export function triggerBrowserDownload(blob: Blob, filename: string): void {
  if (typeof window === "undefined") return;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }, 150);
}
