"""Rate limits for the public SMS-login endpoints.

Both endpoints are anonymous, so they are throttled per client IP. The rates
are deliberately tight: requesting codes is cheap for the attacker (it costs
real SMS credit) and verifying codes is a brute-force surface.
"""

from rest_framework.throttling import AnonRateThrottle


class SmsRequestRateThrottle(AnonRateThrottle):
    scope = "sms_request"


class SmsVerifyRateThrottle(AnonRateThrottle):
    scope = "sms_verify"
