import Foundation

/// Merge GPS points with heart-rate samples and build GPX. Ports
/// `merge_location_hr` + `build_gpx`.
public enum GPXBuilder {

    /// Combine GPS points with HR samples by timestamp, carrying the most recent
    /// HR forward onto each point.
    public static func mergeLocationHR(loc: [[String: Any]], live: [[String: Any]]) -> [[String: Any]] {
        var merged: [Int: [String: Any]] = [:]
        for p in loc {
            guard let t = fnum(p["start_time"]).map({ Int($0) }) else { continue }
            merged[t, default: [:]].merge(p) { _, new in new }
        }
        for p in live {
            guard let t = fnum(p["start_time"]).map({ Int($0) }) else { continue }
            if let hr = fnum(p["heart_rate"]) { merged[t, default: [:]]["heart_rate"] = hr }
        }
        var rows = merged.keys.sorted().map { merged[$0]! }

        var lastHR: Double? = nil
        for i in rows.indices {
            if let hr = fnum(rows[i]["heart_rate"]) { lastHR = hr }
            else if let lastHR { rows[i]["heart_rate"] = lastHR }
        }
        return rows
    }

    /// Returns (gpxText, pointCount). gpxText is nil when there are no coordinates.
    public static func build(rows: [[String: Any]], name: String, type: String) -> (String?, Int) {
        let gps = rows.filter { fnum($0["latitude"]) != nil && fnum($0["longitude"]) != nil }
        if gps.isEmpty { return (nil, 0) }

        var out: [String] = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<gpx creator=\"samsung_to_gpx\" version=\"1.1\" "
            + "xmlns=\"http://www.topografix.com/GPX/1/1\" "
            + "xmlns:gpxtpx=\"http://www.garmin.com/xmlschemas/TrackPointExtension/v1\">",
            "<metadata><time>\(iso(Int(fnum(gps[0]["start_time"]) ?? 0)))</time></metadata>",
            "<trk>",
            "<name>\(xmlEscape(name))</name>",
            "<type>\(type)</type>",
            "<trkseg>",
        ]
        var n = 0
        for r in gps {
            let lat = fnum(r["latitude"])!, lon = fnum(r["longitude"])!
            out.append("<trkpt lat=\"\(lat)\" lon=\"\(lon)\">")
            out.append("<time>\(iso(Int(fnum(r["start_time"]) ?? 0)))</time>")
            if let alt = fnum(r["altitude"]) { out.append(String(format: "<ele>%.1f</ele>", alt)) }
            if let hr = fnum(r["heart_rate"]) {
                out.append(String(format:
                    "<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>%.0f</gpxtpx:hr>"
                    + "</gpxtpx:TrackPointExtension></extensions>", hr))
            }
            out.append("</trkpt>")
            n += 1
        }
        out.append(contentsOf: ["</trkseg>", "</trk>", "</gpx>"])
        return (out.joined(separator: "\n"), n)
    }
}
