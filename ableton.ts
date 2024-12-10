import { encodeOSC, decodeOSC, OSCArgs } from "@deno-plc/adapter-osc";
import { ABLETON_HISTORY_WINDOW } from "./consts.ts";

type ParameterChange = {
  trackName: string;
  deviceName: string;
  paramName: string;
  oldValue: number;
  newValue: number;
  min: number;
  max: number;
  timestamp: number;
};

type ParameterData = {
  trackName: string;
  deviceName: string;
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

  public getTracksDevices = async () => {
    const summary = [];
    const num_tracks = (await this.sendOSC("/live/song/get/num_tracks"))[0];

    const track_data = await this.sendOSC("/live/song/get/track_data", [
      0,
      num_tracks,
      "track.name",
    ]);

    for (const [track_index, track_name] of track_data.entries()) {
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
    return summary;
  };

  // private shouldEvictFromCache(param: ParameterData) {
  //   if (Date.now() - param.timeLastModified >)
  // }

  public async subscribeToDeviceParameters() {
    // First get all tracks and their devices
    const tracks = await this.getTracksDevices();

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
        // Clear existing timeout
        if (metadata.debounceTimer) {
          clearTimeout(metadata.debounceTimer);
        }

        // Set new timeout
        metadata.debounceTimer = setTimeout(() => {
          // Record the parameter change in history
          this.parameterChangeHistory.push({
            trackName: metadata.trackName,
            deviceName: metadata.deviceName,
            paramName: metadata.paramName,
            oldValue: metadata.value,
            newValue: newValue,
            min: metadata.min,
            max: metadata.max,
            timestamp: Date.now(),
          });

          metadata.value = newValue;
          metadata.timeLastModified = Date.now();
          this.parameterMetadata.set(key, metadata);

          // Clear the timer reference
          metadata.debounceTimer = undefined;

          console.log(`Parameter changed:
        Track: ${metadata.trackName} (${trackId})
        Device: ${metadata.deviceName} (${deviceId})
        Parameter: ${metadata.paramName} (${paramId})
        Value: ${value} (range: ${metadata.min}-${metadata.max})`);
        }, 500);
      }
    });

    // Set up listeners and store metadata
    for (const track of tracks) {
      for (const device of track.devices) {
        const parameters = await this.getParameters(track.track_id, device.id);

        parameters.forEach((param) => {
          // Store metadata for this parameter
          const key = `${track.track_id}-${device.id}-${param.param_id}`;
          this.parameterMetadata.set(key, {
            trackName: track.track_name.toString(),
            deviceName: device.name.toString(),
            paramName: param.name.toString(),
            value: param.value as number,
            min: parseFloat(param.min.toString()),
            max: parseFloat(param.max.toString()),
            isInitialValue: true,
            timeLastModified: Date.now(),
          });

          // Start listening for this parameter
          // send() instead of sendOSC() b/c we don't need listeners
          this.send("/live/device/start_listen/parameter/value", [
            track.track_id,
            device.id,
            param.param_id,
          ]);
        });
      }
    }
  }

  private filterRecentParameterChanges() {
    const cutoffTime = Date.now() - this.HISTORY_WINDOW;
    this.parameterChangeHistory = this.parameterChangeHistory.filter(
      (change) => change.timestamp > cutoffTime
    );
  }

  public getRecentParameterChanges(): string {
    // Filter for last 10 minutes only when retrieving
    this.filterRecentParameterChanges();
    const minutesElapsed = (this.HISTORY_WINDOW / (1000 * 60)).toFixed(2);

    if (this.parameterChangeHistory.length === 0) {
      return `No parameter changes detected in the last ${minutesElapsed} minutes.`;
    }

    // Group changes by device
    const changesByDevice = new Map<string, Map<string, ParameterChange>>();

    this.parameterChangeHistory.forEach((change) => {
      const deviceKey = `${change.trackName} - ${change.deviceName}`;
      if (!changesByDevice.has(deviceKey)) {
        changesByDevice.set(deviceKey, new Map<string, ParameterChange>());
      }
      const changesByDeviceParam = changesByDevice.get(deviceKey)!; // idk why TS wants me to assert ! here
      const paramKey = `${change.paramName}`;
      if (!changesByDeviceParam.has(paramKey)) {
        changesByDeviceParam.set(paramKey, change);
      } else {
        const existingChange = changesByDeviceParam.get(paramKey)!; // idk why TS wants me to assert ! here
        existingChange.newValue = change.newValue; // we only care about the first and last values, not any intermediate values
        existingChange.timestamp = change.timestamp;
        changesByDeviceParam.set(paramKey, existingChange);
      }
    });

    // Format the changes into a readable summary
    let summary = `Parameter changes in the last ${minutesElapsed} minutes:\n\n`;

    changesByDevice.forEach((changes, trackDeviceKey) => {
      summary += `${trackDeviceKey}:\n`;
      changes.forEach((change) => {
        summary += `  - ${change.paramName}: ${change.oldValue} → ${change.newValue}\n`;
      });
      summary += "\n";
    });

    return summary;
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

    return Array.from({ length: names.length })
      .slice(2)
      .map((_, index) => ({
        param_id: index,
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
