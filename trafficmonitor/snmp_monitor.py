"""SNMP-based interface bandwidth monitor."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Tuple

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)


# Interface MIB OIDs
IF_SPEED_OID = "1.3.6.1.2.1.2.2.1.5"  # ifSpeed (bps)
IF_IN_OCTETS_32_OID = "1.3.6.1.2.1.2.2.1.10"  # ifInOctets
IF_OUT_OCTETS_32_OID = "1.3.6.1.2.1.2.2.1.16"  # ifOutOctets
IF_HC_IN_OCTETS_64_OID = "1.3.6.1.2.1.31.1.1.1.6"  # ifHCInOctets
IF_HC_OUT_OCTETS_64_OID = "1.3.6.1.2.1.31.1.1.1.10"  # ifHCOutOctets


@dataclass
class BandwidthSample:
    in_bps: float
    out_bps: float
    interface_speed_bps: int
    in_utilization_pct: float
    out_utilization_pct: float
    interval_seconds: float


def _snmp_get_int(
    host: str,
    community: str,
    oid: str,
    if_index: int,
    port: int,
    timeout: int,
    retries: int,
) -> int:
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),  # SNMP v2c
        UdpTransportTarget((host, port), timeout=timeout, retries=retries),
        ContextData(),
        ObjectType(ObjectIdentity(f"{oid}.{if_index}")),
    )
    error_indication, error_status, error_index, var_binds = next(iterator)
    if error_indication:
        raise RuntimeError(f"SNMP error: {error_indication}")
    if error_status:
        raise RuntimeError(
            f"SNMP error at index {error_index}: {error_status.prettyPrint()}"
        )
    return int(var_binds[0][1])


def _read_counters(
    host: str,
    community: str,
    if_index: int,
    port: int,
    timeout: int,
    retries: int,
) -> Tuple[int, int, int]:
    """Return in_octets, out_octets, max_counter_value."""
    try:
        in_octets = _snmp_get_int(
            host, community, IF_HC_IN_OCTETS_64_OID, if_index, port, timeout, retries
        )
        out_octets = _snmp_get_int(
            host, community, IF_HC_OUT_OCTETS_64_OID, if_index, port, timeout, retries
        )
        return in_octets, out_octets, (2**64 - 1)
    except RuntimeError:
        # Fallback for devices that only expose 32-bit octet counters.
        in_octets = _snmp_get_int(
            host, community, IF_IN_OCTETS_32_OID, if_index, port, timeout, retries
        )
        out_octets = _snmp_get_int(
            host, community, IF_OUT_OCTETS_32_OID, if_index, port, timeout, retries
        )
        return in_octets, out_octets, (2**32 - 1)


def monitor_interface_bandwidth(
    host: str,
    community: str,
    if_index: int,
    interval_seconds: float = 5.0,
    port: int = 161,
    timeout: int = 2,
    retries: int = 1,
) -> BandwidthSample:
    """
    Monitor interface utilization by sampling SNMP octet counters.

    Returns a single sampled window (interval_seconds) with in/out bps values.
    """
    interface_speed_bps = _snmp_get_int(
        host, community, IF_SPEED_OID, if_index, port, timeout, retries
    )
    in_1, out_1, max_counter = _read_counters(
        host, community, if_index, port, timeout, retries
    )
    t1 = time.time()
    time.sleep(interval_seconds)
    in_2, out_2, _ = _read_counters(host, community, if_index, port, timeout, retries)
    t2 = time.time()

    elapsed = max(t2 - t1, 1e-6)
    delta_in = in_2 - in_1 if in_2 >= in_1 else (max_counter - in_1 + in_2 + 1)
    delta_out = out_2 - out_1 if out_2 >= out_1 else (max_counter - out_1 + out_2 + 1)

    in_bps = (delta_in * 8) / elapsed
    out_bps = (delta_out * 8) / elapsed
    in_utilization = (in_bps / interface_speed_bps) * 100 if interface_speed_bps else 0
    out_utilization = (
        (out_bps / interface_speed_bps) * 100 if interface_speed_bps else 0
    )

    return BandwidthSample(
        in_bps=in_bps,
        out_bps=out_bps,
        interface_speed_bps=interface_speed_bps,
        in_utilization_pct=in_utilization,
        out_utilization_pct=out_utilization,
        interval_seconds=elapsed,
    )


def sample_as_dict(
    host: str,
    community: str,
    if_index: int,
    interval_seconds: float = 5.0,
) -> Dict[str, float]:
    """Convenience wrapper that returns plain dict output."""
    sample = monitor_interface_bandwidth(
        host=host,
        community=community,
        if_index=if_index,
        interval_seconds=interval_seconds,
    )
    return {
        "in_bps": sample.in_bps,
        "out_bps": sample.out_bps,
        "interface_speed_bps": float(sample.interface_speed_bps),
        "in_utilization_pct": sample.in_utilization_pct,
        "out_utilization_pct": sample.out_utilization_pct,
        "interval_seconds": sample.interval_seconds,
    }
