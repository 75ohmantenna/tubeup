import unittest
from tubeup.utils import key_value_to_dict


class KeyValueToDictTest(unittest.TestCase):

    def test_single_string_input(self):
        # Non-list input should be wrapped into a list
        result = key_value_to_dict('subject:Nature')
        self.assertEqual(result, {'subject': 'Nature'})

    def test_list_with_single_item(self):
        result = key_value_to_dict(['subject:Nature'])
        self.assertEqual(result, {'subject': 'Nature'})

    def test_empty_list(self):
        result = key_value_to_dict([])
        self.assertEqual(result, {})

    def test_multiple_unique_values_same_key(self):
        # Two different values for the same key → result is a list
        result = key_value_to_dict(['subject:Nature', 'subject:Science'])
        self.assertEqual(result, {'subject': ['Nature', 'Science']})

    def test_duplicate_key_value_pair(self):
        # Same key:value pair twice — second occurrence is not appended
        result = key_value_to_dict(['subject:Nature', 'subject:Nature'])
        self.assertEqual(result, {'subject': 'Nature'})

    def test_value_containing_colons(self):
        # Only the first colon is the separator
        result = key_value_to_dict(['url:https://example.com/path'])
        self.assertEqual(result, {'url': 'https://example.com/path'})

    def test_multiple_different_keys(self):
        result = key_value_to_dict(['title:My Video', 'creator:Alice'])
        self.assertEqual(result, {'title': 'My Video', 'creator': 'Alice'})
