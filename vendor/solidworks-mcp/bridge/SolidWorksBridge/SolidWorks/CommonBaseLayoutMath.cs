namespace SolidWorksBridge.SolidWorks;

public record CommonBaseFrame(
    double[] Origin,
    double[] UAxis,
    double[] VAxis,
    double[] Normal);

public record CommonBaseLayout2d(
    double X,
    double Y,
    double? ThetaDegrees = null,
    string? ThetaAxis = null,
    double NormalOffsetMeters = 0);

public record CommonBaseNormalAlignmentRotation(
    double[] Axis,
    double AngleDegrees);

public static class CommonBaseLayoutMath
{
    public static CommonBaseFrame CreateFrame(
        IReadOnlyList<double> origin,
        IReadOnlyList<double> normal,
        IReadOnlyList<double>? preferredUAxis = null)
    {
        var n = Normalize(ToArray3(normal, nameof(normal)));
        if (Length(n) < 1e-12)
        {
            throw new ArgumentException("normal must not be zero.", nameof(normal));
        }

        var preferred = preferredUAxis == null
            ? ChooseFallbackAxis(n)
            : ToArray3(preferredUAxis, nameof(preferredUAxis));

        var u = Subtract(preferred, Scale(n, Dot(preferred, n)));
        if (Length(u) < 1e-9)
        {
            preferred = ChooseFallbackAxis(n);
            u = Subtract(preferred, Scale(n, Dot(preferred, n)));
        }

        u = Normalize(u);
        var v = Normalize(Cross(n, u));

        return new CommonBaseFrame(
            ToArray3(origin, nameof(origin)),
            u,
            v,
            n);
    }

    public static CommonBaseLayout2d ProjectPoint(
        IReadOnlyList<double> point,
        CommonBaseFrame frame)
    {
        var delta = Subtract(ToArray3(point, nameof(point)), frame.Origin);
        return new CommonBaseLayout2d(
            Dot(delta, frame.UAxis),
            Dot(delta, frame.VAxis),
            NormalOffsetMeters: Dot(delta, frame.Normal));
    }

    public static double[] PointFromLayout(CommonBaseLayout2d layout, CommonBaseFrame frame)
        => Add(
            frame.Origin,
            Add(
                Add(Scale(frame.UAxis, layout.X), Scale(frame.VAxis, layout.Y)),
                Scale(frame.Normal, layout.NormalOffsetMeters)));

    public static double[] ComponentTranslationForMappedPoint(
        IReadOnlyList<double> sourceComponentTranslation,
        IReadOnlyList<double> sourceXAxis,
        IReadOnlyList<double> sourceYAxis,
        IReadOnlyList<double> sourceZAxis,
        IReadOnlyList<double> sourcePointWorld,
        IReadOnlyList<double> targetXAxis,
        IReadOnlyList<double> targetYAxis,
        IReadOnlyList<double> targetZAxis,
        IReadOnlyList<double> targetPointWorld)
    {
        var sourceOffset = Subtract(
            ToArray3(sourcePointWorld, nameof(sourcePointWorld)),
            ToArray3(sourceComponentTranslation, nameof(sourceComponentTranslation)));
        var sourceX = Normalize(ToArray3(sourceXAxis, nameof(sourceXAxis)));
        var sourceY = Normalize(ToArray3(sourceYAxis, nameof(sourceYAxis)));
        var sourceZ = Normalize(ToArray3(sourceZAxis, nameof(sourceZAxis)));
        var localPoint = new[]
        {
            Dot(sourceOffset, sourceX),
            Dot(sourceOffset, sourceY),
            Dot(sourceOffset, sourceZ),
        };
        var targetOffset = Add(
            Add(
                Scale(Normalize(ToArray3(targetXAxis, nameof(targetXAxis))), localPoint[0]),
                Scale(Normalize(ToArray3(targetYAxis, nameof(targetYAxis))), localPoint[1])),
            Scale(Normalize(ToArray3(targetZAxis, nameof(targetZAxis))), localPoint[2]));
        return Subtract(ToArray3(targetPointWorld, nameof(targetPointWorld)), targetOffset);
    }

    public static CommonBaseLayout2d ProjectPointWithRotation(
        IReadOnlyList<double> point,
        CommonBaseFrame frame,
        IReadOnlyList<double>? xAxis,
        IReadOnlyList<double>? yAxis,
        IReadOnlyList<double>? zAxis)
    {
        var pointLayout = ProjectPoint(point, frame);
        var rotation = CalculateBestInPlaneRotation(xAxis, yAxis, zAxis, frame);
        return rotation == null
            ? pointLayout
            : pointLayout with
            {
                ThetaDegrees = rotation.Value.ThetaDegrees,
                ThetaAxis = rotation.Value.AxisName,
            };
    }

