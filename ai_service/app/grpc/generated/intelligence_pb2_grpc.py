"""
Python gRPC Service and Stub definitions for konnect.intelligence.v1.
"""

import grpc
from . import intelligence_pb2


class IntelligenceServiceServicer:
    """Base servicer interface for IntelligenceService."""

    def ParseDocument(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def UpdateKnowledgeGraph(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def StreamGraphUpdates(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def Query(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def InvalidateCache(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def BenchmarkLatency(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def CheckHealth(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


class IntelligenceServiceStub:
    """Client stub for connecting to IntelligenceService."""

    def __init__(self, channel):
        self.ParseDocument = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/ParseDocument",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.UpdateKnowledgeGraph = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/UpdateKnowledgeGraph",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.StreamGraphUpdates = channel.unary_stream(
            "/konnect.intelligence.v1.IntelligenceService/StreamGraphUpdates",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.Query = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/Query",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.InvalidateCache = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/InvalidateCache",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.BenchmarkLatency = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/BenchmarkLatency",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )
        self.CheckHealth = channel.unary_unary(
            "/konnect.intelligence.v1.IntelligenceService/CheckHealth",
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )


def add_IntelligenceServiceServicer_to_server(servicer, server):
    # Registration method
    rpc_method_handlers = {
        "ParseDocument": grpc.unary_unary_rpc_method_handler(
            servicer.ParseDocument,
        ),
        "UpdateKnowledgeGraph": grpc.unary_unary_rpc_method_handler(
            servicer.UpdateKnowledgeGraph,
        ),
        "StreamGraphUpdates": grpc.unary_stream_rpc_method_handler(
            servicer.StreamGraphUpdates,
        ),
        "Query": grpc.unary_unary_rpc_method_handler(
            servicer.Query,
        ),
        "InvalidateCache": grpc.unary_unary_rpc_method_handler(
            servicer.InvalidateCache,
        ),
        "BenchmarkLatency": grpc.unary_unary_rpc_method_handler(
            servicer.BenchmarkLatency,
        ),
        "CheckHealth": grpc.unary_unary_rpc_method_handler(
            servicer.CheckHealth,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "konnect.intelligence.v1.IntelligenceService", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))
