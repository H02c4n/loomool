from rest_framework import serializers


class CreateCheckoutSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()


class CheckoutSessionResponseSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    session_id = serializers.CharField()
    checkout_url = serializers.CharField()
