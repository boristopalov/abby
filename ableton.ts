import { encodeOSC, decodeOSC, OSCArgs } from "@deno-plc/adapter-osc";
import { ABLETON_HISTORY_WINDOW } from "./consts.ts";
import { CustomWebSocket } from "./types.d.ts";

type ParameterChange = {
  trackId: number;
  trackName: string;
  deviceId: number;
  deviceName: string;
  paramId: number;
  paramName: string;
  oldValue: number;
  newValue: number;
  min: number;
  max: number;
  timestamp: number;
};

type ParameterData = {
  trackId: number;
  trackName: string;
  deviceId: number;
  deviceName: string;
  paramId: number;
  paramName: string;
  value: number;
  min: number;
  max: number;
  debounceTimer?: number; // Optional param for ignoring smooth parameter transitions
  isInitialValue: boolean;
  timeLastModified: number;
};

export class OSCHandler {
  private connection: Deno.DatagramConn;
  private listeners: Map<string, ((args: OSCArgs) => void)[]>;
  private port: number = 11000;
  private hostname: string = "127.0.0.1";
  private parameterMetadata: Map<string, ParameterData> = new Map();
  private parameterChangeHistory: ParameterChange[] = [];
  private client: CustomWebSocket | undefined = undefined;
  private readonly HISTORY_WINDOW = ABLETON_HISTORY_WINDOW;

  constructor(
    connection: Deno.DatagramConn,
    targetPort?: number,
    hostname?: string
  ) {
    this.connection = connection;
    this.listeners = new Map();
    if (targetPort) this.port = targetPort;
    if (hostname) this.hostname = hostname;
    this.on("/live/error", (error) => {
      console.error("OSC error!", error);
    });
    this.startListening();
  }

  private async startListening() {
    for await (const [data, _] of this.connection) {
      try {
        const [address, args] = decodeOSC(data);
        const addressListeners = this.listeners.get(address);
        if (addressListeners) {
          addressListeners.forEach((listener) => listener(args));
        }
      } catch (error) {
        console.error("Error processing OSC message:", error);
      }
    }
  }

  public setWsClient(ws: CustomWebSocket) {
    this.client = ws;
  }

  public unsetWsClient() {
    this.client = undefined;
  }

  public on(address: string, callback: (args: OSCArgs) => void) {
    if (!this.listeners.has(address)) {
      this.listeners.set(address, []);
    }
    this.listeners.get(address)?.push(callback);
  }

  private async send(address: string, args?: OSCArgs) {
    const encodedMessage = encodeOSC(address, args);
    await this.connection.send(encodedMessage, {
      transport: "udp",
      hostname: this.hostname,
      port: this.port,
    });
  }

