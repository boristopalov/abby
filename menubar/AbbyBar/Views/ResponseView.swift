import SwiftUI

// MARK: - Design System

extension Color {
    enum atelier {
        static let bg          = Color(red: 247/255, green: 243/255, blue: 238/255)
        static let surface     = Color(red: 253/255, green: 250/255, blue: 246/255)
        static let surfaceWarm = Color(red: 245/255, green: 239/255, blue: 232/255)
        static let accent      = Color(red: 196/255, green: 113/255, blue:  74/255)
        static let sage        = Color(red: 122/255, green: 158/255, blue: 126/255)
        static let ink         = Color(red:  28/255, green:  26/255, blue:  24/255)
        static let ink2        = Color(red: 122/255, green: 111/255, blue: 102/255)
        static let ink3        = Color(red: 168/255, green: 158/255, blue: 149/255)
        static let border      = Color(red: 221/255, green: 213/255, blue: 200/255)
        static let borderLight = Color(red: 237/255, green: 231/255, blue: 223/255)
    }
}

// MARK: - ResponseView

struct ResponseView: View {
    let text: String
    let isLoading: Bool

    init(text: String, isLoading: Bool = false) {
        self.text = text
        self.isLoading = isLoading
    }

    var body: some View {
        HStack(spacing: 0) {
            // Accent left border — mirrors the web UI's tool-call reference card style
            Rectangle()
                .fill(Color.atelier.accent)
                .frame(width: 3)

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Response")
                        .font(.system(size: 9, design: .serif))
                        .textCase(.uppercase)
                        .tracking(1.0)
                        .foregroundStyle(Color.atelier.ink3)

                    Spacer()

                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.55)
                            .tint(Color.atelier.accent)
                    }
                }

                ScrollView {
                    Text(text)
                        .font(.system(.caption, design: .serif))
                        .foregroundStyle(Color.atelier.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .lineSpacing(3)
                }
                .frame(maxHeight: 120)
            }
            .padding(12)
        }
        .background(Color.atelier.surface)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(Color.atelier.borderLight, lineWidth: 1)
        )
        .shadow(
            color: Color(red: 0.39, green: 0.27, blue: 0.16).opacity(0.06),
            radius: 8, x: 1, y: 2
        )
    }
}

// MARK: - StatusIndicator

struct StatusIndicator: View {
    let state: ConnectionState
    let modelStatus: String

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(dotColor)
                .frame(width: 6, height: 6)

            Text(statusText)
                .font(.system(size: 10, design: .serif))
                .foregroundStyle(Color.atelier.ink2)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(pillBackground)
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(pillBorder, lineWidth: 0.5)
        )
    }

    private var dotColor: Color {
        switch state {
        case .connected:    return Color.atelier.sage
        case .connecting:   return Color(red: 0.85, green: 0.72, blue: 0.30)
        case .disconnected: return Color.atelier.ink3
        case .error:        return Color(red: 0.78, green: 0.25, blue: 0.20)
        }
    }

    private var pillBackground: Color {
        switch state {
        case .connected:    return Color.atelier.sage.opacity(0.10)
        case .connecting:   return Color(red: 0.85, green: 0.72, blue: 0.30).opacity(0.10)
        default:            return Color.atelier.ink3.opacity(0.08)
        }
    }

    private var pillBorder: Color {
        switch state {
        case .connected:    return Color.atelier.sage.opacity(0.25)
        default:            return Color.atelier.border.opacity(0.5)
        }
    }

    private var statusText: String {
        if !modelStatus.isEmpty { return modelStatus }
        switch state {
        case .connected:          return "Connected"
        case .connecting:         return "Connecting"
        case .disconnected:       return "Disconnected"
        case .error(let message): return message
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        StatusIndicator(state: .connected, modelStatus: "")
        StatusIndicator(state: .connecting, modelStatus: "")
        StatusIndicator(state: .error("Connection failed"), modelStatus: "")
        StatusIndicator(state: .connected, modelStatus: "Loading model...")

        ResponseView(
            text: "This is a sample response from the AI assistant. It can be quite long and will scroll if needed.",
            isLoading: false
        )

        ResponseView(
            text: "Loading response...",
            isLoading: true
        )
    }
    .padding()
    .frame(width: 280)
    .background(Color.atelier.bg)
}
