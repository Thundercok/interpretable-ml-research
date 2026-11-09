"""
rat.app — Application routing and lifecycle coordination.
"""

from rat.app.router import route_request, run_resident_app

__all__ = ["route_request", "run_resident_app"]
