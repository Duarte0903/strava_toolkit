import SwiftUI
import Charts
import StravaToolkitKit

struct WorkoutDetailView: View {
    let workout: Workout
    @EnvironmentObject var model: AppModel

    private struct Sample: Identifiable { let id = UUID(); let x: Double; let y: Double }

    var body: some View {
        let detail = model.detail(for: workout)
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let d = detail {
                    header(d)
                    tiles(d)
                    if !d.hrSeries.isEmpty {
                        section("Heart rate") {
                            chart(d.hrSeries.map { Sample(x: $0.elapsed, y: $0.bpm) },
                                  color: Theme.hrLine, invert: false)
                        }
                    }
                    if !d.paceSeries.isEmpty {
                        section("Pace") {
                            chart(d.paceSeries.map { Sample(x: $0.elapsed, y: $0.secPerKm) },
                                  color: Theme.paceLine, invert: true)   // faster = up
                        }
                    }
                    section("Route") {
                        RouteView(route: d.route.map { CGPoint(x: $0.lon, y: $0.lat) })
                            .frame(height: 200)
                    }
                } else {
                    Text("Couldn't read this workout's data").foregroundStyle(.secondary)
                }
            }
            .padding()
        }
        .navigationTitle(workout.label)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func header(_ d: WorkoutDetail) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(d.sport) · \(d.date)").font(.title2).bold()
            Text(d.hasGPS ? "GPS route" : "No GPS").font(.caption).foregroundStyle(.secondary)
        }
    }

    private func tiles(_ d: WorkoutDetail) -> some View {
        var stats: [(String, String)] = []
        if d.distanceMeters > 0 { stats.append(("Distance", fmtDistance(d.distanceMeters))) }
        stats.append(("Duration", fmtDuration(d.durationSeconds)))
        if let p = d.avgPaceSecPerKm { stats.append(("Avg pace", fmtPace(p))) }
        if let hr = d.avgHR { stats.append(("Avg HR", String(format: "%.0f bpm", hr))) }
        if let hr = d.maxHR { stats.append(("Max HR", String(format: "%.0f bpm", hr))) }
        if let c = d.calories { stats.append(("Calories", String(format: "%.0f", c))) }

        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(), alignment: .leading), count: 3),
                         spacing: 12) {
            ForEach(stats, id: \.0) { name, val in
                VStack(alignment: .leading, spacing: 2) {
                    Text(val).font(.headline)
                    Text(name.uppercased()).font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(.caption).foregroundStyle(.secondary)
            content()
        }
    }

    private func chart(_ samples: [Sample], color: Color, invert: Bool) -> some View {
        Chart(samples) { s in
            LineMark(x: .value("t", s.x), y: .value("v", s.y))
                .foregroundStyle(color)
                .interpolationMethod(.catmullRom)
        }
        .chartYScale(domain: invert ? .automatic(reversed: true) : .automatic)
        .frame(height: 140)
    }
}

/// Aspect-corrected GPS route trace with start/end markers.
private struct RouteView: View {
    let route: [CGPoint]   // x = lon, y = lat

    var body: some View {
        Canvas { ctx, size in
            guard route.count >= 2 else {
                let text = Text("No GPS — indoor / treadmill workout")
                    .font(.footnote).foregroundColor(.secondary)
                ctx.draw(text, at: CGPoint(x: size.width / 2, y: size.height / 2))
                return
            }
            let pad: CGFloat = 14
            let lats = route.map { $0.y }, lons = route.map { $0.x }
            let meanLat = lats.reduce(0, +) / Double(lats.count)
            let kx = cos(meanLat * .pi / 180)
            let xs = lons.map { $0 * kx }
            let xmin = xs.min()!, xmax = xs.max()!
            let ymin = lats.min()!, ymax = lats.max()!
            let xr = max(xmax - xmin, 1e-9), yr = max(ymax - ymin, 1e-9)
            let scale = min((size.width - 2 * pad) / xr, (size.height - 2 * pad) / yr)
            let ox = (size.width - xr * scale) / 2
            let oy = (size.height - yr * scale) / 2

            func pt(_ i: Int) -> CGPoint {
                CGPoint(x: ox + (xs[i] - xmin) * scale,
                        y: (size.height - oy) - (lats[i] - ymin) * scale)   // north = up
            }

            var path = Path()
            path.move(to: pt(0))
            for i in 1..<route.count { path.addLine(to: pt(i)) }
            ctx.stroke(path, with: .color(Theme.routeLine), style: StrokeStyle(lineWidth: 2, lineJoin: .round))

            func dot(_ p: CGPoint, _ c: Color) {
                ctx.fill(Path(ellipseIn: CGRect(x: p.x - 4, y: p.y - 4, width: 8, height: 8)), with: .color(c))
            }
            dot(pt(0), Theme.startDot)
            dot(pt(route.count - 1), Theme.endDot)
        }
    }
}
