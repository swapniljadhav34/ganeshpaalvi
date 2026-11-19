"""
Accounting: GST invoices, payments, expenses and the numbers the owner actually needs
(revenue vs expenses, receivables, GST collected vs paid, cash flow).

Money is always Decimal, rounded half-up to paise. Invoice numbers are gap-free per
Indian financial year (April–March), e.g. PAL/2026-27/0001.
"""

import csv
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.utils import timezone

from .models import Expense, Invoice, InvoiceLine, InvoiceSequence, PaymentRecord

PAISE = Decimal("0.01")
ZERO = Decimal("0.00")
INVOICE_PREFIX = "PAL"


class AccountingError(ValueError):
    pass


def money(x):
    return Decimal(x).quantize(PAISE, rounding=ROUND_HALF_UP)


def financial_year(d: date):
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def next_invoice_number(issue_date):
    fy = financial_year(issue_date)
    with transaction.atomic():
        seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(financial_year=fy)
        InvoiceSequence.objects.filter(pk=seq.pk).update(last_number=F("last_number") + 1)
        seq.refresh_from_db()
    return f"{INVOICE_PREFIX}/{fy}/{seq.last_number:04d}"


def line_amounts(quantity, unit_price, gst_rate, prices_include_tax):
    """(taxable value, tax) for one line."""
    gross = Decimal(quantity) * Decimal(unit_price)
    rate = Decimal(gst_rate) / 100
    taxable = gross / (1 + rate) if prices_include_tax else gross
    taxable = money(taxable)
    tax = money(gross - taxable) if prices_include_tax else money(taxable * rate)
    return taxable, tax


def recalc(invoice):
    subtotal = tax = ZERO
    for line in invoice.lines.all():
        subtotal += line.taxable_value
        tax += line.tax_amount
    if invoice.tax_mode == Invoice.TaxMode.INTER:
        invoice.igst, invoice.cgst, invoice.sgst = tax, ZERO, ZERO
    else:
        half = money(tax / 2)
        invoice.cgst, invoice.sgst, invoice.igst = half, tax - half, ZERO
    invoice.subtotal = subtotal
    invoice.total = subtotal + tax
    refresh_status(invoice, save=False)


def refresh_status(invoice, today=None, save=True):
    today = today or timezone.localdate()
    P = Invoice.PaymentStatus
    if invoice.total > 0 and invoice.amount_paid >= invoice.total:
        status = P.PAID
    elif invoice.due_date and invoice.due_date < today:
        status = P.OVERDUE
    elif invoice.amount_paid > 0:
        status = P.PARTIAL
    else:
        status = P.UNPAID
    invoice.payment_status = status
    if save:
        Invoice.objects.filter(pk=invoice.pk).update(payment_status=status)
    return status


def create_invoice(data, lines, user):
    if not lines:
        raise AccountingError("Add at least one line to the invoice.")
    issue = data.get("issue_date") or timezone.localdate()
    due = data.get("due_date") or issue
    if due < issue:
        raise AccountingError("The due date can't be before the invoice date.")
    with transaction.atomic():
        inv = Invoice.objects.create(number=next_invoice_number(issue), issue_date=issue, due_date=due, created_by=user,
                                     **{k: v for k, v in data.items() if k not in ("issue_date", "due_date")})
        for i, ln in enumerate(lines):
            taxable, tax = line_amounts(ln["quantity"], ln["unit_price"], ln["gst_rate"], inv.prices_include_tax)
            InvoiceLine.objects.create(invoice=inv, order=i, taxable_value=taxable, tax_amount=tax, **ln)
        recalc(inv)
        inv.save()
    return inv


def record_payment(invoice_id, amount, mode, user, *, reference_id="", paid_on=None, notes=""):
    amount = money(amount)
    if amount <= 0:
        raise AccountingError("Enter an amount greater than zero.")
    with transaction.atomic():
        inv = Invoice.objects.select_for_update().get(pk=invoice_id)
        if amount > inv.balance:
            raise AccountingError(f"That's more than the ₹{inv.balance:,.2f} still due on this invoice.")
        pay = PaymentRecord.objects.create(invoice=inv, amount=amount, mode=mode, reference_id=reference_id,
                                           paid_on=paid_on or timezone.localdate(), notes=notes, recorded_by=user)
        Invoice.objects.filter(pk=inv.pk).update(amount_paid=F("amount_paid") + amount)
        inv.refresh_from_db()
        refresh_status(inv)
    return pay


def refresh_overdue(today=None):
    """Nightly: unpaid invoices past their due date become OVERDUE."""
    today = today or timezone.localdate()
    return Invoice.objects.filter(due_date__lt=today, payment_status__in=[Invoice.PaymentStatus.UNPAID, Invoice.PaymentStatus.PARTIAL]) \
        .update(payment_status=Invoice.PaymentStatus.OVERDUE)


def _sum(qs, field):
    return qs.aggregate(v=Coalesce(Sum(field), Value(ZERO), output_field=DecimalField()))["v"]


