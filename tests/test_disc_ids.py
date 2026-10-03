import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import gui

class DiscIdentityTests(unittest.TestCase):
    def test_mod_passes_game_filter(self):
        identity = next(iter(gui.REGIONS.values())).game_id[:4] + '99'
        for disc_id, accepted in ((identity, True), ('ZZZZ99', False)):
            def extract(cmd, **kwargs):
                dest = Path(cmd[cmd.index('--dest') + 1])
                (dest / 'sys').mkdir(parents=True)
                (dest / 'sys/boot.bin').write_bytes(disc_id.encode() + bytes(2))
                return Mock(returncode=0)
            log, done = Mock(), Mock()
            with patch.object(gui, 'find_wit', return_value='wit'), patch.object(gui.subprocess, 'run', side_effect=extract):
                gui.run_patch('mod.iso', True, log, done)
            messages = str(log.call_args_list)
            self.assertEqual('could not find sys/main.dol' in messages, accepted)
            self.assertFalse(done.call_args.args[0])
