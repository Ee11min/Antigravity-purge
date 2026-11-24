# 01 · 权限层：枚举、落点、持久化

Antigravity 的权限系统在 UI 上表现为一个下拉菜单（Request Review / Default / Auto / Turbo），但真正决定行为的是四组值，写在 `userConfig.userSettings` 里。

这一篇把枚举定义、前端映射、落盘路径和验证方法全部拆开。

---

## 1. 枚举真相

从 `main.js`（前端 bundle，12,581,273 字节）反查，偏移 767356 / 785753 处：

```js
F.CascadeCommandsAutoExecution = {
  UNSPECIFIED: 0,
  OFF: 1,
  AUTO: 2,
  EAGER: 3,
  PROCEED_IN_SANDBOX: 4,
}

F.AgentPermissionPreset = {
  UNSPECIFIED: 0,
  REQUEST_REVIEW: 2,
  DEFAULT: 1,
  VETTED: 4,
  TURBO: 3,
  AUTO: 6,
  NONE: 5,
}

F.AgentSettingPolicy = {
  UNSPECIFIED: 0,
  ALLOW: 1,
  ASK: 2,
  DENY: 3,
}
```

注意 `AgentPermissionPreset` 的编号**不是顺序的**：`DEFAULT=1`、`REQUEST_REVIEW=2`、`TURBO=3`、`VETTED=4`、`NONE=5`、`AUTO=6`。写 `2` 得 Request Review，写 `3` 得 Turbo。

---

## 2. 预设表

```js
var jL = {
  request_review: {
    label: "Request Review",
    description: "Every command requires approval.",
    prefValues: {
      enableTerminalSandbox: false,
      cascadeAutoExecutionPolicy: F.CascadeCommandsAutoExecution.OFF,
      nonWorkspaceFileAccessPolicy: F.AgentSettingPolicy.ASK,
      permissionPreset: F.AgentPermissionPreset.REQUEST_REVIEW,
    },
  },
  default: {
    label: "Default",
    description: "Ask before sensitive operations.",
    prefValues: {
      enableTerminalSandbox: true,
      cascadeAutoExecutionPolicy: F.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX,
      nonWorkspaceFileAccessPolicy: F.AgentSettingPolicy.ASK,
      permissionPreset: F.AgentPermissionPreset.DEFAULT,
    },
  },
  auto: {
    label: "Auto",
    description: "Automatically decide if commands run.",
    prefValues: {
      enableTerminalSandbox: true,
      cascadeAutoExecutionPolicy: F.CascadeCommandsAutoExecution.AUTO,
      nonWorkspaceFileAccessPolicy: F.AgentSettingPolicy.ASK,
      permissionPreset: F.AgentPermissionPreset.AUTO,
    },
  },
  turbo: {
    label: "Turbo",
    description: "Run all commands without restrictions.",
    prefValues: {
      enableTerminalSandbox: false,
      cascadeAutoExecutionPolicy: F.CascadeCommandsAutoExecution.EAGER,
      nonWorkspaceFileAccessPolicy: F.AgentSettingPolicy.ALLOW,
      permissionPreset: F.AgentPermissionPreset.TURBO,
    },
  },
};

var amb = ["request_review", "default", "auto", "turbo"];
var bmb = ["request_review", "default", "turbo"];
```

---

## 3. 为什么 UI 里只有两项

```js
function cmb(a = {}) {
  return amb.filter(b => a[b] ?? bmb.includes(b));
}

function kL(a) {
  return !!jL[a]?.prefValues.enableTerminalSandbox;
}

function dmb(a, b) {
  a = cmb(a ?? {});
  return {
    options: a.filter(c => !(!b && kL(c))),
    sandboxHidden: a.filter(c => !b && kL(c)),
  };
}
```

`kL()` 为 true 的档位需要终端沙箱。宿主没有沙箱时（`b = false`），`default` 与 `auto` 被 `options.filter` 剔掉，只剩 `request_review` 与 `turbo`。

UI 上的原话：

```
Local Permissions
Request Review — Every command requires approval.
Turbo — Run all commands without restrictions.
Default and Auto need the terminal sandbox, which isn't available on this host.
```

所以「没有沙箱」这件事反而帮了忙：Turbo 是唯一不依赖沙箱的免审批档，而它恰好是最强的一档。

---

## 4. 落盘路径

前端 `setPrefValue` 的实现（外壳函数 `FUd(a,b,c,d,f)`，偏移约 9004）：

```js
getPrefValue: n => {
  switch (n) {
    case "enableTerminalSandbox":
      return a.rootProvider.getState().userConfig?.userSettings?.enableTerminalSandbox ?? false;
    // ...
  }
},

setPrefValue: async (n, p) => {
  switch (n) {
    case "permissionPreset":              t(await q(uTd(a, p))); break;
    case "cascadeAutoExecutionPolicy":    t(await q(tTd(a, p))); break;
    case "enableTerminalSandbox":         t(await q(zTd(a, p))); break;
    case "nonWorkspaceFileAccessPolicy":  t(await q(yTd(a, p))); break;
    case "permissionGrantsGlobal":        t(await q(HTd(a, p))); break;
  }
},

setPrefValues: async n => {
  for (let t of Object.keys(n)) q(await p(m.setPrefValue(t, n[t])));
},
```

