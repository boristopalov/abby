import Foundation

enum ConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case error(String)
}

enum RecordingState: Equatable {
    case idle
    case recording
    case transcribing
    case sending
    case receivingResponse
}

struct ProjectInfo: Codable, Identifiable {
    let id: Int
    let name: String
    let indexedAt: Int
}

struct ProjectsResponse: Codable {
    let projects: [ProjectInfo]
}
