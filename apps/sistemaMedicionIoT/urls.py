from django.urls import path

from .views import MeasurementCreateAPIView


urlpatterns = [

    path(
        "measurements/",
        MeasurementCreateAPIView.as_view(),
        name="measurement-create",
    ),

]