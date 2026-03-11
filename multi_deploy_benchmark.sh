#!/usr/bin/env bash
# ==============================================================================
# 多容器批量部署执行脚本 (私域机部署工具)
# 
# 功能：
#   1. 支持自定义多个存储目录与对应绑定的端口号变量配置
#   2. 自动把最终离线评测压缩包分别解压到各个目标目录，确保完全隔离的多份评测副本
#   3. 自动修改各自解压后工作区中的 .env 配置文件，将其中的 LOCAL_HOST_PORT 设置为对应端口
#   4. 各自工作区独立挂载执行，由 run_mixed_benchmark.sh 一键在各目录后台拉起评测容器
# 
# 使用方式：
#   修改下方的 PACKAGE_PATH 及 TARGETS 变量，然后执行本脚本。
#   bash multi_deploy_benchmark.sh
# ==============================================================================

set -euo pipefail

# ==========================================
# 用户自定义变量区
# ==========================================

# 1. 最终的压缩包路径（请手动替换为实际的 eval_workspace_*.tar.gz 路径）
PACKAGE_PATH="outputs/eval_workspace_YYYYMMDD_HHMMSS.tar.gz"

# 2. 定义目标部署文件夹与对应的端口号
# 格式: "自定义工作区路径:端口号" (如无需手工创建，系统将自动创建不存在的文件夹)
TARGETS=(
    "/opt/eval_container_1:8113"
    "/opt/eval_container_2:8114"
    "/opt/eval_container_3:8115"
)

# ==========================================

if [ ! -f "$PACKAGE_PATH" ]; then
    echo "❌ 找不到压缩包: $PACKAGE_PATH"
    echo "   请先修改脚本中的 PACKAGE_PATH 变量，指向正确且存在的压缩包文件路径。"
    exit 1
fi

for TARGET in "${TARGETS[@]}"; do
    # 解析路径和端口号
    DIR="${TARGET%%:*}"
    PORT="${TARGET##*:}"
    
    echo "================================================="
    echo "🚀 开始为您部署新容器副本 -> 目标目录: $DIR (配置端口: $PORT)"
    
    # 步骤 1: 创建目录并解压
    mkdir -p "$DIR"
    echo "📦 正在将压缩包分发并解压至 $DIR ..."
    tar -xzf "$PACKAGE_PATH" -C "$DIR"
    
    # 自动定位真实的解压后工作区目录（查找包含 .env 的目录，排除隐藏目录等）
    REAL_WORKSPACE=$(dirname "$(find "$DIR" -name ".env" | head -n 1)")
    if [ -z "$REAL_WORKSPACE" ]; then
        echo "❌ 解压后在 $DIR 未能找到 .env 配置文件，请检查压缩包打包方式。"
        continue
    fi
    echo "📂 识别到实际可挂载的工作区目录: $REAL_WORKSPACE"
    
    # 步骤 2: 修改独立工作区 .env 中的 LOCAL_HOST_PORT 和 LOCAL_URL 端口号
    # 兼容 mac/linux 的 sed 用法
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^LOCAL_HOST_PORT=.*/LOCAL_HOST_PORT=${PORT}/g" "$REAL_WORKSPACE/.env"
        sed -i '' "s|\(LOCAL_URL=.*:\)[0-9]\{1,\}\(/.*\)|\1${PORT}\2|g" "$REAL_WORKSPACE/.env"
    else
        sed -i "s/^LOCAL_HOST_PORT=.*/LOCAL_HOST_PORT=${PORT}/g" "$REAL_WORKSPACE/.env"
        sed -i "s|\(LOCAL_URL=.*:\)[0-9]\{1,\}\(/.*\)|\1${PORT}\2|g" "$REAL_WORKSPACE/.env"
    fi
    echo "✅ 已成功覆盖 $REAL_WORKSPACE/.env 设置，LOCAL_HOST_PORT=$PORT 且同步更新了 LOCAL_URL"
    
    # 步骤 3: 寻找是否有需 load 的离线镜像包（第一次需 load 后续会跳过）
    TAR_PATH="$REAL_WORKSPACE/benchmark-eval.tar.gz"
    if [ -f "$TAR_PATH" ]; then
        IMAGE_TAR_FLAG="--image-tar $TAR_PATH"
    else
        IMAGE_TAR_FLAG=""
    fi

    # 切换到实际工作区并执行拉起
    echo "▶️ 正在触发后台运行脚本..."
    cd "$REAL_WORKSPACE" || exit 1
    
    if [ -f "run_mixed_benchmark.sh" ]; then
        # 挂载执行指令参考 run_mixed_benchmark.sh (并附加 tar 作为备选 load)
        bash run_mixed_benchmark.sh --workspace "$REAL_WORKSPACE" $IMAGE_TAR_FLAG
        echo "✅ 容器副本 $DIR 隔离挂载与启动指令已下发完毕"
    else
        echo "❌ 在工作区未找到 run_mixed_benchmark.sh 启动脚本！"
    fi
    
    # 回到原来位置
    cd - > /dev/null
    echo "================================================="
    echo ""
done

echo "🎉 恭喜！您指定的所在机器所有私域容器部署动作均已触发完毕！"
echo "👉 您可以通过分别进入各工作区下的日志查看进展："
echo "     tail -f <解压实际工作区>/logs/mixed_eval_*.log"
