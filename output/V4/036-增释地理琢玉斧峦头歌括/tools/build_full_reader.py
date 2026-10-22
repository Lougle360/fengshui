#!/usr/bin/env python3
"""Build a clean full-book reading layer from audited page records."""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "90-audit"
BOOK_ID = "a8905dff46683b57"
SOURCE_SHA = "a8905dff46683b57b0bf695c8263c0a098b4ef0106e571564f6a1c898b970a06"

MANUAL_READER = {
    11: "本图列出丁字帐格、出帐贵人、入帐贵人以及阳峡等形态，用来辨认山势在过峡、开帐时的不同格局。",
    12: "本图比较几种只有迎山、缺少送山的峡形，其中包括膝峡、鹤峡等格局，用来观察峡脉两侧山势是否彼此迎送。",
    13: "本图继续说明峡脉的迎送关系，包括曲峡、双迎双送和峡涧等形态。判断重点是峡脉两侧是否有山势呼应和护送。",
    14: "本图比较来势大小和去势方向：来大去小称为倒峡；来小去大，以及正来侧去，则属于另一类过峡形态。",
    15: "本图汇集玉池峡、石峡等峡形，用来说明寻龙时应如何观察山脉经过狭窄处时的形态与方向。",
    16: "本图列出正出水峡、偏出水峡，以及若干崩洪峡格。它们用于辨认过峡处水流的位置和山体崩裂的形态。",
    17: "本图继续列举多种崩洪形态。原图部分题名受印章和刻印影响，阅读时以图形所表现的山体裂隙、交角和走势为主。",
    18: "石梁过水一类的峡形，旧说大致分为十种。廖氏认为：山脉与流水并行时，龙脉不容易辨认；如果石面留下明显的脉路痕迹，古人便把这种形态称为‘崩洪’。东湖主人进一步解释，寻龙当然要观察开帐和过峡，但不能只背诵格局名称。既要懂得一般规则，也要能够根据现场变化判断龙脉的真假、行止和大小。只懂规则而不知变化，容易拘泥；只谈变化而没有规则，也无从验证。",
    19: "看地有一个根本要求：必须知道自己的判断依据。依据清楚，山水的关系就容易理解；没有依据，即使谈论很多吉凶，也只是自欺欺人。前人已经把不少方法写在书中，只因许多人匆匆读过，不肯深入求证，才把本来可以学习的方法说成不可传的秘密。若问一处地形好在哪里，有人会说砂山秀丽、水势有情，也有人强调来龙高耸、活动有力。两种说法都抓住了一部分，但都不能脱离整体地局。",
    20: "重视来龙的人认为：龙脉是地局的根本；即使周围砂水看起来不错，如果来龙虚弱、反背，也难以形成完整格局。这一观点有道理，因为穴场能否凝聚，确实要看龙脉怎样行来、在哪里停住。不过，只说‘重龙’还不够，还必须回答三个问题：怎样分辨龙脉的美恶？怎样分辨真假？怎样判断它继续前行还是已经止息？如果不能说明这些观察方法，只会笼统地说龙脉重要，仍然不能用于现场判断。",
    24: "点穴之前，先要理解‘四落’：初落、青落、末落和分落。初落靠近祖山，要求局势完整、气势宽展；青落利用余枝形成护卫；末落位于龙脉将尽之处，通常要求来势有力，避免风吹水劫；分落则从后龙分出支脉，但支脉必须前后贯通。所谓‘有落皆可作’，不是说任何位置都能取穴，而是提醒学习者：先判断龙脉以哪一种方式停落，再讨论穴位。",
    28: "观察穴场，要看前、后、左、右四面的整体形势，古人称为‘四势’。前后空旷，容易受到直风；左右凹缺，护卫便不完整，所以穴场周围贵在有围合、有补缺。罗城又分内外：靠近穴场的内罗城宜紧密、周全；更外围的山势不必强求处处整齐，但仍要看整体是否聚合。判断时应先看大势，再比较大小、聚散、高低和偏正，不能只因某一座山好看就下结论。",
    29: "判断地局，首先看整体是否完整而不紊乱，水流能否回环收聚。来势短、去势长，或者表面局部聚合、远处大势却四散，这类地形往往只有小聚而没有真正的收束。石山粗露、水声急响，也常被古人视为难以凝聚。相反，如果四周山水共同向中心会合，即使局部略有瑕疵，也应先看大势是否成立。正如古语所说：只有一山一水略显有情，格局仍小；真正重要的是较大的山水形势能否进入同一个局面。",
    30: "许多人容易犯两种错误：一种是只看见局部优点，忽略整体缺陷；另一种是在许多明显问题中勉强寻找一点吉处。这就像从管子里看豹，或爬到树上找鱼。前人说，山势如果漫无回顾，即使前方偶有秀丽山峰，也可能只是空有外形；大势真正收聚时，奇形怪穴也可能成立，大势涣散时，再巧妙的局部形状也可能落空。地势高昂而堂局狭窄，取穴宜相对高处；四周平缓而空间开阔，则宜从低处寻找收聚点。",
    31: "本图说明第四种天财，名为‘弓脚平腾天财’。它的主要特征是山脚向两侧弯伸，主体横来，后方仍有承托。歌诀用‘龙咬尾’比喻山势前后相接，并把这种完整形态与家业兴盛联系起来。图中其余小字是在比较木、土、金、火等轮廓组合，阅读时以主体和两侧山脚的关系为主。",
    32: "本图比较第五种‘双臂天财’和第六种‘单股天财’。双臂指左右两侧都有伸展的山脚，像双臂环抱；单股则只有一侧山脚明显伸出。图中又列出左右仙弓、交牙等变化，用来说明同一种基本形态可以向左或向右偏转。判断重点是主体是否平稳、后方是否有托、伸出的山脚是否朝向并护卫穴场。",
    33: "本图说明第七种‘侧脑天财’。所谓侧脑，是主体中心偏向一侧，穴位也可能随山势落在侧边。图中以睡象、骆驼饮水等形象帮助记忆，并列出左垂、右垂、左转、右转、左单提、右单提等变化。学习时要比较左右偏侧和山脚转向，不要拘泥于动物名称。",
    34: "本图列出正格、左右摇拳、左右叠指、左右鞍、左右纽会等穴形，并说明第八种天财称为“没骨”。判断这类穴形时，重点不在寻找突起，而在观察山势运行中的落穴方向。",
    35: "本图说明第九种‘平面天财’。它的主体较为平展，古人认为土形是否端正、四边是否协调尤其重要；如果整体近似方盘，中心又有收聚，才符合歌诀所说的基本轮廓。图中列出的上下、左右、曲尺、吐舌等小形，是在比较边缘怎样伸缩和转折。",
    36: "本页对前面的天财穴形作归纳。前五种被原书列为传统吉形，并分别有勾脚、垂脚、吐脚、左右摆转等变化；后四种被列为传统凶形，每类只画一个代表。这里的‘吉’‘凶’属于原书分类，读者应先辨认曲尺、金斗、方盘、一字等轮廓，再结合来龙、护砂和水势判断整体，不能只凭单幅图定论。",
    37: "本页开始介绍‘天罡九变’。天罡是古人归纳的一组较刚硬、险峻的穴形，其中并非全部都被判为凶。第一种正体天罡近似车盖，歌诀认为形势刚猛；第二种开口天罡的主体出现开口，如果转折和水势配合，传统上也可能赋予较高评价。这里的军功、贫富等说法，是古代歌诀的应验语言。",
    38: "本页继续列举天罡变化。悬乳天罡有向下伸出的乳状部位；弓脚天罡的山脚弯伸；双臂天罡左右展开，像双臂或鸟翼。原书分别把这些形态与不同人物、功名联系起来。现代读者应把注意力放在主体、开口、伸脚和左右对称关系上，不必把歌诀当作确定预测。",
    39: "本页列出单股、侧脑和没骨三种天罡。单股只有一侧山脚突出；侧脑的中心偏向一侧；没骨则缺少明显突起，穴位要从山势转动和停聚处寻找。歌诀对这些形态既有警告，也有正面评价，说明名称本身不能决定吉凶，还要看具体组合。",
    40: "本页先介绍第九种平面天罡，形态低平而带有尖硬起伏；随后转入‘孤曜九变’。孤曜同样是一组穴形名称，第一种正体被比作倒扣的磬。原书对某些孤曜形态有严厉的凶险判断，同时又认为开口或生金等变化可能出现可取之处。阅读时先比较正体和变体，不要把象形名称直接等同于现实命运。",
    44: "龙脉行来时，常有周围山势随从护卫；穴后以及左右起关拦作用的山，属于砂的一部分。书中认为，穴场要形成收聚，既要有来龙，也要有砂山会合：砂若反背、冲克，水流便容易散去，穴前空间也难以收束。因此，所谓‘拨砂’，不是移动山体，而是通过定穴、定向和辨认方位，判断不同砂山在这个地局中的作用。作者批评只会说‘拨砂’而不能说明观察方法的人。",
    45: "古人把砂称为龙穴的‘用神’，意思是砂山承担护卫穴场、关拦水口、遮挡强风和帮助空间收聚的作用。没有砂山随从，来龙容易显得孤露；穴场没有砂山会合，周围便缺少环抱；水口没有砂山关拦，水势也容易直去。书中把这几种关系概括为：砂飞则水走，风入则气散。现代读者应把这一段先理解为空间围合关系，再阅读后面的传统吉凶评价。",
    46: "砂有不同位置和形态。穴前的朱雀、左右的青龙白虎、穴后的玄武，都可能纳入砂法观察。真正需要‘拨’的，是相对穴场具有明确方位和作用的坐立砂，而不是泛指远处一切山丘。观察时可以反过来验证：如果穴位选择合理，周围砂山应当呈现相对稳定、呼应的关系；如果砂山显得杂乱飞散，也可能说明所取穴位或朝向不合适。因此，砂既可以用来判断穴，也可以帮助校正穴位。",
    47: "看砂先要分清它的形态与朝向。古人给某些山形取名为金钟、仙桥、文笔等，是为了帮助记忆轮廓。然后再结合穴向和方位，判断这座砂在特定地局中属于生旺、泄气还是冲克。书中以‘文笔砂’为例，说明同一座山形在不同方位和朝向中，传统评价可能完全不同。由此可见，砂的名称不能单独决定吉凶，必须放回整个龙、穴、砂、水关系中理解。",
    48: "作者用同一条亥龙、丙向的假设说明拨砂思路：如果巽方有高起之砂，传统上可能赋予较高评价；巽砂低平或缺失，评价便会改变。即使同样有巽砂，采用不同坐向和分金，古法仍会给出不同判断。这些举例的重点，不是让读者机械套用官职、财富或贫贱的预言，而是说明：砂山的作用取决于它与穴位、朝向和其他山水之间的相对关系。",
    49: "所谓拨砂，第一步仍然是‘看’：看形体，也看情意。形体包括方、圆、直、曲、尖、危以及高低远近；情意则看山势是否朝向、环绕和呼应穴场。古人又用九星名称归纳常见轮廓，例如太阳形似覆钟，圆而较高；太阴形似卧弓，圆而较低。学习这些名称时，应先观察轮廓，再理解分类，不能从名称直接跳到吉凶结论。",
    50: "本页继续列举砂形：三台、紫气、贵人、天财、玉案、天马、御屏、天罡、孤曜等。它们都是用熟悉事物比拟山峰轮廓的传统名称。例如玉案多指中间较低、两端较高的形态；御屏强调顶部和主体较为分明。判断时还要比较砂体的高低、远近和肥瘦：过高又近，容易形成压迫；过高而远，影响较弱；过低则要看是否仍与穴场形成呼应。",
    72: "水面平静、环护穴场，是书中所称‘卫身水’较理想的状态。江河、湖海、溪涧和田渠都可能形成这种护卫，但前提是穴场本身稳固，周围能够藏风收聚，不因水面过大而显得孤露飘荡。随后原书开始分类讨论不同水体。首先是海潮水：古人认为大水汇聚之处也可能是大干龙脉停止之处，并把潮水的形态与地方盛衰联系起来。歌诀尤其重视潮头舒缓、颜色明亮和水势回环。",
    73: "原书列举昆山、泉州、仙游、莆田等地的故事，说明作者相信潮水能否到达城邑，会影响一地的兴衰和人才。又以余姚孙氏、王阳明祖地为例，把穴前潮水会合作为家族显贵的解释。这些记载体现了古代风水著作常用历史人物和地方传说验证理论的写法。现代读者可以保留其文献意义，但不能据此认定潮水与个人成就之间存在确定因果。",
    74: "原书接着引用歌诀和王阳明家族的经历，认为其功名符合旧日地记，由此证明海潮水的应验。这属于作者的传统解释。随后转入黄河水：黄河源远流长，两岸形成洛阳、平阳、安邑、蒲坂等重要城邑，因此古人把它与天下大势联系起来。书中还记录了‘黄河清，圣人出’的古代谚语，把河水偶尔变清解释为政治祥瑞。",
    75: "讨论江水时，原书把长江视为众水汇聚的大水系，认为水势虽然浩大，仍以弯曲环抱、流势凝缓为佳，并以南京临长江而兴盛作为例证。随后转入湖水。这里需要区分两层内容：水体规模、弯曲和流速是可以观察的形态；所谓祥瑞、王气和圣人出世，则属于古代文化中的象征解释。",
    76: "湖泊是多条水流汇聚之处。原书引用吴越王钱镠与西湖筑坝的传说，说明作者把湖水工程与政权长短联系起来。接着讨论溪涧水：大干龙脉多靠近江河湖海，较小支脉则可能在溪涧之间停聚。因此观察溪涧时，要看水流是否弯曲、环绕、汇聚、深缓；直急、有声、陡跌的水流，在传统上通常被认为不利于收聚。",
    77: "书中把散漫、满溢而缺少明确流路的水称为‘悲泣水’，传统上认为不利。所谓平田水，并不是积水散在田地中，而是田埂和浅水形成层层向前、平缓延伸的走势。它应当流势悠缓，不直冲、不穿割，也不夹带突兀山煞。若田水从正面层层朝向穴场，左右又有呼应，古人称为‘仓板水’，并把它与财富聚集联系起来。",
    79: "池塘水不拘方、圆或长形，原书更重视位置是否端正、水岸是否弯抱。如果池塘歪斜反背，又处在传统上认为不利的方位，书中称为‘照盆煞’，并附有严厉的家族应验说法。这些应验属于古代判断，不宜作为现代改造池塘的直接依据。接着原书讨论明堂：堂局不必拘泥于方形或圆形，关键是整体平正、洁净、有收束；过度偏斜、穿割或空荡，都被认为会破坏完整性。",
    80: "如果左边窄、右边宽，形势偏右，小房较为有利；如果右边窄、左边宽，形势偏左，长房较为有利，这叫作“偏”。丙子年，我与无锡陈掌衡同看一处祖坟，原处荒芜散乱，毫无收束。我带他转到左边较开阔之处，那里龙势虽然不算繁盛，堂局却能够藏聚，地形方正、圆润、平整而洁净。我告诉他：这样的地方自然能够聚福，选择地势就应当重视整体收聚，不能只贪图旷野开阔。",
}

