# toyuv TeachingSpec

## 教学目标

用可运行的 Python 代码解释现代项目型包管理器的最小闭环：项目需求、依赖解析、锁定、环境同步
和命令执行。目标读者理解 Python 基础，但不需要了解真实包管理器的内部实现。

## 支持场景

1. 初始化带 `pyproject.toml` 的项目。
2. 添加一个或多个直接依赖。
3. 从本地索引递归读取传递依赖。
4. 使用回溯搜索选择满足所有约束的最高版本。
5. 在仍兼容时偏好已有锁文件中的版本。
6. 创建锁文件，并通过项目内容 hash 判断是否过期。
7. 创建真实 Python 虚拟环境，把锁定 artifact 精确同步进去。
8. 在同步后的环境中运行 Python 或其他命令。

## 必须保持的不变量

- 一个规范化包名在单次解析中最多选择一个版本。
- 被选择版本必须满足所有直接和传递约束。
- 锁文件只有在完整解析成功后才会被替换。
- 锁文件的项目 hash 必须对应当前直接依赖和索引配置。
- sync 前先验证所有 artifact 及路径；状态文件最后写入。
- 精确同步完成后，环境中的受管包集合必须等于锁文件中的包集合。
- run 默认先确保 lock 和环境都是最新的。

## 对 uv 的证据映射

分析基于 uv 官方仓库浅克隆的 `7896d58`：

| toyuv 概念 | uv 证据 |
|---|---|
| 项目、环境和锁文件是不同状态 | `docs/concepts/projects/layout.md` |
| lock 是把需求解析为锁文件 | `docs/concepts/projects/sync.md` |
| sync 是从锁文件物化安装集合 | `docs/concepts/projects/sync.md` |
| run 前自动 lock 和 sync | `docs/concepts/projects/sync.md` |
| lock 保留 unchanged/changed 状态 | `crates/uv/src/commands/project/lock.rs` 中的 `LockResult` |
| 解析与 lock 是独立领域模型 | `crates/uv-resolver/src/resolver` 与 `crates/uv-resolver/src/lock` |
| sync 区分 create/check/update/replace | `crates/uv/src/commands/project/sync.rs` 中的 `SyncAction` |

尝试使用 `git-design-intent` 分析最近 12 个提交，但稀疏浅克隆按需获取 Git 对象耗时过长，
本轮主动中止。因此这里不对 uv 作者的历史动机作确定性声明；表中的结论来自当前文档和源码结构。

本机还使用 uv `0.9.26` 做了无依赖项目的动态对照：`uv init --bare` 创建包含项目名、版本、
Python 约束和依赖数组的 `pyproject.toml`；`uv lock` 生成锁文件；`uv sync` 创建 `.venv` 并审计
安装状态。当前官方源码提交与本机二进制版本不同，因此该实验只用于验证高层状态转换，不用于
推断当前实现的内部调用路径。

## 刻意省略

- 完整 PEP 440/508、environment marker、extra 和 dependency group；
- 同一个包针对不同平台锁定多个版本的 universal resolution；
- PyPI Simple API、认证、镜像、多索引和网络重试；
- wheel tag 选择、sdist 构建、build isolation 和 editable install；
- content-addressed 全局缓存、并行下载、hardlink/copy-on-write；
- workspace、Python 版本安装、工具安装、发布和审计；
- console script 生成、native extension 以及卸载脚本；
- uv 的性能目标和完整 CLI 兼容。

这些不是“不重要”，而是位于教学闭环之外。尤其是 marker、wheel tag、构建隔离和 hash 策略，
在真实包管理器里都属于正确性或安全边界。
