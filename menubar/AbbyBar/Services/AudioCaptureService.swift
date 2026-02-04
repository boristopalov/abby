import AVFoundation
import Combine

@MainActor
class AudioCaptureService: ObservableObject {
    @Published var amplitude: Float = 0.0
    @Published var isRecording: Bool = false
    @Published var permissionGranted: Bool = false

    private var audioEngine: AVAudioEngine?
    private var audioFile: AVAudioFile?
    private var recordingURL: URL?

    func requestMicrophonePermission() async -> Bool {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)

        switch status {
        case .authorized:
            permissionGranted = true
            return true
        case .notDetermined:
            let granted = await withCheckedContinuation { continuation in
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    continuation.resume(returning: granted)
                }
            }
            permissionGranted = granted
            return granted
        default:
            permissionGranted = false
            return false
        }
    }

    func startRecording() throws {
        guard !isRecording else { return }

        let audioEngine = AVAudioEngine()
        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)

        // Create temp file for recording
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("wav")

        // Create audio file with standard format
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: format.sampleRate,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false
        ]

        audioFile = try AVAudioFile(
            forWriting: tempURL,
            settings: settings
        )

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let self = self else { return }

            // Calculate RMS amplitude
            let rms = self.calculateRMS(buffer: buffer)

            Task { @MainActor in
                self.amplitude = rms
            }

            // Convert to mono and write to file
            if let monoBuffer = self.convertToMono(buffer: buffer) {
                try? self.audioFile?.write(from: monoBuffer)
            }
        }

        audioEngine.prepare()
        try audioEngine.start()

        self.audioEngine = audioEngine
        self.recordingURL = tempURL
        self.isRecording = true
    }

    func stopRecording() -> URL? {
        guard isRecording else { return nil }

        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil

        let url = recordingURL
        audioFile = nil
        recordingURL = nil
        isRecording = false
        amplitude = 0.0

        return url
    }

    private func calculateRMS(buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData else { return 0 }

        let channelDataValue = channelData.pointee
        let frameLength = Int(buffer.frameLength)

        guard frameLength > 0 else { return 0 }

        var sum: Float = 0
        for i in 0..<frameLength {
            let sample = channelDataValue[i]
            sum += sample * sample
        }

        let rms = sqrt(sum / Float(frameLength))
        // Scale to 0-1 range with amplification
        return min(rms * 5, 1.0)
    }

    private func convertToMono(buffer: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        let format = buffer.format

        // If already mono, return as is
        if format.channelCount == 1 {
            return buffer
        }

        // Create mono format
        guard let monoFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: format.sampleRate,
            channels: 1,
            interleaved: false
        ) else { return nil }

        guard let monoBuffer = AVAudioPCMBuffer(
            pcmFormat: monoFormat,
            frameCapacity: buffer.frameCapacity
        ) else { return nil }

        monoBuffer.frameLength = buffer.frameLength

        guard let srcData = buffer.floatChannelData,
              let dstData = monoBuffer.floatChannelData else { return nil }

        // Average channels to mono
        let frameLength = Int(buffer.frameLength)
        let channelCount = Int(format.channelCount)

        for frame in 0..<frameLength {
            var sum: Float = 0
            for channel in 0..<channelCount {
                sum += srcData[channel][frame]
            }
            dstData[0][frame] = sum / Float(channelCount)
        }

        return monoBuffer
    }
}