  public removeListener(address: string, callback: (args: OSCArgs) => void) {
    const listeners = this.listeners.get(address);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index !== -1) {
        listeners.splice(index, 1);
      }
      if (listeners.length === 0) {
        this.listeners.delete(address);
      }
    }
  }

  public sendOSC(address: string, args?: OSCArgs): Promise<OSCArgs> {
    return new Promise((resolve) => {
      const handler = (response: OSCArgs) => {
        this.removeListener(address, handler);
        resolve(response);
      };
      this.on(address, handler);
      this.send(address, args);
    });
  }
  public getTracksDevices = async (sendProgress = false) => {
    const summary = [];

    // Step 1: Get track count (10% progress)
    if (sendProgress) {
      this.client?.sendMessage({ type: "loading_progress", content: 0 });
    }
    const num_tracks = (await this.sendOSC("/live/song/get/num_tracks"))[0];
    if (sendProgress) {
      this.client?.sendMessage({ type: "loading_progress", content: 10 });
    }

    // Step 2: Get track data (20% progress)
    const track_data = await this.sendOSC("/live/song/get/track_data", [
      0,
      num_tracks,
      "track.name",
    ]);
    if (sendProgress) {
      this.client?.sendMessage({ type: "loading_progress", content: 20 });
    }

    // Step 3: Process each track (remaining 80% distributed across tracks)
    for (const [track_index, track_name] of track_data.entries()) {
      // Calculate progress per track
      if (sendProgress) {
        const progressPerTrack = 30 / track_data.length;
        const currentProgress = 20 + progressPerTrack * track_index;

        this.client?.sendMessage({
          type: "loading_progress",
          content: Math.round(currentProgress),
        });
      }

      const track_num_devices = (
        await this.sendOSC("/live/track/get/num_devices", [track_index])
      )[1];

      if (track_num_devices === 0) {
        continue;
      }

      const track_device_names = await this.sendOSC(
        "/live/track/get/devices/name",
        [track_index]
      );
      const track_device_classes = await this.sendOSC(
        "/live/track/get/devices/class_name",
        [track_index]
      );

      const devices = track_device_names.slice(1).map((name, index) => {
        return {
          id: index,
          name: name,
          class: track_device_classes[index + 1],
        };
      });

      summary.push({
        track_id: track_index,
        track_name: track_name,
        devices: devices,
      });
    }

    // Final progress update
    if (sendProgress) {
      this.client?.sendMessage({ type: "loading_progress", content: 50 });
    }

    return summary;
  };

  // private shouldEvictFromCache(param: ParameterData) {
  //   if (Date.now() - param.timeLastModified >)
  // }

  public async subscribeToDeviceParameters() {
    // First get all tracks and their devices
    this.client?.sendMessage({
      type: "loading_progress",
      content: 0,
    });

    const tracks = await this.getTracksDevices(true);

    // Calculate total steps for progress tracking
    let totalDevices = 0;
    let processedDevices = 0;
    let totalParams = 0;
    let processedParams = 0;

    for (const track of tracks) {
      totalDevices += track.devices.length;
    }

    // Set up listeners and store metadata
    for (const track of tracks) {
      for (const device of track.devices) {
        const parameters = await this.getParameters(track.track_id, device.id);
        totalParams += parameters.length;

        parameters.forEach((param) => {
          // Store metadata for this parameter
          const key = `${track.track_id}-${device.id}-${param.param_id}`;
          this.parameterMetadata.set(key, {
            trackId: track.track_id,
            trackName: track.track_name.toString(),
            deviceId: device.id,
            deviceName: device.name.toString(),
            paramId: param.param_id,
            paramName: param.name.toString(),
            value: param.value as number,
            min: parseFloat(param.min.toString()),
            max: parseFloat(param.max.toString()),
            isInitialValue: false,
            timeLastModified: Date.now(),
          });

          // Start listening for this parameter
          this.send("/live/device/start_listen/parameter/value", [
            track.track_id,
            device.id,
            param.param_id,
          ]);

          processedParams++;
        });

        processedDevices++;
        // Calculate and send progress (50-100%)
        const progress = Math.round(
          50 + (processedDevices / totalDevices) * 50
        );
        this.client?.sendMessage({
          type: "loading_progress",
          content: progress,
        });
      }
    }

    // Single listener for all parameter changes
    this.on("/live/device/get/parameter/value", (args) => {
      const [trackId, deviceId, paramId, value] = args;
      const newValue = value as number;
      const key = `${trackId}-${deviceId}-${paramId}`;
      const metadata = this.parameterMetadata.get(key);

      if (metadata) {
        if (metadata.isInitialValue) {
          metadata.isInitialValue = false;
          this.parameterMetadata.set(key, metadata);
          return;
        }

        // Skip if the value hasn't actually changed
        if (metadata.value === newValue) {
          return;
        }

        // Clear existing timeout
        if (metadata.debounceTimer) {
          clearTimeout(metadata.debounceTimer);
        }

        // Set new timeout
        metadata.debounceTimer = setTimeout(() => {
          const change = {
            trackId: metadata.trackId,
            trackName: metadata.trackName,
            deviceId: metadata.deviceId,
            deviceName: metadata.deviceName,
            paramId: metadata.paramId,
            paramName: metadata.paramName,
            oldValue: metadata.value,
            newValue: newValue,
            min: metadata.min,
            max: metadata.max,
            timestamp: Date.now(),
          };
          // Record the parameter change in history
          this.parameterChangeHistory.push(change);

          metadata.value = newValue;
          metadata.timeLastModified = Date.now();
          this.parameterMetadata.set(key, metadata);

          // Clear the timer reference
          metadata.debounceTimer = undefined;
          const log = `Parameter changed:
        Track: ${metadata.trackName} (${trackId})
        Device: ${metadata.deviceName} (${deviceId})
        Parameter: ${metadata.paramName} (${paramId})
        Value: ${value} (range: ${metadata.min}-${metadata.max})`;

          try {
            this.client?.sendMessage({
              type: "parameter_change",
              content: change,
            });
          } catch (e) {
            console.log("error sending websocket message", e);
          }

          console.log("PARAMETER CHANGE:", log);
        }, 500);
      }
    });

    this.client?.sendMessage({
      type: "loading_progress",
      content: 100,
    });
  }

  private filterRecentParameterChanges() {
    const cutoffTime = Date.now() - this.HISTORY_WINDOW;
    this.parameterChangeHistory = this.parameterChangeHistory.filter(
      (change) => change.timestamp > cutoffTime
    );
  }

  public getRecentParameterChanges(): ParameterChange[] {
    // Filter for last 10 minutes only when retrieving
    this.filterRecentParameterChanges();

    if (this.parameterChangeHistory.length === 0) {
      return [];
    }

    return this.parameterChangeHistory;
  }

  public async unsubscribeFromDeviceParameters() {
    const tracks = await this.getTracksDevices();

    this.parameterMetadata.clear();

    for (const track of tracks) {
      for (const device of track.devices) {
        const parameters = await this.getParameters(track.track_id, device.id);

        parameters.forEach((param) => {
          // Stop listening for this parameter
          this.sendOSC("/live/device/stop_listen/parameter/value", [
            track.track_id,
            device.id,
            param.param_id,
          ]);
        });
      }
    }
  }

  public getParameters = async (track_id: number, device_id: number) => {
    const names = await this.sendOSC("/live/device/get/parameters/name", [
      track_id,
      device_id,
    ]);

    const values = await this.sendOSC("/live/device/get/parameters/value", [
      track_id,
      device_id,
    ]);

    const mins = await this.sendOSC("/live/device/get/parameters/min", [
      track_id,
      device_id,
    ]);

    const maxes = await this.sendOSC("/live/device/get/parameters/max", [
      track_id,
      device_id,
    ]);

    // Ableton has placeholder parameters for some reason
    // const offset = names.findIndex((name) => typeof name === "string");
    // console.log("OFFSET:", offset);

    return Array.from({ length: names.length })
      .slice(2)
      .map((_, index) => ({
        param_id: index, // Changed from index
        name: names[index + 2],
        value: values[index + 2],
        min: mins[index + 2],
        max: maxes[index + 2],
      }));
  };

  public setParameter = async (
    track_id: number,
    device_id: number,
    param_id: number,
    value: number
  ) => {
    const deviceName = await this.sendOSC("/live/device/get/name", [
      track_id,
      device_id,
    ]);

    const paramName = (
      await this.sendOSC("/live/device/get/parameters/name", [
        track_id,
        device_id,
      ])
    )[param_id];

    const originalParamValueName = await this.sendOSC(
      "/live/device/get/parameter/value_string",
      [track_id, device_id, param_id]
    );

    console.log("originalParamValueName", originalParamValueName);

    this.sendOSC("/live/device/set/parameter/value", [
      track_id,
      device_id,
      param_id,
      value,
    ]);

    const finalParamValueName = await this.sendOSC(
      "/live/device/get/parameter/value_string",
      [track_id, device_id, param_id]
    );

    return {
      device: deviceName,
      param: paramName,
      from: originalParamValueName,
      to: finalParamValueName,
    };
  };

  public isLive = async () => {
    const timeout = (ms: number) =>
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Timeout")), ms)
      );

    try {
      await Promise.race([
        this.sendOSC("/live/test", []),
        timeout(5000), // timeout time
      ]);
      return true;
    } catch (error) {
      console.error("OSC Error:", error);
      return false;
    }
  };
}
