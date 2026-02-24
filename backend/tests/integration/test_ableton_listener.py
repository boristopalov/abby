"""
------------------------
Integration tests for the AbletonListener remote script.

Usage:
    # Run all tests (Ableton must be open with the script loaded):
    uv run pytest tests/integration/test_ableton_listener.py -v

    # Skip destructive write tests (safe read-only mode):
    uv run pytest tests/integration/test_ableton_listener.py -v -m "not write"

    # Run only a specific test:
    uv run pytest tests/integration/test_ableton_listener.py -v -k "test_get_session_info"

Configuration:
    Set HOST / PORT below if your script runs on a different address.
"""

import json
import socket
import time

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 9877
TIMEOUT = 5  # seconds

# These are used by write tests — adjust to a track/slot that exists in your
# current Ableton project before running.
TEST_TRACK_INDEX = 0
TEST_CLIP_SLOT_INDEX = 0  # must be EMPTY before the create_clip test runs
TEST_DEVICE_INDEX = 0
TEST_PARAMETER_INDEX = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def send_command(cmd: dict) -> dict:
    """Open a fresh TCP connection, send one JSON command, return the response."""
    with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
        sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
        response_bytes = sock.makefile("r").readline()
    return json.loads(response_bytes)


def cmd(type_: str, params: dict | None = None, id_: str = "test") -> dict:
    return {"id": id_, "type": type_, "params": params or {}}


def assert_success(response: dict) -> dict:
    """Assert the response is a success and return the result payload."""
    assert response.get("status") == "success", f"Expected success, got: {response}"
    assert "result" in response, f"No 'result' key in response: {response}"
    return response["result"]


# ---------------------------------------------------------------------------
# Connection smoke test
# ---------------------------------------------------------------------------


class TestConnection:
    def test_server_reachable(self):
        """TCP connection to the script should succeed."""
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT):
            pass  # just connecting is enough

    def test_unknown_command_returns_error(self):
        response = send_command(cmd("this_command_does_not_exist"))
        assert response["status"] == "error"
        assert "Unknown command" in response.get("message", "")

    def test_response_echoes_id(self):
        response = send_command(cmd("get_session_info", id_="my-unique-id-42"))
        assert response.get("id") == "my-unique-id-42"

    def test_malformed_json_is_skipped(self):
        """Sending garbage should not crash the server; next valid command works."""
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
            f = sock.makefile("r")
            # send garbage first
            sock.sendall(b"not valid json\n")
            time.sleep(0.1)
            # then a real command on the same connection
            sock.sendall((json.dumps(cmd("get_session_info")) + "\n").encode())
            response = json.loads(f.readline())
        assert response["status"] == "success"


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


class TestGetSessionInfo:
    def test_returns_success(self):
        result = assert_success(send_command(cmd("get_session_info")))
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = assert_success(send_command(cmd("get_session_info")))
        for key in (
            "tempo",
            "signature_numerator",
            "signature_denominator",
            "track_count",
            "return_track_count",
            "master_track",
        ):
            assert key in result, f"Missing key: {key}"

    def test_tempo_is_positive_float(self):
        result = assert_success(send_command(cmd("get_session_info")))
        assert isinstance(result["tempo"], (int, float))
        assert result["tempo"] > 0

    def test_master_track_has_volume_and_panning(self):
        result = assert_success(send_command(cmd("get_session_info")))
        mt = result["master_track"]
        assert "volume" in mt
        assert "panning" in mt


class TestGetTrackInfo:
    def test_returns_success(self):
        result = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        for key in (
            "index",
            "name",
            "is_audio_track",
            "is_midi_track",
            "mute",
            "solo",
            "arm",
            "volume",
            "panning",
            "clip_slots",
            "devices",
        ):
            assert key in result, f"Missing key: {key}"

    def test_clip_slots_is_list(self):
        result = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        assert isinstance(result["clip_slots"], list)

    def test_invalid_track_index_returns_error(self):
        response = send_command(cmd("get_track_info", {"track_index": 9999}))
        assert response["status"] == "error"


