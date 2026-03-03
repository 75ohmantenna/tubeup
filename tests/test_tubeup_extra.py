import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from tubeup.TubeUp import TubeUp, DOWNLOAD_DIR_NAME

current_path = os.path.dirname(os.path.realpath(__file__))


def get_testfile_path(name):
    return os.path.join(current_path, 'test_tubeup_files', name)


def copy_testfiles_to_tubeup_rootdir_test():
    testfiles_dir = os.path.join(current_path, 'test_tubeup_files',
                                 'files_for_upload_and_download_tests')
    for filepath in os.listdir(testfiles_dir):
        shutil.copy(
            os.path.join(testfiles_dir, filepath),
            os.path.join(current_path, 'test_tubeup_rootdir', 'downloads',
                         filepath))


# ---------------------------------------------------------------------------
# dir_path setter validation branches
# ---------------------------------------------------------------------------

class TubeUpDirPathValidationTest(unittest.TestCase):

    def test_non_path_like_raises_direrror(self):
        # os.fspath(123) → TypeError → DirError
        with self.assertRaises(TubeUp.DirError) as ctx:
            TubeUp(dir_path=123)
        self.assertIn('string or path-like', str(ctx.exception))

    def test_none_raises_direrror(self):
        # os.fspath(None) → TypeError → DirError
        with self.assertRaises(TubeUp.DirError) as ctx:
            TubeUp(dir_path=None)
        self.assertIn('string or path-like', str(ctx.exception))

    def test_empty_string_raises_direrror(self):
        with self.assertRaises(TubeUp.DirError) as ctx:
            TubeUp(dir_path='')
        self.assertIn('must not be empty', str(ctx.exception))

    def test_whitespace_only_raises_direrror(self):
        with self.assertRaises(TubeUp.DirError) as ctx:
            TubeUp(dir_path='   ')
        self.assertIn('must not be empty', str(ctx.exception))

    def test_root_path_is_existing_file_raises_direrror(self):
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(TubeUp.DirError) as ctx:
                TubeUp(dir_path=f.name)
        self.assertIn('already exists as a file', str(ctx.exception))

    def test_downloads_subdir_is_file_raises_direrror(self):
        tmpdir = tempfile.mkdtemp()
        try:
            downloads_path = os.path.join(tmpdir, DOWNLOAD_DIR_NAME)
            open(downloads_path, 'w').close()
            with self.assertRaises(TubeUp.DirError) as ctx:
                TubeUp(dir_path=tmpdir)
            self.assertIn('already exists as a file', str(ctx.exception))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# __init__ output_template branch
# ---------------------------------------------------------------------------

class TubeUpInitTest(unittest.TestCase):

    def test_output_template_not_none(self):
        tu = TubeUp(output_template='%(title)s.%(ext)s')
        self.assertEqual(tu.output_template, '%(title)s.%(ext)s')


# ---------------------------------------------------------------------------
# generate_ydl_options — optional fields
# ---------------------------------------------------------------------------

class TubeUpGenerateYdlOptionsTest(unittest.TestCase):

    def setUp(self):
        self.tu = TubeUp()

    def _dummy_hook(self, d):
        pass

    def test_with_cookie_file(self):
        result = self.tu.generate_ydl_options(self._dummy_hook,
                                              cookie_file='cookies.txt')
        self.assertEqual(result['cookiefile'], 'cookies.txt')


# ---------------------------------------------------------------------------
# create_archive_org_metadata_from_youtubedl_meta — edge branches
# ---------------------------------------------------------------------------

