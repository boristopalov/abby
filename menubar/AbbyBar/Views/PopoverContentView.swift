import SwiftUI

struct PopoverContentView: View {
    @EnvironmentObject var viewModel: AppViewModel

    var body: some View {
        ZStack {
            Color.atelier.bg
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Header — serif wordmark + status pill
                HStack {
                    Text("Abby")
                        .font(.system(.body, design: .serif).weight(.semibold))
                        .foregroundStyle(Color.atelier.ink)

                    Spacer()

                    StatusIndicator(
                        state: viewModel.connectionState,
                        modelStatus: viewModel.modelLoadingStatus
                    )
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)

                // Thin rule
                Rectangle()
                    .fill(Color.atelier.border)
                    .frame(height: 0.5)

                // Main content
                VStack(spacing: 14) {
                    Spacer()

                    // Orb — audio visualization
                    GrainyGradientCircle(
                        amplitude: viewModel.playbackAmplitude,
                        isProcessing: viewModel.isProcessing,
                        isPlayingAudio: viewModel.isPlayingAudio
                    )
                    .frame(width: 140, height: 140)

                    // Microphone button
                    MicrophoneButton(
                        isRecording: viewModel.isRecording,
                        isReady: viewModel.isReady,
                        amplitude: viewModel.recordingAmplitude
                    ) {
                        viewModel.toggleRecording()
                    }

                    // Hint text — italic serif, tertiary ink
                    Text(hintText)
                        .font(.system(.caption, design: .serif))
                        .italic()
                        .foregroundStyle(Color.atelier.ink3)
                        .multilineTextAlignment(.center)

                    Spacer()

                    // Transcription preview
                    if !viewModel.currentTranscription.isEmpty {
                        Text(viewModel.currentTranscription)
                            .font(.system(.caption, design: .serif))
                            .italic()
                            .foregroundStyle(Color.atelier.ink2)
                            .lineLimit(2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    // Response area
                    if !viewModel.lastResponse.isEmpty || viewModel.isProcessing {
                        ResponseView(
                            text: viewModel.lastResponse.isEmpty ? "Processing..." : viewModel.lastResponse,
                            isLoading: viewModel.isProcessing
                        )
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
        }
        .frame(width: 280, height: 400)
        .fixedSize()
        .preferredColorScheme(.light)
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
