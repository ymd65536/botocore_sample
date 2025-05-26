
## この記事のポイント

- AWS SDK for Python(boto3)のコアとなるbotocoreについて実例をもとに説明しているよ
- botocoreの設定を正しく扱わないとどうなるかについて説明しているよ

## はじめに

この記事では「この前リリースされた機能って実際に動かすとどんな感じなんだろう」とか「もしかしたら内容次第では使えるかも？？」などAWSサービスの中でも特定の機能にフォーカスして検証していく記事です。主な内容としては実践したときのメモを中心に書きます。（忘れやすいことなど）
誤りなどがあれば書き直していく予定です。

今回は「botocoreの使い方を誤るとだいぶ面倒なことになるのでは」というテーマで書きます。

## まずはboto3を使ってみよう

ふとした瞬間、AWS Lambdaの関数をboto3から実行したくなったとします。
たとえば、こんな関数がLambdaで定義されていたとします。

```python
import boto3


def lambda_handler(event, context):
    return f"boto3 version: {boto3.__version__}"

```

なんてことがないboto3のバージョンを取得するだけの関数です。この関数を次に記載するコードでinvokeしてみます。

```python
import boto3

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda')

res_payload = boto3_lambda_client.invoke(
    FunctionName='boto3_version_check',
    InvocationType='RequestResponse'
)['Payload']

print(res_payload.read())
```

実行結果

```text
b'"boto3 version: 1.35.92"'
```

問題なく実行できたかと思います。
このような実装は簡単な用途やテスト実行では問題ないことが多いはずです。そして一見して問題があるようには思えません。`pytest`などを実行してLambdaを実行する場合においてもpassすることがほとんどだと思います。

## 何が問題

結論から先に説明するとboto3の動作が環境によって異なり、想定とは違った動作をする可能性があるということです。説明だけではよくわからないと思いますので実際にやってみましょう。

まずはLambdaで定義したコードを以下のように書き換えます。

```python
import time
import boto3


def lambda_handler(event, context):
    time.sleep(60)
    return f"boto3 version: {boto3.__version__}"

```

もう一度、先ほどのコードからinvokeを実行します。
※実行結果を取得するまでに時間がかかります。

実行結果

```text
botocore.exceptions.ReadTimeoutError: Read timeout on endpoint URL: "https://lambda.ap-northeast-1.amazonaws.com/2015-03-31/functions/boto3_version_check/invocations"
```

エラーが発生して終わるはずです。このように問題なさそうな変更でもエラーが発生します。

## どうしてエラーが発生するのか

結論から述べるとboto3のSessionからClientを生成するとき、認証情報も含めデフォルト値を参照します。この設定値が適切ではないためにエラーが発生します。
(認証では`.aws/credential`、設定では`.aws/config`を参照します。)

なお、認証情報は特に指定がなければ読み込みの優先順位に従って認証されます。AWS CLIも同様ですが、基本的には`default`プロファイルが反応することでしょう。

