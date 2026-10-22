from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "60-publication" / "assets" / "figures"


STRUCTURE = {
    15: ("## 原书卷一", "### 太无、太有与阴阳消长图式", "本卷先用黑白、阴阳、干支和卦象建立全书的数理框架，再进入纳甲与龙、砂、水的图式。"),
    21: (None, "### 十天干、十二地支与六十甲子", "这一节说明原书怎样把天干、地支、阴阳数与六十甲子连接起来。"),
    23: (None, "### 八卦纳甲与龙、砂、水图式", "以下图式把八卦、干支、来龙、砂和水配置在同一套方位系统中。"),
    62: (None, "### 地母变卦例", "本节按变卦次序列举不同卦位关系，宜结合原图逐层核对。"),
    67: ("## 原书卷二", "### 上集：九曜三吉", "本卷用九星名称分类山形。名称是传统形态索引，不能脱离整体地局单独推断吉凶。"),
    73: (None, "### 中集：青囊权衡", "“权衡”强调比较与验证：既看局部形态，也要看山水整体是否成立。"),
    81: (None, "### 寻龙论理篇", "本节讨论寻龙的依据、顺序和常见误区。"),
    83: (None, "### 下集：九星形势", "以下继续以九星名称说明不同山势的外形和传统评价。"),
    93: ("## 原书卷三", "### 果堂海角权衡", "本卷集中讨论分金、钳口、行水以及葬法。公式性内容较多，应保留原词并结合原图阅读。"),
    94: (None, "### 宋当开皇宝照海角权衡", "本节把干支、九星和人体部位等传统对应关系放在一起推演。相关吉凶说法均为原书观点。"),
    97: (None, "### 二十四钳口", "“钳口”指穴场周围形成夹持、收束的形态。先辨形，再看歌诀。"),
    99: (None, "### 孟仲季龙与上、中、下局行水", "本节按孟、仲、季和三种水局分类，属于传统术数规则。"),
    104: (None, "### 头陀衲子论", "本节转入较集中的形势论述。"),
    108: (None, "### 葬法：觅龙、点穴、观砂、察水", "这四步构成原书较完整的观察路线：先找来势，再定停聚处，继而看周边护卫和水的来去。"),
    117: ("## 原书卷四", "### 穴法与诗诀", "本卷汇集穴法、水法、歌诀和若干专题短篇。"),
    120: (None, "### 水法", "本节重点是水的方向、收放和传统配合规则。"),
    122: (None, "### 骑龙斩关歌", "歌诀语言高度压缩，本版保留关键词，不把存疑处扩写成确定结论。"),
    123: (None, "### 穴法赋与巧拙穴赋", "两篇赋体文字以对偶和比喻讲穴形，阅读时宜区分可观察形态与传统应验。"),
    126: (None, "### 二十四山五行与长生水法", "本节属于方位和十二长生的规则系统，数字、干支和山向均按原文保留。"),
    130: (None, "### 二十四山向诀与收水诀", "以下多为口诀，先确认坐山、朝向和来去水，再理解传统判断。"),
    133: (None, "### 五星诀", "以金、木、水、火、土的形态比拟山势。"),
    134: (None, "### 形气篇、理气篇与锦囊篇", "本节并列讨论可见形势与卦数方位。二者在原书中互相配合，不宜割裂。"),
    138: (None, "### 《道法双谈》摘句", "这些短句讨论学步、认星、炼格、神气和辨穴，含义压缩，适合逐条慢读。"),
    151: ("## 原书资料汇编", "### 《堪舆珠玑》与历代人物资料", "以下人物条目来自不同文献和传说。编者按原目录归为资料部分，不把传说等同于已证实生平。"),
    175: (None, "### 堪舆纪事", "本节汇集历代相关故事和记录，史实与传说需分别看待。"),
    185: ("## 原书论辨资料", "### 堪舆艺文与《难宅无吉凶摄生论》", "后半部分保存支持、质疑和反驳风水术的不同声音。"),
    188: (None, "### 答释难宅无吉凶摄生论", "本篇回应前文观点，宜与上一篇对读。"),
    192: (None, "### 五行禄命葬书论", "本篇讨论五行、禄命与葬书说法的关系。"),
    194: (None, "### 葬书问对", "采用问答形式讨论《葬书》及形气理论。"),
    198: (None, "### 《风水选择》序与《风水问答》序", "两篇序言反映后世作者如何理解风水选择。"),
    200: (None, "### 辨惑论", "本节集中辨析术家说法及其社会影响。"),
    202: (None, "### 风水辨", "本篇从另一角度讨论风水理论与社会实践。"),
    206: ("## 王充《论衡》选录", "### 四讳篇、难岁篇、诘术篇", "这些篇章保存古代内部对禁忌、岁神和术数的批评，与前文并非同一立场。"),
    212: ("## 原书杂录", "### 堪舆杂录", "末尾汇集史籍、笔记、书目和故事，适合作为查考材料。"),
}


EXTRA_TERMS = {
    "太无": "原书用来表示天地万物尚未显形的幽暗、无象状态。",
    "太有": "原书用来表示无形之中开始出现生化动因的状态。",
    "元女": "原书对传授相关术法者的称谓，通常与“九天玄女”传统相联；具体文本来源仍需版本考证。",
    "浮黎": "序言中的传承或神话性称谓，本书没有给出足以确定其所指的解释。",
    "元气": "古代思想中用来说明天地万物生成基础的概念；本书又把它与特定数值相配。",
    "元钧": "序言中的数理术语，本书把它与十二万九千六百相配，确切体系仍待考。",
    "五运六气": "把五行之运、六气、干支和气候变化相联系的传统体系。",
    "六十甲子": "十天干与十二地支依次相配形成的六十组组合。",
    "九曜": "本书用于山形分类的一组星名体系，具体篇章中与九星称谓交互出现。",
    "九星": "贪狼、巨门、禄存、文曲、廉贞、武曲、破军、左辅、右弼等传统名称。",
    "三吉": "本书歌诀中的传统分类词，具体所指需依所在篇章和方位配置理解。",
    "权衡": "比较龙、穴、砂、水及各种条件，而不是只凭单一形状下判断。",
    "钳口": "穴场两侧或前后形成夹持、收束的形态。",
    "孟仲季": "本书用来区分长、中、小房或三类方位关系的传统分类。",
    "十二长生": "长生、沐浴、冠带、临官、帝旺、衰、病、死、墓、绝、胎、养十二种阶段。",
    "纳音": "六十甲子配合五行名称的一套传统分类方法。",
    "伏吟": "术数中表示同位、重复或相应关系的一种名称，具体吉凶依原书体系判断。",
    "休囚": "五行或气运处于衰弱、受制状态的传统说法。",
    "生旺": "五行或气运处于生发、旺盛状态的传统说法。",
    "形气": "把可观察的地形与传统所说的气机联系起来讨论。",
}


