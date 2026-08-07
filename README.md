# my_hot_key_inspired_by_maya

Blender 用アドオン集リポジトリです。

## 収録アドオン

| フォルダ | アドオン | 説明 |
|---|---|---|
| `kennys_animation_picker/` | **Kenny's Animation Picker** | AnimSchool Picker 風のビューポート・オーバーレイ型ボーン選択ツール (Blender 5.2 用) |
| `my_hot_key_inspired_by_maya.py` | my_hot_key_inspired_by_maya | Maya 風ホットキー設定 (従来からの同梱ファイル) |

## Kenny's Animation Picker

3D ビューポート上にピッカーをオーバーレイ表示し、キャラクター画像の上に
配置したボタンをクリックして pose bone を選択するアドオンです。

- ビューポート直接描画 (`SpaceView3D.draw_handler_add` + `gpu` / `gpu_extras` / `blf`、`bgl` 不使用)
- 背景画像は外部パス参照方式 (Blend ファイルへの埋め込みなし)
- クリック = 選択 / Shift+クリック = 追加 / Ctrl+クリック = 除外
- 編集モードでボタン追加・移動・色・サイズ・対応ボーンを設定
- 複数リグ / 複数タブ (front / back) 対応
- 全選択・反転選択・左右ミラー選択 (`.L`/`.R` 等の標準命名規則を自動検出)
- セーブデータは外部 JSON ファイル

### インストール

配布 ZIP (`kennys_animation_picker.zip`) を解凍せず、
`Edit > Preferences > Add-ons > Install from Disk...` から選択して有効化します。

### テスト

`tests/` に headless の自動テスト一式があります (Blender 5.2.0 の bpy を使用)。

```bash
# 例 (bpy 5.2.0 環境で)
python3 tests/test_logic.py    # ロジック / JSON / ミラー命名 / 選択
python3 tests/test_draw_dry.py # 描画パス (gpu/blf モック) + モーダル操作
python3 tests/test_install.py  # ZIP インストール → 有効化 → 登録確認 (実フロー)
```

詳細は `kennys_animation_picker/README.md` を参照してください。
