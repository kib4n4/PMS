# backend/accounts/phone.py

"""
Shared phone-number normalization — User.phone_number is stored E.164
("+2547XXXXXXXX"), but inbound payloads from Safaricom (MSISDN) and Meta
(WhatsApp webhook "from") both arrive without the leading "+". Previously
this normalization existed only in billing/tasks.py (for M-Pesa) and
nowhere in the WhatsApp inbound path at all — meaning an inbound WhatsApp
message's phone number (e.g. "254711000001") would never exact-match a
tenant stored as "+254711000001", silently failing tenant lookup.
"""


def normalize_msisdn(msisdn: str) -> str:
    msisdn = str(msisdn).strip()
    return msisdn if msisdn.startswith("+") else f"+{msisdn}"
