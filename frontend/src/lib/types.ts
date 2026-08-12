export type SalesState = "upcoming" | "open" | "sold_out" | "closed";

export interface TicketType {
  id: number;
  name: string;
  description: string;
  price: number;
  price_minor: number;
  currency: string;
  quantity_total: number;
  quantity_available: number;
  max_per_order: number;
  is_sold_out: boolean;
}

export interface EventSummary {
  slug: string;
  title: string;
  tagline: string;
  city: string;
  venue_name: string;
  starts_at: string;
  hero_image_url: string;
  sales_state: SalesState;
  tickets_available: number;
  tickets_total: number;
}

export interface EventDetail extends EventSummary {
  description: string;
  venue_address: string;
  ends_at: string | null;
  doors_open_at: string | null;
  sales_open_at: string;
  sales_close_at: string;
  has_seating: boolean;
  ticket_types: TicketType[];
}

/** Stock snapshot, delivered over HTTP initially and over WebSocket afterwards. */
export interface Availability {
  slug: string;
  sales_state: SalesState;
  tickets_available: number;
  tickets_total: number;
  ticket_types: {
    id: number;
    name: string;
    quantity_available: number;
    quantity_total: number;
    is_sold_out: boolean;
  }[];
  /** How far the queue has moved. Present on WebSocket pushes only. */
  now_serving?: number;
  queue_length?: number;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_email_verified: boolean;
  date_joined: string;
}

export type ReservationStatus =
  | "queued"
  | "allocated"
  | "confirmed"
  | "rejected"
  | "expired"
  | "cancelled";

export interface Reservation {
  public_id: string;
  event_slug: string;
  event_title: string;
  ticket_type_name: string;
  quantity: number;
  status: ReservationStatus;
  failure_reason: string;
  sequence: number | null;
  /** People still ahead in line; null once the queue no longer applies. */
  position: number | null;
  seconds_left: number | null;
  created_at: string;
  allocated_at: string | null;
  expires_at: string | null;
  confirmed_at: string | null;
}
