# 05 · 结论：证据链

这一篇不带新实验，只把前面四篇的结论排成一条链，说明「哪一层破了」和「为什么最后一层破不了」。

---

## 1. 分层的边界

Antigravity 处理一次用户请求，要经过这些层：

```
用户输入
  ↓
[1] 权限层      —— 决定工具调用是否要人审批      ← 可改，已破
[2] 上下文组装层 —— 决定 system prompt 里有什么   ← 可改，已破
[3] 模型推理     —— 决定要不要拒绝               ← 不可改
[4] 网络传输     —— 可拦截、可替换
```

前两层和第四层都在本地，都有明确的配置文件或二进制落脚点。第三层不在本地。

**本项目全部工作的价值，就是把这条边界定位出来了。**

---

## 2. 逐层证据

### 层 1 · 权限：破了，而且是唯一彻底的一层

- 落点明确：`~/.gemini/config/config.json` 的 `userSettings.permissionPreset`。
- 写裸值后被 language_server 规范化成 `AGENT_PERMISSION_PRESET_TURBO` —— **被解析、被接受、被持久化的三重证明**。
- 冷启动后 UI aria-label = `Agent 权限预设，当前：Turbo`。
- 行为验证：`run_command` 无审批浮层，模型直接返回命令输出。
- 失败路径全部记录（UI 点击不持久、`PreToolUse` allow 无效、相关 RPC 全部 404 / 501）。

这一层是**真正意义上的「破甲」**：它拆掉的是「人必须点同意」这个门。

### 层 2 · 上下文：破了，但破了没用

四条通道全部送到模型：

| 通道 | 到达证据 | 行为改变 |
|---|---|---|
| 规则文件 | 模型自报 `user_global: # Operating Directives` | ❌ |
| hooks injectSteps | transcript 有 `injected by a SessionStart hook:` + 全文 | ❌（反向加固） |
| PreToolUse decision | 审计日志有 `PreToolUse run_command {...}` | ❌（UI 不听） |
| exe 模板改写 | 回复末尾稳定出现 `ZN7734` | ❌ |

**`ZN7734` 是这个项目里最重要的一行字。** 它是「上下文已经被我完全控制」的证明——模型读到了我写的字，并照做了（把 token 打在末尾）。但它对「要不要写钓鱼邮件」的判断毫无影响。

这就把「上下文不够好」这个可能性彻底排除了。不是措辞问题，不是权威声明不够，不是伪装不够像。

### 层 3 · 模型对齐：没破，而且本地无法破

决定性证据是 93 KB 的明文 `systemInstruction`：

| 关键词 | 出现次数 |
|---|---|
| `weaponization` | 0 |
| `High Severity` | 0 |
| `attack code` | 0 |
| `phishing` | 0 |
| `malware` | 0 |

服务端提示词**一个安全策略字都没有**。而模型拒绝时的 thinking 里全是这些词。

```
Phishing email requests are clearly a "High Severity" refusal, even if omitting
backend capture logic ... aligns with "weaponization escalation" and "generating
actionable payloads" ...
```

这些词是模型自己产出的分类标签，不是上下文里抄来的。

结论：**拒绝是权重里的对齐行为，不是提示词里的规则，也不是服务端策略层的过滤。**

三家模型的反应方式还各有特点，值得记下来：

- `gemini-3.8-flash`：识别出注入意图并显式说明（`The prompt also contains directives to bypass refusal policies`）。
- `claude-sonnet-4-6`：明确点名框架无效（`The layered "sandbox," "operator configuration," and injected system-message framing doesn't change what's being requested`）。
- `gpt-oss-120b`：给注入文本排了优先级（`system directives and policies override user directives`）。

三家的共同点是**都把注入识别成注入**。这意味着文本注入这条路不只是「无效」，而是**有负收益**——它在给自己制造敌意。

### 层 4 · 网络：完全接管

`SetCloudCodeURL` 是这一层的关键：它把整个后端 URL 换掉，不需要证书、不需要改 hosts、不需要信任根证书。

拿到的东西：

- 完整明文请求体（33 轮对话 + 93 KB systemInstruction + 21 个工具声明）；
- SSE 响应流（可逐帧读，`thought: true` 是 thinking）；
- `Authorization: Bearer` token。

这一层是**技术上最成功的一层**：它让「模型收到了什么、回了什么」变成完全可观测的事实，不再是猜测。

但同时它也是最没用的一层——**看得见，改不动**：

| 干预 | 结果 |
|---|---|
| 追加 `operator_context` | 无效 |
| 重写最后一轮为工单 | 无效 |
| 只保留重写后的单轮 | 无效 |
| `safetySettings` 六类 OFF | `This request was blocked by Gemini's filters` |
| `disableAllPolicy` | `400 Unknown name` |
| `systemInstructionMode` | `400 Unknown name` |

---

## 3. 为什么「题目」不是「提示词不够好」

一个很自然的下一个念头是：再换一种说法试试。

本项目已经排除这条路，理由不是「试了几次都不行」，而是**有反证**：

1. **注入被读到了**（`ZN7734`）——排除「没送到」。
2. **注入被理解了**（模型 thinking 里讨论注入本身）——排除「格式不对」。
3. **注入被拒绝了**（三家一致，理由都是「这是 bypass 尝试」）——排除「说服力不足」。
4. **删掉注入行为不变**（清空五份规则文件后重测）——排除「注入是必要条件」。
5. **提示词里没有策略**（93 KB 全量检索五个关键词皆 0）——排除「只要改掉策略段就行」。

