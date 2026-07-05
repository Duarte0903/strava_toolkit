import Foundation

/// One workout listed from the exercise CSV. Mirrors the dict built by
/// `workout_core.load_workouts`.
public struct Workout: Identifiable, Hashable {
    public let id: String              // Samsung datauuid
    public let row: [String: String]   // raw CSV row
    public let code: Int               // exercise_type
    public let label: String
    public let startMs: Int?           // epoch ms (UTC) or nil
    public let durationSeconds: Double
    public let distanceMeters: Double
    public let avgHR: Double?
    public let hasGPS: Bool

    public static func == (a: Workout, b: Workout) -> Bool { a.id == b.id }
    public func hash(into h: inout Hasher) { h.combine(id) }
}

public enum ExportFormat: String, CaseIterable {
    case auto, tcx, gpx
    public var display: String {
        switch self {
        case .auto: return "Auto (map if GPS)"
        case .tcx: return "TCX"
        case .gpx: return "GPX"
        }
    }
}

/// A single merged track sample. Port of the dict in `build_track`.
public struct TrackPoint {
    public var t: Int          // epoch ms
    public var dist: Double    // cumulative metres
    public var hr: Double?
    public var speed: Double?
    public var cad: Double?

    public init(t: Int, dist: Double, hr: Double? = nil, speed: Double? = nil, cad: Double? = nil) {
        self.t = t; self.dist = dist; self.hr = hr; self.speed = speed; self.cad = cad
    }
}

/// Everything the inspect view needs. Port of `load_detail`.
public struct WorkoutDetail {
    public let sport: String
    public let date: String
    public let durationSeconds: Double
    public let distanceMeters: Double
    public let avgHR: Double?
    public let maxHR: Double?
    public let calories: Double?
    public let avgPaceSecPerKm: Double?
    public let hasGPS: Bool
    public let hrSeries: [(elapsed: Double, bpm: Double)]
    public let paceSeries: [(elapsed: Double, secPerKm: Double)]
    public let route: [(lat: Double, lon: Double)]
}
