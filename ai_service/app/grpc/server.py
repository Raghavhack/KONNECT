"""
gRPC Server Manager.
Handles thread pool configuration, port binding, and graceful shutdown.
"""

import logging
from concurrent import futures
from typing import Optional

try:
    import grpc
    GRPC_AVAILABLE = True
except ImportError:
    grpc = None
    GRPC_AVAILABLE = False

from .servicer import IntelligenceServicer
from .generated import intelligence_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)


class GRPCServer:
    """Manages the gRPC server lifecycle."""

    def __init__(
        self,
        servicer: IntelligenceServicer,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
    ):
        self.servicer = servicer
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.server = None

    def start(self) -> None:
        if not GRPC_AVAILABLE:
            logger.warning("grpc library not available. gRPC server will not start.")
            return

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.max_workers))
        pb2_grpc.add_IntelligenceServiceServicer_to_server(self.servicer, self.server)
        bind_address = f"{self.host}:{self.port}"
        self.server.add_insecure_port(bind_address)
        self.server.start()
        logger.info(f"gRPC Intelligence Server running on {bind_address}")

    def stop(self, grace: Optional[int] = 5) -> None:
        if self.server:
            logger.info("Stopping gRPC server...")
            self.server.stop(grace)
            logger.info("gRPC server stopped.")
