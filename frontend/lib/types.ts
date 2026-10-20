// Shapes returned by the NetLinks API (see backend/app/api/*).

export type Role = "sme" | "buyer" | "admin";

export interface Identity {
  role: Role;
  sme_slug: string | null;
  label: string;
  name: string;
}

export interface AiModeSettings {
  mode: "cached" | "live";
  live_available: boolean;
  live_unavailable_reason: string | null;
  extraction_model_id: string | null;
  embedding_model_id: string | null;
}

export interface Sme {
  id: number;
  slug: string;
  name: string;
  base_town: string;
  province: string;
  size_band: string;
  employees?: number;
  consent_status?: "pending" | "granted" | "declined";
  consent_at?: string | null;
}

export interface DocumentInfo {
  id: number;
  sme_id: number;
  filename: string;
  doc_type: string | null;
  issue_date: string | null;
  period_end: string | null;
  uploaded_at: string;
  uploaded_by_role: string;
  superseded_by_document_id: number | null;
  page_count: number;
}

export type SourceType = "ai_extracted" | "sme_confirmed" | "verified";

export interface Candidate {
  id: number;
  field_key: string;
  value: unknown;
  source_type: SourceType;
  document_id: number | null;
  source_label: string | null;
  page: number | null;
  span_start: number | null;
  span_end: number | null;
  quote: string | null;
  confidence: number | null;
  status: string;
  created_at: string;
  created_by_role: string;
  note: string | null;
  badge: string;
}

export interface ProfileField {
  field_key: string;
  label: string;
  status: "ok" | "missing" | "conflict" | "low_confidence";
  value: unknown;
  source_type: SourceType | null;
  badge: string | null;
  confidence: number | null;
  low_confidence: boolean;
  conflict: boolean;
  selected: Candidate | null;
  candidates: Candidate[];
}

export interface Profile {
  sme: Sme;
  fields: ProfileField[];
  conflicts: string[];
  low_confidence: string[];
  documents: DocumentInfo[];
}

export interface Evidence {
  field_key: string | null;
  value: unknown;
  source_type: SourceType | null;
  source_label: string | null;
  document_id: number | null;
  doc_type: string | null;
  page: number | null;
  span_start: number | null;
  span_end: number | null;
  quote: string | null;
  confidence: number | null;
  candidate_id: number | null;
}

export type Outcome = "pass" | "needs_review" | "fail";
export type MatchStatus = "eligible" | "needs_review" | "not_eligible";

export interface ConflictValue {
  value: unknown;
  source: string;
  document_id: number | null;
  source_type: SourceType | null;
}

export interface Check {
  rule: string;
  label: string;
  outcome: Outcome;
  reason: string;
  evidence: Evidence[];
  group: "mandatory" | "consistency";
  issues: string[];
  details: {
    expiry_date?: string;
    closing_date?: string;
    conflicts?: { field_key: string; label: string; values: ConflictValue[] }[];
    [key: string]: unknown;
  };
}

export interface Component {
  name: string;
  label: string;
  score: number;
  weight: number;
  weighted: number;
  explanation: string;
  evidence: Evidence[];
  details: Record<string, unknown>;
}

export interface InfoRequest {
  id: number;
  opportunity_id: number;
  sme_id?: number;
  kind: "information" | "clarification";
  message: string;
  status: "open" | "responded";
  created_at: string;
  responded_at: string | null;
}

export interface MatchResult {
  sme: Sme;
  status: MatchStatus;
  rank: number | null;
  score_total: number;
  provisional: boolean;
  awaiting_sme: boolean;
  checks: Check[];
  components: Component[];
  info_requests: InfoRequest[];
}

export interface Counts {
  eligible: number;
  needs_review: number;
  not_eligible: number;
  considered?: number;
  excluded_no_consent?: number;
}

export interface MatchRun {
  id: number;
  opportunity_id: number;
  run_at: string;
  run_by_role: string;
  ai_mode: string;
  counts: Counts;
}

export interface ShortlistEntry {
  sme_slug: string;
  sme_name: string;
  position: number;
  engine_rank: number | null;
  status: MatchStatus | null;
  added_at: string;
}

export interface RunPayload {
  opportunity_id: number;
  run: MatchRun | null;
  groups: Record<MatchStatus, MatchResult[]>;
  shortlist: ShortlistEntry[];
}

export interface Criterion {
  rule_type: string;
  params: Record<string, unknown>;
  source_quote?: string | null;
}

export interface Weights {
  capability: number;
  experience: number;
  capacity: number;
  location: number;
}

export interface OpportunitySummary {
  id: number;
  title: string;
  buyer_org: string;
  buyer_contact: string;
  status: string;
  closing_date: string;
  contract_start: string;
  latest_run: MatchRun | null;
}

export interface OpportunityDetail extends OpportunitySummary {
  description: string;
  raw_rfq_text: string;
  weights: Weights;
  mandatory_criteria: Criterion[];
  preferred_criteria: Criterion[];
  capability_text: string;
}

export interface StructureResult {
  ai_result_id: number;
  provider: string;
  model_id: string;
  generated_by: string;
  generated_at: string;
  cache_hit: boolean;
  proposal: {
    title: string;
    closing_date: string;
    capability_text: string;
    mandatory_criteria: Criterion[];
    preferred_criteria: Criterion[];
  };
}

export interface AuditEntry {
  id: number;
  at: string;
  actor_role: string;
  actor_label: string;
  action: string;
  entity_type: string;
  entity_id: number | string | null;
  details: Record<string, unknown>;
  reason: string | null;
}

/** GET /api/audit?page=N&page_size=M (newest first when paginated). */
export interface AuditPage {
  entries: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
  order: string;
}

/** Paginated list envelope, e.g. GET /api/opportunities?page=N&page_size=M. */
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReadinessOpportunity {
  opportunity_id: number;
  title: string;
  buyer_org: string;
  closing_date: string;
  run_id: number | null;
  run_at: string | null;
  status: MatchStatus | null;
  awaiting_sme: boolean;
  checks: Check[];
  actions: { category: string; text: string }[];
}

export interface Readiness {
  sme: Sme;
  requests: (InfoRequest & { opportunity_title: string | null; buyer_org: string | null })[];
  opportunities: ReadinessOpportunity[];
}

export interface DocumentText extends DocumentInfo {
  sme_slug: string;
  sme_name: string;
  pages: string[];
}

export interface GroupRow {
  group: string;
  label: string;
  total: number;
  eligible: number;
  needs_review: number;
  not_eligible: number;
}

export interface Dashboard {
  pipeline: {
    opportunity_id: number;
    title: string;
    run_count: number;
    before: { run_id: number; run_at: string; counts: Counts };
    after: { run_id: number; run_at: string; counts: Counts };
  }[];
  readiness_gaps: { label: string; smes: number; open: number }[];
  requested_skills: { tag: string; label: string; count: number }[];
  decisions: {
    shortlisted: number;
    info_requests: number;
    overrides: {
      count: number;
      items: {
        at: string;
        actor_label: string;
        opportunity_id: number;
        reason: string;
        order: string[];
        engine_ranking: string[];
      }[];
    };
  };
  fairness: {
    run_id: number | null;
    opportunity_id: number | null;
    total: number;
    small_sample: boolean;
    note: string;
    by_province: GroupRow[];
    by_size_band: GroupRow[];
  } | null;
}
