#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多乐园数据采集器（在「能访问 api.themeparks.wiki 的机器」上运行）
---------------------------------------------------------------
线上服务器（阿里云）无国际出口，无法直连 API；本脚本在本机采集后
通过 /api/relay 接口把数据推送到服务器，服务器仅作展示。

用法：
  python collect_push.py            # 立即采集全部在采集窗口内的乐园一次
  python collect_push.py --loop     # 每 10 分钟循环采集（建议用计划任务/cron 跑这个）
  python collect_push.py --park shanghai-disney   # 只采指定乐园

依赖：仅 Python 标准库（urllib）。若本机有 curl 会优先用 curl（更稳）。

部署建议（让看板持续有数据）：
  Windows 计划任务 / macOS crontab / Linux cron 每 10 分钟执行：
      python collect_push.py --loop

  GitHub Actions（推荐，关机也能采）：把本脚本与 .github/workflows/collect.yml
  推到「公开」仓库，在仓库 Settings → Secrets and variables → Actions 配置
  RELAY_SERVER 与 RELAY_TOKEN 两个 secret，Actions 云端每 15 分钟自动采集并
  推送到服务器，完全不依赖任何本地机器开机。
  配置项（均可由环境变量覆盖，缺省为本地默认）：
      RELAY_SERVER  服务器地址，默认 http://8.148.181.106
      RELAY_TOKEN   推送令牌，默认 chimelong2026（须与服务器 RELAY_TOKEN 一致）