※認証情報は[前回](https://qiita.com/ymd65536/items/8aa4b944f8b24292a19c#%E3%82%A2%E3%82%AB%E3%82%A6%E3%83%B3%E3%83%88%E6%83%85%E5%A0%B1%E3%82%92%E5%8F%96%E5%BE%97%E3%81%99%E3%82%8B)説明しました。

### ていうか実行時間長くね？

「60秒後に出力結果が出てもおかしくないのになんか実行結果が出るまで長くね？」と思ったかもしれません。これはのちほど詳しく説明しますが、簡単に説明しておくとboto3では再試行回数というのもが定義されています。

この再試行回数が働いたことによって実行時間が長くなり、ReadTimeoutが発生するということです。

この事象をもう少し具体的に確認したい場合はEC2のストップスタート（停止と起動）をLambdaでやってみると良いでしょう。うまくいくとEC2のストップスタートが複数回実行されているのがわかると思います。

なお、ドキュメントでは以下のリンクに記されています。

参考：[設定リファレンス - botocore 1.38.23 ドキュメント](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)

## エラーを解消するためにはどうすればいいか

結論から述べるとboto3の設定を変更することです。boto3の設定は`.aws/config`から変更ができますが、今回はbotocoreを使って設定を変更してみましょう。

## botocoreってなに

簡単に説明するとboto3の根っこの動作を司る重要な実装と言えます。
それはGitHubを見てもなんとなくわかるかなと思います。

参考：[botocore/botocore at develop · boto/botocore](https://github.com/boto/botocore/tree/develop/botocore)

このbotocoreの設定を変えることでboto3の動作を変更できます。

## 検証

では実際にやってみましょう。先ほどまでタイムアウトが出力されていたスクリプトを修正して戻り値を取得できるようにしましょう。

```python
import os
import boto3
from botocore.client import Config

botocore_config = Config(
    retries={
        'max_attempts': 0
    },
    read_timeout=120,
    connect_timeout=120,
    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
)

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda',config=botocore_config)

res_payload = boto3_lambda_client.invoke(
    FunctionName='boto3_version_check',
    InvocationType='RequestResponse'
)['Payload']

print(res_payload.read())

```

実行結果

```text
b'"boto3 version: 1.35.92"'
```

何がどう変わったかみてきましょう。

## 主な変更点

変更点としては`from botocore.client import Config`を使ってboto3の設定を変更しているということです。具体的には以下のコードです。

```python
from botocore.client import Config

botocore_config = Config(
    retries={
        'max_attempts': 0
    },
    read_timeout=120,
    connect_timeout=120,
    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
)

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda',config=botocore_config)
```

## botocore Configについて知る

今回はよく使うであろう部分について触れます。

参考：[設定リファレンス - botocore 1.38.23 ドキュメント](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)

## region_name

リージョン名を指定します。よくあるboto3のコードでは以下のように指定することもあると思います。

```python
import boto3

client_session = boto3.Session()
# ここでリージョンを指定する
boto3_lambda_client = client_session.client('lambda', region_name='ap-northeast-1')
```

なお、環境変数`AWS_DEFAULT_REGION`を設定しても同様のことができます。設定した場合は以下のように引数を省くことが可能です。

```python
import boto3

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda')
```

botocore Configを使った場合は以下のとおりです。

```python
import boto3
from botocore.client import Config

botocore_config = Config(
    region_name='ap-northeast-1'
)

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda',config=botocore_config)
```

なお、`read_timeout`は60秒、`connect_timeout`は60秒がデフォルトになります。

## read_timeout

今回のエラーの原因となった設定です。これは接続からの読み取りを試みたときにタイムアウト例外がスローされるまでの時間（秒）です。`connect_timeout`を迎えずに無事に接続ができたあとからカウントして60秒（デフォルト）を過ぎると今回のようにタイムアウトが発生します。

## connect_timeout

この設定は接続を試行する際にタイムアウト例外がスローされるまでの時間（秒）です。繋ぐまでにかかった時間を参考にタイムアウトが発生するとも言えます。

接続に60秒かかる場合は設定を変えてみると良いでしょう。ちなみに今回の検証では接続までは時間がかかっておらず、読み取りに時間がかかっています。

## retries

- total_max_attempts
- max_attempts
- mode

### total_max_attempts

最初のリクエスト数を含む試行回数、`total_max_attempts=1`とした場合はリクエストが試行されません。次に説明する`max_attempts`が同時に設定されている場合は`total_max_attempts`が優先されます。

### max_attempts

最初のリクエストを除く試行回数を指定します。`max_attempts=2`とした場合は最初のリクエストを含んで合計3回のリクエストになります。

#### total_max_attemptsとmax_attemptsの比較をコードで見る

試行回数3回の場合のコードを確認します。

`max_attempts`の場合は最初のリクエストを除いて合計3回になるので`max_attempts=2`になります。

```python
import boto3
from botocore.client import Config

botocore_config = Config(
    retries={
        'max_attempts': 2
    },
)
```

`total_max_attempts`の場合は最初のリクエストを含んで3回となるため`total_max_attempts=3`になります。

```python
import boto3
from botocore.client import Config

botocore_config = Config(
    retries={
        'total_max_attempts': 3
    },
)
```

地味な違いですが、AWS Lambdaは実行回数が課金の目安になるため気をつけておくと良いです。

### mode

boto3にはリトライ方法を定義する方法が3種類あります。この設定も試行回数を制御します。

- legacy
- standard
- adaptive

何も設定しなければ、デフォルトで`legacy`が選択されます。

## それ以外の設定

ドキュメントにはたくさんの設定項目がありますが、社内プロキシなどを制限のある環境下では以下の設定項目が有効です。

- proxies
- proxies_config
- client_cert

## まとめ

今回はbotocoreでboto3のリクエストを制御する方法について説明しました。
開発段階ではこういった細かい動作に気づかないことが多く、テストや本番デプロイ時に気づくことが多いです。あるいは問題ないと判断してデフォルト値を使っていたらのちに不具合として現れることがあります。

何かおかしいなと思ったら、CloudWatchによるモニタリングや実行環境を変えてみるなど
条件を変えて実行してみると良いでしょう。
