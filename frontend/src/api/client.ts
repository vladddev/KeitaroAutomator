import type {
  AuthMe,
  CampaignCreatePayload,
  CampaignCreateResult,
  CampaignSummary,
  OfferItem,
  References,
  Stream,
} from "../types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `Ошибка сервера (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      } else if (Array.isArray(data?.detail)) {
        detail = data.detail.map((item: { msg?: string }) => item.msg || String(item)).join("; ");
      }
    } catch {
      // ignore non-json error body
    }

    if (response.status === 401 && path !== "/api/auth/login" && unauthorizedHandler) {
      unauthorizedHandler();
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export const api = {
  getMe: () => apiRequest<AuthMe>("/api/auth/me"),
  login: (apiKey?: string) =>
    apiRequest<AuthMe>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey?.trim() || null }),
    }),
  logout: () => apiRequest<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  getReferences: () => apiRequest<References>("/api/references"),
  searchOffers: (q: string, refresh = false) =>
    apiRequest<OfferItem[]>(
      `/api/offers?q=${encodeURIComponent(q)}&refresh=${refresh ? "true" : "false"}`
    ),
  getCampaigns: (q = "") =>
    apiRequest<CampaignSummary[]>(`/api/campaigns?q=${encodeURIComponent(q)}`),

  createCampaign: (payload: CampaignCreatePayload) =>
    apiRequest<CampaignCreateResult>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getStreams: (campaignKeitaroId: number) =>
    apiRequest<Stream[]>(`/api/campaigns/${campaignKeitaroId}/streams`),
  fetchStreams: (campaignKeitaroId: number) =>
    apiRequest<Stream[]>(`/api/campaigns/${campaignKeitaroId}/fetch-streams`, {
      method: "POST",
    }),

  addOffer: (streamId: number, offerId: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/offers`, {
      method: "POST",
      body: JSON.stringify({ offer_id: offerId }),
    }),
  removeOffer: (streamId: number, offerKeitaroId: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/offers/${offerKeitaroId}/remove`, {
      method: "POST",
    }),
  bringBackOffer: (streamId: number, offerKeitaroId: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/offers/${offerKeitaroId}/bring-back`, {
      method: "POST",
    }),
  pinOffer: (streamId: number, offerKeitaroId: number, isPinned: boolean, share?: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/offers/${offerKeitaroId}/pin`, {
      method: "PATCH",
      body: JSON.stringify({ is_pinned: isPinned, share: share ?? null }),
    }),
  pushStream: (streamId: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/push`, { method: "POST" }),
  cancelStream: (streamId: number) =>
    apiRequest<Stream>(`/api/streams/${streamId}/cancel`, { method: "POST" }),
};
