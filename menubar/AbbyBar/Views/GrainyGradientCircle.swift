import SwiftUI

struct GrainyGradientCircle: View {
    let amplitude: Float
    let isProcessing: Bool
    let isPlayingAudio: Bool

    @State private var phase1: Double = 0
    @State private var phase2: Double = 0
    @State private var phase3: Double = 0

    // Warm atelier palette — terracotta idle, rust/amber processing, sage playing
    private var plasmaColors: (primary: Color, secondary: Color, accent: Color) {
        if isProcessing {
            return (
                Color(red: 0.72, green: 0.33, blue: 0.18),  // Deep rust
                Color(red: 0.87, green: 0.60, blue: 0.25),  // Amber
                Color(red: 0.93, green: 0.78, blue: 0.40)   // Golden
            )
        } else if isPlayingAudio {
            return (
                Color(red: 0.48, green: 0.62, blue: 0.49),  // Sage green
                Color(red: 0.62, green: 0.76, blue: 0.64),  // Light sage
                Color(red: 0.55, green: 0.70, blue: 0.42)   // Olive sage
            )
        } else {
            return (
                Color(red: 0.77, green: 0.44, blue: 0.29),  // Terracotta
                Color(red: 0.87, green: 0.64, blue: 0.32),  // Warm amber
                Color(red: 0.96, green: 0.83, blue: 0.72)   // Peach
            )
        }
    }

    private var animationSpeed: Double {
        if isProcessing { return 6.0 }
        else if isPlayingAudio { return 4.0 }
        return 10.0
    }

    private var amplitudeScale: CGFloat {
        1.0 + CGFloat(amplitude) * (isPlayingAudio ? 0.15 : 0.1)
    }

    private var glowIntensity: Double {
        if isPlayingAudio { return 0.6 + Double(amplitude) * 0.3 }
        else if isProcessing { return 0.5 }
        return 0.4
    }

    var body: some View {
        GeometryReader { geometry in
            let size = min(geometry.size.width, geometry.size.height)

            ZStack {
                // Outer glow — warm colored halo on parchment
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                plasmaColors.primary.opacity(0.22),
                                plasmaColors.secondary.opacity(0.10),
                                .clear
                            ],
                            center: .center,
                            startRadius: size * 0.3,
                            endRadius: size * 0.6
                        )
                    )
                    .frame(width: size * 1.3, height: size * 1.3)
                    .blur(radius: 20)

