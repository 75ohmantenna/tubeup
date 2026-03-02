import os
import re
import tempfile
from collections import defaultdict


EMPTY_ANNOTATION_FILE = ('<?xml version="1.0" encoding="UTF-8" ?>'
                         '<document><annotations></annotations></document>')

# IP address patterns for scrubbing
# IPv4 pattern: matches standard IPv4 addresses (e.g., 192.168.1.1)
IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)

# IPv6 pattern: matches standard IPv6 addresses including compressed forms
# Matches full form (2001:0db8:85a3:0000:0000:8a2e:0370:7334)
# Matches compressed form (2001:db8:85a3::8a2e:370:7334)
# Matches localhost (::1)
# Matches IPv4-mapped IPv6 (::ffff:192.0.2.1)
IPV6_PATTERN = re.compile(
    r"(?:"
    # IPv4-mapped/translated IPv6 (must come first to avoid hex pattern matching the IPv4 part)
    r"::(?:ffff(?::0{1,4})?:)?(?:(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])\.){3}(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])|"
    # 2001:db8:3:4::192.0.2.33
    r"(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])\.){3}(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])|"
    # Link-local IPv6 with zone ID
    r"fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]+|"
    # Standard IPv6 formats
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|"
    r"[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|"
    r":(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|"
    r"(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r")(?![0-9a-fA-F:])",
    re.IGNORECASE,
)

# Backwards compatibility
IP_ADDRESS_PATTERN = IPV4_PATTERN

# All text sidecar extensions produced by yt-dlp that must be scrubbed of IP
# addresses before upload. Kept in one place so coverage never drifts.
# .info.json is handled separately (loaded as JSON, scrubbed, written back).
TEXT_SIDECAR_EXTENSIONS = (
    '.description',
    '.srt', '.vtt', '.sbv', '.sub', '.ass', '.ssa', '.lrc',
    '.annotations.xml',
)


def key_value_to_dict(lst):
    """
    Convert many key:value pair strings into a python dictionary
    """
    if not isinstance(lst, list):
        lst = [lst]

    result = defaultdict(list)
    for item in lst:
        key, value = item.split(":", 1)
        assert value, f"Expected a value! for {key}"
        if result[key] and value not in result[key]:
            result[key].append(value)
        else:
            result[key] = [value]

    # Convert single-item lists back to strings for non-list values
    return {k: v if len(v) > 1 else v[0] for k, v in result.items()}


def sanitize_identifier(identifier, replacement='-'):
    return re.sub(r'[^\w-]', replacement, identifier)


def get_itemname(infodict):
    # Remove illegal characters in identifier
    return sanitize_identifier('%s-%s' % (
        infodict.get('extractor'),
        infodict.get('display_id', infodict.get('id')),
    ))


def check_is_file_empty(filepath):
    """
    Check whether file is empty or not.

    :param filepath:  Path of a file that will be checked.
    :return:          True if the file empty.
    """
    if os.path.exists(filepath):
        return os.stat(filepath).st_size == 0
    else:
        raise FileNotFoundError("Path '%s' doesn't exist" % filepath)


def scrub_ip_addresses(data, ipv4_replacement='127.0.0.1', ipv6_replacement='::1',
                       replacement=None):
    """Recursively scrub IPv4 and IPv6 addresses from a data structure.

    Replaces all IP addresses with replacement strings to prevent leaking
    user IP addresses in uploaded metadata.

    :param data:              Data structure to scrub (dict, list, str, or other).
    :param ipv4_replacement:  String to replace IPv4 addresses with.
    :param ipv6_replacement:  String to replace IPv6 addresses with.
    :param replacement:       Backwards compat - sets both replacements to the same value.
    :return:                  Scrubbed copy of the data structure.
    """
    if replacement is not None:
        ipv4_replacement = replacement
        ipv6_replacement = replacement

    if isinstance(data, dict):
        # http_headers contains outgoing request headers (User-Agent, Accept, etc.)
        # set by yt-dlp itself — they cannot contain the user's real IP address.
        # Skipping them prevents false positives on version strings like Chrome/127.0.0.72.
        return {k: (v if k == 'http_headers' else
                    scrub_ip_addresses(v, ipv4_replacement, ipv6_replacement))
                for k, v in data.items()}
    elif isinstance(data, list):
        return [scrub_ip_addresses(item, ipv4_replacement, ipv6_replacement)
                for item in data]
    elif isinstance(data, str):
        # Scrub IPv6 first (before IPv4 to avoid double-replacing IPv4-mapped IPv6)
        result = IPV6_PATTERN.sub(ipv6_replacement, data)
        result = IPV4_PATTERN.sub(ipv4_replacement, result)
        return result
    else:
        return data


