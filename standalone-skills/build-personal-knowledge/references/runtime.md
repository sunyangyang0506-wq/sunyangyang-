# 本地回放与私有归档

Python 3.10 及以上，仅使用标准库。在 Skill 目录运行。原始输入、SQLite、授权文件、模型响应和导出目录均保存在个人受限工作目录。公开仓只维护源码和合成样本。

## 回放

```sh
python3 scripts/kb.py --db replay.sqlite --policy assets/policy.example.json ingest assets/replay.json
python3 scripts/kb.py --db replay.sqlite --policy assets/policy.example.json show booking --as-of 3
python3 scripts/kb.py --db replay.sqlite --policy assets/policy.example.json verify
python3 scripts/kb.py --db replay.sqlite --policy assets/policy.example.json export snapshots
python3 -m unittest discover -s scripts -p 'test_kb.py' -v
```

连续导入同一输入只保留一份，修改相同 item 产生新修订。topic 和 item 使用稳定的短标识，locator 指向受限来源和版本。手工或宿主提炼后的结构化记录以 assets/replay.json 为样式。授权清单逐来源声明 read、store、sync、topics。每个输入显式分类为 ordinary，内部工作、健康、财务及第三方私人内容在准备输入时排除。内置正则只拦截部分常见凭据和邮件格式，材料分类由可信接入端承担。

## 输入与模型

kb_capture.py 的参数为 --db、--policy、--source、--topic、--scope、格式和输入文件。格式 chatgpt 接收导出中的一个 JSON 文件，按指定 conversation_id 仅读取当前分支。格式 codex 接收某次已授权的 codex exec --json 流，并核对 thread_id。inputs 授权项须精确匹配 [格式、会话或线程 ID、主题]。输入适配器面向已批准处理的特定会话，不应直接接入混合敏感资料的账户目录。Codex 适配器只存通用终态和退出码。聊天短片段仅供本地处理，默认不可导出。跨设备和后台覆盖取决于实际输入。

需要模型提炼时，在来源授权中显式配置 model=true、model_batch_limit 和获准运行的宿主。运行 `kb_distill.py --db DB --policy POLICY --source SOURCE prepare`。宿主使用当前已授权的模型，为每个 id 提议一项变化或 skip，以相同 source、version 和 decisions 数组响应。每项包含 id、kind、title、statement、与输入相符的 evidence 短语及可选 conditions。调用相同命令的 `apply RESULT.json` 导入。模型不能自行改变来源、角色、数据去向或运行工具。只向获准的模型提供 prepare 输出，不额外读取本地材料。脚本本身没有模型密钥、付费调用或网络推理。复核引用和角色后，语义结论仍标候选。未经授权的来源不进入模型流程。

停更检查用 `kb.py --db DB --policy POLICY review metadata.json --idle-hours 48`。metadata 包含 source、coverage、last_activity 和 checked_through，两个时间均须带时区。complete 应由能够证明完整覆盖的适配器提供。ready 返回可回顾的事件和唯一指纹，只表示符合回顾条件。

## 私有归档

首次建专用私有仓时初始化默认分支。把所有者/仓名填入本地 policy 的 repository，把经核验的 GitHub 数字仓库 ID 填入 repository_id，登录 GitHub CLI。运行 `kb.py --db DB --policy POLICY sync --dry-run` 查看待归档文件，再运行 `sync`。真实同步会复核仓库身份、私有状态及写权限。每个不可变快照写入 batches/<内容摘要>/，逐文件使用远端 Git blob 指纹核验。连续重放同一批不会产生空提交；网络中断后使用同一库重新运行 sync。撤权后本地读取和新快照按当前许可筛选。旧导出、旧提交和备份仍须单独清理。离线模式可用 export 生成同一份快照，供经授权的 GitHub 连接器归档。
