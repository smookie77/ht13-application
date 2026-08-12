import { ApiError, getAvailability, getEvent } from "./api";
import type { Availability, EventDetail } from "./types";

/** The one event this deployment sells. Multi-event routing is a later step. */
export const FEATURED_EVENT_SLUG = "hack-tues-13";

export type EventLoadResult =
  | { ok: true; event: EventDetail; availability: Availability }
  | { ok: false; hint: string };

/**
 * Shared loader for every page that renders the featured event, so the
 * fetch-and-degrade behaviour lives in exactly one place.
 */
export async function loadFeaturedEvent(): Promise<EventLoadResult> {
  try {
    const [event, availability] = await Promise.all([
      getEvent(FEATURED_EVENT_SLUG),
      getAvailability(FEATURED_EVENT_SLUG),
    ]);
    return { ok: true, event, availability };
  } catch (error) {
    return {
      ok: false,
      hint:
        error instanceof ApiError && error.status === 404
          ? "The demo event is missing. Run: python manage.py seed_demo --open-now"
          : "Could not reach the API. Is the Django server running on port 8000?",
    };
  }
}
