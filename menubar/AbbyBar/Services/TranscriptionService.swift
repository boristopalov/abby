import Foundation
import WhisperKit

@MainActor
class TranscriptionService: ObservableObject {
    @Published var isModelLoaded: Bool = false
    @Published var isTranscribing: Bool = false
    @Published var loadingProgress: String = ""

    private var whisperKit: WhisperKit?

    func loadModel() async throws {
        guard !isModelLoaded else { return }

        loadingProgress = "Loading speech model..."

        // Use base.en model for faster transcription
        // Models are automatically downloaded on first use
        let config = WhisperKitConfig(model: "base.en")
        whisperKit = try await WhisperKit(config)

        isModelLoaded = true
        loadingProgress = ""
    }

    func transcribe(audioURL: URL) async throws -> String {
        guard let whisperKit = whisperKit else {
            throw TranscriptionError.modelNotLoaded
        }

        isTranscribing = true
        defer { isTranscribing = false }

        let results = try await whisperKit.transcribe(audioPath: audioURL.path)

        guard !results.isEmpty else {
            return ""
        }

        // Combine all segments
        let text = results.compactMap { $0.text }.joined(separator: " ")
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

enum TranscriptionError: LocalizedError {
    case modelNotLoaded
    case transcriptionFailed

    var errorDescription: String? {
        switch self {
        case .modelNotLoaded:
            return "Speech recognition model not loaded"
        case .transcriptionFailed:
            return "Failed to transcribe audio"
        }
    }
}
