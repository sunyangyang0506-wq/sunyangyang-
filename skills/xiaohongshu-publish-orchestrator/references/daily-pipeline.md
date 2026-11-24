# 每日生成、交接和发布的执行契约

## 两端职责

生成端检索、核验、制作完整正文与实际原图，并输出当期发布包和清单。发布端是唯一提交者，负责取回、脱敏、平台排版和后台回执。生成端没有本机浏览器不代表发布端失败；两端不要各自提交同一稿件。

读取实际配置的时区和时间，不在通用 Skill 写死用户账号、聊天 ID 或本机目录。生成端提前完成，发布端按既有补查窗口恢复。可选远程归档单独记状态，不做默认发布前提。

交接清单包含 date、timezone、content_version、images_expected，以及按顺序的 images[number,file,caption,sha256,width,height,section]。完整 Markdown 在正确段落嵌入相对图片路径，图注紧邻图片。清单与实际字节必须一致。原附件不可取回时，生成端同次直接展示原始图片，保留原 ZIP 供恢复。

源端不能写入原稿 Page 时，交接完整 Markdown、清单和明确的待补写状态，由发布端在可用的既有 Page 中按日期补写最新稿与归档，并读回核对；已有同日内容则保留人工修改，仅补缺项。发布后同步真实审核状态与证据位置。Page 写入与平台提交分别记录；归档待补不触发重发，也不能把生成端“未发布”沿用为平台结论。

## 本地可执行检查

[brief_workflow.py](../scripts/brief_workflow.py) 仅做文件校验、格式转换和原子提交记录，不登录、不上传、不代替浏览器操作，也不能自动判断事实或隐私。

每次收到触发，先执行 start 记录尝试，再按输出检查后台：

```bash
python3 scripts/brief_workflow.py start --directory "$RUN_DIR" --date "$BRIEF_DATE"
```

目录最后一级必须是显式日期。脚本读取该目录的 `进度.json`；新目录创建 STARTED，已有记录保留。SYNC_ONLY 表示只同步已有回执，VERIFY_PLATFORM_FIRST 表示结果可能已经提交，禁止再次点击。start/status 都不能代替笔记管理的当前状态。

原文与原图取回、人工信息脱敏后，保存含图位的 Markdown 及 image_order（也支持独立 manifest 的 images 数组）。使用 prepare 验证日期、数量、每张 SHA-256、PNG 完整性及 Markdown 顺序，生成 JPEG 兼容副本与导入 HTML：

```bash
python3 scripts/brief_workflow.py prepare --directory "$RUN_DIR" --date "$BRIEF_DATE" --manifest "$MANIFEST" --markdown "$MARKDOWN"
```

prepare 使用 Pillow 生成同尺寸 JPEG，透明区域合成为白底，不复制原 PNG 的文本元数据，也不修改原 PNG。Mac 与 Linux 都须在任务使用的 Python 环境安装 Pillow；缺失则停止并说明依赖，不自动回退到不同验收标准的系统转换。脚本逐行处理标题、保留全部来源 URL，表格按列名展开全部单元格；缺图、错序、不完整表格或未转换的专有引用会停止。图像的视觉、身份和隐私仍需逐张查看，平台上传后仍需逐处核对图注。

## 提交前原子占用

完成实际后台检查后，在当期目录保存检查 JSON 和预览截图。JSON 包含 date、带时区的 checked_at、evidence_file、images_expected、images_loaded_count，且以下项必须是 JSON 布尔 true：

`account_matches, dedupe_clear, body_complete, privacy_pass, image_positions, images_loaded, markers_removed, cover_first, preview_complete, public_visibility`

这些值必须来自本次实际观察，不能预填为真。时间超过15分钟或图数不同于本地清单时停止。再执行：

```bash
python3 scripts/brief_workflow.py begin-submit --directory "$RUN_DIR" --date "$BRIEF_DATE" --checks "$CHECKS"
```

仅 SUBMIT_ONCE 允许随后点击一次。脚本在文件锁内原子写入 SUBMITTING；并发第二个调用得到 VERIFY_PLATFORM_FIRST。提交后先查笔记管理，保存真实证据，再用 result 同步 UNDER_REVIEW / PUBLISHED / REJECTED / UNKNOWN：

```bash
python3 scripts/brief_workflow.py result --directory "$RUN_DIR" --date "$BRIEF_DATE" --result UNDER_REVIEW --evidence receipt.jpg
```

结果不明时不清空记录重试。只有实际后台明确未提交且同一草稿已核对时，才提供新的证据 JSON（date、checked_at、evidence_file、submission_explicitly_absent=true、same_draft_verified=true），用 resolve-unsubmitted 恢复 DRAFT。已审核中、公开或拒绝的稿件不能用此命令重置。

## 验收与运行边界

用户要求脱离本机运行时，先在实际云环境验证官方登录入口、浏览器接管、账号匹配、跨运行可复用的浏览器会话、持久化素材与账本以及真实云调度。创建云任务、打开登录页、一次登录和启用定时是不同结果，分别记录。云端验证完成后切换唯一提交者并停用旧发布端；无法确认会话和账本跨运行保留时，不将临时沙盒或临时后台进程当作常驻部署。云端继续使用正常身份验证流程，不从本机提取登录凭据。

先对隔离目录验证原包，再对真实状态执行只读 status 和后台去重。不要发测试笔记验证权限。定时任务必须保持启用并读回实际配置；新配置的下一次定时执行仍需核实结果，不能把保存配置称为无人值守验收通过。

运行依赖本机开机、任务应用可运行、Chrome 连接与账号会话有效。系统锁屏、扫码或平台设备验证按官方流程交接给本人，不关闭屏幕锁、不保存凭据或绕过验证。自动流程在异常时保存进度并报告；网络或模型执行失败不能假装完成。下一轮从同一记录恢复。

提交后审核中属于已提交，公开需要后台明确状态。后续同一工作流只读复查近期审核中回执并同步变化，不重新提交往期。每次报告区分配置、文件验证、真实提交、公开和计划运行验收。

## Mac 模式补充

已选择 Mac 时优先执行 [Mac 日常执行与验收](mac-runtime.md)。生成端不得在原件可读时自行发布。SCHEDULED、已预约和已发布等旧状态均按已提交处理；不改变标题或版本绕过去重。单命令文件锁不覆盖浏览器全流程，须由唯一串行执行器或 run_locked.py 保护整个运行。代码提交、Mac 安装、调度启用和未来自然运行的后台回执分别记录。
