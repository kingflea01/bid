import type {
  ApiErrorBody,
  Asset,
  AssetVariant,
  Candidate,
  Company,
  ContentBlock,
  ExportTask,
  Gap,
  ID,
  ListResponse,
  Product,
  Project,
  ProjectFact,
  RedlineRule,
  Requirement,
  Revision,
  Risk,
  ScoreAssessment,
  SectionDiff,
  SectionRevision,
  Snapshot,
  SourceAnchor,
  Task,
  Template,
  TemplateNode,
  User,
  WorkspaceData,
} from '../types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
export const AUTH_EXPIRED_EVENT = 'bid:auth-expired';

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  requestId?: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || `请求失败（${status}）`);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code || 'request_failed';
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

type RequestOptions = RequestInit & { skipAuthEvent?: boolean };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuthEvent, ...init } = options;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('Accept', 'application/json');

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { code: 'http_error', message: `请求失败（${response.status}）` };
    }
    if (response.status === 401 && !skipAuthEvent) {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return (await response.text()) as T;
  return (await response.json()) as T;
}

const json = (value: unknown): string => JSON.stringify(value);
const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', ...(body === undefined ? {} : { body: json(body) }) });
const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PATCH', body: json(body) });
const query = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : '';
};

export interface ProjectCreateInput {
  name: string;
  code: string;
  customer_name: string;
  procurement_type: string;
  package?: string;
  company_revision_id: ID;
  product_revision_id: ID;
  template_revision_id: ID;
  source_project_id?: ID;
}

export interface GapResolutionInput {
  resolution_type: 'text' | 'asset' | 'attachment';
  note: string;
  asset_revision_id?: ID;
  attachment_id?: ID;
}

