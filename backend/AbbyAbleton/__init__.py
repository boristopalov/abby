import asyncio
import json
import threading
import traceback

from _Framework.ControlSurface import ControlSurface  # pyright: ignore

DEFAULT_PORT = 9877
HOST = "127.0.0.1"


def create_instance(c_instance):
    return AbletonListener(c_instance)


class AbletonListener(ControlSurface):
    """AbletonListener Remote Script for Ableton Live"""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._song = self.song()
        self._clients = set()  # set of asyncio.StreamWriter. In theory there we should only have one client at a time
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._setup_dispatch()
        self.log_message(
            "AbletonListener blah initialized on port " + str(DEFAULT_PORT)
        )
        self.show_message("AbletonListener: Listening on port " + str(DEFAULT_PORT))

    def disconnect(self):
        """Called when Ableton closes or the control surface is removed"""
        self.log_message("AbletonListener disconnecting")
        if hasattr(self, "_server"):
            self._loop.call_soon_threadsafe(self._server.close)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(2.0)
        ControlSurface.disconnect(self)

    # --- Asyncio server ---

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_server())
        self._loop.run_forever()

    async def _start_server(self):
        self._server = await asyncio.start_server(
            self._handle_client, HOST, DEFAULT_PORT, reuse_address=True
        )

    async def _handle_client(self, reader, writer):
        """Handle one TCP connection. Protocol: one JSON object per line."""
        peer = writer.get_extra_info("peername")
        self.log_message(f"Client connected: {peer}")
        self._clients.add(writer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    command = json.loads(line)
                except ValueError:
                    self.log_message(f"Invalid JSON from {peer}: {line[:200]}")
                    continue
                response = await self._dispatch(command)
                # Echo the request id back so the client can match response to request
                if "id" in command:
                    response["id"] = command["id"]
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
        finally:
            self._clients.discard(writer)
            writer.close()
            self.log_message(f"Client disconnected: {peer}")

    async def _dispatch(self, command):
        """Route a command dict to its handler.

        Read handlers are called directly on the asyncio thread — safe for
        Live's song object as long as we only read state.

        Write handlers must touch Live's state and are therefore scheduled on
        Live's main thread via schedule_message; a Future bridges back to this
        coroutine so the caller can await the result.
        """
        cmd_type = command.get("type", "")
        params = command.get("params", {})

        if cmd_type in self._read_handlers:
            try:
                result = self._read_handlers[cmd_type](params)
                return {"status": "success", "result": result}
            except Exception as e:
                self.log_message(f"Read handler error {cmd_type} params={params}: {e}")
                return {"status": "error", "message": str(e)}

        if cmd_type in self._write_handlers:
            future = self._loop.create_future()

            def main_thread_task():
                try:
                    result = self._write_handlers[cmd_type](params)
                    self._loop.call_soon_threadsafe(
                        future.set_result, {"status": "success", "result": result}
                    )
                except Exception as e:
                    self.log_message(
                        f"Write handler error {cmd_type} params={params}: {e}"
                    )
                    self._loop.call_soon_threadsafe(
                        future.set_result, {"status": "error", "message": str(e)}
                    )

            try:
                self.schedule_message(0, main_thread_task)
            except AssertionError:
                # Already on the main thread — execute directly
                main_thread_task()

            try:
                return await asyncio.wait_for(future, timeout=10.0)
            except asyncio.TimeoutError:
                self.log_message(
                    f"Timeout waiting for main thread on {cmd_type} params={params}"
                )
                return {"status": "error", "message": "Timeout waiting for main thread"}

        self.log_message(f"Unknown command: {cmd_type}")
        return {"status": "error", "message": "Unknown command: " + cmd_type}

    async def push_event(self, event_type, data):
        """Push an unsolicited event to all connected clients.

        Push events have no 'id' field, so the client read loop can distinguish
        them from command responses.
        """
        message = (json.dumps({"type": event_type, "data": data}) + "\n").encode(
            "utf-8"
        )
        for writer in list(self._clients):
            try:
                writer.write(message)
                await writer.drain()
            except Exception:
                self._clients.discard(writer)

    # --- Dispatch table ---

    def _setup_dispatch(self):
        """Build read/write handler dicts.

        Read handlers are safe to call on the asyncio thread (no Live state mutation).
        Write handlers must run on Live's main thread and are scheduled accordingly.

        NOTE: _get_browser_categories and _get_browser_items are registered here
        for protocol completeness but have no implementation yet — they will raise
        AttributeError and return an error response if called.
        """
        self._read_handlers = {
            "get_session_info": lambda p: self._get_session_info(),
            "get_track_info": lambda p: self._get_track_info(p["track_index"]),
            "get_track_devices": lambda p: self._get_track_devices(p["track_index"]),
            "get_device_parameters": lambda p: self._get_device_parameters(
                p["track_index"], p["device_index"]
            ),
            "get_project_index": lambda p: self._get_project_index(),
            "get_browser_item": lambda p: self._get_browser_item(
                p.get("uri"), p.get("path")
            ),
            "get_browser_categories": lambda p: self._get_browser_categories(
                p.get("category_type", "all")
            ),
            "get_browser_items": lambda p: self._get_browser_items(
                p.get("path", ""), p.get("item_type", "all")
            ),
            "get_browser_tree": lambda p: self.get_browser_tree(
                p.get("category_type", "all")
            ),
            "get_browser_items_at_path": lambda p: self.get_browser_items_at_path(
                p.get("path", "")
            ),
        }
        self._write_handlers = {
            "set_tempo": lambda p: self._set_tempo(p["tempo"]),
            "set_track_name": lambda p: self._set_track_name(
                p["track_index"], p["name"]
            ),
            "set_device_parameter": lambda p: self._set_device_parameter(
                p["track_index"], p["device_index"], p["parameter_index"], p["value"]
            ),
            "create_midi_track": lambda p: self._create_midi_track(p.get("index", -1)),
            "create_audio_track": lambda p: self._create_audio_track(),
            "delete_track": lambda p: self._delete_track(p.get("index")),
            "create_clip": lambda p: self._create_clip(
                p["track_index"], p["clip_index"], p.get("length", 4.0)
            ),
            "delete_clip": lambda p: self._delete_clip(
                p["track_index"], p["clip_index"]
            ),
            "add_notes_to_clip": lambda p: self._add_notes_to_clip(
                p["track_index"], p["clip_index"], p["notes"]
            ),
            "set_clip_name": lambda p: self._set_clip_name(
                p["track_index"], p["clip_index"], p["name"]
            ),
            "fire_clip": lambda p: self._fire_clip(p["track_index"], p["clip_index"]),
            "stop_clip": lambda p: self._stop_clip(p["track_index"], p["clip_index"]),
            "start_playback": lambda p: self._start_playback(),
            "stop_playback": lambda p: self._stop_playback(),
            "load_browser_item": lambda p: self._load_browser_item(
                p["track_index"], p["item_uri"]
            ),
        }

    # --- Command implementations (unchanged from original) ---

    def _get_session_info(self):
        """Get information about the current session"""
        try:
            result = {
                "tempo": self._song.tempo,
                "signature_numerator": self._song.signature_numerator,
                "signature_denominator": self._song.signature_denominator,
                "track_count": len(self._song.tracks),
                "return_track_count": len(self._song.return_tracks),
                "master_track": {
                    "name": "Master",
                    "volume": self._song.master_track.mixer_device.volume.value,
                    "panning": self._song.master_track.mixer_device.panning.value,
                },
            }
            return result
        except Exception as e:
            self.log_message("Error getting session info: " + str(e))
            raise

    def _get_track_info(self, track_index):
        """Get information about a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError(f"Track index {track_index} out of range")

            track = self._song.tracks[track_index]

            # Get clip slots
            clip_slots = []
            for slot_index, slot in enumerate(track.clip_slots):
                clip_info = None
                if slot.has_clip:
                    clip = slot.clip
                    clip_info = {
                        "name": clip.name,
                        "length": clip.length,
                        "is_playing": clip.is_playing,
                        "is_recording": self._safe_track_prop(clip, "is_recording"),
                    }

                clip_slots.append(
                    {"index": slot_index, "has_clip": slot.has_clip, "clip": clip_info}
                )

            # Get devices
            devices = []
            for device_index, device in enumerate(track.devices):
                devices.append(
                    {
                        "index": device_index,
                        "name": device.name,
                        "class_name": device.class_name,
                        "type": self._get_device_type(device),
                    }
                )

            result = {
                "index": track_index,
                "name": track.name,
                "is_audio_track": self._safe_track_prop(track, "has_audio_input"),
                "is_midi_track": self._safe_track_prop(track, "has_midi_input"),
                "mute": self._safe_track_prop(track, "mute"),
                "solo": self._safe_track_prop(track, "solo"),
                "arm": self._safe_track_prop(track, "arm"),
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "clip_slots": clip_slots,
                "devices": devices,
            }
            return result
        except Exception as e:
            self.log_message(
                f"Error getting track info for track index {track_index}: " + str(e)
            )
            raise

    def _get_track_devices(self, track_index):
        """Get the list of devices on a track."""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            track = self._song.tracks[track_index]
            devices = []
            for i, device in enumerate(track.devices):
                devices.append(
                    {
                        "index": i,
                        "name": device.name,
                        "class_name": device.class_name,
                    }
                )
            return {
                "track_index": track_index,
                "track_name": track.name,
                "devices": devices,
            }
        except Exception as e:
            self.log_message(
                f"Error getting track devices for track {track_index}: {e}"
            )
            raise

    def _get_device_parameters(self, track_index, device_index):
        """Get all parameters for a single device.

        Returns name, current value, min, max, display string, and quantization
        flag for every parameter — replaces 5+ per-property OSC calls.
        """
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")
            track = self._song.tracks[track_index]
            if device_index < 0 or device_index >= len(track.devices):
                raise IndexError("Device index out of range")
            device = track.devices[device_index]
            params = []
            for i, p in enumerate(device.parameters):
                try:
                    value_string = str(p.str_for_value(p.value))
                except Exception:
                    value_string = str(round(p.value, 4))
                params.append(
                    {
                        "index": i,
                        "name": p.name,
                        "value": p.value,
                        "min": p.min,
                        "max": p.max,
                        "value_string": value_string,
                        "is_quantized": p.is_quantized,
                    }
                )
            return {
                "track_index": track_index,
                "device_index": device_index,
                "device_name": device.name,
                "class_name": device.class_name,
                "track_name": track.name,
                "parameters": params,
            }
        except Exception as e:
            self.log_message(
                f"Error getting device parameters for track {track_index}, device {device_index}: {e}"
            )
            raise

    def _get_project_index(self):
        """Return the full project structure in one call.

        Replaces ~800 individual OSC round trips with a single TCP request:
        session info + all tracks + all devices + all parameters.
        """
        try:
            tracks = []
            for track_index, track in enumerate(self._song.tracks):
                devices = []
                for device_index, device in enumerate(track.devices):
                    params = []
                    for i, p in enumerate(device.parameters):
                        try:
                            value_string = str(p.str_for_value(p.value))
                        except Exception:
                            value_string = str(round(p.value, 4))
                        params.append(
                            {
                                "index": i,
                                "name": p.name,
                                "value": p.value,
                                "min": p.min,
                                "max": p.max,
                                "value_string": value_string,
                                "is_quantized": p.is_quantized,
                            }
                        )
                    devices.append(
                        {
                            "index": device_index,
                            "name": device.name,
                            "class_name": device.class_name,
                            "parameters": params,
                        }
                    )

                clip_slots = []
                for slot_index, slot in enumerate(track.clip_slots):
                    clip_info = None
                    if slot.has_clip:
                        clip = slot.clip
                        clip_info = {
                            "name": clip.name,
                            "length": clip.length,
                            "is_playing": clip.is_playing,
                            "is_recording": self._safe_track_prop(clip, "is_recording"),
                        }
                    clip_slots.append(
                        {
                            "index": slot_index,
                            "has_clip": slot.has_clip,
                            "clip": clip_info,
                        }
                    )

                tracks.append(
                    {
                        "index": track_index,
                        "name": track.name,
                        "is_audio_track": self._safe_track_prop(
                            track, "has_audio_input"
                        ),
                        "is_midi_track": self._safe_track_prop(track, "has_midi_input"),
                        "mute": self._safe_track_prop(track, "mute"),
                        "solo": self._safe_track_prop(track, "solo"),
                        "arm": self._safe_track_prop(track, "arm"),
                        "volume": track.mixer_device.volume.value,
                        "panning": track.mixer_device.panning.value,
                        "devices": devices,
                        "clip_slots": clip_slots,
                    }
                )

            return {
                "tempo": self._song.tempo,
                "signature_numerator": self._song.signature_numerator,
                "signature_denominator": self._song.signature_denominator,
                "track_count": len(self._song.tracks),
                "return_track_count": len(self._song.return_tracks),
                "master_track": {
                    "volume": self._song.master_track.mixer_device.volume.value,
                    "panning": self._song.master_track.mixer_device.panning.value,
                },
                "tracks": tracks,
            }
        except Exception as e:
            self.log_message("Error getting project index: " + str(e))
            raise

    def _set_device_parameter(self, track_index, device_index, parameter_index, value):
        """Set a device parameter value and return the new display string."""
        try:
            track = self._song.tracks[track_index]
            device = track.devices[device_index]
            param = device.parameters[parameter_index]
            param.value = value
            try:
                value_string = str(param.str_for_value(param.value))
            except Exception:
                value_string = str(round(param.value, 4))
            return {"value": param.value, "value_string": value_string}
        except Exception as e:
            self.log_message(
                f"Error setting device parameter for track {track_index}, device {device_index}, param {parameter_index} to {value}: {e}"
            )
            raise

    def _create_midi_track(self, index):
        """Create a new MIDI track at the specified index"""
        try:
            self._song.create_midi_track(index)

            new_track_index = len(self._song.tracks) - 1 if index == -1 else index
            new_track = self._song.tracks[new_track_index]

            result = {"index": new_track_index, "name": new_track.name}
            return result
        except Exception as e:
            self.log_message(f"Error creating MIDI track at index {index}: {e}")
            raise

    def _create_audio_track(self):
        """Create a new Audio track at the end."""
        try:
            self._song.create_audio_track()

            new_track = self._song.tracks[-1]

            result = {"index": len(self._song.tracks), "name": new_track.name}
            return result

        except Exception as e:
            self.log_message(f"Error creating audio track: {e}")
            raise

    def _delete_track(self, index):
        """Delete a track at the specificed index"""
        try:
            self._song.delete_track(index)

            result = {"index": index}
            return result
        except Exception as e:
            self.log_message(f"Error deleting track at index {index}: {e}")
            raise

    def _set_track_name(self, track_index, name):
        """Set the name of a track"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]
            track.name = name

            result = {"name": track.name}
            return result
        except Exception as e:
            self.log_message(f"Error setting track {track_index} name to '{name}': {e}")
            raise

    def _create_clip(self, track_index, clip_index, length):
        """Create a new MIDI clip in the specified track and clip slot"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]

            if clip_slot.has_clip:
                raise Exception("Clip slot already has a clip")

            clip_slot.create_clip(length)

            result = {"name": clip_slot.clip.name, "length": clip_slot.clip.length}
            return result
        except Exception as e:
            self.log_message(
                f"Error creating clip at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _delete_clip(self, track_index, clip_index):
        """Delete a MIDI clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]
            if not clip_slot.has_clip:
                raise Exception("Clip slot does not have a clip")

            clip_slot.delete_clip()
            return {"success": True}
        except Exception as e:
            self.log_message(
                f"Error deleting clip at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _add_notes_to_clip(self, track_index, clip_index, notes):
        """Add MIDI notes to a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]

            if not clip_slot.has_clip:
                raise Exception("No clip in slot")

            clip = clip_slot.clip

            live_notes = []
            for note in notes:
                pitch = note.get("pitch", 60)
                start_time = note.get("start_time", 0.0)
                duration = note.get("duration", 0.25)
                velocity = note.get("velocity", 100)
                mute = note.get("mute", False)
                live_notes.append((pitch, start_time, duration, velocity, mute))

            clip.set_notes(tuple(live_notes))

            result = {"note_count": len(notes)}
            return result
        except Exception as e:
            self.log_message(
                f"Error adding {len(notes)} notes to clip at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _set_clip_name(self, track_index, clip_index, name):
        """Set the name of a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]

            if not clip_slot.has_clip:
                raise Exception("No clip in slot")

            clip = clip_slot.clip
            clip.name = name

            result = {"name": clip.name}
            return result
        except Exception as e:
            self.log_message(
                f"Error setting clip name to '{name}' at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _set_tempo(self, tempo):
        """Set the tempo of the session"""
        try:
            self._song.tempo = tempo

            result = {"tempo": self._song.tempo}
            return result
        except Exception as e:
            self.log_message(f"Error setting tempo to {tempo}: {e}")
            raise

    def _fire_clip(self, track_index, clip_index):
        """Fire a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]

            if not clip_slot.has_clip:
                raise Exception("No clip in slot")

            clip_slot.fire()

            result = {"fired": True}
            return result
        except Exception as e:
            self.log_message(
                f"Error firing clip at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _stop_clip(self, track_index, clip_index):
        """Stop a clip"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            if clip_index < 0 or clip_index >= len(track.clip_slots):
                raise IndexError("Clip index out of range")

            clip_slot = track.clip_slots[clip_index]
            clip_slot.stop()

            result = {"stopped": True}
            return result
        except Exception as e:
            self.log_message(
                f"Error stopping clip at track {track_index}, slot {clip_index}: {e}"
            )
            raise

    def _start_playback(self):
        """Start playing the session"""
        try:
            self._song.start_playing()

            result = {"playing": self._song.is_playing}
            return result
        except Exception as e:
            self.log_message("Error starting playback: " + str(e))
            raise

    def _stop_playback(self):
        """Stop playing the session"""
        try:
            self._song.stop_playing()

            result = {"playing": self._song.is_playing}
            return result
        except Exception as e:
            self.log_message("Error stopping playback: " + str(e))
            raise

    def _get_browser_item(self, uri, path):
        """Get a browser item by URI or path"""
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")

            result = {"uri": uri, "path": path, "found": False}

            if uri:
                item = self._find_browser_item_by_uri(app.browser, uri)
                if item:
                    result["found"] = True
                    result["item"] = {
                        "name": item.name,
                        "is_folder": item.is_folder,
                        "is_device": item.is_device,
                        "is_loadable": item.is_loadable,
                        "uri": item.uri,
                    }
                    return result

            if path:
                path_parts = path.split("/")

                current_item = None
                if path_parts[0].lower() == "nstruments":
                    current_item = app.browser.instruments
                elif path_parts[0].lower() == "sounds":
                    current_item = app.browser.sounds
                elif path_parts[0].lower() == "drums":
                    current_item = app.browser.drums
                elif path_parts[0].lower() == "audio_effects":
                    current_item = app.browser.audio_effects
                elif path_parts[0].lower() == "midi_effects":
                    current_item = app.browser.midi_effects
                else:
                    current_item = app.browser.instruments
                    path_parts = ["instruments"] + path_parts

                for i in range(1, len(path_parts)):
                    part = path_parts[i]
                    if not part:
                        continue

                    found = False
                    for child in current_item.children:
                        if child.name.lower() == part.lower():
                            current_item = child
                            found = True
                            break

                    if not found:
                        result["error"] = "Path part '{0}' not found".format(part)
                        return result

                result["found"] = True
                result["item"] = {
                    "name": current_item.name,
                    "is_folder": current_item.is_folder,
                    "is_device": current_item.is_device,
                    "is_loadable": current_item.is_loadable,
                    "uri": current_item.uri,
                }

            return result
        except Exception as e:
            self.log_message(
                f"Error getting browser item uri={uri!r} path={path!r}: {e}"
            )
            self.log_message(traceback.format_exc())
            raise

    def _load_browser_item(self, track_index, item_uri):
        """Load a browser item onto a track by its URI"""
        try:
            if track_index < 0 or track_index >= len(self._song.tracks):
                raise IndexError("Track index out of range")

            track = self._song.tracks[track_index]

            app = self.application()

            item = self._find_browser_item_by_uri(app.browser, item_uri)

            if not item:
                raise ValueError(
                    "Browser item with URI '{0}' not found".format(item_uri)
                )

            self._song.view.selected_track = track
            app.browser.load_item(item)

            result = {
                "loaded": True,
                "item_name": item.name,
                "track_name": track.name,
                "uri": item_uri,
            }
            return result
        except Exception as e:
            self.log_message(
                f"Error loading browser item '{item_uri}' onto track {track_index}: {e}"
            )
            self.log_message(traceback.format_exc())
            raise

    def _find_browser_item_by_uri(
        self, browser_or_item, uri, max_depth=10, current_depth=0
    ):
        """Find a browser item by its URI"""
        try:
            if hasattr(browser_or_item, "uri") and browser_or_item.uri == uri:
                return browser_or_item

            if current_depth >= max_depth:
                return None

            if hasattr(browser_or_item, "instruments"):
                categories = [
                    browser_or_item.instruments,
                    browser_or_item.sounds,
                    browser_or_item.drums,
                    browser_or_item.audio_effects,
                    browser_or_item.midi_effects,
                ]

                for category in categories:
                    item = self._find_browser_item_by_uri(
                        category, uri, max_depth, current_depth + 1
                    )
                    if item:
                        return item

                return None

            if hasattr(browser_or_item, "children") and browser_or_item.children:
                for child in browser_or_item.children:
                    item = self._find_browser_item_by_uri(
                        child, uri, max_depth, current_depth + 1
                    )
                    if item:
                        return item

            return None
        except Exception as e:
            self.log_message(f"Error finding browser item by URI {uri!r}: {e}")
            return None

    def _safe_track_prop(self, track, attr, default=False):
        """Read a track property that Live may raise RuntimeError on (e.g. frozen/return tracks)."""
        try:
            return getattr(track, attr)
        except Exception:
            return default

    # --- Helper methods ---

    def _get_device_type(self, device):
        """Get the type of a device"""
        try:
            if device.can_have_drum_pads:
                return "drum_machine"
            elif device.can_have_chains:
                return "rack"
            elif "instrument" in device.class_display_name.lower():
                return "instrument"
            elif "audio_effect" in device.class_name.lower():
                return "audio_effect"
            elif "midi_effect" in device.class_name.lower():
                return "midi_effect"
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def get_browser_tree(self, category_type="all"):
        """
        Get a simplified tree of browser categories.

        Args:
            category_type: Type of categories to get ('all', 'instruments', 'sounds', etc.)

        Returns:
            Dictionary with the browser tree structure
        """
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")

            if not hasattr(app, "browser") or app.browser is None:
                raise RuntimeError("Browser is not available in the Live application")

            browser_attrs = [
                attr for attr in dir(app.browser) if not attr.startswith("_")
            ]
            self.log_message("Available browser attributes: {0}".format(browser_attrs))

            result = {
                "type": category_type,
                "categories": [],
                "available_categories": browser_attrs,
            }

            def process_item(item, depth=0):
                if not item:
                    return None

                result = {
                    "name": item.name if hasattr(item, "name") else "Unknown",
                    "is_folder": hasattr(item, "children") and bool(item.children),
                    "is_device": hasattr(item, "is_device") and item.is_device,
                    "is_loadable": hasattr(item, "is_loadable") and item.is_loadable,
                    "uri": item.uri if hasattr(item, "uri") else None,
                    "children": [],
                }

                return result

            if (category_type == "all" or category_type == "instruments") and hasattr(
                app.browser, "instruments"
            ):
                try:
                    instruments = process_item(app.browser.instruments)
                    if instruments:
                        instruments["name"] = "Instruments"
                        result["categories"].append(instruments)
                except Exception as e:
                    self.log_message("Error processing instruments: {0}".format(str(e)))

            if (category_type == "all" or category_type == "sounds") and hasattr(
                app.browser, "sounds"
            ):
                try:
                    sounds = process_item(app.browser.sounds)
                    if sounds:
                        sounds["name"] = "Sounds"
                        result["categories"].append(sounds)
                except Exception as e:
                    self.log_message("Error processing sounds: {0}".format(str(e)))

            if (category_type == "all" or category_type == "drums") and hasattr(
                app.browser, "drums"
            ):
                try:
                    drums = process_item(app.browser.drums)
                    if drums:
                        drums["name"] = "Drums"
                        result["categories"].append(drums)
                except Exception as e:
                    self.log_message("Error processing drums: {0}".format(str(e)))

            if (category_type == "all" or category_type == "audio_effects") and hasattr(
                app.browser, "audio_effects"
            ):
                try:
                    audio_effects = process_item(app.browser.audio_effects)
                    if audio_effects:
                        audio_effects["name"] = "Audio Effects"
                        result["categories"].append(audio_effects)
                except Exception as e:
                    self.log_message(
                        "Error processing audio_effects: {0}".format(str(e))
                    )

            if (category_type == "all" or category_type == "midi_effects") and hasattr(
                app.browser, "midi_effects"
            ):
                try:
                    midi_effects = process_item(app.browser.midi_effects)
                    if midi_effects:
                        midi_effects["name"] = "MIDI Effects"
                        result["categories"].append(midi_effects)
                except Exception as e:
                    self.log_message(
                        "Error processing midi_effects: {0}".format(str(e))
                    )

            for attr in browser_attrs:
                if attr not in [
                    "instruments",
                    "sounds",
                    "drums",
                    "audio_effects",
                    "midi_effects",
                ] and (category_type == "all" or category_type == attr):
                    try:
                        item = getattr(app.browser, attr)
                        if hasattr(item, "children") or hasattr(item, "name"):
                            category = process_item(item)
                            if category:
                                category["name"] = attr.capitalize()
                                result["categories"].append(category)
                    except Exception as e:
                        self.log_message(
                            "Error processing {0}: {1}".format(attr, str(e))
                        )

            self.log_message(
                "Browser tree generated for {0} with {1} root categories".format(
                    category_type, len(result["categories"])
                )
            )
            return result

        except Exception as e:
            self.log_message("Error getting browser tree: {0}".format(str(e)))
            self.log_message(traceback.format_exc())
            raise

    def get_browser_items_at_path(self, path):
        """
        Get browser items at a specific path.

        Args:
            path: Path in the format "category/folder/subfolder"
                 where category is one of: instruments, sounds, drums, audio_effects, midi_effects
                 or any other available browser category

        Returns:
            Dictionary with items at the specified path
        """
        try:
            app = self.application()
            if not app:
                raise RuntimeError("Could not access Live application")

            if not hasattr(app, "browser") or app.browser is None:
                raise RuntimeError("Browser is not available in the Live application")

            browser_attrs = [
                attr for attr in dir(app.browser) if not attr.startswith("_")
            ]
            self.log_message("Available browser attributes: {0}".format(browser_attrs))

            path_parts = path.split("/")
            if not path_parts:
                raise ValueError("Invalid path")

            root_category = path_parts[0].lower()
            current_item = None

            if root_category == "instruments" and hasattr(app.browser, "instruments"):
                current_item = app.browser.instruments
            elif root_category == "sounds" and hasattr(app.browser, "sounds"):
                current_item = app.browser.sounds
            elif root_category == "drums" and hasattr(app.browser, "drums"):
                current_item = app.browser.drums
            elif root_category == "audio_effects" and hasattr(
                app.browser, "audio_effects"
            ):
                current_item = app.browser.audio_effects
            elif root_category == "midi_effects" and hasattr(
                app.browser, "midi_effects"
            ):
                current_item = app.browser.midi_effects
            else:
                found = False
                for attr in browser_attrs:
                    if attr.lower() == root_category:
                        try:
                            current_item = getattr(app.browser, attr)
                            found = True
                            break
                        except Exception as e:
                            self.log_message(
                                "Error accessing browser attribute {0}: {1}".format(
                                    attr, str(e)
                                )
                            )

                if not found:
                    return {
                        "path": path,
                        "error": "Unknown or unavailable category: {0}".format(
                            root_category
                        ),
                        "available_categories": browser_attrs,
                        "items": [],
                    }

            if current_item is None:
                return {
                    "path": path,
                    "error": "Could not resolve root category: {0}".format(
                        root_category
                    ),
                    "items": [],
                }

            for i in range(1, len(path_parts)):
                part = path_parts[i]
                if not part:
                    continue

                if not hasattr(current_item, "children"):
                    return {
                        "path": path,
                        "error": "Item at '{0}' has no children".format(
                            "/".join(path_parts[:i])
                        ),
                        "items": [],
                    }

                found = False
                for child in current_item.children:
                    if hasattr(child, "name") and child.name.lower() == part.lower():
                        current_item = child
                        found = True
                        break

                if not found:
                    return {
                        "path": path,
                        "error": "Path part '{0}' not found".format(part),
                        "items": [],
                    }

            items = []
            if hasattr(current_item, "children"):
                for child in current_item.children:
                    item_info = {
                        "name": child.name if hasattr(child, "name") else "Unknown",
                        "is_folder": hasattr(child, "children")
                        and bool(child.children),
                        "is_device": hasattr(child, "is_device") and child.is_device,
                        "is_loadable": hasattr(child, "is_loadable")
                        and child.is_loadable,
                        "uri": child.uri if hasattr(child, "uri") else None,
                    }
                    items.append(item_info)

            result = {
                "path": path,
                "name": current_item.name
                if hasattr(current_item, "name")
                else "Unknown",
                "uri": current_item.uri if hasattr(current_item, "uri") else None,
                "is_folder": hasattr(current_item, "children")
                and bool(current_item.children),
                "is_device": hasattr(current_item, "is_device")
                and current_item.is_device,
                "is_loadable": hasattr(current_item, "is_loadable")
                and current_item.is_loadable,
                "items": items,
            }

            self.log_message(
                "Retrieved {0} items at path: {1}".format(len(items), path)
            )
            return result

        except Exception as e:
            self.log_message("Error getting browser items at path: {0}".format(str(e)))
            self.log_message(traceback.format_exc())
            raise