class TubeUpMetadataEdgeCasesTest(unittest.TestCase):

    def _base_meta(self):
        return {
            'title': 'Test Video',
            'webpage_url': 'https://www.youtube.com/watch?v=test123',
            'extractor_key': 'Youtube',
            'extractor': 'youtube',
            'id': 'test123',
            'upload_date': '20200101',
            'uploader': 'TestUser',
            'uploader_url': 'https://www.youtube.com/channel/test',
            'description': 'A test video',
            'tags': ['tag1', 'tag2'],
            'categories': ['Entertainment'],
        }

    def test_no_uploader_falls_through_to_tubeup_py(self):
        meta = self._base_meta()
        del meta['uploader']
        del meta['uploader_url']
        result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(meta)
        self.assertEqual(result['creator'], 'tubeup.py')

    def test_channel_url_used_when_uploader_url_absent(self):
        meta = self._base_meta()
        del meta['uploader_url']
        meta['channel_url'] = 'https://www.youtube.com/channel/fallback'
        result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(meta)
        self.assertEqual(result['channel'],
                         'https://www.youtube.com/channel/fallback')

    def test_no_channel_fields(self):
        meta = self._base_meta()
        del meta['uploader_url']
        result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(meta)
        self.assertNotIn('channel', result)

    def test_categories_non_iterable_prints_message(self):
        meta = self._base_meta()
        meta['categories'] = None  # TypeError when iterated
        with patch('builtins.print') as mock_print:
            result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(
                meta)
        self.assertIn('subject', result)
        mock_print.assert_any_call("No categories found.")

    def test_tags_non_iterable_prints_message(self):
        meta = self._base_meta()
        meta['tags'] = None  # TypeError when iterated
        with patch('builtins.print') as mock_print:
            result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(
                meta)
        self.assertIn('subject', result)
        mock_print.assert_any_call("Unable to process tags successfully.")

    def test_uploader_url_used_when_uploader_empty(self):
        meta = self._base_meta()
        meta['uploader'] = ''  # falsy → fall through to uploader_url
        result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(meta)
        self.assertEqual(result['creator'],
                         'https://www.youtube.com/channel/test')

    def test_soundcloud_url_gives_audio_mediatype(self):
        meta = self._base_meta()
        meta['webpage_url'] = 'https://soundcloud.com/artist/track'
        result = TubeUp.create_archive_org_metadata_from_youtubedl_meta(meta)
        self.assertEqual(result['mediatype'], 'audio')
        self.assertEqual(result['collection'], 'opensource_audio')


# ---------------------------------------------------------------------------
# upload_ia — S3 keys None raises exception
# ---------------------------------------------------------------------------

class TubeUpUploadIAS3Test(unittest.TestCase):

    def setUp(self):
        copy_testfiles_to_tubeup_rootdir_test()
        self.tu = TubeUp(
            dir_path=os.path.join(current_path, 'test_tubeup_rootdir'),
            ia_config_path=get_testfile_path('ia_config_for_test.ini'))
        self.videobasename = os.path.join(
            current_path, 'test_tubeup_rootdir', 'downloads',
            'Mountain_3_-_Video_Background_HD_1080p-6iRV8liah8A')

    def test_s3_keys_none_raises_exception(self):
        with patch('tubeup.TubeUp.parse_config_file') as mock_cfg:
            mock_cfg.return_value = (
                {}, {},
                {'s3': {'access': None, 'secret': None}}
            )
            with self.assertRaises(Exception) as ctx:
                self.tu.upload_ia(self.videobasename)
        self.assertIn('not configured properly', str(ctx.exception))

    def test_s3_access_key_none_raises_exception(self):
        with patch('tubeup.TubeUp.parse_config_file') as mock_cfg:
            mock_cfg.return_value = (
                {}, {},
                {'s3': {'access': None, 'secret': 'mysecret'}}
            )
            with self.assertRaises(Exception) as ctx:
                self.tu.upload_ia(self.videobasename)
        self.assertIn('not configured properly', str(ctx.exception))

    def test_upload_ia_with_custom_meta(self):
        import requests_mock as req_mock

        with req_mock.Mocker() as m:
            m.get('https://s3.us.archive.org',
                  content=b'{"over_limit": 0}',
                  headers={'content-type': 'application/json'})
            m.get('https://archive.org/metadata/youtube-6iRV8liah8A',
                  content=b'{}',
                  headers={'content-type': 'application/json'})
            import glob
            for fp in glob.glob(self.videobasename + '*'):
                fname = os.path.basename(fp)
                m.put('https://s3.us.archive.org/youtube-6iRV8liah8A/%s'
                      % fname,
                      content=b'',
                      headers={'content-type': 'text/plain'})

            identifier, meta = self.tu.upload_ia(
                self.videobasename,
                custom_meta={'subject': 'extra tag'})

        self.assertEqual(identifier, 'youtube-6iRV8liah8A')
        self.assertIn('subject', meta)


