# Smart Search Skill 管理规格

## 目标

Smart Search CLI 统一通过 `smart-search skills` 管理随包发布的 Agent skill，并在交互式 `smart-search setup` 完成 provider 配置后提供 skill 安装步骤。当前只包含 `smart-search-cli`，命令和数据结构需允许未来增加多个 bundled skill。

实现基线于 2026-07-23 核对的 [vercel-labs/skills](https://github.com/vercel-labs/skills) README、[`installer.ts`](https://github.com/vercel-labs/skills/blob/main/src/installer.ts) 和 [`remove.ts`](https://github.com/vercel-labs/skills/blob/main/src/remove.ts)。

## 命令契约

```text
smart-search skills install [NAME]
smart-search skills uninstall [NAME]
smart-search skills status [NAME]
smart-search skills update [NAME]
```

- `NAME` 省略时默认为 `smart-search-cli`，`all` 表示全部 bundled skills。
- `-p, --project` 选择当前工作目录，`-g, --global` 选择当前用户，两者互斥。
- `-a, --agent TARGET` 可重复，`--all-agents` 选择当前 scope 支持的全部 target。
- `-y, --yes` 跳过确认。`install` 另支持 `--copy`。
- 无 scope 时交互选择 Project/Global；无 Agent 时检测本机 Agent 并交互多选。未检测到 Agent 时展示完整列表且不预选。
- 旧参数 `--targets`、`--project-root`、`--source-root` 从公开 CLI 删除。

## 安装模型

每个 scope 使用单一 canonical 实体目录：

```text
Project: <cwd>/.agents/skills/<skill-name>/
Global:  ~/.agents/skills/<skill-name>/
```

每个 Agent 分别定义官方 `project_path` 和 `global_path`。目标路径与 canonical 相同时直接使用实体目录；否则创建指向 canonical skill 的目录链接。

- macOS/Linux 使用相对目录 symlink。
- Windows 优先使用指向绝对 canonical 路径的 directory junction，失败后尝试 directory symlink。
- 链接无法创建时自动复制 canonical 内容到该 target，并在结果中标记 `fallback_to_copy`。
- `--copy` 跳过链接尝试，但仍保留 canonical 作为更新源。
- 安装必须防止路径穿越、self-link、循环链接和覆盖 canonical 自身。

scope 的 canonical root 下保存 `.smart-search-installations.json`，仅记录 schema version、skill hash、target、scope 相对路径和 `direct|symlink|junction|copy` 模式，不保存密钥或用户绝对路径。

## Setup 和卸载

交互式 `setup` 保存 provider 配置后，依次询问是否安装 skill、scope、Agent 和 Symlink/Copy 模式，并在写入前展示路径。`setup --non-interactive` 默认不安装；仅在显式传入 `--agent` 或 `--all-agents` 时安装，未指定 scope 时默认 Project。

`uninstall` 只删除选定 scope/skill/Agent 的精确 target 目录或链接。其他 target 仍在使用时保留 canonical；最后一个 target 卸载后删除 canonical skill 和清单记录。不删除 target 父目录、其他 scope、其他 skill 或未知路径。

## 验收

- 15 个现有 Agent target 均使用官方 project/global 路径。
- 多 target 安装只有一份 canonical 实体内容。
- `status` 能区分 missing、up-to-date、stale、broken link、copy fallback 和 error。
- `update` 更新 canonical，并仅重新同步 copy target。
- Linux/macOS/Windows 聚焦测试覆盖 symlink、junction 和 copy fallback。
- 不读取、修改或提交仓库根目录中的真实 `config.json`。
