import argparse
import asyncio
import logging
import os
import signal
import sys

import uvicorn

from data_gen.simulator.config import SimulatorConfig
from data_gen.simulator.engine import FileMetricExporter, SimulatorEngine

logger = logging.getLogger(__name__)

CONFIG_YAML = os.path.join(os.path.dirname(__file__), "default_config.yml")

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

def load_config(path: str) -> SimulatorConfig:
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f)
    return SimulatorConfig(**data)

async def run_standalone(config: SimulatorConfig, output: str, duration: int) -> None:
    engine = SimulatorEngine(config)
    exporter = FileMetricExporter(output)
    engine.on_metric(exporter)

    logger.info(f"Standalone mode: writing metrics to {output} for {duration}s")

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown requested")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    task = asyncio.create_task(engine.run())

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=duration if duration > 0 else None)
    except asyncio.TimeoutError:
        pass
    finally:
        engine.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        exporter.close()

    logger.info(f"Standalone mode finished")

async def run_server(config: SimulatorConfig) -> None:
    engine = SimulatorEngine(config)
    asyncio.create_task(engine.run())

    from data_gen.simulator.api import create_app
    app = create_app(engine)

    config_obj = uvicorn.Config(
        app,
        host=config.listen_host,
        port=config.listen_port,
        log_level="info",
    )
    server = uvicorn.Server(config_obj)
    logger.info(f"Server mode: listening on {config.listen_host}:{config.listen_port}")
    await server.serve()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Server Simulator — realistic server behavior emulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run as API server (default):
  python -m data_gen.simulator --config data_gen/simulator/default_config.yml

  # Standalone mode: generate 1 hour of data to file:
  python -m data_gen.simulator --standalone --output metrics.jsonl --duration 3600

  # Custom config with verbose logging:
  python -m data_gen.simulator -c my_config.yml -v
        """,
    )
    parser.add_argument(
        "-c", "--config",
        default=CONFIG_YAML,
        help=f"Path to config YAML (default: {CONFIG_YAML})",
    )
    parser.add_argument(
        "-s", "--standalone",
        action="store_true",
        help="Run in standalone mode (no HTTP server)",
    )
    parser.add_argument(
        "-o", "--output",
        default="simulator_output.jsonl",
        help="Output file path (standalone mode)",
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=0,
        help="Duration in seconds for standalone mode (0 = infinite)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    config = load_config(args.config)
    logger.info(f"Config loaded from {args.config}")

    if args.standalone:
        asyncio.run(run_standalone(config, args.output, args.duration))
    else:
        asyncio.run(run_server(config))

if __name__ == "__main__":
    main()