# ---------------------------------------------------------------------------
# get_resource_basenames — playlist + item-exists branches
# ---------------------------------------------------------------------------

class TubeUpGetResourceBasenamesTest(unittest.TestCase):

    def setUp(self):
        copy_testfiles_to_tubeup_rootdir_test()
        self.tu = TubeUp(
            dir_path=os.path.join(current_path, 'test_tubeup_rootdir'))

    @patch('tubeup.TubeUp.YoutubeDL')
    def test_playlist_entries_iterated(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        entry = {
            '_type': 'video',
            'id': 'abc123',
            'extractor': 'youtube',
            'extractor_key': 'Youtube',
            'title': 'Playlist Entry',
            'webpage_url': 'https://www.youtube.com/watch?v=abc123',
        }
        playlist_info = {
            '_type': 'playlist',
            'entries': [entry],
        }
        mock_ydl.extract_info.side_effect = [
            playlist_info,   # first call: download=False to get playlist
            entry,           # second call: actual download of entry
        ]
        mock_ydl.in_download_archive.return_value = False
        mock_ydl.prepare_filename.return_value = 'abc123.mp4'

        with patch('tubeup.TubeUp.internetarchive.get_item') as mock_get_item:
            mock_item = MagicMock()
            mock_item.exists = False
            mock_get_item.return_value = mock_item

            result = self.tu.get_resource_basenames(
                ['https://www.youtube.com/playlist?list=PL123'],
                ignore_existing_item=False)

        self.assertIsInstance(result, set)

    @patch('tubeup.TubeUp.YoutubeDL')
    def test_item_exists_on_ia_skips_download(self, mock_ydl_cls):
        tu = TubeUp(
            dir_path=os.path.join(current_path, 'test_tubeup_rootdir'),
            verbose=True)

        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        video_info = {
            '_type': 'video',
            'id': 'existing123',
            'extractor': 'youtube',
            'extractor_key': 'Youtube',
            'title': 'Already Archived Video',
            'webpage_url': 'https://www.youtube.com/watch?v=existing123',
        }
        mock_ydl.extract_info.return_value = video_info
        mock_ydl.in_download_archive.return_value = False

        with patch('tubeup.TubeUp.internetarchive.get_item') as mock_get_item:
            mock_item = MagicMock()
            mock_item.exists = True
            mock_get_item.return_value = mock_item

            with patch('builtins.print'):
                result = tu.get_resource_basenames(
                    ['https://www.youtube.com/watch?v=existing123'],
                    ignore_existing_item=False)

        # Item existed → download skipped, record_download_archive called
        mock_ydl.record_download_archive.assert_called_once_with(video_info)
        self.assertEqual(result, set())

    @patch('tubeup.TubeUp.YoutubeDL')
    def test_none_entry_logs_warning(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Playlist with a None entry (unavailable video)
        playlist_info = {
            '_type': 'playlist',
            'entries': [None],
        }
        mock_ydl.extract_info.return_value = playlist_info

        with patch('tubeup.TubeUp.internetarchive.get_item'):
            result = self.tu.get_resource_basenames(
                ['https://www.youtube.com/playlist?list=PL123'],
                ignore_existing_item=False)

        self.assertEqual(result, set())

    @patch('tubeup.TubeUp.YoutubeDL')
    def test_in_download_archive_skips_entry(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        video_info = {
            '_type': 'video',
            'id': 'archived123',
            'extractor': 'youtube',
            'extractor_key': 'Youtube',
            'title': 'Already Downloaded',
            'webpage_url': 'https://www.youtube.com/watch?v=archived123',
        }
        mock_ydl.extract_info.return_value = video_info
        mock_ydl.in_download_archive.return_value = True

        with patch('tubeup.TubeUp.internetarchive.get_item'):
            result = self.tu.get_resource_basenames(
                ['https://www.youtube.com/watch?v=archived123'],
                ignore_existing_item=False)

        # Already in archive → nothing downloaded
        mock_ydl.extract_info.assert_called_once()
        self.assertEqual(result, set())
