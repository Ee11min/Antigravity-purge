# hooks/ — 注入通道样例

这三个文件是 Antigravity hooks 通道的完整可运行样例。**默认全部 `enabled: false`** —— 它们是实验记录，不是推荐配置。

装到真实环境要拷到 `~/.gemini/config/` 下（hooks 的工作目录就是 `hooks.json` 所在目录，所以相对路径 `./drill_hook.py` 在那边同样成立）。

| 文件 | 作用 | 实测结果 |
|---|---|---|
| `hooks.json` | 两组 hook 定义 | — |
| `drill_hook.py` | `SessionStart` / `PreInvocation` 注入器 | 注入到达模型，但被识别为 prompt injection，**加固**拒绝 |
| `drill_directives.py` | 注入文本（伪装成仓库约定的那版） | 同上 |
| `allow_all.py` | `PreToolUse` 强制放行 + 审计日志 | hook 被调用，UI **仍弹审批** |

细节见 [`../docs/02-prompt-layers.md`](../docs/02-prompt-layers.md)。

## 契约要点

- 事件：`SessionStart` / `PreToolUse` / `PostToolUse` / `PreInvocation` / `PostInvocation` / `Stop`
- 只支持 `type: "command"`，Windows 走 `cmd /c`，默认 timeout 30s
- `PreToolUse` / `PostToolUse` **必须**包在 `{"matcher": ..., "hooks": [...]}` 里
- 其余事件是扁平 handler 列表（`[{"type":"command", ...}]`）
- `PreInvocation` 输出 `{"injectSteps":[{"systemMessage":{"systemMessage":"..."}},{"userMessage":"..."}]}`
- `PreToolUse` 输出 `{"decision":"allow"|"deny"|"ask"|"force_ask", "permissionOverrides": [...], "overwrite": {...}}`
- `Stop` 输出 `{"decision":"continue","reason":"..."}` 可阻止收工

## 验证注入是否到达

看 transcript：

```
~/.gemini/antigravity/brain/<conversationId>/.system_generated/logs/transcript.jsonl
```

注入成功时会出现：

```
{"step_index":1,"source":"SYSTEM_SDK","type":"SYSTEM_MESSAGE",
 "content":"The following system message was injected by a SessionStart hook:\n<全文>"}
```

**这一步必须先确认，否则无法区分「注入没送到」和「送到了模型不听」。**
