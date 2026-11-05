"""Public builds must never publish into an implicit personal Notion destination."""
from pathlib import Path
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from lumen_organizer.capture import CaptureError
from lumen_organizer.notion_connected import publish_connected

class PublicConfigurationTests(unittest.TestCase):
    def test_missing_or_invalid_notion_destination_never_invokes_a_provider(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / 'not-created'
            for value in ('', 'your-notion-data-source-id', 'https://example.com'):
                with self.subTest(value=value), patch('lumen_organizer.notion_connected.LIBRARY', value), patch('lumen_organizer.notion_connected.subprocess.run') as run:
                    with self.assertRaises(CaptureError):
                        publish_connected('Fictional note', '# Example', 'fictional-id', target)
                    run.assert_not_called()
                    self.assertFalse(target.exists())
