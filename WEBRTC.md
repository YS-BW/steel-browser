# WebRTC 分支与预构建镜像

这是 `steel-dev/steel-browser` 的实验分支 fork，基于上游 `aspectrr/headful-support` 的 `08a2ddfefe3d6d25a443799e27c9bd9f3a459720`。它不是上游正式发行版。

## 直接拉镜像运行

日常运行无需克隆代码或本地构建。镜像仓库：

- 国内：`ccr.ccs.tencentyun.com/ys-bw-steel/steel-browser-webrtc:webrtc`，腾讯云 TCR 公有仓库。
- GHCR：`ghcr.io/ys-bw/steel-browser-webrtc:webrtc`。
- 两个仓库都提供 `sha-63975ed6796341b37cf8bf7a51bead97ceb62b4a`，固定到本次已测试的构建源码。
- 架构：`linux/amd64` 和 `linux/arm64`，Docker 自动选择。

```sh
export STEEL_IMAGE=ccr.ccs.tencentyun.com/ys-bw-steel/steel-browser-webrtc:webrtc
# 也可使用 ghcr.io/ys-bw/steel-browser-webrtc:webrtc
docker pull "$STEEL_IMAGE"

docker run -d --name steel-webrtc \
  --memory=2g --cpus=3 --shm-size=512m \
  --tmpfs /recordings:size=256m \
  -p 127.0.0.1:3000:3000 \
  -p 127.0.0.1:3001:3001 \
  -p 127.0.0.1:9323:9223 \
  -p 127.0.0.1:10000-10010:10000-10010/udp \
  -e NODE_ENV=production \
  -e CHROME_HEADLESS=false \
  -e DOMAIN=127.0.0.1:3000 \
  -e CDP_DOMAIN=127.0.0.1:9323 \
  -e EXTERNAL_IP=127.0.0.1 \
  -e 'ICE_SERVERS_JSON=[]' \
  "$STEEL_IMAGE"
```

- WebRTC 操作页：[http://127.0.0.1:3001/sessions/debug](http://127.0.0.1:3001/sessions/debug)。这是分支自带的 Go 播放器。
- Steel API：[http://127.0.0.1:3000/v1](http://127.0.0.1:3000/v1)。
- CDP：9323。UDP 10000–10010 是 RTC 媒体端口，不能只映射 HTTP 端口。
- 以上参数用于浏览器和 Docker 在同一台机器的场景；端口只绑定本机。远程部署的信令地址、ICE/TURN、鉴权和网络策略需要单独配置和验证。
- 当前 Node API 返回的旧 `debugUrl` 不等同于上述 RTC 页面；本镜像不包含独立的 5173 管理控制台。

也可只下载本仓库的 `docker-compose.webrtc.yml` 配置文件，然后运行：

```sh
docker compose -f docker-compose.webrtc.yml pull
docker compose -f docker-compose.webrtc.yml up -d
```

更新时重新 pull 并重建容器。用完可执行 `docker stop steel-webrtc`。示例录像写入临时内存目录，容器停止后不保留。

## 国内镜像副本

国内副本存放在腾讯云广州地域的免费个人版公有仓库，拉取无需登录。2026-10-18 发布的多架构 digest 为：

```text
sha256:ceb049f65e14cc7a8d364139646350db92c4256ea720f6bf359f4ba5c0f88b6b
```

本次直接复制 GHCR 中已测试的镜像，没有重新构建，两个仓库的 manifest、架构和镜像层保持一致。需要锁定版本时，可把上方镜像名的 `:webrtc` 换成 `@sha256:ceb049f65e14cc7a8d364139646350db92c4256ea720f6bf359f4ba5c0f88b6b`。

国内副本按发布批次手动同步，尚未在 GitHub Actions 中配置腾讯云凭据；后续 GHCR 自动发布不代表国内标签已经更新。同步时，维护者先登录目标仓库，再使用 crane 复制已通过测试的固定 digest；默认复制全部架构：

```sh
crane copy --jobs 2 \
  ghcr.io/ys-bw/steel-browser-webrtc@sha256:ceb049f65e14cc7a8d364139646350db92c4256ea720f6bf359f4ba5c0f88b6b \
  ccr.ccs.tencentyun.com/ys-bw-steel/steel-browser-webrtc:webrtc
```

发布凭据不包含在镜像、Compose 或源码中。

## 修复内容

- 修复 Go RTP 转发持有空 slice 副本、无法得到新视频轨道的问题。
- 将 Go 视频编码声明由 VP8 改为 H.264，匹配 ffmpeg 的实际输出。
- 修复播放器缺少 `hiddenVideo` ID 和未启动视频播放的问题。
- 删除重复 click / keydown 发送，点击 canvas 后正确聚焦且不滚动外层页面。
- 保留上游协议：视频为 WebRTC，信令和用户输入为 WebSocket，系统输入通过 xdotool。

2026-10-18 本机验证：原始分支 RTC connected，但 20 秒解码 0 帧；修复后 20 秒解码 588 帧，1920×1080。Chrome 中通过画面点击、直接按键、文字输入、单次保存和链接导航验证。一次 Save 的服务端计数为 1。

滚轮、特殊键、剪贴板、连接资源回收、长时运行及公网场景仍需完善；这些基本链路测试不代表完整远控产品已经就绪。

## 镜像发布与复现

`.github/workflows/webrtc-image.yml` 使用 GitHub Actions 在 AMD64、ARM64 原生运行器上分别构建完整 `api/Dockerfile`，无需任何本地专用基础镜像。每种架构均先启动真实容器，用 aiortc 解码至少 30 帧 1080p 视频，再推送 GHCR；两种架构都通过后才发布统一的 `webrtc` / `latest` / `sha-…` 标签。结果保存在 workflow artifacts 中。

工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`，无需把个人 token 写入源码。上游 Apache-2.0 许可证保持不变。

需要自行构建时：

```sh
docker build -f api/Dockerfile -t steel-browser-webrtc:local .
python3 -m pip install -r tests/webrtc/requirements.txt
bash tests/webrtc/smoke.sh steel-browser-webrtc:local
```

smoke 脚本用于独立测试环境，会使用 3000、3001、10000–10010 端口。请先确认这些端口空闲。
