#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import base64
import json
import re
import urllib.parse
from typing import List, Dict

import requests
import yaml


def b64_decode_maybe(data: str) -> str:
    """
    尝试把订阅内容当作 Base64 解码（很多订阅是这种格式）
    """
    raw = data.strip()
    # 如果已经是明文链接行，直接返回
    if "://" in raw:
        return raw

    # 去掉空白和换行后再尝试解码
    compact = re.sub(r"\s+", "", raw)
    padding = "=" * (-len(compact) % 4)

    try:
        decoded = base64.urlsafe_b64decode(compact + padding).decode("utf-8", errors="ignore")
        if "://" in decoded:
            return decoded
    except Exception:
        pass

    # 解码失败就原样返回
    return raw


def parse_ss_link(link: str, idx: int) -> Dict:
    """
    解析 ss:// 链接为 Clash 节点格式
    支持两种常见写法：
    1) ss://base64(method:password@host:port)#name
    2) ss://method:password@host:port#name  (少见)
    """
    link = link.strip()
    if not link.startswith("ss://"):
        raise ValueError("not ss link")

    no_scheme = link[len("ss://"):]

    # 先拆 fragment（节点名）
    if "#" in no_scheme:
        main, frag = no_scheme.split("#", 1)
        name = urllib.parse.unquote(frag) or f"JMS-{idx}"
    else:
        main, name = no_scheme, f"JMS-{idx}"

    # 再拆 query（plugin 参数）
    if "?" in main:
        main, query = main.split("?", 1)
        query_dict = urllib.parse.parse_qs(query)
    else:
        query_dict = {}

    # main 可能是 base64，也可能是明文 method:password@host:port
    userinfo_hostport = main
    if "@" not in userinfo_hostport:
        # 尝试 base64 解码
        padding = "=" * (-len(userinfo_hostport) % 4)
        decoded = base64.urlsafe_b64decode(userinfo_hostport + padding).decode("utf-8", errors="ignore")
        userinfo_hostport = decoded

    # 现在应为 method:password@host:port
    if "@" not in userinfo_hostport:
        raise ValueError(f"invalid ss payload: {userinfo_hostport}")

    userinfo, hostport = userinfo_hostport.rsplit("@", 1)
    if ":" not in userinfo:
        raise ValueError(f"invalid userinfo: {userinfo}")
    method, password = userinfo.split(":", 1)

    if ":" not in hostport:
        raise ValueError(f"invalid hostport: {hostport}")
    server, port_str = hostport.rsplit(":", 1)

    proxy = {
        "name": name,
        "type": "ss",
        "server": server.strip("[]"),  # 兼容 IPv6 [] 形式
        "port": int(port_str),
        "cipher": method,
        "password": password,
        "udp": True,
    }

    # 尝试处理 plugin（如 obfs）
    # 常见格式: plugin=obfs-local;obfs=tls;obfs-host=xxx.com
    plugin_vals = query_dict.get("plugin", [])
    if plugin_vals:
        plugin_raw = urllib.parse.unquote(plugin_vals[0])
        parts = plugin_raw.split(";")
        if parts:
            plugin_name = parts[0]
            opts = {}
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    opts[k] = v
            # Clash 常见写法
            proxy["plugin"] = plugin_name
            if opts:
                proxy["plugin-opts"] = opts

    return proxy


