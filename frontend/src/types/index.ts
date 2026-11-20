export interface AuthMe {
  authenticated: boolean;
  mode: "default" | "custom" | null;
  key_hint: string | null;
  default_key_configured: boolean;
  default_campaign_prefix: string;
}

export interface ReferenceItem {
  id: number;
  name: string;
}

export interface References {
  domains: ReferenceItem[];
  groups: ReferenceItem[];
  traffic_sources: ReferenceItem[];
  defaults: {
    domain_id: number | null;
    group_id: number | null;
    traffic_source_id: number | null;
  };
}

export interface OfferItem {
  id: number;
  name: string;
  state: string | null;
}

export interface CampaignSummary {
  id: number;
  name: string;
  alias: string | null;
  state: string | null;
  domain_id: number | null;
  group_id: number | null;
  traffic_source_id: number | null;
}

export interface StreamOffer {
  id: number;
  offer_keitaro_id: number;
  offer_name: string;
  sort_order: number;
  published_status: "active" | "removed" | null;
  published_share: number | null;
  published_is_pinned: boolean;
  draft_status: "active" | "removed";
  draft_share: number;
  draft_is_pinned: boolean;
}

export interface Stream {
  id: number;
  keitaro_id: number;
  campaign_keitaro_id: number;
  name: string;
  position: number;
  stream_type: string;
  schema_name: string;
  has_offers: boolean;
  is_dirty: boolean;
  can_push: boolean;
  total_active_share: number;
  validation_errors: string[];
  synced_at: string;
  offers: StreamOffer[];
}

export interface CampaignCreatePayload {
  name: string;
  country: string;
  offer_id: number;
  domain_id: number | null;
  group_id: number | null;
  traffic_source_id: number | null;
}

export interface CampaignCreateResult {
  id: number;
  keitaro_id: number;
  name: string;
  alias: string | null;
  domain_id: number | null;
  group_id: number | null;
  traffic_source_id: number | null;
  streams: Stream[];
}
