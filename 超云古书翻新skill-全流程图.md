# 超云古书翻新 skill 全流程图

> 依据：`C:\Users\QIQI\.codex\skills\chaoyun-ancient-book-renovator` 的 `SKILL.md`、`references/*.md`、`scripts/init_workspace.py`、`scripts/validate_workspace.py`，以及 8 个子 skill 的 `SKILL.md` 与其 references（workflow 1.10）。
> 用途：指导 skill 优化。第 17 节列出梳理时发现的不一致与可优化点。

## 目录

1. [总体架构：两层模型与子 skill 分工](#1-总体架构两层模型与子-skill-分工)
2. [主流程（SKILL.md 第 1–13 步）](#2-主流程skillmd-第-113-步)
3. [阶段状态机（run-state.json）](#3-阶段状态机run-statejson)
4. [交付模式选择与版本范围锁定](#4-交付模式选择与版本范围锁定)
5. [接收与诊断（G0 / G1）](#5-接收与诊断g0--g1)
6. [原貌重建（G2）](#6-原貌重建g2)
7. [疑点裁决生命周期（G2.5，贯穿全程）](#7-疑点裁决生命周期g25贯穿全程)
8. [文本规范化（G3）](#8-文本规范化g3)
9. [普通读者版生产链（G4 前置 + 1.8/1.10）](#9-普通读者版生产链g4-前置--18110)
10. [阅读单元（workflow 1.10）](#10-阅读单元workflow-110)
11. [真实阅读会话（样章 / 全书）](#11-真实阅读会话样章--全书)
12. [全书读者审编与终稿裁剪（G5 / G5.5）](#12-全书读者审编与终稿裁剪g5--g55)
13. [冻结、忠实度复核与出版（G6）](#13-冻结忠实度复核与出版g6)
14. [质量闸门与完成等级](#14-质量闸门与完成等级)
15. [返工影响路由](#15-返工影响路由)
16. [停止规则与预算控制](#16-停止规则与预算控制)
17. [工作区产物数据流](#17-工作区产物数据流)
18. [优化观察点](#18-优化观察点)

---

## 1. 总体架构：两层模型与子 skill 分工

```mermaid
flowchart LR
    PDF[("源 PDF<br/>只读保留")]

    subgraph EVID["证据层 Evidence layer"]
        direction TB
        E1["页面图像"]
        E2["版面坐标 bbox"]
        E3["忠实原文 source_text"]
        E4["疑点账本"]
        E5["出处 / 审计事件"]
    end

    subgraph READ["阅读层 Reading layer"]
        direction TB
        R1["规范化文本"]
        R2["现代白话"]
        R3["编者添加内容<br/>导言 / 术语 / 图解"]
        R4["Markdown"]
        R5["PDF"]
    end

    PDF --> EVID
    EVID -- "每个阅读块必须回指稳定 block_id" --> READ
    READ -. "禁止覆盖 / 替代" .-x EVID
```

```mermaid
flowchart TB
    CTRL["总控 chaoyun-ancient-book-renovator<br/>超云古书翻新"]

    D["chaoyun-pdf-diagnoser<br/>超云文档慧检"]
    S["chaoyun-source-reconstructor<br/>超云原貌重建"]
    U["chaoyun-uncertainty-adjudicator<br/>超云古书疑点裁决"]
    N["chaoyun-text-normalizer<br/>超云古字通"]
    M["chaoyun-classical-modernizer<br/>超云古文今译"]
    E["chaoyun-reading-editor<br/>超云今读编辑"]
    R["chaoyun-reader-experience-reviser<br/>超云全书读者审编"]
    P["chaoyun-quality-publisher<br/>超云品质出版"]

    CTRL --> D --> S --> N --> M --> E --> R --> P
    CTRL -.-> U
    U <-. "每个检查点" .-> S
    U <-.-> N
    U <-.-> M
    U <-.-> E
    U <-.-> R
    U <-.-> P

    M <-- "理解简报 / 术语含义" --> E
    E <-- "样章 / 过程稿" --> R
    S -- "注释归属 / 续页证据" --> E
```

| 子 skill | 模式 | 主要产物 |
|---|---|---|
| pdf-diagnoser | — | `10-diagnosis/profile.json`、`page-map.jsonl` |
| source-reconstructor | — | `20-source/blocks.jsonl`、`source.md`、`pages/` |
| uncertainty-adjudicator | 任意检查点 / `--pilot` / `--check --publication` | 三份疑点账本、`pilot-review.json`、`uncertainty-release-review.json` |
| text-normalizer | — | `30-normalized/blocks.jsonl`、`normalized.md`、`changes.jsonl` |
| classical-modernizer | understanding / sample / full | `book-understanding.md`、`40-modernized/*`、`terminology.json` |
| reading-editor | design / sample / full-edition | `editorial-plan.md`、`reader-units.json`、`modern-reading.md`、`reader-aids.json`、`source-reader-map.jsonl` |
| reader-experience-reviser | sample / manuscript / final-reader / proof | `reader-review.json`、`reader-revision-ledger.jsonl`、`reader-acceptance-report.json` |
| quality-publisher | — | 候选 PDF、`release-binding.json`、`pdf-reader-review.json`、`quality-report.json`、正式 PDF |

---

## 2. 主流程（SKILL.md 第 1–13 步）

```mermaid
flowchart TD
    S1["① 明确输入<br/>PDF、输出根目录、交付模式、目标读者<br/>今译深度、是否授权付费调用<br/>记录物理页数并逐页分类"]
    S2["② init_workspace.py<br/>建立独立工作区<br/>book.json / run-state.json"]
    S3["③ pdf-diagnoser<br/>书籍档案 + 逐页路线图"]
    S3b["代表章节试点<br/>重建→今译→编辑→疑点闭环<br/>pilot-review.json"]
    G3P{"project_open_items.py --pilot<br/>通过?"}
    S4["④ source-reconstructor<br/>忠实原文 + 页 / 块记录"]
    G4{"validate_workspace.py<br/>--stage source 通过?"}
    S5["⑤ uncertainty-adjudicator<br/>原文重建检查点"]
    S6["⑥ text-normalizer<br/>字形、异体、标点、分段<br/>不得意译"]
    MODE{"delivery_mode =<br/>ordinary_reader?"}
    S7["⑦ 理解 → 设计 → 阅读单元<br/>→ 样章 → 独立样章审读"]
    G7{"validate_production_plan.py<br/>+ validate_reader_units.py<br/>通过?"}
    S8["⑧ 全书今译 + 全书编辑<br/>保存不可变过程稿"]
    S9["⑨ reader-experience-reviser<br/>全书审读 → 修订 → 终稿裁剪<br/>≥3 轮完整通读、末 2 轮稳定"]
    S10["⑩ uncertainty-adjudicator<br/>各检查点 + 发布前全量复核<br/>--check --publication"]
    S11["⑪ lock_acceptance_policy.py<br/>冻结稿件 → 忠实度复核<br/>→ 候选 PDF → 双闸门 → 安装器"]
    S12["⑫ validate_workspace.py<br/>--stage publication"]
    S13["⑬ 报告<br/>等级、页数核对、疑点数字、修订次数<br/>唯一正式发布路径"]
    STOP(["停止并记录阻塞原因"])

    S1 --> S2 --> S3 --> S3b --> G3P
    G3P -- 否 --> S3b
    G3P -- 是 --> S4 --> G4
    G4 -- 否 --> S4
    G4 -- 是 --> S5 --> S6 --> MODE
    MODE -- 是 --> S7 --> G7
    G7 -- 否：方法问题 --> S7
    G7 -- 是 --> S8
    MODE -- "否：对照版 / 证据档案" --> S8
    S8 --> S9
    S9 -- "系统性失败" --> S7
    S9 --> S10 --> S11 --> S12
    S12 -- 否 --> RW["按第 15 节返工"]
    S12 -- 是 --> S13

    S3 -. "损坏 / 加密 / 缺页 / 预算耗尽" .-> STOP
    S4 -. "阅读顺序严重不明" .-> STOP
    S9 -. "同一阻塞连续 2 轮无进展" .-> STOP
```

---

## 3. 阶段状态机（run-state.json）

`init_workspace.py` 中定义的 14 个阶段。灰色 4 个只在 `ordinary_reader` 模式下创建。

```mermaid
stateDiagram-v2
    direction LR
    [*] --> intake
    intake --> diagnosis
    diagnosis --> source
    source --> source_adjudicated
    source_adjudicated --> normalized

    state ordinary_reader_only {
        direction LR
        book_understood --> reader_designed
        reader_designed --> reader_units_built
        reader_units_built --> sample_accepted
    }

    normalized --> book_understood: ordinary_reader
    normalized --> modernized: 对照版 / 档案版
    sample_accepted --> modernized
    modernized --> edited
    edited --> reader_revised
    reader_revised --> final_adjudicated
    final_adjudicated --> publication
    publication --> [*]
```

每个阶段的状态值与流转规则：

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running
    running --> passed
    running --> passed_with_ledger
    running --> blocked
    running --> failed
    blocked --> running: 追加审计事件说明解决方式
    failed --> running: 追加审计事件说明解决方式
    passed --> [*]
    passed_with_ledger --> [*]

    note right of passed_with_ledger
        后一阶段只能在前一阶段
        passed 或 passed_with_ledger 后开始
        run-state 只是摘要，不能作为证据
    end note
```

---

## 4. 交付模式选择与版本范围锁定

```mermaid
flowchart TD
    Q{"用户要什么?"}
    Q -- "普通人可以直接阅读" --> OR["ordinary_reader<br/>普通读者现代版"]
    Q -- "原文与译文对照" --> SC["source_comparison<br/>对照版"]
    Q -- "忠实还原 / 研究用" --> EA["evidence_archive<br/>证据档案版"]
    Q -- "未声明" --> ERR["错误：缺少模式不是豁免"]

    OR & SC & EA --> BOOK["写入 book.json<br/>delivery_mode、target_reader<br/>edition_label、release_filename"]
    BOOK --> NOTE["显示名称不决定闸门<br/>只有 delivery_mode 决定"]

    OR --> SCOPE["10-diagnosis/edition-scope.json<br/>清点：正文 / 注疏 / 序言 / 图 / 表 / 附属文字"]
    SCOPE --> EX{"要排除某一组件?"}
    EX -- 否 --> KEEP["正文、注疏、序言<br/>必须进入读者版"]
    EX -- 是 --> AUTH{"用户明确授权?"}
    AUTH -- "是：记录原话与时间" --> OKX["允许具名排除"]
    AUTH -- 否 --> DENY["禁止：不能把难处理部分<br/>改称“仅过程”或“补充材料”来过关"]
```

---

## 5. 接收与诊断（G0 / G1）

```mermaid
flowchart TD
    A["源 PDF"] --> A1["记录 SHA-256、字节数、页数、文件名"]
    A1 --> A2{"加密 / 损坏?"}
    A2 -- 是 --> STOP(["停止"])
    A2 -- 否 --> A3["Windows：非 ASCII 路径<br/>复制到 ASCII 路径并校验哈希"]
    A3 --> A4["逐页分类：<br/>digital / scan / mixed / image_only / damaged / unsupported"]
    A4 --> A5["逐页处置：<br/>收录 / 前后附属 / 空白非内容<br/>排除并说明原因 / 无法识读"]
    A5 --> G0{"G0：各类页数之和<br/>= 物理页数?"}
    G0 -- 否 --> A5
    G0 -- 是 --> B1["识别版面家族<br/>横 / 竖排、单 / 多栏、双行小注<br/>眉批、表格、图、印章、公式、手写"]
    B1 --> B2["块 / 区域级语言识别<br/>zh-Hans / zh-Hant / lzh / ja / ja-bungo / kanbun / mixed / und"]
    B2 --> B3["按 routing.md 选择路线"]
    B3 --> B4["代表样本集<br/>开头 / 中段 / 结尾 / 最密页 / 图多页<br/>最小注文 / 最差扫描 / 每个语言版面家族"]
    B4 --> B5["在样本上试跑路线"]
    B5 --> G1{"G1：每页有路线<br/>每个家族有已测样本<br/>风险已登记<br/>edition-scope 已锁定?"}
    G1 -- 否 --> B3
    G1 -- 是 --> OUT["profile.json + page-map.jsonl<br/>样本只证明路线，不证明全书质量"]
```

```mermaid
flowchart LR
    R{"页面特征"}
    R --> R1["可靠文字层"] --> X1["抽取文字 + 版面恢复<br/>核对字形与阅读顺序"]
    R --> R2["清晰扫描"] --> X2["版面感知 OCR<br/>抽检竖排、小注、表格、页边"]
    R --> R3["数字 + 扫描混合"] --> X3["逐页混合路线<br/>检出空白 / 乱码文字层"]
    R --> R4["竖排文言"] --> X4["竖排 OCR + lzh 今译<br/>检查列序与注释归属"]
    R --> R5["日文 / 汉文训读"] --> X5["日文 OCR + 语言切分<br/>区分日语语法与文言"]
    R --> R6["密集注 / 双行小注"] --> X6["区域 / 列重建<br/>检查注的锚点"]
    R --> R7["表格 / 图 / 印章 / 公式"] --> X7["保留图像 + 可靠时结构化<br/>不虚构单元格"]
    R --> R8["模糊 / 透印 / 破损"] --> X8["图像增强多版本比对<br/>进疑点账本，不按语义猜"]
    R --> R9["手写 / 草书"] --> X9["专门识别或人工辅助<br/>未独立核验默认 C 级"]
```

---

## 6. 原貌重建（G2）

```mermaid
flowchart TD
    I["profile.json + page-map.jsonl"] --> C0{"有诊断结果?"}
    C0 -- 否 --> DIAG["先诊断"]
    C0 -- 是 --> C1["按足够分辨率渲染 / 保留页面图像<br/>原书页码与逻辑页码分开"]
    C1 --> C2["按页路线抽取或 OCR<br/>坐标、块类型、语言提示、阅读顺序"]
    C2 --> C3["重建标题、正文、注、图注、表、图、跨页段落"]
    C3 --> C4["分配稳定 ID<br/>page_id = P000123<br/>block_id = P000123-B007<br/>component_id、structural_role、bbox、reading_order"]
    C4 --> C5["先写 blocks.jsonl，再生成 source.md"]
    C5 --> C6["对照页面图像核对代表页和高风险页"]
    C6 --> C7["可疑字形 / 阅读顺序 / 破损区域<br/>登记为疑点候选"]
    C7 --> C8["1.10：给出注释对象与跨页续接证据<br/>篇注 / 章注与句注分开识别"]
    C8 --> V["validate_workspace.py --stage source"]
    V --> G2{"G2：页 / 块全覆盖<br/>阅读顺序有依据<br/>无 p000 占位 ID<br/>有注页面没被合成一个 body 块?"}
    G2 -- 否 --> C2
    G2 -- 是 --> ADJ["进入疑点裁决（第 7 节）"]

    classDef hard fill:#fde2e2,stroke:#c00
    HB["硬边界：<br/>保留原字、原误、旧字形<br/>不按语义补字<br/>不把眉批并入正文<br/>表格无法核实就保留图像<br/>页眉页码确认重复规律后才能删"]:::hard
    C3 -.-> HB
```

---

## 7. 疑点裁决生命周期（G2.5，贯穿全程）

同一套账本贯穿所有阶段，只用 `review_cycle` / `checkpoint` 区分轮次。不设“一疑、二疑、终疑”三份文件。

```mermaid
flowchart TD
    DIS["发现<br/>OCR / 视觉 / 翻译 / 规则 / 审读 / 校样"] --> REG["编辑前登记<br/>uncertainty-candidates.jsonl（schema 1.3）<br/>origin_stage、review_cycle、checkpoint<br/>input_ref = 冻结材料的精确定位"]
    REG --> OWN{"指派责任阶段 owner_stage"}
    OWN -- "字形 / 顺序" --> O1["source"]
    OWN -- "字体 / 标点" --> O2["normalized"]
    OWN -- "含义" --> O3["modernized"]
    OWN -- "解释 / 可读性" --> O4["edited / reader_revised"]
    OWN -- "渲染" --> O5["publication"]
    O1 & O2 & O3 & O4 & O5 --> GRP["按页面区域 / 短语分组<br/>保留每个 candidate_id"]
    GRP --> EVI["取证<br/>源图、版面、相邻页、其他识别结果<br/>异体字 / 术语依据<br/>通顺不等于证据"]
    EVI --> DEC{"判定唯一状态"}
    DEC --> D1["resolved_confirmed<br/>有可见或文献依据"]
    DEC --> D2["resolved_noncontent<br/>印章 / 页眉 / 透印"]
    DEC --> D3["resolved_structural<br/>跨页续接 / 顺序 / 图注关系"]
    DEC --> D4["resolved_duplicate<br/>duplicate_of 指向已关闭的主候选"]
    DEC --> D5["open_material<br/>仍无唯一读法或确实缺文"]
    D1 & D2 & D3 & D4 & D5 --> IMP["标 reader_impact<br/>none / low / medium / high"]
    IMP --> FIX{"需要改文字?"}
    FIX -- "是（仅 confirmed）" --> CHG["执行修改<br/>closure.change：input / output / current<br/>offset + before / after 可精确回放"]
    FIX -- 否 --> SIX
    CHG --> SIX["六范围影响复核<br/>source / translation / terminology<br/>reader_text / figures / publication<br/>checked 需附定位证据"]
    SIX --> REV["独立审核执行<br/>review_record：不同 run_id<br/>fidelity_evidence + reader_evidence<br/>closure_sha256 双步绑定"]
    REV --> CL{"关闭还是保留?"}
    CL -- 关闭 --> CLOSED["resolved_* 生效"]
    CL -- 保留 --> OPEN["open_material 生效<br/>稳定 issue_id"]
    CLOSED & OPEN --> PROJ["重新生成投影<br/>uncertain-items.jsonl<br/>只收 open_material"]
    PROJ --> CHK["project_open_items.py --check"]

    CLOSED -. "新证据矛盾 / 依赖变化" .-> REOPEN["追加新裁决 supersedes<br/>旧记录 active:false<br/>沿用原 issue_id"]
    REOPEN --> EVI
```

```mermaid
flowchart LR
    subgraph T["试点：扩大到全书之前"]
        T1["冻结代表章节读者初稿"] --> T2["完整疑点闭环"]
        T2 --> T3["独立审核<br/>expected_answers_withheld: true"]
        T3 --> T4["记录已核实 / 残留 / 新引入错误<br/>耗时、成本"]
        T4 --> T5["pilot-review.json<br/>--pilot 闸门"]
    end
    subgraph F["发布前：终稿全量复核"]
        F1["冻结终稿"] --> F2["逐条复核全部 active 裁决<br/>closed → verified<br/>open → disclosed_unresolved + 终稿引文"]
        F2 --> F3["uncertainty-release-review.json<br/>独立审核记录 + final_review_sha256"]
        F3 --> F4["--check --publication"]
    end
    T5 --> F1
    F4 --> GR{"等级判定"}
    GR -- "无 active material" --> A["可评 A"]
    GR -- "只有 low / medium 且已披露" --> B["可评 B"]
    GR -- "有 high 或证据失败" --> C["C 及以下，阻止发布"]
```

三份账本的关系：

```mermaid
flowchart LR
    C1["uncertainty-candidates.jsonl<br/>全部原始候选，永久保存"] --> A1["uncertainty-adjudication.jsonl<br/>裁决历史，只追加<br/>每个候选恰有一个 active 裁决"]
    A1 -- "只投影 active open_material" --> U1["uncertain-items.jsonl<br/>面向读者的当前未决项<br/>原子重新生成"]
    LEG["旧工作区"] -- "migrate_legacy_ledger.py<br/>先备份；旧关闭一律重开" --> C1
```

---

## 8. 文本规范化（G3）

```mermaid
flowchart TD
    I["20-source/blocks.jsonl"] --> N1["保留每个 block_id 与 source_text"]
    N1 --> N2["声明目标字体，通常为简体<br/>专名 / 术语按项目术语表处理"]
    N2 --> OPS["分开执行、分开记录"]
    OPS --> O1["繁简转换"]
    OPS --> O2["已核实异体字映射"]
    OPS --> O3["标点"]
    OPS --> O4["空白规范"]
    OPS --> O5["保守分段"]
    O1 & O2 & O3 & O4 & O5 --> STRICT["从严复核：人名、日期、数量<br/>引文、公式、书名、罕见术语"]
    STRICT --> OUT["30-normalized/blocks.jsonl<br/>normalized.md<br/>changes.jsonl（每处实质改动一条）"]
    OUT --> G3{"G3：块身份和覆盖与原文一致<br/>改动全部入账<br/>没有意译?"}
    G3 -- 否 --> N1
    G3 -- 是 --> NEXT["进入今译 / 读者生产"]

    BAN["禁止：文言翻白话（属今译）<br/>日文汉字走中文词典<br/>静默把原误改成预期词"]
    OPS -.-> BAN
```

---

## 9. 普通读者版生产链（G4 前置 + 1.8/1.10）

```mermaid
flowchart TD
    NORM["normalized 已通过"] --> U1

    subgraph PRE["批量翻译前的前置阶段"]
        U1["① modernizer / 理解模式<br/>通读全部可靠原文<br/>book-understanding.md<br/>核心问题、主张 + block ID、章节关系<br/>概念依赖、实例、未定含义"]
        U1 --> UB{"核心含义有缺口?"}
        UB -- 是 --> BLK["阻止批量工作<br/>次要疑点进统一账本"]
        UB -- 否 --> U2["② reading-editor / 设计模式<br/>editorial-plan.md<br/>导言叙事、章节衔接、先修与首释顺序<br/>实例、看图路线、查阅材料<br/>起草 delivery-contract.json（pending）"]
        U2 --> U3["②' 建立阅读单元 reader-units.json<br/>原貌重建确认依据<br/>validate_reader_units.py<br/>reader_units_built = passed"]
        U3 --> U4["③ modernizer + editor / 样章<br/>挑一段有代表性的难段<br/>reader-sample.md<br/>含导言、连贯正文、代表概念、内容图"]
        U4 --> U5["④ reader-experience-reviser / 样章模式<br/>新的独立读者，不给答案<br/>测主旨、应用、区分、看图"]
        U5 --> UG{"样章通过?"}
        UG -- "否：方法问题" --> U2
        UG -- "否：理解问题" --> U1
        UG -- 是 --> PP["production-plan.json<br/>bindings 哈希 + sample_selection<br/>blocking_questions = 空<br/>validate_production_plan.py"]
    end

    PP --> F5["⑤ 全书过程稿<br/>译者负责含义，编辑负责解释与顺序<br/>含义变化时更新依赖<br/>保存为不可变过程稿"]
    F5 --> F6["⑥ reviser / 全书审读<br/>按有意义的单元审读，保留回答<br/>局部修正 + 全书语境回归"]
    F6 -- "系统性失败" --> U1
    F6 --> F7["⑦ reviser / 终稿裁剪<br/>从过程稿派生 compact_final_reader<br/>删去 / 移走导读字段、内部元数据<br/>重复脚手架、空泛 AI 话语"]
    F7 --> F8["⑧ reviser / 终稿回归<br/>逐章 + 前后附属部分完整阅读<br/>六项终稿检查"]
    F8 --> PUB["quality-publisher"]
```

样章与疑点试点共用同一个代表章节：

```mermaid
flowchart LR
    CH["同一个代表章节"] --> RP["读者方法试点<br/>production-plan.sample_review"]
    CH --> UP["疑点闭环试点<br/>pilot-review.json"]
    RP -. "共享快照与出处<br/>各自保留问题与结论" .- UP
    RP --> NOTE1["通过不代表全书验收<br/>也不授权付费跑全书"]
    UP --> NOTE1
```

---

## 10. 阅读单元（workflow 1.10）

```mermaid
flowchart TD
    SRC["20-source/blocks.jsonl<br/>+ 原貌重建给出的注释对象与续页证据"] --> RU["reader-units.json<br/>status: reviewed<br/>source_sha256 + review_evidence"]
    RU --> UNIT["units[]：每个源块恰属一个单元<br/>unit_id、kind、source_blocks、source_pages<br/>destination、decision_evidence"]

    UNIT --> K{"kind"}
    K --> K1["main_text"]
    K --> K2["commentary"]
    K --> K3["heading / preface / figure / table / paratext / noncontent"]

    K2 --> SC{"commentary_scope"}
    SC -- passage --> T1["target_units → 一个或多个 main_text"]
    SC -- "chapter / book" --> T2["target_units → 对应 heading"]
    SC -- note --> T3["target_units → commentary（注中注）"]
    SC -- missing_source --> T4["target_units 为空<br/>+ 有效 uncertainty_id + reader_notice<br/>保留古注、说明缺文，禁止补造正文"]
    T1 & T2 & T3 --> NOCYC["不得循环引用"]

    UNIT --> DST{"destination"}
    DST --> D1["final_reader"]
    DST --> D2["supplement"]
    DST --> D3["evidence_only"]

    UNIT --> CONT["continuations[]<br/>from_block → to_block + evidence<br/>同一句跨页续文属同一单元"]

    RU --> V1["validate_reader_units.py"]
    V1 --> V2["validate_production_plan.py<br/>bindings 必须包含 reader-units.json"]

    V2 --> FULL["全书成稿后"]
    FULL --> RR["reader-unit-rendering.json<br/>units_sha256 + manuscript_sha256<br/>按显示顺序：unit_id、start_line、end_line、quote"]
    RR --> V3["validate_reader_units.py --publication<br/>范围有效且不重叠<br/>每个 final_reader 单元恰出现一次<br/>注在其解释对象之后"]
    V3 --> PUBG["两道发布闸门都会调用"]

    CHG["改动任何关系"] -. "生产计划与出版映射失效<br/>重审受影响内容，不能只刷新哈希" .-> RU
```

---

## 11. 真实阅读会话（样章 / 全书）

```mermaid
sequenceDiagram
    autonumber
    participant P as 生产方 producer
    participant C as 总控 controller
    participant R as 独立读者 reviewer（子代理 / 人）
    participant F as 会话文件

    P->>F: 定稿样章 / 终稿（manuscript_sha256）
    C->>F: 先写 tasks（main_point / application / distinction / figure）<br/>不含预期答案
    C->>R: 只给稿件 + 任务，不给生产结论
    R->>F: responses（原样保留，含错误回答）
    C->>F: 读完后再对照原文写 assessments<br/>passed / needs_revision / blocked
    C->>F: provenance（实际问答记录与执行引用）
    alt 有 needs_revision / blocked
        C->>P: 退回修改材料
        P->>F: 新稿件
        C->>R: 开新会话（旧的失败会话保留）
    else 全部 passed
        C->>F: session.status = passed
    end
    Note over C,R: 不同 UUID 或角色名不等于独立执行<br/>没有独立执行条件时必须如实说明，并暂不给出独立读者验收
```

---

## 12. 全书读者审编与终稿裁剪（G5 / G5.5）

```mermaid
flowchart TD
    IN["reading-editor 交付完整过程稿<br/>modern-reading.md + reader-aids.json"] --> SNAP["保存不可变输入快照 + 哈希"]
    SNAP --> PASS1["先完整读一遍，读的时候不改<br/>九个维度：导言承诺、先修、导航、连贯<br/>术语负担、实例、图、重复<br/>原文与编者的区分、收束"]
    PASS1 --> REV["reader-review.json<br/>每个阻碍都写明：读者在哪里停下、猜测、回翻、跟丢论点"]
    REV --> ROUTE{"阻碍类型"}
    ROUTE -- "OCR / 缺文 / 翻译 / 归属 / 含义" --> BACK["退回负责的 skill<br/>+ 登记疑点候选"]
    ROUTE -- "可读性问题" --> OPS
    OPS["reader-revision-ledger.jsonl（只追加）<br/>add / delete_from_reading_path<br/>rewrite / reorganize"]
    OPS --> RISK{"语义风险为中 / 高?"}
    RISK -- 是 --> UA["进入统一疑点生命周期"]
    RISK -- 否 --> APPLY
    UA --> APPLY["应用修订<br/>同步 reader-aids.json，保留 block_id"]
    APPLY --> PROC["保存过程稿<br/>review-history/&lt;cycle_id&gt;/"]
    PROC --> CUT["终稿裁剪 compact_final_reader<br/>保留所有承载原文的内容<br/>删 / 移：导读字段、内部报告、重复脚手架<br/>解决不了具体阻碍的 AI 文字"]
    CUT --> SIX["六项检查<br/>ai_authored_material / guide_material_removed<br/>chapter_completeness / terminology_plainness<br/>figure_truthfulness / pipeline_language_absent"]
    SIX --> LOOP["完整通读第 n 轮<br/>full-passes/ 绑定真实记录与独立执行"]
    LOOP --> NB{"本轮有新的或未决的阻碍?"}
    NB -- 是 --> OPS
    NB -- 否 --> CNT{"n ≥ 3 且最后 2 轮都稳定?"}
    CNT -- 否 --> LOOP
    CNT -- 是 --> ACC["reader-acceptance-report.json（schema 1.2）<br/>含 final_reader_cut：process_sha256、output_sha256<br/>章节级回答、核心术语抽查"]
    ACC --> VAL["validate_reader_revision.py<br/>+ validate_reader_value.py"]
    VAL --> OK{"通过?"}
    OK -- 否 --> OPS
    OK -- 是 --> NEXT["final_adjudicated → 出版"]

    LOOP -. "同一阻碍连续 2 轮无进展" .-> STOP(["保存草稿，报告缺什么<br/>停止不等于验收"])
    PROOF["proof 模式：候选 PDF 上的阅读体验<br/>内容问题回 manuscript 模式<br/>视觉问题回 publisher"] -.-> OPS
```

编辑侧（reading-editor）交稿前的检查清单：

```mermaid
flowchart LR
    E1["导言：现存本性质<br/>题名作者 vs 可证作者<br/>汇编 / 层累情况"] --> E0
    E2["原书目录重建<br/>依据目录页 / 书眉 / 卷次<br/>不按页码偏移推算"] --> E0
    E3["术语表：本书实际用词<br/>核心术语六字段<br/>首现位置 + 引文"] --> E0
    E4["每张内容图有专属看图路线"] --> E0
    E5["传统因果 / 预测说法<br/>写成“书中认为”一类归属"] --> E0
    E6["source-reader-map.jsonl<br/>每个源块一行 + 终稿精确引文"] --> E0
    E7["无流水线用语<br/>forbidden_matches = 0"] --> E0
    E0["editorial-report.json<br/>由 reader-aids.json 推导计数<br/>不许手填"]
```

---

## 13. 冻结、忠实度复核与出版（G6）

```mermaid
flowchart TD
    A0["全部文字定稿<br/>封面 / 版权页文字、导言、原序、正文<br/>注、术语表、附录"] --> A1["lock_acceptance_policy.py<br/>acceptance-policy-lock.json<br/>绑定 edition-scope + 校验器哈希"]
    A1 --> A2["prepare_delivery_review.py<br/>生成 fidelity-review.json（只有 pending）"]
    A2 --> A3["逐块忠实度复核<br/>source_quote / modern_quote / reader_quote<br/>检查遗漏、增添、否定、条件、数量、术语<br/>内容图：原图 vs 终稿图 vs 说明"]
    A3 --> A4["delivery-contract.json<br/>各 outcome 由真实理解审读置为 passed"]
    A4 --> A5["uncertainty-release-review.json<br/>--check --publication"]
    A5 --> B1["渲染候选 PDF<br/>60-publication/candidates/"]
    B1 --> B2["prepare_release_proof.py<br/>生成待审逐页记录（不含批准）"]
    B2 --> B3["逐页人工检查<br/>页面角色、易读性、密度、留白、层级、连贯<br/>页码可见、目录页码、列表 / 术语表格式"]
    B3 --> B4["顺序通读候选 PDF<br/>pdf-reader-review.json 绑定 PDF 哈希<br/>1.10：每页正文与注可区分、跨页注可理解"]
    B4 --> B5["release-binding.json（schema 1.1）"]
    B5 --> G1{"audit_publication.py --candidate-pdf"}
    G1 -- 否 --> RET["退回负责的阶段"]
    G1 -- 是 --> G2{"validate_workspace.py<br/>--candidate-pdf"}
    G2 -- 否 --> RET
    G2 -- 是 --> INST["install_official_pdf.py --expected-pages N<br/>再跑双闸门，要求 A / B<br/>备份旧正式 PDF，检查文件锁，原子替换"]
    INST --> REL["正式发布<br/>60-publication/&lt;原书名&gt;·&lt;版本名&gt;.pdf<br/>modern-reading.md 与定稿逐字节一致"]
    REL --> QR["quality-report.json + 可读版质量报告"]
    QR --> FINAL["validate_workspace.py --stage publication"]

    INST -. "失败时保留旧版本不变" .-> REL0["原正式 PDF"]
    SUP["对照版 MD / PDF<br/>只放 supplements/"] -.-> REL

    HF["硬性失败：<br/>渲染文本里残留 HTML / XML 标签<br/>读者可见流水线消息<br/>OCR 乱码当正文<br/>重复的占位页 ID<br/>页 → 块链接断裂<br/>全扫描却缺逐页视觉证据"]:::hard
    G1 -.-> HF
    classDef hard fill:#fde2e2,stroke:#c00
```

普通读者版的三道独立验收，任何一道都不能替代另一道：

```mermaid
flowchart LR
    I["完整性<br/>PDF 身份、页 / 块清点<br/>各阶段文字非空、图与引用完整"]
    F["忠实度<br/>无增添、无漏否定 / 条件<br/>数量不变、术语不漂移"]
    C["读者理解<br/>能说出章旨、区分概念<br/>看懂图、找到承诺的答案"]
    I --> OK{"三项全部通过"}
    F --> OK
    C --> OK
    OK --> PUB["才可出版"]
```

---

## 14. 质量闸门与完成等级

```mermaid
flowchart LR
    G0["G0 接收完整性"] --> G1["G1 诊断"] --> G2["G2 忠实原文"] --> G25["G2.5 疑点裁决"] --> G3["G3 规范化"] --> G4["G4 今译<br/>含 1.8 前置 + 1.10 阅读单元"] --> G5["G5 阅读编辑"] --> G55["G5.5 全书读者审编"] --> G6["G6 出版"]
```

| 闸门 | 核心判据 |
|---|---|
| G0 | 源 PDF 的哈希、大小、页数已记录；各类页数和等于物理页数；每页至少一个块记录；源文件未被覆盖 |
| G1 | 每页都有路线；每个版面家族有样本；不支持的内容已提前登记；edition-scope 已锁定 |
| G2 | 页 / 块全覆盖；阅读顺序对照过图像；疑点保留可见；每块有组件、结构角色、坐标、顺序 |
| G2.5 | 每个候选恰有一个 active 裁决；关闭必须有证据、六范围复核、独立审核、可回放修改；有试点和终稿复核 |
| G3 | 每处改动可追溯；没有意译；专名、数量从严复核 |
| G4 | 每个内容块已译 / 保留 / 标注处置；文字非空；语言路线正确；没有无据增添；高风险块有独立比对 |
| G5 | 编者内容已标注；层级、术语、图注连贯；有导读路线、首现释义、看图路线、术语表；无流水线用语 |
| G5.5 | 九个维度；≥3 轮完整通读且末 2 轮稳定；回归审读者与生产者不同；终稿裁剪证据齐全 |
| G6 | 资产可解析；字体嵌入；目录和书签可点；逐页检查；唯一正式 PDF；双闸门 + 安装器；等级与账本一致 |

```mermaid
flowchart TD
    S{"所有闸门通过?"}
    S -- 否 --> SEM{"证据足以支持<br/>负责任的转换?"}
    SEM -- 否 --> D["D 无法还原"]
    SEM -- 是 --> C["C 辅助草稿<br/>不得称为可出版、完整版、final"]
    S -- 是 --> H{"有 active high 未决项?"}
    H -- 是 --> C
    H -- 否 --> M{"有 active material 未决项?"}
    M -- 否 --> A["A 可出版"]
    M -- "是：只有 low / medium 且已披露" --> B["B 附存疑清单可读"]
```

---

## 15. 返工影响路由

```mermaid
flowchart LR
    CH{"发生了什么改动?"}
    CH -- "原字 / 阅读顺序 / 缺文" --> R1["回原貌重建 + 疑点裁决<br/>→ 受影响的规范化 / 今译<br/>→ 关联术语、图、章节<br/>→ 新的忠实度、读者、PDF 验收"]
    CH -- "译文或核心术语含义" --> R2["回今译 + 裁决<br/>→ 该术语所有用处和关联论断<br/>→ 受影响章节理解<br/>→ 全书回归 + 出版校样"]
    CH -- "导言 / 解释 / 重组" --> R3["回阅读编辑<br/>→ outcome 承诺、原文与编者边界<br/>→ 新的忠实度 + 读者验收"]
    CH -- "只动排版 / 分页" --> R4["保留内容审核结论<br/>→ 重建 PDF 绑定、逐页校样、导航映射"]
    CH -- "批准后源文件、稿件、资产或合同变了" --> R5["相关证据全部作废<br/>保留历史，重审受影响范围"]
    CH -- "edition-scope 或校验代码变了" --> R6["acceptance-policy-lock 失效<br/>重新加锁 + 重新审核"]
    R1 & R2 & R3 & R4 & R5 & R6 --> ALL["终稿仍需整本回归阅读<br/>哈希不符是确定性停止<br/>run-state 写 passed 也不能覆盖"]
```

---

## 16. 停止规则与预算控制

```mermaid
flowchart TD
    W["任一阶段工作中"] --> Q1{"文件损坏 / 加密?"}
    Q1 -- 是 --> STOP
    Q1 -- 否 --> Q2{"缺页?"}
    Q2 -- 是 --> STOP
    Q2 -- 否 --> Q3{"阅读顺序严重不明?"}
    Q3 -- 是 --> STOP
    Q3 -- 否 --> Q4{"语言被系统性误判?"}
    Q4 -- 是 --> STOP
    Q4 -- 否 --> Q5{"预算耗尽?"}
    Q5 -- 是 --> STOP
    Q5 -- 否 --> Q6{"同一阻碍连续 2 轮<br/>没有新证据或实质进展?"}
    Q6 -- 是 --> STOP2(["停止循环<br/>保存草稿，只请求缺失的证据或决定"])
    Q6 -- 否 --> Q7{"即将付费跑全书?"}
    Q7 -- 是 --> EST["估算页数 / 成本<br/>取得用户授权<br/>样章授权 ≠ 全书授权"]
    Q7 -- 否 --> CONT["继续<br/>每次会话完成有意义的页 / 章<br/>保存可续跑的证据"]
    EST --> CONT
    STOP(["停止<br/>记录确切阻塞原因"])
    STOP & STOP2 --> NOTE["停止 ≠ 验收"]
```

---

## 17. 工作区产物数据流

```mermaid
flowchart TD
    BJ["book.json<br/>run-state.json"]
    I0["00-intake/source-manifest.json"]
    D1["10-diagnosis/<br/>profile.json、page-map.jsonl<br/>edition-scope.json"]
    S1["20-source/<br/>blocks.jsonl、source.md、pages/"]
    N1["30-normalized/<br/>blocks.jsonl、normalized.md、changes.jsonl"]
    M0["40-modernized/book-understanding.md"]
    M1["40-modernized/<br/>blocks.jsonl、modernized.md、terminology.json"]
    E0["50-edited/<br/>editorial-plan.md、reader-units.json<br/>sample/reader-sample.md、production-plan.json<br/>delivery-contract.json"]
    E1["50-edited/<br/>modern-reading.md、blocks.jsonl<br/>reader-aids.json、source-reader-map.jsonl<br/>reader-unit-rendering.json、editorial-report.json"]
    E2["50-edited/<br/>reader-review.json、reader-revision-ledger.jsonl<br/>reader-acceptance-report.json<br/>review-history/（过程稿、full-passes/）"]
    P1["60-publication/<br/>candidates/、modern-reading.md<br/>&lt;书名&gt;·&lt;版本名&gt;.pdf、supplements/"]
    AU["90-audit/<br/>events.jsonl、三份疑点账本<br/>pilot-review.json、fidelity-review.json<br/>uncertainty-release-review.json<br/>acceptance-policy-lock.json<br/>release-binding.json、pdf-reader-review.json<br/>quality-report.json"]

    BJ --> I0 --> D1 --> S1 --> N1 --> M0 --> E0 --> M1 --> E1 --> E2 --> P1
    S1 & N1 & M1 & E1 & E2 & P1 -. "疑点 / 审计事件" .-> AU
    AU -. "哈希绑定" .-> P1
```

块 ID 在各层之间的保持规则：

```mermaid
flowchart LR
    SB["源块 P000123-B007"] --> NB["规范化块<br/>同 block_id"]
    NB --> MB["今译块<br/>同 block_id；拆分用 segment_id<br/>合并时列出全部贡献块"]
    MB --> EB["编辑块<br/>显示层可合段，保留贡献 ID"]
    EB --> MAP["source-reader-map<br/>一块一行 → 终稿标题 + 精确引文"]
    SB -. "处置只能是" .-> DISP["retained / translated / noncontent<br/>unreadable / excluded_with_reason<br/>不许静默丢弃"]
```

---

## 18. 优化观察点

梳理流程时发现的不一致与可优化处，供修改 skill 时参考：

1. **版本号表述互相矛盾。** `reader-production.md` 要求新工作区用 workflow 1.10，而 `data-contract.md` 仍写“New workspaces declare workflow schema 1.8”。`delivery-and-rework.md` 标题还是“workflow 1.6”，`pilot-review.json` 要求 `workflow_version: "1.6"`。建议统一成“当前版本 + 各合同自己的 schema 版本”两层表述。
2. **主流程 13 步没有包含 1.10 的阅读单元阶段。** `reader_units_built` 只在 SKILL.md 末尾补了一段话，第 7 步里没提；阶段 `source_adjudicated` 在正文中也没有名字。建议按第 3 节的状态机重写第 1–13 步，让步骤与 `init_workspace.py` 的 `STAGES` 一一对应。
3. **补丁式叠加的写法太多。** SKILL.md 和各 reference 里大量出现“1.6 增加…、1.7 增加…、1.8 保留并增加…”，读者要自己在脑中合并规则。建议把当前生效规则合并成一份，版本演进单独放进 CHANGELOG。
4. **`data-contract.md` 的目录树不完整。** 缺少 `reader-units.json`、`reader-unit-rendering.json`、`production-plan.json`、`delivery-contract.json`、`editorial-plan.md`、`sample/`、`book-understanding.md`、`60-publication/candidates/`、`90-audit/fidelity-review.json`、`pilot-review.json`、`uncertainty-release-review.json`。实际文件布局分散在四五份文档里。
5. **“九段导言”存在张力。** `editorial-evidence-contract.md` 的示例是 `introduction_sections: 9`，并要求“introduction covers all nine reader-value sections”；而 `reader-units.md` 和 `reading-editor` 又说“不强制印九项介绍”“Nine dimensions do not require nine short paragraphs”。建议明确：九项只是过程稿里的覆盖索引，终稿不按九段排版。
6. **阶段检查散落在多个脚本里。** `validate_workspace.py` 的 `REQUIRED_PREPUBLICATION_STAGES` 不含 `book_understood` / `reader_designed` / `sample_accepted` / `reader_units_built`。前三项在第 264 行单独检查，`reader_units_built` 又在 `validate_integrity.py` 里检查。建议集中成一张“阶段 → 必需文件 → 校验器”的表。
7. **审读轮次负担重。** 样章会话、疑点试点、≥3 轮全书通读（末 2 轮稳定）、终稿复核、PDF 顺序通读、闭环逐条独立审核，每一项都要求独立执行记录。流程上可以考虑合并会话，或者明确哪些证据可以复用，降低单本书的成本和时间。
8. **子 skill 之间是双向依赖。** 子 skill 反向引用总控的 `reader-production.md` / `reader-units.md`（相对路径 `../chaoyun-ancient-book-renovator/...`），单独安装子 skill 时这些链接会失效。可以考虑把共享合同抽到一个公共 reference 包里。
