# DSCode Assistant Windows 用户安装说明

## 安装版

1. 双击 `DSCode Assistant Setup v0.1.0.exe`。
2. 选择安装目录。
3. 按需勾选创建桌面快捷方式。
4. 完成安装后，从桌面或开始菜单启动 `DSCode Assistant`。
5. 首次启动后打开设置，配置自己的模型提供商与 API Key。

程序不需要用户另行安装 Python。

## 便携版

1. 解压 `DSCode Assistant v0.1.0 Portable.zip` 到普通文件夹。
2. 不要直接在 ZIP 压缩包内运行程序。
3. 双击 `DSCode Assistant.exe` 启动。

便携版只是免安装，不代表用户数据写在便携目录。设置和聊天历史仍保存在当前 Windows 用户的数据目录中。

## 用户数据与隐私

- 设置与聊天历史：`%APPDATA%\DSCodeAssistant`
- API Key：Windows 凭据管理器
- DSC 不建立开发者中转服务器；使用云模型时，请求直接发送到用户配置的模型服务地址。

请勿将 API Key 写入项目文件、截图、聊天记录或公开 Issue。

## 卸载

可以从以下任一入口卸载：

- Windows“设置 → 应用 → 已安装的应用”
- 开始菜单中的 `Uninstall DSCode Assistant`

为防止数据丢失，卸载程序默认保留 `%APPDATA%\DSCodeAssistant`。如需彻底清理，请先确认不再需要聊天历史和设置，再手动删除该目录；Windows 凭据管理器中的 API Key 也需要单独删除。

## 常见问题

### Windows 显示未知发布者

当前开源构建未使用商业代码签名证书。请仅从项目官方发布页面或可信分发渠道获取安装包，并核对文件名与版本。

### 程序无法保存 API Key

确认 Windows 凭据管理器服务可用，并尝试以当前 Windows 用户重新启动程序。API Key 不会写入 `settings.json`。

### 安装版与便携版会共享历史记录吗

会。两者默认都使用 `%APPDATA%\DSCodeAssistant`，以保持升级兼容。
