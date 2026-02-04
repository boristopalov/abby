# AbbyBar - Menu Bar Voice Assistant

A macOS menu bar app that captures speech, transcribes it using WhisperKit, and sends it to the Abby backend.

## Requirements

- macOS 14.0+
- Xcode 15.0+

## Setup

### Option 1: Using XcodeGen (Recommended)

1. Install XcodeGen:
   ```bash
   brew install xcodegen
   ```

2. Generate the Xcode project:
   ```bash
   cd /Users/boris/Desktop/projects/abby/menubar
   xcodegen generate
   ```

3. Open the generated project:
   ```bash
   open AbbyBar.xcodeproj
   ```

### Option 2: Manual Xcode Setup

1. Open Xcode and create a new project:
   - Choose "macOS" > "App"
   - Product Name: `AbbyBar`
   - Interface: SwiftUI
   - Language: Swift

2. Delete the auto-generated ContentView.swift

3. Copy all files from `AbbyBar/` folder into your Xcode project

4. Add WhisperKit package:
   - File > Add Package Dependencies
   - Enter: `https://github.com/argmaxinc/WhisperKit.git`
   - Version: 0.9.0+

5. Configure Info.plist:
   - Add `NSMicrophoneUsageDescription`: "AbbyBar needs microphone access to transcribe your voice commands."
   - Add `LSUIElement`: YES (makes it a menu bar only app)

6. Configure Entitlements:
   - Enable App Sandbox
   - Enable Audio Input
   - Enable Outgoing Network Connections

## Running

1. Make sure the backend is running:
   ```bash
   cd /Users/boris/Desktop/projects/abby/backend
   python -m uvicorn app.main:app --reload
   ```

2. Build and run AbbyBar from Xcode (Cmd+R)

3. Click the waveform icon in the menu bar to open the popover

4. Click the circle to start recording, speak, then click again to stop

## Usage

- **Blue/Purple circle**: Idle state
- **Red/Orange circle**: Recording
- **Purple/Cyan circle**: Processing

The circle pulses based on your voice amplitude while recording.

## Troubleshooting

- **"Microphone permission denied"**: Go to System Settings > Privacy & Security > Microphone and enable AbbyBar
- **"Cannot reach server"**: Make sure the backend is running on localhost:8000
- **"No projects found"**: Create a project in the web UI first, or ensure at least one project exists in the database
