"""Classify, de-duplicate and normalise raw records into 缺陷库/defects.jsonl."""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LIB = Path(r"D:\壮五福\风水项目\缺陷库")
RAW = LIB / "work" / "raw.jsonl"
OUT = LIB / "defects.jsonl"

# later entries win when the same defect appears in several versions of one book
VERSION_PRIORITY = [
    "琢玉斧·试跑", "琢玉斧·整本初版", "琢玉斧·重制", "琢玉斧·重制v2", "琢玉斧·V4",
    "平砂玉尺经·1.5", "平砂玉尺经·1.7",
]

CAUSED_AT = {
    "识别": "原文重建",
    "结构": "原文重建",
    "归属": "原文重建",
    "范围": "诊断与编辑设计",
    "忠实性": "白话转换",
    "释读缺口": "白话转换",
    "术语": "阅读编辑",
    "读者层": "阅读编辑",
    "出版": "审核出版",
    "质量门失效": "审核出版",
    "工具缺陷": "工具与脚本",
    "流程噪音": "疑点登记与裁决",
}

FOUND_AT = [
    (r"^reader_review|reader_revision", "读者审编"),
    (r"defect_library_scan", "终稿扫描（本次）"),
    (r"source|ledger|correction_replay", "原文重建与复核"),
    (r"modern|model_judge|editing|translation", "白话转换自检"),
]

PUNCT = re.compile(r"[\s\u3000-\u303f\uff00-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65\u2018-\u201f\u2026\u2014\-,.;:!?'\"()\[\]「」『』《》〈〉【】□…]")


def strip_punct(s):
    return PUNCT.sub("", s or "")


def has(pattern, *texts):
    return any(re.search(pattern, t or "") for t in texts)


def classify_correction(r):
    kind = r["raw_kind"]
    if kind == "cross_page_duplicate":
        return "结构", "跨页重复", None
    if kind == "ocr_pseudo_block":
        return "识别", "OCR伪块", None
    if kind == "coordinate_repair":
        return "结构", "版面坐标错位", None
    b, a = r.get("before") or "", r.get("after") or ""
    if b == a:
        return "流程噪音", "无实质改动的更正记录", "not_defect"
    if strip_punct(b) == strip_punct(a):
        return "识别", "标点误识", None
    if has(r"繁体|简体|异体", r["reason"]) and not has(r"实为|误识|刻误|之误", r["reason"]) and len(b) == len(a):
        return "识别", "繁简异体改动", None
    if has(r"跨页|顺序|错位|归入|切分", r["reason"]):
        return "结构", "跨页切分", None
    sb, sa = strip_punct(b), strip_punct(a)
    if len(sa) > len(sb):
        return "识别", "漏字", None
    if len(sa) < len(sb):
        return "识别", "多字", None
    return "识别", "错字", None


def classify_progress(r):
    t = r["text"]
    if has(r"伪块|重复OCR|重复切", t):
        return "识别", "OCR伪块"
    if has(r"交叉拼接|竖排顺序", t):
        return "结构", "阅读顺序"
    if has(r"切分|跨页|边界|误拆|归回|误提前|退回第|续入", t):
        return "结构", "跨页切分"
    if has(r"参考(本|文本|候选)|参考与底本", t):
        return "识别", "参考本与底本差异"
    if has(r"坐标|路径", t):
        return "结构", "版面坐标错位"
    return "识别", "错字"


POSITIVE = r"这是优点|积极方面|很好|完成度较高|编辑意图明确|覆盖主线所需|处理得当"


