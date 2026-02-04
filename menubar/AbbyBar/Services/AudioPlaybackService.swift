import Foundation
import AVFoundation
import Combine

@MainActor
class AudioPlaybackService: ObservableObject {
    @Published var isPlaying: Bool = false
    @Published var amplitude: Float = 0.0

    private var audioPlayer: AVAudioPlayer?
    private var audioPlayerDelegate: AudioPlayerDelegate?
    private var audioBuffer = Data()
    private var isBuffering: Bool = false
    private var meteringTimer: Timer?

    func audioStart() {
        audioBuffer = Data()
        isBuffering = true
        isPlaying = true
    }

    func appendAudioData(_ data: Data) {
        guard isBuffering else { return }
        audioBuffer.append(data)
    }

    func audioEnd() {
        isBuffering = false
        playBufferedAudio()
    }

    func stop() {
        stopMetering()
        audioPlayer?.stop()
        audioPlayer = nil
        audioBuffer = Data()
        isBuffering = false
        isPlaying = false
        amplitude = 0.0
    }

    private func startMetering() {
        meteringTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.updateAmplitude()
            }
        }
    }

    private func stopMetering() {
        meteringTimer?.invalidate()
        meteringTimer = nil
        amplitude = 0.0
    }

    private func updateAmplitude() {
        guard let player = audioPlayer, player.isPlaying else {
            amplitude = 0.0
            return
        }

        player.updateMeters()
        let power = player.averagePower(forChannel: 0)
        // Convert dB to linear scale (0-1)
        // Typical range is -160 to 0 dB, but voice is usually -50 to 0
        let minDb: Float = -50.0
        let normalizedPower = max(0, (power - minDb) / (-minDb))
        amplitude = normalizedPower
    }

    private func playBufferedAudio() {
        guard !audioBuffer.isEmpty else {
            isPlaying = false
            return
        }

        do {
            audioPlayer = try AVAudioPlayer(data: audioBuffer)
            audioPlayer?.isMeteringEnabled = true
            audioPlayerDelegate = AudioPlayerDelegate { [weak self] in
                Task { @MainActor in
                    self?.stopMetering()
                    self?.isPlaying = false
                }
            }
            audioPlayer?.delegate = audioPlayerDelegate
            audioPlayer?.play()
            startMetering()
        } catch {
            print("Failed to play audio: \(error)")
            isPlaying = false
        }
    }
}

private class AudioPlayerDelegate: NSObject, AVAudioPlayerDelegate {
    private let onFinish: () -> Void

    init(onFinish: @escaping () -> Void) {
        self.onFinish = onFinish
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish()
    }
}