class TestGetTrackDevices:
    def test_returns_success(self):
        result = assert_success(
            send_command(cmd("get_track_devices", {"track_index": TEST_TRACK_INDEX}))
        )
        assert isinstance(result, dict)

    def test_has_devices_list(self):
        result = assert_success(
            send_command(cmd("get_track_devices", {"track_index": TEST_TRACK_INDEX}))
        )
        assert "devices" in result
        assert isinstance(result["devices"], list)

    def test_device_entries_have_required_fields(self):
        result = assert_success(
            send_command(cmd("get_track_devices", {"track_index": TEST_TRACK_INDEX}))
        )
        for device in result["devices"]:
            assert "index" in device
            assert "name" in device
            assert "class_name" in device


class TestGetDeviceParameters:
    @pytest.fixture(autouse=True)
    def skip_if_no_device(self):
        """Skip this class if track 0 has no devices."""
        result = assert_success(
            send_command(cmd("get_track_devices", {"track_index": TEST_TRACK_INDEX}))
        )
        if not result["devices"]:
            pytest.skip(
                f"Track {TEST_TRACK_INDEX} has no devices — skipping parameter tests"
            )

    def test_returns_success(self):
        result = assert_success(
            send_command(
                cmd(
                    "get_device_parameters",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                    },
                )
            )
        )
        assert isinstance(result, dict)

    def test_has_parameters_list(self):
        result = assert_success(
            send_command(
                cmd(
                    "get_device_parameters",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                    },
                )
            )
        )
        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0

    def test_parameter_fields(self):
        result = assert_success(
            send_command(
                cmd(
                    "get_device_parameters",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                    },
                )
            )
        )
        for p in result["parameters"]:
            for field in (
                "index",
                "name",
                "value",
                "min",
                "max",
                "value_string",
                "is_quantized",
            ):
                assert field in p, f"Parameter missing field: {field}"

    def test_invalid_device_index_returns_error(self):
        response = send_command(
            cmd(
                "get_device_parameters",
                {"track_index": TEST_TRACK_INDEX, "device_index": 9999},
            )
        )
        assert response["status"] == "error"


class TestGetProjectIndex:
    def test_returns_success(self):
        result = assert_success(send_command(cmd("get_project_index")))
        assert isinstance(result, dict)

    def test_top_level_keys(self):
        result = assert_success(send_command(cmd("get_project_index")))
        for key in ("tempo", "track_count", "tracks", "master_track"):
            assert key in result, f"Missing key: {key}"

    def test_tracks_list_length_matches_track_count(self):
        result = assert_success(send_command(cmd("get_project_index")))
        assert len(result["tracks"]) == result["track_count"]

    def test_each_track_has_devices_and_clips(self):
        result = assert_success(send_command(cmd("get_project_index")))
        for track in result["tracks"]:
            assert "devices" in track
            assert "clip_slots" in track


class TestGetBrowserTree:
    def test_all_categories(self):
        result = assert_success(
            send_command(cmd("get_browser_tree", {"category_type": "all"}))
        )
        assert "categories" in result
        assert isinstance(result["categories"], list)

    def test_instruments_only(self):
        result = assert_success(
            send_command(cmd("get_browser_tree", {"category_type": "instruments"}))
        )
        assert "categories" in result

    def test_available_categories_key_present(self):
        result = assert_success(
            send_command(cmd("get_browser_tree", {"category_type": "all"}))
        )
        assert "available_categories" in result


class TestGetBrowserItemsAtPath:
    def test_instruments_root(self):
        result = assert_success(
            send_command(cmd("get_browser_items_at_path", {"path": "instruments"}))
        )
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_sounds_root(self):
        result = assert_success(
            send_command(cmd("get_browser_items_at_path", {"path": "sounds"}))
        )
        assert "items" in result

    def test_invalid_path_returns_error_or_empty(self):
        result = assert_success(
            send_command(
                cmd("get_browser_items_at_path", {"path": "nonexistent_category_xyz"})
            )
        )
        # Either an error key or an empty items list is acceptable
        assert "error" in result or result.get("items") == []


