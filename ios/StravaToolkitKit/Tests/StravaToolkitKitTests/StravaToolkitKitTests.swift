import Testing
import Foundation
@testable import StravaToolkitKit

// Uses swift-testing (`import Testing`) since XCTest isn't bundled with the
// Command Line Tools toolchain.

private var fixtures: URL { Bundle.module.url(forResource: "Fixtures", withExtension: nil)! }
private var exportDir: URL { fixtures.appendingPathComponent("export") }
private var zipURL: URL { fixtures.appendingPathComponent("export.zip") }

private func loadFixtureWorkouts() throws -> (SamsungExport.Root, [Workout]) {
    let root = try SamsungExport.resolve(exportDir)
    return (root, SamsungExport.loadWorkouts(root: root))
}

@Test func loadWorkoutsNewestFirstWithLabelsAndGPS() throws {
    let (_, items) = try loadFixtureWorkouts()
    #expect(items.count == 2)
    #expect(items.map(\.id) == ["w1", "w2"])       // 06-14 before 06-13
    #expect(items[0].label == "Run")
    #expect(items[1].label == "Walk")
    #expect(items[0].hasGPS)
    #expect(!items[1].hasGPS)
}

@Test func sportLabels() throws {
    let (_, items) = try loadFixtureWorkouts()
    #expect(SamsungExport.sportLabels(items) == ["Run", "Walk"])
}

@Test func detailSeriesAndSummary() throws {
    let (root, items) = try loadFixtureWorkouts()
    let d = WorkoutDetailLoader.load(exDir: root.exDir, workout: items[0])

    #expect(d.hrSeries.map(\.elapsed) == [0, 1])
    #expect(d.hrSeries.map(\.bpm) == [100, 150])
    #expect(d.paceSeries.map(\.elapsed) == [0, 1])
    #expect(d.paceSeries.map(\.secPerKm) == [500, 250])
    #expect(d.route.count == 2)
    #expect(abs(d.route[0].lat - 38.72) < 1e-9)
    #expect(abs(d.route[0].lon - (-9.14)) < 1e-9)
    #expect(d.maxHR == 182)
    #expect(d.calories == 310)
    #expect(abs(d.avgPaceSecPerKm! - 300) < 1e-6)   // 600s / 2km
    #expect(d.hasGPS)
}

@Test func seriesSkipsZeroAndMissingSpeed() {
    let track = [
        TrackPoint(t: 1000, dist: 0, hr: nil, speed: 0, cad: nil),      // stopped -> skip
        TrackPoint(t: 2000, dist: 0, hr: 140, speed: 5.0, cad: nil),    // 200 s/km
        TrackPoint(t: 3000, dist: 0, hr: 145, speed: nil, cad: nil),    // no speed -> skip
    ]
    let (hr, pace) = WorkoutDetailLoader.series(track: track)
    #expect(pace.map { $0.0 } == [1.0])
    #expect(pace.map { $0.1 } == [200.0])
    #expect(hr.map { $0.1 } == [140, 145])
}

@Test func exportTCXContainsExpectedXML() throws {
    let (root, items) = try loadFixtureWorkouts()
    let out = try Exporter.export(exDir: root.exDir, workout: items[0], format: .tcx)
    #expect(out.kind == "tcx")
    #expect(out.filename.hasSuffix(".tcx"))
    let xml = String(decoding: out.data, as: UTF8.self)
    #expect(xml.contains("<Activity Sport=\"Running\">"))
    #expect(xml.contains("<Trackpoint>"))
    #expect(xml.contains("<HeartRateBpm><Value>100</Value></HeartRateBpm>"))
    #expect(xml.contains("<DistanceMeters>2000.00</DistanceMeters>"))
}

@Test func exportAutoPrefersGPXWhenPresent() throws {
    let (root, items) = try loadFixtureWorkouts()
    let out = try Exporter.export(exDir: root.exDir, workout: items[0], format: .auto)
    #expect(out.kind == "gpx")
    #expect(out.filename.hasSuffix(".gpx"))
    let xml = String(decoding: out.data, as: UTF8.self)
    #expect(xml.contains("<trkpt lat=\"38.72\" lon=\"-9.14\">"))
    #expect(xml.contains("<gpxtpx:hr>100</gpxtpx:hr>"))   // HR carried onto GPS point
}

@Test func exportGPXThrowsWithoutGPS() throws {
    let (root, items) = try loadFixtureWorkouts()
    #expect(throws: (any Error).self) {
        try Exporter.export(exDir: root.exDir, workout: items[1], format: .gpx)
    }
}

@Test func filenameFormat() throws {
    let (root, items) = try loadFixtureWorkouts()
    let out = try Exporter.export(exDir: root.exDir, workout: items[0], format: .tcx)
    #expect(out.filename == "2025-06-14_0800_Run_w1.tcx")  // YYYY-MM-DD_HHMM_Label_id8.ext
}

@Test func buildTrackScalesSynthesizedDistanceToKnownTotal() {
    let points: [[String: Any]] = [
        ["start_time": 0, "speed": 5.0],
        ["start_time": 10000, "speed": 5.0],   // 10s @ 5m/s = 50m synthesized
    ]
    let (track, computed) = TrackBuilder.build(points: points, totalDistance: 100)
    #expect(abs(computed - 100) < 1e-6)          // scaled to known total
    #expect(abs(track.last!.dist - 100) < 1e-6)
}

@Test func unzipRoundTripsExport() throws {
    let dest = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("stk-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: dest) }
    try ZipReader.unzip(zipURL, to: dest)

    let root = try SamsungExport.resolve(dest)
    let items = SamsungExport.loadWorkouts(root: root)
    #expect(items.count == 2)
    let d = WorkoutDetailLoader.load(exDir: root.exDir, workout: items[0])
    #expect(d.route.count == 2)                   // inflated JSON is usable
}

@Test func maybeGunzipPassesThroughNonGzip() {
    let original = Data(String(repeating: "the quick brown fox ", count: 20).utf8)
    #expect(Inflate.maybeGunzip(original) == original)
}

@Test func exportLogMissingCorruptAndRoundTrip() throws {
    let dir = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("stklog-\(UUID().uuidString)")
    let path = dir.appendingPathComponent("sub/exported.json")   // nested
    defer { try? FileManager.default.removeItem(at: dir) }

    #expect(ExportLog.load(path: path).isEmpty)                  // missing -> empty
    _ = try ExportLog.mark(["a", "b"], path: path)
    #expect(Set(ExportLog.load(path: path).keys) == ["a", "b"])  // round-trip
    _ = try ExportLog.mark(["a"], path: path)
    #expect(Set(ExportLog.load(path: path).keys) == ["a", "b"])  // re-mark preserves
    #expect(FileManager.default.fileExists(atPath: path.path))   // created nested dir

    try Data("{not json".utf8).write(to: path)
    #expect(ExportLog.load(path: path).isEmpty)                  // corrupt -> empty
}
