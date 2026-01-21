/**
 * Computes the Convex Hull of a set of points using Monotone Chain algorithm.
 * Input: Array of {latitude, longitude} objects.
 * Output: Array of [lat, lon] tuples defining the hull polygon.
 */

export interface Point {
    latitude: number;
    longitude: number;
}

export function getConvexHull(points: Point[]): [number, number][] {
    if (points.length < 3) {
        // Not enough points for a hull, just return them or a line
        return points.map(p => [p.latitude, p.longitude]);
    }

    // Sort by latitude (y), then longitude (x)
    // Actually standard Monotone Chain sorts by X then Y.
    // Let's treat Lon as X, Lat as Y.
    const sorted = [...points].sort((a, b) => {
        return a.longitude === b.longitude
            ? a.latitude - b.latitude
            : a.longitude - b.longitude;
    });

    // Cross product of vectors OA and OB
    // value > 0: counter-clockwise
    // value < 0: clockwise
    // value = 0: colinear
    const cross = (o: Point, a: Point, b: Point) => {
        return (a.longitude - o.longitude) * (b.latitude - o.latitude)
            - (a.latitude - o.latitude) * (b.longitude - o.longitude);
    };

    // Build lower hull
    const lower: Point[] = [];
    for (const p of sorted) {
        while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
            lower.pop();
        }
        lower.push(p);
    }

    // Build upper hull
    const upper: Point[] = [];
    for (let i = sorted.length - 1; i >= 0; i--) {
        const p = sorted[i];
        while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
            upper.pop();
        }
        upper.push(p);
    }

    // Concatenate lower and upper to create full hull
    // Remove last point of each as it's repeated
    lower.pop();
    upper.pop();

    const hullStub = [...lower, ...upper];
    return hullStub.map(p => [p.latitude, p.longitude]);
}
