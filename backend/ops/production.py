"""
Production batches: PLANNED → RAW_MATERIALS_READY → IN_PRODUCTION → QC_TESTING → PACKAGING → COMPLETED.

Completing a batch adds its output to stock exactly once (row lock + status check inside one
transaction), logs a PRODUCTION_IN movement and re-checks the item's alerts, so
'Production needed' / 'Low stock' clear themselves when the new stock is enough.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from .inventory import StockError, adjust_stock, evaluate_alerts
from .models import InventoryItem, ProductionBatch, StockMovement

S = ProductionBatch.Status


def _new_code(today):
    prefix = f"PB-{today:%y%m%d}-"
    n = ProductionBatch.objects.filter(batch_code__startswith=prefix).count() + 1
    return f"{prefix}{n:03d}"


def create_batch(item, planned_quantity, user=None, *, assigned_to=None, start_date=None, expected_completion_date=None,
                 expiry_date=None, notes=""):
    if int(planned_quantity) < 1:
        raise StockError("Planned quantity must be at least 1.")
    today = timezone.localdate()
    for _ in range(5):  # retry if two batches are created in the same instant
        try:
            with transaction.atomic():
                batch = ProductionBatch.objects.create(
                    batch_code=_new_code(today), item=item, planned_quantity=int(planned_quantity), created_by=user,
                    assigned_to=assigned_to, start_date=start_date or today, expected_completion_date=expected_completion_date,
                    expiry_date=expiry_date, notes=notes or "",
                )
                evaluate_alerts(InventoryItem.objects.get(pk=item.pk))  # a planned batch clears 'Production needed'
                return batch
        except IntegrityError:
            continue
    raise StockError("Could not create a batch number — please try again.")


def move_batch(batch_id, new_status, user=None, *, completed_quantity=None, wastage_quantity=None, notes=None):
    new_status = S(new_status)
    with transaction.atomic():
        batch = ProductionBatch.objects.select_for_update().select_related("item").get(pk=batch_id)
        if batch.status in (S.COMPLETED, S.CANCELLED):
            raise StockError(f"Batch {batch.batch_code} is already {batch.get_status_display().lower()}.")
        if new_status == batch.status:
            raise StockError("The batch is already at this stage.")
        if notes:
            batch.notes = (batch.notes + "\n" if batch.notes else "") + f"[{timezone.localtime():%d %b %H:%M}] {notes.strip()}"
        if wastage_quantity is not None:
            if int(wastage_quantity) < 0:
                raise StockError("Wastage can't be negative.")
            batch.wastage_quantity = int(wastage_quantity)

        if new_status == S.COMPLETED and not batch.item_id:
            raise StockError("This batch's product was deleted, so it can only be cancelled.")
        if new_status == S.COMPLETED:
            qty = int(completed_quantity if completed_quantity is not None else batch.planned_quantity)
            if qty < 1:
                raise StockError("Enter how many good pieces this batch produced.")
            batch.completed_quantity = qty
            batch.completed_at = timezone.now()
            batch.status = S.COMPLETED
            batch.save()
            adjust_stock(batch.item, StockMovement.Kind.PRODUCTION_IN, qty, f"Production batch {batch.batch_code} completed",
                         user, batch_number=batch.batch_code, production_batch=batch)
            if batch.expiry_date:  # the fresh lot is now the one on the shelf
                InventoryItem.objects.filter(pk=batch.item_id).update(batch_number=batch.batch_code, expiry_date=batch.expiry_date)
                evaluate_alerts(InventoryItem.objects.get(pk=batch.item_id))
        else:
            batch.status = new_status
            batch.save()
            if new_status == S.CANCELLED:
                evaluate_alerts(InventoryItem.objects.get(pk=batch.item_id))  # 'Production needed' may come back
    return batch
