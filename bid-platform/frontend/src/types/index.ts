export type ID = string;
export type JsonObject = Record<string, unknown>;
export type ListResponse<T> = T[] | { items: T[]; total?: number };

export interface User {
  id: ID;
  username: string;
  display_name: string;
  global_role: 'system_admin' | 'config_admin' | 'editor' | 'reviewer' | 'viewer' | string;
  active: boolean;
}

export interface Task {
  id: ID;
  task_type: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | string;
  progress?: number;
  error_code?: string;
  created_at?: string;
  finished_at?: string;
}

export interface Project {
  id: ID;
  name: string;
  code: string;
  customer_name: string;
  procurement_type: string;
  status: string;
  owner_id: ID;
  version: number;
  created_at: string;
  updated_at?: string;
  source_project_id?: ID | null;
  package_name?: string;
  package?: string;
  config_refs?: {
    company_revision_id?: ID;
    product_revision_id?: ID;
    template_revision_id?: ID;
  };
}

export interface Revision {
  id: ID;
  revision_no: number;
  status: 'draft' | 'published' | 'archived' | string;
  fields_json?: JsonObject;
  technical_fields_json?: JsonObject;
  nodes_json?: TemplateNode[];
  content_json?: ContentBlock[];
  created_at?: string;
  published_by?: ID;
}

export interface Company {
  id: ID;
  code: string;
  name: string;
  status: string;
  revisions?: Revision[];
}

export interface Product {
  id: ID;
  code: string;
  name: string;
  status: string;
  revisions?: Revision[];
}

export interface AssetVariant {
  id: ID;
  asset_id: ID;
  code: string;
  name: string;
  description?: string;
  status: string;
  revisions?: Revision[];
}

export interface Asset {
  id: ID;
  code: string;
  title: string;
  asset_type: string;
  scope: string;
  industry?: string;
  product_id?: ID;
  customer_name?: string;
  owner_id?: ID;
  valid_from?: string;
  valid_to?: string;
  status: string;
  variants?: AssetVariant[];
}

export interface RedlineRule {
  id: ID;
  scope_type: 'company' | 'product';
  scope_id?: ID;
  category: string;
  position: string;
  condition_json: JsonObject;
  action: string;
  legal_review: boolean;
  revision_no: number;
  status: string;
}

export interface Template {
  id: ID;
  name: string;
  project_type: string;
  status: string;
  revisions?: Revision[];
}

export interface TemplateNode {
  id?: ID;
  key: string;
  title: string;
  locked: boolean;
  content_mode?: string;
  children?: TemplateNode[];
}

export type ContentBlock =
  | { id?: ID; type: 'paragraph' | 'heading'; text: string }
  | { id?: ID; type: 'list'; items: string[]; ordered?: boolean }
  | { id?: ID; type: 'table'; rows: string[][]; header?: string[] }
  | { id?: ID; type: 'fact_ref'; fact_key: string; label?: string; fallback_text?: string }
  | { id?: ID; type: 'attachment_ref'; attachment_id: ID; label?: string; status?: string }
  | { id?: ID; type: 'placeholder'; label: string; gap_id?: ID; placeholder_type?: string }
  | { id?: ID; type: 'tender_ooxml_ref'; anchor_key: string; label?: string; text?: string };

export interface SectionRevision {
  id: ID;
  section_id?: ID;
  revision_no: number;
  content_json: ContentBlock[];
  source_type: string;
  source_asset_revision_id?: ID;
  source_history_revision_id?: ID;
  created_by?: ID;
  created_at?: string;
  source_label?: string;
}

export type ContentStatus = 'empty' | 'ready' | 'gap' | string;
export type ReviewStatus = 'unconfirmed' | 'confirmed' | 'needs_review' | string;

export interface ProjectSection {
  id: ID;
  project_id: ID;
  parent_id: ID | null;
  position: number;
  title: string;
  section_key: string;
  source_type: string;
  locked: boolean;
  content_mode: 'group' | 'asset' | 'tender' | 'attachment' | 'manual' | string;
  selected_revision_id?: ID | null;
  selected_revision?: SectionRevision | null;
  current_revision?: SectionRevision | null;
  content_status: ContentStatus;
  review_status: ReviewStatus;
  version: number;
  candidate_count?: number;
}

export interface RequirementAnchor {
  anchor_key: string;
  quote: string;
}

export interface Requirement {
  id: ID;
  document_id: ID;
  code: string;
  category: string;
  response_type: string;
  text: string;
  normalized_json?: JsonObject;
  mandatory_level?: string;
  score_max?: number;
  status: 'original' | 'inferred' | 'missing' | 'needs_review' | string;
  confidence?: number;
  anchors?: RequirementAnchor[];
  section_id?: ID;
  mapping_status?: 'confirmed' | 'unconfirmed' | 'partial' | 'missing' | string;
  mapping_source?: string;
}

