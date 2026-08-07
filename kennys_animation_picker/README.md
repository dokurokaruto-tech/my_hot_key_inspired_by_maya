# Kenny's Animation Picker

**Blender 5.2 用** の AnimSchool Picker 風ボーン選択アドオンです。

3D ビューポート上にオーバーレイとしてピッカーを表示し、キャラクター画像
(背景) の上に配置したボタンをクリックするだけで pose bone を選択できます。

![overview]

## 主な機能

- **ビューポート・オーバーレイ表示**
  `SpaceView3D.draw_handler_add` による直接描画。別ウィンドウや N パネル埋め込み
  ではありません。ON/OFF トグル付き。
- **背景画像は外部パス参照方式**
  画像ファイルは Blend ファイルに埋め込みません。JSON 内にパスを保持します。
  (jpeg / png 対応)
- **クリック可能なボタン** (矩形 / 円形)
  - クリック = 選択 (他を解除)
  - Shift + クリック = 追加選択 (トグル)
  - Ctrl + クリック = 除外選択
  - ピッカー領域外のクリックはビューポート操作 (回転・パン等) にそのまま
    通すため、通常の 3D ビュー操作と競合しません。
- **編集モード**
  オーバーレイ上のクリックでボタン追加 / ドラッグで移動 / クリックで選択。
  N パネルから座標・サイズ・色・形状・対応ボーン名を編集できます。
- **複数リグ / 複数タブ** (front / back 等) の切り替え
- **選択ユーティリティ**: 全選択 / 解除 / 反転 / **左右ミラー選択**
- **セーブデータは外部 JSON**
  プロジェクト間で使い回せるように、ピッカー設定一式を `.json` ファイルとして
  書き出し・読み込みできます。

## 動作環境

- Blender **5.2.0** (5.2.x LTS)
- 描画は `gpu` + `gpu_extras` + `blf` のみ使用。非推奨の `bgl` は不使用。
- 純 Python / bpy のみ。PySide / Qt 等の外部 GUI ライブラリは不要。

## インストール

1. `kennys_animation_picker.zip` をダウンロードします (**解凍しない**)。
2. Blender を起動し、`Edit > Preferences > Add-ons` を開きます。
3. 右上の `Install from Disk...` をクリックし、ZIP を選択します。
4. 一覧から **"Animation: Kenny's Animation Picker"** にチェックを入れます。
5. 3D ビューポートの N パネル (右側のサイドバー) に **"Picker"** タブが
   追加されます。

> レガシーアドオン形式 (`bl_info` + `__init__.py`) です。
> ユーザー addons フォルダ (`%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`)
> に `kennys_animation_picker` フォルダごと配置しても有効化できます。

## 使い方

### 1. 有効化と背景画像

1. N パネル > **Picker** タブを開き、**Enable Picker** にチェックを入れます。
   ビューポート左下に半透明のピッカー領域が表示されます。
2. **Edit Mode** にチェックを入れます。
3. **Background Image** 欄の **Load Image** からキャラクター立ち絵などの
   画像ファイルを選択します。
4. **Fit Image to Viewport** ボタンで大きさを調整するか、Scale / X / Y /
   Opacity で手動調整します。
5. **Edit Mode** のチェックを外します。

### 2. ボタンの配置

編集モード中にオーバーレイ上で行えます (N パネルでも操作可能)。

- **空き領域をクリック** → その位置にボタンが作成されます
- **ボタンをドラッグ** → 移動
- **ボタンをクリック** → N パネルに選択され、以下の項目を編集できます
  - `ID`: ボタンの識別子 (ユニークにしてください)
  - `Bone`: クリック時に選択する pose bone 名
  - `Label`: ボタンに表示するテキスト (空なら ID / Bone を使用)
  - `X / Y / W / H`: 位置とサイズ (背景画像ピクセル基準)
  - `Shape`: Rectangle / Circle
  - `Color`: ボタンの色
- **Add Button** / **Duplicate** / **Delete** ボタンでも追加・複製・削除できます

### 3. 選択操作

