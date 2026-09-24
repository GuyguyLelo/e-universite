from django.shortcuts import redirect


class EspaceEtudiantMiddleware:
    """Un étudiant non personnel reste dans son espace personnel."""

    PREFIXES_AUTORISES = (
        "/students/mon-espace",
        "/accounts/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_staff or user.is_superuser:
            return self.get_response(request)
        if not hasattr(user, "student_profile"):
            return self.get_response(request)
        path = request.path or ""
        if any(path.startswith(prefix) for prefix in self.PREFIXES_AUTORISES):
            return self.get_response(request)
        return redirect("students:mon_espace")
