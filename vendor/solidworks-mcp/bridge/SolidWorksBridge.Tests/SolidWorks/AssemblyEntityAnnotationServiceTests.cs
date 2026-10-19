using SolidWorksBridge.SolidWorks;
using Moq;
using System.Text;
using System.Text.Json;

namespace SolidWorksBridge.Tests.SolidWorks;

public class AssemblyEntityAnnotationServiceTests
{
    [Theory]
    [InlineData("拉伸1", null)]
    [InlineData("拉伸1", "")]
    [InlineData("草图1", "ProfileFeature")]
    [InlineData("折弯1", "OneBend")]
    public void ShouldCaptureFeatureTarget_FiltersNonDimensionFeatureTypes(string? featureName, string? featureTypeName)
    {
        Assert.False(AssemblyEntityAnnotationService.ShouldCaptureFeatureTarget(featureName, featureTypeName));
    }

    [Theory]
    [InlineData("3D草图1", "3DProfileFeature")]
    [InlineData("拉伸1", "Extrude")]
    [InlineData("基体法兰1", "BaseFlange")]
    public void ShouldCaptureFeatureTarget_KeepsPhysicalOrEditableFeatureTypes(string featureName, string featureTypeName)
    {
        Assert.True(AssemblyEntityAnnotationService.ShouldCaptureFeatureTarget(featureName, featureTypeName));
    }

    [Fact]
    public void ShouldKeepCaptureTarget_WhenFeatureTypeIsRequired_FiltersTargetsWithoutValidFeatureTypeName()
    {
        var component = new AssemblyEntityCaptureTargetInfo
        {
            TargetId = "component-1",
            EntityKind = "component",
            DisplayName = "装配体/零件1",
        };
        var profile = new AssemblyEntityCaptureTargetInfo
        {
            TargetId = "feature-profile",
            EntityKind = "feature",
            DisplayName = "装配体/草图1",
            FeatureName = "草图1",
            FeatureTypeName = "ProfileFeature",
        };
        var extrude = new AssemblyEntityCaptureTargetInfo
        {
            TargetId = "feature-extrude",
            EntityKind = "feature",
            DisplayName = "装配体/拉伸1",
            FeatureName = "拉伸1",
            FeatureTypeName = "Extrude",
        };

        Assert.False(AssemblyEntityAnnotationService.ShouldKeepCaptureTarget(component, requireFeatureTypeName: true));
        Assert.False(AssemblyEntityAnnotationService.ShouldKeepCaptureTarget(profile, requireFeatureTypeName: true));
        Assert.True(AssemblyEntityAnnotationService.ShouldKeepCaptureTarget(extrude, requireFeatureTypeName: true));
    }

    [Fact]
    public void ShouldKeepCaptureTarget_WhenFeatureTypeIsNotRequired_KeepsNonFeatureTargets()
    {
        var component = new AssemblyEntityCaptureTargetInfo
        {
            TargetId = "component-1",
            EntityKind = "component",
            DisplayName = "装配体/零件1",
        };

        Assert.True(AssemblyEntityAnnotationService.ShouldKeepCaptureTarget(component, requireFeatureTypeName: false));
    }

    [Fact]
    public void QueryAssemblyStructuralComponentTargets_FindsStructualInfoByType()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"sw-mcp-structural-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        string manifestPath = Path.Combine(directory, "manifest.json");
        try
        {
            var manifest = new
            {
                schemaVersion = AssemblyEntityAnnotationService.CaptureSchemaVersion,
                manifestPath,
                outputDirectory = directory,
                targets = new object[]
                {
                    new
                    {
                        targetId = "height-target",
                        entityKind = "feature",
                        displayName = "active assembly/0:HeightFeature",
                        featureName = "HeightFeature",
                        featureTypeName = "Extrude",
                        featurePath = "0:HeightFeature",
                        hasSubFeatures = true,
                        StructualInfo = new
                        {
                            IsStructualComponent = true,
                            Type = "Height",
                        },
                    },
                    new
                    {
                        targetId = "length-target",
                        entityKind = "feature",
                        displayName = "active assembly/1:LengthFeature",
                        featureName = "LengthFeature",
                        featureTypeName = "Extrude",
                        featurePath = "1:LengthFeature",
                        hasSubFeatures = true,
                        StructualInfo = new
                        {
                            IsStructualComponent = true,
                            Type = "Length",
                        },
                    },
                    new
                    {
                        targetId = "normal-target",
                        entityKind = "feature",
                        displayName = "active assembly/2:InternalFeature",
                        featureName = "InternalFeature",
                        featureTypeName = "Extrude",
                        featurePath = "2:InternalFeature",
                    },
                },
            };
            File.WriteAllText(
                manifestPath,
                JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }),
                Encoding.UTF8);

            var service = new AssemblyEntityAnnotationService(new Mock<ISwConnectionManager>().Object);

            var result = service.QueryAssemblyStructuralComponentTargets(
                manifestPath,
                type: null,
                query: "我想将这整个零件的高度增高100mm",
                maxResults: 10);

            Assert.Equal("height", result.RequestedType);
            var match = Assert.Single(result.Matches);
            Assert.Equal("height-target", match.Target.TargetId);
            Assert.Equal("height", match.StructuralType);
            Assert.True(match.StructualInfo.IsMarkedStructural);
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }
}
