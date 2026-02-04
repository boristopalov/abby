import SwiftUI

struct MicrophoneButton: View {
    let isRecording: Bool
    let isReady: Bool
    let amplitude: Float
    let action: () -> Void

    @State private var pulsePhase: Bool = false

    private var amplitudeScale: CGFloat {
        if isRecording {
            return 1.0 + CGFloat(amplitude) * 0.35
        }
        return 1.0
    }

    private var pulseScale: CGFloat {
        pulsePhase ? 1.05 : 1.0
    }

    private var iconColor: Color {
        if !isReady {
            return .gray
        } else if isRecording {
            return .white
        } else {
            return .primary
        }
    }

    private var backgroundColor: Color {
        if isRecording {
            return Color(red: 1.0, green: 0.25, blue: 0.35)
        } else {
            return .secondary.opacity(0.15)
        }
    }

    private var glowColor: Color {
        Color(red: 1.0, green: 0.3, blue: 0.4)
    }

    var body: some View {
        Button(action: action) {
            ZStack {
                // Glow effect when recording
                if isRecording {
                    Circle()
                        .fill(glowColor.opacity(0.25))
                        .frame(width: 70, height: 70)
                        .blur(radius: 8)
                        .scaleEffect(amplitudeScale * pulseScale)
                }

                // Main circle background
                Circle()
                    .fill(backgroundColor)
                    .frame(width: 55, height: 55)
                    .shadow(
                        color: isRecording ? glowColor.opacity(0.5) : .clear,
                        radius: isRecording ? 6 + CGFloat(amplitude) * 10 : 0
                    )

                // Microphone icon
                Image(systemName: isRecording ? "mic.fill" : "mic")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(iconColor)
                    .scaleEffect(isRecording ? 1.0 + CGFloat(amplitude) * 0.12 : 1.0)
                    .animation(.easeOut(duration: 0.08), value: amplitude)
            }
            .scaleEffect(amplitudeScale * pulseScale)
            .animation(.easeOut(duration: 0.08), value: amplitudeScale)
            .animation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true), value: pulsePhase)
        }
        .buttonStyle(.plain)
        .disabled(!isReady)
        .opacity(isReady ? 1.0 : 0.5)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                pulsePhase = true
            }
        }
    }
}

#Preview {
    VStack(spacing: 30) {
        MicrophoneButton(isRecording: false, isReady: true, amplitude: 0.0) {}
        MicrophoneButton(isRecording: true, isReady: true, amplitude: 0.5) {}
        MicrophoneButton(isRecording: false, isReady: false, amplitude: 0.0) {}
    }
    .padding()
    .background(Color(white: 0.15))
}
