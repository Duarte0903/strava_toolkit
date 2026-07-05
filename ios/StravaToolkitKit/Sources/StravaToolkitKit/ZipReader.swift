import Foundation

/// Minimal ZIP extractor (store + deflate) built on the Compression framework.
/// Enough to unpack a Samsung Health export .zip on-device.
public enum ZipReader {

    public enum ZipError: Error, CustomStringConvertible {
        case notAZip
        case corrupt(String)
        public var description: String {
            switch self {
            case .notAZip: return "That file isn't a valid .zip."
            case .corrupt(let m): return "Couldn't read the .zip: \(m)"
            }
        }
    }

    /// Extract `zipURL` into `dest` (created if needed). Returns written file URLs.
    @discardableResult
    public static func unzip(_ zipURL: URL, to dest: URL) throws -> [URL] {
        let data = try Data(contentsOf: zipURL)
        return try unzip(data: data, to: dest)
    }

    static func u16(_ d: Data, _ o: Int) -> Int { Int(d[o]) | (Int(d[o + 1]) << 8) }
    static func u32(_ d: Data, _ o: Int) -> Int {
        Int(d[o]) | (Int(d[o + 1]) << 8) | (Int(d[o + 2]) << 16) | (Int(d[o + 3]) << 24)
    }

    @discardableResult
    static func unzip(data d: Data, to dest: URL) throws -> [URL] {
        // Data indexing must be zero-based; normalise just in case.
        let data = Data(d)
        let eocdSig = 0x06054b50
        // Scan backwards for the End Of Central Directory record.
        var eocd = -1
        if data.count >= 22 {
            var i = data.count - 22
            let lower = max(0, data.count - 22 - 65_536)
            while i >= lower {
                if u32(data, i) == eocdSig { eocd = i; break }
                i -= 1
            }
        }
        guard eocd >= 0 else { throw ZipError.notAZip }

        let entryCount = u16(data, eocd + 10)
        var cd = u32(data, eocd + 16)          // offset of first central-directory header

        let fm = FileManager.default
        try fm.createDirectory(at: dest, withIntermediateDirectories: true)
        var written: [URL] = []

        for _ in 0 ..< entryCount {
            guard cd + 46 <= data.count, u32(data, cd) == 0x02014b50 else {
                throw ZipError.corrupt("bad central directory header")
            }
            let method = u16(data, cd + 10)
            let compSize = u32(data, cd + 20)
            let nameLen = u16(data, cd + 28)
            let extraLen = u16(data, cd + 30)
            let commentLen = u16(data, cd + 32)
            let localOff = u32(data, cd + 42)
            let nameData = data.subdata(in: (cd + 46) ..< (cd + 46 + nameLen))
            let name = String(decoding: nameData, as: UTF8.self)
            cd += 46 + nameLen + extraLen + commentLen

            // Skip directory entries and unsafe paths.
            if name.hasSuffix("/") { continue }
            if name.hasPrefix("/") || name.contains("..") { continue }

            // Locate the data via the local header's own name/extra lengths.
            guard localOff + 30 <= data.count, u32(data, localOff) == 0x04034b50 else {
                throw ZipError.corrupt("bad local header for \(name)")
            }
            let lNameLen = u16(data, localOff + 26)
            let lExtraLen = u16(data, localOff + 28)
            let start = localOff + 30 + lNameLen + lExtraLen
            guard start + compSize <= data.count else { throw ZipError.corrupt("truncated data for \(name)") }
            let comp = data.subdata(in: start ..< (start + compSize))

            let out: Data
            switch method {
            case 0: out = comp                                   // stored
            case 8:
                guard let inflated = Inflate.rawDeflate(comp) else {
                    throw ZipError.corrupt("inflate failed for \(name)")
                }
                out = inflated
            default:
                throw ZipError.corrupt("unsupported compression (\(method)) for \(name)")
            }

            let fileURL = dest.appendingPathComponent(name)
            try fm.createDirectory(at: fileURL.deletingLastPathComponent(),
                                   withIntermediateDirectories: true)
            try out.write(to: fileURL)
            written.append(fileURL)
        }
        return written
    }
}
