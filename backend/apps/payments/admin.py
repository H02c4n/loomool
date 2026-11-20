from django.contrib import admin, messages

from apps.payments import services
from apps.payments.models import Payment, PaymentEvent, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "status",
        "amount_cents",
        "currency",
        "checkout_session_id",
        "payment_intent_id",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "id",
        "order__id",
        "checkout_session_id",
        "payment_intent_id",
    )
    readonly_fields = (
        "id",
        "order",
        "checkout_session_id",
        "payment_intent_id",
        "amount_cents",
        "currency",
        "status",
        "created_at",
        "updated_at",
    )
    actions = ["refund_full_action"]

    @admin.action(description="Refund full amount via Stripe (irreversible)")
    def refund_full_action(self, request, queryset):
        for payment in queryset:
            try:
                services.refund_payment(
                    payment=payment,
                    actor=request.user,
                    reason="admin_full_refund",
                )
                self.message_user(
                    request,
                    f"Refund requested for payment {payment.id}.",
                    messages.SUCCESS,
                )
            except services.PaymentNotRefundable as exc:
                self.message_user(
                    request,
                    f"Payment {payment.id} is not refundable (status: {exc.status}).",
                    messages.WARNING,
                )
            except services.AlreadyRefunded:
                self.message_user(
                    request,
                    f"Payment {payment.id} already refunded.",
                    messages.WARNING,
                )
            except services.StripeRefundError as exc:
                self.message_user(
                    request,
                    f"Stripe error for {payment.id}: {exc}",
                    messages.ERROR,
                )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "amount_cents",
        "status",
        "stripe_refund_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "payment__id", "stripe_refund_id")
    readonly_fields = (
        "id",
        "payment",
        "stripe_refund_id",
        "amount_cents",
        "reason",
        "status",
        "created_at",
    )


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = (
        "stripe_event_id",
        "event_type",
        "processed_at",
        "signature_valid",
        "created_at",
    )
    list_filter = ("event_type", "signature_valid")
    search_fields = ("stripe_event_id", "event_type")
    readonly_fields = (
        "stripe_event_id",
        "event_type",
        "payload",
        "processed_at",
        "signature_valid",
        "created_at",
    )