def classify_review(r):
    t = r["text"]
    if has(POSITIVE, t) and not has(r"但|却|缺少|不足|问题", t.split("；")[0][:40] if "但" not in t else ""):
        if has(r"^(积极方面|各图均附|第\d+—\d+行术语表的|结尾能)", t):
            return "流程噪音", "审读把优点记作待修", "not_defect"
    if has(r"对应原经|看似没有对应|古注", t):
        return "归属", "经注对应不清", None
    if has(r"术语|词表|关键词|“例”", t):
        return "术语", "术语解释不足", None
    if has(r"原图|示意|读图|图示|图像", t) and not has(r"重复|反复|机械", t):
        return "读者层", "图示说明不足", None
    if has(r"目录|索引|定位|回查|导航|小标题", t):
        return "读者层", "导航与查找", None
    if has(r"字段|流程|话术|过程|校勘|版刻题署|疑文说明|审核", t):
        return "读者层", "流程内容混入正文", None
    if has(r"重复|节奏|堆叠|篇幅|失衡", t):
        return "读者层", "重复与节奏", None
    if has(r"图", t):
        return "读者层", "图示说明不足", None
    if has(r"编者|推测|原书主张|顺句", t):
        return "读者层", "编者判断与原文混淆", None
    if has(r"前置|基础|示意|先读", t):
        return "读者层", "前置知识不足", None
    if has(r"开篇|定义|题名|署名|作者|第一屏|两层|三层", t):
        return "读者层", "导读与开篇", None
    if has(r"跨块|残句|打断|跨页|分块|章节边界|突然转入", t):
        return "结构", "阅读连续性", None
    return "读者层", "其他读者障碍", None


GAP = r"具体所指|所指不详|具體所指不详|语义不明|語意不明|语意不明|含义不明|含義不明|无法释读|無法|无法确定|不详|不明|残缺|残句|不完整|殘缺|具体含义|原文未明|不通|无法解读|难以理解"

# boilerplate clauses written by the pipeline; they say nothing about the specific defect
TEMPLATE_CLAUSES = [
    r"\d+轮自动修复后核义模型仍建议修订，已保守记录。?",
    r"该段已在二次修复与独立复判中接受",
    r"旧工作记录保留作历史证据，不再投射为读者未决项。?",
    r"属于审校评论或表达建议，不是未辨原文。?",
    r"本地硬校验仍未通过，已记录供后续自动处理或人工核对。?",
    r"原页若干字仍难逐字确定",
    r"最终读者文本只保留可稳妥说明的文意，不把猜字写成定论。?",
    r"该记录是短题签保留或图式结构说明，不是未决正文释义。?",
    r"保留底本可见录文，白话阶段不得靠通行本或理论补造，并在最终稿逐项核查读者影响。?",
    r"第[\d\-—]+页复核后仍有刻痕、墨损或字形不能唯一裁决",
    r"第[\d\-—]+页逐图校勘已完成",
    r"The high-impact translation risk was repaired[^；;]*",
    r"opaque terms remain explicit[^；;]*",
    r"这些候选对应的文字、漏字、角色或坐标更正均已落入当前输入[^；;]*",
    r"依据原页字形、成组对举、上下文或异体字规则复核后，可作确定处理。?",
    r"原图或旧刻仍不足以支持唯一读法",
    r"保留一个面向读者的实质疑点。?",
    r"该候选不构成读者层缺文。?",
    r"视觉复核结论为保留原字",
]
TEMPLATE_RE = re.compile("|".join(TEMPLATE_CLAUSES))


def strip_templates(s):
    parts = [p.strip() for p in re.split(r"[；;]", TEMPLATE_RE.sub("", s or ""))]
    return "；".join(p for p in parts if len(p) > 1)