export const api = {
  auth: {
    login: (username: string, password: string) =>
      request<User>('/auth/login', {
        method: 'POST',
        body: json({ username, password }),
        skipAuthEvent: true,
      }),
    me: () => request<User>('/auth/me', { skipAuthEvent: true }),
    logout: () => post<void>('/auth/logout'),
  },
  companies: {
    list: () => get<ListResponse<Company>>('/companies'),
    create: (input: Pick<Company, 'code' | 'name'> & { status?: string }) =>
      post<Company>('/companies', input),
    update: (id: ID, input: Partial<Pick<Company, 'code' | 'name' | 'status'>>) =>
      patch<Company>(`/companies/${id}`, input),
    createRevision: (id: ID, fields_json: Record<string, unknown>) =>
      post<Revision>(`/companies/${id}/revisions`, { fields_json }),
    publish: (revisionId: ID) => post<Revision>(`/company-revisions/${revisionId}:publish`),
  },
  products: {
    list: () => get<ListResponse<Product>>('/products'),
    create: (input: Pick<Product, 'code' | 'name'> & { status?: string }) =>
      post<Product>('/products', input),
    update: (id: ID, input: Partial<Pick<Product, 'code' | 'name' | 'status'>>) =>
      patch<Product>(`/products/${id}`, input),
    createRevision: (
      id: ID,
      input: { fields_json: Record<string, unknown>; technical_fields_json: Record<string, unknown> },
    ) => post<Revision>(`/products/${id}/revisions`, input),
    publish: (revisionId: ID) => post<Revision>(`/product-revisions/${revisionId}:publish`),
  },
  assets: {
    list: (params: { asset_type?: string; product_id?: ID; customer_name?: string } = {}) =>
      get<ListResponse<Asset>>(`/assets${query(params)}`),
    create: (input: Record<string, unknown>) => post<Asset>('/assets', input),
    createVariant: (id: ID, input: Pick<AssetVariant, 'code' | 'name' | 'description'>) =>
      post<AssetVariant>(`/assets/${id}/variants`, input),
    createRevision: (variantId: ID, content_json: ContentBlock[]) =>
      post<Revision>(`/variants/${variantId}/revisions`, {
        content_json,
        source_format: 'structured_blocks',
      }),
    publish: (revisionId: ID) => post<Revision>(`/asset-revisions/${revisionId}:publish`),
    uploadAttachment: (assetId: ID, file: File, attachmentType: string, validTo?: string) => {
      const body = new FormData();
      body.append('file', file);
      body.append('attachment_type', attachmentType);
      if (validTo) body.append('valid_to', validTo);
      return request<{ id: ID; file_id: ID }>(`/assets/${assetId}/attachments`, {
        method: 'POST',
        body,
      });
    },
  },
  redlines: {
    list: () => get<ListResponse<RedlineRule>>('/redline-rules'),
    create: (input: Record<string, unknown>) => post<RedlineRule>('/redline-rules', input),
    update: (id: ID, input: Record<string, unknown>) =>
      patch<RedlineRule>(`/redline-rules/${id}`, input),
  },
  templates: {
    list: () => get<ListResponse<Template>>('/templates'),
    revisions: (id: ID) => get<ListResponse<Revision>>(`/templates/${id}/revisions`),
    create: (input: Pick<Template, 'name' | 'project_type'> & { status?: string }) =>
      post<Template>('/templates', input),
    createRevision: (id: ID, nodes_json: TemplateNode[]) =>
      post<Revision>(`/templates/${id}/revisions`, { nodes_json }),
    publish: (revisionId: ID) => post<Revision>(`/template-revisions/${revisionId}:publish`),
  },
  projects: {
    list: (params: { keyword?: string; status?: string; page?: number; page_size?: number } = {}) =>
      get<ListResponse<Project>>(`/projects${query(params)}`),
    get: (id: ID) => get<Project>(`/projects/${id}`),
    create: (input: ProjectCreateInput) => post<Project>('/projects', input),
    uploadTender: (id: ID, file: File) => {
      const body = new FormData();
      body.append('file', file);
      body.append('document_type', 'tender');
      return request<{ id: ID; project_id: ID; status: string; page_count?: number }>(
        `/projects/${id}/tender-documents`,
        { method: 'POST', body },
      );
    },
    parse: (id: ID, version?: number) =>
      post<{ task_id?: ID; tasks?: Task[] }>(`/projects/${id}:parse`, { version }),
    analyze: (id: ID, version?: number) =>
      post<{ task_ids?: ID[]; tasks?: Task[] }>(`/projects/${id}:analyze`, { version }),
    resolveMapping: (id: ID, version?: number) =>
      post<{ task_id?: ID; status?: string; tasks?: Task[] }>(`/projects/${id}:resolve-mapping`, { version }),
    workspace: (id: ID) => get<WorkspaceData>(`/projects/${id}/workspace`),
    requirements: (id: ID) => get<ListResponse<Requirement>>(`/projects/${id}/requirements`),
    risks: (id: ID) => get<ListResponse<Risk>>(`/projects/${id}/risks`),
    scores: (id: ID) => get<ListResponse<ScoreAssessment>>(`/projects/${id}/score-assessments`),
    updateFact: (id: ID, factKey: string, input: { value_json: unknown; value_type: string; version?: number; status?: string }) =>
      patch<ProjectFact>(`/projects/${id}/facts/${encodeURIComponent(factKey)}`, input),
  },
  tasks: {
    get: (id: ID) => get<Task>(`/tasks/${id}`),
  },
  sources: {
    get: (documentId: ID, anchorKey: string) =>
      get<SourceAnchor>(`/tender-documents/${documentId}/anchors/${encodeURIComponent(anchorKey)}`),
  },
  sections: {
    update: (id: ID, input: { title?: string; version: number }) =>
      patch<import('../types').ProjectSection>(`/sections/${id}`, input),
    move: (id: ID, input: { parent_id: ID | null; position: number; version: number; project_version: number }) =>
      post<import('../types').ProjectSection>(`/sections/${id}:move`, input),
    candidates: (id: ID) => get<ListResponse<Candidate>>(`/sections/${id}/candidates`),
    diff: (id: ID, candidateId: ID) =>
      get<SectionDiff>(`/sections/${id}/diff${query({ candidate_id: candidateId })}`),
    selectVersion: (
      id: ID,
      input: { candidate_id: ID; version: number; project_version: number },
    ) => post<SectionRevision>(`/sections/${id}:select-version`, input),
    saveRevision: (
      id: ID,
      input: { content_json: ContentBlock[]; base_version: number; version: number },
    ) => post<SectionRevision>(`/sections/${id}/revisions`, input),
    confirm: (id: ID, input: { selected_revision_id?: ID | null; version: number }) =>
      post<import('../types').ProjectSection>(`/sections/${id}:confirm`, input),
  },
  gaps: {
    resolve: (id: ID, input: GapResolutionInput, file?: File) => {
      if (!file) return post<Gap>(`/gaps/${id}:resolve`, { resolution_json: input });
      const body = new FormData();
      body.append('resolution_json', json(input));
      body.append('file', file);
      return request<Gap>(`/gaps/${id}:resolve`, { method: 'POST', body });
    },
  },
  risks: {
    dispose: (id: ID, input: { disposition: string; disposition_note: string }) =>
      post<Risk>(`/risks/${id}:disposition`, input),
  },
  snapshots: {
    list: (projectId: ID) => get<ListResponse<Snapshot>>(`/projects/${projectId}/snapshots`),
    create: (projectId: ID, input: { label?: string; version: number }) =>
      post<Snapshot>(`/projects/${projectId}/snapshots`, input),
  },
  exports: {
    list: (projectId: ID) => get<ListResponse<ExportTask>>(`/projects/${projectId}/exports`),
    create: (
      projectId: ID,
      input: { snapshot_id: ID; export_kind: 'review' | 'formal'; format: 'docx' | 'pdf' },
    ) => post<ExportTask>(`/projects/${projectId}/exports`, input),
    get: (id: ID) => get<ExportTask>(`/exports/${id}`),
    download: async (id: ID, fileName: string) => {
      const response = await fetch(`${API_BASE}/exports/${id}/download`, { credentials: 'include' });
      if (!response.ok) {
        let body: ApiErrorBody;
        try {
          body = (await response.json()) as ApiErrorBody;
        } catch {
          body = { code: 'download_failed', message: '导出文件下载失败' };
        }
        throw new ApiError(response.status, body);
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },
  },
};