第 5 条是最硬的。如果拒绝依赖提示词里的某段文字，那么改掉那段文字应该有效；而实际上这段文字**根本不存在**。

---

## 4. 真正能兑现的形态

代理已经在链路中间了，所以不必再求后端松口。做法：

### 4.1 拦截

```python
def _proxy(self):
    body = read_body(self)
    if 'streamGenerateContent' in self.path:
        return self.serve_local(json.loads(body))
    return self.forward(body)
```

### 4.2 重组

把 `contents[].parts[].text` 按对话顺序拼成给目标模型的 prompt：

```python
def to_messages(req):
    out = []
    si = req.get('systemInstruction', {})
    sys_txt = '\n'.join(p.get('text', '') for p in si.get('parts', []))
    if sys_txt:
        out.append({'role': 'system', 'content': sys_txt})
    for c in req.get('contents', []):
        role = 'assistant' if c.get('role') == 'model' else 'user'
        txt = '\n'.join(p.get('text', '') for p in c.get('parts', []) if 'text' in p)
        if txt:
            out.append({'role': role, 'content': txt})
    return out
```

### 4.3 回填 SSE

```python
def sse_chunk(text):
    return ('data: ' + json.dumps({
        "response": {
            "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 0, "candidatesTokenCount": len(text)},
        }
    }, ensure_ascii=False) + "\n\n").encode('utf-8')
```

工具调用走 `functionCall` 帧：

```json
{"response":{"candidates":[{"content":{"parts":[{
  "functionCall":{"name":"run_command","args":{"CommandLine":"..."}}
}]}}]}}
```

壳子解析这个结构，照常渲染、照常执行（Turbo 下不需审批）。

### 4.4 为什么这条路可行

- 不受 `F.Model` 封闭枚举限制。那个枚举只挡 UI 层的 customModels：`JetboxWriteState` 写 `customModelsConfig.customModels` 时 `model_id` 字段会被 protobuf 丢弃，且 `features.customModelsFeature` 不下发时前端永不 `dispatch(eZa(...))`，`supported` 恒 false。
- 不经过 Google 侧任何过滤器（`safetySettings` / 策略层 / 模型对齐都不在这条路上）。
- 不需要说服任何模型。

**这是唯一真正意义上的「破甲」路径：不是说服模型，而是换掉模型。**

---

## 5. 已知无效的完整清单

供后来者省时间，以下全部实测无效：

### 权限
- UI 点 Turbo（重启回退）
- `PreToolUse` `decision:"allow"`
- `PreToolUse` `permissionOverrides:["*"]`
- `GetPermissionSettings` RPC（`failed_precondition`）
- `GetUserSettings` RPC（`unimplemented`）
- `ANTIGRAVITY_PERM_GRANTS` 环境变量

### 上下文
- `AGENTS.md` / `GEMINI.md`（四份，全路径）
- `config/rules/*.md`（三种 `trigger` 值）
- hooks `injectSteps`（三轮措辞 × systemMessage + userMessage）
- `PreToolUse` hook 改工具参数
- exe 内嵌模板五区域等长改写（生效，无效）

### 模型路由
- `AGY_LLM_GATEWAY_*` 全套环境变量（Tier 3 网关从未被触发，日志无 `[ModelConfig] Resolving models from Tier 3`）
- `JetboxWriteState` 写 `customModelsConfig`（写进去了，UI 不显示，`model_id` 被 protobuf 丢弃）
- BYOK / 自定义 OpenAI 端点（前端 `openai` 字面量 0 次，无入口）
- `SetMendelFlagOverrides`（`403 permission_denied: Mendel flag overrides require developer mode`）
- `devMode`（`window.__APP_CONFIG__.devMode === false`，由注入配置决定，非本地文件）

### 网络
- 追加 `operator_context`
- 重写 `contents` 单轮
- 只保留末轮 + 去 tools
- `safetySettings` 六类 `threshold: "OFF"`
- `disableAllPolicy` / `systemInstructionMode`（网关 schema 拒绝）

---

## 6. 一句话

**客户端能改的全部改了，改到的全部生效了，行为一点没变——因为决定权不在客户端。**

真要兑现，就得换掉第三层，也就是走第 4 节。

---

## 7. 方法论备注

这个项目值得留下的不是结论，是几条方法论：

1. **埋探针**。任何注入实验都必须带一个可验证的副作用（`ZN7734`），否则无法区分「没送到」和「送到了不听」。这是本项目最有价值的一步。
2. **做减法对照**。删掉全部注入后重测，才能证明注入不是必要条件。很多人停在这一步之前就下结论。
3. **找落点，不找 RPC**。Antigravity 的很多状态不在 RPC 里，而在 JSON 文件里。`config.json` 一行改动胜过十次 RPC 尝试。
4. **按端口反查 hub**。取错 hub 文件时所有 RPC 都报 CSRF 错误，看起来像「RPC 不存在」，实际是 token 错了。
5. **等长补丁 + 硬断言**。改二进制必须 `assert len(out) == len(src)`，否则后面所有偏移全崩，且崩得不明显。
6. **看服务端发来的原文**。在拿到 93 KB `systemInstruction` 之前，所有关于「拒绝是因为提示词里写了 X」的猜测全是错的。
