import SwiftUI

struct PopoverContentView: View {
    @EnvironmentObject var viewModel: AppViewModel

    var body: some View {
        VStack(spacing: 16) {
            // Status indicator
            StatusIndicator(
                state: viewModel.connectionState,
                modelStatus: viewModel.modelLoadingStatus
            )

            Spacer()

            // Main circle for agent audio visualization
            GrainyGradientCircle(
                amplitude: viewModel.playbackAmplitude,
                isProcessing: viewModel.isProcessing,
                isPlayingAudio: viewModel.isPlayingAudio
            )
            .frame(width: 160, height: 160)

            // Microphone button
            MicrophoneButton(
                isRecording: viewModel.isRecording,
                isReady: viewModel.isReady,
                amplitude: viewModel.recordingAmplitude
            ) {
                viewModel.toggleRecording()
            }

            // Recording hint
            Text(hintText)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            Spacer()

            // Transcription preview
            if !viewModel.currentTranscription.isEmpty {
                Text(viewModel.currentTranscription)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity)
            }

            // Response area
            if !viewModel.lastResponse.isEmpty || viewModel.isProcessing {
                ResponseView(
                    text: viewModel.lastResponse.isEmpty ? "Processing..." : viewModel.lastResponse,
                    isLoading: viewModel.isProcessing
                )
            }
        }
        .padding(20)
        .frame(width: 280, height: 400)
        .fixedSize()
        .animation(nil, value: viewModel.connectionState)
        .animation(nil, value: viewModel.isProcessing)
        .animation(nil, value: viewModel.lastResponse)
        .animation(nil, value: viewModel.currentTranscription)
        .task {
            await viewModel.initialize()
        }
    }

    private var hintText: String {
        if !viewModel.isReady {
            return "Initializing..."
        } else if viewModel.isRecording {
            return "Tap mic to stop"
        } else if viewModel.isProcessing {
            return "Processing..."
        } else if viewModel.isPlayingAudio {
            return "Playing response..."
        } else {
            return "Tap mic to record"
        }
    }
}

#Preview {
    PopoverContentView()
        .environmentObject(AppViewModel())
}
