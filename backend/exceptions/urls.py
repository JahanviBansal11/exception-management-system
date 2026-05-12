from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    ExceptionRequestViewSet,
    ReferenceDataView,
    WorklistSummaryView,
    WorklistNotificationsView,
    SecurityUsersView,
    SecurityUserDetailView,
    SecurityAuditTrailView,
    SecurityAuditListView,
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)

router = DefaultRouter()
router.register(r'exceptions', ExceptionRequestViewSet, basename="exceptions")

urlpatterns = router.urls + [
    path('reference/', ReferenceDataView.as_view(), name='reference_data'),
    path('worklist/summary/', WorklistSummaryView.as_view(), name='worklist_summary'),
    path('worklist/notifications/', WorklistNotificationsView.as_view(), name='worklist_notifications'),
    path('security/users/', SecurityUsersView.as_view(), name='security_users'),
    path('security/users/<int:user_id>/', SecurityUserDetailView.as_view(), name='security_user_detail'),
    path('security/audit-list/', SecurityAuditListView.as_view(), name='security_audit_list'),
    path('security/audit-trail/', SecurityAuditTrailView.as_view(), name='security_audit_trail'),
    path('notifications/', NotificationListView.as_view(), name='notifications_list'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notifications_unread_count'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notifications_mark_all_read'),
    path('notifications/<int:pk>/read/', NotificationMarkReadView.as_view(), name='notification_mark_read'),
]
