import os
import tempfile
import unittest

from tubeup.utils import (sanitize_identifier, check_is_file_empty,
                          scrub_ip_addresses, scrub_ip_addresses_from_file,
                          TEXT_SIDECAR_EXTENSIONS)


class UtilsTest(unittest.TestCase):

    def test_preserve_valid_identifiers(self):
        valid = [
            'youtube--QBwhSklJks',
            'youtube-_--M04_mN-M',
            'youtube-Xy2jZABDB40'
        ]
        clean = [sanitize_identifier(x) for x in valid]
        self.assertListEqual(valid, clean)

    def test_sanitize_bad_identifiers(self):
        bad = [
            'twitch:vod-v181464551',
            'twitch:clips-1003820974',
            'twitter:card-1192732384065708032'
        ]
        expect = [
            'twitch-vod-v181464551',
            'twitch-clips-1003820974',
            'twitter-card-1192732384065708032'
        ]
        clean = [sanitize_identifier(x) for x in bad]
        self.assertListEqual(expect, clean)

    def test_check_is_file_empty_when_file_is_empty(self):
        # Create a file for the test
        with open('testemptyfile.txt', 'w'):
            pass

        self.assertTrue(check_is_file_empty('testemptyfile.txt'))
        os.remove('testemptyfile.txt')

    def test_check_is_file_empty_when_file_is_not_empty(self):
        with open('testfilenotempty.txt', 'w') as not_empty_file:
            not_empty_file.write('just a text')

        self.assertFalse(check_is_file_empty('testfilenotempty.txt'))
        os.remove('testfilenotempty.txt')

    def test_check_is_file_empty_when_file_doesnt_exist(self):
        with self.assertRaisesRegex(
                FileNotFoundError,
                r"^Path 'file_that_doesnt_exist.txt' doesn't exist$"):
            check_is_file_empty('file_that_doesnt_exist.txt')

    def test_scrub_ip_addresses_from_string(self):
        input_str = 'https://example.com/api/manifest?ip=23.234.85.189&other=param'
        expected = 'https://example.com/api/manifest?ip=127.0.0.1&other=param'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_ip_addresses_from_dict(self):
        input_dict = {
            'url': 'https://manifest.googlevideo.com/api/manifest/hls_playlist/ip/23.234.85.189/id/video123',
            'manifest_url': 'https://example.com/manifest/ip/192.168.1.1/file.m3u8',
            'metadata': {'server': '10.0.0.1', 'port': 8080},
        }
        expected = {
            'url': 'https://manifest.googlevideo.com/api/manifest/hls_playlist/ip/127.0.0.1/id/video123',
            'manifest_url': 'https://example.com/manifest/ip/127.0.0.1/file.m3u8',
            'metadata': {'server': '127.0.0.1', 'port': 8080},
        }
        self.assertEqual(scrub_ip_addresses(input_dict), expected)

    def test_scrub_ip_addresses_from_list(self):
        input_list = [
            'Server at 192.168.1.100',
            'https://api.example.com/v1/endpoint?client_ip=10.20.30.40',
            'No IP address here',
        ]
        expected = [
            'Server at 127.0.0.1',
            'https://api.example.com/v1/endpoint?client_ip=127.0.0.1',
            'No IP address here',
        ]
        self.assertEqual(scrub_ip_addresses(input_list), expected)

    def test_scrub_ip_addresses_preserves_non_strings(self):
        input_data = {'number': 42, 'boolean': True, 'none': None, 'url': 'http://1.2.3.4/api'}
        expected = {'number': 42, 'boolean': True, 'none': None, 'url': 'http://127.0.0.1/api'}
        self.assertEqual(scrub_ip_addresses(input_data), expected)

    def test_scrub_ip_addresses_skips_http_headers(self):
        # Chrome version strings like 127.0.0.72 match the IPv4 pattern; http_headers
        # contains outgoing request headers set by yt-dlp and can never hold the user's
        # real IP, so the whole key must be left untouched.
        ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/127.0.0.72 Safari/537.36')
        input_data = {
            'url': 'https://manifest.googlevideo.com/api/manifest?ip=23.234.85.189',
            'http_headers': {
                'User-Agent': ua,
                'Accept': 'text/html',
            },
        }
        result = scrub_ip_addresses(input_data)
        # Real IP in url must be scrubbed
        self.assertIn('127.0.0.1', result['url'])
        self.assertNotIn('23.234.85.189', result['url'])
        # http_headers must be passed through unchanged
        self.assertEqual(result['http_headers']['User-Agent'], ua)

    def test_scrub_ip_addresses_custom_replacement(self):
        input_str = 'IP address: 192.168.0.1'
        expected = 'IP address: [REDACTED]'
        self.assertEqual(scrub_ip_addresses(input_str, replacement='[REDACTED]'), expected)

    def test_scrub_ip_addresses_from_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('Server IP: 192.168.1.1\n')
            f.write('Client connected from 10.0.0.50\n')
            f.write('No IP on this line\n')
            f.write('Multiple IPs: 172.16.0.1 and 8.8.8.8\n')
            temp_file = f.name

        try:
            ip_count = scrub_ip_addresses_from_file(temp_file)
            self.assertEqual(ip_count, 4)

            with open(temp_file, 'r') as f:
                content = f.read()
            expected_content = (
                'Server IP: 127.0.0.1\n'
                'Client connected from 127.0.0.1\n'
                'No IP on this line\n'
                'Multiple IPs: 127.0.0.1 and 127.0.0.1\n'
            )
            self.assertEqual(content, expected_content)
        finally:
            os.remove(temp_file)

    def test_scrub_ip_addresses_from_file_with_custom_replacement(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('IP: 1.2.3.4')
            temp_file = f.name

        try:
            ip_count = scrub_ip_addresses_from_file(temp_file, replacement='X.X.X.X')
            self.assertEqual(ip_count, 1)

            with open(temp_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, 'IP: X.X.X.X')
        finally:
            os.remove(temp_file)

    def test_scrub_ip_addresses_from_nonexistent_file(self):
        with self.assertRaisesRegex(FileNotFoundError, r"doesn't exist"):
            scrub_ip_addresses_from_file('nonexistent_file.txt')

    def test_scrub_ipv6_addresses_from_string(self):
        input_str = 'Server: 2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        expected = 'Server: ::1'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_ipv6_compressed_form(self):
        input_str = 'Connect to 2001:db8:85a3::8a2e:370:7334'
        expected = 'Connect to ::1'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_ipv6_localhost(self):
        # ::1 is the replacement, so it should not be double-replaced
        input_str = 'Localhost: ::1'
        expected = 'Localhost: ::1'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_ipv4_mapped_ipv6(self):
        input_str = 'Mapped: ::ffff:192.0.2.1'
        expected = 'Mapped: ::1'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_mixed_ipv4_and_ipv6(self):
        input_str = 'IPv4: 192.168.1.1, IPv6: 2001:db8::1'
        expected = 'IPv4: 127.0.0.1, IPv6: ::1'
        self.assertEqual(scrub_ip_addresses(input_str), expected)

    def test_scrub_from_file_streaming_returns_replacement_count(self):
        """Streaming mode must return IP count (not line count) when multiple IPs share a line."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('IPs: 192.168.1.1 and 10.0.0.1\n')
            f.write('IPv6: 2001:db8::1\n')
            temp_file = f.name

        try:
            ip_count = scrub_ip_addresses_from_file(temp_file, streaming_threshold=0)
            self.assertEqual(ip_count, 3)  # 2 IPv4 + 1 IPv6, not 2 lines
        finally:
            os.remove(temp_file)

    def test_streaming_and_non_streaming_return_same_count(self):
        """Streaming and non-streaming paths must return identical replacement counts."""
        content = 'IPs: 192.168.1.1 and 2001:db8::1\nAnother: 10.0.0.1\n'

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            file1 = f.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            file2 = f.name

        try:
            count_non_streaming = scrub_ip_addresses_from_file(file1)
            count_streaming = scrub_ip_addresses_from_file(file2, streaming_threshold=0)
            self.assertEqual(count_non_streaming, count_streaming)
            self.assertEqual(count_non_streaming, 3)  # 2 IPv4 + 1 IPv6
        finally:
            os.remove(file1)
            os.remove(file2)

    def test_scrub_preserves_non_utf8_bytes(self):
        """Non-UTF-8 bytes must survive a scrub pass unchanged (non-streaming)."""
        raw = b'Server: 192.168.1.1\nsome\xff\xfebytes\n'

        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(raw)
            temp_file = f.name

        try:
            scrub_ip_addresses_from_file(temp_file)
            with open(temp_file, 'rb') as f:
                result = f.read()
            self.assertEqual(result, b'Server: 127.0.0.1\nsome\xff\xfebytes\n')
        finally:
            os.remove(temp_file)

    def test_scrub_preserves_non_utf8_bytes_streaming(self):
        """Non-UTF-8 bytes must survive a scrub pass unchanged (streaming)."""
        raw = b'Server: 192.168.1.1\nsome\xff\xfebytes\n'

        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(raw)
            temp_file = f.name

        try:
            scrub_ip_addresses_from_file(temp_file, streaming_threshold=0)
            with open(temp_file, 'rb') as f:
                result = f.read()
            self.assertEqual(result, b'Server: 127.0.0.1\nsome\xff\xfebytes\n')
        finally:
            os.remove(temp_file)

    def test_streaming_leaves_no_predictable_tmp_file(self):
        """Streaming mode must not leave a predictable .tmp file beside the source."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('IP: 1.2.3.4\n')
            temp_file = f.name

        try:
            scrub_ip_addresses_from_file(temp_file, streaming_threshold=0)
            self.assertFalse(os.path.exists(temp_file + '.tmp'))
        finally:
            os.remove(temp_file)

    def test_text_sidecar_extensions_covers_ssa(self):
        """TEXT_SIDECAR_EXTENSIONS must include .ssa (previously uncovered)."""
        self.assertTrue('video.ssa'.endswith(TEXT_SIDECAR_EXTENSIONS))

    def test_ssa_file_is_scrubbed(self):
        """Previously uncovered .ssa extension is scrubbed of IP addresses."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ssa') as f:
            f.write('Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Server: 192.168.0.1\n')
            temp_file = f.name

        try:
            count = scrub_ip_addresses_from_file(temp_file)
            self.assertEqual(count, 1)
            with open(temp_file) as f:
                content = f.read()
            self.assertIn('127.0.0.1', content)
            self.assertNotIn('192.168.0.1', content)
        finally:
            os.remove(temp_file)

    def test_binary_extensions_not_in_text_sidecars(self):
        """Binary media extensions must not appear in TEXT_SIDECAR_EXTENSIONS."""
        for ext in ('.mp4', '.webm', '.mkv', '.mp3', '.jpg', '.png', '.m4a'):
            self.assertFalse(
                ('video' + ext).endswith(TEXT_SIDECAR_EXTENSIONS),
                msg='%s should not be classified as a text sidecar' % ext,
            )

    def test_scrub_ipv6_from_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('Server IPv6: 2001:0db8:85a3::8a2e:370:7334\n')
            f.write('Client IPv4: 10.0.0.1\n')
            f.write('IPv4-mapped: ::ffff:192.0.2.128\n')
            temp_file = f.name

        try:
            ip_count = scrub_ip_addresses_from_file(temp_file)
            self.assertEqual(ip_count, 3)  # 1 IPv6 + 1 IPv4 + 1 IPv4-mapped

            with open(temp_file, 'r') as f:
                content = f.read()
            expected_content = 'Server IPv6: ::1\nClient IPv4: 127.0.0.1\nIPv4-mapped: ::1\n'
            self.assertEqual(content, expected_content)
        finally:
            os.remove(temp_file)
