import Foundation

// Merge live_data samples into a clean per-timestamp track with a monotonically
// increasing cumulative distance. Direct port of `build_track` in
// samsung_to_tcx.py.

public enum TrackBuilder {
    public static func build(points: [[String: Any]], totalDistance: Double)
        -> (track: [TrackPoint], computed: Double)
    {
        let pts = points
            .filter { $0["start_time"] != nil }
            .sorted { (fnum($0["start_time"]) ?? 0) < (fnum($1["start_time"]) ?? 0) }
        if pts.isEmpty { return ([], 0.0) }

        let haveNativeDist = pts.contains { $0["distance"] != nil && fnum($0["distance"]) != nil }

        var track: [TrackPoint] = []
        var cum = 0.0
        var lastSpeed = 0.0
        var lastHR: Double? = nil
        var lastCad: Double? = nil
        var prevT: Int? = nil

        for p in pts {
            let t = Int(fnum(p["start_time"]) ?? 0)
            let hr = fnum(p["heart_rate"])
            let sp = fnum(p["speed"])
            let cad = fnum(p["cadence"])
            let nd = fnum(p["distance"])

            if hr != nil { lastHR = hr }
            if cad != nil { lastCad = cad }

            if haveNativeDist {
                if let nd { cum += nd }      // per-point distance is an incremental delta
            } else {
                if let prevT {               // integrate speed over the interval
                    let dt = Double(t - prevT) / 1000.0
                    if dt > 0 { cum += lastSpeed * dt }
                }
                if let sp { lastSpeed = sp }
            }
            prevT = t
            track.append(TrackPoint(t: t, dist: cum, hr: lastHR, speed: sp, cad: lastCad))
        }

        var computed = track.last?.dist ?? 0.0

        // If distance was synthesised from speed and we know the real total,
        // scale so pace/distance are accurate.
        if !haveNativeDist, totalDistance > 0, computed > 0 {
            let factor = totalDistance / computed
            for i in track.indices { track[i].dist *= factor }
            computed = totalDistance
        }
        return (track, computed)
    }
}
