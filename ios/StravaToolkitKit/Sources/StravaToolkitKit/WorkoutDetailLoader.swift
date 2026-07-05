import Foundation

/// Builds the inspect-view detail for one workout. Direct port of `load_detail`.
public enum WorkoutDetailLoader {

    /// Derive HR and pace series from a track (elapsed seconds from the first
    /// sample). Pace = 1000/speed s/km, skipping zero/absent speeds.
    public static func series(track: [TrackPoint])
        -> (hr: [(Double, Double)], pace: [(Double, Double)])
    {
        var hr: [(Double, Double)] = []
        var pace: [(Double, Double)] = []
        guard let t0 = track.first?.t else { return (hr, pace) }
        for tp in track {
            let elapsed = Double(tp.t - t0) / 1000.0
            if let bpm = tp.hr { hr.append((elapsed, bpm)) }
            if let sp = tp.speed, sp > 0 { pace.append((elapsed, 1000.0 / sp)) }
        }
        return (hr, pace)
    }

    public static func load(exDir: URL, workout w: Workout) -> WorkoutDetail {
        let livePoints = SeriesJSON.load(exDir: exDir, ref: w.row["live_data"])
        let (track, _) = TrackBuilder.build(points: livePoints, totalDistance: w.distanceMeters)
        let (hrSeries, paceSeries) = series(track: track)

        var route: [(Double, Double)] = []
        if w.hasGPS {
            for p in SeriesJSON.load(exDir: exDir, ref: w.row["location_data"]) {
                if let lat = fnum(p["latitude"]), let lon = fnum(p["longitude"]) {
                    route.append((lat, lon))
                }
            }
        }

        let distM = w.distanceMeters
        let durS = w.durationSeconds
        let avgPace = distM > 0 ? durS / (distM / 1000.0) : nil

        return WorkoutDetail(
            sport: w.label,
            date: fmtDate(w.startMs),
            durationSeconds: durS,
            distanceMeters: distM,
            avgHR: w.avgHR,
            maxHR: fnum(w.row["max_heart_rate"]),
            calories: fnum(w.row["calorie"]),
            avgPaceSecPerKm: avgPace,
            hasGPS: w.hasGPS,
            hrSeries: hrSeries.map { (elapsed: $0.0, bpm: $0.1) },
            paceSeries: paceSeries.map { (elapsed: $0.0, secPerKm: $0.1) },
            route: route.map { (lat: $0.0, lon: $0.1) })
    }
}
