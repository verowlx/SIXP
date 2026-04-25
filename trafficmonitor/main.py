from __future__ import annotations

from snmp_monitor import monitor_interface_bandwidth


def _ask(prompt: str, cast_func, default=None):
    while True:
        raw = input(
            f"{prompt}" + (f" [{default}]" if default is not None else "") + ": "
        ).strip()
        if raw == "" and default is not None:
            return default
        try:
            return cast_func(raw)
        except ValueError:
            print("Invalid value, please try again.")


def main() -> None:
    print("SNMP Interface Bandwidth Monitor")
    print("-" * 32)

    host = input("Host/IP: ").strip()
    community = input("SNMP community: ").strip()
    if_index = _ask("Interface index (ifIndex)", int)
    interval_seconds = _ask("Sampling interval in seconds", float, 5.0)
    port = _ask("SNMP port", int, 161)
    timeout = _ask("Timeout (seconds)", int, 2)
    retries = _ask("Retries", int, 1)

    sample = monitor_interface_bandwidth(
        host=host,
        community=community,
        if_index=if_index,
        interval_seconds=interval_seconds,
        port=port,
        timeout=timeout,
        retries=retries,
    )

    print("\nResult:")
    print(f"in_bps: {sample.in_bps:.2f}")
    print(f"out_bps: {sample.out_bps:.2f}")
    print(f"interface_speed_bps: {sample.interface_speed_bps}")
    print(f"in_utilization_pct: {sample.in_utilization_pct:.2f}")
    print(f"out_utilization_pct: {sample.out_utilization_pct:.2f}")
    print(f"interval_seconds: {sample.interval_seconds:.3f}")


if __name__ == "__main__":
    main()