# ---------------------------------------------------------------------------
# Write handlers  (marked with pytest.mark.write)
# ---------------------------------------------------------------------------


@pytest.mark.write
class TestSetTempo:
    @pytest.fixture(autouse=True)
    def restore_tempo(self):
        original = assert_success(send_command(cmd("get_session_info")))["tempo"]
        yield
        send_command(cmd("set_tempo", {"tempo": original}))

    def test_set_tempo_changes_value(self):
        info = assert_success(send_command(cmd("get_session_info")))
        original = info["tempo"]
        new_tempo = 140.0 if original != 140.0 else 120.0
        result = assert_success(send_command(cmd("set_tempo", {"tempo": new_tempo})))
        assert abs(result["tempo"] - new_tempo) < 0.01

    def test_set_tempo_reflected_in_session_info(self):
        new_tempo = 99.5
        send_command(cmd("set_tempo", {"tempo": new_tempo}))
        info = assert_success(send_command(cmd("get_session_info")))
        assert abs(info["tempo"] - new_tempo) < 0.01


@pytest.mark.write
class TestSetTrackName:
    @pytest.fixture(autouse=True)
    def restore_track_name(self):
        original = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )["name"]
        yield
        send_command(
            cmd("set_track_name", {"track_index": TEST_TRACK_INDEX, "name": original})
        )

    def test_rename_track(self):
        new_name = "__pytest_track__"
        result = assert_success(
            send_command(
                cmd(
                    "set_track_name",
                    {"track_index": TEST_TRACK_INDEX, "name": new_name},
                )
            )
        )
        assert result["name"] == new_name

    def test_invalid_track_returns_error(self):
        response = send_command(
            cmd("set_track_name", {"track_index": 9999, "name": "x"})
        )
        assert response["status"] == "error"


@pytest.mark.write
class TestCreateMidiTrack:
    @pytest.fixture(autouse=True)
    def cleanup_created_track(self):
        before = assert_success(send_command(cmd("get_session_info")))["track_count"]
        yield
        after = assert_success(send_command(cmd("get_session_info")))["track_count"]
        for _ in range(after - before):
            send_command(cmd("delete_track", {"index": before}))

    def test_creates_track_at_end(self):
        before = assert_success(send_command(cmd("get_session_info")))["track_count"]
        result = assert_success(send_command(cmd("create_midi_track", {"index": -1})))
        after = assert_success(send_command(cmd("get_session_info")))["track_count"]

        assert after == before + 1
        assert "index" in result
        assert "name" in result