FIGURE_PAGES = set(range(11, 18)) | {25, 26, 27, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 70, 71}

CANONICAL_TITLES = {
    23: ("卷三", "點穴歌", "点穴歌"),
    43: ("卷四", "撥砂歌", "拨砂歌"),
    65: ("卷五", "鑑水歌", "鉴水歌"),
}

READER_RISK_NOTES = {
    14: "原图右侧有裁切或模糊区域，白话说明只概括能够确认的两种峡形。",
    26: "本页竖排图题有高风险释读项，请结合所附原图核查，不据语义强补。",
    34: "本页右列有两处字迹无法可靠辨认，白话说明仅保留可确认的穴形关系。",
    53: "本页部分图中文字细小或受版面影响，名称以可辨轮廓为主。",
    55: "本页图题存在残缺，白话说明没有补写无法确认的字。",
    60: "本页个别贵人砂图题辨识风险较高，请以原图形态为主要证据。",
    71: "本页图示部分标注不清，白话说明只解释三层分合的整体关系。",
    80: "现存扫描在本页末尾中断，原书后续内容不在本次来源中；末句不完整，本版不作续补。",
}


def load_curated() -> dict[int, dict]:
    path = ROOT / "tools" / "build_curated_sample.py"
    spec = importlib.util.spec_from_file_location("curated", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return {int(row["page"]): row for row in module.PAGES}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def clean_reader_text(text: str) -> str:
    text = text.replace("本页句子未完", "").replace("〔图书〕", "").replace("〔圖書〕", "")
    text = re.sub(r"〔(?:疑|缺)[^〕]*〕", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" \n")


def repair_volume_title(page: int, source: str, normalized: str, modern: str) -> tuple[str, str, str]:
    if page not in CANONICAL_TITLES:
        return source, normalized, modern
    volume, traditional_topic, simplified_topic = CANONICAL_TITLES[page]
    source_tail = source.split(volume, 1)[1] if volume in source else ""
    normalized_tail = normalized.split(volume, 1)[1] if volume in normalized else ""
    source = f"嚴陵張九儀增釋地理琢玉斧巒頭歌括 {volume}{source_tail}"
    normalized = f"严陵张九仪增释地理琢玉斧峦头歌括 {volume}{normalized_tail}"
    modern = f"《地理琢玉斧峦头歌括》{volume}，由严陵张九仪增释。本卷主题为“{simplified_topic}”。题署所列参订者姓名部分受刻印和版面影响，完整字样请在原文对照版中核查。"
    return source, normalized, modern


def uncertainty_record(note, page_id: str, block_id: str, source_image: str) -> dict | None:
    if isinstance(note, dict):
        reason = str(note.get("reason") or "")
        excerpt = str(note.get("excerpt") or "")
        severity = str(note.get("severity") or ("high" if "无法" in reason or "缺" in excerpt else "medium"))
        nonbody = any(word in reason + excerpt for word in ("印章", "馆藏", "圖書館", "图书馆", "藏书"))
        status = "resolved_nonbody" if nonbody else "open"
        return {"schema_version": "1.0", "page_id": page_id, "block_id": block_id,
                "severity": "low" if nonbody else severity, "status": status, "note": note,
                "source_image": source_image}
    text = str(note).strip()
    if not text or not any(word in text for word in ("无法", "模糊", "残缺", "不确定", "缺损", "裁切", "暂定")):
        return None
    nonbody = any(word in text for word in ("印章", "馆藏", "圖書館", "图书馆", "藏书章", "馆藏章"))
    return {"schema_version": "1.0", "page_id": page_id, "block_id": block_id,
            "severity": "low" if nonbody else ("high" if "无法" in text or "残缺" in text else "medium"),
            "status": "resolved_nonbody" if nonbody else "open", "note": text,
            "source_image": source_image}


def main() -> int:
    curated = load_curated()
    pages: dict[int, dict] = {}
    for path in AUDIT.glob("vision-pass2*.jsonl"):
        for row in load_jsonl(path):
            pages[int(row["source_page"])] = row
    refinements = {int(row["source_page"]): row for row in load_jsonl(AUDIT / "reader-refinements.jsonl")}
    chapter_edits = {int(row["source_page"]): row for row in load_jsonl(AUDIT / "reader-chapter-edits-122b.jsonl")}
    if sorted(pages) != list(range(1, 81)):
        raise SystemExit("visual evidence does not cover source pages 1-80")

    source_rows, normalized_rows, modern_rows, edited_rows = [], [], [], []
    uncertainty_rows = []
    reader_pages: dict[int, str] = {}
    for page in range(1, 81):
        page_id = f"P{page:06d}"
        block_id = f"{page_id}-B001"
        visual = pages[page]["result"]
        if page in curated:
            source = curated[page]["source"]
            normalized = curated[page]["normalized"]
            modern = curated[page]["modern"]
            confidence = curated[page]["confidence"]
            notes = list(curated[page]["uncertainty"])
            block_type = curated[page]["type"]
        else:
            source = visual.get("faithful_source_text", "").strip()
            normalized = visual.get("normalized_text", source).strip()
            refined = refinements.get(page, {}).get("result", {})
            modern = refined.get("modern_text") or visual.get("modern_text", "")
            confidence = 0.95 if refined or visual.get("confidence") == "high" else 0.85
            notes = list(visual.get("uncertainties") or [])
            note = refined.get("editor_note")
            if note:
                notes.append(note)
            block_type = refined.get("page_role", visual.get("page_type", "body"))
        modern = chapter_edits.get(page, {}).get("modern_text", modern)
        modern = MANUAL_READER.get(page, modern)
        modern = clean_reader_text(modern)
        source, normalized, modern = repair_volume_title(page, source, normalized, modern)
        if page == 9 and modern.endswith("。时"):
            modern = modern[:-1]
        if page == 79 and modern.endswith("不偏"):
            modern += "斜。"
        if not modern:
            modern = "这一页主要为图形示意，相关内容已结合图像保留在本节。"
        if page == 55:
            modern = modern.replace("披发贵人", "披发贵人。", 1).split("披发贵人。", 1)[0] + "披发贵人。"
        reader_pages[page] = modern
        base = {"schema_version": "1.0", "book_id": BOOK_ID, "page_id": page_id,
                "block_id": block_id, "source_page": page, "block_type": block_type,
                "bbox": None, "source_image": f"20-source/pages/{page_id}.jpg",
                "source_text": source, "language": "lzh", "disposition": "retained",
                "confidence": confidence, "evidence": ["vision_pass1", "vision_pass2", "reader_edit"],
                "notes": notes}
        source_rows.append({**base, "operation": "source", "normalized_text": None, "modern_text": None})
        normalized_rows.append({**base, "operation": "normalize", "normalized_text": normalized, "modern_text": None})
        modern_rows.append({**base, "operation": "translate", "normalized_text": normalized, "modern_text": modern})
        edited_rows.append({**base, "operation": "edit", "normalized_text": normalized, "modern_text": modern})
        for note in notes:
            record = uncertainty_record(note, page_id, block_id, f"20-source/pages/{page_id}.jpg")
            if record:
                uncertainty_rows.append(record)
        if page == 80:
            uncertainty_rows.append({"schema_version": "1.0", "page_id": page_id, "block_id": block_id,
                                     "severity": "high", "status": "open",
                                     "note": "现存来源在句中结束，后续页不在本次扫描中；不得补写。",
                                     "source_image": f"20-source/pages/{page_id}.jpg"})

    for path, rows in ((ROOT / "20-source/blocks.jsonl", source_rows),
                       (ROOT / "30-normalized/blocks.jsonl", normalized_rows),
                       (ROOT / "40-modernized/blocks.jsonl", modern_rows),
                       (ROOT / "50-edited/blocks.jsonl", edited_rows),
                       (ROOT / "90-audit/uncertain-items.jsonl", uncertainty_rows)):
        dump_jsonl(path, rows)

    page_map = [{"schema_version": "1.0", "page_id": f"P{p:06d}", "source_page": p,
                 "classification": "scan", "layout": "vertical_mixed" if p in FIGURE_PAGES else "vertical_text",
                 "language": "lzh", "route": "dual_visual_review"} for p in range(1, 81)]
    dump_jsonl(ROOT / "10-diagnosis/page-map.jsonl", page_map)

    book = {"schema_version": "1.0", "book_id": BOOK_ID, "title": "增释地理琢玉斧峦头歌括",
            "author": "张九仪", "editor": "葛超云", "producer": "壮五福国学院",
            "source_pdf_sha256": SOURCE_SHA, "source_pdf_pages": 80,
            "source_pages": 80, "edition_scope": "full_reading_edition",
            "target_reader": "现代普通读者", "target_language": "zh-Hans"}
    (ROOT / "book.json").write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    profile = {"schema_version": "1.0", "book_id": BOOK_ID, "source_pdf_pages": 80,
               "included_pages": list(range(1, 81)), "page_type": "scan_vertical_zh_hant",
               "status": "full_coverage", "routes": ["dual_visual_transcription", "reader_focused_edit"]}
    (ROOT / "10-diagnosis/profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    introduction = """# 本书介绍

《增释地理琢玉斧峦头歌括》是一部面向风水研习者的峦头经典，重点讲解如何通过山形、水势和周围环境，辨认龙脉的行止、穴场的真假以及砂水的吉凶。

本书认为，学习风水不能只记口诀、套方位，更重要的是看懂真实地形。山脉从哪里发源，怎样起伏转折，经过什么样的过峡，最终在哪里停蓄结穴；穴场周围的砂山是否环抱，来水是否有情，去水是否收束，这些都是判断一处地局的重要依据。

书中围绕“龙、穴、砂、水”展开，收录了大量传统峦头术语、歌诀和山形图，详细介绍过峡、点穴、天财、天罡、贵人、砂法和水法等内容。读者可以结合图形，认识不同山势的形态特征，理解古人判断地形格局时所使用的方法。

与只讲抽象理论的风水书不同，本书特别重视“形”。许多难以用文字说明的山形，通过图像、名称和歌诀相互配合，帮助学习者建立基本的识形能力。对于刚接触峦头的读者，它可以作为认识山形的入门读物；对于已经具备一定基础的爱好者，也可以用来整理传统术语，复习龙穴砂水之间的关系。

本次现代白话版对原书进行了重新整理，把繁体古文、古代句式和较难理解的术语转换为现代汉语，同时保留原书中具有学习价值的山形图。重要术语在首次出现时加入简明解释，使没有古文基础的风水爱好者也能顺畅阅读。

**版本说明：**本次取得的扫描共80页，最后一页在一段对话中途结束，说明现存来源并非完整终卷。本版忠实整理这80页，不推测、不续补缺失的后文。

需要说明的是，书中的“上格、中格、下格”以及富贵、贫贱、科甲、官职等判断，反映的是古代风水理论及其社会观念。现代读者学习时，宜把重点放在山形识别、地势观察和传统峦头体系的理解上，结合实地环境进行思考，不应把歌诀当作脱离现场即可机械套用的结论。

如果你希望系统学习传统峦头，理解古人如何寻龙、察砂、观水和辨穴，这本书可以作为一部图文结合、由形入理的基础经典。

“看山不是只看高低，看水不是只看远近。真正的峦头学习，是从山水的起伏、转折、开合与聚散中，读懂一处地局的来龙去脉。”

"""
    reading_guide = """# 阅读本书前需要知道的事

## 编者导读：先建立一条观察路线

这本书不是要求读者先背完所有歌诀，而是训练一种观察山水的方法。第一次阅读时，请先记住以下顺序：

1. **看龙**：山势从哪里来，怎样起伏、转折，是否有连续的来路。
2. **看止**：山势在哪里减缓、展开或停聚，是否具备形成穴场的条件。
3. **看砂**：前后左右的山丘是否护卫、呼应，有没有明显反背或直冲。
4. **看水**：水从哪里来，在哪里汇聚，又从哪里离开。
5. **看整体**：龙、穴、砂、水能否形成一个相互配合、相对收聚的空间。

读到“富贵、科甲、贫贱、凶祸”等判断时，要把它们看作古代风水体系内部的应验语言。它们反映了作者所处时代的社会观念，不是经过现代科学验证的因果结论。本版保留这些说法，是为了忠实呈现原书；编者说明则帮助读者区分“看见了什么地形”和“古人怎样解释这种地形”。

## 阅读提示：怎样看本书的古图

原图多为示意图，不是现代等高线地图。读图时先找主干山势，再看左右分支；然后观察图中标出的穴位、护砂和水路。图名常用人物、器物或动物比拟山形，例如“覆钟”“卧弓”“贵人”“天马”。这些名称只是帮助记忆轮廓，不表示山中真的存在相应人物或物件。

如果图中文字细小、残缺或与现代用语不一致，应以本版图下注解和正文解释为主；无法可靠辨认的字，不根据语义擅自补成确定结论。

## 全书内容地图

- **序言**：说明本书的来历，以及作者为什么强调从真实山形入手。
- **过峡与行龙**：观察山脉怎样穿过狭窄处，以及两侧有没有迎送护卫。
- **卷三·点穴歌**：从龙脉的停落、四势和罗城判断穴场。
- **天财、天罡、孤曜**：用九种变形比较不同穴形，重点在识形，不在死背应验。
- **卷四·拨砂歌**：理解砂山如何护穴、关水，以及定穴定向为什么会改变砂的作用。
- **贵人砂**：学习象形山峰的传统分类及其古代等级判断。
- **卷五·鉴水歌**：从水的来去、聚散、快慢和分合反推山势与穴场。
- **阅读实践与术语表**：把全书转换成现代人可执行的观察步骤，并集中解释术语。

"""
    closing_guide = """# 阅读实践：普通人怎样观察一处地形

## 编者导读：第一次实地观察只做五件事

不要一到现场就判断吉凶，也不要急着给山峰套名称。先站在相对开阔、安全的位置，用同一个观察点完成下面五步。

1. **找来路**：确定主要山势从哪个方向延伸而来，记录它是否连续，有没有明显中断或突然转折。
2. **找停聚**：观察山势在哪里由急转缓、由窄变宽，前方是否出现相对平稳的空间。
3. **看左右**：比较左右两侧是否都有山形呼应；记录哪一侧较高、较近、较完整，不急着判断青龙白虎谁吉谁凶。
4. **看前方和水口**：找出前方较低或较开的方向，观察水流、道路或谷地从哪里进入、从哪里离开。
5. **画一张简图**：只标来龙、中心观察点、左右护卫、前方空间和水流箭头。能画清关系以后，再使用本书术语。

## 现场记录模板

- **观察地点与日期**：记录位置、天气和观察点。
- **来龙**：方向、连续性、起伏和主要转折。
- **穴场候选区域**：为什么认为这里可能停聚；有哪些反证。
- **左侧与右侧砂山**：高低、远近、朝向、是否有缺口。
- **明堂**：宽窄、平整程度、是否过度空旷。
- **水系与道路**：来向、去向、速度、弯曲、汇聚和穿越情况。
- **尚不能确定的问题**：把疑问留下，不用一个术语强行解释全部现象。

## 阅读提示：三个常见误区

第一，只看一座形似某物的山峰，就直接套用“贵人”“天马”等名称。象形只是辅助记忆，完整判断还要看它与穴场、来龙和水势的关系。

第二，只寻找书中所说的吉处，忽略更大的散乱、冲射或不安全因素。原书自己也反复提醒，要先看大势，再看局部。

第三，把古代“主富贵、主科甲、主凶祸”的说法当成确定预测。现代阅读应把这些内容放回历史语境，重点学习其中对方向、围合、聚散和层次的观察方式。

## 一页速查：从现场回到本书

看不清山脉来路时，回看“过峡与行龙”；不知道中心位置是否成立时，回看“卷三·点穴歌”；左右山形复杂时，回看“卷四·拨砂歌”；水路复杂时，回看“卷五·鉴水歌”；遇到陌生名称时，查阅书末术语表。

"""
    parts = ["# 增释地理琢玉斧峦头歌括\n\n", "## 现代白话版\n\n",
             "张九仪原著\n\n", "葛超云 整理\n\n", "本版以现代简体白话整理，面向普通读者。\n\n",
             introduction, reading_guide, "# 序言\n\n"]
    section_titles = {
        18: "# 正文\n\n## 编者导读：从过峡进入全书的观察方法\n\n前面的图先帮助读者辨认山脉经过狭窄处时的形态。本节进一步强调：格局名称只是起点，真正的判断必须说明依据，并把来龙、砂山和水势放在同一个整体中观察。\n\n",
        23: "# 卷三·点穴歌\n\n## 编者导读：先找山势怎样停，再谈穴在哪里\n\n本卷依次讨论四落、结穴方式、四势与罗城，以及天财、天罡、孤曜等穴形。阅读时先看山势是否停聚、四周是否围合，再看某种象形名称；不要倒过来只凭轮廓寻找所谓吉穴。\n\n",
        43: "# 卷四·拨砂歌\n\n## 编者导读：砂不是一座孤立的山，而是穴场周围的关系\n\n本卷的核心是理解砂山怎样护卫穴场、关拦水口，以及定穴、定向以后，同一座山为何会承担不同作用。所谓‘拨’，主要是辨认和配置关系，不是移动山体。\n\n",
        65: "# 卷五·鉴水歌\n\n## 编者导读：用水的来去聚散反看山势\n\n本卷先说明龙是根本、水是寻找龙脉的重要线索，再讨论水的分合以及海潮、江河、湖泊、溪涧、田水和池塘。普通读者应优先观察水流方向、速度、弯曲和汇聚，古代应验故事放在其次。\n\n",
    }
    editorial_before_page = {
        11: "## 图解入门：过峡时看什么\n\n**阅读提示：**先找图中最细窄的连接处，再看左右有没有小山迎送。过峡像山脉的‘关节’，重点是前后是否连续，而不是把每一种图形当成固定模板。\n\n",
        21: "## 原书案例目录（供查考）\n\n**编者注：**以下数页是原书收录案例的目录，保留用于了解原书结构。第一次阅读可以略读，不必记忆地名和页码。\n\n",
        28: "## 四势与罗城：先看整体是否围合\n\n",
        31: "## 天财九变：把名称当作轮廓索引\n\n**阅读提示：**这一组图是在比较同一类穴形怎样发生开口、伸脚、偏侧等变化。先比较轮廓，不要仅凭‘天财’二字推断财富。\n\n",
        37: "## 天罡与孤曜：形态分类不等于现实命运\n\n**阅读提示：**歌诀中的官职、贫富和凶祸属于古代应验语言。本版保留原意，但阅读重点是九种形态怎样彼此区别。\n\n",
        41: "## 原书案例目录（供查考）\n\n**编者注：**以下是配套地图说的案例目录，第一次通读可以跳过；需要追查某个传统案例时再回来查阅。\n\n",
        47: "## 从看砂到拨砂\n\n",
        51: "## 贵人砂：用人物和器物帮助记忆山形\n\n**阅读提示：**‘贵人’是象形分类。请比较木星、华盖、台阶、马形等组合关系，不要把古代官职等级直接理解为现代人的命运预测。\n\n",
        61: "## 原书案例目录（供查考）\n\n**编者注：**以下目录记录原书曾配套讨论的地点。地名具有版本与文献价值，但不影响掌握本卷方法，可按需要略读。\n\n",
        69: "## 从水势寻找龙脉\n\n",
        70: "## 三层分合：从近到远观察水系\n\n**阅读提示：**小分合看穴场附近，次分合看龙虎与案山之间，大分合看祖山到外水口。三层不是三个互不相关的项目，而是由近及远的同一套水系结构。\n\n",
        72: "## 不同水体的传统观察方法\n\n**阅读提示：**以下历史故事用于说明作者所相信的应验关系。现代读者可保留其文献意义，同时把注意力放在水流是否弯曲、平缓、汇聚和环抱。\n\n",
        79: "## 池塘水与明堂\n\n",
    }
    paragraph = ""
    terminal = tuple("。！？；：.!?;:》）”’\"")
    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            parts.append(paragraph.replace("推广到实际实例", "推广到具体实例") + "\n\n")
            paragraph = ""
    for page in range(3, 81):
        if page in section_titles:
            flush_paragraph()
            parts.append(section_titles[page])
        if page in editorial_before_page:
            flush_paragraph()
            parts.append(editorial_before_page[page])
        if page in FIGURE_PAGES:
            flush_paragraph()
            parts.append(f"![相关山形示意图](../20-source/pages/P{page:06d}.jpg)\n\n")
        if page in READER_RISK_NOTES:
            flush_paragraph()
            parts.append(f"**审校提示：**{READER_RISK_NOTES[page]}\n\n")
        text = reader_pages[page]
        if paragraph and not paragraph.endswith(terminal):
            paragraph += text
        else:
            flush_paragraph()
            paragraph = text
    flush_paragraph()
    parts.append(closing_guide)
    glossary_path = ROOT / "60-publication" / "术语表.md"
    if glossary_path.exists():
        glossary_lines = glossary_path.read_text(encoding="utf-8").splitlines()
        if glossary_lines and glossary_lines[0].startswith("# "):
            glossary_lines[0] = "# 附录：术语表"
        parts.append("\n" + "\n".join(glossary_lines).rstrip() + "\n")
    markdown = "".join(parts)
    for path in (ROOT / "50-edited/modern-reading.md", ROOT / "60-publication/modern-reading.md"):
        path.write_text(markdown, encoding="utf-8")

    state = {"schema_version": "1.0", "book_id": BOOK_ID,
             "updated_at": datetime.now(timezone.utc).isoformat(), "edition_scope": "full_reading_edition",
             "stages": {name: {"status": "passed_with_ledger" if name in {"source", "normalized", "modernized", "edited"} else "passed"}
                        for name in ("intake", "diagnosis", "source", "normalized", "modernized", "edited")}}
    state["stages"]["publication"] = {"status": "pending"}
    (ROOT / "run-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": 80, "reader_chars": len(markdown), "uncertainties": len(uncertainty_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
