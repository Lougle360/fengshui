"""Build 缺陷库/缺陷库统计报告.md from defects.jsonl (read-only with respect to all book workspaces)."""
import re
import sys
from collections import Counter
from pathlib import Path

from report_stats import BOOK_NAMES, CATEGORY_ORDER, KIND_NAMES, LIB, crosstab, load, real

sys.stdout.reconfigure(encoding="utf-8")
OUTPUT = Path(r"D:\壮五福\风水项目\output")
REPORT = LIB / "缺陷库统计报告.md"

rows, metrics, raw_n = load()
REAL = real(rows)
NON_SCAN = [r for r in REAL if r["record_kind"] != "text_scan"]
SCAN = [r for r in rows if r["record_kind"] == "text_scan"]


def book(r):
    return f"{r['book']} {BOOK_NAMES.get(r['book'], '')}"


def pct(a, b):
    return f"{a / b * 100:.0f}%" if b else "—"


def clip(s, n=160):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "……"


def find(pred):
    for r in rows:
        if pred(r):
            return r
    return None


def text_of(r):
    return " ".join(str(r.get(k) or "") for k in ("description", "reason", "before", "after"))


def table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in line) + " |" for line in body]
    return "\n".join(out)


# ---------------------------------------------------------------- numbers used in the prose
n_doubt = sum(1 for r in rows if r["record_kind"] == "doubt")
n_noise = sum(1 for r in rows if r["category"] == "流程噪音")
n_false = sum(1 for r in rows if r["outcome"] == "not_defect")
n_closed = sum(1 for r in rows if r["outcome"] == "closed_unchanged")
n_template_close = sum(1 for r in rows if r["closure_template"])
gap_ledger = [r for r in NON_SCAN if r["category"] == "释读缺口"]
gap_typo = [r for r in gap_ledger if r["subcategory"] == "错字未校正直接进入译文"]
yuannv = sum(1 for r in rows if "元女" in text_of(r))
yuannv_scan = sum(1 for r in SCAN if "元女" in text_of(r))
BAZHAI = ["绝命", "天医", "五鬼", "游魂", "生气", "延年", "祸害", "六煞"]
bazhai_hits = [r for r in rows if r["category"] in ("术语", "释读缺口") and r["record_kind"] == "doubt"
               and re.search("|".join(BAZHAI), r["description"] or "")]
source_side = [r for r in NON_SCAN if r["category"] in ("识别", "结构", "归属", "工具缺陷")]
template_rationale_n = next((t["count"] for t in metrics.get("V4/001-青囊海角经", {}).get("adjudication_rationale", {}).get("top", [])
                             if t["text"].startswith("属于审校评论")), 0)
CURRENT_VERSIONS = {"青囊海角经", "入地眼全书", "平砂玉尺经·1.7", "郭璞葬经", "琢玉斧·V4"}
SCAN_CUR = [r for r in SCAN if r["version"] in CURRENT_VERSIONS]
scan_gap_all = sum(1 for r in SCAN if r["category"] == "释读缺口")
scan_gap_cur = sum(1 for r in SCAN_CUR if r["category"] == "释读缺口")


# ---------------------------------------------------------------- final text scan density per version
def final_text_stats():
    out = []
    by_ws = Counter()
    by_ws_sub = crosstab(SCAN, lambda r: r["evidence"].split(":")[0], lambda r: r["subcategory"])
    for r in SCAN:
        by_ws[r["evidence"].split(":")[0]] += 1
    for path in sorted(by_ws_sub, key=lambda p: (p.split("/")[0], p)):
        f = OUTPUT / path
        chars = len(re.sub(r"\s", "", f.read_text(encoding="utf-8"))) if f.exists() else 0
        sub = by_ws_sub[path]
        gap = sub.get("终稿残留“所指不详”", 0)
        ver = next((r["version"] for r in SCAN if r["evidence"].startswith(path)), "")
        out.append([ver, f"`{path}`", f"{chars:,}", gap, f"{gap / chars * 10000:.1f}" if chars else "—",
                    sub.get("流程用语混入正文", 0), sub.get("版心页眉混入正文", 0), sub.get("AI腔套话", 0)])
    return out


