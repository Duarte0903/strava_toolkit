import Foundation

/// Build a TCX document from a track. Direct port of `build_tcx`.
public enum TCXBuilder {
    public static func build(row: [String: String], track: [TrackPoint],
                             totalDistance: Double, startMs: Int) -> String {
        let durS = (fnum(row["duration"]) ?? 0) / 1000.0
        let cal = fnum(row["calorie"])
        let meanHR = fnum(row["mean_heart_rate"])
        let maxHR = fnum(row["max_heart_rate"])
        let code = Int(fnum(row["exercise_type"]) ?? 0)
        let sport = Labels.sport(for: code)

        var out: [String] = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<TrainingCenterDatabase "
            + "xmlns=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2\" "
            + "xmlns:ns3=\"http://www.garmin.com/xmlschemas/ActivityExtension/v2\" "
            + "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
            + "xsi:schemaLocation=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
            + "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd\">",
            "<Activities>",
            "<Activity Sport=\"\(sport)\">",
            "<Id>\(iso(startMs))</Id>",
            "<Lap StartTime=\"\(iso(startMs))\">",
            String(format: "<TotalTimeSeconds>%.0f</TotalTimeSeconds>", durS),
            String(format: "<DistanceMeters>%.2f</DistanceMeters>", totalDistance),
        ]
        if let cal { out.append(String(format: "<Calories>%.0f</Calories>", cal)) }
        if let meanHR { out.append(String(format: "<AverageHeartRateBpm><Value>%.0f</Value></AverageHeartRateBpm>", meanHR)) }
        if let maxHR { out.append(String(format: "<MaximumHeartRateBpm><Value>%.0f</Value></MaximumHeartRateBpm>", maxHR)) }
        out.append("<Intensity>Active</Intensity>")
        out.append("<TriggerMethod>Manual</TriggerMethod>")
        out.append("<Track>")

        for tp in track {
            out.append("<Trackpoint>")
            out.append("<Time>\(iso(tp.t))</Time>")
            out.append(String(format: "<DistanceMeters>%.2f</DistanceMeters>", tp.dist))
            if let hr = tp.hr {
                out.append(String(format: "<HeartRateBpm><Value>%.0f</Value></HeartRateBpm>", hr))
            }
            if let cad = tp.cad, Labels.biking.contains(code) {
                out.append(String(format: "<Cadence>%.0f</Cadence>", min(cad, 254)))
            }
            if let sp = tp.speed {
                out.append(String(format:
                    "<Extensions><ns3:TPX><ns3:Speed>%.3f</ns3:Speed></ns3:TPX></Extensions>", sp))
            }
            out.append("</Trackpoint>")
        }
        out.append(contentsOf: ["</Track>", "</Lap>", "</Activity>", "</Activities>", "</TrainingCenterDatabase>"])
        return out.joined(separator: "\n")
    }
}
