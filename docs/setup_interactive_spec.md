# Setup 与 Skills 交互式向导规格

## 目标

`smart-search setup` 与 `smart-search skills` 在真实终端中使用方向键、空格和确认提示完成枚举选择，避免要求用户手输 transport、scope、Agent 名称及安装方式。API URL、model 和 API key 仍属于自由文本，其中密钥必须隐藏输入。

## 交互契约

- 交互式提示写入 stderr，最终 JSON、Markdown 或 content 结果继续写入 stdout 或 `--output`。
- 单选使用方向键和 Enter，多选使用方向键、空格和 Enter，确认使用 Y/N。
- `setup` 再次运行时逐项确认已有必需配置，默认保留；替换密钥时不回显。
- 环境变量提供的配置属于外部管理。向导可以继续使用，但不得把环境变量中的值复制到配置文件。
- 所有配置和 skill 安装选择先汇总预览，用户最终确认后才开始写入。
- Esc/Ctrl-C 返回退出码 130；最终确认选择 No 返回 `cancelled: true`，且不得修改配置或 skill。
- 非 TTY 环境不回退到文字菜单。`setup` 应提示使用 `--non-interactive`，`skills` 应提示使用 `--yes`、scope 和 Agent 参数。

## Setup 流程

1. 读取当前有效配置及来源。
2. 方向键选择 Grok transport，默认当前值；显式 `--grok-transport` 优先且不再询问。
3. 处理所选 Grok transport 的必需字段，以及 Exa、Context7、ZRead、Firecrawl 的 API key。
4. 配置文件中已有字段先询问是否保留；环境变量字段先确认是否继续使用；缺失或选择替换的字段再输入。
5. 显式提供的可选 endpoint、model、stream、tools 和 Exa search type 继续直接保存，不新增额外高级配置问题。
6. 询问是否安装 bundled skill。选择安装后依次确定 scope、Agent 目标和必要的 symlink/copy 模式。
7. 显示脱敏摘要并最终确认，再保存配置和安装 skill。

## Skills 流程

- `project/global` 使用单选，默认 project。
- Agent 使用多选，展示全部支持当前 scope 的目标，并预选检测到的 Agent。
- 只有目标路径与 canonical skill 路径不同时才询问 symlink/copy，默认 symlink。
- install、update、uninstall 在执行前显示路径摘要并确认；status 只选择范围和目标，不要求执行确认。
- 显式参数与 `--yes` 继续支持脚本及 CI，并保持原有默认语义。

## 验收

- 交互取消前不产生配置或 skill 写入。
- 非交互命令契约和 JSON 字段保持兼容。
- Ubuntu、macOS、Windows 的 packaged CLI 与 skill 安装验证通过。
- 私密配置及密钥不会出现在日志、测试快照、README 或 Git 提交中。
