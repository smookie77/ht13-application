"""Ticket PDF rendering.

WeasyPrint over ReportLab: the ticket is laid out as HTML/CSS in a Django
template, so changing the design is a template edit rather than a rewrite of
drawing coordinates, and the same markup can be previewed in a browser.
"""

import base64
import io
import logging

import qrcode
from django.template.loader import render_to_string
from weasyprint import HTML

logger = logging.getLogger(__name__)


def qr_data_uri(payload: str) -> str:
    """QR as an inline data URI.

    Embedding it avoids WeasyPrint making a network fetch mid-render, which
    would make PDF generation depend on the web server being reachable.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    buffer = io.BytesIO()
    qr.make_image(fill_color="#0f172a", back_color="white").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def render_ticket_pdf(context: dict) -> bytes:
    """Render one ticket to PDF bytes."""
    html = render_to_string("tickets/ticket.html", context)
    pdf = HTML(string=html).write_pdf()
    logger.info("Rendered ticket PDF (%s bytes)", len(pdf))
    return pdf
