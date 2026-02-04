import SwiftUI
import Combine

@MainActor
class AppViewModel: ObservableObject {
    // Published state
    @Published var connectionState: ConnectionState = .disconnected
    @Published var isRecording: Bool = false
    @Published var isProcessing: Bool = false
    @Published var recordingAmplitude: Float = 0.0
    @Published var playbackAmplitude: Float = 0.0
    @Published var currentTranscription: String = ""
    @Published var lastResponse: String = ""
    @Published var modelLoadingStatus: String = ""
    @Published var isReady: Bool = false
    @Published var isPlayingAudio: Bool = false

    // Services
    private let audioService = AudioCaptureService()
    private let transcriptionService = TranscriptionService()
    private let webSocketService = AudioWebSocketService()
    private let audioPlaybackService = AudioPlaybackService()

    // Session management
    private var sessionId = UUID()
    private var projectId: Int?

    private var cancellables = Set<AnyCancellable>()

    init() {
        setupBindings()
    }

    private func setupBindings() {
        // Bind recording amplitude
        audioService.$amplitude
            .receive(on: DispatchQueue.main)
            .assign(to: &$recordingAmplitude)

        // Bind playback amplitude
        audioPlaybackService.$amplitude
            .receive(on: DispatchQueue.main)
            .assign(to: &$playbackAmplitude)

        // Bind recording state
        audioService.$isRecording
            .receive(on: DispatchQueue.main)
            .assign(to: &$isRecording)

        // Bind connection state
        webSocketService.$connectionState
            .receive(on: DispatchQueue.main)
            .assign(to: &$connectionState)

        // Bind responses
        webSocketService.$lastResponse
            .receive(on: DispatchQueue.main)
            .assign(to: &$lastResponse)

        // Bind processing state from transcription and websocket
        Publishers.CombineLatest(
            transcriptionService.$isTranscribing,
            webSocketService.$isReceiving
        )
        .map { $0 || $1 }
        .receive(on: DispatchQueue.main)
        .assign(to: &$isProcessing)

        // Bind model loading status
        transcriptionService.$loadingProgress
            .receive(on: DispatchQueue.main)
            .assign(to: &$modelLoadingStatus)

        // Bind audio playback state
        audioPlaybackService.$isPlaying
            .receive(on: DispatchQueue.main)
            .assign(to: &$isPlayingAudio)

        // Wire up audio streaming events
        webSocketService.audioStartSubject
            .receive(on: DispatchQueue.main)
            .sink { [weak self] in
                self?.audioPlaybackService.audioStart()
            }
            .store(in: &cancellables)

        webSocketService.audioDataSubject
            .receive(on: DispatchQueue.main)
            .sink { [weak self] data in
                self?.audioPlaybackService.appendAudioData(data)
            }
            .store(in: &cancellables)

        webSocketService.audioEndSubject
            .receive(on: DispatchQueue.main)
            .sink { [weak self] in
                self?.audioPlaybackService.audioEnd()
            }
            .store(in: &cancellables)

        // Handle errors by resetting audio playback state
        webSocketService.audioErrorSubject
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.audioPlaybackService.stop()
            }
            .store(in: &cancellables)
    }

    func initialize() async {
        // Request microphone permission
        let granted = await audioService.requestMicrophonePermission()
        guard granted else {
            connectionState = .error("Microphone permission denied")
            return
        }

        // Load WhisperKit model
        do {
            try await transcriptionService.loadModel()
        } catch {
            connectionState = .error("Failed to load model")
            return
        }

        // Fetch available projects and connect
        await fetchProjectsAndConnect()

        isReady = true
    }

    private func fetchProjectsAndConnect() async {
        guard let url = URL(string: "http://127.0.0.1:8000/api/projects") else {
            connectionState = .error("Invalid server URL")
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                connectionState = .error("Server not available")
                return
            }

            let projectsResponse = try JSONDecoder().decode(ProjectsResponse.self, from: data)

            if let firstProject = projectsResponse.projects.first {
                projectId = firstProject.id
                await webSocketService.connect(sessionId: sessionId, projectId: firstProject.id)
            } else {
                connectionState = .error("No projects found")
            }
        } catch {
            connectionState = .error("Cannot reach server")
        }
    }

    func toggleRecording() {
        guard isReady else { return }

        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }

    private func startRecording() {
        // Clear previous state
        currentTranscription = ""
        lastResponse = ""

        do {
            try audioService.startRecording()
        } catch {
            lastResponse = "Failed to start recording"
        }
    }

    private func stopRecording() {
        guard let audioURL = audioService.stopRecording() else { return }

        Task {
            await processRecording(audioURL: audioURL)
        }
    }

    private func processRecording(audioURL: URL) async {
        currentTranscription = "Transcribing..."
        print("[AppViewModel] Starting transcription for: \(audioURL)")

        do {
            // Transcribe audio
            let transcription = try await transcriptionService.transcribe(audioURL: audioURL)
            print("[AppViewModel] Transcription result: '\(transcription)'")
            currentTranscription = transcription

            // Send to backend if we got text
            print("[AppViewModel] connectionState: \(connectionState), transcription.isEmpty: \(transcription.isEmpty)")
            if !transcription.isEmpty && connectionState == .connected {
                print("[AppViewModel] Sending message to backend...")
                try await webSocketService.sendMessage(transcription)
                print("[AppViewModel] Message sent successfully")
            } else if transcription.isEmpty {
                currentTranscription = ""
                lastResponse = "No speech detected"
            } else {
                print("[AppViewModel] Not sending - connection not ready")
            }
        } catch {
            print("[AppViewModel] Error: \(error)")
            lastResponse = "Error: \(error.localizedDescription)"
            currentTranscription = ""
        }

        // Clean up temp audio file
        try? FileManager.default.removeItem(at: audioURL)
    }
}
