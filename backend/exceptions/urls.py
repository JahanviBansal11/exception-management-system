from rest_framework.routers import DefaultRouter
from .views import ExceptionViewSet

router = DefaultRouter()
router.register(r'exceptions', ExceptionViewSet, basename="exceptions")

urlpatterns = router.urls