    public static (double ThetaDegrees, string AxisName, double ProjectionLength)? CalculateBestInPlaneRotation(
        IReadOnlyList<double>? xAxis,
        IReadOnlyList<double>? yAxis,
        IReadOnlyList<double>? zAxis,
        CommonBaseFrame frame)
    {
        var candidates = new[]
        {
            ("x", xAxis),
            ("y", yAxis),
            ("z", zAxis),
        };

        (double ThetaDegrees, string AxisName, double ProjectionLength)? best = null;
        foreach (var (axisName, axis) in candidates)
        {
            if (axis == null || axis.Count < 3)
            {
                continue;
            }

            var projected = ProjectVectorToPlane(axis, frame.Normal);
            var length = Length(projected);
            if (length < 1e-9)
            {
                continue;
            }

            var unit = Normalize(projected);
            var theta = Math.Atan2(Dot(unit, frame.VAxis), Dot(unit, frame.UAxis)) * 180.0 / Math.PI;
            if (best == null || length > best.Value.ProjectionLength)
            {
                best = (NormalizeAngleDegrees(theta), axisName, length);
            }
        }

        return best;
    }

    public static double? CalculateInPlaneRotationForAxis(
        IReadOnlyList<double>? axis,
        CommonBaseFrame frame)
    {
        if (axis == null || axis.Count < 3)
        {
            return null;
        }

        var projected = ProjectVectorToPlane(axis, frame.Normal);
        if (Length(projected) < 1e-9)
        {
            return null;
        }

        var unit = Normalize(projected);
        return NormalizeAngleDegrees(Math.Atan2(Dot(unit, frame.VAxis), Dot(unit, frame.UAxis)) * 180.0 / Math.PI);
    }

    public static double NormalizeAngleDegrees(double angleDegrees)
    {
        var value = angleDegrees % 360.0;
        if (value <= -180.0) value += 360.0;
        if (value > 180.0) value -= 360.0;
        return value;
    }

    public static double DeltaAngleDegrees(double fromDegrees, double toDegrees)
        => NormalizeAngleDegrees(toDegrees - fromDegrees);

    public static double Dot(IReadOnlyList<double> a, IReadOnlyList<double> b)
        => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

    public static bool NormalsMatchDirection(
        IReadOnlyList<double> candidate,
        IReadOnlyList<double> baseline,
        double dotThreshold = 0.95)
        => IsValidNormal(candidate)
            && IsValidNormal(baseline)
            && Dot(Normalize(candidate), Normalize(baseline)) >= dotThreshold;

    public static bool IsValidNormal(IReadOnlyList<double>? vector, double tolerance = 1e-9)
        => vector is { Count: >= 3 } && Length(vector) >= tolerance;

    public static CommonBaseNormalAlignmentRotation? CalculateNormalAlignmentRotation(
        IReadOnlyList<double> fromNormal,
        IReadOnlyList<double> toNormal)
    {
        if (!IsValidNormal(fromNormal) || !IsValidNormal(toNormal))
        {
            return null;
        }

        var from = Normalize(fromNormal);
        var to = Normalize(toNormal);
        var dot = Math.Clamp(Dot(from, to), -1, 1);
        if (dot > 0.999999)
        {
            return new CommonBaseNormalAlignmentRotation([1, 0, 0], 0);
        }

        var axis = Cross(from, to);
        var axisLength = Length(axis);
        if (axisLength < 1e-9)
        {
            axis = Cross(from, ChooseFallbackAxis(from));
            axisLength = Length(axis);
        }

        if (axisLength < 1e-9)
        {
            return null;
        }

        double[] normalizedAxis = [axis[0] / axisLength, axis[1] / axisLength, axis[2] / axisLength];
        var angleDegrees = Math.Acos(dot) * 180.0 / Math.PI;
        return new CommonBaseNormalAlignmentRotation(normalizedAxis, angleDegrees);
    }

    public static double[] Normalize(IReadOnlyList<double> vector)
    {
        var data = ToArray3(vector, nameof(vector));
        var length = Length(data);
        return length < 1e-12 ? [0, 0, 0] : [data[0] / length, data[1] / length, data[2] / length];
    }

    private static double[] ChooseFallbackAxis(IReadOnlyList<double> normal)
    {
        var xScore = Math.Abs(Dot(normal, [1.0, 0, 0]));
        return xScore < 0.9 ? [1, 0, 0] : [0, 1, 0];
    }

    private static double[] ToArray3(IReadOnlyList<double> values, string name)
    {
        if (values.Count < 3)
        {
            throw new ArgumentException($"{name} must contain at least three numbers.", name);
        }

        return [values[0], values[1], values[2]];
    }

    private static double Length(IReadOnlyList<double> vector)
        => Math.Sqrt(Dot(vector, vector));

    private static double[] Add(IReadOnlyList<double> a, IReadOnlyList<double> b)
        => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];

    private static double[] Subtract(IReadOnlyList<double> a, IReadOnlyList<double> b)
        => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

    private static double[] Scale(IReadOnlyList<double> vector, double scale)
        => [vector[0] * scale, vector[1] * scale, vector[2] * scale];

    private static double[] ProjectVectorToPlane(IReadOnlyList<double> vector, IReadOnlyList<double> normal)
    {
        var data = ToArray3(vector, nameof(vector));
        var n = Normalize(normal);
        return Subtract(data, Scale(n, Dot(data, n)));
    }

    private static double[] Cross(IReadOnlyList<double> a, IReadOnlyList<double> b)
        => [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ];
}
