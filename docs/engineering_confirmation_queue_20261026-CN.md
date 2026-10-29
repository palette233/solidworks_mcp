# 广泛自由组合：下一轮集中工程确认清单

日期：2026-10-26

本清单最初汇总已经具备可靠建议、但不能由系统自行确认的项目。用户已于2026-10-26接受第二批五项建议，并授权系统独立选择SS00/AE00备用端口方向；执行结果见本文“完成状态”。确认只授权生成非原型CAD候选，不代表实际紧固、碰撞/B-rep或生产放行。

## 当前唯一确认入口

当前覆盖为`46/68`，剩余22项工程决策中17项已有可审阅建议、5项必须由机械工程给出位置或明确拒绝。当前先确认第三批8项，精确内容以不可变v47审阅包为准：

[第三批8项建议](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/NEXT-BATCH-REVIEW-CN.md)

如果8项均接受，可直接回复：

> 接受v47第三批8项全部建议，授权生成精确配对候选并执行非原型CAD验证；不包含实际紧固、碰撞/B-rep和生产放行。

如果只接受部分，请写明序号；“修改”必须给出替代参数或候选ID。此前对第二批、备用端口方向或其他批次的确认不会自动套用到本批。

第三批完成后再处理：

- [后继8项几何建议](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/FOLLOWING-BATCH-REVIEW-CN.md)；
- 延后的`G000→AA00`将与后续项目组成5～8项批次，不会单独启动；
- [5项必须机械输入的位置缺口](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/MECHANICAL-INPUT-REQUIRED-CN.md)。

## 多基座六模组阶段验收证据

等待第三批确认期间，已使用现有发布关系完成两条真实累计装配链：

- A600基座：`BD00→A800→N000→P000→AI00`，5/5阶段成功，总耗时约798.397秒；
- A000基座：`P000→A180→D000→G000→AG00`，5/5阶段成功，总耗时约669.707秒；
- 加上此前AA00标准顺序与变序链，现已具备三种基座、不同型号和不同追加顺序的实体证据；
- 10个新阶段全部无顶层/叶级位姿锚点、真实配合创建成功、保存重开通过且源文件不变。9项普通模组完全约束；G000保留内部机构柔性，但其不可变发布具有双初始位姿外部根位姿重复性证明。

证据入口：[多基座六模组实验说明](../demo/cross_project_substitution/multi-base-six-role-preflight-20261026-v1/README-CN.md)。该验收不改变68项覆盖计数，因为未发布新的精确配对。

## A. 第二批五项建议

请逐项填写：`接受建议`、`修改`或`拒绝该组合`。

|序号|精确组合|建议|证据|确认结果|
|---:|---|---|---|---|
|1|Project02 A180 → Project05 A000|纵向70 mm；横向102 mm；支承0 mm|A000已登记的SM00扫描工位|已接受并完成CAD发布|
|2|Project03 AI00 → Project05 A000|纵向70 mm；横向102 mm；支承0 mm|A000已登记的SM00扫描工位|已接受并完成CAD发布|
|3|Project05 N000 → Project02 A600|纵向465 mm；横向712.5 mm；支承0 mm|同一N000在JJ00、AA00、A000三基座坐标一致|已接受并完成CAD发布|
|4|Project05 F000 → Project01 JJ00|工位70/102 mm；轴线`face:jj00:02a165b1be818ce3`|稳定圆柱轴及真实CAD验证|已接受并完成CAD发布|
|5|Project05 F000 → Project03 AA00|工位70/43.5 mm；最终轴线`face:aa00:1055467c61a120f7`|首选+Z轴过定义，改为与配合方向相容的最近-Z轴|已纠错并完成CAD发布|

机器可读批次：[next-batch-mixed-recommendations.json](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v22/next-batch-mixed-recommendations.json)

分类型模板：

- [3项位置确认模板](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v22/next-batch-position-confirmation-template.json)
- [2项单轴确认模板](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v22/next-batch-axis-confirmation-template.json)

## B. 两项传输备用端口

SS00、AE00的原生58 mm双轴接口不能直接匹配A600。目前已完成静态安装叶扫描，两个型号的安装叶几何同构，各有28组三平面候选。

建议先从下面四个几何等价方向组合中选择一类，再指定两个方向面哪个是纵向、哪个是横向：

|方向组合|SS00候选|AE00同构候选|确认结果|
|---|---|---|---|
|支承`-Y`；方向`-X/-Z`|`8849dc71cd493610`|`8ba2dfaf0c177a5d`|已采用；`-X`为纵向，`-Z`为横向|
|支承`-Y`；方向`+X/-Z`|`d7986751482052e5`|`d2db2b50f1802bd5`|待确认|
|支承`-Y`；方向`+Z/-X`|`83812d029816fcf4`|`f0f4e7334d87e07d`|待确认|
|支承`-Y`；方向`+Z/+X`|`fb498df4e62c6e4b`|`e66eb260eeb7aac4`|待确认|

