from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps._auth.permissions import any_of, permission

from .models import Measurement
from .serializers import MeasurementSerializer


@api_view(["GET", "POST"])
@permission_classes([
    any_of(
        permission(
            user=["Factory manager", "Store manager"],
            can=["see"],
        ),
        permission(
            user=["Bot"],
            can=["create"],
        ),
    ),
])
def measurements(request):

    if request.method == "GET":
        measurements = Measurement.objects.all()

        serializer = MeasurementSerializer(
            measurements,
            many=True,
        )

        return Response(
            {
                "success": True,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    if request.method == "POST":
        serializer = MeasurementSerializer(
            data=request.data,
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                {
                    "success": True,
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )