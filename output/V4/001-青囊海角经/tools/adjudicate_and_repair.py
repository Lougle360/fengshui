from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit"
MODERN = ROOT / "40-modernized"


MANUAL_REPAIRS = {
    "P000015-B003": "在恍惚幽暗、还没有具体形象的状态中，万物的形体尚未显现。",
    "P000015-B005": "图中用纯黑表示“太无”：它幽暗无形，不能直接显现。黄石公所说的“太无不无”，以及《老子》所说的“无，名天地之始”，都在说明天地、人三才尚混合为一气、不可见闻的状态。书中说，九天玄女设置此图，是为了让学习者由此体会大道。原文末句残缺，本版不补写。",
    "P000016-B002": "从无形之中产生有形：太元一动，天地和万物由此获得生成的条件。",
    "P000016-B004": "图中一点白色表示纯阳潜藏在黑色之中，虽处幽暗而内含光明，这就是“黑中有白，阴里怀阳”。原书借《图经》和《老子》的话说明：有形万物从虚静之中发生；没有这一点阳气，阴也不能独自完成生化。所谓“知白守黑”，就是把握这种由静到动、由无形到有形的转机。作者认为，前两幅图所表达的根本关系，比后来用八卦、甲子推演万物更为基础。",
    "P000016-B005": "阳气刚开始发动、万物尚未形成之时，其中景象微妙，难以完全用语言表达。",
    "P000017-B001": "黑白相合，以子、午标示阴阳消长的关键，万物由此发生变化。",
    "P000017-B003": "天地的位置确立以后，阴阳彼此消长；日月循环，寒暑也随之推移。《图经》把这种关系概括为“有无相生，万物化成”。动静有时序，盛衰有定数，于是可以用八卦推演、用历法节律相互参照。原书以子时为阳气开始生发之处，以午时为阴气开始生发之处，并据此说明万物变化的枢纽。",
    "P000018-B003": "“五运六气”是原书用天象、五行和干支解释气候及人事的一套体系。书中把火、土、木、金、水五类天运分别配入若干星宿，又规定甲己属土运、乙庚属金运、丙辛属水运、丁壬属木运、戊癸属火运。随后，原书把不同气运与人的性情相联系，并用“生旺”与“休囚”解释兴衰。这些属于传统术数中的对应关系，不是现代科学结论。",
    "P000019-B004": "数字“一”确立以后，才有了判断盈亏、消长和五行阴阳的基础。从一到十的天地之数合计为五十五，原书将它与河图、洛书的数理结构相联系，再把十天干与十二地支配合，用来构成六十甲子和后续的历数推演。",
    "P000020-B003": "原书把六十甲子与八卦、五行、阴阳盛衰结合起来，用以推演旺、墓等状态并判断传统意义上的吉凶。顺应其规则被视为吉，违背则被视为凶。这里表达的是书中术数体系的内部规则。",
    "P000020-B004": "一、三、五、七、九是奇数，原书归为阳数、天数，并把五个阳数与十天干联系起来。",
    "P000020-B005": "二、四、六、八、十是偶数，原书归为阴数、地数，并把六个阴数层次与十二地支联系起来。",
    "P000021-B003": "十二地支环列于十二宫，再与十天干相配，每一组又配五气，从而组成六十甲子。原书用“天变而地不变”概括这种配合法，并借冬至葭灰飞动、尧时蓂荚生落等传统说法，说明日、月、年的甲子起点。",
    "P000022-B002": "原书以五行所处的旺衰状态为纳音取象：水旺而金潜藏其中，称为“海中金”；水有源流而从地下涌出，称为“涧下水”。",
    "P000022-B003": "阴中含阳、声势突然发动，原书取象为“霹雳火”；水与土相互依存，取象为“壁上土”。",
    "P000022-B004": "阳气初生，原书取象为“扶桑木”；木旺而生火，取象为“炉中火”。",
    "P000079-B011": "原书把乾、坤、艮、巽列为“孟”，配长房；把甲、庚、丙、壬列为“仲”，配中房；把乙、辛、丁、癸列为“季”，配小房。放水宜小不宜大；末句涉及沟头与命位的距离，原文简略，本版不作确定扩写。",
    "P000081-B004": "以上规则还要以阴阳配合正确、地形格局符合条件为前提，不能在任何地点机械套用；条件不具备时尤其不可触犯书中所列禁忌。",
    "P000089-B015": "如果形势孤单、两旁没有护卫，就不必继续寻找穴位；必须有左右山势相助。这类星体多在平洋地区结穴，还要有相间的星峰配合，原书才认为五福齐全。",
    "P000118-B005": "这种山形像倒扣的锅，原书归为金星。山势行进宜有弯曲转折并形成相生关系；如果两侧支脚歪斜，传统上被认为会带来刑伤。",
    "P000194-B010": "问的人说：“这些说法的荒谬乖错已经如此明显，为什么其中又似乎包含一些选择葬地的道理呢？”",
    "P000194-B011": "回答说：“术数书的内容并不纯一，往往好坏混杂。创造事物时所凭的智慧本来就很难完全用语言表达，因此不能只因书中有失误，就把其中可能合理的部分一并遮蔽。”",
    "P000194-B012": "问的人又说：“那么，其中值得肯定的说法究竟是什么？”",
    "P000195-B001": "回答说：“关键在‘乘生气’三个字。班固说，形与气彼此相连、首尾相应。这一说法抓住了形法的要点，也和《葬书》的意思相互表里。山川的起止、会合与分散，体现了形势和气机的相互作用，因此观察地形与观察宫宅、人物形貌，在古人看来出自同一套原则。后来杨、廖等术家把这套方法推演得更加精细。要真正理解它，必须能体察山川形态及其来去变化，不能只靠公式。事情虽然被人看作卑微，其中的道理却很细致；相关著作虽多，‘乘生气’三字已经概括了核心。”",
    "P000195-B002": "又有人问：“星本来是天象，术家却用星名来称呼山形，这符合《葬书》的本意吗？”",
    "P000195-B003": "回答说：“五行和阴阳是古人用来解释天地化育的体系，在天表现为象，在地表现为形；声音、颜色、外貌和形状也按类别相应。既然细小事物都被纳入这种分类，山岳这样巨大的形体当然也会被纳入。只要其中确有可说明的道理，不必要求每一种说法都直接出自古书。”",
    "P000195-B004": "问的人说：“直长的形状归为木，尖锐的归为火，曲折流动的归为水，这些我还能理解；为什么圆形归为金，方形归为土呢？”",
    "P000195-B006": "问的人又说：“有人说世间万事都以顺行为常，只有炼丹和地理讲求逆行，这是什么意思？”",
    "P000195-B007": "回答说：“人体五脏在古人观念中与天地相应，精气流行以滋养形体，阴阳交感以延续后代；其中包含相反力量的交互。天地之气在地中运行，滋润草木，又向上蒸腾形成光景，也依靠上下、内外的交互才能贯通幽明。理解炼丹术所说的‘逆’，也就能理解地理术怎样谈‘乘生气’；它并不只是给两种相对事物起一个名称。”",
    "P000213-B001": "《搜采异闻录》记载：当时民间营建住宅，稍遇疾病灾祸，往往就说是“犯土”，所以道家有谢土的章醮文书。按《后汉书·来历传》的记载，安帝时皇太子受惊后患病，居于宠幸的乳母野王君王圣之家。太子厨监邴吉认为王圣的住宅刚刚修缮，触犯土禁，不宜久住。作者据此认为，“犯土”的说法古已有之。",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def combined_reason(row: dict) -> str:
    return "；".join(str(x) for x in (row.get("issues") or []) + (row.get("uncertainty") or []) if str(x).strip())


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    blocks_path = MODERN / "blocks.jsonl"
    blocks = read_jsonl(blocks_path)
    repaired = []
    for block in blocks:
        if block["block_id"] in MANUAL_REPAIRS:
            before = block.get("modern_text") or ""
            after = MANUAL_REPAIRS[block["block_id"]]
            if before != after:
                block["modern_text"] = after
                block["review_status"] = "accepted_after_manual_semantic_repair"
                block["confidence"] = max(float(block.get("confidence") or 0), 0.9)
                block["manual_repair_v2"] = {"before": before, "after": after, "reviewed_at": now,
                                              "method": "source-bounded classical modernization"}
                repaired.append(block["block_id"])
    write_jsonl(blocks_path, blocks)

    # Always rebuild from the immutable modernization ledger.  Reading the
    # projected open-items file here makes a second run lose resolved records.
    legacy = read_jsonl(MODERN / "uncertainties.jsonl")
    candidates = []
    adjudications = []
    open_items = []
    seen_reason: dict[tuple[str, str], str] = {}
    for index, row in enumerate(legacy, 1):
        candidate_id = f"UC{index:06d}"
        reason = combined_reason(row)
        candidate = {
            "schema_version": "1.0", "candidate_id": candidate_id,
            "page_id": row["page_id"], "block_id": row["block_id"],
            "origin_stage": "modernized", "kind": "translation" if row.get("issues") else "terminology",
            "excerpt": str(row.get("source") or "")[:240], "reason": reason,
            "source_image": row.get("source_image"), "severity": row.get("severity", "medium"),
            "created_by": "migrated-v4-ledger",
        }
        candidates.append(candidate)
        key = (row["block_id"], re.sub(r"\s+", "", reason))
        if key in seen_reason:
            status, impact, rationale = "resolved_duplicate", "none", f"与 {seen_reason[key]} 重复。"
        elif row["block_id"] in MANUAL_REPAIRS:
            status, impact, rationale = "resolved_confirmed", "none", "已依据规范化原文完成保守白话修订。"
        elif any(word in reason for word in ("没有完成可验证", "误译", "增译", "篡改", "无依据", "错误", "偏离原意")):
            status, impact, rationale = "open_material", "high", "现有现代释读仍有实质语义风险，不能用提示框代替修复。"
        elif any(word in reason for word in ("缺", "残", "乱码", "无法辨认", "无法确定", "不完整")):
            status, impact, rationale = "open_material", "medium", "现有来源不足以支持唯一释读。"
        elif any(word in reason for word in ("具体所指不详", "未明", "不明确", "不确定")):
            status, impact, rationale = "open_material", "low", "专名或术语含义未能由本书材料唯一确定。"
        else:
            status, impact, rationale = "resolved_structural", "none", "属于审校评论或表达建议，不是未辨原文。"
        seen_reason[key] = candidate_id
        adjudication_id = f"UA{index:06d}"
        issue_id = f"UI{len(open_items)+1:06d}" if status == "open_material" else None
        if status == "open_material" and reason:
            rationale = reason[:360]
        adjudication = {
            "schema_version": "1.0", "adjudication_id": adjudication_id,
            "candidate_ids": [candidate_id], "status": status, "reader_impact": impact,
            "page_id": row["page_id"], "block_id": row["block_id"], "rationale": rationale,
            "evidence": [row.get("source_image")], "before": None, "after": None,
            "reviewed_at": now, "reviewer": "chaoyun-uncertainty-adjudicator",
        }
        if status == "resolved_confirmed":
            adjudication["modern_text_before"] = row.get("candidate")
            adjudication["modern_text_after"] = MANUAL_REPAIRS.get(row["block_id"])
        if issue_id:
            adjudication["issue_id"] = issue_id
        adjudications.append(adjudication)
        if status == "open_material":
            open_items.append({
                "schema_version": "1.1", "issue_id": issue_id,
                "adjudication_id": adjudication_id, "status": "open", "reader_impact": impact,
                "page_id": row["page_id"], "block_id": row["block_id"], "note": rationale,
                "source_image": row.get("source_image"),
            })
    write_jsonl(AUDIT / "uncertainty-candidates.jsonl", candidates)
    write_jsonl(AUDIT / "uncertainty-adjudication.jsonl", adjudications)
    write_jsonl(AUDIT / "uncertain-items.jsonl", open_items)

    events_path = AUDIT / "events.jsonl"
    existing = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    if '"event_id": "book001-editorial-rebuild-adjudication-v2"' not in existing:
        event = {"schema_version": "1.0", "event_id": "book001-editorial-rebuild-adjudication-v2",
                 "time": now, "actor": "codex", "operation": "adjudicate_and_repair",
                 "source_ids": repaired, "before": "delivered_B", "after": "revision_C",
                 "confidence": 0.9, "rationale": "Return known translation defects to modernization and separate raw candidates from material open items."}
        with events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    state_path = ROOT / "run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["updated_at"] = now
    state["current_stage"] = "modernized"
    state["grade"] = "C"
    state["stages"]["modernized"] = {"status": "passed_with_ledger", "blocks": len(blocks),
                                        "manual_semantic_repairs": len(MANUAL_REPAIRS), "open_material": len(open_items)}
    state["stages"]["edited"] = {"status": "running", "reason": "full editorial rebuild"}
    state["stages"]["publication"] = {"status": "pending"}
    state["stages"]["delivery"] = {"status": "revision_required"}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"repaired_blocks": len(repaired), "candidates": len(candidates),
                      "adjudications": len(adjudications), "open_material": len(open_items)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