def classify_doubt(r):
    t, rs_full, kind = r["text"], r["reason"], r["raw_kind"] or ""
    rs = strip_templates(rs_full)
    both_full = f"{t}；{rs_full}"
    both = f"{t}；{rs}"
    if has(r"(經|经)(\s*[上下]\s*卷之?|\s+卷之?)\s*[一二三四五六七八九十廿]+", both) and has(GAP + r"|版刻", both):
        return "结构", "版心页眉被当作正文释读", None
    if kind == "reader_revision":
        return "范围", "过程版到读者版的语义裁切", "fixed" if has(r"修复", rs_full) else None
    if has(r"复核确认属于跨页续文、版面关系、编者说明或完整性提示", rs_full):
        return "流程噪音", "说明性记录", "not_defect"
    if has(r"古文或日文与候选文本高度相同，没有完成可验证的白话化", rs_full):
        return "忠实性", "未完成白话化", None
    if has(r"Short heading/contributor label", both_full):
        return "流程噪音", "非正文短标签被登记", "not_defect"
    if has(r"old_text_not_uniquely_located|旧定位不足以安全回写|second_pass_evidence_not_auditable", rs_full):
        return "工具缺陷", "字形修订无法回写", None
    if has(r"馆藏章|印章|页边墨迹|非正文标记|藏書印|圖書館", both_full):
        return "流程噪音", "馆藏章等非正文误报", "not_defect"
    if has(r"在古籍中常见，此处按原字保留|可能为'[\u4e00-\u9fff]+'的异体|需确认是否为'[\u4e00-\u9fff]'的异体", both):
        return "流程噪音", "繁简字形误报", "not_defect"
    if has(r"图中文字清晰|无明显错字或模糊|图中文字与候选转录(基本)?一致|无残缺或(无法确认字|歧义)|未见明显残缺|文字解释完整", both) and not has(r"〔疑|〔缺|无法辨识", both):
        return "流程噪音", "无问题也登记", "not_defect"
    if has(r"^末句跨页|跨页，书名在下一页|末句跨页，下一页继续|承接上一?页", t):
        return "流程噪音", "说明性记录", "not_defect"
    if has(r"照录，准确|翻译准确|释读准确|处理准确|无误。", rs):
        return "流程噪音", "无问题也登记", "not_defect"
    if has(r"术语表未批准的括号解释", rs) and len(re.sub(r"出现术语表未批准的括号解释：[^；]*", "", rs).strip("；")) < 4:
        return "流程噪音", "规则校验告警", None
    if has(r"'.'为'.'的繁体|‘.’为‘.’的繁体", rs):
        return "流程噪音", "繁简字形误报", "not_defect"

    # source-side doubts
    if kind in ("reading_order", "layout"):
        if has(r"注|经句|角色|按语", rs):
            return "归属", "经注分界", None
        return "结构", "阅读顺序与版面", None
    if kind == "missing":
        return "识别", "漏字", None
    if kind == "extra":
        return "识别", "多字", None
    if kind == "glyph" or (kind in ("ledger_item",) and not has(r"白话|释读|语义|含义", rs)):
        if has(r"褪印|墨损|覆墨|模糊|不可辨|无法辨识|漫漶|〔缺|遮挡|不清|破损", both):
            return "识别", "漫漶不可辨", None
        if has(r"跨页|接续|续第|下一页", both):
            return "结构", "跨页接续", None
        if not rs.strip() and has(r"刻痕、墨损", rs_full):
            return "识别", "漫漶不可辨", None
        return "识别", "疑字待定", None

    # translation-side doubts
    if has(r"漏译|漏失|未释读|未体现", rs):
        return "忠实性", "漏译", None
    if has(r"增译|扩写|无依据|自行补充|改写为陈述|主观添加|添加了原文|原文没有", rs):
        return "忠实性", "增译或无依据扩写", None
    if has(r"OCR|传抄错误|明显的错字", rs) and has(GAP, both):
        return "释读缺口", "错字未校正直接进入译文", None
    if has(r"误译|误释|反义|释为.*错误|错误|误将|不准确|误作|错译|理解有误|偏差", rs):
        return "忠实性", "误译", None
    if has(r"确定结论|确定化|写成确定|确定解读|写成了?事实|确定解释|直接写为确定", rs):
        return "忠实性", "不确定写成确定", None
    if has(r"含义未定专名", rs):
        return "术语", "专名含义待定", None
    if has(r"保护项未保留|数字或干支", rs):
        return "忠实性", "干支数字等保护项丢失", None
    if has(GAP, both):
        if has(r"OCR|讹|误刻|误写|之误|错字|讹误|乱码|疑为", both):
            return "释读缺口", "错字未校正直接进入译文", None
        if has(r"残句|不完整|残缺|殘缺|缺字|跨页|节选", both):
            return "释读缺口", "残句或切断", None
        return "释读缺口", "术语或短语所指不详", None
    if not rs.strip() and has(r"核义模型仍建议修订|硬校验仍未通过|属于审校评论", rs_full):
        return "流程噪音", "通用占位理由（未说明问题）", None
    if kind == "terminology":
        return "术语", "术语含义待定", None
    after = r.get("after") or ""
    if has(r"具体所指不详|所指不详|原文未明|含义不明|语义不明|含义不详", after):
        if has(r"之误|疑为|讹", after):
            return "释读缺口", "错字未校正直接进入译文", None
        return "释读缺口", "术语或短语所指不详", None
    if not t.strip() and not rs.strip():
        return "流程噪音", "通用占位理由（未说明问题）", None
    if has(r"(可能|疑)为.{1,8}之(误|讹)", both):
        return "释读缺口", "错字未校正直接进入译文", None
    phrases = [p for p in re.split(r"[；;]", t) if p.strip() and not TEMPLATE_RE.search(p)]
    if phrases and all(len(p.strip()) <= 12 for p in phrases):
        return "释读缺口", "术语或短语所指不详", None
    return "忠实性", "其他翻译疑点", None


