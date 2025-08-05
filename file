FROM python:3.11

WORKDIR /app

# Set pip mirror source to domestic source
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装Oracle客户端依赖
RUN apt-get update && apt-get install -y \
    libaio1 \
    wget \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装Oracle Instant Client
RUN mkdir -p /opt/oracle \
    && wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip -O /opt/oracle/instantclient.zip \
    && unzip /opt/oracle/instantclient.zip -d /opt/oracle \
    && rm /opt/oracle/instantclient.zip \
    && echo /opt/oracle/instantclient* > /etc/ld.so.conf.d/oracle-instantclient.conf \
    && ldconfig

# 设置环境变量
ENV PYTHONPATH=/app
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient*

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动应用程序
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]