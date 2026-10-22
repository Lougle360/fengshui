#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
rows = [
    json.loads(line)
    for line in (ROOT / "20-source/blocks.v19-candidates.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
audit = json.loads((ROOT / "90-audit/source-candidate-review.json").read_text(encoding="utf-8"))

assert len({row["block_id"] for row in rows}) == len(rows)
page5 = [row for row in rows if row["page_id"] == "P000005"]
assert page5[0]["collated_text"] == "而其深者猶有聚"
assert page5[0]["structural_role"] == "body"
assert all("book004-b000034-p000-6b6f4f7f8d" not in row["page_ocr_support"] or row["structural_role"] != "commentary_unaligned" for row in rows)
assert 5 in audit["visually_locked_page_boundaries"]
assert audit["visually_locked_page_boundaries"] == list(range(1, 28))
assert [item["page"] for item in audit["boundary_leading_source_only_fragments"]] == [8, 9, 10, 22, 25, 26, 27]
page10_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 10)
assert page10_reading["scan_variant_for_anchor"] == "或種作耕墾"
assert page10_reading["following_source_only_text"] == "界斷乾流"
page1_first = next(row for row in rows if row["block_id"] == "P000001-C001")
assert page1_first["collated_text"] == "內篇一"
page2_first = next(row for row in rows if row["block_id"] == "P000002-C001")
assert page2_first["collated_text"].startswith("萬物同出一源")
page2_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 2)
assert page2_reading["scan_variant_for_anchor"] == "萬物同出一原"
page3_first = next(row for row in rows if row["block_id"] == "P000003-C001")
assert page3_first["collated_text"].startswith("父母遺骨藏于融會之地")
page4_first = next(row for row in rows if row["block_id"] == "P000004-C001")
assert page4_first["collated_text"] == "丘壟之骨，岡阜之支，氣之所隨"
assert audit["candidate_blocks"] == len(rows)
assert isinstance(audit["multi_region_blocks"], int)
p7_first = next(row for row in rows if row["block_id"] == "P000007-C001")
assert p7_first["source_text"] == "言其彷彿也矣"
assert p7_first["promotion_status"] == "accepted"
p7_second = next(row for row in rows if row["block_id"] == "P000007-C002")
assert p7_second["source_text"] == "勢來形止是謂全氣全氣之地當葬其止"
assert p7_second["promotion_status"] == "accepted"
p7_full_qi_note = next(row for row in rows if row["block_id"] == "P000007-C003")
assert "可謂吃緊爲人矣" in p7_full_qi_note["source_text"]
assert "尺寸不可升變" in p7_full_qi_note["source_text"]
assert len(p7_full_qi_note["regions"]) == 2
assert p7_full_qi_note["promotion_status"] == "accepted"
p7_winding_note = next(row for row in rows if row["block_id"] == "P000007-C005")
assert p7_winding_note["source_text"].endswith("其融結之情如此")
assert p7_winding_note["promotion_status"] == "accepted"
p7_short_note = next(row for row in rows if row["block_id"] == "P000007-C007")
assert p7_short_note["source_text"] == "若人踞然不動而有所待也"
assert sum(row["promotion_status"] == "accepted" for row in rows) >= 8
p1_heading = next(row for row in rows if row["block_id"] == "P000001-C001")
assert p1_heading["source_text"] == "內篇一"
assert p1_heading["promotion_status"] == "accepted"
p1_main = next(row for row in rows if row["block_id"] == "P000001-C002")
assert p1_main["source_text"] == "葬者乘生氣也"
assert p1_main["promotion_status"] == "accepted"
p1_opening_note = next(row for row in rows if row["block_id"] == "P000001-C003")
assert "廼錦囊一書之開鍵也" in p1_opening_note["source_text"]
assert "生氣者卽一元運體之氣也" in p1_opening_note["source_text"]
assert p1_opening_note["promotion_status"] == "accepted"
p1_five_qi = next(row for row in rows if row["block_id"] == "P000001-C004")
assert p1_five_qi["source_text"] == "五氣行乎地中發而生乎萬物"
assert p1_five_qi["promotion_status"] == "accepted"
p1_five_qi_note = next(row for row in rows if row["block_id"] == "P000001-C005")
assert p1_five_qi_note["source_text"] == "五氣卽五行之氣迺生氣之別名也夫一氣分爲陰陽析而爲五行雖運於天實出乎地其行則萬物發生聚則山川融結融結者亦二五之精妙合而凝也"
assert p1_five_qi_note["promotion_status"] == "accepted"
assert len(p1_five_qi_note["regions"]) == 2
p1_body = next(row for row in rows if row["block_id"] == "P000001-C006")
assert p1_body["source_text"] == "人受體於父母本骸得氣遺體受廕"
assert p1_body["promotion_status"] == "accepted"
p1_long = next(row for row in rows if row["block_id"] == "P000001-C007")
assert p1_long["source_text"].endswith("蓋衆人之先與天地")
assert p1_long["continues_to_next_page"] is True
assert p1_long["promotion_status"] == "accepted"
assert len(p1_long["regions"]) == 2
p2_opening = next(row for row in rows if row["block_id"] == "P000002-C001")
assert p2_opening["source_text"].startswith("萬物同出一原")
assert p2_opening["continues_from_previous_page"] is True
assert p2_opening["promotion_status"] == "accepted"
p2_main = next(row for row in rows if row["block_id"] == "P000002-C002")
assert p2_main["source_text"] == "經曰氣感而應鬼福及人"
assert p2_main["promotion_status"] == "accepted"
p2_note = next(row for row in rows if row["block_id"] == "P000002-C003")
assert "當以何法而能致之乎蓋亦因聖人有卜兆安厝之旨" in p2_note["source_text"]
assert p2_note["source_text"].endswith("人子有謀本受親之情以")
assert p2_note["continues_to_next_page"] is True
assert p2_note["promotion_status"] == "accepted"
assert len(p2_note["regions"]) == 2
p3_bell = next(row for row in rows if row["block_id"] == "P000003-C002")
assert p3_bell["source_text"] == "是以銅山西崩靈鐘東應"
assert p3_bell["promotion_status"] == "accepted"
p3_opening_note = next(row for row in rows if row["block_id"] == "P000003-C001")
assert p3_opening_note["source_text"].startswith("父母遺骨藏於融會之地則是子孫之心")
assert "故降神孕秀以鍾於生息之源" in p3_opening_note["source_text"]
assert "世人往往以遺骨棄於水中" in p3_opening_note["source_text"]
assert p3_opening_note["continues_from_previous_page"] is True
assert p3_opening_note["promotion_status"] == "accepted"
p3_bell_note = next(row for row in rows if row["block_id"] == "P000003-C003")
assert "氣相感應尤人受體於父母也" in p3_bell_note["source_text"]
assert "母欲其歸則嘆指而曾子心痛" in p3_bell_note["source_text"]
assert p3_bell_note["promotion_status"] == "accepted"
p3_chestnut = next(row for row in rows if row["block_id"] == "P000003-C004")
assert p3_chestnut["source_text"] == "木華於春栗芽於室"
assert p3_chestnut["promotion_status"] == "accepted"
p3_chestnut_note = next(row for row in rows if row["block_id"] == "P000003-C005")
assert "野人藏栗春栗知木華而家藏之栗亦芽" in p3_chestnut_note["source_text"]
assert "夫一氣旁薄於天地間無端倪" in p3_chestnut_note["source_text"]
assert p3_chestnut_note["promotion_status"] == "accepted"
p3_bones = next(row for row in rows if row["block_id"] == "P000003-C006")
assert p3_bones["source_text"] == "蓋生者氣之聚凝結者成骨死而獨留故葬者反氣入骨以廕所生之法也"
assert p3_bones["promotion_status"] == "accepted"
p3_bones_note = next(row for row in rows if row["block_id"] == "P000003-C007")
assert "復藉神氣資乎其間遂能生而爲人" in p3_bones_note["source_text"]
assert "上智之士圖而於吉地之中" in p3_bones_note["source_text"]
assert p3_bones_note["promotion_status"] == "accepted"
p3_heading = next(row for row in rows if row["block_id"] == "P000003-C008")
assert p3_heading["source_text"] == "內篇二"
assert p3_heading["promotion_status"] == "accepted"
p4_opening = next(row for row in rows if row["block_id"] == "P000004-C001")
assert p4_opening["source_text"] == "丘壟之骨岡阜之支氣之所隨"
assert p4_opening["promotion_status"] == "accepted"
p4_opening_note = next(row for row in rows if row["block_id"] == "P000004-C002")
assert p4_opening_note["source_text"].startswith("此章乃塟之中之綱領也")
assert "又全藉乎心目之明以區別也" in p4_opening_note["source_text"]
assert p4_opening_note["promotion_status"] == "accepted"
p4_wind_water = next(row for row in rows if row["block_id"] == "P000004-C003")
assert p4_wind_water["source_text"] == "經曰氣乘風則散界水則止"
assert p4_wind_water["promotion_status"] == "accepted"
p4_wind_water_note = next(row for row in rows if row["block_id"] == "P000004-C004")
assert p4_wind_water_note["source_text"].endswith("堂裏避風如避賊可不慎哉")
assert p4_wind_water_note["promotion_status"] == "accepted"
p4_highland_note = next(row for row in rows if row["block_id"] == "P000004-C006")
assert "天陰自上而降生氣浮露" in p4_highland_note["source_text"]
assert "雖八面無蔽已自不覺" in p4_highland_note["source_text"]
assert len(p4_highland_note["regions"]) == 2
assert p4_highland_note["promotion_status"] == "accepted"
p4_water_priority = next(row for row in rows if row["block_id"] == "P000004-C007")
assert p4_water_priority["bbox"] == [365, 502, 405, 918]
p4_water_note = next(row for row in rows if row["block_id"] == "P000004-C008")
assert "但有橫水欄其兒適何害" in p4_water_note["source_text"]
assert "二者皆次得水爲上也" in p4_water_note["source_text"]
assert len(p4_water_note["regions"]) == 2
assert p4_water_note["promotion_status"] == "accepted"
p4_outer_qi_note = next(row for row in rows if row["block_id"] == "P000004-C010")
assert "外氣形橫則內之生氣自然止也" in p4_outer_qi_note["source_text"]
assert p4_outer_qi_note["promotion_status"] == "accepted"
p4_ancients = next(row for row in rows if row["block_id"] == "P000004-C005")
assert p4_ancients["source_text"] == "古人聚之使不散行之使有止故謂之風水"
assert p4_ancients["promotion_status"] == "accepted"
p4_rule = next(row for row in rows if row["block_id"] == "P000004-C007")
assert p4_rule["source_text"] == "風水之法得水為上藏風次之"
assert p4_rule["promotion_status"] == "accepted"
p4_outer_qi = next(row for row in rows if row["block_id"] == "P000004-C009")
assert p4_outer_qi["source_text"] == "經曰外氣橫形內氣止生蓋言此也"
assert p4_outer_qi["promotion_status"] == "accepted"
p4_continuation = next(row for row in rows if row["block_id"] == "P000004-C011")
assert p4_continuation["source_text"] == "何以言之氣之盛雖流行而其餘者猶有止雖零散"
assert p4_continuation["continues_to_next_page"] is True
assert p4_continuation["promotion_status"] == "accepted"
p5_continuation = next(row for row in rows if row["block_id"] == "P000005-C001")
assert p5_continuation["source_text"] == "而其深者猶有聚"
assert p5_continuation["continues_from_previous_page"] is True
assert p5_continuation["promotion_status"] == "accepted"
p5_continuation_note = next(row for row in rows if row["block_id"] == "P000005-C002")
assert "大山段落平洋四面寬廣" in p5_continuation_note["source_text"]
assert "但得求橫水攔截而使之有止耳" in p5_continuation_note["source_text"]
assert p5_continuation_note["promotion_status"] == "accepted"
p5_depth = next(row for row in rows if row["block_id"] == "P000005-C003")
assert p5_depth["source_text"] == "故藏於涸燥者宜淺藏於坦夷者宜深"
assert p5_depth["promotion_status"] == "accepted"
p5_depth_note = next(row for row in rows if row["block_id"] == "P000005-C004")
assert "景純至此則傾囊倒篋盡洩塟法之玄祕矣" in p5_depth_note["source_text"]
assert "雨注即傾" in p5_depth_note["source_text"]
assert p5_depth_note["promotion_status"] == "accepted"
p5_shallow_deep = next(row for row in rows if row["block_id"] == "P000005-C005")
assert p5_shallow_deep["source_text"] == "經曰淺深得乘風水自成"
assert p5_shallow_deep["promotion_status"] == "accepted"
p5_shallow_deep_note = next(row for row in rows if row["block_id"] == "P000005-C006")
assert "塟謂高壠之塟露而勿隱" in p5_shallow_deep_note["source_text"]
assert p5_shallow_deep_note["source_text"].endswith("九星白法以定尺寸者謬也")
assert p5_shallow_deep_note["promotion_status"] == "accepted"
p5_yin_yang = next(row for row in rows if row["block_id"] == "P000005-C007")
assert p5_yin_yang["source_text"] == "夫陰陽之氣噫而爲風升而爲雲降而爲雨行乎地中而爲生氣"
assert "且" not in p5_yin_yang["source_text"]
assert p5_yin_yang["promotion_status"] == "accepted"
p5_yin_yang_note = next(row for row in rows if row["block_id"] == "P000005-C008")
assert "此所以位天地育萬物者" in p5_yin_yang_note["source_text"]
assert p5_yin_yang_note["source_text"].endswith("破腮翻鬥之患也")
assert p5_yin_yang_note["promotion_status"] == "accepted"
p5_earth_qi = next(row for row in rows if row["block_id"] == "P000005-C009")
assert p5_earth_qi["source_text"] == "夫土者氣之體有土斯有氣氣者水之母有氣斯有水"
assert p5_earth_qi["continues_to_next_page"] is False
assert p5_earth_qi["promotion_status"] == "accepted"
p6_qi_moves = next(row for row in rows if row["block_id"] == "P000006-C002")
assert p6_qi_moves["source_text"] == "經曰土形氣行物因以生"
assert p6_qi_moves["promotion_status"] == "accepted"
p6_opening_note = next(row for row in rows if row["block_id"] == "P000006-C001")
assert "故遂以水爲天一之始蓋得而未精者也" in p6_opening_note["source_text"]
assert p6_opening_note["promotion_status"] == "accepted"
p6_qi_moves_note = next(row for row in rows if row["block_id"] == "P000006-C003")
assert p6_qi_moves_note["source_text"].endswith("此引經結上文有土斯有氣之意")
assert p6_qi_moves_note["promotion_status"] == "accepted"
p6_heading = next(row for row in rows if row["block_id"] == "P000006-C004")
assert p6_heading["source_text"] == "內篇三"
assert p6_heading["promotion_status"] == "accepted"
p6_qi_course = next(row for row in rows if row["block_id"] == "P000006-C005")
assert p6_qi_course["source_text"] == "夫氣行乎地中其行也因地之勢其聚也因勢之止"
assert p6_qi_course["promotion_status"] == "accepted"
p6_qi_course_note = next(row for row in rows if row["block_id"] == "P000006-C006")
assert "謂氣行地中人不可見" in p6_qi_course_note["source_text"]
assert p6_qi_course_note["promotion_status"] == "accepted"
p6_burial = next(row for row in rows if row["block_id"] == "P000006-C007")
assert p6_burial["source_text"] == "葬者原其起乘其止"
assert p6_burial["promotion_status"] == "accepted"
p6_burial_note = next(row for row in rows if row["block_id"] == "P000006-C008")
assert "善塟者必原其起以觀勢乘其止以定穴" in p6_burial_note["source_text"]
assert "粘穴乘其脈之盡處" in p6_burial_note["source_text"]
assert p6_burial_note["promotion_status"] == "accepted"
p6_terrain = next(row for row in rows if row["block_id"] == "P000006-C009")
assert p6_terrain["source_text"] == "地勢原脈山勢原骨委蛇東西或爲南北"
assert p6_terrain["promotion_status"] == "accepted"
p6_terrain_note = next(row for row in rows if row["block_id"] == "P000006-C010")
assert "必常認土脊以爲脈" in p6_terrain_note["source_text"]
assert p6_terrain_note["source_text"].endswith("岡阜之支意同耳")
assert p6_terrain_note["promotion_status"] == "accepted"
p6_scale = next(row for row in rows if row["block_id"] == "P000006-C011")
assert p6_scale["source_text"] == "千尺爲勢百尺爲形"
assert p6_scale["promotion_status"] == "accepted"
p6_scale_note = next(row for row in rows if row["block_id"] == "P000006-C012")
assert p6_scale_note["source_text"].endswith("山川形勢豈真有尺度之拘特")
assert p6_scale_note["continues_to_next_page"] is True
assert p6_scale_note["promotion_status"] == "accepted"
p7_gathering = next(row for row in rows if row["block_id"] == "P000007-C012")
assert p7_gathering["source_text"] == "來積止聚沖陽和陰"
assert p7_gathering["promotion_status"] == "accepted"
p7_depth_note = next(row for row in rows if row["block_id"] == "P000007-C011")
assert "須得趨揖朝拱" in p7_depth_note["source_text"]
assert p7_depth_note["source_text"].endswith("不欲其斗瀉反背而無情也")
assert p7_depth_note["promotion_status"] == "accepted"
p7_gathering_note = next(row for row in rows if row["block_id"] == "P000007-C013")
assert "斯乃陰陽交濟山水沖和" in p7_gathering_note["source_text"]
assert p7_gathering_note["promotion_status"] == "accepted"
p7_soil_water = next(row for row in rows if row["block_id"] == "P000007-C014")
assert p7_soil_water["source_text"] == "土高水深鬱草茂林"
assert p7_soil_water["promotion_status"] == "accepted"
p7_soil_water_note = next(row for row in rows if row["block_id"] == "P000007-C015")
assert "曷謂地理之美者" in p7_soil_water_note["source_text"]
assert p7_soil_water_note["source_text"].endswith("迺其驗也")
assert p7_soil_water_note["promotion_status"] == "accepted"
p7_nobility = next(row for row in rows if row["block_id"] == "P000007-C016")
assert p7_nobility["source_text"] == "貴若千乘富如萬金"
assert p7_nobility["promotion_status"] == "accepted"
p7_nobility_note = next(row for row in rows if row["block_id"] == "P000007-C017")
assert p7_nobility_note["source_text"] == "氣象尊嚴若千乘之貴也簇擁繁夥猶萬金之富"
assert p7_nobility_note["promotion_status"] == "accepted"
p8_opening = next(row for row in rows if row["block_id"] == "P000008-C001")
assert p8_opening["source_text"] == "經曰形止氣蓄化生萬物爲上地也"
assert p8_opening["promotion_status"] == "accepted"
p8_opening_note = next(row for row in rows if row["block_id"] == "P000008-C002")
assert "藏蓄于中矣" in p8_opening_note["source_text"]
assert p8_opening_note["promotion_status"] == "accepted"
p8_heading = next(row for row in rows if row["block_id"] == "P000008-C003")
assert p8_heading["source_text"] == "內篇四"
assert p8_heading["promotion_status"] == "accepted"
p8_level = next(row for row in rows if row["block_id"] == "P000008-C004")
assert p8_level["source_text"] == "地貴平夷土貴有支"
assert p8_level["promotion_status"] == "accepted"
p8_level_note = next(row for row in rows if row["block_id"] == "P000008-C005")
assert "平緩恬軟" in p8_level_note["source_text"]
assert "一二尺" in p8_level_note["source_text"]
assert p8_level_note["promotion_status"] == "accepted"
p8_branch = next(row for row in rows if row["block_id"] == "P000008-C006")
assert p8_branch["source_text"] == "支之所起氣隨而始支之所終氣隨以鐘"
assert p8_branch["promotion_status"] == "accepted"
p8_branch_note = next(row for row in rows if row["block_id"] == "P000008-C007")
assert "原其起乘其止氣脈隨之而行" in p8_branch_note["source_text"]
assert p8_branch_note["promotion_status"] == "accepted"
p8_observe = next(row for row in rows if row["block_id"] == "P000008-C008")
assert p8_observe["source_text"] == "觀支之法隱隱隆隆微妙玄通吉在其中"
assert p8_observe["promotion_status"] == "accepted"
p8_observe_note = next(row for row in rows if row["block_id"] == "P000008-C009")
assert "隆隆無中之有也" in p8_observe_note["source_text"]
assert p8_observe_note["promotion_status"] == "accepted"
p8_auspicious = next(row for row in rows if row["block_id"] == "P000008-C010")
assert p8_auspicious["source_text"] == "經曰地有吉氣土隨而起支有止氣水隨而比勢順形動回復始終法葬其中永吉無凶"
assert p8_auspicious["promotion_status"] == "accepted"
p8_auspicious_note = next(row for row in rows if row["block_id"] == "P000008-C011")
assert p8_auspicious_note["source_text"].endswith("首尾無蔽終始有")
assert p8_auspicious_note["promotion_status"] == "accepted"
p9_mountain = next(row for row in rows if row["block_id"] == "P000009-C001")
assert p9_mountain["source_text"] == "山者勢險而有也法葬其所會"
assert p9_mountain["promotion_status"] == "accepted"
p9_mountain_note = next(row for row in rows if row["block_id"] == "P000009-C002")
assert "兩邊金魚隨脈而行" in p9_mountain_note["source_text"]
assert len(p9_mountain_note.get("regions", [])) == 2
assert p9_mountain_note["promotion_status"] == "accepted"
p9_arrival = next(row for row in rows if row["block_id"] == "P000009-C003")
assert p9_arrival["source_text"] == "乘其所來"
assert p9_arrival["promotion_status"] == "accepted"
p9_arrival_note = next(row for row in rows if row["block_id"] == "P000009-C004")
assert "手中之杖放倒指定生氣之入路" in p9_arrival_note["source_text"]
assert p9_arrival_note["promotion_status"] == "accepted"
p9_ruined = next(row for row in rows if row["block_id"] == "P000009-C005")
assert p9_ruined["source_text"] == "審其所廢"
assert p9_ruined["promotion_status"] == "accepted"
p9_ruined_note = next(row for row in rows if row["block_id"] == "P000009-C006")
assert p9_ruined_note["source_text"].endswith("歲久年深不明")
assert p9_ruined_note["promotion_status"] == "accepted"
p10_ruined_continuation = next(row for row in rows if row["block_id"] == "P000010-C001")
assert p10_ruined_continuation["source_text"].startswith("或種作耕墾界斷乾流")
assert "井中察地之理" in p10_ruined_continuation["source_text"]
assert p10_ruined_continuation["promotion_status"] == "accepted"
p10_support = next(row for row in rows if row["block_id"] == "P000010-C002")
assert p10_support["source_text"] == "擇其所相"
assert p10_support["promotion_status"] == "accepted"
p10_support_note = next(row for row in rows if row["block_id"] == "P000010-C003")
assert "破腮翻鬥" in p10_support_note["source_text"]
assert p10_support_note["promotion_status"] == "accepted"
p10_avoid = next(row for row in rows if row["block_id"] == "P000010-C004")
assert p10_avoid["source_text"] == "避其所害"
assert p10_avoid["promotion_status"] == "accepted"
p10_avoid_note = next(row for row in rows if row["block_id"] == "P000010-C005")
assert p10_avoid_note["source_text"].endswith("劉氏之所謂四惡皆在")
assert p10_avoid_note["promotion_status"] == "accepted"
p11_avoid_tail = next(row for row in rows if row["block_id"] == "P000011-C001")
assert p11_avoid_tail["source_text"] == "所當避也"
assert p11_avoid_tail["promotion_status"] == "accepted"
p11_source_only_main = next(row for row in rows if row["block_id"] == "P000011-C002")
assert p11_source_only_main["source_text"] == "是以君子奪神功改天命"
assert p11_source_only_main["promotion_status"] == "accepted"
p11_source_only_note = next(row for row in rows if row["block_id"] == "P000011-C003")
assert "天命可移也神功可奪也" in p11_source_only_note["source_text"]
assert p11_source_only_note["promotion_status"] == "accepted"
p11_speed = next(row for row in rows if row["block_id"] == "P000011-C004")
assert p11_speed["source_text"] == "禍福不旋日經曰葬山之法若呼吸中言應速也"
assert p11_speed["promotion_status"] == "accepted"
p11_speed_note = next(row for row in rows if row["block_id"] == "P000011-C005")
assert "若還差一指如隔萬重山" in p11_speed_note["source_text"]
assert p11_speed_note["promotion_status"] == "accepted"
p11_barren = next(row for row in rows if row["block_id"] == "P000011-C006")
assert p11_barren["source_text"].startswith("山之不可葬者五")
assert p11_barren["promotion_status"] == "accepted"
p11_barren_note = next(row for row in rows if row["block_id"] == "P000011-C007")
assert "開井而得五色土穴" in p11_barren_note["source_text"]
assert p11_barren_note["promotion_status"] == "accepted"
p11_cut = next(row for row in rows if row["block_id"] == "P000011-C008")
assert p11_cut["source_text"] == "氣因形來而斷山不可葬也"
assert p11_cut["promotion_status"] == "accepted"
p11_cut_note = next(row for row in rows if row["block_id"] == "P000011-C009")
assert "一息不來身是殼" in p11_cut_note["source_text"]
assert p11_cut_note["promotion_status"] == "accepted"
p12_stone = next(row for row in rows if row["block_id"] == "P000012-C001")
assert p12_stone["source_text"] == "氣因土行而石山不可葬也"
assert p12_stone["promotion_status"] == "accepted"
p12_stone_note = next(row for row in rows if row["block_id"] == "P000012-C002")
assert "其中得土穴者" in p12_stone_note["source_text"]
assert p12_stone_note["promotion_status"] == "accepted"
p12_passing = next(row for row in rows if row["block_id"] == "P000012-C003")
assert p12_passing["source_text"] == "氣以勢止而過山不可葬也"
assert p12_passing["promotion_status"] == "accepted"
p12_passing_note = next(row for row in rows if row["block_id"] == "P000012-C004")
assert "橫龍滴落正龍腰落" in p12_passing_note["source_text"]
assert p12_passing_note["promotion_status"] == "accepted"
p12_alone = next(row for row in rows if row["block_id"] == "P000012-C005")
assert p12_alone["source_text"] == "氣以龍會而獨山不可葬也"
assert p12_alone["promotion_status"] == "accepted"
p12_alone_note = next(row for row in rows if row["block_id"] == "P000012-C006")
assert "蓋得水爲上藏風次之" in p12_alone_note["source_text"]
assert p12_alone_note["promotion_status"] == "accepted"
p12_five = next(row for row in rows if row["block_id"] == "P000012-C007")
assert p12_five["source_text"] == "經曰童斷石過獨生新凶而消已福"
assert p12_five["promotion_status"] == "accepted"
p12_five_note = next(row for row in rows if row["block_id"] == "P000012-C008")
assert "腐骨爛棺" in p12_five_note["source_text"]
assert p12_five_note["promotion_status"] == "accepted"
p12_upper = next(row for row in rows if row["block_id"] == "P000012-C009")
assert p12_upper["source_text"] == "上地之山若伏若連其原自天"
assert p12_upper["promotion_status"] == "accepted"
p12_upper_note = next(row for row in rows if row["block_id"] == "P000012-C010")
assert "藕斷絲連術中謂之脫卸" in p12_upper_note["source_text"]
assert p12_upper_note["promotion_status"] == "accepted"
page13 = [row for row in rows if row["source_page"] == 13]
assert len(page13) == 24
assert all(row["promotion_status"] == "accepted" for row in page13)
assert next(row for row in page13 if row["block_id"] == "P000013-C009")["source_text"] == "若懷萬寶而燕息"
assert next(row for row in page13 if row["block_id"] == "P000013-C011")["source_text"] == "若具萬膳而絜齊"
assert next(row for row in page13 if row["block_id"] == "P000013-C013")["source_text"] == "若橐之鼓"
assert next(row for row in page13 if row["block_id"] == "P000013-C017")["source_text"] == "若龍若鸞或騰或盤"
assert next(row for row in page13 if row["block_id"] == "P000013-C021")["source_text"] == "天光發新"
page14 = [row for row in rows if row["source_page"] == 14]
assert len(page14) == 19
assert sum(row["promotion_status"] == "accepted" for row in page14) == 18
assert next(row for row in page14 if row["block_id"] == "P000014-C004")["source_text"] == "四勢端明五害不親"
assert next(row for row in page14 if row["block_id"] == "P000014-C008")["source_text"] == "外篇一"
assert next(row for row in page14 if row["block_id"] == "P000014-C019")["promotion_status"] == "rejected_duplicate"
page15 = [row for row in rows if row["source_page"] == 15]
assert len(page15) == 10
assert all(row["promotion_status"] == "accepted" for row in page15)
assert next(row for row in page15 if row["block_id"] == "P000015-C001")["source_text"] == "故支塟其巔壠塟其麓"
assert next(row for row in page15 if row["block_id"] == "P000015-C002")["source_text"].startswith("支塟其巔緩而急之也")
assert next(row for row in page15 if row["block_id"] == "P000015-C007")["source_text"].endswith("候虜有間")
assert len(next(row for row in page15 if row["block_id"] == "P000015-C008")["regions"]) == 2
assert next(row for row in page15 if row["block_id"] == "P000015-C009")["source_text"] == "乘金相水穴土印木"
assert next(row for row in page15 if row["block_id"] == "P000015-C010")["source_text"].endswith("壽帶孩衿")
page16 = [row for row in rows if row["source_page"] == 16]
assert len(page16) == 11
assert all(row["promotion_status"] == "accepted" for row in page16)
assert next(row for row in page16 if row["block_id"] == "P000016-C001")["source_text"].endswith("不能以造于精妙也")
assert len(next(row for row in page16 if row["block_id"] == "P000016-C005")["regions"]) == 2
assert next(row for row in page16 if row["block_id"] == "P000016-C006")["source_text"] == "陰陽沖和五土四備"
assert next(row for row in page16 if row["block_id"] == "P000016-C007")["source_text"].endswith("其斯之謂歟")
assert len(next(row for row in page16 if row["block_id"] == "P000016-C008")["regions"]) == 2
assert next(row for row in page16 if row["block_id"] == "P000016-C011")["source_text"] == "崑崙插漢聳入而下若萬馬奔馳而來也"
page17 = [row for row in rows if row["source_page"] == 17]
assert len(page17) == 11
assert all(row["promotion_status"] == "accepted" for row in page17)
assert next(row for row in page17 if row["block_id"] == "P000017-C001")["source_text"] == "形如負扆有壠中峙法塟其止"
assert next(row for row in page17 if row["block_id"] == "P000017-C003")["source_text"] == "經曰勢止形昂前澗後岡龍首之藏"
assert len(next(row for row in page17 if row["block_id"] == "P000017-C008")["regions"]) == 2
assert "不蓄之穴腐骨之藏也" in next(row for row in page17 if row["block_id"] == "P000017-C010")["source_text"]
assert next(row for row in page17 if row["block_id"] == "P000017-C011")["source_text"].endswith("敗棺之藏也")
page18 = [row for row in rows if row["source_page"] == 18]
assert len(page18) == 5
assert sum(row["promotion_status"] == "accepted" for row in page18) == 4
assert next(row for row in page18 if row["block_id"] == "P000018-C002")["source_text"].endswith("備具五色")
assert len(next(row for row in page18 if row["block_id"] == "P000018-C003")["regions"]) == 2
assert "讀郭璞經云好地方有五色土" in next(row for row in page18 if row["block_id"] == "P000018-C003")["source_text"]
assert next(row for row in page18 if row["block_id"] == "P000018-C004")["source_text"] == "夫乾如穴粟"
assert next(row for row in page18 if row["block_id"] == "P000018-C005")["promotion_status"] == "rejected_duplicate"
page19 = [row for row in rows if row["source_page"] == 19]
assert len(page19) == 15
assert all(row["promotion_status"] == "accepted" for row in page19)
assert next(row for row in page19 if row["block_id"] == "P000019-C002")["source_text"] == "溫如刲肉"
assert next(row for row in page19 if row["block_id"] == "P000019-C006")["source_text"] == "皆為凶宅"
assert next(row for row in page19 if row["block_id"] == "P000019-C008")["source_text"] == "玄武垂頭"
assert next(row for row in page19 if row["block_id"] == "P000019-C015")["source_text"].endswith("但不可蹲而垂耳")
page20 = [row for row in rows if row["source_page"] == 20]
assert len(page20) == 16
assert all(row["promotion_status"] == "accepted" for row in page20)
assert next(row for row in page20 if row["block_id"] == "P000020-C001")["source_text"] == "形勢反此法當破死"
assert next(row for row in page20 if row["block_id"] == "P000020-C006")["source_text"].endswith("夫龍虎俱以馴順俯伏為吉")
assert len(next(row for row in page20 if row["block_id"] == "P000020-C012")["regions"]) == 2
assert next(row for row in page20 if row["block_id"] == "P000020-C015")["source_text"] == "派于未盛朝於大旺"
assert next(row for row in page20 if row["block_id"] == "P000020-C016")["source_text"].endswith("此水之未盛")
page21 = [row for row in rows if row["source_page"] == 21]
assert len(page21) == 4
assert all(row["promotion_status"] == "accepted" for row in page21)
assert next(row for row in page21 if row["block_id"] == "P000021-C001")["source_text"] == "山囚水流虜王滅候"
assert "宗廟之說非也" in next(row for row in page21 if row["block_id"] == "P000021-C002")["source_text"]
assert next(row for row in page21 if row["block_id"] == "P000021-C003")["collation_reference_only"] is False
assert next(row for row in page21 if row["block_id"] == "P000021-C004")["source_text"].endswith("雜篇一")
page22_review = [row for row in rows if row["source_page"] == 22]
assert len(page22_review) == 12
assert all(row["promotion_status"] == "accepted" for row in page22_review)
assert next(row for row in page22_review if row["block_id"] == "P000022-C001")["source_text"] == "雜篇一"
assert next(row for row in page22_review if row["block_id"] == "P000022-C002")["source_text"] == "占山之法以勢為難而形次之方又次之"
assert len(next(row for row in page22_review if row["block_id"] == "P000022-C003")["regions"]) == 2
assert next(row for row in page22_review if row["block_id"] == "P000022-C006")["source_text"] == "勢如巨浪重嶺疊嶂千乘之塟"
assert next(row for row in page22_review if row["block_id"] == "P000022-C012")["source_text"] == "勢如驚蛇屈曲徐斜滅國亡家"
page23_review = [row for row in rows if row["source_page"] == 23]
assert len(page23_review) == 19
assert all(row["promotion_status"] == "accepted" for row in page23_review)
assert next(row for row in page23_review if row["block_id"] == "P000023-C001")["source_text"].startswith("橫竄直播行度不調")
assert next(row for row in page23_review if row["block_id"] == "P000023-C002")["source_text"] == "勢如矛戈兵死形囚"
assert next(row for row in page23_review if row["block_id"] == "P000023-C006")["source_text"] == "形如負扆有壠中峙法塟其止王侯崛起"
assert "然壠中又有分袁壠也" in next(row for row in page23_review if row["block_id"] == "P000023-C013")["source_text"]
assert next(row for row in page23_review if row["block_id"] == "P000023-C018")["source_text"] == "形如亂衣妬女淫妻"
page24_review = [row for row in rows if row["source_page"] == 24]
assert len(page24_review) == 24
assert all(row["promotion_status"] == "accepted" for row in page24_review)
assert next(row for row in page24_review if row["block_id"] == "P000024-C003")["source_text"] == "形如覆舟女病男囚"
assert next(row for row in page24_review if row["block_id"] == "P000024-C005")["source_text"] == "形如橫几子滅孫死"
assert next(row for row in page24_review if row["block_id"] == "P000024-C011")["source_text"] == "牛臥馬馳鸞舞鳳飛"
assert "勢凶形吉百無一勢吉形凶禍不旋日" in next(row for row in page24_review if row["block_id"] == "P000024-C023")["source_text"]
assert next(row for row in page24_review if row["block_id"] == "P000024-C024")["source_text"].endswith("順則吉")
page25_review = [row for row in rows if row["source_page"] == 25]
assert len(page25_review) == 7
assert all(row["promotion_status"] == "accepted" for row in page25_review)
assert next(row for row in page25_review if row["block_id"] == "P000025-C001")["source_text"].startswith("形逆則凶")
assert next(row for row in page25_review if row["block_id"] == "P000025-C001")["source_text"].endswith("雜篇下")
assert len(next(row for row in page25_review if row["block_id"] == "P000025-C003")["regions"]) == 2
assert "星卦者之所假托非景純之所作者明矣" in next(row for row in page25_review if row["block_id"] == "P000025-C003")["source_text"]
assert next(row for row in page25_review if row["block_id"] == "P000025-C004")["source_text"] == "是故四勢之山生八方之龍四勢行龍八龍施生一得其宅吉慶榮貴"
assert next(row for row in page25_review if row["block_id"] == "P000025-C007")["source_text"].endswith("二十四方")
page26_review = [row for row in rows if row["source_page"] == 26]
assert len(page26_review) == 11
assert all(row["promotion_status"] == "accepted" for row in page26_review)
assert len(next(row for row in page26_review if row["block_id"] == "P000026-C001")["regions"]) == 2
assert next(row for row in page26_review if row["block_id"] == "P000026-C002")["source_text"] == "蓋穴有三吉塟有六凶天光下臨地德上載"
assert next(row for row in page26_review if row["block_id"] == "P000026-C006")["source_text"].startswith("陰陽沖和五土四備")
assert "卜日之弊" in next(row for row in page26_review if row["block_id"] == "P000026-C009")["source_text"]
assert next(row for row in page26_review if row["block_id"] == "P000026-C011")["source_text"].endswith("不量力度德")
page27_review = [row for row in rows if row["source_page"] == 27]
assert len(page27_review) == 8
assert all(row["promotion_status"] == "accepted" for row in page27_review)
assert next(row for row in page27_review if row["block_id"] == "P000027-C001")["source_text"] == "也憑福峙勢為四凶"
assert next(row for row in page27_review if row["block_id"] == "P000027-C003")["source_text"] == "僭上偪下為五凶"
assert len(next(row for row in page27_review if row["block_id"] == "P000027-C004")["regions"]) == 2
assert next(row for row in page27_review if row["block_id"] == "P000027-C007")["source_text"] == "經曰穴吉塟凶與棄尸同"
assert next(row for row in page27_review if row["block_id"] == "P000027-C008")["source_text"].endswith("況將")
page11 = [row for row in rows if row["source_page"] == 11]
page11_texts = [row.get("source_text") or row.get("collated_text") or "" for row in page11]
restored_index = page11_texts.index("是以君子奪神功改天命")
next_main_index = next(i for i, text in enumerate(page11_texts) if text.startswith("禍福不旋日"))
assert restored_index < next_main_index
assert page11[restored_index]["component_id"] == "C-MAIN"
assert page11[restored_index]["structural_role"] == "body"
assert page11[restored_index]["collation_reference_only"] is False
page12_first = next(row for row in rows if row["block_id"] == "P000012-C001")
assert page12_first["collated_text"] == "氣因土行，而石山不可葬也"
page13_first = next(row for row in rows if row["block_id"] == "P000013-C001")
assert page13_first["collated_text"] == "若水之波"
page14_first = next(row for row in rows if row["block_id"] == "P000014-C001")
assert page14_first["collated_text"].startswith("之副廳堂")
page15_first = next(row for row in rows if row["block_id"] == "P000015-C001")
assert page15_first["collated_text"] == "故支葬其額，城葬其麓"
page15_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 15)
assert page15_reading["scan_variant_for_anchor"] == "故支葬其巔壠葬其麓"
page16_first = next(row for row in rows if row["block_id"] == "P000016-C001")
assert page16_first["collated_text"].startswith("筻口鳥跡")
assert page16_first["continues_from_previous_page"] is True
page17_first = next(row for row in rows if row["block_id"] == "P000017-C001")
assert page17_first["collated_text"] == "形如負峙，有城中峙，法葬其止"
page17_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 17)
assert page17_reading["scan_variant_for_anchor"] == "形如負扆有壠中峙法葬其止"
page18_first = next(row for row in rows if row["block_id"] == "P000018-C001")
assert page18_first["collated_text"].startswith("天地之氣")
page19_first = next(row for row in rows if row["block_id"] == "P000019-C001")
assert page19_first["collated_text"].startswith("土無氣脈")
assert page19_first["continues_from_previous_page"] is False
page19_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 19)
assert page19_reading["scan_variant_for_anchor"] == "土無氣脈上聚下虛"
page20_text = "".join((row.get("source_text") or row.get("collated_text") or "") for row in rows if row["source_page"] == 20)
page21_first = next(row for row in rows if row["block_id"] == "P000021-C001")
assert "小流合大流" not in page20_text
assert page21_first["collated_text"] == "山囚水流，虜王滅候"
assert audit["reference_only_omissions"][0]["id"] == "REF-OMIT-P020-P021-001"
page22 = [row for row in rows if row["source_page"] == 22]
assert page22[0]["structural_role"] == "heading"
assert page22[0]["collated_text"] == "雜篇"
assert page22[1]["collated_text"] == "占山之法，以势为难，而形次之，方又次之"
page23_first = next(row for row in rows if row["block_id"] == "P000023-C001")
assert page23_first["collated_text"].startswith("横窜直播")
page23_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 23)
assert page23_reading["scan_variant_for_anchor"] == "橫竄直播"
page24_first = next(row for row in rows if row["block_id"] == "P000024-C001")
assert page24_first["collated_text"] == "形如灰囊，灾舍焚仓"
page25_first = next(row for row in rows if row["block_id"] == "P000025-C001")
assert page25_first["collated_text"].startswith("逆者凶")
page25_reading = next(item for item in audit["boundary_source_specific_readings"] if item["page"] == 25)
assert page25_reading["scan_variant_for_anchor"] == "逆則凶"
page26_first = next(row for row in rows if row["block_id"] == "P000026-C001")
assert page26_first["structural_role"] == "commentary_unaligned"
assert page26_first["collated_text"] is None
assert page26_first["source_text"].startswith("無位而配合於中官")
page27_first = next(row for row in rows if row["block_id"] == "P000027-C001")
assert page27_first["collated_text"] == "凭福恃势为四凶"
assert [item["id"] for item in audit["reference_only_omissions"]] == [
    "REF-OMIT-P020-P021-001",
    "REF-OMIT-P026-P027-001",
]
page28_main = next(row for row in rows if row.get("reference_segment_index") == 300 and row["source_page"] == 28)
assert page28_main["source_page"] == 28
assert page28_main["collated_text"] == "玩味，则知景纯之心法矣"
page28 = [row for row in rows if row["source_page"] == 28]
assert len(page28) == 3
assert page28[0]["structural_role"] == "commentary_unaligned"
assert page28[0]["source_text"].endswith("學者當熟讀")
assert page28[0]["continues_from_previous_page"] is True
assert page28[1]["reference_segment_index"] == 300
assert page28[1]["source_text"] == "玩味則知景純之心法矣"
assert page28[2]["structural_role"] == "commentary_unaligned"
assert page28[2]["source_text"].startswith("或問曰是開闢以來")
assert page28[2]["source_text"].endswith("或棄自家之吉地而")
assert page28[2]["continues_to_next_page"] is True
assert len(page28[2]["regions"]) == 4
assert not any(row.get("reference_segment_index") == 300 and row["source_page"] == 29 for row in rows)
page29 = [row for row in rows if row["source_page"] == 29]
assert len(page29) == 2
assert page29[0]["structural_role"] == "running_header"
assert page29[0]["source_text"] == "郭朴塟經 卷一"
assert page29[1]["continues_from_previous_page"] is True
assert page29[1]["source_text"].startswith("反別圖塟於非地者")
assert page29[1]["source_text"].endswith("以留待福人之來也")
assert audit["structural_overrides_applied"] == [{
    "reference_segment_index": 300,
    "source_pages": [28, 29],
    "target_page": 28,
    "status": "visually_confirmed_page_assignment",
}]
print(json.dumps({"passed": True, "candidate_blocks": len(rows), "page5_blocks": len(page5)}, ensure_ascii=False))
