import Foundation

/// Convert one workout to a TCX/GPX document. Direct port of `export_workout`.
public enum Exporter {

    public struct Output {
        public let filename: String
        public let kind: String       // "tcx" | "gpx"
        public let data: Data
    }

    public enum ExportError: Error, CustomStringConvertible {
        case noData(String)
        public var description: String {
            if case let .noData(reason) = self { return reason }
            return "No usable data"
        }
    }

    /// Returns the file to write, or throws `.noData` when nothing usable exists
    /// (mirrors the desktop's `(None, reason)`).
    public static func export(exDir: URL, workout w: Workout, format: ExportFormat) throws -> Output {
        let row = w.row
        let code = w.code
        let livePoints = SeriesJSON.load(exDir: exDir, ref: row["live_data"])
        let wantGPX = (format == .gpx) || (format == .auto && w.hasGPS)

        if wantGPX && w.hasGPS {
            let loc = SeriesJSON.load(exDir: exDir, ref: row["location_data"])
            let merged = GPXBuilder.mergeLocationHR(loc: loc, live: livePoints)
            let (label, gtype) = Labels.gpxLabel(for: code)
            let s = w.startMs ?? merged.first.flatMap { fnum($0["start_time"]).map { Int($0) } }
            let name = s != nil ? "\(label) \(iso(s!))" : label
            let (gpxText, _) = GPXBuilder.build(rows: merged, name: name, type: gtype)
            if let gpxText {
                let fname = safeName(startMs: s, label: label, exId: w.id, ext: "gpx")
                return Output(filename: fname, kind: "gpx", data: Data(gpxText.utf8))
            }
            if format == .gpx { throw ExportError.noData("no GPS points") }
            // auto: fall through to TCX
        }

        if format == .gpx { throw ExportError.noData("no GPS") }

        // TCX
        let (track, computed) = TrackBuilder.build(points: livePoints, totalDistance: w.distanceMeters)
        let hasHR = track.contains { $0.hr != nil }
        if track.isEmpty || (w.distanceMeters == 0 && !hasHR) {
            throw ExportError.noData("no usable data")
        }
        let s = w.startMs ?? track[0].t
        let label = Labels.label(for: code)
        let tcxText = TCXBuilder.build(row: row, track: track,
                                       totalDistance: w.distanceMeters > 0 ? w.distanceMeters : computed,
                                       startMs: s)
        let fname = safeName(startMs: s, label: label, exId: w.id, ext: "tcx")
        return Output(filename: fname, kind: "tcx", data: Data(tcxText.utf8))
    }
}
