import type {
  ArticleDraftOut,
  ContentRequestCreate,
  ContentRequestDetail,
  ContentRequestOut,
  HumanReviewOut,
  MeResponse,
  PublishingQueueOut,
  RewriteAccepted,
  ReviewDecision,
  SourceOut,
  SourceStatus,
  UsageSummaryOut,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  requestCode: (email: string) =>
    request<{ message: string }>("/auth/request-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  verifyCode: (email: string, code: string) =>
    request<{ message: string }>("/auth/verify-code", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),

  me: () => request<MeResponse>("/auth/me"),

  listRequests: () => request<ContentRequestOut[]>("/api/requests"),

  createRequest: (body: ContentRequestCreate) =>
    request<ContentRequestOut>("/api/requests", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getRequestDetail: (id: string) => request<ContentRequestDetail>(`/api/requests/${id}`),

  submitReview: (requestId: string, articleDraftId: string, decision: ReviewDecision, notes?: string) =>
    request<HumanReviewOut>(`/api/requests/${requestId}/review`, {
      method: "POST",
      body: JSON.stringify({ article_draft_id: articleDraftId, decision, notes: notes ?? null }),
    }),

  listPublishingQueue: () => request<PublishingQueueOut[]>("/api/publishing-queue"),

  scheduleQueueItem: (id: string, scheduledFor: string | null) =>
    request<PublishingQueueOut>(`/api/publishing-queue/${id}/schedule`, {
      method: "POST",
      body: JSON.stringify({ scheduled_for: scheduledFor }),
    }),

  cancelQueueItem: (id: string) =>
    request<PublishingQueueOut>(`/api/publishing-queue/${id}/cancel`, { method: "POST" }),

  retryQueueItem: (id: string) =>
    request<PublishingQueueOut>(`/api/publishing-queue/${id}/retry`, { method: "POST" }),

  setQueueItemStatus: (id: string, status: PublishingQueueOut["status"]) =>
    request<PublishingQueueOut>(`/api/publishing-queue/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  rewriteDraft: (draftId: string, instructions?: string) =>
    request<RewriteAccepted>(`/api/drafts/${draftId}/rewrite`, {
      method: "POST",
      body: JSON.stringify({ instructions: instructions?.trim() || null }),
    }),

  rewriteAdaptation: (adaptationId: string, instructions?: string) =>
    request<RewriteAccepted>(`/api/channel-adaptations/${adaptationId}/rewrite`, {
      method: "POST",
      body: JSON.stringify({ instructions: instructions?.trim() || null }),
    }),

  editDraft: (draftId: string, bodyMarkdown: string, title?: string | null) =>
    request<ArticleDraftOut>(`/api/drafts/${draftId}`, {
      method: "PUT",
      body: JSON.stringify({ body_markdown: bodyMarkdown, title: title ?? null }),
    }),

  getUsageSummary: () => request<UsageSummaryOut>("/api/usage/summary"),

  overrideSourceStatus: (
    requestId: string,
    sourceId: string,
    status: Extract<SourceStatus, "selected" | "discarded">,
    reason?: string
  ) =>
    request<SourceOut>(`/api/requests/${requestId}/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason: reason ?? null }),
    }),

  uploadAsset: async (file: File): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_URL}/api/uploads`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? detail;
      } catch {
        // not JSON — fall back to statusText
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<UploadResult>;
  },
};

export interface UploadResult {
  storage_path: string;
  url: string;
  content_type: string;
  size: number;
}