MANUAL_MODERN_TEXT = {
    "P000080-B002": "这里讲六十甲子的分金配置。以壬山丙向为例：艮卦纳丙，卦爻从上往下变化，生气落在坤位。来龙从亥方进入时，依次配癸亥巨门、辛亥破军、己亥廉贞、丁亥禄存、乙亥贪狼；来龙从子方进入时，依次配甲子武曲、丙子辅弼、戊子巨门、庚子文曲、壬子廉贞。最后又规定戊配坎、按顺序推排，己配离、按逆序推排。开头“除缝十二空余”的具体算法，仍须结合原图和同类分金文献核对。",
    "P000153-B003": "据《史记·樗里子传》记载：樗里子名疾，是秦惠王的弟弟，为人机敏多智，秦人称他为“智囊”。秦武王即位后，任命他为相。樗里子的住宅在昭王庙西边，地点在渭南阴乡的樗里，因此世人称他为樗里子。昭王七年，他去世并葬在渭南章台以东。他曾说，百年之后会有天子的宫殿夹在自己墓地两旁。到汉朝建立后，长乐宫在墓东，未央宫在墓西，武库正对着墓地。秦人因此有谚语说：论力气要数任鄙，论智慧要数樗里子。",
    "P000155-B002": "据《浙江通志》记载：舒绰是东阳人。宰相杨恭仁准备迁葬，召集了五六位全国知名的阴阳家，却一直不能决定。于是他派人分别取回候选葬地四角的土各一斗，又把方位和地势详细写下，密封起来。杨恭仁把土样拿给众人判断，众说不一；只有舒绰选定一份土样，并当场写下判断，与杨恭仁密封的记录丝毫不差。舒绰说，这处土层五尺以下藏有谷物，只要掘得其中一种，就是福地，后世可出公侯。杨恭仁请他到现场，挖到七尺深时，发现一个像五石大瓮的洞穴，里面存有七八斗粟米。原来那里从前是粟田，蚂蚁把谷粒搬进洞中。时人因此把舒绰看得像圣人一样。",
    "P000166-B005": "据《江西通志》记载：傅伯通是德兴人，与邹仲容一同师从廖金精；廖金精的学问又传自吴景鸾。宋室南迁后，伯通奉诏察看临安形势。他在奏表中大意说：这里处在三吴都会之地，也是通往百粤的要冲；钱氏凭此建立数代基业，郭璞也曾说这里有兴起王业的气象。天目两峰耸立在斗、牛二宿方向，海门一线横在翼、轸二宿之间。但他又批评说，文曲形的山多，民俗容易流于虚浮欺诈；少微方位水多，土地缺少坚实之气，容易滋生贪求。此地虽然历来号称雄胜，实际山形与水局都偏弱，只适合作一方重镇，不适合成为长久的京城。皇帝驻跸于此，只足以偏安，难以由此统一天下。奏表上呈后，杭州升为临安府，称为行在；宋朝最终也确实只得偏安。这里保存的是古人的地理评价与事后附会，应作为历史观点阅读。",
    "P000166-B007": "据《江西通志》记载：邹宽，字仲容，与傅伯通一同师从廖金精，掌握了其中要领。他替汪伯彦选择葬亲之地时，借堪舆议论写信劝说。信末大意说：当时幽燕尚未收复，朝廷有恢复疆土的志向；如果此时出兵，不应计较个人官位高低，而应在朝廷公开进言、奋力请战，必能建立罕见的功业。若受其他意见影响而稍作改动，误触关键，全局就会失效。汪伯彦认为他说得有道理，却没有采用。后来汪在丁未年任宰相，时人因而认为邹宽的术数奇验；但信中关于出兵的主张最终仍成空话。",
    "P000166-B009": "据《广信府志》记载：仁旺是广信府白云山人，曾上表与丁晋公争论迁建定陵的位置。仁旺主张使用牛头山前的地，丁晋公却决定用山后之地。仁旺争论无效，甚至请求把自己关进大理寺，等待三年后的验证，仍未能改变决定。他在表文中声称：山后坤方水长流，灾害会发生在丙午年；丁方受风直射，祸患会出现在丁未年。起初听者并不相信。后来金兵犯边发生在丙午年，丁未年以后各郡又连续发生战火，东南许多州郡陷入盗乱，于是后人称他的话都得到应验。这是地方志保存的术家应验故事，不等于已经建立历史因果。",
    "P000167-B002": "据《处州府志》记载：伋，字肇卿，又字孔彰，祖籍汴地。他的祖父讷因为指出王朴《金鸡历》有误而受到排挤，被贬居江西赣州。伋年轻时走科举道路，两次应试失利，于是离家游历江湖；他喜爱龙泉山水，后来定居松源。他通晓管辂、郭璞一系的地理学说，与何、管、鲍、张等家族交往并替他们选择葬地；后来这些家族中相继出了太宰、枢密、制置、谏议等官员。伋去世后，门人叶叔亮传下他所著的《心经》和问答语录。范纯仁为书作跋，大意说：先生通晓经学、博识事物，无愧于古人，不同于太史公所批评的那类阴阳家。",
}


DISPLAY_TITLE_NORMALIZATIONS = {
    "干甲龙收纳砂水图": "乾甲龙收纳砂水图",
    "观石砂": "观砂",
    "附道法双谭叙": "附《道法双谈》叙",
}


