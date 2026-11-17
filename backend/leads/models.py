"""
Leads & Enquiries — every WhatsApp tap, form, AI hand-off and B2B request lands here.
"""

from django.db import models


class LeadInquiry(models.Model):
    class BuyerType(models.TextChoices):
        SHOPPER = "shopper", "Shopper"
        RETAILER = "retailer", "Retailer"
        CHEMIST = "chemist", "Chemist / Pharmacy"
        HOTEL = "hotel", "Hotel"
        SALON = "salon", "Salon / Spa"
        CORPORATE = "corporate", "Corporate Gifting"
        DISTRIBUTOR = "distributor", "Distributor"

    class Source(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email form"
        AI = "ai", "AI Care Guide"
        CONTACT = "contact", "Contact form"
        B2B = "b2b", "B2B form"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUOTED = "quoted", "Quoted"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    class Tier(models.TextChoices):
        RETAIL = "retail", "Retail"
        WHOLESALE = "wholesale", "Wholesale"

    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    business_name = models.CharField(max_length=140, blank=True)
    buyer_type = models.CharField(max_length=12, choices=BuyerType.choices, default=BuyerType.SHOPPER, db_index=True)
    city = models.CharField(max_length=80, blank=True)
    message = models.TextField(blank=True)

    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True)
    package = models.ForeignKey("catalog.PackageOption", on_delete=models.SET_NULL, null=True, blank=True)
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.RETAIL)
    quantity = models.PositiveIntegerField(null=True, blank=True)

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CONTACT, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    notes = models.TextField(blank=True, help_text="Private notes for your team — customers never see these.")
    page_url = models.CharField(max_length=400, blank=True, help_text="Page the visitor was on.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lead / enquiry"
        verbose_name_plural = "Leads & enquiries"
        indexes = [models.Index(fields=["status", "-created_at"], name="lead_status_new")]

    def __str__(self):
        who = self.name or self.business_name or self.phone or "Visitor"
        return f"{who} — {self.get_source_display()}"