def classify(r):
    k = r["record_kind"]
    if k == "rework":
        m = r["manual"]
        return m["category"], m["subcategory"], None
    if k == "text_scan":
        return {
            "释读缺口": ("释读缺口", "终稿残留“所指不详”"),
            "流程用语混入": ("读者层", "流程用语混入正文"),
            "AI腔套话": ("读者层", "AI腔套话"),
            "版心混入": ("结构", "版心页眉混入正文"),
        }[r["raw_kind"]] + (None,)
    if k == "correction":
        return classify_correction(r)
    if k == "progress_log":
        return classify_progress(r) + (None,)
    if k == "review_finding":
        return classify_review(r)
    return classify_doubt(r)


def severity(cat, sub, r):
    impact = str(r.get("reader_impact") or "").lower()
    if r["record_kind"] == "rework":
        return r["manual"]["severity"]
    if cat in ("流程噪音",):
        return "无"
    if sub in ("标点误识", "繁简异体改动", "版面坐标错位"):
        return "仅外观"
    if cat in ("范围", "归属", "忠实性"):
        return "影响原意"
    if cat in ("识别", "结构"):
        if sub in ("漫漶不可辨", "疑字待定") and impact in ("low", "none"):
            return "影响阅读"
        return "影响原意"
    if cat == "工具缺陷":
        return "影响原意"
    if impact == "high" and cat in ("释读缺口", "术语"):
        return "影响原意"
    return "影响阅读"


def rework_cost(cat, sub, r):
    if r["record_kind"] == "rework":
        return r["manual"]["rework_cost"]
    return "局部修正"


def found_at(r):
    if r["record_kind"] == "rework":
        return r["manual"]["found_at"]
    f = str(r.get("found_at") or "")
    for pat, name in FOUND_AT:
        if re.search(pat, f):
            return name
    return f or "未知"


def caused_at(cat, r):
    if r["record_kind"] == "rework":
        return r["manual"]["caused_at"]
    return CAUSED_AT.get(cat, "未知")


def norm_key(s):
    s = unicodedata.normalize("NFKC", s or "")
    return strip_punct(s)[:60]