# ---------------------------------------------------------------- typical cases
def case_block(title, r, note, show=("before", "desc", "after")):
    if r is None:
        return f"- **{title}**：记录中未找到对应条目。\n"
    loc = r["location"] or {}
    where = "、".join(x for x in [f"第{loc['page']}页" if loc.get("page") else "", loc.get("block") or ""] if x)
    lines = [f"- **{title}**（{book(r)}·{r['version']}{('，' + where) if where else ''}；{r['subcategory']}；{r['defect_id']}）"]
    if r.get("before") and "before" in show:
        lines.append(f"  - 原文/改前：{clip(r['before'], 120)}")
    if "desc" in show:
        lines.append(f"  - 记录内容：{clip(r['description'], 200)}")
    if r.get("reason") and "reason" in show:
        lines.append(f"  - 记录理由：{clip(r['reason'], 220)}")
    if r.get("after") and "after" in show:
        lines.append(f"  - 改后/译文：{clip(r['after'], 120)}")
    lines.append(f"  - 说明：{note}")
    lines.append(f"  - 证据：`{clip(r['evidence'], 200)}`")
    return "\n".join(lines) + "\n"


def rk(desc_kw):
    return find(lambda r: r["record_kind"] == "rework" and desc_kw in r["description"])


CASES = {
    "识别": [
        ("形近错字", find(lambda r: r["record_kind"] == "correction" and "如朱未之忠烈公" in (r["before"] or "")),
         "“朱未之”应为“宋末文”，三字全错，意思从人名变成无法理解的词组，是典型的形近误识。"),
        ("漏字", find(lambda r: r["record_kind"] == "correction" and (r["before"] or "") == "倒左出是破煞倒沖"),
         "漏掉方位字“辰”，水法口诀就断了。干支字一旦漏掉，读者无法自行补回。"),
        ("漫漶字组靠逐图复核才救回", find(lambda r: r["record_kind"] == "doubt" and "繡湖季讓言九宜" in (r["after"] or "")),
         "旧转录把鉴定者姓名读成“□語錯抑季先□”，逐图复核后才得出“繡湖季讓言九宜”。"),
    ],
    "结构": [
        ("自动切分整半页漏掉", rk("第16页上半版"), "自动切分错误会整段丢失原文，而且后续白话、编辑层看不出缺了什么。"),
        ("版心页眉混进最终白话正文", find(lambda r: r["record_kind"] == "text_scan" and r["subcategory"] == "版心页眉混入正文" and "巽人经下" in (r["description"] or "")),
         "“巽人经下 卷之 四”其实是版心的“玉尺经下 卷之四”，OCR 把“玉尺”误成“巽人”，白话层又把它当正文，还写上“具体所指不详”。", ("desc",)),
        ("跨页重复", find(lambda r: r["record_kind"] == "correction" and r["subcategory"] == "跨页重复"),
         "上一页尾部和下一页开头有大段文字完全重复，如果没被发现，读者会读到重复的经文。", ("desc",)),
    ],
    "归属": [
        ("经注分界错误", rk("正文与原注分界"), "经文和注文分错，白话层就会把注家观点当成经文原意。"),
        ("独立经句被并入注文", find(lambda r: r["record_kind"] == "doubt" and "独立经句被并入注文" in (r["reason"] or "")),
         "逐图复核发现一整句经文被合并进前面的注文，必须重新建块并调整后续解释的归属。", ("desc", "reason")),
        ("读者看不出注文对应哪句经", find(lambda r: r["record_kind"] == "review_finding" and r["category"] == "归属"),
         "读者审编层也能发现归属问题，但这时已经是整本读者稿，修改成本更高。", ("desc",)),
    ],
    "范围": [
        ("交付范围定错，成品撤销", rk("旧注不进最终正文"),
         "这是全库返工代价最高的一类：编辑方案一开始定错范围，后面所有环节都按错误范围做，质量报告还给了 B 级。"),
        ("过程版到读者版的裁切风险", find(lambda r: r["record_kind"] == "doubt" and r["subcategory"] == "过程版到读者版的语义裁切"),
         "范围错误纠正后，还需要全书 307 个来源块逐一回绑，才能确认没有遗漏。", ("desc", "reason")),
    ],
    "忠实性": [
        ("误译", find(lambda r: r["record_kind"] == "doubt" and "暴溺" in (r["reason"] or "")),
         "核义模型指出“暴溺”被误释为溺水，但这条只被“保守记录”，没有进入修复。", ("reason",)),
        ("反向错译", find(lambda r: r["record_kind"] == "doubt" and "反向错译" in (r["reason"] or "")),
         "原文说“以水为护卫”，译文译成“不属于以水为护卫”，意思完全相反。", ("reason",)),
        ("无依据扩写", find(lambda r: r["record_kind"] == "doubt" and (r["after"] or "").startswith("阳相关内容")),
         "把单字“陽”机械扩写成“阳相关内容”，读者看到的是一句不通的现代汉语。", ("reason", "after")),
    ],
    "释读缺口": [
        ("OCR 错字直接进入译文", find(lambda r: r["record_kind"] == "text_scan" and "言简意贼" in (r["description"] or "")),
         "“言简意贼”显然是“言简意赅”，却一直留到了最终读者稿；原文重建阶段本该在这里改掉。", ("desc",)),
        ("错字被当成未知术语", find(lambda r: r["record_kind"] == "text_scan" and "那甲" in (r["description"] or "")),
         "“那甲”即“纳甲”，是风水常用术语。译文已经猜到了，却仍写“具体所指不详”，读者只看到一句含糊的话。", ("desc",)),
        ("避讳字被当成未知专名", find(lambda r: r["record_kind"] == "text_scan" and "元女”，具体所指不详" in (r["description"] or "")),
         f"“元女”是清代避讳“玄”字后的写法，即“九天玄女”。全库有 {yuannv} 条记录涉及“元女”，其中 {yuannv_scan} 处留在最终读者稿，一条术语规则就能消除。", ("desc",)),
    ],
    "术语": [
        ("八宅标准术语被标为含义待定", find(lambda r: r["record_kind"] == "doubt" and r["category"] == "术语" and "绝命长房灾" in (r["description"] or "")),
         f"“绝命、天医、五鬼、游魂、生气、延年”是八宅游星的标准名称。疑点账本里有 {len(bazhai_hits)} 条把这些词当成待定术语或所指不详。", ("desc", "reason")),
        ("已交付的书被查出 25 个术语错误", rk("25 个术语错误"), "术语错误是在 Skill 升级时回头验证才发现的，说明原交付流程里没有术语核验环节。"),
        ("术语解释不足", find(lambda r: r["record_kind"] == "review_finding" and r["category"] == "术语"),
         "读者审编层反复指出术语只列名、不解释。", ("desc",)),
    ],
    "读者层": [
        ("流程用语直接印进读者稿", find(lambda r: r["record_kind"] == "text_scan" and r["subcategory"] == "流程用语混入正文" and "核义模型" in (r["description"] or "")),
         "“1轮自动修复后核义模型仍建议修订，已保守记录”是内部流程状态，却出现在给读者看的正文里。", ("desc",)),
        ("独立试读不通过", rk("独立前向试读不通过"), "内容忠实但读者读不懂，属于读者层缺陷，要靠独立试读才能发现。"),
        ("模板句反复出现", find(lambda r: r["record_kind"] == "review_finding" and "证据边界句反复出现" in (r["description"] or "")),
         "同一句免责说明重复二十多次，读者体验机械。", ("desc",)),
    ],
    "出版": [
        ("成品反复作废", rk("发布历史中保留了 11 个"), "作废原因没有写进文件，下一本书无法从这些失败中学习。"),
    ],
    "质量门失效": [
        ("评 B 级后被用户退回", rk("1.5 版质量报告评为 B 级"), "质量报告宣称达到交付门槛，但用户不接受；退回理由没有记录，这正是人工意见录入表要补上的位置。"),
    ],
    "工具缺陷": [
        ("字形修订无法回写", find(lambda r: r["category"] == "工具缺陷" and "old_text_not_uniquely_located" in (r["reason"] or "")),
         f"原页已经找出正确字形，但脚本定位不到旧文本，只能“保守保留”，错字因此留在现代版里。全库共 {sum(1 for r in NON_SCAN if r['category'] == '工具缺陷')} 条。", ("reason",)),
    ],
    "流程噪音": [
        ("短标题被登记为疑点", find(lambda r: r["subcategory"] == "非正文短标签被登记" and r.get("before")),
         "章节小标题、校订者署名因为没有匹配到分段锚点，被批量登记成疑点，然后又批量关闭。", ("before", "reason")),
        ("繁简字形误报", find(lambda r: r["subcategory"] == "繁简字形误报" and "趙" in text_of(r)) or find(lambda r: r["subcategory"] == "繁简字形误报"),
         "正常的繁体字或异体字被当成疑字登记。", ("desc", "reason")),
        ("用一句模板关闭疑点", find(lambda r: r["closure_template"] and r["category"] == "释读缺口"),
         f"001 有 {template_rationale_n} 条裁决用同一句“属于审校评论或表达建议，不是未辨原文”关闭，其中 {n_template_close} 条是释读、术语、忠实性类的疑点，不少确实没有解决。", ("desc", "reason")),
    ],
}


