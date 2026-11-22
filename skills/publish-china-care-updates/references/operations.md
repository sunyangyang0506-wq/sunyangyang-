# 发布、回执与咨询

## 发布配置

- 私有配置保存发布账号 ID、已授权操作者、时区、渠道、媒体存放位置、可选非临床咨询入口及状态库位置。第一次绑定以服务返回的账号核对。默认每个北京时间自然日最多一期，一张主图加一个 15–30 秒英语字幕视频。没有时点偏好时建议北京时间 21:00，每天检查已有同目的任务再配置一个任务。不要改动中文早报。
- 原创图片和视频随每期生成，脚本输出 1280×720 PNG、H.264 MP4、英文字幕文本和带哈希值的清单。视频无声，所有内容可从字幕读完。检查小屏可读性、字幕完整、数字和图片授权。示例可在任意日期离线演练；真实发送只接受当日重新核对过的 edition。
- 保持信息台账与发布状态在持久化私有存储。一次只选一个发布渠道；切换前核对目标账号的时间线、排程和旧渠道未决请求。不要向公共 GitHub 提交线索、凭据、授权记录或含患者数据的素材。

### 路径 A · Metricool

1. 用 getbrandsettings 取得已绑定 X 账号与品牌，并复查连接、发送权限和时区。无账号时在 Metricool 的 Connections 中绑定；X 属于部分套餐的付费附加项，任何购买由账号持有人决定。
2. 使用 Metricool 的媒体上传/图库，或已经允许公开投递的媒体托管，取得平台能读取的 PNG 和 MP4。通过 URL 交付时必须公开可直读、稳定、指向正确文件，分别验证 MIME。私有文档链接、sandbox 路径和临时签名地址均不可填作长期素材地址。若连接器只收 URL，可经已授权的 Metricool 媒体上传界面从设备上传，或用已配置的路径 B。不得通过自动操作 x.com 网页发帖。
3. 查询已排程和已发布内容，与账号、日期、story_key/revision、英文文本和媒体核对。在私有状态台账持久预占主帖/视频各自的键。对可保存 X thread 的入口提交同一串两节，主帖附 PNG，第二节附 MP4。仅支持单条的连接器分成两条：为首条排程，取得 X 原帖公开链接后再把链接加入可独立阅读的视频帖，校验字数，然后投递。禁止把两个素材类型硬塞进只接受单一类型的调度字段。
4. 保存平台返回的 schedule ID 和时间；回读排程校验账号、文本、图片/视频均在。到点通过已发记录或目标账号时间线拿到 X status ID/链接，核对两段的文案与附件后才报已发布。账号过期、回执不明或附件被忽略时暂停相应动作，先对账后修复。若首条已发仅补视频。私有台账至少记录 account、day、story_key、revision、slot、text_hash、status、provider_id、post_url、last_checked。
5. 参考 [Metricool X 发布说明](https://help.metricool.com/schedule-and-publish-on-x-twitter-klho8)、[官方媒体接入说明](https://help.metricool.com/basic-guide-for-api-integration-r97af)、[X 自动化规则](https://help.x.com/en/rules-and-policies/x-automation)。按适用平台规则标识自动化账号。禁止主动批量回复、私信、关注、按疾病筛人或抓取个人健康信息。

### 路径 B · X 用户授权 API

在可信运行环境注入短期有效的 `X_USER_ACCESS_TOKEN` 和已验证的 `X_EXPECTED_USER_ID`。应用以 OAuth 2.0 用户上下文取得 tweet.read、tweet.write、users.read、media.write，长期运行由宿主凭据服务按需刷新。应用级令牌不能代表账号发帖。在同一持久私有卷设置状态库；多台主机应统一派发给一个写入者。若是临时执行环境且没有可持久化的账本，就用支持排程和对账的平台。需要相应 X API 访问权限和额度。

```bash
python3 scripts/publish_x.py edition.json /private/path/edition --state /private/volume/x-care.sqlite --send
```

先同时准备好两项媒体，再逐段提交。首次创建前保留意图；返回成功即保存 ID，再用 GET 比对身份、文本、媒体及父帖。超时或不确定结果保留 pending，不自动重发。在时间线匹配同一账号、正文和媒体取得实际 ID 后，传 `--recover root=实际ID` 或 `--recover video=实际ID` 加 `--send` 与同一 `--state`，脚本先回读核对，再恢复缺少的一节。无法确认不存在的写入交人工对账，不重放。过日的半成品先处理旧帖回执与证据时效，再单独补发或标注不补。不要将 pending、queued 或 partial 报成 published。接口见 [写帖](https://docs.x.com/x-api/posts/create-post)、[分片媒体](https://docs.x.com/x-api/media/quickstart/media-upload-chunked)。

## 读者行动与商机归因

- **就医导航**。发预约前可问的问题，让读者自行向官方机构确认语种、材料、报价、支付和随访。通用导航帖可邀请读者选择城市或想看的办事指南，例如 “Which city should our next booking guide cover?” 在已授权、验证过的自有非临床入口可提供公开清单。避免承诺代约、诊疗、价格或跨境处方。
- **研究及靶向药**。解释监管和研究材料，给官方标签或试验登记页；不得根据评论推断诊断、选择药物或招募患者。将“请帮我判断用药/入组资格”的来信转为“请向主管医生或试验中心询问”，无病历收集。同行提问可列为下期公共选题。
- **机构合作**。在独立的非临床运营话题下邀请国际部、翻译、保险或服务协调团队通过已核验的业务入口主动联系。示例：“Does your international desk publish a pre-visit checklist in English? We’re collecting public examples.” 标明独立运营、利益关系和有无合作，不能把提及某院写成合作。
- **公开资讯与商业招揽**。科普稿仅附原始论文、监管文本或公共信息出处；不把特定疗法/医院、疗效陈述与付费咨询、预约跳转、买药、返点或赞助促销组合。涉及推广特定诊疗服务、付费转介或定向广告时，将内容转入独立商业审查，核实运营地、目标市场与主体资质。参考 [市场监管总局等三部门医疗广告认定指南](https://www.samr.gov.cn/zt/ndzt/2025n/ggf/zyfb/art/2025/art_8daf3ed052d749fcbee6eb3909b29e10.html)。
- **私有最小记录**。只记录主动询问的随机编号、来源 post_id/经同意的来源码、咨询类别、可选城市/语言、联系许可、下一步、状态与更新时间。本人提交、明确要求后续联系才可进入跟进队列。公开提问可匿名计数。未经授权不导出 DM、发送回复、与医院共享身份或保存病历。读者发送健康或身份材料时不复制到表或 Git，引导到接诊方正式通道，按账号的数据保留/删除规则处理。
- **判定标准**。点赞/播放为曝光；问资料是主动询问；明确提出具体非临床导航或机构合作需求，同时同意后续联系才是有效商机。状态按 received → qualified → handed_off → confirmed/closed；只在接收方确认后计确认对接。区分 B2C 导航、B2B 合作、医学个案和噪声。
- **复盘**。按发帖后 24 小时与 7 天读取授权可见的展现、播放、点击、去重主动询问、有效商机和确认对接。使用 post_id 或不含用户信息的来源码归因，无法归因单列。有效咨询率 = 可归因有效咨询 / 可归因去重主动询问；确认对接率 = 确认对接 / 有效商机。分母为零写 N/A，无法读取写 unknown。每周选择一个变量（城市、问题、格式或 CTA）比较，不能从曝光推算患者数或营收。


**可执行归因。** 从有权限的私有收件箱读取本账号收到的主动联系；没有读权限时报告“不可观测”。逐条判断具体需求、是否同意跟进，交给人工负责人时只在私有系统传递。对同一询问使用稳定的随机 UUID 十六进制值，在私有 JSONL 每行记录一个状态事件。字段为 `inquiry_key, post_id, category, stage, at, opted_in, specific_need`。category 用 navigation / partnership / medical_question / other。post_id 不可知用 null，at 使用带时区的 ISO 时间。输入从 received 起的完整历史；去重后按真实状态变化统计。运行 `python3 "$SKILL_ROOT"/scripts/inquiries.py events.jsonl` 输出每帖各类主动咨询、有效咨询、已交接和已确认数量。互动后台不可见或未取得完整数据时不得把未知报为零。