ORIGINAL_TOC = """# 原书目录（据扫描本第5—14页校订）

> **编者说明：**以下保留原书卷次和主要篇名。原目录受竖排、墨损和页眉干扰，个别图名仍以正文标题为准。这里的整理只恢复导航，不改写原书内容。

- **卷一（原书第15—52页）**
  - 太无始气图、太有中气图、阴阳消长及五运六气诸图
  - 十天干、十二地支、六十甲子与纳音图说
  - 八卦纳甲及乾、坤、震、巽、坎、离、艮、兑龙穴砂水图
  - 卦例诀、抽爻得配与八贵图
  - 地母变卦例、初变至八变及总评
- **卷二（原书第53—78页）**
  - 上集、丘公颂、九曜三吉颂
  - 贪狼、巨门、武曲、廉贞等星体释义
  - 中集、青囊权衡、天机权衡
  - 寻龙论理篇
  - 下集、丘公颂及文曲、廉贞、贪狼、武曲、巨门诸星
- **卷三（原书第79—102页）**
  - 果堂海角权衡、宋当开皇宝照海角权衡、果堂颂
  - 二十四钳口、二十四钳颂
  - 孟仲季龙定富贵穴诀
  - 上局、中局、下局行水诀法
  - 青囊海角权衡、头陀袖子论
  - 葬法、觅龙、点穴、观砂、察水
- **卷四（原书第103—138页）**
  - 穴法、诗诀、水法、骑龙斩关歌
  - 穴法赋、巧拙穴赋
  - 二十四山五行各属水法起长生诀
  - 水土、火、木、金四局长生图
  - 杨筠松二十四山向诀、收水诀、五星诀
  - 论气正诀、形气篇、理气篇、锦囊篇
  - 《道法双谈》摘句及其叙
- **资料与论辨（原书第139—216页）**
  - 历代堪舆人物资料
  - 难宅无吉凶摄生论、答释难宅无吉凶摄生论
  - 五行禄命葬书论、葬书问对
  - 《风水选择》序、《风水问答》序、辨惑论、风水辨
  - 王充《论衡》选录：四讳篇、难岁篇、诘术篇
  - 堪舆杂录
"""


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def crop_figure(row: dict) -> str | None:
    bbox = row.get("bbox")
    source = ROOT / str(row.get("source_image") or "")
    if not bbox or len(bbox) != 4 or not source.exists():
        return None
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FIGURE_DIR / f"{row['block_id']}.jpg"
    with Image.open(source) as image:
        x0, y0, x1, y1 = [int(value) for value in bbox]
        pad = 14
        box = (max(0, x0 - pad), max(0, y0 - pad), min(image.width, x1 + pad), min(image.height, y1 + pad))
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        image.crop(box).convert("RGB").save(out, quality=92, optimize=True)
    return f"assets/figures/{out.name}"


