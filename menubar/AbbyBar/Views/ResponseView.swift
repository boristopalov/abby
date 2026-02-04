import SwiftUI

struct ResponseView: View {
    let text: String
    let isLoading: Bool

    init(text: String, isLoading: Bool = false) {
        self.text = text
        self.isLoading = isLoading
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Response")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Spacer()

                if isLoading {
                    ProgressView()
                        .scaleEffect(0.6)
                }
            }

            ScrollView {
                Text(text)
                    .font(.system(.body, design: .rounded))
                    .foregroundStyle(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(maxHeight: 150)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(.ultraThinMaterial)
        )
    }
}

struct StatusIndicator: View {
    let state: ConnectionState
    let modelStatus: String

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)

            Text(statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var statusColor: Color {
        switch state {
        case .connected:
            return .green
        case .connecting:
            return .yellow
        case .disconnected:
            return .gray
        case .error:
            return .red
        }
    }

    private var statusText: String {
        if !modelStatus.isEmpty {
            return modelStatus
        }

        switch state {
        case .connected:
            return "Connected"
        case .connecting:
            return "Connecting..."
        case .disconnected:
            return "Disconnected"
        case .error(let message):
            return message
        }
    }
}

#Preview {
    VStack(spacing: 20) {
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
}
