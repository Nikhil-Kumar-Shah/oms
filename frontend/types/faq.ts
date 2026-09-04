/**
 * FAQ Domain Types
 * Matches backend schemas in app/schemas/faq.py
 */

export type FAQStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface FAQResponse {
  id: string;
  question: string;
  answer: string;
  category: string;
  display_order: number;
  status: FAQStatus;
  target_audience: string;
  related_route?: string | null;
  route_label?: string | null;
  created_by_id?: string | null;
  created_by_username?: string | null;
  updated_by_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FAQCreate {
  question: string;
  answer: string;
  category?: string;
  display_order?: number;
  status?: FAQStatus;
  target_audience?: string;
  related_route?: string;
  route_label?: string;
}

export interface FAQUpdate {
  question?: string;
  answer?: string;
  category?: string;
  display_order?: number;
  status?: FAQStatus;
  target_audience?: string;
  related_route?: string;
  route_label?: string;
}

export interface FAQListResponse {
  total: number;
  items: FAQResponse[];
}