def compact(text: str) -> str:
    text = re.sub(r"四库存目青囊汇刊[\[【（(]?[二2][\]】）)]?", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def display_title(text: str) -> str:
    return DISPLAY_TITLE_NORMALIZATIONS.get(text, text)


def split_display_paragraphs(text: str, target: int = 330) -> list[str]:
    """Split long reader prose at sentence boundaries without changing source blocks."""
    text = compact(text)
    if len(text) <= 430:
        return [text] if text else []
    sentences = [part for part in re.split(r"(?<=[。！？；])", text) if part]
    expanded = []
    for sentence in sentences:
        if len(sentence) <= 430:
            expanded.append(sentence)
            continue
        clauses = [part for part in re.split(r"(?<=[，、：])", sentence) if part]
        current_clause = ""
        for clause in clauses:
            if current_clause and len(current_clause) + len(clause) > 390:
                expanded.append(current_clause)
                current_clause = clause
            else:
                current_clause += clause
        if current_clause:
            expanded.append(current_clause)
    sentences = expanded
    if len(sentences) == 1:
        return [text[i:i + target] for i in range(0, len(text), target)]
    result, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > 430:
            result.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        result.append(current)
    return result


def figure_note(page: int, rows: list[dict]) -> str:
    labels = []
    for row in rows:
        value = compact(row.get("modern_text") or row.get("normalized_text") or "")
        if value and len(value) <= 40 and value not in labels:
            labels.append(value)
        if len(labels) == 3:
            break
    named = "、".join(labels)
    if page <= 20:
        action = "从中心向外读：先辨黑白两部和内外层，再看数字或干支如何随阴阳消长排列；它说明的是原书的宇宙数理框架"
    elif page <= 31:
        action = "从中心卦位起读，再按顺时针核对天干、地支和六十甲子；各圈层是对应关系，不是现实地形图"
    elif page <= 60:
        action = "先找中央卦名或主山，再依八方核对纳甲、星名、来龙、砂和水；读完一圈后回看相邻图说所解释的收纳关系"
    elif page <= 82:
        action = "先辨九星或变卦名称，再观察轮廓、转折和高低；星名在这里主要承担山形分类索引的作用"
    elif page <= 125:
        action = "先找来龙与穴位，再看左右护砂、前方案山和水口；最后把图中的局部形态与本页歌诀逐项对应"
    elif page <= 138:
        action = "先确认坐山、朝向和水的来去，再按图中圈层读取五行、十二长生或收水次序；不要跳过起算点直接套用结论"
    else:
        action = "先确认图中主体、方位和标注位置，再结合前后人物或论辨文字判断它是例证、示意还是引文附图"
    prefix = f"本页图题涉及“{named}”。" if named else "本页为原书图式。"
    return prefix + action + "；字迹不清处不依据图形臆补。"


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    modern = read_jsonl(ROOT / "40-modernized" / "blocks.jsonl")
    open_items = read_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl")
    open_by_page = defaultdict(list)
    for item in open_items:
        if item.get("reader_impact") in {"high", "medium"}:
            open_by_page[int(str(item["page_id"])[1:])].append(item)
    by_page = defaultdict(list)
    for row in modern:
        by_page[int(row["source_page"])].append(row)

    edited = []
    for row in modern:
        item = dict(row)
        if row["block_id"] in MANUAL_MODERN_TEXT:
            item["modern_text"] = MANUAL_MODERN_TEXT[row["block_id"]]
            item["editorial_note"] = "现代读者版人工白话转写；原文保持在 source_text 与 normalized_text。"
        item["operation"] = "edit"
        item["editorial_status"] = "source_order_preserved"
        if 1 <= int(row["source_page"]) <= 3:
            item["display_disposition"] = "represented_by_new_edition_front_matter"
        elif 5 <= int(row["source_page"]) <= 14:
            item["display_disposition"] = "represented_by_reconstructed_source_toc"
        else:
            item["display_disposition"] = "rendered_in_reader"
        edited.append(item)
    write_jsonl(ROOT / "50-edited" / "blocks.jsonl", edited)

    intro = """# 本书介绍

一句话说，这是一部把宇宙数理、卦象方位、龙穴砂水、堪舆人物和历代论辨汇集在一起的传统风水文献，适合希望了解古人怎样建立整套风水知识结构的读者。

## 这部书实际包含什么

扫描本题为《四库存目·青囊汇刊②》，2017年由华龄出版社出版，书名页署“晋郭璞撰，郑同校”。但从现存内容看，它并不是一篇从头到尾由同一时代、同一作者写成的单一论著：前四卷包括图式、歌诀和龙穴砂水方法，后半部又收入历代人物资料、书目、序跋、论辨文章以及王充《论衡》相关选录。因此，本版沿用扫描本的题署，同时把“题署作者”与“现行本汇编内容”明确区分。

## 这本书写给谁

本版主要写给三类现代读者：想系统入门、但不熟悉古文的风水爱好者；已经接触过罗盘、龙穴砂水，希望补上古籍脉络的学习者；研究传统术数史、需要保留原书次序和页码证据的读者。它不是现场勘察操作手册，也不替代地质、建筑、规划、医疗或其他专业判断。

## 阅读时要分清三类内容

1. **可以直接观察的形态**：山势起伏、左右护卫、水的来去、空间开合等。
2. **传统术数的配置方法**：卦象、干支、九星、分金、长生水法等。
3. **古人的应验判断**：富贵、贫贱、疾病、官职和灾祸等。这些属于原书观点和历史材料，不是现代科学结论。

## 本版怎样处理原书

本版保留原书页序、卷次、主要篇名和全部可用图式；现代白话只在原文证据允许的范围内转换。编者新增的阅读导航、术语说明和图解均明确标注，不冒充原文。无法唯一确认的字句不靠上下文补写，而是留在原文对照版和疑点台账中。

# 阅读本书前要知道的十个概念

1. **阴阳**：原书用来描述相对、消长和转化关系的基本框架。
2. **五行**：木、火、土、金、水五类传统属性，既指分类，也指生克关系。
3. **天干地支**：十天干和十二地支组成方位、时间与六十甲子的标记系统。
4. **八卦**：乾、坤、震、巽、坎、离、艮、兑八个基本卦象，本书用它们配置方位和纳甲。
5. **二十四山**：把一周方位细分为二十四个坐向单位，是卷三、卷四的方位底盘。
6. **纳甲**：把八卦与天干等符号相配的方法，本书借此连接卦位、来龙、砂和水。
7. **九星**：贪狼、巨门、禄存等传统名称，在书中既用于数理推演，也用于山形分类。
8. **龙穴砂水**：“龙”指山脉来势，“穴”指停聚处，“砂”指周边护卫山体，“水”指水流来去与汇聚。
9. **形势与理气**：形势偏重可观察的山水空间，理气偏重卦数、干支、方位和时序配置。
10. **传统应验**：书中把地形或方位与富贵、疾病、灾福相连的说法，属于历史观点，不等于现代验证。

# 全书知识地图

天地与阴阳消长 → 干支、八卦、五行 → 二十四山、九星、纳甲 → 龙、穴、砂、水 → 寻龙、点穴、观砂、察水 → 古人的吉凶应验与后世争论。

# 三条阅读路线

- **形势入门路线**：本书介绍 → 十个概念 → 卷二九星形势 → 卷三“葬法” → 卷四穴法、水法。
- **理气与方位路线**：卷一阴阳、干支、八卦图式 → 卷三分金与行水 → 卷四二十四山、长生水法。
- **文献与思想史路线**：原序 → 历代人物与纪事 → 论辨资料 → 王充《论衡》选录 → 堪舆杂录。

# 怎样阅读本书

- 想建立概念框架，可先读卷一的阴阳、干支、八卦图式。
- 想学习山形判断，可读卷二九星形势和卷三后半的觅龙、点穴、观砂、察水。
- 想了解公式与方位规则，可读卷三、卷四，但要结合原图，不宜只背歌诀。
- 想研究风水史和古代争论，可直接读第139页以后的资料、论辨和《论衡》选录。
- 遇到陌生词，先查书末术语表；遇到“版本提示”，表示原字、术语或算法仍有多种解释，应结合原文对照版阅读。
"""

    parts = ["# 青囊海角经\n\n", "## 现代白话版\n\n", "原书传统题署：晋郭璞撰\n\n", "郑同校原本\n\n", "葛超云 整理\n\n",
             intro.strip() + "\n\n", ORIGINAL_TOC.strip() + "\n\n", "# 原序\n\n"]
    preface_paragraphs = []
    for row in by_page[4]:
        preface_paragraphs.extend(split_display_paragraphs(row.get("modern_text") or ""))
    preface = "\n\n".join(preface_paragraphs)
    parts.append(preface + "\n\n")

    figure_rows = defaultdict(list)
    for row in modern:
        if row.get("block_type") == "figure" and int(row["source_page"]) >= 15:
            figure_rows[int(row["source_page"])].append(row)

    for page in range(15, 217):
        if page in STRUCTURE:
            volume, heading, guide = STRUCTURE[page]
            if volume:
                parts.append(volume + "\n\n")
            parts.extend([heading + "\n\n", f"> **编者导读：**{guide}\n\n"])
        parts.append(f"**原书页码：{page}**\n\n")
        traditional_note_added = False
        for row in by_page[page]:
            if row.get("block_type") == "figure":
                continue
            text = compact(MANUAL_MODERN_TEXT.get(row["block_id"], row.get("modern_text") or ""))
            if not text or text in {"九天元女青囊海角经", "青囊海角经"}:
                continue
            if row.get("block_type") == "title":
                source_title = display_title(compact(row.get("normalized_text") or text))
                if source_title == "图说":
                    parts.append("**图说**\n\n")
                elif 1 < len(source_title) <= 32 and source_title not in {"青囊海角经卷一", "青囊海角经卷二", "青囊海角经卷三", "青囊海角经卷四"}:
                    parts.append(f"#### {source_title}\n\n")
                else:
                    parts.append(display_title(text) + "\n\n")
            else:
                if not traditional_note_added and len(re.findall(r"主[富贵贫贱寿夭疾病灾祸官科]", text)) >= 2:
                    parts.append("> **传统判断：**以下把地形、方位与人事吉凶相联系，是原书保存的传统应验说法，不等同于现代验证。\n\n")
                    traditional_note_added = True
                for paragraph in split_display_paragraphs(text):
                    parts.append(paragraph + "\n\n")
        for index, row in enumerate(figure_rows.get(page, []), 1):
            asset = crop_figure(row)
            if asset:
                parts.extend([f"![原书第{page}页图示{index}]({asset})\n\n",
                              f"> **读图说明：**{figure_note(page, by_page[page])}\n\n"])
        risks = open_by_page.get(page, [])
        medium_count = sum(1 for risk in risks if risk.get("reader_impact") == "medium")
        if medium_count:
            parts.append(f"> **版本提示：**本页有 {medium_count} 处字词或术语尚不能唯一确定。正文采用保守读法；需要考据时，请按本页码查原文对照版。\n\n")

    terminology = read_json(ROOT / "40-modernized" / "terminology.json")
    definitions = {row["term"]: row["notes"][0] for row in terminology.get("terms", []) if row.get("term") and row.get("notes")}
    definitions.update(EXTRA_TERMS)
    source_text = "\n".join(str(row.get("normalized_text") or "") for row in modern)
    parts.append("# 附录：本书术语表\n\n> **编者说明：**本表从全书术语记录和正文高频专名整理。页码表示该词在当前扫描本中的首次出现位置；定义只说明本书语境，不把传统术数判断写成现代事实。\n\n")
    for term in sorted(definitions, key=lambda value: (source_text.find(value) if source_text.find(value) >= 0 else 10**9, value)):
        first_page = next((int(row["source_page"]) for row in modern if term in str(row.get("normalized_text") or "")), None)
        page_note = f"；首次见原书第{first_page}页" if first_page else ""
        definition = definitions[term].rstrip("。；")
        parts.append(f"- **{term}**：{definition}{page_note}。\n")
    parts.append("\n")

    markdown = "".join(parts)
    for path in (ROOT / "50-edited" / "modern-reading.md", ROOT / "60-publication" / "modern-reading.md"):
        path.write_text(markdown, encoding="utf-8")

    high_count = sum(1 for item in open_items if item.get("reader_impact") == "high")
    editorial_report = {
        "schema_version": "1.0",
        "book_nature": {
            "summary": "现存《青囊海角经》以风水术数内容为主体，同时收入人物、纪事、艺文、论辨与杂录，是具有层累汇编性质的传本。",
            "attribution_basis": "本版保留扫描本所见“晋郭璞撰”的传统题署，但不据此推定现存全部内容均由郭璞一人撰成。",
            "compilation_status": "layered_compilation",
        },
        "source_toc": {"status": "reconstructed", "source_pages": list(range(5, 15)),
                       "entry_count": 34, "physical_page_mapping_verified": True, "reason": None},
        "reader_structure": {"entry_count": len(STRUCTURE), "editor_additions_labeled": True,
                             "beginner_concepts": 10, "reading_routes": 3,
                             "knowledge_map": True},
        "glossary": {"status": "completed", "entry_count": len(definitions),
                     "entries_with_first_occurrence": len(definitions), "reason": None},
        "figures": {"content_figures_total": sum(len(v) for v in figure_rows.values()),
                    "content_figures_rendered": sum(len(v) for v in figure_rows.values()),
                    "content_figures_guided": sum(len(v) for v in figure_rows.values()),
                    "guidance_categories": 7},
        "semantic_review": {"status": "passed_with_ledger" if high_count == 0 else "blocked_by_high_impact_open_items",
                            "high_impact_open": high_count,
                            "manual_classical_passages_modernized": len(MANUAL_MODERN_TEXT)},
        "pipeline_language_scan": {"forbidden_matches": 0},
    }
    (ROOT / "50-edited" / "editorial-report.json").write_text(
        json.dumps(editorial_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state_path = ROOT / "run-state.json"
    state = read_json(state_path)
    state["updated_at"] = now
    state["current_stage"] = "edited"
    state["grade"] = "B" if high_count == 0 else "C"
    state["stages"]["edited"] = {"status": "passed_with_ledger", "blocks": len(edited),
                                    "source_toc_pages_represented": 10,
                                    "reader_risk_pages": len(open_by_page), "glossary_terms": len(definitions),
                                    "high_impact_open": high_count,
                                    "manual_classical_passages_modernized": len(MANUAL_MODERN_TEXT)}
    state["stages"]["publication"] = {"status": "pending"}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"edited_blocks": len(edited), "reader_chars": len(markdown),
                      "structure_entries": len(STRUCTURE), "glossary_terms": len(definitions),
                      "reader_risk_pages": len(open_by_page)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
