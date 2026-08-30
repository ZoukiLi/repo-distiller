# toyuv

`toyuv` 是一个受 [uv](https://docs.astral.sh/uv/) 启发的教学型 Python 包管理器。它不调用
`pip` 完成核心工作，而是用少量纯 Python 代码展示五个状态如何衔接：

它也是 [Repo Distiller](../../README.md) 的第一个完整案例。独立验证器和一次真实运行报告位于
[`evidence/toyuv`](../../evidence/toyuv/)，用于证明这里的代码不仅可读，而且可以实际解析、
安装、导入、运行并拒绝冲突输入。

```text
pyproject.toml 中的宽松需求
          │
          ▼
   回溯式依赖解析
          │
          ▼
 toyuv.lock 中的精确版本
          │
          ▼
  .toyuv-env 中的实际文件
          │
          ▼
  在该环境中运行命令
```

它实现了：

- `toyuv init`：创建项目；
- `toyuv add`：修改直接依赖，然后自动 lock 和 sync；
- `toyuv lock`：解析传递依赖，偏好仍兼容的已锁定版本；
- `toyuv sync`：创建虚拟环境，并执行精确同步；
- `toyuv run`：在执行命令前自动 lock 和 sync；
- `toyuv tree`：从锁文件显示依赖树。

为了让示例离线、可重复，默认 registry 是随项目附带的 JSON 教学索引。它包含
`greet-demo`、`color-demo` 和 `legacy-demo` 的几个版本。安装过程会校验 artifact hash，再把
索引中的纯 Python 文件复制进虚拟环境。

## 快速体验

不安装也可以从源码运行：

```powershell
cd toyuv
$env:PYTHONPATH = "$PWD\src"
python -m toyuv init demo
cd demo
python -m toyuv add greet-demo
python -m toyuv tree
python -m toyuv run python -c "from greet_demo import greet; print(greet('world'))"
```

如果本机安装了 uv，也可以用 uv 管理 `toyuv` 自己：

```powershell
cd toyuv
uv run python -m unittest discover -s tests -v
uv run toyuv --help
```

演示冲突：

```powershell
python -m toyuv add "greet-demo>=2" legacy-demo
```

`legacy-demo` 要求 `greet-demo<2`，因此求解器会输出冲突约束，而不是悄悄选择一个错误版本。

## 自定义本地索引

在项目的 `pyproject.toml` 中加入：

```toml
[tool.toyuv]
index = "../my-index.json"
```

索引格式可以参考 `src/toyuv/demo-index.json`。每个版本声明依赖和待安装文件。文件内容放在
JSON 中只是教学取舍；工业实现通常下载 wheel、验证多个 hash、处理平台 tag，并在必要时隔离
构建 sdist。

## 阅读顺序

建议按下面的顺序阅读源码：

1. `project.py`：意图状态——用户想要什么；
2. `requirements.py`：约束如何表示；
3. `resolver.py`：如何得到一致的版本集合；
4. `lockfile.py`：如何冻结一个解析结果；
5. `environment.py`：如何让实际环境收敛到锁文件；
6. `operations.py`：为什么 `run` 前需要自动 lock 和 sync。

完整范围、证据和刻意省略项见 [TEACHING_SPEC.md](TEACHING_SPEC.md)。
