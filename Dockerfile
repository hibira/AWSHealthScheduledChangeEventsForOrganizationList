FROM public.ecr.aws/lambda/python:3.11

# 依存関係をインストール
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# アプリケーションコードをコピー
COPY get_eol_health.py ${LAMBDA_TASK_ROOT}
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}

# Lambda関数のハンドラーを指定
CMD ["lambda_handler.lambda_handler"]