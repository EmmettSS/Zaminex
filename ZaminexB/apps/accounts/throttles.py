from apps.common.throttles import ResilientAnonRateThrottle

from .login_security import _client_ip


class SmsAnonRateThrottle(ResilientAnonRateThrottle):
    def get_ident(self, request) -> str:
        return _client_ip(request) or "anonymous"


class SmsRequestRateThrottle(SmsAnonRateThrottle):
    scope = "sms_request"


class SmsVerifyRateThrottle(SmsAnonRateThrottle):
    scope = "sms_verify"
