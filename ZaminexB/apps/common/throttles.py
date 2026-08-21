from rest_framework.throttling import AnonRateThrottle


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"