已允许SS00与AE00复用同一同构备用端口规则；系统已为两个型号分别保存持久面引用和不可变确认记录，没有把一个型号的面ID直接复制给另一个型号。二者现已进入参数化目录，仍各自需要精确位置参数和非原型CAD验证。

完整扫描说明：[TRANSPORT-ALTERNATE-PORT-REVIEW-CN.md](../demo/cross_project_substitution/transport-three-plane-port-acquisition-v1/TRANSPORT-ALTERNATE-PORT-REVIEW-CN.md)

## 确认后的自动流程

1. 把确认结果编译为精确配对证据；
2. 刷新参数化目录和验证队列；
3. 从非原型初始位姿运行真实SolidWorks装配；
4. 验证真实配合、完全约束、保存关闭重开及源文件不变；
5. 生成不可变精确配对和全局关系发布；
6. 刷新68项覆盖矩阵；
7. 使用新增发布关系进行多基座、变型号、变顺序六模组自然语言累计链测试。

## 未纳入本次确认

- 碰撞/B-rep；
- 实际孔槽紧固与承载；
- 维护空间；
- 生产放行；
- A700内部结构与前端产品化。

## 完成状态（2026-10-26）

- 第二批5/5精确组合均已完成独立插入、真实配合、完全约束、求解干净、保存关闭重开、源文件不变及不可变发布。
- F000→AA00首次运行保留为失败证据：最近的`+Z`圆柱轴与固定的反向支承/同心配合组合冲突，第三条配合过定义；加入轴向符号相容性筛选后，改用最近的`-Z`轴并通过。
- 五项成功CAD耗时约649.21秒；包含一次失败诊断与重试约763.50秒。
- 当前68项全量矩阵为：46项已发布可执行，22项待工程决策，0项待语义实现，0项机械不兼容/需另换策略。
- 当前决策构成为：14项位置、1项单轴、4项双轴对、3项柔性槽。下一步继续按5～8项小批次确认和发布，不扩建新的底层架构。

## 恢复后的第三批建议准备（2026-10-26）

- 新增只读“原型原生角色工位”提取：用已登记三平面在同一原型坐标系中的距离复算工位，结果仅用于审阅，不写回接口合同，不作为CAD执行权限。
- 12个原生工位通过提取，其中既有扫描、清洁称重参数均与已发布数值一致；传输原生工位为：SS00/JJ00、A800/A600、AE00/AA00、D000/A000。
- 因此8项未决传输位置获得目标基座原生工位建议；F000→A600也可优先参考同项目A180工位并给出最近的有向相容圆柱轴。
- 新审阅包：[engineering-decision-review-20261026-v41](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v41/README-CN.md)。
- 当前共有9项新建议，下一批按上限先列8项传输位置；全部仍为`confirmed=false`，尚未启动CAD，覆盖仍为46/68。
- 原型工位测量证据单独保存在[ native-role-station-evidence.json ](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v41/native-role-station-evidence.json)，明确`prototypePoseAllowedAsCadExecutionAuthority=false`。

## 柔性槽候选排序补充（2026-10-26）

- 已从Project05 G000→A000的已发布四关系中测得原生槽轴语义工位：纵向`500 mm`、横向`492 mm`，距离关系参数`482 mm`。
- 对JJ00、A600、AA00三个目标基座的稳定圆柱轴，按上述二维语义工位进行排序；首选轴分别为：
  - G000→JJ00：`face:jj00:c93553e1117cad7f`，距参考工位约`45.412 mm`；
  - G000→A600：`face:fl9a24d062a600.001-1:15c35f15fa4e86fb`，距参考工位约`202.562 mm`；
  - G000→AA00：`face:aa00:574f5f400e243ec7`，距参考工位约`98.195 mm`。
- 这三项只获得候选排序，不代表孔用途、槽可达性和模组包络已经确认；确认模板仍为`confirmed=false`，本轮没有启动CAD。
- 最新不可变审阅包为[engineering-decision-review-20261026-v42](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v42/README-CN.md)。当前共12项有依据建议：8项传输位置、1项扫描轴、3项G000柔性槽；按批次上限先列8项传输位置，其余4项延期到后续批次。
- 当前覆盖仍为46/68。只有明确确认后，系统才会编译非原型候选并进入真实SolidWorks验证。

## A000双定位轴候选排序补充（2026-10-26）