"""
import sys, os, json, time, datetime, urllib.request, urllib.error

# ============ 配置 ============
SERVER = os.environ.get("RELAY_SERVER", "http://8.148.181.106")   # 服务器地址（端口 80）
RELAY_TOKEN = os.environ.get("RELAY_TOKEN", "chimelong2026")      # 与服务端 RELAY_TOKEN 一致
API_BASE = "https://api.themeparks.wiki/v1/entity/{uuid}/live"

# 与 cloud-server/server-core.js 的 PARKS 保持一致（含 uuid / hours）
PARKS = [
    {"id":"chimelong-ocean","name":"长隆海洋王国","region":"中国","uuid":"6f8764b7-172a-4fcf-8fec-10d3e44a55e4","hours":{"open":10,"close":19,"closeMinute":30}},
    {"id":"chimelong-spaceship","name":"长隆飞船乐园","region":"中国","uuid":"18a2aeb2-7be5-4273-8cac-611ae5b519f6"},
    {"id":"chimelong-paradise","name":"广州长隆欢乐世界","region":"中国","uuid":"73436fe5-1f14-400f-bfbf-ab6766269e70"},
    {"id":"chimelong-safari","name":"广州长隆野生动物世界","region":"中国","uuid":"a148a943-616b-41c8-b5f8-27e67f7bdf33"},
    {"id":"shanghai-disney","name":"上海迪士尼","region":"中国","uuid":"ddc4357c-c148-4b36-9888-07894fe75e83"},
    {"id":"hongkong-disney","name":"香港迪士尼","region":"中国","uuid":"bd0eb47b-2f02-4d4d-90fa-cb3a68988e3b"},
    {"id":"universal-beijing","name":"北京环球影城","region":"中国","uuid":"68e1d8f0-ed42-4351-af25-160421e37ce0"},
    {"id":"oceanpark-hk","name":"香港海洋公园","region":"中国","uuid":"1c6cf709-2157-443d-9c4b-d443dd53c0de"},
    {"id":"fantawild-wuhu","name":"芜湖方特东方神画","region":"中国","uuid":"61db06cd-7f71-4a15-920e-857e7cc698cb"},
    {"id":"fantawild-tianjin","name":"天津方特探险","region":"中国","uuid":"b45a6515-1beb-48f9-b373-f770820be202"},
    {"id":"boonie-ningbo","name":"宁波熊出没乐园","region":"中国","uuid":"48420d03-8f40-4b15-b841-c145a93fec6d"},
    {"id":"magic-kingdom","name":"奥兰多·神奇王国","region":"国际","uuid":"75ea578a-adc8-4116-a54d-dccb60765ef9"},
    {"id":"disneyland-ca","name":"加州·迪士尼乐园","region":"国际","uuid":"7340550b-c14d-4def-80bb-acdb51d49a66"},
    {"id":"tokyo-disneyland","name":"东京迪士尼乐园","region":"国际","uuid":"3cc919f1-d16d-43e0-8c3f-1dd269bd1a42"},
    {"id":"tokyo-disneysea","name":"东京迪士尼海洋","region":"国际","uuid":"67b290d5-3478-4f23-b601-2f8fb71ba803"},
    {"id":"universal-fl","name":"奥兰多·环球影城","region":"国际","uuid":"eb3f4560-2383-4a36-9152-6b3e5ed6bc57"},
    {"id":"epic-universe","name":"奥兰多·环球史诗宇宙","region":"国际","uuid":"12dbb85b-265f-44e6-bccf-f1faa17211fc"},
    {"id":"universal-hollywood","name":"好莱坞·环球影城","region":"国际","uuid":"bc4005c5-8c7e-41d7-b349-cdddf1796427"},
    {"id":"universal-japan","name":"大阪·环球影城","region":"国际","uuid":"47f61fac-7586-41ac-ae80-61c9257cf33e"},
    {"id":"sixflags-magic-mountain","name":"六旗魔山","region":"国际","uuid":"c6073ab0-83aa-4e25-8d60-12c8f25684bc"},
    {"id":"europa-park","name":"欧洲乐园 Europa-Park","region":"国际","uuid":"639738d3-9574-4f60-ab5b-4c392901320b"},
    {"id":"phantasialand","name":"幻想乐园 Phantasialand","region":"国际","uuid":"abb67808-61e3-49ef-996c-1b97ed64fac6"},
    {"id":"efteling","name":"艾夫特琳 Efteling","region":"国际","uuid":"30713cf6-69a9-47c9-a505-52bb965f01be"},
    {"id":"fuji-q","name":"富士急高地","region":"国际","uuid":"ae527507-b1d0-4d40-83ea-143d87bef989"},
]

def beijing_now():
    utc = datetime.datetime.now(datetime.timezone.utc)
    return utc + datetime.timedelta(hours=8)

def within_hours(park):
    if not park.get("hours"): return True
    bj = beijing_now(); h = bj.hour; m = bj.minute
    h_open = park["hours"]["open"]; h_close = park["hours"]["close"]; cmin = park["hours"].get("closeMinute", 0)
    if h < h_open: return False
    if h > h_close: return False
    if h == h_close and m > cmin: return False
    return True

def _try_fetch(uuid):
    url = API_BASE.format(uuid=uuid)
    # 优先 curl（避免某些环境的 SSL 问题）
    try:
        import subprocess
        out = subprocess.run(["curl","-4","-s","--ssl-no-revoke","--connect-timeout","10","--max-time","12",
                              "-H","User-Agent: Mozilla/5.0", url],
                             capture_output=True, text=True, timeout=16).stdout
        if out and out.strip():
            return json.loads(out)
    except Exception:
        pass
    # 回退 urllib
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_live(uuid):
    # 一次重试，降低 Cloudflare TLS 抖动导致的偶发失败
    try:
        return _try_fetch(uuid)
    except Exception:
        time.sleep(2)
        return _try_fetch(uuid)

def collect_one(park):
    try:
        api = fetch_live(park["uuid"])
        live = api.get("liveData") or []
        attractions = [{
            "name": it.get("name"),
            "waitTime": ((it.get("queue") or {}).get("STANDBY") or {}).get("waitTime", -1),
            "status": (it.get("status") or "unknown").lower(),
            "lastUpdated": it.get("lastUpdated") or ""
        } for it in live]
        bj = beijing_now()
        date_str = bj.strftime("%Y-%m-%d"); time_str = bj.strftime("%H:%M")
        point = {
            "park": park["id"], "date": date_str, "time": time_str,
            "attractions": attractions,
            "allCount": len(attractions),
            "openCount": sum(1 for a in attractions if a["status"] == "operating"),
            "timestamp": bj.isoformat()
        }
        push(point)
        print(f"  [OK] {park['name']}: {len(attractions)} 项, {point['openCount']} 开放 @ {time_str}")
    except Exception as e:
        print(f"  [FAIL] {park['name']}: {e}")

def push(point):
    url = f"{SERVER}/api/relay"
    data = json.dumps(point).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type":"application/json",
                                           "x-relay-token": RELAY_TOKEN})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError(f"relay HTTP {r.status}")

def main():
    args = sys.argv[1:]
    loop = "--loop" in args
    only = None
    for a in args:
        if a.startswith("--park"):
            only = a.split("=",1)[-1] if "=" in a else (args[args.index(a)+1] if args.index(a)+1 < len(args) else None)
    targets = [p for p in PARKS if (only is None or p["id"] == only)]
    if not targets:
        print("未匹配到乐园:", only); sys.exit(1)
    while True:
        bj = beijing_now()
        print(f"\n===== 采集 {bj.strftime('%Y-%m-%d %H:%M')} (北京)  目标 {len(targets)} 个 =====")
        for p in targets:
            if not within_hours(p):
                print(f"  [skip] {p['name']} 不在采集窗口")
                continue
            collect_one(p)
        if not loop:
            break
        # 对齐到下一个 :00/:10/:20 ... 整 10 分钟
        now = time.time()
        sleep_to = (int(now // 600) + 1) * 600 - now + 1
        print(f"  休眠 {int(sleep_to)}s 至下一采集点...")
        time.sleep(sleep_to)

if __name__ == "__main__":
    main()
