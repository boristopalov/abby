import { encodeOSC, decodeOSC, OSCArgs } from "@deno-plc/adapter-osc";

export class OSCHandler {
  private connection: Deno.DatagramConn;
  private listeners: Map<string, ((args: OSCArgs) => void)[]>;
  private port: number = 11000;
  private hostname: string = "127.0.0.1";

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
