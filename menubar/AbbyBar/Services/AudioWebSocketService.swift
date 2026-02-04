import Foundation
import Combine

@MainActor
class AudioWebSocketService: ObservableObject {
    @Published var connectionState: ConnectionState = .disconnected
    @Published var lastResponse: String = ""
    @Published var isReceiving: Bool = false

    // Audio events - consumers should subscribe to these
    let audioStartSubject = PassthroughSubject<Void, Never>()
    let audioDataSubject = PassthroughSubject<Data, Never>()
    let audioEndSubject = PassthroughSubject<Void, Never>()
    let audioErrorSubject = PassthroughSubject<String, Never>()

    // Function call events
    @Published var lastFunctionCall: FunctionCall?

    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var messageBuffer: String = ""
    private var receiveTask: Task<Void, Never>?

    private let baseURL = "ws://127.0.0.1:8000/ws/audio"

    func connect(sessionId: UUID, projectId: Int) async {
        guard connectionState != .connected && connectionState != .connecting else { return }

        connectionState = .connecting

        let urlString = "\(baseURL)?sessionId=\(sessionId.uuidString)&projectId=\(projectId)"
        print("[WebSocket] Connecting to: \(urlString)")
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
        print("[WebSocket] Connection state set to connected")

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
        print("[WebSocket] sendMessage called with: '\(text)'")
        guard let webSocket = webSocket, connectionState == .connected else {
            print("[WebSocket] Not connected, throwing error")
            throw WebSocketError.notConnected
        }

        let payload: [String: String] = ["message": text]
        let data = try JSONSerialization.data(withJSONObject: payload)
        guard let jsonString = String(data: data, encoding: .utf8) else {
            throw WebSocketError.encodingFailed
        }

        print("[WebSocket] Sending JSON: \(jsonString)")
        try await webSocket.send(.string(jsonString))
        print("[WebSocket] Send completed")
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
        switch message {
        case .string(let text):
            await handleTextMessage(text)
        case .data(let data):
            // Binary frame = MP3 audio data
            audioDataSubject.send(data)
        @unknown default:
            break
        }
    }

    private func handleTextMessage(_ text: String) async {
        print("[WebSocket] Received text: \(text.prefix(200))")
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            print("[WebSocket] Failed to parse message")
            return
        }
        print("[WebSocket] Message type: \(type)")

        switch type {
        case "text":
            if let content = json["content"] as? String {
                messageBuffer += content
                lastResponse = messageBuffer
            }

        case "audio_start":
            audioStartSubject.send()

        case "audio_end":
            audioEndSubject.send()

        case "end_message":
            lastResponse = messageBuffer
            messageBuffer = ""
            isReceiving = false

        case "function_call":
            if let name = json["name"] as? String {
                let args = json["arguments"] as? [String: Any]
                lastFunctionCall = FunctionCall(name: name, arguments: args)
            }

        case "error":
            let errorMessage = (json["content"] as? String) ?? "Unknown error"
            lastResponse = "Error: \(errorMessage)"
            isReceiving = false
            audioErrorSubject.send(errorMessage)

        case "loading_progress", "tracks":
            break

        default:
            break
        }
    }
}

struct FunctionCall: Equatable {
    let name: String
    let arguments: [String: Any]?

    static func == (lhs: FunctionCall, rhs: FunctionCall) -> Bool {
        lhs.name == rhs.name
    }
}
