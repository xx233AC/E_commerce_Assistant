export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export type Entity = { [key: string]: unknown; id?: string; version?: number }
export type Role = 'admin' | 'operator' | 'viewer'
export interface User extends Entity { id: string; username: string; display_name: string; role: Role; status: 'active' | 'disabled' }
export interface ApiMeta { request_id: string; page?: number; page_size?: number; total?: number; total_pages?: number }
export interface ApiResponse<T = Entity> { data: T; meta: ApiMeta }
export interface ErrorDetail { field: string | null; row_number: number | null; code: string; message: string }
export interface ErrorBody { code: string; message: string; details: ErrorDetail[]; retryable: boolean }
export interface Schema {
  $ref?: string; type?: string; description?: string; format?: string; enum?: (string | number)[];
  pattern?: string; default?: unknown; properties?: Record<string, Schema>; required?: string[];
  items?: Schema; anyOf?: Schema[]; oneOf?: Schema[]; allOf?: Schema[];
  minLength?: number; maxLength?: number; minimum?: number; maximum?: number;
  minItems?: number; maxItems?: number; minProperties?: number; const?: unknown;
  additionalProperties?: boolean; [key: string]: unknown;
}
export interface Parameter { name: string; in: string; required?: boolean; description?: string; schema: Schema }
export interface Operation {
  id: string; method: string; path: string; title: string; roles: string[]; permission: string;
  origin: string; parameters: Parameter[]; body: string | null; concurrency: boolean;
  idempotent: boolean; responses: string[];
}