def summary(start, end):
    invoices = Invoice.objects.filter(issue_date__range=(start, end))
    payments = PaymentRecord.objects.filter(paid_on__range=(start, end))
    expenses = Expense.objects.filter(spent_on__range=(start, end))
    open_inv = Invoice.objects.exclude(payment_status=Invoice.PaymentStatus.PAID)
    balance = F("total") - F("amount_paid")

    revenue_ex_tax = _sum(invoices, "subtotal")
    invoiced_total = _sum(invoices, "total")
    output_gst = _sum(invoices, "cgst") + _sum(invoices, "sgst") + _sum(invoices, "igst")
    received = _sum(payments, "amount")
    spent = _sum(expenses, "amount")
    input_gst = _sum(expenses, "gst_amount")

    def months(qs, date_field, value_field):
        rows = qs.annotate(m=TruncMonth(date_field)).values("m").annotate(v=Sum(value_field)).order_by("m")
        return {r["m"].strftime("%Y-%m"): r["v"] for r in rows}

    inv_m, rec_m, exp_m = months(invoices, "issue_date", "subtotal"), months(payments, "paid_on", "amount"), months(expenses, "spent_on", "amount")
    keys = sorted(set(inv_m) | set(rec_m) | set(exp_m))
    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "revenue": revenue_ex_tax,                       # invoiced, before GST
        "invoiced_total": invoiced_total,                # invoiced, incl. GST
        "cash_received": received,
        "expenses": spent,
        "net_profit_estimate": revenue_ex_tax - (spent - input_gst),
        "net_cashflow": received - spent,
        "receivables": {
            "total": _sum(open_inv.annotate(b=balance), "b"),
            "overdue": _sum(open_inv.filter(payment_status=Invoice.PaymentStatus.OVERDUE).annotate(b=balance), "b"),
            "wholesale": _sum(open_inv.filter(channel=Invoice.Channel.WHOLESALE).annotate(b=balance), "b"),
            "count": open_inv.count(),
        },
        "gst": {
            "cgst": _sum(invoices, "cgst"), "sgst": _sum(invoices, "sgst"), "igst": _sum(invoices, "igst"),
            "output": output_gst, "input": input_gst, "net_payable": output_gst - input_gst,
        },
        "expenses_by_category": [
            {"category": r["category"], "label": Expense.Category(r["category"]).label, "amount": r["v"]}
            for r in expenses.values("category").annotate(v=Sum("amount")).order_by("-v")
        ],
        "monthly": [{"month": k, "revenue": inv_m.get(k, ZERO), "received": rec_m.get(k, ZERO), "expenses": exp_m.get(k, ZERO)} for k in keys],
    }


# ---------------------------------------------------------------------------
# CSV export (safe against spreadsheet formula injection)
# ---------------------------------------------------------------------------
def safe_cell(v):
    """Text starting with = + - @ is treated as a formula by Excel — neutralise it."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return "" if v is None else v


def csv_response(filename, header, rows):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("﻿")  # Excel opens UTF-8 (₹) correctly with a BOM
    w = csv.writer(resp)
    w.writerow(header)
    for r in rows:
        w.writerow([safe_cell(c) for c in r])
    return resp


def export_csv(kind, start, end):
    if kind == "invoices":
        qs = Invoice.objects.filter(issue_date__range=(start, end)).order_by("issue_date", "number")
        return csv_response(f"invoices-{start}-{end}.csv",
                            ["Number", "Date", "Due", "Channel", "Customer", "GSTIN", "Taxable", "CGST", "SGST", "IGST", "Total", "Paid", "Balance", "Status"],
                            ([i.number, i.issue_date, i.due_date, i.get_channel_display(), i.customer_name, i.customer_gstin, i.subtotal,
                              i.cgst, i.sgst, i.igst, i.total, i.amount_paid, i.balance, i.get_payment_status_display()] for i in qs.iterator()))
    if kind == "payments":
        qs = PaymentRecord.objects.filter(paid_on__range=(start, end)).select_related("invoice").order_by("paid_on")
        return csv_response(f"payments-{start}-{end}.csv", ["Date", "Invoice", "Customer", "Amount", "Mode", "Reference", "Notes"],
                            ([p.paid_on, p.invoice.number, p.invoice.customer_name, p.amount, p.get_mode_display(), p.reference_id, p.notes]
                             for p in qs.iterator()))
    if kind == "expenses":
        qs = Expense.objects.filter(spent_on__range=(start, end)).order_by("spent_on")
        return csv_response(f"expenses-{start}-{end}.csv", ["Date", "Category", "Vendor", "Vendor GSTIN", "Amount", "GST", "Description", "Receipt"],
                            ([e.spent_on, e.get_category_display(), e.vendor, e.vendor_gstin, e.amount, e.gst_amount, e.description,
                              "yes" if e.receipt else "no"] for e in qs.iterator()))
    raise AccountingError("Unknown export.")