各 `xTd` 函数体是同一个模式（偏移 12366998–12370001）：

```js
async function uTd(a, b) {
  R$(a, f => {
    f.userConfig || (f.userConfig = ec(hi, {}));
    f.userConfig.userSettings || (f.userConfig.userSettings = ec(Zh, {}));
    f.userConfig.userSettings.permissionPreset = b;
  });
  d(await c(a.lsClient.jetboxWriteState(ec(ui, { userConfig: ... }))));
}
```

即：

```
setPrefValue → jetboxWriteState({userConfig:{userSettings:{...}}}) → ~/.gemini/config/config.json
```

**改 `config.json` 与点 UI 走的是同一个落点。** 区别只在于：UI 那次点击在某些路径上没把写盘 burn 下去（重启即回退），而直接改文件必然被读到。

---

## 5. 直接写文件

备份后改 `~/.gemini/config/config.json`（Windows: `C:\Users\<你>\.gemini\config\config.json`）的 `userSettings`：

```json
{
  "userSettings": {
    "permissionPreset": "TURBO",
    "autoExecutionPolicy": "EAGER",
    "enableTerminalSandbox": false,
    "nonWorkspaceFileAccessPolicy": "ALLOW"
  }
}
```

裸字符串就行。重启后 language_server 会**规范化写回**成 proto 枚举名：

```json
{
  "userSettings": {
    "autoExecutionPolicy": "CASCADE_COMMANDS_AUTO_EXECUTION_EAGER",
    "enableTerminalSandbox": false,
    "nonWorkspaceFileAccessPolicy": "AGENT_SETTING_POLICY_ALLOW",
    "permissionGrantsV2Migrated": true,
    "permissionPreset": "AGENT_PERMISSION_PRESET_TURBO",
    "remoteControlHostname": "xi-77377-rising-quasar",
    "sandboxEnabledAtV2Migration": false
  }
}
```

**关键判据**：如果重启后被写回成枚举名，就证明它真的被 proto 解码、接受并持久化了。如果原样留着裸字符串，说明没走通。

---

## 6. 验证

### 6.1 读 UI 状态

```python
import sys
sys.path.insert(0, r'D:\dpskk\Antigravity-purge\tools')
import cdp

T = cdp.main_target(9223)
W = cdp.WS(T['webSocketDebuggerUrl'])

def jv(e):
    r = W.call('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return r.get('result', {}).get('result', {}).get('value')

print(jv("""document.querySelector('[data-testid="permissions-selector-trigger"]').getAttribute('aria-label')"""))
# => Agent 权限预设，当前：Turbo
```

### 6.2 行为验证

在 Turbo 下发一条要执行命令的消息：

```
Run the shell command 'echo PERSIST_TURBO_OK' and report its output.
```

- Request Review：界面弹出审批浮层，四个选项 `1 Yes, allow this time` / `2 Yes, and always allow 'X' in this conversation` / `3 Yes, and always allow 'X'` / `4 否`，外加 `跳过` / `提交↵`。
- Turbo：**无浮层**，模型直接回 `PERSIST_TURBO_OK`。

---

## 7. 失败路径记录（避免重复踩）

| 尝试 | 结果 |
|---|---|
| 点 UI 的 Turbo 菜单项 | 会话内生效，**重启回退** |
| `SetPrefValue` RPC | 不存在这个 RPC（前端走 jetbox） |
| `UpdatePermissionSettings` | 存在但语义不同（云端权限授予） |
| `GetPermissionSettings` | `failed_precondition: cloud conversations are not enabled for this user` |
| `GetUserSettings` | `unimplemented` |
| `PreToolUse` hook `decision:"allow"` | hook 被调用，UI 仍弹审批 |
| `PreToolUse` hook `permissionOverrides:["*"]` | 同上，无效 |

结论：**只有改 `config.json` 这一步是可靠且持久的。**

---

## 8. `ANTIGRAVITY_PERM_GRANTS`

exe 里存在这个环境变量名，暗示可以按会话注入权限授予。实测启动时带上它没有任何效果——权限值仍以 `config.json` 为准。这一条记录在此，供后续排查。

---

## 附：连不上后端（loadCodeAssist / oauth2 token 超时）

```
failed to get load code assist response: Post "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist":
Post "https://oauth2.googleapis.com/token": dial tcp [2404:6800:4008:c15::5f]:443:
connectex: A connection attempt failed because the connected party did not properly respond ...
```

这条报错跟权限层无关，但会让人误以为是配置改坏了（表现是模型列表空、界面「未选择模型」「无项目」）。

`language_server.exe` 是 Go 二进制，Go 的 `ProxyFromEnvironment` 只看环境变量，**不看 Windows 系统代理注册表**。所以：

| 组件 | 走不走系统代理 |
|---|---|
| Electron 前端（Chromium） | ✅ 读注册表，能走 |
| `language_server.exe`（Go） | ❌ 只读 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` |

FlClash 开了系统代理，前端正常，后端直连 → 解析到不通的 IPv6 → 超时。修法见
[`../scripts/fix-proxy.ps1`](../scripts/fix-proxy.ps1)，README 第 3e 节有用法。