- ボタンをクリック → 対応ボーンを選択
- Shift + クリック → 追加選択 / 解除 (トグル)
- Ctrl + クリック → 除外選択
- N パネルの **Selection** 欄:
  - `Select All` / `Clear` / `Invert`
  - `Mirror L/R`: 選択ボーンの左右ミラーを **標準命名規則の自動検出** で
    追加選択します

### 4. 左右ミラー命名規則 (自動検出)

優先順位の高い順に、以下のサフィックスパターンを検出します:

| パターン | 例 |
|---|---|
| `.L` / `.R` (Blender 標準) | `head.L` → `head.R` |
| `_L` / `_R` | `arm_L` → `arm_R` |
| `_l` / `_r` | `leg_l` → `leg_r` |
| `Left` / `Right` | `earLeft` → `earRight` |
| `left` / `right` | `earleft` → `earright` |

数字サフィックスにも対応: `hand_L.001` → `hand_R.001`

### 5. セーブ / ロード (JSON)

- **Save...**: 現在のリグ・タブ・ボタン・背景画像パスを JSON に書き出します
- **Load...**: JSON を読み込みます (複数リグ / 複数タブ対応)

背景画像パスが相対パスの場合、**JSON ファイルと同じフォルダ** → **Blend ファイルの
フォルダ** → カレントフォルダ の順で解決されます。プロジェクトを移動するときは
JSON と画像を同じフォルダに置いておくと安全です。

### JSON フォーマット

```json
{
  "format_version": 1,
  "tool": "Kenny's Animation Picker",
  "pickers": [
    {
      "rig_name": "Anby",
      "tabs": [
        {
          "name": "front",
          "background_image": "C:/path/to/picker_front.jpg",
          "anchor": "BL",
          "image_scale": 1.0,
          "image_offset_x": 0.0,
          "image_offset_y": 0.0,
          "image_opacity": 1.0,
          "buttons": [
            {"id": "head", "bone": "head", "shape": "rect",
             "x": 100, "y": 50, "w": 40, "h": 40,
             "color": "#88cc44", "label": "HEAD"}
          ]
        }
      ]
    }
  ]
}
```

読み込み時は、下記のような「単一リグ + 単一タブ」の簡易形式も受け付けます:

```json
{
  "rig_name": "Anby",
  "background_image": "C:/path/to/picker_front.jpg",
  "buttons": [
    {"id": "head", "bone": "head", "shape": "rect", "x": 100, "y": 50, "w": 40, "h": 40, "color": "#88cc44"}
  ]
}
```

## 技術メモ (Blender 5.2 API 対応)

- 選択 API: Blender 5.2 では `Bone.select` / `EditBone.select` に代わり
  **`PoseBone.select`** が標準です。本アドオンは両対応のヘルパ経由で選択します。
- 描画: `gpu.types.GPUTexture` (背景画像) + カスタム `GPUShader` +
  `gpu_extras.batch` + `blf` (テキスト)。`bgl` は使用しません。
- クリック処理: `SpaceView3D.draw_handler_add` + modal operator 方式。
  ピッカー領域内のクリックのみ処理し、他は `PASS_THROUGH` します。

## トラブルシューティング

- **クリックしても反応しない**: Enable Picker を一度 OFF → ON し直してください
  (ファイルを読み込んだ直後は自動的に OFF になります)。
- **背景画像が表示されない**: パスが正しいか、ファイルが存在するか確認して
  ください。存在しない場合は半透明のプレースホルダ領域が表示されます。
- **大きな画像で初回表示が遅い**: 初回のみ GPU テクスチャへ変換します
  (2 回目以降はキャッシュされます)。
- **ボタンがずれる**: ボタン座標は背景画像のピクセル基準です。別解像度の
  画像に差し替えると位置が変わります。

## ファイル構成

```
kennys_animation_picker.zip
└── kennys_animation_picker/
    ├── __init__.py      … アドオン本体 (単一ファイル)
    ├── README.md
    └── examples/
        └── sample_picker.json
```

## ライセンス

MIT License (商用・個人利用とも自由に使用できます)。