def parse_vmess_link(link: str, idx: int) -> Dict:
    """
    解析 vmess://base64(json) 链接为 Clash 节点格式
    常见字段：ps, add, port, id, aid, net, type, host, path, tls, sni
    """
    link = link.strip()
    if not link.startswith("vmess://"):
        raise ValueError("not vmess link")

    payload = link[len("vmess://"):].strip()
    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8", errors="ignore")
    cfg = json.loads(decoded)

    name = cfg.get("ps") or f"JMS-VMESS-{idx}"
    server = cfg.get("add")
    port = int(cfg.get("port", 0))
    uuid = cfg.get("id")
    aid = int(cfg.get("aid", 0))
    network = (cfg.get("net") or "tcp").lower()
    host = cfg.get("host") or ""
    path = cfg.get("path") or ""
    tls_flag = str(cfg.get("tls") or "").lower()
    sni = cfg.get("sni") or ""

    if not server or not port or not uuid:
        raise ValueError("vmess missing required fields(add/port/id)")

    proxy = {
        "name": name,
        "type": "vmess",
        "server": server,
        "port": port,
        "uuid": uuid,
        "alterId": aid,
        "cipher": "auto",
        "udp": True,
        "network": network,
    }

    # vmess JSON 里的 type（常见为 none）不是 Clash 节点顶层 type，不能覆盖 "vmess"
    # 这里不直接写入，避免出现 type: none

    if tls_flag in ("tls", "1", "true"):
        proxy["tls"] = True
        if sni:
            proxy["servername"] = sni

    if network == "ws":
        ws_opts = {}
        if path:
            ws_opts["path"] = path
        if host:
            ws_opts["headers"] = {"Host": host}
        if ws_opts:
            proxy["ws-opts"] = ws_opts
    elif network == "h2":
        h2_opts = {}
        if host:
            h2_opts["host"] = [h.strip() for h in host.split(",") if h.strip()]
        if path:
            h2_opts["path"] = path
        if h2_opts:
            proxy["h2-opts"] = h2_opts
    elif network == "grpc":
        grpc_opts = {}
        if path:
            grpc_opts["grpc-service-name"] = path
        if grpc_opts:
            proxy["grpc-opts"] = grpc_opts

    return proxy


def convert_subscription_to_clash(sub_text: str) -> List[Dict]:
    decoded = b64_decode_maybe(sub_text)
    lines = [x.strip() for x in decoded.splitlines() if x.strip()]
    proxies = []

    for i, line in enumerate(lines, start=1):
        if line.startswith("ss://"):
            try:
                proxies.append(parse_ss_link(line, i))
            except Exception as e:
                print(f"[WARN] 第 {i} 行 ss 解析失败: {e}")
        elif line.startswith("vmess://"):
            try:
                proxies.append(parse_vmess_link(line, i))
            except Exception as e:
                print(f"[WARN] 第 {i} 行 vmess 解析失败: {e}")
        else:
            print(f"[WARN] 第 {i} 行暂不支持，已跳过: {line[:60]}...")

    return proxies


def build_clash_config(proxies: List[Dict]) -> Dict:
    names = [p["name"] for p in proxies]
    return {
        "mixed-port": 1087,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "PROXY",
                "type": "select",
                "proxies": names if names else ["DIRECT"],
            }
        ],
        "rules": [
            "GEOIP,CN,DIRECT",
            "MATCH,PROXY"
        ],
    }


def fetch_subscription_text(url: str, ua: str = "clash-converter/1.0") -> str:
    resp = requests.get(url, timeout=20, headers={"User-Agent": ua})
    resp.raise_for_status()
    return resp.text


def convert_url_to_clash_config(url: str, ua: str = "clash-converter/1.0") -> Dict:
    sub_text = fetch_subscription_text(url, ua)
    proxies = convert_subscription_to_clash(sub_text)
    if not proxies:
        raise ValueError("没有解析到可用节点（目前脚本支持 ss:// 与 vmess://）")
    return build_clash_config(proxies)


def main():
    parser = argparse.ArgumentParser(description="Convert JustMySocks subscription to Clash YAML")
    parser.add_argument("-u", "--url", required=True, help="订阅地址")
    parser.add_argument("-o", "--output", default="clash.yaml", help="输出文件名，默认 clash.yaml")
    parser.add_argument("--ua", default="clash-converter/1.0", help="HTTP User-Agent")
    args = parser.parse_args()

    try:
        clash_cfg = convert_url_to_clash_config(args.url, args.ua)
    except ValueError as e:
        raise SystemExit(str(e))

    with open(args.output, "w", encoding="utf-8") as f:
        yaml.safe_dump(clash_cfg, f, allow_unicode=True, sort_keys=False)

    print(f"转换完成：{args.output}，共 {len(clash_cfg['proxies'])} 个节点")


if __name__ == "__main__":
    main()
