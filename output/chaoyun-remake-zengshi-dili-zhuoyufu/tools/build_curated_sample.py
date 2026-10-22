#!/usr/bin/env python3
"""Build the corrected ten-page evidence and reading layers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOK_ID = "a8905dff46683b57"
SOURCE_SHA = "a8905dff46683b57b0bf695c8263c0a098b4ef0106e571564f6a1c898b970a06"


PAGES = [
    {
        "page": 1, "type": "title", "confidence": 0.99,
        "source": "光緒二十年季春月重鐫\n嚴陵張九儀增釋地理琢玉斧巒頭歌括\n苧蘿袁玉書參訂\n文奎堂藏板",
        "normalized": "光绪二十年季春月重镌。严陵张九仪增释《地理琢玉斧峦头歌括》。苎萝袁玉书参订。文奎堂藏板。",
        "modern": "光绪二十年春季三月重新刊刻。严陵人张九仪增补解释《地理琢玉斧峦头歌括》，苎萝人袁玉书参与校订，文奎堂藏版。",
        "uncertainty": [],
    },
    {
        "page": 2, "type": "noncontent", "confidence": 0.70,
        "source": "〔館藏章及手寫編號〕\n1086230\nBF\n1774\nF4H75\n1894\nX1",
        "normalized": "〔馆藏章及手写编号〕1086230；BF；1774；F4H75；1894；X1。",
        "modern": "这一页是馆藏和分类信息，不属于原书正文。可辨编号包括 1086230、BF、1774、F4H75、1894、X1。",
        "uncertainty": ["馆藏章文字受叠印影响，未强行释读。"],
    },
    {
        "page": 3, "type": "body", "confidence": 0.96,
        "source": "余素不諳地理事，然憶在京師時，每見親友家有倏數年而興發者，又倏數季而衰落者，人莫不曰：某家某地得也，某家某地失也。",
        "normalized": "余素不谙地理事，然忆在京师时，每见亲友家有倏数年而兴发者，又倏数季而衰落者。人莫不曰：某家某地得也，某家某地失也。",
        "modern": "我一向不懂风水。回想在京城时，常见亲友之家有的几年间忽然兴旺起来，有的不过几个季度便衰败下去。人们总会说：某家是因为选对了地方，某家是因为选错了地方。",
        "uncertainty": ["连接两种情形的字图像略糊，结合字形与对举结构暂定为‘又’。"],
    },
    {
        "page": 4, "type": "body", "confidence": 0.94,
        "source": "而余總未之知也。及來佐理越郡，山川秀色燦爛目中，里巷大小戶莫不諳陰陽、搜吉地，余因是亦動念焉。迨攝暨陽事，諸生中得一袁玉書者，素行孝友人。",
        "normalized": "而余总未之知也。及来佐理越郡，山川秀色灿烂目中，里巷大小户莫不谙阴阳、搜吉地，余因是亦动念焉。迨摄暨阳事，诸生中得一袁玉书者，素行孝友人。",
        "modern": "我一直不明白其中的道理。后来到越郡协助处理政务，满眼都是秀丽山川；街巷里的大小人家，无不谈论阴阳、寻访吉地，我也因此留意起风水。后来代理暨阳政务时，我在诸生中结识袁玉书；他平日孝顺父母、友爱兄弟。",
        "uncertainty": ["‘暨陽’受印章和墨色影响，结合地名及字形暂定。"],
    },
    {
        "page": 5, "type": "body", "confidence": 0.86,
        "source": "也為嚴尊卜葬域，延堪輿家以求鶴舉，而人各異詞，理多淆雜，吉凶無一定之見，心甚〔缺二字〕之。庚辰春，嚴陵張九儀以探親戾止，諸生袁玉書素讀其《四彈子》《砂……",
        "normalized": "也为严尊卜葬域，延堪舆家以求鹤举，而人各异词，理多淆杂，吉凶无一定之见，心甚〔缺二字〕之。庚辰春，严陵张九仪以探亲戾止，诸生袁玉书素读其《四弹子》《砂……",
        "modern": "袁玉书曾为父亲选择墓地，延请堪舆家，希望妥善安葬；但各人说法不同，道理混杂，对吉凶没有一致判断，他对此十分困惑。庚辰年春天，严陵人张九仪因探亲来到这里。袁玉书平时就研读张九仪的《四弹子》和《砂……》（书名在下一页接续）。",
        "uncertainty": ["‘心甚’之后两字无法可靠辨认。", "末句跨页，书名在下一页接续。"],
    },
    {
        "page": 6, "type": "body", "confidence": 0.98,
        "source": "水要訣》兩書，每圖會晤之，無由。一旦賁臨，相見不啻飢渴之得遇飲與食也。遂盡弟子禮，執經而問難焉。追隨間，覆視古仙蹟，其中貴賤貧富，了了在目，一如……",
        "normalized": "《水要诀》两书，每图会晤之，无由。一旦贲临，相见不啻饥渴之得遇饮与食也。遂尽弟子礼，执经而问难焉。追随间，覆视古仙迹，其中贵贱贫富，了了在目，一如……",
        "modern": "……《砂水要诀》两部书，一直想与作者见面，却没有机会。一天张九仪忽然到来，彼此相见，就像饥渴的人得到饮食一样。袁玉书于是尽弟子之礼，拿着经书请教疑难。跟随学习期间，他们复核古代名师留下的风水遗迹，其中所对应的贵贱贫富都清楚地呈现在眼前，仿佛……",
        "uncertainty": ["本页首字承接上一页书名。", "末句跨页，下一页继续。"],
    },
    {
        "page": 7, "type": "body", "confidence": 0.96,
        "source": "素識者於人。遂以為神奇詭怪，不可以尋常測識，而不知其實平易淺近。篋中所手錄者，不過一《琢玉斧巒頭歌括》而已。夫《琢玉斧》，初學入門之書，而九儀……",
        "normalized": "素识者于人。遂以为神奇诡怪，不可以寻常测识，而不知其实平易浅近。箧中所手录者，不过一《琢玉斧峦头歌括》而已。夫《琢玉斧》，初学入门之书，而九仪……",
        "modern": "……就像熟悉一个人的人观察他一样。人们因此以为这门学问神奇诡异，不能用常理揣测，却不知道它实际上平易浅近。张九仪箱中亲手抄录的，不过是一部《琢玉斧峦头歌括》。《琢玉斧》原是初学者的入门书，而张九仪……",
        "uncertainty": ["首句承接上一页。", "末句跨页。"],
    },
    {
        "page": 8, "type": "body", "confidence": 0.90,
        "source": "增釋之，證之以己註舊地而發明之。是知讀書者不在多而在精，固非獨制舉家為然也。理河洛之理，挨星之法，口授以傳者固有秘旨，而取其理而布施之……",
        "normalized": "增释之，证之以己注旧地而发明之。是知读书者不在多而在精，固非独制举家为然也。理河洛之理，挨星之法，口授以传者固有秘旨，而取其理而布施之……",
        "modern": "……为它增补解释，又以自己注解过的旧地案例加以印证和阐明。由此可知，读书不在于数量多，而在于钻研得精；这并不只是科举应试者才如此。河洛之理、挨星之法中，靠口授传承的部分固然有秘密要旨；但把其中的道理推广到实际……",
        "uncertainty": ["‘證之’二字墨色较淡，结合字形和句义暂定。", "末句跨页。"],
    },
    {
        "page": 9, "type": "body", "confidence": 0.95,
        "source": "實跡，取其法而運用之岡巒，實不外此歌括中所論之密旨。而余之素不諳地理者，捧誦之，批閱之，亦不覺為之動念已。\n峕",
        "normalized": "实迹，取其法而运用之冈峦，实不外此歌括中所论之密旨。而余之素不谙地理者，捧诵之，批阅之，亦不觉为之动念已。\n时",
        "modern": "……落实到实例，把其中的方法运用于山川形势，也都没有超出这部歌括所讨论的精要。我这样一个向来不懂风水的人，捧读、批阅此书，也不知不觉受到触动，开始留心这门学问。",
        "uncertainty": ["页末‘峕’为‘时’的异体字，是题记时间的起始标记，不并入正文。"],
    },
    {
        "page": 10, "type": "colophon", "confidence": 0.99,
        "source": "康熙辛巳仲春，奉直大夫、同知紹興府事、漁陽祖光珮題於臥龍官舍。",
        "normalized": "康熙辛巳仲春，奉直大夫、同知绍兴府事、渔阳祖光珮题于卧龙官舍。",
        "modern": "康熙辛巳年仲春，奉直大夫、绍兴府同知、渔阳人祖光珮，题写于卧龙官舍。",
        "uncertainty": [],
    },
]


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    generated = datetime.now(timezone.utc).isoformat()
    book = {
        "schema_version": "1.0", "book_id": BOOK_ID,
        "title": "增释地理琢玉斧峦头歌括", "author": "张九仪",
        "source_pdf_sha256": SOURCE_SHA, "source_pdf_pages": 80,
        "source_pages": 10, "edition_scope": "quality_sample_pages_1_10",
        "target_reader": "现代普通读者", "target_language": "zh-Hans",
    }
    dump_json(ROOT / "book.json", book)
    profile = {
        "schema_version": "1.0", "book_id": BOOK_ID, "source_pdf_pages": 80,
        "included_pages": list(range(1, 11)), "page_type": "scan_vertical_zh_hant",
        "routes": ["dual_visual_transcription", "parallel_edition_alignment", "independent_visual_review"],
        "status": "sample_only",
    }
    dump_json(ROOT / "10-diagnosis" / "profile.json", profile)
    dump_jsonl(ROOT / "10-diagnosis" / "page-map.jsonl", [
        {"schema_version": "1.0", "page_id": f"P{x['page']:06d}", "source_page": x["page"],
         "classification": "image_only" if x["type"] == "noncontent" else "scan",
         "layout": "vertical_single_block", "language": "lzh" if x["type"] == "body" else "zh-Hant",
         "route": "dual_visual_plus_reference_alignment"}
        for x in PAGES
    ])

    source_rows: list[dict] = []
    normalized_rows: list[dict] = []
    modern_rows: list[dict] = []
    edited_rows: list[dict] = []
    changes: list[dict] = []
    uncertainty_rows: list[dict] = []
    for item in PAGES:
        page = item["page"]
        page_id = f"P{page:06d}"
        block_id = f"{page_id}-B001"
        base = {
            "schema_version": "1.0", "book_id": BOOK_ID, "page_id": page_id,
            "block_id": block_id, "source_page": page, "block_type": item["type"],
            "bbox": None, "source_image": f"20-source/pages/{page_id}.jpg",
            "source_text": item["source"], "language": "lzh" if item["type"] == "body" else "zh-Hant",
            "disposition": "noncontent" if item["type"] == "noncontent" else "retained",
            "confidence": item["confidence"], "evidence": ["vision_pass1", "vision_pass2", "visual_spot_check"],
            "notes": item["uncertainty"],
        }
        source_rows.append({**base, "operation": "source", "normalized_text": None, "modern_text": None})
        normalized_rows.append({**base, "operation": "normalize", "normalized_text": item["normalized"], "modern_text": None})
        modern_rows.append({**base, "operation": "translate", "normalized_text": item["normalized"], "modern_text": item["modern"]})
        edited_rows.append({**base, "operation": "edit", "normalized_text": item["normalized"], "modern_text": item["modern"]})
        changes.append({"schema_version": "1.0", "book_id": BOOK_ID, "page_id": page_id, "block_id": block_id,
                        "operation": "traditional_to_simplified_and_punctuation", "before_sha256": hashlib.sha256(item["source"].encode()).hexdigest(),
                        "after_sha256": hashlib.sha256(item["normalized"].encode()).hexdigest()})
        for note in item["uncertainty"]:
            uncertainty_rows.append({"schema_version": "1.0", "page_id": page_id, "block_id": block_id,
                                     "severity": "medium", "status": "open", "note": note,
                                     "source_image": f"20-source/pages/{page_id}.jpg"})

    dump_jsonl(ROOT / "20-source" / "blocks.jsonl", source_rows)
    dump_jsonl(ROOT / "30-normalized" / "blocks.jsonl", normalized_rows)
    dump_jsonl(ROOT / "30-normalized" / "changes.jsonl", changes)
    dump_jsonl(ROOT / "40-modernized" / "blocks.jsonl", modern_rows)
    dump_json(ROOT / "40-modernized" / "terminology.json", {
        "暨阳": "今浙江诸暨一带的旧称", "堪舆": "传统风水术的旧称", "挨星": "按特定规则推排星位的方法"
    })
    dump_jsonl(ROOT / "50-edited" / "blocks.jsonl", edited_rows)
    dump_jsonl(ROOT / "90-audit" / "uncertain-items.jsonl", uncertainty_rows)

    def source_md() -> str:
        parts = ["# 增释地理琢玉斧峦头歌括 - 前十页忠实转录\n"]
        for row in source_rows:
            parts += [f"\n## 原 PDF 第 {row['source_page']} 页\n", f"![原页 {row['source_page']}]({row['source_image']})\n",
                      "\n### 忠实转录\n", row["source_text"] + "\n"]
            if row["notes"]:
                parts += ["\n### 存疑\n", *[f"- {x}\n" for x in row["notes"]]]
        return "".join(parts)

    def reading_md() -> str:
        parts = [
            "# 增释地理琢玉斧峦头歌括\n\n",
            "> **前十页质量样章**：本文件不是整本成品。每页保留扫描证据、忠实转录、简体点校和现代白话。\n\n",
            "> 在线异本仅作校勘线索，最终取舍以当前扫描页字形为准。\n",
        ]
        for item in PAGES:
            page = item["page"]
            parts += [f"\n## 原 PDF 第 {page} 页\n\n", f"![原 PDF 第 {page} 页](../20-source/pages/P{page:06d}.jpg)\n\n",
                      "### 忠实转录\n\n", item["source"] + "\n\n",
                      "### 简体点校\n\n", item["normalized"] + "\n\n",
                      "### 现代白话\n\n", item["modern"] + "\n"]
            if item["uncertainty"]:
                parts += ["\n### 校勘存疑\n\n", *[f"- {x}\n" for x in item["uncertainty"]]]
        return "".join(parts)

    (ROOT / "20-source" / "source.md").write_text(source_md(), encoding="utf-8")
    (ROOT / "30-normalized" / "normalized.md").write_text(reading_md(), encoding="utf-8")
    (ROOT / "40-modernized" / "modernized.md").write_text(reading_md(), encoding="utf-8")
    (ROOT / "50-edited" / "modern-reading.md").write_text(reading_md(), encoding="utf-8")
    (ROOT / "60-publication" / "modern-reading.md").write_text(reading_md(), encoding="utf-8")
    state = {
        "schema_version": "1.0", "book_id": BOOK_ID, "updated_at": generated, "edition_scope": "sample_pages_1_10",
        "stages": {name: {"status": "passed_with_ledger" if name in {"source", "normalized", "modernized", "edited"} else "passed"}
                   for name in ("intake", "diagnosis", "source", "normalized", "modernized", "edited")},
    }
    state["stages"]["publication"] = {"status": "pending"}
    dump_json(ROOT / "run-state.json", state)
    print(json.dumps({"pages": 10, "uncertainties": len(uncertainty_rows), "workspace": str(ROOT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
