#!/usr/bin/env python3
"""Convert LoRa position measurements to the dataset layout used by BLE."""

from __future__ import annotations

import argparse
import csv
import glob
import math
import random
from pathlib import Path


REQUIRED_COLUMNS = {
    "pose_x",
    "pose_y",
    "mean_rssi_dbm",
    "valid_measurement",
    "transmitter_id",
    "transmitter_x",
    "transmitter_y",
    "transmitter_z",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build gateway_position.yml, gateway_rssi.csv, tx_pos.csv, "
        "train_index.txt, and test_index.txt from LoRa measurement CSV files."
    )
    parser.add_argument(
        "--input-glob",
        default="./data/20260*/position_measurements.csv",
        help="Glob for source CSV files (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("lora_rssi"),
        help="Destination directory (default: %(default)s)",
    )
    parser.add_argument(
        "--receiver-z",
        type=float,
        default=0.470,
        help="TurtleBot antenna height used in tx_pos.csv, in metres (default: %(default)s)",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=None,
        help="Number of test samples (default: 20%% of all valid samples)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for reproducible index shuffling (default: %(default)s)",
    )
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Include rows whose valid_measurement value is false",
    )
    return parser.parse_args()


def is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def finite_float(row: dict[str, str], column: str, source: Path, line: int) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{source}:{line}: invalid {column!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{source}:{line}: non-finite {column!r}")
    return value


def load_measurements(
    paths: list[Path], include_invalid: bool
) -> tuple[list[tuple[float, float, float]], dict[str, tuple[float, float, float]]]:
    samples: list[tuple[float, float, float]] = []
    transmitters: dict[str, tuple[float, float, float]] = {}

    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")

            for line, row in enumerate(reader, start=2):
                if not include_invalid and not is_true(row["valid_measurement"]):
                    continue

                transmitter_id = row["transmitter_id"].strip()
                if not transmitter_id:
                    raise ValueError(f"{path}:{line}: empty transmitter_id")
                transmitter_position = tuple(
                    finite_float(row, column, path, line)
                    for column in ("transmitter_x", "transmitter_y", "transmitter_z")
                )
                previous = transmitters.setdefault(transmitter_id, transmitter_position)
                if previous != transmitter_position:
                    raise ValueError(
                        f"{path}:{line}: inconsistent position for {transmitter_id}: "
                        f"{transmitter_position} != {previous}"
                    )

                samples.append(
                    (
                        finite_float(row, "pose_x", path, line),
                        finite_float(row, "pose_y", path, line),
                        finite_float(row, "mean_rssi_dbm", path, line),
                    )
                )

    if not samples:
        raise ValueError("No measurement rows matched the requested criteria")
    return samples, transmitters


def format_number(value: float) -> str:
    return format(value, ".15g")


def write_dataset(
    output_dir: Path,
    samples: list[tuple[float, float, float]],
    transmitters: dict[str, tuple[float, float, float]],
    receiver_z: float,
    test_size: int | None,
    seed: int,
) -> None:
    if test_size is None:
        test_size = round(len(samples) * 0.20)
    if test_size < 0 or test_size > len(samples):
        raise ValueError(f"--test-size must be between 0 and {len(samples)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "gateway_position.yml").open("w", encoding="utf-8") as handle:
        for transmitter_id in sorted(transmitters):
            coordinates = ", ".join(format_number(v) for v in transmitters[transmitter_id])
            handle.write(f"{transmitter_id}: [{coordinates}]\n")

    with (output_dir / "gateway_rssi.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["RSSI_LoRa_Mean"])
        writer.writerows((format_number(rssi),) for _, _, rssi in samples)

    with (output_dir / "tx_pos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["x", "y", "z"])
        writer.writerows(
            (format_number(x), format_number(y), format_number(receiver_z))
            for x, y, _ in samples
        )

    indices = list(range(len(samples)))
    random.Random(seed).shuffle(indices)
    test_indices = indices[:test_size]
    train_indices = indices[test_size:]
    (output_dir / "train_index.txt").write_text(
        "".join(f"{index}\n" for index in train_indices), encoding="utf-8"
    )
    (output_dir / "test_index.txt").write_text(
        "".join(f"{index}\n" for index in test_indices), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    paths = [Path(path) for path in sorted(glob.glob(args.input_glob))]
    if not paths:
        raise SystemExit(f"No files matched {args.input_glob!r}")

    samples, transmitters = load_measurements(paths, args.include_invalid)
    write_dataset(
        args.output_dir,
        samples,
        transmitters,
        args.receiver_z,
        args.test_size,
        args.seed,
    )
    print(
        f"Wrote {len(samples)} samples from {len(paths)} files and "
        f"{len(transmitters)} transmitter(s) to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