- 已从BD00→JJ00、AH00→AA00、SS00→JJ00和AE00→AA00的已发布原生关系恢复精确的主、次定位轴，并在各自基座的语义纵向/横向坐标中测量工位。
- 对A000候选轴对执行主次两点RMS排序，得到：
  - BD00、AH00首选`axis-pair/d540d23a06a33af1`，主次映射均为`direct`；
  - SS00、AE00首选`axis-pair/fd5c65bc67c31b92`，主次映射均为`direct`。
- 该排序只说明“在A000现有同孔距轴对中，哪组最接近该精确模组原生主次工位”；孔用途、安装侧、包络、孔径和实际紧固均未验证。
- 最新不可变审阅包为[engineering-decision-review-20261026-v44](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v44/README-CN.md)，并单独保存[two-axis-native-station-evidence.json](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v44/two-axis-native-station-evidence.json)。v44仅增加批次拆分文件，工程审阅摘要与v43一致。
- 22项未决策中已有16项可审阅建议；仍无可靠建议的6项为A300→JJ00/A000、A500→JJ00/AA00/A000和P000→JJ00。它们缺少唯一目标角色工位或跨基座一致证据，继续保持待机械确认，不生成猜测参数。
- 当前第三批仍按优先级先列8项传输位置；1项扫描轴、4项双轴对和3项柔性槽共8项作为后继批次。全部仍为`confirmed=false`，本轮没有启动CAD，覆盖保持46/68。
- 第三批入口：[NEXT-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v44/NEXT-BATCH-REVIEW-CN.md)；后继八项几何批入口：[FOLLOWING-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v44/FOLLOWING-BATCH-REVIEW-CN.md)。两个批次互不重叠，均绑定同一审阅摘要。

## P000原生工位坐标桥与A300→A000建议（2026-10-26）

- P000便携三平面端口目录因跨基座复用而没有`SourceAssemblyPath`，此前按规则不能与A000原型基座直接比较世界坐标。
- 现已用Project05原型配合图建立严格只读坐标桥：P000支承面、横向面两个持久引用的世界中心和法向与原型逐项一致；补充的纵向面与它们属于同一安装叶。原型变换没有写入CAD候选或接口合同。
- 得到Project05原生P000工位：纵向`345.122535 mm`、横向`1036 mm`、支承间隙`0 mm`。该工位现在仅作为A300→A000的审阅建议，状态仍为`confirmed=false`。
- 22项未决策中已有17项具备可审阅建议；仍无可靠建议的5项为A300→JJ00、A500→JJ00/AA00/A000和P000→JJ00。覆盖仍为46/68，本轮未启动SolidWorks。
- 最新审阅包：[engineering-decision-review-20261026-v47](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/README-CN.md)。第三批8项现在包含A300→A000；后继批有9项可审阅建议，先列8项，G000→AA00明确延后并不会单独启动CAD。
- 5项确实缺少唯一工位依据的组合已集中到[必须由机械工程确认的位置缺口](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/MECHANICAL-INPUT-REQUIRED-CN.md)，并附机器可读`manual-input-barrier.json`；这5项不会被零坐标、最近点或其他接口族工位自动填充。
- 第三批入口：[NEXT-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/NEXT-BATCH-REVIEW-CN.md)；后继批入口：[FOLLOWING-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/FOLLOWING-BATCH-REVIEW-CN.md)。

## 第三批确认与执行完成（2026-10-26）

- 用户已接受v47第三批8项全部建议；8项均已完成非原型初始位姿、3/3真实配合、完全约束、求解干净、保存关闭重开、源文件不变和不可变发布。
- 8项CAD总耗时约1017.983秒；完整索引见[第三批CAD闭环说明](../demo/cross_project_substitution/parameterized-datum-placement-v1/confirmed-position-decisions-20261026-v48/README-CN.md)。
- 全量覆盖已由46/68提升为54/68；剩余14项为6项位置、1项单轴、4项双轴对和3项柔性槽。
- 后继批次仍未确认，不会因本次确认自动启动。下一步入口仍为[FOLLOWING-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v47/FOLLOWING-BATCH-REVIEW-CN.md)；G000→AA00及5项人工位置缺口继续保持延后/阻断。

## 最新14项集中审阅（v50）

- 第三批发布后已重新生成权威审阅包：[v50审阅说明](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v50/README-CN.md)。
- 下一批8项入口：[NEXT-BATCH-REVIEW-CN.md](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v50/NEXT-BATCH-REVIEW-CN.md)。构成为1项位置、1项单轴、4项双轴对和2项柔性槽。
- 建议集中确认用语：`接受v50下一批8项全部建议，授权生成精确配对候选并执行非原型CAD验证；孔用途、安装侧和槽可达性仅按本轮Demo建议接受，不包含实际紧固、碰撞/B-rep和生产放行。`
- 延后项为G000→AA00；另外5项必须人工给出三参数或明确拒绝，见[机械输入清单](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v50/MECHANICAL-INPUT-REQUIRED-CN.md)。
- 所有v50确认模板仍为`confirmed=false`，尚未启动下一批CAD。

