---
name: douyin-persona-audit
version: 1.2.0
description: 在身份确认、平台许可和资料可访问的前提下，逐条研究用户本人抖音公开及已授权作品，提炼有时间戳的表达特征证据，回馈图文、口播与视觉 Skill；不依赖猜测或未经授权的采集。
---

# 抖音个人表达审计 Skill

## 1｜目的
对用户本人抖音账号建立可追溯的作品与表达证据，用于校准：
- 图文表达
- 口播节奏
- 视觉风格
- 评论触发点
- 内容栏目假设

本 Skill 不负责绕过登录、平台限制、版权、验证码、Cookie 或反爬机制。

## 2｜前置条件
- 用户明确确认账号归属。
- 作品属于公开可访问内容，或由用户主动授权提供。
- 若需要登录，登录验证由用户本人完成。
- 读取权限不等于下载、长期保存或再次公开的权限。

## 3｜必做步骤
1. 核验账号：昵称、主页、公开状态、核验时间。
2. 建立作品清单：作品ID、URL、发布时间、标题、类型、时长、可访问性。
3. 分页到可访问范围结束；无法证明完整度时写“可访问作品”，不得写“全量历史”。
4. 对可访问作品逐条观看/听取。
5. 建立时间戳证据，如：
   - 00:06 生活画面进入
   - 00:22 提出疑问
   - 01:10 情绪增强
6. 区分作者原声、配音、字幕和剪辑。
7. 只有实际读取评论后，才分析互动触发点。
8. 用 A/B/C 证据等级管理表达特征：
   - A：用户明确自述 + 多作品重复证据
   - B：少量作品支持
   - C：待验证假设
9. 将稳定结论反馈给其他 Skill，并保留来源、时间戳和审计日期。

## 4｜作品台账字段
至少记录：
- video_id
- video_url
- published_at
- title
- format
- duration_seconds
- media_access
- voice_is_original
- transcript_available
- visual_available
- comments_available
- views / likes / comments / favorites / shares（仅可见时）
- opening_0_3s
- scene_anchor
- question_turn
- mechanism_insight
- emotion_movement
- speaking_features
- timestamp_evidence
- audience_evidence
- confidence
- reviewed_at
- notes

## 5｜分析原则
### 语音
只有听过原声才能报告语速、停顿、音量、重音和情绪起伏。

### 视觉
静态照片只能说明该张照片中的表情、姿态和场景，不能推断稳定人格。

### 内容
用户本人原话优先；助手生成稿不能计入作者原始证据。

### 平台
抖音表现不自动等于小红书表现。跨平台结论必须重新验证。

### 评论
将评论触发原因区分为：
- 经历复现
- 价值观争议
- 补充故事
- 寻求方法
- 负面误解
- 其他

只有实际看到评论后才能统计。

## 6｜阻断规则
- 未访问视频，不得声称已看完账号。
- 未听音频，不得声称已学习真实语速/音色。
- 未读评论，不得声称已发现评论高频词。
- 无完整作品总数，不得写“覆盖100%”。
- 不为互动量强行制造家庭冲突、焦虑和标签化。
- 不自动上传、发布或保存全部媒体。

## 7｜交付
`账号确认表 + 作品清单 + 逐条证据台账 + 表达指纹报告 + Skill变更说明 + 待确认事项`

字段模板见：
`../../shared/douyin-work-ledger-template.csv`

采集协议见：
`../../shared/douyin-full-account-protocol.md`
