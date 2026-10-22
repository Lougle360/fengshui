# 阅读单元与普通读者成书规范（workflow 1.10）

适用普通读者白话版。证据层保留源块；理解、翻译和版面按完整阅读单元组织。无注的正文完全合法。注释必须说明解释对象，但不能把总注、篇注、注中注或缺失所释正文的存世古注硬配给最近一句。

## 所有权与交接

1. 原貌重建识别正文、古注、篇题、旁注和跨页续文，逐图核实关系。参考文本只辅助定位；不能覆盖扫描底本。难字和缺文进入已有疑点流程。
2. 今读编辑在设计阶段建立全书阅读单元；原貌重建负责确认依据。逐块确认后运行下述预生产校验，记录 run-state 的 reader_units_built 为 passed。只有代表样章允许提前试译。
3. 古文今译一起读取正文、所属注释及邻接上下文，分别保留各层作者的判断。所有输出仍保留原 block_id；合并显示不合并或改写证据记录。
4. 全书编辑保存过程导读版，另生成普通读者稿及显示位置映射。任何改动关系表都会使绑定该表的生产计划和出版映射失效，重新审核受影响内容；不得仅刷新哈希。
5. 全书读者审编执行原有至少三轮全文复核、最后两轮稳定的规则，真实逐章复述并检查注释归属、跨页接续、术语和多余的 AI 说明。
6. 出版读取冻结稿；逐页确认正文和注释的层级及承接关系，运行双重发布校验后由安装器替换正式 PDF。

## 可执行合同

在 50-edited/reader-units.json 写入对象：

- schema_version: "1.0"，status: "reviewed"，source_sha256 对应 20-source/blocks.jsonl。
- review_evidence 为实际结构审核记录：file（工作区相对路径）、sha256、reason。该记录应含扫描页、坐标/源块、判断依据和审核结论。
- units 为非空数组。每项包含 unit_id、kind、source_blocks、source_pages（升序去重的物理页）、destination、decision_evidence。证据对象与 review_evidence 格式相同。
- kind 可为 main_text、commentary、heading、preface、figure、table、paratext、noncontent；destination 为 final_reader、supplement、evidence_only。每个源块恰属一个单元，去向仍受 edition-scope 和 source-reader-map 约束。
- commentary 必须有 commentary_scope 和 target_units。passage 指向一个或多个 main_text；chapter/book 指向相应 heading；note 指向 commentary。不得有循环。普通正文不要求配注。
- 若扫描底本确实缺少所释正文，使用 missing_source、空 target_units、有效 uncertainty_id 和简短 reader_notice；保留古注、说明缺文，禁止补造正文。这不是跳过疑点裁决的出口，高影响缺失仍阻止发布。
- continuations 是数组（没有则为空）。每项含 from_block、to_block、evidence。同一句跨页续文应属于同一阅读单元，并保持源阅读顺序；检查源记录的 continues_from_previous_page / continues_to_next_page。

运行：

```shell
python scripts/validate_reader_units.py WORKSPACE
python scripts/validate_production_plan.py WORKSPACE
```

production-plan.json 的 bindings 必须包含 reader-units.json。校验验证覆盖、引用、顺序及证据绑定；它不能判定经注归属在语义上正确。

成稿后写 50-edited/reader-unit-rendering.json，含 units_sha256、manuscript_sha256 和按显示顺序排列的 units。每项为 unit_id、start_line、end_line、quote（所指范围内的实际文字）。范围必须有效、互不重叠，所有 final_reader 单元恰出现一次，注释必须出现在其解释对象之后。跨页续文可在同一单元内分段。

```shell
python scripts/validate_reader_units.py WORKSPACE --publication
```

两道现有发布闸门均调用该校验。页码、颜色、缩进只体现关系，不能代替源证据判断。

## 读者版写作与排版

正文和古注均译成现代白话；“原经”描述来源层级，不意味着重新印入未经翻译的文言文。保持原经与注者各自声音，必要时一句说明区分层级。避免反复印“经文：”“旧注：”；以字重、缩进、细线等体现层级，颜色不得是唯一信号。

连续原经按语义合并；注释按论述转折分段。长注跨页允许自然延续，但下一页应能辨认它仍属前文。不要为了每页有正文而复制或捏造经文。古注与对象相隔较远时增加必要的简短指引。

介绍、章前引导、术语六字段等完整证据保留在过程版。最终正文按实际阅读障碍决定保留多少，不强制印九项介绍或六字段模板。术语用本书实例解释；缺证据就明说，不用“结合上下文理解”等空话凑项。

复核记录必须来自实际阅读。脚本只准备待审清单、提取文字和汇总已有结论，禁止批量生成“全部通过”、逐页套话、读者答案或独立审核身份。

## 范本与迁移

《郭璞葬经（五经四书解义本）》本次获读者认可的版本用于学习经注层级、续文处理、术语实例和清洁正文，见 [范本说明](guopu-reader-benchmark.md)。它的字数、页数、单元数及颜色不是其他书的硬指标。

旧书的接受记录和已交付 PDF 保留。更新 Skill 不自动改写已发布书，也不把旧报告升级成 1.10 验收。继续旧任务时记录实际版本；要迁移到 1.10，先补真实关系证据和位置映射、重新锁定验收政策，再完成受影响审核。没有变化的历史证据不需要重复制造。
