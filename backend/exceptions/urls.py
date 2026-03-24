from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    ExceptionRequestViewSet,
    ReferenceDataView,
    WorklistSummaryView,
    WorklistNotificationsView,
    SecurityUsersView,
    SecurityUserDetailView,
)

router = DefaultRouter()
router.register(r'exceptions', ExceptionRequestViewSet, basename="exceptions")

urlpatterns = router.urls + [
    path('reference/', ReferenceDataView.as_view(), name='reference_data'),
    path('worklist/summary/', WorklistSummaryView.as_view(), name='worklist_summary'),
    path('worklist/notifications/', WorklistNotificationsView.as_view(), name='worklist_notifications'),
    path('security/users/', SecurityUsersView.as_view(), name='security_users'),
    path('security/users/<int:user_id>/', SecurityUserDetailView.as_view(), name='security_user_detail'),
]
