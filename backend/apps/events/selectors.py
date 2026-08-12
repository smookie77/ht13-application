"""Read-side helpers.

Kept out of views and serializers so the same payload can be produced by the
HTTP endpoint and by the WebSocket broadcaster without duplication.
"""

from .models import Event


def availability_payload(event: Event) -> dict:
    ticket_types = [
        {
            "id": tt.id,
            "name": tt.name,
            "quantity_available": tt.quantity_available,
            "quantity_total": tt.quantity_total,
            "is_sold_out": tt.is_sold_out,
        }
        for tt in event.ticket_types.all()
    ]
    return {
        "slug": event.slug,
        "sales_state": event.sales_state,
        "tickets_available": event.tickets_available,
        "tickets_total": event.tickets_total,
        "ticket_types": ticket_types,
    }
