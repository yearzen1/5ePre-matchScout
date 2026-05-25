# 5E 赛前侦察器

![5EPreMatchScout](5ePre-matchScout.png)

CS2 5Eplay 平台的赛前侦察工具，通过 Chrome DevTools Protocol 自动捕获 WebSocket 对战数据，实时显示双方玩家信息。

## 功能

- 自动启动 5E 客户端并连接调试端口
- 自动启动 Steam（在设置中配置路径后自动检测并启动）
- 捕获排位赛（42205234）和普通赛（39583794）的对战数据
- 实时显示双方玩家 UUID、昵称、状态等信息
- 一键复制玩家 UUID
- 设置界面可配置 5E 客户端路径、Steam 路径和本人昵称

## 使用

从 [Releases](https://github.com/yearzen1/5ePre-matchScout/releases) 下载最新版 `5EPreMatchScout.exe`，直接运行即可。

**首次使用：** 点击窗口右上角 ⚙ 按钮，设置 5E 客户端路径、Steam 路径和你的游戏昵称。程序会自动拉起 Steam 和 5E 客户端并开始监听匹配。

## 打包

```bash
pip install -r requirements.txt
pyinstaller --onefile --noconsole --name "5EPreMatchScout" --hidden-import "websocket" --hidden-import "customtkinter" gui.py
```

## 依赖

- customtkinter
- websocket-client
- Pillow