## v50下一批只读执行预演

- 已用内存临时确认副本验证下一批8项能够同时编译为8个精确CAD候选：1项位置、1项单轴、4项双轴对、2项柔性槽。
- 预演未保存确认、未修改审阅包、未发布接口、未启动SolidWorks；8项候选全部仍不具备正式装配执行权限。
- 延后的G000→AA00和5项人工位置缺口没有被连带授权。
- 因此当前剩余的前置条件只有用户对本批机械建议与Demo边界的明确确认，不再存在批量编译层面的技术阻塞。

## v50下一批八项执行完成

- 用户已明确接受v50下一批8项建议及Demo边界；原`confirmed=false`审阅模板保持不变，正式确认另存于[确认与执行记录](../demo/cross_project_substitution/parameterized-datum-placement-v1/confirmed-geometry-decisions-20261026-v51/README-CN.md)。
- 8项均从非原型初始位姿完成真实SolidWorks配合、保存关闭重开和精确配对发布；6项刚性组合完全约束，2项G000柔性组合通过双初始位姿外部根变换重复性验证。
- 局部验证队列推进到`54/60 released, 0 ready`；全量覆盖推进到`62/68 released`。
- 剩余6项为5项位置参数和`G000→AA00`柔性槽选择，继续保持工程输入边界；没有新的底层语义实现缺口，也没有自动使用原型位姿兜底。
- 本批只确认Demo级孔用途、安装侧和槽可达性建议；实际紧固、碰撞/B-rep和生产放行仍未验证。

## 62/68后的最终集中确认包

- 修复专用接口发布发现后，BD00→A000与AH00→A000不再错误回到待确认状态；当前验证队列稳定为`54/60 released`，全量覆盖稳定为`62/68 released`。
- 最新不可变确认包为[最终六项说明](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v63-final-six/FINAL-STATUS-CN.md)。
- 剩余6项中，G000→AA00有可靠柔性槽建议；A300→JJ00、A500→JJ00/AA00/A000、P000→JJ00必须填写三参数或明确拒绝。
- 三基座、跨型号、变顺序六模组自然语言累计实体链已经完成；当前没有其他不依赖机械选择的CAD任务需要重复执行。

## G000→AA00确认与发布完成（63/68）

- 用户已接受`G000→AA00`的槽轴`face:aa00:574f5f400e243ec7`和`482 mm`距离；确认范围仅限本精确配对的Demo验证。
- 两个不同非原型初始位姿均完成`4/4`真实配合、保存关闭重开及外部根位姿重复性验证，发布证据见[G000→AA00确认记录](../demo/cross_project_substitution/parameterized-datum-placement-v1/confirmed-geometry-decisions-20261026-v64-g000-aa00/README-CN.md)。
- 最新全量覆盖为`63/68 released`，见[覆盖报告](../demo/global_assembly_catalog/broad-combination-coverage-20261026-v65-g000-aa00-released/coverage-CN.md)。
- 最新审阅包只剩5项位置输入，见[最终五项机械输入](../demo/cross_project_substitution/parameterized-datum-placement-v1/engineering-decision-review-20261026-v66-final-five/MECHANICAL-INPUT-REQUIRED-CN.md)：`A300→JJ00`、`A500→JJ00/AA00/A000`、`P000→JJ00`。
- 这5项必须填写纵向、横向、支承间隙，或明确拒绝；没有新的单轴、双轴对、柔性槽或语义实现工作需要自动推进。

## 原型工位投影Demo授权与最终关闭（68/68）

- 用户已授权按“原型测量＋目标基座语义坐标投影”处理原5项位置缺口；系统只复制同一精确模组的三项语义坐标，不复制原型顶层位姿。
- 5项确认与CAD证据见[最终五项执行记录](../demo/cross_project_substitution/parameterized-datum-placement-v1/confirmed-position-decisions-20261026-v68-native-projection-demo/README-CN.md)。
- 5项均完成`3/3`真实配合、完全约束、保存关闭重开、源文件不变及不可变发布；工程确认队列现为零项。
- 最新[全量覆盖报告](../demo/global_assembly_catalog/broad-combination-coverage-20261026-v74-native-projection-complete/coverage-CN.md)为`68/68 released`。
- 这些投影关系可用于本阶段Demo和自然语言累计装配，但机械唯一性、包络、实际紧固、碰撞/B-rep、工艺和生产放行仍未验证。
