# 事件行事曆 — 法說/財報日期紀律性記錄 + IV 凸起對照 (2026-10-13)

## 動機
用戶: 「財報發生日期要全部紀律性紀錄並用來分析,10/15 是台積電財報」。系統原本沒有事件行事曆,
IV 凸起/凹陷警示無法分辨「已知事件溢價」與「錯價/資料問題」。

## 來源 (不手打)
MOPS 重訊「法人說明會」公告已由 tmf-news-collector 落在 news_items (source_tier=1, 2026-07-22 起 515 筆/472 檔),
body 為固定格式: `1.召開法人說明會之日期：115/10/15 2.召開法人說明會之時間：14 時 00 分 3.…地點：… 4.…擇要訊息：…`。
台積電 Q3 法說 10/15 14:00 即由 9/29 公告 (news_uid 可追溯) 解析而得。

## 設計
- `data/event_calendar.csv` (git 追蹤, 為真相來源): date,time,type,name,symbol,impact,source,detail
  - type: earnings (自辦、擇要含 財務報告/財報/營運結果/業績展望) / investor_conf (受邀參加券商) / macro / settlement
  - impact: index (symbol ∈ INDEX_MOVERS 台指權值前 10) / stock
  - source: `mops:<news_uid>` 或 `manual`;upsert key (date, symbol, type);依 date,symbol 排序
- `scripts/event_calendar.py`: parse_mops_body / classify / sync (news_items → CSV) / load_events / events_between / add
- `iv_term.iv_term_lines(..., events=None)`: impact=index 的事件 → 找「結算時刻 > 事件時刻」的第一個到期
  (台積電 10/15 14:00 收盤後 → 落在 10/16 到期而非 10/14),輸出
  `📅 10/15 14:00 台積電 法說 → 10/16 到期 · 隱含事件波動 ±X 點 (x.x%)` 或 `無額外溢價`。
  事件溢價 = 該到期總變異數 − 以鄰近無事件到期推算的基準變異數 (每場 forward variance × 場數),
  負值 → 無額外溢價。
- 排程: `sync` 掛進 iv-snapshot 每次執行前 (同一 launchd, 09:00 前第一次);休市日不跑亦無妨 (公告多在盤後)。

## 驗證
單元測試 (parser、分類、upsert、事件→到期對應、溢價公式);sync 實跑後 CSV 含 2330 2026-10-15 14:00 earnings;
dry-run 期限表顯示事件行。
