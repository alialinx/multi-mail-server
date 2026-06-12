import re

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](-?[a-z0-9])*\.)+[a-z]{2,}$", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@(?=.{1,253}$)([a-z0-9](-?[a-z0-9])*\.)+[a-z]{2,}$", re.IGNORECASE)


def valid_domain(name):
    return bool(DOMAIN_RE.match(name))


def valid_email(address):
    return bool(EMAIL_RE.match(address))


def valid_alias_address(address):
    if address.startswith("@"):
        return valid_domain(address[1:])
    return valid_email(address)
