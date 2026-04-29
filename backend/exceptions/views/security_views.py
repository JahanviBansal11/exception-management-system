from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User, Group
from django.db.models import Prefetch

from exceptions.models import ExceptionRequest, AuditLog
from exceptions.permissions import IsSecurity
from .helpers import is_security

_ALLOWED_ROLES = {"Requestor", "Approver", "RiskOwner", "Security"}


class SecurityUsersView(APIView):
    """Security-only: list and create users."""
    permission_classes = [IsAuthenticated]

    def _check(self, request):
        if not is_security(request.user):
            raise PermissionDenied("Only Security team can administer users.")

    def get(self, request):
        self._check(request)
        users = User.objects.all().order_by("username")
        return Response({
            "roles": sorted(_ALLOWED_ROLES),
            "users": [
                {
                    "id": u.id, "username": u.username, "email": u.email,
                    "first_name": u.first_name, "last_name": u.last_name,
                    "is_active": u.is_active,
                    "roles": list(u.groups.values_list("name", flat=True)),
                }
                for u in users
            ],
        })

    def post(self, request):
        self._check(request)
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        email = (request.data.get("email") or "").strip()
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        roles = request.data.get("roles") or []
        is_active = bool(request.data.get("is_active", True))

        if not username:
            raise ValidationError({"username": "Username is required."})
        if not password:
            raise ValidationError({"password": "Password is required."})
        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": "Username already exists."})

        invalid = [r for r in roles if r not in _ALLOWED_ROLES]
        if invalid:
            raise ValidationError({"roles": f"Invalid roles: {', '.join(invalid)}"})

        user = User.objects.create_user(
            username=username, password=password, email=email,
            first_name=first_name, last_name=last_name, is_active=is_active,
        )
        if roles:
            user.groups.set([Group.objects.get_or_create(name=r)[0] for r in roles])

        return Response({"message": "User created.", "id": user.id}, status=201)


class SecurityUserDetailView(APIView):
    """Security-only: update an existing user."""
    permission_classes = [IsAuthenticated]

    def _check(self, request):
        if not is_security(request.user):
            raise PermissionDenied("Only Security team can administer users.")

    def patch(self, request, user_id):
        self._check(request)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError({"user": "User not found."})

        for field in ("email", "first_name", "last_name"):
            if field in request.data:
                setattr(user, field, (request.data[field] or "").strip())
        if "is_active" in request.data:
            user.is_active = bool(request.data["is_active"])
        if pw := request.data.get("password"):
            user.set_password(pw)
        if "roles" in request.data:
            roles = request.data["roles"] or []
            invalid = [r for r in roles if r not in _ALLOWED_ROLES]
            if invalid:
                raise ValidationError({"roles": f"Invalid roles: {', '.join(invalid)}"})
            user.groups.set([Group.objects.get_or_create(name=r)[0] for r in roles])

        user.save()
        return Response({"message": "User updated."})


class SecurityAuditTrailView(APIView):
    """Security-only: paginated audit trail with optional filters."""
    permission_classes = [IsAuthenticated, IsSecurity]

    def get(self, request):
        exc_id = request.query_params.get("exception_id")
        action_type = request.query_params.get("action_type")
        performed_by = request.query_params.get("performed_by")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            raise ValidationError({"error": "limit and offset must be integers."})
        if not (1 <= limit <= 200):
            raise ValidationError({"limit": "Must be between 1 and 200."})
        if offset < 0:
            raise ValidationError({"offset": "Must be >= 0."})

        qs = AuditLog.objects.select_related("exception_request", "performed_by").order_by("-timestamp")

        if exc_id:
            try:
                qs = qs.filter(exception_request_id=int(exc_id))
            except (TypeError, ValueError):
                raise ValidationError({"exception_id": "Must be an integer."})
        if action_type:
            valid = [c[0] for c in AuditLog.ACTION_CHOICES]
            if action_type not in valid:
                raise ValidationError({"action_type": f"Must be one of {valid}."})
            qs = qs.filter(action_type=action_type)
        if performed_by:
            qs = qs.filter(performed_by__username=performed_by)

        from datetime import datetime
        if start_date:
            try:
                qs = qs.filter(timestamp__gte=datetime.fromisoformat(start_date.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                raise ValidationError({"start_date": "Must be ISO format."})
        if end_date:
            try:
                qs = qs.filter(timestamp__lte=datetime.fromisoformat(end_date.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                raise ValidationError({"end_date": "Must be ISO format."})

        total = qs.count()
        logs = qs[offset: offset + limit]

        return Response({
            "count": total, "limit": limit, "offset": offset,
            "results": [
                {
                    "id": log.id,
                    "exception_id": log.exception_request_id,
                    "exception_short_description": log.exception_request.short_description
                                                   if log.exception_request else None,
                    "action_type": log.action_type,
                    "previous_status": log.previous_status,
                    "new_status": log.new_status,
                    "performed_by": log.performed_by.username if log.performed_by else None,
                    "performed_by_name": (log.performed_by.get_full_name() or log.performed_by.username)
                                         if log.performed_by else None,
                    "timestamp": log.timestamp.isoformat(),
                    "details": log.details or {},
                }
                for log in logs
            ],
        })


class SecurityAuditListView(APIView):
    """Security-only: exception list with last audit action summary."""
    permission_classes = [IsAuthenticated, IsSecurity]

    _SORT_MAP = {
        "latest": "-id", "oldest": "id",
        "id_asc": "id", "id_desc": "-id",
        "status_asc": ("status", "-id"), "status_desc": ("-status", "-id"),
        "risk_asc": ("risk_rating", "-id"), "risk_desc": ("-risk_rating", "-id"),
    }

    def get(self, request):
        sort_by = request.query_params.get("sort_by", "latest")
        try:
            limit = int(request.query_params.get("limit", 25))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            raise ValidationError({"error": "limit and offset must be integers."})
        if not (1 <= limit <= 200):
            raise ValidationError({"limit": "Must be between 1 and 200."})

        ordering = self._SORT_MAP.get(sort_by, "-id")
        audit_prefetch = Prefetch(
            "audit_logs",
            queryset=AuditLog.objects.select_related("performed_by").order_by("-timestamp"),
        )
        qs = ExceptionRequest.objects.prefetch_related(audit_prefetch)
        qs = qs.order_by(*ordering) if isinstance(ordering, tuple) else qs.order_by(ordering)

        total = qs.count()
        exceptions = qs[offset: offset + limit]

        results = []
        for exc in exceptions:
            logs = exc.audit_logs.all()  # uses prefetch cache
            last = logs[0] if logs else None
            results.append({
                "id": exc.id,
                "short_description": exc.short_description,
                "status": exc.status,
                "risk_rating": exc.risk_rating,
                "last_action": last.action_type if last else None,
                "performed_by": (last.performed_by.get_full_name() or last.performed_by.username)
                                if last and last.performed_by else None,
                "last_audit_timestamp": last.timestamp.isoformat() if last else None,
            })

        return Response({"count": total, "limit": limit, "offset": offset, "results": results})
