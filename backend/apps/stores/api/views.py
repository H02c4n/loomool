from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.stores.models import Store
from apps.stores.permissions import IsStoreMember

from .serializers import StoreDetailSerializer, StoreListSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def store_list_view(request):
    """
    List stores the requester can see.

    Anonymous -> blocked by IsAuthenticated.
    SUPER_ADMIN -> all stores.
    Everyone else -> owned stores + membership stores.
    """
    qs = Store.objects.for_user(request.user).order_by("name")
    serializer = StoreListSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStoreMember])
def store_detail_view(request, store_id):
    """
    Detail for a single store.

    Another seller's store => 404 (spec 0.2 §3b), never 403.
    """
    store = Store.objects.for_user(request.user).filter(id=store_id).first()
    if store is None:
        return Response(
            {"detail": "Not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # has_object_permission is invoked by DRF when using generic views;
    # with @api_view we enforce it explicitly for defence in depth.
    if not IsStoreMember().has_object_permission(request, None, store):
        return Response(
            {"detail": "Not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = StoreDetailSerializer(store, context={"request": request})
    return Response(serializer.data)