def build():
    L = []
    w = L.append
    w("# 古书翻新缺陷库统计报告")
    w("")
    w("> **基于 AI 工作记录的初版。** 本报告只统计各书工作目录中已有的账本、事件、审编意见、进度日志和最终读者稿；"
      "用户的人工意见尚未录入，录入后需要重算。所有数字都能在 `defects.jsonl` 里按 `evidence` 字段回查到原始文件和行号。")
    w("")
    w(f"数据范围：6 本书、11 个工作区（含《琢玉斧》试跑、整本初版、重制、重制 v2、V4 五个版本，《平砂玉尺经》1.5 和 1.7 两个版本）。"
      f"原始记录 {raw_n:,} 条，跨版本、跨账本合并后 {len(rows):,} 条。书稿、账本、Skill 文件均未修改。")
    w("")

    # ------------------------------------------------ conclusions
    scan_gap_current = {r["version"] for r in SCAN}
    w("## 一、结论：最该先拦截的三类问题")
    w("")
    w(f"### 1. 释读缺口：错字和常见术语在白话阶段被写成“具体所指不详”")
    w("")
    w(f"这是数量最多的一类。疑点账本里有 {len(gap_ledger)} 条释读缺口；各版本最终读者稿里共扫描到 "
      f"{scan_gap_all} 处“具体所指不详”一类的说法，其中 {scan_gap_cur} 处在各书当前版本里。"
      f"账本中的释读缺口有 {len(gap_typo)} 条（{pct(len(gap_typo), len(gap_ledger))}）能明确看出根源是原文错字没有在上一环节改掉"
      f"（例如“言简意贼”“那甲”“康贞”）；另有大量是常见术语被当作未知词，例如避讳字“元女”一项就涉及 {yuannv} 条记录，"
      f"八宅游星名称涉及 {len(bazhai_hits)} 条。")
    w("")
    w("这些问题大多在账本里已经被标出来，但仍然进入了最终稿，也就是“已知问题带病交付”。"
      "新版本明显好转：《平砂玉尺经》1.7、《琢玉斧》V4、《郭璞葬经》的最终稿里几乎没有这类说法；"
      "《青囊海角经》和《入地眼全书》当前的最终稿仍各有两百多处。")
    w("")
    w("**拦截位置：** 原文重建出口和白话转换入口。具体做法是：进入白话前，疑字要么改正、要么明确标为底本残损；"
      "共享术语库先收录避讳字（元→玄）、八宅游星、纳甲等高频词；最终稿按每万字“所指不详”次数设硬上限。")
    w("")
    w("### 2. 原文重建：识别和结构错误数量大、返工代价最高")
    w("")
    w(f"识别、结构、归属和工具缺陷四类合计 {len(source_side)} 条（不含终稿扫描）。数量不是最多，但全库最贵的返工几乎都出在这里："
      "《琢玉斧》整本初版只有 10/80 页视觉重建成功，最后整本重做三轮；《郭璞葬经》自动切分漏掉第 16 页上半版，候选块从 359 重建到 309，前后校正多次；"
      "网络参考本多出 541 字险些混进底本。另有 "
      f"{sum(1 for r in NON_SCAN if r['category'] == '工具缺陷')} 条已找出正确字形却因脚本定位失败无法回写，错字因此留在现代版里。")
    w("")
    w("**拦截位置：** 原文重建阶段结束时做结构锁定，设第一个人工检查点（对应《skill优化方案V1》第 3 条），"
      "逐页确认页序、跨页接续、经注分界后再进入白话；字形修订回写失败要算作阻断错误，不能“保守保留”。")
    w("")
    w("### 3. 质量门失效：审核结论模板化，B 级成品反复被推翻")
    w("")
    fid = metrics.get("V4/003-平砂玉尺经-1.7", {}).get("fidelity_review", {})
    fid4 = metrics.get("V4/004-郭璞葬经-1.8", {}).get("fidelity_review", {})
    pdf4 = metrics.get("V4/004-郭璞葬经-1.8", {}).get("pdf_reader_review", {})
    w(f"《平砂玉尺经》1.7 的忠实性复核 {fid.get('blocks')} 块全部“通过”，检查说明只有 {fid.get('distinct_checks_text')} 种写法；"
      f"《郭璞葬经》{fid4.get('blocks')} 块同样全部通过、说明只有 {fid4.get('distinct_checks_text')} 种；"
      f"它的 PDF 读者审查 {pdf4.get('pages')} 页，去掉页码后只有 {pdf4.get('distinct_after_removing_page_numbers')} 种不同评语。"
      f"疑点账本 {n_doubt:,} 条中有 {n_noise} 条是流程噪音（{pct(n_noise, n_doubt)}），{n_closed} 条语义疑点没有任何改动就被关闭。"
      "结果是：《平砂玉尺经》1.5 评 B 级后被用户退回；《青囊海角经》评 B 级后又整体重建两次，第三轮语义修复还找出 59 条高影响翻译错误；"
      "《郭璞葬经》按错误范围发布的 B 级 PDF 被撤销。")
    w("")
    w("**拦截位置：** 审核出版阶段。审核者换用与生成者不同的模型，每一项检查必须引用具体句子，禁止整块批量通过；"
      "交付前设第二个人工检查点（对应《skill优化方案V1》第 6 条）。")
    w("")

    # ------------------------------------------------ overview
    w("## 二、总体数字")
    w("")
    kinds = Counter(r["record_kind"] for r in rows)
    w(table(["记录来源", "条数", "说明"], [
        [KIND_NAMES["doubt"], kinds["doubt"], "疑点候选与裁决账本、不确定项账本"],
        [KIND_NAMES["correction"], kinds["correction"], "原文更正事件、011 的逐页更正文件"],
        [KIND_NAMES["progress_log"], kinds["progress_log"], "《郭璞葬经》当前工作进度中的缺陷描述"],
        [KIND_NAMES["review_finding"], kinds["review_finding"], "读者审编报告里的具体问题"],
        [KIND_NAMES["text_scan"], kinds["text_scan"], "本次对最终读者稿的关键词扫描，与账本有重叠，单独统计"],
        [KIND_NAMES["rework"], kinds["rework"], "从质量报告、升级说明、发布历史整理的高代价返工"],
    ]))
    w("")
    oc = Counter(r["outcome"] for r in rows)
    w(table(["处理结果", "条数", "含义"], [
        ["unresolved", oc["unresolved"], "记录里没有修复或关闭的证据"],
        ["in_final_text", oc["in_final_text"], "出现在最终读者稿中（仅终稿扫描）"],
        ["fixed", oc["fixed"], "有改前改后或修复记录"],
        ["closed_unchanged", oc["closed_unchanged"], "语义类疑点未作改动即关闭"],
        ["not_defect", oc["not_defect"], "复核确认不是问题（误报）"],
        ["fixed_or_superseded", oc["fixed_or_superseded"], "读者审编意见在后续版本中已处理或被替换"],
        ["rejected", oc["rejected"], "审编意见被明确拒绝"],
    ]))
    w("")
    w(f"`not_defect`（误报）共 {n_false} 条，占全部记录的 {pct(n_false, len(rows))}、疑点账本的 "
      f"{pct(sum(1 for r in rows if r['record_kind'] == 'doubt' and r['outcome'] == 'not_defect'), n_doubt)}。"
      "以下统计除非另注，都已排除流程噪音和误报。")
    w("")

    # ------------------------------------------------ by category
    w("## 三、按缺陷类别")
    w("")
    ct = crosstab(REAL, lambda r: r["category"], lambda r: r["record_kind"])
    body = []
    for c in CATEGORY_ORDER:
        if c == "流程噪音":
            continue
        d = ct[c]
        tot = sum(d.values())
        body.append([c, tot - d.get("text_scan", 0), d.get("text_scan", 0), d.get("doubt", 0), d.get("correction", 0),
                     d.get("review_finding", 0), d.get("progress_log", 0), d.get("rework", 0)])
    w(table(["类别", "合计（不含终稿扫描）", "终稿扫描", "疑点账本", "更正记录", "审编意见", "进度日志", "返工记录"], body))
    w("")
    w("主要子类（不含终稿扫描，前 25 项）：")
    w("")
    sub = Counter((r["category"], r["subcategory"]) for r in NON_SCAN).most_common(25)
    w(table(["类别", "子类", "条数"], [[c, s, n] for (c, s), n in sub]))
    w("")
    sev = Counter(r["severity"] for r in NON_SCAN)
    w(f"严重程度（不含终稿扫描）：影响原意 {sev['影响原意']} 条，影响阅读 {sev['影响阅读']} 条，仅外观 {sev['仅外观']} 条。")
    w("")

    # ------------------------------------------------ by stage
    w("## 四、按产生环节和发现环节")
    w("")
    cf = crosstab(REAL, lambda r: r["caused_at"], lambda r: r["found_at"])
    founds = [f for f, _ in Counter(r["found_at"] for r in REAL).most_common()]
    order = ["诊断与编辑设计", "原文重建", "底本条件", "工具与脚本", "白话转换", "阅读编辑", "审核出版"]
    w(table(["产生环节 \\ 发现环节"] + founds + ["合计"],
            [[c] + [cf[c].get(f, 0) or "" for f in founds] + [sum(cf[c].values())] for c in order if c in cf]))
    w("")
    w(f"“终稿扫描（本次）”一列共 {len(SCAN)} 处，是这次扫描各版本最终读者稿时统计到的；其中 {len(SCAN_CUR)} 处在各书当前版本里，"
      "也就是说它们通过了 Skill 自身的全部检查，印进了成品。"
      "白话转换产生的问题几乎都由白话阶段的自检发现，但发现后多数只是“记录”，没有退回上一环节修正。")
    w("")

    # ------------------------------------------------ by book
    w("## 五、按书")
    w("")
    bt = crosstab(NON_SCAN, lambda r: r["book"], lambda r: r["category"])
    cats = [c for c in CATEGORY_ORDER if c != "流程噪音" and any(bt[b].get(c) for b in bt)]
    w(table(["书"] + cats + ["合计"], [[book({"book": b})] + [bt[b].get(c, 0) or "" for c in cats] + [sum(bt[b].values())] for b in sorted(bt)]))
    w("")
    w("最终读者稿扫描（按版本；每万字次数按去掉空白后的字数计算）：")
    w("")
    w(table(["版本", "文件", "字数", "所指不详类", "每万字", "流程用语", "版心混入", "AI 腔套话"], final_text_stats()))
    w("")
    w("同一本书的新版本比旧版本明显干净：《平砂玉尺经》从 1.5 到 1.7、《琢玉斧》从整本初版到 V4，“所指不详”类说法都基本清零。"
      "《青囊海角经》《入地眼全书》当前最终稿还没有经过同样的处理。")
    w("")

    # ------------------------------------------------ rework
    w("## 六、高代价返工")
    w("")
    w("这些记录来自质量报告、升级说明、发布历史和当前工作进度，由人工逐条整理（`tools/rework_manual.json`）。"
      "“撤销成品”指已经生成的 PDF 或已评级的成品被作废。")
    w("")
    rw = sorted([r for r in rows if r["record_kind"] == "rework"], key=lambda r: (r["rework_cost"] != "撤销成品", r["book"]))
    w(table(["书", "类别", "问题", "发现于", "代价", "证据"],
            [[book(r), r["category"], clip(r["description"], 110), r["found_at"], r["rework_cost"], f"`{clip(r['evidence'], 90)}`"] for r in rw]))
    w("")
    w(f"撤销成品共 {sum(1 for r in rw if r['rework_cost'] == '撤销成品')} 次。只有《琢玉斧》整本初版是 Skill 自己的质量报告评为 C 级、主动判定不合格的；"
      "《青囊海角经》《平砂玉尺经》1.5、《郭璞葬经》范围错误版三次，都是先评了 B 级，再被用户退回或事后复查推翻；"
      "《郭璞葬经》另有 11 个发布目录被作废。")
    w("")

    # ------------------------------------------------ false alarms & templates
    w("## 七、误报、流程噪音与模板化审核")
    w("")
    bo = crosstab([r for r in rows if r["record_kind"] == "doubt"], lambda r: r["book"], lambda r: r["outcome"])
    noise_b = Counter(r["book"] for r in rows if r["record_kind"] == "doubt" and r["category"] == "流程噪音")
    w(table(["书", "疑点数", "流程噪音", "误报（not_defect）", "未改动即关闭", "已修复", "未解决"],
            [[book({"book": b}), sum(bo[b].values()), noise_b[b], bo[b].get("not_defect", 0), bo[b].get("closed_unchanged", 0),
              bo[b].get("fixed", 0), bo[b].get("unresolved", 0)] for b in sorted(bo)]))
    w("")
    ns = Counter(r["subcategory"] for r in rows if r["category"] == "流程噪音").most_common()
    w("流程噪音的构成：" + "；".join(f"{s} {n} 条" for s, n in ns) + "。")
    w("")
    w("审核文本的重复程度（来自 `work/process-metrics.json`）：")
    w("")
    mbody = []
    for ws, m in metrics.items():
        if "fidelity_review" in m:
            f = m["fidelity_review"]
            mbody.append([ws, "忠实性复核", f"{f['passed']}/{f['blocks']} 块通过", f"检查说明 {f['distinct_checks_text']} 种、证据说明 {f['distinct_evidence_text']} 种"])
        if "pdf_reader_review" in m:
            p = m["pdf_reader_review"]
            mbody.append([ws, "PDF 读者审查", f"{p['pages']} 页，结论 {p['status']}", f"去掉页码后评语 {p['distinct_after_removing_page_numbers']} 种"])
        if "adjudication_rationale" in m:
            a = m["adjudication_rationale"]
            top = a["top"][0] if a["top"] else {"text": "", "count": 0}
            mbody.append([ws, "疑点裁决理由", f"{a['rows']} 条，{a['distinct_rationale']} 种写法", f"最常见一句出现 {top['count']} 次：{clip(top['text'], 40)}"])
    w(table(["工作区", "审核环节", "规模", "重复程度"], mbody))
    w("")
    w("批量通过和一句话关闭本身不一定错，但它意味着审核没有留下可核对的依据；上面的返工记录说明，这些“通过”后来多次被推翻。")
    w("")

    # ------------------------------------------------ cases
    w("## 八、典型案例（每类最多 3 个）")
    w("")
    for c in CATEGORY_ORDER:
        w(f"### {c}")
        w("")
        for item in CASES.get(c, []):
            title, r, note = item[0], item[1], item[2]
            show = item[3] if len(item) > 3 else ("before", "after")
            w(case_block(title, r, note, show))
    # ------------------------------------------------ coverage
    w("## 九、各书记录覆盖程度")
    w("")
    w(table(["书", "有哪些记录", "缺什么 / 注意事项"], [
        ["001 青囊海角经", "疑点候选与裁决、更正事件、语义修复记录、归档的旧质量报告、最终读者稿",
         f"没有逐页源文复核日志；{template_rationale_n} 条疑点用同一句模板关闭，真实处理情况无法从记录判断。"],
        ["002 入地眼全书", "不确定项账本（含编辑候选）、更正事件、最终读者稿",
         "没有裁决账本和质量报告，疑点的“是否已修”无法判断，因此全部记为未解决；交付总账停在 09-26，不据此推断验收结果。"],
        ["003 平砂玉尺经", "1.5 与 1.7 两套完整账本、读者审编历史、1.5 退回归档、1.7 升级说明",
         "1.5 被用户退回的具体理由没有写入任何文件；两版疑点 500 条完全重合，已合并。"],
        ["004 郭璞葬经", "疑点账本、当前工作进度、逐页复核、11 个作废发布目录、最终稿",
         "疑点账本 86 条的候选理由全部为空，只能靠裁决和进度日志判断；作废原因按目录名推断。"],
        ["011 青囊心印", "疑点账本、逐页更正文件、坐标回放、CURRENT.md",
         "尚未产出最终读者稿，没有白话层和读者层数据；这里的数字只反映原文重建阶段。"],
        ["036 琢玉斧", "试跑、整本初版、重制、重制 v2、V4 五个版本的不确定项与裁决账本",
         "早期版本块号不统一，跨版本合并只按文字匹配，可能有少量重复未合并；V4 自身记录较少。"],
    ]))
    w("")

    # ------------------------------------------------ method
    w("## 十、方法与可信度")
    w("")
    w("1. `tools/extract_defects.py` 只读提取各工作区的账本、事件、审编意见、进度日志，并扫描最终读者稿，输出 `work/raw.jsonl`。")
    w("2. `tools/classify_defects.py` 按分类表归类，先剥掉流水线反复写入的模板句再判断，避免模板里的词误触发分类；"
      "同书同块同文字的记录跨版本合并，保留最新版本为代表，并在 `versions`、`occurrences`、`evidence` 里保留全部来源。")
    w("3. 归类准确率用随机抽样人工核对：第一轮 50 条准确率 82%，按错误修订规则后，第二、三轮换新样本分别为 88%、84%（暴露出新的长尾问题），"
      "第四轮 92%，最终一轮独立抽样 96%。抽查样本保存在 `work/check-50-*.txt`。")
    w("4. 终稿扫描用关键词匹配，同一行命中多个关键词会计为多条；它和疑点账本描述的是同一批问题的不同阶段，所以单独列出、不与账本相加。")
    w("5. 严重程度和返工代价以规则估计为主，只有返工记录是人工逐条判断的。")
    w("")
    w("用户的人工意见录入后（见 `人工意见录入表.md`），需要重算第一节结论，并对照 AI 记录找出哪些问题只有人能发现。")
    w("")
    REPORT.write_text("\n".join(L), encoding="utf-8")
    print("wrote", REPORT, len(L), "lines")
    missing = [(c, t) for c, items in CASES.items() for t, r, *_ in items if r is None]
    print("missing cases:", missing)


if __name__ == "__main__":
    build()
