#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
from pathlib import Path

import requests
import yaml
from flask import Flask, g, jsonify, request, Response

from jms_to_clash import convert_url_to_clash_config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("access")

CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_subscriptions() -> tuple[dict, str | None]:
    if not CONFIG_PATH.exists():
        return {}, None

    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return {}, f"failed to load config.yaml: {e}"

    subscriptions = data.get("subscriptions", {})
    if not isinstance(subscriptions, dict):
        return {}, "invalid config.yaml: subscriptions must be an object"

    normalized = {}
    for k, v in subscriptions.items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip():
            return {}, "invalid config.yaml: subscription id/url must be non-empty string"
        normalized[k.strip()] = v.strip()

    return normalized, None


SUBSCRIPTIONS, CONFIG_ERROR = load_subscriptions()


def get_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",", 1)[0].strip()
    return request.remote_addr or "-"


@app.before_request
def before_request() -> None:
    g.start_time = time.perf_counter()


@app.after_request
def after_request(response):
    started = getattr(g, "start_time", None)
    duration_ms = 0
    if started is not None:
        duration_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "ip=%s method=%s path=%s status=%s duration_ms=%s",
        get_client_ip(),
        request.method,
        request.path,
        response.status_code,
        duration_ms,
    )
    return response


def convert_by_url(url: str, ua: str, output_format: str = "yaml"):
    if output_format not in {"yaml", "json"}:
        return jsonify({"error": "output_format must be 'yaml' or 'json'"}), 400

    try:
        clash_cfg = convert_url_to_clash_config(url, ua)
    except requests.RequestException as e:
        return jsonify({"error": f"failed to fetch subscription: {e}"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception:
        return jsonify({"error": "internal server error"}), 500

    if output_format == "json":
        return jsonify({"proxies_count": len(clash_cfg.get("proxies", [])), "config": clash_cfg})

    yaml_text = yaml.safe_dump(clash_cfg, allow_unicode=True, sort_keys=False)
    return Response(yaml_text, content_type="text/yaml; charset=utf-8")


@app.get("/api/v1/convert/<id>")
def convert_by_id(id: str):
    if CONFIG_ERROR:
        return jsonify({"error": CONFIG_ERROR}), 500

    ua = request.args.get("ua", "clash-converter/1.0")
    output_format = request.args.get("output_format", "yaml").lower()

    url = SUBSCRIPTIONS.get(id)
    if not url:
        return jsonify({"error": f"invalid id: {id}"}), 400

    return convert_by_url(url, ua, output_format)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9527)