def main():
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        cat, sub, forced = classify(r)
        r["category"], r["subcategory"] = cat, sub
        if forced:
            r["outcome"] = forced
        r["severity"] = severity(cat, sub, r)
        r["caused_at"] = caused_at(cat, r)
        r["found_at_stage"] = found_at(r)
        r["rework_cost"] = rework_cost(cat, sub, r)
        r["closure_template"] = bool(re.search(r"属于审校评论或表达建议，不是未辨原文", r["reason"])) and cat in ("释读缺口", "术语", "忠实性")
        if r["outcome"] == "not_defect" and cat in ("释读缺口", "术语", "忠实性"):
            r["outcome"] = "closed_unchanged"
        if (r["record_kind"] == "doubt" and r["outcome"] == "not_defect" and cat in ("识别", "结构", "归属")
                and re.search(r"已落入当前输入", r["reason"] or "")
                and (cat != "识别" or strip_punct(r.get("before")) != strip_punct(r.get("after")))):
            r["outcome"] = "fixed"

    # 011: merge text corrections into the matching doubt (same UC id)
    fixed_ids = defaultdict(list)
    for r in rows:
        if r["book"] == "011" and r["record_kind"] == "correction" and r.get("ref_id"):
            fixed_ids[(r["ref_id"], r.get("page"))].append(r)

    groups = defaultdict(list)
    for r in rows:
        if r["record_kind"] in ("doubt", "review_finding", "correction"):
            ident = r.get("block_id") or ""
            if r["book"] == "036" and r["record_kind"] == "doubt":
                ident = ""  # early 琢玉斧 versions use different block ids
            key = (r["book"], r["record_kind"], r["category"], ident, norm_key(r["text"] or r["before"]))
        else:
            key = (r["book"], r["record_kind"], r["ref_id"], r["workspace"])
        groups[key].append(r)

    prio = {v: i for i, v in enumerate(VERSION_PRIORITY)}
    merged = []
    for key, lst in groups.items():
        lst.sort(key=lambda x: prio.get(x["version"], 99))
        rep = dict(lst[-1])
        rep["versions"] = sorted({x["version"] for x in lst}, key=lambda v: prio.get(v, 99))
        rep["occurrences"] = len(lst)
        rep["evidence"] = " | ".join(dict.fromkeys(x["evidence"] for x in lst))[:900]
        merged.append(rep)

    # attach 011 corrections to doubts, then drop the standalone correction rows that were merged
    merged_ids = set()
    for r in merged:
        if r["book"] == "011" and r["record_kind"] == "doubt" and (r.get("ref_id"), r.get("page")) in fixed_ids:
            cs = fixed_ids[(r["ref_id"], r.get("page"))]
            r["outcome"] = "fixed" if r["outcome"] in ("unresolved", "not_defect") else r["outcome"]
            r["before"] = r["before"] or "；".join(c["before"] for c in cs)
            r["after"] = r["after"] or "；".join(c["after"] for c in cs)
            r["evidence"] += " | " + " | ".join(c["evidence"] for c in cs)
            r["linked_corrections"] = len(cs)
    # keep standalone corrections: each text change is its own defect instance

    merged.sort(key=lambda r: (r["book"], r["record_kind"], r["category"], r["subcategory"]))
    with OUT.open("w", encoding="utf-8") as f:
        for i, r in enumerate(merged, 1):
            rec = {
                "defect_id": f"D{i:05d}",
                "book": r["book"],
                "version": r["version"],
                "versions": r["versions"],
                "location": {"page": r.get("page"), "block": r.get("block_id")},
                "category": r["category"],
                "subcategory": r["subcategory"],
                "caused_at": r["caused_at"],
                "found_at": r["found_at_stage"],
                "severity": r["severity"],
                "outcome": r["outcome"],
                "is_false_alarm": r["outcome"] == "not_defect",
                "rework_cost": r["rework_cost"],
                "before": (r.get("before") or None) and str(r["before"])[:400],
                "after": (r.get("after") or None) and str(r["after"])[:400],
                "description": r["text"] or r["reason"],
                "reason": r["reason"] if r["reason"] != r["text"] else None,
                "record_kind": r["record_kind"],
                "source_type": "ai_record",
                "closure_template": r["closure_template"],
                "occurrences": r["occurrences"],
                "evidence": r["evidence"],
                "ref_id": r.get("ref_id"),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("raw", len(rows), "merged", len(merged))
    c = Counter((r["category"]) for r in merged)
    print(c.most_common())


if __name__ == "__main__":
    main()
