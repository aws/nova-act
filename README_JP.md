# Nova Act

<p align="center">
   	<a href="README_JP.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
	<a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
</p>

Amazon Nova Actのための Python SDK です。

Nova Actは、Webブラウザで確実にアクションを実行できるように設計されたエージェントを構築するためのSDK + モデルの初期研究プレビューです。SDKを使用することで、開発者は複雑なワークフローを小さな信頼性の高いコマンドに分解し、必要に応じて詳細を追加し、APIを呼び出し、ブラウザの直接操作を組み合わせることができます。開発者は、テスト、ブレークポイント、アサート、並列化のためのスレッドプーリングなど、Pythonコードを組み合わせることができます。発表の詳細については、以下をご覧ください：https://labs.amazon.science/blog/nova-act

## 免責事項

Amazon Nova Actは実験的なSDKです。Nova Actを使用する際は、以下の点に注意してください：

1. Nova Actは間違いを起こす可能性があります。Nova Actのモニタリングと[利用規約](https://www.amazon.com/gp/help/customer/display.html?nodeId=TTFAPMmEqemeDWZaWf)に従った使用は、ユーザーの責任となります。当社は、サービスの提供、開発、改善のため、Nova Actとのインタラクション（プロンプトやNova Actがブラウザと関与している際に取得されたスクリーンショットを含む）に関する情報を収集します。Nova Actのデータの削除をリクエストする場合は、nova-act@amazon.comまでメールでご連絡ください。

2. APIキーは共有しないでください。APIキーにアクセスできる人は誰でも、あなたのAmazonアカウントでNova Actを操作できます。APIキーを紛失したり、他人がアクセスした可能性がある場合は、nova-act@amazon.comに連絡してキーを無効化し、新しいキーを取得してください。

3. アカウントパスワードなどの機密情報はNova Actに提供しないことを推奨します。Playwrightコールを通じて機密情報を使用する場合、Nova Actがアクションを完了する際にブラウザ上で情報が表示されていると、スクリーンショットに情報が含まれる可能性があることに注意してください。（以下の[機密情報の入力](#機密情報の入力)を参照）

4. デフォルトのブラウジング環境を使用している場合、エージェントを識別するにはユーザーエージェント文字列内の`NovaAct`を確認してください。独自のブラウジング環境でNova Actを操作する場合や、ユーザーエージェントをカスタマイズする場合は、同じ文字列を含めることを推奨します。

## 前提条件

1. オペレーティングシステム：MacOSまたはUbuntu
2. Python 3.10以上

## ビルド

```sh
python -m pip install --editable '.[dev]'
python -m build --wheel --no-isolation --outdir dist/ .
```

## セットアップ

### 認証

https://nova.amazon.com/act に移動し、APIキーを生成してください。

ターミナルで以下を実行してAPIキーを環境変数として保存します：
```sh
export NOVA_ACT_API_KEY="your_api_key"
```

### インストール

```bash
pip install nova-act
```

## クイックスタート：Amazonでコーヒーメーカーを注文する

*注：NovaActを初めて実行する場合、起動に1〜2分かかることがあります。これは、NovaActが[Playwrightモジュールのインストール](https://playwright.dev/python/docs/browsers#install-browsers)を行う必要があるためです。2回目以降の実行は数秒で起動します。この機能は環境変数`NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL`を設定することでオフにできます。*

### スクリプトモード

```python
from nova_act import NovaAct

with NovaAct(starting_page="https://www.amazon.com") as nova:
    nova.act("search for a coffee maker")
    nova.act("select the first result")
    nova.act("scroll down or up until you see 'add to cart' and then click 'add to cart'")
```

SDKは(1)Chromeを開き、(2)Amazon.comでコーヒーメーカーの商品詳細ページに移動してカートに追加し、(3)Chromeを閉じます。実行の詳細はコンソールログメッセージとして出力されます。

NovaActの初期化に関する他のランタイムオプションについては、[NovaActの初期化](#novaactの初期化)セクションを参照してください。

### インタラクティブモード

_**注意**: NovaActは現時点で`ipython`をサポートしていません。標準のPythonシェルを使用してください。_

インタラクティブPythonを使用すると、実験がしやすくなります：

```sh
% python
Python 3.10.16 (main, Dec  3 2024, 17:27:57) [Clang 16.0.0 (clang-1600.0.26.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> from nova_act import NovaAct
>>> nova = NovaAct(starting_page="https://www.amazon.com")
>>> nova.start()
>>> nova.act("search for a coffee maker")
```

エージェントが上記のステップを完了したら、次のステップを入力できます：

```sh
>>> nova.act("select the first result")
```

これらの`act()`呼び出しの間にブラウザを操作することもできますが、`act()`の実行中はブラウザを操作しないでください。基礎となるモデルが変更内容を認識できなくなります！

### サンプル

[samples](./src/nova_act/samples)フォルダには、Nova Actを使用してさまざまなタスクを完了するいくつかの例が含まれています：
* 不動産Webサイトでアパートを検索し、各アパートの駅からの距離を検索し、これらを1つの結果セットにまとめます。[このサンプル](./src/nova_act/samples/apartments_caltrain.py)は、複数のNovaActを並列に実行する方法を示しています（詳細は以下を参照）。
* Sweetgreenから食事を注文して配達してもらいます。[このサンプル](./src/nova_act/samples/order_salad.py)は、`user_data_dir`をオーバーライドして、order.sweetgreen.comで認証済みのブラウザを提供する方法を示しています（詳細は以下を参照）。

## act()の使い方

既存のコンピュータ使用エージェントは、エンドツーエンドのタスクを達成するために、1つのプロンプトで全体の目標（場合によってはエージェントを導くためのヒントを含む）を指定します。そしてエージェントは、目標を達成するために多くのステップを順番に実行する必要があり、途中で発生する問題や非決定性により、ワークフローが軌道から外れる可能性があります。

残念ながら、現在のSOTAエージェントモデルは、このような方法で使用した場合に満足のいく信頼性レベルを達成することができません。Nova Actでは、別の人にタスクの完了方法を説明するかのように、プロンプトのステップを複数の`act()`呼び出しに分割することを提案します。これが、繰り返し可能で信頼性が高く、保守が容易なワークフローを構築するための現時点での最善の方法だと考えています。

Nova Actのプロンプト作成時：

**1. エージェントが行うべきことを明確かつ簡潔に指示する**

❌ やってはいけない例
```python
nova.act("注文履歴からIndia Palaceからの最新の注文を見つけて再注文する")
```

✅ 推奨される例
```python
nova.act("ハンバーガーメニューアイコンをクリックし、注文履歴に移動し、India Palaceからの最新の注文を見つけて再注文する")
```

❌ やってはいけない例
```python
nova.act("VTAのルートを見てみましょう")
```

✅ 推奨される例
```python
nova.act("ルートタブに移動する")
```

❌ やってはいけない例
```python
nova.act("友達に会いに行きたいので、Orange Lineの次の電車がいつ来るか調べる必要があります。")
```

✅ 推奨される例
```python
nova.act(f"Government Centerから{time}以降のOrange Lineの次の出発時刻を探す")
```

**2. 大きなアクションを小さなアクションに分割する**

❌ やってはいけない例
```python
nova.act("$100未満で最高の評価のホテルを予約して")
```

✅ 推奨される例
```python
nova.act(f"{startdate}から{enddate}の間のヒューストンのホテルを検索")
nova.act("平均顧客評価でソート")
nova.act("$100以下の最初のホテルの予約ボタンを押す")
nova.act(f"{blob}に従って名前、住所、生年月日を入力")
...
```

## 一般的な構成要素

### Webページから情報を抽出する

`pydantic`を使用し、ブラウザページに関する質問に特定のスキーマで回答するよう`act()`に要求します。

- 構造化された応答を期待する場合は、boolean（はい/いいえ）であっても、必ずスキーマを使用してください。
- 情報を抽出するプロンプトは、独立した`act()`呼び出しに分けてください。

例：
```python
from pydantic import BaseModel
from nova_act import NovaAct, ActResult


class Book(BaseModel):
    title: str
    author: str

class BookList(BaseModel):
    books: list[Book]


def get_books(year: int) -> BookList | None:
    """
    NYTの年間トップ本を取得し、BookListとして返します。エラーの場合はNoneを返します。
    """
    with NovaAct(
        starting_page=f"https://en.wikipedia.org/wiki/List_of_The_New_York_Times_number-one_books_of_{year}#Fiction"
    ) as nova:
        result = nova.act("Fiction（小説）リストの本を返してください",
                       # パース用のスキーマを指定
                       schema=BookList.model_json_schema())
        if not result.matches_schema:
            # act応答がスキーマと一致しない場合 ¯\_(ツ)_/¯
            return None
        # JSONをPydanticモデルにパース
        book_list = BookList.model_validate(result.parsed_response)
        return book_list
```

boolean応答のみが必要な場合は、便利な`BOOL_SCHEMA`定数があります：

例：
```python
from nova_act import NovaAct, BOOL_SCHEMA

with NovaAct(starting_page="https://www.amazon.com") as nova:
    result = nova.act("ログインしていますか？", schema=BOOL_SCHEMA)
    if not result.matches_schema:
        # act応答がスキーマと一致しない場合 ¯\_(ツ)_/¯
        print(f"無効な結果：{result=}")
    else:
        # result.parsed_responseがbooleanになります
        if result.parsed_response:
            print("ログインしています")
        else:
            print("ログインしていません")
```

### 複数のセッションを並列に実行する

1つの`NovaAct`インスタンスは一度に1つのブラウザしか操作できません。ただし、複数の`NovaAct`インスタンスで複数のブラウザを同時に操作することは可能です！これらは非常に軽量です。これを使用してタスクの一部を並列化し、インターネットのためのブラウザ使用マップリデュースのようなものを作成できます。以下のコードは、異なるブラウザインスタンスで並列に本を検索します。なお、以下のコードは前の「Webページから情報を抽出する」セクションの本のサンプルを基にしています。

前述の`get_books`の例を使用：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

from nova_act import ActError, NovaAct


# 完全なリストをここに蓄積します
all_books = []
# max_workersをアクティブなブラウザセッションの最大数に設定します
with ThreadPoolExecutor(max_workers=10) as executor:
    # 2010年から2024年までの本を並列に取得します
    future_to_books = {
        executor.submit(get_books, year): year for year in range(2010, 2025)
    }
    # 結果をall_booksに収集します
    for future in as_completed(future_to_books.keys()):
        try:
            year = future_to_books[future]
            book_list = future.result()
            if book_list is not None:
                all_books.extend(book_list.books)
        except ActError as exc:
            print(f"エラーのため年をスキップ：{exc}")

print(f"{len(all_books)}冊の本が見つかりました：\n{all_books}")
```

### 認証、Cookie、永続的なブラウザ状態

必要なWebサイトに既にログインしている既存のChromeプロファイルを指定して、認証を支援することができます。
デフォルトでは、各NovaActはそのChrome `user_data_dir`として新しい一時ディレクトリから開始します。ただし、
`user_data_dir`引数を使用して既存のディレクトリを指定することができます。

推奨されるアプローチは、NovaAct用に新しい`user_data_dir`をセットアップし、必要に応じて再認証したり、
より多くのWebサイトにログインしたりして更新することです。以下は、`user_data_dir`の設定や変更を支援するサンプルスクリプトです。

```python
import os

from nova_act import NovaAct

os.makedirs(user_data_dir, exist_ok=True)

with NovaAct(starting_page="https://amazon.com/", user_data_dir=user_data_dir, clone_user_data_dir=False):
    input("Webサイトにログインし、完了したらEnterを押してください...")

print(f"ユーザーデータディレクトリを{user_data_dir=}に保存しました")
```

このスクリプトはインストールに含まれています：`python -m nova_act.samples.setup_chrome_user_data_dir`

各NovaActインスタンスは独自の`user_data_dir`が必要なため、既存の`user_data_dir`を提供する場合、各NovaActの一時ディレクトリにコピーが作成されます。必要に応じて、`clone_user_data_dir`引数を`False`に設定することでこれを無効にできますが、一度に1つのセッションのみがそのディレクトリにアクセスしていることを確認する必要があります。

複数の`NovaAct`インスタンスを並列に実行している場合、それぞれが独自のコピーを作成する必要があるため、クローニングはオンのままにしておく必要があります。

### 機密情報の入力

パスワードや機密情報（クレジットカード、社会保障番号）を入力する場合は、機密情報をモデルにプロンプトしないでください。入力したい要素に焦点を当てるようモデルに依頼してください。次に、Playwright APIを直接使用して`client.page.keyboard.type(sensitive_string)`でデータを入力します。そのデータは、[`getpass`](https://docs.python.org/3/library/getpass.html)を使用したコマンドラインでのプロンプト、引数の使用、または環境変数の設定など、任意の方法で取得できます。

> **注意：** Playwright APIを通じて提供された情報を含め、機密情報を表示しているブラウザ画面でNova Actにアクションを実行するよう指示した場合、その情報は収集されるスクリーンショットに含まれます。

```python
# サインイン
nova.act("ユーザー名janedoeを入力し、パスワードフィールドをクリックする")
# コマンドラインからパスワードを収集し、playwrightを通じて入力します（ネットワーク経由で送信されません）
nova.page.keyboard.type(getpass())
# ユーザー名とパスワードが入力されたので、NovaActに進行を指示します
nova.act("サインインする")
```

> **注：** ページ要素がエージェントによってフォーカスできない問題が発生することがあります。この問題の修正に取り組んでいます。それまでの間、回避策として以下のようにNova Actに指示することができます：
> ```python
> nova.act("パスワードフィールドに ''を入力する")
> nova.page.keyboard.type(getpass())
> ```

### CAPTCHAs

NovaActはCAPTCHAを解決しません。それはユーザーが行う必要があります。スクリプトが特定の場所でCAPTCHAに遭遇した場合、以下のことができます：

1. CAPTCHAが表示されているかどうかを確認する（`act()`を使用して画面を検査）
2. CAPTCHAがある場合、ワークフローを一時停止し、ユーザーにCAPTCHAを突破するよう依頼します。例えばターミナルから起動されたワークフローの場合は`input()`を使用し、CAPTCHAを通過したらユーザーがワークフローを再開できるようにします。

```python
result = nova.act("画面にCAPTCHAがありますか？", schema=BOOL_SCHEMA)
if result.matches_schema and result.parsed_response:
    input("CAPTCHAを解決し、完了したらReturnを押してください")
...
```

### Webサイトでの検索

```python
nova.go_to_url(website_url)
nova.act("catsを検索する")
```

モデルが検索ボタンを見つけるのに苦労している場合、Enterを押して検索を開始するよう指示できます。

```python
nova.act("catsを検索する。Enterを押して検索を開始する。")
```

### ファイルのダウンロード

Playwrightを使用して、Webページ上のファイルをダウンロードできます。

ダウンロードアクションボタンを通じて：

```python
# ダウンロードをキャプチャするようplaywrightに依頼し、その後ページを操作してダウンロードを開始します
with nova.page.expect_download() as download_info:
    nova.act("ダウンロードボタンをクリックする")

# ダウンロードの一時パスが利用可能です
print(f"ダウンロードしたファイル {download_info.value.path()}")

# ダウンロードしたファイルを任意の場所に永続的に保存します
download_info.value.save_as("my_downloaded_file")
```

`act()`を使用して移動した現在のページ（例：PDF）をダウンロード：

```python
# Playwrightのrequestを使用してコンテンツをダウンロードします
response = nova.page.request.get(nova.page.url)
with open("downloaded.pdf", "wb") as f:
    f.write(response.body())
```

### 日付の選択

絶対時間で開始日と終了日を指定するのが最も効果的です。

```python
nova.act("3月23日から3月28日の日付を選択する")
```

### ブラウザのユーザーエージェントの設定

Nova ActにはPlaywrightのChromeとChromiumブラウザが付属しています。これらはPlaywrightによって設定されたデフォルトのユーザーエージェントを使用します。`user_agent`オプションでこれをオーバーライドできます：

```python
nova = NovaAct(..., user_agent="MyUserAgent/2.7")
```

### ログ

デフォルトでは、`NovaAct`は`logging.INFO`以上のすべてのログを出力します。これは環境変数`NOVA_ACT_LOG_LEVEL`の下に整数値を指定することでオーバーライドできます。整数は[Pythonのログレベル](https://docs.python.org/3/library/logging.html#logging-levels)に対応している必要があります。

### actトレースの表示

`act()`が完了すると、実行内容のトレースを自己完結型のhtmlファイルに出力します。ファイルの場所はコンソールトレースに出力されます。

```sh
> ** View your act run here: /var/folders/6k/75j3vkvs62z0lrz5bgcwq0gw0000gq/T/tmpk7_23qte_nova_act_logs/15d2a29f-a495-42fb-96c5-0fdd0295d337/act_844b076b-be57-4014-b4d8-6abed1ac7a5e_output.html
```

`NovaAct`に`logs_directory`引数を渡すことで、このディレクトリを変更できます。

### セッションの記録

`NovaAct`コンストラクタで`logs_directory`を設定し、`record_video=True`を指定することで、ブラウザセッション全体を簡単に記録できます。

## 既知の制限事項

Nova Actは、プロトタイピングと探索のための研究プレビューです。これは、大規模で有用なエージェントを構築するための重要な機能を構築するという私たちのビジョンの最初のステップです。この段階では多くの制限に遭遇することが予想されます。より良いものにするために[nova-act@amazon.com](mailto:nova-act@amazon.com?subject=Nova%20Act%20Bug%20Report)にフィードバックを提供してください。

例えば：

* `act()`は非ブラウザアプリケーションと対話できません。
* `act()`は高レベルのプロンプトでは信頼性が低くなります。
* `act()`はマウスオーバーで隠れている要素と対話できません。
* `act()`はブラウザウィンドウと対話できません。これは、位置情報へのアクセスを要求するブラウザモーダルなどは`act()`の邪魔にはなりませんが、必要な場合は手動で承認する必要があることを意味します。

## リファレンス

### NovaActの初期化

コンストラクタは以下を受け入れます：

* `starting_page (str)`：開始ページのURL（必須引数）
* `headless (bool)`：ブラウザをヘッドレスモードで起動するかどうか（デフォルトは`False`）
* `quiet (bool)`：ターミナルへのログ出力を抑制するかどうか（デフォルトは`False`）
* `user_data_dir (str)`：Cookie やローカルストレージなどのブラウザセッションデータを保存する[ユーザーデータディレクトリ](https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md#introduction)へのパス（デフォルトは`None`）
* `nova_act_api_key (str)`：認証のために生成したAPIキー。環境変数`NOVA_ACT_API_KEY`が設定されていない場合は必須。渡された場合、環境変数より優先されます。
* `logs_directory (str)`：NovaActがログ、実行情報、ビデオ（`record_video`が`True`に設定されている場合）を出力するディレクトリ
* `record_video (bool)`：ビデオを記録して`logs_directory`に保存するかどうか。ビデオを記録するには`logs_directory`の指定が必要です。

これにより1つのブラウザセッションが作成されます。必要な数のブラウザセッションを作成して並列に実行できますが、1つのセッションはシングルスレッドでなければなりません。

### ブラウザの操作

#### actの使用

`act()`は、ユーザーから自然言語のプロンプトを受け取り、ユーザーに代わってブラウザウィンドウを操作して目標を達成します。引数：

* `max_steps (int)`：`act()`がタスクを諦めるまでに実行するステップ（ブラウザ操作）の最大数を設定します。これを使用して、エージェントが異なるパスを試みて永遠にスタックしないようにします。デフォルトは30です。
* `timeout (int)`：act呼び出し全体のタイムアウト秒数。モデルサーバーの負荷とWebサイトのレイテンシーによってステップごとの時間が変わる可能性があるため、`max_steps`の使用を推奨します。

`ActResult`を返します。

```python
class ActResult:
    response: str | None
    parsed_response: Union[Dict[str, Any], List[Any], str, int, float, bool] | None
    valid_json: bool | None
    matches_schema: bool | None
    metadata: ActMetadata

class ActMetadata:
    session_id: str | None
    act_id: str | None
    num_steps_executed: int
    start_time: float
    end_time: float
    prompt: string
```

インタラクティブモードを使用する場合、ctrl+xでエージェントアクションを終了し、別の`act()`呼び出しのためにブラウザをそのまま残すことができます。ctrl+cではこれができず、ブラウザが終了し、`NovaAct`の再起動が必要になります。

#### プログラムで実行する

`NovaAct`は、Playwrightの[`Page`](https://playwright.dev/python/docs/api/class-page)オブジェクトを`page`属性で直接公開しています。

これを使用して、ブラウザの現在の状態（スクリーンショットやDOMなど）を取得したり、操作したりできます：

```python
screenshot_bytes = nova.page.screenshot()
dom_string = nova.page.content()
nova.page.keyboard.type("hello")
```

**注意：`nova.page.goto`の代わりに`nova.go_to_url`を使用してください**

Playwright Pageの`goto()`メソッドには30秒のデフォルトタイムアウトがあり、読み込みが遅いWebサイトで失敗する可能性があります。ページがこの時間内に読み込みを完了しない場合、`goto()`は`TimeoutError`を発生させ、ワークフローが中断される可能性があります。さらに、Playwrightがページが完全に読み込まれる前に準備ができたと判断する場合があるため、goto()はactとうまく連携しない場合があります。
これらの問題に対処するため、より信頼性の高いナビゲーションを提供する新しい関数`go_to_url()`を実装しました。`nova.start()`の後に`nova.go_to_url(url)`を呼び出すことで使用できます。

## バグの報告
改善にご協力ください！問題に気づいた場合は、nova-act@amazon.comにバグレポートを提出してください。
メールには以下を必ず含めてください：
- 問題の説明
- コンソールログメッセージとして出力されたセッションID
- 使用しているワークフローのスクリプト

皆様のフィードバックは、すべてのユーザーにとってより良い体験を確保するために貴重です。

Nova Actをお試しいただきありがとうございます！
