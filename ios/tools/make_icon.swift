// Renders the StravaToolkit app icon (1024×1024 PNG) with CoreGraphics.
// Regenerate:  swift ios/tools/make_icon.swift <output.png>
// Concept: a white running route on Strava orange, green start dot, arrowhead
// heading up-right (export your activity to Strava).

import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let outPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1] : "/tmp/AppIcon-1024.png"

let S = 1024
let cs = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CGContext(data: nil, width: S, height: S, bitsPerComponent: 8, bytesPerRow: 0,
                    space: cs, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!  // opaque, no alpha
let full = CGRect(x: 0, y: 0, width: S, height: S)

func rgb(_ r: Double, _ g: Double, _ b: Double) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: 1)
}

// --- background: vertical Strava-orange gradient ---
let grad = CGGradient(colorsSpace: cs,
                      colors: [rgb(1.0, 0.42, 0.03), rgb(0.86, 0.27, 0.0)] as CFArray,
                      locations: [0, 1])!
ctx.drawLinearGradient(grad, start: CGPoint(x: 0, y: S), end: CGPoint(x: 0, y: 0), options: [])

// --- route path (Catmull-Rom through waypoints) ---
// CoreGraphics origin is bottom-left.
let pts: [CGPoint] = [
    CGPoint(x: 235, y: 300),
    CGPoint(x: 430, y: 430),
    CGPoint(x: 560, y: 300),
    CGPoint(x: 640, y: 560),
    CGPoint(x: 815, y: 720),
]

func catmullRom(_ p: [CGPoint]) -> CGPath {
    let path = CGMutablePath()
    path.move(to: p[0])
    for i in 0 ..< p.count - 1 {
        let p0 = p[max(i - 1, 0)]
        let p1 = p[i]
        let p2 = p[i + 1]
        let p3 = p[min(i + 2, p.count - 1)]
        let c1 = CGPoint(x: p1.x + (p2.x - p0.x) / 6.0, y: p1.y + (p2.y - p0.y) / 6.0)
        let c2 = CGPoint(x: p2.x - (p3.x - p1.x) / 6.0, y: p2.y - (p3.y - p1.y) / 6.0)
        path.addCurve(to: p2, control1: c1, control2: c2)
    }
    return path
}

ctx.setStrokeColor(rgb(1, 1, 1))
ctx.setLineWidth(74)
ctx.setLineCap(.round)
ctx.setLineJoin(.round)
ctx.addPath(catmullRom(pts))
ctx.strokePath()

// --- arrowhead at the end, aligned to the final tangent ---
let a = pts[pts.count - 2], b = pts[pts.count - 1]
let dx = b.x - a.x, dy = b.y - a.y
let len = max((dx * dx + dy * dy).squareRoot(), 0.0001)
let tx = dx / len, ty = dy / len            // unit tangent
let px = -ty, py = tx                        // unit perpendicular
let head: CGFloat = 132
let halfW: CGFloat = 96
let tip = CGPoint(x: b.x + tx * head * 0.55, y: b.y + ty * head * 0.55)
let baseC = CGPoint(x: b.x - tx * head * 0.35, y: b.y - ty * head * 0.35)
let left = CGPoint(x: baseC.x + px * halfW, y: baseC.y + py * halfW)
let right = CGPoint(x: baseC.x - px * halfW, y: baseC.y - py * halfW)
let arrow = CGMutablePath()
arrow.move(to: tip)
arrow.addLine(to: left)
arrow.addLine(to: right)
arrow.closeSubpath()
ctx.setFillColor(rgb(1, 1, 1))
ctx.addPath(arrow)
ctx.fillPath()

// --- start dot: green with a white ring for contrast ---
let start = pts[0]
func disc(_ c: CGPoint, _ r: CGFloat, _ color: CGColor) {
    ctx.setFillColor(color)
    ctx.fillEllipse(in: CGRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r))
}
disc(start, 60, rgb(1, 1, 1))
disc(start, 42, rgb(0.055, 0.62, 0.43))

// --- write PNG ---
guard let img = ctx.makeImage() else { fatalError("makeImage failed") }
let url = URL(fileURLWithPath: outPath)
guard let dst = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)
else { fatalError("destination failed") }
CGImageDestinationAddImage(dst, img, nil)
if CGImageDestinationFinalize(dst) {
    print("wrote \(outPath)")
} else {
    fatalError("finalize failed")
}
