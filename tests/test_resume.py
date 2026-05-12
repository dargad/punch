import unittest
import datetime
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from punch.web import timecard_id, TimecardEntry
from punch.commands import (
    _clear_progress,
    _get_progress_path,
    _load_progress,
    _save_progress,
    handle_submit,
)


def _make_timecard(case_no="00000100", minutes=60,
                   start_date=datetime.date(2026, 5, 1),
                   start_time=datetime.time(9, 0)):
    return TimecardEntry(
        case_no=case_no,
        owner="Test User",
        minutes=minutes,
        start_date=start_date,
        start_time=start_time,
        work_performed="some work",
        desc="Coding",
    )


# ---------------------------------------------------------------------------
# timecard_id
# ---------------------------------------------------------------------------

class TestTimecardId(unittest.TestCase):
    def test_returns_string(self):
        tc = _make_timecard()
        self.assertIsInstance(timecard_id(tc), str)

    def test_stable_across_equal_instances(self):
        self.assertEqual(timecard_id(_make_timecard()), timecard_id(_make_timecard()))

    def test_different_case_no_gives_different_id(self):
        self.assertNotEqual(
            timecard_id(_make_timecard(case_no="00000001")),
            timecard_id(_make_timecard(case_no="00000002")),
        )

    def test_different_minutes_gives_different_id(self):
        self.assertNotEqual(
            timecard_id(_make_timecard(minutes=30)),
            timecard_id(_make_timecard(minutes=60)),
        )

    def test_different_start_date_gives_different_id(self):
        self.assertNotEqual(
            timecard_id(_make_timecard(start_date=datetime.date(2026, 5, 1))),
            timecard_id(_make_timecard(start_date=datetime.date(2026, 5, 2))),
        )

    def test_different_start_time_gives_different_id(self):
        self.assertNotEqual(
            timecard_id(_make_timecard(start_time=datetime.time(9, 0))),
            timecard_id(_make_timecard(start_time=datetime.time(10, 0))),
        )


# ---------------------------------------------------------------------------
# Progress file helpers
# ---------------------------------------------------------------------------

class TestProgressHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp_dir.name, "punch.yaml")
        open(self.config_path, "w").close()
        self._patcher = patch("punch.commands.get_config_path", return_value=self.config_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.tmp_dir.cleanup()

    def test_get_progress_path_is_in_config_dir(self):
        path = _get_progress_path()
        self.assertEqual(os.path.dirname(path), self.tmp_dir.name)
        self.assertTrue(path.endswith(".json"))

    def test_load_progress_returns_empty_set_when_no_file(self):
        self.assertEqual(_load_progress(), set())

    def test_save_and_load_roundtrip(self):
        ids = {"id_a", "id_b", "id_c"}
        _save_progress(ids)
        self.assertEqual(_load_progress(), ids)

    def test_save_writes_valid_json(self):
        _save_progress({"x", "y"})
        with open(_get_progress_path()) as f:
            data = json.load(f)
        self.assertIn("submitted", data)
        self.assertEqual(set(data["submitted"]), {"x", "y"})

    def test_clear_removes_file(self):
        _save_progress({"id1"})
        _clear_progress()
        self.assertFalse(os.path.exists(_get_progress_path()))

    def test_load_after_clear_returns_empty_set(self):
        _save_progress({"id1"})
        _clear_progress()
        self.assertEqual(_load_progress(), set())

    def test_clear_when_no_file_does_not_raise(self):
        _clear_progress()  # should not raise


# ---------------------------------------------------------------------------
# handle_submit resume logic
# ---------------------------------------------------------------------------

class TestHandleSubmitResume(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp_dir.name, "punch.yaml")
        open(self.config_path, "w").close()

        self.config = {"full_name": "Test User", "timecards_url": "http://example.com"}
        self.console = MagicMock()
        self.console.input.return_value = "y"

        self.tc1 = _make_timecard(case_no="00000001", start_date=datetime.date(2026, 5, 1))
        self.tc2 = _make_timecard(case_no="00000002", start_date=datetime.date(2026, 5, 2))
        self.tc3 = _make_timecard(case_no="00000003", start_date=datetime.date(2026, 5, 3))
        self.all_timecards = [self.tc1, self.tc2, self.tc3]

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _args(self, resume=False, dry_run=False):
        return SimpleNamespace(
            from_=None, to=None,
            resume=resume, dry_run=dry_run,
            headed=False, interactive=False,
            verbose=False, sleep=0,
        )

    def _run(self, args, timecards=None, submit_return=True):
        tcs = timecards if timecards is not None else self.all_timecards
        with patch("punch.commands.get_timecards", return_value=tcs), \
             patch("punch.commands.submit_timecards", return_value=submit_return) as mock_submit, \
             patch("punch.commands.show_timecards_table"), \
             patch("punch.commands.get_config_path", return_value=self.config_path):
            handle_submit(args, self.config, "tasks.txt", self.console)
        return mock_submit

    def test_no_resume_submits_all_timecards(self):
        mock_submit = self._run(self._args(resume=False))
        mock_submit.assert_called_once()
        submitted_tcs = mock_submit.call_args[0][1]
        self.assertEqual(submitted_tcs, self.all_timecards)

    def test_no_resume_passes_on_progress_for_crash_recovery(self):
        # on_progress should be passed even without --resume so a mid-run crash
        # leaves a recoverable progress file
        mock_submit = self._run(self._args(resume=False))
        on_progress = mock_submit.call_args.kwargs["on_progress"]
        self.assertIsNotNone(on_progress)

    def test_dry_run_does_not_pass_on_progress(self):
        mock_submit = self._run(self._args(dry_run=True))
        on_progress = mock_submit.call_args.kwargs["on_progress"]
        self.assertIsNone(on_progress)

    def test_resume_with_no_progress_file_submits_all(self):
        mock_submit = self._run(self._args(resume=True))
        submitted_tcs = mock_submit.call_args[0][1]
        self.assertEqual(submitted_tcs, self.all_timecards)

    def test_resume_skips_already_submitted_entries(self):
        already_done = {timecard_id(self.tc1), timecard_id(self.tc2)}
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress(already_done)

        mock_submit = self._run(self._args(resume=True))
        submitted_tcs = mock_submit.call_args[0][1]
        self.assertEqual(submitted_tcs, [self.tc3])

    def test_resume_prints_skip_count(self):
        already_done = {timecard_id(self.tc1), timecard_id(self.tc2)}
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress(already_done)

        self._run(self._args(resume=True))
        printed = " ".join(str(c) for c in self.console.print.call_args_list)
        self.assertIn("2", printed)
        self.assertIn("skip", printed.lower())

    def test_resume_all_done_does_not_call_submit(self):
        all_done = {timecard_id(tc) for tc in self.all_timecards}
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress(all_done)

        mock_submit = self._run(self._args(resume=True))
        mock_submit.assert_not_called()

    def test_resume_all_done_clears_progress_file(self):
        all_done = {timecard_id(tc) for tc in self.all_timecards}
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress(all_done)
            self._run(self._args(resume=True))
            self.assertEqual(_load_progress(), set())

    def test_on_progress_callback_saves_id_to_file(self):
        captured_callback = {}

        def fake_submit(_config, _timecards, **kwargs):
            captured_callback["fn"] = kwargs.get("on_progress")

        with patch("punch.commands.get_timecards", return_value=self.all_timecards), \
             patch("punch.commands.submit_timecards", side_effect=fake_submit), \
             patch("punch.commands.show_timecards_table"), \
             patch("punch.commands.get_config_path", return_value=self.config_path):
            handle_submit(self._args(), self.config, "tasks.txt", self.console)

        on_progress = captured_callback["fn"]
        self.assertIsNotNone(on_progress)

        test_id = timecard_id(self.tc1)
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            on_progress(test_id)
            self.assertIn(test_id, _load_progress())

    def test_progress_cleared_after_successful_non_dry_run(self):
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress({"leftover"})

        self._run(self._args(resume=False, dry_run=False))

        with patch("punch.commands.get_config_path", return_value=self.config_path):
            self.assertEqual(_load_progress(), set())

    def test_progress_not_cleared_after_dry_run(self):
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress({"leftover"})

        self._run(self._args(dry_run=True))

        with patch("punch.commands.get_config_path", return_value=self.config_path):
            self.assertIn("leftover", _load_progress())

    def test_cancelled_submission_does_not_clear_progress(self):
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress({"leftover"})

        self.console.input.return_value = "n"
        self._run(self._args(resume=False))

        with patch("punch.commands.get_config_path", return_value=self.config_path):
            self.assertIn("leftover", _load_progress())

    def test_progress_not_cleared_after_incomplete_submission(self):
        with patch("punch.commands.get_config_path", return_value=self.config_path):
            _save_progress({"leftover"})

        self._run(self._args(resume=False, dry_run=False), submit_return=False)

        with patch("punch.commands.get_config_path", return_value=self.config_path):
            self.assertIn("leftover", _load_progress())


if __name__ == "__main__":
    unittest.main()
