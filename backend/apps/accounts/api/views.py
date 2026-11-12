from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import MeSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(MeSerializer(request.user).data)
