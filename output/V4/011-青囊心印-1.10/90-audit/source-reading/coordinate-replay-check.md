# UC000121 / UC000122 有限坐标更正复核

2026-09-29，独立执行 `/root/qingnang_source_004_007`。本次仅检查两项新坐标输入及文字不变性；依已读取的源文重建、疑点裁决 Skill 证据优先与独立回放要求。实际查看 P000013.native.jpeg、P000019.native.jpeg 及 P000019-lower-detail.png，读取更正明细、两份 before 快照、两份 current inputs 和当前 blocks。未修改源文或 ledger，不作全书通过、正式 closure 或其他疑点关闭。

## 有限结论

| 项目 | 当前实际记录 | 对图判断 |
|---|---|---|
| UC000121 / P000013-B010 | bbox `[699,795,914,1341]`，无 regions | 修正得到图证支持。下半右侧五列注均纳入，原漏出的第五列「沐浴宜靜來則多淫庫方宜去來則翻起俱為不得位而成凶」现已覆盖。左邻转接注 B011 保持独立，不见因此吞并下一列正文。 |
| UC000122 / P000019-B018 | bbox `[610,787,652,1230]`；唯一 region 同该框 | 修正得到图证支持。「明元空只在五行中知此理不必尋納甲」位于本单列。原 `[650,984,698,1169]` 的右邻注文区域已从该经句删除，没有再将其当跨列尾文。 |

两项 current input 坐标与 blocks 坐标一致。更正前后逐页、逐数组块比较 text：`pages-013-014.json` 24 块、`pages-019-020.json` 44 块，均为 **0 项文字差异**，页数和块数不变。两目标块的 current source_text 与 input text 对应；本次修改不涉及补字、删字或重排文字。更正明细的 input/output SHA256 与实际 before/current 文件相符。

## P19-B011 褪印限制

再次查看后，P19-B011 下半约 x650–784、y867–1188 的大片淡印 **仍不能唯一读取**。可辨的前后字不构成恢复中间整段的充分证据；当前两个 `□` 所代表的未辨字组，不能当成各确定只缺一个字。删除 B018 的错列 region 并未增加这片原图信息，也没有解决 B011 的残缺/候选问题。

本次不提出猜补，不对 B011 的全部候选字串作确认，不将 UC000121/122 的坐标支持外推为该段文字闭合。保留当前未决，除非取得更清晰原图或其他新的、可定位证据；不再进行无新增证据的全书循环复核。

## 实际读取文件 SHA256

路径相对本书工作区；这些值是本执行读取时的身份，不覆盖前一份 correction-replay-independent.md 所绑定的旧状态。

| 文件 | SHA256 |
|---|---|
| 20-source/blocks.jsonl | 4F9A38B698EF5255507F8E8DED776C49B6D1975BD253DA8464AF05BB8435A77B |
| 90-audit/source-reading/corrections-coordinate-replay.json | 5E53A59EA995E73228DC866DC376499431F10414812471D8DFD358BAF3BD4152 |
| 90-audit/source-reading/snapshots/before-coordinate-replay/pages-013-014.json | 6B8B31BF9607E192EB4C54011FF81C3A508C12F6EAD3FD74F79BD1F30E908317 |
| 20-source/transcription-inputs/pages-013-014.json | C0A3F0A595E675ACF84FE2CCE10AE8695256537254AF99FF7E4842E335A57E94 |
| 90-audit/source-reading/snapshots/before-coordinate-replay/pages-019-020.json | F93F5606FD8FA7186373B4D7CFC8621343895EC3DD52F7DF59B6B7B842103D68 |
| 20-source/transcription-inputs/pages-019-020.json | 790DB550A94AC7435DEA95E8B05E88322FF906BDBBA18BBA51AD9B3F03268638 |
| 20-source/pages/P000013.native.jpeg | 7FD0852DD63610BF4E52F9DD3B18EA233EC6FE29D4B2A387EB375AC0E829B213 |
| 20-source/pages/P000019.native.jpeg | 4799292DCF4FB8BEF6E436ABB5A01505FE2B03DC68646EEBB04CCC64149504E8 |
| 20-source/pages/P000019-lower-detail.png | 966EBD4E2173C7400931EA5FECA2AEC7AA281B01111D7334E68506EE46597C19 |
