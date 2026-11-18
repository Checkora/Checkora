class PlayerTimezoneMiddleware:
    """Remember the time zone a signed-in player's browser reports.

    app.js puts the IANA name in the `tz` cookie. Streak days are counted in
    that zone. The profile is written only when the zone changes, and the
    session remembers the last one written, so a normal request costs nothing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = request.COOKIES.get('tz', '')
        if (
            name
            and len(name) <= 64
            and request.user.is_authenticated
            and request.session.get('tz') != name
        ):
            from .models import UserProfile
            from .progression import zone_for

            if zone_for(name):
                UserProfile.objects.filter(user=request.user).update(timezone=name)
                request.session['tz'] = name
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Middleware to set secure HTTP headers on all responses.

    This implements recommendations from docs/SECURITY_HEADERS_AUDIT.md:
    1. Content-Security-Policy (CSP)
    2. Permissions-Policy
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # CSP policies matching the external domains loaded in the project
        csp_policies = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
            "img-src 'self' data: https://checkora.edward7780.com",
            "connect-src 'self'",
            "frame-src 'self'",
        ]
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = "; ".join(csp_policies)
        
        # Permissions-Policy to explicitly disable unused hardware features
        if "Permissions-Policy" not in response:
            response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        
        return response
