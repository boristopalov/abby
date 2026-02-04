import SwiftUI

@main
struct AbbyBarApp: App {
    @StateObject private var viewModel = AppViewModel()

    var body: some Scene {
        MenuBarExtra {
            PopoverContentView()
                .environmentObject(viewModel)
        } label: {
            Image(systemName: "waveform.circle.fill")
                .symbolRenderingMode(.hierarchical)
        }
        .menuBarExtraStyle(.window)
    }
}
