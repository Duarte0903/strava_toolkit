import Foundation
import Compression

// Raw DEFLATE + gzip decompression via Apple's Compression framework.
// Apple's COMPRESSION_ZLIB consumes raw DEFLATE (RFC 1951) — exactly what ZIP
// stores for method 8, and what remains after stripping a gzip wrapper.

public enum Inflate {
    /// Inflate raw DEFLATE bytes. `hint` seeds the output buffer; it grows on demand.
    public static func rawDeflate(_ src: Data, hint: Int = 1 << 16) -> Data? {
        if src.isEmpty { return Data() }
        var capacity = max(hint, src.count * 4, 1024)
        while true {
            let dst = UnsafeMutablePointer<UInt8>.allocate(capacity: capacity)
            defer { dst.deallocate() }
            let n = src.withUnsafeBytes { (sp: UnsafeRawBufferPointer) -> Int in
                compression_decode_buffer(dst, capacity,
                                          sp.bindMemory(to: UInt8.self).baseAddress!, src.count,
                                          nil, COMPRESSION_ZLIB)
            }
            if n == 0 { return nil }
            // If we exactly filled the buffer, the output may have been truncated;
            // grow and retry so we never silently lose data.
            if n == capacity && capacity < (1 << 28) {
                capacity *= 2
                continue
            }
            return Data(bytes: dst, count: n)
        }
    }

    /// Decompress a gzip member (RFC 1952): parse the header, inflate the body.
    public static func gzip(_ data: Data) -> Data? {
        let b = [UInt8](data)
        guard b.count > 18, b[0] == 0x1f, b[1] == 0x8b, b[2] == 8 else { return nil }
        let flags = b[3]
        var i = 10
        func skipZeroTerminated() { while i < b.count && b[i] != 0 { i += 1 }; i += 1 }
        if flags & 0x04 != 0 {                 // FEXTRA
            guard i + 1 < b.count else { return nil }
            let xlen = Int(b[i]) | (Int(b[i + 1]) << 8)
            i += 2 + xlen
        }
        if flags & 0x08 != 0 { skipZeroTerminated() }   // FNAME
        if flags & 0x10 != 0 { skipZeroTerminated() }   // FCOMMENT
        if flags & 0x02 != 0 { i += 2 }                  // FHCRC
        guard i <= b.count - 8 else { return nil }
        let body = data.subdata(in: i ..< (data.count - 8))  // drop 8-byte CRC+ISIZE trailer
        return rawDeflate(body)
    }

    /// gzip if magic present, otherwise return the bytes unchanged.
    public static func maybeGunzip(_ data: Data) -> Data {
        if data.count >= 2, data[data.startIndex] == 0x1f,
           data[data.startIndex + 1] == 0x8b {
            return gzip(data) ?? data
        }
        return data
    }
}
