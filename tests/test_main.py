import unittest
from unittest.mock import patch, MagicMock

from tubeup.__main__ import main
from tubeup.TubeUp import TubeUp as RealTubeUp


def _make_args(**overrides):
    defaults = {
        '<url>': ['https://www.youtube.com/watch?v=test'],
        '--cookies': None,
        '--proxy': None,
        '--username': None,
        '--password': None,
        '--quiet': False,
        '--debug': False,
        '--use-download-archive': False,
        '--ignore-existing-item': False,
        '--dir': None,
        '--output': None,
        '--metadata': [],
    }
    defaults.update(overrides)
    return defaults


class TestMain(unittest.TestCase):

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_basic_success(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args()
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([
            ('test-id', {'title': 'Test Video'})
        ])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            main()

        mock_tubeup_cls.assert_called_once_with(
            verbose=True, dir_path='~/.tubeup', output_template=None)
        mock_tu.archive_urls.assert_called_once()

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_quiet_mode(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--quiet': True})
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            main()

        mock_tubeup_cls.assert_called_once_with(
            verbose=False, dir_path='~/.tubeup', output_template=None)

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_debug_mode_configures_logging(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--debug': True})
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            with patch('tubeup.__main__.logging') as mock_logging:
                mock_root = MagicMock()
                mock_logging.getLogger.return_value = mock_root
                mock_logging.DEBUG = 10
                mock_logging.StreamHandler = MagicMock(return_value=MagicMock())
                mock_logging.Formatter = MagicMock(return_value=MagicMock())
                main()

        mock_logging.getLogger.assert_called_with()
        mock_root.setLevel.assert_called_with(10)

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_custom_dir_used(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--dir': '/tmp/custom'})
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            main()

        mock_tubeup_cls.assert_called_once_with(
            verbose=True, dir_path='/tmp/custom', output_template=None)

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_dir_error_exits_with_code_1(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--dir': '/no/such/place'})
        mock_tubeup_cls.DirError = RealTubeUp.DirError
        mock_tubeup_cls.side_effect = RealTubeUp.DirError('no such directory')

        with self.assertRaises(SystemExit) as ctx:
            with patch('builtins.print'):
                main()

        self.assertEqual(ctx.exception.code, 1)

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_archive_exception_exits_with_code_1(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args()
        mock_tu = MagicMock()
        mock_tu.archive_urls.side_effect = RuntimeError('network failure')
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with self.assertRaises(SystemExit) as ctx:
            with patch('builtins.print'):
                with patch('tubeup.__main__.traceback.print_exc'):
                    main()

        self.assertEqual(ctx.exception.code, 1)

    @patch('tubeup.__main__.key_value_to_dict', return_value={'subject': 'Nature'})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_metadata_passed_to_archive_urls(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--metadata': ['subject:Nature']})
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            main()

        mock_kvd.assert_called_once_with(['subject:Nature'])

    @patch('tubeup.__main__.key_value_to_dict', return_value={})
    @patch('tubeup.__main__.TubeUp')
    @patch('tubeup.__main__.docopt.docopt')
    def test_output_template_passed(self, mock_docopt, mock_tubeup_cls, mock_kvd):
        mock_docopt.return_value = _make_args(**{'--output': '%(title)s.%(ext)s'})
        mock_tu = MagicMock()
        mock_tu.archive_urls.return_value = iter([])
        mock_tubeup_cls.return_value = mock_tu
        mock_tubeup_cls.DirError = RealTubeUp.DirError

        with patch('builtins.print'):
            main()

        mock_tubeup_cls.assert_called_once_with(
            verbose=True, dir_path='~/.tubeup',
            output_template='%(title)s.%(ext)s')
