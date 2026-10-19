using Moq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorksBridge.SolidWorks;

namespace SolidWorksBridge.Tests.SolidWorks;

public class AssemblyServiceTests
{
    [Fact]
    public void TryParseCylinderSurfaceParameters_NormalizesAxisAndPreservesRadius()
    {
        var result = AssemblyService.TryParseCylinderSurfaceParameters(
            [0.1, 0.2, 0.3, 0.0, 0.0, 2.0, 0.025]);

        Assert.NotNull(result);
        Assert.Equal([0.1, 0.2, 0.3], result!.Origin);
        Assert.Equal([0.0, 0.0, 1.0], result.Axis);
        Assert.Equal(0.025, result.Radius, 9);
    }

    [Theory]
    [InlineData(0.0)]
    [InlineData(-0.01)]
    public void TryParseCylinderSurfaceParameters_RejectsNonPositiveRadius(double radius)
    {
        var result = AssemblyService.TryParseCylinderSurfaceParameters(
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, radius]);

        Assert.Null(result);
    }

    [Fact]
    public void ListTopLevelComponentSubtreePoses_TraversesOnlyRequestedRoot()
    {
        var child = new Mock<Component2>();
        // SolidWorks commonly qualifies nested Name2 values with their parent.
        // The public hierarchy must not repeat that parent segment.
        child.SetupGet(component => component.Name2).Returns("A100-1/A150-1");
        child.Setup(component => component.GetPathName()).Returns(@"C:\Models\A150.SLDASM");
        child.Setup(component => component.GetChildren()).Returns(Array.Empty<object>());

        var target = new Mock<Component2>();
        target.SetupGet(component => component.Name2).Returns("A100-1");
        target.Setup(component => component.GetPathName()).Returns(@"C:\Models\A100.SLDASM");
        target.Setup(component => component.GetChildren()).Returns(new object[] { child.Object });

        var unrelated = new Mock<Component2>();
        unrelated.SetupGet(component => component.Name2).Returns("A600-1");
        unrelated.Setup(component => component.GetPathName()).Returns(@"C:\Models\A600.SLDASM");

        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true))
            .Returns(new object[] { target.Object, unrelated.Object });
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var poses = new AssemblyService(manager.Object)
            .ListTopLevelComponentSubtreePoses("A100-1");

        Assert.Equal(2, poses.Count);
        Assert.Equal("A100-1", poses[0].HierarchyPath);
        Assert.Equal("A100-1/A150-1", poses[1].HierarchyPath);
        Assert.Equal("A150-1", poses[1].Name);
        unrelated.Verify(component => component.GetChildren(), Times.Never);
    }

    [Fact]
    public void ListTopLevelComponentSubtreePoses_ReportsLocalAndTotalTransformsSeparately()
    {
        var localMath = new Mock<MathTransform>();
        localMath.SetupGet(transform => transform.ArrayData).Returns(new double[]
        {
            1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3, 1, 0, 0, 0,
        });
        var totalMath = new Mock<MathTransform>();
        totalMath.SetupGet(transform => transform.ArrayData).Returns(new double[]
        {
            0, 1, 0, -1, 0, 0, 0, 0, 1, 10, 20, 30, 1, 0, 0, 0,
        });
        var target = new Mock<Component2>();
        target.SetupGet(component => component.Name2).Returns("A100-1");
        target.Setup(component => component.GetPathName()).Returns(@"C:\Models\A100.SLDASM");
        target.Setup(component => component.GetChildren()).Returns(Array.Empty<object>());
        target.SetupGet(component => component.Transform2).Returns(localMath.Object);
        target.Setup(component => component.GetTotalTransform(true)).Returns(totalMath.Object);

        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true)).Returns(new object[] { target.Object });
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var pose = Assert.Single(new AssemblyService(manager.Object)
            .ListTopLevelComponentSubtreePoses("A100-1"));

        Assert.Equal(new[] { 1d, 2d, 3d }, pose.Translation);
        Assert.Equal(new[] { 10d, 20d, 30d }, pose.TotalTranslation);
        Assert.Equal(new[] { 0d, 1d, 0d }, pose.TotalXAxis);
        Assert.Equal(new[] { -1d, 0d, 0d }, pose.TotalYAxis);
        Assert.Equal(new[] { 0d, 0d, 1d }, pose.TotalZAxis);
    }

    [Fact]
    public void SetComponentSolvingState_ResolvesExactNestedHierarchyPath()
    {
        var solvingState = (int)swComponentSolvingOption_e.swComponentFlexibleSolving;
        var selectData = new Mock<SelectData>();
        var selectionManager = new Mock<SelectionMgr>();
        selectionManager.Setup(manager => manager.CreateSelectData()).Returns(selectData.Object);

        var child = new Mock<Component2>();
        child.SetupGet(component => component.Name2).Returns("AD20-1");
        child.Setup(component => component.GetPathName()).Returns(@"C:\Models\AD20.SLDASM");
        child.Setup(component => component.GetChildren()).Returns(Array.Empty<object>());
        child.SetupGet(component => component.Solving).Returns(() => solvingState);
        child.SetupGet(component => component.ReferencedConfiguration).Returns("Default");
        child.Setup(component => component.GetSuppression())
            .Returns((int)swComponentSuppressionState_e.swComponentFullyResolved);
        child.SetupGet(component => component.Visible)
            .Returns((int)swComponentVisibilityState_e.swComponentVisible);
        child.SetupGet(component => component.ExcludeFromBOM).Returns(false);
        child.Setup(component => component.IsEnvelope()).Returns(false);
        child.Setup(component => component.Select4(false, selectData.Object, false)).Returns(true);

        var parent = new Mock<Component2>();
        parent.SetupGet(component => component.Name2).Returns("AD10-1");
        parent.Setup(component => component.GetPathName()).Returns(@"C:\Models\AD10.SLDASM");
        parent.Setup(component => component.GetChildren()).Returns(new object[] { child.Object });

        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true)).Returns(new object[] { parent.Object });
        assembly.Setup(document => document.CompConfigProperties5(
                It.IsAny<int>(),
                It.IsAny<int>(),
                It.IsAny<bool>(),
                It.IsAny<bool>(),
                It.IsAny<string>(),
                It.IsAny<bool>(),
                It.IsAny<bool>()))
            .Callback<int, int, bool, bool, string, bool, bool>((_, state, _, _, _, _, _) => solvingState = state)
            .Returns(true);
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        model.SetupGet(document => document.ISelectionManager).Returns(selectionManager.Object);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var result = new AssemblyService(manager.Object).SetComponentSolvingState(
            "AD10-1/AD20-1",
            (int)swComponentSolvingOption_e.swComponentRigidSolving,
            rebuild: false);

        Assert.True(result.Success);
        Assert.Equal("AD10-1/AD20-1", result.HierarchyPath);
        Assert.Equal((int)swComponentSolvingOption_e.swComponentRigidSolving, result.ActualSolvingState);
    }

    [Fact]
    public void ResolveAllLightweightComponents_ReportsNativeResolveAndRebuildResult()
    {
        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.ResolveAllLightWeightComponents(false)).Returns(0);
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        model.Setup(document => document.EditRebuild3()).Returns(true);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var result = new AssemblyService(manager.Object)
            .ResolveAllLightweightComponents(warnIfNotResolved: false, rebuild: true);

        Assert.True(result.Success);
        Assert.Equal(0, result.RawResolveCode);
        Assert.True(result.RebuildSucceeded);
        assembly.Verify(document => document.ResolveAllLightWeightComponents(false), Times.Once);
        model.Verify(document => document.EditRebuild3(), Times.Once);
    }

    [Theory]
    [InlineData((int)swMateType_e.swMateCOINCIDENT, true)]
    [InlineData((int)swMateType_e.swMateCONCENTRIC, true)]
    [InlineData((int)swMateType_e.swMatePARALLEL, true)]
    [InlineData((int)swMateType_e.swMateDISTANCE, true)]
    [InlineData((int)swMateType_e.swMateANGLE, false)]
    [InlineData((int)swMateType_e.swMateWIDTH, false)]
    public void MatePairDemo_AllowsOnlyBasicTwoFaceMateTypes(int mateType, bool expected)
    {
        Assert.Equal(expected, AssemblyService.IsSupportedMatePairType(mateType));
    }

    [Fact]
    public void CanonicalMatePairKey_IsIndependentOfEndpointOrder()
    {
        string forward = AssemblyService.CanonicalMatePairKey("A180", "A800");
        string reverse = AssemblyService.CanonicalMatePairKey("A800", "A180");

        Assert.Equal(forward, reverse);
        Assert.Equal("A180|A800", forward);
    }

    [Fact]
    public void BuildModuleMateBundles_GroupsMateFeaturesAndPreservesInstallationEvidence()
    {
        var modules = new[]
        {
            new AssemblyModuleMateGraphNode("A600", "A600-1", @"C:\Models\A600.SLDASM", "A600-1", null, false, 3, "swComponentResolved", 1),
            new AssemblyModuleMateGraphNode("A800", "A800-1", @"C:\Models\A800.SLDASM", "A800-1", null, false, 3, "swComponentResolved", 1),
        };
        var endpoints = new[]
        {
            new AssemblyModuleMateGraphEndpoint(0, "A600", "A600-1", "A600-1/Base-1", "Base-1", "Base-1", @"C:\Models\Base.SLDPRT", "Face", 0, 2, 0.1, null, null, null, null, null, "a"),
            new AssemblyModuleMateGraphEndpoint(1, "A800", "A800-1", "A800-1/Rail-1", "Rail-1", "Rail-1", @"C:\Models\Rail.SLDPRT", "Face", 0, 4, 0.2, null, null, null, null, null, "b"),
        };
        var mates = new[]
        {
            new AssemblyModuleMateGraphMate("距离1", (int)swMateType_e.swMateDISTANCE, "swMateDISTANCE", 0, "swAlignNONE", 0.025, null, false, true, null, new[] { "A800", "A600" }, new[] { "A800-1", "A600-1" }, endpoints),
            new AssemblyModuleMateGraphMate("平行1", (int)swMateType_e.swMatePARALLEL, "swMatePARALLEL", 0, "swAlignNONE", null, null, false, true, null, new[] { "A600", "A800" }, new[] { "A600-1", "A800-1" }, endpoints),
        };

        var bundle = Assert.Single(AssemblyService.BuildModuleMateBundles(mates, modules));

        Assert.Equal("A600", bundle.FirstModuleToken);
        Assert.Equal("A800", bundle.SecondModuleToken);
        Assert.Equal(2, bundle.MateCount);
        Assert.Equal(2, bundle.BasicTwoFaceRebuildableMateCount);
        Assert.True(bundle.HasPositionDimension);
        Assert.False(bundle.HasCompoundPositioningMate);
        Assert.True(bundle.HasOrientationRelation);
        Assert.Equal("POSITION_AND_ORIENTATION_BUNDLE_CANDIDATE", bundle.InstallationRelationAssessment);
    }

    [Fact]
    public void BuildModuleMateBundles_DoesNotClaimOrientationOnlyRelationFullyPositionsModules()
    {
        var modules = new[]
        {
            new AssemblyModuleMateGraphNode("A180", "A180-1", "", "A180-1", null, false, 3, "swComponentResolved", 1),
            new AssemblyModuleMateGraphNode("A800", "A800-1", "", "A800-1", null, false, 3, "swComponentResolved", 1),
        };
        var mate = new AssemblyModuleMateGraphMate(
            "平行2", (int)swMateType_e.swMatePARALLEL, "swMatePARALLEL", 0, "swAlignNONE",
            null, null, false, false, "diagnostic", new[] { "A180", "A800" }, new[] { "A180-1", "A800-1" }, Array.Empty<AssemblyModuleMateGraphEndpoint>());

        var bundle = Assert.Single(AssemblyService.BuildModuleMateBundles(new[] { mate }, modules));

        Assert.False(bundle.HasPositionDimension);
        Assert.False(bundle.HasCompoundPositioningMate);
        Assert.True(bundle.HasOrientationRelation);
        Assert.Equal("ORIENTATION_OR_CONTACT_ONLY_PARTIAL_RELATION", bundle.InstallationRelationAssessment);
    }

    [Theory]
    [InlineData(0.0000005, false)]
    [InlineData(0.0000010, false)]
    [InlineData(0.0000011, true)]
    [InlineData(0.0005051, true)]
    public void AreBoundingBoxesSeparated_UsesConservativeMetreTolerance(
        double gap,
        bool expected)
    {
        double[] first = [0, 0, 0, 1, 1, 1];
        double[] second = [1 + gap, 0, 0, 2 + gap, 1, 1];

        bool separated = AssemblyService.AreBoundingBoxesSeparated(first, second);

        Assert.Equal(expected, separated);
    }

    [Fact]
    public void AreBoundingBoxesSeparated_NormalizesBoundsAndChecksAllAxes()
    {
        double[] firstReversed = [1, 1, 1, 0, 0, 0];
        double[] separatedOnZ = [0.25, 0.25, 1.01, 0.75, 0.75, 2];

        bool separated = AssemblyService.AreBoundingBoxesSeparated(firstReversed, separatedOnZ);

        Assert.True(separated);
    }

    [Fact]
    public void AreBoundingBoxesSeparated_MissingOrOverlappingBoundsRequireExactCheck()
    {
        double[] overlapping = [0.5, 0.5, 0.5, 1.5, 1.5, 1.5];

        Assert.False(AssemblyService.AreBoundingBoxesSeparated(null, overlapping));
        Assert.False(AssemblyService.AreBoundingBoxesSeparated([0, 0, 0], overlapping));
        Assert.False(AssemblyService.AreBoundingBoxesSeparated([0, 0, 0, 1, 1, 1], overlapping));
    }

    [Fact]
    public void SuppressAndRestoreTopLevelMateFeatures_ChangesOnlyMateGroupChildren()
    {
        var mate = new Mock<Feature>();
        mate.Setup(f => f.Name).Returns("Coincident1");
        mate.Setup(f => f.GetTypeName2()).Returns("MateCoincident");
        mate.SetupSequence(f => f.IsSuppressed()).Returns(false).Returns(true);
        mate.Setup(f => f.SetSuppression((int)swFeatureSuppressionAction_e.swSuppressFeature)).Returns(true);
        mate.Setup(f => f.SetSuppression((int)swFeatureSuppressionAction_e.swUnSuppressFeature)).Returns(true);
        mate.Setup(f => f.IGetNextSubFeature()).Returns((Feature)null!);

        var mateGroup = new Mock<Feature>();
        mateGroup.Setup(f => f.GetTypeName2()).Returns("MateGroup");
        mateGroup.Setup(f => f.IGetFirstSubFeature()).Returns(mate.Object);
        mateGroup.Setup(f => f.IGetNextFeature()).Returns((Feature)null!);

        var assembly = new Mock<IAssemblyDoc>();
        var model = assembly.As<IModelDoc2>();
        model.Setup(d => d.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        model.Setup(d => d.IFirstFeature()).Returns(mateGroup.Object);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.IsConnected).Returns(true);
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var service = new AssemblyService(manager.Object);
        var suppressed = service.SuppressTopLevelMateFeatures();
        var restored = service.RestoreTopLevelMateFeatures(suppressed);

        Assert.Equal(["Coincident1"], suppressed);
        Assert.Equal(["Coincident1"], restored);
        mate.Verify(f => f.SetSuppression((int)swFeatureSuppressionAction_e.swSuppressFeature), Times.Once);
        mate.Verify(f => f.SetSuppression((int)swFeatureSuppressionAction_e.swUnSuppressFeature), Times.Once);
    }

    [Fact]
    public void SuppressTopLevelComponentsExcept_ValidatesKeepListAndPreservesRequestedInstances()
    {
        var keep = new Mock<Component2>();
        keep.SetupGet(component => component.Name2).Returns("A100-1");
        keep.Setup(component => component.IsSuppressed()).Returns(false);

        var remove = new Mock<Component2>();
        remove.SetupGet(component => component.Name2).Returns("A600-1");
        remove.SetupSequence(component => component.IsSuppressed())
            .Returns(false)
            .Returns(true)
            .Returns(true);
        remove.Setup(component => component.SetSuppression2((int)swComponentSuppressionState_e.swComponentSuppressed))
            .Returns((int)swComponentSuppressionState_e.swComponentSuppressed);

        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true))
            .Returns(new object[] { keep.Object, remove.Object });
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        model.Setup(document => document.EditRebuild3()).Returns(true);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var result = new AssemblyService(manager.Object)
            .SuppressTopLevelComponentsExcept(["A100-1"]);

        Assert.True(result.Success);
        Assert.Equal(["A100-1"], result.RemainingResolvedComponentNames);
        Assert.Equal(["A600-1"], result.SuppressedComponentNames);
        remove.Verify(
            component => component.SetSuppression2((int)swComponentSuppressionState_e.swComponentSuppressed),
            Times.Once);
    }

    [Fact]
    public void SuppressTopLevelComponentsExcept_MissingKeepNameDoesNotModifyAssembly()
    {
        var component = new Mock<Component2>();
        component.SetupGet(item => item.Name2).Returns("A100-1");
        component.Setup(item => item.IsSuppressed()).Returns(false);
        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true))
            .Returns(new object[] { component.Object });
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var result = new AssemblyService(manager.Object)
            .SuppressTopLevelComponentsExcept(["A100-1", "A200-1"]);

        Assert.False(result.Success);
        Assert.Equal(["A200-1"], result.MissingKeepComponentNames);
        component.Verify(
            item => item.SetSuppression2(It.IsAny<int>()),
            Times.Never);
    }

    [Fact]
    public void HideTopLevelComponentsExcept_HidesContextWithoutSuppressingIt()
    {
        var keepVisible = (int)swComponentVisibilityState_e.swComponentVisible;
        var hidden = (int)swComponentVisibilityState_e.swComponentHidden;
        var keep = new Mock<Component2>();
        keep.SetupGet(component => component.Name2).Returns("A100-1");
        keep.SetupProperty(component => component.Visible, hidden);
        keep.Setup(component => component.IsSuppressed()).Returns(false);
        var context = new Mock<Component2>();
        context.SetupGet(component => component.Name2).Returns("A600-1");
        context.SetupProperty(component => component.Visible, keepVisible);
        context.Setup(component => component.IsSuppressed()).Returns(false);
        var assembly = new Mock<IAssemblyDoc>();
        assembly.Setup(document => document.GetComponents(true))
            .Returns(new object[] { keep.Object, context.Object });
        var model = assembly.As<IModelDoc2>();
        model.Setup(document => document.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);
        model.Setup(document => document.EditRebuild3()).Returns(true);
        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(app => app.IActiveDoc2).Returns(model.Object);
        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(connection => connection.IsConnected).Returns(true);
        manager.Setup(connection => connection.SwApp).Returns(swApp.Object);
        manager.Setup(connection => connection.EnsureConnected());

        var result = new AssemblyService(manager.Object)
            .HideTopLevelComponentsExcept(["A100-1"]);

        Assert.True(result.Success);
        Assert.Equal(["A100-1"], result.VisibleComponentNames);
        Assert.Equal(["A600-1"], result.HiddenComponentNames);
        Assert.Equal(keepVisible, keep.Object.Visible);
        Assert.Equal(hidden, context.Object.Visible);
        keep.Verify(component => component.SetSuppression2(It.IsAny<int>()), Times.Never);
        context.Verify(component => component.SetSuppression2(It.IsAny<int>()), Times.Never);
    }

    [Fact]
    public void TraverseAssemblyFeatureTrees_PropagatesComponentContextToNestedFeatureNodes()
    {
        var feature = new Mock<Feature>();
        feature.Setup(f => f.Name).Returns("Boss-Extrude1");
        feature.Setup(f => f.GetTypeName2()).Returns("BossExtrude");

        var component = new Mock<Component2>();
        component.Setup(c => c.Name2).Returns("SquareTube-1");
        component.Setup(c => c.GetPathName()).Returns(@"C:\Models\SquareTube.sldprt");

        var featureNode = new Mock<TreeControlItem>();
        featureNode.SetupGet(n => n.Text).Returns("Boss-Extrude1");
        featureNode.SetupGet(n => n.ObjectType).Returns(101);
        featureNode.SetupGet(n => n.Object).Returns(feature.Object);
        featureNode.SetupGet(n => n.IsRoot).Returns(false);
        featureNode.SetupGet(n => n.Expanded).Returns(false);
        featureNode.Setup(n => n.GetFirstChild()).Returns((TreeControlItem)null!);
        featureNode.Setup(n => n.GetNext()).Returns((TreeControlItem)null!);

        var componentNode = new Mock<TreeControlItem>();
        componentNode.SetupGet(n => n.Text).Returns("SquareTube-1");
        componentNode.SetupGet(n => n.ObjectType).Returns(202);
        componentNode.SetupGet(n => n.Object).Returns(component.Object);
        componentNode.SetupGet(n => n.IsRoot).Returns(false);
        componentNode.SetupGet(n => n.Expanded).Returns(true);
        componentNode.Setup(n => n.GetFirstChild()).Returns(featureNode.Object);
        componentNode.Setup(n => n.GetNext()).Returns((TreeControlItem)null!);

        var rootNode = new Mock<TreeControlItem>();
        rootNode.SetupGet(n => n.Text).Returns("TopAsm");
        rootNode.SetupGet(n => n.ObjectType).Returns(1);
        rootNode.SetupGet(n => n.Object).Returns((object?)null);
        rootNode.SetupGet(n => n.IsRoot).Returns(true);
        rootNode.SetupGet(n => n.Expanded).Returns(true);
        rootNode.Setup(n => n.GetFirstChild()).Returns(componentNode.Object);
        rootNode.Setup(n => n.GetNext()).Returns((TreeControlItem)null!);

        var featureManager = new Mock<IFeatureManager>();
        featureManager.Setup(fm => fm.GetFeatureTreeRootItem2(It.IsAny<int>())).Returns(rootNode.Object);

        var assembly = new Mock<IAssemblyDoc>();
        var model = assembly.As<IModelDoc2>();
        model.Setup(d => d.GetTitle()).Returns("TopAsm");
        model.Setup(d => d.GetPathName()).Returns(@"C:\Models\TopAsm.sldasm");
        model.Setup(d => d.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(model.Object);
        swApp.Setup(s => s.FeatureManager).Returns(featureManager.Object);

        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.IsConnected).Returns(true);
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var result = new AssemblyService(manager.Object).TraverseAssemblyFeatureTrees();

        var nestedFeature = Assert.Single(result.Nodes.Where(node => node.FeatureName == "Boss-Extrude1"));
        Assert.Equal("SquareTube-1", nestedFeature.ComponentName);
        Assert.Equal(@"C:\Models\SquareTube.sldprt", nestedFeature.ComponentPath);
        Assert.Equal("SquareTube-1", nestedFeature.HierarchyPath);
    }

    [Fact]
    public void TraverseAssemblyFeatureTrees_ReadsLoadedChildDocumentFeaturesWhenUiNodeIsCollapsed()
    {
        var sketchFeature = new Mock<Feature>();
        sketchFeature.Setup(f => f.Name).Returns("草图1");
        sketchFeature.Setup(f => f.GetTypeName2()).Returns("ProfileFeature");
        sketchFeature.Setup(f => f.GetFirstSubFeature()).Returns((Feature)null!);
        sketchFeature.Setup(f => f.GetNextFeature()).Returns((Feature)null!);

        var partDocument = new Mock<IModelDoc2>();
        partDocument.Setup(d => d.GetTitle()).Returns("SquareTube.SLDPRT");
        partDocument.Setup(d => d.GetPathName()).Returns(@"C:\Models\SquareTube.sldprt");
        partDocument.Setup(d => d.FirstFeature()).Returns(sketchFeature.Object);

        var component = new Mock<Component2>();
        component.Setup(c => c.Name2).Returns("SquareTube-1");
        component.Setup(c => c.GetPathName()).Returns(@"C:\Models\SquareTube.sldprt");
        component.Setup(c => c.GetModelDoc2()).Returns(partDocument.Object);
        component.Setup(c => c.GetChildren()).Returns(Array.Empty<object>());

        var componentNode = new Mock<TreeControlItem>();
        componentNode.SetupGet(n => n.Text).Returns("SquareTube-1");
        componentNode.SetupGet(n => n.ObjectType).Returns(202);
        componentNode.SetupGet(n => n.Object).Returns(component.Object);
        componentNode.SetupGet(n => n.IsRoot).Returns(false);
        componentNode.SetupGet(n => n.Expanded).Returns(false);
        componentNode.Setup(n => n.GetFirstChild()).Returns((TreeControlItem)null!);
        componentNode.Setup(n => n.GetNext()).Returns((TreeControlItem)null!);

        var rootNode = new Mock<TreeControlItem>();
        rootNode.SetupGet(n => n.Text).Returns("TopAsm");
        rootNode.SetupGet(n => n.ObjectType).Returns(1);
        rootNode.SetupGet(n => n.Object).Returns((object?)null);
        rootNode.SetupGet(n => n.IsRoot).Returns(true);
        rootNode.SetupGet(n => n.Expanded).Returns(true);
        rootNode.Setup(n => n.GetFirstChild()).Returns(componentNode.Object);
        rootNode.Setup(n => n.GetNext()).Returns((TreeControlItem)null!);

        var featureManager = new Mock<IFeatureManager>();
        featureManager.Setup(fm => fm.GetFeatureTreeRootItem2(It.IsAny<int>())).Returns(rootNode.Object);

        var assembly = new Mock<IAssemblyDoc>();
        var model = assembly.As<IModelDoc2>();
        model.Setup(d => d.GetTitle()).Returns("TopAsm");
        model.Setup(d => d.GetPathName()).Returns(@"C:\Models\TopAsm.sldasm");
        model.Setup(d => d.GetType()).Returns((int)swDocumentTypes_e.swDocASSEMBLY);

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(model.Object);
        swApp.Setup(s => s.FeatureManager).Returns(featureManager.Object);

        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.IsConnected).Returns(true);
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var result = new AssemblyService(manager.Object).TraverseAssemblyFeatureTrees();

        var loadedSketch = Assert.Single(result.Nodes.Where(node => node.FeatureName == "草图1"));
        Assert.True(loadedSketch.IsSketch);
        Assert.Equal("SquareTube-1", loadedSketch.ComponentName);
        Assert.Equal(@"C:\Models\SquareTube.sldprt", loadedSketch.ComponentPath);
        Assert.Equal("SquareTube-1", loadedSketch.HierarchyPath);
        Assert.Equal("SquareTube.SLDPRT", loadedSketch.DocumentTitle);
    }

    [Fact]
    public void OpenComponentForEditing_RequiresConfirmedSingleAssemblyMatch()
    {
        var assembly = new Mock<IAssemblyDoc>();
        var model = assembly.As<IModelDoc2>();
        model.Setup(d => d.GetPathName()).Returns(@"C:\Models\TopAsm.sldasm");

        var component = new Mock<Component2>();
        component.Setup(c => c.Name2).Returns("SquareTube-1");
        component.Setup(c => c.GetPathName()).Returns(@"C:\Models\SquareTube.sldprt");
        component.Setup(c => c.GetChildren()).Returns(Array.Empty<object>());
        assembly.Setup(a => a.GetComponents(true)).Returns(new object[] { component.Object });

        var swApp = new Mock<ISldWorksApp>();
        swApp.Setup(s => s.IActiveDoc2).Returns(model.Object);
        swApp.Setup(s => s.ActivateDoc(@"C:\Models\SquareTube.sldprt"))
            .Returns(new SwDocumentInfo(@"C:\Models\SquareTube.sldprt", "SquareTube", (int)swDocumentTypes_e.swDocPART));

        var manager = new Mock<ISwConnectionManager>();
        manager.Setup(m => m.IsConnected).Returns(true);
        manager.Setup(m => m.SwApp).Returns(swApp.Object);
        manager.Setup(m => m.EnsureConnected());

        var result = new AssemblyService(manager.Object).OpenComponentForEditing(@"C:\Models\SquareTube.sldprt", "SquareTube-1");

        Assert.True(result.Opened);
        Assert.Equal("SquareTube-1", result.ComponentName);
        Assert.Equal(@"C:\Models\SquareTube.sldprt", result.ComponentPath);
        swApp.Verify(s => s.ActivateDoc(@"C:\Models\SquareTube.sldprt"), Times.Once);
    }
}
