import argparse
import yaml
import logging
from pathlib import Path
from core.clip_orchestrator import PyPongAIClipOrchestrator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("pypongai_capture", {})

def main():
    parser = argparse.ArgumentParser(description="Capture PyPongAI Gameplay Clips")
    parser.add_argument("--mode", type=str, choices=["gen_0_vs_gen_50", "progression", "test"],
                        default="test", help="Recording mode")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    parser.add_argument("--generations", type=int, default=50, help="Max generations for progression mode")
    parser.add_argument("--sample-every", type=int, default=10, help="Sampling interval for progression mode")
    parser.add_argument("--no-ipc", action="store_true", help="Disable IPC-based recording")
    parser.add_argument("--debug", action="store_true", help="Show verbose logs (including game output)")
    
    parser.add_argument("--game-path", type=str, help="Path to PyPongAI repository")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug logging enabled.")
    
    # Load config
    config_file = Path("config.yaml")
    base_config = load_config(config_file)
    
    # Overrides
    if args.output_dir:
        base_config["output_dir"] = args.output_dir
    if args.game_path:
        base_config["game_path"] = args.game_path
    
    ipc_enabled = base_config.get("ipc_enabled", True) and not args.no_ipc
    
    orchestrator = PyPongAIClipOrchestrator(base_config)
    
    # Select recording method
    record_func = orchestrator.record_match_with_ipc if ipc_enabled else orchestrator.record_match
    
    logger.info(f"Starting auto-capture in mode: {args.mode} (IPC: {ipc_enabled})")
    
    if args.mode == "test":
        result = record_func("test_run", model_name="test_model")
        logger.info(f"Test Result: {result}")
    
    elif args.mode == "gen_0_vs_gen_50":
        # Note: we manually call record_func twice for comparison or use the orchestrator helper
        # If using helper, it should be updated to honor ipc_enabled.
        # Let's just do it manually here for maximum control in this script.
        logger.info("Recording Gen 0...")
        gen_0 = record_func("gen_0_random_sample", model_name="gen_0")
        
        logger.info("Recording Gen 50...")
        gen_50 = record_func("gen_50_champion_sample", model_name="gen_50")
        
        logger.info(f"Hero Features Results: gen_0={bool(gen_0)}, gen_50={bool(gen_50)}")
    
    elif args.mode == "progression":
        results = []
        for gen in range(0, args.generations + 1, args.sample_every):
            logger.info(f"Recording generation {gen}...")
            meta = record_func(f"gen_{gen}_sample", model_name=f"gen_{gen}")
            if meta:
                results.append(meta)
        logger.info(f"Progression Results: {len(results)} clips recorded.")

if __name__ == "__main__":
    main()
