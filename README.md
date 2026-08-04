# My Hot Key Inspired by Maya

Maya 風のホットキー・ビューポート操作・Micro Manipulator・Hotbox を Blender に追加するアドオンです。

**Author:** dokurokaruto

## 対応バージョン

- Blender 3.6 以降（4.x 含む）

## インストール

1. `my_hot_key_inspired_by_maya.py` をダウンロード
2. Blender → **Edit → Preferences → Add-ons → Install...**
3. ファイルを選択してインストール
4. **My Hot Key Inspired by Maya** にチェックを入れて有効化
5. （任意）アドオン設定で Industry Compatible ベースや各種オプションを調整

有効化すると、Blender を再起動してもオペレーター・キーマップ・ハンドラが自動で復元されます。

## 主な操作

| キー | 動作 |
|------|------|
| Alt + LMB / MMB / RMB | 回転 / パン / ズーム |
| Space 単押し | 四分割ビュー トグル |
| Space 長押し | Hotbox（パイメニュー） |
| Q / W / E / R | 矩形選択 / 移動 / 回転 / スケール |
| Ctrl + Shift + RMB | Manipulator Settings（方向・Micro・モード） |
| Z | Undo |
| Alt + Q | 再生 / 停止 |
| Alt + W / S | 前後のキーフレーム |
| Alt + A / D | 1 フレーム移動 |
| Alt + 1 | コントローラー（ボーン）表示切替 |
| Alt + * または Alt + Shift + 8 | トランスフォーム初期化（Anim エディタでは選択キーをデフォルト化） |
| F | 選択にフォーカス |
| 4 / 5 / 6 / 7 | シェーディング切替 |
| Graph: D 単押し / 長押し | Auto Clamped / ハンドル種別メニュー |
| Graph: Shift + MMB | 軸ロックでキー移動 |

## アドオン設定

**Preferences → Add-ons → My Hot Key Inspired by Maya**

- Industry Compatible をベースにする
- 読み込み時にユーザーキーマップをリセット（初回セットアップ向け・破壊的）
- Maya 式ズーム / 3 ボタンマウスエミュレート無効化
- Space・D の長押し判定時間
- グラフ点サイズ、Micro Manipulator サイズ など
- **Maya風キーマップを再適用** … キーマップをやり直す
- **キーマッププリセットを書き出し** … 現在の設定を presets に保存

## 開発メモ

- キー割り当ては `keyconfigs.addon` に登録し、無効化時にクリーンに解除します
- 競合するユーザー側バインドは一時無効化し、解除時に復元します
- カスタムオペレーター / Gizmo / `load_post` ハンドラは `register` / `unregister` で管理します
