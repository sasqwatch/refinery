#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from fnmatch import fnmatch
from ipaddress import ip_address
from urllib.parse import urlparse

from . import PatternExtractor
from .. import RefineryCriticalException
from ...lib.patterns import indicators


class xtp(PatternExtractor):
    """
    Extract Patterns: Uses regular expressions to extract indicators from the
    input data and optionally filters these results heuristically. The unit is
    designed to extract indicators such as domain names and IP addresses, see
    below for a complete list. To extract data formats such as hex-encoded
    data, use `refinery.carve`.
    """

    _LEGITIMATE_HOSTS = [
        'adobe.com',
        'digicert.com',
        'google.com',
        'microsoft.com',
        'openssl.org',
        'openxmlformats.org',
        'symantec.com',
        'symauth.com',
        'symcb.com',
        'thawte.com',
        'verisign.com',
        'w3.org',
        'xmlsoap.org',
    ]

    _DOMAIN_WHITELIST = [
        'system.net',
        'wscript.shell',
    ]

    def interface(self, argp):
        argp.add_argument('-f', '--filter', action='store_true', help=(
            'If this setting is enabled, the xtp unit will attempt to reduce the number '
            'of false positives by certain crude heuristics.'))
        argp.add_argument('pattern', metavar='PATTERN', type=str, nargs='*',
            default=['hostname', 'url', 'email'], help=(
                'Choose the pattern to extract, defaults are hostname, url, and email. '
                'Use an asterix character to select all available patterns. The available '
                'patterns are: {}'.format(', '.join(p.name for p in indicators))
            )
        )
        return super().interface(argp)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        patterns = {
            p for name in self.args.pattern for p in indicators if fnmatch(p.name, name)
        }
        if indicators.hostname in patterns:
            patterns.remove(indicators.hostname)
            patterns.add(indicators.ipv4)
            patterns.add(indicators.domain)
        self.pattern = '|'.join(F'(?P<{p.name}>{p.value})' for p in patterns)
        self.log_debug(F'using pattern: {self.pattern}')
        self.pattern = re.compile(self.pattern.encode(self.codec))

    @classmethod
    def _check_match(cls, data, pos, name, value):
        if name == 'ipv4':
            ocets = [int(x) for x in value.split(B'.')]
            if ocets.count(0) >= 3:
                return None
            for area in (
                data[pos - 20 : pos + 20],
                data[pos * 2 - 40 : pos * 2 + 40 : 2],
                data[pos * 2 - 41 : pos * 2 + 39 : 2]
            ):
                if B'version' in area.lower():
                    return None
            ip = ip_address(value.decode(cls.codec))
            if not ip.is_global and not ip.is_private:
                return None
        elif name in ('url', 'socket', 'domain'):
            ioc = value.decode(cls.codec)
            if '://' not in ioc: ioc = F'TCP://{ioc}'
            host = urlparse(ioc).netloc.split(':', 1)[0].lower()
            if any(host.endswith(w) for w in cls._LEGITIMATE_HOSTS):
                return None
            if any(host == w for w in cls._DOMAIN_WHITELIST):
                return None
            hostparts = host.split('.')
            if len(hostparts) == 2 and hostparts[0] == 'this':
                return None
        elif name == 'path':
            if len(value) < 8:
                return None
            if len(value) > 16 and len(re.findall(RB'\\x\d\d', value)) > len(value) // 10:
                return None
        return value

    def process(self, data):
        whitelist = set()

        def check(match):
            for name, value in match.groupdict().items():
                if value is not None:
                    break
            else:
                raise RefineryCriticalException('Received empty match.')
            if value in whitelist:
                return None
            result = self._check_match(data, match.start(), name, value)
            if result is not None:
                return result
            whitelist.add(value)

        transforms = None if not self.args.filter else [check]
        yield from self.matches_processed(data, self.pattern, transforms)
