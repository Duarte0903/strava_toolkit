import Foundation
import StravaToolkitKit

// Headless verification harness for StravaToolkitKit — runs without XCTest or
// Xcode (neither ships with the Command Line Tools). Mirrors the swift-testing
// suite. Usage: swift run stkcheck <path-to-Fixtures>

var failures = 0
var passes = 0
func check(_ cond: Bool, _ name: String) {
    if cond { passes += 1 } else { failures += 1; print("  ✗ FAIL: \(name)") }
}
func approx(_ a: Double, _ b: Double, _ eps: Double = 1e-6) -> Bool { abs(a - b) < eps }

guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write(Data("usage: stkcheck <path-to-Fixtures>\n".utf8))
    exit(2)
}
let fixtures = URL(fileURLWithPath: CommandLine.arguments[1])
let exportDir = fixtures.appendingPathComponent("export")
let zipURL = fixtures.appendingPathComponent("export.zip")

do {
    // --- parsing ---
    let root = try SamsungExport.resolve(exportDir)
    let items = SamsungExport.loadWorkouts(root: root)
    check(items.count == 2, "loadWorkouts count == 2")
    check(items.map(\.id) == ["w1", "w2"], "newest-first order")
    check(items[0].label == "Run" && items[1].label == "Walk", "labels")
    check(items[0].hasGPS && !items[1].hasGPS, "hasGPS flags")
    check(SamsungExport.sportLabels(items) == ["Run", "Walk"], "sportLabels")

    // --- detail ---
    let d = WorkoutDetailLoader.load(exDir: root.exDir, workout: items[0])
    check(d.hrSeries.map(\.elapsed) == [0, 1], "hr elapsed")
    check(d.hrSeries.map(\.bpm) == [100, 150], "hr values")
    check(d.paceSeries.map(\.secPerKm) == [500, 250], "pace values (1000/speed)")
    check(d.route.count == 2 && approx(d.route[0].lat, 38.72, 1e-9), "route points")
    check(d.maxHR == 182 && d.calories == 310, "max HR + calories")
    check(approx(d.avgPaceSecPerKm ?? -1, 300), "avg pace 300 s/km")

    // --- pace skips zero/missing speed ---
    let track = [
        TrackPoint(t: 1000, dist: 0, hr: nil, speed: 0, cad: nil),
        TrackPoint(t: 2000, dist: 0, hr: 140, speed: 5.0, cad: nil),
        TrackPoint(t: 3000, dist: 0, hr: 145, speed: nil, cad: nil),
    ]
    let (hr, pace) = WorkoutDetailLoader.series(track: track)
    check(pace.map { $0.0 } == [1.0] && pace.map { $0.1 } == [200.0], "pace skips zero/missing")
    check(hr.map { $0.1 } == [140, 145], "hr from track")

    // --- TCX ---
    let tcx = try Exporter.export(exDir: root.exDir, workout: items[0], format: .tcx)
    let tx = String(decoding: tcx.data, as: UTF8.self)
    check(tcx.kind == "tcx" && tcx.filename.hasSuffix(".tcx"), "tcx kind/filename")
    check(tx.contains("<Activity Sport=\"Running\">"), "tcx sport")
    check(tx.contains("<HeartRateBpm><Value>100</Value></HeartRateBpm>"), "tcx HR")
    check(tx.contains("<DistanceMeters>2000.00</DistanceMeters>"), "tcx distance")
    check(tcx.filename == "2025-06-14_0800_Run_w1.tcx", "tcx filename format")

    // --- GPX (auto prefers GPX when GPS present) ---
    let gpx = try Exporter.export(exDir: root.exDir, workout: items[0], format: .auto)
    let gx = String(decoding: gpx.data, as: UTF8.self)
    check(gpx.kind == "gpx", "auto -> gpx when GPS")
    check(gx.contains("<trkpt lat=\"38.72\" lon=\"-9.14\">"), "gpx trkpt")
    check(gx.contains("<gpxtpx:hr>100</gpxtpx:hr>"), "gpx HR carried onto GPS point")

    // --- GPX forced without GPS throws ---
    var threw = false
    do { _ = try Exporter.export(exDir: root.exDir, workout: items[1], format: .gpx) }
    catch { threw = true }
    check(threw, "gpx without GPS throws")

    // --- track distance scaling ---
    let pts: [[String: Any]] = [["start_time": 0, "speed": 5.0], ["start_time": 10000, "speed": 5.0]]
    let (tr, computed) = TrackBuilder.build(points: pts, totalDistance: 100)
    check(approx(computed, 100) && approx(tr.last!.dist, 100), "synthesized distance scaled to total")

    // --- zip round-trip (exercises raw-deflate inflate) ---
    let dest = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("stk-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: dest) }
    try ZipReader.unzip(zipURL, to: dest)
    let zroot = try SamsungExport.resolve(dest)
    let zitems = SamsungExport.loadWorkouts(root: zroot)
    check(zitems.count == 2, "unzip + parse == 2 workouts")
    check(WorkoutDetailLoader.load(exDir: zroot.exDir, workout: zitems[0]).route.count == 2,
          "inflated JSON usable")

    // --- gunzip passthrough ---
    let raw = Data("passthrough".utf8)
    check(Inflate.maybeGunzip(raw) == raw, "maybeGunzip passthrough")

    // --- export log ---
    let logDir = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("stklog-\(UUID().uuidString)")
    let logPath = logDir.appendingPathComponent("sub/exported.json")   // nested: tests dir creation
    defer { try? FileManager.default.removeItem(at: logDir) }

    check(ExportLog.load(path: logPath).isEmpty, "export log: missing file -> empty")
    _ = try ExportLog.mark(["a", "b"], path: logPath)
    check(Set(ExportLog.load(path: logPath).keys) == ["a", "b"], "export log: mark + load round-trip")
    _ = try ExportLog.mark(["a"], path: logPath)                       // re-mark a; b must survive
    check(Set(ExportLog.load(path: logPath).keys) == ["a", "b"], "export log: re-mark preserves others")
    check(FileManager.default.fileExists(atPath: logPath.path), "export log: created nested dir + file")

    // corrupt file -> empty
    try Data("{not json".utf8).write(to: logPath)
    check(ExportLog.load(path: logPath).isEmpty, "export log: corrupt file -> empty")

} catch {
    print("  ✗ EXCEPTION: \(error)")
    failures += 1
}

print("\n\(passes) checks passed, \(failures) failed")
exit(failures == 0 ? 0 : 1)
