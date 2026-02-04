import Foundation
import Combine

@MainActor
class WebSocketService: ObservableObject {
    @Published var connectionState: ConnectionState = .disconnected
    @Published var lastResponse: String = ""
    @Published var isReceiving: Bool = false

    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var messageBuffer: String = ""
    private var receiveTask: Task<Void, Never>?

    private let baseURL = "ws://127.0.0.1:8000/ws"

    func connect(sessionId: UUID, projectId: Int) async {
        guard connectionState != .connected && connectionState != .connecting else { return }

        connectionState = .connecting

        let urlString = "\(baseURL)?sessionId=\(sessionId.uuidString)&projectId=\(projectId)"
        guard let url = URL(string: urlString) else {
            connectionState = .error("Invalid URL")
            return
        }

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        session = URLSession(configuration: configuration)
        webSocket = session?.webSocketTask(with: url)
        webSocket?.resume()

        connectionState = .connected

        // Start receiving messages
        receiveTask = Task {
            await receiveMessages()
        }
    }

    func disconnect() {
        receiveTask?.cancel()
        receiveTask = nil
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
        session?.invalidateAndCancel()
        session = nil
        connectionState = .disconnected
    }

    func sendMessage(_ text: String) async throws {
        guard let webSocket = webSocket, connectionState == .connected else {
            throw WebSocketError.notConnected
        }

        let payload: [String: String] = ["message": text]
        let data = try JSONSerialization.data(withJSONObject: payload)
        guard let jsonString = String(data: data, encoding: .utf8) else {
            throw WebSocketError.encodingFailed
        }

        try await webSocket.send(.string(jsonString))
        isReceiving = true
        messageBuffer = ""
        lastResponse = ""
    }

    private func receiveMessages() async {
        guard let webSocket = webSocket else { return }

        while connectionState == .connected && !Task.isCancelled {
            do {
                let message = try await webSocket.receive()
                await handleMessage(message)
            } catch {
                if connectionState == .connected {
                    connectionState = .error(error.localizedDescription)
                }
                break
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) async {
        let text: String
        switch message {
        case .string(let str):
            text = str
        case .data(let data):
            guard let str = String(data: data, encoding: .utf8) else { return }
            text = str
        @unknown default:
            return
        }

        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }

        switch type {
        case "text":
            if let content = json["content"] as? String {
                messageBuffer += content
                lastResponse = messageBuffer
            }

        case "end_message":
            lastResponse = messageBuffer
            messageBuffer = ""
            isReceiving = false

        case "error":
            if let content = json["content"] as? String {
                lastResponse = "Error: \(content)"
            }
            isReceiving = false

        case "loading_progress", "tracks", "function_call":
            // Ignore these message types for now
            break

        default:
            break
        }
    }
}

enum WebSocketError: LocalizedError {
    case notConnected
    case encodingFailed

    var errorDescription: String? {
        switch self {
        case .notConnected:
            return "Not connected to server"
        case .encodingFailed:
            return "Failed to encode message"
        }
    }
}
