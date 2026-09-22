# backend/billing/pdf.py

"""
Invoice and payment-receipt PDF generation via ReportLab — pure Python,
no system-level dependencies (unlike WeasyPrint's Cairo/Pango), which
keeps the Docker image simple.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()
_TABLE_STYLE = TableStyle(
    [
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#223330")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCE3DF")),
    ]
)


def _build_pdf(elements) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    doc.build(elements)
    return buffer.getvalue()


def _header(title: str, subtitle: str) -> list:
    return [
        Paragraph("Dime PMS", _STYLES["Title"]),
        Paragraph(title, _STYLES["Heading2"]),
        Paragraph(subtitle, _STYLES["Normal"]),
        Spacer(1, 10 * mm),
    ]


def _details_table(rows: list) -> Table:
    table = Table(rows, colWidths=[55 * mm, 100 * mm])
    table.setStyle(_TABLE_STYLE)
    return table


def render_invoice_pdf(invoice) -> bytes:
    lease = invoice.lease
    landlord = lease.unit.property.landlord
    credential = getattr(landlord, "daraja_credential", None)

    elements = _header(
        f"Invoice {invoice.reference}",
        f"Billing period {invoice.period_start} – {invoice.period_end}",
    )
    elements.append(
        _details_table(
            [
                ["Tenant", lease.tenant.full_name],
                ["Property", f"{lease.unit.property.name} — {lease.unit.label}"],
                ["Landlord", landlord.full_name],
                ["Due date", str(invoice.due_date)],
                ["Status", invoice.get_status_display()],
                ["Amount due", f"KES {invoice.amount_due:,.2f}"],
                ["Amount paid", f"KES {invoice.amount_paid:,.2f}"],
                ["Balance", f"KES {invoice.amount_due - invoice.amount_paid:,.2f}"],
            ]
        )
    )
    elements.append(Spacer(1, 10 * mm))
    if credential:
        elements.append(
            Paragraph(
                f"Pay via M-Pesa Paybill {credential.shortcode}, Account Number {invoice.reference}.",
                _STYLES["Normal"],
            )
        )

    return _build_pdf(elements)


def render_receipt_pdf(payment) -> bytes:
    invoice = payment.invoice
    lease = invoice.lease

    elements = _header("Payment Receipt", f"Receipt for {payment.mpesa_transaction_id}")
    elements.append(
        _details_table(
            [
                ["Tenant", lease.tenant.full_name],
                ["Property", f"{lease.unit.property.name} — {lease.unit.label}"],
                ["Invoice reference", invoice.reference],
                ["M-Pesa transaction ID", payment.mpesa_transaction_id],
                ["Amount paid", f"KES {payment.amount:,.2f}"],
                ["Received at", payment.received_at.strftime("%Y-%m-%d %H:%M")],
            ]
        )
    )
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("Thank you for your payment.", _STYLES["Normal"]))

    return _build_pdf(elements)
