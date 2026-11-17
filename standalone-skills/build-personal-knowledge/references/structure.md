# 结构与字段约定

知识库目录：`config.json`；`index.json`；`ideas/<id>.json` 和 `<id>.md`；`evolution/<id>.jsonl`；`maps/<topic>.md`；`reviews/<date>.md`；`sources/`（仅保存获准的最少必要原始证据）。项目交付物留在项目仓库，以路径及版本关联。

## 配置

```json
{
  "schema_version": "1.0",
  "timezone": "Asia/Shanghai",
  "idle_hours": 48,
  "repository": null,
  "branch": null,
  "visibility": "private",
  "source_scope": [],
  "scheduler_status": "not_configured",
  "last_successful_sync": null
}
```

repository 必须来自用户指定或可验证的现有专用知识库。禁止挪用健康、EDC、背题宝等无关仓库来存全部个人知识。未配置目标不阻塞内容提炼，但不得虚报 Git 同步成功。

## 想法对象

- `id`：稳定 ID，例如 IDEA-20261117-001。日期表示建档日期；创建前查索引分配序号，并检查碰撞。
- `title, topic, tags, revision, created_at, updated_at`：时间使用含时区 ISO 8601。
- `problem, audience, intended_value, core_idea, mechanism`：问题、对象、价值、主张、作用机制。
- `assumptions, constraints, alternatives, validation_plan`：假设、约束、选项及检验方式。
- `claims[]`：`id, text, kind, evidence_ids, confidence`；kind 为 user_statement / observed_fact / assistant_inference / open_question；confidence 为 confirmed / tentative / unknown。
- `sources[]`：`id, locator, source_type, occurred_at, captured_at, excerpt, access_scope`；定位符为真实对话/消息/文件路径/URL；无法获得消息 ID 时使用诚实的上下文定位说明。
- `relations[]`：`target_id, type, rationale, evidence_ids`；type 为 deepens / branches_from / contradicts / supersedes / merges / reuses / tests。
- `project`：`id, locator, status, next_action, owner, acceptance, blockers`；未知字段 null。
- `status`：captured / exploring / testing / validated / rejected / dormant；停更只触发回顾，不能自动判定项目放弃。
- `sensitivity, sync_status`：private 或用户指定级别；pending / synced / blocked；synced 要有远程提交证据。

## 演变事件

每行一个 JSON 对象：`event_id, idea_id, occurred_at, recorded_at, event_type, before, after, trigger, evidence_ids, attribution, impact, source_fingerprint`。

同一来源定位符、内容及事件类型生成确定性的 source_fingerprint（可用 SHA-256），重复导入先查重。缺来源 ID 时保留明确标识的本地来源 ID。事件追加后不得悄悄修改；纠正以新事件指向旧事件。

索引维护每个主题的最新版本、项目链接、来源更新时间、最近回顾指纹。所有关系 target_id 必须存在，否则列入待补充，不能生成悬空图节点。