@pytest.mark.write
class TestClipWorkflow:
    """
    Tests create_clip → add_notes_to_clip → set_clip_name → fire_clip → stop_clip
    in sequence.  Requires TEST_CLIP_SLOT_INDEX to be empty on the test track.
    """

    @classmethod
    def setup_class(cls):
        track = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        if not track["is_midi_track"]:
            pytest.skip(
                f"Track {TEST_TRACK_INDEX} is not a MIDI track — skipping clip workflow tests"
            )
        if track["clip_slots"][TEST_CLIP_SLOT_INDEX]["has_clip"]:
            pytest.skip(
                f"Track {TEST_TRACK_INDEX} slot {TEST_CLIP_SLOT_INDEX} already has a clip — skipping clip workflow tests"
            )

    @classmethod
    def teardown_class(cls):
        track = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        if track["clip_slots"][TEST_CLIP_SLOT_INDEX]["has_clip"]:
            send_command(
                cmd(
                    "delete_clip",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "clip_index": TEST_CLIP_SLOT_INDEX,
                    },
                )
            )

    def test_01_create_clip(self):
        response = send_command(
            cmd(
                "create_clip",
                {
                    "track_index": TEST_TRACK_INDEX,
                    "clip_index": TEST_CLIP_SLOT_INDEX,
                    "length": 4.0,
                },
            )
        )
        result = assert_success(response)
        assert result["length"] == 4.0

    def test_02_add_notes(self):
        notes = [
            {
                "pitch": 60,
                "start_time": 0.0,
                "duration": 0.5,
                "velocity": 100,
                "mute": False,
            },
            {
                "pitch": 64,
                "start_time": 0.5,
                "duration": 0.5,
                "velocity": 90,
                "mute": False,
            },
            {
                "pitch": 67,
                "start_time": 1.0,
                "duration": 1.0,
                "velocity": 80,
                "mute": False,
            },
            {
                "pitch": 60,
                "start_time": 2.0,
                "duration": 2.0,
                "velocity": 70,
                "mute": False,
            },
        ]
        result = assert_success(
            send_command(
                cmd(
                    "add_notes_to_clip",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "clip_index": TEST_CLIP_SLOT_INDEX,
                        "notes": notes,
                    },
                )
            )
        )
        assert result["note_count"] == len(notes)

    def test_03_set_clip_name(self):
        result = assert_success(
            send_command(
                cmd(
                    "set_clip_name",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "clip_index": TEST_CLIP_SLOT_INDEX,
                        "name": "pytest clip",
                    },
                )
            )
        )
        assert result["name"] == "pytest clip"

    def test_04_clip_name_reflected_in_track_info(self):
        track = assert_success(
            send_command(cmd("get_track_info", {"track_index": TEST_TRACK_INDEX}))
        )
        slot = track["clip_slots"][TEST_CLIP_SLOT_INDEX]
        assert slot["has_clip"]
        assert slot["clip"]["name"] == "pytest clip"

    def test_05_fire_clip(self):
        result = assert_success(
            send_command(
                cmd(
                    "fire_clip",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "clip_index": TEST_CLIP_SLOT_INDEX,
                    },
                )
            )
        )
        assert result["fired"] is True

    def test_06_stop_clip(self):
        time.sleep(0.5)
        result = assert_success(
            send_command(
                cmd(
                    "stop_clip",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "clip_index": TEST_CLIP_SLOT_INDEX,
                    },
                )
            )
        )
        assert result["stopped"] is True


@pytest.mark.write
class TestSetDeviceParameter:
    @pytest.fixture(autouse=True)
    def skip_if_no_device(self):
        result = assert_success(
            send_command(cmd("get_track_devices", {"track_index": TEST_TRACK_INDEX}))
        )
        if not result["devices"]:
            pytest.skip(f"Track {TEST_TRACK_INDEX} has no devices")

    @pytest.fixture(autouse=True)
    def restore_parameter(self):
        params = assert_success(
            send_command(
                cmd(
                    "get_device_parameters",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                    },
                )
            )
        )["parameters"]
        if not params:
            yield
            return
        original_value = params[TEST_PARAMETER_INDEX]["value"]
        yield
        send_command(
            cmd(
                "set_device_parameter",
                {
                    "track_index": TEST_TRACK_INDEX,
                    "device_index": TEST_DEVICE_INDEX,
                    "parameter_index": TEST_PARAMETER_INDEX,
                    "value": original_value,
                },
            )
        )

    def test_set_parameter_value(self):
        params = assert_success(
            send_command(
                cmd(
                    "get_device_parameters",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                    },
                )
            )
        )["parameters"]

        if not params:
            pytest.skip("Device has no parameters")

        p = params[TEST_PARAMETER_INDEX]
        mid_value = (p["min"] + p["max"]) / 2.0

        # this might fail sometimes, e.g. if we have a binary value like on/off
        result = assert_success(
            send_command(
                cmd(
                    "set_device_parameter",
                    {
                        "track_index": TEST_TRACK_INDEX,
                        "device_index": TEST_DEVICE_INDEX,
                        "parameter_index": 1,
                        "value": mid_value,
                    },
                )
            )
        )

        assert abs(result["value"] - mid_value) < 0.01
        assert "value_string" in result

    def test_invalid_parameter_index_returns_error(self):
        response = send_command(
            cmd(
                "set_device_parameter",
                {
                    "track_index": TEST_TRACK_INDEX,
                    "device_index": TEST_DEVICE_INDEX,
                    "parameter_index": 99999,
                    "value": 0.5,
                },
            )
        )
        assert response["status"] == "error"