                // Sphere base — warm-tinted surface
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                Color.white.opacity(0.06),
                                Color.white.opacity(0.02),
                                Color(white: 0.5).opacity(0.04)
                            ],
                            center: .center,
                            startRadius: 0,
                            endRadius: size * 0.5
                        )
                    )
                    .frame(width: size, height: size)

                // Internal plasma layers (clipped to sphere)
                ZStack {
                    // Flowing band 1 - vertical wave
                    plasmaWave(
                        size: size,
                        color1: plasmaColors.primary,
                        color2: .white.opacity(0.6),
                        rotation: phase1 * 0.3,
                        offsetX: sin(phase1) * size * 0.15,
                        offsetY: cos(phase1 * 0.7) * size * 0.1,
                        scaleX: 0.35 + sin(phase1 * 0.5) * 0.1,
                        scaleY: 1.1
                    )

                    // Flowing band 2 - diagonal
                    plasmaWave(
                        size: size,
                        color1: plasmaColors.secondary,
                        color2: .white.opacity(0.5),
                        rotation: 45 + phase2 * 0.25,
                        offsetX: cos(phase2 * 0.8) * size * 0.12,
                        offsetY: sin(phase2 * 0.6) * size * 0.08,
                        scaleX: 0.3 + cos(phase2 * 0.4) * 0.08,
                        scaleY: 1.0
                    )

                    // Flowing band 3 - accent color
                    plasmaWave(
                        size: size,
                        color1: plasmaColors.accent,
                        color2: .white.opacity(0.4),
                        rotation: -30 + phase3 * 0.2,
                        offsetX: sin(phase3 * 0.9) * size * 0.18,
                        offsetY: cos(phase3 * 0.5) * size * 0.12,
                        scaleX: 0.25 + sin(phase3 * 0.6) * 0.06,
                        scaleY: 0.95
                    )

                    // Central glow core
                    Ellipse()
                        .fill(
                            RadialGradient(
                                colors: [
                                    .white.opacity(0.35),
                                    plasmaColors.primary.opacity(0.18),
                                    .clear
                                ],
                                center: .center,
                                startRadius: 0,
                                endRadius: size * 0.3
                            )
                        )
                        .frame(width: size * 0.5, height: size * 0.6)
                        .blur(radius: 15)
                        .offset(
                            x: sin(phase1 * 0.3) * size * 0.05,
                            y: cos(phase2 * 0.4) * size * 0.05
                        )
                }
                .clipShape(Circle())
                .frame(width: size, height: size)

                // Rim highlight (top)
                Ellipse()
                    .fill(
                        LinearGradient(
                            colors: [
                                .white.opacity(0.4),
                                .white.opacity(0.15),
                                .clear
                            ],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .frame(width: size * 0.7, height: size * 0.25)
                    .offset(y: -size * 0.32)
                    .blur(radius: 4)

                // Rim highlight (bottom edge)
                Ellipse()
                    .stroke(
                        LinearGradient(
                            colors: [
                                .clear,
                                .white.opacity(0.12),
                                .white.opacity(0.22),
                                .white.opacity(0.12),
                                .clear
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        ),
                        lineWidth: 1.5
                    )
                    .frame(width: size * 0.85, height: size * 0.15)
                    .offset(y: size * 0.38)
                    .blur(radius: 1)

                // Sphere edge definition
                Circle()
                    .stroke(
                        LinearGradient(
                            colors: [
                                .white.opacity(0.20),
                                .white.opacity(0.08),
                                .clear,
                                .white.opacity(0.04),
                                .white.opacity(0.12)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1.5
                    )
                    .frame(width: size - 1, height: size - 1)
                    .blur(radius: 0.5)
            }
            .frame(width: size, height: size)
            .scaleEffect(amplitudeScale)
            .animation(.easeOut(duration: 0.1), value: amplitudeScale)
            .shadow(
                color: plasmaColors.primary.opacity(glowIntensity * 0.35),
                radius: 20,
                x: 0,
                y: 6
            )
            .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
        }
        .onAppear {
            startAnimations()
        }
    }

    @ViewBuilder
    private func plasmaWave(
        size: CGFloat,
        color1: Color,
        color2: Color,
        rotation: Double,
        offsetX: CGFloat,
        offsetY: CGFloat,
        scaleX: CGFloat,
        scaleY: CGFloat
    ) -> some View {
        Ellipse()
            .fill(
                LinearGradient(
                    colors: [
                        .clear,
                        color1.opacity(0.3),
                        color2.opacity(0.5),
                        color1.opacity(0.4),
                        .clear
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .frame(width: size, height: size)
            .scaleEffect(x: scaleX, y: scaleY)
            .rotationEffect(.degrees(rotation))
            .offset(x: offsetX, y: offsetY)
            .blur(radius: 8)
    }

    private func startAnimations() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            withAnimation(.linear(duration: animationSpeed).repeatForever(autoreverses: false)) {
                phase1 = .pi * 2
            }
            withAnimation(.linear(duration: animationSpeed * 1.3).repeatForever(autoreverses: false)) {
                phase2 = .pi * 2
            }
            withAnimation(.linear(duration: animationSpeed * 1.7).repeatForever(autoreverses: false)) {
                phase3 = .pi * 2
            }
        }
    }
}

#Preview {
    HStack(spacing: 30) {
        VStack {
            GrainyGradientCircle(amplitude: 0.0, isProcessing: false, isPlayingAudio: false)
                .frame(width: 160, height: 160)
            Text("Idle")
                .font(.system(.caption, design: .serif))
                .foregroundStyle(Color.atelier.ink2)
        }

        VStack {
            GrainyGradientCircle(amplitude: 0.4, isProcessing: true, isPlayingAudio: false)
                .frame(width: 160, height: 160)
            Text("Processing")
                .font(.system(.caption, design: .serif))
                .foregroundStyle(Color.atelier.ink2)
        }

        VStack {
            GrainyGradientCircle(amplitude: 0.6, isProcessing: false, isPlayingAudio: true)
                .frame(width: 160, height: 160)
            Text("Playing")
                .font(.system(.caption, design: .serif))
                .foregroundStyle(Color.atelier.ink2)
        }
    }
    .padding(40)
    .background(Color.atelier.bg)
}
