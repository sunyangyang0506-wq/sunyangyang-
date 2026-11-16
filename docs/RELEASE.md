# Release Process

仓库已配置Tag驱动Release：

`vX.Y.Z` tag推送后，GitHub Actions自动执行校验、Golden Eval、单测、打包、SHA256并创建Release。

本地预打包：

```bash
make check
make package
```

产物：
- 每个Skill独立zip
- 完整skills-bundle
- SHA256SUMS.txt

当前GitHub连接器没有创建Tag/Release的写接口，因此首次Tag需要在支持git push的环境执行：

```bash
git tag v3.6.0
git push origin v3.6.0
```

之后Release流程自动完成。