export interface Candidate {
  id: ID;
  section_id?: ID;
  candidate_type: string;
  candidate_id?: ID;
  name?: string;
  title?: string;
  revision_no?: number;
  revision_label?: string;
  source_label?: string;
  rank_score?: number;
  rank_reasons: string[];
  status: string;
  valid_from?: string;
  valid_to?: string;
  current?: boolean;
  recommended?: boolean;
  note?: string;
}

export interface DiffRow {
  type: 'unchanged' | 'added' | 'removed' | 'modified' | string;
  before_text?: string;
  after_text?: string;
  before?: ContentBlock | string;
  after?: ContentBlock | string;
}

export interface SectionDiff {
  section_id: ID;
  candidate_id: ID;
  current_revision_id?: ID;
  candidate_revision_id?: ID;
  current_label?: string;
  candidate_label?: string;
  changes: DiffRow[];
  impacted_sections?: Array<{ id: ID; title: string }>;
  fact_changes?: Array<{ fact_key: string; before?: unknown; after?: unknown }>;
}

export interface Gap {
  id: ID;
  project_id: ID;
  section_id?: ID;
  requirement_id?: ID;
  gap_type: string;
  title: string;
  blocking: boolean;
  status: 'open' | 'resolved' | 'closed' | string;
  resolved_by?: ID;
  resolution_json?: JsonObject;
}

export interface Risk {
  id: ID;
  project_id: ID;
  requirement_id?: ID;
  redline_rule_id?: ID;
  category: string;
  conflict_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical' | string;
  recommendation: string;
  legal_review: boolean;
  disposition?: 'pending' | 'accepted' | 'mitigated' | 'rejected' | 'resolved' | string;
  disposed_by?: ID;
  disposition_note?: string;
  requirement_text?: string;
}

export interface ScoreAssessment {
  id: ID;
  project_id?: ID;
  requirement_id: ID;
  score_min?: number;
  score_max?: number;
  evidence_json?: JsonObject | unknown[];
  gap_json?: JsonObject | unknown[];
  status: string;
  requirement_text?: string;
}

export interface ProjectFact {
  id: ID;
  project_id?: ID;
  fact_key: string;
  value_json: unknown;
  value_type: 'string' | 'number' | 'boolean' | 'date' | 'json' | string;
  source_type: string;
  source_id?: ID;
  status: 'unconfirmed' | 'confirmed' | 'conflict' | string;
  confirmed_by?: ID;
  version?: number;
}

export interface Activity {
  id: ID;
  actor_id?: ID;
  actor_name?: string;
  action: string;
  entity_type: string;
  entity_id: ID;
  detail_json?: JsonObject;
  created_at: string;
  section_id?: ID;
}

export interface ExportCheck {
  key: string;
  label: string;
  passed: boolean;
  blocking?: boolean;
  detail?: string;
}

export interface ExportReadiness {
  can_export_review: boolean;
  can_export_formal: boolean;
  checks: ExportCheck[];
  unconfirmed_sections?: number;
  open_blocking_gaps?: number;
  undisposed_risks?: number;
  current_snapshot_id?: ID;
}

export interface Snapshot {
  id: ID;
  project_id?: ID;
  snapshot_no: number;
  label?: string;
  created_by: ID;
  created_by_name?: string;
  created_at: string;
  formal_ready?: boolean;
  qa_json?: JsonObject;
}

export interface ExportTask {
  id: ID;
  project_id?: ID;
  snapshot_id: ID;
  snapshot_no?: number;
  export_kind: 'review' | 'formal';
  format: 'docx' | 'pdf';
  status: 'queued' | 'running' | 'succeeded' | 'failed' | string;
  qa_json?: JsonObject;
  file_id?: ID;
  error_code?: string;
  created_by?: ID;
  created_at?: string;
  finished_at?: string;
}

export interface WorkspaceData {
  project: Project;
  sections: ProjectSection[];
  requirements: Requirement[];
  gaps: Gap[];
  risks: Risk[];
  facts: ProjectFact[];
  tasks: Task[];
  activities?: Activity[];
  snapshots?: Snapshot[];
  export_readiness?: ExportReadiness;
}

export interface SourceAnchor {
  anchor_key: string;
  block_type?: string;
  text: string;
  quote?: string;
  page_no?: number;
  paragraph_index?: number;
  bbox_json?: number[];
  document_id?: ID;
  document_name?: string;
  outline_title?: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}