def _scrub_ip_addresses_from_file_streaming(filepath, ipv4_replacement='127.0.0.1',
                                            ipv6_replacement='::1'):
    """Scrub IP addresses from a large text file line-by-line (memory-efficient).

    :param filepath:          Path to text file to scrub.
    :param ipv4_replacement:  String to replace IPv4 addresses with.
    :param ipv6_replacement:  String to replace IPv6 addresses with.
    :return:                  Number of IP addresses replaced.
    """
    file_dir = os.path.dirname(os.path.abspath(filepath))
    replacements = 0
    tmp_fd, temp_path = tempfile.mkstemp(dir=file_dir)
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8', errors='surrogateescape') as fout:
            with open(filepath, 'r', encoding='utf-8', errors='surrogateescape') as fin:
                for line in fin:
                    ipv6_matches = IPV6_PATTERN.findall(line)
                    line = IPV6_PATTERN.sub(ipv6_replacement, line)
                    ipv4_matches = IPV4_PATTERN.findall(line)
                    line = IPV4_PATTERN.sub(ipv4_replacement, line)
                    replacements += len(ipv6_matches) + len(ipv4_matches)
                    fout.write(line)
        os.replace(temp_path, filepath)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return replacements


def scrub_ip_addresses_from_file(filepath, ipv4_replacement='127.0.0.1',
                                 ipv6_replacement='::1', replacement=None,
                                 streaming_threshold=1048576):
    """Scrub IP addresses from a text file in-place.

    Uses streaming (line-by-line) mode for files larger than streaming_threshold
    to reduce memory usage. Small files are processed in-memory.

    :param filepath:             Path to text file to scrub.
    :param ipv4_replacement:     String to replace IPv4 addresses with.
    :param ipv6_replacement:     String to replace IPv6 addresses with.
    :param replacement:          Backwards compat - sets both replacements to same value.
    :param streaming_threshold:  File size in bytes above which streaming mode is used.
    :return:                     Number of IP addresses replaced.
    :raises FileNotFoundError:   If filepath doesn't exist.
    """
    if replacement is not None:
        ipv4_replacement = replacement
        ipv6_replacement = replacement

    if not os.path.exists(filepath):
        raise FileNotFoundError("Path '%s' doesn't exist" % filepath)

    file_size = os.path.getsize(filepath)

    if file_size > streaming_threshold:
        return _scrub_ip_addresses_from_file_streaming(filepath, ipv4_replacement,
                                                       ipv6_replacement)
    else:
        with open(filepath, 'r', encoding='utf-8', errors='surrogateescape') as f:
            content = f.read()

        ipv6_matches = IPV6_PATTERN.findall(content)
        scrubbed_content = IPV6_PATTERN.sub(ipv6_replacement, content)

        ipv4_matches = IPV4_PATTERN.findall(scrubbed_content)
        scrubbed_content = IPV4_PATTERN.sub(ipv4_replacement, scrubbed_content)

        with open(filepath, 'w', encoding='utf-8', errors='surrogateescape') as f:
            f.write(scrubbed_content)

        return len(ipv6_matches) + len(ipv4_matches)
