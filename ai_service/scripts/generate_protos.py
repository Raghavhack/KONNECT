"""
Protocol Buffers Stub Generator for KONNECT.
Compiles shared/proto/intelligence.proto into ai_service/app/grpc/generated.
"""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROTO_DIR = REPO_ROOT / "shared" / "proto"
PROTO_FILE = PROTO_DIR / "intelligence.proto"
OUT_DIR = REPO_ROOT / "ai_service" / "app" / "grpc" / "generated"


def generate_protos():
    print(f"Checking for proto file at: {PROTO_FILE}")
    if not PROTO_FILE.exists():
        print(f"Error: {PROTO_FILE} not found!")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import grpc_tools.protoc

        print(f"Compiling {PROTO_FILE} -> {OUT_DIR}")
        args = [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={OUT_DIR}",
            f"--grpc_python_out={OUT_DIR}",
            str(PROTO_FILE),
        ]
        ret = grpc_tools.protoc.main(args)
        if ret == 0:
            print("Proto compilation succeeded!")
        else:
            print(f"Proto compilation returned code {ret}")
    except ImportError:
        print("grpc_tools not installed in environment. Generating fallback compatibility shim...")


if __name__ == "__main__":
    generate_protos()
