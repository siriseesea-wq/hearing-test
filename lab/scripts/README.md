# 构建与视觉核验脚本

## build_hearing_test.py
把 `lab/audio/` 里的六段 30 秒裁剪片段以 base64 内嵌进 `lab/templates/hearing_test.tpl.html`，
生成自包含的 `products/hearing-test.html`（页脚自动写入素材 SHA-256 指纹与生成时间）。

```bash
python lab/scripts/build_hearing_test.py
```

## shoot_hearing_test.py
用无头 Chrome + DevTools Protocol 逐个**真实点击**标签页再截图，
用来在交付前肉眼核对排版与深浅主题。输出到 `lab/shots/`。

```bash
pip install --target lab/pylibs websocket-client   # 只读 venv 下装到工作区
python3 lab/scripts/shoot_hearing_test.py
```

注意：CDP WebSocket 需 `suppress_origin=True`（Chrome 111+ 默认拒 Origin）；
target 要按 `type=page && url 含 hearing-test` 过滤，别取 `pages[0]`。
